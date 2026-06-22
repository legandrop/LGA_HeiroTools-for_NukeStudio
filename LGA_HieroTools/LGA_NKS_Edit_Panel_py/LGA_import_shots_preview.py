"""
____________________________________________________________________

  LGA_import_shots_preview v1.02 | Lega

  Logica de datos para la pagina Import Preview de LGA_import_shots.

  v1.02: classify_track_type reconoce tracks _dmp_ como tipo "dmp".
  v1.01: Soporte de track keys unicas (name||bt_index) para distinguir tracks
         duplicados por nombre en preview/import. Expone track_key y
         track_label (con sufijo "(2)" cuando aplica), manteniendo
         compatibilidad con mapeo legado por nombre.

____________________________________________________________________
"""

from __future__ import annotations

import re

try:
    import hiero.core
    _HIERO_AVAILABLE = True
except ImportError:
    _HIERO_AVAILABLE = False


# ── logging inyectable ────────────────────────────────────────────────────────

# Se reemplaza desde el módulo principal con set_debug_print()
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


# ── utilidad de color ─────────────────────────────────────────────────────────

def mix_colors(hex_color: str, base: str = "#1e1e1e", factor: float = 1.0) -> str:
    """
    Mezcla hex_color con base a la intensidad indicada por factor.

    factor=1.0  → hex_color puro
    factor=0.0  → base puro
    factor=0.35 → 35% hex_color + 65% base  (útil para fondos de chips)

    Retorna string hex "#rrggbb".
    """
    def _parse(h):
        h = h.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    r1, g1, b1 = _parse(hex_color)
    r2, g2, b2 = _parse(base)
    t = max(0.0, min(1.0, factor))
    r = int(r1 * t + r2 * (1 - t))
    g = int(g1 * t + g2 * (1 - t))
    b = int(b1 * t + b2 * (1 - t))
    return "#%02x%02x%02x" % (r, g, b)


# ── clasificación de track ────────────────────────────────────────────────────

def classify_track_type(track_name: str) -> str:
    """
    Clasifica el tipo de track por su nombre.

    Retorna: "plate" | "editref" | "comp" | "roto" | "cleanup" | "dmp" | "other"
    """
    lower = str(track_name).strip().lower()
    if lower.endswith("plate"):
        return "plate"
    if "editref" in lower:
        return "editref"
    if lower == "_comp_" or lower.startswith("_comp_"):
        return "comp"
    if lower == "_roto_" or lower.startswith("_roto_"):
        return "roto"
    if lower == "_cleanup_" or lower.startswith("_cleanup_"):
        return "cleanup"
    if lower == "_dmp_" or lower.startswith("_dmp_"):
        return "dmp"
    return "other"


_TRACK_KEY_SEP = "||"


def _make_track_key(track_name: str, bt_index: int) -> str:
    return "%s%s%d" % (str(track_name), _TRACK_KEY_SEP, int(bt_index))


def _parse_track_key(track_ref):
    text = str(track_ref or "")
    if _TRACK_KEY_SEP in text:
        name, idx_txt = text.rsplit(_TRACK_KEY_SEP, 1)
        try:
            return name, int(idx_txt)
        except Exception:
            return name, None
    return text, None


# ── helpers de búsqueda en track ─────────────────────────────────────────────

def _clip_display_name(item) -> str:
    """
    Devuelve el nombre de display de un TrackItem de Hiero a partir del
    nombre del archivo fuente, eliminando el número de frame y la extensión.

    Ejemplos:
      "TEST_013_010_aPlate_v01_%04d.exr"  → "TEST_013_010_aPlate_v01"
      "TEST_013_010_aPlate_v01_1001.exr"  → "TEST_013_010_aPlate_v01"
      "TEST_013_020_EditRef.mov"           → "TEST_013_020_EditRef"

    Esto es más informativo que item.name() que devuelve solo el shot/basename.
    Si la extracción falla, se usa item.name() como fallback.
    """
    try:
        fileinfos = item.source().mediaSource().fileinfos()
        if fileinfos:
            import os as _os
            basename = _os.path.basename(fileinfos[0].filename())
            # Paso 1: quitar patrones tipo _%04d.exr  (EXR sequences con printf format)
            name = re.sub(r'[_.]%\d*[dD]\.[^.]+$', '', basename)
            # Paso 2: quitar patrones tipo _1001.exr  (frame number explícito, ≥4 dígitos)
            name = re.sub(r'[_.]\d{4,}\.[^.]+$', '', name)
            # Paso 3: quitar extensión restante  (.mov, .mxf, .mp4, etc.)
            name = re.sub(r'\.[^.]+$', '', name)
            if name:
                _log("_clip_display_name: '%s' → '%s'" % (basename, name))
                return name
    except Exception as exc:
        _log("_clip_display_name: error extrayendo nombre de archivo → %s" % exc)
    # Fallback
    fallback = item.name()
    _log("_clip_display_name: usando fallback item.name() = '%s'" % fallback)
    return fallback


