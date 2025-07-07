"""
________________________________________________________________

  LGA_NKS_Flow_Assign_Assignee v1.2 | Lega Pugliese
  Asigna un usuario a una tarea en ShotGrid (Flow) a partir del base_name y nombre de usuario
________________________________________________________________
"""

import os
import sys
import json
import shotgun_api3
from PySide2.QtCore import QRunnable, Slot, QThreadPool, Signal, QObject, Qt
from PySide2.QtWidgets import (
    QApplication,
    QMessageBox,
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
)
from PySide2.QtGui import QFont

# Agregar la ruta actual al sys.path para importar SecureConfig_Reader
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from SecureConfig_Reader import get_flow_credentials

DEBUG = False
debug_messages = []


def debug_print(message):
    if DEBUG:
        debug_messages.append(str(message))


def print_debug_messages():
    if DEBUG and debug_messages:
        print("\n".join(debug_messages))
        debug_messages.clear()


def get_user_info_from_config(user_name):
    """
    Obtiene información del usuario desde el archivo de configuración.

    Args:
        user_name (str): Nombre del usuario en Flow

    Returns:
        tuple: (user_name, user_color) o (user_name, "#666666") si no se encuentra
    """
    try:
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "LGA_NKS_Flow_Users.json"
        )

        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                users = config.get("users", [])

                for user in users:
                    if user.get("name") == user_name:
                        return user.get("name", user_name), user.get("color", "#666666")

        # Si no se encuentra, usar valores por defecto
        return user_name, "#666666"

    except Exception as e:
        debug_print(f"Error leyendo configuración de usuarios: {e}")
        return user_name, "#666666"


# Clase de ventana de estado para mostrar progreso de asignación en Flow
class FlowStatusWindow(QDialog):
    def __init__(self, user_name, user_color, task_type="asignar usuario", parent=None):
        super(FlowStatusWindow, self).__init__(parent)
        self.setWindowTitle("Flow | Assign User")
        self.setModal(False)  # Cambiar a no modal para evitar problemas
        self.setMinimumWidth(500)

        # Evitar que la ventana se cierre automáticamente
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        # Layout principal
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Etiqueta de estado inicial con formato HTML para múltiples colores
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setTextFormat(Qt.RichText)  # Habilitar formato HTML

        # Mensaje inicial
        if task_type == "asignar usuario":
            task_text = "Asignando usuario"
        elif task_type == "obtener asignados":
            task_text = "Obteniendo asignados"
        elif task_type == "limpiar asignados":
            task_text = "Limpiando asignados"
        else:
            task_text = "Procesando"

        initial_message = (
            f"<div style='text-align: left;'>"
            f"<span style='color: #CCCCCC; '>{task_text} </span>"
            f"<span style='color: #CCCCCC; background-color: {user_color}; '>{user_name}</span>"
            f"</div>"
        )

        font = QFont()
        font.setPointSize(10)
        self.status_label.setFont(font)
        self.status_label.setText(initial_message)
        self.status_label.setStyleSheet("padding: 10px;")

        layout.addWidget(self.status_label)

        # Etiqueta para mostrar el shot que se está procesando
        self.shot_label = QLabel("")
        self.shot_label.setAlignment(Qt.AlignLeft)
        self.shot_label.setWordWrap(True)
        self.shot_label.setTextFormat(Qt.RichText)
        self.shot_label.setStyleSheet("padding: 10px;")
        layout.addWidget(self.shot_label)

        # Etiqueta para mensajes de resultado
        self.result_label = QLabel("")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setWordWrap(True)
        self.result_label.setTextFormat(Qt.RichText)
        layout.addWidget(self.result_label)

        # Espaciador
        # layout.addStretch()

        # Botón de Close
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        self.close_button.setEnabled(
            False
        )  # Deshabilitado hasta que termine el procesamiento
        layout.addWidget(self.close_button)

    def update_shot_info(self, shot_name, task_name=None):
        """Actualiza la ventana con el shot que se está procesando"""
        shot_html = "<div style='text-align: left;'>"
        shot_html += f"<span style='color: #CCCCCC; '>Shot:</span> <span style='color: #6AB5CA; '>{shot_name}</span>"
        if task_name:
            shot_html += f"<br><span style='color: #CCCCCC; '>Task:</span> <span style='color: #B56AB5; '>{task_name}</span>"
        shot_html += "</div>"
        self.shot_label.setText(shot_html)
        self._adjust_window_size()

    def show_processing_message(self):
        """Muestra el mensaje de procesamiento"""
        processing_html = f"<span style='color: #CCCCCC; '>Conectando a Flow Production Tracking...</span>"
        self.result_label.setText(processing_html)
        self.result_label.setStyleSheet("padding: 10px;")
        self._adjust_window_size()

    def show_success(self, message):
        """Muestra mensaje de éxito en verde"""
        success_html = f"<span style='color: #00ff00; '>{message}</span>"
        self.result_label.setText(success_html)
        self.result_label.setStyleSheet("padding: 10px;")
        self.close_button.setEnabled(True)  # Habilitar botón de Close
        self._adjust_window_size()

    def show_error(self, message):
        """Muestra mensaje de error en rojo"""
        error_html = f"<span style='color: #C05050; '>{message}</span>"
        self.result_label.setText(error_html)
        self.result_label.setStyleSheet("padding: 10px;")
        self.close_button.setEnabled(True)  # Habilitar botón de Close
        self._adjust_window_size()

    def _adjust_window_size(self):
        """Ajusta el tamaño de la ventana basándose en el contenido"""
        self.adjustSize()
        self.updateGeometry()

    def closeEvent(self, event):
        """
        Manejar el evento de cierre para evitar que se cierre automáticamente.
        Solo se cierra cuando el usuario hace clic en el botón Close o cuando ya terminó el procesamiento.
        """
        if not self.close_button.isEnabled():
            # Si el botón Close está deshabilitado, significa que aún está procesando
            # No permitir cerrar la ventana
            event.ignore()
        else:
            # Si el botón está habilitado, permitir cerrar
            event.accept()


