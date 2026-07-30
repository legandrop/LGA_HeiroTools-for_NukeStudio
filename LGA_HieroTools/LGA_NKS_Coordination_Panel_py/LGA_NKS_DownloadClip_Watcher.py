"""
____________________________________________________________________

  LGA_NKS_DownloadClip_Watcher v1.04 | Lega

  v1.04: Ramas de version. Lee los intents que escribe DownloadClip en
         logs/download_clip_intent/ y sube el clip a la version que realmente
         se descargo; si la descarga fue de la rama de otro compositor no
         toca el clip. Sin intent (marcador latest de FileManager) sube a la
         cabeza de la RAMA del clip y ya no al maximo global, que podia
         saltarlo a la rama de otro.
  v1.03: Soporta markers "latest" para subir version del clip en timeline
         (flujo equivalente a Flow Pull: VersionScanner + setActiveVersion).
  v1.02: Tras reconectar, hace un toggle del estado enabled del track item
         para forzar el refresco del viewer (evita que se vea negro).
  v1.01: Watcher reubicado en la carpeta del panel; lo arranca el panel.
  v1.00: Version inicial.

  Watcher de finalizacion de descargas del boton "Download Clip"
  (LGA_NKS_FileManager_DownloadClip.py).

  Lo arranca el Coordination Panel (LGA_NKS_Coordination_Panel.py) al
  cargarse en el arranque de Hiero. Cada pocos segundos revisa la carpeta
  de marcadores (logs/download_clip_done/) donde FileManager escribe un
  .json al terminar cada descarga CLI lanzada con --notify-completion.
  Cuando aparece un marcador, busca el/los clip(s) cuyo media coincide
  con la ruta descargada y los reconecta automaticamente.

  Diseno:
  - Corre en el hilo principal de Hiero via QTimer (la reconexion toca
    la API de Hiero y debe ejecutarse en el main thread). No bloquea: el
    callback es trabajo de milisegundos.
  - Es stateless entre ticks: solo reacciona a marcadores que aparecen.
    Si una descarga se cancela, FileManager se cierra o crashea, no se
    escribe marcador y el watcher simplemente sigue idle.
  - Cada marcador se borra siempre tras procesarlo (haya match o no).
  - Marcadores sin clip que matchee se reintentan hasta un TTL y luego
    se descartan, para evitar huerfanos eternos.
____________________________________________________________________
"""

import os
import sys
import json
import glob
import time
import re
import logging
import queue
from logging.handlers import QueueHandler, QueueListener
import traceback

# Intervalo de sondeo de la carpeta de marcadores
POLL_INTERVAL_MS = 5000
# Tiempo maximo que se conserva un marcador sin clip que matchee
MARKER_TTL_SECONDS = 1800  # 30 min

# Variables globales de logging
DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True
script_start_time = None
debug_log_listener = None
debug_logger = None

# Importar QtCore (mismo adaptador que usan los paneles)
QtCore = None
try:
    # La raiz Startup es el padre de la carpeta de este script
    _startup_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if _startup_dir not in sys.path:
        sys.path.insert(0, _startup_dir)
    from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore  # type: ignore
except Exception as _qt_err:
    try:
        from PySide6 import QtCore  # type: ignore
    except Exception:
        try:
            from PySide2 import QtCore  # type: ignore
        except Exception:
            print(f"[DownloadClipWatcher] No se pudo importar QtCore: {_qt_err}")

# Ramas: los intents dicen a que version subir el clip y el helper de ramas
# evita saltar de rama cuando no hay intent.
read_intent = None
clear_intent = None
head_of_branch_containing = None
try:
    _shared_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "LGA_NKS_Shared"
    )
    if _shared_dir not in sys.path:
        sys.path.insert(0, _shared_dir)
    from LGA_NKS_BranchDownloadPlan import clear_intent, read_intent  # type: ignore
    from LGA_NKS_VersionBranching import head_of_branch_containing  # type: ignore
except Exception as _branch_err:
    print(f"[DownloadClipWatcher] No se pudo importar el helper de ramas: {_branch_err}")


class RelativeTimeFormatter(logging.Formatter):
    """Formatter que incluye tiempo relativo desde el inicio del script."""

    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created
        relative_time = record.created - script_start_time
        record.relative_time = f"{relative_time:.3f}s"
        return super().format(record)


