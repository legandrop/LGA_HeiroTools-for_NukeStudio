"""
____________________________________________________________________

  LGA_NKS_Compare_Versions v1.21 | Lega

  Crea un nuevo track con una version anterior del clip seleccionado
  y pone al track en modo difference

  v1.21: La version anterior se busca dentro de la RAMA del clip. Antes se
         ordenaban todas las versiones del bin y se tomaba la de al lado, asi
         que estando en v100 bajaba a v012, que es la rama de otro compositor
         y no una version previa de este trabajo.
  v1.20: Centralización del nombre del track usando TRACK_comp_EXR del módulo LGA_NKS_GetClip
____________________________________________________________________

"""

import hiero.core
import hiero.ui
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtGui
from pathlib import Path
import sys

# Importar utilidades para obtener clips
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    from LGA_NKS_Shared.LGA_NKS_GetClip import TRACK_comp_EXR
    from LGA_NKS_VersionBranching import branch_containing, extract_version_number
else:
    # Fallback si no se encuentra el módulo
    TRACK_comp_EXR = "_comp_"


def copy_clip():
    # Obtener la secuencia activa en el timeline
    seq = hiero.ui.activeSequence()
    if not seq:
        print("No active sequence found.")
        return None

    # Obtener el timeline editor
    te = hiero.ui.getTimelineEditor(seq)
    selected_clips = te.selection()

    if len(selected_clips) == 0:
        print("*** No clips selected on the track ***")
        return None

    # Copiar el primer clip seleccionado (suponiendo que solo se selecciona uno)
    clip = selected_clips[0]
    if isinstance(clip, hiero.core.EffectTrackItem):
        print(f"Ignored effect item: {clip.name()}")
        return None

    copied_clip = clip.copy()
    print(f"Copied clip: {clip.name()}")
    return copied_clip, clip.timelineIn(), clip.timelineOut() - clip.timelineIn() + 1


def reorder_tracks_and_add_compare(seq):
    # Verificar si ya existe un track llamado "COMPARE"
    compare_track = None
    for track in seq.videoTracks():
        if track.name() == "COMPARE":
            compare_track = track
            break

    # Si no existe un track llamado "COMPARE", encontrar el indice del track TRACK_comp_EXR y crear "COMPARE"
    if not compare_track:
        exr_index = -1
        for index, track in enumerate(seq.videoTracks()):
            if track.name() == TRACK_comp_EXR:
                exr_index = index
                break

        if exr_index == -1:
            print(f"No se encontro un track llamado '{TRACK_comp_EXR}'.")
            return None

        # Obtener la lista de todos los tracks de video
        video_tracks = list(seq.videoTracks())
        print(f"Current video tracks: {[track.name() for track in video_tracks]}")

        # Remover todos los tracks
        for track in video_tracks:
            seq.removeTrack(track)

        # Crear el nuevo track llamado "COMPARE"
        compare_track = hiero.core.VideoTrack("COMPARE")

        # Reinsertar los tracks en el orden deseado, incluyendo el nuevo track antes de TRACK_comp_EXR
        reordered_tracks = (
            video_tracks[:exr_index] + [compare_track] + video_tracks[exr_index:]
        )
        for track in reordered_tracks:
            seq.addTrack(track)

        print(f"Track 'COMPARE' added and moved to index {exr_index}.")
        print(f"Reordered video tracks: {[track.name() for track in reordered_tracks]}")
    else:
        print("Track 'COMPARE' already exists.")

    return compare_track


def paste_clip_to_compare(compare_track, copied_clip, start_time, duration):
    if not compare_track or not copied_clip:
        return

    # Pegar el clip en el track COMPARE
    compare_track.addItem(copied_clip)
    copied_clip.setTimelineIn(start_time)
    copied_clip.setTimelineOut(start_time + duration - 1)
    print(
        f"Pasted clip '{copied_clip.name()}' to track COMPARE at start time {start_time}"
    )


def toggle_blend_mode_for_exr(seq):
    # Volver a encontrar el track TRACK_comp_EXR despues de agregar el track "COMPARE"
    for track in seq.videoTracks():
        if track.name() == TRACK_comp_EXR:
            exr_track = track
            break
    else:
        print(f"No se encontro un track llamado '{TRACK_comp_EXR}'.")
        return

    # Verificar si el blend mode ya esta activado
    if exr_track.isBlendEnabled():
        # Si esta activado, lo desactiva
        exr_track.setBlendEnabled(False)
        print(f"Blend mode desactivado para el track '{TRACK_comp_EXR}'.")
    else:
        # Si no esta activado, lo activa y cambia el modo a "Difference"
        exr_track.setBlendEnabled(True)
        exr_track.setBlendMode("difference")
        print(f"Blend mode 'Difference' activado para el track '{TRACK_comp_EXR}'.")