def _find_adjacent_clips(track, prev_shot_name, next_shot_name):
    """
    Dado un track de Hiero y los nombres exactos del shot anterior y siguiente,
    devuelve el clip que pertenece a cada uno (o None si no existe en ese track).

    Busca por item.name() — el shot name del TrackItem — en lugar de por posición
    de frames. Esto evita que clips lejanos de otros shots sean clasificados
    incorrectamente como vecinos cuando el track tiene un gap en ese slot.

    Retorna:
        (before, after)  — cada uno es dict|None con keys:
                           name, tl_in, tl_out, duration
    """
    before = None
    after  = None

    for item in track.items():
        if not _HIERO_AVAILABLE:
            break
        try:
            if isinstance(item, hiero.core.EffectTrackItem):
                continue
            shot_name = item.name()
            tl_in     = int(item.timelineIn())
            tl_out    = int(item.timelineOut())
            disp_name = _clip_display_name(item)
        except Exception as exc:
            _log("_find_adjacent_clips: excepción leyendo item → %s" % exc)
            continue

        _log(
            "_find_adjacent_clips: examinando clip '%s' (shot='%s') TL %d-%d"
            % (disp_name, shot_name, tl_in, tl_out)
        )

        if prev_shot_name and shot_name == prev_shot_name:
            duration = tl_out - tl_in + 1
            _log("_find_adjacent_clips: → before '%s' dur=%d" % (disp_name, duration))
            before = {
                "name": disp_name, "tl_in": tl_in, "tl_out": tl_out,
                "duration": duration,
            }

        elif next_shot_name and shot_name == next_shot_name:
            duration = tl_out - tl_in + 1
            _log("_find_adjacent_clips: → after '%s' dur=%d" % (disp_name, duration))
            after = {
                "name": disp_name, "tl_in": tl_in, "tl_out": tl_out,
                "duration": duration,
            }

    _log(
        "_find_adjacent_clips: → before=%s | after=%s"
        % (
            ("'%s' %df" % (before["name"], before["duration"])) if before else "None",
            ("'%s' %df" % (after["name"],  after["duration"]))  if after  else "None",
        )
    )
    return before, after


# ── función principal ─────────────────────────────────────────────────────────

