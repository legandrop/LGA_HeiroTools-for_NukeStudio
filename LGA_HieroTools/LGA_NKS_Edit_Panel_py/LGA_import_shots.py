"""
____________________________________________________________________

  LGA_import_shots v1.27 | Lega

  Importa shots al proyecto de Nuke Studio.
  Analiza la carpeta _input del shot, detecta plates/editrefs/seqrefs
  y versiones en publish, y los coloca en el timeline en la posicion
  alfabeticamente correcta.

  v1.27: Bulk Import con seleccion multiple de carpetas, tabs editables por
         shot, preview grafico combinado con chips proporcionales y colores,
         y ejecucion en un unico undo.
  v1.26: El browser de seleccion de shot abre en la ultima carpeta elegida,
         guardada persistentemente en ImportShots.ini.
  v1.25: Fix tabs avanzados: no forzar ancho de QTabBar (evita header
         recortado al reabrir), checkbox vuelve a indicador nativo y
         separador del header se repinta al mostrar/ocultar tabs.
  v1.24: Fix visual del checkbox de tabs avanzados y recalculo de ancho
         del QTabBar al mostrar/ocultar Rename y Transcode Plates.
  v1.23: La ventana abre siempre en IMPORT. Agrega checkbox persistente
         "Shot Rename and Transcode tabs" para mostrar/ocultar Rename,
         Transcode Plates y Open Queue; default apagado.
  v1.22: Aumenta padding derecho interno en Prefix/Suffix y agrega
         padding derecho a Delimiter/Frame Number Digit.
  v1.21: Agrega padding derecho interno a la columna Prefix/Suffix.
  v1.20: Ajuste de anchos en Rename: Search & Replace pierde espacio,
         Prefix/Suffix gana ese ancho mas padding liberado del preset.
  v1.19: Rename igualado a MediaTools: labels sin numero de step,
         nueva columna Prefix/Suffix persistente y en presets, boton
         "Reset Values", pipeline de preview de 6 stages.
  v1.18: Fix apertura Import Shot: Rename ahora tolera items sin path valido
         usando fallbacks y no bloquea la creacion de la ventana.
  v1.17: Si existe el shot en el timeline, permite igualmente continuar
  v1.16: Transcode Plates: Forzar dimensiones pares (recomendado) ahora visible
         en el tab Transcode. Y arreglo de UI
  v1.15: Transcode Plates: DWAA usa compression fija 45 sin slider/spinbox.
         Upscale bloqueado siempre; se elimina el checkbox "Aplicar solo si
         la resolucion origen es mayor".
  v1.14: Tab cycle del tab Rename limitado a los 4 line edits de SR1/SR2
         (excluye swap, case sensitive, combos y botones via NoFocus).
         NoFocus tambien en los botones Save preset, Clear/defaults y
         Run Rename para que no muestren el rectangulo de foco amarillo
         tras navegar con teclado.
  v1.13: Reintroducido el match automatico entre los 4 steps y los presets
         guardados (ahora barato gracias a las mejoras de v1.12). El combo
         muestra el nombre del preset que coincide o "----" si no hay
         match. Removidos todos los logs de timing [RenameLag] y la
         infraestructura de debug en LGA_import_shots_rename.py.
  v1.12: Performance del preview de Rename: nueva funcion
         build_row_ops_for_ui (liviana, sin iterdir) usada por
         _mark_collisions; build_row_ops original sigue usandose en
         execute_ops para enumerar archivo por archivo. Debounce de
         100ms del refresh para que el typing en search/replace sea
         instantaneo. Flush del timer al apretar Run Rename.
  v1.11: Step 1 del rename ahora usa color verde (antes amarillo, chocaba
         con el step 4).
  v1.10: Combo de presets de rename simplificado: ya no se chequea el match
         contra los settings actuales en cada cambio. El combo muestra el
         nombre del preset al cargarlo y pasa a "----" apenas el usuario
         edita cualquier campo. Mas espaciado entre los widgets de col 3.
  v1.09: Dropdown de presets de rename con guardar/borrar (mismo patron
         que el combo de Destino del tab Transcode).
  v1.08: Seccion presets en tab rename
  v1.07: Navegación por tabs (Rename / Transcode Plates / Import).
         Tablas independientes, refresh inteligente con _needs_refresh.
         Import Now directo sin preview obligatorio.
  v1.06: Recalcula insert_frame en el momento exacto de presionar "Import Now"
         para evitar posicion incorrecta cuando multiples ventanas estan abiertas
         y otra termina de importar antes (el frame calculado al abrir la ventana
         quedaba stale tras el push de clips del import previo).
  v1.05: Cola global de transcode (TranscodeQueueManager) con UI Open Queue.
         Dropdown de track con boton "Crear track" integrado en la tabla.
         Boton "Go Back" bloqueado y renombrado a "Transcoding, wait..." durante
         transcode activo o en cola; restaurado al terminar.
  v1.04: Evita abrir dos ventanas de Import Shot para el mismo shot.
         Los avisos de duplicado usan dialogos propios sin iconos, con estilo de la tool.
  v1.03: Boton "Import and Create V000" en la pagina de Import Preview.
         Dialogo no bloqueante (show en lugar de exec_).
  v1.02: In/Out del timeline dentro del bloque de undo; el undo del
         import revierte tambien el cambio de In/Out. Elimina la
         seleccion de clips post-import (reemplazada por la vista).
  v1.01: Ajusta la vista del timeline al shot importado.

____________________________________________________________________
"""

import os
import re
import sys
import json
import importlib
import logging
import platform
import queue
import subprocess
import time
import traceback
from pathlib import Path
from logging.handlers import QueueHandler, QueueListener

import hiero.core
import hiero.ui

CURRENT_DIR = Path(__file__).resolve().parent
STARTUP_DIR = CURRENT_DIR.parent
SHARED_DIR = STARTUP_DIR / "LGA_NKS_Shared"
if str(SHARED_DIR) not in sys.path:
    sys.path.insert(0, str(SHARED_DIR))
if str(STARTUP_DIR) not in sys.path:
    sys.path.insert(0, str(STARTUP_DIR))

# ── herramientas externas (rutas relativas a SHARED_DIR) ──────────
# Windows: OIIO_Win/oiiotool.exe y FFmpeg_Win/bin/ffprobe.exe
# macOS/Linux: pendiente de implementar rutas para esas plataformas
_OS = platform.system()
if _OS == "Windows":
    _OIIOTOOL = SHARED_DIR / "OIIO_Win" / "oiiotool.exe"
    _FFPROBE   = SHARED_DIR / "FFmpeg_Win" / "bin" / "ffprobe.exe"
    _SUBPROCESS_EXTRA = {"creationflags": subprocess.CREATE_NO_WINDOW}
else:
    _OIIOTOOL = None
    _FFPROBE   = None
    _SUBPROCESS_EXTRA = {}

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore
from LGA_NKS_Flow_NamingUtils import clean_base_name, extract_shot_code


def _has_visible_import_shot_dialogs():
    app = QtWidgets.QApplication.instance()
    if not app:
        return False
    for widget in app.topLevelWidgets():
        try:
            if widget.objectName() == "LGA_ImportShotDialog" and widget.isVisible():
                return True
        except Exception:
            continue
    return False


def _has_visible_transcode_queue_window():
    app = QtWidgets.QApplication.instance()
    if not app:
        return False
    for widget in app.topLevelWidgets():
        try:
            if widget.objectName() == "LGA_TranscodeQueueWindow" and widget.isVisible():
                return True
        except Exception:
            continue
    return False


# During tool development, force the helper to reload on every panel execution.
_TRANSCODE_HELPER = "LGA_NKS_Edit_Panel_py.LGA_import_shots_transcode"
if _TRANSCODE_HELPER in sys.modules:
    del sys.modules[_TRANSCODE_HELPER]
_transcode_mod = importlib.import_module(_TRANSCODE_HELPER)
TranscodeWorker         = _transcode_mod.TranscodeWorker
check_existing_outputs  = _transcode_mod.check_existing_outputs
delete_existing_outputs = _transcode_mod.delete_existing_outputs
show_overwrite_warning  = _transcode_mod.show_overwrite_warning

_TRANSCODE_QUEUE_HELPER = "LGA_NKS_Edit_Panel_py.LGA_import_shots_transcode_queue"
_queue_helper_had_visible_dialogs = _has_visible_import_shot_dialogs()
_queue_helper_reloaded = False
if _TRANSCODE_QUEUE_HELPER in sys.modules and not _queue_helper_had_visible_dialogs:
    del sys.modules[_TRANSCODE_QUEUE_HELPER]
    _queue_helper_reloaded = True
transcode_queue_mod = importlib.import_module(_TRANSCODE_QUEUE_HELPER)
get_transcode_queue_manager = transcode_queue_mod.get_manager
try:
    transcode_queue_mod.debug_print(
        "queue helper import mode: %s (visible_dialogs=%s)" % (
            "reloaded" if _queue_helper_reloaded else "reused/imported",
            _queue_helper_had_visible_dialogs,
        )
    )
except Exception:
    pass

_SETTINGS_HELPER = "LGA_NKS_Edit_Panel_py.LGA_import_shots_settings"
if _SETTINGS_HELPER in sys.modules:
    del sys.modules[_SETTINGS_HELPER]
settings_mod = importlib.import_module(_SETTINGS_HELPER)

_TRANSCODE_QUEUE_UI_HELPER = "LGA_NKS_Edit_Panel_py.LGA_import_shots_transcode_queue_ui"
_queue_ui_had_visible_windows = (
    _has_visible_import_shot_dialogs() or _has_visible_transcode_queue_window()
)
_queue_ui_reloaded = False
if _TRANSCODE_QUEUE_UI_HELPER in sys.modules and not _queue_ui_had_visible_windows:
    del sys.modules[_TRANSCODE_QUEUE_UI_HELPER]
    _queue_ui_reloaded = True
transcode_queue_ui_mod = importlib.import_module(_TRANSCODE_QUEUE_UI_HELPER)
show_transcode_queue_window = transcode_queue_ui_mod.show_queue_window
try:
    transcode_queue_mod.debug_print(
        "queue UI helper import mode: %s (visible_windows=%s)" % (
            "reloaded" if _queue_ui_reloaded else "reused/imported",
            _queue_ui_had_visible_windows,
        )
    )
except Exception:
    pass

_RENAME_SETTINGS_HELPER = "LGA_NKS_Edit_Panel_py.LGA_import_shots_rename_settings"
if _RENAME_SETTINGS_HELPER in sys.modules:
    del sys.modules[_RENAME_SETTINGS_HELPER]
rename_settings_mod = importlib.import_module(_RENAME_SETTINGS_HELPER)

_RENAME_HELPER = "LGA_NKS_Edit_Panel_py.LGA_import_shots_rename"
if _RENAME_HELPER in sys.modules:
    del sys.modules[_RENAME_HELPER]
rename_mod = importlib.import_module(_RENAME_HELPER)

_PREVIEW_HELPER = "LGA_NKS_Edit_Panel_py.LGA_import_shots_preview"
if _PREVIEW_HELPER in sys.modules:
    del sys.modules[_PREVIEW_HELPER]
preview_mod = importlib.import_module(_PREVIEW_HELPER)
build_import_preview_data = preview_mod.build_import_preview_data
mix_colors                = preview_mod.mix_colors
classify_track_type       = preview_mod.classify_track_type

_TIMELINE_HELPER = "LGA_NKS_Edit_Panel_py.LGA_import_shots_timeline"
if _TIMELINE_HELPER in sys.modules:
    del sys.modules[_TIMELINE_HELPER]
timeline_mod = importlib.import_module(_TIMELINE_HELPER)

_BIN_HELPER = "LGA_NKS_Edit_Panel_py.LGA_import_shots_bin"
if _BIN_HELPER in sys.modules:
    del sys.modules[_BIN_HELPER]
bin_mod = importlib.import_module(_BIN_HELPER)

_BULK_HELPER = "LGA_NKS_Edit_Panel_py.LGA_import_shots_bulk"
if _BULK_HELPER in sys.modules:
    del sys.modules[_BULK_HELPER]
bulk_mod = importlib.import_module(_BULK_HELPER)

# ── tooltip helper ──────────────────────────────────────────────────────────
_TOOLTIP_HELPER = "LGA_NKS_Shared.LGA_tooltip_helper"
if _TOOLTIP_HELPER in sys.modules:
    del sys.modules[_TOOLTIP_HELPER]
try:
    _tooltip_mod        = importlib.import_module(_TOOLTIP_HELPER)
    set_clip_tooltip    = _tooltip_mod.set_clip_tooltip
    apply_tooltip_ss    = _tooltip_mod.apply_tooltip_stylesheet
except Exception as _te:
    def set_clip_tooltip(*a, **kw): pass
    def apply_tooltip_ss(*a, **kw): pass

# La inyección de debug_print se hace después de que setup_debug_logging() corra
# (ver final del bloque de logging más abajo → _inject_preview_logger())

# ── flags ──────────────────────────────────────────────────────────
# Si True, el transcode escribe a {seq_path}/test_transcode/ y los
# checkboxes "Mover originales" / "Borrar /Originals" quedan inertes.
Transcode_TEST_Mode = False
# Si True, Rename trabaja sobre copia en carpeta "renamned" y no toca originales.
Rename_Test_mode = False

# Debounce del refresh del preview de Rename (ms tras la última edición).
# Evita correr compute_preview en cada keystroke; el preview se actualiza
# cuando el user pausa de tipear.
_RENAME_REFRESH_DEBOUNCE_MS = 100

# ── logging ────────────────────────────────────────────────────────
DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True
script_start_time = None
debug_log_listener = None
debug_log_context = ""


class RelativeTimeFormatter(logging.Formatter):
    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created
        record.relative_time = "%.3fs" % (record.created - script_start_time)
        return super().format(record)


