"""
____________________________________________________________________

  LGA_NKS_Flow_Shot_info v1.93 | Lega

  Imprime informacion del shot y las versiones de la task seleccionada
  (comp, roto o cleanup) en el playhead.

  v1.93: Muestra replies de notas como hilos anidados y limita la linea vertical
         al contenedor exterior, sin bordes extra en autor ni contenido.
  v1.92: Project name extraído desde el segmento VFX-NOMBRE del path del archivo
         (con fallback al primer bloque del filename si el path no contiene VFX-).
         Corrige proyectos como MORLASP cuyos shots tienen prefijo MOR en el filename.
  v1.91: Recupera descripcion de task inicial y texto del header de version.
  v1.90: Wrap de textos sin scroll horizontal y resaltado de comentarios de playlist.
  v1.89: Identacion comentarios, comentarios de playlist, colores de nombres de usuario
  v1.88: UI unificada con la de PipeSync (FlowNotesPopover).
         - Titulo: shot_code | task_type | assignee.
         - Header morado por version con "vNNN | subida X | por Y" y
           "Time logged: Xh/Xd" tomado de task_timelogs.
         - Descripcion con label "Descripcion: (por autor)".
         - Comentarios con separador horizontal y label
           "Comentario: (por autor, fecha a las HH:mm)".
         - Thumbnails 150px con label "Frame N" desde attachment_info.
         - Filtra notas espejo de descripcion (0-300s) y duplicados de content.
         - Fechas formateadas como en DateUtils::formatFriendlyDate.
  v1.87: Filtra notas auto-generadas por PipeSync al subir una version.
         Cuando el usuario sube una version desde PipeSync, se crea un
         comentario con el mismo contenido que la descripcion de la version,
         por el mismo usuario y unos segundos despues. Ese comentario duplicado
         ahora se descarta (umbral configurable, default 120s).
  v1.86: Soporte multi-task. Si el playhead atraviesa clips de varias tasks
         (TASK_EXR_TRACKS), muestra el popover compartido `LGA_NKS_TaskSelectionDialog`
         para que el usuario elija. Antes pedía siempre la task 'comp', así que
         nunca mostraba descripción/notas de roto o cleanup.
  v1.85: Actualizado para usar las clases del adapter para compatibilidad PySide2/6
  v1.84: Actualizado para ser compatible con ambos sistemas de nomenclatura:
         - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
         - PROYECTO_SEQ_SHOT (3 bloques simplificado)
____________________________________________________________________

"""

import hiero.core
import hiero.ui
import os
import re
import json
import sys
import sqlite3
import subprocess
import platform
import logging
import queue
import time
import importlib
from datetime import datetime, timezone
from logging.handlers import QueueHandler, QueueListener
from pathlib import Path
# Importar compatibilidad Qt para Hiero Panels
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, QShortcut, QApplication
from LGA_NKS_Shared.LGA_NKS_PipeSyncPaths import get_pipesync_db_path

# Usar directamente las clases del adapter (ya manejan compatibilidad PySide2/6)
QCoreApplication = QApplication  # Para compatibilidad
Qt = QtCore.Qt
QSize = QtCore.QSize
Signal = QtCore.Signal
QFontMetrics = QtGui.QFontMetrics
QKeySequence = QtGui.QKeySequence
QPixmap = QtGui.QPixmap
QCursor = QtGui.QCursor
QWidget = QtWidgets.QWidget
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QTextEdit = QtWidgets.QTextEdit
QScrollArea = QtWidgets.QScrollArea
QLabel = QtWidgets.QLabel
QFrame = QtWidgets.QFrame
QPushButton = QtWidgets.QPushButton
QSizePolicy = QtWidgets.QSizePolicy
QIcon = QtGui.QIcon
QColor = QtGui.QColor

DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True

script_start_time = None
debug_log_listener = None


class RelativeTimeFormatter(logging.Formatter):
    """Formatter que incluye tiempo relativo desde el inicio del script."""

    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created
        relative_time = record.created - script_start_time
        record.relative_time = f"{relative_time:.3f}s"
        return super().format(record)


def setup_debug_logging(script_name="FlowShotInfo"):
    """Configura el logging para escribir solo en archivo."""
    global debug_log_listener

    log_filename = f"DebugPy_{script_name}.log"
    log_file_path = os.path.join(os.path.dirname(__file__), "..", "logs", log_filename)
    log_file_path = os.path.normpath(log_file_path)

    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    try:
        with open(log_file_path, "w", encoding="utf-8") as handle:
            handle.write(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    except Exception:
        pass

    logger_name = f"{script_name.lower()}_logger"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:
        logger.handlers.clear()

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    formatter = RelativeTimeFormatter("[%(relative_time)s] %(message)s")
    file_handler.setFormatter(formatter)

    log_queue = queue.Queue()
    queue_handler = QueueHandler(log_queue)
    queue_handler.setLevel(logging.DEBUG)
    logger.addHandler(queue_handler)

    if debug_log_listener:
        try:
            debug_log_listener.stop()
        except Exception:
            pass

    debug_log_listener = QueueListener(
        log_queue, file_handler, respect_handler_level=True
    )
    debug_log_listener.daemon = True
    debug_log_listener.start()

    return logger


debug_logger = setup_debug_logging(script_name="FlowShotInfo")


def debug_print(*message, level="info"):
    """Loggea por defecto a archivo y opcionalmente a consola."""
    global script_start_time

    msg = " ".join(str(arg) for arg in message)

    if DEBUG and DEBUG_LOG:
        if script_start_time is None:
            script_start_time = time.time()
        if level == "debug":
            debug_logger.debug(msg)
        elif level == "warning":
            debug_logger.warning(msg)
        elif level == "error":
            debug_logger.error(msg)
        else:
            debug_logger.info(msg)

    if DEBUG and DEBUG_CONSOLE:
        if script_start_time is None:
            script_start_time = time.time()
        relative_time = time.time() - script_start_time
        print(f"[{relative_time:.3f}s] {msg}")

# Importar utilidades de naming desde shareds de dominio Flow
flow_shared_dir = Path(__file__).parent.parent / "LGA_NKS_Shared"
sys.path.append(str(flow_shared_dir))
from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    extract_project_name_from_path,
    clean_base_name,
)

