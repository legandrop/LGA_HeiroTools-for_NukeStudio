"""
__________________________________________________________________

  LGA_NKS_Flow_Shot_info v1.80 - Lega Pugliese
  Imprime informacion del shot y las versiones de la task comp
__________________________________________________________________

"""

import hiero.core
import os
import re
import json
import sys
import sqlite3
import subprocess
import platform
from PySide2.QtCore import QCoreApplication, Qt, QSize, Signal
from PySide2.QtGui import QFontMetrics, QKeySequence, QPixmap, QCursor
from PySide2.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QTextEdit,
    QApplication,
    QShortcut,
    QScrollArea,
    QLabel,
    QFrame,
)


# Variable global para activar o desactivar los prints
DEBUG = False


def debug_print(*message):
    if DEBUG:
        print(*message)


def extract_frame_from_filename(filename):
    """
    Extrae el numero de frame de un nombre de archivo de attachment.
    Los archivos siguen el patron: {shot_name}_{task_name}_v{version_number}_{frame_number}[_{counter}].{extension}
    Retorna el numero de frame o "---" si no encuentra
    """
    try:
        # Obtener solo el nombre sin extension
        name_without_ext = os.path.splitext(os.path.basename(filename))[0]
        debug_print(f"Extrayendo frame de: {name_without_ext}")

        # Separar por guiones bajos
        parts = name_without_ext.split("_")

        # Patron 1: Buscar despues de v{numero} debe venir el frame
        for i, part in enumerate(parts):
            if part.lower().startswith("v") and len(part) > 1 and part[1:].isdigit():
                # Encontramos la version, el siguiente elemento deberia ser el frame
                if i + 1 < len(parts) and parts[i + 1].isdigit():
                    frame_number = parts[i + 1]
                    debug_print(f"Frame encontrado (patron v_frame): {frame_number}")
                    return frame_number

        # Patron 2: Buscar cualquier parte que sea solo numeros y tenga 2-4 digitos (frame range tipico)
        for part in parts:
            if part.isdigit() and 2 <= len(part) <= 4:
                debug_print(f"Frame encontrado (patron numerico): {part}")
                return part

        # Patron 3: Buscar numeros al final del nombre
        if parts and parts[-1].isdigit():
            debug_print(f"Frame encontrado (final): {parts[-1]}")
            return parts[-1]

        debug_print("No se encontro numero de frame en el nombre del archivo")
        return "---"

    except Exception as e:
        debug_print(f"Error al extraer frame: {e}")
        return "---"


