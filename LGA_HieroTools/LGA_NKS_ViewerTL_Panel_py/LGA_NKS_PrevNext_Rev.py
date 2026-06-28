"""
____________________________________________________________________

  LGA_NKS_PrevNext_Rev v1.27 | Lega

  Busca el clip anterior o siguiente con estado Rev Lega, Rev Sebas, Rev Charly, Rev Juano o Rev Javi
  y ajusta la vista:
  1. Obtiene la posición actual del playhead.
  2. Encuentra el clip más cercano con el color especificado en la dirección indicada.
  3. Establece los puntos In/Out basados en el clip EditRef correspondiente a esa posición.
     Si no existe un track EditRef, usa directamente el clip del task en review.
  4. Selecciona el clip usado para establecer el In/Out.
  5. Mueve el playhead a la posición del In.
  6. Ajusta el zoom para que se ajuste al clip seleccionado.
  7. Deselecciona todos los clips.

  v1.27: Corrige Rev Juano para buscar el color real #7F4B69, igual que Pull/Push.
  v1.26: Agrega soporte para Rev Charly (#a9909d).
  v1.25: Si no existe un track EditRef, usa el In/Out del clip del task en review
  v1.24: No descarta clips offline para navegación y agrega logging a archivo
  v1.23: Usa módulo centralizado LGA_NKS_GetClip con método híbrido para buscar clips EditRef cuando la posición coincide con el playhead
____________________________________________________________________
"""

import hiero.core
import hiero.ui
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtGui, QtCore
import logging
import queue
import time
from logging.handlers import QueueHandler, QueueListener
from pathlib import Path
import sys

DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True

script_start_time = None
debug_log_listener = None

# Importar métodos de selección híbrida
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    try:
        from LGA_NKS_Shared import LGA_NKS_GetClip as clip_utils

        find_clip_at_playhead_in_track = clip_utils.find_clip_at_playhead_in_track
    except ImportError:
        find_clip_at_playhead_in_track = None
else:
    find_clip_at_playhead_in_track = None


class RelativeTimeFormatter(logging.Formatter):
    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created
        relative_time = record.created - script_start_time
        record.relative_time = f"{relative_time:.3f}s"
        return super().format(record)


def setup_debug_logging(script_name="ViewerPrevNextRev"):
    global debug_log_listener

    startup_dir = Path(__file__).parent.parent
    log_file_path = startup_dir / "logs" / f"DebugPy_{script_name}.log"
    log_file_path.parent.mkdir(parents=True, exist_ok=True)

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

    debug_log_listener = QueueListener(
        log_queue, file_handler, respect_handler_level=True
    )
    debug_log_listener.daemon = True
    debug_log_listener.start()

    return logger


debug_logger = setup_debug_logging()


def debug_print(*message):
    global script_start_time

    msg = " ".join(str(arg) for arg in message)

    if DEBUG and DEBUG_LOG:
        if script_start_time is None:
            script_start_time = time.time()
        debug_logger.info(msg)

    if DEBUG and DEBUG_CONSOLE:
        print(msg)


# Definir los colores que buscamos
COLORS = {
    "lega": QtGui.QColor(105, 19, 94),  # #69135e
    "sup": QtGui.QColor(189, 127, 159),  # #bd7f9f
    "charly": QtGui.QColor(169, 144, 157),  # #a9909d
    "juano": QtGui.QColor(127, 75, 105),  # #7F4B69
    "javi": QtGui.QColor(156, 62, 94),  # #9c3e5e
}


def get_current_playhead_position():
    """
    Obtiene la posición actual del playhead.
    """
    try:
        viewer = hiero.ui.currentViewer()
        if viewer:
            return viewer.time()
        return None
    except Exception as e:
        debug_print(f"Error al obtener la posición del playhead: {e}")
        return None


