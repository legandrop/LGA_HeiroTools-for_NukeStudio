"""
____________________________________________________________________

  LGA_NKS_NextPrev_Annotation v1.00 | Lega

  Navega entre las anotaciones del clip seleccionado en el timeline.

  v1.00: Version inicial con navegacion a la anotacion siguiente y anterior.
____________________________________________________________________
"""

import hiero.core
import hiero.ui


def get_selected_track_item():
    """Devuelve el primer TrackItem seleccionado en el timeline activo."""
    sequence = hiero.ui.activeSequence()
    if not sequence:
        print("[ANNOTATION_NAV] No hay una secuencia activa.")
        return None

    timeline_editor = hiero.ui.getTimelineEditor(sequence)
    if not timeline_editor:
        print("[ANNOTATION_NAV] No se encontro el editor de timeline.")
        return None

    selection = timeline_editor.selection()
    if not selection:
        print("[ANNOTATION_NAV] No hay ningun clip seleccionado.")
        return None

    for item in selection:
        if isinstance(item, hiero.core.TrackItem):
            return item

    print("[ANNOTATION_NAV] La seleccion no contiene un TrackItem.")
    return None


def get_annotation_frames_for_track_item(track_item):
    """Obtiene los frames de timeline de las anotaciones del clip indicado."""
    source = track_item.source()
    if not source:
        return []

    annotation_track = source.getAnnotationsTrack()
    if not annotation_track:
        return []

    timeline_in = int(track_item.timelineIn())
    timeline_out = int(track_item.timelineOut())
    source_in = float(track_item.sourceIn())
    frames = []

    for subtrack in annotation_track.subTrackItems():
        for annotation in subtrack:
            annotation_source_frame = float(annotation.timelineIn())
            timeline_frame = timeline_in + int(
                round(annotation_source_frame - source_in)
            )

            if timeline_in <= timeline_frame <= timeline_out:
                frames.append(timeline_frame)

    return sorted(set(frames))


def go_to_annotation(direction):
    """Mueve el viewer a la anotacion siguiente o anterior del clip seleccionado."""
    track_item = get_selected_track_item()
    if not track_item:
        return

    viewer = hiero.ui.currentViewer()
    if not viewer:
        print("[ANNOTATION_NAV] No hay un viewer activo.")
        return

    frames = get_annotation_frames_for_track_item(track_item)
    if not frames:
        print("[ANNOTATION_NAV] No se encontraron anotaciones en el clip seleccionado.")
        return

    current_frame = int(viewer.player(0).time())

    if direction == "previous":
        for frame in reversed(frames):
            if frame < current_frame:
                viewer.setTime(frame)
                print("[ANNOTATION_NAV] Salto a anotacion anterior:", frame)
                return

        viewer.setTime(frames[-1])
        print("[ANNOTATION_NAV] Vuelta a la ultima anotacion:", frames[-1])
        return

    for frame in frames:
        if frame > current_frame:
            viewer.setTime(frame)
            print("[ANNOTATION_NAV] Salto a anotacion siguiente:", frame)
            return

    viewer.setTime(frames[0])
    print("[ANNOTATION_NAV] Vuelta a la primera anotacion:", frames[0])


def main(direction="next"):
    if direction not in ("next", "previous"):
        raise ValueError("La direccion debe ser 'next' o 'previous'.")

    go_to_annotation(direction)


if __name__ == "__main__":
    main()
