"""
____________________________________________________________________

  LGA_import_shots_rename v1.01 | Lega

  Helpers de logica para la seccion Rename de LGA_import_shots.

  Changelog:
  - v1.01: Agrega stages Prefix/Suffix al preview, rename real y colores.

____________________________________________________________________
"""

from __future__ import annotations

import os
import re
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path


_SEQ_RE = re.compile(r"^(?P<prefix>.+?)(?P<delim>[_.])(?P<frame>\d+)\.exr$", re.IGNORECASE)
_SEQ_HASH_RE = re.compile(r"^(?P<prefix>.+?)(?P<delim>[_.])(?P<hashes>#+)\.exr$", re.IGNORECASE)


@dataclass
class RenameOp:
    src: str
    dst: str


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _colorize(text: str, colors_by_index: dict[int, str]) -> str:
    if not text:
        return ""
    chunks = []
    cur_color = None
    cur = []
    for i, ch in enumerate(text):
        c = colors_by_index.get(i)
        if c != cur_color:
            if cur:
                raw = "".join(cur)
                if cur_color:
                    chunks.append("<span style='color:%s; font-weight:600;'>%s</span>" % (cur_color, _html_escape(raw)))
                else:
                    chunks.append("<span style='color:#a7a7a7;'>%s</span>" % _html_escape(raw))
            cur = [ch]
            cur_color = c
        else:
            cur.append(ch)
    if cur:
        raw = "".join(cur)
        if cur_color:
            chunks.append("<span style='color:%s; font-weight:600;'>%s</span>" % (cur_color, _html_escape(raw)))
        else:
            chunks.append("<span style='color:#a7a7a7;'>%s</span>" % _html_escape(raw))
    return "".join(chunks)


def _seq_info_from_file_name(file_name: str):
    m = _SEQ_RE.match(file_name)
    if not m:
        return None
    frame = m.group("frame")
    return {
        "prefix": m.group("prefix"),
        "delim": m.group("delim"),
        "padding": len(frame),
        "frame_example": frame,
    }


def _seq_info_from_hash_name(name: str):
    m = _SEQ_HASH_RE.match(name)
    if not m:
        return None
    return {
        "prefix": m.group("prefix"),
        "delim": m.group("delim"),
        "padding": len(m.group("hashes")),
    }


def _find_literal(haystack: str, needle: str, start_idx: int, case_sensitive: bool) -> int:
    if case_sensitive:
        return haystack.find(needle, start_idx)
    return haystack.lower().find(needle.lower(), start_idx)


def _apply_search_replace_stage(
    cur_text: str,
    cur_orig_map: list[int | None],
    cur_tags: list[set[int]],
    search: str,
    replace: str,
    case_sensitive: bool,
    stage_id: int,
):
    if not search:
        return cur_text, cur_orig_map, cur_tags, set(), False

    out_text_parts = []
    out_map: list[int | None] = []
    out_tags: list[set[int]] = []
    changed_orig = set()
    idx = 0
    changed = False

    while True:
        pos = _find_literal(cur_text, search, idx, case_sensitive)
        if pos < 0:
            break
        end = pos + len(search)

        out_text_parts.append(cur_text[idx:pos])
        out_map.extend(cur_orig_map[idx:pos])
        out_tags.extend(cur_tags[idx:pos])

        src_slice_map = cur_orig_map[pos:end]
        src_slice_tags = cur_tags[pos:end]
        if replace == cur_text[pos:end]:
            out_text_parts.append(cur_text[pos:end])
            out_map.extend(src_slice_map)
            out_tags.extend(src_slice_tags)
        else:
            changed = True
            for oi in src_slice_map:
                if oi is not None:
                    changed_orig.add(oi)
            out_text_parts.append(replace)
            out_map.extend([None] * len(replace))
            out_tags.extend([{stage_id} for _ in replace])

        idx = end

    out_text_parts.append(cur_text[idx:])
    out_map.extend(cur_orig_map[idx:])
    out_tags.extend(cur_tags[idx:])
    return "".join(out_text_parts), out_map, out_tags, changed_orig, changed