class ThumbnailWidget(QLabel):
    """Widget personalizado para mostrar un thumbnail clickeable"""

    def __init__(self, image_path, thumbnail_size=80):
        super().__init__()
        self.image_path = image_path
        self.thumbnail_size = thumbnail_size
        self.original_pixmap = None
        self.load_image()
        self.update_size()
        self.setAlignment(Qt.AlignCenter)
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setStyleSheet(
            """
            QLabel {
                border: 0px solid #444444;
                background-color: #2a2a2a;
                margin: 2px;
                padding: 2px;
            }
            QLabel:hover {
                border: 0px solid #007ACC;
            }
        """
        )

    def load_image(self):
        """Carga la imagen original"""
        try:
            if os.path.exists(self.image_path):
                self.original_pixmap = QPixmap(self.image_path)
                if self.original_pixmap.isNull():
                    debug_print(f"No se pudo cargar la imagen: {self.image_path}")
                    self.create_placeholder()
            else:
                debug_print(f"Archivo de imagen no existe: {self.image_path}")
                self.create_placeholder()
        except Exception as e:
            debug_print(f"Error al cargar imagen {self.image_path}: {e}")
            self.create_placeholder()

    def create_placeholder(self):
        """Crea un pixmap de placeholder"""
        self.original_pixmap = QPixmap(self.thumbnail_size, self.thumbnail_size)
        self.original_pixmap.fill(Qt.gray)

    def update_size(self):
        """Actualiza el tamaño del thumbnail manteniendo la relación de aspecto"""
        if self.original_pixmap and not self.original_pixmap.isNull():
            scaled_pixmap = self.original_pixmap.scaled(
                self.thumbnail_size,
                self.thumbnail_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self.setPixmap(scaled_pixmap)
            self.setFixedSize(
                self.thumbnail_size + 4, self.thumbnail_size + 4
            )  # +4 for border and padding

    def mousePressEvent(self, event):
        """Maneja el evento de clic del mouse para abrir la imagen"""
        if event.button() == Qt.LeftButton:
            debug_print(f"Abriendo imagen: {self.image_path}")
            try:
                if platform.system() == "Windows":
                    os.startfile(self.image_path)
                elif platform.system() == "Darwin":  # macOS
                    subprocess.Popen(["open", self.image_path])
                else:  # Linux
                    subprocess.Popen(["xdg-open", self.image_path])
            except Exception as e:
                debug_print(f"Error al abrir imagen: {e}")
        super().mousePressEvent(event)


class ThumbnailContainerWidget(QWidget):
    """Widget contenedor que incluye thumbnail y frame number"""

    def __init__(self, image_path, thumbnail_size=80):
        super().__init__()
        self.image_path = image_path
        self.thumbnail_size = thumbnail_size
        self.setup_ui()

    def setup_ui(self):
        """Configura la interfaz del contenedor"""
        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(2, 2, 2, 2)

        # Thumbnail principal
        self.thumbnail = ThumbnailWidget(self.image_path, self.thumbnail_size)
        layout.addWidget(self.thumbnail, alignment=Qt.AlignCenter)

        # Label de frame number
        frame_number = extract_frame_from_filename(self.image_path)
        self.frame_label = QLabel(f"f{frame_number}")
        self.frame_label.setStyleSheet(
            "color: #cccccc; font-size: 10px; background-color: transparent;"
        )
        self.frame_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.frame_label, alignment=Qt.AlignCenter)


app = None
window = None


