"""
____________________________________________________________________

  LGA_NKS_Flow_Assignee v1.26 | Lega

  Imprime los asignados de una tarea en ShotGrid (Flow) a partir del base_name.
  Se usa desde el panel de assignee de LGA_NKS_Assignee_Panel.py
  Actualizado para ser compatible con ambos sistemas de nomenclatura:
  - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
  - PROYECTO_SEQ_SHOT (3 bloques simplificado)

  v1.26: los usuarios salen de la DB de PipeSync (tabla flow_users), no del JSON local.
  v1.25: Recibe file_path desde el panel para extraer project_name desde el
         segmento VFX-NOMBRE del path (corrige proyectos como PROJALT con
         prefijo PROJA en el filename). Normaliza default_task para aliases
         (compo → comp) evitando pre-selección incorrecta en el diálogo.
  v1.24: Actualiza la UI para mostrar las tasks y los asignados en Flow.
         Funciona con todas las tasks disponibles en Flow.
  v1.23: Actualiza la base de datos local pipesync.db con la asignación
____________________________________________________________________
"""

import os
import re
import sys
import json
# Importar compatibilidad Qt para Hiero Panels
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt
from LGA_NKS_Shared.LGA_NKS_Flow_Users_Config import find_user_by_name

# Reasignar clases para compatibilidad con código existente
QRunnable = QtCore.QRunnable
Slot = QtCore.Slot
QThreadPool = QtCore.QThreadPool
Signal = QtCore.Signal
QObject = QtCore.QObject
QTimer = QtCore.QTimer

QApplication = QtWidgets.QApplication
QMessageBox = QtWidgets.QMessageBox
QDialog = QtWidgets.QDialog
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton
QCheckBox = QtWidgets.QCheckBox
QWidget = QtWidgets.QWidget

QFont = QtGui.QFont

# Agregar la ruta actual al sys.path para importar SecureConfig_Reader
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "LGA_NKS_Shared"))
import shotgun_api3

from SecureConfig_Reader import get_flow_credentials
from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    extract_project_name_from_path,
    extract_task_name,
    normalize_task_name,
)
from LGA_NKS_Shared.LGA_NKS_Flow_Task_Config import (
    DEFAULT_TASK_NAME,
    get_task_color,
    sort_tasks_by_pipeline,
)

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


def prepare_tasks_for_selection(tasks):
    simplified = []
    for task in tasks or []:
        simplified.append(
            {
                "id": task.get("id"),
                "name": task.get("content", "Task"),
                "assignees": task.get("task_assignees", []),
            }
        )
    return sort_tasks_by_pipeline(simplified)


def get_user_info_from_config(user_name=None):
    """
    Obtiene nombre y color desde la DB de PipeSync (tabla flow_users).
    Para Get Assignees no hay usuario específico, así que usamos valores genéricos.

    Args:
        user_name (str): Nombre del usuario (opcional)

    Returns:
        tuple: (display_name, color)
    """
    try:
        if user_name:
            user = find_user_by_name(user_name)
            if user:
                return user["name"], user["color"]

            # Si no se encuentra, usar valores por defecto
            return user_name, "#666666"
        else:
            # Para Get Assignees, usar valores genéricos
            return "", "#4A90A4"

    except Exception as e:
        debug_print(f"Error leyendo configuración de usuarios: {e}")
        return user_name or "", "#666666"