def _apply_delimiter_stage(cur_text, cur_orig_map, cur_tags, delimiter_char, stage_id):
    info = _seq_info_from_hash_name(cur_text)
    if not info:
        return cur_text, cur_orig_map, cur_tags, set(), False
    if info["delim"] == delimiter_char:
        return cur_text, cur_orig_map, cur_tags, set(), False
    m = _SEQ_HASH_RE.match(cur_text)
    if not m:
        return cur_text, cur_orig_map, cur_tags, set(), False
    delim_idx = m.start("delim")
    out = list(cur_text)
    out[delim_idx] = delimiter_char
    out_text = "".join(out)
    out_map = list(cur_orig_map)
    out_tags = [set(x) for x in cur_tags]
    out_tags[delim_idx].add(stage_id)
    changed_orig = set()
    oi = cur_orig_map[delim_idx]
    if oi is not None:
        changed_orig.add(oi)
    return out_text, out_map, out_tags, changed_orig, True


def _apply_padding_stage(cur_text, cur_orig_map, cur_tags, digits, stage_id):
    info = _seq_info_from_hash_name(cur_text)
    if not info:
        return cur_text, cur_orig_map, cur_tags, set(), False
    m = _SEQ_HASH_RE.match(cur_text)
    if not m:
        return cur_text, cur_orig_map, cur_tags, set(), False
    hashes_start, hashes_end = m.start("hashes"), m.end("hashes")
    old_len = hashes_end - hashes_start
    if old_len == digits:
        return cur_text, cur_orig_map, cur_tags, set(), False

    prefix = cur_text[:hashes_start]
    suffix = cur_text[hashes_end:]
    new_hashes = "#" * digits
    out_text = prefix + new_hashes + suffix

    out_map = []
    out_tags = []
    out_map.extend(cur_orig_map[:hashes_start])
    out_tags.extend(cur_tags[:hashes_start])

    changed_orig = set()
    for oi in cur_orig_map[hashes_start:hashes_end]:
        if oi is not None:
            changed_orig.add(oi)

    out_map.extend([None] * digits)
    out_tags.extend([{stage_id} for _ in range(digits)])

    out_map.extend(cur_orig_map[hashes_end:])
    out_tags.extend(cur_tags[hashes_end:])
    return out_text, out_map, out_tags, changed_orig, True


def _apply_prefix_stage(cur_text, cur_orig_map, cur_tags, prefix, stage_id):
    if not prefix:
        return cur_text, cur_orig_map, cur_tags, set(), False
    out_text = prefix + cur_text
    out_map = [None] * len(prefix) + list(cur_orig_map)
    out_tags = [{stage_id} for _ in prefix] + [set(x) for x in cur_tags]
    return out_text, out_map, out_tags, set(), True


def _suffix_insert_pos(cur_text: str, is_sequence: bool) -> int:
    if is_sequence:
        m = re.match(r"^(.+?)(_[vV]\d+)([_.]\#+\.exr)$", cur_text, re.IGNORECASE)
        if m:
            return m.start(2)
        m = re.match(r"^(.+?)([_.])(\#+)(\.exr)$", cur_text, re.IGNORECASE)
        if m:
            return m.start(2)

    m = re.match(r"^(.+?)(_[vV]\d+)(\.[^.]+)$", cur_text)
    if m:
        return m.start(2)
    m = re.match(r"^(.+?)(\.[^.]+)$", cur_text)
    if m:
        return m.start(2)
    return len(cur_text)