def setup_debug_logging(script_name="DownloadClipWatcher"):
    """Configura el logging para escribir SOLO en archivo (limpieza por ejecucion)."""
    global debug_log_listener

    log_filename = f"debugPy_{script_name}.log"
    log_file_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "logs", log_filename
    )
    log_file_path = os.path.abspath(log_file_path)
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    try:
        with open(log_file_path, "w", encoding="utf-8") as f:
            f.write(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    except Exception as e:
        print(f"[DownloadClipWatcher] Warning: no se pudo limpiar el log: {e}")

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


try:
    debug_logger = setup_debug_logging(script_name="DownloadClipWatcher")
except Exception as _e:
    print(f"[DownloadClipWatcher] FALLO al inicializar logger: {_e}")


def debug_print(*message, level="info"):
    global script_start_time

    msg = " ".join(str(arg) for arg in message)

    if DEBUG and DEBUG_LOG and debug_logger is not None:
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


def get_marker_dir():
    """Carpeta vigilada donde FileManager escribe los marcadores de finalizacion.

    Debe coincidir con get_notify_dir() de LGA_NKS_FileManager_DownloadClip.py.
    """
    marker_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "logs", "download_clip_done"
    )
    return os.path.abspath(marker_dir)


def get_intent_dir():
    """Carpeta de intents que escribe LGA_NKS_FileManager_DownloadClip.py.

    Debe coincidir con get_intent_dir() de ese modulo. El intent dice a que
    version subir el clip: el marcador de FileManager solo trae la ruta
    descargada y con eso no se puede distinguir "bajaron mi rama" de
    "bajaron la rama de otro".
    """
    intent_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "logs", "download_clip_intent"
    )
    return os.path.abspath(intent_dir)


def _normalize_path(path):
    """Normaliza una ruta para comparar (Windows es case-insensitive)."""
    norm = os.path.normpath(str(path)).replace("\\", "/").lower()
    return norm.rstrip("/")


def _safe_remove(path):
    try:
        os.remove(path)
    except Exception as e:
        debug_print(f"No se pudo borrar el marcador {path}: {e}", level="warning")


def _iter_all_track_items():
    """Itera todos los track items de todas las secuencias abiertas en Hiero."""
    try:
        import hiero.core
    except Exception as e:
        debug_print(f"hiero.core no disponible: {e}", level="error")
        return

    sequences = []
    try:
        for project in hiero.core.projects():
            try:
                sequences.extend(project.sequences())
            except Exception:
                pass
    except Exception as e:
        debug_print(f"No se pudieron listar proyectos: {e}", level="warning")

    if not sequences:
        try:
            import hiero.ui

            active = hiero.ui.activeSequence()
            if active:
                sequences = [active]
        except Exception:
            pass

    for seq in sequences:
        try:
            for track in seq.videoTracks():
                for item in track.items():
                    yield item
        except Exception:
            continue


def _refresh_viewer_cache(item, clip_name):
    """Fuerza refresco visual del viewer para evitar frame negro cacheado."""
    try:
        was_enabled = item.isEnabled()
        item.setEnabled(not was_enabled)
        item.setEnabled(was_enabled)
        debug_print(f"Viewer refrescado (toggle enabled) para: {clip_name}")
    except Exception as toggle_error:
        debug_print(
            f"No se pudo refrescar el viewer para '{clip_name}': {toggle_error}",
            level="warning",
        )


def _reconnect_clip(item):
    """Reconecta el media de un track item (reconnectMedia con fallback refresh)."""
    try:
        clip_name = item.name()
    except Exception:
        clip_name = "<sin nombre>"

    try:
        source = item.source()
        media_source = source.mediaSource()
        was_online = media_source.isMediaPresent()
    except Exception as e:
        debug_print(f"No se pudo acceder al media de '{clip_name}': {e}", level="error")
        return False

    try:
        source.reconnectMedia()
        debug_print(f"reconnectMedia ejecutado para: {clip_name}")
    except Exception as reconnect_error:
        debug_print(
            f"reconnectMedia fallo ({reconnect_error}), intentando refresh",
            level="warning",
        )
        try:
            media_source.refresh()
            debug_print(f"refresh ejecutado como fallback para: {clip_name}")
        except Exception as refresh_error:
            debug_print(f"refresh tambien fallo: {refresh_error}", level="error")

    try:
        now_online = item.source().mediaSource().isMediaPresent()
    except Exception:
        now_online = False

    # Forzar refresco del viewer para limpiar cache visual de offline.
    _refresh_viewer_cache(item, clip_name)

    debug_print(f"Clip '{clip_name}': online {was_online} -> {now_online}")
    return True