def setup_debug_logging(script_name="ImportShots"):
    global debug_log_listener
    log_path = STARTUP_DIR / "logs" / ("debugPy_%s.log" % script_name)
    log_path.parent.mkdir(exist_ok=True)
    try:
        if _has_visible_import_shot_dialogs() and log_path.exists():
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write("\n--- Nueva ventana: %s ---\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        else:
            log_path.write_text("Fecha: %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"), encoding="utf-8")
    except Exception:
        pass
    logger = logging.getLogger("%s_logger" % script_name.lower())
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    if logger.handlers:
        logger.handlers.clear()
    fh = logging.FileHandler(str(log_path), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(RelativeTimeFormatter("[%(relative_time)s] %(message)s"))
    lq = queue.Queue()
    qh = QueueHandler(lq)
    qh.setLevel(logging.DEBUG)
    logger.addHandler(qh)
    if debug_log_listener:
        try:
            debug_log_listener.stop()
        except Exception:
            pass
    debug_log_listener = QueueListener(lq, fh, respect_handler_level=True)
    debug_log_listener.daemon = True
    debug_log_listener.start()
    return logger


debug_logger = setup_debug_logging(script_name="ImportShots")


def set_debug_context(context):
    global debug_log_context
    debug_log_context = str(context or "").strip()


def debug_print(*message, level="info"):
    global script_start_time
    if not (DEBUG and DEBUG_LOG):
        return
    msg = " ".join(str(a) for a in message)
    if debug_log_context:
        msg = "[%s] %s" % (debug_log_context, msg)
    if script_start_time is None:
        script_start_time = time.time()
    getattr(debug_logger, level)(msg)
    if DEBUG and DEBUG_CONSOLE:
        print("[%.3fs] %s" % (time.time() - script_start_time, msg))


def cleanup_logging():
    global debug_log_listener
    if debug_log_listener:
        try:
            debug_log_listener.stop()
        except Exception:
            pass


def _inject_preview_logger():
    """Inyecta debug_print en los módulos auxiliares para que usen el mismo logger."""
    for mod in (preview_mod, timeline_mod, bin_mod, bulk_mod):
        try:
            mod.set_debug_print(debug_print)
        except Exception:
            pass


_inject_preview_logger()


import atexit
atexit.register(cleanup_logging)


# ── color del shotname en columnas Nombre de las tres tablas ─────
SHOTNAME_COLOR = "#B56AB5"  # ✅✅ cambiar aquí para ajustar el magenta en todas las tablas

# ── colores (igual que CreateV000) ────────────────────────────────
PATH_SHOT_COLOR = "#c56cf0"
PATH_SEP_COLOR  = "#bbbbbb"
PATH_LEVEL_COLORS = {
    0: "#ffff66", 1: "#28b5b5", 2: "#ff9a8a", 3: "#0088ff",
    4: "#ffd369", 5: "#28b5b5", 6: "#ff9a8a", 7: "#6bc9ff",
    8: "#ffd369", 9: "#28b5b5", 10: "#ff9a8a", 11: "#6bc9ff",
}

# ── colores de tabla de media (borde izquierdo por tipo de fila) ──
# task colors: igual que TASK_COLORS en CreateV000
_CLR_COMP    = "#3381e0"   # comp publish
_CLR_ROTO    = "#2abf7e"   # roto publish
_CLR_CLEANUP = "#27c8c3"   # cleanup publish
_CLR_DMP     = "#e08033"   # dmp publish
_CLR_PLATES  = "#42616d"   # plates input (EXR seq)
_CLR_REFS    = "#aa9e54"   # references (editref / seqref)

_TASK_ROW_COLORS = {
    "comp":    _CLR_COMP,
    "roto":    _CLR_ROTO,
    "cleanup": _CLR_CLEANUP,
    "dmp":     _CLR_DMP,
}
_TASK_ORDER = {"comp": 0, "roto": 1, "cleanup": 2, "dmp": 3}

# ── colores para anotaciones en tabla / dropdowns ─────────────────
# Derivados de la paleta PATH_LEVEL_COLORS pero desaturados ~40 %
# para no competir con el texto base #a7a7a7.
_CLR_AR            = "#a89060"   # aspect ratio          — dorado suave
_CLR_PAR           = "#c4787a"   # pixel aspect ratio    — rosa muted
_CLR_FRAMES        = "#b09040"   # cantidad de frames    — ámbar cálido
_CLR_COMP_ZIP      = "#a06060"   # compresión zip/piz    — rojo suave
_CLR_COMP_DWAA     = "#6a9960"   # compresión dwaa/dwab  — verde suave
_CLR_STATUS_PENDING  = "#5a9ab5" # estado Pendiente      — cian suave
_CLR_STATUS_DONE     = "#6a9960" # estado DONE           — verde suave
_CLR_STATUS_ERROR    = "#a06060" # estado Error          — rojo suave
_CLR_STATUS_UPSCALE  = "#a06060" # estado Upscale (bloq) — rojo suave

# ── colores de botones especiales ──────────────────────────────────
# Botón "Open Queue" — variables para que el usuario las cambies
# fácilmente por el color que quiera (ej. verde) manteniendo patrón.
_QUEUE_BTN_BG_NORMAL = "#3a7b91"  # violeta oscuro normal
_QUEUE_BTN_BG_HOVER  = "#4db4cb"  # violeta claro hover

# ── constantes de track ────────────────────────────────────────────
BURNIN_TRACK_NAMES = {"burnin", "burn in", "burn_in"}
_DWAA_COMPRESSION_LEVEL = 45

# Orden canónico de tracks de video, de abajo hacia arriba en el stack de Hiero
# (= de arriba hacia abajo tal como los devuelve reversed(seq.videoTracks())).
# Se usa para ordenar el dropdown y para determinar la posición de inserción
# cuando se crea un track nuevo desde el combo.
_IMPORT_TRACK_ORDER = [
    "aPlate", "bPlate", "cPlate", "dPlate", "ePlate",
    "fgPlate", "bgPlate", "EditRef", "EditRefClean",
    "_comp_", "_roto_", "_cleanup_", "_dmp_",
]

PLATE_KEYWORDS = [
    ("seqref",       None),           # None = solo bin
    ("editrefclean", "EditRefClean"),
    ("editref",      "EditRef"),
    ("fgplate",      "fgPlate"),
    ("bgplate",      "bgPlate"),
    ("aplate",       "aPlate"),
    ("bplate",       "bPlate"),
    ("cplate",       "cPlate"),
    ("dplate",       "dPlate"),
    ("eplate",       "ePlate"),
]

TASK_FOLDERS = {
    "comp":    ("Comp",    "_comp_"),
    "roto":    ("Roto",    "_roto_"),
    "cleanup": ("Cleanup", "_cleanup_"),
    "dmp":     ("DMP",     "_dmp_"),
}

EXR_EXTENSIONS  = {".exr"}
MOV_EXTENSIONS  = {".mov", ".mxf", ".mp4"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".dpx"}


# ══════════════════════════════════════════════════════════════════
#  Helpers de carpeta / media
# ══════════════════════════════════════════════════════════════════

def _detect_track_from_name(name):
    """Devuelve nombre de track o None (solo bin) segun keywords."""
    lower = name.lower()
    for kw, track in PLATE_KEYWORDS:
        if kw in lower:
            return track   # puede ser None (seqref)
    return None


def _is_plate_track(track_name):
    """True si el nombre de track corresponde a un plate."""
    if not track_name:
        return False
    return str(track_name).strip().lower().endswith("plate")


def _version_number(name):
    """Extrae numero de version de un nombre (v01, v001, v002). Retorna -1 si no hay."""
    m = re.search(r"[_\-]v(\d+)", name, re.IGNORECASE)
    return int(m.group(1)) if m else -1


def _folder_size_bytes(folder_path):
    """Suma el tamaño en bytes de los archivos directos de una carpeta (no recursivo)."""
    total = 0
    try:
        for f in os.listdir(folder_path):
            p = os.path.join(folder_path, f)
            if os.path.isfile(p):
                try:
                    total += os.path.getsize(p)
                except Exception:
                    pass
    except Exception:
        return 0
    return total


def _format_bytes(n):
    """Formatea bytes a string legible (KB/MB/GB)."""
    if not n:
        return "—"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024.0:
            return ("%.0f %s" % (n, unit)) if unit in ("B", "KB") else ("%.2f %s" % (n, unit))
        n /= 1024.0
    return "%.2f PB" % n


def _scan_exr_sequence(folder_path):
    """Escanea una carpeta y retorna (first_frame, last_frame, count, first_file_path)."""
    try:
        files = sorted(
            f for f in os.listdir(folder_path)
            if os.path.splitext(f)[1].lower() in EXR_EXTENSIONS
        )
    except Exception:
        return None, None, 0, None
    if not files:
        return None, None, 0, None

    def _frame_num(fname):
        m = re.search(r"(\d+)\.exr$", fname, re.IGNORECASE)
        return int(m.group(1)) if m else 0

    frames = [_frame_num(f) for f in files]
    frames = [f for f in frames if f > 0]
    if not frames:
        return None, None, len(files), os.path.join(folder_path, files[0])
    return min(frames), max(frames), len(files), os.path.join(folder_path, files[0])


def _read_exr_metadata(exr_path):
    """Resolucion, compresion, bit depth, channels y PAR de un frame EXR via oiiotool --info -v."""
    w, h, fps, comp, bitdepth, channels, par = None, None, None, None, None, None, None
    if not (_OIIOTOOL and _OIIOTOOL.exists()):
        debug_print("_read_exr_metadata: oiiotool no disponible", level="warning")
        return w, h, fps, comp, bitdepth, channels, par
    try:
        r = subprocess.run(
            [str(_OIIOTOOL), "--info", "-v", str(exr_path)],
            capture_output=True, text=True, timeout=10,
            **_SUBPROCESS_EXTRA,
        )
        out = r.stdout + r.stderr
        debug_print("oiiotool output para %s:\n%s" % (Path(exr_path).name, out[:600]))
        # "path/to/file.exr:  1920 x 1080, 3 channel, half openexr"
        m = re.search(r"(\d+)\s*x\s*(\d+),\s*(\d+)\s*channel,\s*(\w+)", out)
        if m:
            w, h = int(m.group(1)), int(m.group(2))
            channels = int(m.group(3))
            bitdepth = m.group(4)
        else:
            m = re.search(r"(\d+)\s*x\s*(\d+)", out)
            if m:
                w, h = int(m.group(1)), int(m.group(2))
            m = re.search(r"(\d+)\s*channel", out)
            if m:
                channels = int(m.group(1))
            m = re.search(r"channel,\s*(\w+)", out)
            if m:
                bitdepth = m.group(1)
        # 'framesPerSecond: 24/1'  o  'framesPerSecond: 24'
        m = re.search(r'[Ff]rames[Pp]er[Ss]econd[:\s]+"?(\d+)/(\d+)"?', out)
        if m:
            num, den = int(m.group(1)), int(m.group(2))
            if den:
                fps = float(num) / float(den)
        if fps is None:
            m = re.search(r'[Ff]rames[Pp]er[Ss]econd[:\s]+"?([\d.]+)"?', out)
            if m:
                try:
                    fps = float(m.group(1))
                except Exception:
                    pass
        # '    compression: "zip"'  o  '    compression: dwaa'
        m = re.search(r'compression[:\s]+"?([A-Za-z0-9_]+)"?', out, re.IGNORECASE)
        if m:
            comp = m.group(1)
        # '    PixelAspectRatio: 1'  o  '    PixelAspectRatio: 2'
        m = re.search(r'[Pp]ixel[Aa]spect[Rr]atio[:\s]+"?([\d.]+)"?', out)
        if m:
            try:
                par = float(m.group(1))
            except Exception:
                pass
        debug_print("EXR meta: %sx%s fps=%s comp=%s bd=%s ch=%s par=%s" % (
            w, h, fps, comp, bitdepth, channels, par))
    except Exception as e:
        debug_print("_read_exr_metadata error: %s" % e, level="error")
    return w, h, fps, comp, bitdepth, channels, par


def _read_mov_metadata(mov_path):
    """Resolucion, fps, codec y nb_frames de un MOV/MXF via ffprobe (JSON)."""
    w, h, fps, codec, nb_frames = None, None, None, None, None
    if not (_FFPROBE and _FFPROBE.exists()):
        debug_print("_read_mov_metadata: ffprobe no disponible", level="warning")
        return w, h, fps, codec, nb_frames
    try:
        r = subprocess.run(
            [str(_FFPROBE), "-v", "quiet", "-print_format", "json",
             "-show_streams", str(mov_path)],
            capture_output=True, text=True, timeout=15,
            **_SUBPROCESS_EXTRA,
        )
        data = json.loads(r.stdout)
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                w     = stream.get("width")
                h     = stream.get("height")
                codec = stream.get("codec_name")
                rfr   = stream.get("r_frame_rate", "")
                if "/" in rfr:
                    num, den = rfr.split("/")
                    try:
                        fps = float(num) / float(den)
                    except Exception:
                        pass
                # nb_frames: campo directo o calculado desde duracion * fps
                raw_nb = stream.get("nb_frames")
                if raw_nb:
                    try:
                        nb_frames = int(raw_nb)
                    except Exception:
                        pass
                if nb_frames is None and fps and stream.get("duration"):
                    try:
                        nb_frames = int(round(float(stream["duration"]) * fps))
                    except Exception:
                        pass
                break
        debug_print("MOV meta %s: %sx%s fps=%s codec=%s frames=%s" % (
            Path(mov_path).name, w, h, fps, codec, nb_frames))
    except Exception as e:
        debug_print("_read_mov_metadata error: %s" % e, level="error")
    # codec se almacena en el campo "compression" del item
    return w, h, fps, codec, nb_frames


def _scan_input_folder(shot_root):
    """
    Escanea {shot_root}/_input/ y retorna lista de dicts con info de cada item.
    Cada dict: {name, path, kind, track, first_frame, last_frame, frame_count,
                first_file, width, height, fps, compression, is_latest, version_num}
    kind: 'exr_seq' | 'mov' | 'other'
    """
    input_dir = Path(shot_root) / "_input"
    if not input_dir.exists():
        return []

    items = []

    # 1. Subcarpetas ➜ secuencias EXR
    try:
        subdirs = sorted(d for d in input_dir.iterdir() if d.is_dir())
    except Exception:
        subdirs = []

    # Agrupar por nombre base (sin version) para detectar la mas alta
    plate_groups = {}  # base_key ➜ [subdir, ...]
    for sd in subdirs:
        first_f, last_f, count, first_file = _scan_exr_sequence(str(sd))
        if count == 0:
            continue
        track = _detect_track_from_name(sd.name)
        # Agrupar: quitamos la parte _vNN al final para la clave de grupo
        base_key = re.sub(r"[_\-]v\d+$", "", sd.name, flags=re.IGNORECASE).lower()
        plate_groups.setdefault(base_key, []).append({
            "name": sd.name,
            "path": str(sd),
            "kind": "exr_seq",
            "track": track,
            "first_frame": first_f,
            "last_frame": last_f,
            "frame_count": count,
            "first_file": first_file,
            "version_num": _version_number(sd.name),
        })

    for base_key, group in plate_groups.items():
        group.sort(key=lambda x: x["version_num"])
        max_ver = max(x["version_num"] for x in group)
        has_multiple_versions = len(group) > 1
        for entry in group:
            entry["is_latest"] = (entry["version_num"] == max_ver)
            entry["has_multiple_versions"] = has_multiple_versions
            # Leer metadata solo del primer archivo
            w, h, fps, comp, bd, ch, par = (None,) * 7
            if entry["first_file"]:
                w, h, fps, comp, bd, ch, par = _read_exr_metadata(entry["first_file"])
            entry.update({"width": w, "height": h, "fps": fps, "compression": comp,
                          "bitdepth": bd, "channels": ch, "pixel_aspect_ratio": par})
            items.append(entry)

    # 2. Archivos sueltos en _input/
    try:
        loose = sorted(f for f in input_dir.iterdir() if f.is_file())
    except Exception:
        loose = []

    # Agrupar MOVs por "clave de track" para detectar versiones, igual que EXR seqs.
    # Regla de agrupación:
    #   - Track nombrado (EditRef, EditRefClean, aPlate, …) → clave = "track:<track>"
    #     Todas las versiones de un EditRef van al mismo grupo.
    #   - Track None (seqref) o desconocido ("?") → clave = "name:<base_sin_version>"
    #     Se agrupan por nombre base; archivos sin relación no se mezclan.
    mov_groups = {}  # clave → [entry_dict, ...]

    for f in loose:
        ext = f.suffix.lower()
        if ext in MOV_EXTENSIONS:
            # MOVs sueltos: solo detectamos seqref y editref.
            # Nunca heredan track de plates aunque compartan nombre base con un EXR.
            stem_lower = f.stem.lower()
            if "seqref" in stem_lower:
                track = None          # bin only
            elif "editrefclean" in stem_lower:
                track = "EditRefClean"
            elif "editref" in stem_lower:
                track = "EditRef"
            elif "plate" in stem_lower:
                # Si el nombre contiene "plate", se distribuye como plate.
                track = _detect_track_from_name(f.stem) or "aPlate"
            else:
                track = "?"           # desconocido, usuario decide
            mw, mh, mfps, mcodec, mnb = _read_mov_metadata(str(f))
            entry = {
                "name": f.stem,
                "path": str(f),
                "kind": "mov",
                "ext": f.suffix.lstrip(".").upper(),  # "MOV", "MXF", "MP4"
                "track": track,
                "first_frame": 1 if mnb else None,
                "last_frame": mnb,
                "frame_count": mnb,
                "first_file": str(f),
                "width": mw, "height": mh, "fps": mfps, "compression": mcodec,
                "bitdepth": None, "channels": None,
                "is_latest": True,           # se actualiza en el paso de versioning
                "has_multiple_versions": False,
                "version_num": _version_number(f.stem),
            }
            if track and track != "?":
                group_key = "track:" + track
            else:
                base = re.sub(r"[_\-]v\d+$", "", f.stem, flags=re.IGNORECASE).lower()
                group_key = "name:" + base
            mov_groups.setdefault(group_key, []).append(entry)

        elif ext in IMAGE_EXTENSIONS:
            items.append({
                "name": f.name,
                "path": str(f),
                "kind": "other",
                "track": None,
                "first_frame": None, "last_frame": None, "frame_count": None,
                "first_file": str(f),
                "width": None, "height": None, "fps": None, "compression": None,
                "bitdepth": None, "channels": None,
                "is_latest": True,
                "version_num": -1,
            })

    # Aplicar versioning a cada grupo de MOVs (mismo patrón que EXR seqs)
    for group_key, group in mov_groups.items():
        group.sort(key=lambda x: x["version_num"])
        max_ver = max(x["version_num"] for x in group)
        has_multiple = len(group) > 1
        for entry in group:
            # Si ningún archivo tiene número de versión (max_ver == -1), todos son "latest"
            entry["is_latest"] = (entry["version_num"] == max_ver or max_ver == -1)
            entry["has_multiple_versions"] = has_multiple
        items.extend(group)

    # Ordenar: plates por track-name luego version, movs, otros
    def _sort_key(x):
        order = {"exr_seq": 0, "mov": 1, "other": 2}
        return (order.get(x["kind"], 9), x.get("track") or "zzz", x["version_num"])

    items.sort(key=_sort_key)
    return items


def _scan_publish_folders(shot_root):
    """
    Escanea las carpetas de task en shot_root y retorna una lista de dicts,
    una entrada por cada version encontrada (no solo la mas alta).
    Cada dict incluye is_latest=True solo para la version mas alta de cada task.
    Orden: por task (TASK_FOLDERS insertion order), luego version descendente.
    """
    results = []
    shot_path = Path(shot_root)
    for task, (folder_name, track) in TASK_FOLDERS.items():
        task_dir = shot_path / folder_name
        if not task_dir.exists():
            continue
        publish_dir = task_dir / "4_publish"
        if not publish_dir.exists():
            continue

        # Buscar TODAS las subcarpetas de version
        try:
            version_dirs = [
                d for d in publish_dir.iterdir()
                if d.is_dir() and re.search(r"_v\d+$", d.name, re.IGNORECASE)
            ]
        except Exception:
            version_dirs = []

        if not version_dirs:
            continue

        # Ordenar descendente (mayor version primero)
        version_dirs.sort(key=lambda d: _version_number(d.name), reverse=True)
        max_ver = _version_number(version_dirs[0].name)

        for vd in version_dirs:
            first_f, last_f, count, first_file = _scan_exr_sequence(str(vd))
            w, h, fps, comp, bd, ch, par = (None,) * 7
            if first_file:
                w, h, fps, comp, bd, ch, par = _read_exr_metadata(first_file)
            ver_num = _version_number(vd.name)
            results.append({
                "task": task, "folder_name": folder_name, "track": track,
                "publish_exists": True, "has_versions": True,
                "version_dir": str(vd), "version_name": vd.name,
                "version_num": ver_num,
                "is_latest": (ver_num == max_ver),
                "first_file": first_file,
                "first_frame": first_f, "last_frame": last_f, "frame_count": count,
                "width": w, "height": h, "fps": fps, "compression": comp,
                "bitdepth": bd, "channels": ch, "pixel_aspect_ratio": par,
                "path": str(vd),
                # Campos normalizados para compatibilidad con import_item_to_bin:
                "kind": "exr_seq",   # publish items son siempre EXR sequences
                "name": vd.name,     # nombre de la versión (ej. TEST_013_020_comp_v02)
            })

    return results


# ══════════════════════════════════════════════════════════════════
#  Helpers de timeline
# ══════════════════════════════════════════════════════════════════

def _is_burnin_track(track_name):
    return track_name.lower().strip() in BURNIN_TRACK_NAMES


def _get_shot_name_from_folder(folder_path):
    return Path(folder_path).name


def _collect_timeline_shots(seq):
    """
    Escanea todos los tracks de video no-BurnIn para construir lista de shots
    existentes.

    Agrupa por item.name() y toma el rango completo del shot:
      timeline_in  = min(timelineIn)  entre todos los clips de ese shot
      timeline_out = max(timelineOut) entre todos los clips de ese shot

    Esto evita que un plate corto/offseteado en un track secundario defina
    por error el final del shot cuando existe un comp, plate o editref mas largo
    en otro track.

    Retorna list de {shot_name, timeline_in, timeline_out, track_name, track_names}.
    """
    shots_by_name = {}
    for track in seq.videoTracks():
        tname = track.name()
        if _is_burnin_track(tname):
            continue
        for item in track.items():
            if isinstance(item, hiero.core.EffectTrackItem):
                continue
            try:
                name = item.name()
                tl_in = int(item.timelineIn())
                tl_out = int(item.timelineOut())
            except Exception:
                continue
            if not name:
                continue

            shot_data = shots_by_name.get(name)
            if shot_data is None:
                shots_by_name[name] = {
                    "shot_name": name,
                    "timeline_in": tl_in,
                    "timeline_out": tl_out,
                    "track_name": tname,
                    "track_names": [tname],
                }
                continue

            if tl_in < shot_data["timeline_in"]:
                shot_data["timeline_in"] = tl_in
            if tl_out > shot_data["timeline_out"]:
                shot_data["timeline_out"] = tl_out
                # track_name conserva el track que define el final master.
                shot_data["track_name"] = tname
            if tname not in shot_data["track_names"]:
                shot_data["track_names"].append(tname)

    shots = list(shots_by_name.values())
    shots.sort(key=lambda x: x["timeline_in"])
    return shots


def _shot_exists_in_timeline(seq, shot_name, shot_root):
    """
    Doble criterio: nombre del TrackItem Y path de la media contiene el shot root.
    """
    shot_name_lower = shot_name.lower()
    shot_root_norm = shot_root.replace("\\", "/").rstrip("/").lower()

    for track in seq.videoTracks():
        for item in track.items():
            if isinstance(item, hiero.core.EffectTrackItem):
                continue
            try:
                if item.name().lower() == shot_name_lower:
                    return True
                # Chequear path de media
                try:
                    fi = item.source().mediaSource().fileinfos()
                    if fi:
                        media_path = fi[0].filename().replace("\\", "/").lower()
                        if shot_root_norm in media_path:
                            return True
                except Exception:
                    pass
            except Exception:
                continue
    return False


def _find_insert_frame(seq, shot_name, duration):
    """
    Determina el frame donde insertar el shot nuevo basandose en orden alfabetico.
    Retorna (insert_frame, frames_to_push, prev_shot_name, next_shot_name).
    prev_shot_name y next_shot_name son los nombres exactos de los shots vecinos
    en el timeline (o None si no existen), para que el preview los busque por nombre.
    """
    shots = _collect_timeline_shots(seq)
    if not shots:
        return 0, 0, None, None

    # Ordenar los shots existentes alfabeticamente por nombre
    shots_alpha = sorted(shots, key=lambda x: x["shot_name"].lower())

    # Encontrar donde encaja el nuevo shot
    insert_before = None
    insert_before_idx = None
    for i, s in enumerate(shots_alpha):
        if shot_name.lower() < s["shot_name"].lower():
            insert_before = s
            insert_before_idx = i
            break

    if insert_before is None:
        # El nuevo shot va al final
        last = max(shots, key=lambda x: x["timeline_out"])
        insert_frame = last["timeline_out"] + 1
        prev_shot_name = shots_alpha[-1]["shot_name"] if shots_alpha else None
        return insert_frame, 0, prev_shot_name, None

    # Insertar antes de insert_before: usamos su timeline_in actual
    insert_frame = insert_before["timeline_in"]
    next_shot_name = insert_before["shot_name"]
    prev_shot_name = shots_alpha[insert_before_idx - 1]["shot_name"] if insert_before_idx > 0 else None
    return insert_frame, duration, prev_shot_name, next_shot_name


# ══════════════════════════════════════════════════════════════════
#  Helpers UI
# ══════════════════════════════════════════════════════════════════

_DIALOG_STYLE = """
QDialog {
    background-color: #2B2B2B;
    border: 1px solid #555555;
}
QLabel {
    color: #a7a7a7;
}
"""

_TABLE_STYLE = """
QTableWidget {
    background-color: #272727;
    border: 1px solid #333333;
    color: #a7a7a7;
    gridline-color: #333333;
    outline: none;
}
QHeaderView::section {
    background-color: #2B2B2B;
    color: #999999;
    padding: 4px 8px;
    border: 0px;
    border-bottom: 1px solid #444444;
    font-weight: bold;
}
QTableWidget::item { padding-left: 6px; padding-right: 6px; }
QTableWidget::item:selected { background-color: #353535; color: #cccccc; }
"""

_BTN_CANCEL = """
QPushButton {
    background-color: #555555;
    border: 1px solid #666666;
    color: #CCCCCC;
    padding: 7px 18px;
    border-radius: 3px;
}
QPushButton:hover { background-color: #666666; }
"""

_BTN_PRIMARY = """
QPushButton {
    background-color: #443a91;
    border: none;
    color: #B2B2B2;
    padding: 7px 18px;
    border-radius: 5px;
    font-weight: bold;
}
QPushButton:hover { background-color: #774dcb; color: #ffffff; }
QPushButton:disabled { background-color: #2a2540; color: #666666; border: none; }
"""

_BTN_SECONDARY = """
QPushButton {
    background-color: #3a3a3a;
    border: 1px solid #555555;
    color: #CCCCCC;
    padding: 7px 18px;
    border-radius: 3px;
}
QPushButton:hover { background-color: #4a4a4a; }
QPushButton:disabled { background-color: #2a2a2a; color: #666666; border-color: #3a3a3a; }
"""

_BTN_SMALL = """
QPushButton {
    background-color: #2e2e2e;
    border: 1px solid #444444;
    color: #999999;
    padding: 3px 10px;
    border-radius: 3px;
    font-size: 11px;
}
QPushButton:hover { background-color: #383838; color: #cccccc; }
QPushButton:disabled { background-color: #272727; color: #555555; }
"""

_BTN_QUEUE_OPEN = """
QPushButton {{
    background-color: {normal_bg};
    border: none;
    color: #B2B2B2;
    padding: 7px 18px;
    border-radius: 5px;
    font-weight: bold;
}}
QPushButton:hover {{ background-color: {hover_bg}; color: #ffffff; }}
QPushButton:disabled {{ background-color: #2a2540; color: #666666; border: none; }}
""".format(normal_bg=_QUEUE_BTN_BG_NORMAL, hover_bg=_QUEUE_BTN_BG_HOVER)

_CHECKBOX_STYLE = """
QCheckBox {
    color: #a7a7a7;
    spacing: 8px;
    padding: 0px 4px;
}
QCheckBox:hover { color: #cccccc; }
"""

# ✅✅ Espacio (px) entre el separador horizontal y la fila de botones de acción.
# Se aplica en todas las páginas (media y convert) para mantener equilibrio visual.
_BTN_ROW_TOP_SPACING = 15


def _show_tool_message(parent, title, message):
    dialog = QtWidgets.QDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setModal(True)
    dialog.setMinimumWidth(440)
    dialog.setStyleSheet(
        _DIALOG_STYLE
        + """
        QLabel#ToolMessageTitle {
            color: #CCCCCC;
            font-size: 15px;
            font-weight: bold;
        }
        QLabel#ToolMessageBody {
            color: #A7A7A7;
            font-size: 12px;
            line-height: 1.35;
        }
        """
    )

    layout = QtWidgets.QVBoxLayout(dialog)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(12)

    title_lbl = QtWidgets.QLabel(title)
    title_lbl.setObjectName("ToolMessageTitle")
    layout.addWidget(title_lbl)

    body_lbl = QtWidgets.QLabel(message)
    body_lbl.setObjectName("ToolMessageBody")
    body_lbl.setWordWrap(True)
    layout.addWidget(body_lbl)

    btn_row = QtWidgets.QHBoxLayout()
    btn_row.addStretch()
    ok_btn = QtWidgets.QPushButton("OK")
    ok_btn.setMinimumWidth(90)
    ok_btn.setStyleSheet(_BTN_PRIMARY)
    ok_btn.clicked.connect(dialog.accept)
    btn_row.addWidget(ok_btn)
    layout.addLayout(btn_row)

    return dialog.exec_()


def _show_shot_exists_confirm(shot_name):
    """Muestra aviso de shot duplicado con opcion de continuar. Retorna True si el usuario elige continuar."""
    dialog = QtWidgets.QDialog(None)
    dialog.setWindowTitle("Import Shot")
    dialog.setModal(True)
    dialog.setMinimumWidth(440)
    dialog.setStyleSheet(
        _DIALOG_STYLE
        + """
        QLabel#ToolMessageTitle {
            color: #CCCCCC;
            font-size: 15px;
            font-weight: bold;
        }
        QLabel#ToolMessageBody {
            color: #A7A7A7;
            font-size: 12px;
            line-height: 1.35;
        }
        """
    )

    layout = QtWidgets.QVBoxLayout(dialog)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(12)

    title_lbl = QtWidgets.QLabel("Import Shot")
    title_lbl.setObjectName("ToolMessageTitle")
    layout.addWidget(title_lbl)

    body_lbl = QtWidgets.QLabel(
        "El shot '%s' ya existe en el timeline.\n\n"
        "Podés continuar de todas formas si querés importarlo como duplicado." % shot_name
    )
    body_lbl.setObjectName("ToolMessageBody")
    body_lbl.setWordWrap(True)
    layout.addWidget(body_lbl)

    btn_row = QtWidgets.QHBoxLayout()
    btn_row.addStretch()

    cancel_btn = QtWidgets.QPushButton("Cancel")
    cancel_btn.setMinimumWidth(90)
    cancel_btn.setStyleSheet(_BTN_CANCEL)
    cancel_btn.clicked.connect(dialog.reject)
    btn_row.addWidget(cancel_btn)

    btn_row.addSpacing(8)

    continue_btn = QtWidgets.QPushButton("Continue anyway")
    continue_btn.setMinimumWidth(120)
    continue_btn.setStyleSheet(_BTN_PRIMARY)
    continue_btn.clicked.connect(dialog.accept)
    btn_row.addWidget(continue_btn)

    layout.addLayout(btn_row)

    return dialog.exec_() == QtWidgets.QDialog.Accepted


def _section_label(text):
    lbl = QtWidgets.QLabel(text)
    lbl.setStyleSheet("color: #CCCCCC; font-weight: bold; padding-top: 4px;")
    return lbl


def _rn_escape(text):
    """Minimal HTML escape para nombres de archivo."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _cell_html_label(html, bg="#272727"):
    """QLabel con HTML coloreado para usar como cellWidget en tablas.
    Transparente a eventos de mouse para que el cellClicked de la tabla
    siga funcionando correctamente."""
    lbl = QtWidgets.QLabel()
    lbl.setTextFormat(QtCore.Qt.RichText)
    lbl.setText(html)
    lbl.setStyleSheet("background:%s; padding:2px 6px;" % bg)
    lbl.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
    return lbl


def _comp_color(comp, greyed=False):
    """Devuelve el color HTML para una compresión EXR dada."""
    cl = (comp or "").lower()
    if cl in ("dwaa", "dwab"):
        return "#4a6e4a" if greyed else _CLR_COMP_DWAA
    if cl in ("zip", "zips", "piz"):
        return "#6e4a4a" if greyed else _CLR_COMP_ZIP
    return "#666666" if greyed else "#888888"


def _separator(orientation="h"):
    sep = QtWidgets.QFrame()
    sep.setFrameShape(
        QtWidgets.QFrame.HLine if orientation == "h" else QtWidgets.QFrame.VLine
    )
    sep.setFrameShadow(QtWidgets.QFrame.Sunken)
    sep.setStyleSheet("color: #444444; margin: 0px;")
    return sep


class GradientTextLabel(QtWidgets.QLabel):
    """QLabel que pinta su texto con un gradiente lineal limitado al ancho del texto."""

    def __init__(self, text, colors, bg_color="#313131", parent=None):
        super().__init__(text, parent)
        self._colors = colors
        self._bg_color = bg_color

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.TextAntialiasing)
        painter.setFont(self.font())
        # Fondo
        painter.fillRect(self.rect(), QtGui.QColor(self._bg_color))

        # Calcular el bounding rect real del texto
        fm = QtGui.QFontMetrics(self.font())
        text = self.text()
        text_w = fm.horizontalAdvance(text) if hasattr(fm, "horizontalAdvance") else fm.width(text)
        text_h = fm.height()
        margins = self.contentsMargins()
        # Posicion del texto: alineado a la izquierda con padding-left
        x0 = margins.left()
        y0 = (self.height() - text_h) // 2
        text_rect = QtCore.QRect(x0, y0, text_w, text_h)

        # Gradiente horizontal limitado al ancho del texto
        gradient = QtGui.QLinearGradient(x0, 0, x0 + text_w, 0)
        n = len(self._colors)
        for i, c in enumerate(self._colors):
            pos = i / (n - 1) if n > 1 else 0
            gradient.setColorAt(pos, QtGui.QColor(c))
        pen = QtGui.QPen(QtGui.QBrush(gradient), 1)
        painter.setPen(pen)
        painter.drawText(text_rect, QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, text)
        painter.end()


# ══════════════════════════════════════════════════════════════════
#  ComboBox custom — pinta la flecha con QPainter
# ══════════════════════════════════════════════════════════════════

class _ArrowComboBox(QtWidgets.QComboBox):
    """QComboBox que pinta su propia flecha ▼ via paintEvent.
    Requiere que el stylesheet oculte la flecha nativa con
    `QComboBox::down-arrow { image: none; width:0; height:0; }`."""

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        rect = self.rect()
        cx = rect.right() - 10
        cy = rect.center().y() + 1
        path = QtGui.QPainterPath()
        path.moveTo(cx - 4, cy - 2)
        path.lineTo(cx + 4, cy - 2)
        path.lineTo(cx, cy + 3)
        path.closeSubpath()
        p.fillPath(path, QtGui.QColor("#999999"))
        p.end()


# ══════════════════════════════════════════════════════════════════
#  SpinBox custom — dibuja las flechas ▲▼ con QPainter (igual patrón que
#  _ArrowComboBox). La stylesheet oculta las flechas nativas; los botones
#  nativos del SO siguen siendo clickeables (solo se reemplaza la imagen).
# ══════════════════════════════════════════════════════════════════

class _ArrowSpinBox(QtWidgets.QSpinBox):
    """QSpinBox que dibuja sus propias flechas ▲▼ via paintEvent.
    Solución análoga a _ArrowComboBox: los botones nativos funcionan,
    solo se pinta encima. Selección de texto: fondo gris claro / texto oscuro."""

    _STYLE = (
        "QSpinBox { background:#272727; border:1px solid #444; color:#a7a7a7;"
        " padding:2px 20px 2px 4px;"
        " selection-background-color:#505060; selection-color:#d0d0d0; }"
        "QSpinBox::up-button, QSpinBox::down-button"
        " { background:transparent; border:none; width:18px; }"
        "QSpinBox::up-arrow, QSpinBox::down-arrow"
        " { image:none; width:0; height:0; }"
    )

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        r = self.rect()
        cx = r.right() - 9
        # Flecha ▲ (cuarto superior derecho)
        cy_up = r.height() // 4
        path_up = QtGui.QPainterPath()
        path_up.moveTo(cx - 4, cy_up + 2)
        path_up.lineTo(cx + 4, cy_up + 2)
        path_up.lineTo(cx,     cy_up - 2)
        path_up.closeSubpath()
        p.fillPath(path_up, QtGui.QColor("#999999"))
        # Flecha ▼ (cuarto inferior derecho)
        cy_dn = r.height() * 3 // 4
        path_dn = QtGui.QPainterPath()
        path_dn.moveTo(cx - 4, cy_dn - 2)
        path_dn.lineTo(cx + 4, cy_dn - 2)
        path_dn.lineTo(cx,     cy_dn + 2)
        path_dn.closeSubpath()
        p.fillPath(path_dn, QtGui.QColor("#999999"))
        p.end()


# ══════════════════════════════════════════════════════════════════
#  Stylesheet base para _ArrowComboBox
#  Uso: combo.setStyleSheet(_COMBO_ARROW_STYLE) + combo.setView(QListView())
# ══════════════════════════════════════════════════════════════════

_COMBO_BASE = (
    "QComboBox { background-color:#272727; border:1px solid #444; "
    "color:#a7a7a7; padding:3px 6px; }"
    "QComboBox::drop-down { border:0px; width:18px; }"
    "QComboBox::down-arrow { image:none; width:0px; height:0px; }"
    "QComboBox QAbstractItemView { background-color:#2B2B2B; color:#a7a7a7; "
    "selection-background-color:#272727; selection-color:#a7a7a7; outline:0; }"
)


def _ar_str(w, h):
    """Devuelve el aspect ratio como '16:9', '2.39:1', etc."""
    if not w or not h:
        return ""
    try:
        from math import gcd
        g = gcd(int(w), int(h))
        rw, rh = int(w) // g, int(h) // g
        if rw <= 32 and rh <= 32:
            return "%d:%d" % (rw, rh)
        return "%.2f:1" % (w / float(h))
    except Exception:
        return ""


# ══════════════════════════════════════════════════════════════════
#  Delegate para combo de resolución (AR en dorado)
# ══════════════════════════════════════════════════════════════════

# Ancho del área de click del ícono de papelera en el dropdown de presets
_PRESET_TRASH_W = 26


class _ResPresetListView(QtWidgets.QListView):
    """QListView usado como popup del combo de resoluciones.

    El QComboBoxPrivateContainer instala un eventFilter en el listview mismo, lo que
    intercepta los MouseButtonRelease antes de que lleguen a nuestro override de
    mouseReleaseEvent. Por eso instalamos nuestro filtro en el viewport(), que NO
    está filtrado por el container.
    """

    def __init__(self, on_delete_cb, parent=None):
        super(_ResPresetListView, self).__init__(parent)
        self._on_delete = on_delete_cb
        self._hovered_trash_row = -1
        self.setMouseTracking(True)

    def showEvent(self, event):
        """Instalamos el filtro en el viewport cuando el popup se muestra."""
        super(_ResPresetListView, self).showEvent(event)
        vp = self.viewport()
        if vp:
            vp.setMouseTracking(True)
            vp.installEventFilter(self)

    def hideEvent(self, event):
        """Limpiamos el hover al cerrar el popup."""
        super(_ResPresetListView, self).hideEvent(event)
        self._hovered_trash_row = -1

    @staticmethod
    def _is_deletable(text):
        t = text.strip()
        return (not t.startswith("Original")
                and t != "Custom..."
                and not t.startswith("Timeline"))

    def _in_trash_zone(self, row, pos):
        m = self.model()
        if not m:
            return False
        vrect = self.visualRect(m.index(row, 0))
        return pos.x() >= vrect.right() - _PRESET_TRASH_W

    def _update_hover(self, pos):
        m = self.model()
        if not m:
            return
        idx = self.indexAt(pos)
        row = idx.row() if idx.isValid() else -1
        new_hover = -1
        if row >= 0:
            text = m.data(m.index(row, 0)) or ""
            if self._is_deletable(text) and self._in_trash_zone(row, pos):
                new_hover = row
        if new_hover != self._hovered_trash_row:
            old = self._hovered_trash_row
            self._hovered_trash_row = new_hover
            vp = self.viewport()
            for r in (old, new_hover):
                if r >= 0:
                    vp.update(self.visualRect(m.index(r, 0)))

    def eventFilter(self, obj, event):
        vp = self.viewport()
        if obj is vp:
            etype = event.type()
            if etype == QtCore.QEvent.MouseMove:
                self._update_hover(event.pos())
            elif etype == QtCore.QEvent.Leave:
                old = self._hovered_trash_row
                self._hovered_trash_row = -1
                m = self.model()
                if m and old >= 0:
                    self.viewport().update(self.visualRect(m.index(old, 0)))
            elif etype == QtCore.QEvent.MouseButtonRelease:
                m = self.model()
                if m:
                    idx = self.indexAt(event.pos())
                    row = idx.row() if idx.isValid() else -1
                    if row >= 0:
                        text = m.data(m.index(row, 0)) or ""
                        if self._is_deletable(text) and self._in_trash_zone(row, event.pos()):
                            self._on_delete(row)
                            return True  # consumir ➜ no seleccionar ni cerrar popup
        return super(_ResPresetListView, self).eventFilter(obj, event)


class _ResPresetDelegate(QtWidgets.QStyledItemDelegate):
    """Pinta items del combo de resoluciones con [AR] en dorado y trash icon a la derecha."""

    _CLR_TEXT = "#a7a7a7"
    _CLR_AR   = "#a89060"

    def __init__(self, list_view, pix_trash, pix_hover, parent=None):
        super(_ResPresetDelegate, self).__init__(parent)
        self._view      = list_view
        self._pix_trash = pix_trash
        self._pix_hover = pix_hover

    @staticmethod
    def _is_deletable(text):
        t = text.strip()
        return (not t.startswith("Original")
                and t != "Custom..."
                and not t.startswith("Timeline"))

    def paint(self, painter, option, index):
        painter.save()
        bg = (QtGui.QColor("#353535")
              if (option.state & QtWidgets.QStyle.State_Selected)
              else QtGui.QColor("#2B2B2B"))
        painter.fillRect(option.rect, bg)

        text = index.data() or ""
        deletable = self._is_deletable(text)

        # Área de texto: si deletable reservar espacio para el trash
        text_rect = option.rect.adjusted(6, 0, -(_PRESET_TRASH_W + 4) if deletable else -4, 0)

        segments = re.split(r'(\[[^\]]*\])', text)
        fm = painter.fontMetrics()
        x  = text_rect.x()

        for seg in segments:
            if not seg:
                continue
            is_ar = seg.startswith("[")
            painter.setPen(QtGui.QColor(self._CLR_AR if is_ar else self._CLR_TEXT))
            sw = fm.horizontalAdvance(seg)
            painter.drawText(x, text_rect.top(), sw, text_rect.height(),
                             QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, seg)
            x += sw

        if deletable:
            hovered = (self._view._hovered_trash_row == index.row())
            pix = (self._pix_hover if (hovered and self._pix_hover and not self._pix_hover.isNull())
                   else self._pix_trash)
            if pix and not pix.isNull():
                icon_sz = 14
                tx = option.rect.right() - _PRESET_TRASH_W + (_PRESET_TRASH_W - icon_sz) // 2
                ty = option.rect.top() + (option.rect.height() - icon_sz) // 2
                scaled = pix.scaled(icon_sz, icon_sz,
                                    QtCore.Qt.KeepAspectRatio,
                                    QtCore.Qt.SmoothTransformation)
                painter.drawPixmap(tx, ty, scaled)

        painter.restore()

    def sizeHint(self, option, index):
        sh = super(_ResPresetDelegate, self).sizeHint(option, index)
        return sh.expandedTo(QtCore.QSize(0, 24))


# ══════════════════════════════════════════════════════════════════
#  Variantes para el combo de presets del tab Rename.
#  Misma UX (trash icon, hover, click en zona de papelera) que el de
#  resoluciones; sólo cambia la regla de "qué item es deletable":
#  todos lo son excepto los items virtuales "----" y "(sin presets)".
# ══════════════════════════════════════════════════════════════════

_RENAME_PRESET_PLACEHOLDER_NOMATCH = "----"
_RENAME_PRESET_PLACEHOLDER_EMPTY   = "(sin presets)"


def _rename_preset_is_deletable(text):
    t = (text or "").strip()
    if not t:
        return False
    if t == _RENAME_PRESET_PLACEHOLDER_NOMATCH:
        return False
    if t == _RENAME_PRESET_PLACEHOLDER_EMPTY:
        return False
    return True


class _RenamePresetListView(_ResPresetListView):
    @staticmethod
    def _is_deletable(text):
        return _rename_preset_is_deletable(text)


class _RenamePresetDelegate(_ResPresetDelegate):
    @staticmethod
    def _is_deletable(text):
        return _rename_preset_is_deletable(text)


# ══════════════════════════════════════════════════════════════════
#  List view y delegate para combo de track
#  La última opción "＋ Crear track <name>" actúa como botón:
#  al hacer click se llama al callback y el evento se consume
#  (el combo no cambia su valor actual).  Mismo patrón que
#  _ResPresetListView / trash icon del combo de resolución.
# ══════════════════════════════════════════════════════════════════

_TRACK_CREATE_PREFIX = "+ Crear track "


class _TrackComboListView(QtWidgets.QListView):
    """QListView para el combo de asignación de tracks.

    La opción 'Crear track <name>' se comporta como botón: al hacer click
    se llama on_create_cb(text) y el evento se consume sin cerrar el popup
    ni cambiar el valor del combo.

    El QComboBoxPrivateContainer instala un eventFilter en el listview mismo,
    interceptando MouseButtonRelease antes de que llegue a nuestro override.
    Por eso instalamos nuestro filtro en el viewport(), que NO está filtrado
    por el container.  (Mismo patrón que _ResPresetListView.)
    """

    def __init__(self, on_create_cb, parent=None):
        super(_TrackComboListView, self).__init__(parent)
        self._on_create = on_create_cb
        self._hovered_create_row = -1
        self.setMouseTracking(True)

    def showEvent(self, event):
        super(_TrackComboListView, self).showEvent(event)
        vp = self.viewport()
        if vp:
            vp.setMouseTracking(True)
            vp.installEventFilter(self)

    def hideEvent(self, event):
        super(_TrackComboListView, self).hideEvent(event)
        self._hovered_create_row = -1

    @staticmethod
    def _is_create_option(text):
        return text.startswith(_TRACK_CREATE_PREFIX)

    def _update_hover(self, pos):
        m = self.model()
        if not m:
            return
        idx = self.indexAt(pos)
        row = idx.row() if idx.isValid() else -1
        new_hover = -1
        if row >= 0:
            text = m.data(m.index(row, 0)) or ""
            if self._is_create_option(text):
                new_hover = row
        if new_hover != self._hovered_create_row:
            old = self._hovered_create_row
            self._hovered_create_row = new_hover
            vp = self.viewport()
            for r in (old, new_hover):
                if r >= 0:
                    vp.update(self.visualRect(m.index(r, 0)))

    def eventFilter(self, obj, event):
        vp = self.viewport()
        if obj is vp:
            etype = event.type()
            if etype == QtCore.QEvent.MouseMove:
                self._update_hover(event.pos())
            elif etype == QtCore.QEvent.Leave:
                old = self._hovered_create_row
                self._hovered_create_row = -1
                m = self.model()
                if m and old >= 0:
                    self.viewport().update(self.visualRect(m.index(old, 0)))
            elif etype == QtCore.QEvent.MouseButtonRelease:
                m = self.model()
                if m:
                    idx = self.indexAt(event.pos())
                    row = idx.row() if idx.isValid() else -1
                    if row >= 0:
                        text = m.data(m.index(row, 0)) or ""
                        if self._is_create_option(text):
                            self._on_create(text)
                            return True  # consumir → no seleccionar ni cerrar popup
        return super(_TrackComboListView, self).eventFilter(obj, event)


class _TrackComboDelegate(QtWidgets.QStyledItemDelegate):
    """Pinta las opciones del combo de track.

    La opción '+ Crear track <name>' se pinta con fondo verde oscuro y texto
    verde (estilo botón), diferenciándose de las opciones de track normales.
    En hover el fondo se aclara levemente.
    """

    _CLR_TEXT        = "#a7a7a7"
    _CLR_CREATE_TEXT = "#7aba7a"   # verde suave — acción positiva
    _CLR_CREATE_BG   = "#1a2a1a"   # fondo verde muy oscuro
    _CLR_CREATE_HOV  = "#253525"   # hover: verde oscuro un poco más claro

    def __init__(self, list_view, parent=None):
        super(_TrackComboDelegate, self).__init__(parent)
        self._view = list_view

    @staticmethod
    def _is_create_option(text):
        return text.startswith(_TRACK_CREATE_PREFIX)

    def paint(self, painter, option, index):
        painter.save()
        text = index.data() or ""
        is_create = self._is_create_option(text)

        if is_create:
            hovered = (self._view._hovered_create_row == index.row())
            bg = QtGui.QColor(self._CLR_CREATE_HOV if hovered
                              else self._CLR_CREATE_BG)
        else:
            bg = (QtGui.QColor("#353535")
                  if (option.state & QtWidgets.QStyle.State_Selected)
                  else QtGui.QColor("#2B2B2B"))
        painter.fillRect(option.rect, bg)

        text_rect = option.rect.adjusted(6, 0, -4, 0)
        clr = self._CLR_CREATE_TEXT if is_create else self._CLR_TEXT
        painter.setPen(QtGui.QColor(clr))
        painter.drawText(text_rect,
                         QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft, text)
        painter.restore()

    def sizeHint(self, option, index):
        sh = super(_TrackComboDelegate, self).sizeHint(option, index)
        return sh.expandedTo(QtCore.QSize(0, 24))


# ══════════════════════════════════════════════════════════════════
#  Dialogo principal
# ══════════════════════════════════════════════════════════════════

class _HeaderSeparator(QtWidgets.QWidget):
    """Línea de 1px debajo del tab header.

    Pinta la línea en `LINE_COLOR` excepto en el rect horizontal del tab
    activo, donde pinta `GAP_COLOR` (= bg del tab activo = bg del body) para
    que el tab seleccionado parezca "abrir" el separador y conectarse
    visualmente con la página debajo.
    """

    LINE_COLOR = QtGui.QColor("#4a4a4a")
    GAP_COLOR  = QtGui.QColor("#2b2b2b")  # = QTabBar::tab:selected background

    def __init__(self, tab_bar, parent=None):
        super(_HeaderSeparator, self).__init__(parent)
        self._tab_bar = tab_bar
        self.setFixedHeight(1)
        tab_bar.currentChanged.connect(self.update)
        tab_bar.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self._tab_bar:
            etype = event.type()
            if etype in (
                QtCore.QEvent.Resize,
                QtCore.QEvent.Move,
                QtCore.QEvent.LayoutRequest,
                QtCore.QEvent.Show,
                QtCore.QEvent.Hide,
                QtCore.QEvent.StyleChange,
            ):
                self.update()
        return super(_HeaderSeparator, self).eventFilter(obj, event)

    def paintEvent(self, event):
        p = QtGui.QPainter(self)
        p.fillRect(self.rect(), self.LINE_COLOR)
        idx = self._tab_bar.currentIndex()
        if idx < 0:
            return
        rect = self._tab_bar.tabRect(idx)
        if rect.isEmpty():
            return
        # tabRect viene en coords del QTabBar; lo traemos a coords del separador
        top_left_global = self._tab_bar.mapToGlobal(rect.topLeft())
        x = self.mapFromGlobal(top_left_global).x()
        p.fillRect(x, 0, rect.width(), self.height(), self.GAP_COLOR)


class _ImportShotTabBar(QtWidgets.QTabBar):
    """QTabBar con tabSizeHint ampliado.

    Qt calcula el ancho de cada tab usando QFontMetrics sobre el texto crudo,
    sin contemplar `letter-spacing` del QSS. Como aquí el CSS aplica
    letter-spacing 1px, el texto pintado termina siendo más ancho que la
    celda y se cropea en los extremos. Compensamos sumando un margen extra.
    """
    EXTRA_WIDTH = 24  # px adicionales por tab — cubre letter-spacing + aire

    def tabSizeHint(self, index):
        s = super(_ImportShotTabBar, self).tabSizeHint(index)
        s.setWidth(s.width() + self.EXTRA_WIDTH)
        return s


class ImportShotDialog(QtWidgets.QDialog):

    TAB_RENAME    = 0
    TAB_TRANSCODE = 1
    TAB_IMPORT    = 2
    IMPORT_MAIN    = 0
    IMPORT_PREVIEW = 1

    _TAB_H_PAD_EXTRA = 14  # px adicionales a cada lado de todos los tabs — ajustar a mano

    _TAB_STYLE = (
        """
        QWidget#LGA_ImportShotHeader {
            background: #232323;
        }
        QTabBar {
            background: #232323;
            qproperty-drawBase: 0;
        }
        QTabBar::tab {
            background: #232323;
            color: #777777;
            padding: 16px %dpx;
            /* border 1px transparent en todos los tabs para que el geometry
               sea idéntico entre seleccionado y no seleccionado. El
               seleccionado sólo overridea los colores de top/left/right. */
            border: 1px solid transparent;
            font-weight: bold;
            font-size: 12px;
            letter-spacing: 1px;
        }
        QTabBar::tab:selected {
            background: #2b2b2b;
            color: #774dcb;
            border-top-color: #4a4a4a;
            border-left-color: #4a4a4a;
            border-right-color: #4a4a4a;
            /* border-bottom queda transparent → no reaparece la línea
               que el separador "abre" debajo del tab activo. */
        }
        QTabBar::tab:hover:!selected { color: #AAAAAA; background: #272727; }
        QTabBar::tab:disabled { color: #444444; background: #232323; }
    """
        % _TAB_H_PAD_EXTRA
    )

    def __init__(self, shot_root, shot_name, seq, insert_frame, frames_to_push,
                 prev_shot_name, next_shot_name,
                 input_items, publish_items, parent=None):
        super(ImportShotDialog, self).__init__(parent)
        self.shot_root       = shot_root
        self.shot_name       = shot_name
        self.seq             = seq
        self.insert_frame    = insert_frame
        self.frames_to_push  = frames_to_push
        self.prev_shot_name  = prev_shot_name
        self.next_shot_name  = next_shot_name
        self.input_items     = input_items
        self.publish_items   = publish_items

        self._track_overrides = {}
        self._create_v000_tasks = set()
        self._needs_refresh = set()

        # Custom resolution + Preserve AR
        self._custom_ar_updating = False   # evita recursión al actualizar spinboxes

        # FPS del timeline (para tooltips de duración en segundos)
        try:
            self._fps = float(self.seq.framerate().toFloat())
        except Exception:
            self._fps = 24.0

        # Resolución del timeline (para el preset "Timeline" hardcoded)
        try:
            fmt = self.seq.format()
            self._tl_w, self._tl_h = int(fmt.width()), int(fmt.height())
        except Exception:
            self._tl_w, self._tl_h = None, None

        # Cargar settings persistentes ANTES de construir la UI.
        # _res_presets_raw = solo los presets del INI (sin Original/Timeline/Custom...).
        # _res_presets     = lista completa con hardcoded head+tail añadidos.
        self._imp_settings    = settings_mod.load_all_settings()
        self._res_presets_raw = settings_mod.load_res_presets()
        self._res_presets     = self._build_full_presets()
        self._window_id       = "%s-%x" % (
            re.sub(r"[^A-Za-z0-9_.-]+", "_", shot_name or "shot"),
            id(self),
        )
        self._transcode_active = False
        self._transcode_manager = get_transcode_queue_manager()

        self.setWindowTitle("Import Shot — %s" % shot_name)
        self.setObjectName("LGA_ImportShotDialog")
        self.setProperty("shot_name", shot_name)
        self.setProperty("shot_root", shot_root)
        self.setProperty("window_id", self._window_id)
        self.setModal(False)
        flags = self.windowFlags()
        flags &= ~QtCore.Qt.WindowContextHelpButtonHint
        flags |= QtCore.Qt.WindowMinimizeButtonHint
        self.setWindowFlags(flags)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.finished.connect(self._on_dialog_finished)
        self.destroyed.connect(
            lambda *_args, window_id=self._window_id, shot=self.shot_name:
                self._log_dialog_destroyed(window_id, shot)
        )
        self.setMinimumWidth(1300)
        self.setMinimumHeight(650)
        self.setStyleSheet(_DIALOG_STYLE + self._TAB_STYLE)

        self._root_layout = QtWidgets.QVBoxLayout(self)
        # Margins=0 en el root: el fondo dark del header y la línea separadora
        # llegan hasta los bordes izq/der/sup de la ventana. El padding lateral
        # de 9px se aplica adentro del header (en `_hdr_lay`) y en el wrapper
        # del stack, de forma que tabs y shotname queden en su posición visual
        # original sin franjas grises a los costados.
        self._root_layout.setContentsMargins(0, 0, 0, 0)
        self._root_layout.setSpacing(0)

        self._status_labels = []
        self._open_queue_buttons = []
        self._advanced_tabs_checkboxes = []

        # ── Tab Header ────────────────────────────────────────────
        # Wrapper QWidget que contiene tabs + stretch + shotname como
        # hermanos del mismo QHBoxLayout. Reemplaza el viejo
        # QTabWidget.setCornerWidget(), que no respetaba SizePolicy y
        # dejaba el shotname más bajo que los tabs.
        self._header = QtWidgets.QWidget()
        self._header.setObjectName("LGA_ImportShotHeader")
        self._header.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        _hdr_lay = QtWidgets.QHBoxLayout(self._header)
        # left=0 (prueba): el primer tab queda flush con el borde izquierdo.
        # right=9 mantiene el shotname en su posición visual original.
        _hdr_lay.setContentsMargins(0, 0, 9, 0)
        _hdr_lay.setSpacing(0)

        self._tab_bar = _ImportShotTabBar()
        self._tab_bar.setExpanding(False)
        self._tab_bar.setDrawBase(False)
        self._tab_bar.addTab("RENAME")
        self._tab_bar.addTab("TRANSCODE PLATES")
        self._tab_bar.addTab("IMPORT")
        _hdr_lay.addWidget(self._tab_bar, 0, QtCore.Qt.AlignBottom)
        _hdr_lay.addStretch(1)

        _shot_lbl = QtWidgets.QLabel(
            "<span style='color:#6AB5CA;'>%s</span>"
            " <span style='color:#888888;'>/</span> "
            "<span style='color:#B56AB5;'>%s</span>"
            % (self._seq_name(), self.shot_name)
        )
        _shot_lbl.setTextFormat(QtCore.Qt.RichText)
        _shot_lbl.setStyleSheet(
            "QLabel { background: transparent; font-size:14px; font-weight:bold; "
            "padding:0 12px 0 8px; }"
        )
        _hdr_lay.addWidget(_shot_lbl, 0, QtCore.Qt.AlignVCenter)

        self._root_layout.addWidget(self._header)

        # Línea separadora con "hueco" bajo el tab activo para conectar
        # visualmente el tab seleccionado con la página debajo.
        self._header_sep = _HeaderSeparator(self._tab_bar)
        self._root_layout.addWidget(self._header_sep)

        # ── Stack de páginas ─────────────────────────────────────
        # Mantenemos el nombre `_tab_widget` como atributo de
        # compatibilidad: ahora apunta al QStackedWidget.
        # Se envuelve en un container con margins (9, 0, 9, 9) para
        # que el contenido de las páginas conserve el padding original
        # respecto a los bordes del diálogo, mientras el header dark
        # y la línea separadora siguen llegando edge-to-edge.
        self._tab_widget = QtWidgets.QStackedWidget()
        _body = QtWidgets.QWidget()
        _body_lay = QtWidgets.QVBoxLayout(_body)
        _body_lay.setContentsMargins(9, 10, 9, 9)
        _body_lay.setSpacing(0)
        _body_lay.addWidget(self._tab_widget)
        self._root_layout.addWidget(_body, 1)

        self._page_rename  = self._build_page_rename()
        self._page_convert = self._build_page_convert()
        self._page_import  = self._build_tab_import()

        self._tab_widget.addWidget(self._page_rename)
        self._tab_widget.addWidget(self._page_convert)
        self._tab_widget.addWidget(self._page_import)

        self._tab_bar.currentChanged.connect(self._tab_widget.setCurrentIndex)
        self._tab_bar.currentChanged.connect(self._on_tab_changed)

        self._connect_transcode_manager()

        debug_print("ImportShotDialog init: applying advanced tab visibility")
        self._apply_advanced_tabs_visibility(save=False)
        debug_print("ImportShotDialog init: set current tab Import")
        self._tab_bar.setCurrentIndex(self.TAB_IMPORT)
        self._tab_widget.setCurrentIndex(self.TAB_IMPORT)
        debug_print("ImportShotDialog init complete window_id=%s" % self._window_id)

    # ── header ───────────────────────────────────────────────────

    def _connect_transcode_manager(self):
        """Conecta esta ventana al manager global de transcode."""
        mgr = self._transcode_manager
        mgr.queue_changed.connect(self._on_global_transcode_queue_changed)
        mgr.log_message.connect(self._on_manager_transcode_log)
        mgr.sequence_started.connect(self._on_manager_sequence_started)
        mgr.sequence_done.connect(self._on_manager_sequence_done)
        mgr.job_cancelled.connect(self._on_manager_job_cancelled)
        mgr.batch_done.connect(self._on_manager_batch_done)
        mgr.fatal_error.connect(self._on_manager_transcode_error)
        try:
            mgr.note_window_opened(self._window_id, self.shot_name)
        except Exception as exc:
            debug_print("TranscodeQueueManager open log error: %s" % exc, level="warning")
        debug_print("TranscodeQueueManager conectado window_id=%s" % self._window_id)
        debug_print("TranscodeQueueManager snapshot request window_id=%s" % self._window_id)
        self._update_global_status_label(mgr.snapshot())
        debug_print("TranscodeQueueManager snapshot applied window_id=%s" % self._window_id)

    def _make_footer_pair(self):
        """Crea (footer buttons, status widget) para integrar en la fila inferior."""
        buttons = QtWidgets.QWidget()
        buttons.setStyleSheet("QWidget { background: transparent; }")
        buttons_row = QtWidgets.QHBoxLayout(buttons)
        buttons_row.setContentsMargins(0, 0, 0, 0)
        buttons_row.setSpacing(6)

        open_queue_btn = QtWidgets.QPushButton("Open Queue")
        open_queue_btn.setStyleSheet(_BTN_QUEUE_OPEN)
        open_queue_btn.clicked.connect(self._show_transcode_queue_window)
        self._open_queue_buttons.append(open_queue_btn)

        buttons_row.addWidget(open_queue_btn)
        advanced_chk = QtWidgets.QCheckBox("Shot Rename and Transcode tabs")
        advanced_chk.setStyleSheet(_CHECKBOX_STYLE)
        advanced_chk.setFocusPolicy(QtCore.Qt.NoFocus)
        advanced_chk.setChecked(self._advanced_tabs_enabled())
        advanced_chk.stateChanged.connect(self._on_advanced_tabs_toggled)
        self._advanced_tabs_checkboxes.append(advanced_chk)
        buttons_row.addWidget(advanced_chk)

        box = QtWidgets.QWidget()
        box.setStyleSheet("QWidget { background: transparent; }")
        row = QtWidgets.QHBoxLayout(box)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)

        pre_lbl = QtWidgets.QLabel("")
        pre_lbl.setStyleSheet("color:#a7a7a7; padding:0px;")

        shot_btn = QtWidgets.QPushButton("")
        shot_btn.setFlat(True)
        shot_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        shot_btn.setStyleSheet(
            "QPushButton { background: transparent; border:0px; padding:0px;"
            " margin:0px; color:%s; text-align:left; }"
            "QPushButton:hover { color:#e2a2e2; text-decoration: none; }"
            "QPushButton:pressed { color:#9f529f; }" % SHOTNAME_COLOR
        )
        shot_btn.clicked.connect(
            lambda _checked=False, b=shot_btn: self._focus_import_shot_window(
                str(b.property("window_id") or ""),
                str(b.property("shot_name") or b.text() or ""),
            )
        )

        post_lbl = QtWidgets.QLabel("")
        post_lbl.setStyleSheet("color:#a7a7a7; padding:0px;")

        row.addWidget(pre_lbl)
        row.addWidget(shot_btn)
        row.addWidget(post_lbl)
        row.addStretch(1)

        shot_btn.setVisible(False)
        self._status_labels.append({
            "box": box,
            "pre": pre_lbl,
            "shot": shot_btn,
            "post": post_lbl,
        })
        self._refresh_footer_controls()
        return buttons, box

    def _advanced_tabs_enabled(self):
        ui = self._imp_settings.get("ui", {})
        return str(ui.get("advanced_tabs", "false")).lower() == "true"

    def _on_advanced_tabs_toggled(self, state):
        enabled = (state == QtCore.Qt.Checked)
        self._imp_settings.setdefault("ui", {})["advanced_tabs"] = (
            "true" if enabled else "false"
        )
        self._apply_advanced_tabs_visibility(save=True)

    def _apply_advanced_tabs_visibility(self, save=False):
        enabled = self._advanced_tabs_enabled()
        for chk in getattr(self, "_advanced_tabs_checkboxes", []):
            chk.blockSignals(True)
            chk.setChecked(enabled)
            chk.blockSignals(False)

        for idx in (self.TAB_RENAME, self.TAB_TRANSCODE):
            try:
                self._tab_bar.setTabVisible(idx, enabled)
            except AttributeError:
                self._tab_bar.setTabEnabled(idx, enabled)
            else:
                self._tab_bar.setTabEnabled(idx, enabled)

        if not enabled and self._tab_bar.currentIndex() != self.TAB_IMPORT:
            self._tab_bar.setCurrentIndex(self.TAB_IMPORT)
            self._tab_widget.setCurrentIndex(self.TAB_IMPORT)

        self._refresh_header_layout()
        self._refresh_footer_controls()
        if save:
            self._save_ui_settings()

    def _refresh_header_layout(self):
        # Si una versión previa forzó min/max width del tabbar, lo reseteamos.
        # Dejamos que Qt calcule el ancho natural para evitar header recortado.
        self._tab_bar.setMinimumWidth(0)
        self._tab_bar.setMaximumWidth(16777215)
        self._tab_bar.updateGeometry()
        self._header.layout().invalidate()
        self._header.updateGeometry()
        self._header.update()
        if hasattr(self, "_header_sep"):
            self._header_sep.update()
        QtCore.QTimer.singleShot(0, self._refresh_header_separator)

    def _refresh_header_separator(self):
        if hasattr(self, "_header_sep"):
            self._header_sep.update()

    def _refresh_footer_controls(self):
        enabled = self._advanced_tabs_enabled()
        for btn in getattr(self, "_open_queue_buttons", []):
            btn.setVisible(enabled)

    def _save_ui_settings(self):
        settings_mod.save_all_settings({
            "ui": {
                "advanced_tabs": self._imp_settings.get("ui", {}).get(
                    "advanced_tabs", "false"
                )
            }
        })

    def _show_transcode_queue_window(self):
        try:
            show_transcode_queue_window(
                self._transcode_manager,
                parent=None,
                focus_window_callback=self._focus_import_shot_window,
            )
        except Exception as exc:
            debug_print("show transcode queue window error: %s" % exc, level="warning")

    def _focus_import_shot_window(self, window_id, shot_name):
        app = QtWidgets.QApplication.instance()
        if not app:
            return
        target = None
        shot_key = (shot_name or "").strip().lower()
        for widget in app.topLevelWidgets():
            try:
                if widget.objectName() != "LGA_ImportShotDialog" or not widget.isVisible():
                    continue
                if window_id and str(widget.property("window_id") or "") == window_id:
                    target = widget
                    break
                if shot_key and str(widget.property("shot_name") or "").strip().lower() == shot_key:
                    target = widget
                    break
            except Exception:
                continue
        if not target:
            debug_print(
                "focus import shot window failed window_id=%s shot=%s" % (window_id, shot_name),
                level="warning",
            )
            return
        try:
            target.show()
            if hasattr(target, "showNormal") and target.isMinimized():
                target.showNormal()
            target.raise_()
            target.activateWindow()
            debug_print("focus import shot window window_id=%s shot=%s" % (window_id, shot_name))
        except Exception as exc:
            debug_print("focus import shot window error: %s" % exc, level="warning")

    def showEvent(self, event):
        super(ImportShotDialog, self).showEvent(event)
        QtCore.QTimer.singleShot(0, self._refresh_header_layout)

    def closeEvent(self, event):
        debug_print(
            "ImportShotDialog closeEvent window_id=%s shot=%s"
            % (getattr(self, "_window_id", ""), self.shot_name)
        )
        try:
            self._transcode_manager.note_window_closed(self._window_id, self.shot_name)
        except Exception as exc:
            debug_print("TranscodeQueueManager close log error: %s" % exc, level="warning")
        super(ImportShotDialog, self).closeEvent(event)

    def _on_dialog_finished(self, result):
        debug_print(
            "ImportShotDialog finished window_id=%s shot=%s result=%s"
            % (getattr(self, "_window_id", ""), self.shot_name, result)
        )
        try:
            self._transcode_manager.note_window_closed(
                self._window_id, self.shot_name, source="finished"
            )
        except Exception as exc:
            debug_print("TranscodeQueueManager finished log error: %s" % exc, level="warning")

    def _log_dialog_destroyed(self, window_id, shot_name):
        debug_print("ImportShotDialog destroyed window_id=%s shot=%s" % (window_id, shot_name))
        try:
            self._transcode_manager.note_window_closed(window_id, shot_name, source="destroyed")
        except Exception as exc:
            debug_print("TranscodeQueueManager destroyed log error: %s" % exc, level="warning")

    def _seq_name(self):
        try:
            return self.seq.name()
        except Exception:
            return ""

    # ── navegación entre páginas ─────────────────────────────────

    # ══════════════════════════════════════════════════════════
    #  TAB IMPORT: sub-vistas (main table + preview)
    # ══════════════════════════════════════════════════════════

    def _build_tab_import(self):
        """Contenedor del tab Import con QStackedWidget interno."""
        container = QtWidgets.QWidget()
        vbox = QtWidgets.QVBoxLayout(container)
        vbox.setContentsMargins(0, 0, 0, 0)
        vbox.setSpacing(0)

        self._import_inner_stack = QtWidgets.QStackedWidget()
        self._import_main_page    = self._build_import_main()
        self._import_preview_page = self._build_import_preview()
        self._import_inner_stack.addWidget(self._import_main_page)
        self._import_inner_stack.addWidget(self._import_preview_page)
        self._import_inner_stack.setCurrentIndex(self.IMPORT_MAIN)

        vbox.addWidget(self._import_inner_stack)
        return container

    def _build_import_main(self):
        """Vista principal del tab Import: tabla de media + botones de acción."""
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(6)

        self._media_table = self._build_media_table()
        layout.addWidget(self._media_table, 1)

        # Fila de selección rápida
        sel_row = QtWidgets.QHBoxLayout()
        sel_row.setSpacing(4)
        for label, slot in [
            ("Select All",    self._select_all),
            ("Clear",         self._clear_selection),
            ("Plates",        lambda: self._select_section("plates")),
            ("References",    lambda: self._select_section("refs")),
            ("Publish",       lambda: self._select_section("publish")),
        ]:
            btn = QtWidgets.QPushButton(label)
            btn.setStyleSheet(_BTN_SMALL)
            btn.clicked.connect(slot)
            sel_row.addWidget(btn)
        sel_row.addStretch()
        layout.addLayout(sel_row)

        layout.addWidget(_separator())
        layout.addSpacing(_BTN_ROW_TOP_SPACING)

        # Botones de acción
        btn_row = QtWidgets.QHBoxLayout()
        _oq_btn, _status_lbl = self._make_footer_pair()
        btn_row.addWidget(_oq_btn)
        btn_row.addSpacing(8)
        btn_row.addWidget(_status_lbl, 1)

        self._preview_btn = QtWidgets.QPushButton("Preview Timeline")
        self._preview_btn.setStyleSheet(_BTN_SECONDARY)
        self._preview_btn.setToolTip("Previsualizar la disposición en el timeline antes de importar")
        self._preview_btn.clicked.connect(self._go_to_import_preview)
        btn_row.addWidget(self._preview_btn)

        btn_row.addSpacing(6)

        self._import_now_btn = QtWidgets.QPushButton("Import Now")
        self._import_now_btn.setStyleSheet(_BTN_PRIMARY)
        self._import_now_btn.setToolTip("Importar al bin y colocar en el timeline")
        self._import_now_btn.clicked.connect(self._do_import)
        btn_row.addWidget(self._import_now_btn)

        btn_row.addSpacing(6)

        self._import_v000_btn = QtWidgets.QPushButton("Import and Create V000")
        self._import_v000_btn.setStyleSheet(_BTN_PRIMARY)
        self._import_v000_btn.setToolTip("Importar al timeline y abrir Create V000 al terminar")
        self._import_v000_btn.clicked.connect(self._do_import_and_v000)
        btn_row.addWidget(self._import_v000_btn)

        layout.addLayout(btn_row)

        self._update_action_btns()
        return page

    def _build_media_table(self):
        # col 0: barra de color (4 px)  col 1: checkbox (28 px)
        # col 2: Nombre  3: Tipo  4: Resolución  5: FPS  6: Compresión  7: Frames/Duration  8: Track
        headers = ["", "", "Nombre", "Tipo", "Resolución", "FPS", "Compresión", "Frames/Duration", "Track"]
        table = QtWidgets.QTableWidget()
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.verticalHeader().setVisible(False)
        table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setFocusPolicy(QtCore.Qt.NoFocus)
        table.setShowGrid(False)
        table.setAlternatingRowColors(False)
        table.setStyleSheet(_TABLE_STYLE)
        table.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)

        rows = self._build_table_rows()
        self._table_rows = rows
        table.setRowCount(len(rows))

        self._checkboxes = {}
        self._track_combos = {}

        for i, row_data in enumerate(rows):
            if row_data["type"] == "section_header":
                self._populate_section_header_row(table, i, row_data)
            else:
                self._populate_data_row(table, i, row_data)

        header = table.horizontalHeader()
        header.setMinimumSectionSize(1)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        table.setColumnWidth(0, 5)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        table.setColumnWidth(1, 28)
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        # Tipo, FPS, Compresión — ajustan al contenido
        for col in (3, 5, 6):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.ResizeToContents)
        # Resolución (col 4) — mínimo 165px para "2048×1152 (2.39:1)"
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.Interactive)
        table.setColumnWidth(4, 165)
        # Frames/Duration (col 7) — mínimo 210px para "1001–1480  (480f - 20.0s)"
        header.setSectionResizeMode(7, QtWidgets.QHeaderView.Interactive)
        table.setColumnWidth(7, 210)
        # Track — ajusta al contenido
        header.setSectionResizeMode(8, QtWidgets.QHeaderView.ResizeToContents)

        table.cellClicked.connect(self._on_media_row_clicked)
        return table

    def _on_media_row_clicked(self, row, col):
        if row in self._checkboxes and self._shift_click_active():
            self._exclusive_check_row(self._checkboxes, row)
            self._update_action_btns()
            return
        if col <= 1:
            return  # barra de color y checkbox manejan sus propios eventos
        if row in self._checkboxes:
            chk = self._checkboxes[row]
            chk.setChecked(not chk.isChecked())

    def _shift_click_active(self):
        return bool(QtWidgets.QApplication.keyboardModifiers() & QtCore.Qt.ShiftModifier)

    def _exclusive_check_row(self, checkbox_map, target_row):
        target = checkbox_map.get(target_row)
        if target is None or not target.isEnabled():
            return False
        for row_i, chk in checkbox_map.items():
            if not chk.isEnabled():
                continue
            desired = (row_i == target_row)
            if chk.isChecked() != desired:
                chk.setChecked(desired)
        return True

    def _on_media_chk_clicked(self, row):
        if self._shift_click_active() and self._exclusive_check_row(self._checkboxes, row):
            self._update_action_btns()

    def _on_convert_row_clicked(self, row, col):
        if row in self._convert_checkboxes and self._shift_click_active():
            self._exclusive_check_row(self._convert_checkboxes, row)
            self._update_transcode_btn_state()
            self._refresh_convert_destinos()
            return
        if col <= 1:
            return  # barra de color y checkbox manejan sus propios eventos
        if row in self._convert_checkboxes:
            chk = self._convert_checkboxes[row]
            if chk.isEnabled():
                chk.setChecked(not chk.isChecked())
        self._update_transcode_btn_state()

    def _on_convert_chk_clicked(self, row):
        if self._shift_click_active() and self._exclusive_check_row(self._convert_checkboxes, row):
            self._update_transcode_btn_state()
            self._refresh_convert_destinos()

    def _on_convert_row_double_clicked(self, row, col):
        """Doble click en la tabla de transcode: restaura checkbox (cancela el toggle del
        primer click) y abre la carpeta del item en el explorador del sistema."""
        import os, subprocess
        # El primer click ya hizo toggle del checkbox; lo invertimos para dejarlo como estaba.
        if col > 1 and row in self._convert_checkboxes:
            chk = self._convert_checkboxes[row]
            if chk.isEnabled():
                chk.setChecked(not chk.isChecked())
            self._update_transcode_btn_state()
        # Abrir carpeta en el explorador
        if not hasattr(self, "_convert_rows") or row >= len(self._convert_rows):
            return
        item = self._convert_rows[row]
        path = item.get("path", "")
        if not path:
            return
        if os.name == "nt":
            os.startfile(path)
        elif os.name == "posix":
            subprocess.Popen(["open", path])

    def _build_table_rows(self):
        """
        Construye la lista de filas con secciones intercaladas.
        Tipos: 'section_header' | 'data'
        También puebla self._section_data_rows: {section -> [row_indices]}.
        """
        rows = []
        self._section_data_rows = {"publish": [], "plates": [], "refs": []}

        # PUBLISH — todas las versiones, ordenadas por task y luego version desc
        pub_sorted = sorted(
            (p for p in self.publish_items if p.get("has_versions")),
            key=lambda p: (_TASK_ORDER.get(p["task"], 9), -p["version_num"])
        )
        if pub_sorted:
            rows.append({"type": "section_header", "label": "PUBLISH", "color": "#777777"})
            for p in pub_sorted:
                idx = len(rows)
                self._section_data_rows["publish"].append(idx)
                rows.append({"type": "data", "source": "publish", "item": p,
                             "section": "publish"})

        # PLATES — EXR sequences + MOVs detectados como plates
        plates = [i for i in self.input_items
                  if i["kind"] == "exr_seq"
                  or (i["kind"] == "mov" and _is_plate_track(i.get("track")))]
        if plates:
            rows.append({"type": "section_header", "label": "PLATES", "color": _CLR_PLATES, "text_color": "#6fc9d9"})
            for item in plates:
                idx = len(rows)
                self._section_data_rows["plates"].append(idx)
                rows.append({"type": "data", "source": "input", "item": item,
                             "section": "plates"})

        # REFERENCES — MOVs de _input (editref primero, seqref despues)
        def _ref_sort_key(x):
            n = x.get("name", "").lower()
            if "editrefclean" in n: return 0
            if "editref" in n:      return 1
            if "seqref" in n:       return 2
            return 3

        refs = sorted(
            [i for i in self.input_items
             if i["kind"] == "mov" and not _is_plate_track(i.get("track"))],
            key=_ref_sort_key
        )
        if refs:
            rows.append({"type": "section_header", "label": "REFERENCES",
                         "color": _CLR_REFS})
            for item in refs:
                idx = len(rows)
                self._section_data_rows["refs"].append(idx)
                rows.append({"type": "data", "source": "input", "item": item,
                             "section": "refs"})

        return rows

    def _populate_section_header_row(self, table, row_i, row_data):
        ncols = table.columnCount()
        color = row_data["color"]
        text_color = row_data.get("text_color", color)
        label = row_data["label"]

        # Para PUBLISH, usar gradiente de colores (cleanup ➜ roto ➜ comp)
        if label == "PUBLISH":
            gradient = QtGui.QLinearGradient(0, 0, 0, 1)
            gradient.setCoordinateMode(QtGui.QGradient.ObjectBoundingMode)
            gradient.setColorAt(0.0, QtGui.QColor("#27c8c3"))   # cleanup
            gradient.setColorAt(0.5, QtGui.QColor("#2abf7e"))   # roto
            gradient.setColorAt(1.0, QtGui.QColor("#3381e0"))   # comp
            bar = QtWidgets.QTableWidgetItem()
            bar.setBackground(QtGui.QBrush(gradient))
            bar.setFlags(QtCore.Qt.NoItemFlags)
            table.setItem(row_i, 0, bar)
        else:
            # Para otras secciones, color sólido
            bar = QtWidgets.QTableWidgetItem()
            bar.setBackground(QtGui.QColor(color))
            bar.setFlags(QtCore.Qt.NoItemFlags)
            table.setItem(row_i, 0, bar)

        table.setSpan(row_i, 1, 1, ncols - 1)
        if label == "PUBLISH":
            lbl = GradientTextLabel(
                "  " + label, ["#3381e0", "#2abf7e", "#27c8c3"]
            )
            lbl.setContentsMargins(8, 3, 8, 3)
            font = lbl.font()
            font.setBold(True)
            font.setPointSize(8)
            lbl.setFont(font)
        else:
            lbl = QtWidgets.QLabel("  " + label)
            lbl.setStyleSheet(
                "color: %s; font-weight: bold; font-size: 11px; "
                "padding: 3px 8px; background: #313131; letter-spacing: 1px;" % text_color
            )
        table.setCellWidget(row_i, 1, lbl)
        table.setRowHeight(row_i, 24)

    def _populate_data_row(self, table, row_i, row_data):
        source  = row_data["source"]
        item    = row_data["item"]
        section = row_data.get("section", "")

        is_input_exr = (source == "input" and item.get("kind") == "exr_seq")
        is_latest    = item.get("is_latest", True)
        is_seqref    = (source == "input" and item.get("track") is None
                        and "seqref" in item.get("name", "").lower())

        # Col 0: barra de color (indica tipo/task de la fila)
        if section == "publish":
            bar_color = _TASK_ROW_COLORS.get(item.get("task", ""), "#555555")
        elif section == "plates":
            bar_color = _CLR_PLATES
        else:
            bar_color = _CLR_REFS
        bar_item = QtWidgets.QTableWidgetItem()
        bar_item.setBackground(QtGui.QColor(bar_color))
        bar_item.setFlags(QtCore.Qt.NoItemFlags)
        table.setItem(row_i, 0, bar_item)

        # Col 1: checkbox — marcado por defecto solo para la versión más reciente
        chk = QtWidgets.QCheckBox()
        chk.setStyleSheet("color:#a7a7a7; padding:2px;")
        chk.setChecked(is_latest)
        chk.stateChanged.connect(self._update_action_btns)
        chk.clicked.connect(lambda _checked=False, ri=row_i: self._on_media_chk_clicked(ri))
        self._checkboxes[row_i] = chk
        container = QtWidgets.QWidget()
        cl = QtWidgets.QHBoxLayout(container)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setAlignment(QtCore.Qt.AlignCenter)
        cl.addWidget(chk)
        table.setCellWidget(row_i, 1, container)

        # Col 2: Nombre
        name = item.get("name") or item.get("version_name") or ""
        if is_seqref:
            name_color = _CLR_REFS
            tooltip    = "Se importará al bin. No se coloca en el timeline."
        elif section == "publish":
            name_color = "#CCCCCC" if is_latest else "#777777"
            tooltip    = ""
        else:
            name_color = "#CCCCCC" if is_latest else "#888888"
            tooltip    = ""
        shot_pfx_len = len(self.shot_name) if name.startswith(self.shot_name) else 0
        if shot_pfx_len:
            shot_clr = SHOTNAME_COLOR if is_latest else mix_colors(SHOTNAME_COLOR, "#272727", 0.55)
            rest_esc = _rn_escape(name[shot_pfx_len:])
            name_html = (
                "<span style='color:%s;'>%s</span>"
                "<span style='color:%s;'>%s</span>"
                % (shot_clr, _rn_escape(name[:shot_pfx_len]), name_color, rest_esc)
            )
            name_lbl = _cell_html_label(name_html)
            if tooltip:
                name_lbl.setToolTip(tooltip)
            table.setCellWidget(row_i, 2, name_lbl)
        else:
            name_item = QtWidgets.QTableWidgetItem(name)
            name_item.setForeground(QtGui.QColor(name_color))
            if tooltip:
                name_item.setToolTip(tooltip)
            table.setItem(row_i, 2, name_item)

        # Col 3: Tipo
        if source == "publish" or item.get("kind") == "exr_seq":
            kind_str = "EXR seq"
        elif item.get("kind") == "mov":
            kind_str = (item.get("ext") or
                        Path(item.get("path", "")).suffix.lstrip(".").upper() or "MOV")
        else:
            kind_str = "Archivo"
        tipo_item = QtWidgets.QTableWidgetItem(kind_str)
        tipo_item.setForeground(QtGui.QColor("#888888"))
        table.setItem(row_i, 3, tipo_item)

        # Color base para esta fila (más apagado si no es la versión latest)
        _dim = "#888888" if is_latest else "#666666"

        # Col 4: Res — dimensiones en dim, AR en dorado suave
        w, h = item.get("width"), item.get("height")
        if w and h:
            ar = _ar_str(w, h)
            if ar:
                ar_clr = _CLR_AR if is_latest else "#786840"
                res_html = ("<span style='color:%s;'>%d×%d</span>"
                            " <span style='color:%s;'>(%s)</span>" % (_dim, w, h, ar_clr, ar))
                table.setCellWidget(row_i, 4, _cell_html_label(res_html))
            else:
                ri = QtWidgets.QTableWidgetItem("%d×%d" % (w, h))
                ri.setForeground(QtGui.QColor(_dim))
                table.setItem(row_i, 4, ri)
        else:
            ri = QtWidgets.QTableWidgetItem("—")
            ri.setForeground(QtGui.QColor(_dim))
            table.setItem(row_i, 4, ri)

        # Col 5: FPS
        fps = item.get("fps")
        fps_str = ("%.5g" % fps) if fps else "—"
        fps_item = QtWidgets.QTableWidgetItem(fps_str)
        fps_item.setForeground(QtGui.QColor(_dim))
        table.setItem(row_i, 5, fps_item)

        # Col 6: Compresión — coloreada según tipo (dwaa=verde, zip/piz=rojo)
        comp = item.get("compression") or "—"
        cc = _comp_color(comp, greyed=not is_latest)
        if cc != _dim:
            comp_html = "<span style='color:%s;'>%s</span>" % (cc, comp)
            table.setCellWidget(row_i, 6, _cell_html_label(comp_html))
        else:
            ci = QtWidgets.QTableWidgetItem(comp)
            ci.setForeground(QtGui.QColor(cc))
            table.setItem(row_i, 6, ci)

        # Col 7: Frames  "1001–1480  (480f - 20.0s)"
        ff = item.get("first_frame")
        lf = item.get("last_frame")
        fc = item.get("frame_count")
        if ff is not None and lf is not None:
            fc_val = fc if fc is not None else (lf - ff + 1)
            fps_val = item.get("fps")
            secs_txt = (" - %.1fs" % (fc_val / float(fps_val))) if fps_val else ""
            fc_clr = _CLR_FRAMES if is_latest else "#786830"
            frames_html = (
                "<span style='color:%s;'>%d–%d</span>"
                "  (<span style='color:%s;'>%df%s</span>)" % (
                    _dim, ff, lf, fc_clr, fc_val, secs_txt))
            table.setCellWidget(row_i, 7, _cell_html_label(frames_html))
        else:
            fi = QtWidgets.QTableWidgetItem("—")
            fi.setForeground(QtGui.QColor(_dim))
            table.setItem(row_i, 7, fi)

        # Col 8: Track (dropdown editable para inputs, label para publish)
        if source == "input" and item.get("kind") in ("exr_seq", "mov"):
            combo = self._build_track_combo(item, row_i)
            table.setCellWidget(row_i, 8, combo)
            self._track_combos[row_i] = combo
        else:
            track_str = item.get("track") or "—"
            lbl = QtWidgets.QLabel(track_str)
            lbl.setStyleSheet("color:#888888; padding:2px 6px;")
            table.setCellWidget(row_i, 8, lbl)

    # ── helpers de tracks del timeline ───────────────────────────────────────

    _CREATE_TRACK_PREFIX = "+ Crear track "

    def _get_seq_track_names(self):
        """
        Retorna los nombres de los video tracks existentes en self.seq,
        en orden visual top-to-bottom (= reversed(videoTracks())), excluyendo BurnIn.
        Se ordena por _IMPORT_TRACK_ORDER; tracks desconocidos van al final.
        """
        if not self.seq:
            return []
        try:
            names = []
            for track in reversed(list(self.seq.videoTracks())):  # top→bottom visual
                name = track.name()
                if not _is_burnin_track(name):
                    names.append(name)
            # Ordenar según _IMPORT_TRACK_ORDER (top-to-bottom visual = reversed bt-order)
            # _IMPORT_TRACK_ORDER está en bt-order (aPlate=abajo, BurnIn=arriba),
            # así que el orden visual es reversed → _IMPORT_TRACK_ORDER reversed.
            visual_order = list(reversed(_IMPORT_TRACK_ORDER))
            def sort_key(n):
                try:
                    return visual_order.index(n)
                except ValueError:
                    return len(visual_order)
            names.sort(key=sort_key)
            return names
        except Exception:
            return []

    def _create_plate_track(self, track_name):
        """
        Crea un nuevo VideoTrack con el nombre dado en self.seq, insertado en
        la posición alfabética correcta dentro de la sección de plates.

        SISTEMA DE COORDENADAS
        ─────────────────────
        seq.videoTracks() devuelve bt-order: índice 0 = fondo del panel,
        índice mayor = tope. aPlate tiene el mayor índice (está arriba).
        _IMPORT_TRACK_ORDER = ["aPlate", "bPlate", ..., "_dmp_"] está en
        orden visual TOP→BOTTOM (índice 0 = arriba en el panel).

        BÚSQUEDA DE VECINOS (en términos de _IMPORT_TRACK_ORDER):
        · lower_idx: track con mayor rank en _IMPORT_TRACK_ORDER aún < new_pos.
          Este track tiene un MAYOR bt-trackIndex que el nuevo → está ENCIMA
          del nuevo track en el panel. Es el track "debajo del cual" se inserta
          el nuevo (el nuevo ocupa su índice y él sube uno).
        · upper_idx: track con menor rank en _IMPORT_TRACK_ORDER aún > new_pos.
          Tiene MENOR bt-trackIndex → está DEBAJO del nuevo en el panel.

        INSERCIÓN (patrón LGA_NKS_CreateNewTrack / InsertTest):
          insert_at = lower_idx   (trackIndex del vecino de arriba)
          new_list = video_tracks[:insert_at] + [new_track] + video_tracks[insert_at:]
          for t in new_list: seq.addTrack(t)

        Retorna el nuevo hiero.core.VideoTrack, o None en caso de error.
        """
        if not self.seq:
            return None
        try:
            new_track = hiero.core.VideoTrack(track_name)
            video_tracks = list(self.seq.videoTracks())

            def bt_order_idx(name):
                if _is_burnin_track(name):
                    return len(_IMPORT_TRACK_ORDER) + 1  # BurnIn siempre encima
                try:
                    return _IMPORT_TRACK_ORDER.index(name)
                except ValueError:
                    return len(_IMPORT_TRACK_ORDER)      # desconocido: justo bajo BurnIn

            new_pos = bt_order_idx(track_name)

            # Vecino inferior: track existente con mayor bt-rank que sea < new_pos.
            # Es el que debe quedar inmediatamente debajo del nuevo en el stack.
            lower_idx = None          # índice en video_tracks
            lower_pos = -1
            # Vecino superior: track existente con menor bt-rank que sea > new_pos.
            upper_idx = None
            upper_pos = len(_IMPORT_TRACK_ORDER) + 2

            for i, t in enumerate(video_tracks):
                tp = bt_order_idx(t.name())
                if tp < new_pos and tp > lower_pos:
                    lower_pos = tp
                    lower_idx = i
                if tp > new_pos and tp < upper_pos:
                    upper_pos = tp
                    upper_idx = i

            # Punto de inserción en video_tracks (el resto del stack no cambia).
            # videoTracks() es bt-order: índice 0 = fondo, índice mayor = tope.
            # aPlate tiene el MAYOR índice (está arriba en el panel).
            # Para insertar dPlate DEBAJO de bPlate se usa insert_at = trackIndex(bPlate)
            # = lower_idx: el nuevo track ocupa el índice de bPlate y bPlate sube uno.
            if lower_idx is not None:
                insert_at = lower_idx       # el vecino de arriba cede su índice y sube
            elif upper_idx is not None:
                insert_at = upper_idx       # insertar justo antes del vecino inferior
            else:
                insert_at = 0               # sin vecinos conocidos → fondo

            new_bt_list = (video_tracks[:insert_at]
                           + [new_track]
                           + video_tracks[insert_at:])

            # Remover todos y reinsertar con el nuevo track intercalado
            for t in video_tracks:
                self.seq.removeTrack(t)
            for t in new_bt_list:
                self.seq.addTrack(t)

            below = video_tracks[lower_idx].name() if lower_idx is not None else "—"
            above = video_tracks[upper_idx].name() if upper_idx is not None else "—"
            debug_print("_create_plate_track: '%s' creado entre '%s' (abajo) y "
                        "'%s' (arriba)  insert_at=%d"
                        % (track_name, below, above, insert_at))
            return new_track

        except Exception as exc:
            debug_print("_create_plate_track: error → %s" % exc, level="error")
            return None

    def _refresh_track_combo_options(self, created_track_name=None, creator_row=None):
        """
        Reconstruye las opciones de todos los combos de track tras añadir un
        track nuevo al timeline.  Preserva la selección actual de cada combo.

        created_track_name: nombre del track recién creado (o None).
        creator_row: row_id del combo que inició la creación.  Ese combo
            pasa a mostrar el track recién creado como selección.  Los demás
            combos que tenían la opción "Crear track <name>" seleccionada
            (caso de navegación por teclado) también se actualizan.
        """
        new_options = self._get_seq_track_names()

        for row_id, combo in self._track_combos.items():
            current_sel = combo.currentText()

            # Determinar la selección destino
            create_opt = self._CREATE_TRACK_PREFIX + (created_track_name or "")
            if created_track_name and row_id == creator_row:
                # Este combo inició la creación vía botón → asignar el track
                target_sel = created_track_name
            elif created_track_name and current_sel == create_opt:
                # Selección vía teclado: la opción "Crear…" era el valor actual
                target_sel = created_track_name
            else:
                target_sel = current_sel

            # Calcular la opción "Crear" para este row (si aplica)
            row_item = self._table_rows[row_id].get("item", {})
            auto_track = row_item.get("track") if row_item else None
            create_option = None
            if (auto_track and _is_plate_track(auto_track)
                    and auto_track not in new_options):
                create_option = self._CREATE_TRACK_PREFIX + auto_track

            options = ["— sin track —"] + new_options
            if create_option:
                options.append(create_option)

            combo.blockSignals(True)
            combo.clear()
            for opt in options:
                combo.addItem(opt)

            # Restaurar selección
            if target_sel in new_options:
                combo.setCurrentText(target_sel)
            elif target_sel == "— sin track —":
                combo.setCurrentIndex(0)
            else:
                combo.setCurrentIndex(0)

            combo.blockSignals(False)

    # ── construcción de combo de track ───────────────────────────────────────

    def _build_track_combo(self, item: dict, row_id: int):
        """
        Construye el combo de track para un ítem de input (exr_seq o mov).

        Opciones:
          - "— sin track —"
          - Tracks existentes en self.seq (visual top-to-bottom, sin BurnIn)
          - "＋ Crear track <name>" al final, solo si el track auto-detectado
            es un *plate y no existe todavía en el timeline.

        Reglas de conflicto (un solo clip por track):
          - Si el track auto-detectado ya está asignado a otro row:
              · ítem EXR desplaza a cualquier MOV existente en ese track.
              · ítem MOV cede ante cualquier EXR o MOV existente → "— sin track —".
          - El desplazado queda en "— sin track —" automáticamente.
        """
        current_track = item.get("track")
        # Tratar "?" como sin asignar
        if current_track == "?":
            current_track = None
        is_exr = (item.get("kind") == "exr_seq")

        existing_tracks = self._get_seq_track_names()

        # Opción "Crear track" si el auto-detectado es plate y no existe aún
        create_option = None
        if (current_track and _is_plate_track(current_track)
                and current_track not in existing_tracks):
            create_option = self._CREATE_TRACK_PREFIX + current_track

        # ── Resolución de conflictos en carga inicial ──────────────────────
        if current_track and current_track != "— sin track —":
            for existing_row, existing_combo in list(self._track_combos.items()):
                if existing_combo.currentText() == current_track:
                    existing_item = self._table_rows[existing_row].get("item", {})
                    existing_is_exr = (existing_item.get("kind") == "exr_seq")
                    iname = item.get("name") or item.get("version_name") or "?"
                    ename = existing_item.get("name") or "?"

                    if is_exr and not existing_is_exr:
                        # EXR actual gana sobre MOV existente
                        existing_combo.blockSignals(True)
                        existing_combo.setCurrentIndex(0)  # "— sin track —"
                        existing_combo.blockSignals(False)
                        self._track_overrides[existing_row] = "— sin track —"
                        debug_print(
                            "[track_conflict] EXR '%s' desplaza MOV '%s' del track '%s'"
                            % (iname, ename, current_track)
                        )
                    elif not is_exr and existing_is_exr:
                        # MOV actual cede ante EXR existente
                        debug_print(
                            "[track_conflict] MOV '%s' cede track '%s' (EXR '%s' tiene prioridad)"
                            % (iname, current_track, ename)
                        )
                        current_track = None
                    else:
                        # Mismo tipo (EXR vs EXR, o MOV vs MOV):
                        # gana la versión más alta; en empate gana el existente.
                        cur_ver = item.get("version_num", -1)
                        ext_ver = existing_item.get("version_num", -1)
                        if cur_ver > ext_ver:
                            # Actual es más reciente → desplaza al existente
                            existing_combo.blockSignals(True)
                            existing_combo.setCurrentIndex(0)
                            existing_combo.blockSignals(False)
                            self._track_overrides[existing_row] = "— sin track —"
                            debug_print(
                                "[track_conflict] '%s' (v%d) desplaza '%s' (v%d) del track '%s'"
                                % (iname, cur_ver, ename, ext_ver, current_track)
                            )
                        else:
                            # Existente es más reciente o igual → actual cede
                            debug_print(
                                "[track_conflict] '%s' (v%d) cede track '%s' (ya tiene '%s' v%d)"
                                % (iname, cur_ver, current_track, ename, ext_ver)
                            )
                            current_track = None
                    break

        # ── Construir combo ────────────────────────────────────────────────
        # La opción "Crear track" actúa como botón vía _TrackComboListView:
        # el click se consume sin cambiar el valor actual del combo.
        def _on_create_opt(create_text, _rid=row_id):
            self._on_track_combo_changed(_rid, create_text)

        _track_list_view = _TrackComboListView(_on_create_opt)
        _track_delegate  = _TrackComboDelegate(_track_list_view)
        _track_list_view.setItemDelegate(_track_delegate)

        combo = _ArrowComboBox()
        combo.setView(_track_list_view)
        combo.setStyleSheet(
            "QComboBox { background-color:#272727; border:0px; "
            "color:#a7a7a7; padding:1px 4px; }"
            "QComboBox::drop-down { border:0px; width:14px; }"
            "QComboBox::down-arrow { image:none; width:0px; height:0px; }"
            "QComboBox QAbstractItemView { background-color:#2B2B2B; "
            "border:1px solid #444444; color:#a7a7a7; "
            "selection-background-color:#272727; selection-color:#a7a7a7; outline:none; }"
        )
        options = ["— sin track —"] + existing_tracks
        if create_option:
            options.append(create_option)
        for opt in options:
            combo.addItem(opt)

        # Selección inicial: "— sin track —" cuando el track aún no existe.
        # La opción "Crear track" es un botón, nunca el valor seleccionado.
        combo.blockSignals(True)
        if current_track and current_track in existing_tracks:
            combo.setCurrentText(current_track)
        else:
            combo.setCurrentIndex(0)  # "— sin track —"
        combo.blockSignals(False)

        combo.currentTextChanged.connect(
            lambda txt, rid=row_id: self._on_track_combo_changed(rid, txt)
        )
        return combo

    def _on_track_combo_changed(self, changed_row: int, new_track: str):
        """
        Registra el track elegido y desasigna cualquier otro clip que ya
        tuviera ese track asignado.

        Si la selección es "Crear track <name>", crea el track en el timeline
        y refresca todos los combos para que usen el nombre real.
        """
        # ── Detectar selección "Crear track" ──────────────────────────────
        if new_track.startswith(self._CREATE_TRACK_PREFIX):
            track_to_create = new_track[len(self._CREATE_TRACK_PREFIX):]
            debug_print("_on_track_combo_changed: creando track '%s'" % track_to_create)

            project = None
            try:
                project = self.seq.project()
            except Exception:
                pass

            def _do_create():
                return self._create_plate_track(track_to_create)

            if project:
                with project.beginUndo("Crear track: %s" % track_to_create):
                    new_t = _do_create()
            else:
                new_t = _do_create()

            if new_t is not None:
                # Refrescar todos los combos con el nuevo track incluido.
                # creator_row indica qué combo inició la acción para asignarle
                # el track recién creado (su selección estaba en "— sin track —"
                # porque la opción "Crear" es un botón, no un valor seleccionado).
                self._refresh_track_combo_options(
                    created_track_name=track_to_create,
                    creator_row=changed_row,
                )
                self._track_overrides[changed_row] = track_to_create
            else:
                # Falló la creación: volver a sin track
                combo = self._track_combos.get(changed_row)
                if combo:
                    combo.blockSignals(True)
                    combo.setCurrentIndex(0)
                    combo.blockSignals(False)
                self._track_overrides[changed_row] = "— sin track —"

            self._update_action_btns()
            return

        # ── Flujo normal ──────────────────────────────────────────────────
        self._track_overrides[changed_row] = new_track

        if not new_track or new_track == "— sin track —":
            self._update_action_btns()
            return

        # Desasignar otras filas que ya tenían el mismo track
        for row, combo in list(self._track_combos.items()):
            if row == changed_row:
                continue
            if combo.currentText() == new_track:
                combo.blockSignals(True)
                combo.setCurrentIndex(0)  # "— sin track —"
                combo.blockSignals(False)
                self._track_overrides[row] = "— sin track —"

        self._update_action_btns()

    def _get_track_for_row(self, row):
        if row in self._track_combos:
            txt = self._track_combos[row].currentText()
            if not txt or txt == "— sin track —":
                return None
            # Si por algún motivo quedó una opción "Crear track" sin resolver, ignorar
            if txt.startswith(self._CREATE_TRACK_PREFIX):
                return None
            return txt
        row_data = self._table_rows[row]
        if row_data.get("type") == "section_header":
            return None
        track = row_data["item"].get("track")
        return track if track and track != "?" else None

    def _update_action_btns(self):
        if not hasattr(self, "_checkboxes"):
            return
        any_checked = any(chk.isChecked() for chk in self._checkboxes.values())
        has_track_assigned = any(
            chk.isChecked() and self._get_track_for_row(row) is not None
            for row, chk in self._checkboxes.items()
            if self._table_rows[row].get("type") != "section_header"
        ) if hasattr(self, "_table_rows") else False

        if hasattr(self, "_preview_btn"):
            self._preview_btn.setEnabled(any_checked)
        if hasattr(self, "_import_now_btn"):
            self._import_now_btn.setEnabled(has_track_assigned)
        if hasattr(self, "_import_v000_btn"):
            self._import_v000_btn.setEnabled(has_track_assigned)
        if hasattr(self, "_preview_import_now_btn"):
            self._preview_import_now_btn.setEnabled(has_track_assigned)
        if hasattr(self, "_preview_import_v000_btn"):
            self._preview_import_v000_btn.setEnabled(has_track_assigned)

    def _go_to_import_preview(self):
        """Cambia a la sub-vista de preview dentro del tab Import."""
        self._update_import_page()
        self._import_inner_stack.setCurrentIndex(self.IMPORT_PREVIEW)

    def _on_tab_changed(self, index):
        """Manejador de cambio de tab. Ejecuta refresh si el tab necesita uno."""
        tab_map = {
            self.TAB_RENAME:    "rename",
            self.TAB_TRANSCODE: "transcode",
            self.TAB_IMPORT:    "import",
        }
        tab_name = tab_map.get(index)
        if tab_name and tab_name in self._needs_refresh:
            self._needs_refresh.discard(tab_name)
            self.input_items   = _scan_input_folder(self.shot_root)
            self.publish_items = _scan_publish_folders(self.shot_root)

        if index == self.TAB_RENAME:
            self._update_rename_page()
        elif index == self.TAB_TRANSCODE:
            saved_chk = {}
            if hasattr(self, "_convert_rows") and hasattr(self, "_convert_checkboxes"):
                for i, chk in self._convert_checkboxes.items():
                    if i < len(self._convert_rows):
                        path = self._convert_rows[i].get("path", "")
                        if path:
                            saved_chk[path] = chk.isChecked()
            self._update_convert_page(saved_chk=saved_chk)
        elif index == self.TAB_IMPORT:
            # Vuelve a la vista principal al entrar al tab
            if hasattr(self, "_import_inner_stack"):
                self._import_inner_stack.setCurrentIndex(self.IMPORT_MAIN)

    # ── selección rápida ─────────────────────────────────────────

    def _select_all(self):
        for chk in self._checkboxes.values():
            chk.setChecked(True)

    def _clear_selection(self):
        for chk in self._checkboxes.values():
            chk.setChecked(False)

    def _select_section(self, section):
        for row_i in self._section_data_rows.get(section, []):
            if row_i in self._checkboxes:
                self._checkboxes[row_i].setChecked(True)

    # ══════════════════════════════════════════════════════════
    #  PAGINA: Rename
    # ══════════════════════════════════════════════════════════

    def _on_rename_row_clicked(self, row, col):
        display_rows = getattr(self, "_rename_display_rows", [])
        if row < len(display_rows) and display_rows[row].get("type") == "section_header":
            return
        if row in self._rename_checkboxes and self._shift_click_active():
            self._exclusive_check_row(self._rename_checkboxes, row)
            self._update_rename_btn_state()
            self._update_rename_summary()
            return
        if col <= 1:
            return
        if row in self._rename_checkboxes:
            chk = self._rename_checkboxes[row]
            if chk.isEnabled():
                chk.setChecked(not chk.isChecked())
        self._update_rename_btn_state()

    def _on_rename_chk_clicked(self, row):
        if self._shift_click_active() and self._exclusive_check_row(self._rename_checkboxes, row):
            self._update_rename_btn_state()
            self._update_rename_summary()

    def _on_rename_row_double_clicked(self, row, col):
        import os
        import subprocess
        display_rows = getattr(self, "_rename_display_rows", [])
        if row < len(display_rows) and display_rows[row].get("type") == "section_header":
            return
        if col > 1 and row in self._rename_checkboxes:
            chk = self._rename_checkboxes[row]
            if chk.isEnabled():
                chk.setChecked(not chk.isChecked())
            self._update_rename_btn_state()
        if row >= len(display_rows):
            return
        dr = display_rows[row]
        if dr.get("type") != "data":
            return
        it = dr["preview_row"]
        p = it.get("folder_path") if it.get("is_sequence") else it.get("item_path")
        if not p:
            return
        if os.name == "nt":
            os.startfile(p)
        elif os.name == "posix":
            subprocess.Popen(["open", p])

    def _populate_rename_section_header(self, row_i, row_data):
        ncols = self._rename_table.columnCount()
        color = row_data["color"]
        text_color = row_data.get("text_color", color)
        label = row_data["label"]

        if label == "PUBLISH":
            gradient = QtGui.QLinearGradient(0, 0, 0, 1)
            gradient.setCoordinateMode(QtGui.QGradient.ObjectBoundingMode)
            gradient.setColorAt(0.0, QtGui.QColor("#27c8c3"))
            gradient.setColorAt(0.5, QtGui.QColor("#2abf7e"))
            gradient.setColorAt(1.0, QtGui.QColor("#3381e0"))
            bar = QtWidgets.QTableWidgetItem()
            bar.setBackground(QtGui.QBrush(gradient))
            bar.setFlags(QtCore.Qt.NoItemFlags)
            self._rename_table.setItem(row_i, 0, bar)
        else:
            bar = QtWidgets.QTableWidgetItem()
            bar.setBackground(QtGui.QColor(color))
            bar.setFlags(QtCore.Qt.NoItemFlags)
            self._rename_table.setItem(row_i, 0, bar)

        self._rename_table.setSpan(row_i, 1, 1, ncols - 1)
        if label == "PUBLISH":
            lbl = GradientTextLabel("  " + label, ["#3381e0", "#2abf7e", "#27c8c3"])
            lbl.setContentsMargins(8, 3, 8, 3)
            font = lbl.font()
            font.setBold(True)
            font.setPointSize(8)
            lbl.setFont(font)
        else:
            lbl = QtWidgets.QLabel("  " + label)
            lbl.setStyleSheet(
                "color: %s; font-weight: bold; font-size: 11px; "
                "padding: 3px 8px; background: #313131; letter-spacing: 1px;" % text_color
            )
        self._rename_table.setCellWidget(row_i, 1, lbl)
        self._rename_table.setRowHeight(row_i, 24)

    def _on_rename_chk_changed(self, row_i):
        display_rows = getattr(self, "_rename_display_rows", [])
        if row_i >= len(display_rows):
            return
        dr = display_rows[row_i]
        if dr.get("type") != "data":
            return
        it = dr["preview_row"]
        chk = self._rename_checkboxes.get(row_i)
        if chk is None:
            return
        is_checked = chk.isChecked()
        _dash = "<span style='color:#444444;'>—</span>"
        _plain = "<span style='color:#a7a7a7;'>%s</span>"
        # Cols 2 y 5 (original): colores solo si checkbox activado
        orig_disp = it.get("original_html", "") if is_checked else (_plain % _rn_escape(it.get("original_name", "")))
        fold_orig_disp = it.get("folder_original_html", "") if is_checked else (_plain % _rn_escape(it.get("folder_name", "")))
        self._rename_table.setCellWidget(row_i, 2, _cell_html_label(orig_disp))
        self._rename_table.setCellWidget(row_i, 5, _cell_html_label(fold_orig_disp))
        self._rename_table.setCellWidget(
            row_i, 4,
            _cell_html_label(it.get("renamed_html", "") if is_checked else _dash)
        )
        self._rename_table.setCellWidget(
            row_i, 6,
            _cell_html_label(it.get("folder_renamed_html", "") if is_checked else _dash)
        )
        if is_checked:
            st_color = _CLR_STATUS_PENDING
            st = it.get("status", "Pendiente")
            if not it.get("has_changes"):
                st_color = "#888888"
            st_html = "<span style='color:%s;'>%s</span>" % (st_color, st)
        else:
            st_html = _dash
        self._rename_table.setCellWidget(row_i, 7, _cell_html_label(st_html))
        self._update_rename_btn_state()
        self._update_rename_summary()

    def _build_page_rename(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(8)

        if Rename_Test_mode:
            _tm_row = QtWidgets.QHBoxLayout()
            _tm_lbl = QtWidgets.QLabel("  ⚠  TEST MODE")
            _tm_lbl.setStyleSheet("color:#d9a441; font-weight:bold; padding:2px 6px;")
            _tm_row.addWidget(_tm_lbl)
            _tm_row.addStretch()
            layout.addLayout(_tm_row)

        self._rename_table = QtWidgets.QTableWidget()
        self._rename_table.setColumnCount(8)
        self._rename_table.setHorizontalHeaderLabels(
            ["", "", "Original", "➜", "Renamed", "Folder Original", "Folder Renamed", "Estado"]
        )
        _estado_hdr = self._rename_table.horizontalHeaderItem(7)
        if _estado_hdr:
            _estado_hdr.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        self._rename_table.verticalHeader().setVisible(False)
        self._rename_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self._rename_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._rename_table.setFocusPolicy(QtCore.Qt.NoFocus)
        self._rename_table.setShowGrid(False)
        self._rename_table.setStyleSheet(_TABLE_STYLE)
        self._rename_table.setMinimumHeight(120)
        self._rename_table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        hdr = self._rename_table.horizontalHeader()
        hdr.setMinimumSectionSize(1)
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        self._rename_table.setColumnWidth(0, 5)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        self._rename_table.setColumnWidth(1, 28)
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.Interactive)
        self._rename_table.setColumnWidth(2, 300)
        hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.Fixed)
        self._rename_table.setColumnWidth(3, 24)
        hdr.setSectionResizeMode(4, QtWidgets.QHeaderView.Interactive)
        self._rename_table.setColumnWidth(4, 300)
        hdr.setSectionResizeMode(5, QtWidgets.QHeaderView.Interactive)
        self._rename_table.setColumnWidth(5, 210)
        hdr.setSectionResizeMode(6, QtWidgets.QHeaderView.Interactive)
        self._rename_table.setColumnWidth(6, 210)
        hdr.setSectionResizeMode(7, QtWidgets.QHeaderView.Interactive)
        self._rename_table.setColumnWidth(7, 175)
        hdr.setStretchLastSection(False)
        self._rename_table.cellClicked.connect(self._on_rename_row_clicked)
        self._rename_table.cellDoubleClicked.connect(self._on_rename_row_double_clicked)
        layout.addWidget(self._rename_table, 1)

        self._rename_summary_lbl = QtWidgets.QLabel("")
        self._rename_summary_lbl.setStyleSheet("color:#888888; padding:2px 6px;")
        layout.addWidget(self._rename_summary_lbl)

        layout.addWidget(_separator())

        line_style = (
            "QLineEdit { background-color:#272727; border:1px solid #444;"
            " color:#a7a7a7; padding:4px 8px; border-radius:3px;"
            " selection-background-color:#505060; selection-color:#d0d0d0; }"
            "QLineEdit:focus { border:1px solid #555555; }"
        )

        # Opciones en 2 columnas — igual que transcode
        opts_row = QtWidgets.QHBoxLayout()
        opts_row.setSpacing(20)

        # Columna izquierda - Search & Replace 1 + 2
        col_left = QtWidgets.QVBoxLayout()
        col_left.setSpacing(6)

        col_left.addWidget(_section_label("Search & Replace 1"))
        sr1_row = QtWidgets.QHBoxLayout()
        self._rename_sr1_search = QtWidgets.QLineEdit()
        self._rename_sr1_search.setPlaceholderText("Search")
        self._rename_sr1_search.setStyleSheet(line_style)
        self._rename_sr1_replace = QtWidgets.QLineEdit()
        self._rename_sr1_replace.setPlaceholderText("Replace")
        self._rename_sr1_replace.setStyleSheet(line_style)
        self._rename_sr1_case = QtWidgets.QCheckBox("Case Sensitive")
        self._rename_sr1_case.setStyleSheet("color:#a7a7a7; padding:2px;")
        self._rename_sr1_case.setFocusPolicy(QtCore.Qt.NoFocus)
        _sr1_swap = QtWidgets.QPushButton("⇄")
        _sr1_swap.setStyleSheet(_BTN_SMALL)
        _sr1_swap.setFixedWidth(28)
        _sr1_swap.setToolTip("Intercambiar Search y Replace")
        _sr1_swap.setFocusPolicy(QtCore.Qt.NoFocus)
        _sr1_swap.clicked.connect(lambda: self._swap_sr(self._rename_sr1_search, self._rename_sr1_replace))
        sr1_row.addWidget(self._rename_sr1_search, 1)
        sr1_row.addWidget(_sr1_swap, 0)
        sr1_row.addWidget(self._rename_sr1_replace, 1)
        sr1_row.addWidget(self._rename_sr1_case, 0)
        col_left.addLayout(sr1_row)

        col_left.addSpacing(8)

        col_left.addWidget(_section_label("Search & Replace 2"))
        sr2_row = QtWidgets.QHBoxLayout()
        self._rename_sr2_search = QtWidgets.QLineEdit()
        self._rename_sr2_search.setPlaceholderText("Search")
        self._rename_sr2_search.setStyleSheet(line_style)
        self._rename_sr2_replace = QtWidgets.QLineEdit()
        self._rename_sr2_replace.setPlaceholderText("Replace")
        self._rename_sr2_replace.setStyleSheet(line_style)
        self._rename_sr2_case = QtWidgets.QCheckBox("Case Sensitive")
        self._rename_sr2_case.setStyleSheet("color:#a7a7a7; padding:2px;")
        self._rename_sr2_case.setFocusPolicy(QtCore.Qt.NoFocus)
        _sr2_swap = QtWidgets.QPushButton("⇄")
        _sr2_swap.setStyleSheet(_BTN_SMALL)
        _sr2_swap.setFixedWidth(28)
        _sr2_swap.setToolTip("Intercambiar Search y Replace")
        _sr2_swap.setFocusPolicy(QtCore.Qt.NoFocus)
        _sr2_swap.clicked.connect(lambda: self._swap_sr(self._rename_sr2_search, self._rename_sr2_replace))
        sr2_row.addWidget(self._rename_sr2_search, 1)
        sr2_row.addWidget(_sr2_swap, 0)
        sr2_row.addWidget(self._rename_sr2_replace, 1)
        sr2_row.addWidget(self._rename_sr2_case, 0)
        col_left.addLayout(sr2_row)

        col_left.addStretch()
        opts_row.addLayout(col_left, 3)

        # Wrapper para todo lo que va a la derecha de col_left.
        # Tiene stretch=1 igual que col_left, asi col_left mantiene su ancho (~50%).
        right_wrap = QtWidgets.QHBoxLayout()
        right_wrap.setSpacing(0)

        # Espacio entre col_left y el separador vertical
        right_wrap.addSpacing(10)

        # Separador vertical entre col_left y col_right
        right_wrap.addWidget(_separator("v"))

        # Espacio entre el separador y el contenido de col_right
        right_wrap.addSpacing(30)

        # Columna Prefix / Suffix + Delimiter / Digits
        col_pref_suf = QtWidgets.QVBoxLayout()
        col_pref_suf.setSpacing(6)

        col_pref_suf.addWidget(_section_label("Prefix"))
        prefix_row = QtWidgets.QHBoxLayout()
        self._rename_prefix_input = QtWidgets.QLineEdit()
        self._rename_prefix_input.setPlaceholderText("Prefix")
        self._rename_prefix_input.setStyleSheet(line_style)
        prefix_row.addWidget(self._rename_prefix_input, 1)
        prefix_row.addSpacing(20)
        col_pref_suf.addLayout(prefix_row)

        col_pref_suf.addSpacing(8)

        col_pref_suf.addWidget(_section_label("Suffix"))
        suffix_row = QtWidgets.QHBoxLayout()
        self._rename_suffix_input = QtWidgets.QLineEdit()
        self._rename_suffix_input.setPlaceholderText("Suffix")
        self._rename_suffix_input.setStyleSheet(line_style)
        suffix_row.addWidget(self._rename_suffix_input, 1)
        suffix_row.addSpacing(20)
        col_pref_suf.addLayout(suffix_row)

        col_pref_suf.addStretch()
        right_wrap.addLayout(col_pref_suf, 2)

        right_wrap.addSpacing(10)
        right_wrap.addWidget(_separator("v"))
        right_wrap.addSpacing(30)

        col_right = QtWidgets.QVBoxLayout()
        col_right.setSpacing(6)

        col_right.addWidget(_section_label("Delimiter"))
        delim_inner = QtWidgets.QHBoxLayout()
        delim_lbl = QtWidgets.QLabel("Before frame:")
        delim_lbl.setStyleSheet("color:#a7a7a7;")
        delim_inner.addWidget(delim_lbl)
        self._rename_delim_combo = _ArrowComboBox()
        self._rename_delim_combo.setStyleSheet(self._COMBO_STYLE)
        self._rename_delim_combo.setView(QtWidgets.QListView())
        self._rename_delim_combo.addItems(["_", "."])
        self._rename_delim_combo.setFixedWidth(80)
        self._rename_delim_combo.setFocusPolicy(QtCore.Qt.NoFocus)
        delim_inner.addWidget(self._rename_delim_combo)
        delim_inner.addStretch()
        delim_inner.addSpacing(20)
        col_right.addLayout(delim_inner)

        col_right.addSpacing(8)

        col_right.addWidget(_section_label("Frame Number Digit"))
        pad_inner = QtWidgets.QHBoxLayout()
        pad_lbl = QtWidgets.QLabel("Digits:")
        pad_lbl.setStyleSheet("color:#a7a7a7;")
        pad_inner.addWidget(pad_lbl)
        self._rename_digits_spin = _ArrowSpinBox()
        self._rename_digits_spin.setRange(1, 12)
        self._rename_digits_spin.setValue(4)
        self._rename_digits_spin.setStyleSheet(_ArrowSpinBox._STYLE)
        self._rename_digits_spin.setFixedWidth(88)
        self._rename_digits_spin.setFocusPolicy(QtCore.Qt.NoFocus)
        pad_inner.addWidget(self._rename_digits_spin)
        pad_inner.addStretch()
        pad_inner.addSpacing(20)
        col_right.addLayout(pad_inner)

        col_right.addStretch()
        right_wrap.addLayout(col_right, 1)

        # Espacio para correr la columna 3 hacia la derecha
        right_wrap.addSpacing(10)

        # Separador vertical
        right_wrap.addWidget(_separator("v"))

        # Espacio entre el separador y el contenido de col_extra
        right_wrap.addSpacing(30)

        # Columna Preset
        col_extra = QtWidgets.QVBoxLayout()
        col_extra.setSpacing(12)

        # Fila Preset: label + dropdown
        preset_row = QtWidgets.QHBoxLayout()
        preset_row.setSpacing(6)
        preset_lbl = QtWidgets.QLabel("Preset:")
        preset_lbl.setStyleSheet("color:#a7a7a7;")
        preset_row.addWidget(preset_lbl)
        self._rename_preset_combo = _ArrowComboBox()
        self._rename_preset_combo.setStyleSheet(self._COMBO_STYLE)
        _pix_trash_r = QtGui.QPixmap(str(SHARED_DIR / "icons" / "trash.svg"))
        _pix_hover_r = QtGui.QPixmap(str(SHARED_DIR / "icons" / "trash_hover.svg"))
        _r_list = _RenamePresetListView(self._on_rename_preset_delete)
        self._rename_preset_combo.setView(_r_list)
        _r_list.setItemDelegate(_RenamePresetDelegate(_r_list, _pix_trash_r, _pix_hover_r))
        self._rename_preset_combo.setMinimumWidth(180)
        self._rename_preset_combo.setFocusPolicy(QtCore.Qt.NoFocus)
        preset_row.addWidget(self._rename_preset_combo, 1)
        col_extra.addLayout(preset_row)

        self._rename_save_preset_btn = QtWidgets.QPushButton("Save Preset")
        self._rename_save_preset_btn.setStyleSheet(_BTN_SMALL)
        self._rename_save_preset_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self._rename_save_preset_btn.clicked.connect(self._on_rename_save_preset_clicked)
        col_extra.addWidget(self._rename_save_preset_btn)

        self._rename_clear_defaults_btn = QtWidgets.QPushButton("Reset Values")
        self._rename_clear_defaults_btn.setStyleSheet(_BTN_SMALL)
        self._rename_clear_defaults_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self._rename_clear_defaults_btn.clicked.connect(self._reset_rename_to_defaults)
        col_extra.addWidget(self._rename_clear_defaults_btn)
        col_extra.addStretch()
        right_wrap.addLayout(col_extra, 0)

        # Espacio libre a la derecha de la columna Preset
        _RENAME_COL3_RIGHT_PADDING = 20
        right_wrap.addSpacing(_RENAME_COL3_RIGHT_PADDING)

        opts_row.addLayout(right_wrap, 5)

        layout.addLayout(opts_row)
        layout.addWidget(_separator())

        btn_row = QtWidgets.QHBoxLayout()
        _oq_btn, _status_lbl = self._make_footer_pair()
        btn_row.addWidget(_oq_btn)
        btn_row.addSpacing(8)
        btn_row.addWidget(_status_lbl, 1)
        self._apply_rename_btn = QtWidgets.QPushButton("Run Rename")
        self._apply_rename_btn.setStyleSheet(_BTN_PRIMARY)
        self._apply_rename_btn.setEnabled(False)
        self._apply_rename_btn.setFocusPolicy(QtCore.Qt.NoFocus)
        self._apply_rename_btn.clicked.connect(self._run_rename)
        btn_row.addWidget(self._apply_rename_btn)
        layout.addSpacing(_BTN_ROW_TOP_SPACING)
        layout.addLayout(btn_row)

        self._rename_checkboxes = {}
        self._rename_selected_rows = []
        self._rename_preview_rows = []
        self._rename_display_rows = []
        self._rename_applying_preset = False
        # Debounce del refresh de preview: evita correr compute_preview en cada
        # keystroke. Se reinicia en cada _on_rename_settings_changed y dispara
        # el refresh tras `_RENAME_REFRESH_DEBOUNCE_MS` ms de inactividad.
        self._rename_refresh_timer = QtCore.QTimer(self)
        self._rename_refresh_timer.setSingleShot(True)
        self._rename_refresh_timer.setInterval(_RENAME_REFRESH_DEBOUNCE_MS)
        self._rename_refresh_timer.timeout.connect(self._refresh_rename_preview)
        self._rename_presets = rename_settings_mod.load_rename_presets()
        self._rename_settings = rename_settings_mod.load_settings()
        self._load_rename_settings_to_ui()
        self._connect_rename_autosave()
        self._rebuild_rename_preset_combo()
        self._rename_preset_combo.currentIndexChanged.connect(
            self._on_rename_preset_combo_changed
        )
        # Tab cycle: sólo entre los 4 line edits de SR1/SR2 (excluye swap, case
        # sensitive, combos y botones, que ya tienen FocusPolicy = NoFocus).
        QtWidgets.QWidget.setTabOrder(self._rename_sr1_search,  self._rename_sr1_replace)
        QtWidgets.QWidget.setTabOrder(self._rename_sr1_replace, self._rename_sr2_search)
        QtWidgets.QWidget.setTabOrder(self._rename_sr2_search,  self._rename_sr2_replace)
        QtWidgets.QWidget.setTabOrder(self._rename_sr2_replace, self._rename_prefix_input)
        QtWidgets.QWidget.setTabOrder(self._rename_prefix_input, self._rename_suffix_input)
        QtWidgets.QWidget.setTabOrder(self._rename_suffix_input, self._rename_sr1_search)
        self._refresh_rename_preview()
        return page

    def _connect_rename_autosave(self):
        for _w, _sig in [
            (self._rename_sr1_search, "textChanged"),
            (self._rename_sr1_replace, "textChanged"),
            (self._rename_sr1_case, "stateChanged"),
            (self._rename_sr2_search, "textChanged"),
            (self._rename_sr2_replace, "textChanged"),
            (self._rename_sr2_case, "stateChanged"),
            (self._rename_prefix_input, "textChanged"),
            (self._rename_suffix_input, "textChanged"),
            (self._rename_delim_combo, "currentIndexChanged"),
            (self._rename_digits_spin, "valueChanged"),
        ]:
            getattr(_w, _sig).connect(self._on_rename_settings_changed)

    def _load_rename_settings_to_ui(self):
        s = self._rename_settings
        sr1 = s.get("sr1", {})
        sr2 = s.get("sr2", {})
        prefix = s.get("prefix", {})
        suffix = s.get("suffix", {})
        dm = s.get("delimiter", {})
        pd = s.get("padding", {})
        self._rename_sr1_search.setText(sr1.get("search", ""))
        self._rename_sr1_replace.setText(sr1.get("replace", ""))
        self._rename_sr1_case.setChecked(sr1.get("case_sensitive", "false").lower() == "true")
        self._rename_sr2_search.setText(sr2.get("search", ""))
        self._rename_sr2_replace.setText(sr2.get("replace", ""))
        self._rename_sr2_case.setChecked(sr2.get("case_sensitive", "false").lower() == "true")
        self._rename_prefix_input.setText(prefix.get("text", ""))
        self._rename_suffix_input.setText(suffix.get("text", ""))
        d = dm.get("char", "_")
        self._rename_delim_combo.setCurrentIndex(1 if d == "." else 0)
        try:
            self._rename_digits_spin.setValue(int(pd.get("digits", "4")))
        except Exception:
            self._rename_digits_spin.setValue(4)

    def _collect_rename_settings_from_ui(self):
        return {
            "sr1": {
                "search": self._rename_sr1_search.text(),
                "replace": self._rename_sr1_replace.text(),
                "case_sensitive": str(self._rename_sr1_case.isChecked()).lower(),
            },
            "sr2": {
                "search": self._rename_sr2_search.text(),
                "replace": self._rename_sr2_replace.text(),
                "case_sensitive": str(self._rename_sr2_case.isChecked()).lower(),
            },
            "prefix": {
                "text": self._rename_prefix_input.text(),
            },
            "suffix": {
                "text": self._rename_suffix_input.text(),
            },
            "delimiter": {
                "char": self._rename_delim_combo.currentText(),
            },
            "padding": {
                "digits": str(self._rename_digits_spin.value()),
            },
        }

    def _swap_sr(self, search_edit, replace_edit):
        a, b = search_edit.text(), replace_edit.text()
        search_edit.setText(b)
        replace_edit.setText(a)

    def _on_rename_settings_changed(self, *_):
        self._rename_settings = self._collect_rename_settings_from_ui()
        rename_settings_mod.save_settings(self._rename_settings)
        # Debounce: en vez de refrescar el preview en cada keystroke, reiniciamos
        # el timer single-shot. Si llega otra edición antes de que dispare, se
        # cancela y vuelve a empezar la cuenta. El refresh corre cuando el user
        # pausa de tipear `_RENAME_REFRESH_DEBOUNCE_MS` ms.
        self._rename_refresh_timer.start()
        if not self._rename_applying_preset:
            self._update_rename_preset_combo_selection()

    def _reset_rename_to_defaults(self):
        self._rename_sr1_search.setText("")
        self._rename_sr1_replace.setText("")
        self._rename_sr1_case.setChecked(False)
        self._rename_sr2_search.setText("")
        self._rename_sr2_replace.setText("")
        self._rename_sr2_case.setChecked(False)
        self._rename_prefix_input.setText("")
        self._rename_suffix_input.setText("")
        self._rename_delim_combo.setCurrentIndex(0)  # "_"
        self._rename_digits_spin.setValue(4)

    # ── Presets de rename ──────────────────────────────────────────────────────

    def _current_rename_preset_dict(self):
        """Snapshot de los 6 steps en formato preset (sin nombre)."""
        return {
            "sr1_search":  self._rename_sr1_search.text(),
            "sr1_replace": self._rename_sr1_replace.text(),
            "sr1_case":    "true" if self._rename_sr1_case.isChecked() else "false",
            "sr2_search":  self._rename_sr2_search.text(),
            "sr2_replace": self._rename_sr2_replace.text(),
            "sr2_case":    "true" if self._rename_sr2_case.isChecked() else "false",
            "prefix":      self._rename_prefix_input.text(),
            "suffix":      self._rename_suffix_input.text(),
            "delim":       self._rename_delim_combo.currentText(),
            "digits":      str(self._rename_digits_spin.value()),
        }

    def _rebuild_rename_preset_combo(self, force_select=None):
        """Reconstruye items del combo basado en self._rename_presets.

        - Sin presets: un único item "(sin presets)" y combo deshabilitado.
        - Con presets: lista los presets precedidos del placeholder virtual "----".
          Si force_select es un índice válido (0-based en self._rename_presets),
          selecciona ese preset; si no, selecciona "----".
        """
        combo = self._rename_preset_combo
        combo.blockSignals(True)
        combo.clear()
        if not self._rename_presets:
            combo.addItem(_RENAME_PRESET_PLACEHOLDER_EMPTY)
            combo.setEnabled(False)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
            return

        combo.setEnabled(True)
        combo.addItem(_RENAME_PRESET_PLACEHOLDER_NOMATCH)
        for p in self._rename_presets:
            combo.addItem(p.get("name", ""))

        if force_select is not None and 0 <= force_select < len(self._rename_presets):
            combo.setCurrentIndex(force_select + 1)  # +1 por el "----" en pos 0
        else:
            combo.setCurrentIndex(0)  # "----"
        combo.blockSignals(False)

    def _preset_matches_current(self, preset):
        cur = self._current_rename_preset_dict()
        for k in rename_settings_mod.PRESET_FIELDS:
            if str(preset.get(k, "")) != cur[k]:
                return False
        return True

    def _find_matching_rename_preset_index(self):
        """Devuelve el índice en self._rename_presets que matchea, o -1."""
        for i, p in enumerate(self._rename_presets):
            if self._preset_matches_current(p):
                return i
        return -1

    def _update_rename_preset_combo_selection(self):
        """Selecciona en el combo el preset que matchea con el estado actual de
        los 6 steps, o '----' si ninguno matchea. No hace nada si no hay
        presets cargados (combo en '(sin presets)' deshabilitado)."""
        if not self._rename_presets:
            return
        combo = self._rename_preset_combo
        match_idx = self._find_matching_rename_preset_index()
        target = (match_idx + 1) if match_idx >= 0 else 0  # +1 por '----' en pos 0
        if combo.currentIndex() == target:
            return
        combo.blockSignals(True)
        combo.setCurrentIndex(target)
        combo.blockSignals(False)

    def _on_rename_preset_combo_changed(self, idx):
        # idx 0 es el placeholder "----" (con presets) o "(sin presets)" (sin presets)
        if idx <= 0 or not self._rename_presets:
            return
        preset_idx = idx - 1  # los presets reales empiezan en 1
        if preset_idx >= len(self._rename_presets):
            return
        self._apply_rename_preset(self._rename_presets[preset_idx])

    def _apply_rename_preset(self, preset):
        """Setea los widgets desde el preset. Dispara autosave + refresh, pero el
        flag _rename_applying_preset evita que el combo se mueva a '----'."""
        self._rename_applying_preset = True
        try:
            self._rename_sr1_search.setText(preset.get("sr1_search", ""))
            self._rename_sr1_replace.setText(preset.get("sr1_replace", ""))
            self._rename_sr1_case.setChecked(
                str(preset.get("sr1_case", "false")).lower() == "true"
            )
            self._rename_sr2_search.setText(preset.get("sr2_search", ""))
            self._rename_sr2_replace.setText(preset.get("sr2_replace", ""))
            self._rename_sr2_case.setChecked(
                str(preset.get("sr2_case", "false")).lower() == "true"
            )
            self._rename_prefix_input.setText(preset.get("prefix", ""))
            self._rename_suffix_input.setText(preset.get("suffix", ""))
            d = preset.get("delim", "_")
            self._rename_delim_combo.setCurrentIndex(1 if d == "." else 0)
            try:
                self._rename_digits_spin.setValue(int(preset.get("digits", "4")))
            except Exception:
                self._rename_digits_spin.setValue(4)
        finally:
            self._rename_applying_preset = False

    def _on_rename_save_preset_clicked(self):
        name = rename_settings_mod.show_save_rename_preset_dialog(parent=self)
        if not name:
            return
        new_preset = {"name": name}
        new_preset.update(self._current_rename_preset_dict())
        self._rename_presets.append(new_preset)
        rename_settings_mod.save_rename_presets(self._rename_presets)
        # Reconstruir combo y seleccionar el preset recien agregado.
        self._rebuild_rename_preset_combo(
            force_select=len(self._rename_presets) - 1
        )

    def _on_rename_preset_delete(self, row):
        """Callback del trash icon del listview (row es el row del combo).

        Con presets cargados el row 0 es '----' (no deletable) y los presets
        reales empiezan en row 1. Tras borrar, el combo queda en '----'.
        """
        if not self._rename_presets:
            return
        preset_idx = row - 1
        if not 0 <= preset_idx < len(self._rename_presets):
            return
        del self._rename_presets[preset_idx]
        rename_settings_mod.save_rename_presets(self._rename_presets)
        self._rename_preset_combo.hidePopup()
        self._rebuild_rename_preset_combo()
        # Si el estado actual matchea otro preset que quedó, lo selecciona;
        # si no, queda el "----" que dejó _rebuild_rename_preset_combo.
        self._update_rename_preset_combo_selection()

    def _update_rename_page(self):
        debug_print(
            "_update_rename_page start publish=%d input=%d" % (
                len(getattr(self, "publish_items", []) or []),
                len(getattr(self, "input_items", []) or []),
            )
        )
        all_items = []
        for p in getattr(self, "publish_items", []):
            if p.get("has_versions"):
                item = dict(p)
                item["source"] = "publish"
                all_items.append(item)
        for inp in getattr(self, "input_items", []):
            if inp["kind"] == "exr_seq":
                item = dict(inp)
                item["source"] = "plates"
                all_items.append(item)
        for inp in getattr(self, "input_items", []):
            if inp["kind"] == "mov":
                item = dict(inp)
                item["source"] = "refs"
                all_items.append(item)
        self._rename_selected_rows = rename_mod.build_selected_rows(all_items)
        debug_print("_update_rename_page selected rows=%d" % len(self._rename_selected_rows))
        self._refresh_rename_preview()
        debug_print("_update_rename_page done")

    def _refresh_rename_preview(self):
        if not hasattr(self, "_rename_table"):
            debug_print("_refresh_rename_preview skipped: no _rename_table", level="warning")
            return
        debug_print("_refresh_rename_preview start")

        # Guardar estados de checkboxes actuales por item_path para preservarlos
        saved_chk_states = {}
        _old_display = getattr(self, "_rename_display_rows", [])
        _old_chk = getattr(self, "_rename_checkboxes", {})
        for _i, _chk in _old_chk.items():
            if _i < len(_old_display) and _old_display[_i].get("type") == "data":
                _pr = _old_display[_i]["preview_row"]
                saved_chk_states[_pr.get("item_path", "")] = _chk.isChecked()

        colors = {
            1: _CLR_COMP_DWAA,  # verde suave (antes amarillo, choca con step 4)
            2: _CLR_PAR,
            3: "#c678dd",
            4: "#e5c07b",
            5: _CLR_COMP,
            6: _CLR_FRAMES,
        }
        self._rename_preview_rows = rename_mod.compute_preview(
            getattr(self, "_rename_selected_rows", []),
            self._collect_rename_settings_from_ui() if hasattr(self, "_rename_sr1_search") else getattr(self, "_rename_settings", {}),
            colors,
            shot_name=self.shot_name,
            shotname_color=SHOTNAME_COLOR,
        )
        debug_print("_refresh_rename_preview computed rows=%d" % len(self._rename_preview_rows))

        # Construir display_rows: secciones intercaladas igual que la tabla principal
        _SECTION_META = {
            "publish": ("PUBLISH",    "#777777",  "#777777"),
            "plates":  ("PLATES",     _CLR_PLATES, "#6fc9d9"),
            "refs":    ("REFERENCES", _CLR_REFS,   _CLR_REFS),
        }
        _TASK_BAR_CLR = {
            "comp":    _CLR_COMP,
            "roto":    _CLR_ROTO,
            "cleanup": _CLR_CLEANUP,
            "dmp":     _CLR_DMP,
        }
        seen_sections = []
        display_rows = []
        for pr in self._rename_preview_rows:
            src = pr.get("source", "")
            if src not in seen_sections:
                seen_sections.append(src)
                label, color, text_color = _SECTION_META.get(src, (src.upper(), "#777777", "#777777"))
                display_rows.append({
                    "type": "section_header",
                    "label": label,
                    "color": color,
                    "text_color": text_color,
                    "source": src,
                })
            display_rows.append({"type": "data", "preview_row": pr})
        self._rename_display_rows = display_rows
        debug_print("_refresh_rename_preview display rows=%d" % len(display_rows))

        self._rename_table.clearSpans()
        self._rename_table.setRowCount(len(display_rows))
        self._rename_checkboxes = {}

        for i, dr in enumerate(display_rows):
            if dr["type"] == "section_header":
                self._populate_rename_section_header(i, dr)
                continue

            it = dr["preview_row"]
            blocked = it.get("blocked", False)

            # Barra de color según sección/tarea (nunca gris por blocked)
            src = it.get("source", "")
            if src == "publish":
                task = (it.get("item") or {}).get("task", "")
                bar_color = _TASK_BAR_CLR.get(task, _CLR_COMP)
            elif src == "refs":
                bar_color = _CLR_REFS
            else:
                bar_color = _CLR_PLATES
            bar = QtWidgets.QTableWidgetItem()
            bar.setBackground(QtGui.QColor(bar_color))
            bar.setFlags(QtCore.Qt.NoItemFlags)
            self._rename_table.setItem(i, 0, bar)

            # Estado inicial del checkbox: preservar si hay estado guardado, sino default
            item_path = it.get("item_path", "")
            if blocked:
                initial_checked = False
            elif item_path in saved_chk_states:
                initial_checked = saved_chk_states[item_path]
            else:
                initial_checked = True

            chk = QtWidgets.QCheckBox()
            chk.setStyleSheet("color:#a7a7a7; padding:2px;")
            chk.setChecked(initial_checked)  # antes de conectar la señal
            chk.setEnabled(not blocked)
            chk.stateChanged.connect(lambda _state, ri=i: self._on_rename_chk_changed(ri))
            chk.clicked.connect(lambda _checked=False, ri=i: self._on_rename_chk_clicked(ri))
            self._rename_checkboxes[i] = chk
            cbox = QtWidgets.QWidget()
            cl = QtWidgets.QHBoxLayout(cbox)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setAlignment(QtCore.Qt.AlignCenter)
            cl.addWidget(chk)
            self._rename_table.setCellWidget(i, 1, cbox)

            _dash = "<span style='color:#444444;'>—</span>"
            _plain = "<span style='color:#a7a7a7;'>%s</span>"
            # Col 2 (original): colores solo si checkbox activo; plano si no
            if blocked:
                orig_disp = _plain % _rn_escape(it.get("original_name", ""))
            elif initial_checked:
                orig_disp = it.get("original_html", "")
            else:
                orig_disp = _plain % _rn_escape(it.get("original_name", ""))
            self._rename_table.setCellWidget(i, 2, _cell_html_label(orig_disp))
            arrow = QtWidgets.QTableWidgetItem("➜")
            arrow.setForeground(QtGui.QColor("#444444" if blocked else "#666666"))
            arrow.setTextAlignment(QtCore.Qt.AlignCenter)
            self._rename_table.setItem(i, 3, arrow)

            if blocked:
                self._rename_table.setCellWidget(i, 4, _cell_html_label(_dash))
                self._rename_table.setCellWidget(i, 5, _cell_html_label(
                    _plain % _rn_escape(it.get("folder_name", ""))))
                self._rename_table.setCellWidget(i, 6, _cell_html_label(_dash))
                st_html = "<span style='color:%s;'>%s</span>" % (
                    _CLR_STATUS_UPSCALE, it.get("status", "Bloqueado"))
            elif initial_checked:
                self._rename_table.setCellWidget(
                    i, 4, _cell_html_label(it.get("renamed_html", "")))
                self._rename_table.setCellWidget(i, 5, _cell_html_label(it.get("folder_original_html", "")))
                self._rename_table.setCellWidget(
                    i, 6, _cell_html_label(it.get("folder_renamed_html", "")))
                st_color = _CLR_STATUS_PENDING
                st = it.get("status", "Pendiente")
                if not it.get("has_changes"):
                    st_color = "#888888"
                st_html = "<span style='color:%s;'>%s</span>" % (st_color, st)
            else:
                # Unchecked (estado guardado)
                self._rename_table.setCellWidget(i, 4, _cell_html_label(_dash))
                self._rename_table.setCellWidget(i, 5, _cell_html_label(
                    _plain % _rn_escape(it.get("folder_name", ""))))
                self._rename_table.setCellWidget(i, 6, _cell_html_label(_dash))
                st_html = _dash
            self._rename_table.setCellWidget(i, 7, _cell_html_label(st_html))

        self._update_rename_summary()
        self._update_rename_btn_state()
        debug_print("_refresh_rename_preview done")

    def _update_import_handle_label(self):
        """Actualiza el label de handle auto-calculado debajo de la tabla de import preview."""
        if not hasattr(self, "_import_handle_lbl"):
            return
        info = getattr(self, "_handle_info", {})
        if not info:
            self._import_handle_lbl.setText("")
            self._import_handle_lbl.setVisible(False)
            return

        parts = []
        for tname in sorted(info.keys()):
            h = info[tname]
            h_in  = h["handle_in"]
            h_out = h["handle_out"]
            if h["half_frame"]:
                text = (
                    '<span style="color:#888888">%s handle: </span>'
                    '<span style="color:#aa9e54">%d f</span>'
                    '<span style="color:#888888"> &nbsp;(in <b>%d</b> / out <b>%d</b>) &nbsp;</span>'
                    '<span style="color:#e08033">⚠ diferencia impar — handle asimétrico</span>'
                    % (tname, h_in, h_in, h_out)
                )
            else:
                text = (
                    '<span style="color:#888888">%s handle: </span>'
                    '<span style="color:#aa9e54">%d f</span>'
                    % (tname, h_in)
                )
            parts.append(text)

        separator = '<span style="color:#555555"> &nbsp;&nbsp;|&nbsp;&nbsp; </span>'
        self._import_handle_lbl.setText(
            "<html><body>" + separator.join(parts) + "</body></html>"
        )
        self._import_handle_lbl.setVisible(True)

    def _update_rename_summary(self):
        """Recalcula y actualiza el label de resumen de la tabla de rename."""
        blocked_n = 0
        checked_ok = 0
        display_rows = getattr(self, "_rename_display_rows", [])
        for i, dr in enumerate(display_rows):
            if dr.get("type") != "data":
                continue
            it = dr["preview_row"]
            if it.get("blocked"):
                blocked_n += 1
            else:
                chk = self._rename_checkboxes.get(i)
                if chk and chk.isChecked() and it.get("has_changes"):
                    checked_ok += 1
        if hasattr(self, "_rename_summary_lbl"):
            self._rename_summary_lbl.setText(
                "%d items · %d listos para rename · %d bloqueados" % (
                    len(getattr(self, "_rename_preview_rows", [])), checked_ok, blocked_n
                )
            )

    def _update_rename_btn_state(self):
        ready = False
        display_rows = getattr(self, "_rename_display_rows", [])
        for i, chk in self._rename_checkboxes.items():
            if not chk.isEnabled() or not chk.isChecked():
                continue
            if i < len(display_rows):
                dr = display_rows[i]
                if dr.get("type") == "data" and dr["preview_row"].get("has_changes"):
                    ready = True
                    break
        self._apply_rename_btn.setEnabled(ready)
        self._apply_rename_btn.setToolTip("" if ready else "No hay filas válidas con cambios")

    def _run_rename(self):
        # Si hay un refresh debounceado pendiente, flushearlo ahora para que la
        # tabla esté sincronizada con los settings actuales antes de ejecutar.
        if (hasattr(self, "_rename_refresh_timer")
                and self._rename_refresh_timer.isActive()):
            self._rename_refresh_timer.stop()
            self._refresh_rename_preview()

        to_apply = []
        display_rows = getattr(self, "_rename_display_rows", [])
        for i, chk in self._rename_checkboxes.items():
            if not chk.isEnabled() or not chk.isChecked():
                continue
            if i < len(display_rows):
                dr = display_rows[i]
                if dr.get("type") != "data":
                    continue
                row = dr["preview_row"]
                if row.get("blocked") or not row.get("has_changes"):
                    continue
                to_apply.append(row)

        # Guardar estado de checkboxes ANTES de ejecutar para restaurarlos después
        saved_chk = {
            idx: chk.isChecked()
            for idx, chk in self._rename_checkboxes.items()
        }

        # Construir mapping old_path → new_path para actualizar self._table_rows tras éxito
        old_to_new = {}
        for pr in to_apply:
            old_path = pr.get("item_path") or pr.get("folder_path", "")
            if pr.get("is_sequence"):
                new_folder = str(Path(pr["folder_path"]).parent / pr["target_folder_name"])
                old_to_new[os.path.normcase(os.path.normpath(old_path))] = {
                    "new_path": new_folder,
                    "new_name": pr["target_folder_name"],
                    "is_sequence": True,
                }
            else:
                new_file = str(Path(pr["item_path"]).with_name(pr["renamed_name"]))
                old_to_new[os.path.normcase(os.path.normpath(old_path))] = {
                    "new_path": new_file,
                    "new_name": pr["renamed_name"],
                    "is_sequence": False,
                }

        if Rename_Test_mode:
            QtWidgets.QMessageBox.information(
                self,
                "Rename Test Mode",
                "Rename_Test_mode está activo.\n"
                "Se creará la carpeta 'renamned' en paralelo y se renombrará SOLO sobre la copia.",
            )
        result = rename_mod.execute_ops(
            to_apply,
            test_mode=Rename_Test_mode,
            test_folder_name="renamned",
            log_fn=debug_print,
        )
        if result.get("errors"):
            QtWidgets.QMessageBox.warning(
                self,
                "Rename",
                "Se produjo un error durante el rename:\n%s" % "\n".join(result["errors"]),
            )
            return
        applied = int(result.get("applied", 0))
        if applied > 0:
            self._needs_refresh.update({"transcode", "import"})

            # Actualizar rutas en self._table_rows para reflejar los items renombrados
            for row_data in self._table_rows:
                if row_data.get("type") != "data":
                    continue
                item = row_data["item"]
                item_path_norm = os.path.normcase(os.path.normpath(str(item.get("path", ""))))
                if item_path_norm in old_to_new:
                    mapping = old_to_new[item_path_norm]
                    item["path"] = mapping["new_path"]
                    item["name"] = mapping["new_name"]
                    if mapping["is_sequence"]:
                        try:
                            new_folder_p = Path(mapping["new_path"])
                            if new_folder_p.exists():
                                exr_files = sorted(
                                    f for f in new_folder_p.iterdir()
                                    if f.is_file() and f.suffix.lower() == ".exr"
                                )
                                if exr_files:
                                    item["first_file"] = str(exr_files[0])
                        except Exception:
                            pass
                    else:
                        item["first_file"] = mapping["new_path"]

            self._update_rename_page()

        self._refresh_rename_preview()

        # Marcar con estado de éxito los items renombrados
        if applied > 0:
            renamed_new_paths = {
                os.path.normcase(os.path.normpath(v["new_path"]))
                for v in old_to_new.values()
            }
            for i, dr in enumerate(self._rename_display_rows):
                if dr.get("type") != "data":
                    continue
                pr = dr["preview_row"]
                item_path_norm = os.path.normcase(os.path.normpath(pr.get("item_path", "")))
                if item_path_norm in renamed_new_paths:
                    st_html = "<span style='color:%s;'>✓ Renombrado</span>" % _CLR_STATUS_DONE
                    self._rename_table.setCellWidget(i, 7, _cell_html_label(st_html))

        # Restaurar estados de checkboxes tal como estaban antes del rename
        for idx, was_checked in saved_chk.items():
            if idx in self._rename_checkboxes:
                chk = self._rename_checkboxes[idx]
                if chk.isEnabled() and chk.isChecked() != was_checked:
                    chk.setChecked(was_checked)

    # ══════════════════════════════════════════════════════════
    #  PAGINA: Transcode Plates
    # ══════════════════════════════════════════════════════════

    # Presets de resolución: label ➜ (W, H) o None (original)
    _COMBO_STYLE = (
        "QComboBox { background-color:#272727; border:1px solid #444; "
        "color:#a7a7a7; padding:3px 6px; }"
        "QComboBox::drop-down { border:0px; width:18px; }"
        "QComboBox::down-arrow { image:none; width:0px; height:0px; }"
        "QComboBox QAbstractItemView { background-color:#2B2B2B; color:#a7a7a7; "
        "selection-background-color:#272727; selection-color:#a7a7a7; outline:0; }"
    )

    _SPIN_STYLE = """
        QSpinBox, QDoubleSpinBox {
            background-color: #272727; border: 1px solid #444;
            color: #a7a7a7; padding: 2px 20px 2px 4px;
        }
        QSpinBox::up-button, QDoubleSpinBox::up-button {
            subcontrol-origin: border; subcontrol-position: top right;
            width: 18px; border-left: 1px solid #444;
            background-color: #2e2e2e;
        }
        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover {
            background-color: #3a3a3a;
        }
        QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-bottom: 4px solid #888;
            width: 0px; height: 0px;
        }
        QSpinBox::down-button, QDoubleSpinBox::down-button {
            subcontrol-origin: border; subcontrol-position: bottom right;
            width: 18px; border-left: 1px solid #444;
            background-color: #2e2e2e;
        }
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {
            background-color: #3a3a3a;
        }
        QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 4px solid #888;
            width: 0px; height: 0px;
        }
    """

    def _build_page_convert(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(8)

        # Tabla de plates a transcodear
        # col 0: barra color (10px)  col 1: checkbox (28px)
        # col 2: Nombre  col 3: Origen  col 4: ➜  col 5: Destino  col 6: Tamaño  col 7: Estado
        self._convert_table = QtWidgets.QTableWidget()
        self._convert_table.setColumnCount(8)
        self._convert_table.setHorizontalHeaderLabels(
            ["", "", "Nombre", "Origen", "➜", "Destino", "Tamaño", "Estado"]
        )
        self._convert_table.verticalHeader().setVisible(False)
        self._convert_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self._convert_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._convert_table.setFocusPolicy(QtCore.Qt.NoFocus)
        self._convert_table.setShowGrid(False)
        self._convert_table.setStyleSheet(_TABLE_STYLE)
        self._convert_table.setMinimumHeight(120)
        self._convert_table.setMaximumHeight(220)
        hdr = self._convert_table.horizontalHeader()
        hdr.setMinimumSectionSize(1)
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        self._convert_table.setColumnWidth(0, 5)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        self._convert_table.setColumnWidth(1, 28)
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        # Origen (col 3) — 400px para "4096×2160 (2.39:1) (2) · 16b · RGB · dwaa · 480f - 20.0s"
        hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.Interactive)
        self._convert_table.setColumnWidth(3, 400)
        # Flecha (col 4)
        hdr.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)
        # Destino (col 5) — mínimo 320px para "2048×858 (2.39:1) · half · RGB · dwaa"
        hdr.setSectionResizeMode(5, QtWidgets.QHeaderView.Interactive)
        self._convert_table.setColumnWidth(5, 320)
        # Tamaño — ajusta al contenido; Estado — ancho fijo para caber barra de progreso
        hdr.setSectionResizeMode(6, QtWidgets.QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(7, QtWidgets.QHeaderView.Interactive)
        self._convert_table.setColumnWidth(7, 130)
        self._convert_checkboxes = {}
        self._convert_table.cellClicked.connect(self._on_convert_row_clicked)
        self._convert_table.cellDoubleClicked.connect(self._on_convert_row_double_clicked)
        layout.addWidget(self._convert_table)

        layout.addWidget(_separator())

        # ── Opciones en 2 columnas ─────────────────────────────────
        opts_row = QtWidgets.QHBoxLayout()
        opts_row.setSpacing(20)

        # Columna izquierda — Codec / Calidad
        col_codec = QtWidgets.QVBoxLayout()
        col_codec.setSpacing(6)
        col_codec.addWidget(_section_label("Codec / Calidad"))

        dwaa_option_row = QtWidgets.QHBoxLayout()
        dwaa_option_row.setSpacing(8)
        self._convert_dwaa_chk = QtWidgets.QCheckBox("Convertir a DWAA")
        self._convert_dwaa_chk.setChecked(True)
        self._convert_dwaa_chk.setStyleSheet("color:#a7a7a7; padding:2px;")
        self._convert_dwaa_chk.stateChanged.connect(self._on_dwaa_chk_changed)
        dwaa_option_row.addWidget(self._convert_dwaa_chk)
        self._convert_dwaa_level_lbl = QtWidgets.QLabel(
            "compression %d" % _DWAA_COMPRESSION_LEVEL
        )
        self._convert_dwaa_level_lbl.setStyleSheet("color:#666666; padding:2px;")
        dwaa_option_row.addWidget(self._convert_dwaa_level_lbl)
        dwaa_option_row.addStretch()
        col_codec.addLayout(dwaa_option_row)

        ch_row = QtWidgets.QHBoxLayout()
        ch_lbl = QtWidgets.QLabel("Channels:")
        ch_lbl.setStyleSheet("color:#a7a7a7;")
        ch_row.addWidget(ch_lbl)
        self._convert_channels = _ArrowComboBox()
        self._convert_channels.setStyleSheet(self._COMBO_STYLE)
        self._convert_channels.setView(QtWidgets.QListView())
        for opt in ("Mantener", "Reducir a RGB"):
            self._convert_channels.addItem(opt)
        self._convert_channels.setFixedWidth(170)
        self._convert_channels.currentIndexChanged.connect(
            lambda *_: self._refresh_convert_destinos()
        )
        ch_row.addWidget(self._convert_channels)
        ch_row.addStretch()
        col_codec.addLayout(ch_row)

        col_codec.addStretch()
        opts_row.addLayout(col_codec, 1)

        # Separador vertical
        opts_row.addWidget(_separator("v"))

        # Columna derecha — Resolución
        col_res = QtWidgets.QVBoxLayout()
        col_res.setSpacing(6)
        col_res.addWidget(_section_label("Resolución"))

        res_row = QtWidgets.QHBoxLayout()
        res_lbl = QtWidgets.QLabel("Destino:")
        res_lbl.setStyleSheet("color:#a7a7a7;")
        res_row.addWidget(res_lbl)
        self._res_combo = _ArrowComboBox()
        self._res_combo.setStyleSheet(self._COMBO_STYLE)
        _pix_trash = QtGui.QPixmap(str(SHARED_DIR / "icons" / "trash.svg"))
        _pix_hover = QtGui.QPixmap(str(SHARED_DIR / "icons" / "trash_hover.svg"))
        _res_list = _ResPresetListView(self._on_delete_preset)
        self._res_combo.setView(_res_list)
        _res_list.setItemDelegate(_ResPresetDelegate(_res_list, _pix_trash, _pix_hover))
        for label, preset in self._res_presets:
            if preset and preset not in ("custom", "timeline"):
                tw, th = preset
                ar = _ar_str(tw, th)
                display = ("%s  [%s]" % (label, ar)) if ar else label
            else:
                display = label
            self._res_combo.addItem(display)
        self._res_combo.currentIndexChanged.connect(self._on_res_preset_changed)
        self._res_combo.setMinimumWidth(260)
        res_row.addWidget(self._res_combo)
        res_row.addStretch()
        col_res.addLayout(res_row)

        # Custom W × H (oculto salvo Custom) — usa _ArrowSpinBox (solución ganadora)
        self._custom_res_widget = QtWidgets.QWidget()
        cr_row = QtWidgets.QHBoxLayout(self._custom_res_widget)
        cr_row.setContentsMargins(0, 0, 0, 0)
        self._convert_custom_w = _ArrowSpinBox()
        self._convert_custom_w.setRange(1, 16384)
        self._convert_custom_w.setValue(2048)
        self._convert_custom_w.setStyleSheet(_ArrowSpinBox._STYLE)
        self._convert_custom_w.setFixedWidth(88)
        self._convert_custom_h = _ArrowSpinBox()
        self._convert_custom_h.setRange(1, 16384)
        self._convert_custom_h.setValue(1152)
        self._convert_custom_h.setStyleSheet(_ArrowSpinBox._STYLE)
        self._convert_custom_h.setFixedWidth(88)
        x_lbl = QtWidgets.QLabel("×")
        x_lbl.setStyleSheet("color:#a7a7a7;")
        self._save_preset_btn = QtWidgets.QPushButton("Save preset")
        self._save_preset_btn.setStyleSheet(_BTN_SMALL)
        self._save_preset_btn.setFixedHeight(24)
        self._save_preset_btn.setToolTip("Guardar esta resolución como preset")
        self._save_preset_btn.clicked.connect(self._on_save_preset_clicked)
        cr_row.addWidget(self._convert_custom_w)
        cr_row.addWidget(x_lbl)
        cr_row.addWidget(self._convert_custom_h)
        cr_row.addSpacing(8)
        cr_row.addWidget(self._save_preset_btn)
        cr_row.addStretch()
        self._custom_res_widget.hide()
        col_res.addWidget(self._custom_res_widget)
        self._convert_custom_w.valueChanged.connect(self._on_custom_w_changed)
        self._convert_custom_h.valueChanged.connect(self._on_custom_h_changed)

        # Preserve aspect ratio + Dimensión que manda (misma fila)
        keep_ar_row_widget = QtWidgets.QWidget()
        keep_ar_row = QtWidgets.QHBoxLayout(keep_ar_row_widget)
        keep_ar_row.setContentsMargins(0, 0, 0, 0)
        keep_ar_row.setSpacing(8)
        self._convert_keep_ar = QtWidgets.QCheckBox("Preserve aspect ratio")
        self._convert_keep_ar.setChecked(True)
        self._convert_keep_ar.setStyleSheet("color:#a7a7a7; padding:2px;")
        self._convert_keep_ar.stateChanged.connect(self._on_keep_ar_changed)
        keep_ar_row.addWidget(self._convert_keep_ar)

        self._match_dim_widget = QtWidgets.QWidget()
        md_row = QtWidgets.QHBoxLayout(self._match_dim_widget)
        md_row.setContentsMargins(0, 0, 0, 0)
        md_row.setSpacing(6)
        md_lbl = QtWidgets.QLabel("|  Dimensión que manda:")
        md_lbl.setStyleSheet("color:#a7a7a7;")
        md_row.addWidget(md_lbl)
        self._convert_match_dim = _ArrowComboBox()
        self._convert_match_dim.setStyleSheet(self._COMBO_STYLE)
        self._convert_match_dim.setView(QtWidgets.QListView())
        for opt in ("Match target width", "Match target height"):
            self._convert_match_dim.addItem(opt)
        self._convert_match_dim.setFixedWidth(180)
        self._convert_match_dim.currentIndexChanged.connect(self._on_match_dim_changed)
        md_row.addWidget(self._convert_match_dim)
        keep_ar_row.addWidget(self._match_dim_widget)
        keep_ar_row.addStretch()
        col_res.addWidget(keep_ar_row_widget)
        self._keep_ar_prev_state = self._convert_keep_ar.isChecked()

        # Desanamorfizar (PAR fuente inline, a la derecha del checkbox)
        deana_main_row = QtWidgets.QHBoxLayout()
        deana_main_row.setContentsMargins(0, 0, 0, 0)
        deana_main_row.setSpacing(8)
        self._convert_deana_chk = QtWidgets.QCheckBox("Desanamorfizar (Pixel Aspect Ratio)")
        self._convert_deana_chk.setChecked(False)
        self._convert_deana_chk.setStyleSheet("color:#a7a7a7; padding:2px;")
        self._convert_deana_chk.stateChanged.connect(self._on_deana_chk_changed)
        deana_main_row.addWidget(self._convert_deana_chk)
        self._deana_par_widget = QtWidgets.QWidget()
        deana_row = QtWidgets.QHBoxLayout(self._deana_par_widget)
        deana_row.setContentsMargins(0, 0, 0, 0)
        deana_row.setSpacing(6)
        deana_lbl = QtWidgets.QLabel("|  PAR fuente:")
        deana_lbl.setStyleSheet("color:#a7a7a7;")
        deana_row.addWidget(deana_lbl)
        self._convert_deana_par = _ArrowComboBox()
        self._convert_deana_par.setStyleSheet(self._COMBO_STYLE)
        self._convert_deana_par.setView(QtWidgets.QListView())
        for opt in ("1.3", "1.5", "1.8", "2.0"):
            self._convert_deana_par.addItem(opt)
        self._convert_deana_par.setFixedWidth(80)
        self._convert_deana_par.currentIndexChanged.connect(
            lambda *_: self._refresh_convert_destinos()
        )
        deana_row.addWidget(self._convert_deana_par)
        self._deana_par_widget.hide()
        deana_main_row.addWidget(self._deana_par_widget)
        deana_main_row.addStretch()
        col_res.addLayout(deana_main_row)

        # Dimensiones pares (opción recomendada para evitar incompatibilidades)
        self._convert_even_dims_chk = QtWidgets.QCheckBox("Forzar dimensiones pares (recomendado)")
        self._convert_even_dims_chk.setChecked(True)
        self._convert_even_dims_chk.setStyleSheet("color:#a7a7a7; padding:2px;")
        self._convert_even_dims_chk.setToolTip(
            "Si el resultado queda con ancho o alto impar, resta 1 px en esa dimensión."
        )
        self._convert_even_dims_chk.stateChanged.connect(
            lambda *_: self._refresh_convert_destinos()
        )
        col_res.addWidget(self._convert_even_dims_chk)

        flt_row = QtWidgets.QHBoxLayout()
        flt_lbl = QtWidgets.QLabel("Filtro resampling:")
        flt_lbl.setStyleSheet("color:#a7a7a7;")
        flt_row.addWidget(flt_lbl)
        self._convert_filter = _ArrowComboBox()
        self._convert_filter.setStyleSheet(self._COMBO_STYLE)
        self._convert_filter.setView(QtWidgets.QListView())
        for opt in ("lanczos3", "cubic", "box"):
            self._convert_filter.addItem(opt)
        self._convert_filter.setFixedWidth(150)
        flt_row.addWidget(self._convert_filter)
        flt_row.addStretch()
        col_res.addLayout(flt_row)

        col_res.addStretch()
        opts_row.addLayout(col_res, 1)

        layout.addLayout(opts_row)

        layout.addWidget(_separator())

        # Manejo de originales
        orig_lbl = _section_label("Manejo de originales")
        layout.addWidget(orig_lbl)

        # Aviso de test mode
        if Transcode_TEST_Mode:
            test_warn = QtWidgets.QLabel(
                "🧪  TEST MODE — el output va a {seq}/test_transcode/. "
                "Los originales no se mueven."
            )
            test_warn.setStyleSheet(
                "color:#d9a441; font-style:italic; padding:4px 0px;"
            )
            test_warn.setWordWrap(True)
            layout.addWidget(test_warn)

        self._delete_originals_chk = QtWidgets.QCheckBox("Borrar /Originals al terminar")
        self._delete_originals_chk.setChecked(False)
        self._delete_originals_chk.setEnabled(not Transcode_TEST_Mode)
        self._delete_originals_chk.setStyleSheet("color:#a7a7a7; padding:2px;")
        self._delete_originals_chk.setToolTip(
            "Los originales siempre se mueven a _input/Originals/<plate>/ antes del transcode.\n"
            "Activa para borrarlos automáticamente al terminar."
        )
        layout.addWidget(self._delete_originals_chk)

        # Resumen (totales sin estimaciones)
        layout.addWidget(_separator())
        self._convert_summary_lbl = QtWidgets.QLabel("")
        self._convert_summary_lbl.setStyleSheet(
            "color:#cccccc; padding:4px 0px; font-weight:bold;"
        )
        layout.addWidget(self._convert_summary_lbl)

        layout.addStretch()

        # Log panel (3 líneas, expandible)
        layout.addWidget(_separator())
        log_row = QtWidgets.QHBoxLayout()
        self._convert_log = QtWidgets.QPlainTextEdit()
        self._convert_log.setReadOnly(True)
        self._convert_log.setMaximumHeight(60)
        self._convert_log.setStyleSheet(
            "background:#1e1e1e; border:1px solid #333; color:#888888; padding:3px;"
        )
        log_row.addWidget(self._convert_log, 1)
        self._log_expand_btn = QtWidgets.QPushButton("▲")
        self._log_expand_btn.setFixedSize(24, 24)
        self._log_expand_btn.setStyleSheet(
            "background:#333; border:1px solid #555; color:#aaa; border-radius:3px;"
        )
        self._log_expand_btn.setToolTip("Expandir log")
        self._log_expand_btn.clicked.connect(self._toggle_convert_log)
        self._log_expanded = False
        log_row.addWidget(self._log_expand_btn, 0, QtCore.Qt.AlignBottom)
        layout.addLayout(log_row)

        # Botones
        btn_row = QtWidgets.QHBoxLayout()
        _oq_btn, _status_lbl = self._make_footer_pair()
        btn_row.addWidget(_oq_btn)
        btn_row.addSpacing(8)
        btn_row.addWidget(_status_lbl, 1)
        self._start_transcode_btn = QtWidgets.QPushButton("Start Transcode")
        self._start_transcode_btn.setStyleSheet(_BTN_PRIMARY)
        self._start_transcode_btn.setEnabled(False)
        self._start_transcode_btn.setToolTip("Selecciona al menos un EXR")
        self._start_transcode_btn.clicked.connect(self._run_transcode)
        btn_row.addWidget(self._start_transcode_btn)
        layout.addSpacing(_BTN_ROW_TOP_SPACING)
        layout.addLayout(btn_row)

        # Aplicar settings guardados (después de que todos los widgets existen)
        self._load_settings_to_ui()

        # Conectar auto-guardado DESPUÉS de cargar (para no disparar saves innecesarios)
        for _w, _sig in [
            (self._convert_dwaa_chk,     "stateChanged"),
            (self._convert_channels,     "currentIndexChanged"),
            (self._convert_filter,       "currentIndexChanged"),
            (self._res_combo,            "currentIndexChanged"),
            (self._convert_custom_w,     "valueChanged"),
            (self._convert_custom_h,     "valueChanged"),
            (self._convert_keep_ar,      "stateChanged"),
            (self._convert_match_dim,    "currentIndexChanged"),
            (self._convert_deana_chk,    "stateChanged"),
            (self._convert_deana_par,    "currentIndexChanged"),
            (self._convert_even_dims_chk, "stateChanged"),
            (self._delete_originals_chk, "stateChanged"),
        ]:
            getattr(_w, _sig).connect(self._save_all_settings)

        return page

    # ══════════════════════════════════════════════════════════════
    #  PÁGINA: Import Preview (sub-vista del tab Import)
    # ══════════════════════════════════════════════════════════════

    def _build_import_preview(self):
        # Aplicar stylesheet de tooltips a la QApplication (una sola vez es suficiente)
        apply_tooltip_ss(QtWidgets.QApplication.instance())

        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setSpacing(8)

        # Tabla timeline
        # col 0: barra de color (10 px fijo)
        # col 1: track name   (130 px fijo)
        # col 2: Shot Anterior  — eje temporal del shot previo (stretch igual)
        # col 3: Shot Nuevo     — eje temporal del shot importado (stretch igual)
        # col 4: Shot Siguiente — eje temporal del shot siguiente (stretch igual)
        self._import_table = QtWidgets.QTableWidget()
        self._import_table.setColumnCount(5)
        self._import_table.setHorizontalHeaderLabels(
            ["", "Track", "Shot Anterior", "Shot Nuevo", "Shot Siguiente"]
        )
        self._import_table.verticalHeader().setVisible(False)
        self._import_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self._import_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self._import_table.setFocusPolicy(QtCore.Qt.NoFocus)
        self._import_table.setShowGrid(False)
        self._import_table.setAlternatingRowColors(False)
        self._import_table.setStyleSheet(_TABLE_STYLE + """
            QHeaderView::section:nth-child(4) { color: #9080cc; }
        """)
        self._import_table.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )

        hdr = self._import_table.horizontalHeader()
        hdr.setMinimumSectionSize(1)
        hdr.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        self._import_table.setColumnWidth(0, 5)
        hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        self._import_table.setColumnWidth(1, 130)
        hdr.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)
        hdr.setSectionResizeMode(4, QtWidgets.QHeaderView.Stretch)

        layout.addWidget(self._import_table, 1)

        self._import_handle_lbl = QtWidgets.QLabel("")
        self._import_handle_lbl.setTextFormat(QtCore.Qt.RichText)
        self._import_handle_lbl.setWordWrap(True)
        self._import_handle_lbl.setStyleSheet("padding:3px 6px; background: transparent;")
        self._import_handle_lbl.setVisible(False)
        layout.addWidget(self._import_handle_lbl)

        layout.addWidget(_separator())
        layout.addSpacing(_BTN_ROW_TOP_SPACING)

        # Fila de botones
        btn_row = QtWidgets.QHBoxLayout()
        _oq_btn, _status_lbl = self._make_footer_pair()
        btn_row.addWidget(_oq_btn)
        btn_row.addSpacing(8)
        btn_row.addWidget(_status_lbl, 1)

        self._preview_back_btn = QtWidgets.QPushButton("← Go Back")
        self._preview_back_btn.setStyleSheet(_BTN_SECONDARY)
        self._preview_back_btn.clicked.connect(
            lambda: self._import_inner_stack.setCurrentIndex(self.IMPORT_MAIN)
        )
        btn_row.addWidget(self._preview_back_btn)

        btn_row.addSpacing(6)

        self._preview_import_now_btn = QtWidgets.QPushButton("Import Now")
        self._preview_import_now_btn.setStyleSheet(_BTN_PRIMARY)
        self._preview_import_now_btn.setToolTip("Importar al bin y colocar en el timeline")
        self._preview_import_now_btn.clicked.connect(self._do_import)
        btn_row.addWidget(self._preview_import_now_btn)

        btn_row.addSpacing(6)

        self._preview_import_v000_btn = QtWidgets.QPushButton("Import and Create V000")
        self._preview_import_v000_btn.setStyleSheet(_BTN_PRIMARY)
        self._preview_import_v000_btn.setToolTip(
            "Importar al timeline y abrir Create V000 al terminar"
        )
        self._preview_import_v000_btn.clicked.connect(self._do_import_and_v000)
        btn_row.addWidget(self._preview_import_v000_btn)

        layout.addLayout(btn_row)

        return page

    def _track_bar_color(self, track_type: str) -> str:
        """Devuelve el color de la barra izquierda según el tipo de track."""
        return {
            "plate":   _CLR_PLATES,
            "editref": _CLR_REFS,
            "comp":    _CLR_COMP,
            "roto":    _CLR_ROTO,
            "cleanup": _CLR_CLEANUP,
        }.get(track_type, "#555555")

    def _item_section_color(self, row_data: dict) -> str:
        """Devuelve el color de barra correspondiente al ítem según su sección."""
        section = row_data.get("section", "")
        if section == "plates":
            return _CLR_PLATES
        if section == "refs":
            return _CLR_REFS
        if section == "publish":
            task = row_data.get("item", {}).get("task", "")
            return _TASK_ROW_COLORS.get(task, "#777777")
        return "#555555"

    @staticmethod
    def _fmt_duration(frame_count) -> str:
        """Formatea frame_count como '480f' o '' si es None/0."""
        try:
            fc = int(frame_count)
            return "%df" % fc if fc > 0 else ""
        except (TypeError, ValueError):
            return ""

    @staticmethod
    def _is_burnin_track(name: str) -> bool:
        """True si el nombre del track es 'burnin' (normalizado, sin importar mayúsculas)."""
        return name.strip().lower().replace(" ", "").replace("_", "") == "burnin"

    @staticmethod
    def _chip_color(clip_name: str, bar_color: str, track_type: str) -> str:
        """
        Devuelve el color del chip.

        Regla v000: si el clip pertenece a un track comp/roto/cleanup y su nombre
        contiene una versión v000, v00, v0000, etc., el color es #474747 (gris oscuro).
        Esto indica que es una versión cero/base, aún no trabajada.
        """
        if track_type in ("comp", "roto", "cleanup"):
            if re.search(r'[._]v0{2,}(?:\b|_|$)', clip_name, re.IGNORECASE):
                return "#474747"
        return bar_color

    def _build_burnin_row(self) -> QtWidgets.QWidget:
        """
        Widget que ocupa las 3 columnas del track BurnIn.

        Muestra 3 tiras horizontales delgadas (#c0c0c0) con mini-padding entre ellas,
        que en total suman la misma altura que una fila normal de clips.
        Representa gráficamente el burn-in gráfico que cubre todo el timeline.
        Sin tooltips ni interacción.
        """
        COLOR = "#c0c0c0"
        w  = QtWidgets.QWidget()
        lo = QtWidgets.QVBoxLayout(w)
        lo.setContentsMargins(4, 4, 4, 4)
        lo.setSpacing(3)
        w.setStyleSheet("background: transparent;")
        for _ in range(3):
            bar = QtWidgets.QWidget()
            bar.setStyleSheet(
                "background: %s; border-radius: 2px;" % COLOR
            )
            bar.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding,
            )
            lo.addWidget(bar)
        return w

    def _make_chip_label(
        self,
        text: str,
        color: str = "#555555",
        is_new: bool = False,
        duration_text: str = "",
        frames: int = 0,
        fps: float = 24.0,
    ) -> QtWidgets.QLabel:
        """
        Devuelve un QLabel estilizado como bloque de clip de timeline.

        - El texto del chip es SOLO el nombre (sin duración).
        - La duración y segundos se muestran en el tooltip.
        - El chip puede shrinkear por debajo de su sizeHint: el texto se cropea.
        - Los clips "new" (a importar) llevan texto en bold; los de contexto en normal.
        - Todos los chips usan el mismo color derivado del track (is_new solo cambia bold).

        Args:
            text:          Nombre del clip (puede cropearse si el chip es muy angosto).
            color:         Color del track (hex).
            is_new:        True para clips a importar (bold), False para contexto.
            duration_text: Ignorado — se usa "frames" para el tooltip.
            frames:        Duración en frames (para tooltip).
            fps:           FPS del proyecto (para convertir a segundos en tooltip).
        """
        _BASE  = "#1a1a1a"
        bg     = mix_colors(color, _BASE, 0.35)
        border = color
        clr    = mix_colors(color, "#ffffff", 0.75)
        weight = "bold" if is_new else "normal"

        lbl = QtWidgets.QLabel(text)
        lbl.setTextFormat(QtCore.Qt.PlainText)
        lbl.setStyleSheet(
            "background: %s; border: 1px solid %s; color: %s; "
            "font-weight: %s; padding: 4px 6px; border-radius: 3px;"
            % (bg, border, clr, weight)
        )
        # Permitir que el chip shrinkee por debajo de su sizeHint:
        # el texto se cropea naturalmente (Qt alinea a la izquierda y corta).
        lbl.setMinimumWidth(1)
        lbl.setSizePolicy(
            QtWidgets.QSizePolicy.Ignored,   # ignora sizeHint horizontal
            QtWidgets.QSizePolicy.Preferred,
        )
        # Tooltip con nombre completo, frames y segundos
        if frames > 0:
            set_clip_tooltip(lbl, text, frames, fps=fps, color=color)
        return lbl

    def _build_before_cell(
        self, before_clip, bar_color: str,
        shot_start: int, shot_dur: int,
        track_type: str = "other",
    ) -> QtWidgets.QWidget:
        """
        Celda de Shot Anterior.

        shot_start  = tl_in mínimo entre todos los before clips del timeline.
        shot_dur    = duración total del shot anterior (max_tl_out − shot_start + 1).

        El clip más largo llena el 100 % de la celda.
        Clips más cortos o desplazados se posicionan con offset y ancho proporcionales.
        El color del chip puede sobreescribirse para versiones v000 en tracks comp/roto/cleanup.
        """
        K  = 1000
        w  = QtWidgets.QWidget()
        lo = QtWidgets.QHBoxLayout(w)
        lo.setContentsMargins(2, 2, 0, 2)
        lo.setSpacing(0)
        w.setStyleSheet("background: transparent;")
        if before_clip is None:
            return w

        clip_name     = before_clip["name"]
        clip_dur      = before_clip["duration"]
        chip_color    = self._chip_color(clip_name, bar_color, track_type)
        offset_frames = max(0, before_clip["tl_in"] - shot_start)
        offset_K = int(min(1.0, offset_frames / shot_dur) * K)
        chip_K   = int(min(1.0, clip_dur      / shot_dur) * K)
        total    = offset_K + chip_K
        if total > K:
            offset_K = int(offset_K * K // total)
            chip_K   = K - offset_K
        trail_K = max(0, K - offset_K - chip_K)

        debug_print(
            "[before_cell] '%s' dur=%d shot_dur=%d offset=%d color=%s "
            "→ off_K=%d chip_K=%d trail_K=%d"
            % (clip_name, clip_dur, shot_dur, offset_frames, chip_color,
               offset_K, chip_K, trail_K)
        )
        if offset_K > 0:
            lo.addStretch(offset_K)
        lbl = self._make_chip_label(
            clip_name, chip_color, is_new=False,
            frames=clip_dur, fps=self._fps,
        )
        lo.addWidget(lbl, chip_K)
        if trail_K > 0:
            lo.addStretch(trail_K)
        return w

    def _build_new_cell(
        self, new_items: list, bar_color: str, shot_dur: int,
        track_type: str = "other",
        handle_in: int = 0,
    ) -> QtWidgets.QWidget:
        """
        Celda de Shot Nuevo.

        shot_dur  = duración del clip nuevo más largo entre todos los tracks.
        handle_in = frames de offset inicial para editrefs (handle automático).

        Sin handle: el clip empieza en TC 0.
        Con handle: se antepone un spacer de handle_in frames antes del chip.
        """
        K  = 1000
        w  = QtWidgets.QWidget()
        lo = QtWidgets.QHBoxLayout(w)
        lo.setContentsMargins(0, 2, 0, 2)
        lo.setSpacing(0)
        w.setStyleSheet("background: transparent;")
        if not new_items:
            return w

        item0      = new_items[0]
        clip_dur   = item0.get("frame_count") or 0
        new_name   = item0.get("name") or item0.get("version_name") or ""
        chip_color = self._chip_color(new_name, bar_color, track_type)

        if handle_in > 0:
            offset_K = int(min(1.0, handle_in / shot_dur) * K)
            chip_K   = max(1, int(min(1.0, clip_dur / shot_dur) * K)) if clip_dur > 0 else 0
            total    = offset_K + chip_K
            if total > K:
                offset_K = int(offset_K * K // total)
                chip_K   = K - offset_K
            trail_K = max(0, K - offset_K - chip_K)
        else:
            offset_K = 0
            chip_K   = max(1, int(min(1.0, clip_dur / shot_dur) * K)) if clip_dur > 0 else 0
            trail_K  = K - chip_K

        debug_print(
            "[new_cell] '%s' dur=%d shot_dur=%d handle_in=%d color=%s "
            "→ off_K=%d chip_K=%d trail_K=%d"
            % (new_name, clip_dur, shot_dur, handle_in, chip_color,
               offset_K, chip_K, trail_K)
        )
        if offset_K > 0:
            lo.addStretch(offset_K)
        if chip_K > 0:
            lbl = self._make_chip_label(
                new_name, chip_color, is_new=True,
                frames=clip_dur, fps=self._fps,
            )
            lo.addWidget(lbl, chip_K)
        if trail_K > 0:
            lo.addStretch(trail_K)
        return w

    def _build_after_cell(
        self, after_clip, bar_color: str,
        shot_start: int, shot_dur: int,
        track_type: str = "other",
    ) -> QtWidgets.QWidget:
        """
        Celda de Shot Siguiente.

        shot_start  = tl_in mínimo entre todos los after clips del timeline.
        shot_dur    = duración total del shot siguiente (max_tl_out − shot_start + 1).

        Misma lógica que _build_before_cell pero para el shot posterior.
        """
        K  = 1000
        w  = QtWidgets.QWidget()
        lo = QtWidgets.QHBoxLayout(w)
        lo.setContentsMargins(0, 2, 2, 2)
        lo.setSpacing(0)
        w.setStyleSheet("background: transparent;")
        if after_clip is None:
            return w

        clip_name     = after_clip["name"]
        clip_dur      = after_clip["duration"]
        chip_color    = self._chip_color(clip_name, bar_color, track_type)
        offset_frames = max(0, after_clip["tl_in"] - shot_start)
        offset_K = int(min(1.0, offset_frames / shot_dur) * K)
        chip_K   = int(min(1.0, clip_dur      / shot_dur) * K)
        total    = offset_K + chip_K
        if total > K:
            offset_K = int(offset_K * K // total)
            chip_K   = K - offset_K
        trail_K = max(0, K - offset_K - chip_K)

        debug_print(
            "[after_cell] '%s' dur=%d shot_dur=%d offset=%d color=%s "
            "→ off_K=%d chip_K=%d trail_K=%d"
            % (clip_name, clip_dur, shot_dur, offset_frames, chip_color,
               offset_K, chip_K, trail_K)
        )
        if offset_K > 0:
            lo.addStretch(offset_K)
        lbl = self._make_chip_label(
            clip_name, chip_color, is_new=False,
            frames=clip_dur, fps=self._fps,
        )
        lo.addWidget(lbl, chip_K)
        if trail_K > 0:
            lo.addStretch(trail_K)
        return w

    def _update_import_page(self):
        """Recopila ítems chequeados, llama a build_import_preview_data y puebla la tabla."""
        # 1. Recopilar ítems chequeados agrupados por track
        #    Para cada track se conserva SOLO la versión más alta (mayor version_num).
        items_by_track_raw: dict[str, list[dict]] = {}
        unassigned_raw: list[tuple[dict, dict]] = []   # (item, row_data)

        for row, chk in self._checkboxes.items():
            if not chk.isChecked():
                continue
            row_data = self._table_rows[row]
            if row_data.get("type") == "section_header":
                continue
            track = self._get_track_for_row(row)
            item  = row_data.get("item", {})
            if not item:
                continue
            if track:
                items_by_track_raw.setdefault(track, []).append(item)
            else:
                unassigned_raw.append((item, row_data))

        # Deduplicar por track: solo la versión con mayor version_num
        items_by_track: dict[str, list[dict]] = {}
        for tname, items in items_by_track_raw.items():
            if len(items) > 1:
                latest = max(items, key=lambda x: x.get("version_num", -1))
                items_by_track[tname] = [latest]
            else:
                items_by_track[tname] = list(items)

        # Construir lista de unassigned con su color de sección
        unassigned: list[dict] = []
        for item, row_data in unassigned_raw:
            enriched = dict(item)
            enriched["_color"] = self._item_section_color(row_data)
            unassigned.append(enriched)

        # ── Calcular handle automático por track editref ──────────────────────
        # master_dur = frame_count del clip más largo de TODOS los tracks asignados.
        # Para cada track editref: handle = (master_dur - editref_dur) / 2
        # Si la diferencia es impar: handle_in = diff//2, handle_out = diff - handle_in
        master_dur = max(
            (item.get("frame_count") or 0
             for items in items_by_track.values() for item in items),
            default=0,
        )
        self._handle_info = {}   # {track_name: {handle_in, handle_out, half_frame, ...}}
        for tname, items in items_by_track.items():
            if classify_track_type(tname) == "editref" and items:
                editref_dur = items[0].get("frame_count") or 0
                if master_dur > 0 and editref_dur > 0 and editref_dur < master_dur:
                    diff       = master_dur - editref_dur
                    handle_in  = diff // 2
                    handle_out = diff - handle_in
                    self._handle_info[tname] = {
                        "handle_in":   handle_in,
                        "handle_out":  handle_out,
                        "half_frame":  (diff % 2 != 0),
                        "editref_dur": editref_dur,
                        "master_dur":  master_dur,
                    }
                    debug_print(
                        "_update_import_page: handle '%s' master=%d editref=%d "
                        "→ in=%d out=%d%s"
                        % (tname, master_dur, editref_dur, handle_in, handle_out,
                           " (impar)" if diff % 2 != 0 else "")
                    )
        self._update_import_handle_label()

        # 2. Construir datos del preview
        data = build_import_preview_data(
            self.seq,
            self.shot_name,
            self.insert_frame,
            self.prev_shot_name,
            self.next_shot_name,
            items_by_track,
            unassigned,
        )

        # 3. Poblar la tabla
        self._populate_import_table(data)

        # Habilitar ambos botones de import solo si hay ítems asignados a tracks
        has_assigned = bool(items_by_track)
        _import_tip = (
            "Importar al bin y colocar en el timeline"
            if has_assigned else
            "No hay ítems con track asignado para importar"
        )
        _v000_tip = (
            "Importar al timeline y abrir Create V000 al terminar"
            if has_assigned else
            "No hay ítems con track asignado para importar"
        )
        if hasattr(self, "_preview_import_now_btn"):
            self._preview_import_now_btn.setEnabled(has_assigned)
            self._preview_import_now_btn.setToolTip(_import_tip)
        if hasattr(self, "_preview_import_v000_btn"):
            self._preview_import_v000_btn.setEnabled(has_assigned)
            self._preview_import_v000_btn.setToolTip(_v000_tip)

    def _populate_import_table(self, data: dict):
        """
        Puebla self._import_table con los datos del preview.

        Columnas: barra(0) · track name(1) · Shot Anterior(2) · Shot Nuevo(3) · Shot Siguiente(4)

        Cada columna tiene su propio eje temporal (shot_dur) calculado globalmente:
          - Anterior: ventana temporal del shot previo (min tl_in → max tl_out de todos los before clips)
          - Nuevo:    max frame_count de todos los clips nuevos
          - Siguiente: ventana temporal del shot siguiente (min tl_in → max tl_out de todos los after clips)

        Dentro de cada columna el clip más largo = 100 %.
        Clips más cortos o desplazados se posicionan con offset y ancho proporcionales.
        """
        table = self._import_table
        table.clearContents()

        tracks     = data.get("tracks", [])
        unassigned = data.get("unassigned", [])

        # ── Métricas globales de cada shot ────────────────────────────────────
        # Shot Anterior
        all_before = [tdata["before_clip"] for tdata in tracks if tdata.get("before_clip")]
        if all_before:
            before_shot_start = min(c["tl_in"] for c in all_before)
            before_shot_end   = max(c["tl_out"] for c in all_before)
            before_shot_dur   = max(before_shot_end - before_shot_start + 1, 1)
        else:
            before_shot_start = 0
            before_shot_dur   = 1

        # Shot Nuevo
        new_shot_dur = max(
            (it.get("frame_count") or 0
             for tdata in tracks for it in tdata.get("new_items", [])),
            default=1,
        )
        new_shot_dur = max(new_shot_dur, 1)

        # Shot Siguiente
        all_after = [tdata["after_clip"] for tdata in tracks if tdata.get("after_clip")]
        if all_after:
            after_shot_start = min(c["tl_in"] for c in all_after)
            after_shot_end   = max(c["tl_out"] for c in all_after)
            after_shot_dur   = max(after_shot_end - after_shot_start + 1, 1)
        else:
            after_shot_start = 0
            after_shot_dur   = 1

        debug_print(
            "[populate_import_table] tracks=%d unassigned=%d "
            "before_shot_dur=%d new_shot_dur=%d after_shot_dur=%d"
            % (len(tracks), len(unassigned),
               before_shot_dur, new_shot_dur, after_shot_dur)
        )

        # ── Filas ─────────────────────────────────────────────────────────────
        n_rows = len(tracks)
        if unassigned:
            n_rows += 1 + len(unassigned)
        table.setRowCount(n_rows)
        row_h = 36

        row_i = 0
        for tdata in tracks:
            tname     = tdata["track_name"]
            ttype     = tdata["track_type"]
            before    = tdata.get("before_clip")
            new_items = tdata.get("new_items", [])
            after     = tdata.get("after_clip")
            bar_color = self._track_bar_color(ttype)

            debug_print(
                "[populate_import_table] row=%d track='%s' "
                "before=%s new=%d after=%s"
                % (row_i, tname, bool(before), len(new_items), bool(after))
            )

            # Col 0: barra de color
            bar = QtWidgets.QTableWidgetItem()
            bar.setBackground(QtGui.QColor(bar_color))
            bar.setFlags(QtCore.Qt.NoItemFlags)
            table.setItem(row_i, 0, bar)

            # Col 1: track name
            name_lbl = QtWidgets.QLabel("  " + tname)
            name_lbl.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignLeft)
            name_lbl.setStyleSheet(
                "color: %s; font-size: 11px; padding: 0px 4px; background: transparent;"
                % mix_colors(bar_color, "#ffffff", 0.55)
            )
            table.setCellWidget(row_i, 1, name_lbl)

            # ── BurnIn: representación gráfica especial ────────────────────
            if self._is_burnin_track(tname):
                table.setSpan(row_i, 2, 1, 3)
                table.setCellWidget(row_i, 2, self._build_burnin_row())
                table.setRowHeight(row_i, row_h)
                row_i += 1
                continue

            # Col 2: Shot Anterior
            table.setCellWidget(row_i, 2, self._build_before_cell(
                before, bar_color, before_shot_start, before_shot_dur,
                track_type=ttype,
            ))

            # Col 3: Shot Nuevo — editrefs reciben el handle_in como offset
            editref_handle_in = 0
            if ttype == "editref":
                editref_handle_in = getattr(self, "_handle_info", {}).get(
                    tname, {}
                ).get("handle_in", 0)
            table.setCellWidget(row_i, 3, self._build_new_cell(
                new_items, bar_color, new_shot_dur,
                track_type=ttype,
                handle_in=editref_handle_in,
            ))

            # Col 4: Shot Siguiente
            table.setCellWidget(row_i, 4, self._build_after_cell(
                after, bar_color, after_shot_start, after_shot_dur,
                track_type=ttype,
            ))

            table.setRowHeight(row_i, row_h)
            row_i += 1

        # ── Sección sin track asignado ────────────────────────────────────────
        if unassigned:
            # Encabezado de sección — span cols 1-4 completo
            bar_item = QtWidgets.QTableWidgetItem()
            bar_item.setBackground(QtGui.QColor("#555555"))
            bar_item.setFlags(QtCore.Qt.NoItemFlags)
            table.setItem(row_i, 0, bar_item)

            table.setSpan(row_i, 1, 1, 4)
            hdr_lbl = QtWidgets.QLabel("  SIN TRACK ASIGNADO")
            hdr_lbl.setStyleSheet(
                "color: #888888; font-weight: bold; font-size: 11px; "
                "padding: 3px 8px; background: #313131; letter-spacing: 1px;"
            )
            table.setCellWidget(row_i, 1, hdr_lbl)
            table.setRowHeight(row_i, 24)
            row_i += 1

            # Cada ítem sin track: chip proporcional en columna "Shot Nuevo" (col 3)
            # Cols 2 y 4 permanecen vacías (sin span).
            for item in unassigned:
                icolor  = item.get("_color", "#555555")
                iname   = item.get("name") or item.get("version_name") or "—"
                dur_v   = item.get("frame_count") or 0

                bar2 = QtWidgets.QTableWidgetItem()
                bar2.setBackground(QtGui.QColor(icolor))
                bar2.setFlags(QtCore.Qt.NoItemFlags)
                table.setItem(row_i, 0, bar2)

                # Cols 1, 2 y 4: vacías (fondo transparente)
                for empty_col in (1, 2, 4):
                    empty_w = QtWidgets.QWidget()
                    empty_w.setStyleSheet("background: transparent;")
                    table.setCellWidget(row_i, empty_col, empty_w)

                # Col 3: chip en Shot Nuevo — proporcional a new_shot_dur
                K       = 1000
                chip_K  = max(1, int(min(1.0, dur_v / new_shot_dur) * K)) if dur_v > 0 else K
                trail_K = max(0, K - chip_K)

                chip_container = QtWidgets.QWidget()
                chip_layout    = QtWidgets.QHBoxLayout(chip_container)
                chip_layout.setContentsMargins(0, 2, 0, 2)
                chip_layout.setSpacing(0)
                chip_container.setStyleSheet("background: transparent;")

                lbl = self._make_chip_label(
                    iname, color=icolor, is_new=False,
                    frames=dur_v, fps=self._fps,
                )
                chip_layout.addWidget(lbl, chip_K)
                if trail_K > 0:
                    chip_layout.addStretch(trail_K)

                table.setCellWidget(row_i, 3, chip_container)
                table.setRowHeight(row_i, row_h)
                row_i += 1

    # ── Importación real ─────────────────────────────────────────

    def _item_hiero_color(self, row_data: dict) -> str:
        """
        Devuelve el color hex para el BinItem/TrackItem en Hiero.

        Misma lógica que _chip_color en el preview:
        - Plates  → _CLR_PLATES
        - Refs    → _CLR_REFS
        - Publish → color de tarea; gris oscuro (#474747) si es v000
        """
        bar_color = self._item_section_color(row_data)
        section = row_data.get("section", "")
        if section == "publish":
            task = row_data.get("item", {}).get("task", "")
            clip_name = (row_data.get("item", {}).get("name", "")
                         or row_data.get("item", {}).get("version_name", ""))
            track_type = task if task in ("comp", "roto", "cleanup") else "other"
            return self._chip_color(clip_name, bar_color, track_type)
        return bar_color

    def _do_import(self):
        """
        Ejecuta la importación de los ítems chequeados al bin y al timeline.

        Flujo:
          1. Recolectar ítems marcados con track asignado (junto con su color).
          2. Abrir bloque de undo (with project.beginUndo).
          3. Hacer espacio: empujar clips cuyo tl_out >= insert_frame.
          4. Importar al bin, colorear BinItem y colocar en el timeline.
          5. Post-import: seleccionar los nuevos clips en el Timeline Editor.
        """
        # ── Recolección de ítems ──────────────────────────────────────────────
        # items_by_track: {track_name: [(item_dict, hex_color), ...]}
        items_by_track = {}
        for row, chk in self._checkboxes.items():
            if not chk.isChecked():
                continue
            row_data = self._table_rows[row]
            if row_data.get("type") == "section_header":
                continue
            track = self._get_track_for_row(row)
            item  = row_data.get("item", {})
            if not item or not track:
                continue
            color = self._item_hiero_color(row_data)
            items_by_track.setdefault(track, []).append((item, color))

        if not items_by_track:
            debug_print("_do_import: no hay items con track asignado", level="warning")
            return

        # ── Obtener proyecto desde la secuencia (no projects()[0]) ──────────────
        # Con múltiples proyectos abiertos, projects()[0] puede ser el proyecto
        # equivocado. El beginUndo debe abrirse en el que contiene self.seq.
        project = None
        try:
            project = self.seq.project()
        except Exception:
            pass

        errors = []
        placed = 0
        placed_items = []  # TrackItems colocados exitosamente
        _view_tc_in  = None  # tc_in calculado dentro del undo → leído en PASO 5
        _view_tc_out = None

        def _run_import():
            nonlocal placed, _view_tc_in, _view_tc_out

            # ── Recalcular posición justo antes del import ────────────────────
            # Cuando varias ventanas están abiertas simultáneamente, el timeline
            # puede haber cambiado desde que se calculó insert_frame al abrir
            # esta ventana. Recalcular aquí garantiza la posición correcta.
            _shot_dur = max(
                (it["frame_count"] for it in self.input_items
                 if it["kind"] == "exr_seq" and it.get("is_latest")),
                default=0,
            )
            if _shot_dur == 0:
                _shot_dur = max(
                    (it["frame_count"] for it in self.input_items
                     if it["kind"] == "exr_seq"),
                    default=100,
                )
            _new_insert, _new_push, _new_prev, _new_next = _find_insert_frame(
                self.seq, self.shot_name, _shot_dur
            )
            if _new_insert != self.insert_frame or _new_push != self.frames_to_push:
                debug_print(
                    "_do_import: posición recalculada → insert_frame %d→%d,"
                    " frames_to_push %d→%d"
                    % (self.insert_frame, _new_insert,
                       self.frames_to_push, _new_push)
                )
            self.insert_frame   = _new_insert
            self.frames_to_push = _new_push

            # ── PASO 1: Hacer espacio ─────────────────────────────────────────
            # effective_insert_frame es el min(tl_in) de los clips empujados;
            # es donde debe comenzar el nuevo shot para quedar adyacente al siguiente.
            effective_insert_frame = self.insert_frame

            if self.frames_to_push > 0:
                debug_print(
                    "_do_import → PASO 1: push tl_out>=%d por %d frames"
                    % (self.insert_frame, self.frames_to_push)
                )
                moved, effective_insert_frame = timeline_mod.push_clips_right(
                    self.seq, self.insert_frame, self.frames_to_push
                )
                debug_print("_do_import: %d clips movidos %d frames"
                            " | effective_insert_frame=%d"
                            % (moved, self.frames_to_push, effective_insert_frame))
            else:
                debug_print(
                    "_do_import: frames_to_push=0, sin necesidad de hacer espacio"
                    " | effective_insert_frame=%d" % effective_insert_frame)

            # ── PASO 2: Import al bin + colorear + colocación en timeline ─────
            debug_print("_do_import → PASO 2: import al bin y colocación en timeline")

            target_bin = bin_mod.find_or_create_shot_bin(self.seq, self.shot_name)

            for track_name, entries in items_by_track.items():
                for item, clip_color in entries:
                    clip_name   = item.get("name", "") or item.get("version_name", "?")
                    frame_count = item.get("frame_count", 0) or 0

                    clip, err = bin_mod.import_item_to_bin(item, target_bin)
                    if err:
                        errors.append("Bin: %s — %s" % (clip_name, err))
                        debug_print("_do_import: error bin '%s' → %s"
                                    % (clip_name, err), level="warning")
                        continue

                    # Colorear BinItem con el mismo color del chip del preview
                    try:
                        bin_item = clip.binItem()
                        if bin_item is not None:
                            bin_item.setColor(QtGui.QColor(clip_color))
                            debug_print("_do_import: color BinItem '%s' → %s"
                                        % (clip_name, clip_color))
                    except Exception as exc:
                        debug_print("_do_import: color BinItem fallo (no critico) → %s"
                                    % exc, level="warning")

                    # Preferir frame_count del item; fallback: duration que detectó Hiero
                    if frame_count == 0 and clip is not None:
                        try:
                            frame_count = clip.mediaSource().duration()
                            debug_print("_do_import: frame_count desde Hiero = %d"
                                        % frame_count)
                        except Exception:
                            pass

                    # Aplicar handle offset para editrefs
                    clip_tl_in = effective_insert_frame
                    if classify_track_type(track_name) == "editref":
                        handle_info = getattr(self, "_handle_info", {}).get(track_name)
                        if handle_info:
                            clip_tl_in += handle_info["handle_in"]
                            debug_print(
                                "_do_import: handle editref '%s' → offset +%d → tl_in=%d"
                                % (track_name, handle_info["handle_in"], clip_tl_in)
                            )

                    debug_print("_do_import: colocando '%s' en track '%s' tl=%d dur=%d"
                                % (clip_name, track_name, clip_tl_in, frame_count))

                    ti, err2 = timeline_mod.place_clip_in_timeline(
                        self.seq, clip, track_name,
                        clip_tl_in, frame_count, self.shot_name,
                    )
                    if err2:
                        errors.append("Timeline: %s — %s" % (clip_name, err2))
                        debug_print("_do_import: error timeline '%s' → %s"
                                    % (clip_name, err2), level="warning")
                    else:
                        placed += 1
                        placed_items.append(ti)
                        debug_print("_do_import: OK — '%s' en track '%s' tl=%d-%d"
                                    % (clip_name, track_name,
                                       clip_tl_in,
                                       clip_tl_in + frame_count - 1))

            # ── PASO 3: Estirar BurnIn hasta el final del timeline ────────────
            if placed > 0:
                debug_print("_do_import → PASO 3: stretch BurnIn")
                timeline_mod.stretch_burnin(self.seq)

            # ── PASO 4: In/Out del timeline al rango del shot ─────────────────
            # Dentro del bloque de undo para que Ctrl+Z revierta también este
            # cambio junto con el import.
            if placed_items:
                valid_items = [ti for ti in placed_items
                               if ti.parentTrack() is not None]
                if valid_items:
                    try:
                        tc_in  = min(int(ti.timelineIn())  for ti in valid_items)
                        tc_out = max(int(ti.timelineOut()) for ti in valid_items)
                        self.seq.setInTime(tc_in)
                        self.seq.setOutTime(tc_out)
                        _view_tc_in  = tc_in
                        _view_tc_out = tc_out
                        debug_print("_do_import PASO 4: in=%d out=%d" % (tc_in, tc_out))
                    except Exception as exc:
                        debug_print("_do_import PASO 4: error → %s" % exc,
                                    level="warning")

        # ── Ejecutar todo dentro de un único bloque de undo ───────────────────
        if project:
            debug_print("_do_import: beginUndo abierto")
            with project.beginUndo("Import Shot: %s" % self.shot_name):
                _run_import()
            debug_print("_do_import: endUndo cerrado")
        else:
            _run_import()

        # ── PASO 5: Playhead al TC IN + zoom (operaciones de UI pura) ────────
        # Fuera del bloque de undo: no tienen semántica de modelo, no se revierten.
        # El In/Out ya fue establecido en PASO 4 dentro del undo.
        # El QTimer interno dispara el zoom después de que self.accept() cierre
        # el diálogo y la ventana del timeline recupere el foco.
        if _view_tc_in is not None and _view_tc_out is not None:
            try:
                debug_print(
                    "_do_import PASO 5: set_viewer_to_shot tc_in=%d tc_out=%d"
                    % (_view_tc_in, _view_tc_out)
                )
                timeline_mod.set_viewer_to_shot(self.seq, _view_tc_in, _view_tc_out)
            except Exception as exc:
                debug_print("_do_import PASO 5: error → %s" % exc, level="warning")

        if errors:
            QtWidgets.QMessageBox.warning(
                self,
                "Import — errores parciales",
                "Se completó con %d ítem(s) colocados.\n\nErrores:\n%s"
                % (placed, "\n".join(errors)),
            )
        else:
            debug_print("_do_import: %d ítems importados correctamente" % placed)

        self.accept()

        # ── Lanzar Create V000 si fue pedido ──────────────────────────────────
        # Se ejecuta con QTimer(0) para que el diálogo esté completamente cerrado
        # antes de que CreateV000 abra su propia ventana.
        if getattr(self, "_pending_create_v000", False):
            debug_print("_do_import: lanzando CreateV000 post-import")
            QtCore.QTimer.singleShot(0, _launch_create_v000)

    def _do_import_and_v000(self):
        """Marca que CreateV000 debe lanzarse al terminar y ejecuta el import normal."""
        self._pending_create_v000 = True
        self._do_import()

    def _on_res_preset_changed(self, idx):
        preset = self._res_presets[idx][1] if 0 <= idx < len(self._res_presets) else None
        self._custom_res_widget.setVisible(preset == "custom")
        self._save_preset_btn.setVisible(preset == "custom")
        if preset == "custom" and self._convert_keep_ar.isChecked():
            self._sync_custom_res_to_source_ar()
        self._update_match_dim_visibility()
        self._refresh_convert_destinos()

    def _on_keep_ar_changed(self, _state=None):
        now_enabled = self._convert_keep_ar.isChecked()
        was_enabled = getattr(self, "_keep_ar_prev_state", now_enabled)
        if now_enabled and not was_enabled:
            # Si veníamos de custom libre (W/H arbitrarios), al activar preserve
            # normalizamos usando "Dimensión que manda".
            self._sync_custom_res_to_source_ar()
        self._keep_ar_prev_state = now_enabled
        self._update_match_dim_visibility()
        self._refresh_convert_destinos()

    def _update_match_dim_visibility(self):
        """Muestra 'Dimensión que manda' cuando Preserve aspect ratio está activo."""
        self._match_dim_widget.setVisible(self._convert_keep_ar.isChecked())

    def _get_representative_res(self):
        """Devuelve (src_w, src_h) del primer EXR disponible, o (None, None)."""
        if hasattr(self, "_convert_rows"):
            for it in self._convert_rows:
                if it.get("kind") != "mov" and it.get("width") and it.get("height"):
                    return it["width"], it["height"]
        return None, None

    def _is_custom_res_selected(self):
        idx = self._res_combo.currentIndex()
        return (
            0 <= idx < len(self._res_presets)
            and self._res_presets[idx][1] == "custom"
        )

    def _match_target_is_width(self):
        return self._convert_match_dim.currentIndex() == 0

    def _sync_custom_res_to_source_ar(self):
        """En preset Custom + Preserve AR, ajusta la dimensión derivada según match_dim."""
        if not self._is_custom_res_selected() or not self._convert_keep_ar.isChecked():
            return
        src_w, src_h = self._get_representative_res()
        if not (src_w and src_h):
            return

        self._custom_ar_updating = True
        try:
            if self._match_target_is_width():
                tw = self._convert_custom_w.value()
                new_h = max(1, int(round(tw * src_h / float(src_w))))
                self._convert_custom_h.setValue(new_h)
            else:
                th = self._convert_custom_h.value()
                new_w = max(1, int(round(th * src_w / float(src_h))))
                self._convert_custom_w.setValue(new_w)
        finally:
            self._custom_ar_updating = False

    def _on_custom_w_changed(self):
        """Sincroniza resolución Custom con AR cuando Preserve está activo."""
        if self._custom_ar_updating:
            return
        if self._is_custom_res_selected() and self._convert_keep_ar.isChecked():
            self._sync_custom_res_to_source_ar()
        self._refresh_convert_destinos()

    def _on_custom_h_changed(self):
        """Sincroniza resolución Custom con AR cuando Preserve está activo."""
        if self._custom_ar_updating:
            return
        if self._is_custom_res_selected() and self._convert_keep_ar.isChecked():
            self._sync_custom_res_to_source_ar()
        self._refresh_convert_destinos()

    def _on_match_dim_changed(self, *_):
        if self._convert_keep_ar.isChecked():
            self._sync_custom_res_to_source_ar()
        self._refresh_convert_destinos()

    def _current_target_res(self, src_w, src_h):
        """Devuelve (tw, th) destino segun preset y opciones de aspect ratio.

        - Original:  devuelve dimensiones del origen (sin cambio).
        - Preset fijo: si PAR activo, ajusta la dimensión secundaria.
        - Custom:    si PAR activo, "Dimensión que manda" define qué eje
                     se respeta y el otro se recalcula por ítem según AR source;
                     si PAR desactivado, usa los spinboxes tal cual.
        """
        idx = self._res_combo.currentIndex()
        preset = self._res_presets[idx][1] if 0 <= idx < len(self._res_presets) else None
        if preset is None:
            return src_w, src_h          # Original
        if preset == "timeline":
            tw = self._tl_w or src_w
            th = self._tl_h or src_h
            if self._convert_keep_ar.isChecked() and src_w and src_h:
                match_width = self._convert_match_dim.currentText().startswith("Match target width")
                if match_width:
                    th = int(round(tw * src_h / float(src_w)))
                else:
                    tw = int(round(th * src_w / float(src_h)))
            return tw, th
        if preset == "custom":
            if self._convert_keep_ar.isChecked() and src_w and src_h:
                if self._match_target_is_width():
                    tw = self._convert_custom_w.value()
                    th = int(round(tw * src_h / float(src_w)))
                else:
                    th = self._convert_custom_h.value()
                    tw = int(round(th * src_w / float(src_h)))
                return tw, th
            return self._convert_custom_w.value(), self._convert_custom_h.value()
        # preset fijo (w, h)
        tw, th = preset
        if self._convert_keep_ar.isChecked() and src_w and src_h:
            match_width = self._convert_match_dim.currentText().startswith("Match target width")
            if match_width:
                th = int(round(tw * src_h / float(src_w)))
            else:
                tw = int(round(th * src_w / float(src_h)))
        return tw, th

    def _update_res_combo_labels(self):
        """Actualiza los items del combo con la resolución final real y AR."""
        src_w, src_h = self._get_representative_res()
        for i, (label, preset) in enumerate(self._res_presets):
            if preset is None:
                # "Original": mostrar AR del source si está disponible
                if src_w and src_h:
                    ar = _ar_str(src_w, src_h)
                    self._res_combo.setItemText(
                        i, ("%s  [%s]" % (label, ar)) if ar else label)
                else:
                    self._res_combo.setItemText(i, label)
                continue
            if preset == "custom":
                self._res_combo.setItemText(i, label)
                continue
            if preset == "timeline":
                tl_w = self._tl_w or src_w
                tl_h = self._tl_h or src_h
                if tl_w and tl_h:
                    base_ar = _ar_str(tl_w, tl_h)
                    base_res = "Timeline  %d×%d" % (tl_w, tl_h)
                    base = ("%s  [%s]" % (base_res, base_ar)) if base_ar else base_res
                    if src_w and src_h:
                        tw, th = tl_w, tl_h
                        if self._convert_keep_ar.isChecked():
                            match_width = self._convert_match_dim.currentText().startswith("Match target width")
                            if match_width:
                                th = int(round(tw * src_h / float(src_w)))
                            else:
                                tw = int(round(th * src_w / float(src_h)))
                        tw, th = self._apply_deana_if_active(tw, th)
                        tw, th = self._apply_even_dims_if_active(tw, th)
                        comp_ar = _ar_str(tw, th)
                        ar_part = ("  [%s]" % comp_ar) if comp_ar else ""
                        self._res_combo.setItemText(
                            i, "%s  ➜  %d×%d%s" % (base, tw, th, ar_part))
                    else:
                        self._res_combo.setItemText(i, base)
                else:
                    self._res_combo.setItemText(i, "Timeline")
                continue
            tw, th = preset
            preset_ar = _ar_str(tw, th)
            if not src_w or not src_h:
                base = ("%s  [%s]" % (label, preset_ar)) if preset_ar else label
                self._res_combo.setItemText(i, base)
                continue
            # Con source: calculamos resolución real según PAR y match_dim
            if self._convert_keep_ar.isChecked():
                match_width = self._convert_match_dim.currentText().startswith("Match target width")
                if match_width:
                    th = int(round(tw * src_h / float(src_w)))
                else:
                    tw = int(round(th * src_w / float(src_h)))
            tw, th = self._apply_deana_if_active(tw, th)
            tw, th = self._apply_even_dims_if_active(tw, th)
            computed_ar = _ar_str(tw, th)
            base = ("%s  [%s]" % (label, preset_ar)) if preset_ar else label
            ar_part = ("  [%s]" % computed_ar) if computed_ar else ""
            self._res_combo.setItemText(
                i, "%s  ➜  %d×%d%s" % (base, tw, th, ar_part))

    def _on_dwaa_chk_changed(self, state):
        """Actualiza destinos cuando cambia el uso de compresion DWAA."""
        self._convert_dwaa_level_lbl.setVisible(state == QtCore.Qt.Checked)
        self._refresh_convert_destinos()

    def _on_deana_chk_changed(self, state):
        """Muestra u oculta el selector de PAR de desanamorfizado."""
        self._deana_par_widget.setVisible(state == QtCore.Qt.Checked)
        self._refresh_convert_destinos()

    # ── Presets helpers ────────────────────────────────────────────────────────

    _N_HEAD = 2   # entradas hardcoded al inicio: Original + Timeline
    _N_TAIL = 1   # entradas hardcoded al final:  Custom...

    def _build_full_presets(self):
        """Construye la lista completa de presets (head hardcoded + INI + tail hardcoded)."""
        tl_lbl = "Timeline"
        if self._tl_w and self._tl_h:
            ar = _ar_str(self._tl_w, self._tl_h)
            res_part = "%d\u00d7%d" % (self._tl_w, self._tl_h)
            tl_lbl = ("Timeline  %s  [%s]" % (res_part, ar)) if ar else ("Timeline  %s" % res_part)
        head = [
            ("Original", None),
            (tl_lbl, "timeline"),
        ]
        mid  = [settings_mod.preset_to_tuple(p) for p in self._res_presets_raw]
        tail = [("Custom...", "custom")]
        return head + mid + tail

    # ── Settings persistentes ──────────────────────────────────────────────────

    def _load_settings_to_ui(self):
        """Aplica los settings cargados desde el INI a los widgets."""
        s   = self._imp_settings
        cod = s.get("codec", {})
        res = s.get("res", {})
        org = s.get("originals", {})

        # Codec
        self._convert_dwaa_chk.setChecked(cod.get("dwaa", "true").lower() == "true")
        ch_val = cod.get("channels", "all")
        self._convert_channels.setCurrentIndex(1 if ch_val == "rgb" else 0)
        flt_idx = self._convert_filter.findText(cod.get("filter", "lanczos3"))
        self._convert_filter.setCurrentIndex(max(0, flt_idx))

        # Resolution
        try:
            pi = int(res.get("preset_index", "0"))
            pi = max(0, min(pi, self._res_combo.count() - 1))
            self._res_combo.setCurrentIndex(pi)
        except ValueError:
            pass
        try:
            self._convert_custom_w.setValue(int(res.get("custom_w", "2048")))
        except ValueError:
            pass
        try:
            self._convert_custom_h.setValue(int(res.get("custom_h", "1152")))
        except ValueError:
            pass
        self._convert_keep_ar.setChecked(res.get("keep_ar", "true").lower() == "true")
        try:
            md_idx = int(res.get("match_dim", "0"))
            self._convert_match_dim.setCurrentIndex(max(0, min(md_idx, 1)))
        except ValueError:
            pass
        self._convert_deana_chk.setChecked(res.get("deana", "false").lower() == "true")
        dp_idx = self._convert_deana_par.findText(res.get("deana_par", "2.0"))
        self._convert_deana_par.setCurrentIndex(max(0, dp_idx))
        self._convert_even_dims_chk.setChecked(
            res.get("even_dims", "true").lower() == "true"
        )

        # Originals (solo si no estamos en test mode)
        if not Transcode_TEST_Mode:
            self._delete_originals_chk.setChecked(org.get("delete", "false").lower() == "true")

    def _save_all_settings(self, *_):
        """Guarda todos los settings al INI."""
        settings_mod.save_all_settings({
            "codec": {
                "dwaa":       str(self._convert_dwaa_chk.isChecked()).lower(),
                "channels":   ("rgb" if self._convert_channels.currentText() == "Reducir a RGB"
                               else "all"),
                "filter":     self._convert_filter.currentText(),
            },
            "res": {
                "preset_index": str(self._res_combo.currentIndex()),
                "custom_w":     str(self._convert_custom_w.value()),
                "custom_h":     str(self._convert_custom_h.value()),
                "keep_ar":      str(self._convert_keep_ar.isChecked()).lower(),
                "match_dim":    str(self._convert_match_dim.currentIndex()),
                "deana":        str(self._convert_deana_chk.isChecked()).lower(),
                "deana_par":    self._convert_deana_par.currentText(),
                "even_dims":    str(self._convert_even_dims_chk.isChecked()).lower(),
            },
            "originals": {
                "delete": str(self._delete_originals_chk.isChecked()).lower(),
            },
        })

    # ── Presets de resolución dinámicos ────────────────────────────────────────

    def _rebuild_res_combo(self, select_idx=None):
        """Reconstruye el combo desde _res_presets_raw (INI) + hardcoded head/tail."""
        self._res_presets = self._build_full_presets()

        prev_idx = self._res_combo.currentIndex() if select_idx is None else select_idx

        self._res_combo.blockSignals(True)
        self._res_combo.clear()
        for label, preset in self._res_presets:
            if preset and preset not in ("custom", "timeline"):
                tw, th = preset
                ar = _ar_str(tw, th)
                display = ("%s  [%s]" % (label, ar)) if ar else label
            else:
                display = label
            self._res_combo.addItem(display)

        valid_idx = max(0, min(prev_idx, self._res_combo.count() - 1))
        self._res_combo.setCurrentIndex(valid_idx)
        self._res_combo.blockSignals(False)

        self._on_res_preset_changed(valid_idx)
        self._update_res_combo_labels()

    def _on_delete_preset(self, row):
        """Elimina el preset en la posición row del combo (y del INI)."""
        n_head = self._N_HEAD
        n_tail = self._N_TAIL
        n_total = len(self._res_presets)

        # Proteger hardcoded head (Original, Timeline) y tail (Custom...)
        if row < n_head or row >= n_total - n_tail:
            return

        ini_row = row - n_head  # índice en _res_presets_raw

        cur_idx = self._res_combo.currentIndex()
        if cur_idx == row:
            new_idx = max(0, row - 1)  # seleccionar el de arriba
        elif cur_idx > row:
            new_idx = cur_idx - 1
        else:
            new_idx = cur_idx

        del self._res_presets_raw[ini_row]
        settings_mod.save_res_presets(self._res_presets_raw)
        # Cerrar popup para que Qt recalcule el alto del desplegable sin filas vacías.
        self._res_combo.hidePopup()
        self._rebuild_res_combo(select_idx=new_idx)
        self._save_all_settings()

    def _on_save_preset_clicked(self):
        """Abre el diálogo de guardar preset y añade el nuevo a la lista."""
        w = self._convert_custom_w.value()
        h = self._convert_custom_h.value()
        name = settings_mod.show_save_preset_dialog(w, h, parent=self)
        if not name:
            return

        # Insertar al final de los presets INI (antes de Custom... hardcoded)
        ini_insert = len(self._res_presets_raw)
        self._res_presets_raw.append({"name": name, "w": w, "h": h})
        settings_mod.save_res_presets(self._res_presets_raw)
        # El índice en el combo = offset head + posición INI
        combo_idx = self._N_HEAD + ini_insert
        self._rebuild_res_combo(select_idx=combo_idx)
        self._save_all_settings()

    def _apply_deana_if_active(self, tw, th):
        """Multiplica el ancho por el PAR elegido si desanamorfizar está activo."""
        if (hasattr(self, "_convert_deana_chk")
                and self._convert_deana_chk.isChecked()
                and tw):
            par = float(self._convert_deana_par.currentText())
            tw  = int(round(tw * par))
        return tw, th

    def _apply_even_dims_if_active(self, tw, th):
        """Si está activo, corrige dimensiones impares restando 1 px (mínimo 1)."""
        if not (hasattr(self, "_convert_even_dims_chk")
                and self._convert_even_dims_chk.isChecked()):
            return tw, th
        if tw and (tw % 2) and tw > 1:
            tw -= 1
        if th and (th % 2) and th > 1:
            th -= 1
        return tw, th

    def _target_compression(self, src_comp):
        return "dwaa" if self._convert_dwaa_chk.isChecked() else (src_comp or "—")

    def _target_bitdepth(self, src_bd):
        return src_bd or "—"

    def _target_channels(self, src_ch):
        sel = self._convert_channels.currentText()
        if sel == "Reducir a RGB":
            return 3
        return src_ch  # Mantener

    @staticmethod
    def _ch_str(ch):
        if isinstance(ch, int):
            if ch == 1:  return "Y"
            if ch == 3:  return "RGB"
            if ch == 4:  return "RGBA"
            return "%dch" % ch
        return "—"

    @staticmethod
    def _fmt_bd(bd):
        """Convierte 'half'➜'16b', 'float'➜'32b'. Resto se muestra tal cual."""
        if bd == "half":   return "16b"
        if bd == "float":  return "32b"
        return bd or "—"

    @staticmethod
    def _fmt_par(par):
        """Formatea PAR numérico para display: 1.0➜'1', 2.0➜'2', 1.33➜'1.33'."""
        if par is None:
            return None
        v = float(par)
        return ("%d" % int(v)) if v == int(v) else ("%.4g" % v)

    def _refresh_convert_destinos(self):
        """Recalcula columnas 'Destino' y 'Estado' y las labels del combo (EXR solamente).

        Detecta automáticamente los casos de upscale bloqueado:
        - Destino: muestra la resolución final (griseado si upscale bloqueado o desactivado)
        - Estado:  'Pendiente' (cian) | '⚠ Upscale' (rojo) | '—' (gris, fila desactivada)
        """
        if not hasattr(self, "_convert_table") or not hasattr(self, "_convert_rows"):
            return
        self._update_res_combo_labels()
        for row_i, item in enumerate(self._convert_rows):
            if item.get("kind") == "mov":
                continue

            # ── Fila desactivada (checkbox off) ──────────────────────────
            chk = self._convert_checkboxes.get(row_i) if hasattr(self, "_convert_checkboxes") else None
            if chk is not None and not chk.isChecked():
                self._convert_table.setCellWidget(
                    row_i, 5, _cell_html_label("<span style='color:#444444;'>—</span>")
                )
                self._convert_table.setCellWidget(
                    row_i, 7, _cell_html_label("<span style='color:#444444;'>—</span>")
                )
                continue

            sw, sh = item.get("width"), item.get("height")
            tw, th = self._current_target_res(sw, sh)

            # ¿El resize resultaría en upscale y está bloqueado?
            is_upscale_blocked = (
                sw and sh and tw and th
                and (tw > sw or th > sh)
            )
            if is_upscale_blocked:
                tw, th = sw, sh  # se mantiene el original

            # Aplicar desanamorfizado DESPUÉS del check de upscale
            tw, th = self._apply_deana_if_active(tw, th)
            tw, th = self._apply_even_dims_if_active(tw, th)

            # ── Columna 5: Destino ────────────────────────────────────────
            dest_fg = "#555555" if is_upscale_blocked else "#a7a7a7"
            comp = self._target_compression(item.get("compression"))
            bd   = self._fmt_bd(self._target_bitdepth(item.get("bitdepth")))
            ch   = self._target_channels(item.get("channels"))
            if tw and th:
                ar = _ar_str(tw, th)
                ar_clr = "#5a4a30" if is_upscale_blocked else _CLR_AR
                if ar:
                    res_h = ("<span style='color:%s;'>%d×%d</span>"
                             " <span style='color:%s;'>(%s)</span>" % (
                                 dest_fg, tw, th, ar_clr, ar))
                else:
                    res_h = "<span style='color:%s;'>%d×%d</span>" % (dest_fg, tw, th)
            else:
                res_h = "<span style='color:%s;'>—</span>" % dest_fg
            # PAR destino: 1 si desanamorfizando, PAR fuente si no
            if hasattr(self, "_convert_deana_chk") and self._convert_deana_chk.isChecked():
                tpar_fmt = "1"
            else:
                tpar_fmt = self._fmt_par(item.get("pixel_aspect_ratio"))
            par_clr = "#5a3a3a" if is_upscale_blocked else _CLR_PAR
            tpar_h = (" <span style='color:%s;'>(%s)</span>" % (par_clr, tpar_fmt)) if tpar_fmt else ""
            comp_clr = dest_fg if is_upscale_blocked else _comp_color(comp)
            bd_h   = "<span style='color:%s;'>%s</span>" % (dest_fg, bd or "—")
            ch_h   = "<span style='color:%s;'>%s</span>" % (dest_fg, self._ch_str(ch))
            comp_h = "<span style='color:%s;'>%s</span>" % (comp_clr, comp)
            dest_html = "%s%s · %s · %s · %s" % (res_h, tpar_h, bd_h, ch_h, comp_h)
            self._convert_table.setCellWidget(row_i, 5, _cell_html_label(dest_html))

            # ── Columna 7: Estado ─────────────────────────────────────────
            if is_upscale_blocked:
                st_html = ("<span style='color:%s;'>⚠ Upscale</span>"
                           % _CLR_STATUS_UPSCALE)
            else:
                st_html = ("<span style='color:%s;'>Pendiente</span>"
                           % _CLR_STATUS_PENDING)
            self._convert_table.setCellWidget(row_i, 7, _cell_html_label(st_html))

    def _update_convert_page(self, saved_chk=None):
        if saved_chk is None:
            saved_chk = {}
        # Todos los plates de input (EXR + MOVs de plates); MOVs entran deshabilitados
        plate_items = [
            it for it in getattr(self, "input_items", [])
            if it["kind"] in ("exr_seq", "mov")
        ]

        # Poblar tabla
        self._convert_rows = plate_items
        self._convert_table.setRowCount(len(plate_items))

        self._convert_checkboxes = {}
        total_size = 0
        total_frames = 0
        for i, it in enumerate(plate_items):
            is_mov = it.get("kind") == "mov"
            dim_color = "#555555" if is_mov else "#888888"
            name_color = "#666666" if is_mov else "#cccccc"

            # Col 0: barra de color (plates)
            bar = QtWidgets.QTableWidgetItem()
            bar.setBackground(QtGui.QColor(_CLR_PLATES if not is_mov else "#444444"))
            bar.setFlags(QtCore.Qt.NoItemFlags)
            self._convert_table.setItem(i, 0, bar)

            # Col 1: checkbox (deshabilitado para MOVs)
            chk = QtWidgets.QCheckBox()
            chk.setStyleSheet("color:#a7a7a7; padding:2px;")
            if is_mov:
                chk.setChecked(False)
                chk.setEnabled(False)
                chk.setToolTip("Transcode de MOV pendiente de implementación")
            else:
                item_path = it.get("path", "")
                chk.setChecked(saved_chk.get(item_path, True))
            chk.stateChanged.connect(lambda *_: self._update_transcode_btn_state())
            chk.stateChanged.connect(lambda *_: self._refresh_convert_destinos())
            chk.clicked.connect(lambda _checked=False, ri=i: self._on_convert_chk_clicked(ri))
            self._convert_checkboxes[i] = chk
            chk_container = QtWidgets.QWidget()
            cl = QtWidgets.QHBoxLayout(chk_container)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setAlignment(QtCore.Qt.AlignCenter)
            cl.addWidget(chk)
            self._convert_table.setCellWidget(i, 1, chk_container)

            # Col 2: Nombre
            tc_name = it.get("name", "")
            tc_pfx_len = len(self.shot_name) if (not is_mov and tc_name.startswith(self.shot_name)) else 0
            if tc_pfx_len:
                tc_name_html = (
                    "<span style='color:%s;'>%s</span>"
                    "<span style='color:%s;'>%s</span>"
                    % (SHOTNAME_COLOR, _rn_escape(tc_name[:tc_pfx_len]),
                       name_color, _rn_escape(tc_name[tc_pfx_len:]))
                )
                tc_name_lbl = _cell_html_label(tc_name_html)
                if is_mov:
                    tc_name_lbl.setToolTip("Transcode de MOV pendiente de implementación")
                self._convert_table.setCellWidget(i, 2, tc_name_lbl)
            else:
                name_item = QtWidgets.QTableWidgetItem(tc_name)
                name_item.setForeground(QtGui.QColor(name_color))
                if is_mov:
                    name_item.setToolTip("Transcode de MOV pendiente de implementación")
                self._convert_table.setItem(i, 2, name_item)

            # Col 3: Origen "WxH [AR] · bd · Nch · comp · #f - Xs"
            sw, sh = it.get("width"), it.get("height")
            sc = it.get("compression") or "—"
            sbd = self._fmt_bd(it.get("bitdepth"))
            sch = it.get("channels")
            fc = it.get("frame_count") or 0
            fps_val = it.get("fps")
            if not is_mov:
                total_frames += fc
            # resolución con AR coloreado
            if sw and sh:
                ar = _ar_str(sw, sh)
                ar_clr = "#555555" if is_mov else _CLR_AR
                if ar:
                    res_h = ("<span style='color:%s;'>%d×%d</span>"
                             " <span style='color:%s;'>(%s)</span>" % (
                                 dim_color, sw, sh, ar_clr, ar))
                else:
                    res_h = "<span style='color:%s;'>%d×%d</span>" % (dim_color, sw, sh)
            else:
                res_h = "<span style='color:%s;'>—</span>" % dim_color
            # PAR en rosa (solo si está disponible)
            spar = self._fmt_par(it.get("pixel_aspect_ratio"))
            par_clr = "#555555" if is_mov else _CLR_PAR
            par_h = (" <span style='color:%s;'>(%s)</span>" % (par_clr, spar)) if spar else ""
            # compresión coloreada
            sc_clr = _comp_color(sc, greyed=is_mov)
            sc_h = "<span style='color:%s;'>%s</span>" % (sc_clr, sc)
            # frames con segundos coloreados
            fc_clr = "#555555" if is_mov else _CLR_FRAMES
            secs_txt = (" - %.1fs" % (fc / float(fps_val))) if fps_val and fc else ""
            fc_h = "<span style='color:%s;'>%df%s</span>" % (fc_clr, fc, secs_txt)
            bd_h = "<span style='color:%s;'>%s</span>" % (dim_color, sbd)
            ch_h = "<span style='color:%s;'>%s</span>" % (dim_color, self._ch_str(sch))
            origen_html = "%s%s · %s · %s · %s · %s" % (res_h, par_h, bd_h, ch_h, sc_h, fc_h)
            self._convert_table.setCellWidget(i, 3, _cell_html_label(origen_html))

            # Col 4: flecha
            arrow = QtWidgets.QTableWidgetItem("➜")
            arrow.setForeground(QtGui.QColor("#444444" if is_mov else "#666666"))
            arrow.setTextAlignment(QtCore.Qt.AlignCenter)
            self._convert_table.setItem(i, 4, arrow)

            # Col 5: Destino — placeholder; se completa en _refresh_convert_destinos
            if is_mov:
                self._convert_table.setCellWidget(
                    i, 5, _cell_html_label("<span style='color:#555555;'>—</span>"))
            else:
                self._convert_table.setItem(i, 5, QtWidgets.QTableWidgetItem(""))

            # Col 6: Tamaño actual
            size_b = _folder_size_bytes(it.get("path", ""))
            if not is_mov:
                total_size += size_b
            s_item = QtWidgets.QTableWidgetItem(_format_bytes(size_b))
            s_item.setForeground(QtGui.QColor(dim_color))
            s_item.setTextAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
            self._convert_table.setItem(i, 6, s_item)

            # Col 7: Estado inicial (se reescribe en _refresh_convert_destinos para EXR)
            if is_mov:
                st_html = "<span style='color:#555555;'>No soportado</span>"
            else:
                st_html = "<span style='color:%s;'>Pendiente</span>" % _CLR_STATUS_PENDING
            self._convert_table.setCellWidget(i, 7, _cell_html_label(st_html))

        self._refresh_convert_destinos()

        # Resumen
        if plate_items:
            self._convert_summary_lbl.setText(
                "%d plate%s · %d frames · %s en disco" % (
                    len(plate_items), "" if len(plate_items) == 1 else "s",
                    total_frames, _format_bytes(total_size),
                )
            )
        else:
            self._convert_summary_lbl.setText("No hay plates seleccionados.")

        self._update_transcode_btn_state()

    def _toggle_convert_log(self):
        self._log_expanded = not self._log_expanded
        if self._log_expanded:
            self._convert_log.setMaximumHeight(16777215)
            self._log_expand_btn.setText("▼")
            self._log_expand_btn.setToolTip("Colapsar log")
        else:
            self._convert_log.setMaximumHeight(60)
            self._log_expand_btn.setText("▲")
            self._log_expand_btn.setToolTip("Expandir log")

    # ══════════════════════════════════════════════════════════
    #  Transcode — estado del botón y ejecución
    # ══════════════════════════════════════════════════════════

    def _update_transcode_btn_state(self):
        """Habilita Start Transcode si hay al menos un EXR habilitado y chequeado."""
        if not hasattr(self, "_convert_checkboxes") or not hasattr(self, "_start_transcode_btn"):
            return
        if getattr(self, "_transcode_active", False):
            self._start_transcode_btn.setEnabled(False)
            self._start_transcode_btn.setToolTip("Transcode en curso")
            return
        has_exr = any(
            chk.isChecked() and chk.isEnabled()
            for chk in self._convert_checkboxes.values()
        )
        self._start_transcode_btn.setEnabled(has_exr)
        self._start_transcode_btn.setToolTip(
            "" if has_exr else "Selecciona al menos un EXR"
        )

    def _run_transcode(self):
        """Handler del botón Start Transcode.

        Inicializa la cola de secuencias y arranca la primera.
        Las siguientes se procesan una a una en _start_next_sequence(),
        que se llama al finalizar cada worker.
        """
        if not hasattr(self, "_convert_checkboxes") or not hasattr(self, "_convert_rows"):
            return

        # Recolectar secuencias EXR con checkbox activo
        job_sequences = []
        for row_i, chk in self._convert_checkboxes.items():
            if not chk.isChecked() or not chk.isEnabled():
                continue
            item = self._convert_rows[row_i]
            tw, th = self._current_target_res(item.get("width"), item.get("height"))
            sw, sh = item.get("width"), item.get("height")
            if sw and sh and tw and th:
                if tw > sw or th > sh:
                    tw, th = sw, sh
            # Aplicar desanamorfizado DESPUÉS del check de upscale
            tw, th = self._apply_deana_if_active(tw, th)
            tw, th = self._apply_even_dims_if_active(tw, th)
            job_sequences.append((row_i, item, tw, th))

        if not job_sequences:
            return

        # Guardar estado compartido para toda la cola
        self._sequence_queue       = list(job_sequences)
        self._transcode_results_all = []
        self._transcode_flags = {
            "test_mode":        Transcode_TEST_Mode,
            "move_originals":   not Transcode_TEST_Mode,  # siempre True en modo normal
            "delete_originals": self._delete_originals_chk.isChecked(),
        }
        _deana_active = (hasattr(self, "_convert_deana_chk")
                         and self._convert_deana_chk.isChecked())
        self._transcode_global_opts = {
            "compression":        self._target_compression(None),
            "dwa_level":          _DWAA_COMPRESSION_LEVEL,
            "resize_filter":      self._convert_filter.currentText(),
            "workers":            6,
            "channels":           ("rgb" if self._convert_channels.currentText() == "Reducir a RGB"
                                   else "all"),
            "pixel_aspect_ratio": 1.0 if _deana_active else None,
        }

        # Deshabilitar tabs mientras hay trabajo en curso (solo esta ventana)
        self._transcode_active = True
        self._start_transcode_btn.setEnabled(False)
        self._tab_bar.setTabEnabled(self.TAB_RENAME, False)
        self._tab_bar.setTabEnabled(self.TAB_IMPORT, False)
        self._convert_log.clear()

        self._transcode_results_all = []
        self._transcode_manager.enqueue_jobs(
            self._window_id,
            self.shot_name,
            job_sequences,
            self._transcode_global_opts,
            self._transcode_flags,
            str(SHARED_DIR),
            ui_parent=self,
        )

    def _start_next_sequence(self):
        """Saca la siguiente secuencia de la cola, la verifica y lanza su worker.

        - Si hay conflicto de archivos: muestra el diálogo de warning.
          Si el usuario cancela esa secuencia, pasa a la siguiente.
          Si confirma, borra los EXR existentes antes de empezar.
        - Cuando la cola se vacía, llama a _finalize_transcode().
        """
        flags = self._transcode_flags
        while self._sequence_queue:
            row_i, item, tw, th = self._sequence_queue.pop(0)
            has_conflict, conflict_desc = check_existing_outputs(
                item, flags["test_mode"], flags["move_originals"]
            )
            if has_conflict:
                seq_name = item.get("name") or Path(item["path"]).name
                proceed  = show_overwrite_warning(seq_name, conflict_desc, parent=self)
                if not proceed:
                    continue  # saltar esta secuencia, probar la siguiente
                try:
                    delete_existing_outputs(
                        item,
                        flags["test_mode"],
                        flags["move_originals"],
                        log_fn=lambda msg: debug_print("transcode cleanup %s" % msg),
                    )
                except Exception as exc:
                    self._set_convert_status(row_i, "✗ Error", _CLR_STATUS_ERROR)
                    self._append_log("Cleanup abortado: %s" % exc)
                    debug_print("transcode cleanup failed: %s" % exc)
                    continue

            # Lanzar worker para esta única secuencia
            worker = TranscodeWorker(
                [(row_i, item, tw, th)],
                self._transcode_global_opts,
                test_mode        = flags["test_mode"],
                move_originals   = flags["move_originals"],
                delete_originals = flags["delete_originals"],
                shared_dir       = str(SHARED_DIR),
            )
            worker.signals.log_message.connect(self._on_transcode_log)
            worker.signals.sequence_started.connect(self._on_sequence_started)
            worker.signals.sequence_done.connect(self._on_sequence_done)
            worker.signals.all_done.connect(self._on_worker_batch_done)
            worker.signals.error.connect(self._on_transcode_error)
            QtCore.QThreadPool.globalInstance().start(worker)
            debug_print("TranscodeWorker iniciado — secuencia %d" % row_i)
            return  # esperar a que termine antes de continuar con la cola

        # Cola vacía: todas las secuencias se procesaron (o se cancelaron)
        self._finalize_transcode()

    # ── Handlers de señales del worker ─────────────────────────

    def _on_transcode_log(self, msg):
        """Agrega una línea al panel de log de transcode."""
        self._convert_log.appendPlainText(msg)

    def _on_manager_transcode_log(self, window_id, msg):
        if window_id != self._window_id:
            return
        self._on_transcode_log(msg)

    def _on_manager_sequence_started(self, window_id, row_i, dst_dir_str, total_frames):
        if window_id != self._window_id:
            return
        self._on_sequence_started(row_i, dst_dir_str, total_frames)

    def _on_manager_sequence_done(self, window_id, row_i, ok, stats):
        if window_id != self._window_id:
            return
        self._on_sequence_done(row_i, ok, stats)

    def _on_manager_job_cancelled(self, window_id, row_i, result):
        if window_id != self._window_id:
            return
        if not hasattr(self, "_transcode_results_all"):
            self._transcode_results_all = []
        self._transcode_results_all.append(result)
        self._set_convert_status(row_i, "Cancelado", _CLR_STATUS_UPSCALE)

    def _on_manager_batch_done(self, window_id, results):
        if window_id != self._window_id:
            return
        self._transcode_results_all = list(results or [])
        self._finalize_transcode()

    def _on_manager_transcode_error(self, window_id, msg):
        if window_id != self._window_id:
            return
        self._on_transcode_error(msg)

    def _on_global_transcode_queue_changed(self, snapshot):
        """Actualiza etiquetas de fila y footer global segun la cola global."""
        if hasattr(self, "_convert_table"):
            for job in snapshot:
                if job.get("window_id") != self._window_id:
                    continue
                row_i = job.get("row_i")
                if row_i is None or row_i >= self._convert_table.rowCount():
                    continue
                status = job.get("status")
                if status == "queued":
                    pos = job.get("position") or 0
                    self._set_convert_status(row_i, "Queued #%d" % pos, _CLR_STATUS_PENDING)
                elif status in ("running", "starting"):
                    if not (hasattr(self, "_transcode_pbars") and row_i in self._transcode_pbars):
                        self._set_convert_status(row_i, "Procesando", _CLR_STATUS_PENDING)

        self._update_global_status_label(snapshot)

    def _update_global_status_label(self, snapshot):
        if not hasattr(self, "_status_labels"):
            return
        active = next((j for j in snapshot if j.get("status") in ("running", "starting")), None)
        pending = [j for j in snapshot if j.get("status") == "queued"]

        pre_text = ""
        shot_text = ""
        post_text = ""
        window_id = ""
        if not active and not pending:
            pass
        elif active:
            shot_text = active.get("shot_name", "")
            window_id = active.get("window_id", "")
            pending_count = len(pending)
            pre_text = "Convirtiendo plates del shot " if shot_text else "Convirtiendo plates"
            if pending_count:
                post_text = ". Plates restantes: %d" % pending_count if shot_text else " restantes: %d" % pending_count
        else:
            pre_text = "%d plates en fila" % len(pending)

        for parts in self._status_labels:
            try:
                if isinstance(parts, dict):
                    parts["pre"].setText(pre_text)
                    parts["shot"].setText(shot_text)
                    parts["shot"].setProperty("window_id", window_id)
                    parts["shot"].setProperty("shot_name", shot_text)
                    parts["shot"].setVisible(bool(shot_text))
                    parts["post"].setText(post_text)
                else:
                    # Compatibilidad con labels creados por una version anterior del dialogo.
                    text = pre_text + shot_text + post_text
                    parts.setText(text)
            except Exception:
                pass

    def _set_convert_status(self, row_i, text, color):
        if not hasattr(self, "_convert_table") or row_i >= self._convert_table.rowCount():
            return
        html = "<span style='color:%s;'>%s</span>" % (color, text)
        self._convert_table.setCellWidget(row_i, 7, _cell_html_label(html))

    # Estilo de la barra de progreso de transcode
    _PBAR_STYLE = """
        QProgressBar {
            background-color: #393959;
            border: none;
            border-radius: 5px;
            text-align: center;
            color: #cccccc;
            font-size: 9px;
            min-height: 16px;
            max-height: 22px;
        }
        QProgressBar::chunk {
            background-color: #443a91;
            border-radius: 5px;
        }
    """

    def _on_sequence_started(self, row_i, dst_dir_str, total_frames):
        """Crea barra de progreso en la columna Estado e inicia polling QTimer."""
        if row_i >= self._convert_table.rowCount():
            return

        pbar = QtWidgets.QProgressBar()
        pbar.setRange(0, max(total_frames, 1))
        pbar.setValue(0)
        pbar.setFormat("%v/%m")
        pbar.setStyleSheet(self._PBAR_STYLE)
        self._convert_table.setCellWidget(row_i, 7, pbar)

        # Inicializar dicts de timers/pbars si no existen
        if not hasattr(self, "_transcode_timers"):
            self._transcode_timers = {}
        if not hasattr(self, "_transcode_pbars"):
            self._transcode_pbars = {}

        dst_dir = Path(dst_dir_str)
        self._transcode_pbars[row_i] = pbar

        timer = QtCore.QTimer()
        timer.setInterval(300)
        timer.timeout.connect(
            lambda: self._poll_transcode_progress(row_i, dst_dir, total_frames, pbar)
        )
        self._transcode_timers[row_i] = timer
        timer.start()

    def _poll_transcode_progress(self, row_i, dst_dir, total_frames, pbar):
        """Cuenta archivos .exr en dst_dir y actualiza la barra de progreso."""
        if not dst_dir.exists():
            return
        try:
            done = sum(1 for _ in dst_dir.glob("*.exr"))
            pbar.setValue(min(done, total_frames))
        except Exception:
            pass

    def _on_sequence_done(self, row_i, ok, stats):
        """Detiene el timer de progreso y actualiza el Estado a DONE o Error."""
        # Detener y eliminar timer
        if hasattr(self, "_transcode_timers") and row_i in self._transcode_timers:
            self._transcode_timers[row_i].stop()
            del self._transcode_timers[row_i]
        if hasattr(self, "_transcode_pbars"):
            self._transcode_pbars.pop(row_i, None)

        if row_i < self._convert_table.rowCount():
            if ok:
                elapsed = ""
                try:
                    elapsed_v = float((stats or {}).get("elapsed_seconds") or 0.0)
                except Exception:
                    elapsed_v = 0.0
                if elapsed_v > 0.0:
                    elapsed = " (%.1fs)" % elapsed_v
                html = "<span style='color:%s;'>DONE%s</span>" % (_CLR_STATUS_DONE, elapsed)
            else:
                html = "<span style='color:%s;'>✗ Error</span>" % _CLR_STATUS_ERROR
            self._convert_table.setCellWidget(row_i, 7, _cell_html_label(html))

    def _on_worker_batch_done(self, results):
        """El worker de una secuencia terminó. Acumula resultados y arranca la siguiente."""
        self._transcode_results_all.extend(results)
        self._start_next_sequence()

    def _finalize_transcode(self):
        """Se llama cuando la cola queda vacía. Muestra resumen y re-habilita botones."""
        results  = self._transcode_results_all
        total    = len(results)
        ok_count = sum(1 for r in results if r.get("ok"))
        cancelled_count = sum(1 for r in results if r.get("cancelled"))
        if total == 0:
            summary = "⚠ Todas las secuencias fueron canceladas"
        elif ok_count == total:
            summary = "✓ Transcode completo: %d/%d OK" % (ok_count, total)
        elif cancelled_count and ok_count + cancelled_count == total:
            summary = "⚠ Transcode: %d/%d OK, %d canceladas" % (
                ok_count, total, cancelled_count
            )
        else:
            summary = "⚠ Transcode: %d/%d OK, %d con errores" % (
                ok_count, total, total - ok_count - cancelled_count
            )
        self._on_transcode_log(summary)
        self._transcode_active = False
        self._start_transcode_btn.setEnabled(True)
        self._tab_bar.setTabEnabled(self.TAB_RENAME, True)
        self._tab_bar.setTabEnabled(self.TAB_IMPORT, True)
        self._needs_refresh.update({"rename", "import"})
        self._update_transcode_btn_state()
        debug_print("Transcode all_done — %d/%d OK" % (ok_count, total))

    def _on_transcode_error(self, msg):
        """Error fatal en el worker: vacía la cola, re-habilita botones."""
        self._on_transcode_log("ERROR FATAL: " + msg)
        debug_print("Transcode error fatal: %s" % msg, level="error")
        if hasattr(self, "_sequence_queue"):
            self._sequence_queue.clear()
        if not hasattr(self, "_transcode_results_all"):
            self._transcode_results_all = []
        if not self._transcode_results_all:
            self._transcode_results_all.append({"ok": False, "error": msg})
        self._finalize_transcode()

    # ══════════════════════════════════════════════════════════
    #  Helpers
    # ══════════════════════════════════════════════════════════

    def _show_error(self, msg):
        QtWidgets.QMessageBox.critical(self, "Import Shot — Error", msg)

    def _run_set_shot_name(self):
        try:
            from LGA_NKS_Edit_Panel_py import LGA_NKS_SetShotName  # noqa: F401
        except Exception:
            pass

    def _run_create_v000(self):
        try:
            from LGA_NKS_Edit_Panel_py import LGA_NKS_CreateV000  # noqa: F401
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════
#  Singleton del diálogo (patrón no-bloqueante, igual que CreateV000)
# ══════════════════════════════════════════════════════════════════

class _BulkShotPanel(ImportShotDialog):
    """Editor liviano que reutiliza exactamente la tabla del import individual."""

    def __init__(self, entry, seq, parent=None):
        QtWidgets.QDialog.__init__(self, parent)
        self.setWindowFlags(QtCore.Qt.Widget)
        self.shot_root = entry["shot_root"]
        self.shot_name = entry["shot_name"]
        self.seq = seq
        self.insert_frame = entry["insert_frame"]
        self.frames_to_push = entry.get("max_frames", 100)
        self.prev_shot_name = entry.get("prev_shot_name")
        self.next_shot_name = entry.get("next_shot_name")
        self.input_items = entry["input_items"]
        self.publish_items = entry["publish_items"]
        self._track_overrides = {}
        self._create_v000_tasks = set()
        try:
            self._fps = float(seq.framerate().toFloat())
        except Exception:
            self._fps = 24.0

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(9, 9, 9, 9)
        layout.addWidget(self._build_media_table(), 1)
        buttons = QtWidgets.QHBoxLayout()
        for label, slot in [
            ("Select All", self._select_all),
            ("Clear", self._clear_selection),
            ("Plates", lambda: self._select_section("plates")),
            ("References", lambda: self._select_section("refs")),
            ("Publish", lambda: self._select_section("publish")),
        ]:
            button = QtWidgets.QPushButton(label)
            button.setStyleSheet(_BTN_SMALL)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)

    def selected_items(self):
        result = []
        for row, checkbox in self._checkboxes.items():
            if not checkbox.isChecked():
                continue
            row_data = self._table_rows[row]
            track = self._get_track_for_row(row)
            if row_data.get("type") == "data" and track:
                result.append((track, row_data["item"], self._item_hiero_color(row_data)))
        return result

    def master_duration(self):
        duration = max(
            (it.get("frame_count") or 0 for it in self.input_items
             if it.get("kind") == "exr_seq" and it.get("is_latest")),
            default=0,
        )
        return duration or 100


class BulkImportDialog(QtWidgets.QDialog):
    """Tabs editables por shot, preview combinado y ejecucion atomica del batch."""

    def __init__(self, seq, entries, skipped=None, parent=None):
        super(BulkImportDialog, self).__init__(parent)
        self.seq = seq
        self.entries = entries
        self.skipped = skipped or []
        self.panels = []
        self.setObjectName("LGA_BulkImportDialog")
        self.setWindowTitle("Bulk Import Shots — %d shots" % len(entries))
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose, True)
        self.setMinimumSize(1300, 700)
        self.setStyleSheet(_DIALOG_STYLE)

        root = QtWidgets.QVBoxLayout(self)
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet(ImportShotDialog._TAB_STYLE)
        for entry in entries:
            panel = _BulkShotPanel(entry, seq, self)
            self.panels.append(panel)
            self.tabs.addTab(panel, entry["shot_name"])
        self.preview_page = self._build_preview_page()
        self.tabs.addTab(self.preview_page, "PREVIEW")
        self.tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self.tabs, 1)

        footer = QtWidgets.QHBoxLayout()
        if self.skipped:
            skipped_text = "Omitidos (ya existen o repetidos): %s" % ", ".join(self.skipped)
            label = QtWidgets.QLabel(skipped_text)
            label.setStyleSheet("color:#c69a58;")
            label.setToolTip(skipped_text)
            footer.addWidget(label, 1)
        else:
            footer.addStretch(1)
        cancel = QtWidgets.QPushButton("Cancel")
        cancel.setStyleSheet(_BTN_SECONDARY)
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        self.import_button = QtWidgets.QPushButton("Import All (%d shots)" % len(entries))
        self.import_button.setStyleSheet(_BTN_PRIMARY)
        self.import_button.clicked.connect(self._do_bulk_import)
        footer.addWidget(self.import_button)
        root.addLayout(footer)

    def _build_preview_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        note = QtWidgets.QLabel(
            "Resultado combinado: desde el vecino anterior al primer shot nuevo "
            "hasta el vecino siguiente al ultimo. Nuevos en color; existentes en gris."
        )
        note.setStyleSheet("color:#999999; padding:3px;")
        layout.addWidget(note)
        self.preview_table = QtWidgets.QTableWidget()
        self.preview_table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.preview_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.preview_table.setFocusPolicy(QtCore.Qt.NoFocus)
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.setShowGrid(False)
        self.preview_table.setStyleSheet(_TABLE_STYLE)
        layout.addWidget(self.preview_table, 1)
        return page

    def _on_tab_changed(self, index):
        # Un tab puede haber creado un track. Refrescar las opciones del resto
        # sin alterar sus selecciones actuales.
        for panel in self.panels:
            panel._refresh_track_combo_options()
        if index == self.tabs.count() - 1:
            self._refresh_preview()

    def _preview_shots(self, layout_data):
        alpha = sorted(layout_data["final_shots"], key=lambda s: s["shot_name"].lower())
        new_indices = [i for i, shot in enumerate(alpha) if shot.get("is_new")]
        if not new_indices:
            return []
        first = max(0, min(new_indices) - 1)
        last = min(len(alpha) - 1, max(new_indices) + 1)
        return alpha[first:last + 1]

    def _existing_preview_data(self):
        """Clips existentes con geometria relativa para dibujarlos greyed out."""
        result = {}
        shot_ranges = {}
        for track in self.seq.videoTracks():
            try:
                track_name = track.name()
            except Exception:
                continue
            for item in track.items():
                if isinstance(item, hiero.core.EffectTrackItem):
                    continue
                try:
                    shot_name = item.name()
                    clip_name = item.source().name()
                    tl_in = int(item.timelineIn())
                    tl_out = int(item.timelineOut())
                except Exception:
                    continue
                result.setdefault((shot_name, track_name), []).append({
                    "name": clip_name,
                    "tl_in": tl_in,
                    "tl_out": tl_out,
                    "duration": max(1, tl_out - tl_in + 1),
                })
                bounds = shot_ranges.setdefault(shot_name, [tl_in, tl_out])
                bounds[0] = min(bounds[0], tl_in)
                bounds[1] = max(bounds[1], tl_out)
        return result, shot_ranges

    def _build_bulk_timeline_cell(self, clip, shot_start, shot_duration,
                                  color, is_new=False, offset_frames=None):
        """Bloque grafico proporcional, equivalente a las celdas del preview original."""
        helper = self.panels[0]
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(2, 3, 2, 3)
        layout.setSpacing(0)
        widget.setStyleSheet("background: transparent;")
        if not clip:
            return widget

        duration = max(0, int(clip.get("duration") or clip.get("frame_count") or 0))
        if offset_frames is None:
            offset_frames = max(0, int(clip.get("tl_in", shot_start)) - shot_start)
        master = max(1, int(shot_duration or 1))
        scale = 1000
        offset_weight = int(min(1.0, offset_frames / float(master)) * scale)
        chip_weight = max(1, int(min(1.0, duration / float(master)) * scale))
        total = offset_weight + chip_weight
        if total > scale:
            offset_weight = int(offset_weight * scale // total)
            chip_weight = max(1, scale - offset_weight)
        trail_weight = max(0, scale - offset_weight - chip_weight)

        if offset_weight:
            layout.addStretch(offset_weight)
        name = clip.get("name") or clip.get("version_name") or "?"
        label = helper._make_chip_label(
            name, color=color, is_new=is_new,
            frames=duration, fps=helper._fps,
        )
        if not is_new:
            label.setGraphicsEffect(None)
            label.setStyleSheet(
                "background:#303030; border:1px solid #595959; color:#858585; "
                "font-weight:normal; padding:4px 6px; border-radius:3px;"
            )
        layout.addWidget(label, chip_weight)
        if trail_weight:
            layout.addStretch(trail_weight)
        return widget

    def _refresh_preview(self):
        new_data = [{"shot_name": p.shot_name, "max_frames": p.master_duration()}
                    for p in self.panels]
        layout_data = bulk_mod.simulate_bulk_layout(
            _collect_timeline_shots(self.seq), new_data
        )
        shots = self._preview_shots(layout_data)
        selected = {}
        track_names = []
        try:
            track_names = [t.name() for t in reversed(list(self.seq.videoTracks()))]
        except Exception:
            pass
        for panel in self.panels:
            for track, item, color in panel.selected_items():
                selected.setdefault((panel.shot_name, track), []).append((item, color))
                if track not in track_names:
                    track_names.append(track)

        existing, existing_ranges = self._existing_preview_data()
        table = self.preview_table
        table.clearSpans()
        table.clear()
        table.setRowCount(len(track_names))
        table.setColumnCount(len(shots) + 2)
        table.setHorizontalHeaderLabels(["", "Track"] + [s["shot_name"] for s in shots])
        helper = self.panels[0]
        for row, track_name in enumerate(track_names):
            track_type = classify_track_type(track_name)
            bar_color = helper._track_bar_color(track_type)
            bar = QtWidgets.QTableWidgetItem()
            bar.setBackground(QtGui.QColor(bar_color))
            bar.setFlags(QtCore.Qt.NoItemFlags)
            table.setItem(row, 0, bar)
            track_item = QtWidgets.QTableWidgetItem(track_name)
            track_item.setForeground(QtGui.QColor(mix_colors(bar_color, "#ffffff", 0.58)))
            table.setItem(row, 1, track_item)

            if helper._is_burnin_track(track_name):
                if shots:
                    table.setSpan(row, 2, 1, len(shots))
                    table.setCellWidget(row, 2, helper._build_burnin_row())
                table.setRowHeight(row, 42)
                continue

            for col, shot in enumerate(shots, 2):
                key = (shot["shot_name"], track_name)
                if shot.get("is_new"):
                    entries = selected.get(key, [])
                    item, item_color = (
                        max(entries, key=lambda pair: pair[0].get("version_num", -1))
                        if entries else (None, bar_color)
                    )
                    shot_duration = max(
                        (candidate.get("frame_count") or 0
                         for (shot_key, _track), values in selected.items()
                         if shot_key == shot["shot_name"]
                         for candidate, _candidate_color in values),
                        default=max(1, shot["tl_out"] - shot["tl_in"] + 1),
                    )
                    offset = 0
                    if item and track_type == "editref":
                        offset = self._editref_offset(track_name, item, shot_duration)
                    clip = dict(item) if item else None
                    if clip:
                        clip["duration"] = clip.get("frame_count") or 0
                    cell_widget = self._build_bulk_timeline_cell(
                        clip, shot["tl_in"], shot_duration,
                        helper._chip_color(
                            (clip or {}).get("name", ""), item_color, track_type
                        ),
                        is_new=True, offset_frames=offset,
                    )
                else:
                    clips = existing.get(key, [])
                    clip = clips[0] if clips else None
                    bounds = existing_ranges.get(shot["shot_name"], [0, 0])
                    shot_duration = max(1, bounds[1] - bounds[0] + 1)
                    cell_widget = self._build_bulk_timeline_cell(
                        clip, bounds[0], shot_duration,
                        "#666666", is_new=False,
                    )
                table.setCellWidget(row, col, cell_widget)
            table.setRowHeight(row, 42)
        header = table.horizontalHeader()
        header.setMinimumSectionSize(1)
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Fixed)
        table.setColumnWidth(0, 5)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.Fixed)
        table.setColumnWidth(1, 130)
        for col, shot in enumerate(shots, 2):
            header.setSectionResizeMode(col, QtWidgets.QHeaderView.Interactive)
            table.setColumnWidth(col, 220)
            header_item = table.horizontalHeaderItem(col)
            header_item.setForeground(QtGui.QColor(
                "#a88ee0" if shot.get("is_new") else "#686868"
            ))

    @staticmethod
    def _editref_offset(track_name, item, master_duration):
        if classify_track_type(track_name) != "editref":
            return 0
        duration = item.get("frame_count") or 0
        return max(0, master_duration - duration) // 2

    def _do_bulk_import(self):
        empty = [p.shot_name for p in self.panels if not p.selected_items()]
        if empty:
            _show_tool_message(
                self, "Bulk Import",
                "Estos shots no tienen items seleccionados con track asignado:\n%s"
                % "\n".join(empty),
            )
            return

        project = None
        try:
            project = self.seq.project()
        except Exception:
            pass
        errors, placed_items = [], []

        def run():
            for panel in sorted(self.panels, key=lambda p: p.shot_name.lower()):
                duration = panel.master_duration()
                selected_items = panel.selected_items()
                selected_master = max(
                    (item.get("frame_count") or 0
                     for _track, item, _color in selected_items),
                    default=duration,
                )
                insert_frame, frames_to_push, _prev, _next = _find_insert_frame(
                    self.seq, panel.shot_name, duration
                )
                effective_frame = insert_frame
                if frames_to_push > 0:
                    _moved, effective_frame = timeline_mod.push_clips_right(
                        self.seq, insert_frame, frames_to_push
                    )
                target_bin = bin_mod.find_or_create_shot_bin(self.seq, panel.shot_name)
                for track_name, item, color in selected_items:
                    clip_name = item.get("name") or item.get("version_name") or "?"
                    clip, error = bin_mod.import_item_to_bin(item, target_bin)
                    if error:
                        errors.append("%s / %s (bin): %s" %
                                      (panel.shot_name, clip_name, error))
                        continue
                    try:
                        clip.binItem().setColor(QtGui.QColor(color))
                    except Exception:
                        pass
                    frame_count = item.get("frame_count") or 0
                    if not frame_count:
                        try:
                            frame_count = clip.mediaSource().duration()
                        except Exception:
                            frame_count = 0
                    clip_in = effective_frame + self._editref_offset(
                        track_name, item, selected_master
                    )
                    timeline_item, error = timeline_mod.place_clip_in_timeline(
                        self.seq, clip, track_name, clip_in, frame_count, panel.shot_name
                    )
                    if error:
                        errors.append("%s / %s (timeline): %s" %
                                      (panel.shot_name, clip_name, error))
                    elif timeline_item is not None:
                        placed_items.append(timeline_item)
            if placed_items:
                timeline_mod.stretch_burnin(self.seq)
                valid = [item for item in placed_items if item.parentTrack() is not None]
                if valid:
                    self.seq.setInTime(min(int(item.timelineIn()) for item in valid))
                    self.seq.setOutTime(max(int(item.timelineOut()) for item in valid))

        self.import_button.setEnabled(False)
        try:
            if project:
                with project.beginUndo("Bulk Import: %d shots" % len(self.panels)):
                    run()
            else:
                run()
        finally:
            self.import_button.setEnabled(True)

        if placed_items:
            tc_in = min(int(item.timelineIn()) for item in placed_items
                        if item.parentTrack() is not None)
            tc_out = max(int(item.timelineOut()) for item in placed_items
                         if item.parentTrack() is not None)
            timeline_mod.set_viewer_to_shot(self.seq, tc_in, tc_out)
        if errors:
            QtWidgets.QMessageBox.warning(
                self, "Bulk Import — errores parciales",
                "%d items colocados.\n\n%s" % (len(placed_items), "\n".join(errors)),
            )
        self.accept()


_import_shot_dialog_instance = None
_bulk_import_dialog_instance = None


def _clear_import_dialog(*_):
    """Libera la referencia global al diálogo cuando se cierra."""
    global _import_shot_dialog_instance
    _import_shot_dialog_instance = None


def _visible_import_dialog_for_shot(shot_name):
    app = QtWidgets.QApplication.instance()
    if not app:
        return None

    shot_key = (shot_name or "").strip().lower()
    for widget in app.topLevelWidgets():
        try:
            if (
                widget.objectName() == "LGA_ImportShotDialog"
                and widget.isVisible()
                and str(widget.property("shot_name") or "").strip().lower() == shot_key
            ):
                return widget
        except Exception:
            continue
    return None


def _launch_create_v000():
    """
    Llama a LGA_NKS_CreateV000.main() tal como lo hace el Edit Panel.
    Se invoca desde QTimer.singleShot(0, ...) para que el diálogo de import
    esté completamente cerrado antes de que CreateV000 abra su ventana.
    """
    try:
        _cv0_key = "LGA_NKS_Edit_Panel_py.LGA_NKS_CreateV000"
        if _cv0_key in sys.modules:
            del sys.modules[_cv0_key]
        _cv0 = importlib.import_module(_cv0_key)
        _cv0.main()
        debug_print("_launch_create_v000: CreateV000 abierto")
    except Exception as exc:
        debug_print("_launch_create_v000: error → %s" % exc, level="warning")


# ══════════════════════════════════════════════════════════════════
#  Entry point
# ══════════════════════════════════════════════════════════════════

def main():
    debug_print("=== LGA_import_shots start ===")

    seq = hiero.ui.activeSequence()
    if not seq:
        QtWidgets.QMessageBox.warning(
            None, "Import Shot", "No hay sequence activa."
        )
        return

    # Seleccionar carpeta. Reutiliza la ultima elegida si sigue disponible.
    browser_settings = settings_mod.load_all_settings()
    initial_directory = browser_settings.get("ui", {}).get(
        "last_shot_directory", ""
    )
    if not initial_directory or not Path(initial_directory).is_dir():
        initial_directory = ""

    shot_roots = bulk_mod.pick_shot_folders(initial_directory, parent=None)
    if not shot_roots:
        debug_print("Cancelled — no folder selected")
        return

    shot_roots = [root.replace("\\", "/") for root in shot_roots]
    shot_root = shot_roots[0]
    settings_mod.save_all_settings({
        "ui": {
            "last_shot_directory": shot_root,
        }
    })

    if len(shot_roots) > 1:
        global _bulk_import_dialog_instance
        seen_names = set()
        skipped = []
        entries = []
        timeline_shots = _collect_timeline_shots(seq)
        timeline_names = {shot["shot_name"].lower() for shot in timeline_shots}
        for root in shot_roots:
            name = _get_shot_name_from_folder(root)
            key = name.lower()
            if (key in seen_names or key in timeline_names
                    or _shot_exists_in_timeline(seq, name, root)):
                skipped.append(name)
                continue
            seen_names.add(key)
            debug_print("Bulk scan: %s" % root)
            input_items = _scan_input_folder(root)
            publish_items = _scan_publish_folders(root)
            max_frames = max(
                (item.get("frame_count") or 0 for item in input_items
                 if item.get("kind") == "exr_seq" and item.get("is_latest")),
                default=0,
            ) or 100
            entries.append({
                "shot_root": root,
                "shot_name": name,
                "input_items": input_items,
                "publish_items": publish_items,
                "max_frames": max_frames,
            })

        if not entries:
            _show_tool_message(
                None, "Bulk Import",
                "Todos los shots seleccionados ya existen en el timeline o estan repetidos."
            )
            return

        placements = bulk_mod.simulate_bulk_layout(
            timeline_shots, entries
        )["placements"]
        dlg = BulkImportDialog(seq, placements, skipped=skipped)

        def _clear_bulk(*_args):
            global _bulk_import_dialog_instance
            _bulk_import_dialog_instance = None

        dlg.finished.connect(_clear_bulk)
        dlg.destroyed.connect(_clear_bulk)
        _bulk_import_dialog_instance = dlg
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        return

    shot_name = _get_shot_name_from_folder(shot_root)
    set_debug_context(shot_name)
    debug_print("Shot root: %s  shot_name: %s" % (shot_root, shot_name))

    existing_dialog = _visible_import_dialog_for_shot(shot_name)
    if existing_dialog:
        _show_tool_message(
            None,
            "Import Shot",
            "Ya hay una ventana de Import Shot abierta para '%s'.\n\n"
            "No se puede abrir otra ventana para el mismo shot." % shot_name,
        )
        existing_dialog.raise_()
        existing_dialog.activateWindow()
        debug_print("Aborted — import dialog already open: %s" % shot_name, level="warning")
        return

    # Verificar si ya existe
    if _shot_exists_in_timeline(seq, shot_name, shot_root):
        confirm = _show_shot_exists_confirm(shot_name)
        if not confirm:
            debug_print("Aborted — shot already exists: %s" % shot_name, level="warning")
            return
        debug_print("User chose to continue despite existing shot: %s" % shot_name, level="warning")

    # Analizar carpeta
    debug_print("Scanning _input...")
    input_items = _scan_input_folder(shot_root)
    debug_print("Found %d input items" % len(input_items))

    debug_print("Scanning publish folders...")
    publish_items = _scan_publish_folders(shot_root)
    debug_print("Found %d publish entries" % len(publish_items))

    # Calcular duracion del plate mas largo para posicionamiento
    max_frames = max(
        (it["frame_count"] for it in input_items
         if it["kind"] == "exr_seq" and it.get("is_latest")),
        default=0
    )
    if max_frames == 0:
        max_frames = 100  # fallback si no hay EXR todavia

    insert_frame, frames_to_push, prev_shot_name, next_shot_name = _find_insert_frame(
        seq, shot_name, max_frames)
    debug_print("Insert frame: %d  push: %d  duration: %d  prev='%s'  next='%s'" % (
        insert_frame, frames_to_push, max_frames,
        prev_shot_name or "", next_shot_name or ""))

    # Abrir dialogo (no bloqueante — igual que CreateV000)
    global _import_shot_dialog_instance

    debug_print("Creating ImportShotDialog...")
    try:
        dlg = ImportShotDialog(
            shot_root, shot_name, seq,
            insert_frame, frames_to_push,
            prev_shot_name, next_shot_name,
            input_items, publish_items,
        )
    except Exception as exc:
        debug_print("ImportShotDialog creation failed: %s" % exc, level="error")
        debug_print(traceback.format_exc(), level="error")
        raise
    debug_print("ImportShotDialog created")
    dlg.finished.connect(_clear_import_dialog)
    dlg.destroyed.connect(_clear_import_dialog)
    _import_shot_dialog_instance = dlg
    debug_print("ImportShotDialog show...")
    dlg.show()
    dlg.raise_()
    dlg.activateWindow()
    debug_print("ImportShotDialog shown")


if __name__ == "__main__":
    main()
