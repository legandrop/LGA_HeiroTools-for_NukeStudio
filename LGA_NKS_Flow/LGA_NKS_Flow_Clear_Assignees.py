"""
________________________________________________________________

  LGA_NKS_Flow_Clear_Assignees v1.2 | Lega Pugliese
  Elimina los asignados de una tarea en ShotGrid (Flow) a partir del base_name
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
    QSizePolicy,
)
from PySide2.QtGui import QFont

# Agregar la ruta actual al sys.path para importar SecureConfig_Reader
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from SecureConfig_Reader import get_flow_credentials

# Variable global para debug
DEBUG = False

debug_messages = []


def debug_print(message):
    if DEBUG:
        debug_messages.append(str(message))


def print_debug_messages():
    if DEBUG and debug_messages:
        print("\n".join(debug_messages))
        debug_messages.clear()


def get_user_info_from_config(user_name=None):
    """
    Obtiene información del usuario desde el archivo de configuración.
    Para Clear Assignees, no tenemos usuario específico, así que usamos valores genéricos.

    Args:
        user_name (str): Nombre del usuario (opcional)

    Returns:
        tuple: (display_name, color)
    """
    try:
        if user_name:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "LGA_NKS_Flow_Users.json"
            )

            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    users = config.get("users", [])

                    for user in users:
                        if user.get("name") == user_name:
                            return user.get("name", user_name), user.get(
                                "color", "#666666"
                            )

            # Si no se encuentra, usar valores por defecto
            return user_name, "#666666"
        else:
            # Para Clear Assignees, usar valores genéricos
            return "System", "#B85450"

    except Exception as e:
        debug_print(f"Error leyendo configuración de usuarios: {e}")
        return user_name or "System", "#666666"


# Clase de ventana de estado para mostrar progreso de limpiar asignados en Flow
class FlowStatusWindow(QDialog):
    def __init__(
        self, user_name, user_color, task_type="limpiar asignados", parent=None
    ):
        super(FlowStatusWindow, self).__init__(parent)
        self.setWindowTitle("Flow | Clear Assignees")
        self.setModal(False)  # Cambiar a no modal para evitar problemas
        self.setMinimumWidth(500)
        self.setMinimumHeight(150)  # Establecer una altura minima
        self.setSizePolicy(
            QSizePolicy.Preferred, QSizePolicy.Fixed
        )  # Permitir que se ajuste horizontalmente, pero fija verticalmente

        # Evitar que la ventana se cierre automáticamente
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        # Layout principal
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Etiqueta de estado inicial con formato HTML para múltiples colores
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setTextFormat(Qt.RichText)  # Habilitar formato HTML

        font = QFont()
        font.setPointSize(10)
        self.status_label.setFont(font)
        self.status_label.setStyleSheet("padding: 0px;")

        layout.addWidget(self.status_label)

        # Etiqueta para mostrar el shot que se está procesando
        self.shot_label = QLabel("")
        self.shot_label.setAlignment(Qt.AlignLeft)
        self.shot_label.setWordWrap(True)
        self.shot_label.setTextFormat(Qt.RichText)
        self.shot_label.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        layout.addWidget(self.shot_label)

        # Etiqueta para mensajes de resultado
        self.result_label = QLabel("")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setWordWrap(True)
        self.result_label.setTextFormat(Qt.RichText)
        layout.addWidget(self.result_label)

        # Espaciador
        layout.addStretch()

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
        # Restar 20px de la altura para hacer la ventana mas compacta
        current_height = self.height()
        new_height = max(0, current_height + 5)
        self.setFixedHeight(new_height)

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
        debug_print("Inicializando conexion a ShotGrid para eliminar asignados")
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
            [
                "content",
                "is",
                task_name_lower,
            ],  # ShotGrid parece distinguir mayus/minus en 'is'
        ]
        fields_task = ["id", "content"]
        tasks = self.sg.find("Task", filters_task, fields_task)

        # Fallback si no encuentra por 'is', intenta con 'contains' o iterando
        if not tasks:
            filters_task_all = [["entity", "is", {"type": "Shot", "id": shot_id}]]
            fields_task_all = ["id", "content"]
            all_tasks = self.sg.find("Task", filters_task_all, fields_task_all)
            for task in all_tasks:
                if task["content"].lower() == task_name_lower:
                    tasks = [task]
                    break

        if tasks:
            task_id = tasks[0]["id"]
            debug_print(f"Task encontrada: {tasks[0]['content']} (ID: {task_id})")
            return shot_code_found, task_id
        else:
            debug_print(
                f"No se encontro la tarea '{task_name_lower}' para el shot {shot_code_found}."
            )
            return shot_code_found, None

    def clear_task_assignees(self, task_id):
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return False, "Conexion a ShotGrid no inicializada"
        try:
            debug_print(f"Eliminando asignados de la tarea ID: {task_id}")
            result = self.sg.update("Task", task_id, {"task_assignees": []})
            if result:
                debug_print(
                    f"Asignados eliminados exitosamente para la tarea {task_id}"
                )
                return True, f"Asignados eliminados para la tarea ID {task_id}"
            else:
                debug_print(f"Fallo al eliminar asignados para la tarea {task_id}")
                return False, f"Fallo al actualizar la tarea ID {task_id}"
        except Exception as e:
            debug_print(f"Error al eliminar los asignados de la tarea: {e}")
            return False, f"Error al eliminar asignados: {e}"


class WorkerSignals(QObject):
    shot_info_ready = Signal(str, str)  # shot_name, task_name
    finished = Signal(bool, str)  # success, message
    error = Signal(str)


class ClearAssigneeWorker(QRunnable):
    def __init__(self, base_name, status_window):
        super(ClearAssigneeWorker, self).__init__()
        self.base_name = base_name
        self.status_window = status_window
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            debug_print("=== Iniciando limpieza de asignados ===")

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

            # Extraer datos del base_name
            project_name = self.base_name.split("_")[0]
            parts = self.base_name.split("_")
            shot_code = "_".join(parts[:5])
            # Extraer nombre de la tarea
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
            task_name = parts[version_index - 1].lower()  # Asegurarse que sea lowercase

            # Emitir información del shot y task
            self.signals.shot_info_ready.emit(shot_code, task_name)

            debug_print(
                f"Buscando shot y tarea para el proyecto: {project_name}, Shot: {shot_code}, Tarea: {task_name}"
            )
            shot_name_found, task_id = sg_manager.find_shot_and_task_id(
                project_name, shot_code, task_name
            )
            shot_name = shot_name_found if shot_name_found else shot_code

            if not task_id:
                self.signals.error.emit(
                    f"No se encontro la tarea '{task_name}' para el shot {shot_name}."
                )
                return

            debug_print(
                f"Task ID encontrado: {task_id}. Intentando eliminar asignados..."
            )
            success, message = sg_manager.clear_task_assignees(task_id)

            if success:
                self.signals.finished.emit(
                    True,
                    f"Asignados eliminados exitosamente de {shot_name}/{task_name}",
                )
            else:
                self.signals.error.emit(message)

        except Exception as e:
            debug_print(f"Error en ClearAssigneeWorker: {e}")
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


def clear_task_assignees_from_base_name(base_name):
    """
    Función principal del script de limpiar asignados.

    Args:
        base_name (str): Nombre base del clip
    """
    global _status_window

    debug_print("=== Iniciando LGA_NKS_Flow_Clear_Assignees ===")

    # Obtener información genérica para la ventana (no hay usuario específico)
    user_display_name, user_color = get_user_info_from_config()

    # Crear aplicación Qt si no existe
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    # Crear y mostrar ventana de estado
    _status_window = FlowStatusWindow(
        user_display_name, user_color, "limpiar asignados"
    )
    _status_window.show()
    _status_window.show_processing_message()  # Mostrar mensaje de procesamiento

    # Crear worker para procesamiento en hilo separado
    worker = ClearAssigneeWorker(base_name, _status_window)

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

    # Ejecutar el worker en un hilo separado
    QThreadPool.globalInstance().start(worker)

    debug_print("=== Worker iniciado en hilo separado ===")


if __name__ == "__main__":
    import sys

    # Asegurarse que QApplication exista si se ejecuta standalone
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)

    if len(sys.argv) < 2:
        print("Uso: python LGA_NKS_Flow_Clear_Assignees.py <base_name>")
    else:
        base_name_arg = sys.argv[1]
        clear_task_assignees_from_base_name(base_name_arg)
        # Mantener la aplicacion corriendo si es necesario para que el dialogo aparezca
        if "__main__" == __name__ and not QApplication.instance():
            sys.exit(app.exec_())  # Solo si no hay instancia previa