def _apply_suffix_stage(cur_text, cur_orig_map, cur_tags, suffix, is_sequence, stage_id):
    if not suffix:
        return cur_text, cur_orig_map, cur_tags, set(), False
    pos = _suffix_insert_pos(cur_text, is_sequence)
    out_text = cur_text[:pos] + suffix + cur_text[pos:]
    out_map = list(cur_orig_map[:pos]) + [None] * len(suffix) + list(cur_orig_map[pos:])
    out_tags = (
        [set(x) for x in cur_tags[:pos]]
        + [{stage_id} for _ in suffix]
        + [set(x) for x in cur_tags[pos:]]
    )
    return out_text, out_map, out_tags, set(), True


def build_selected_rows(selected_items: list[dict]) -> list[dict]:
    rows = []
    for item in selected_items:
        kind = item.get("kind")
        source = item.get("source", "")
        raw_path = item.get("path") or item.get("version_dir") or item.get("first_file") or ""
        if not raw_path:
            continue
        path = Path(raw_path)

        is_seq = False
        seq_info = None
        first_file = item.get("first_file") or ""
        if kind == "exr_seq" and first_file and path.suffix.lower() == ".exr":
            path = Path(first_file).parent
        if kind == "exr_seq" or (path.is_dir() and first_file):
            ff = Path(first_file).name
            seq_info = _seq_info_from_file_name(ff)
            if seq_info:
                is_seq = True

        if is_seq:
            folder_name = path.name
            original_name = "%s%s%s.exr" % (
                seq_info["prefix"],
                seq_info["delim"],
                "#" * seq_info["padding"],
            )
            # Mínimo de dígitos requeridos para representar el frame más alto sin perder ceros
            # significativos. Ej: frame 98776 → 5; frame 1230 → 4.
            _last = item.get("last_frame")
            _min_d = max(len(str(int(_last))) if _last is not None else 1, 1)
            rows.append({
                "source": source,
                "item": item,
                "item_path": str(path),
                "folder_path": str(path),
                "folder_name": folder_name,
                "is_sequence": True,
                "seq_prefix": seq_info["prefix"],
                "seq_delim": seq_info["delim"],
                "seq_padding": seq_info["padding"],
                "original_name": original_name,
                "min_digits_needed": _min_d,
            })
            continue

        file_path = path
        file_name = file_path.name
        rows.append({
            "source": source,
            "item": item,
            "item_path": str(file_path),
            "folder_path": str(file_path.parent),
            "folder_name": file_path.parent.name,
            "is_sequence": False,
            "original_name": file_name,
        })

    return rows