class ShotGridManager:
    def __init__(self, url, login, password):
        debug_print("Inicializando conexion a ShotGrid para asignar usuario")
        try:
            self.sg = shotgun_api3.Shotgun(url, login=login, password=password)
            debug_print("Conexion a ShotGrid inicializada exitosamente")
        except Exception as e:
            debug_print(f"Error al inicializar la conexion a ShotGrid: {e}")
            self.sg = None

    def find_shot_and_task_id(self, project_name, shot_code, task_name_lower):
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return None, None
        debug_print(f"Buscando proyecto con nombre: {project_name}")
        try:
            projects = self.sg.find(
                "Project", [["name", "is", project_name]], ["id", "name"]
            )
        except Exception as e:
            debug_print(f"Error buscando proyecto: {e}")
            return None, None
        if not projects:
            debug_print("No se encontro el proyecto con el nombre especificado.")
            return None, None
        project_id = projects[0]["id"]
        filters_shot = [
            ["project", "is", {"type": "Project", "id": project_id}],
            ["code", "is", shot_code],
        ]
        fields_shot = ["id", "code"]
        shots = self.sg.find("Shot", filters_shot, fields_shot)
        if not shots:
            debug_print("No se encontro el Shot con el codigo especificado.")
            return None, None
        shot_id = shots[0]["id"]
        shot_code_found = shots[0]["code"]
        debug_print(f"Shot encontrado: {shot_code_found} (ID: {shot_id})")
        filters_task = [
            ["entity", "is", {"type": "Shot", "id": shot_id}],
            ["content", "is", task_name_lower],
        ]
        fields_task = ["id", "content", "task_assignees"]
        tasks = self.sg.find("Task", filters_task, fields_task)
        if not tasks:
            filters_task_all = [["entity", "is", {"type": "Shot", "id": shot_id}]]
            fields_task_all = ["id", "content", "task_assignees"]
            all_tasks = self.sg.find("Task", filters_task_all, fields_task_all)
            for task in all_tasks:
                if task["content"].lower() == task_name_lower:
                    tasks = [task]
                    break
        if tasks:
            task = tasks[0]
            debug_print(f"Task encontrada: {task['content']} (ID: {task['id']})")
            return shot_code_found, task
        else:
            debug_print(
                f"No se encontro la tarea '{task_name_lower}' para el shot {shot_code_found}."
            )
            return shot_code_found, None

    def find_user_by_name(self, user_name):
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return None
        try:
            users = self.sg.find(
                "HumanUser", [["name", "is", user_name]], ["id", "name"]
            )
            if users:
                debug_print(
                    f"Usuario encontrado: {users[0]['name']} (ID: {users[0]['id']})"
                )
                return users[0]
            else:
                debug_print(f"No se encontro el usuario '{user_name}' en ShotGrid.")
                return None
        except Exception as e:
            debug_print(f"Error buscando usuario: {e}")
            return None

    def add_assignee_to_task(self, task_id, current_assignees, user):
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return False, "Conexion a ShotGrid no inicializada"
        try:
            # Evitar duplicados
            assignees = current_assignees or []
            if any(u["id"] == user["id"] for u in assignees):
                debug_print(f"El usuario ya es asignado de la tarea.")
                return True, "El usuario ya estaba asignado a la tarea."
            new_assignees = assignees + [user]
            result = self.sg.update("Task", task_id, {"task_assignees": new_assignees})
            if result:
                debug_print(f"Usuario asignado exitosamente a la tarea {task_id}")
                return True, f"Usuario asignado exitosamente."
            else:
                debug_print(f"Fallo al asignar usuario a la tarea {task_id}")
                return False, f"Fallo al actualizar la tarea."
        except Exception as e:
            debug_print(f"Error al asignar usuario: {e}")
            return False, f"Error al asignar usuario: {e}"


