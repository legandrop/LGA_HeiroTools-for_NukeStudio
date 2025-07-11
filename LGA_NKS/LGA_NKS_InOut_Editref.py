"""
__________________________________________________________

  LGA_NKS_InOut_Editref v1.41 | Lega Pugliese

  Establece los puntos In y Out de la secuencia activa
  basándose en el clip más cercano del track "EditRef".
   1. Obtiene la secuencia activa y la posición del playhead.
   2. Encuentra el clip más cercano en el track "EditRef".
   3. Establece los puntos In y Out basados en ese clip.
   4. Selecciona el clip, mueve el playhead al inicio y ajusta
      la vista para que se ajuste al clip seleccionado.
__________________________________________________________
"""

import hiero.core
import hiero.ui
from PySide2.QtCore import QTimer

DEBUG = False


def debug_print(*message):
    if DEBUG:
        print(*message)


def set_in_out_from_edit_ref_track():
    """
    Establece los puntos In y Out basándose en el clip más cercano del track EditRef.
    """
    # Obtener la secuencia activa
    seq = hiero.ui.activeSequence()
    if not seq:
        debug_print("No hay una secuencia activa.")
        return None

    # Obtener la posicion del playhead
    te = hiero.ui.getTimelineEditor(seq)
    current_viewer = hiero.ui.currentViewer()
    player = current_viewer.player() if current_viewer else None
    playhead_frame = player.time() if player else None

    if playhead_frame is None:
        debug_print("No se pudo obtener la posicion del playhead.")
        return None

    # Buscar el track llamado "EditRef" o "EditRefClean"
    edit_ref_track = None
    for track in seq.videoTracks():
        if track.name() == "EditRef":
            edit_ref_track = track
            break
    if not edit_ref_track:
        for track in seq.videoTracks():
            if track.name() == "EditRefClean":
                edit_ref_track = track
                break

    if not edit_ref_track:
        debug_print("No se encontro un track llamado 'EditRef' ni 'EditRefClean'.")
        return None

    # Buscar el clip mas cercano en el track EditRef
    edit_ref_clip = None
    min_distance = float("inf")
    for item in edit_ref_track.items():
        if item.timelineIn() <= playhead_frame < item.timelineOut():
            edit_ref_clip = item
            break
        else:
            # Calcular la distancia al playhead
            if playhead_frame < item.timelineIn():
                distance = item.timelineIn() - playhead_frame
            else:
                distance = playhead_frame - item.timelineOut()
            if distance < min_distance:
                min_distance = distance
                edit_ref_clip = item

    if not edit_ref_clip:
        debug_print("No se encontro ningun clip en el track EditRef.")
        return None

    # Obtener el in y out del clip de referencia
    ref_in = edit_ref_clip.timelineIn()
    ref_out = edit_ref_clip.timelineOut()

    # Establecer el in y out de la secuencia
    seq.setInTime(ref_in)
    seq.setOutTime(ref_out)

    debug_print(
        f"Se ha establecido el in/out de la secuencia a [{ref_in}, {ref_out}] basado en el clip de EditRef mas cercano."
    )

    return edit_ref_clip, edit_ref_track.name()


def seleccionar_y_ajustar_clip(clip, track_name):
    """
    Selecciona el clip y ajusta la vista para que se ajuste al clip seleccionado.
    """
    if not clip:
        return

    try:
        # Seleccionar el clip
        timeline_editor = hiero.ui.getTimelineEditor(hiero.ui.activeSequence())
        if timeline_editor:
            timeline_editor.setSelection([clip])
            debug_print(f"Clip seleccionado: {clip.name()}")

            # Mover el playhead al inicio del clip
            viewer = hiero.ui.currentViewer()
            if viewer:
                new_time = clip.timelineIn()
                debug_print(f"Moviendo playhead al inicio del clip: {new_time}")
                viewer.setTime(new_time)
            else:
                debug_print("No se pudo obtener el viewer")

            # Obtener y activar la ventana del timeline
            window = timeline_editor.window()
            window.activateWindow()
            window.setFocus()

            # Ejecutar el comando Zoom to Fit después de que la UI se actualice
            QTimer.singleShot(
                0, lambda: hiero.ui.findMenuAction("Zoom to Fit").trigger()
            )
            debug_print("Ejecutando comando Zoom to Fit")
        else:
            debug_print("No se pudo obtener el timeline editor.")
    except Exception as e:
        debug_print(f"Error al seleccionar y ajustar el clip: {e}")


def main():
    """
    Función principal que establece los puntos In/Out y ajusta la vista.
    """
    result = set_in_out_from_edit_ref_track()
    if result:
        clip, track_name = result
        if track_name == "EditRefClean":
            seleccionar_y_ajustar_clip(clip, track_name)


if __name__ == "__main__":
    main()