def compute_preview(rows: list[dict], settings: dict, stage_colors: dict[int, str],
                    shot_name: str = "", shotname_color: str = "") -> list[dict]:
    sr1 = settings.get("sr1", {})
    sr2 = settings.get("sr2", {})
    prefix_cfg = settings.get("prefix", {})
    suffix_cfg = settings.get("suffix", {})
    delimiter = settings.get("delimiter", {})
    padding = settings.get("padding", {})
    prefix_text = prefix_cfg.get("text", "")
    suffix_text = suffix_cfg.get("text", "")
    delimiter_char = delimiter.get("char", "_")
    if delimiter_char not in ("_", "."):
        delimiter_char = "_"
    try:
        user_digits = int(padding.get("digits", 4))
    except Exception:
        user_digits = 4
    user_digits = max(1, min(user_digits, 12))

    preview = []
    for row in rows:
        original = row["original_name"]
        cur = original
        cur_map = list(range(len(cur)))
        cur_tags = [set() for _ in cur]
        orig_stage_marks = {1: set(), 2: set(), 3: set(), 4: set(), 5: set(), 6: set()}
        changed_any = False
        effective_digits = None

        cur, cur_map, cur_tags, marks, changed = _apply_search_replace_stage(
            cur,
            cur_map,
            cur_tags,
            sr1.get("search", ""),
            sr1.get("replace", ""),
            sr1.get("case_sensitive", "false").lower() == "true",
            stage_id=1,
        )
        orig_stage_marks[1].update(marks)
        changed_any = changed_any or changed

        cur, cur_map, cur_tags, marks, changed = _apply_search_replace_stage(
            cur,
            cur_map,
            cur_tags,
            sr2.get("search", ""),
            sr2.get("replace", ""),
            sr2.get("case_sensitive", "false").lower() == "true",
            stage_id=2,
        )
        orig_stage_marks[2].update(marks)
        changed_any = changed_any or changed

        cur, cur_map, cur_tags, marks, changed = _apply_prefix_stage(
            cur,
            cur_map,
            cur_tags,
            prefix_text,
            stage_id=3,
        )
        orig_stage_marks[3].update(marks)
        changed_any = changed_any or changed

        cur, cur_map, cur_tags, marks, changed = _apply_suffix_stage(
            cur,
            cur_map,
            cur_tags,
            suffix_text,
            row.get("is_sequence"),
            stage_id=4,
        )
        orig_stage_marks[4].update(marks)
        changed_any = changed_any or changed

        if row.get("is_sequence"):
            cur, cur_map, cur_tags, marks, changed = _apply_delimiter_stage(
                cur, cur_map, cur_tags, delimiter_char, stage_id=5
            )
            orig_stage_marks[5].update(marks)
            changed_any = changed_any or changed

            # Dígitos efectivos: nunca menor al mínimo necesario para el frame más alto
            seq_min_digits = row.get("min_digits_needed", 1)
            effective_digits = max(user_digits, seq_min_digits)

            cur, cur_map, cur_tags, marks, changed = _apply_padding_stage(
                cur, cur_map, cur_tags, effective_digits, stage_id=6
            )
            orig_stage_marks[6].update(marks)
            changed_any = changed_any or changed

        renamed = cur
        orig_colors = {}
        for stage_id, idxs in orig_stage_marks.items():
            clr = stage_colors.get(stage_id)
            if not clr:
                continue
            for oi in idxs:
                orig_colors[oi] = clr

        ren_colors = {}
        for i, tags in enumerate(cur_tags):
            if not tags:
                continue
            st = sorted(tags)[-1]
            clr = stage_colors.get(st)
            if clr:
                ren_colors[i] = clr

        # Shotname prefix como capa base (S&R tiene prioridad al mergear encima)
        if shot_name and shotname_color:
            if original.startswith(shot_name):
                sn_base = {i: shotname_color for i in range(len(shot_name))}
                orig_colors = {**sn_base, **orig_colors}
            if renamed.startswith(shot_name):
                sn_base = {i: shotname_color for i in range(len(shot_name))}
                ren_colors = {**sn_base, **ren_colors}

        folder_warning = None
        blocked = False
        if row.get("is_sequence"):
            folder_name = row.get("folder_name", "")
            seq_prefix = row.get("seq_prefix", "")
            if folder_name != seq_prefix:
                blocked = True
                folder_warning = "Mismatch carpeta/seq"

        target_folder_name = row.get("folder_name", "")
        folder_original_html = "<span style='color:#a7a7a7;'>%s</span>" % _html_escape(row.get("folder_name", ""))
        folder_renamed_html = folder_original_html
        if row.get("is_sequence"):
            ren_info = _seq_info_from_hash_name(renamed)
            if ren_info and ren_info.get("prefix"):
                target_folder_name = ren_info["prefix"]
            else:
                target_folder_name = row.get("seq_prefix", row.get("folder_name", ""))

            orig_folder_colors = {}
            ren_folder_colors = {}
            prefix_len = len(row.get("seq_prefix", ""))
            for i in range(prefix_len):
                if i in orig_colors:
                    orig_folder_colors[i] = orig_colors[i]
            ren_prefix_len = len(target_folder_name)
            for i in range(ren_prefix_len):
                if i in ren_colors:
                    ren_folder_colors[i] = ren_colors[i]
            folder_original_html = _colorize(row.get("folder_name", ""), orig_folder_colors)
            folder_renamed_html = _colorize(target_folder_name, ren_folder_colors)

        preview.append({
            **row,
            "renamed_name": renamed,
            "has_changes": changed_any and (renamed != original),
            "original_html": _colorize(original, orig_colors),
            "renamed_html": _colorize(renamed, ren_colors),
            "folder_original_html": folder_original_html,
            "folder_renamed_html": folder_renamed_html,
            "blocked": blocked,
            "status": folder_warning or ("Pendiente" if changed_any else "Sin cambios"),
            "target_folder_name": target_folder_name,
            "effective_digits": effective_digits if row.get("is_sequence") else None,
            "user_digits": user_digits if row.get("is_sequence") else None,
        })

    _mark_collisions(preview)
    return preview


