"""
____________________________________________________________________

  LGA_NKS_PipeSync_CreatePsync v1.01 | Lega

  Genera un archivo .psync portátil con la ruta del shot seleccionado.
  Shift+Click en el panel crea el token en el Desktop listo para compartir.

  v1.01: la carpeta del shot se detecta con is_shot_folder_name() de
         NamingUtils, que valida el vendor code contra la DB de PipeSync.
         El regex local no reconocia el naming PROYECTO_SEQ_SHOT_VENDOR y
         caia al fallback por profundidad de ruta.
____________________________________________________________________
"""

from pathlib import Path
import sys
import os
import json
import datetime
import getpass
import socket
import logging
import queue
from logging.handlers import QueueHandler, QueueListener
import time
import re

utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    from LGA_NKS_Shared.LGA_NKS_GetClip import get_clip_to_process
    from LGA_NKS_Shared import LGA_NKS_GetClip as clip_utils

# Deteccion de la carpeta del shot: el helper central conoce los vendor codes de
# la DB de PipeSync (naming PROYECTO_SEQ_SHOT_VENDOR). Si no se puede importar,
# get_shot_path() cae al regex local, que no entiende vendor.
try:
    from LGA_NKS_Shared.LGA_NKS_Flow_NamingUtils import (
        is_shot_folder_name,
        extract_project_name_from_path,
    )
except ImportError:
    is_shot_folder_name = None
    extract_project_name_from_path = None

DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True
script_start_time = None
debug_log_listener = None
Desarrollo = True


class RelativeTimeFormatter(logging.Formatter):
    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created
        relative_time = record.created - script_start_time
        record.relative_time = f"{relative_time:.3f}s"
        return super().format(record)


def setup_debug_logging(script_name="PipeSync_CreatePsync"):
    global debug_log_listener

    log_filename = f"debugPy_{script_name}.log"
    log_file_path = os.path.join(
        os.path.dirname(__file__), "..", "logs", log_filename
    )
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
            print(f"Warning: No se pudo resetear el log: {e}")

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


debug_logger = setup_debug_logging()


def debug_print(*message, level="info"):
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


def get_shot_path(file_path):
    normalized_path = os.path.normpath(file_path)
    path_parts = normalized_path.replace("\\", "/").split("/")
    debug_print(f"Partes de la ruta: {path_parts}")

    # El helper central valida el vendor code contra la DB de PipeSync; el regex
    # queda como fallback para cuando NamingUtils no se pudo importar.
    shot_pattern = re.compile(
        r"^[A-Za-z0-9]+(?:_[A-Za-z]+|_[0-9]{3,5}[A-Za-z]?)?_[0-9]{3,5}[A-Za-z]?_[0-9]{3,4}$"
    )
    project_name = (
        extract_project_name_from_path(file_path)
        if extract_project_name_from_path
        else None
    )
    for i in range(len(path_parts) - 1, -1, -1):
        segmento = path_parts[i]
        if is_shot_folder_name:
            es_shot = is_shot_folder_name(segmento, project_name)
        else:
            es_shot = bool(shot_pattern.match(segmento))
        if es_shot:
            shot_path = "/".join(path_parts[: i + 1])
            debug_print(f"Ruta del shot detectada por patrón: {shot_path}")
            return shot_path

    root_len = 0
    if len(path_parts) >= 2 and path_parts[0] == "" and path_parts[1] == "Volumes":
        root_len = 3
        if len(path_parts) > 3 and re.match(r"^[A-Za-z]$", path_parts[3]):
            root_len = 4
    elif path_parts and re.match(r"^[A-Za-z]:$", path_parts[0]):
        root_len = 1
    elif len(path_parts) >= 4 and path_parts[0] == "" and path_parts[1] == "":
        root_len = 4
    else:
        root_len = 1 if path_parts and path_parts[0] else 0

    expected_len = root_len + 3
    if expected_len > 0 and len(path_parts) >= expected_len:
        shot_path = "/".join(path_parts[:expected_len])
        debug_print(f"Ruta del shot por estructura: {shot_path}")
        return shot_path

    debug_print("Ruta no tiene suficientes partes, usando fallback")
    clip_folder = os.path.dirname(file_path)
    input_folder = os.path.dirname(clip_folder)
    return os.path.dirname(input_folder)


def resolve_shot_from_clip():
    clip = get_clip_to_process(track_name=None, prioritize_multiple_selection=False)
    if not clip:
        debug_print("No se encontró clip para procesar")
        return None, None

    fileinfos = clip.source().mediaSource().fileinfos()
    file_path = fileinfos[0].filename() if fileinfos else None
    if not file_path:
        debug_print("No se pudo obtener la ruta del archivo del clip")
        return None, None

    shot_path = get_shot_path(file_path)
    shot_name = Path(shot_path).name
    debug_print(f"Shot detectado: {shot_name} ({shot_path})")
    return shot_name, shot_path


def choose_output_directory():
    candidates = [
        Path.home() / "Desktop",
        Path.home(),
        Path.cwd(),
    ]
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            return candidate
        except Exception:
            continue
    return Path.cwd()


def generate_unique_filename(directory, base_name):
    target = directory / base_name
    counter = 1
    while target.exists():
        target = directory / f"{Path(base_name).stem}_{counter}.psync"
        counter += 1
    return target


def write_psync_file(output_path, shot_name, shot_path):
    data = {
        "version": 1,
        "shot_name": shot_name,
        "local_path": shot_path.replace("/", "\\"),
        "generated_at_utc": datetime.datetime.utcnow().isoformat() + "Z",
        "generated_by_user": getpass.getuser(),
        "generated_on_host": socket.gethostname(),
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    debug_print(f"Archivo .psync generado en: {output_path}")


def main():
    debug_print("=== PIPE SYNC CREATE TOKEN ===")
    try:
        shot_name, shot_path = resolve_shot_from_clip()
        if not shot_name or not shot_path:
            return

        output_dir = choose_output_directory()
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = generate_unique_filename(output_dir, f"{shot_name}.psync")
        write_psync_file(output_file, shot_name, shot_path)
        debug_print(f"Token listo para compartir: {output_file}")
    except Exception as e:
        debug_print(f"Error al generar token PipeSync: {e}", level="error")


if __name__ == "__main__":
    main()