# Clase de ventana de estado para mostrar progreso de obtener asignados en Flow
class FlowStatusWindow(QDialog):
    def __init__(
        self, user_name, user_color, task_type="obtener asignados", parent=None
    ):
        super(FlowStatusWindow, self).__init__(parent)
        self.setWindowTitle("Flow | Assignees")
        self.setModal(False)
        self.setMinimumWidth(540)
        self.setMinimumHeight(180)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        self._task_rows = []

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setTextFormat(Qt.RichText)
        task_text = "Obteniendo asignados" if task_type == "obtener asignados" else "Procesando"
        if user_name:
            initial_message = (
                f"<div style='text-align: left;'>"
                f"<span style='color: #CCCCCC;'>{task_text} </span>"
                f"<span style='color: #CCCCCC; background-color: {user_color};'>{user_name}</span>"
                f"</div>"
            )
        else:
            initial_message = (
                f"<div style='text-align: left;'>"
                f"<span style='color: #CCCCCC;'>{task_text}</span>"
                f"</div>"
            )
        font = QFont()
        font.setPointSize(10)
        self.status_label.setFont(font)
        self.status_label.setText(initial_message)
        self.status_label.setStyleSheet("padding: 10px;")
        layout.addWidget(self.status_label)

        self.shot_label = QLabel("")
        self.shot_label.setAlignment(Qt.AlignLeft)
        self.shot_label.setWordWrap(True)
        self.shot_label.setTextFormat(Qt.RichText)
        self.shot_label.setStyleSheet("padding: 10px;")
        layout.addWidget(self.shot_label)

        self.validation_label = QLabel("")
        self.validation_label.setAlignment(Qt.AlignLeft)
        self.validation_label.setWordWrap(True)
        self.validation_label.setTextFormat(Qt.RichText)
        self.validation_label.setStyleSheet("padding: 10px; color: #CCCCCC;")
        layout.addWidget(self.validation_label)

        self.task_widget = QWidget()
        self.task_widget_layout = QVBoxLayout()
        self.task_widget_layout.setContentsMargins(10, 0, 10, 0)
        self.task_widget_layout.setSpacing(4)
        self.task_widget.setLayout(self.task_widget_layout)
        self.task_widget.setVisible(False)
        layout.addWidget(self.task_widget)

        self.assignees_label = QLabel("")
        self.assignees_label.setAlignment(Qt.AlignLeft)
        self.assignees_label.setWordWrap(True)
        self.assignees_label.setTextFormat(Qt.RichText)
        self.assignees_label.setStyleSheet(
            "padding-left: 10px; padding-right: 10px; padding-top: 10px;"
        )
        layout.addWidget(self.assignees_label)

        self.result_label = QLabel("")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setWordWrap(True)
        self.result_label.setTextFormat(Qt.RichText)
        layout.addWidget(self.result_label)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.close_button)
        self.set_close_enabled(False)

    def update_shot_info(self, shot_name, task_name=None):
        shot_html = "<div style='text-align: left;'>"
        shot_html += f"<span style='color: #CCCCCC;'>Shot:</span> <span style='color: #6AB5CA;'>{shot_name}</span>"
        if task_name:
            shot_html += f"<br><span style='color: #CCCCCC;'>Task:</span> <span style='color: #B56AB5;'>{task_name}</span>"
        shot_html += "</div>"
        self.shot_label.setText(shot_html)
        self._adjust_window_size()

    def show_validation_message(self, shot_name):
        message = (
            f"Verificando en Flow que el shot <span style='color:#6AB5CA;'>{shot_name}</span> exista "
            "y recuperando sus tasks disponibles..."
        )
        self.validation_label.setText(message)
        self._adjust_window_size()

    def show_shot_not_found(self, shot_name):
        self.validation_label.setText(
            f"<span style='color:#C05050;'>El shot '{shot_name}' no existe en Flow Production Tracking.</span>"
        )
        self.show_error("No hay tareas para consultar.")

    def show_processing_message(self, custom_text=None):
        processing_html = custom_text or "<span style='color: #CCCCCC;'>Conectando a Flow Production Tracking...</span>"
        self.result_label.setText(processing_html)
        self.result_label.setStyleSheet("padding: 10px;")
        self.clear_validation_message()
        self._adjust_window_size()

    def _clear_task_rows(self):
        while self.task_widget_layout.count():
            child = self.task_widget_layout.takeAt(0)
            widget = child.widget()
            if widget:
                widget.deleteLater()
        self._task_rows = []

    def _create_task_row(self, task):
        row_widget = QWidget()
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_widget.setLayout(row_layout)

        checkbox = QCheckBox()
        checkbox.setChecked(True)
        checkbox.setEnabled(False)
        row_layout.addWidget(checkbox)

        name_label = QLabel(
            f"<span style='color:{get_task_color(task['name'])}; font-weight:bold;'>{task['name']}</span>"
        )
        name_label.setTextFormat(Qt.RichText)
        row_layout.addWidget(name_label)

        assignees_label = QLabel(self._format_assignees(task.get("assignees")))
        assignees_label.setTextFormat(Qt.RichText)
        assignees_label.setWordWrap(True)
        row_layout.addWidget(assignees_label, 1)

        return row_widget

    def _format_assignees(self, assignees):
        if not assignees:
            return "<span style='color:#888888;'>Sin asignados</span>"
        chips = []
        for user in assignees:
            user_name = user.get("name", "Sin nombre")
            chips.append(
                f"<span style='color:#CCCCCC; background-color:#2E2E2E; padding:2px 6px; border-radius:4px;'>{user_name}</span>"
            )
        return " ".join(chips)

    def display_tasks(self, tasks):
        self._clear_task_rows()
        if tasks:
            instruction = QLabel(
                "<span style='color:#CCCCCC;'>Tasks y asignados en Flow:</span>"
            )
            instruction.setWordWrap(True)
            self.task_widget_layout.addWidget(instruction)

        for task in tasks:
            row_widget = self._create_task_row(task)
            self.task_widget_layout.addWidget(row_widget)
            self._task_rows.append(row_widget)

        self.task_widget.setVisible(bool(tasks))
        self.assignees_label.setText("")
        self.set_close_enabled(True)
        self._adjust_window_size()

    def clear_status_message(self):
        self.status_label.clear()
        self._adjust_window_size()

    def clear_validation_message(self):
        self.validation_label.clear()
        self._adjust_window_size()

    def set_close_enabled(self, enabled):
        self.close_button.setEnabled(enabled)

    def update_assignees_info(self, tasks_with_assignees):
        if not tasks_with_assignees:
            self.assignees_label.setText(
                "<span style='color: #C0C0C0;'>No se encontraron asignados.</span>"
            )
            self.task_widget.setVisible(False)
            self.set_close_enabled(True)
            self._adjust_window_size()
            return

        self.display_tasks(tasks_with_assignees)

    def _get_user_color(self, user_name):
        try:
            user = find_user_by_name(user_name)
            return user["color"] if user else "#666666"
        except Exception as e:
            debug_print(f"Error leyendo usuarios de PipeSync: {e}")
            return "#666666"

    def show_success(self, message):
        self.result_label.setText(f"<span style='color: #00ff00;'>{message}</span>")
        self.result_label.setStyleSheet("padding: 10px;")
        self.set_close_enabled(True)
        self.clear_status_message()
        self.clear_validation_message()
        self._adjust_window_size()

    def show_error(self, message):
        self.result_label.setText(f"<span style='color: #C05050;'>{message}</span>")
        self.result_label.setStyleSheet("padding: 10px;")
        self.set_close_enabled(True)
        self._adjust_window_size()

    def _adjust_window_size(self):
        self.adjustSize()
        self.updateGeometry()

    def closeEvent(self, event):
        if not self.close_button.isEnabled():
            event.ignore()
        else:
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
        fields = ["id", "content", "task_assignees"]
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


