"""
____________________________________________________________________

  LGA_NKS_FileManager_DownloadClip v1.01 | Lega

  Descarga el/los clip(s) seleccionado(s) desde Wasabi S3 usando
  FileManager CLI. A diferencia de "Download Shot", descarga solo el
  media del clip, no la carpeta entera del shot.

  - Archivo de video unico (.mov, .mp4)  -> FileManager --download-file <archivo>
  - Secuencia de imagenes (%04d.exr ...) -> FileManager --download <carpeta de la secuencia>
  Todos los clips seleccionados se envian en una sola llamada al CLI.

  Pasa --notify-completion para que FileManager escriba un marcador al terminar
  cada descarga; el watcher LGA_NKS_DownloadClip_Watcher.py lo detecta y reconecta
  el clip offline automaticamente.

  v1.01: migra al helper central FileManagerS3 + --context studio/client.
         Conserva --notify-completion y modo latest.

  v1.00: Soporta modo latest (Shift+Click) para descargar la version mas nueva
         via CLI de FileManager (--download-latest / --download-latest-file).

  v0.04: Agrega --notify-completion para reconexion automatica del clip al terminar.

  v0.03: Implementa la descarga real via FileManager CLI.
         Distingue archivo unico (singleFile) vs secuencia.

  v0.02: Usa el Metodo 1 (seleccion pura de clips, sin playhead).
         Soporta uno o varios clips seleccionados a la vez.

  v0.01: Solo imprime via debug_print:
        - Nombre del clip
        - Ruta del clip
        - Estado online/offline del media
____________________________________________________________________
"""

from pathlib import Path
import sys
import os
import subprocess
import logging
import queue
from logging.handlers import QueueHandler, QueueListener
import datetime
import time
import traceback

# Agregar ruta de shared modules
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists() and str(utils_path) not in sys.path:
    sys.path.insert(0, str(utils_path))

from LGA_NKS_Shared.LGA_NKS_FileManagerLauncher import (
    build_filemanager_command,
    resolve_context_mode,
)

# Variables globales de logging
DEBUG = False
DEBUG_CONSOLE = False
DEBUG_LOG = True
script_start_time = None
debug_log_listener = None
debug_logger = None
_log_file_path_resolved = None

# Variable de desarrollo para cambiar la ruta del ejecutable
Desarrollo = True


def get_notify_dir():
    """Carpeta donde FileManager escribe los marcadores de finalizacion de descarga.

    Es vigilada por LGA_NKS_DownloadClip_Watcher.py. Vive dentro de Startup/logs/.
    """
    notify_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "logs", "download_clip_done"
    )
    return os.path.abspath(notify_dir)


class RelativeTimeFormatter(logging.Formatter):
    """Formatter con hora absoluta y tiempo relativo desde el inicio."""

    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created

        relative_time = record.created - script_start_time
        record.relative_time = f"{relative_time:.3f}s"
        return super().format(record)


def setup_debug_logging(script_name="FileManager_DownloadClip"):
    """Configura el logging para escribir SOLO en archivo (limpieza diaria)."""
    global debug_log_listener, _log_file_path_resolved

    log_filename = f"debugPy_{script_name}.log"
    log_file_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "logs", log_filename
    )
    log_file_path = os.path.abspath(log_file_path)
    _log_file_path_resolved = log_file_path

    print(f"[DownloadClip] log target: {log_file_path}")
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    today_str = datetime.date.today().isoformat()
    should_reset = True
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
            should_reset = first_line != f"Fecha: {today_str}"
        except Exception:
            should_reset = True

    if should_reset:
        try:
            with open(log_file_path, "w", encoding="utf-8") as f:
                f.write(f"Fecha: {today_str}\n")
        except Exception as e:
            print(f"[DownloadClip] Warning: no se pudo resetear el log: {e}")

    logger_name = f"{script_name.lower()}_logger"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:
        logger.handlers.clear()

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    formatter = RelativeTimeFormatter(
        "[%(asctime)s] [%(relative_time)s] %(message)s", datefmt="%H:%M:%S"
    )
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


# Setup del logger con captura de cualquier fallo
try:
    debug_logger = setup_debug_logging(script_name="FileManager_DownloadClip")
    print("[DownloadClip] logger inicializado OK")
