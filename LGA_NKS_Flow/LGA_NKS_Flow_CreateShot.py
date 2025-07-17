"""
____________________________________________________________________________________

  LGA_NKS_Flow_CreateShot v1.0 | Lega Pugliese
  Script para crear shots en ShotGrid basado en el nombre del clip seleccionado en Hiero
____________________________________________________________________________________
"""

import hiero.core
import os
import re
import sys
from pathlib import Path
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

# Agregar la ruta de shotgun_api3 al sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "LGA_ToolPack"))

import shotgun_api3

# Importar el modulo de configuracion segura
sys.path.append(str(Path(__file__).parent))
from SecureConfig_Reader import get_flow_credentials


DEBUG = False
debug_messages = []


def debug_print(message):
    """Imprime un mensaje de debug si la variable DEBUG es True."""
    if DEBUG:
        debug_messages.append(str(message))


def print_debug_messages():
    if DEBUG and debug_messages:
        print("\n".join(debug_messages))
        debug_messages.clear()


# Clase de ventana de estado para mostrar progreso de creacion de shot en Flow
class FlowStatusWindow(QDialog):
    def __init__(self, task_type="crear shot", parent=None):
        super(FlowStatusWindow, self).__init__(parent)
        self.setWindowTitle("Flow | Create Shot")
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

        # Mensaje inicial
        if task_type == "crear shot":
            task_text = "Creando shot en ShotGrid"
        else:
            task_text = "Procesando"

        initial_message = (
            f"<div style='text-align: left;'>"
            f"<span style='color: #CCCCCC; '>{task_text}</span>"
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

    def update_shot_info(self, shot_name, project_name=None):
        """Actualiza la ventana con el shot que se está procesando"""
        shot_html = "<div style='text-align: left;'>"
        if project_name:
            shot_html += f"<span style='color: #CCCCCC; '>Proyecto:</span> <span style='color: #6AB5CA; '>{project_name}</span><br>"
        shot_html += f"<span style='color: #CCCCCC; '>Shot:</span> <span style='color: #B56AB5; '>{shot_name}</span>"
        shot_html += "</div>"
        self.shot_label.setText(shot_html)
        self._adjust_window_size()

    def show_processing_message(self):
        """Muestra el mensaje de procesamiento"""
        processing_html = f"<span style='color: #CCCCCC; '>Conectando a Flow Production Tracking...</span>"
        self.result_label.setText(processing_html)
        self.result_label.setStyleSheet("padding: 10px;")
        self._adjust_window_size()

    def show_step_message(self, message):
        """Muestra mensaje de paso actual"""
        step_html = f"<span style='color: #CCCCCC; '>{message}</span>"
        self.result_label.setText(step_html)
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
    """Clase para manejar operaciones en ShotGrid."""

    def __init__(self, url, login, password):
        debug_print("Inicializando conexion a ShotGrid para crear shot")
        try:
            self.sg = shotgun_api3.Shotgun(url, login=login, password=password)
            debug_print("Conexion a ShotGrid inicializada exitosamente")
        except Exception as e:
            debug_print(f"Error al inicializar la conexion a ShotGrid: {e}")
            self.sg = None

    def find_shot_and_tasks(self, project_name, shot_code):
        """Encuentra el shot en ShotGrid y sus tareas asociadas. Si no existe, lo crea."""
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return None, None

        projects = self.sg.find(
            "Project", [["name", "is", project_name]], ["id", "name"]
        )
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
                tasks = self.find_tasks_for_shot(shot_id)
                return shots[0], tasks
            else:
                debug_print("No se encontro el shot. Creando shot...")
                created_shot = self.create_shot(project_id, shot_code)
                if created_shot:
                    tasks = self.find_tasks_for_shot(created_shot["id"])
                    return created_shot, tasks
                return None, None
        else:
            debug_print("No se encontro el proyecto en ShotGrid.")
        return None, None

    def find_tasks_for_shot(self, shot_id):
        """Encuentra las tareas asociadas a un shot."""
        if not self.sg:
            return []
        filters = [["entity", "is", {"type": "Shot", "id": shot_id}]]
        fields = ["id", "content", "sg_status_list"]
        return self.sg.find("Task", filters, fields)

    def create_shot(self, project_id, shot_code):
        """Crea un shot en ShotGrid con los parametros predefinidos."""
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return None

        # Parametros predefinidos
        sequence_name = "103"
        description = "Descripcion test"
        task_template_name = "Template_comp"

        debug_print(f"Creando shot '{shot_code}' con parametros predefinidos...")

        # Buscar secuencia
        sequence_filters = [
            ["project", "is", {"type": "Project", "id": project_id}],
            ["code", "is", sequence_name],
        ]
        sequences = self.sg.find("Sequence", sequence_filters, ["id", "code"])
        if not sequences:
            debug_print(f"ERROR: No se encontro la secuencia '{sequence_name}'")
            return None

        sequence_id = sequences[0]["id"]
        debug_print(f"Secuencia encontrada: {sequences[0]['code']} (ID: {sequence_id})")

        # Buscar task template
        task_templates = self.sg.find(
            "TaskTemplate", [["code", "is", task_template_name]], ["id", "code"]
        )
        if not task_templates:
            debug_print(
                f"ERROR: No se encontro el task template '{task_template_name}'"
            )
            return None

        task_template_id = task_templates[0]["id"]
        debug_print(
            f"Task Template encontrado: {task_templates[0]['code']} (ID: {task_template_id})"
        )

        # Crear el shot
        shot_data = {
            "project": {"type": "Project", "id": project_id},
            "code": shot_code,
            "description": description,
            "sg_sequence": {"type": "Sequence", "id": sequence_id},
            "task_template": {"type": "TaskTemplate", "id": task_template_id},
        }

        try:
            new_shot = self.sg.create("Shot", shot_data)
            debug_print(
                f"Shot creado exitosamente: {new_shot['code']} (ID: {new_shot['id']})"
            )
            return new_shot
        except Exception as e:
            debug_print(f"ERROR al crear el shot: {e}")
            return None


class HieroOperations:
    """Clase para manejar operaciones en Hiero."""

    def __init__(self, shotgrid_manager):
        self.sg_manager = shotgrid_manager

    def parse_exr_name(self, file_name):
        """Extrae el nombre base del archivo EXR y el numero de version."""
        base_name = re.sub(r"_%04d\.exr$", "", file_name)
        version_match = re.search(r"_v(\d+)", base_name)
        version_number = version_match.group(1) if version_match else "Unknown"
        return base_name, version_number

    def get_selected_clips_info(self):
        """Obtiene informacion de los clips seleccionados en el timeline de Hiero."""
        seq = hiero.ui.activeSequence()
        if seq:
            te = hiero.ui.getTimelineEditor(seq)
            selected_clips = te.selection()
            if selected_clips:
                clips_info = []
                for clip in selected_clips:
                    file_path = clip.source().mediaSource().fileinfos()[0].filename()
                    exr_name = os.path.basename(file_path)
                    base_name, version_number = self.parse_exr_name(exr_name)

                    project_name = base_name.split("_")[0]
                    parts = base_name.split("_")
                    shot_code = "_".join(parts[:5])

                    clips_info.append(
                        {
                            "base_name": base_name,
                            "project_name": project_name,
                            "shot_code": shot_code,
                            "version_number": version_number,
                        }
                    )
                return clips_info
            else:
                debug_print("No se han seleccionado clips en el timeline.")
                return []
        else:
            debug_print("No se encontro una secuencia activa en Hiero.")
            return []

    def process_selected_clips(self):
        """Procesa los clips seleccionados en el timeline de Hiero."""
        clips_info = self.get_selected_clips_info()
        if not clips_info:
            return []

        results = []
        for clip_info in clips_info:
            shot, tasks = self.sg_manager.find_shot_and_tasks(
                clip_info["project_name"], clip_info["shot_code"]
            )
            if shot:
                debug_print(f"Clip seleccionado: {clip_info['base_name']}")
                debug_print(f"Shot de SG encontrado: {shot['code']}")
                debug_print(f"Descripcion del shot: {shot['description']}")
                debug_print("Tareas asociadas:")
                if tasks:
                    for task in tasks:
                        debug_print(f"- Nombre: {task['content']}")
                        debug_print(f"  Estado: {task['sg_status_list']}")
                else:
                    debug_print("No hay tareas asociadas a este shot.")

                results.append(
                    {
                        "clip_info": clip_info,
                        "shot": shot,
                        "tasks": tasks,
                        "success": True,
                    }
                )
            else:
                debug_print("No se encontro el shot correspondiente en ShotGrid.")
                results.append(
                    {
                        "clip_info": clip_info,
                        "shot": None,
                        "tasks": None,
                        "success": False,
                    }
                )

        return results


class WorkerSignals(QObject):
    shot_info_ready = Signal(str, str)  # shot_name, project_name
    step_update = Signal(str)  # step message
    finished = Signal(bool, str)  # success, message
    error = Signal(str)


class CreateShotWorker(QRunnable):
    def __init__(self, status_window):
        super(CreateShotWorker, self).__init__()
        self.status_window = status_window
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            debug_print("=== Iniciando creacion de shots ===")

            # Obtener credenciales de Flow DENTRO del worker
            self.signals.step_update.emit("Obteniendo credenciales...")
            sg_url, sg_login, sg_password = get_flow_credentials()
            if not all([sg_url, sg_login, sg_password]):
                self.signals.error.emit(
                    "No se pudieron obtener las credenciales de Flow desde SecureConfig."
                )
                return

            # Crear manager ShotGrid DENTRO del worker
            self.signals.step_update.emit("Conectando a ShotGrid...")
            sg_manager = ShotGridManager(sg_url, sg_login, sg_password)
            if not sg_manager.sg:
                self.signals.error.emit(
                    "No se pudo inicializar la conexión a ShotGrid."
                )
                return

            # Crear operador de Hiero
            self.signals.step_update.emit("Obteniendo clips seleccionados...")
            hiero_ops = HieroOperations(sg_manager)

            # Obtener informacion de clips
            clips_info = hiero_ops.get_selected_clips_info()
            if not clips_info:
                self.signals.error.emit(
                    "No se encontraron clips seleccionados en Hiero."
                )
                return

            # Procesar cada clip
            total_clips = len(clips_info)
            success_count = 0

            for i, clip_info in enumerate(clips_info, 1):
                # Emitir información del shot
                self.signals.shot_info_ready.emit(
                    clip_info["shot_code"], clip_info["project_name"]
                )

                self.signals.step_update.emit(
                    f"Procesando clip {i}/{total_clips}: {clip_info['shot_code']}"
                )

                # Procesar shot
                shot, tasks = sg_manager.find_shot_and_tasks(
                    clip_info["project_name"], clip_info["shot_code"]
                )

                if shot:
                    success_count += 1
                    debug_print(f"Shot procesado exitosamente: {shot['code']}")
                else:
                    debug_print(f"Error procesando shot: {clip_info['shot_code']}")

            # Mensaje final
            if success_count == total_clips:
                self.signals.finished.emit(
                    True,
                    f"Todos los shots ({success_count}/{total_clips}) fueron procesados exitosamente.",
                )
            elif success_count > 0:
                self.signals.finished.emit(
                    True,
                    f"Se procesaron {success_count}/{total_clips} shots exitosamente.",
                )
            else:
                self.signals.error.emit("No se pudieron procesar ninguno de los shots.")

        except Exception as e:
            debug_print(f"Error en CreateShotWorker: {e}")
            self.signals.error.emit(f"Error: {str(e)}")


# Variable global para mantener referencia a la ventana
_status_window = None


def create_shots_from_selected_clips():
    """
    Función principal del script de creación de shots.
    """
    global _status_window

    debug_print("=== Iniciando LGA_NKS_Flow_CreateShot ===")

    # Crear aplicación Qt si no existe
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    # Crear y mostrar ventana de estado
    _status_window = FlowStatusWindow("crear shot")
    _status_window.show()
    _status_window.show_processing_message()  # Mostrar mensaje de procesamiento

    # Crear worker para procesamiento en hilo separado
    worker = CreateShotWorker(_status_window)

    # Conectar señales
    worker.signals.shot_info_ready.connect(
        lambda shot_name, project_name, window=_status_window: window.update_shot_info(
            shot_name, project_name
        )
    )
    worker.signals.step_update.connect(
        lambda message, window=_status_window: window.show_step_message(message)
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


def main():
    """Función principal para compatibilidad hacia atrás."""
    create_shots_from_selected_clips()


if __name__ == "__main__":
    main()
