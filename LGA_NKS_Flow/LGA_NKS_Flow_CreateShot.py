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
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QCheckBox,
    QFrame,
    QLineEdit,
)
from PySide2.QtGui import QFont, QPixmap
from PySide2.QtCore import QRect

# Agregar la ruta de shotgun_api3 al sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "LGA_ToolPack"))

import shotgun_api3

# Importar el modulo de configuracion segura
sys.path.append(str(Path(__file__).parent))
from SecureConfig_Reader import get_flow_credentials

# IMPORTANTE!!!! NO ACTIVAR DEBUG PORQUE CRASHEA HIERO!!!!!!!!!!!!!!!!!!!!!!!!!!!!
DEBUG = False
debug_messages = []


def debug_print(message):
    """Imprime un mensaje de debug si la variable DEBUG es True."""
    if DEBUG:
        debug_messages.append(str(message))
        print(f"[DEBUG] {message}")  # Imprimir inmediatamente tambien


def print_debug_messages():
    if DEBUG and debug_messages:
        print("\n".join(debug_messages))
        debug_messages.clear()


def get_active_sequence_name():
    """Obtiene el nombre de la secuencia activa en Hiero"""
    try:
        seq = hiero.ui.activeSequence()
        if seq:
            sequence_name = seq.name()
            debug_print(f"Secuencia activa encontrada: {sequence_name}")
            return sequence_name
        else:
            debug_print("ERROR: No se encontro una secuencia activa")
            return None
    except Exception as e:
        debug_print(f"ERROR obteniendo nombre de secuencia: {e}")
        return None


# Funciones para crear thumbnails de shots
def zoom_to_fill_in_viewer():
    """Aplica zoom to fill al viewer actual"""
    viewer = hiero.ui.currentViewer()
    if not viewer:
        debug_print("❌ No hay viewer activo")
        return False

    try:
        player = viewer.player()
        if not player:
            debug_print("❌ No se encontró el player del viewer")
            return False

        player.zoomToFill()
        debug_print("✅ Zoom to Fill aplicado con éxito")
        return True
    except Exception as e:
        debug_print(f"❌ Error aplicando zoomToFill: {e}")
        return False


def crop_to_aspect_ratio(qimage, target_aspect):
    """Recorta la imagen a la relacion de aspecto especificada."""
    width = qimage.width()
    height = qimage.height()

    current_aspect = width / height

    if current_aspect > target_aspect:
        new_width = int(height * target_aspect)
        offset_x = int((width - new_width) / 2)
        rect = QRect(offset_x, 0, new_width, height)
        cropped = qimage.copy(rect)
        return cropped
    else:
        new_height = int(width / target_aspect)
        offset_y = int((height - new_height) / 2)
        rect = QRect(0, offset_y, width, new_height)
        cropped = qimage.copy(rect)
        return cropped


def get_shot_name_from_selected_clip():
    """Obtiene el nombre del shot desde el clip seleccionado o desde el path del archivo."""
    sequence = hiero.ui.activeSequence()
    if not sequence:
        debug_print("No se encontró una secuencia activa.")
        return None

    timeline_editor = hiero.ui.getTimelineEditor(sequence)
    selected_clips = timeline_editor.selection()

    if not selected_clips:
        debug_print("No hay clips seleccionados en el timeline.")
        sequence_name = sequence.name()
        debug_print(f"Usando nombre de secuencia: {sequence_name}")
        return sequence_name

    # Tomar el primer clip seleccionado
    clip = selected_clips[0]

    try:
        # Intentar obtener el shot name del clip
        shot_name = clip.name()
        if shot_name:
            debug_print(f"Shot name desde clip.name(): {shot_name}")
            return shot_name
    except:
        pass

    try:
        # Si no hay shot name, extraerlo del path del archivo
        file_path = clip.source().mediaSource().fileinfos()[0].filename()
        debug_print(f"File path: {file_path}")

        # Extraer nombre base del archivo
        exr_name = os.path.basename(file_path)
        base_name = re.sub(r"_%04d\.exr$", "", exr_name)
        base_name = re.sub(r"_v\d+$", "", base_name)  # Remover version si existe

        # Si el nombre base contiene guiones bajos, tomar las primeras partes como shot code
        parts = base_name.split("_")
        if len(parts) >= 5:
            shot_code = "_".join(parts[:5])
            debug_print(f"Shot code extraído del path: {shot_code}")
            return shot_code
        else:
            debug_print(f"Nombre base del archivo: {base_name}")
            return base_name

    except Exception as e:
        debug_print(f"Error extrayendo shot name del path: {e}")

    # Como último recurso, usar el nombre de la secuencia
    sequence_name = sequence.name()
    debug_print(f"Usando nombre de secuencia como fallback: {sequence_name}")
    return sequence_name