class ShotGridManager:
    """Clase para manejar operaciones con datos de la base de datos SQLite en lugar de JSON."""

    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

    def find_project(self, project_name):
        cur = self.conn.cursor()
        cur.execute("SELECT * FROM projects WHERE project_name = ?", (project_name,))
        return cur.fetchone()

    def find_shot(self, project_name, shot_code):
        cur = self.conn.cursor()
        cur.execute(
            """
            SELECT s.* FROM shots s
            JOIN projects p ON s.project_id = p.id
            WHERE p.project_name = ? AND s.shot_name = ?
            """,
            (project_name, shot_code),
        )
        shot = cur.fetchone()
        if not shot:
            return None
        # Estructura igual al JSON original
        shot_dict = {
            "shot_name": shot["shot_name"],
            "sequence": shot["sequence"],
            "tasks": [],
        }
        # Obtener las tasks asociadas a este shot
        cur.execute("SELECT * FROM tasks WHERE shot_id = ?", (shot["id"],))
        tasks = cur.fetchall()
        for task in tasks:
            task_dict = {
                "task_type": task["task_type"],
                "task_description": task["task_description"],
                "task_status": task["task_status"],
                "task_assigned_to": None,
                "versions": [],
            }
            # Obtener asignado
            cur.execute(
                "SELECT assigned_to FROM task_assignments WHERE task_id = ?",
                (task["id"],),
            )
            assign = cur.fetchone()
            if assign:
                task_dict["task_assigned_to"] = assign["assigned_to"]
            else:
                task_dict["task_assigned_to"] = "No asignado"
            # Obtener versiones
            cur.execute(
                "SELECT * FROM versions WHERE task_id = ? ORDER BY version_number DESC",
                (task["id"],),
            )
            versions = cur.fetchall()
            for v in versions:
                # Obtener comentarios/notas de la version con información de attachments
                cur.execute(
                    "SELECT content, created_by, created_on, local_attachment_paths FROM version_notes WHERE version_id = ? ORDER BY created_on DESC",
                    (v["id"],),
                )
                notes = cur.fetchall()
                comments = []
                for n in notes:
                    # Procesar attachment paths si existen
                    attachment_paths = []
                    if n["local_attachment_paths"]:
                        # Los paths están separados por punto y coma
                        paths = n["local_attachment_paths"].split(";")
                        for path in paths:
                            path = path.strip()
                            if path and os.path.exists(path):
                                attachment_paths.append(path)

                    comments.append(
                        {
                            "user": n["created_by"] or "",
                            "text": n["content"] or "",
                            "date": n["created_on"],
                            "attachments": attachment_paths,
                        }
                    )
                version_dict = {
                    "version_number": f"v{v['version_number']:03d}",
                    "version_description": v["description"] or "",
                    "version_date": v["created_on"] or "",
                    "created_by": v["created_by"] or "Unknown",
                    "comments": comments,
                }
                task_dict["versions"].append(version_dict)
            shot_dict["tasks"].append(task_dict)
        return shot_dict

    def find_task(self, shot, task_name):
        for t in shot["tasks"]:
            if t["task_type"].lower() == task_name.lower():
                return t
        return None

    def close(self):
        if hasattr(self, "conn") and self.conn:
            self.conn.close()


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

    def process_selected_clips(self):
        """Procesa los clips seleccionados en el timeline de Hiero."""
        debug_print("Processing selected clips...")
        seq = hiero.ui.activeSequence()
        if seq:
            te = hiero.ui.getTimelineEditor(seq)
            selected_clips = te.selection()
            results = []

            if selected_clips:
                for clip in selected_clips:
                    if isinstance(clip, hiero.core.EffectTrackItem):
                        continue  # Pasar de largo los clips que sean efectos

                    file_path = clip.source().mediaSource().fileinfos()[0].filename()
                    exr_name = os.path.basename(file_path)
                    base_name, version_number = self.parse_exr_name(exr_name)

                    project_name = base_name.split("_")[0]
                    parts = base_name.split("_")
                    shot_code = "_".join(parts[:5])

                    # Realizar operacion intensiva en el JSON
                    QCoreApplication.processEvents()
                    shot = self.sg_manager.find_shot(project_name, shot_code)
                    debug_print(f"Shot found: {shot}")

                    QCoreApplication.processEvents()
                    if shot:
                        task = self.sg_manager.find_task(shot, "comp")
                        debug_print(f"Task found: {task}")
                        task_description = (
                            task["task_description"] if task else "No info available"
                        )
                        assignee = task["task_assigned_to"] if task else "No assignee"
                        versions = task["versions"] if task else []

                        # Obtener las tres ultimas versiones
                        last_versions = sorted(
                            versions, key=lambda v: v["version_date"], reverse=True
                        )
                        version_info = []
                        for v in last_versions:
                            match = re.search(r"v(\d+)", v["version_number"])
                            version_number = (
                                match.group() if match else v["version_number"]
                            )
                            version_info.append(
                                {
                                    "version_number": version_number,
                                    "version_description": v["version_description"]
                                    or "No description",
                                    "comments": v.get("comments", []),
                                    "created_by": v.get("created_by", "Unknown"),
                                }
                            )

                        shot_info = {
                            "shot_code": shot["shot_name"],
                            "description": task_description,
                            "assignee": assignee,
                            "versions": version_info,
                        }
                        results.append(shot_info)
                    QCoreApplication.processEvents()
            debug_print("Processing completed.")
            return results
        else:
            debug_print("No se encontro una secuencia activa en Hiero.")
            return []


