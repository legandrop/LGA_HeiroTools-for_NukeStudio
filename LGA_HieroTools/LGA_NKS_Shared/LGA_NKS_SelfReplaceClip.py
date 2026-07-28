"""
____________________________________________________________________

  LGA_NKS_SelfReplaceClip v1.21 | Lega

  Usado por runtime activo:
  - LGA_NKS_Edit_Panel.py

  Reconnect automático con el mismo clip, corrige desplazamiento de frames,
  mueve versión original al bin 'Conform' y restaura color original.

  v1.21: Agregado parámetro force_all_clips para procesar todos los clips del timeline
         o solo los seleccionados. Compatible con el botón Reconnect Win > Mac del Edit Panel.
____________________________________________________________________

"""

import hiero.core
import hiero.ui
import os
import re
import sys
import logging
import queue
import datetime
import time
from logging.handlers import QueueHandler, QueueListener

# Variables globales de logging (valores por defecto)
DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True
script_start_time = None
debug_log_listener = None


class RelativeTimeFormatter(logging.Formatter):
    """Formatter con hora absoluta y tiempo relativo desde el inicio."""
    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created

        relative_time = record.created - script_start_time
        record.relative_time = f"{relative_time:.3f}s"
        return super().format(record)


def setup_debug_logging(script_name="SelfReplaceClip"):
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


debug_logger = setup_debug_logging(script_name="SelfReplaceClip")


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


debug_print("Iniciando LGA_NKS_SelfReplaceClip.py...")

debug_print(f"Python path incluye Startup: {'Python/Startup' in str(sys.path)}")
debug_print(f"Directorio actual: {os.getcwd()}")
adapter_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "LGA_QtAdapter_HieroTools.py",
)
debug_print(f"Archivo real LGA_NKS_Shared/LGA_QtAdapter_HieroTools.py existe: {os.path.exists(adapter_path)}")

# Importar LGA_QtAdapter_HieroTools con fallback
try:
    from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtGui
    debug_print("LGA_QtAdapter_HieroTools importado correctamente")
except ImportError as e:
    debug_print(f"Error importando LGA_QtAdapter_HieroTools: {e}")
    QtGui = None

def print_clip_info(shot, prefix=""):
    """
    Imprime la información detallada del clip
    """
    debug_print(f"\n{prefix} Clip Info:")
    debug_print(f"Clip Name: {shot.name()}")
    
    # Información del clip en la timeline
    debug_print("\nTimeline Info:")
    debug_print(f"Source In: {shot.sourceIn()}")
    debug_print(f"Source Out: {shot.sourceOut()}")
    debug_print(f"Source Duration: {shot.sourceDuration()}")
    debug_print(f"Timeline In: {shot.timelineIn()}")
    debug_print(f"Timeline Out: {shot.timelineOut()}")
    debug_print(f"Timeline Duration: {shot.duration()}")
    
    # Información del Source
    source = shot.source()
    media_source = source.mediaSource()
    debug_print("\nSource Info:")
    debug_print(f"Source In: {source.sourceIn()}")
    debug_print(f"Source Out: {source.sourceOut()}")
    debug_print(f"Frame Rate: {source.framerate()}")
    
    # Información adicional del clip
    debug_print("\nAdditional Clip Info:")
    debug_print(f"Original Frame Rate: {shot.playbackSpeed()}")
    debug_print(f"Media Source Path: {media_source.fileinfos()[0].filename()}")
    
    # Información del formato
    format_obj = source.format()
    if format_obj:
        debug_print("\nFormat Info:")
        debug_print(f"Format: {format_obj.name()}")
        debug_print(f"Resolution: {format_obj.width()}x{format_obj.height()}")

def get_full_bin_path(bin_item):
    path = []
    while bin_item:
        if isinstance(bin_item, hiero.core.Bin):
            path.append(bin_item.name())
        bin_item = bin_item.parentBin() if hasattr(bin_item, 'parentBin') else None
    return '/'.join(reversed(path))

def find_or_create_bin(project, bin_path):
    """
    Encuentra un bin existente o crea uno nuevo si no existe.

    Args:
    - project (hiero.core.Project): El proyecto actual en Hiero.
    - bin_path (str): La ruta del bin.

    Returns:
    - hiero.core.Bin: El bin encontrado o creado.
    """
    bin_names = bin_path.split('/')
    current_bin = project.clipsBin()
    for bin_name in bin_names:
        found_bin = None
        for item in current_bin.items():
            if isinstance(item, hiero.core.Bin) and item.name() == bin_name:
                found_bin = item
                break
        if not found_bin:
            found_bin = hiero.core.Bin(bin_name)
            current_bin.addItem(found_bin)
        current_bin = found_bin
    return current_bin

def move_clip_to_bin(project, clip_name, source_bin_name, target_bin_path, shot):
    """
    Mueve un clip de un bin de origen a un bin de destino en el proyecto.

    Args:
    - project (hiero.core.Project): El proyecto actual en Hiero.
    - clip_name (str): El nombre del clip que se movera.
    - source_bin_name (str): El nombre del bin de origen que contiene el clip.
    - target_bin_path (str): La ruta del bin de destino donde se movera el clip.
    """
    source_bin = None
    for bin_item in project.clipsBin().items():
        if bin_item.name() == source_bin_name:
            source_bin = bin_item
            break

    if source_bin:
        clip_to_move = None
        for clip_item in source_bin.items():
            if clip_item.name() == clip_name:
                clip_to_move = clip_item
                break

        if clip_to_move:
            target_bin = find_or_create_bin(project, target_bin_path)
            source_bin.removeItem(clip_to_move)
            # Remover el clip del bin original (no me esta funcionando)
            original_bin_item = shot.source().binItem()
            original_bin = original_bin_item.parentBin()
            # original_bin.removeItem(original_bin_item)    

            target_bin.addItem(clip_to_move)
            debug_print(f"Se movio el clip '{clip_name}' del bin '{source_bin_name}' al bin '{target_bin_path}'.")
        else:
            debug_print(f"No se encontro el clip '{clip_name}' en el bin de origen '{source_bin_name}'.")
    else:
        debug_print(f"No se encontro el bin de origen '{source_bin_name}'.")