def create_shot_thumbnail():
    """Crea un thumbnail del shot actual y retorna la ruta del archivo creado."""
    # Aplicar zoom to fill primero
    if not zoom_to_fill_in_viewer():
        debug_print("❌ No se pudo aplicar zoom to fill")
        return None

    # Obtener el shot name
    shot_name = get_shot_name_from_selected_clip()
    if not shot_name:
        debug_print("❌ No se pudo obtener el nombre del shot")
        return None

    # Limpiar el shot name para usarlo como nombre de archivo
    shot_name = re.sub(r'[<>:"/\\|?*]', "_", shot_name)  # Remover caracteres inválidos
    debug_print(f"Shot name limpio: {shot_name}")

    # Crear carpeta de cache relativa al script
    script_dir = os.path.dirname(__file__)
    cache_dir = os.path.join(script_dir, "ShotThumbs_Cache")

    # Crear directorio si no existe
    os.makedirs(cache_dir, exist_ok=True)
    debug_print(f"Carpeta de destino: {cache_dir}")

    # Obtener imagen del viewer
    viewer = hiero.ui.currentViewer()
    if not viewer:
        debug_print("❌ No hay viewer activo")
        return None

    qimage = viewer.image()
    if qimage is None or qimage.isNull():
        debug_print("❌ viewer.image() devolvió None o imagen nula")
        return None

    # Obtener la secuencia activa y su relacion de aspecto
    sequence = hiero.ui.activeSequence()
    if sequence is None:
        debug_print("No hay ninguna secuencia activa, usando 16:9 por defecto.")
        target_aspect = 16 / 9
    else:
        format = sequence.format()
        width = format.width()
        height = format.height()
        target_aspect = width / height
        debug_print(
            f"Relación de aspecto de la secuencia: {width} x {height} ({target_aspect:.2f})"
        )

    # Aplicar crop
    qimage_cropped = crop_to_aspect_ratio(qimage, target_aspect)
    debug_print(
        f"Snapshot size (cropped): {qimage_cropped.width()} × {qimage_cropped.height()}"
    )

    # Generar nombre de archivo único
    import time

    timestamp = int(time.time())
    filename = f"{shot_name}_{timestamp}.jpg"
    full_path = os.path.join(cache_dir, filename)

    # Guardar imagen
    ok = qimage_cropped.save(full_path, "JPEG")

    if ok and os.path.exists(full_path):
        debug_print(f"✅ Shot Thumbnail guardado: {filename}")
        debug_print(f"Ruta completa: {full_path}")
        return full_path
    else:
        debug_print("❌ No se pudo crear el archivo.")
        debug_print(f"save() result: {ok}, exists: {os.path.exists(full_path)}")
        return None