# Importar módulo utilitario para obtener clips
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
HAS_CLIP_UTILS = False
if utils_path.exists():
    try:
        sys.path.insert(0, str(utils_path))
        from LGA_NKS_Shared.LGA_NKS_GetClip import get_clip_to_process, get_selected_clips
        from LGA_NKS_Shared import LGA_NKS_GetClip as clip_utils
        from LGA_NKS_Shared.LGA_NKS_TaskSelectionDialog import (
            resolve_task_at_playhead,
            track_for_task,
        )
        HAS_CLIP_UTILS = True
    except ImportError as e:
        debug_print(f"Error importando módulo LGA_NKS_GetClip: {e}")


# Umbral (en segundos) para considerar que una nota fue auto-generada al subir
# una version desde PipeSync. Si la nota tiene mismo autor y mismo contenido
# que la descripcion de la version, y se creo dentro de este umbral, se descarta.
VERSION_DUPLICATE_NOTE_WINDOW_SECONDS = 600


# --------------------------------------------------------------------------- #
# Paleta y QSS (port directo de PipeSync 2: mainwindow.cpp + flow_notes.qss)
# --------------------------------------------------------------------------- #
COLORS = {
    "bg_principal": "#161616",
    "bg_popover": "#232323",
    "bg_version_container": "#1e1e1e",
    "bg_version_header": "#3C3764",
    "border_principal": "#303030",
    "txt_principal": "#B2B2B2",
    "txt_principal_strong": "#dddddd",
    "txt_secundario": "#929292",
    "txt_subtle": "#cccccc",
    "txt_desc_title": "#d8d8d8",
    "txt_desc_meta": "#b8b8b8",
    "txt_body": "#909090",
    "txt_playlist": "#ffcc33",
    "attachment_label_bg": "#2D2A26",
    "attachment_label_fg": "#8B7355",
}

SHOT_INFO_QSS = """
QWidget#flowNotesContentWidget {
    background-color: %(bg_popover)s;
}
QWidget#flowNotesHeaderWidget {
    background-color: %(bg_popover)s;
    border-bottom: 1px solid rgba(48, 48, 48, 0.7);
}
QLabel#flowNotesTitle {
    color: %(txt_principal)s;
    font-family: "Segoe UI", "Inter", Arial, Helvetica, sans-serif;
    font-weight: 500;
    font-size: 18px;
    background-color: transparent;
}
QLabel#flowTaskDescription {
    background-color: transparent;
    border: none;
    font-size: 14px;
    padding: 0px;
    margin: 0px;
}
QScrollArea#flowNotesScrollArea {
    background-color: transparent;
    border: none;
}
QWidget#flowNotesScrollContent {
    background-color: transparent;
}
QScrollArea#flowNotesScrollArea QScrollBar:vertical {
    background-color: #252525; width: 8px; margin: 0px; border-radius: 4px;
}
QScrollArea#flowNotesScrollArea QScrollBar::handle:vertical {
    background-color: #2E2E2E; min-height: 30px; border-radius: 4px;
}
QScrollArea#flowNotesScrollArea QScrollBar::handle:vertical:hover {
    background-color: #3D3D3D;
}
QScrollArea#flowNotesScrollArea QScrollBar::add-line:vertical,
QScrollArea#flowNotesScrollArea QScrollBar::sub-line:vertical {
    height: 0px; background: none;
}
QWidget#flowVersionContainer {
    background-color: %(bg_version_container)s;
    border: 1px solid rgba(48, 48, 48, 0.6);
    border-radius: 6px;
}
QWidget#flowVersionHeader {
    background-color: %(bg_version_header)s;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}
QLabel#flowVersionInfo {
    background-color: transparent; font-size: 14px; font-weight: 500;
}
QLabel#flowVersionTimeLogged {
    background-color: transparent; font-size: 13px; font-weight: 400;
}
QLabel#flowVersionDescriptionTitle,
QLabel#flowVersionDescriptionContent {
    background-color: transparent; font-size: 14px; border: none; padding: 4px 0px;
}
QWidget#flowVersionCommentsContainer {
    background-color: transparent; border-radius: 4px;
}
QWidget#flowVersionComment { background-color: transparent; }
QWidget#flowVersionCommentReply {
    border-left: 2px solid #555555;
    background-color: transparent;
}
QFrame#flowCommentSeparator {
    color: %(border_principal)s;
    background-color: %(border_principal)s;
    border: none; max-height: 1px;
}
QLabel#flowVersionCommentHeader {
    background-color: transparent; padding-top: 4px;
    font-size: 14px; font-weight: 400;
}
QLabel#flowVersionCommentContent {
    background-color: transparent; color: #909090; font-size: 14px;
    border: none; padding: 0; margin: 0;
}
QLabel#flowVersionCommentAttachment {
    color: %(attachment_label_fg)s;
    background-color: %(attachment_label_bg)s;
    border-radius: 0px; font-size: 13px;
}
QPushButton#flowVersionCommentThumbnail {
    border: 2px solid #404040; border-radius: 8px;
    background-color: transparent; padding: 2px;
}
QPushButton#flowVersionCommentThumbnail:hover {
    border-color: #606060; background-color: rgba(255, 255, 255, 0.05);
}
""" % COLORS


# --------------------------------------------------------------------------- #
# Formato de fechas (port de DateUtils::formatFriendlyDate de PipeSync 2)
# --------------------------------------------------------------------------- #
_MONTHS_SHORT = {
    1: "Ene", 2: "Feb", 3: "Mar", 4: "Abr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dic",
}