def find_clip_with_color(direction, rev_type):
    """
    Encuentra el clip con el color especificado en la dirección indicada.
    Ignora el clip actual si el playhead está sobre él.
    """
    seq = hiero.ui.activeSequence()
    if not seq:
        debug_print("No hay una secuencia activa.")
        return None

    playhead_pos = get_current_playhead_position()
    if playhead_pos is None:
        debug_print("No se pudo obtener la posición del playhead.")
        return None

    target_clip = None
    min_distance = float("inf")
    target_color = COLORS.get(rev_type)
    debug_print(
        f"Buscando clip con color rev_type='{rev_type}' en dirección '{direction}' desde playhead={playhead_pos}"
    )

    if not target_color:
        debug_print(f"No existe color configurado para rev_type='{rev_type}'")
        return None

    # Buscar en todas las pistas de video
    for track in seq.videoTracks():
        for item in track.items():
            if isinstance(item, hiero.core.EffectTrackItem):
                continue

            if not item.source():
                debug_print(f"Clip sin source, se omite: {item.name()}")
                continue

            # Verificar si el clip tiene el color buscado
            bin_item = item.source().binItem()
            if bin_item and bin_item.color() == target_color:
                clip_start = item.timelineIn()
                clip_end = item.timelineOut()

                # Ignorar el clip si el playhead está sobre él
                if clip_start <= playhead_pos < clip_end:
                    debug_print(f"Ignorando clip actual: {item.name()}")
                    continue

                # Para dirección "next", buscar clips después del playhead
                if direction == "next" and clip_start > playhead_pos:
                    distance = clip_start - playhead_pos
                    if distance < min_distance:
                        min_distance = distance
                        target_clip = item
                        debug_print(
                            f"Encontrado clip siguiente: {item.name()} a distancia {distance}"
                        )

                # Para dirección "prev", buscar clips antes del playhead
                elif direction == "prev" and clip_end < playhead_pos:
                    distance = playhead_pos - clip_end
                    if distance < min_distance:
                        min_distance = distance
                        target_clip = item
                        debug_print(
                            f"Encontrado clip anterior: {item.name()} a distancia {distance}"
                        )

    if target_clip:
        debug_print(
            f"Clip seleccionado: {target_clip.name()} [{target_clip.timelineIn()}-{target_clip.timelineOut()}]"
        )
    else:
        debug_print(f"No se encontraron más clips {rev_type} en dirección {direction}")

    return target_clip


def find_editref_clip_at_position(position):
    """
    Encuentra el clip en el track EditRef en la posición dada.
    Usa método híbrido cuando la posición coincide con el playhead actual.
    """
    seq = hiero.ui.activeSequence()
    if not seq:
        debug_print("No hay una secuencia activa.")
        return None

    # Verificar si la posición coincide con el playhead actual para usar método híbrido
    current_playhead = get_current_playhead_position()
    use_hybrid = current_playhead is not None and position == current_playhead

    # Buscar todos los tracks EditRef, porque puede haber más de uno con el mismo nombre
    edit_ref_tracks = [
        track for track in seq.videoTracks() if track.name() == "EditRef"
    ]

    if not edit_ref_tracks:
        debug_print("No se encontró un track llamado 'EditRef'.")
        return None

    debug_print(f"Tracks EditRef encontrados: {len(edit_ref_tracks)}")

    # Si la posición es la del playhead actual y existe un solo EditRef, usar método híbrido
    if use_hybrid and len(edit_ref_tracks) == 1 and find_clip_at_playhead_in_track:
        clip = find_clip_at_playhead_in_track(seq, track_name="EditRef")
        if clip:
            debug_print(f"Clip EditRef encontrado usando método híbrido: {clip.name()}")
            return clip
    elif use_hybrid and len(edit_ref_tracks) > 1:
        debug_print(
            "Hay múltiples tracks EditRef; se omite método híbrido y se busca manualmente en todos."
        )

    # Buscar el clip que contiene la posición en cualquiera de los EditRef
    for idx, track in enumerate(edit_ref_tracks, start=1):
        debug_print(
            f"Revisando EditRef #{idx} con {len(track.items())} item(s) para posición {position}"
        )
        for item in track.items():
            if item.timelineIn() <= position < item.timelineOut():
                debug_print(
                    f"Clip EditRef encontrado en track #{idx}: {item.name()} [{item.timelineIn()}-{item.timelineOut()}]"
                )
                return item

    # Si no se encuentra un clip que contenga la posición, buscar el más cercano
    # después de la posición entre todos los EditRef
    closest_clip = None
    min_distance = float("inf")
    closest_track_idx = None
    for idx, track in enumerate(edit_ref_tracks, start=1):
        for item in track.items():
            if item.timelineIn() > position:
                distance = item.timelineIn() - position
                if distance < min_distance:
                    min_distance = distance
                    closest_clip = item
                    closest_track_idx = idx

    if closest_clip:
        debug_print(
            f"No hubo match exacto en EditRef. Se usa el más cercano del track #{closest_track_idx}: "
            f"{closest_clip.name()} [{closest_clip.timelineIn()}-{closest_clip.timelineOut()}]"
        )
    else:
        debug_print(
            "No se encontró clip exacto ni clip posterior en ningún track EditRef."
        )

    return closest_clip  # Retornar el clip más cercano si no se encuentra uno exacto


