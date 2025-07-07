"""
_____________________________________________________________

  LGA_NKS_Flow_Assignee v1.2 | Lega Pugliese
  Imprime los asignados de una tarea en ShotGrid (Flow) a partir del base_name
  Se usa desde el panel de assignee de LGA_NKS_Flow_Assignee_Panel.py
_____________________________________________________________
"""

import os
import re
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
    Para Get Assignees, no tenemos usuario específico, así que usamos valores genéricos.

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
            # Para Get Assignees, usar valores genéricos
            return "System", "#4A90A4"

    except Exception as e:
        debug_print(f"Error leyendo configuración de usuarios: {e}")
        return user_name or "System", "#666666"


# Clase de ventana de estado para mostrar progreso de obtener asignados en Flow
class FlowStatusWindow(QDialog):
    def __init__(
        self, user_name, user_color, task_type="obtener asignados", parent=None
    ):
        super(FlowStatusWindow, self).__init__(parent)
        self.setWindowTitle("Flow | Assignees")
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

        layout.addWidget(self.status_label)

        # Etiqueta para mostrar el shot que se está procesando
        self.shot_label = QLabel("")
        self.shot_label.setAlignment(Qt.AlignLeft)
        self.shot_label.setWordWrap(True)
        self.shot_label.setTextFormat(Qt.RichText)
        self.shot_label.setStyleSheet("padding-left: 10px; padding-right: 10px;")
        layout.addWidget(self.shot_label)

        # Etiqueta para mostrar los asignados encontrados
        self.assignees_label = QLabel("")
        self.assignees_label.setAlignment(Qt.AlignLeft)
        self.assignees_label.setWordWrap(True)
        self.assignees_label.setTextFormat(Qt.RichText)
        self.assignees_label.setStyleSheet(
            "padding-left: 10px; padding-right: 10px; padding-top: 10px;"
        )
        layout.addWidget(self.assignees_label)

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
        shot_html += f"<span style='color: #CCCCCC; '>Shot: </span><span style='color: #6AB5CA; '>{shot_name}</span>"
        if task_name:
            shot_html += f"<br><span style='color: #CCCCCC; '>Task: </span><span style='color: #B56AB5; '>{task_name}</span>"
        shot_html += "</div>"
        self.shot_label.setText(shot_html)
        self._adjust_window_size()

    def update_assignees_info(self, assignees):
        """Actualiza la ventana con los asignados encontrados usando sus colores"""
        if assignees:
            assignees_html = "<div style='text-align: left;'>"
            assignees_html += (
                "<span style='color: #CCCCCC; '>Asignados encontrados:</span><br>"
            )
            for user in assignees:
                user_name = user.get("name", "Sin nombre")
                user_color = self._get_user_color(user_name)
                assignees_html += f"<span style='color: #CCCCCC; background-color: {user_color}; padding: 2px 4px; margin: 1px; border-radius: 3px;'>{user_name}</span><br>"
            assignees_html += "</div>"
        else:
            assignees_html = "<span style='color: #C0C0C0; '>No se encontraron asignados para esta tarea</span>"

        self.assignees_label.setText(assignees_html)
        self._adjust_window_size()

    def _get_user_color(self, user_name):
        """Obtiene el color del usuario desde la configuración"""
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
                            return user.get("color", "#666666")

            # Si no se encuentra, usar color por defecto
            return "#666666"

        except Exception as e:
            debug_print(f"Error leyendo configuración de usuarios: {e}")
            return "#666666"

    def show_processing_message(self):
        """Muestra el mensaje de procesamiento"""
        processing_html = f"<span style='color: #CCCCCC; '>Conectando a Flow Production Tracking...</span>"
        self.result_label.setText(processing_html)
        self.result_label.setStyleSheet("padding: 10px;")
        self._adjust_window_size()

    def show_success(self, message):
        """Limpia el mensaje de resultado en caso de éxito y habilita el botón de cierre"""
        self.result_label.setText("")  # Borrar el mensaje
        self.result_label.setStyleSheet(
            ""
        )  # Borrar el estilo para que no quede el padding
        self.status_label.setText("")  # Borrar el mensaje de procesamiento
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
        debug_print("Inicializando conexion a ShotGrid")
        try:
            self.sg = shotgun_api3.Shotgun(url, login=login, password=password)
            debug_print("Conexion a ShotGrid inicializada exitosamente")
        except Exception as e:
            debug_print(f"Error al inicializar la conexion a ShotGrid: {e}")
            self.sg = None

    def find_shot_and_tasks(self, project_name, shot_code):
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return None, None, None
        debug_print(f"Buscando proyecto con nombre: {project_name}")
        try:
            projects = self.sg.find(
                "Project", [["name", "is", project_name]], ["id", "name"]
            )
        except Exception as e:
            debug_print(f"Error buscando proyecto: {e}")
            return None, None, None
        if projects:
            project_id = projects[0]["id"]
            filters = [
                ["project", "is", {"type": "Project", "id": project_id}],
                ["code", "is", shot_code],
            ]
            fields = ["id", "code", "description"]
            shots = self.sg.find("Shot", filters, fields)
            if shots:
                shot_id = shots[0]["id"]
                debug_print(f"Shot encontrado: {shots[0]['code']} (ID: {shot_id})")
                tasks = self.find_tasks_for_shot(shot_id)
                return projects[0], shots[0], tasks
            else:
                debug_print("No se encontro el Shot con el codigo especificado.")
                return None, None, None
        else:
            debug_print("No se encontro el proyecto con el nombre especificado.")
            return None, None, None

    def find_tasks_for_shot(self, shot_id):
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return []
        filters = [["entity", "is", {"type": "Shot", "id": shot_id}]]
        fields = ["id", "content", "sg_status_list"]
        return self.sg.find("Task", filters, fields)

    def get_task_assignees(self, task_id):
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return []
        try:
            task = self.sg.find_one("Task", [["id", "is", task_id]], ["task_assignees"])
            if task and task["task_assignees"]:
                return task["task_assignees"]
            else:
                debug_print(f"No hay asignados para la tarea {task_id}")
                return []
        except Exception as e:
            debug_print(f"Error al obtener los asignados de la tarea: {e}")
            return []


