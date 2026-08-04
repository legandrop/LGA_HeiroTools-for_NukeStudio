"""
____________________________________________________________________

  LGA_NKS_Flow_Assign_Assignee v1.26 | Lega

  Asigna un usuario a una tarea en ShotGrid (Flow) a partir del base_name y nombre de usuario

  v1.26: los usuarios salen de la DB de PipeSync (tabla flow_users), no del JSON local.
  v1.25: Recibe file_path desde el panel para extraer project_name desde el
         segmento VFX-NOMBRE del path (corrige proyectos como PROJALT con
         prefijo PROJA en el filename). Normaliza default_task para aliases
         (compo → comp) evitando pre-selección incorrecta en el diálogo.
  v1.24: Actualiza la UI para mostrar las tasks y los asignados en Flow.
         Funciona con todas las tasks disponibles en Flow.
  v1.23: Actualiza la base de datos local pipesync.db con la asignación
  v1.22: Verifica y asigna automáticamente el proyecto al usuario si no lo tiene asignado
         antes de asignar la task comp
  v1.21: Actualizado para ser compatible con ambos sistemas de nomenclatura:
         - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
         - PROYECTO_SEQ_SHOT (3 bloques simplificado)
____________________________________________________________________
"""

import os
import sys
import json
import sqlite3
import platform
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
QSizePolicy = QtWidgets.QSizePolicy
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
from LGA_NKS_Shared.LGA_NKS_PipeSyncPaths import get_pipesync_db_path

DEBUG = False
debug_messages = []


class DBManager:
    """Clase simplificada para manejar operaciones con la base de datos SQLite local."""

    def __init__(self):
        self.db_path = get_pipesync_db_path("pipesync.db")

        if self.db_path and os.path.exists(self.db_path):
            try:
                self.conn = sqlite3.connect(self.db_path)
                self.conn.row_factory = sqlite3.Row
                debug_print(f"Conexión exitosa a la base de datos: {self.db_path}")
            except Exception as e:
                debug_print(f"Error al conectar a la base de datos: {e}")
                self.conn = None
        else:
            debug_print(f"DB file not found at path: {self.db_path}")
            self.conn = None

    def find_shot(self, project_name, shot_code):
        """Busca un shot por nombre y código en la base de datos."""
        if not self.conn:
            debug_print("No hay conexión a la base de datos")
            return None

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT s.* FROM shots s
                JOIN projects p ON s.project_id = p.id
                WHERE p.project_name = ? AND s.shot_name = ?
                """,
                (project_name, shot_code),
            )
            return cur.fetchone()
        except Exception as e:
            debug_print(
                f"Error al buscar shot {shot_code} en proyecto {project_name}: {e}"
            )
            return None

    def find_task(self, shot_id, task_name):
        """Busca una tarea específica por nombre y shot_id."""
        if not self.conn:
            debug_print("No hay conexión a la base de datos")
            return None

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT * FROM tasks
                WHERE shot_id = ? AND LOWER(task_type) = LOWER(?)
                """,
                (shot_id, task_name),
            )
            return cur.fetchone()
        except Exception as e:
            debug_print(
                f"Error al buscar tarea {task_name} para shot_id {shot_id}: {e}"
            )
            return None

    def add_task_assignment(self, task_id, assigned_to):
        """Añade una asignación de tarea en la base de datos local."""
        if not self.conn:
            debug_print("No hay conexión a la base de datos")
            return False

        try:
            cur = self.conn.cursor()
            # Primero verificar si ya existe la asignación
            cur.execute(
                "SELECT id FROM task_assignments WHERE task_id = ? AND assigned_to = ?",
                (task_id, assigned_to)
            )
            existing = cur.fetchone()

            if existing:
                debug_print(f"La asignación ya existe en la base de datos local")
                return True

            # Si no existe, insertar nueva asignación
            cur.execute(
                """
                INSERT INTO task_assignments (task_id, assigned_to)
                VALUES (?, ?)
                """,
                (task_id, assigned_to),
            )
            self.conn.commit()
            debug_print(
                f"Asignación añadida a la tarea local (ID: {task_id}) para: {assigned_to}"
            )
            return True
        except Exception as e:
            debug_print(f"Error al añadir asignación a la tarea local: {e}")
            return False

    def close(self):
        """Cierra la conexión a la base de datos."""
        if self.conn:
            self.conn.close()
            self.conn = None