def _extract_version_number(text):
    """Extrae el numero de version usando el ultimo token _v### del nombre."""
    matches = list(re.finditer(r"_v(\d+)", str(text), re.IGNORECASE))
    if not matches:
        return -1
    try:
        return int(matches[-1].group(1))
    except Exception:
        return -1


def _pick_version(bin_item, target_version=None, current_version=None):
    """Elige a que Version del binItem cambiar.

    - `target_version`: la version que se acaba de descargar (viene del
      intent). Es la eleccion mas precisa: se baja eso, se muestra eso.
    - Si no esta disponible, la cabeza de la RAMA del clip. Nunca el maximo
      global: la version mas alta puede ser de la rama de otro compositor
      y saltar ahi cambia el trabajo que el artista tiene en pantalla.
    """
    try:
        versions = list(bin_item.items())
    except Exception:
        return None
    if not versions:
        return None

    numbers = [_extract_version_number(v.name()) for v in versions]

    if target_version is not None:
        for version, number in zip(versions, numbers):
            if number == target_version:
                return version
        debug_print(
            f"La version descargada v{target_version} no aparece en el binItem; "
            "se usa la cabeza de la rama",
            level="warning",
        )

    if current_version is None or head_of_branch_containing is None:
        # Sin rama que respetar (o sin helper) queda el comportamiento viejo.
        try:
            return max(versions, key=lambda v: _extract_version_number(v.name()))
        except Exception:
            return None

    head = head_of_branch_containing(numbers, current_version)
    for version, number in zip(versions, numbers):
        if number == head:
            return version
    return None


def _switch_clip_to_version(item, target_version=None):
    """Cambia la version activa del clip tras una descarga.

    Con `target_version` va exactamente a la version descargada; sin ella,
    a la cabeza de la rama del clip (ver _pick_version).
    """
    try:
        import hiero.core
    except Exception as e:
        debug_print(f"hiero.core no disponible para versionado: {e}", level="error")
        return False

    try:
        clip_name = item.name()
    except Exception:
        clip_name = "<sin nombre>"

    try:
        source = item.source()
        media_source = source.mediaSource()
        was_online = media_source.isMediaPresent()
    except Exception as e:
        debug_print(
            f"No se pudo acceder al media para versionado de '{clip_name}': {e}",
            level="error",
        )
        return False

    try:
        bin_item = source.binItem()
    except Exception:
        bin_item = None
    if not bin_item:
        debug_print(f"No se pudo obtener binItem para '{clip_name}'", level="warning")
        return False

    try:
        active_version = bin_item.activeVersion()
    except Exception:
        active_version = None
    if not active_version:
        debug_print(
            f"No hay activeVersion disponible para '{clip_name}'", level="warning"
        )
        return False

    try:
        vc = hiero.core.VersionScanner()
        vc.doScan(active_version)
    except Exception as scan_error:
        debug_print(
            f"VersionScanner.doScan fallo para '{clip_name}': {scan_error}",
            level="warning",
        )

    current_version = _extract_version_number(active_version.name())
    highest_version = _pick_version(
        bin_item, target_version=target_version, current_version=current_version
    )
    if highest_version is None:
        debug_print(
            f"No se pudo determinar la version destino para '{clip_name}'",
            level="warning",
        )
        return False

    try:
        old_name = active_version.name()
    except Exception:
        old_name = "<desconocida>"
    try:
        new_name = highest_version.name()
    except Exception:
        new_name = "<desconocida>"

    try:
        bin_item.setActiveVersion(highest_version)
        debug_print(
            f"setActiveVersion aplicado para '{clip_name}': {old_name} -> {new_name}"
        )
    except Exception as set_error:
        debug_print(
            f"No se pudo setActiveVersion para '{clip_name}': {set_error}",
            level="error",
        )
        return False

    # Si estaba offline (o sigue offline), intentar reconectar media del source.
    try:
        now_online = source.mediaSource().isMediaPresent()
    except Exception:
        now_online = False
    if (not was_online) or (not now_online):
        try:
            source.reconnectMedia()
            debug_print(f"reconnectMedia ejecutado tras cambio de version: {clip_name}")
        except Exception as reconnect_error:
            debug_print(
                f"reconnectMedia fallo tras cambio de version ({reconnect_error}), "
                "intentando refresh",
                level="warning",
            )
            try:
                source.mediaSource().refresh()
            except Exception as refresh_error:
                debug_print(
                    f"refresh tambien fallo tras cambio de version: {refresh_error}",
                    level="error",
                )

    try:
        now_online = source.mediaSource().isMediaPresent()
    except Exception:
        now_online = False

    _refresh_viewer_cache(item, clip_name)
    debug_print(
        f"Clip '{clip_name}' (versionado): online {was_online} -> {now_online}"
    )
    return True