def _format_friendly_date(dt, include_time=False):
    """Reproduce DateUtils::formatFriendlyDate del PipeSync C++."""
    if dt is None:
        return "Fecha desconocida"
    today = datetime.now(dt.tzinfo).date() if dt.tzinfo else datetime.now().date()
    date_day = dt.date()
    days_diff = (today - date_day).days

    if days_diff > 0:
        if days_diff == 1:
            out = "Ayer"
        elif days_diff <= 15:
            out = f"Hace {days_diff} dias"
        elif date_day.year == today.year:
            out = f"{date_day.day} {_MONTHS_SHORT[date_day.month]}"
        else:
            out = f"{date_day.day} {_MONTHS_SHORT[date_day.month]} {date_day.year % 100}"
    elif days_diff == 0:
        out = "Hoy"
    else:
        d = -days_diff
        if d == 1:
            out = "Manana"
        elif d == 2:
            out = "Pasado manana"
        elif d <= 15:
            out = f"Dentro de {d} dias"
        elif date_day.year == today.year:
            out = f"{date_day.day} {_MONTHS_SHORT[date_day.month]}"
        else:
            out = f"{date_day.day} {_MONTHS_SHORT[date_day.month]} {date_day.year % 100}"

    if include_time:
        out += f" a las {dt.strftime('%H:%M')}"
    return out


def _format_logged_time(minutes):
    """Reproduce el formato de Time logged de PipeSync (8h = 1 dia)."""
    if not minutes or minutes <= 0:
        return ""
    days = minutes / (8.0 * 60.0)
    if days >= 1.0:
        return f"{days:.1f}d"
    hours = minutes / 60.0
    return f"{hours:.1f}h"


