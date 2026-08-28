"""
____________________________________________________________________

  LGA_NKS_Flow_CreateShot v1.47 | Lega

  Script para crear shots en ShotGrid basado en el nombre del clip seleccionado en Hiero.
  SIN usar templates predefinidos - crea tasks manualmente para mayor control.

  v1.47: Los carteles de aviso pasan al helper LGA_NKS_MessageBox con el
         estilo del pack.

  v1.46: `apr` pasa a "Delivery Apr" y la cola queda pubsh -> check -> apr. En
         el dropdown de shot sale `pbshed` y entra `check`, que es el que usa
         PipeSync y el que ahora acepta projb.

  v1.45: Los dropdowns toman el ORDEN del sg_status_list de Flow (Review Javi
         antes que Review Juano) y check pasa a "Delivery Checked".

  v1.44: Los dropdowns de estado se filtran por contexto contra los codigos reales
         de cada sitio de Flow. Suma OK for Delivery, Review Prod y Delivered
         (pbshed, el "entregado" de projb) y alinea los colores de la cola verde.

  v1.43: Popup de los dropdowns: fondo uniforme #272727 con una bolita del color
         del estado a la izquierda de cada nombre (en vez de cada fila coloreada),
         texto #cccccc y hover (#3a3a3a). El blanco de contraste pasa de #ffffff a
         #cccccc (combo cerrado y popup).
  v1.42: Dropdowns de estado con ancho fijo 140px. Nuevo reviewer "Charly"
         (Charly Villafañe, id 2002) entre Juano y Javi, en create y modify.
  v1.41: ColoredStatusComboBox pinta el combo cerrado a mano (paintEvent): fondo del
         color del estado, texto contrastado dibujado UNA sola vez (fix del
         doble-texto en negro), linea vertical separadora y flecha SVG
         (dropdown_arrow[_white].svg desde LGA_NKS_Shared/icons via ICONS_DIR,
         ruta derivada de __file__). El popup usa el delegate sobre la view.
  v1.40: Estado de shot y de task pasan de checkbox a dropdowns coloreados
         (ColoredStatusComboBox; SHOT_STATES/TASK_STATES). Create Shot escribe el
         sg_status_list elegido (default ready). Modify prefilea el estado real.
         Reviewers: helpers resolve_reviewer_ids() y reviewers_config_from_task()
         (ida/vuelta UI <-> Flow). Nuevos update_shot_status/priority/task_reviewers.
         Ver docs/Docu_Flow_Estados_Colores.md.
  v1.39: Cuando el shot no tiene thumbnail en Flow (Modify Shot), el placeholder
         muestra un boton "Take Snapshot" que captura el viewer y lo deja listo en
         self.thumbnail_path (no se sube hasta confirmar). Nuevos metodos:
         _show_take_snapshot_button(), _on_take_snapshot_clicked(),
         _show_captured_thumbnail_pixmap().
  v1.38: ShotConfigDialog acepta existing_thumb_path para mostrar el thumbnail
         actual del shot (usado por Modify Shot). find_shot_and_tasks() ahora
         tambien devuelve el campo "image". Nuevo metodo show_existing_thumbnail().
  v1.37: Sequence (sg_sequence) extraída desde el segmento de carpeta que sigue a
         VFX-NOMBRE en el path (estructura VFX-PROYECTO/SECUENCIA/SHOT), por clip,
         en lugar del nombre del timeline de Hiero. Fallback: valor del diálogo /
         nombre del timeline. get_active_sequence_name() acepta file_path.
         Ver docs/Docu_ProjectName_Extraction.md.
  v1.36: Project name extraído desde el segmento VFX-NOMBRE del path del archivo
         (con fallback al primer bloque del filename si el path no contiene VFX-).
         Corrige proyectos como PROJALT cuyos shots tienen prefijo PROJA en el filename.
  v1.35: El diálogo de configuración ahora se muestra no modal con show()
         y continúa el flujo por callback al cerrar/aceptar.
         Evita que la ventana tome el foco bloqueando Hiero/Nuke Studio.
  v1.34: Creación automática de estructura de carpetas por task
         Integración con módulo LGA_NKS_Flow_CreateShot_Folders
         Crea carpetas automáticamente después de crear shot y tasks en Flow
  v1.33: Pre-chequeo inteligente de existencia antes de mostrar la UI
         Muestra ventana "Comprobando existencia de los shots en Flow"
         Bloquea la creación si alguno ya existe (multi selección)
         Lanza automáticamente Modify Shot cuando el shot único ya existe
  v1.32: Agregado modo de modificación de shots existentes
         Reutiliza la misma UI compacta de creación
         Permite agregar/eliminar tasks y actualizar la descripción
         No afecta estados ni tiempos de las tasks existentes
  v1.31: Migración al método híbrido centralizado de selección de clips
         Soporte para selección múltiple usando módulo LGA_NKS_GetClip
         Respeta TRACK_comp_EXR del módulo (actualmente "_comp_")
  v1.30: Reducción automática del 30% en tiempo estimado antes de subir a Flow
         (ej: 1 día ingresado → 0.7 días en Flow)
  v1.29: UI compacta - Tasks deshabilitadas ocupan 1 línea sin campos ni divisores
         Checkbox a la izquierda del nombre, columnas aparecen solo cuando se habilita
  v1.28: Todas las tasks del pipeline agregadas con colores específicos
         Comp, Roto, Cleanup, DMP, Model, Retopo, Rigging, Shaders,
         Match Move, Animation, FX, Lighting
  v1.27: Sistema modular de tasks - Fácil agregar nuevas tasks (DRY)
         Agregada task Roto + enable/disable dinámico de campos
  v1.26: UI reorganizada en columnas
  v1.25: Agregado checkbox "High Priority" para asignar sg_prioridad="high"
  v1.24: Mensajes diferenciados para shots existentes vs creados + pipeline step Comp
  v1.23: Sistema de Logging Seguro para Hilos
  v1.22: Agregado campo para tiempo estimado en días (sg_estdias)
  v1.21: Asigna reviewers a la task usando el campo task_reviewers
  v1.20: Creación sin Templates
  v1.10: Sistema Dual de Nomenclatura:
         - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
         - PROYECTO_SEQ_SHOT (3 bloques simplificado)
____________________________________________________________________
"""

import hiero.core
import logging
import os
import queue
import re
import sys
import time
from logging.handlers import QueueHandler, QueueListener
from pathlib import Path
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt
from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning
QApplication = QtWidgets.QApplication
QMessageBox = QtWidgets.QMessageBox
QDialog = QtWidgets.QDialog
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton
QSizePolicy = QtWidgets.QSizePolicy
QTextEdit = QtWidgets.QTextEdit
QCheckBox = QtWidgets.QCheckBox
QFrame = QtWidgets.QFrame
QLineEdit = QtWidgets.QLineEdit
QComboBox = QtWidgets.QComboBox
QStyledItemDelegate = QtWidgets.QStyledItemDelegate
QFont = QtGui.QFont
QPixmap = QtGui.QPixmap
QColor = QtGui.QColor
QBrush = QtGui.QBrush
QRect = QtCore.QRect
QRunnable = QtCore.QRunnable
Slot = QtCore.Slot
QThreadPool = QtCore.QThreadPool
Signal = QtCore.Signal
QObject = QtCore.QObject
QDoubleValidator = QtGui.QDoubleValidator
QTimer = QtCore.QTimer

# Agregar la ruta de shotgun_api3 al sys.path
shared_dir = Path(__file__).parent.parent / "LGA_NKS_Shared"
sys.path.insert(0, str(shared_dir))
import shotgun_api3

# Importar el modulo de configuracion segura
sys.path.append(str(shared_dir))
from SecureConfig_Reader import get_flow_credentials

# Importar utilidades de naming
from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    extract_project_name_from_path,
    extract_sequence_name_from_path,
    clean_base_name,
)

# Importar módulo centralizado para obtener clips
from pathlib import Path
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    from LGA_NKS_Shared.LGA_NKS_GetClip import get_clips_to_process, get_clip_to_process
    from LGA_NKS_Shared import LGA_NKS_GetClip as clip_utils
    # La sincronización de DEBUG se hace después de su definición (ver más abajo)

from LGA_NKS_Shared.LGA_NKS_Flow_Task_Config import AVAILABLE_TASKS
from LGA_NKS_Shared.LGA_NKS_ContextProfile import get_context_mode
from LGA_NKS_Shared.LGA_NKS_Flow_Status_Config import filter_states_for_mode

# Importar módulo de creación de carpetas
folders_path = Path(__file__).parent
sys.path.insert(0, str(folders_path))
from LGA_NKS_Flow_CreateShot_Folders import create_folders_for_shot_tasks


DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True
script_start_time = None
debug_log_listener = None
debug_logger = None

# Sincronizar debug con el módulo centralizado de clips (después de definir DEBUG)
if 'clip_utils' in globals():
    clip_utils.DEBUG = DEBUG


class RelativeTimeFormatter(logging.Formatter):
    """Formatter que incluye tiempo relativo desde el inicio del script."""
    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created

        relative_time = record.created - script_start_time
        record.relative_time = f"{relative_time:.3f}s"
        return super().format(record)