def _find_and_apply(target_path, kind, action_fn, action_name):
    """Busca clips por path y aplica una accion (reconnect / latest switch)."""
    if not target_path:
        return 0
    target_norm = _normalize_path(target_path)
    matched = 0

    try:
        import hiero.core
    except Exception:
        hiero = None

    for item in _iter_all_track_items():
        try:
            if hiero is not None and isinstance(item, hiero.core.EffectTrackItem):
                continue
        except Exception:
            pass

        try:
            media_source = item.source().mediaSource()
            fileinfos = media_source.fileinfos()
            if not fileinfos:
                continue
            clip_path = fileinfos[0].filename()
        except Exception:
            continue

        clip_key = (
            _normalize_path(os.path.dirname(clip_path))
            if kind == "folder"
            else _normalize_path(clip_path)
        )

        if clip_key != target_norm:
            continue

        try:
            item_name = item.name()
        except Exception:
            item_name = "?"
        debug_print(f"Match ({kind}/{action_name}): clip '{item_name}' <- {target_path}")
        try:
            action_fn(item)
        except Exception as action_error:
            debug_print(
                f"Error aplicando accion '{action_name}' a '{item_name}': {action_error}",
                level="error",
            )
        matched += 1

    return matched


def _find_and_reconnect(target_path, kind):
    """Busca y reconecta los clips cuyo media coincide con target_path.

    kind == 'file'   -> match exacto contra la ruta del media.
    kind == 'folder' -> match contra el dirname del media (secuencia).
    Devuelve la cantidad de clips encontrados (procesados).
    """
    return _find_and_apply(target_path, kind, _reconnect_clip, "reconnect")


def _find_and_switch_to_latest(target_path, kind):
    """Busca clips por path original y los sube a la cabeza de SU rama."""
    return _find_and_apply(
        target_path, kind, _switch_clip_to_version, "switch-branch-head"
    )


def _apply_intent(intent, downloaded_path, kind):
    """Aplica el intent de una descarga por ramas.

    Devuelve cuantos "asuntos" quedaron atendidos, para que el marcador se
    pueda borrar. Una descarga de rama ajena cuenta como atendida aunque no
    toque ningun clip: se bajo lo que se pidio y el clip no se mueve.
    """
    intent_dir = get_intent_dir()
    clip_path = intent.get("clip_path")
    target_version = intent.get("version")
    branch_label = intent.get("branch_label", "?")

    if not intent.get("switch"):
        debug_print(
            f"Intent de rama {branch_label} sin cambio de version: se bajo la rama "
            "de otro compositor y el clip queda donde estaba."
        )
        if clear_intent is not None:
            clear_intent(intent_dir, downloaded_path)
        return 1

    matched = 0
    if clip_path:
        matched = _find_and_apply(
            clip_path,
            intent.get("kind", kind),
            lambda item: _switch_clip_to_version(item, target_version),
            f"switch-v{target_version}",
        )
    if matched == 0 and downloaded_path:
        # El clip pudo haber cambiado de ruta (o ya estar en la version nueva):
        # al menos se intenta reconectar por la ruta descargada.
        matched = _find_and_reconnect(downloaded_path, kind)

    if matched and clear_intent is not None:
        clear_intent(intent_dir, downloaded_path)
    return matched