def debug_print(message):
    if DEBUG:
        debug_messages.append(str(message))


def print_debug_messages():
    if DEBUG and debug_messages:
        print("\n".join(debug_messages))
        debug_messages.clear()


def prepare_tasks_for_selection(tasks):
    """Devuelve las tasks en un formato simplificado para la UI."""
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


def get_user_info_from_config(user_name):
    """
    Obtiene nombre y color desde la DB de PipeSync (tabla flow_users).

    Args:
        user_name (str): Nombre del usuario en Flow

    Returns:
        tuple: (user_name, user_color) o (user_name, "#666666") si no se encuentra
    """
    try:
        user = find_user_by_name(user_name)
        if user:
            return user["name"], user["color"]
        return user_name, "#666666"

    except Exception as e:
        debug_print(f"Error leyendo usuarios de PipeSync: {e}")
        return user_name, "#666666"


# Clase de ventana de estado para mostrar progreso de asignación en Flow
class FlowStatusWindow(QDialog):
    def __init__(self, user_name, user_color, task_type="asignar usuario", parent=None):
        super(FlowStatusWindow, self).__init__(parent)
        self.setWindowTitle("Flow | Assign User")
        self.setModal(False)
        self.setMinimumWidth(560)
        self.setMinimumHeight(220)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        self._task_rows = []
        self._task_confirm_callback = None

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setTextFormat(Qt.RichText)

        if task_type == "asignar usuario":
            task_text = "Asignando usuario"
        elif task_type == "obtener asignados":
            task_text = "Obteniendo asignados"
        elif task_type == "limpiar asignados":
            task_text = "Limpiando asignados"
        else:
            task_text = "Procesando"

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

        self.result_label = QLabel("")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setWordWrap(True)
        self.result_label.setTextFormat(Qt.RichText)
        layout.addWidget(self.result_label)

        self.action_button = QPushButton("Aplicar")
        self.action_button.setVisible(False)
        self.action_button.setEnabled(False)
        self.action_button.clicked.connect(self._handle_apply_clicked)
        layout.addWidget(self.action_button)

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
        message = (
            f"<span style='color:#C05050;'>El shot '{shot_name}' no existe en Flow Production Tracking.</span>"
        )
        self.validation_label.setText(message)
        self.show_error("No hay tareas para procesar.")

    def show_processing_message(self, custom_text=None):
        processing_html = custom_text or "<span style='color: #CCCCCC;'>Conectando a Flow Production Tracking...</span>"
        self.result_label.setText(processing_html)
        self.result_label.setStyleSheet("padding: 10px;")
        self.clear_validation_message()
        self._adjust_window_size()

    def present_task_selection(
        self,
        tasks,
        default_task=None,
        on_confirm=None,
        auto_confirm=False,
        action_label="Aplicar",
        enable_selection=True,
    ):
        self._task_confirm_callback = on_confirm if enable_selection else None
        self.action_button.setVisible(enable_selection)
        self.action_button.setText(action_label)
        self.action_button.setEnabled(enable_selection and bool(tasks))

        self._clear_task_rows()

        if tasks:
            instruction = QLabel(
                "<span style='color:#CCCCCC;'>Seleccioná las tasks a las que querés aplicar el cambio:</span>"
            )
            instruction.setWordWrap(True)
            self.task_widget_layout.addWidget(instruction)

        default_lower = default_task.lower() if default_task else DEFAULT_TASK_NAME.lower()
        for task in tasks:
            is_default = task["name"].lower() == default_lower
            row = self._create_task_row(task, is_default, enable_selection)
            self.task_widget_layout.addWidget(row["widget"])
            self._task_rows.append(row)

        if enable_selection and self._task_rows and not any(
            row["checkbox"].isChecked() for row in self._task_rows
        ):
            self._task_rows[0]["checkbox"].setChecked(True)

        self.task_widget.setVisible(bool(tasks))
        self._adjust_window_size()
        self.set_close_enabled(True)

        if auto_confirm and enable_selection and tasks:
            QTimer.singleShot(0, self._handle_apply_clicked)

    def _create_task_row(self, task, checked, enable_selection):
        row_widget = QWidget()
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        row_widget.setLayout(row_layout)

        checkbox = QCheckBox()
        checkbox.setChecked(checked)
        checkbox.setEnabled(enable_selection)
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

        return {"widget": row_widget, "checkbox": checkbox, "task": task, "assignees_label": assignees_label}

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

    def _clear_task_rows(self):
        while self.task_widget_layout.count():
            child = self.task_widget_layout.takeAt(0)
            widget = child.widget()
            if widget:
                widget.deleteLater()
        self._task_rows = []

    def lock_task_selection(self):
        for row in self._task_rows:
            row["checkbox"].setEnabled(False)
        self.action_button.setEnabled(False)

    def unlock_task_selection(self):
        for row in self._task_rows:
            row["checkbox"].setEnabled(True)
        self.action_button.setEnabled(True)

    def clear_status_message(self):
        self.status_label.clear()
        self._adjust_window_size()

    def clear_validation_message(self):
        self.validation_label.clear()
        self._adjust_window_size()

    def set_close_enabled(self, enabled):
        self.close_button.setEnabled(enabled)

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

    def _get_selected_tasks(self):
        selected = []
        for row in self._task_rows:
            if row["checkbox"].isChecked():
                selected.append(row["task"])
        return selected

    def _handle_apply_clicked(self):
        if not self._task_confirm_callback:
            return
        selected = self._get_selected_tasks()
        if not selected:
            self.show_error("Seleccioná al menos una task.")
            self.unlock_task_selection()
            return
        self.lock_task_selection()
        self.set_close_enabled(False)
        self._task_confirm_callback(selected)

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

    def find_project(self, project_name):
        if not self.sg:
            return None
        try:
            projects = self.sg.find(
                "Project", [["name", "is", project_name]], ["id", "name"]
            )
            return projects[0] if projects else None
        except Exception as e:
            debug_print(f"Error buscando proyecto '{project_name}': {e}")
            return None

    def find_shot(self, project_id, shot_code):
        if not self.sg:
            return None
        filters = [
            ["project", "is", {"type": "Project", "id": project_id}],
            ["code", "is", shot_code],
        ]
        try:
            shots = self.sg.find("Shot", filters, ["id", "code"])
            return shots[0] if shots else None
        except Exception as e:
            debug_print(f"Error buscando shot '{shot_code}': {e}")
            return None

    def get_tasks_for_shot(self, shot_id):
        if not self.sg:
            return []
        filters = [["entity", "is", {"type": "Shot", "id": shot_id}]]
        fields = ["id", "content", "task_assignees", "step"]
        try:
            return self.sg.find("Task", filters, fields)
        except Exception as e:
            debug_print(f"Error obteniendo tasks para shot {shot_id}: {e}")
            return []

    def get_shot_with_tasks(self, project_name, shot_code):
        project = self.find_project(project_name)
        if not project:
            return None, None, []
        shot = self.find_shot(project["id"], shot_code)
        if not shot:
            return project, None, []
        tasks = self.get_tasks_for_shot(shot["id"])
        return project, shot, tasks

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

    def check_user_has_project(self, user, project_name):
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return False, None

        try:
            projects = self.sg.find(
                "Project", [["name", "is", project_name]], ["id", "name"]
            )

            if not projects:
                debug_print(f"No se encontro el proyecto '{project_name}' en Flow.")
                return False, None

            project_id = projects[0]["id"]
            user_projects = user.get("projects", [])

            for proj_ref in user_projects:
                if proj_ref.get("id") == project_id:
                    debug_print(
                        f"Usuario ya tiene asignado el proyecto '{project_name}'"
                    )
                    return True, project_id

            debug_print(f"Usuario NO tiene asignado el proyecto '{project_name}'")
            return False, project_id

        except Exception as e:
            debug_print(f"Error al verificar proyecto del usuario: {e}")
            return False, None

    def assign_project_to_user(self, user_id, project_id):
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return False

        try:
            user = self.sg.find_one(
                "HumanUser", [["id", "is", user_id]], ["id", "name", "projects"]
            )

            if not user:
                debug_print(f"No se encontro el usuario con ID {user_id}")
                return False

            current_projects = user.get("projects", [])

            for proj_ref in current_projects:
                if proj_ref.get("id") == project_id:
                    debug_print(f"El proyecto ya estaba asignado al usuario")
                    return True

            new_project_ref = {"type": "Project", "id": project_id}
            new_projects = current_projects + [new_project_ref]

            result = self.sg.update("HumanUser", user_id, {"projects": new_projects})

            if result:
                debug_print(f"Proyecto asignado exitosamente al usuario {user_id}")
                return True
            else:
                debug_print(f"Fallo al asignar proyecto al usuario {user_id}")
                return False

        except Exception as e:
            debug_print(f"Error al asignar proyecto al usuario: {e}")
            return False

    def add_assignee_to_task(self, task_id, current_assignees, user):
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return False, "Conexion a ShotGrid no inicializada"
        try:
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

            project = sg_manager.find_project(project_name)
            if not project:
                self.signals.error.emit(
                    f"No se encontró el proyecto '{project_name}' en Flow."
                )
                return

            shot = sg_manager.find_shot(project["id"], shot_code)
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

            tasks = sg_manager.get_tasks_for_shot(shot["id"])
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