except Exception as _e:
    print(f"[DownloadClip] FALLO al inicializar logger: {_e}")
    traceback.print_exc()


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


def _get_selected_clips():
    """Obtiene los clips realmente seleccionados en el timeline (uno o varios).

    Usa el Metodo 1 (seleccion pura, sin playhead, sin filtro de track) via el
    helper compartido get_selected_clips(). Cae a seleccion directa si falla.
    """
    try:
        utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
        if utils_path.exists() and str(utils_path) not in sys.path:
            sys.path.insert(0, str(utils_path))
        from LGA_NKS_Shared.LGA_NKS_GetClip import get_selected_clips
        return get_selected_clips()
    except Exception as e:
        debug_print(
            f"Fallback: no se pudo usar get_selected_clips: {e}", level="warning"
        )

    # Fallback: tomar la seleccion directamente del timeline
    try:
        import hiero.ui
        import hiero.core

        seq = hiero.ui.activeSequence()
        if seq is None:
            debug_print("No hay secuencia activa", level="warning")
            return []
        te = hiero.ui.getTimelineEditor(seq)
        sel = te.selection() if te else []
        return [
            item
            for item in sel
            if not isinstance(item, hiero.core.EffectTrackItem)
        ]
    except Exception as e:
        debug_print(f"Fallback de seleccion fallo: {e}", level="error")
    return []


def _inspect_clip(clip):
    """Devuelve un dict con la info del clip o None si no se pudo resolver.

    Claves del dict:
      - name (str)
      - file_path (str): ruta del media (con token de secuencia si aplica)
      - is_single_file (bool): True si es archivo unico, False si es secuencia
      - online (bool|None): estado del media
    """
    try:
        clip_name = clip.name()
    except Exception as e:
        clip_name = f"<error: {e}>"

    try:
        media_source = clip.source().mediaSource()
    except Exception as e:
        debug_print(f"No se pudo obtener mediaSource: {e}", level="error")
        return None

    file_path = None
    try:
        fileinfos = media_source.fileinfos()
        if fileinfos:
            file_path = fileinfos[0].filename()
    except Exception as e:
        debug_print(f"No se pudieron obtener fileinfos: {e}", level="error")

    if not file_path:
        debug_print(f"Clip '{clip_name}' sin ruta de media", level="warning")
        return None

    # singleFile() True -> archivo unico (.mov); False -> secuencia de imagenes
    try:
        is_single_file = bool(media_source.singleFile())
    except Exception as e:
        debug_print(
            f"No se pudo determinar singleFile(): {e} - se asume secuencia",
            level="warning",
        )
        is_single_file = False

    try:
        online = bool(media_source.isMediaPresent())
    except Exception as e:
        debug_print(
            f"No se pudo determinar online/offline: {e}", level="warning"
        )
        online = None

    return {
        "name": clip_name,
        "file_path": file_path,
        "is_single_file": is_single_file,
        "online": online,
    }


def _path_has_vfx_root(path):
    """True si alguna parte de la ruta empieza con 'VFX-' (requisito del CLI)."""
    parts = os.path.normpath(path).replace("\\", "/").split("/")
    return any(p.upper().startswith("VFX-") for p in parts)


def _dedupe_preserve_order(paths):
    """Devuelve la lista sin duplicados preservando el orden de aparicion."""
    seen = set()
    out = []
    for p in paths:
        key = os.path.normpath(str(p)).replace("\\", "/").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def build_filemanager_cmd(folder_paths, file_paths, notify_dir=None, download_latest=False):
    """Construye el comando del CLI para modo normal o latest.

    - Modo normal:
      --download (carpetas) y --download-file (archivos)
    - Modo latest:
      --download-latest (carpetas) y --download-latest-file (archivos)

    Si notify_dir esta dado, agrega --notify-completion para que FileManager
    escriba un marcador al terminar cada descarga.
    Devuelve la lista de argumentos o None si no se puede construir.
    """
    folder_paths = _dedupe_preserve_order(folder_paths)
    file_paths = _dedupe_preserve_order(file_paths)

    folder_flag = "--download-latest" if download_latest else "--download"
    file_flag = "--download-latest-file" if download_latest else "--download-file"

    cli_args = []
    if folder_paths:
        cli_args.append(folder_flag)
        cli_args.extend(folder_paths)
    if file_paths:
        cli_args.append(file_flag)
        cli_args.extend(file_paths)

    if not cli_args:
        return None

    if notify_dir:
        cli_args.append("--notify-completion")
        cli_args.append(notify_dir)

    try:
        context_mode = resolve_context_mode()
        cmd = build_filemanager_command(
            cli_args,
            desarrollo=Desarrollo,
            script_dir=Path(__file__).parent,
            context_mode=context_mode,
        )
        debug_print(f"Contexto FileManager resuelto: {context_mode}")
        return cmd
    except Exception as exc:
        debug_print(
            f"No se pudo construir comando de FileManagerS3: {exc}",
            level="error",
        )
        return None


