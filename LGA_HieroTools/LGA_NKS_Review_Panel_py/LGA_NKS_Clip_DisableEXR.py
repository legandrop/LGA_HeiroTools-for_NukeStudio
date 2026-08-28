"""
____________________________________________________________________

  LGA_NKS_Clip_DisableEXR v1.32 | Lega

  Habilita o deshabilita el clip en el track especificado (por defecto usa TRACK_comp_EXR del módulo LGA_NKS_GetClip).

  Funcionamiento:
  1. Obtiene el clip del track especificado en la posición del playhead usando el módulo centralizado
  2. Si no encuentra clip en playhead, usa el clip seleccionado como fallback
  3. Invierte el estado de habilitación del clip (enabled/disabled)

  Modo `enable_rev_fallback=True` (default, escenario comp / botón "ON OFF _comp_"):
  - Trabaja exclusivamente sobre el playhead (sin fallback a selección).
  - Si el track _comp_ está vacío en el playhead o el clip ahí es v00/v000, busca un track
    de review (_compRev_, _compMOV_, _compMXF_, etc.) y opera sobre el clip de ese track.
  - Si el track encontrado no coincide con TRACK_comp_REV, ofrece renombrarlo al nombre canónico
    antes de operar.

  Modo `enable_rev_fallback=False` (wrappers de otras tasks, ej: roto):
  - Comportamiento original: usa `get_clip_to_process` (playhead con fallback a selección).

  v1.32: El diálogo de renombrado de track pasa a ask_question del helper
         LGA_NKS_MessageBox (estilo del pack), adaptando el retorno a bool.
  v1.31: Default `enable_rev_fallback=True` para que el botón ON OFF _comp_ herede el nuevo
         flujo sin necesidad de un wrapper específico. El wrapper de roto pasa `False` explícito
         para mantener su comportamiento original.
  v1.30: Agrega lógica de fallback al track de review (TRACK_comp_REV) cuando _comp_ está vacío
         o tiene v00/v000 en el playhead. Detecta tracks similares (_compMOV_, _compMXF_, etc.)
         y ofrece renombrarlos al nombre canónico.
  v1.22: main() acepta track_name opcional para reusar desde otros scripts (ej: DisableRoto)
  v1.21: Usa TRACK_comp_EXR del módulo en lugar de hardcodear "EXR", permitiendo cambiar el track por defecto
  v1.10: Usa el módulo utilitario LGA_NKS_GetClip para obtener el clip (no permite selecciones múltiples)
____________________________________________________________________

"""

import hiero.core
import hiero.ui
import os
import re
from pathlib import Path
import sys

DEBUG = True

def debug_print(*message):
    if DEBUG:
        print(*message)

# Importar utilidades para obtener clips y constantes de tracks
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    from LGA_NKS_Shared.LGA_NKS_GetClip import (
        get_clip_to_process,
        find_clip_at_playhead_in_track,
        TRACK_comp_EXR,
        TRACK_comp_REV,
    )
    # Sincronizar el debug con el módulo utilitario
    from LGA_NKS_Shared import LGA_NKS_GetClip as clip_utils
    clip_utils.DEBUG = DEBUG
else:
    debug_print("ERROR: No se encontró el módulo LGA_NKS_GetClip")

# Qt para el diálogo de renombrado
try:
    from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets
    from LGA_NKS_Shared.LGA_NKS_MessageBox import ask_question
except Exception:
    QtWidgets = None
    ask_question = None


# Patrón v00/v000 (mismo criterio que LGA_NKS_ON_Clips_OFF_v00-Clips.py)
_V00_PATTERN = re.compile(r"_comp_v(\d{2,3})", re.IGNORECASE)

# Patrón de tracks "similares" a _comp_ (ej: _compMOV_, _compMXF_, _compRev_)
# Excluye al propio _comp_ por requerir al menos una letra entre "comp" y el "_" final.
_SIMILAR_COMP_TRACK_PATTERN = re.compile(r"^_comp[A-Za-z]+_$", re.IGNORECASE)


def toggle_clip_enabled(clip):
    """
    Invierte el estado de habilitación del clip.
    """
    if not clip:
        return False

    try:
        nuevo_estado = not clip.isEnabled()
        clip.setEnabled(nuevo_estado)
        estado_texto = "habilitado" if nuevo_estado else "deshabilitado"
        debug_print(f"Clip {clip.name()} {estado_texto}")
        return True
    except Exception as e:
        debug_print(f"Error al cambiar el estado del clip: {e}")
        return False


def _is_v00_clip(clip):
    """Devuelve True si el filename del clip matchea _comp_v00 o _comp_v000."""
    try:
        fileinfos = clip.source().mediaSource().fileinfos()
        if not fileinfos:
            return False
        file_path = fileinfos[0].filename()
        if not file_path:
            return False
        filename = os.path.basename(file_path)
        m = _V00_PATTERN.search(filename)
        if not m:
            return False
        version = m.group(1)
        return version in ("00", "000")
    except Exception as e:
        debug_print(f"Error verificando v00 en clip: {e}")
        return False


def _find_clip_in_track_at_playhead(track):
    """Busca un clip (no efecto) bajo el playhead en un track específico."""
    try:
        viewer = hiero.ui.currentViewer()
        if not viewer:
            return None
        current_time = viewer.time()
        for item in track:
            if isinstance(item, hiero.core.EffectTrackItem):
                continue
            if item.timelineIn() <= current_time < item.timelineOut():
                return item
        return None
    except Exception as e:
        debug_print(f"Error buscando clip en track {track.name()}: {e}")
        return None