# Clase de ventana de configuracion para shots
class ShotConfigDialog(QDialog):
    def __init__(self, clips_info, sequence_name=None, parent=None):
        super(ShotConfigDialog, self).__init__(parent)
        self.setWindowTitle("Flow | Shot Configuration")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        self.clips_info = clips_info
        self.sequence_name = sequence_name
        self.shot_config = None

        # Layout principal
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Titulo
        title_label = QLabel("Configuracion para crear shots")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #CCCCCC; padding: 10px;")
        layout.addWidget(title_label)

        # Informacion de clips
        clips_label = QLabel(f"Se van a procesar {len(self.clips_info)} clips:")
        clips_label.setStyleSheet("color: #CCCCCC; padding: 5px;")
        layout.addWidget(clips_label)

        # Lista de clips
        for clip_info in self.clips_info:
            clip_frame = QFrame()
            clip_frame.setStyleSheet(
                "border: 1px solid #444444; border-radius: 3px; margin: 2px; padding: 5px;"
            )
            clip_layout = QVBoxLayout(clip_frame)

            project_shot_label = QLabel(
                f"<span style='color: #6AB5CA;'>{clip_info['project_name']}</span> / <span style='color: #B56AB5;'>{clip_info['shot_code']}</span>"
            )
            project_shot_label.setTextFormat(Qt.RichText)
            clip_layout.addWidget(project_shot_label)

            layout.addWidget(clip_frame)

        # Separador
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("color: #444444;")
        layout.addWidget(separator)

        # Campo de descripcion del shot
        desc_label = QLabel("Shot Description:")
        desc_label.setStyleSheet(
            "color: #CCCCCC; font-weight: bold; padding-top: 10px;"
        )
        layout.addWidget(desc_label)

        self.description_text = QTextEdit()
        self.description_text.setMaximumHeight(80)  # 3 lineas aproximadamente
        self.description_text.setPlainText("")
        self.description_text.setStyleSheet(
            """
            QTextEdit {
                background-color: #2B2B2B;
                border: 1px solid #555555;
                color: #CCCCCC;
                padding: 5px;
                border-radius: 3px;
            }
        """
        )
        layout.addWidget(self.description_text)

        # Campo de secuencia
        seq_label = QLabel("Sequence:")
        seq_label.setStyleSheet("color: #CCCCCC; font-weight: bold; padding-top: 10px;")
        layout.addWidget(seq_label)

        self.sequence_line_edit = QLineEdit()
        self.sequence_line_edit.setText(self.sequence_name)
        self.sequence_line_edit.setStyleSheet(
            """
            QLineEdit {
                background-color: #2B2B2B;
                border: 1px solid #555555;
                color: #CCCCCC;
                padding: 5px;
                border-radius: 3px;
                height: 20px;
            }
        """
        )
        layout.addWidget(self.sequence_line_edit)

        # Checkboxes
        self.copy_to_comp_cb = QCheckBox("Copy shot description to Comp Description")
        self.copy_to_comp_cb.setChecked(True)  # Activado por defecto
        self.copy_to_comp_cb.setStyleSheet("color: #CCCCCC; padding: 5px;")
        layout.addWidget(self.copy_to_comp_cb)

        self.shot_ready_cb = QCheckBox("Shot status Ready to start")
        self.shot_ready_cb.setChecked(True)  # Activado por defecto
        self.shot_ready_cb.setStyleSheet("color: #CCCCCC; padding: 5px;")
        layout.addWidget(self.shot_ready_cb)

        self.task_ready_cb = QCheckBox("Task Comp status Ready to start")
        self.task_ready_cb.setChecked(True)  # Activado por defecto
        self.task_ready_cb.setStyleSheet("color: #CCCCCC; padding: 5px;")
        layout.addWidget(self.task_ready_cb)

        # Thumbnail del shot (solo si hay un clip seleccionado)
        self.thumbnail_label = None
        self.thumbnail_path = None
        if len(self.clips_info) == 1:
            self.create_and_show_thumbnail(layout)

        # Espaciador
        layout.addStretch()

        # Botones
        button_layout = QHBoxLayout()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setStyleSheet(
            """
            QPushButton {
                background-color: #555555;
                border: 1px solid #666666;
                color: #CCCCCC;
                padding: 8px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """
        )
        button_layout.addWidget(self.cancel_button)

        button_layout.addStretch()

        self.create_button = QPushButton("Create Shots")
        self.create_button.clicked.connect(self.accept_config)
        self.create_button.setStyleSheet(
            """
            QPushButton {
                background-color: #0078D4;
                border: 1px solid #106EBE;
                color: white;
                padding: 8px 15px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #106EBE;
            }
        """
        )
        button_layout.addWidget(self.create_button)

        layout.addLayout(button_layout)

        # Estilo general del dialogo
        self.setStyleSheet(
            """
            QDialog {
                background-color: #2B2B2B;
                border: 1px solid #555555;
            }
        """
        )

    def accept_config(self):
        """Acepta la configuracion y guarda los valores"""
        self.shot_config = {
            "description": self.description_text.toPlainText(),
            "sequence_name": self.sequence_line_edit.text().strip(),
            "copy_to_comp": self.copy_to_comp_cb.isChecked(),
            "shot_ready": self.shot_ready_cb.isChecked(),
            "task_ready": self.task_ready_cb.isChecked(),
        }
        self.accept()

    def get_config(self):
        """Retorna la configuracion seleccionada"""
        return self.shot_config

    def create_and_show_thumbnail(self, layout):
        """Crea y muestra el thumbnail del shot en la UI"""
        try:
            # Crear el thumbnail
            thumbnail_path = create_shot_thumbnail()
            if thumbnail_path:
                self.thumbnail_path = thumbnail_path

                # Crear separador para el thumbnail
                thumb_separator = QFrame()
                thumb_separator.setFrameShape(QFrame.HLine)
                thumb_separator.setFrameShadow(QFrame.Sunken)
                thumb_separator.setStyleSheet("color: #444444;")
                layout.addWidget(thumb_separator)

                # Label para el thumbnail
                thumb_title = QLabel("Shot Preview:")
                thumb_title.setStyleSheet(
                    "color: #CCCCCC; font-weight: bold; padding-top: 10px;"
                )
                layout.addWidget(thumb_title)

                # Widget para mostrar el thumbnail
                self.thumbnail_label = QLabel()
                self.thumbnail_label.setAlignment(Qt.AlignCenter)
                self.thumbnail_label.setStyleSheet(
                    """
                    QLabel {
                        border: 1px solid #555555;
                        border-radius: 3px;
                        padding: 5px;
                        background-color: #1E1E1E;
                    }
                """
                )

                # Cargar y escalar la imagen
                pixmap = QPixmap(thumbnail_path)
                if not pixmap.isNull():
                    # Escalar la imagen manteniendo la relacion de aspecto
                    scaled_pixmap = pixmap.scaled(
                        300, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation
                    )
                    self.thumbnail_label.setPixmap(scaled_pixmap)
                    self.thumbnail_label.setFixedSize(
                        320, 220
                    )  # Un poco mas grande que la imagen para el padding
                    layout.addWidget(self.thumbnail_label)
                    debug_print(f"✅ Thumbnail mostrado en la UI: {thumbnail_path}")
                else:
                    debug_print("❌ No se pudo cargar el pixmap del thumbnail")
            else:
                debug_print("❌ No se pudo crear el thumbnail")
        except Exception as e:
            debug_print(f"❌ Error creando thumbnail: {e}")

    def cleanup_thumbnail(self):
        """Limpia el archivo temporal del thumbnail"""
        if self.thumbnail_path and os.path.exists(self.thumbnail_path):
            try:
                os.remove(self.thumbnail_path)
                debug_print(f"✅ Archivo temporal eliminado: {self.thumbnail_path}")
            except Exception as e:
                debug_print(f"❌ Error eliminando archivo temporal: {e}")

    def closeEvent(self, event):
        """Sobrescribe el evento de cierre para limpiar archivos temporales"""
        self.cleanup_thumbnail()
        super(ShotConfigDialog, self).closeEvent(event)

    def reject(self):
        """Sobrescribe reject para limpiar archivos temporales"""
        self.cleanup_thumbnail()
        super(ShotConfigDialog, self).reject()

    def accept(self):
        """Sobrescribe accept para limpiar archivos temporales después"""
        super(ShotConfigDialog, self).accept()
        # Nota: No limpiamos aquí porque el archivo podría usarse después
        # Se limpiará cuando se destruya la ventana


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

    def upload_thumbnail(self, entity_type, entity_id, thumbnail_path):
        """Sube un thumbnail a una entidad en ShotGrid."""
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return False

        if not thumbnail_path:
            debug_print("No se proporciono ruta de thumbnail")
            return False

        if not os.path.exists(thumbnail_path):
            debug_print(
                f"ERROR: No se encontro el archivo de thumbnail: {thumbnail_path}"
            )
            return False

        debug_print(f"Verificando archivo antes de subir: {thumbnail_path}")
        debug_print(f"Archivo existe: {os.path.exists(thumbnail_path)}")
        debug_print(
            f"Tamaño del archivo: {os.path.getsize(thumbnail_path) if os.path.exists(thumbnail_path) else 'N/A'}"
        )

        try:
            debug_print(f"Iniciando subida de thumbnail: {thumbnail_path}")
            result = self.sg.upload_thumbnail(entity_type, entity_id, thumbnail_path)
            debug_print(f"Thumbnail subido exitosamente: {result}")
            return True
        except Exception as e:
            debug_print(f"ERROR al subir thumbnail: {e}")
            import traceback

            debug_print(f"Traceback completo: {traceback.format_exc()}")
            return False

    def find_shot_and_tasks(
        self, project_name, shot_code, shot_config, thumbnail_path=None
    ):
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
            fields = ["id", "code", "description", "sg_status_list"]
            shots = self.sg.find("Shot", filters, fields)
            if shots:
                shot_id = shots[0]["id"]
                # Actualizar shot existente si es necesario
                self.update_shot_status_if_needed(shot_id, shot_config)

                # NO subir thumbnail a shots existentes para evitar crashes
                debug_print(
                    f"Shot existente encontrado: {shot_code}, saltando subida de thumbnail"
                )

                tasks = self.find_tasks_for_shot(shot_id, shot_config)
                return shots[0], tasks
            else:
                debug_print("No se encontro el shot. Creando shot...")
                created_shot = self.create_shot(
                    project_id, shot_code, shot_config, thumbnail_path
                )
                if created_shot:
                    tasks = self.find_tasks_for_shot(created_shot["id"], shot_config)
                    return created_shot, tasks
                return None, None
        else:
            debug_print("No se encontro el proyecto en ShotGrid.")
        return None, None

    def find_tasks_for_shot(self, shot_id, shot_config):
        """Encuentra las tareas asociadas a un shot."""
        if not self.sg:
            return []

        try:
            filters = [["entity", "is", {"type": "Shot", "id": shot_id}]]
            fields = ["id", "content", "sg_status_list", "sg_description"]
            tasks = self.sg.find("Task", filters, fields)
            debug_print(f"Encontradas {len(tasks)} tareas para el shot")

            # Actualizar tareas si es necesario (de forma inmediata y simple)
            for task in tasks:
                debug_print(f"Procesando tarea: {task['content']}")
                try:
                    if task["content"].lower() == "comp" and shot_config["task_ready"]:
                        debug_print("Actualizando status de tarea Comp a ready...")
                        self.sg.update("Task", task["id"], {"sg_status_list": "ready"})
                        debug_print("Task status actualizado exitosamente")

                    if (
                        task["content"].lower() == "comp"
                        and shot_config["copy_to_comp"]
                    ):
                        debug_print("Copiando descripcion a tarea Comp...")
                        self.sg.update(
                            "Task",
                            task["id"],
                            {"sg_description": shot_config["description"]},
                        )
                        debug_print("Task description actualizada exitosamente")
                except Exception as e:
                    debug_print(f"Error actualizando tarea {task['content']}: {e}")

            return tasks
        except Exception as e:
            debug_print(f"Error en find_tasks_for_shot: {e}")
            return []

    def update_shot_status_if_needed(self, shot_id, shot_config):
        """Actualiza el estado del shot si es necesario."""
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return
        if shot_config["shot_ready"]:
            try:
                self.sg.update("Shot", shot_id, {"sg_status_list": "ready"})
                debug_print("Shot status actualizado a 'ready'")
            except Exception as e:
                debug_print(f"Error actualizando shot status: {e}")

    def update_task_status(self, task_id, status):
        """Actualiza el estado de una tarea."""
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return
        try:
            self.sg.update("Task", task_id, {"sg_status_list": status})
            debug_print(f"Task status actualizado a '{status}'")
        except Exception as e:
            debug_print(f"Error actualizando task status: {e}")

    def update_task_description(self, task_id, description):
        """Actualiza la descripcion de una tarea."""
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return
        try:
            self.sg.update("Task", task_id, {"sg_description": description})
            debug_print(f"Task description actualizada")
        except Exception as e:
            debug_print(f"Error actualizando task description: {e}")

    def create_shot(self, project_id, shot_code, shot_config, thumbnail_path=None):
        """Crea un shot en ShotGrid con los parametros configurados."""
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return None

        # Parametros predefinidos
        sequence_name = shot_config.get("sequence_name")
        task_template_name = "Template_comp"

        debug_print(f"Creando shot '{shot_code}' con configuracion personalizada...")

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

        # Crear el shot con la configuracion
        shot_data = {
            "project": {"type": "Project", "id": project_id},
            "code": shot_code,
            "description": shot_config["description"],
            "sg_sequence": {"type": "Sequence", "id": sequence_id},
            "task_template": {"type": "TaskTemplate", "id": task_template_id},
        }

        # Agregar status si esta configurado
        if shot_config["shot_ready"]:
            shot_data["sg_status_list"] = "ready"

        try:
            new_shot = self.sg.create("Shot", shot_data)
            debug_print(
                f"Shot creado exitosamente: {new_shot['code']} (ID: {new_shot['id']})"
            )

            # Subir thumbnail si se proporciono
            if thumbnail_path:
                debug_print(f"Subiendo thumbnail para shot: {shot_code}")
                upload_success = self.upload_thumbnail(
                    "Shot", new_shot["id"], thumbnail_path
                )
                if upload_success:
                    debug_print(
                        f"✅ Thumbnail subido exitosamente para shot: {shot_code}"
                    )
                else:
                    debug_print(f"❌ Error subiendo thumbnail para shot: {shot_code}")

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

    def process_selected_clips(self, shot_config, thumbnail_path=None):
        """Procesa los clips seleccionados en el timeline de Hiero."""
        clips_info = self.get_selected_clips_info()
        if not clips_info:
            return []

        results = []
        for clip_info in clips_info:
            shot, tasks = self.sg_manager.find_shot_and_tasks(
                clip_info["project_name"],
                clip_info["shot_code"],
                shot_config,
                thumbnail_path,
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
    def __init__(self, status_window, shot_config, thumbnail_path=None):
        super(CreateShotWorker, self).__init__()
        self.status_window = status_window
        self.shot_config = shot_config
        self.thumbnail_path = thumbnail_path
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            debug_print("=== Iniciando creacion de shots ===")

            # Obtener credenciales de Flow DENTRO del worker
            self.signals.step_update.emit("Obteniendo credenciales...")
            sg_url, sg_login, sg_password = get_flow_credentials_secure()
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
                    clip_info["project_name"],
                    clip_info["shot_code"],
                    self.shot_config,
                    self.thumbnail_path,
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


def get_flow_credentials_secure():
    sg_url, sg_login, sg_password = get_flow_credentials()
    if not sg_url or not sg_login or not sg_password:
        debug_print(
            "No se pudieron obtener las credenciales de Flow desde SecureConfig."
        )
        return None, None, None

    # Para Flow, usamos login directo en lugar de API key
    return sg_url, sg_login, sg_password


# Variables globales para mantener referencias
_status_window = None


def cleanup_thumbnail_file(thumbnail_path):
    """Limpia el archivo temporal del thumbnail."""
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            os.remove(thumbnail_path)
            debug_print(f"✅ Archivo temporal eliminado: {thumbnail_path}")
        except Exception as e:
            debug_print(f"❌ Error eliminando archivo temporal: {e}")


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

    # Primero obtener informacion de clips para mostrar en el dialogo de configuracion
    hiero_ops_temp = HieroOperations(None)
    clips_info = hiero_ops_temp.get_selected_clips_info()

    if not clips_info:
        QMessageBox.warning(
            None, "Error", "No se encontraron clips seleccionados en Hiero."
        )
        return

    # Obtener nombre de la secuencia activa
    sequence_name = get_active_sequence_name()
    if not sequence_name:
        QMessageBox.warning(
            None,
            "Error",
            "No se pudo obtener el nombre de la secuencia activa en Hiero.",
        )
        return

    # Mostrar dialogo de configuracion
    config_dialog = ShotConfigDialog(clips_info, sequence_name)
    if config_dialog.exec_() != QDialog.Accepted:
        # Limpiar thumbnail si el usuario cancela
        config_dialog.cleanup_thumbnail()
        return  # Usuario cancelo

    shot_config = config_dialog.get_config()
    if not shot_config:
        config_dialog.cleanup_thumbnail()
        return

        # Obtener la ruta del thumbnail antes de limpiar
    thumbnail_path = config_dialog.thumbnail_path

    # NO limpiar thumbnail hasta después del worker

    # Crear y mostrar ventana de estado
    _status_window = FlowStatusWindow("crear shot")
    _status_window.show()
    _status_window.show_processing_message()  # Mostrar mensaje de procesamiento

    # Crear worker para procesamiento en hilo separado
    worker = CreateShotWorker(_status_window, shot_config, thumbnail_path)

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
        lambda success, message, window=_status_window: (
            window.show_success(message) if window else None,
            cleanup_thumbnail_file(thumbnail_path),
        )
    )
    worker.signals.error.connect(
        lambda error_msg, window=_status_window: (
            window.show_error(error_msg) if window else None,
            cleanup_thumbnail_file(thumbnail_path),
        )
    )

    # Ejecutar en hilo separado
    QThreadPool.globalInstance().start(worker)

    debug_print("=== Worker iniciado en hilo separado ===")


def main():
    """Función principal para compatibilidad hacia atrás."""
    create_shots_from_selected_clips()


if __name__ == "__main__":
    main()