def self_replace_clip(copied_clip):
    try:
        if isinstance(copied_clip, hiero.core.EffectTrackItem):
            print(f"Ignored effect item: {copied_clip.name()}")
            return

        # Obtener el archivo original del clip copiado
        file_path = copied_clip.source().mediaSource().fileinfos()[0].filename()
        print(f"Replacing clip with file: {file_path}")

        # Reemplazar el clip copiado con el archivo original
        copied_clip.replaceClips(file_path)
        print(f"Clip replaced successfully with {file_path}.")
    except Exception as e:
        print(f"Error replacing clip: {e}")


def scan_and_downgrade_clip_version(clip):
    """Baja el clip copiado a la version anterior DENTRO de su rama.

    Ordenar todas las versiones y tomar la anterior cruzaba de rama: parado
    en v100 la "anterior" resultaba ser v012, que no es una version previa
    de este trabajo sino la punta de la rama de otro compositor.
    """

    def get_all_versions(binItem):
        versions = binItem.items()
        return sorted(versions, key=lambda v: extract_version_number(v.name()))

    vc = hiero.core.VersionScanner()
    bin_item = clip.source().binItem()
    activeVersion = bin_item.activeVersion()
    vc.doScan(activeVersion)

    versions = get_all_versions(bin_item)
    if versions:
        current_version = bin_item.activeVersion()
        current_number = extract_version_number(current_version.name())
        numbers = [extract_version_number(v.name()) for v in versions]
        own_branch = branch_containing(numbers, current_number)

        # Candidatas: solo las de su rama que esten por debajo de la actual.
        previous_numbers = [n for n in own_branch if n < current_number]
        if previous_numbers:
            target = max(previous_numbers)
            previous_version = next(
                v for v, n in zip(versions, numbers) if n == target
            )
            bin_item.setActiveVersion(previous_version)
            print(f"Changed {clip.name()} to version {previous_version.name()}")
        else:
            print(f"{clip.name()} is already at the oldest version of its branch.")
    else:
        print(f"No versions found for clip: {clip.name()}")


def main(selected_clip=None):
    # Obtener la secuencia activa en el timeline
    seq = hiero.ui.activeSequence()
    if not seq:
        print("No active sequence found.")
        return

    # Iniciar una accion de undo para las primeras operaciones
    project = seq.project()
    project.beginUndo(
        f"Copy Clip, Reorder Tracks, Paste Clip to COMPARE, and Set {TRACK_comp_EXR} to Difference"
    )

    try:
        # Copiar el clip seleccionado
        if selected_clip:
            copied_clip_data = (
                selected_clip.copy(),
                selected_clip.timelineIn(),
                selected_clip.timelineOut() - selected_clip.timelineIn() + 1,
            )
        else:
            copied_clip_data = copy_clip()

        if copied_clip_data is None:
            return

        copied_clip, start_time, duration = copied_clip_data

        # Manejo adicional si copied_clip es None despues del desempaquetado (aunque copied_clip_data is None deberia cubrirlo)
        if not copied_clip:
            return

        # Guardar el clip original antes de copiarlo
        original_clip = hiero.ui.getTimelineEditor(seq).selection()[0]

        # Reordenar los tracks y agregar el track COMPARE (solo si no existe)
        compare_track = reorder_tracks_and_add_compare(seq)
        if not compare_track:
            return

        # Limpiar el track COMPARE antes de pegar el nuevo clip para evitar duplicados
        # Se convierte a lista para permitir la modificacion durante la iteracion
        for item in list(compare_track.items()):
            compare_track.removeItem(item)
        print(f"Track 'COMPARE' limpiado de items anteriores.")

        # Pegar el clip copiado en el track COMPARE
        paste_clip_to_compare(compare_track, copied_clip, start_time, duration)

        # Cambiar el modo del track TRACK_comp_EXR a "difference"
        toggle_blend_mode_for_exr(seq)
    except Exception as e:
        print(f"Error during operation: {e}")
    finally:
        # Finalizar la primera accion de undo
        project.endUndo()

    # Iniciar una nueva accion de undo para el self replace clip
    project.beginUndo("Self Replace Clip")
    try:
        # Reemplazar el clip copiado en el track COMPARE con el archivo original
        self_replace_clip(copied_clip)
    except Exception as e:
        print(f"Error during self replace clip: {e}")
    finally:
        # Finalizar la segunda accion de undo
        project.endUndo()

    # Iniciar una nueva accion de undo para escanear y bajar la version del nuevo clip
    project.beginUndo("Scan and Downgrade New Clip Version")
    try:
        # Escanear y bajar una version del nuevo clip
        scan_and_downgrade_clip_version(copied_clip)
    except Exception as e:
        print(f"Error during scan and downgrade clip version: {e}")
    finally:
        # Finalizar la tercera accion de undo
        project.endUndo()