class GUIWindow(QWidget):
    def __init__(self, hiero_ops, parent=None):
        super(GUIWindow, self).__init__(parent)
        self.hiero_ops = hiero_ops
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Info")
        self.setStyleSheet("background-color: #2a2a2a; color: #cccccc;")
        self.setMinimumSize(800, 600)

        # Layout principal
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Scroll area para el contenido
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet(
            """
            QScrollArea {
                border: none;
                background-color: #2a2a2a;
            }
            QScrollBar:vertical {
                background-color: #333333;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #666666;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #888888;
            }
        """
        )

        # Widget contenedor para el scroll
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setSpacing(15)
        self.scroll_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area)

        # Anadir evento para cerrar la ventana con la tecla ESC
        shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        shortcut.activated.connect(self.close)

    def closeEvent(self, event):
        # Cerrar la conexión de sg_manager si existe
        if hasattr(self.hiero_ops, "sg_manager") and self.hiero_ops.sg_manager:
            self.hiero_ops.sg_manager.close()
            self.hiero_ops.sg_manager = None
        super(GUIWindow, self).closeEvent(event)

    def create_shot_header_widget(self, shot_code, assignee, description):
        """Crea el widget de cabecera para un shot"""
        header_widget = QWidget()
        header_layout = QVBoxLayout(header_widget)
        header_layout.setSpacing(5)
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Titulo del shot y asignado
        title_label = QLabel(
            f"<b style='color:#CCCC00; font-size:14px;'>{shot_code}</b> | <span style='color:#007ACC; font-weight:bold;'>{assignee}</span>"
        )
        title_label.setStyleSheet("background-color: transparent;")
        header_layout.addWidget(title_label)

        # Descripcion
        if description and description != "Sin descripcion":
            desc_label = QLabel(
                f"<span style='color:#009688; font-weight:bold;'>Description:</span> {description}"
            )
            desc_label.setStyleSheet("background-color: transparent;")
            desc_label.setWordWrap(True)
            header_layout.addWidget(desc_label)

        return header_widget

    def create_version_widget(self, version):
        """Crea el widget para una version"""
        version_widget = QWidget()
        version_layout = QVBoxLayout(version_widget)
        version_layout.setSpacing(0)
        version_layout.setContentsMargins(
            20, 20, 0, 20
        )  # Indentacion para las versiones, sin margenes extras

        # Titulo de la version y descripcion combinados
        version_number = version["version_number"].split("_")[-1]
        version_creator = version.get("created_by", "Unknown")
        version_description = version["version_description"] or ""

        # Combinar en un solo QLabel con HTML y salto de linea
        combined_text = (
            f"<span style='color:#007ACC; font-weight:bold;'>{version_number}</span> | "
            f"<span style='color:#AAAAAA;'>{version_creator}</span>"
        )

        if version_description:
            combined_text += f"<br/><br/><span style='color:#CCCCCC; font-size:12px;'>{version_description}</span>"

        version_label = QLabel(combined_text)
        # Ajustar line-height y eliminar margenes/rellenos para reducir el espacio vertical
        version_label.setStyleSheet(
            "background-color: transparent; padding: 0px; margin: 0px; line-height: 0.8;"
        )
        version_label.setWordWrap(True)
        version_layout.addWidget(version_label)

        # Comentarios de la version
        for comment in version.get("comments", []):
            comment_widget = self.create_comment_widget(comment)
            version_layout.addWidget(comment_widget)

        return version_widget

    def create_comment_widget(self, comment):
        """Crea el widget para un comentario con sus attachments"""
        comment_widget = QWidget()
        comment_layout = QVBoxLayout(comment_widget)
        comment_layout.setSpacing(5)
        comment_layout.setContentsMargins(
            30, 0, 0, 0
        )  # Indentacion para los comentarios

        # Texto del comentario
        comment_user = comment["user"]
        comment_text = comment["text"] if comment["text"] else ""
        attachments = comment.get("attachments", [])

        # Si hay texto de comentario, mostrarlo
        if comment_text:
            # Procesar saltos de linea para el display
            comment_text_processed = comment_text.replace("\n\n", "<br><br>").replace(
                "\n", "<br>"
            )
            comment_label = QLabel(
                f"<b style='color:#AAAAAA;'>{comment_user}:</b> {comment_text_processed}"
            )
            comment_label.setStyleSheet("background-color: transparent;")
            comment_label.setWordWrap(True)
            comment_layout.addWidget(comment_label)
        elif attachments:
            # Si no hay texto pero hay attachments, mostrar solo el usuario
            user_label = QLabel(f"<b style='color:#AAAAAA;'>{comment_user}:</b>")
            user_label.setStyleSheet("background-color: transparent;")
            comment_layout.addWidget(user_label)

        # Thumbnails de attachments si existen
        if attachments:
            thumbnails_widget = self.create_thumbnails_widget(attachments)
            comment_layout.addWidget(thumbnails_widget)

        return comment_widget

    def create_thumbnails_widget(self, attachment_paths):
        """Crea el widget que contiene los thumbnails de los attachments"""
        thumbnails_widget = QWidget()
        thumbnails_layout = QHBoxLayout(thumbnails_widget)
        thumbnails_layout.setSpacing(5)
        thumbnails_layout.setContentsMargins(0, 5, 0, 5)
        thumbnails_layout.setAlignment(Qt.AlignLeft)

        for attachment_path in attachment_paths:
            # Verificar que sea un archivo de imagen
            if attachment_path.lower().endswith(
                (".jpg", ".jpeg", ".png", ".tiff", ".tif")
            ):
                thumbnail_container = ThumbnailContainerWidget(
                    attachment_path, thumbnail_size=80
                )
                thumbnails_layout.addWidget(thumbnail_container)

        # Añadir stretch para empujar thumbnails a la izquierda
        thumbnails_layout.addStretch()

        return thumbnails_widget

    def display_results(self, results):
        """Muestra los resultados recopilados en una ventana independiente."""
        debug_print("Displaying results...")

        # Limpiar contenido anterior
        for i in reversed(range(self.scroll_layout.count())):
            child = self.scroll_layout.itemAt(i).widget()
            if child:
                child.setParent(None)

        if not results:
            no_results_label = QLabel("No se encontraron resultados")
            no_results_label.setAlignment(Qt.AlignCenter)
            no_results_label.setStyleSheet("color: #888888; font-size: 14px;")
            self.scroll_layout.addWidget(no_results_label)
            self.show()
            return

        for result in results:
            debug_print(f"Processing result: {result}")

            # Procesar datos del shot
            description = (
                result["description"]
                if result["description"] is not None
                else "Sin descripcion"
            )
            assignee = (
                result["assignee"] if result["assignee"] is not None else "No assignee"
            )
            shot_code = result["shot_code"]
            versions = result["versions"]

            # Crear widget del shot
            shot_widget = QFrame()
            shot_widget.setFrameStyle(QFrame.Box)
            shot_widget.setStyleSheet(
                """
                QFrame {
                    border: 0px solid #444444;
                    border-radius: 5px;
                    background-color: #333333;
                    margin: 5px;
                    padding: 10px;
                }
            """
            )

            shot_layout = QVBoxLayout(shot_widget)
            shot_layout.setSpacing(10)

            # Agregar cabecera del shot
            header_widget = self.create_shot_header_widget(
                shot_code, assignee, description
            )
            shot_layout.addWidget(header_widget)

            # Agregar versiones
            for version in versions:
                version_widget = self.create_version_widget(version)
                shot_layout.addWidget(version_widget)

            self.scroll_layout.addWidget(shot_widget)

        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.show()
        debug_print("Results displayed successfully.")


def main():
    global app, window
    # Usar la ruta hardcodeada de la base de datos
    db_path = r"C:/Portable/LGA/PipeSync/cache/pipesync.db"
    if not os.path.exists(db_path):
        debug_print(f"DB file not found at path: {db_path}")
        return
    sg_manager = ShotGridManager(db_path)
    hiero_ops = HieroOperations(sg_manager)
    if not QApplication.instance():
        app = QApplication(sys.argv)
    else:
        app = QApplication.instance()
    window = GUIWindow(hiero_ops)
    results = hiero_ops.process_selected_clips()
    debug_print(f"Results: {results}")
    window.display_results(results)
    window.show()
    app.exec_()


if __name__ == "__main__":
    main()