def main(download_latest=False):
    """Descarga el/los clip(s) seleccionado(s) desde Wasabi S3."""
    mode_label = "LATEST" if download_latest else "NORMAL"
    debug_print(f"=== FILEMANAGER DOWNLOAD CLIP ({mode_label}) ===")
    debug_print(f"log file: {_log_file_path_resolved}")

    try:
        clips = _get_selected_clips()

        if not clips:
            debug_print(
                "No hay clips seleccionados en el timeline", level="warning"
            )
            return

        total = len(clips)
        debug_print(f"Clips seleccionados: {total}")

        folder_paths = []  # secuencias -> --download (carpeta contenedora)
        file_paths = []    # archivos unicos -> --download-file

        for index, clip in enumerate(clips, start=1):
            debug_print(f"--- Clip {index}/{total} ---")
            info = _inspect_clip(clip)
            if info is None:
                continue

            debug_print(f"Nombre del clip: {info['name']}")
            debug_print(f"Ruta del clip: {info['file_path']}")
            if info["online"] is None:
                debug_print("Estado del media: DESCONOCIDO")
            else:
                debug_print(
                    f"Estado del media: {'ONLINE' if info['online'] else 'OFFLINE'}"
                )

            file_path = info["file_path"]

            if not _path_has_vfx_root(file_path):
                debug_print(
                    f"Ruta sin raiz 'VFX-', se omite (FileManager la rechazaria): {file_path}",
                    level="warning",
                )
                continue

            if info["is_single_file"]:
                # Archivo de video unico: se descarga el archivo tal cual
                debug_print(
                    "Tipo: archivo unico -> "
                    + ("--download-latest-file" if download_latest else "--download-file")
                )
                file_paths.append(file_path)
            else:
                # Secuencia de imagenes: se descarga la carpeta contenedora
                seq_folder = os.path.dirname(file_path)
                debug_print(
                    "Tipo: secuencia -> "
                    + (
                        "--download-latest carpeta: "
                        if download_latest
                        else "--download carpeta: "
                    )
                    + str(seq_folder)
                )
                folder_paths.append(seq_folder)

        if not folder_paths and not file_paths:
            debug_print("No hay nada para descargar", level="warning")
            return

        notify_dir = get_notify_dir()
        try:
            os.makedirs(notify_dir, exist_ok=True)
        except Exception as e:
            debug_print(f"No se pudo crear la carpeta de notificacion: {e}", level="warning")
        debug_print(f"Notify dir: {notify_dir}")

        cmd = build_filemanager_cmd(
            folder_paths, file_paths, notify_dir, download_latest=download_latest
        )
        if not cmd:
            debug_print("No se pudo construir el comando de FileManager", level="error")
            return

        debug_print(f"Ejecutando: {' '.join(cmd)}")
        try:
            subprocess.Popen(cmd, shell=False)
            debug_print(
                f"FileManager iniciado ({mode_label}): {len(folder_paths)} secuencia(s), "
                f"{len(file_paths)} archivo(s)"
            )
        except Exception as cmd_error:
            debug_print(f"Error al ejecutar FileManager: {cmd_error}", level="error")

    except Exception as e:
        debug_print(f"Error al procesar los clips: {e}", level="error")
        debug_print(traceback.format_exc(), level="error")


if __name__ == "__main__":
    latest_arg = any(
        arg in ("--latest", "--download-latest", "--download-latest-file")
        for arg in sys.argv[1:]
    )
    main(download_latest=latest_arg)