def get_clip_color(clip):
    """
    Devuelve el color actual del BinItem asociado al clip.
    """
    try:
        bin_item = clip.source().binItem()
        return bin_item.color()
    except Exception as e:
        debug_print(f"No se pudo obtener el color del clip: {e}")
        return None

def set_clip_color(clip, color):
    """
    Asigna un color al BinItem asociado al clip.
    """
    try:
        bin_item = clip.source().binItem()
        if color:
            bin_item.setColor(color)
            debug_print(f"Color restaurado para el clip: {clip.name()}")
    except Exception as e:
        debug_print(f"No se pudo asignar el color al clip: {e}")

def main(force_all_clips=False):
    debug_print("\n==== INICIANDO SCRIPT DE SELFREPLACE ====")
    try:
        projects = hiero.core.projects()
        if not projects:
            debug_print("No hay proyectos abiertos")
            return
        project = projects[-1]
        debug_print(f"Proyecto activo: {project.name()}")
        with project.beginUndo("Self Replace Clips"):
            seq = hiero.ui.activeSequence()
            if not seq:
                debug_print("No active sequence found.")
                return

            te = hiero.ui.getTimelineEditor(seq)
            
            # Si force_all_clips es True, obtener todos los clips del timeline
            if force_all_clips:
                all_clips = []
                for track in seq.videoTracks():
                    for track_item in track:
                        if not isinstance(track_item, hiero.core.EffectTrackItem):
                            all_clips.append(track_item)
                selected_clips = all_clips
                debug_print(f"Procesando todos los clips del timeline ({len(selected_clips)} clips)...")
            else:
                selected_clips = te.selection()
                debug_print(f"Procesando clips seleccionados ({len(selected_clips)} clips)...")

            if len(selected_clips) == 0:
                debug_print("*** No hay clips seleccionados en la pista ***")
            else:
                valid_clips = [clip for clip in selected_clips if not isinstance(clip, hiero.core.EffectTrackItem)]
                skipped_clips = [clip.name() for clip in selected_clips if isinstance(clip, hiero.core.EffectTrackItem)]
                
                debug_print(f"Procesando {len(valid_clips)} clips válidos...")
                if skipped_clips:
                    debug_print(f"Salteando {len(skipped_clips)} efectos: {', '.join(skipped_clips)}")
                
                for shot in valid_clips:
                    # Leer color original antes del replace
                    original_color = get_clip_color(shot)
                    # Imprimir información del clip antes del reemplazo
                    print_clip_info(shot, "BEFORE")
                    
                    # Guardar los valores originales
                    original_source_in = shot.sourceIn()
                    original_source_out = shot.sourceOut()
                    original_source_in_source = shot.source().sourceIn()
                    frame_offset = 997  # Offset para llevar a 1001
                    
                    file_path = shot.source().mediaSource().fileinfos()[0].filename() if shot.source().mediaSource().fileinfos() else None
                    if not file_path:
                        debug_print("No se encontro el path del archivo del clip.")
                        continue
                    debug_print("\nFile path:", file_path)

                    bin_item = shot.source().binItem()
                    full_bin_path = get_full_bin_path(bin_item)
                    full_bin_path = full_bin_path.replace("Sequences/", "")
                    debug_print("Ruta completa del bin para el clip:", full_bin_path)

                    try:
                        shot.replaceClips(file_path)
                        debug_print("Clip reemplazado exitosamente.")
                        
                        # Verificar si los frames necesitan corrección
                        if shot.sourceIn() < original_source_in:
                            debug_print("\n¡ADVERTENCIA! Los frames se han corrido, aplicando corrección...")
                            
                            # Calcular el nuevo source in/out basado en el original + offset
                            new_source_in = original_source_in
                            new_source_out = original_source_out
                            
                            # Aplicar los nuevos valores
                            shot.setSourceIn(new_source_in)
                            shot.setSourceOut(new_source_out)
                            
                            debug_print("\nFrame correction applied:")
                            debug_print(f"Source In adjusted: {shot.sourceIn()} -> {new_source_in}")
                            debug_print(f"Source Out adjusted: {shot.sourceOut()} -> {new_source_out}")
                        else:
                            debug_print("\nLos frames están correctos, no se requiere corrección.")
                        
                        # Restaurar el color original
                        set_clip_color(shot, original_color)
                        
                        # Imprimir información del clip después del reemplazo
                        print_clip_info(shot, "AFTER")
                        
                    except Exception as e:
                        debug_print(f"Error reemplazando el clip: {e}")

                    new_clip_name = shot.source().name()
                    debug_print(f"Nombre del clip: {new_clip_name}")

                    conform_bin_name = "Conform"
                    original_bin_name = full_bin_path.split(' > ')[-1]
                    move_clip_to_bin(project, new_clip_name, conform_bin_name, full_bin_path, shot)

        debug_print("\n==== SCRIPT DE SELFREPLACE COMPLETADO ====")
    except Exception as e:
        debug_print(f"Error en script SelfReplace: {e}")
        import traceback
        debug_print(traceback.format_exc())