def set_in_out_from_clip(clip):
    """
    Establece los puntos In y Out de la secuencia basados en el clip.
    """
    if not clip:
        return None, None

    seq = hiero.ui.activeSequence()
    if not seq:
        return None, None

    ref_in = clip.timelineIn()
    ref_out = clip.timelineOut()

    seq.setInTime(ref_in)
    seq.setOutTime(ref_out)
    debug_print(f"Se ha establecido el in/out de la secuencia a [{ref_in}, {ref_out}]")

    return ref_in, ref_out


def move_playhead_to_position(position):
    """
    Mueve el playhead a una posición específica.
    """
    viewer = hiero.ui.currentViewer()
    if viewer:
        debug_print(f"Moviendo playhead a la posición: {position}")
        viewer.setTime(position)


def ajustar_vista_al_clip():
    """
    Ajusta la vista para que se ajuste al clip seleccionado usando el comando de menú.
    Primero activa la ventana del timeline y luego ejecuta el comando con un timer.
    """
    try:
        # Obtener y activar la ventana del timeline
        window = hiero.ui.getTimelineEditor(hiero.ui.activeSequence()).window()
        window.activateWindow()
        window.setFocus()

        # Ejecutar el comando Zoom to Fit después de que la UI se actualice
        QtCore.QTimer.singleShot(0, lambda: hiero.ui.findMenuAction("Zoom to Fit").trigger())
        debug_print("Ejecutando comando Zoom to Fit")
    except Exception as e:
        debug_print(f"Error al ajustar la vista: {e}")


def main(direction, rev_type):
    """
    Función principal que ejecuta la secuencia completa de operaciones.
    """
    debug_print(f"=== Inicio PrevNext Rev | direction={direction} | rev_type={rev_type} ===")

    # 1. Encontrar el clip con el color especificado en la dirección indicada
    target_clip = find_clip_with_color(direction, rev_type)
    if not target_clip:
        debug_print(
            f"No se encontraron más clips con estado Rev_{rev_type.capitalize()}."
        )
        return

    # 2. Obtener la posición del clip
    clip_position = target_clip.timelineIn()
    debug_print(
        f"Clip Rev_{rev_type.capitalize()} encontrado en posición: {clip_position}"
    )

    # 3. Encontrar el clip EditRef correspondiente. Si no existe ningún track
    # EditRef, usar directamente el clip del task que está en review.
    seq = hiero.ui.activeSequence()
    has_editref_track = any(track.name() == "EditRef" for track in seq.videoTracks())

    if has_editref_track:
        reference_clip = find_editref_clip_at_position(clip_position)
        if not reference_clip:
            debug_print("No se encontró un clip EditRef correspondiente.")
            return
    else:
        reference_clip = target_clip
        debug_print(
            "No existe un track EditRef. Se usa el In/Out del clip del task en review: "
            f"{target_clip.name()} [{target_clip.timelineIn()}-{target_clip.timelineOut()}]"
        )

    # 4. Establecer In/Out basados en el clip de referencia elegido
    in_point, out_point = set_in_out_from_clip(reference_clip)
    if in_point is None:
        debug_print("No se pudieron establecer los puntos In/Out.")
        return

    # 5. Seleccionar el clip usado como referencia
    timeline_editor = hiero.ui.getTimelineEditor(hiero.ui.activeSequence())
    if timeline_editor:
        timeline_editor.setSelection([reference_clip])
        debug_print(f"Clip seleccionado: {reference_clip.name()}")

    # 6. Mover el playhead a la posición del In
    move_playhead_to_position(in_point)

    # 7. Ajustar el zoom para que se ajuste al clip
    ajustar_vista_al_clip()

    # 8. Deseleccionar todos los clips
    if timeline_editor:
        timeline_editor.selectNone()
        debug_print("Clips deseleccionados")


if __name__ == "__main__":
    # Si se ejecuta directamente, usar valores por defecto
    main("next", "lega")