def build_import_preview_data(
    seq,
    shot_name: str,
    insert_frame: int,
    prev_shot_name,
    next_shot_name,
    items_by_track: dict[str, list[dict]],
    unassigned_items: list[dict],
) -> dict:
    """
    Construye la estructura de datos para el preview de importación.

    Args:
        seq:              hiero.core.Sequence activa
        shot_name:        nombre del shot que se importa
        insert_frame:     frame de inserción calculado por _find_insert_frame()
        prev_shot_name:   nombre exacto del shot anterior en el timeline (o None)
        next_shot_name:   nombre exacto del shot siguiente en el timeline (o None)
        items_by_track:   dict track_key → [item_dict] de los ítems chequeados.
                          track_key puede ser:
                            - "TrackName||<bt_index>" (preferido, único)
                            - "TrackName" (legado)
        unassigned_items: ítems chequeados sin track asignado, cada uno con
                          un campo extra "_color" con su color de barra

    Retorna:
        {
          "tracks": [
            {
              "track_key": str,
              "track_name": str,
              "track_label": str,
              "track_type": "plate"|"editref"|"comp"|"roto"|"cleanup"|"other",
              "before_clip": {"name": str, "tl_in": int, "tl_out": int, "duration": int} | None,
              "new_items":   [item_dict],
              "after_clip":  {"name": str, "tl_in": int, "tl_out": int, "duration": int} | None,
            },
            ...
          ],
          "unassigned": [item_dict],  # cada uno tiene "_color"
        }

    Reglas de inclusión de tracks:
    - Se incluyen TODOS los tracks del timeline sin excepción.
    - El orden es de arriba hacia abajo como se ve en el timeline (reversed de videoTracks()).
    - Los tracks asignados a ítems nuevos que no existen en el timeline
      se añaden al final de la lista.
    """
    tracks_result = []

    if not _HIERO_AVAILABLE or seq is None:
        _log("build_import_preview_data: Hiero no disponible o seq es None", level="warning")
        return {
            "tracks": tracks_result,
            "unassigned": list(unassigned_items),
        }

    try:
        # bt-order: índice 0 = fondo del timeline.
        tracks_bt = list(seq.videoTracks())
    except Exception as exc:
        _log("build_import_preview_data: error obteniendo videoTracks: %s" % exc, level="error")
        tracks_bt = []

    _log(
        "build_import_preview_data: seq='%s', insert_frame=%d, "
        "prev_shot='%s', next_shot='%s', "
        "tracks_en_timeline=%d, tracks_con_items=%d, unassigned=%d"
        % (seq.name(), insert_frame,
           prev_shot_name or "", next_shot_name or "",
           len(tracks_bt), len(items_by_track), len(unassigned_items))
    )

    total_by_name = {}
    for track in tracks_bt:
        tname = track.name()
        if tname.strip().lower() in {"burnin", "burn in", "burn_in"}:
            continue
        total_by_name[tname] = total_by_name.get(tname, 0) + 1

    seen_by_name = {}
    seen_track_keys = set()
    seen_track_names = set()
    # Compatibilidad: si llegan claves legadas por nombre y hay duplicados,
    # solo el primer track topmost consume esos ítems.
    assigned_legacy_names = set()

    for bt_index in range(len(tracks_bt) - 1, -1, -1):  # top→bottom
        track = tracks_bt[bt_index]
        try:
            tname = track.name()
        except Exception:
            continue

        if tname.strip().lower() in {"burnin", "burn in", "burn_in"}:
            continue

        seen_track_names.add(tname)
        track_key = _make_track_key(tname, bt_index)
        seen_track_keys.add(track_key)

        seen_by_name[tname] = seen_by_name.get(tname, 0) + 1
        occ = seen_by_name[tname]
        track_label = tname if total_by_name.get(tname, 0) <= 1 else "%s (%d)" % (tname, occ)

        before, after = _find_adjacent_clips(track, prev_shot_name, next_shot_name)

        if track_key in items_by_track:
            new_items = items_by_track[track_key]
        elif tname in items_by_track and tname not in assigned_legacy_names:
            new_items = items_by_track[tname]
            assigned_legacy_names.add(tname)
        else:
            new_items = []

        _log(
            "  track='%s' | before=%s | new_items=%d | after=%s"
            % (
                track_label,
                ("'%s' %df" % (before["name"], before["duration"])) if before else "None",
                len(new_items),
                ("'%s' %df" % (after["name"], after["duration"])) if after else "None",
            )
        )

        tracks_result.append({
            "track_key": track_key,
            "track_name": tname,
            "track_label": track_label,
            "track_type": classify_track_type(tname),
            "before_clip": before,
            "new_items": list(new_items),
            "after_clip": after,
        })

    # Tracks asignados a ítems nuevos que NO existen en el timeline
    for track_ref, items in items_by_track.items():
        track_name, bt_index = _parse_track_key(track_ref)
        explicit_key = _make_track_key(track_name, bt_index) if bt_index is not None else None
        if explicit_key and explicit_key in seen_track_keys:
            continue
        if bt_index is None and track_name in seen_track_names:
            continue
        _log("  track='%s' no existe en timeline → se añade al final" % track_name)
        tracks_result.append({
            "track_key": explicit_key or track_name,
            "track_name": track_name,
            "track_label": track_name,
            "track_type": classify_track_type(track_name),
            "before_clip": None,
            "new_items": list(items),
            "after_clip": None,
        })

    return {
        "tracks": tracks_result,
        "unassigned": list(unassigned_items),
    }
