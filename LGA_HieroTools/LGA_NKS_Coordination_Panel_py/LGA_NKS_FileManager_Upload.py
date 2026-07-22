"""
____________________________________________________________________

  LGA_NKS_FileManager_Upload v1.01 | Lega

  Sube el shot seleccionado a Wasabi S3 usando FileManager CLI.
  Extrae la ruta del shot tomando las primeras 4 partes: unidad/proyecto/grupo/shot.
  Soporta modo desarrollo con variable Desarrollo = True y verificación automática.

  v1.01: migra al helper central FileManagerS3 + --context studio/client.
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
import re

# Agregar ruta del módulo utilitario
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    from LGA_NKS_Shared.LGA_NKS_GetClip import get_clip_to_process
    from LGA_NKS_Shared import LGA_NKS_GetClip as clip_utils
    from LGA_NKS_Shared.LGA_NKS_FileManagerLauncher import (
        build_filemanager_command,
        resolve_context_mode,
    )

# Variables globales de logging (valores por defecto)
DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True
script_start_time = None
debug_log_listener = None

# Variable de desarrollo para cambiar la ruta del ejecutable
Desarrollo = True

class RelativeTimeFormatter(logging.Formatter):
    """Formatter con hora absoluta y tiempo relativo desde el inicio."""

    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created

        relative_time = record.created - script_start_time
        record.relative_time = f"{relative_time:.3f}s"
        return super().format(record)


def setup_debug_logging(script_name="FileManager_Upload"):
    """Configura el logging para escribir SOLO en archivo."""
    global debug_log_listener

    log_filename = f"debugPy_{script_name}.log"
    log_file_path = os.path.join(
        os.path.dirname(__file__), "..", "logs", log_filename
    )

    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    # Limpieza diaria: si el log no es de hoy, se borra y se agrega encabezado con fecha
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


debug_logger = setup_debug_logging(script_name="FileManager_Upload")


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

    # 1) Deteccion por patron de nombre de shot (ej: BRDA_050_010)
    shot_pattern = re.compile(
        r"^[A-Za-z0-9]+(?:_[A-Za-z]+|_[0-9]{3,5}[A-Za-z]?)?_[0-9]{3,5}[A-Za-z]?_[0-9]{3,4}$"
    )
    for i in range(len(path_parts) - 1, -1, -1):
        if shot_pattern.match(path_parts[i]):
            shot_path = "/".join(path_parts[: i + 1])
            debug_print(f"Ruta del shot detectada por patron: {shot_path}")
            return shot_path

    # 2) Deteccion por estructura de ruta (root + proyecto/grupo/shot)
    root_len = 0
    if len(path_parts) >= 2 and path_parts[0] == "" and path_parts[1] == "Volumes":
        root_len = 3  # /Volumes/<volumen>
        if len(path_parts) > 3 and re.match(r"^[A-Za-z]$", path_parts[3]):
            root_len = 4  # /Volumes/<volumen>/<drive>
    elif path_parts and re.match(r"^[A-Za-z]:$", path_parts[0]):
        root_len = 1  # T:
    elif len(path_parts) >= 4 and path_parts[0] == "" and path_parts[1] == "":
        root_len = 4  # //server/share
    else:
        root_len = 1 if path_parts and path_parts[0] else 0

    expected_len = root_len + 3
    if expected_len > 0 and len(path_parts) >= expected_len:
        shot_path = "/".join(path_parts[:expected_len])
        debug_print(f"Ruta del shot por estructura: {shot_path}")
        return shot_path

    # 3) Fallback si no hay suficientes partes
    debug_print("Ruta no tiene suficientes partes, usando fallback")
    clip_folder = os.path.dirname(file_path)
    input_folder = os.path.dirname(clip_folder)
    return os.path.dirname(input_folder)


def build_filemanager_cmd(action_flag, shot_path):
    try:
        context_mode = resolve_context_mode()
        cmd = build_filemanager_command(
            [action_flag, shot_path],
            desarrollo=Desarrollo,
            script_dir=Path(__file__).parent,
            context_mode=context_mode,
        )
        debug_print(f"Contexto FileManager resuelto: {context_mode}")
        return cmd
    except Exception as exc:
        debug_print(f"No se pudo construir comando de FileManagerS3: {exc}", level="error")
        return None

def main():
    """Función principal que sube el shot seleccionado a Wasabi S3"""
    debug_print("=== FILEMANAGER UPLOAD SHOT ===")

    try:
        # Obtener el clip usando el método híbrido inteligente (playhead primero, selección como fallback)
        clip = get_clip_to_process(track_name=None, prioritize_multiple_selection=False)

        if not clip:
            debug_print("No se encontró clip para procesar")
            return

        # Obtener la ruta del archivo del clip
        file_path = clip.source().mediaSource().fileinfos()[0].filename() if clip.source().mediaSource().fileinfos() else None

        if file_path:
            # La estructura es: unidad:/proyecto/grupo/shot/_input/version/archivo
            # Necesitamos llegar a: unidad:/proyecto/grupo/shot
            # Partimos desde el archivo y subimos hasta encontrar la carpeta del shot

            # Normalizar la ruta y dividir por ambos separadores (/ y \)
            shot_path = get_shot_path(file_path)

            debug_print(f"Ruta del archivo: {file_path}")
            debug_print(f"Ruta del shot: {shot_path}")

            # Ejecutar FileManager con --upload
            cmd = build_filemanager_cmd("--upload", shot_path)
            if not cmd:
                return

            debug_print(f"Ejecutando: {' '.join(cmd)}")

            try:
                # Ejecutar el comando (no esperamos que termine, FileManager abre la GUI)
                subprocess.Popen(cmd, shell=False)
                debug_print("FileManager iniciado para subida")
            except Exception as cmd_error:
                debug_print(f"Error al ejecutar FileManager: {cmd_error}")
        else:
            debug_print("No se pudo obtener la ruta del archivo del clip")

    except Exception as e:
        debug_print(f"Error al procesar el clip: {e}")

if __name__ == "__main__":
    main()