class AssignmentSignals(QObject):
    task_started = Signal(str)
    finished = Signal(bool, str)
    error = Signal(str)


class AssignSelectedTasksWorker(QRunnable):
    def __init__(self, project_name, shot_name, user_name, tasks):
        super(AssignSelectedTasksWorker, self).__init__()
        self.project_name = project_name
        self.shot_name = shot_name
        self.user_name = user_name
        self.tasks = tasks
        self.signals = AssignmentSignals()

    @Slot()
    def run(self):
        try:
            sg_url, sg_login, sg_password = get_flow_credentials_secure()
            if not all([sg_url, sg_login, sg_password]):
                self.signals.error.emit(
                    "No se pudieron obtener las credenciales de Flow desde SecureConfig."
                )
                return

            sg_manager = ShotGridManager(sg_url, sg_login, sg_password)
            if not sg_manager.sg:
                self.signals.error.emit("No se pudo inicializar la conexión a ShotGrid.")
                return

            user = sg_manager.find_user_by_name(self.user_name)
            if not user:
                self.signals.error.emit(
                    f"No se encontró el usuario '{self.user_name}' en ShotGrid."
                )
                return

            user_with_projects = sg_manager.sg.find_one(
                "HumanUser", [["id", "is", user["id"]]], ["id", "name", "projects"]
            )
            if not user_with_projects:
                self.signals.error.emit(
                    f"No se pudo obtener información completa del usuario '{self.user_name}'."
                )
                return

            has_project, project_id = sg_manager.check_user_has_project(
                user_with_projects, self.project_name
            )
            project_assigned = False
            if not has_project and project_id:
                project_assigned = sg_manager.assign_project_to_user(
                    user_with_projects["id"], project_id
                )

            for task in self.tasks:
                task_name = task["name"]
                self.signals.task_started.emit(task_name)
                current_assignees = task.get("assignees", [])
                success, message = sg_manager.add_assignee_to_task(
                    task["id"], current_assignees, user
                )
                if not success:
                    self.signals.error.emit(f"{task_name}: {message}")
                    return
                self.update_local_database(
                    self.project_name, self.shot_name, task_name, self.user_name
                )

            tasks_list = ", ".join(task["name"] for task in self.tasks)
            success_message = (
                f"Usuario '{self.user_name}' asignado a {self.shot_name}/{tasks_list}"
            )
            if project_assigned:
                success_message += (
                    f" (se agregó el proyecto '{self.project_name}' al usuario)"
                )
            self.signals.finished.emit(True, success_message)

        except Exception as exc:
            debug_print(f"Error en AssignSelectedTasksWorker: {exc}")
            self.signals.error.emit(f"Error asignando usuario: {exc}")

    def update_local_database(self, project_name, shot_name, task_name, user_name):
        try:
            db_manager = DBManager()
            if not db_manager.conn:
                debug_print("No se pudo conectar a la base de datos local")
                return

            db_shot = db_manager.find_shot(project_name, shot_name)
            if not db_shot:
                debug_print(
                    f"No se encontró el shot {shot_name} en la base de datos local"
                )
                db_manager.close()
                return

            db_task = db_manager.find_task(db_shot["id"], task_name)
            if not db_task:
                debug_print(
                    f"No se encontró la tarea {task_name} en la base de datos local"
                )
                db_manager.close()
                return

            debug_print(
                f"Añadiendo asignación a la tarea local (ID: {db_task['id']}) para: {user_name}"
            )
            db_manager.add_task_assignment(db_task["id"], user_name)
            db_manager.close()
        except Exception as exc:
            debug_print(f"Error actualizando base de datos local: {exc}")


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