def _process_marker(marker_path):
    """Procesa un marcador .json: reconecta los clips y/o borra el marcador."""
    try:
        with open(marker_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        debug_print(
            f"Marcador corrupto, se descarta: {marker_path} ({e})", level="error"
        )
        _safe_remove(marker_path)
        return

    task_id = data.get("task_id", "?")
    success = bool(data.get("success", False))
    items = data.get("items", []) or []

    if not success:
        debug_print(
            f"Descarga fallida (task {task_id}): no se reconecta. Marcador descartado.",
            level="warning",
        )
        _safe_remove(marker_path)
        return

    intent_dir = get_intent_dir()
    total_matched = 0
    for entry in items:
        path = entry.get("path")  # path resuelto/descargado
        kind = entry.get("kind", "file")
        requested_path = entry.get("requested_path")  # path original del clip
        is_latest = bool(entry.get("latest", False))

        # Descarga por ramas: DownloadClip dejo un intent con la version exacta
        # que se bajo y si el clip tiene que moverse ahi.
        intent = None
        if path and read_intent is not None:
            try:
                intent = read_intent(intent_dir, path)
            except Exception as intent_error:
                debug_print(
                    f"No se pudo leer el intent de {path}: {intent_error}",
                    level="warning",
                )

        if intent is not None:
            total_matched += _apply_intent(intent, path, kind)
            continue

        if is_latest and requested_path:
            # Marcador latest de FileManager (flujo viejo o fallback): se sube
            # el clip pero acotado a su rama, nunca al maximo global.
            matched_latest = _find_and_switch_to_latest(requested_path, kind)
            total_matched += matched_latest
            if matched_latest == 0 and path:
                # Fallback: si no encontro por path original, intentar reconexion por path resuelto
                total_matched += _find_and_reconnect(path, kind)
        else:
            if not path:
                continue
            total_matched += _find_and_reconnect(path, kind)

    if total_matched > 0:
        debug_print(
            f"Marcador {task_id} procesado: {total_matched} clip(s) reconectado(s). Se borra."
        )
        _safe_remove(marker_path)
        return

    # No se encontro ningun clip que matchee: reintentar hasta el TTL
    try:
        age = time.time() - os.path.getmtime(marker_path)
    except Exception:
        age = MARKER_TTL_SECONDS + 1

    if age > MARKER_TTL_SECONDS:
        debug_print(
            f"Marcador {task_id} sin clip que matchee y vencido ({age:.0f}s). Se descarta.",
            level="warning",
        )
        _safe_remove(marker_path)
    else:
        debug_print(
            f"Marcador {task_id}: sin clip que matchee aun, se reintentara (edad {age:.0f}s)"
        )


def _scan_markers():
    """Escanea la carpeta de marcadores y procesa los .json presentes."""
    marker_dir = get_marker_dir()
    if not os.path.isdir(marker_dir):
        return

    markers = glob.glob(os.path.join(marker_dir, "*.json"))
    for marker_path in markers:
        try:
            _process_marker(marker_path)
        except Exception as e:
            debug_print(
                f"Error procesando marcador {marker_path}: {e}", level="error"
            )
            debug_print(traceback.format_exc(), level="error")


if QtCore is not None:

    class DownloadClipWatcher(QtCore.QObject):
        """QObject con un QTimer que vigila la carpeta de marcadores."""

        def __init__(self):
            super(DownloadClipWatcher, self).__init__()
            self._timer = QtCore.QTimer(self)
            self._timer.setInterval(POLL_INTERVAL_MS)
            self._timer.timeout.connect(self._on_tick)
            self._timer.start()
            debug_print(
                f"=== DownloadClip Watcher iniciado (cada {POLL_INTERVAL_MS} ms) ==="
            )
            debug_print(f"Vigilando: {get_marker_dir()}")

        def _on_tick(self):
            try:
                _scan_markers()
            except Exception as e:
                debug_print(f"Error en tick del watcher: {e}", level="error")
                debug_print(traceback.format_exc(), level="error")


# Instancia global del watcher (referencia para evitar garbage collection)
_watcher_instance = None


def start_watcher():
    """Inicia el watcher si aun no esta corriendo."""
    global _watcher_instance
    if QtCore is None:
        print("[DownloadClipWatcher] QtCore no disponible, watcher no iniciado")
        return
    if _watcher_instance is None:
        _watcher_instance = DownloadClipWatcher()


# Al cargarse el modulo, arrancar el watcher automaticamente.
try:
    start_watcher()
except Exception as _e:
    print(f"[DownloadClipWatcher] No se pudo iniciar el watcher: {_e}")
    traceback.print_exc()