class WorkerSignals(QObject):
    shot_info_ready = Signal(str, str)  # shot_name, task_name
    assignees_ready = Signal(list)  # assignees list
    finished = Signal(bool, str)  # success, message
    error = Signal(str)


class AssigneeWorker(QRunnable):
    def __init__(self, base_name, status_window):
        super(AssigneeWorker, self).__init__()
        self.base_name = base_name
        self.status_window = status_window
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            debug_print("=== Iniciando obtención de asignados ===")

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

            # Extraer datos del base_name igual que en el script de push
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
            task_name = parts[version_index - 1].lower()

            # Emitir información del shot y task
            self.signals.shot_info_ready.emit(shot_code, task_name)

            debug_print(
                f"Buscando shot y tareas para el proyecto: {project_name}, Shot: {shot_code}"
            )
            project, shot, tasks = sg_manager.find_shot_and_tasks(
                project_name, shot_code
            )
            if not tasks:
                self.signals.error.emit("No se encontraron tareas para el shot.")
                return
            # Buscar el task_id correcto
            task_id = None
            for task in tasks:
                if task["content"].lower() == task_name:
                    task_id = task["id"]
                    break
            if not task_id:
                self.signals.error.emit(
                    f"No se encontro la tarea '{task_name}' para el shot."
                )
                return
            debug_print(f"Task ID encontrado: {task_id}")
            # Obtener los asignados
            assignees = sg_manager.get_task_assignees(task_id)
            shot_name = shot.get("code", "-") if shot else shot_code

            # Emitir los asignados encontrados
            self.signals.assignees_ready.emit(assignees)

            # Emitir mensaje de finalización exitosa
            count = len(assignees) if assignees else 0
            self.signals.finished.emit(
                True, f"Se encontraron {count} asignado(s) para {shot_name}/{task_name}"
            )

        except Exception as e:
            debug_print(f"Error en AssigneeWorker: {e}")
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


def show_task_assignees_from_base_name(base_name):
    """
    Función principal del script de obtener asignados.

    Args:
        base_name (str): Nombre base del clip
    """
    global _status_window

    debug_print("=== Iniciando LGA_NKS_Flow_Assignee ===")

    # Obtener información genérica para la ventana (no hay usuario específico)
    user_display_name, user_color = get_user_info_from_config()

    # Crear aplicación Qt si no existe
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    # Crear y mostrar ventana de estado
    _status_window = FlowStatusWindow(
        user_display_name, user_color, "obtener asignados"
    )
    _status_window.show()
    _status_window.show_processing_message()  # Mostrar mensaje de procesamiento

    # Crear worker para procesamiento en hilo separado
    worker = AssigneeWorker(base_name, _status_window)

    # Conectar señales
    worker.signals.shot_info_ready.connect(
        lambda shot_name, task_name, window=_status_window: window.update_shot_info(
            shot_name, task_name
        )
    )
    worker.signals.assignees_ready.connect(
        lambda assignees, window=_status_window: window.update_assignees_info(assignees)
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

    if len(sys.argv) < 2:
        print("Uso: python LGA_NKS_Flow_Assignee.py <base_name>")
    else:
        base_name = sys.argv[1]
        show_task_assignees_from_base_name(base_name)