class TaskFetchSignals(QObject):
    ready = Signal(dict)
    error = Signal(str)


class ShotTaskDiscoveryWorker(QRunnable):
    def __init__(self, base_name, file_path=None):
        super(ShotTaskDiscoveryWorker, self).__init__()
        self.base_name = base_name
        self.file_path = file_path
        self.signals = TaskFetchSignals()

    @Slot()
    def run(self):
        try:
            sg_url, sg_login, sg_password = get_flow_credentials_secure()
            if not all([sg_url, sg_login, sg_password]):
                self.signals.error.emit(
                    "No se pudieron obtener las credenciales de Flow desde SecureConfig."
                )
                return

            project_name = extract_project_name_from_path(self.file_path)
            if project_name:
                debug_print(f"Project name (from path): {project_name}")
            else:
                project_name = extract_project_name(self.base_name)
                debug_print(f"Project name (from filename fallback): {project_name}")
            shot_code = extract_shot_code(self.base_name)
            default_task = normalize_task_name(extract_task_name(self.base_name)) or DEFAULT_TASK_NAME

            sg_manager = ShotGridManager(sg_url, sg_login, sg_password)
            if not sg_manager.sg:
                self.signals.error.emit("No se pudo inicializar la conexión a ShotGrid.")
                return

            project, shot, tasks = sg_manager.find_shot_and_tasks(
                project_name, shot_code
            )
            if not project:
                self.signals.error.emit(
                    f"No se encontró el proyecto '{project_name}' en Flow."
                )
                return

            if not shot:
                payload = {
                    "project_name": project_name,
                    "shot_code": shot_code,
                    "shot_name": shot_code,
                    "shot_exists": False,
                    "tasks": [],
                    "default_task": default_task,
                }
                self.signals.ready.emit(payload)
                return

            payload = {
                "project_name": project_name,
                "shot_code": shot_code,
                "shot_name": shot.get("code", shot_code),
                "shot_exists": True,
                "tasks": prepare_tasks_for_selection(tasks),
                "default_task": default_task,
            }
            self.signals.ready.emit(payload)
        except Exception as exc:
            debug_print(f"Error en ShotTaskDiscoveryWorker: {exc}")
            self.signals.error.emit(f"Error verificando shot en Flow: {exc}")




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


