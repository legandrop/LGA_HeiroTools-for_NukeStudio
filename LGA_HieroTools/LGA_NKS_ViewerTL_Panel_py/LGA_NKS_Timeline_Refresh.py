"""
____________________________________________________________________

  LGA_NKS_Timeline_Refresh v1.21 | Lega

  Refresca el timeline cerrándolo y volviéndolo a abrir,
  manteniendo los ajustes del viewer:
  1. Captura el estado actual del viewer (masking, etc).
  2. Cierra el viewer activo.
  3. Reabre la misma secuencia en un nuevo timeline viewer.
  4. Restaura los ajustes del viewer.

  v1.21: Sistema A de logging — solo archivo, sin consola.
____________________________________________________________________
"""

import hiero.core
import hiero.ui
import os
import logging
import queue
from logging.handlers import QueueHandler, QueueListener
import time

DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True

script_start_time = None
debug_log_listener = None


class RelativeTimeFormatter(logging.Formatter):
    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created
        record.relative_time = f"{record.created - script_start_time:.3f}s"
        return super().format(record)


def setup_debug_logging(script_name="TimelineRefresh"):
    global debug_log_listener

    log_file_path = os.path.join(
        os.path.dirname(__file__), "..", "logs", f"debugPy_{script_name}.log"
    )
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    try:
        with open(log_file_path, "w", encoding="utf-8") as f:
            f.write(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    except Exception:
        pass

    logger = logging.getLogger(f"{script_name.lower()}_logger")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:
        logger.handlers.clear()

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(RelativeTimeFormatter("[%(relative_time)s] %(message)s"))

    log_queue = queue.Queue()
    queue_handler = QueueHandler(log_queue)
    queue_handler.setLevel(logging.DEBUG)
    logger.addHandler(queue_handler)

    if debug_log_listener:
        try:
            debug_log_listener.stop()
        except Exception:
            pass

    debug_log_listener = QueueListener(log_queue, file_handler, respect_handler_level=True)
    debug_log_listener.daemon = True
    debug_log_listener.start()

    return logger


debug_logger = setup_debug_logging(script_name="TimelineRefresh")


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
        print(f"[{time.time() - script_start_time:.3f}s] {msg}")

def get_viewer_state(viewer):
    """
    Captura el estado actual del viewer.
    """
    if not viewer:
        return None

    try:
        state = {
            'time': viewer.time(),
            'mask_style': viewer.maskOverlayStyle(),
            'lut': viewer.player().LUT(),
            'gain': viewer.gain(),
            'gamma': viewer.gamma()
        }
        debug_print("Estado del viewer capturado:")
        debug_print(f"- Tiempo: {state['time']}")
        debug_print(f"- Estilo de máscara: {state['mask_style']}")
        debug_print(f"- LUT: {state['lut']}")
        debug_print(f"- Gain: {state['gain']}")
        debug_print(f"- Gamma: {state['gamma']}")
        return state
    except Exception as e:
        debug_print(f"Error al capturar el estado del viewer: {e}")
        return None

def restore_viewer_state(viewer, state):
    """
    Restaura el estado del viewer.
    """
    if not viewer or not state:
        debug_print("No se puede restaurar el estado: viewer o state es None")
        return

    try:
        debug_print("\nRestaurando estado del viewer...")
        debug_print(f"- Estableciendo tiempo a: {state['time']}")
        viewer.setTime(state['time'])

        debug_print(f"- Estableciendo estilo de máscara a: {state['mask_style']}")
        viewer.setMaskOverlayStyle(state['mask_style'])

        # Si había un aspecto 2.35:1, lo restauramos
        if state['mask_style'] != hiero.ui.Player.MaskOverlayStyle.eMaskOverlayNone:
            debug_print("- Estableciendo aspecto 2.35:1")
            viewer.setMaskOverlayFromRemote("2.35:1")

        debug_print(f"- Estableciendo LUT a: {state['lut']}")
        viewer.player().setLUT(state['lut'])

        debug_print(f"- Estableciendo Gain a: {state['gain']}")
        viewer.setGain(state['gain'])  # Cambiado de setDisplayGain a setGain

        debug_print(f"- Estableciendo Gamma a: {state['gamma']}")
        viewer.setGamma(state['gamma'])  # Cambiado de setDisplayGamma a setGamma

        debug_print("Estado del viewer restaurado completamente")
    except Exception as e:
        debug_print(f"Error al restaurar el estado del viewer: {e}")

def get_new_viewer_after_open(old_viewer_object_name):
    """
    Obtiene el viewer nuevo después de openInTimeline().
    Confirmado: currentViewer() después de openInTimeline() devuelve el viewer nuevo.
    """
    try:
        new_viewer = hiero.ui.currentViewer()
        if new_viewer:
            # Verificar que sea diferente al viejo comparando objectName()
            window = new_viewer.window()
            if window and hasattr(window, 'objectName'):
                obj_name = window.objectName()
                if obj_name and obj_name.startswith('uk.co.thefoundry.sequenceviewer'):
                    if obj_name != old_viewer_object_name:
                        debug_print(f"✓ Viewer nuevo encontrado con objectName: {obj_name}")
                        return new_viewer
                    else:
                        debug_print(f"⚠️ currentViewer() devolvió viewer viejo (objectName: {obj_name})")
        return new_viewer  # Devolver aunque no podamos verificar (mejor que None)
    except Exception as e:
        debug_print(f"Error obteniendo viewer nuevo: {e}")
        import traceback
        debug_print(traceback.format_exc())
    return None

def main():
    """
    Reabre la misma secuencia en un nuevo timeline viewer y retorna los objetos nuevos.
    """
    # Obtener el viewer activo
    active_viewer = hiero.ui.currentViewer()
    if not active_viewer:
        debug_print("No se encontró un viewer activo")
        return None, None

    debug_print("\n1. Capturando estado del viewer activo...")
    # Guardar el estado del viewer
    viewer_state = get_viewer_state(active_viewer)
    if not viewer_state:
        debug_print("No se pudo capturar el estado del viewer")
        return None, None

    debug_print("\n2. Guardando información de la secuencia activa...")
    # Guardar la información de la secuencia activa
    active_sequence = active_viewer.player().sequence()
    if not active_sequence:
        debug_print("No se encontró una secuencia activa")
        return None, None

    # Guardar objectName() del viewer y timeline viejo
    old_viewer_window = active_viewer.window()
    old_viewer_object_name = old_viewer_window.objectName() if (old_viewer_window and hasattr(old_viewer_window, 'objectName')) else None
    
    old_timeline = hiero.ui.getTimelineEditor(active_sequence)
    old_timeline_object_name = None
    if old_timeline:
        old_timeline_window = old_timeline.window()
        old_timeline_object_name = old_timeline_window.objectName() if (old_timeline_window and hasattr(old_timeline_window, 'objectName')) else None
    
    debug_print(f"\nViewer viejo objectName: {old_viewer_object_name}")
    debug_print(f"Timeline viejo objectName: {old_timeline_object_name}")

    debug_print("Comentado: Cerrando viewer activo...")
    """
    debug_print("\n3. Cerrando viewer activo...")
    # Cerrar el viewer activo
    viewer_window = active_viewer.window()
    if viewer_window:
        viewer_window.close()
    """

    debug_print("\n4. Abriendo nueva secuencia...")
    # Abrir la secuencia en un nuevo timeline
    new_timeline = hiero.ui.openInTimeline(active_sequence)
    if not new_timeline:
        debug_print("No se pudo abrir el nuevo timeline")
        return None, None
    
    debug_print(f"\n5. Timeline nuevo obtenido (ID: {hex(id(new_timeline))})")
    
    # Obtener el viewer nuevo usando currentViewer() (confirmado que devuelve el nuevo después de openInTimeline)
    debug_print("\n6. Obteniendo viewer nuevo...")
    new_viewer = get_new_viewer_after_open(old_viewer_object_name)
    
    if new_viewer:
        debug_print(f"Viewer nuevo obtenido (ID: {hex(id(new_viewer))})")
        restore_viewer_state(new_viewer, viewer_state)
    else:
        debug_print("⚠️ No se pudo obtener el viewer nuevo")
    
    # Retornar los objetos nuevos Y la información del viewer viejo para que el wrapper pueda cerrarlo al final
    return new_timeline, new_viewer, old_viewer_object_name, old_timeline_object_name

if __name__ == "__main__":
    main()