def _html_escape(text):
    return (
        (text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# --------------------------------------------------------------------------- #
# Colores de autores en notas (port de ShotCard_UI.cpp / getAssigneeReadableTextColor)
# --------------------------------------------------------------------------- #
_FALLBACK_USER_COLORS = {
    "lega pugliese":     "#50214A",
    "sebas romano":      "#4A2D3C",
    "mariel falco":      "#3C3809",
    "patricio barreiro": "#114829",
    "matias moretti":    "#291148",
    "ignacio jamilis":   "#481111",
}
_USER_COLOR_FEDE_BLESA = "#b084ff"
_USER_COLOR_UNKNOWN    = "#d6c94a"


def _load_user_colors_from_json():
    """Carga colores desde LGA_NKS_Flow_Users.json (mismo archivo que el panel Assignee)."""
    json_path = Path(__file__).parent.parent / "LGA_NKS_Flow_Users.json"
    colors = {}
    try:
        if json_path.exists():
            with open(json_path, encoding="utf-8") as fh:
                data = json.load(fh)
            for entry in data.get("users", []):
                name   = (entry.get("name")        or "").strip()
                wasabi = (entry.get("wasabi_user")  or "").strip()
                hex_c  = (entry.get("color")        or "").strip()
                if not hex_c or not hex_c.startswith("#"):
                    continue
                if name:
                    colors[name.casefold()] = hex_c
                if wasabi:
                    colors[wasabi.casefold()] = hex_c
    except Exception as exc:
        debug_print(f"Error cargando LGA_NKS_Flow_Users.json: {exc}", level="warning")
    return colors


# Cargar una sola vez al importar el modulo
_USER_COLORS = _load_user_colors_from_json()


def _get_user_text_color(user_name):
    """Devuelve color CSS legible para un autor (port de getAssigneeReadableTextColor).

    Reglas:
    - Fede Blesa: siempre #b084ff.
    - Buscar en JSON; si no, en fallback hardcodeado.
    - Si no se encuentra: amarillo #d6c94a.
    - El color base se aclara iterativamente hasta brillo percibido >= 155.
    """
    if not user_name:
        return _USER_COLOR_UNKNOWN
    normalized = user_name.strip().casefold()
    if normalized == "fede blesa":
        return _USER_COLOR_FEDE_BLESA
    base_hex = _USER_COLORS.get(normalized) or _FALLBACK_USER_COLORS.get(normalized)
    if not base_hex:
        return _USER_COLOR_UNKNOWN
    color = QColor(base_hex)
    if not color.isValid():
        return _USER_COLOR_UNKNOWN
    for _ in range(50):
        brightness = (color.red() * 299 + color.green() * 587 + color.blue() * 114) // 1000
        if brightness >= 155:
            break
        color = color.lighter(118)
        if color.red() >= 245 and color.green() >= 245 and color.blue() >= 245:
            break
    return color.name()


def _user_name_span(user_name):
    """Nombre de usuario coloreado como <span> HTML (port de userColorSpan() de C++)."""
    safe = _html_escape((user_name or "").strip())
    if not safe:
        return ""
    return f"<span style='color: {_get_user_text_color(user_name)};'>{safe}</span>"


def _playlist_meta_span(playlist_name):
    """Texto HTML para metadata de comentarios que vienen desde una playlist."""
    safe_name = _html_escape((playlist_name or "").strip())
    playlist_word = (
        f"<span style='color: {COLORS['txt_playlist']}; font-weight: 800;'>playlist</span>"
    )
    if safe_name:
        return f"{playlist_word}: {safe_name}"
    return playlist_word


def _parse_pipesync_datetime(value):
    """Parsea el formato de fecha de pipesync.db ('YYYY-MM-DD HH:MM:SS[+/-HH:MM]').

    Retorna un datetime con tzinfo o None si no se puede parsear.
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if not text:
        return None
    # SQLite suele guardar 'YYYY-MM-DD HH:MM:SS-03:00'. fromisoformat necesita 'T'.
    iso = text.replace(" ", "T", 1)
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        try:
            dt = datetime.strptime(text[:19], "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _is_version_upload_duplicate_note(note, version_description, version_created_by, version_created_on):
    """Detecta si una nota es la auto-generada por PipeSync al subir la version.

    Se considera duplicada cuando:
    - Mismo autor que la version.
    - Contenido (trim) igual a la descripcion de la version.
    - Fecha dentro de VERSION_DUPLICATE_NOTE_WINDOW_SECONDS respecto de la version.
    """
    note_user = (note["created_by"] or "").strip()
    version_user = (version_created_by or "").strip()
    if not note_user or note_user != version_user:
        return False

    note_text = (note["content"] or "").strip()
    desc_text = (version_description or "").strip()
    if not note_text or not desc_text or note_text != desc_text:
        return False

    note_dt = _parse_pipesync_datetime(note["created_on"])
    version_dt = _parse_pipesync_datetime(version_created_on)
    if not note_dt or not version_dt:
        # Si falta fecha pero coinciden autor y contenido, lo tratamos como duplicado.
        return True

    delta = abs((note_dt - version_dt).total_seconds())
    return delta <= VERSION_DUPLICATE_NOTE_WINDOW_SECONDS


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


class ThumbnailButton(QPushButton):
    """QPushButton que muestra un thumbnail de imagen y lo abre al hacer clic."""

    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setObjectName("flowVersionCommentThumbnail")
        self.setCursor(QCursor(Qt.PointingHandCursor))
        self.setFlat(True)

        pix = QPixmap(image_path)
        if pix.isNull():
            pix = QPixmap(150, 80)
            pix.fill(QColor("#3a3a3a"))
        else:
            pix = pix.scaledToWidth(150, Qt.SmoothTransformation)
        self.setIcon(QIcon(pix))
        self.setIconSize(pix.size())
        self.setFixedSize(pix.size())
        self.setToolTip(f"Clic para abrir: {os.path.basename(image_path)}")
        self.clicked.connect(self._open_image)

    def _open_image(self):
        debug_print(f"Abriendo imagen: {self.image_path}")
        try:
            if platform.system() == "Windows":
                os.startfile(self.image_path)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", self.image_path])
            else:
                subprocess.Popen(["xdg-open", self.image_path])
        except Exception as exc:
            debug_print(f"Error al abrir imagen: {exc}")


app = None
window = None


def find_project_for_sequence(target_sequence):
    """Busca el proyecto que contiene la secuencia activa."""
    if not target_sequence:
        return None

    for project in hiero.core.projects():
        try:
            for sequence in project.sequences():
                if sequence == target_sequence:
                    return project
        except Exception:
            continue
    return None


def get_playlist_panel_registration_state():
    """Chequea si el Playlist Panel fue registrado en esta sesion."""
    try:
        playlist_panel_module = sys.modules.get("LGA_NKS_Playlist_Panel")
        if playlist_panel_module is None:
            return False
        return getattr(playlist_panel_module, "playlistPanel", None) is not None
    except Exception as exc:
        debug_print("Error chequeando registro del Playlist Panel:", str(exc), level="warning")
        return False


def should_redirect_to_playlist_shot_info():
    """Determina si Flow Shot Info debe delegar al Shot Info de playlist."""
    if not HAS_CLIP_UTILS:
        return False

    sequence = hiero.ui.activeSequence()
    project = find_project_for_sequence(sequence)
    clip = get_clip_to_process(track_name=None, prioritize_multiple_selection=False)

    if not sequence or not project or not clip or isinstance(clip, list):
        debug_print(
            "Vendor dispatch skipped due to missing context.",
            f"sequence_present={bool(sequence)}",
            f"project_present={bool(project)}",
            f"clip_present={bool(clip)}",
            level="debug",
        )
        return False

    try:
        clip_name = clip.name()
    except Exception:
        clip_name = ""

    project_prefix = project.name().split("_")[0] if project.name() else ""
    clip_prefix = clip_name.split("_")[0] if clip_name else ""
    is_vendor = bool(project_prefix and clip_prefix and project_prefix != clip_prefix)

    playlist_panel_registered = get_playlist_panel_registration_state()
    current_user_is_master = False

    if not playlist_panel_registered:
        try:
            from LGA_NKS_Playlist_Panel_py.LGA_NKS_Playlist_Panel_Permissions import (
                is_current_user_master,
            )

            current_user_is_master = is_current_user_master()
        except Exception as exc:
            debug_print(
                "No se pudo chequear Master para vendor dispatch:",
                str(exc),
                level="warning",
            )

    debug_print(
        "Vendor dispatch context:",
        f"sequence_name='{sequence.name()}'",
        f"timeline_project_name='{project.name()}'",
        f"clip_name='{clip_name}'",
        f"project_prefix='{project_prefix}'",
        f"clip_prefix='{clip_prefix}'",
        f"is_vendor={is_vendor}",
        f"playlist_panel_registered={playlist_panel_registered}",
        f"current_user_is_master={current_user_is_master}",
    )

    return is_vendor and (playlist_panel_registered or current_user_is_master)


def run_playlist_shot_info():
    """Ejecuta el Shot Info del Playlist Panel."""
    module = importlib.import_module(
        "LGA_NKS_Playlist_Panel_py.LGA_NKS_FlowPlaylist_Shot_info"
    )
    module.main()


class ShotGridManager:
    """Clase para manejar operaciones con datos de la base de datos SQLite en lugar de JSON."""

    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._has_version_note_replies_table = self._table_exists(
            "version_note_replies"
        )

    def _table_exists(self, table_name):
        cur = self.conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        )
        return cur.fetchone() is not None

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
            # Obtener timelogs y agruparlos por numero de version (regex v0*N)
            timelog_minutes_by_version = {}
            try:
                cur.execute(
                    "SELECT duration, description FROM task_timelogs WHERE task_id = ?",
                    (task["id"],),
                )
                tl_re = re.compile(r"v0*(\d+)", re.IGNORECASE)
                for tl in cur.fetchall():
                    desc = (tl["description"] or "").strip()
                    m = tl_re.search(desc)
                    if not m:
                        continue
                    vn = int(m.group(1))
                    timelog_minutes_by_version[vn] = (
                        timelog_minutes_by_version.get(vn, 0.0)
                        + float(tl["duration"] or 0.0)
                    )
            except sqlite3.Error as exc:
                debug_print(
                    "Error consultando task_timelogs:", str(exc), level="warning"
                )
            # Obtener versiones
            cur.execute(
                "SELECT * FROM versions WHERE task_id = ? ORDER BY version_number DESC",
                (task["id"],),
            )
            versions = cur.fetchall()
            for v in versions:
                # Obtener comentarios/notas de la version con información de attachments
                cur.execute(
                    "SELECT id, content, created_by, created_on, local_attachment_paths, "
                    "attachment_info, from_playlist, playlist_name "
                    "FROM version_notes WHERE version_id = ? ORDER BY created_on ASC",
                    (v["id"],),
                )
                notes = cur.fetchall()
                comments = []
                seen_contents = set()
                for n in notes:
                    # Saltar la nota auto-generada por PipeSync al subir la version
                    # (mismo autor + mismo contenido que la descripcion + fecha cercana).
                    if _is_version_upload_duplicate_note(
                        n,
                        v["description"],
                        v["created_by"],
                        v["created_on"],
                    ):
                        debug_print(
                            "Skipping auto-generated upload note:",
                            f"version_id={v['id']}",
                            f"user='{n['created_by']}'",
                            f"note_date='{n['created_on']}'",
                            f"version_date='{v['created_on']}'",
                            level="debug",
                        )
                        continue
                    # Saltar duplicados de content exacto (igual que FlowNotesPopover de PipeSync)
                    content_key = (n["content"] or "").strip()
                    if content_key and content_key in seen_contents:
                        continue
                    seen_contents.add(content_key)
                    # Procesar attachment paths si existen
                    attachment_paths = []
                    if n["local_attachment_paths"]:
                        for path in n["local_attachment_paths"].split(";"):
                            path = path.strip()
                            if path and os.path.exists(path):
                                attachment_paths.append(path)

                    # Cargar replies asociados a esta nota.
                    replies_rows = []
                    if self._has_version_note_replies_table:
                        cur.execute(
                            "SELECT content, created_by, created_on "
                            "FROM version_note_replies "
                            "WHERE version_note_id = ? "
                            "ORDER BY created_on ASC",
                            (n["id"],),
                        )
                        replies_rows = cur.fetchall()
                    replies = [
                        {
                            "user": reply_row["created_by"] or "",
                            "text": reply_row["content"] or "",
                            "date": reply_row["created_on"],
                        }
                        for reply_row in replies_rows
                    ]

                    comments.append(
                        {
                            "user": n["created_by"] or "",
                            "text": n["content"] or "",
                            "date": n["created_on"],
                            "attachments": attachment_paths,
                            "attachment_info": n["attachment_info"] or "",
                            "from_playlist": bool(n["from_playlist"] or 0),
                            "playlist_name": n["playlist_name"] or "",
                            "replies": replies,
                        }
                    )
                version_dict = {
                    "version_number": f"v{v['version_number']:03d}",
                    "version_number_int": int(v["version_number"]),
                    "version_description": v["description"] or "",
                    "version_date": v["created_on"] or "",
                    "created_by": v["created_by"] or "Unknown",
                    "logged_minutes": float(
                        timelog_minutes_by_version.get(int(v["version_number"]), 0.0)
                    ),
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
        # Sincronizar debug con el módulo utilitario
        if HAS_CLIP_UTILS:
            clip_utils.DEBUG = DEBUG

    def parse_exr_name(self, file_name):
        """Extrae el nombre base del archivo EXR y el numero de version."""
        # Usar función compartida para limpiar el nombre base
        base_name = clean_base_name(file_name)
        # Buscar versión en el nombre original (antes de limpiar)
        version_match = re.search(r"_v(\d+)", file_name)
        version_number = version_match.group(1) if version_match else "Unknown"
        return base_name, version_number

    def process_selected_clips(self):
        """Procesa el clip del playhead resolviendo la task entre las disponibles.

        Si en el playhead hay clips de varias tasks (`_comp_`, `_roto_`, `_cleanup_`),
        muestra un popover para elegir cuál mostrar. Si hay una sola, la usa
        automáticamente. Si no hay clip en ninguna, cae al método actual con
        TRACK_comp_EXR y selección como fallback.
        """
        debug_print("Processing selected clips...")

        if not HAS_CLIP_UTILS:
            debug_print("ERROR: Módulo LGA_NKS_GetClip no disponible. No se pueden procesar clips.")
            return []

        seq = hiero.ui.activeSequence()
        resolved_task = resolve_task_at_playhead(seq, title="Select task") if seq else None
        debug_print(f"Task resuelta para Shot_info: {resolved_task}")

        if resolved_task:
            target_track = track_for_task(resolved_task)
            playhead_clip = get_clip_to_process(track_name=target_track)
        else:
            playhead_clip = get_clip_to_process(track_name=None)

        if playhead_clip:
            clips_to_process = [playhead_clip]
            debug_print(
                f">>> Usando clip del playhead. resolved_task='{resolved_task}'"
            )
        else:
            clips_to_process = get_selected_clips()
            debug_print(
                ">>> No hay clip en playhead; usando clips seleccionados como fallback"
            )

        # Task name a usar en find_task: la resuelta del playhead, o 'comp' por compatibilidad
        active_task_name = resolved_task or "comp"

        results = []
        if not clips_to_process:
            debug_print("No se encontraron clips para procesar.")
            return results

        for clip in clips_to_process:
            if isinstance(clip, hiero.core.EffectTrackItem):
                continue  # Pasar de largo los clips que sean efectos

            file_path = clip.source().mediaSource().fileinfos()[0].filename()
            exr_name = os.path.basename(file_path)
            base_name, version_number = self.parse_exr_name(exr_name)
            clip_name = ""
            try:
                clip_name = clip.name()
            except Exception:
                clip_name = exr_name

            # Usar funciones compartidas para extraer información
            project_name = extract_project_name_from_path(file_path)
            if project_name:
                debug_print(f"Project name (from path): {project_name}")
            else:
                project_name = extract_project_name(base_name)
                debug_print(f"Project name (from filename fallback): {project_name}")
            shot_code = extract_shot_code(base_name)
            debug_print(
                "Clip context:",
                f"clip_name='{clip_name}'",
                f"file_path='{file_path}'",
                f"exr_name='{exr_name}'",
                f"base_name='{base_name}'",
                f"project_name='{project_name}'",
                f"shot_code='{shot_code}'",
            )

            # Operaciones intensivas: ceder tiempo de UI
            QCoreApplication.processEvents()
            shot = self.sg_manager.find_shot(project_name, shot_code)
            debug_print(f"Shot found: {shot}")
            if not shot:
                debug_print(
                    "No se encontro shot en pipesync.db para la combinacion parseada.",
                    f"project_name='{project_name}'",
                    f"shot_code='{shot_code}'",
                    level="warning",
                )

            QCoreApplication.processEvents()
            if shot:
                task = self.sg_manager.find_task(shot, active_task_name)
                debug_print(f"Task found ({active_task_name}): {task}")
                task_description = (
                    task["task_description"] if task else "No info available"
                )
                assignee = task["task_assigned_to"] if task else "No assignee"
                versions = task["versions"] if task else []

                last_versions = sorted(
                    versions, key=lambda v: v["version_date"], reverse=True
                )
                version_info = []
                for v in last_versions:
                    match = re.search(r"v(\d+)", v["version_number"])
                    version_number = match.group() if match else v["version_number"]
                    version_info.append(
                        {
                            "version_number": version_number,
                            "version_description": v["version_description"]
                            or "",
                            "version_date": v.get("version_date", ""),
                            "comments": v.get("comments", []),
                            "created_by": v.get("created_by", "Unknown"),
                            "logged_minutes": v.get("logged_minutes", 0.0),
                        }
                    )

                # Display name de la task (capitalizado: "comp" -> "Comp")
                task_type_display = (task["task_type"] if task else active_task_name) or active_task_name
                if task_type_display:
                    task_type_display = task_type_display[:1].upper() + task_type_display[1:]

                shot_info = {
                    "shot_code": shot["shot_name"],
                    "task_type": task_type_display,
                    "description": task_description,
                    "assignee": assignee,
                    "versions": version_info,
                }
                results.append(shot_info)
            QCoreApplication.processEvents()

        debug_print("Processing completed.")
        return results


class GUIWindow(QWidget):
    def __init__(self, hiero_ops, parent=None):
        super(GUIWindow, self).__init__(parent)
        self.hiero_ops = hiero_ops
        self._wrapping_labels = []
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Info")
        self.setObjectName("flowNotesContentWidget")
        self.setStyleSheet(SHOT_INFO_QSS)
        self.setMinimumSize(900, 700)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Header (titulo del shot/task/assignee)
        self.header_widget = QWidget()
        self.header_widget.setObjectName("flowNotesHeaderWidget")
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(16, 12, 12, 12)
        self.title_label = QLabel("")
        self.title_label.setObjectName("flowNotesTitle")
        self._configure_wrapping_label(self.title_label)
        header_layout.addWidget(self.title_label, 1)
        main_layout.addWidget(self.header_widget)

        # Scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("flowNotesScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.scroll_content = QWidget()
        self.scroll_content.setObjectName("flowNotesScrollContent")
        self.scroll_content.setMinimumWidth(0)
        self.scroll_content.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setContentsMargins(12, 12, 12, 12)
        self.scroll_layout.setSpacing(16)
        self.scroll_layout.setAlignment(Qt.AlignTop)

        self.scroll_area.setWidget(self.scroll_content)
        main_layout.addWidget(self.scroll_area, 1)

        # Cerrar con ESC
        shortcut = QShortcut(QKeySequence(Qt.Key_Escape), self)
        shortcut.activated.connect(self.close)

    def resizeEvent(self, event):
        super(GUIWindow, self).resizeEvent(event)
        self._update_wrapping_widths()

    def closeEvent(self, event):
        # Cerrar la conexión de sg_manager si existe
        if hasattr(self.hiero_ops, "sg_manager") and self.hiero_ops.sg_manager:
            self.hiero_ops.sg_manager.close()
            self.hiero_ops.sg_manager = None
        super(GUIWindow, self).closeEvent(event)

    def _set_title(self, shot_code, task_type, assignee):
        parts = [p for p in (shot_code, task_type, assignee) if p]
        self.title_label.setText("  |  ".join(parts))

    def _configure_wrapping_label(self, label, extra_width=0):
        label.setWordWrap(True)
        label.setMinimumWidth(0)
        label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._wrapping_labels.append((label, extra_width))

    def _update_wrapping_widths(self):
        if not hasattr(self, "scroll_area") or not hasattr(self, "scroll_layout"):
            return
        viewport_width = self.scroll_area.viewport().width()
        if viewport_width <= 0:
            return

        # QScrollArea::viewport() ya descuenta el scrollbar vertical, pero no los
        # margenes de los layouts internos ni los indentados de cada label.
        scroll_margins = self.scroll_layout.contentsMargins()
        base_width = (
            viewport_width
            - scroll_margins.left()
            - scroll_margins.right()
            - 4
        )
        self.scroll_content.setFixedWidth(max(0, viewport_width - 1))

        for label, extra_width in list(self._wrapping_labels):
            if label is None:
                continue
            try:
                if label.parent() is None:
                    continue
                label.setMaximumWidth(max(80, base_width - extra_width))
            except RuntimeError:
                continue

    def create_task_description_widget(self, description):
        """Crea el bloque inicial de descripcion general de la task."""
        section = QWidget()
        section.setMinimumWidth(0)
        section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout = QVBoxLayout(section)
        layout.setContentsMargins(12, 0, 8, 0)
        layout.setSpacing(0)

        raw_description = (description or "").strip()
        if not raw_description or raw_description == "No info available":
            raw_description = "Sin descripcion"

        esc_description = _html_escape(raw_description).replace("\n", "<br/>")
        html = (
            f"<span style='color: {COLORS['txt_desc_title']}; font-weight: 700; font-size: 15px;'>"
            f"Descripción de task:</span> "
            f"<span style='color: {COLORS['txt_body']};'>{esc_description}</span>"
        )

        label = QLabel(html)
        label.setObjectName("flowTaskDescription")
        label.setTextFormat(Qt.RichText)
        self._configure_wrapping_label(label, extra_width=20)
        layout.addWidget(label)
        return section

    def create_version_widget(self, version):
        """Crea el widget contenedor para una version (header morado + descripcion + comentarios)."""
        container = QWidget()
        container.setObjectName("flowVersionContainer")
        container.setMinimumWidth(0)
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 12)
        c_layout.setSpacing(0)

        c_layout.addWidget(self._build_version_header(version))
        c_layout.addWidget(self._build_description_section(version))

        comments = version.get("comments", [])
        if comments:
            c_layout.addWidget(self._build_comments_section(comments))

        return container

    def _build_version_header(self, version):
        header = QWidget()
        header.setObjectName("flowVersionHeader")
        header.setFixedHeight(40)

        hl = QHBoxLayout(header)
        hl.setContentsMargins(16, 8, 16, 8)

        # version_number puede venir como "v007" o "v7"; normalizar a 3 digitos
        raw_vn = version.get("version_number", "")
        m = re.search(r"\d+", raw_vn or "")
        vn_text = f"v{int(m.group()):03d}" if m else (raw_vn or "v???")

        version_dt = _parse_pipesync_datetime(version.get("version_date"))
        date_text = _html_escape(_format_friendly_date(version_dt, include_time=False))
        author_text = _html_escape(version.get("created_by") or "Unknown")

        info_html = (
            f"<span style='color: {COLORS['txt_principal_strong']}; font-weight: 800;'>{vn_text}</span>"
            f"<span style='color: {COLORS['txt_secundario']};'> &nbsp;&nbsp; | &nbsp;&nbsp; subida </span>"
            f"<span style='color: {COLORS['txt_subtle']};'>{date_text}</span>"
            f"<span style='color: {COLORS['txt_secundario']};'> &nbsp;&nbsp; por </span>"
            f"<span style='color: {COLORS['txt_subtle']};'>{author_text}</span>"
        )
        info_label = QLabel(info_html)
        info_label.setObjectName("flowVersionInfo")
        info_label.setTextFormat(Qt.RichText)
        info_label.setMinimumWidth(0)
        info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        info_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        hl.addWidget(info_label, 1)

        time_text = _format_logged_time(version.get("logged_minutes", 0.0))
        if time_text:
            time_html = (
                f"<span style='color: {COLORS['txt_secundario']};'>Time logged: </span>"
                f"<span style='color: {COLORS['txt_subtle']};'>{time_text}</span>"
            )
            time_label = QLabel(time_html)
            time_label.setObjectName("flowVersionTimeLogged")
            time_label.setTextFormat(Qt.RichText)
            time_label.setMinimumWidth(0)
            time_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
            time_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            hl.addWidget(time_label)

        return header

    def _build_description_section(self, version):
        section = QWidget()
        section.setMinimumWidth(0)
        section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sl = QVBoxLayout(section)
        sl.setContentsMargins(12, 8, 8, 8)
        sl.setSpacing(0)

        author = (version.get("created_by") or "").strip()
        title_html = (
            f"<span style='color: {COLORS['txt_desc_title']}; font-weight: 700; font-size: 15px;'>Descripción:</span>"
        )
        if author:
            title_html += (
                f"<span style='color: {COLORS['txt_desc_meta']}; font-size: 14px;'>"
                f"&nbsp;(por {_user_name_span(author)})</span>"
            )
        title_label = QLabel(title_html)
        title_label.setObjectName("flowVersionDescriptionTitle")
        title_label.setTextFormat(Qt.RichText)
        self._configure_wrapping_label(title_label, extra_width=20)
        sl.addWidget(title_label)
        sl.addSpacing(2)

        desc = (version.get("version_description") or "").strip()
        if desc:
            esc = _html_escape(desc).replace("\n", "<br/>")
            content_html = f"<span style='color: {COLORS['txt_body']};'>{esc}</span>"
        else:
            content_html = f"<span style='color: {COLORS['txt_body']};'>Sin descripción</span>"

        content_label = QLabel(content_html)
        content_label.setObjectName("flowVersionDescriptionContent")
        content_label.setTextFormat(Qt.RichText)
        self._configure_wrapping_label(content_label, extra_width=20)
        content_label.setContentsMargins(12, 0, 0, 0)
        sl.addWidget(content_label)

        return section

    def _build_comments_section(self, comments):
        section = QWidget()
        section.setObjectName("flowVersionCommentsContainer")
        section.setMinimumWidth(0)
        section.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        sl = QVBoxLayout(section)
        sl.setContentsMargins(6, 0, 6, 0)
        sl.setSpacing(4)

        for comment in comments:
            sep = QFrame()
            sep.setObjectName("flowCommentSeparator")
            sep.setFrameShape(QFrame.HLine)
            sep.setFixedHeight(1)
            sl.addWidget(sep)
            sl.addWidget(self.create_comment_widget(comment))

        return section

    def create_comment_widget(self, comment):
        """Crea el widget para un comentario con header, contenido y thumbnails."""
        w = QWidget()
        w.setObjectName("flowVersionComment")
        w.setMinimumWidth(0)
        w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        wl = QVBoxLayout(w)
        wl.setContentsMargins(18, 0, 0, 8)
        wl.setSpacing(0)

        author = (comment.get("user") or "").strip()
        n_dt = _parse_pipesync_datetime(comment.get("date"))
        date_str = _format_friendly_date(n_dt, include_time=True)

        from_playlist = comment.get("from_playlist", False)
        playlist_name = (comment.get("playlist_name") or "").strip()

        meta_parts = _user_name_span(author) + f", {_html_escape(date_str)}"
        if from_playlist:
            meta_parts += f", {_playlist_meta_span(playlist_name)}"

        header_html = (
            f"<span style='color: {COLORS['txt_desc_title']}; font-size: 15px; font-weight: 700;'>Comentario:</span>"
            f"<span style='color: {COLORS['txt_desc_meta']}; font-size: 14px;'>"
            f"&nbsp;(por {meta_parts})</span>"
        )
        header_label = QLabel(header_html)
        header_label.setObjectName("flowVersionCommentHeader")
        header_label.setTextFormat(Qt.RichText)
        self._configure_wrapping_label(header_label, extra_width=30)
        header_label.setContentsMargins(0, 8, 0, 0)
        wl.addWidget(header_label)
        wl.addSpacing(6)

        text = (comment.get("text") or "").strip()
        if text:
            esc = _html_escape(text).replace("\n", "<br/>")
            content_html = f"<span style='color: {COLORS['txt_body']};'>{esc}</span>"
            content_label = QLabel(content_html)
            content_label.setObjectName("flowVersionCommentContent")
            content_label.setTextFormat(Qt.RichText)
            self._configure_wrapping_label(content_label, extra_width=30)
            content_label.setContentsMargins(12, 0, 0, 0)
            wl.addWidget(content_label)

        # Attachments con frame info
        attachments = comment.get("attachments", []) or []
        frame_texts = self._frame_texts_from_attachment_info(comment.get("attachment_info"))
        if attachments:
            wl.addWidget(self.create_thumbnails_widget(attachments, frame_texts))

        for reply in comment.get("replies", []) or []:
            wl.addWidget(self.create_reply_widget(reply))

        return w

    def create_reply_widget(self, reply):
        reply_widget = QWidget()
        reply_widget.setObjectName("flowVersionCommentReply")
        reply_layout = QVBoxLayout(reply_widget)
        reply_layout.setSpacing(4)
        reply_layout.setContentsMargins(30, 4, 0, 4)

        author = (reply.get("user") or "").strip()
        r_dt = _parse_pipesync_datetime(reply.get("date"))
        date_str = _format_friendly_date(r_dt, include_time=True)

        header_html = (
            f"<span style='color: {COLORS['txt_desc_meta']}; font-size: 14px; font-weight: 700;'>"
            f"{_user_name_span(author)}</span>"
            f"<span style='color: {COLORS['txt_desc_meta']}; font-size: 13px;'>&nbsp;{_html_escape(date_str)}</span>"
        )
        header_label = QLabel(header_html)
        header_label.setTextFormat(Qt.RichText)
        header_label.setWordWrap(True)
        reply_layout.addWidget(header_label)

        text = (reply.get("text") or "").strip()
        if text:
            esc = _html_escape(text).replace("\n", "<br/>")
            content_label = QLabel(f"<span style='color: {COLORS['txt_body']};'>{esc}</span>")
            content_label.setTextFormat(Qt.RichText)
            content_label.setWordWrap(True)
            content_label.setContentsMargins(12, 0, 0, 0)
            reply_layout.addWidget(content_label)

        return reply_widget

    @staticmethod
    def _frame_texts_from_attachment_info(attachment_info):
        out = []
        if not attachment_info:
            return out
        try:
            data = json.loads(attachment_info)
        except (TypeError, ValueError):
            return out
        if not isinstance(data, list):
            return out
        for entry in data:
            if isinstance(entry, dict) and entry.get("frame") is not None:
                out.append(f"Frame {entry['frame']}")
            else:
                out.append("Sin Frame Number")
        return out

    def create_thumbnails_widget(self, attachment_paths, frame_texts=None):
        """Layout horizontal de thumbnails con label "Frame N" debajo de cada uno."""
        if frame_texts is None:
            frame_texts = []

        thumbs_w = QWidget()
        thumbs_w.setObjectName("flowVersionCommentThumbnails")
        tl = QHBoxLayout(thumbs_w)
        tl.setContentsMargins(12, 8, 0, 8)
        tl.setSpacing(8)

        valid_idx = 0
        for path in attachment_paths:
            if not path.lower().endswith((".jpg", ".jpeg", ".png", ".tiff", ".tif")):
                continue
            col = QWidget()
            cl = QVBoxLayout(col)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(4)

            btn = ThumbnailButton(path)
            cl.addWidget(btn)

            frame_text = (
                frame_texts[valid_idx] if valid_idx < len(frame_texts) else "Sin Frame Number"
            )
            lab = QLabel(frame_text)
            lab.setObjectName("flowVersionCommentAttachment")
            lab.setFixedWidth(150)
            lab.setAlignment(Qt.AlignCenter)
            cl.addWidget(lab)

            tl.addWidget(col)
            valid_idx += 1

        tl.addStretch(1)
        return thumbs_w

    def display_results(self, results):
        """Muestra los resultados recopilados en el scroll area."""
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

        # Titulo: datos del primer resultado
        first = results[0]
        self._set_title(
            first.get("shot_code", ""),
            first.get("task_type", ""),
            first.get("assignee", ""),
        )

        for result in results:
            debug_print(f"Processing result: {result}")
            self.scroll_layout.addWidget(
                self.create_task_description_widget(result.get("description", ""))
            )
            for version in result.get("versions", []):
                self.scroll_layout.addWidget(self.create_version_widget(version))

        self.setWindowFlags(self.windowFlags() | Qt.Window)
        self.show()
        self._update_wrapping_widths()
        QtCore.QTimer.singleShot(0, self._update_wrapping_widths)
        debug_print("Results displayed successfully.")


def main():
    global app, window
    if should_redirect_to_playlist_shot_info():
        debug_print(
            "Vendor timeline detectado desde Flow Shot Info. Redirigiendo a Playlist Shot Info."
        )
        run_playlist_shot_info()
        return

    db_path = get_pipesync_db_path("pipesync.db")

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