def _mark_collisions(preview_rows: list[dict]):
    """Detecta colisiones (duplicados entre filas + destino existente) usando
    `build_row_ops_for_ui` (liviano, sin iterdir). El chequeo exhaustivo file-by-file
    se hace recién al ejecutar el rename, no en cada refresh del preview.
    """
    # Cache: una sola call a build_row_ops_for_ui por fila, reutilizada en las
    # tres pasadas siguientes.
    ops_by_pr_id = {}
    for pr in preview_rows:
        if pr.get("blocked"):
            continue
        ops_by_pr_id[id(pr)] = build_row_ops_for_ui(pr)

    # Pasada 1: claimed_targets para detectar dos filas apuntando al mismo destino.
    claimed_targets = {}
    for pr in preview_rows:
        if pr.get("blocked"):
            continue
        for op in ops_by_pr_id.get(id(pr), ()):
            dst = os.path.normcase(os.path.normpath(op.dst))
            claimed_targets.setdefault(dst, []).append(pr)
    for dst, owners in claimed_targets.items():
        if len(owners) > 1:
            for pr in owners:
                pr["blocked"] = True
                pr["status"] = "Conflicto destino duplicado"

    # Pasada 2: set de sources planeados (para no falsear "destino ya existe"
    # cuando ese destino es el src de otra fila que también vamos a mover).
    planned_src = set()
    for pr in preview_rows:
        if pr.get("blocked"):
            continue
        for op in ops_by_pr_id.get(id(pr), ()):
            planned_src.add(os.path.normcase(os.path.normpath(op.src)))

    # Pasada 3: chequeo de existencia en disco (sólo sobre las ops representativas).
    for pr in preview_rows:
        if pr.get("blocked"):
            continue
        for op in ops_by_pr_id.get(id(pr), ()):
            dst_norm = os.path.normcase(os.path.normpath(op.dst))
            src_norm = os.path.normcase(os.path.normpath(op.src))
            if dst_norm == src_norm:
                continue
            if os.path.exists(op.dst) and dst_norm not in planned_src and os.path.exists(op.src):
                pr["blocked"] = True
                pr["status"] = "Destino ya existe"
                break


