"""
____________________________________________________________________

  LGA_import_shots_bin v1.00 | Lega

  Helpers de bin para la importacion real de LGA_import_shots.

____________________________________________________________________
"""

from __future__ import annotations

try:
    import hiero.core
    _HIERO_AVAILABLE = True
except ImportError:
    _HIERO_AVAILABLE = False


# ── logging inyectable ────────────────────────────────────────────────────────

_debug_print = None


def set_debug_print(fn):
    """Inyecta la función debug_print del módulo principal."""
    global _debug_print
    _debug_print = fn


def _log(*args, level="info"):
    if _debug_print is not None:
        try:
            _debug_print(*args, level=level)
        except Exception:
            pass


# ── funciones públicas ────────────────────────────────────────────────────────

def find_or_create_shot_bin(seq, shot_name: str):
    """
    Busca o crea el bin destino para el shot, siguiendo la estructura:
        clipsBin / F <seq_name> / <shot_name>

    Idéntica a la estructura que usa LGA_NKS_OrganizeProject.py.

    Retorna hiero.core.Bin, o None si no se puede resolver.
    """
    if not _HIERO_AVAILABLE:
        _log("find_or_create_shot_bin: Hiero no disponible", level="warning")
        return None

    try:
        project = hiero.core.projects()[0]
    except Exception as exc:
        _log("find_or_create_shot_bin: no se pudo obtener el proyecto → %s" % exc,
             level="error")
        return None

    clips_bin = project.clipsBin()

    # Sub-bin de secuencia: "F <seq_name>"
    try:
        seq_name = seq.name()
    except Exception:
        seq_name = ""
    seq_bin_name = ("F %s" % seq_name) if seq_name else "Shots"

    seq_bin = None
    for item in clips_bin.items():
        try:
            if hasattr(item, "name") and item.name() == seq_bin_name:
                seq_bin = item
                break
        except Exception:
            pass

    if seq_bin is None:
        seq_bin = hiero.core.Bin(seq_bin_name)
        clips_bin.addItem(seq_bin)
        _log("find_or_create_shot_bin: creado bin '%s'" % seq_bin_name)
    else:
        _log("find_or_create_shot_bin: bin '%s' ya existe" % seq_bin_name)

    # Sub-bin de shot: "<shot_name>"
    shot_bin = None
    for item in seq_bin.items():
        try:
            if hasattr(item, "name") and item.name() == shot_name:
                shot_bin = item
                break
        except Exception:
            pass

    if shot_bin is None:
        shot_bin = hiero.core.Bin(shot_name)
        seq_bin.addItem(shot_bin)
        _log("find_or_create_shot_bin: creado bin '%s/%s'" % (seq_bin_name, shot_name))
    else:
        _log("find_or_create_shot_bin: bin '%s/%s' ya existe" % (seq_bin_name, shot_name))

    return shot_bin


def import_item_to_bin(item: dict, target_bin):
    """
    Importa un ítem (EXR seq o MOV) como hiero.core.Clip y lo agrega al bin.

    El item es el dict que construye _scan_input_folder / _scan_publish_folders:
      kind       : "exr_seq" | "mov"
      first_file : ruta al primer EXR (solo si kind == "exr_seq")
      path       : ruta al archivo MOV (solo si kind == "mov")
      name       : nombre de display del clip

    Patron basado en LGA_NKS_CreateV000._import_v000_to_bin:
    - Crea hiero.core.Clip desde first_file (deteccion automatica de secuencia).
    - Asigna el nombre con clip.setName().
    - Agrega al bin con BinItem.
    - Llama clip.rescan() y loguea el rango detectado por Hiero.

    Retorna (clip, error_str). error_str es None si OK.
    """
    if not _HIERO_AVAILABLE:
        return None, "Hiero no disponible"

    kind = item.get("kind")
    path = item.get("path", "")
    name = item.get("name", "") or item.get("version_name", "") or "clip"

    _log("import_item_to_bin: kind='%s' name='%s'" % (kind, name))

    try:
        if kind == "exr_seq":
            first = item.get("first_file", "")
            if not first:
                msg = "Sin first_file para EXR seq: %s" % path
                _log("import_item_to_bin: %s" % msg, level="error")
                return None, msg
            _log("import_item_to_bin: creando Clip desde '%s'" % first)
            clip = hiero.core.Clip(str(first))

        elif kind == "mov":
            _log("import_item_to_bin: creando Clip desde '%s'" % path)
            clip = hiero.core.Clip(str(path))

        else:
            msg = "Tipo de item no soportado: kind='%s' para '%s'" % (kind, name)
            _log("import_item_to_bin: %s" % msg, level="error")
            return None, msg

        # Asignar nombre al clip
        clip.setName(name)

        # Agregar al bin
        if target_bin is not None:
            bin_item = hiero.core.BinItem(clip)
            target_bin.addItem(bin_item)
            _log("import_item_to_bin: '%s' agregado al bin" % name)

        # Rescan para que Hiero lea el rango real de disco (patron de CreateV000)
        try:
            ms = clip.mediaSource()
            before_first = int(ms.startTime())
            before_last  = int(ms.startTime() + ms.duration() - 1)
            clip.rescan()
            ms = clip.mediaSource()
            after_first = int(ms.startTime())
            after_last  = int(ms.startTime() + ms.duration() - 1)
            _log("import_item_to_bin: rescan '%s' rango %d-%d → %d-%d"
                 % (name, before_first, before_last, after_first, after_last))
        except Exception as re:
            _log("import_item_to_bin: rescan fallo (no critico) → %s" % re,
                 level="warning")

        return clip, None

    except Exception as exc:
        _log("import_item_to_bin: excepcion importando '%s' → %s" % (name, exc),
             level="error")
        return None, str(exc)