def setup_debug_logging(script_name="FlowCreateShot"):
    """Configura el logging para escribir SOLO en archivo."""
    global debug_log_listener

    log_filename = f"debugPy_{script_name}.log"
    log_file_path = os.path.join(
        os.path.dirname(__file__), "..", "logs", log_filename
    )
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    try:
        with open(log_file_path, "w", encoding="utf-8") as f:
            f.write(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
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


debug_logger = setup_debug_logging(script_name="FlowCreateShot")


def debug_print(*message, level="info"):
    """Función de logging con switches por consola/archivo."""
    global script_start_time

    msg = " ".join(str(arg) for arg in message)

    if DEBUG and DEBUG_LOG and debug_logger:
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
        timestamped_msg = f"[{relative_time:.3f}s] {msg}"
        print(timestamped_msg)


def print_debug_messages():
    """Compatibilidad con señales de workers (sin imprimir en consola)."""
    debug_print("=== Fin de logs del worker ===", level="debug")


def cleanup_logging():
    """Limpia el listener al terminar."""
    global debug_log_listener
    if debug_log_listener:
        try:
            debug_print("Deteniendo listener de logging...")
            debug_log_listener.stop()
            debug_print("Listener detenido")
        except Exception as e:
            debug_print(f"Error en cleanup: {e}", level="error")


try:
    import atexit
    atexit.register(cleanup_logging)
except Exception:
    pass


def get_active_sequence_name(file_path=None):
    """Obtiene el nombre de la secuencia para Flow.

    Primario: segmento de carpeta que sigue a "VFX-NOMBRE" en la ruta del clip
    (estructura VFX-PROYECTO/SECUENCIA/SHOT). Fallback: nombre de la secuencia
    activa en Hiero (comportamiento anterior).
    Ver docs/Docu_ProjectName_Extraction.md.
    """
    # Primario: desde la ruta del archivo
    seq_from_path = extract_sequence_name_from_path(file_path) if file_path else None
    if seq_from_path:
        debug_print(f"Secuencia (from path): {seq_from_path}")
        return seq_from_path

    # Fallback: nombre del timeline de Hiero
    try:
        seq = hiero.ui.activeSequence()
        if seq:
            sequence_name = seq.name()
            debug_print(f"Secuencia (from timeline fallback): {sequence_name}")
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
    """Obtiene el nombre del shot desde el clip seleccionado o desde el path del archivo.
    Usa el método híbrido centralizado (playhead primero, luego selección como fallback)."""
    sequence = hiero.ui.activeSequence()
    if not sequence:
        debug_print("No se encontró una secuencia activa.")
        return None

    # Usar módulo centralizado para obtener clip (método híbrido)
    # track_name=None para respetar TRACK_comp_EXR del módulo
    clip = get_clip_to_process(track_name=None, prioritize_multiple_selection=False)

    if not clip:
        debug_print("No se encontró clip en playhead ni clips seleccionados.")
        sequence_name = sequence.name()
        debug_print(f"Usando nombre de secuencia: {sequence_name}")
        return sequence_name

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

        # Extraer nombre base del archivo usando utilidades de naming
        exr_name = os.path.basename(file_path)
        base_name = clean_base_name(exr_name)

        # Extraer shot_code usando detección automática de formato
        shot_code = extract_shot_code(base_name)
        if shot_code:
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
# ============================================================================
# Estados de Flow para los dropdowns (nombre visible, codigo SG, color UI).
#
# Los colores son los del dropdown y NO los del clip del timeline: son dos
# paletas distintas a proposito (ver docs/Docu_Flow_Estados_Colores.md). Lo que
# si sale de la fuente compartida es QUE codigos existen en cada contexto:
# los dos sitios de Flow no tienen la misma lista y escribir uno que el sitio no
# tiene falla con "'xxx' is not a valid status".
#
# Las listas de abajo son el superset de los dos sitios; `filter_states_for_mode`
# deja los del contexto activo.
# ============================================================================
ALL_SHOT_STATES = [
    ("Not ready", "noread", "#d3d3d3"),
    ("Omited", "omit", "#78b487"),
    ("Ready to start", "ready", "#c2b234"),
    ("In progress", "progre", "#6443bf"),
    ("In playlist", "plylst", "#99c153"),
    ("OK for Delivery", "pubsh", "#50bfc7"),
    ("Delivered", "check", "#38a138"),
    ("Delivery Apr", "apr", "#266612"),
]

ALL_TASK_STATES = [
    ("Not ready", "noread", "#d3d3d3"),
    ("Omited", "omit", "#78b487"),
    ("Ready to start", "ready", "#c2b234"),
    ("In progress", "progre", "#6443bf"),
    ("Corrections", "corr", "#2e77d4"),
    ("Review Sebas", "rev_su", "#a65680"),
    ("Review Charly", "revcha", "#a9909d"),
    ("Review Juano", "revjua", "#7f4b69"),
    ("Review Javi", "revjav", "#8f3f72"),
    ("Review Lega", "revleg", "#68135d"),
    ("Review Hold", "revhld", "#9e6a15"),
    ("Review Prod", "revprd", "#8cbf3f"),
    ("Review Dir", "rev_di", "#b5db4b"),
    ("OK for Delivery", "pubsh", "#50bfc7"),
    ("Delivered", "check", "#38a138"),
    ("Delivery Apr", "apr", "#266612"),
]


def get_shot_states():
    return filter_states_for_mode(ALL_SHOT_STATES, get_context_mode(), entity="shot")


def get_task_states():
    return filter_states_for_mode(ALL_TASK_STATES, get_context_mode(), entity="task")

# Estado por defecto en Create Shot (shot y task)
DEFAULT_STATE_CODE = "ready"

# Carpeta de iconos (ruta derivada del __file__ del script, nunca absoluta hardcodeada)
ICONS_DIR = Path(__file__).parent.parent / "LGA_NKS_Shared" / "icons"

# Mapeo de los reviewers de la UI (clave interna) al nombre real en Flow.
REVIEWER_KEY_TO_NAME = {
    "lega_pugliese": "Lega Pugliese",
    "sebas_romano": "Sebas Romano",
    "juano": "Juan Olivares",
    "charly_villafane": "Charly Villafañe",
    "javi_bravo": "Javi Bravo",
}


def resolve_reviewer_ids(sg, reviewers_config):
    """Convierte el dict de reviewers de la UI en lista de {type, id} de HumanUser."""
    ids = []
    for key, selected in (reviewers_config or {}).items():
        if not selected:
            continue
        name = REVIEWER_KEY_TO_NAME.get(key)
        if not name:
            continue
        try:
            users = sg.find("HumanUser", [["name", "is", name]], ["id"])
            if users:
                ids.append({"type": "HumanUser", "id": users[0]["id"]})
            else:
                debug_print(f"Reviewer '{name}' no encontrado en Flow")
        except Exception as e:
            debug_print(f"Error buscando reviewer '{name}': {e}")
    return ids


def reviewers_config_from_task(task_data):
    """Construye el dict de reviewers de la UI desde el campo task_reviewers de Flow."""
    names = set()
    for user in (task_data or {}).get("task_reviewers") or []:
        n = user.get("name") if isinstance(user, dict) else None
        if n:
            names.add(n)
    return {key: (name in names) for key, name in REVIEWER_KEY_TO_NAME.items()}


def _contrast_text_color(hex_color):
    """Devuelve '#000000' (fondos claros) o '#cccccc' (fondos oscuros) segun la
    luminancia del color de fondo, para que el texto sea legible."""
    h = (hex_color or "").lstrip("#")
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except Exception:
        return "#cccccc"
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    return "#000000" if luminance > 0.55 else "#cccccc"


class _StatusItemDelegate(QStyledItemDelegate):
    """Pinta cada item del popup con fondo oscuro uniforme (#272727), una bolita
    del color del estado a la izquierda y el nombre en #cccccc. Hover/seleccion
    aclara la fila."""

    _BG = "#272727"
    _BG_HOVER = "#3a3a3a"
    _TEXT = "#cccccc"
    _DOT = 10  # diametro de la bolita

    def paint(self, painter, option, index):
        state_brush = index.data(Qt.BackgroundRole)
        dot_color = (
            state_brush.color()
            if (state_brush is not None and hasattr(state_brush, "color"))
            else QColor("#888888")
        )
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        # Fondo del item (uniforme), mas claro en hover/seleccion
        hovered = option.state & (
            QtWidgets.QStyle.State_Selected | QtWidgets.QStyle.State_MouseOver
        )
        painter.fillRect(option.rect, QColor(self._BG_HOVER if hovered else self._BG))

        # Bolita con el color del estado
        r = option.rect
        d = self._DOT
        dot_x = r.left() + 8
        dot_y = r.center().y() - d // 2
        painter.setPen(Qt.NoPen)
        painter.setBrush(dot_color)
        painter.drawEllipse(dot_x, dot_y, d, d)

        # Nombre del estado
        painter.setPen(QColor(self._TEXT))
        text = index.data(Qt.DisplayRole) or ""
        text_rect = r.adjusted(8 + d + 8, 0, -8, 0)
        painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, text)
        painter.restore()

    def sizeHint(self, option, index):
        size = super(_StatusItemDelegate, self).sizeHint(option, index)
        size.setHeight(max(size.height(), 24))
        return size


class ColoredStatusComboBox(QComboBox):
    """ComboBox de estados. El combo CERRADO se pinta entero a mano (fondo del color
    del estado, texto contrastado dibujado UNA sola vez, linea vertical y flecha SVG),
    evitando el doble-texto que produce el estilo nativo. El POPUP usa
    _StatusItemDelegate para colorear cada item."""

    _ARROW_DARK = None
    _ARROW_WHITE = None

    def __init__(self, states, parent=None):
        super(ColoredStatusComboBox, self).__init__(parent)
        self._code_to_index = {}
        self._states = list(states)  # (name, code, color)
        self.setFixedWidth(140)  # ancho fijo para shot y task

        # Popup con delegate coloreado
        self.setView(QtWidgets.QListView())
        self.view().setItemDelegate(_StatusItemDelegate(self))

        # Cargar las flechas una sola vez (ruta relativa al .py via ICONS_DIR)
        if ColoredStatusComboBox._ARROW_DARK is None:
            ColoredStatusComboBox._ARROW_DARK = QPixmap(
                str(ICONS_DIR / "dropdown_arrow.svg")
            )
            ColoredStatusComboBox._ARROW_WHITE = QPixmap(
                str(ICONS_DIR / "dropdown_arrow_white.svg")
            )

        for idx, (name, code, color) in enumerate(states):
            self.addItem(name)
            self.setItemData(idx, code, Qt.UserRole)
            self.setItemData(idx, QBrush(QColor(color)), Qt.BackgroundRole)
            self.setItemData(
                idx, QBrush(QColor(_contrast_text_color(color))), Qt.ForegroundRole
            )
            self._code_to_index[code] = idx

        # Ocultar frame/arrow nativos: el combo cerrado lo pintamos en paintEvent.
        self.setStyleSheet(
            "QComboBox { border: none; border-radius: 3px; padding: 0px;"
            " min-height: 22px; }"
            " QComboBox::drop-down { width: 0px; border: none; }"
            " QComboBox::down-arrow { image: none; width: 0px; height: 0px; }"
            " QComboBox QAbstractItemView { background-color: #272727; outline: 0;"
            " border: 1px solid #555555; }"
        )

    def paintEvent(self, event):
        idx = self.currentIndex()
        if idx < 0 or idx >= len(self._states):
            super(ColoredStatusComboBox, self).paintEvent(event)
            return
        name, code, color = self._states[idx]
        text_color = _contrast_text_color(color)

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        r = self.rect()

        # Fondo redondeado con el color del estado + borde sutil
        painter.setPen(QColor("#555555"))
        painter.setBrush(QColor(color))
        painter.drawRoundedRect(r.adjusted(0, 0, -1, -1), 3, 3)

        # Texto del estado (UNA sola vez)
        painter.setPen(QColor(text_color))
        painter.drawText(
            r.adjusted(8, 0, -26, 0), Qt.AlignVCenter | Qt.AlignLeft, name
        )

        # Linea vertical separadora antes de la flecha
        line_x = r.right() - 22
        sep = QColor(text_color)
        sep.setAlpha(120)
        painter.setPen(sep)
        painter.drawLine(line_x, r.top() + 4, line_x, r.bottom() - 4)

        # Flecha (SVG segun contraste del fondo): clara salvo en fondos claros
        arrow = self._ARROW_DARK if text_color == "#000000" else self._ARROW_WHITE
        if arrow is not None and not arrow.isNull():
            aw = ah = 10
            ax = r.right() - 17
            ay = r.center().y() - ah // 2
            painter.drawPixmap(ax, ay, aw, ah, arrow)
        painter.end()

    def current_code(self):
        return self.itemData(self.currentIndex(), Qt.UserRole)

    def set_code(self, code):
        """Selecciona el item por codigo SG. Si no existe, no cambia nada."""
        idx = self._code_to_index.get(code)
        if idx is not None:
            self.setCurrentIndex(idx)
            return True
        return False