def build_row_ops_for_ui(preview_row: dict) -> list[RenameOp]:
    """Versión liviana de build_row_ops para el preview de UI.

    Devuelve hasta 2 ops representativas por fila SIN tocar el disco
    (sin iterdir, sin enumerar cientos de frames). Es suficiente para:
      - Detectar colisiones entre filas (claimed_targets/planned_src).
      - Chequear "Destino ya existe" sobre rutas representativas.

    NO usar para ejecutar el rename. Para ejecutar usar build_row_ops()
    que sí enumera cada archivo.
    """
    if preview_row.get("blocked"):
        return []
    if not preview_row.get("has_changes"):
        return []

    if not preview_row.get("is_sequence"):
        src = preview_row.get("item_path", "")
        dst = str(Path(src).with_name(preview_row.get("renamed_name", "")))
        if src == dst:
            return []
        return [RenameOp(src=src, dst=dst)]

    folder_path = Path(preview_row.get("folder_path", ""))
    old_name = preview_row.get("original_name", "")
    new_name = preview_row.get("renamed_name", "")
    old_info = _seq_info_from_hash_name(old_name)
    new_info = _seq_info_from_hash_name(new_name)
    if not old_info or not new_info:
        return []

    ops = []

    # Op representativa de los renames de archivo: usamos el primer frame real
    # del item si está disponible, mapeado a su nombre nuevo. Es una sola op
    # que sirve para detectar conflictos de claim y chequear si el destino
    # ya existe sin necesidad de enumerar la secuencia entera.
    item = preview_row.get("item") or {}
    first_file = item.get("first_file")
    if first_file:
        m = _SEQ_RE.match(Path(first_file).name)
        if m:
            frame_num = int(m.group("frame"))
            new_frame_str = str(frame_num).zfill(new_info["padding"])
            new_file_name = "%s%s%s.exr" % (
                new_info["prefix"], new_info["delim"], new_frame_str
            )
            dst_file = str(Path(first_file).with_name(new_file_name))
            if first_file != dst_file:
                ops.append(RenameOp(src=first_file, dst=dst_file))

    # Op del folder rename si aplica
    new_folder_name = preview_row.get("target_folder_name", folder_path.name)
    if new_folder_name and new_folder_name != folder_path.name:
        ops.append(RenameOp(
            src=str(folder_path),
            dst=str(folder_path.with_name(new_folder_name)),
        ))

    return ops


def build_row_ops(preview_row: dict) -> list[RenameOp]:
    if preview_row.get("blocked"):
        return []
    if not preview_row.get("has_changes"):
        return []

    if not preview_row.get("is_sequence"):
        src = preview_row.get("item_path", "")
        dst = str(Path(src).with_name(preview_row.get("renamed_name", "")))
        if src == dst:
            return []
        return [RenameOp(src=src, dst=dst)]

    folder_path = Path(preview_row.get("folder_path", ""))
    old_name = preview_row.get("original_name", "")
    new_name = preview_row.get("renamed_name", "")
    old_info = _seq_info_from_hash_name(old_name)
    new_info = _seq_info_from_hash_name(new_name)
    if not old_info or not new_info:
        return []

    ops = []
    try:
        files = sorted(folder_path.iterdir())
    except Exception:
        files = []

    for fp in files:
        if not fp.is_file():
            continue
        m = _SEQ_RE.match(fp.name)
        if not m:
            continue
        if m.group("prefix") != old_info["prefix"] or m.group("delim") != old_info["delim"]:
            continue
        frame_num = int(m.group("frame"))
        new_frame = str(frame_num).zfill(new_info["padding"])
        new_file_name = "%s%s%s.exr" % (
            new_info["prefix"], new_info["delim"], new_frame
        )
        dst = str(fp.with_name(new_file_name))
        if str(fp) != dst:
            ops.append(RenameOp(src=str(fp), dst=dst))

    old_folder = folder_path
    new_folder_name = preview_row.get("target_folder_name", old_folder.name)
    if new_folder_name and new_folder_name != old_folder.name:
        ops.append(RenameOp(src=str(old_folder), dst=str(old_folder.with_name(new_folder_name))))

    return ops


def _prepare_test_rows(rows_to_apply: list[dict], test_folder_name: str):
    prepared = []
    for row in rows_to_apply:
        cloned = dict(row)
        if row.get("is_sequence"):
            src_folder = Path(row.get("folder_path", ""))
            if not src_folder.exists():
                continue
            sandbox_root = src_folder.parent / test_folder_name
            sandbox_root.mkdir(parents=True, exist_ok=True)
            cloned_folder = sandbox_root / src_folder.name
            if cloned_folder.exists():
                shutil.rmtree(str(cloned_folder), ignore_errors=True)
            shutil.copytree(str(src_folder), str(cloned_folder))
            cloned["folder_path"] = str(cloned_folder)
            cloned["item_path"] = str(cloned_folder)
            cloned["folder_name"] = cloned_folder.name
            prepared.append(cloned)
            continue

        src_file = Path(row.get("item_path", ""))
        if not src_file.exists():
            continue
        sandbox_root = src_file.parent / test_folder_name
        sandbox_root.mkdir(parents=True, exist_ok=True)
        cloned_file = sandbox_root / src_file.name
        shutil.copy2(str(src_file), str(cloned_file))
        cloned["item_path"] = str(cloned_file)
        cloned["folder_path"] = str(cloned_file.parent)
        cloned["folder_name"] = cloned_file.parent.name
        prepared.append(cloned)
    return prepared