def show_task_assignees_from_base_name(base_name, file_path=None):
    """
    Función principal del script de obtener asignados.

    Args:
        base_name (str): Nombre base del clip
        file_path (str): Ruta completa del clip (para extraer project_name desde VFX-NOMBRE)
    """
    global _status_window

    debug_print("=== Iniciando LGA_NKS_Flow_Assignee ===")

    # Obtener información genérica para la ventana (no hay usuario específico)
    user_display_name, user_color = get_user_info_from_config()

    # Crear aplicación Qt si no existe
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    shot_preview = extract_shot_code(base_name) or "-"

    _status_window = FlowStatusWindow(
        user_display_name, user_color, "obtener asignados"
    )
    _status_window.show()
    _status_window.show_validation_message(shot_preview)

    def handle_task_selection(payload):
        shot_name = payload.get("shot_name", shot_preview)
        _status_window.update_shot_info(shot_name)
        if not payload.get("shot_exists"):
            _status_window.show_shot_not_found(shot_name)
            return

        tasks = payload.get("tasks", [])
        _status_window.clear_status_message()
        _status_window.clear_validation_message()
        if not tasks:
            _status_window.show_error(
                "El shot existe pero no tiene tasks configuradas en Flow."
            )
            return

        _status_window.update_assignees_info(tasks)
        names = ", ".join(task["name"] for task in tasks)
        _status_window.show_success(
            f"Se listaron los asignados de {shot_name}/{names}"
        )

    discovery_worker = ShotTaskDiscoveryWorker(base_name, file_path=file_path)
    discovery_worker.signals.ready.connect(handle_task_selection)
    discovery_worker.signals.error.connect(
        lambda error_msg, window=_status_window: window.show_error(error_msg)
    )

    QThreadPool.globalInstance().start(discovery_worker)
    debug_print("=== Worker de descubrimiento iniciado ===")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Uso: python LGA_NKS_Flow_Assignee.py <base_name>")
    else:
        base_name = sys.argv[1]
        show_task_assignees_from_base_name(base_name)