class ShotConfigDialog(QDialog):
    def __init__(
        self,
        clips_info,
        sequence_name=None,
        parent=None,
        dialog_mode="create",
        action_button_label=None,
        allow_thumbnail_creation=True,
        existing_thumb_path=None,
    ):
        super(ShotConfigDialog, self).__init__(parent)
        self.dialog_mode = dialog_mode
        self.allow_thumbnail_creation = allow_thumbnail_creation
        self.existing_thumb_path = existing_thumb_path
        self.setWindowTitle(
            "Flow | Modify Shot" if dialog_mode == "modify" else "Flow | Shot Creation"
        )
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        self.clips_info = clips_info
        self.sequence_name = sequence_name
        self.shot_config = None
        self.existing_tasks = set()
        
        # Diccionario para almacenar widgets de tasks dinámicamente
        # Estructura: {task_name: {widget_key: widget_object}}
        self.task_widgets = {}

        # Layout principal
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Titulo
        title_text = (
            "Configuracion para modificar shots"
            if dialog_mode == "modify"
            else "Configuracion para crear shots"
        )
        title_label = QLabel(title_text)
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet("color: #CCCCCC; padding: 5px;")
        layout.addWidget(title_label)

        # Informacion de clips
        clips_label = QLabel(f"Se van a procesar {len(self.clips_info)} clips:")
        clips_label.setStyleSheet("color: #CCCCCC; padding: 2px 5px 0px 5px;")
        layout.addWidget(clips_label)

        # Lista de clips
        for clip_info in self.clips_info:
            clip_frame = QFrame()
            clip_frame.setStyleSheet(
                "border: none; border-radius: 3px; margin: 1px; padding: 2px;"
            )
            clip_layout = QVBoxLayout(clip_frame)

            project_shot_label = QLabel(
                f"<span style='color: #6AB5CA;'>{clip_info['project_name']}</span> / <span style='color: #B56AB5;'>{clip_info['shot_code']}</span>"
            )
            project_shot_label.setTextFormat(Qt.RichText)
            clip_layout.addWidget(project_shot_label)

            layout.addWidget(clip_frame)

        # Espacio pequeño antes del separador
        layout.addSpacing(5)

        # Separador
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("color: #444444; margin: 0px;")
        layout.addWidget(separator)

        # Espacio pequeño después del separador
        layout.addSpacing(5)

        # Layout horizontal para thumbnail y descripción
        thumbnail_description_layout = QHBoxLayout()

        # Columna izquierda: Thumbnail (primera columna)
        self.thumbnail_placeholder_layout = QVBoxLayout()
        thumbnail_label = QLabel("Shot Thumbnail:")
        thumbnail_label.setStyleSheet(
            "color: #CCCCCC; font-weight: bold; padding-top: 5px;"
        )
        self.thumbnail_placeholder_layout.addWidget(thumbnail_label)

        # Placeholder para el thumbnail con tamaño fijo igual a la descripción
        self.thumbnail_placeholder = QLabel()
        self.thumbnail_placeholder.setFixedSize(120, 80)  # Ancho proporcional, altura igual al campo de descripción
        self.thumbnail_placeholder.setStyleSheet(
            """
            QLabel {
                border: 2px dashed #555555;
                border-radius: 3px;
                background-color: #1a1a1a;
                color: #666666;
                text-align: center;
                padding: 5px;
            }
        """
        )
        self.thumbnail_placeholder.setText("Thumbnail\n(120x80)")
        self.thumbnail_placeholder.setAlignment(Qt.AlignCenter)
        self.thumbnail_placeholder_layout.addWidget(self.thumbnail_placeholder)

        thumbnail_description_layout.addLayout(self.thumbnail_placeholder_layout, 1)  # Stretch factor reducido para dar más espacio a descripción

        # Espacio entre columnas
        thumbnail_description_layout.addSpacing(20)

        # Columna derecha: Descripción del shot (segunda columna)
        description_layout = QVBoxLayout()
        desc_label = QLabel("Shot Description:")
        desc_label.setStyleSheet(
            "color: #CCCCCC; font-weight: bold; padding-top: 5px;"
        )
        description_layout.addWidget(desc_label)

        self.description_text = QTextEdit()
        self.description_text.setMaximumHeight(80)  # 3 lineas aproximadamente
        self.description_text.setPlainText("")
        self.description_text.setStyleSheet(
            """
            QTextEdit {
                background-color: #272727;
                border: 1px solid #333333;
                color: #a7a7a7;
                padding: 5px;
                border-radius: 3px;
            }
        """
        )
        description_layout.addWidget(self.description_text)
        thumbnail_description_layout.addLayout(description_layout, 3)  # Stretch factor mayor para más espacio horizontal

        # Layout de 3 columnas principales: [Thumb+Desc] | [Sequence] | [Status+Priority]
        main_three_column_layout = QHBoxLayout()

        # Columna 1: Thumbnail + Descripción del shot (ya creado arriba)
        main_three_column_layout.addLayout(thumbnail_description_layout, 4)  # Stretch factor mayor para dar más espacio al shot description

        # Espacio entre columnas principales
        main_three_column_layout.addSpacing(30)

        # Columna 2: Sequence
        sequence_column_layout = QVBoxLayout()
        seq_label = QLabel("Sequence:")
        seq_label.setStyleSheet("color: #CCCCCC; font-weight: bold; padding-top: 5px;")
        sequence_column_layout.addWidget(seq_label)

        self.sequence_line_edit = QLineEdit()
        self.sequence_line_edit.setText(self.sequence_name)
        self.sequence_line_edit.setMaximumWidth(120)  # Limitar ancho máximo
        self.sequence_line_edit.setStyleSheet(
            """
            QLineEdit {
                background-color: #272727;
                border: 1px solid #333333;
                color: #a7a7a7;
                padding: 5px;
                border-radius: 3px;
                height: 20px;
            }
        """
        )
        sequence_column_layout.addWidget(self.sequence_line_edit)

        # Espaciador para alinear hacia arriba
        sequence_column_layout.addStretch()

        main_three_column_layout.addLayout(sequence_column_layout, 1)  # Stretch factor 1

        # Espacio entre segunda y tercera columna
        main_three_column_layout.addSpacing(30)

        # Columna 3: Shot status + Priority (layout vertical)
        status_priority_column_layout = QVBoxLayout()

        # Shot status (arriba)
        shot_status_layout = QVBoxLayout()
        shot_status_label = QLabel("Shot status:")
        shot_status_label.setStyleSheet("color: #CCCCCC; font-weight: bold; padding-top: 5px;")
        shot_status_layout.addWidget(shot_status_label)

        self.shot_status_combo = ColoredStatusComboBox(get_shot_states())
        self.shot_status_combo.set_code(DEFAULT_STATE_CODE)  # Ready to start por defecto
        shot_status_layout.addWidget(self.shot_status_combo)
        status_priority_column_layout.addLayout(shot_status_layout)

        # Espacio entre status y priority
        status_priority_column_layout.addSpacing(10)

        # Priority (abajo)
        priority_layout = QVBoxLayout()
        priority_label = QLabel("Priority:")
        priority_label.setStyleSheet("color: #CCCCCC; font-weight: bold; padding-top: 5px;")
        priority_layout.addWidget(priority_label)

        self.high_priority_cb = QCheckBox("High")
        self.high_priority_cb.setChecked(False)  # Desactivado por defecto
        self.high_priority_cb.setStyleSheet("color: #a7a7a7; padding: 2px;")
        priority_layout.addWidget(self.high_priority_cb)
        status_priority_column_layout.addLayout(priority_layout)

        main_three_column_layout.addLayout(status_priority_column_layout, 1)  # Stretch factor reducido

        layout.addLayout(main_three_column_layout)

        # Campo de tiempo estimado en días (se agrega en el layout de 5 columnas más abajo)
        self.estimated_days_line_edit = QLineEdit()
        self.estimated_days_line_edit.setText("0")
        self.estimated_days_line_edit.setMaxLength(5)  # Permitir decimales (ej: 12.5)
        self.estimated_days_line_edit.setFixedWidth(80)  # Ancho mayor para decimales
        self.estimated_days_line_edit.setStyleSheet(
            """
            QLineEdit {
                background-color: #272727;
                border: 1px solid #333333;
                color: #a7a7a7;
                padding: 5px;
                border-radius: 3px;
                height: 20px;
            }
        """
        )
        # Validación para números decimales
        validator = QDoubleValidator(0.0, 99.9, 1)  # Mínimo 0, máximo 99.9, 1 decimal
        validator.setNotation(QDoubleValidator.StandardNotation)
        self.estimated_days_line_edit.setValidator(validator)

        # Espacio pequeño antes del separador
        layout.addSpacing(10)

        # ==================================================================================
        # GENERACIÓN DINÁMICA DE TASKS
        # ==================================================================================
        # Generar una sección para cada task configurada
        for task_config in AVAILABLE_TASKS:
            # Separador antes de cada task
            task_separator = QFrame()
            task_separator.setFrameShape(QFrame.HLine)
            task_separator.setFrameShadow(QFrame.Sunken)
            task_separator.setStyleSheet("color: #444444;")
            layout.addWidget(task_separator)
            
            # Espaciado pequeño y consistente después del separador
            layout.addSpacing(1)
            
            # Crear fila de task
            task_layout = self.create_task_row(task_config, task_separator)
            layout.addLayout(task_layout)

        # Thumbnail del shot (solo si hay un clip seleccionado)
        self.thumbnail_label = None
        self.thumbnail_path = None
        self.take_snapshot_button = None
        debug_print(f"[INFO] Numero de clips seleccionados: {len(self.clips_info)}")
        if self.allow_thumbnail_creation and len(self.clips_info) == 1:
            debug_print("[INFO] Creando thumbnail para clip unico...")
            self.create_and_show_thumbnail()
        elif self.dialog_mode == "modify":
            # En Modify Shot siempre: si hay thumb en Flow lo muestra; si no, ofrece
            # el boton "Take Snapshot" (existing_thumb_path puede venir None).
            debug_print(
                "[INFO] Modify Shot: mostrando thumb actual de Flow o boton Take Snapshot..."
            )
            self.show_existing_thumbnail(self.existing_thumb_path)
        else:
            debug_print("[INFO] No se crea thumbnail (multiples clips en create)")

        # Espaciador
        layout.addStretch()

        # Botones
        button_layout = QHBoxLayout()

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.handle_cancel)
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

        button_layout.addSpacing(10)  # Espacio pequeño entre botones

        button_text = action_button_label
        if not button_text:
            button_text = "Modify Shot" if dialog_mode == "modify" else "Create Shot"
        self.create_button = QPushButton(button_text)
        self.create_button.clicked.connect(self.accept_config)
        self.create_button.setStyleSheet(
            """
            QPushButton {
                background-color: #443a91;
                color: #b2b2b2;
                padding: 8px 15px;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #774dcb;
                color: #CCCCCC;
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

    def create_task_row(self, task_config, task_separator):
        """
        Crea una fila de UI para una task de forma dinámica.
        
        Args:
            task_config (dict): Configuración de la task con keys: name, pipeline_step, enabled_by_default, color
            task_separator (QFrame): Separador asociado a esta task (para ocultarlo cuando está deshabilitada)
            
        Returns:
            QHBoxLayout: Layout con todos los widgets de la task
        """
        task_name = task_config["name"]
        enabled_by_default = task_config["enabled_by_default"]
        task_color = task_config.get("color", "#6AB5CA")  # Color por defecto si no está especificado
        
        # Inicializar diccionario para esta task
        self.task_widgets[task_name] = {}
        self.task_widgets[task_name]["separator"] = task_separator
        
        # Layout principal de 5 columnas
        task_layout = QHBoxLayout()

        # ===== Columna 1: Checkbox Enable y Nombre de Task =====
        name_layout = QHBoxLayout()  # Cambiado a horizontal
        name_layout.setSpacing(1)  # Espacio pequeño entre checkbox y nombre
        name_layout.setContentsMargins(0, 0, 0, 0)  # Sin márgenes adicionales
        
        enabled_cb = QCheckBox("")  # Checkbox sin texto
        enabled_cb.setChecked(enabled_by_default)
        enabled_cb.setStyleSheet("color: #a7a7a7; padding: 2px;")
        name_layout.addWidget(enabled_cb)
        
        name_label = QLabel(task_name.upper())
        name_label.setStyleSheet(f"color: {task_color}; font-weight: bold; padding-top: 0px; font-size: 12px;")
        name_layout.addWidget(name_label)
        
        # Espaciador para empujar todo a la izquierda
        name_layout.addStretch()
        
        task_layout.addLayout(name_layout, 1)
        
        self.task_widgets[task_name]["enabled"] = enabled_cb

        # Espacio entre columnas
        task_layout.addSpacing(30)

        # ===== Columna 2: Est. Days =====
        est_days_widget = QFrame()  # Widget contenedor para poder ocultarlo
        est_days_widget.setFrameShape(QFrame.NoFrame)  # Sin borde visible
        est_days_layout = QVBoxLayout(est_days_widget)
        est_days_layout.setContentsMargins(0, 0, 0, 0)  # Sin márgenes adicionales
        est_days_label = QLabel("Est. Days")
        est_days_label.setStyleSheet("color: #CCCCCC; font-weight: bold; padding-top: 3px;")
        est_days_layout.addWidget(est_days_label)

        estimated_days_edit = QLineEdit()
        estimated_days_edit.setText("0")
        estimated_days_edit.setMaxLength(5)  # Permitir decimales (ej: 12.5)
        estimated_days_edit.setFixedWidth(80)
        estimated_days_edit.setStyleSheet(
            """
            QLineEdit {
                background-color: #272727;
                border: 1px solid #333333;
                color: #a7a7a7;
                padding: 2px 5px;
                border-radius: 3px;
                height: 20px;
            }
        """
        )
        # Validación para números decimales
        validator = QDoubleValidator(0.0, 99.9, 1)
        validator.setNotation(QDoubleValidator.StandardNotation)
        estimated_days_edit.setValidator(validator)
        
        est_days_layout.addWidget(estimated_days_edit)
        task_layout.addWidget(est_days_widget, 1)
        
        self.task_widgets[task_name]["estimated_days"] = estimated_days_edit
        self.task_widgets[task_name]["est_days_label"] = est_days_label
        self.task_widgets[task_name]["est_days_widget"] = est_days_widget

        # Espacio entre columnas
        task_layout.addSpacing(30)

        # ===== Columna 3: Status =====
        status_widget = QFrame()  # Widget contenedor para poder ocultarlo
        status_widget.setFrameShape(QFrame.NoFrame)  # Sin borde visible
        status_layout = QVBoxLayout(status_widget)
        status_layout.setContentsMargins(0, 0, 0, 0)  # Sin márgenes adicionales
        status_label = QLabel("Status")
        status_label.setStyleSheet("color: #CCCCCC; font-weight: bold; padding-top: 0px;")
        status_layout.addWidget(status_label)

        task_status_combo = ColoredStatusComboBox(get_task_states())
        task_status_combo.set_code(DEFAULT_STATE_CODE)  # Ready to start por defecto
        status_layout.addWidget(task_status_combo)
        task_layout.addWidget(status_widget, 1)

        self.task_widgets[task_name]["task_status"] = task_status_combo
        self.task_widgets[task_name]["status_label"] = status_label
        self.task_widgets[task_name]["status_widget"] = status_widget

        # Espacio entre columnas
        task_layout.addSpacing(30)

        # ===== Columna 4: Description =====
        desc_widget = QFrame()  # Widget contenedor para poder ocultarlo
        desc_widget.setFrameShape(QFrame.NoFrame)  # Sin borde visible
        desc_layout = QVBoxLayout(desc_widget)
        desc_layout.setContentsMargins(0, 0, 0, 0)  # Sin márgenes adicionales
        desc_label = QLabel("Description")
        desc_label.setStyleSheet("color: #CCCCCC; font-weight: bold; padding-top: 0px;")
        desc_layout.addWidget(desc_label)

        copy_description_cb = QCheckBox("copy from shot")
        copy_description_cb.setChecked(True)  # Activado por defecto
        copy_description_cb.setStyleSheet("color: #a7a7a7; padding: 5px;")
        desc_layout.addWidget(copy_description_cb)
        task_layout.addWidget(desc_widget, 1)
        
        self.task_widgets[task_name]["copy_description"] = copy_description_cb
        self.task_widgets[task_name]["desc_label"] = desc_label
        self.task_widgets[task_name]["desc_widget"] = desc_widget

        # Espacio entre columnas
        task_layout.addSpacing(30)

        # ===== Columna 5: Reviewers (más ancha) =====
        reviewers_widget = QFrame()  # Widget contenedor para poder ocultarlo
        reviewers_widget.setFrameShape(QFrame.NoFrame)  # Sin borde visible
        reviewers_layout = QVBoxLayout(reviewers_widget)
        reviewers_layout.setContentsMargins(0, 0, 0, 0)  # Sin márgenes adicionales
        reviewers_label = QLabel("Reviewers")
        reviewers_label.setStyleSheet("color: #CCCCCC; font-weight: bold; padding-top: 0px;")
        reviewers_layout.addWidget(reviewers_label)

        # Reviewers checkboxes en línea horizontal
        reviewers_checkboxes_layout = QHBoxLayout()

        reviewer_lega_cb = QCheckBox("Lega")
        reviewer_lega_cb.setChecked(True)
        reviewer_lega_cb.setStyleSheet("color: #a7a7a7; padding: 2px;")
        reviewers_checkboxes_layout.addWidget(reviewer_lega_cb)

        reviewer_sebas_cb = QCheckBox("Sebas")
        reviewer_sebas_cb.setChecked(True)
        reviewer_sebas_cb.setStyleSheet("color: #a7a7a7; padding: 2px;")
        reviewers_checkboxes_layout.addWidget(reviewer_sebas_cb)

        reviewer_juano_cb = QCheckBox("Juano")
        reviewer_juano_cb.setChecked(True)
        reviewer_juano_cb.setStyleSheet("color: #a7a7a7; padding: 2px;")
        reviewers_checkboxes_layout.addWidget(reviewer_juano_cb)

        reviewer_charly_cb = QCheckBox("Charly")
        reviewer_charly_cb.setChecked(True)
        reviewer_charly_cb.setStyleSheet("color: #a7a7a7; padding: 2px;")
        reviewers_checkboxes_layout.addWidget(reviewer_charly_cb)

        reviewer_javi_cb = QCheckBox("Javi")
        reviewer_javi_cb.setChecked(True)
        reviewer_javi_cb.setStyleSheet("color: #a7a7a7; padding: 2px;")
        reviewers_checkboxes_layout.addWidget(reviewer_javi_cb)

        reviewers_layout.addLayout(reviewers_checkboxes_layout)
        task_layout.addWidget(reviewers_widget, 2)  # Stretch factor 2 para hacerla más ancha
        
        self.task_widgets[task_name]["reviewer_lega"] = reviewer_lega_cb
        self.task_widgets[task_name]["reviewer_sebas"] = reviewer_sebas_cb
        self.task_widgets[task_name]["reviewer_juano"] = reviewer_juano_cb
        self.task_widgets[task_name]["reviewer_charly"] = reviewer_charly_cb
        self.task_widgets[task_name]["reviewer_javi"] = reviewer_javi_cb
        self.task_widgets[task_name]["reviewers_label"] = reviewers_label
        self.task_widgets[task_name]["reviewers_widget"] = reviewers_widget

        # ===== Conectar checkbox de enable para habilitar/deshabilitar campos =====
        enabled_cb.toggled.connect(
            lambda checked, tn=task_name: self.toggle_task_fields(tn, checked)
        )
        
        # Aplicar estado inicial
        self.toggle_task_fields(task_name, enabled_by_default)

        return task_layout

    def toggle_task_fields(self, task_name, enabled):
        """
        Muestra u oculta las columnas de configuración de una task según el estado del checkbox.
        
        Args:
            task_name (str): Nombre de la task
            enabled (bool): Si está habilitada o no
        """
        widgets = self.task_widgets.get(task_name, {})
        
        # Ocultar/mostrar los widgets contenedores de las columnas (2-5)
        column_widgets = [
            "est_days_widget",
            "status_widget",
            "desc_widget",
            "reviewers_widget"
        ]
        
        for widget_key in column_widgets:
            widget = widgets.get(widget_key)
            if widget:
                widget.setVisible(enabled)
        
        # Mostrar/ocultar el separador
        separator = widgets.get("separator")
        if separator:
            separator.setVisible(enabled)
        
        # Ajustar el tamaño de la ventana para acomodar el cambio
        # Esperar un frame para que Qt actualice el layout
        QTimer.singleShot(0, self.adjust_window_size)
    
    def set_task_fields_editable(self, task_name, editable):
        """Habilita o deshabilita los campos editables de una task."""
        widgets = self.task_widgets.get(task_name, {})
        field_keys = [
            "estimated_days",
            "task_status",
            "copy_description",
            "reviewer_lega",
            "reviewer_sebas",
            "reviewer_juano",
            "reviewer_charly",
            "reviewer_javi",
        ]
        for key in field_keys:
            widget = widgets.get(key)
            if widget:
                widget.setEnabled(editable)

    def set_shot_fields_editable(self, editable):
        """Habilita o deshabilita los campos generales del shot."""
        if hasattr(self, "shot_status_combo"):
            self.shot_status_combo.setEnabled(editable)
        if hasattr(self, "high_priority_cb"):
            self.high_priority_cb.setEnabled(editable)

    def prefill_from_existing_shot(
        self,
        shot_data,
        existing_tasks_map,
        lock_existing_task_fields=True,
    ):
        """Prefill de la UI con datos existentes (modo Modify)."""
        if not shot_data:
            return

        description = shot_data.get("description") or ""
        self.description_text.setPlainText(description)

        # Secuencia desde el shot si está disponible
        seq_entity = shot_data.get("sg_sequence") or {}
        sequence_value = (
            seq_entity.get("name")
            or seq_entity.get("code")
            or self.sequence_line_edit.text()
        )
        if sequence_value:
            self.sequence_line_edit.setText(sequence_value)

        # Estado y prioridad REALES del shot desde Flow
        self.shot_status_combo.set_code(shot_data.get("sg_status_list"))
        self.high_priority_cb.setChecked(
            (shot_data.get("sg_prioridad") or "").lower() == "high"
        )

        if lock_existing_task_fields:
            self.set_shot_fields_editable(False)

        for task_name, task_info in existing_tasks_map.items():
            widgets = self.task_widgets.get(task_name)
            if not widgets:
                continue

            self.existing_tasks.add(task_name)

            widgets["enabled"].blockSignals(True)
            widgets["enabled"].setChecked(True)
            widgets["enabled"].blockSignals(False)

            self.toggle_task_fields(task_name, True)
            widgets["enabled"].setProperty("existing_task", True)

            # Estado REAL de la task desde Flow
            widgets["task_status"].set_code(task_info.get("sg_status_list"))

            # Reviewers REALES desde Flow (task_reviewers)
            rev_cfg = reviewers_config_from_task(task_info)
            widgets["reviewer_lega"].setChecked(rev_cfg.get("lega_pugliese", False))
            widgets["reviewer_sebas"].setChecked(rev_cfg.get("sebas_romano", False))
            widgets["reviewer_juano"].setChecked(rev_cfg.get("juano", False))
            widgets["reviewer_charly"].setChecked(rev_cfg.get("charly_villafane", False))
            widgets["reviewer_javi"].setChecked(rev_cfg.get("javi_bravo", False))

            # Dias estimados reales (si los hay) - solo informativo
            est = task_info.get("sg_estdias")
            if est:
                try:
                    widgets["estimated_days"].setText(str(est))
                except Exception:
                    pass

            if lock_existing_task_fields:
                self.set_task_fields_editable(task_name, False)
    
    def adjust_window_size(self):
        """Ajusta el tamaño de la ventana según el contenido visible"""
        self.adjustSize()
        self.updateGeometry()

    def accept_config(self):
        """Acepta la configuracion y guarda los valores"""
        action_label = "Modify Shot" if self.dialog_mode == "modify" else "Create Shot"
        debug_print(f"Boton '{action_label}' presionado")
        # Configuración base del shot
        self.shot_config = {
            "description": self.description_text.toPlainText(),
            "sequence_name": self.sequence_line_edit.text().strip(),
            "shot_status": self.shot_status_combo.current_code(),
            "high_priority": self.high_priority_cb.isChecked(),
        }
        
        # Recopilar configuración de tasks dinámicamente
        tasks_config = {}
        for task_name, widgets in self.task_widgets.items():
            # Obtener el valor de días estimados
            try:
                estimated_days_text = widgets["estimated_days"].text().strip()
                estimated_days = float(estimated_days_text) if estimated_days_text else 0.0
            except ValueError:
                estimated_days = 0.0
            
            tasks_config[task_name] = {
                "enabled": widgets["enabled"].isChecked(),
                "task_status": widgets["task_status"].current_code(),
                "copy_description": widgets["copy_description"].isChecked(),
                "estimated_days": estimated_days,
                "reviewers": {
                    "lega_pugliese": widgets["reviewer_lega"].isChecked(),
                    "sebas_romano": widgets["reviewer_sebas"].isChecked(),
                    "juano": widgets["reviewer_juano"].isChecked(),
                    "charly_villafane": widgets["reviewer_charly"].isChecked(),
                    "javi_bravo": widgets["reviewer_javi"].isChecked(),
                }
            }
        
        self.shot_config["tasks"] = tasks_config
        self.accept()

    def handle_cancel(self):
        action_label = "Modify Shot" if self.dialog_mode == "modify" else "Create Shot"
        debug_print(f"Boton 'Cancel' presionado (modo: {action_label})")
        self.reject()

    def get_config(self):
        """Retorna la configuracion seleccionada"""
        return self.shot_config

    def create_and_show_thumbnail(self):
        """Crea y muestra el thumbnail del shot en la columna derecha"""
        try:
            # Crear el thumbnail
            thumbnail_path = create_shot_thumbnail()
            if thumbnail_path:
                self.thumbnail_path = thumbnail_path

                # Remover el placeholder
                self.thumbnail_placeholder.hide()
                self.thumbnail_placeholder.setParent(None)

                # Widget para mostrar el thumbnail
                self.thumbnail_label = QLabel()
                self.thumbnail_label.setAlignment(Qt.AlignCenter)
                self.thumbnail_label.setStyleSheet(
                    """
                    QLabel {
                        border: none;
                        border-radius: 3px;
                        padding: 5px;
                        background-color: transparent;
                    }
                """
                )

                # Cargar y escalar la imagen
                pixmap = QPixmap(thumbnail_path)
                if not pixmap.isNull():
                    # Escalar la imagen manteniendo la relacion de aspecto, con altura fija de 80px
                    scaled_pixmap = pixmap.scaledToHeight(
                        80, Qt.SmoothTransformation
                    )
                    self.thumbnail_label.setPixmap(scaled_pixmap)

                    # Ajustar el ancho para que quepa en el layout (máximo ~120px considerando padding)
                    label_width = min(scaled_pixmap.width() + 10, 120)
                    self.thumbnail_label.setFixedSize(label_width, 80)

                    # Reemplazar el placeholder con el thumbnail real
                    self.thumbnail_placeholder_layout.addWidget(self.thumbnail_label)
                    debug_print(f"✅ Thumbnail mostrado en la UI: {thumbnail_path}")
                else:
                    debug_print("❌ No se pudo cargar el pixmap del thumbnail")
                    # Mostrar mensaje de error en el placeholder
                    self.thumbnail_placeholder.setText("Error\ncargando\nthumbnail")
                    self.thumbnail_placeholder.setStyleSheet(
                        """
                        QLabel {
                            border: 2px dashed #C05050;
                            border-radius: 3px;
                            background-color: #1a1a1a;
                            color: #C05050;
                            text-align: center;
                            padding: 5px;
                        }
                    """
                    )
            else:
                debug_print("❌ No se pudo crear el thumbnail")
                # Mostrar mensaje cuando no se puede crear el thumbnail
                self.thumbnail_placeholder.setText("No se pudo\ncrear\nthumbnail")
                self.thumbnail_placeholder.setStyleSheet(
                    """
                    QLabel {
                        border: 2px dashed #C05050;
                        border-radius: 3px;
                        background-color: #1a1a1a;
                        color: #C05050;
                        text-align: center;
                        padding: 5px;
                    }
                """
                )
        except Exception as e:
            debug_print(f"❌ Error creando thumbnail: {e}")
            # Mostrar mensaje de error
            self.thumbnail_placeholder.setText("Error\ncreando\nthumbnail")
            self.thumbnail_placeholder.setStyleSheet(
                """
                QLabel {
                    border: 2px dashed #C05050;
                    border-radius: 3px;
                    background-color: #1a1a1a;
                    color: #C05050;
                    text-align: center;
                    padding: 5px;
                }
            """
            )

    def show_existing_thumbnail(self, thumb_path):
        """Muestra en el placeholder el thumbnail actual del shot (descargado de Flow).
        Usado en Modify Shot para ver el thumb que el shot ya tiene en Flow.
        Si el shot no tiene thumbnail, ofrece un boton para capturar uno."""
        try:
            if thumb_path and os.path.exists(thumb_path):
                pixmap = QPixmap(thumb_path)
                if not pixmap.isNull():
                    scaled_pixmap = pixmap.scaledToHeight(80, Qt.SmoothTransformation)
                    self.thumbnail_placeholder.setText("")
                    self.thumbnail_placeholder.setPixmap(scaled_pixmap)
                    label_width = min(scaled_pixmap.width() + 10, 120)
                    self.thumbnail_placeholder.setFixedSize(label_width, 80)
                    debug_print(f"✅ Thumbnail actual de Flow mostrado: {thumb_path}")
                    return
            # Sin thumbnail en Flow (o no se pudo cargar): ofrecer capturar uno
            debug_print("ℹ️ El shot no tiene thumbnail en Flow: ofreciendo Take Snapshot")
            self._show_take_snapshot_button()
        except Exception as e:
            debug_print(f"❌ Error mostrando el thumbnail actual: {e}")

    def _show_take_snapshot_button(self):
        """Reemplaza el placeholder vacio por un boton para capturar un snapshot del
        viewer. El snapshot NO se sube a Flow hasta confirmar con 'Modify Shot'."""
        self.thumbnail_placeholder.hide()
        self.thumbnail_placeholder.setParent(None)
        self.take_snapshot_button = QPushButton("Take\nSnapshot")
        self.take_snapshot_button.setFixedSize(120, 80)
        self.take_snapshot_button.setStyleSheet(
            """
            QPushButton {
                background-color: #443a91;
                color: #b2b2b2;
                border: 1px solid #555555;
                border-radius: 3px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #774dcb; color: #CCCCCC; }
            """
        )
        self.take_snapshot_button.clicked.connect(self._on_take_snapshot_clicked)
        self.thumbnail_placeholder_layout.addWidget(self.take_snapshot_button)

    def _on_take_snapshot_clicked(self):
        """Captura un snapshot del viewer y lo muestra. Queda en self.thumbnail_path
        para que Modify Shot lo suba a Flow al confirmar."""
        thumbnail_path = create_shot_thumbnail()
        if not thumbnail_path:
            debug_print("❌ No se pudo capturar el snapshot del viewer (reintentar)")
            return  # dejar el boton para reintentar
        self.thumbnail_path = thumbnail_path
        if self.take_snapshot_button is not None:
            self.take_snapshot_button.hide()
            self.take_snapshot_button.setParent(None)
            self.take_snapshot_button = None
        self._show_captured_thumbnail_pixmap(thumbnail_path)
        debug_print(f"✅ Snapshot capturado (sin subir aun): {thumbnail_path}")

    def _show_captured_thumbnail_pixmap(self, thumbnail_path):
        """Muestra el snapshot recien capturado en la columna del thumbnail."""
        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignCenter)
        pixmap = QPixmap(thumbnail_path)
        if not pixmap.isNull():
            scaled = pixmap.scaledToHeight(80, Qt.SmoothTransformation)
            self.thumbnail_label.setPixmap(scaled)
            self.thumbnail_label.setFixedSize(min(scaled.width() + 10, 120), 80)
        self.thumbnail_placeholder_layout.addWidget(self.thumbnail_label)

    def cleanup_thumbnail(self):
        """Limpia el archivo temporal del thumbnail"""
        if self.thumbnail_path and os.path.exists(self.thumbnail_path):
            try:
                os.remove(self.thumbnail_path)
                debug_print(f"✅ Archivo temporal eliminado: {self.thumbnail_path}")
            except Exception as e:
                debug_print(f"❌ Error eliminando archivo temporal: {e}")
        # Tambien limpiar el thumbnail actual descargado de Flow (Modify Shot)
        if self.existing_thumb_path and os.path.exists(self.existing_thumb_path):
            try:
                os.remove(self.existing_thumb_path)
                debug_print(
                    f"✅ Archivo temporal (thumb Flow) eliminado: {self.existing_thumb_path}"
                )
            except Exception as e:
                debug_print(f"❌ Error eliminando thumb temporal de Flow: {e}")

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
        self.task_type = task_type
        if task_type == "crear shot":
            self.setWindowTitle("Flow | Create Shot")
        elif task_type == "modificar shot":
            self.setWindowTitle("Flow | Modify Shot")
        else:
            self.setWindowTitle("Flow | Flow")
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
        task_text_map = {
            "crear shot": "Creando shot en ShotGrid",
            "modificar shot": "Modificando shot en ShotGrid",
        }
        task_text = task_text_map.get(task_type, "Procesando")

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
        self.project_cache = {}

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

    def get_project_id(self, project_name):
        """Obtiene y cachea el ID del proyecto."""
        if not self.sg or not project_name:
            return None

        if project_name in self.project_cache:
            return self.project_cache[project_name]

        projects = self.sg.find(
            "Project",
            [["name", "is", project_name]],
            ["id", "name"],
        )
        if projects:
            project_id = projects[0]["id"]
            self.project_cache[project_name] = project_id
            return project_id

        debug_print(f"No se encontro el proyecto en ShotGrid: {project_name}")
        return None

    def shot_exists(self, project_name, shot_code):
        """Verifica si un shot existe en Flow."""
        if not self.sg:
            return False, None
        project_id = self.get_project_id(project_name)
        if not project_id:
            return False, None
        filters = [
            ["project", "is", {"type": "Project", "id": project_id}],
            ["code", "is", shot_code],
        ]
        fields = [
            "id",
            "code",
            "description",
            "sg_status_list",
            "sg_prioridad",
            "sg_sequence",
            "project",
        ]
        shots = self.sg.find("Shot", filters, fields)
        if shots:
            return True, shots[0]
        return False, None

    def find_shot_and_tasks(
        self,
        project_name,
        shot_code,
        shot_config=None,
        thumbnail_path=None,
        create_if_missing=True,
        file_path=None,
    ):
        """Encuentra el shot en ShotGrid y sus tareas asociadas. Si no existe, lo crea.
        Retorna: (shot, tasks, was_created) donde was_created es True si se creó nuevo."""
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return None, None, False
        project_id = self.get_project_id(project_name)
        if not project_id:
            return None, None, False

        filters = [
            ["project", "is", {"type": "Project", "id": project_id}],
            ["code", "is", shot_code],
        ]
        fields = [
            "id",
            "code",
            "description",
            "sg_status_list",
            "sg_prioridad",
            "sg_sequence",
            "project",
            "image",  # URL del thumbnail actual del shot (para mostrarlo en Modify Shot)
        ]
        shots = self.sg.find("Shot", filters, fields)
        if shots:
            shot_id = shots[0]["id"]
            debug_print(
                f"Shot existente encontrado: {shot_code}. No se realizarán modificaciones desde Create Shot."
            )

            tasks = self.find_tasks_for_shot(shot_id)
            return shots[0], tasks, False  # False = no fue creado, ya existía

        if not create_if_missing:
            debug_print(
                f"Shot '{shot_code}' no existe y create_if_missing=False (modo lectura)."
            )
            return None, None, False

        if not shot_config:
            debug_print("No se proporciono shot_config para crear el shot.")
            return None, None, False

        debug_print("No se encontro el shot. Creando shot...")
        created_shot = self.create_shot(
            project_id, shot_code, shot_config, thumbnail_path, file_path=file_path
        )
        if created_shot:
            tasks = self.find_tasks_for_shot(created_shot["id"])

            # ==================================================================================
            # CREAR CARPETAS PARA LAS TASKS HABILITADAS
            # ==================================================================================
            if file_path and shot_config:
                shot_base_path = self.calculate_shot_base_path(file_path)
                if shot_base_path:
                    # Obtener lista de tasks habilitadas
                    enabled_tasks = []
                    tasks_config = shot_config.get("tasks", {})
                    for task_name, task_cfg in tasks_config.items():
                        if task_cfg.get("enabled", False):
                            enabled_tasks.append(task_name)

                    if enabled_tasks:
                        debug_print(f"Creando carpetas para tasks: {', '.join(enabled_tasks)}")
                        folder_result, folder_logs = create_folders_for_shot_tasks(
                            shot_base_path, enabled_tasks
                        )
                        # Loguear todos los mensajes del proceso de carpetas
                        for log_msg in folder_logs:
                            debug_print(log_msg)
                    else:
                        debug_print("No hay tasks habilitadas para crear carpetas")
                else:
                    debug_print("No se pudo calcular shot_base_path para crear carpetas")

            return created_shot, tasks, True  # True = fue creado
        return None, None, False

    def find_tasks_for_shot(self, shot_id, shot_config=None):
        """Encuentra las tareas asociadas a un shot."""
        if not self.sg:
            return []

        try:
            filters = [["entity", "is", {"type": "Shot", "id": shot_id}]]
            fields = [
                "id",
                "content",
                "sg_status_list",
                "sg_description",
                "sg_estdias",
                "task_reviewers",
            ]
            tasks = self.sg.find("Task", filters, fields)
            debug_print(f"Encontradas {len(tasks)} tareas para el shot")

            # NOTA: Las tasks creadas manualmente ya tienen la configuración correcta
            # No necesitamos actualizarlas nuevamente para evitar conflictos
            debug_print(
                "Tasks procesadas correctamente (configuracion aplicada en creacion)"
            )

            return tasks
        except Exception as e:
            debug_print(f"Error en find_tasks_for_shot: {e}")
            return []

    def delete_task(self, task_id):
        """Elimina una task existente."""
        if not self.sg:
            return False
        try:
            self.sg.delete("Task", task_id)
            debug_print(f"Task eliminada (ID: {task_id})")
            return True
        except Exception as e:
            debug_print(f"Error eliminando task {task_id}: {e}")
            return False

    def update_shot_description(self, shot_id, description):
        """Actualiza la descripción del shot."""
        if not self.sg:
            return False
        try:
            self.sg.update("Shot", shot_id, {"description": description})
            debug_print("Descripcion del shot actualizada")
            return True
        except Exception as e:
            debug_print(f"Error actualizando descripcion del shot: {e}")
            return False

    def update_shot_status(self, shot_id, status_code):
        """Actualiza el estado (sg_status_list) de un shot."""
        if not self.sg or not status_code:
            return False
        try:
            self.sg.update("Shot", shot_id, {"sg_status_list": status_code})
            debug_print(f"Shot status actualizado a '{status_code}'")
            return True
        except Exception as e:
            debug_print(f"Error actualizando shot status: {e}")
            return False

    def update_shot_priority(self, shot_id, priority_code):
        """Actualiza la prioridad (sg_prioridad) de un shot ('high'/'normal')."""
        if not self.sg or not priority_code:
            return False
        try:
            self.sg.update("Shot", shot_id, {"sg_prioridad": priority_code})
            debug_print(f"Shot prioridad actualizada a '{priority_code}'")
            return True
        except Exception as e:
            debug_print(f"Error actualizando shot prioridad: {e}")
            return False

    def update_task_reviewers(self, task_id, reviewers_config):
        """Actualiza los reviewers (task_reviewers) de una task desde el dict de la UI."""
        if not self.sg:
            return False
        reviewer_ids = resolve_reviewer_ids(self.sg, reviewers_config)
        try:
            self.sg.update("Task", task_id, {"task_reviewers": reviewer_ids})
            debug_print(f"Reviewers de task {task_id} actualizados ({len(reviewer_ids)})")
            return True
        except Exception as e:
            debug_print(f"Error actualizando reviewers: {e}")
            return False

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

    def create_shot(
        self, project_id, shot_code, shot_config, thumbnail_path=None, file_path=None
    ):
        """Crea un shot en ShotGrid SIN usar templates - crea tasks manualmente."""
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return None

        # Secuencia: primario desde la ruta del clip (segmento despues de
        # VFX-NOMBRE), fallback al valor del dialog (que por defecto ya viene del
        # path del primer clip o del nombre del timeline de Hiero).
        sequence_name = extract_sequence_name_from_path(file_path)
        if sequence_name:
            debug_print(f"Secuencia (from path): {sequence_name}")
        else:
            sequence_name = shot_config.get("sequence_name")
            debug_print(f"Secuencia (from dialog/timeline fallback): {sequence_name}")
        debug_print(f"Creando shot '{shot_code}' manualmente sin template...")

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

        # Crear el shot SIN template
        shot_data = {
            "project": {"type": "Project", "id": project_id},
            "code": shot_code,
            "description": shot_config["description"],
            "sg_sequence": {"type": "Sequence", "id": sequence_id},
            # NOTA: No se incluye "task_template" para evitar usar templates predefinidos
        }

        # Estado del shot desde el dropdown (default: ready)
        shot_data["sg_status_list"] = shot_config.get("shot_status", DEFAULT_STATE_CODE)

        # Agregar prioridad alta si esta configurada
        if shot_config.get("high_priority", False):
            shot_data["sg_prioridad"] = "high"

        try:
            new_shot = self.sg.create("Shot", shot_data)
            debug_print(
                f"Shot creado exitosamente: {new_shot['code']} (ID: {new_shot['id']})"
            )

            # ==================================================================================
            # CREAR TASKS DINÁMICAMENTE
            # ==================================================================================
            tasks_config = shot_config.get("tasks", {})
            
            for task_name, task_cfg in tasks_config.items():
                # Saltar tasks deshabilitadas
                if not task_cfg.get("enabled", False):
                    debug_print(f"Task '{task_name}' deshabilitada por configuración del usuario")
                    continue
                
                # Crear la task
                success = self.create_task_for_shot(
                    project_id=project_id,
                    shot_id=new_shot["id"],
                    task_name=task_name,
                    task_config=task_cfg,
                    shot_description=shot_config["description"]
                )
                
                if success:
                    debug_print(f"Task '{task_name}' creada exitosamente")
                else:
                    debug_print(f"Error creando task '{task_name}'")

            # Subir thumbnail si se proporciono
            if thumbnail_path:
                debug_print(f"Subiendo thumbnail para shot: {shot_code} - Path: {thumbnail_path}")
                debug_print(f"Archivo existe: {os.path.exists(thumbnail_path)}")
                upload_success = self.upload_thumbnail(
                    "Shot", new_shot["id"], thumbnail_path
                )
                if upload_success:
                    debug_print(f"Thumbnail subido exitosamente para shot: {shot_code}")
                else:
                    debug_print(f"Error subiendo thumbnail para shot: {shot_code}")
            else:
                debug_print(f"No se proporciono thumbnail_path para shot: {shot_code}")

            return new_shot
        except Exception as e:
            debug_print(f"ERROR al crear el shot: {e}")
            return None

    def create_task_for_shot(self, project_id, shot_id, task_name, task_config, shot_description):
        """
        Crea una task para un shot de forma genérica.
        
        Args:
            project_id (int): ID del proyecto
            shot_id (int): ID del shot
            task_name (str): Nombre de la task (ej: "Comp", "Roto")
            task_config (dict): Configuración de la task
            shot_description (str): Descripción del shot (para copiar si está habilitado)
            
        Returns:
            bool: True si se creó exitosamente, False si hubo error
        """
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return False
        
        try:
            # Buscar el pipeline step correspondiente
            # NOTA: Para encontrar el pipeline step, buscamos por el nombre de la task
            # que debe coincidir con el código del step en ShotGrid
            pipeline_step_name = None
            for task_cfg in AVAILABLE_TASKS:
                if task_cfg["name"] == task_name:
                    pipeline_step_name = task_cfg["pipeline_step"]
                    break
            
            if not pipeline_step_name:
                debug_print(f"ADVERTENCIA: No se encontró configuración para task '{task_name}'")
                pipeline_step_name = task_name  # Usar el nombre de la task como fallback
            
            step_filters = [["code", "is", pipeline_step_name]]
            steps = self.sg.find("Step", step_filters, ["id", "code"])
            step_id = None
            if steps:
                step_id = steps[0]["id"]
                debug_print(f"Pipeline step '{pipeline_step_name}' encontrado (ID: {step_id})")
            else:
                debug_print(f"ADVERTENCIA: No se encontró el pipeline step '{pipeline_step_name}'")
            
            # Crear data de la task
            task_data = {
                "content": task_name,
                "entity": {"type": "Shot", "id": shot_id},
                "sg_status_list": "noread",  # Estado inicial por defecto
                "project": {"type": "Project", "id": project_id},
            }
            
            # Asignar pipeline step si se encontró
            if step_id:
                task_data["step"] = {"type": "Step", "id": step_id}
            
            # Estado de la task desde el dropdown (default: noread)
            task_data["sg_status_list"] = task_config.get("task_status", "noread")

            # Copiar descripción del shot si está habilitado
            if task_config.get("copy_description", False) and shot_description:
                task_data["sg_description"] = shot_description
            
            # Agregar tiempo estimado si es mayor que 0
            # Aplicar reducción del 30% antes de subir a Flow
            estimated_days = task_config.get("estimated_days", 0)
            if estimated_days > 0:
                # Reducir 30%: multiplicar por 0.7 (ej: 1 día -> 0.7 días)
                estimated_days_reduced = estimated_days * 0.7
                task_data["sg_estdias"] = estimated_days_reduced
                debug_print(f"Tiempo estimado: {estimated_days} días -> {estimated_days_reduced:.2f} días (reducción 30%)")
            
            # Crear la task
            new_task = self.sg.create("Task", task_data)
            debug_print(f"Task '{task_name}' creada exitosamente (ID: {new_task['id']})")
            
            # Asignar reviewers (resuelve nombres -> HumanUser ids con el helper compartido)
            selected_reviewer_ids = resolve_reviewer_ids(
                self.sg, task_config.get("reviewers", {})
            )

            # Asignar todos los reviewers a la task usando task_reviewers
            if selected_reviewer_ids:
                try:
                    self.sg.update("Task", new_task["id"], {"task_reviewers": selected_reviewer_ids})
                    debug_print(f"Asignados {len(selected_reviewer_ids)} reviewers a task {task_name}")
                except Exception as e:
                    debug_print(f"Error asignando reviewers a task: {e}")
            else:
                debug_print(f"No se seleccionaron reviewers para task '{task_name}'")
            
            return True
            
        except Exception as e:
            debug_print(f"ERROR al crear task '{task_name}': {e}")
            return False


class HieroOperations:
    """Clase para manejar operaciones en Hiero."""

    def __init__(self, shotgrid_manager):
        self.sg_manager = shotgrid_manager

    def parse_exr_name(self, file_name):
        """Extrae el nombre base del archivo EXR y el numero de version."""
        base_name = clean_base_name(file_name)
        version_match = re.search(r"_v(\d+)", file_name)
        version_number = version_match.group(1) if version_match else "Unknown"
        return base_name, version_number

    def get_selected_clips_info(self):
        """Obtiene informacion de los clips usando el método híbrido centralizado.
        Permite selección múltiple: si hay múltiples clips seleccionados en el track,
        procesa todos ellos. Si no, usa el clip del playhead."""
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("No se encontro una secuencia activa en Hiero.")
            return []
        
        # Usar módulo centralizado con selección múltiple habilitada
        # track_name=None para respetar TRACK_comp_EXR del módulo
        clips = get_clips_to_process(track_name=None, prioritize_multiple_selection=True)
        
        if not clips:
            debug_print("No se encontraron clips para procesar (ni en playhead ni seleccionados).")
            return []
        
        clips_info = []
        for clip in clips:
            try:
                file_path = clip.source().mediaSource().fileinfos()[0].filename()
                exr_name = os.path.basename(file_path)
                base_name, version_number = self.parse_exr_name(exr_name)

                # Usar funciones de naming utils para extraer información
                project_name = extract_project_name_from_path(file_path)
                if project_name:
                    debug_print(f"Project name (from path): {project_name}")
                else:
                    project_name = extract_project_name(base_name)
                    debug_print(f"Project name (from filename fallback): {project_name}")
                shot_code = extract_shot_code(base_name)

                clips_info.append(
                    {
                        "base_name": base_name,
                        "project_name": project_name,
                        "shot_code": shot_code,
                        "version_number": version_number,
                        "file_path": file_path,
                    }
                )
            except Exception as e:
                debug_print(f"Error procesando clip {clip.name()}: {e}")
                continue
        
        return clips_info

    def calculate_shot_base_path(self, file_path):
        """
        Calcula el path base del shot desde un archivo EXR.
        Similar a la lógica en Push.py: 4 niveles arriba del archivo.

        Args:
            file_path: Path completo del archivo EXR

        Returns:
            str: Path base del shot o None si no se puede calcular
        """
        try:
            normalized_path = os.path.normpath(file_path)
            path_parts = normalized_path.split(os.sep)

            if os.path.isabs(file_path) and len(path_parts) >= 5:
                # Calcular 4 niveles arriba: dirname(dirname(dirname(dirname(file_path))))
                shot_base_path = os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.dirname(file_path)))
                )
                debug_print(f"Shot base path calculado: {shot_base_path}")
                return shot_base_path
            else:
                debug_print("No se puede calcular shot_base_path (ruta inválida)")
                return None
        except Exception as e:
            debug_print(f"Error calculando shot_base_path para {file_path}: {e}")
            return None

    def process_selected_clips(self, shot_config, thumbnail_path=None):
        """Procesa los clips seleccionados en el timeline de Hiero."""
        clips_info = self.get_selected_clips_info()
        if not clips_info:
            return []

        results = []
        for clip_info in clips_info:
            shot, tasks, _ = self.sg_manager.find_shot_and_tasks(
                clip_info["project_name"],
                clip_info["shot_code"],
                shot_config,
                thumbnail_path,
                file_path=clip_info.get("file_path"),
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
    debug_output = Signal()  # Señal para imprimir logs al final


class ShotExistenceSignals(QObject):
    finished = Signal(list)  # Lista de dicts con clip_info y shot existente
    error = Signal(str)
    debug_output = Signal()


class CreateShotWorker(QRunnable):
    def __init__(self, status_window, shot_config, clips_info, thumbnail_path=None):
        super(CreateShotWorker, self).__init__()
        self.status_window = status_window
        self.shot_config = shot_config
        self.clips_info = clips_info  # Clips obtenidos en el hilo principal
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
                self.signals.debug_output.emit()
                self.signals.error.emit(
                    "No se pudieron obtener las credenciales de Flow desde SecureConfig."
                )
                return

            # Crear manager ShotGrid DENTRO del worker
            self.signals.step_update.emit("Conectando a ShotGrid...")
            sg_manager = ShotGridManager(sg_url, sg_login, sg_password)
            if not sg_manager.sg:
                self.signals.debug_output.emit()
                self.signals.error.emit(
                    "No se pudo inicializar la conexión a ShotGrid."
                )
                return

            # Usar clips_info que ya se obtuvieron en el hilo principal
            # NO obtenerlos de nuevo aquí porque las funciones del módulo centralizado
            # necesitan ejecutarse en el hilo principal (acceden al viewer de Hiero)
            clips_info = self.clips_info
            if not clips_info:
                self.signals.debug_output.emit()
                self.signals.error.emit(
                    "No se encontraron clips para procesar."
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
                shot, tasks, was_created = sg_manager.find_shot_and_tasks(
                    clip_info["project_name"],
                    clip_info["shot_code"],
                    self.shot_config,
                    self.thumbnail_path,
                    file_path=clip_info.get("file_path"),
                )

                if shot and was_created:
                    # Shot creado exitosamente
                    success_count += 1
                    debug_print(f"Shot creado exitosamente: {shot['code']}")
                elif shot and not was_created:
                    # Shot ya existía
                    debug_print(f"Shot ya existe: {clip_info['shot_code']}")
                    self.signals.step_update.emit(
                        f"Shot '{clip_info['shot_code']}' ya existía en ShotGrid. No se realizaron modificaciones."
                    )
                    # No incrementar success_count, será tratado como error
                else:
                    # Error al procesar shot
                    debug_print(f"Error procesando shot: {clip_info['shot_code']}")
                    self.signals.step_update.emit(
                        f"ERROR: No se pudo procesar el shot '{clip_info['shot_code']}'"
                    )

            # Emitir señal para imprimir logs al final
            self.signals.debug_output.emit()

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
            # Emitir señal para imprimir logs al final
            self.signals.debug_output.emit()
            self.signals.error.emit(f"Error: {str(e)}")


class ShotExistenceCheckWorker(QRunnable):
    def __init__(self, clips_info):
        super(ShotExistenceCheckWorker, self).__init__()
        self.clips_info = clips_info
        self.signals = ShotExistenceSignals()

    @Slot()
    def run(self):
        try:
            debug_print("=== Iniciando chequeo de existencia de shots ===")
            sg_url, sg_login, sg_password = get_flow_credentials_secure()
            if not all([sg_url, sg_login, sg_password]):
                self.signals.debug_output.emit()
                self.signals.error.emit(
                    "No se pudieron obtener las credenciales de Flow desde SecureConfig."
                )
                return

            sg_manager = ShotGridManager(sg_url, sg_login, sg_password)
            if not sg_manager.sg:
                self.signals.debug_output.emit()
                self.signals.error.emit(
                    "No se pudo inicializar la conexión a ShotGrid."
                )
                return

            existing = []
            for clip_info in self.clips_info:
                project_name = clip_info.get("project_name")
                shot_code = clip_info.get("shot_code")
                if not project_name or not shot_code:
                    continue
                exists, shot_data = sg_manager.shot_exists(project_name, shot_code)
                if exists:
                    debug_print(f"Shot '{shot_code}' ya existe en Flow.")
                    existing.append(
                        {
                            "clip_info": clip_info,
                            "shot": shot_data,
                        }
                    )

            debug_print(
                f"Chequeo de existencia finalizado. Existentes: {len(existing)}"
            )
            self.signals.debug_output.emit()
            self.signals.finished.emit(existing)
        except Exception as e:
            debug_print(f"Error en ShotExistenceCheckWorker: {e}")
            self.signals.debug_output.emit()
            self.signals.error.emit(str(e))


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
_config_dialog = None


def cleanup_thumbnail_file(thumbnail_path):
    """Limpia el archivo temporal del thumbnail."""
    if thumbnail_path and os.path.exists(thumbnail_path):
        try:
            os.remove(thumbnail_path)
            debug_print(f"✅ Archivo temporal eliminado: {thumbnail_path}")
        except Exception as e:
            debug_print(f"❌ Error eliminando archivo temporal: {e}")


def launch_modify_shot_script():
    """Carga el script de Modify Shot y ejecuta su flujo principal."""
    script_path = Path(__file__).with_name("LGA_NKS_Flow_ModifyShot.py")
    debug_print(f"Intentando lanzar Modify Shot desde: {script_path}")
    if not script_path.exists():
        debug_print("No se encontró el script Modify Shot", level="warning")
        show_warning(
            None,
            "Flow | Modify Shot",
            f"No se encontró el script Modify Shot en: {script_path}",
        )
        return
    try:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "LGA_NKS_Flow_ModifyShot_runtime", str(script_path)
        )
        if spec is None or spec.loader is None:
            raise ImportError("No se pudo cargar el módulo Modify Shot.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        debug_print("Modify Shot cargado correctamente, iniciando flujo")
        module.main()
    except Exception as e:
        debug_print(f"Error lanzando Modify Shot: {e}", level="error")
        show_warning(None, "Flow | Modify Shot", str(e))


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
        debug_print("No se encontraron clips seleccionados para crear shots", level="warning")
        show_warning(
            None, "Error", "No se encontraron clips seleccionados en Hiero."
        )
        return

    # Obtener nombre de la secuencia: primario desde la ruta del primer clip
    # (segmento despues de VFX-NOMBRE), fallback al nombre del timeline de Hiero.
    first_file_path = clips_info[0].get("file_path") if clips_info else None
    sequence_name = get_active_sequence_name(first_file_path)
    if not sequence_name:
        debug_print("No se pudo obtener el nombre de la secuencia activa", level="warning")
        show_warning(
            None,
            "Error",
            "No se pudo obtener el nombre de la secuencia activa en Hiero.",
        )
        return

    # Iniciar pre-chequeo de existencia
    start_shot_existence_check(clips_info, sequence_name)


def start_shot_existence_check(clips_info, sequence_name):
    """Abre ventana de estado y lanza worker para verificar existencia previa."""
    global _status_window

    debug_print(
        f"Iniciando pre-chequeo de existencia para {len(clips_info)} clip(s)"
    )
    _status_window = FlowStatusWindow("crear shot")
    _status_window.show()
    _status_window.show_step_message("Comprobando existencia de los shots en Flow...")

    worker = ShotExistenceCheckWorker(clips_info)

    worker.signals.finished.connect(
        lambda existing: handle_shot_existence_result(
            existing, clips_info, sequence_name
        )
    )
    worker.signals.error.connect(handle_shot_existence_error)
    worker.signals.debug_output.connect(lambda: print_debug_messages())

    QThreadPool.globalInstance().start(worker)


def handle_shot_existence_error(message):
    global _status_window
    debug_print(f"Error en chequeo de existencia: {message}", level="error")
    if _status_window:
        _status_window.show_error(message)
    else:
        show_warning(None, "Flow | Create Shot", message)


def handle_shot_existence_result(existing_shots, clips_info, sequence_name):
    global _status_window

    if existing_shots:
        shot_names = [item["clip_info"]["shot_code"] for item in existing_shots]
        formatted_list = "<br>".join(sorted(shot_names))
        debug_print(
            f"Chequeo de existencia: {len(existing_shots)} shot(s) ya existen"
        )

        if len(clips_info) == 1:
            if _status_window:
                _status_window.close()
                _status_window = None
            # Shot único ya existente: abrir Modify Shot directamente
            debug_print("Shot unico ya existe, lanzando Modify Shot")
            launch_modify_shot_script()
            return
        else:
            message = (
                "No se pueden crear los shots seleccionados porque ya existen:<br>"
                f"{formatted_list}"
            )
            if _status_window:
                _status_window.show_error(message)
            else:
                show_warning(
                    None,
                    "Shots ya existentes",
                    "Ya existen en Flow:\n" + "\n".join(sorted(shot_names)),
                )
            return

    # Ningún shot existe: cerrar ventana y continuar con el flujo normal
    debug_print("Ningun shot existe, continuando con Create Shot")
    if _status_window:
        _status_window.close()
        _status_window = None

    show_shot_config_dialog(clips_info, sequence_name)


def show_shot_config_dialog(clips_info, sequence_name):
    """Muestra el dialogo de configuración de forma no modal."""
    global _config_dialog

    debug_print("Mostrando dialogo de configuracion de shots")
    config_dialog = ShotConfigDialog(clips_info, sequence_name)
    _config_dialog = config_dialog
    config_dialog.finished.connect(
        lambda result, dialog=config_dialog: handle_shot_config_finished(
            result, dialog, clips_info
        )
    )
    config_dialog.show()


def handle_shot_config_finished(result, config_dialog, clips_info):
    """Continua el flujo de Create Shot cuando cierra el dialogo no modal."""
    global _config_dialog, _status_window

    if result != QDialog.Accepted:
        debug_print("Dialogo cancelado por el usuario", level="warning")
        config_dialog.cleanup_thumbnail()
        if _config_dialog is config_dialog:
            _config_dialog = None
        config_dialog.deleteLater()
        return

    shot_config = config_dialog.get_config()
    if not shot_config:
        debug_print("No se obtuvo configuracion del dialogo", level="warning")
        config_dialog.cleanup_thumbnail()
        if _config_dialog is config_dialog:
            _config_dialog = None
        config_dialog.deleteLater()
        return

    thumbnail_path = config_dialog.thumbnail_path
    if _config_dialog is config_dialog:
        _config_dialog = None
    config_dialog.deleteLater()

    _status_window = FlowStatusWindow("crear shot")
    _status_window.show()
    _status_window.show_processing_message()

    worker = CreateShotWorker(_status_window, shot_config, clips_info, thumbnail_path)

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
    worker.signals.debug_output.connect(lambda: print_debug_messages())

    QThreadPool.globalInstance().start(worker)
    debug_print("=== Worker iniciado en hilo separado ===")


def main():
    """Función principal para compatibilidad hacia atrás."""
    create_shots_from_selected_clips()


if __name__ == "__main__":
    main()