def assign_assignee_to_task(base_name, user_name, file_path=None):
    """
    Función principal del script de asignación.

    Args:
        base_name (str): Nombre base del clip
        user_name (str): Nombre del usuario a asignar
        file_path (str): Ruta completa del clip (para extraer project_name desde VFX-NOMBRE)
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

    shot_preview = extract_shot_code(base_name) or "-"

    _status_window = FlowStatusWindow(user_display_name, user_color, "asignar usuario")
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

        auto_confirm = len(tasks) == 1

        def start_assignment(selected_tasks):
            if not selected_tasks:
                _status_window.show_error("Seleccioná al menos una task.")
                return
            _status_window.clear_validation_message()
            _status_window.show_processing_message(
                "<span style='color:#CCCCCC;'>Asignando tasks seleccionadas en Flow...</span>"
            )
            _status_window.set_close_enabled(False)
            worker = AssignSelectedTasksWorker(
                payload["project_name"], shot_name, user_name, selected_tasks
            )
            worker.signals.task_started.connect(
                lambda task_name, window=_status_window, shot=shot_name: window.update_shot_info(
                    shot, task_name
                )
            )
            worker.signals.finished.connect(
                lambda success, message, window=_status_window: window.show_success(
                    message
                )
            )
            worker.signals.error.connect(
                lambda error_msg, window=_status_window: window.show_error(error_msg)
            )
            QThreadPool.globalInstance().start(worker)

        _status_window.present_task_selection(
            tasks,
            default_task=payload.get("default_task"),
            on_confirm=start_assignment,
            auto_confirm=auto_confirm,
            action_label="Asignar en Flow",
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

    if len(sys.argv) < 3:
        print("Uso: python LGA_NKS_Flow_Assign_Assignee.py <base_name> <user_name>")
    else:
        base_name = sys.argv[1]
        user_name = sys.argv[2]
        assign_assignee_to_task(base_name, user_name)