def execute_ops(rows_to_apply: list[dict], test_mode: bool = False, test_folder_name: str = "renamned", log_fn=None):
    def _log(*parts):
        if log_fn:
            try:
                log_fn(*parts)
            except Exception:
                pass

    _log("=== Rename execute_ops ===")
    _log("rows_to_apply:", len(rows_to_apply), "test_mode:", test_mode, "test_folder:", test_folder_name)
    effective_rows = rows_to_apply
    if test_mode:
        _log("Preparing test rows...")
        effective_rows = _prepare_test_rows(rows_to_apply, test_folder_name)
        _log("Prepared test rows:", len(effective_rows))

    ops = []
    for row in effective_rows:
        ops.extend(build_row_ops(row))
    _log("Total ops generated:", len(ops))
    if not ops:
        _log("No ops to execute.")
        return {"applied": 0, "errors": []}

    file_ops = []
    dir_ops = []
    for op in ops:
        src_path = Path(op.src)
        if src_path.exists() and src_path.is_dir():
            dir_ops.append(op)
        elif src_path.suffix.lower() == "":
            if src_path.exists() and src_path.is_dir():
                dir_ops.append(op)
            else:
                file_ops.append(op)
        else:
            file_ops.append(op)

    ordered_files = sorted(
        file_ops,
        key=lambda o: -len(Path(o.src).parts)
    )
    ordered_dirs = sorted(
        dir_ops,
        key=lambda o: -len(Path(o.src).parts)
    )
    tmp_ops = []
    errors = []
    try:
        _log("Phase 1 (file -> tmp). file_ops:", len(ordered_files))
        for op in ordered_files:
            src = Path(op.src)
            if not src.exists():
                _log("SKIP missing src:", str(src))
                continue
            tmp_name = src.with_name("%s.__rename_tmp_%s__" % (src.name, uuid.uuid4().hex[:8]))
            _log("TMP:", str(src), "->", str(tmp_name))
            src.rename(tmp_name)
            tmp_ops.append((tmp_name, Path(op.dst)))

        applied = 0
        _log("Phase 2 (tmp -> final). tmp_ops:", len(tmp_ops))
        for tmp_src, final_dst in tmp_ops:
            final_dst.parent.mkdir(parents=True, exist_ok=True)
            _log("FINAL:", str(tmp_src), "->", str(final_dst))
            tmp_src.rename(final_dst)
            applied += 1

        _log("Phase 3 (dir rename). dir_ops:", len(ordered_dirs))
        for op in ordered_dirs:
            src = Path(op.src)
            dst = Path(op.dst)
            if not src.exists():
                _log("SKIP missing dir src:", str(src))
                continue
            dst.parent.mkdir(parents=True, exist_ok=True)
            _log("DIR:", str(src), "->", str(dst))
            src.rename(dst)
            applied += 1
        _log("Applied ops:", applied)
        return {"applied": applied, "errors": errors}
    except Exception as exc:
        _log("ERROR execute_ops:", exc)
        errors.append(str(exc))
        for tmp_src, final_dst in reversed(tmp_ops):
            try:
                if tmp_src.exists():
                    if not final_dst.exists():
                        orig_guess = Path(str(tmp_src).split(".__rename_tmp_")[0])
                        _log("ROLLBACK:", str(tmp_src), "->", str(orig_guess))
                        tmp_src.rename(orig_guess)
            except Exception:
                pass
        return {"applied": 0, "errors": errors}