class WorkerSignals(QObject):
    shot_info_ready = Signal(str, str)  # shot_name, task_name
    finished = Signal(bool, str)  # success, message
    error = Signal(str)


class AssignAssigneeWorker(QRunnable):
    def __init__(self, base_name, user_name, status_window):
        super(AssignAssigneeWorker, self).__init__()
        self.base_name = base_name
        self.user_name = user_name
        self.status_window = status_window
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            debug_print(f"=== Iniciando asignación para usuario: {self.user_name} ===")

            # Obtener credenciales de Flow DENTRO del worker
            sg_url, sg_login, sg_password = get_flow_credentials_secure()
            if not all([sg_url, sg_login, sg_password]):
                self.signals.error.emit(
                    "No se pudieron obtener las credenciales de Flow desde SecureConfig."
                )
                return

            # Crear manager ShotGrid DENTRO del worker
            sg_manager = ShotGridManager(sg_url, sg_login, sg_password)
            if not sg_manager.sg:
                self.signals.error.emit(
                    "No se pudo inicializar la conexión a ShotGrid."
                )
                return

            project_name = self.base_name.split("_")[0]
            parts = self.base_name.split("_")
            shot_code = "_".join(parts[:5])
            version_number_str = None
            for part in parts:
                if part.startswith("v") and part[1:].isdigit():
                    version_number_str = part
                    break
            if not version_number_str:
                self.signals.error.emit(
                    "Error: No se encontro un numero de version valido en el nombre base."
                )
                return
            version_index = parts.index(version_number_str)
            task_name = parts[version_index - 1].lower()

            # Emitir información del shot y task
            self.signals.shot_info_ready.emit(shot_code, task_name)

            debug_print(
                f"Buscando shot y tarea para el proyecto: {project_name}, Shot: {shot_code}, Tarea: {task_name}"
            )
            shot_name_found, task = sg_manager.find_shot_and_task_id(
                project_name, shot_code, task_name
            )
            shot_name = shot_name_found if shot_name_found else shot_code
            if not task:
                self.signals.error.emit(
                    f"No se encontro la tarea '{task_name}' para el shot {shot_name}."
                )
                return
            user = sg_manager.find_user_by_name(self.user_name)
            if not user:
                self.signals.error.emit(
                    f"No se encontro el usuario '{self.user_name}' en ShotGrid."
                )
                return
            current_assignees = task.get("task_assignees", [])
            success, message = sg_manager.add_assignee_to_task(
                task["id"], current_assignees, user
            )

            if success:
                self.signals.finished.emit(
                    True,
                    f"Usuario '{self.user_name}' asignado exitosamente a {shot_name}/{task_name}",
                )
            else:
                self.signals.error.emit(message)

        except Exception as e:
            debug_print(f"Error en AssignAssigneeWorker: {e}")
            self.signals.error.emit(f"Error: {str(e)}")


def get_flow_credentials_secure():
    sg_url, sg_login, sg_password = get_flow_credentials()
    if not sg_url or not sg_login or not sg_password:
        debug_print(
            "No se pudieron obtener las credenciales de Flow desde SecureConfig."
        )
        return None, None, None

    # Para Flow, usamos login directo en lugar de API key
    return sg_url, sg_login, sg_password


# Variable global para mantener referencia a la ventana
_status_window = None


def assign_assignee_to_task(base_name, user_name):
    """
    Función principal del script de asignación.

    Args:
        base_name (str): Nombre base del clip
        user_name (str): Nombre del usuario a asignar
    """
    global _status_window

    debug_print(
        f"=== Iniciando LGA_NKS_Flow_Assign_Assignee para usuario: {user_name} ==="
    )

    # Obtener información del usuario para la ventana
    user_display_name, user_color = get_user_info_from_config(user_name)

    # Crear aplicación Qt si no existe
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    # Crear y mostrar ventana de estado
    _status_window = FlowStatusWindow(user_display_name, user_color, "asignar usuario")
    _status_window.show()
    _status_window.show_processing_message()  # Mostrar mensaje de procesamiento

    # Crear worker para procesamiento en hilo separado
    worker = AssignAssigneeWorker(base_name, user_name, _status_window)

    # Conectar señales
    worker.signals.shot_info_ready.connect(
        lambda shot_name, task_name, window=_status_window: window.update_shot_info(
            shot_name, task_name
        )
    )
    worker.signals.finished.connect(
        lambda success, message, window=_status_window: window.show_success(message)
    )
    worker.signals.error.connect(
        lambda error_msg, window=_status_window: window.show_error(error_msg)
    )

    # Ejecutar en hilo separado
    QThreadPool.globalInstance().start(worker)

    debug_print("=== Worker iniciado en hilo separado ===")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Uso: python LGA_NKS_Flow_Assign_Assignee.py <base_name> <user_name>")
    else:
        base_name = sys.argv[1]
        user_name = sys.argv[2]
        assign_assignee_to_task(base_name, user_name)