def _find_similar_comp_tracks(seq):
    """
    Devuelve la lista de tracks cuyo nombre matchea el patrón _compXXX_ (case-insensitive),
    excluyendo el propio _comp_.
    """
    matches = []
    try:
        for track in seq.videoTracks():
            name = track.name()
            if name.upper() == TRACK_comp_EXR.upper():
                continue
            if _SIMILAR_COMP_TRACK_PATTERN.match(name):
                matches.append(track)
    except Exception as e:
        debug_print(f"Error buscando tracks similares a _comp_: {e}")
    return matches


def _ask_rename_track(found_name, canonical_name):
    """
    Diálogo Sí/No preguntando si renombrar `found_name` a `canonical_name`.
    Devuelve True si el usuario acepta, False en cualquier otro caso.
    """
    if QtWidgets is None or ask_question is None:
        debug_print("Qt no disponible, no se puede mostrar el diálogo de renombrado.")
        return False
    try:
        # Pregunta estandar del pack: devuelve bool directamente
        return ask_question(
            None,
            "Track de review encontrado",
            f"Se encontró el track <b>{found_name}</b>, que no coincide con el "
            f"nombre canónico <b>{canonical_name}</b>.<br><br>"
            f"¿Querés renombrarlo a <b>{canonical_name}</b> y continuar con el toggle?",
            yes_text="Yes",
            no_text="No",
        )
    except Exception as e:
        debug_print(f"Error mostrando diálogo de renombrado: {e}")
        return False


def _resolve_clip_with_rev_fallback():
    """
    Lógica especial para el botón ON/OFF _comp_:
    - Si _comp_ tiene un clip en el playhead y NO es v00/v000 → devuelve ese clip.
    - Si _comp_ está vacío en el playhead, o el clip es v00/v000 → busca tracks similares
      (_compXXX_) y devuelve el clip bajo el playhead del track de review.
    - Si encuentra un track similar pero con nombre distinto al canónico, ofrece renombrar
      antes de devolver el clip. Si el usuario cancela, devuelve None.

    Devuelve el clip a togglear, o None si no hay nada que hacer.
    """
    try:
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("No hay secuencia activa.")
            return None

        comp_clip = find_clip_at_playhead_in_track(seq, track_name=TRACK_comp_EXR)
        if comp_clip and not _is_v00_clip(comp_clip):
            debug_print(f"Clip en _comp_ válido (no v00): {comp_clip.name()}")
            return comp_clip

        if comp_clip:
            debug_print(f"Clip en _comp_ es v00/v000, buscando track de review.")
        else:
            debug_print("No hay clip en _comp_ en el playhead, buscando track de review.")

        similar_tracks = _find_similar_comp_tracks(seq)
        if not similar_tracks:
            debug_print("No se encontraron tracks similares a _comp_.")
            return comp_clip  # puede ser None o un v00; mantiene comportamiento mínimo

        # Priorizar el track canónico si existe (case-insensitive)
        canonical = next(
            (t for t in similar_tracks if t.name().upper() == TRACK_comp_REV.upper()),
            None,
        )
        if canonical is not None:
            debug_print(f"Track canónico encontrado: {canonical.name()}")
            return _find_clip_in_track_at_playhead(canonical)

        # No hay canónico: elegir candidato a renombrar
        # Preferir uno que tenga clip bajo el playhead
        candidates_with_clip = [
            (t, _find_clip_in_track_at_playhead(t)) for t in similar_tracks
        ]
        chosen_track, chosen_clip = next(
            ((t, c) for (t, c) in candidates_with_clip if c is not None),
            (similar_tracks[0], None),
        )

        if not _ask_rename_track(chosen_track.name(), TRACK_comp_REV):
            debug_print("Usuario canceló el renombrado. Abortando toggle.")
            return None

        old_name = chosen_track.name()
        try:
            chosen_track.setName(TRACK_comp_REV)
            debug_print(f"Track renombrado: '{old_name}' → '{TRACK_comp_REV}'")
        except Exception as e:
            debug_print(f"Error renombrando el track '{old_name}': {e}")
            return None

        # Re-resolver el clip por las dudas (algunos backends invalidan referencias al renombrar)
        return chosen_clip if chosen_clip else _find_clip_in_track_at_playhead(chosen_track)

    except Exception as e:
        debug_print(f"Error en _resolve_clip_with_rev_fallback: {e}")
        return None


def main(track_name=None, enable_rev_fallback=True):
    """
    Función principal que ejecuta la secuencia de operaciones.

    Args:
        track_name: nombre del track a usar. None = TRACK_comp_EXR (por defecto).
                    Pasar TRACK_roto_EXR para operar sobre _roto_, etc.
        enable_rev_fallback: si True (por defecto, escenario comp), activa el fallback al track
                             de review. Cuando _comp_ está vacío en el playhead o tiene v00/v000,
                             busca un track _compXXX_ y opera sobre ese clip. Si el track tiene
                             un nombre distinto al canónico (TRACK_comp_REV), pregunta si
                             renombrarlo antes de operar. Wrappers para otras tasks (ej: roto)
                             deben pasar `enable_rev_fallback=False` explícitamente.
    """
    if enable_rev_fallback:
        clip = _resolve_clip_with_rev_fallback()
        if not clip:
            debug_print("No se encontró un clip válido para togglear (fallback REV).")
            return
        if toggle_clip_enabled(clip):
            debug_print("Operación completada con éxito (fallback REV).")
        else:
            debug_print("No se pudo cambiar el estado del clip (fallback REV).")
        return

    # Comportamiento original (genérico)
    clip = get_clip_to_process(track_name=track_name, prioritize_multiple_selection=False)
    if not clip:
        debug_print("No se encontró un clip en el track especificado en la posición actual o seleccionado.")
        return

    if toggle_clip_enabled(clip):
        debug_print("Operación completada con éxito.")
    else:
        debug_print("No se pudo cambiar el estado del clip.")

if __name__ == "__main__":
    main()
