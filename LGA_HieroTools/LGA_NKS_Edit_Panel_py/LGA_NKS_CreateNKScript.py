"""
____________________________________________________________________

  LGA_NKS_CreateNKScript v1.04 | Lega

  Crea el script de comp de Nuke de un shot a partir del template .nk
  del proyecto (<raiz>/ASSETS/*.nk), editandolo como texto plano:
  reemplaza los Reads de plates/denoised por las rutas reales del shot
  (version mas alta con EXR), borra los trios Read+Anchor+Stamp de los
  plates que no existen, clona trios para plates extra, apunta los
  OCIO (CDL/CLF) a los Look_Files del shot, centra el EditRef y ajusta
  el frame range del proyecto. El resultado se escribe en
  <shot>/Comp/1_projects/<shot>_comp_v000.nk (si ya existe, avisa y no pisa).

  v1.04: Las dos ventanas usan las hojas del modulo de estilo en vez de
         rehacerlas con tokens: Style.FORM, BTN_SECONDARY para las opciones
         de template y Cancel, BTN_PRIMARY para Create (unico violeta, ultimo
         a la derecha) y apply_ui_font. Se van los siete font-size propios y
         el spinbox del handle vuelve a ser nativo, como manda la hoja.
  v1.03: Rango siempre desde 1001. El publish comp_v000 (si existe) aparece
         como opcion default de rango; la duracion de cada plate sale del
         timeline cuando difiere del disco (retimes/trims), y la ventana
         muestra en vivo el rango resultante.
  v1.02: La salida es siempre <shot>_comp_v000.nk (antes buscaba la primera
         version libre); si ya existe, avisa y no pisa. El boton pasa a
         llamarse Create NK v000.
  v1.01: Fix: generar sobre el mismo shot con el que se armo el template
         abortaba por el control de "menciones al shot de origen".
         Log de cada corrida a logs/DebugPy_LGA_NKS_CreateNKScript.log.
  v1.00: Version inicial (nucleo portado de la sonda auditada
         nk_template_probe v0.07).
____________________________________________________________________
"""

import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import hiero.core
    import hiero.ui

    HIERO_AVAILABLE = True
except ImportError:
    HIERO_AVAILABLE = False

_shared_dir = Path(__file__).parent.parent / "LGA_NKS_Shared"
if _shared_dir.exists() and str(_shared_dir) not in sys.path:
    sys.path.insert(0, str(_shared_dir))
_pack_dir = Path(__file__).parent.parent
if _pack_dir.exists() and str(_pack_dir) not in sys.path:
    sys.path.insert(0, str(_pack_dir))

DEBUG = False

# Log de cada corrida, misma convencion que los otros logs del panel
LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "logs", "DebugPy_LGA_NKS_CreateNKScript.log"
)


def debug_print(*message):
    if DEBUG:
        print(*message)


def write_log_file(status, lines=None):
    """Escribe el log de la corrida (se pisa en cada ejecucion)."""
    try:
        import time

        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("[%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), status))
            for line in lines or []:
                fh.write(line + "\n")
    except OSError:
        pass


# ============================
# Constantes del template
# ============================

# Tokens de plate que el template contempla, en orden de columnas
KNOWN_LETTERS = ["a", "b", "c", "d", "e", "f"]
KNOWN_SPECIALS = ["cb", "rf", "cc", "lg"]

# aPlate y aDenoised nunca se borran: sus anchors estan cableados al resto
# del comp (stamps en la zona COLOR). Si faltan, es error.
NEVER_DELETE = {"aPlate", "aDenoised"}

# Layout del backdrop input (medido sobre el template)
COLUMN_START_X = -2087
COLUMN_STEP = 161
GROUP_GAP = 161
BACKDROP_RIGHT_PAD = 2532

INPUT_DIR_NAME = "_input"
LOOK_DIR_NAME = "Look_Files"
ASSETS_DIR_NAME = "ASSETS"
PROJECTS_SUBPATH = ("Comp", "1_projects")
DEFAULT_HANDLE = 8
START_FRAME = 1001  # los .nk arrancan siempre en 1001

# Nombre de shot tipo PROJ_1234_5678_VND (vendor al final)
SHOT_NAME_RE = re.compile(r"^[A-Za-z0-9]+_\d{3,4}_\d{3,4}_[A-Za-z0-9]{2,4}$")
SHOT_TOKEN_RE = re.compile(r"[A-Za-z0-9]+_\d{3,4}_\d{3,4}_[A-Za-z0-9]{2,4}")

PLATE_FOLDER_RE = re.compile(r"_([A-Za-z][A-Za-z0-9]*?Plate[0-9]*)_v\d+", re.IGNORECASE)


class CreateNKError(Exception):
    """Error esperado del flujo, para mostrar en un dialogo."""


# ============================
# Escaneo del shot
# ============================


def get_version(name):
    """Ultima ocurrencia de _v<NN> en el nombre, o 0."""
    versions = re.findall(r"_v(\d+)", name, re.IGNORECASE)
    return int(versions[-1]) if versions else 0


def list_plate_folders(root):
    """dict token_normalizado -> [carpetas candidatas, de version mas alta a
    mas baja]. El token normaliza gPlate -> g y preserva el sufijo numerico
    que va despues de Plate (cbPlate2 -> cb#2)."""
    if not os.path.isdir(root):
        return {}
    by_token = {}
    for entry in sorted(os.listdir(root)):
        full = os.path.join(root, entry)
        if not os.path.isdir(full):
            continue
        if "DENOISED" in entry.upper():
            continue
        m = PLATE_FOLDER_RE.search(entry)
        if not m:
            continue
        m2 = re.match(r"([A-Za-z]+?)Plate([0-9]*)$", m.group(1), re.IGNORECASE)
        if not m2:
            continue
        token = m2.group(1).lower() + ("#" + m2.group(2) if m2.group(2) else "")
        by_token.setdefault(token, []).append(full)
    for token in by_token:
        by_token[token].sort(key=lambda p: get_version(os.path.basename(p)), reverse=True)
    return by_token


def sequence_from_folder(folder):
    """dict con ruta %0Nd, first y last, o None si no hay EXR."""
    try:
        exrs = sorted(f for f in os.listdir(folder) if f.lower().endswith(".exr"))
    except OSError:
        return None
    if not exrs:
        return None
    frames = []
    pattern = None
    for f in exrs:
        m = re.search(r"(\d+)(?=\.exr$)", f, re.IGNORECASE)
        if not m:
            continue
        frames.append(int(m.group(1)))
        if pattern is None:
            pad = "%%0%dd" % len(m.group(1))
            pattern = f[: m.start(1)] + pad + f[m.end(1):]
    if not frames or pattern is None:
        return None
    return {
        "folder": folder,
        "path": folder.replace("\\", "/") + "/" + pattern,
        "first": min(frames),
        "last": max(frames),
    }


def best_sequence(folders, warnings, what):
    """Primera carpeta (de mas nueva a mas vieja) con EXR; si una version
    superior esta vacia, avisa y cae a la anterior."""
    for i, folder in enumerate(folders):
        info = sequence_from_folder(folder)
        if info is not None:
            if i > 0:
                warnings.append(
                    "%s: version mas alta sin EXR (%s), uso %s"
                    % (what, os.path.basename(folders[0]), os.path.basename(folder))
                )
            return info
    return None


def find_denoised_folders(prerender_root, plate_folder_name):
    """Carpetas Denoised candidatas para un plate, de mas nueva a mas vieja."""
    if not os.path.isdir(prerender_root):
        return []
    m = PLATE_FOLDER_RE.search(plate_folder_name)
    if not m:
        return []
    token_re = re.compile(r"(^|_)%s_v\d+" % re.escape(m.group(1)), re.IGNORECASE)
    matches = []
    for entry in sorted(os.listdir(prerender_root)):
        full = os.path.join(prerender_root, entry)
        if not os.path.isdir(full):
            continue
        if "DENOISED" not in entry.upper():
            continue
        if not token_re.search(entry):
            continue
        matches.append(full)
    matches.sort(key=lambda p: get_version(os.path.basename(p)), reverse=True)
    return matches


def token_to_key(token, denoised=False):
    """'g' -> 'gPlate'/'gDenoised'; 'cb#2' -> 'cbPlate2'/'cbDenoised2'."""
    base, _, suffix = token.partition("#")
    word = "Denoised" if denoised else "Plate"
    return base + word + suffix


def token_sort_key(token):
    base, _, suffix = token.partition("#")
    return (base, int(suffix) if suffix else 0)


def scan_shot(shot_root):
    """Plan de columnas del shot: lista ordenada de dicts
    {key, token, kind, info}, solo con lo que existe en disco, mas la lista
    de avisos (plates sin EXR, denoised huerfanos, versiones vacias)."""
    input_root = os.path.join(shot_root, INPUT_DIR_NAME)
    prerender_root = os.path.join(shot_root, "Comp", "2_prerenders")
    plates = list_plate_folders(input_root)

    letters = sorted(
        (t for t in plates if len(t.partition("#")[0]) == 1), key=token_sort_key
    )
    specials = []
    unknown = []
    for base in KNOWN_SPECIALS:
        specials.extend(
            sorted((t for t in plates if t.partition("#")[0] == base), key=token_sort_key)
        )
    for t in plates:
        if t not in letters and t not in specials:
            unknown.append(t)

    columns = []
    for token in letters:
        info = best_sequence(plates[token], unknown, token_to_key(token))
        if info is None:
            unknown.append(token + " (sin EXR)")
            continue
        columns.append({"key": token_to_key(token), "token": token, "kind": "plate", "info": info})
        den_folders = find_denoised_folders(prerender_root, os.path.basename(info["folder"]))
        den_info = best_sequence(den_folders, unknown, token_to_key(token, denoised=True))
        if den_info:
            columns.append({
                "key": token_to_key(token, denoised=True),
                "token": token, "kind": "denoised", "info": den_info,
            })
    for token in specials:
        info = best_sequence(plates[token], unknown, token_to_key(token))
        if info is None:
            unknown.append(token + " (sin EXR)")
            continue
        columns.append({"key": token_to_key(token), "token": token, "kind": "plate", "info": info})

    # denoised huerfanos: prerenders Denoised de un token sin plate en _input
    if os.path.isdir(prerender_root):
        plate_tokens_upper = set()
        for folders in plates.values():
            for folder in folders:
                m = PLATE_FOLDER_RE.search(os.path.basename(folder))
                if m:
                    plate_tokens_upper.add(m.group(1).upper())
        for entry in sorted(os.listdir(prerender_root)):
            if "DENOISED" not in entry.upper():
                continue
            m = PLATE_FOLDER_RE.search(entry)
            if m and m.group(1).upper() not in plate_tokens_upper:
                unknown.append("denoised huerfano sin plate en _input: %s" % entry)
    return columns, unknown


def resolve_look_files(shot_root):
    """(ruta cdl del aPlate o None, ruta clf o None). Acepta *_cdl y *.cdl."""
    look_dir = os.path.join(shot_root, INPUT_DIR_NAME, LOOK_DIR_NAME)
    cdl = None
    clf = None
    if os.path.isdir(look_dir):
        cdls = []
        clfs = []
        for f in sorted(os.listdir(look_dir)):
            low = f.lower()
            if "aplate" in low and (low.endswith("_cdl") or low.endswith(".cdl")):
                cdls.append(f)
            if low.endswith(".clf") or low.endswith(".cfl"):
                clfs.append(f)
        if cdls:
            cdls.sort(key=get_version)
            cdl = os.path.join(look_dir, cdls[-1]).replace("\\", "/")
        if clfs:
            clfs.sort(key=get_version)
            clf = os.path.join(look_dir, clfs[-1]).replace("\\", "/")
    return cdl, clf


def probe_mov_frames(mov_path):
    """Cantidad de frames de un mov via ffprobe, o None si no se pudo."""
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=nb_frames",
                "-of", "default=nw=1:nk=1", mov_path,
            ],
            capture_output=True, text=True, timeout=60,
        )
        value = out.stdout.strip()
        return int(value) if value.isdigit() else None
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def publish_v000_info(shot_root, shot_name):
    """Secuencia EXR del publish comp_v000 del shot (Create EXR v000), o None."""
    folder = os.path.join(shot_root, "Comp", "4_publish", "%s_comp_v000" % shot_name)
    if not os.path.isdir(folder):
        return None
    return sequence_from_folder(folder)


def find_editref(shot_root):
    """Ruta del mov de EditRef de version mas alta en _input, o None."""
    input_root = os.path.join(shot_root, INPUT_DIR_NAME)
    if not os.path.isdir(input_root):
        return None
    movs = [
        f for f in sorted(os.listdir(input_root))
        if "editref" in f.lower() and f.lower().endswith(".mov")
    ]
    if not movs:
        return None
    movs.sort(key=get_version)
    return os.path.join(input_root, movs[-1]).replace("\\", "/")


# ============================
# Parser de .nk: chunks por profundidad de llaves (ignora \{ y \})
# ============================

UNESCAPED_BRACE = re.compile(r"(?<!\\)([{}])")


def split_chunks(lines):
    """Lista de chunks; cada chunk es una lista de lineas contiguas.
    Un chunk multi-linea arranca donde la profundidad sube de 0 y termina
    cuando vuelve a 0. Lineas sin llaves a profundidad 0 son chunks propios."""
    chunks = []
    current = []
    depth = 0
    for line in lines:
        deltas = UNESCAPED_BRACE.findall(line)
        current.append(line)
        depth += deltas.count("{") - deltas.count("}")
        if depth < 0:
            raise CreateNKError("Template invalido: llaves desbalanceadas")
        if depth == 0:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    if depth != 0:
        raise CreateNKError("Template invalido: llaves sin cerrar")
    return chunks


def chunk_class(chunk):
    """Clase del nodo; tolera indentacion (nodos internos de un Group)."""
    m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s+\{", chunk[0])
    return m.group(1) if m else None


def _knob_re(knob):
    return re.compile(r"^(\s+)%s (.*)$" % re.escape(knob))


def chunk_knob(chunk, knob):
    """Valor crudo de un knob (' knob valor'), tolera indentacion, o None."""
    pat = _knob_re(knob)
    for line in chunk:
        m = pat.match(line)
        if m:
            return m.group(2).strip()
    return None


def set_chunk_knob(chunk, knob, value):
    """Reemplaza in place la primera linea del knob preservando la
    indentacion. True si la encontro."""
    pat = _knob_re(knob)
    for i, line in enumerate(chunk):
        m = pat.match(line)
        if m:
            chunk[i] = "%s%s %s" % (m.group(1), knob, value)
            return True
    return False


def normalized_label(chunk):
    raw = chunk_knob(chunk, "label")
    if raw is None:
        return None
    return raw.strip('"').replace("\\n", "").strip()


def quote_if_needed(path):
    return '"%s"' % path if " " in path else path


# ============================
# Trios Read + Anchor + Stamp
# ============================


def find_read_chunks(chunks):
    """dict label_normalizado -> indice de chunk, solo para clases Read."""
    found = {}
    for i, chunk in enumerate(chunks):
        if chunk_class(chunk) != "Read":
            continue
        label = normalized_label(chunk)
        if label:
            found[label] = i
    return found


def _is_stack_line(chunk):
    return len(chunk) == 1 and (
        chunk[0].startswith("set ") or chunk[0].startswith("push ")
    )


def trio_indices(chunks, read_idx, for_delete=False):
    """Indices [read, anchor, stamp] verificando estructura. Entre medio
    puede haber lineas set/push (aPlate/aDenoised), que NO se incluyen;
    un trio con set/push no se puede borrar."""
    result = [read_idx]
    idx = read_idx + 1
    has_stack = False
    while _is_stack_line(chunks[idx]):
        has_stack = True
        idx += 1
    if chunk_class(chunks[idx]) != "NoOp" or not (
        chunk_knob(chunks[idx], "name") or ""
    ).startswith("Anchor_"):
        raise CreateNKError(
            "El template no tiene la estructura esperada tras el Read %s"
            % chunk_knob(chunks[read_idx], "name")
        )
    result.append(idx)
    anchor_name = chunk_knob(chunks[idx], "name")
    idx += 1
    while _is_stack_line(chunks[idx]):
        has_stack = True
        idx += 1
    if chunk_class(chunks[idx]) == "PostageStamp":
        if chunk_knob(chunks[idx], "anchor") != anchor_name:
            raise CreateNKError("El Stamp tras %s no apunta a su anchor" % anchor_name)
        result.append(idx)
    if for_delete and has_stack:
        raise CreateNKError(
            "El trio de %s tiene lineas set/push: no es seguro borrarlo"
            % chunk_knob(chunks[read_idx], "name")
        )
    return result


def fill_read(chunk, info):
    set_chunk_knob(chunk, "file", quote_if_needed(info["path"]))
    for knob, value in (
        ("first", info["first"]),
        ("last", info["last"]),
        ("origfirst", info["first"]),
        ("origlast", info["last"]),
    ):
        set_chunk_knob(chunk, knob, str(value))


def set_trio_xpos(chunks_of_trio, x):
    for chunk in chunks_of_trio:
        set_chunk_knob(chunk, "xpos", str(x))


def clone_trio(trio_chunks, new_key, new_read_name, new_anchor_name, new_stamp_name):
    """Copia un trio cambiando nombres, labels y titles."""
    old_anchor = chunk_knob(trio_chunks[1], "name")
    cloned = []
    for chunk in trio_chunks:
        cloned.append([line.replace(old_anchor, new_anchor_name) for line in chunk])
    set_chunk_knob(cloned[0], "name", new_read_name)
    set_chunk_knob(cloned[0], "label", new_key)
    set_chunk_knob(cloned[1], "title", new_key)
    if len(cloned) > 2:
        set_chunk_knob(cloned[2], "name", new_stamp_name)
        set_chunk_knob(cloned[2], "title", new_key)
    return cloned


def max_numbered_name(chunks, prefix):
    best = 0
    pat = re.compile(r"^%s(\d+)$" % re.escape(prefix))
    for chunk in chunks:
        name = chunk_knob(chunk, "name")
        if name:
            m = pat.match(name)
            if m:
                best = max(best, int(m.group(1)))
    return best


def check_anchor_orphans(all_chunks, deleted_indices):
    """Ningun chunk restante debe referenciar anchors de bloques borrados."""
    deleted_anchors = set()
    for i in deleted_indices:
        name = chunk_knob(all_chunks[i], "name")
        if name and name.startswith("Anchor_"):
            deleted_anchors.add(name)
    problems = []
    for i, chunk in enumerate(all_chunks):
        if i in deleted_indices:
            continue
        for line in chunk:
            for anchor in deleted_anchors:
                if anchor in line:
                    problems.append(
                        "%s referencia %s" % (chunk_knob(chunk, "name"), anchor)
                    )
    return problems


# ============================
# Deteccion del shot de origen del template
# ============================


def detect_source_shot(template_text, template_name):
    """(shot_origen, carpeta_secuencia_origen) leidos del propio template.

    El shot de origen es el token tipo PROJ_1234_5678_VND mas frecuente en
    el texto que no sea el del nombre del template (que suele ser _0000_).
    La secuencia es el segmento de ruta que precede a ese shot."""
    template_token = None
    m = SHOT_TOKEN_RE.search(template_name)
    if m:
        template_token = m.group(0)
    counts = {}
    for token in SHOT_TOKEN_RE.findall(template_text):
        if token == template_token:
            continue
        counts[token] = counts.get(token, 0) + 1
    if not counts:
        raise CreateNKError(
            "No pude detectar el shot de origen del template (%s)" % template_name
        )
    source_shot = max(counts, key=lambda t: counts[t])
    seq_m = re.search(r"[/\\]([^/\\\s\"]+)[/\\]%s" % re.escape(source_shot), template_text)
    source_seq = seq_m.group(1) if seq_m else None
    return source_shot, source_seq


# ============================
# Armado del script
# ============================


def build_script(
    template_text,
    template_name,
    shot_root,
    out_path,
    log,
    columns=None,
    unknown=None,
    project_first=None,
    project_last=None,
    editref_frames=None,
    editref_start=None,
):
    """Genera el texto del .nk nuevo a partir del template.

    columns/unknown pueden venir de un scan_shot() previo (para no re-escanear).
    project_first/last: rango del proyecto (default: rango del aPlate).
    editref_frames: duracion del EditRef en frames (default: ffprobe).
    editref_start: frame de inicio del EditRef (default: centrado)."""
    shot_root = shot_root.rstrip("\\/")
    shot_name = os.path.basename(shot_root)
    if not SHOT_NAME_RE.match(shot_name):
        raise CreateNKError("El nombre del shot no es reconocible: %s" % shot_name)
    seq_folder = os.path.basename(os.path.dirname(shot_root))
    source_shot, source_seq = detect_source_shot(template_text, template_name)
    log.append("Shot: %s (seq %s) | origen del template: %s" % (shot_name, seq_folder, source_shot))

    if columns is None:
        columns, unknown = scan_shot(shot_root)
    unknown = unknown or []
    for col in columns:
        log.append(
            "  %-12s %s  [%d-%d]"
            % (col["key"], col["info"]["path"], col["info"]["first"], col["info"]["last"])
        )
    for u in unknown:
        log.append("  AVISO: %s" % u)

    present_keys = {c["key"] for c in columns}
    for key in NEVER_DELETE:
        if key not in present_keys:
            raise CreateNKError("El shot no tiene %s: no se puede armar el script" % key)

    lines = template_text.split("\n")
    chunks = split_chunks(lines)
    reads = find_read_chunks(chunks)

    known_keys = []
    for letter in KNOWN_LETTERS:
        known_keys.append(letter + "Plate")
        known_keys.append(letter + "Denoised")
    for sp in KNOWN_SPECIALS:
        known_keys.append(sp + "Plate")
    missing_labels = [k for k in known_keys if k not in reads]
    if missing_labels:
        raise CreateNKError(
            "El template no tiene estos Reads esperados: %s" % ", ".join(missing_labels)
        )

    # 1. llenar slots conocidos existentes / borrar los que no existen
    to_delete = []
    col_by_key = {c["key"]: c for c in columns}
    trios = {}
    for key in known_keys:
        trio = trio_indices(chunks, reads[key], for_delete=key not in col_by_key)
        if key in col_by_key:
            fill_read(chunks[reads[key]], col_by_key[key]["info"])
            trios[key] = [chunks[i] for i in trio]
            log.append("  SET %s" % key)
        else:
            to_delete.extend(trio)
            log.append("  BORRAR %s" % key)

    orphans = check_anchor_orphans(chunks, set(to_delete))
    if orphans:
        raise CreateNKError("Referencias a anchors borrados: %s" % orphans)

    # 2. clonar trios para columnas extra (gPlate, cbPlate2, gDenoised, ...)
    next_read = max_numbered_name(chunks, "Read") + 1
    next_stamp = max_numbered_name(chunks, "Stamp") + 1
    clones = {}
    used_names = {chunk_knob(c, "name") for c in chunks}
    for col in columns:
        if col["key"] in known_keys:
            continue
        source_key = "fDenoised" if col["kind"] == "denoised" else "fPlate"
        source_trio = trio_indices(chunks, reads[source_key])
        anchor_name = "Anchor_" + re.sub(r"[^A-Za-z0-9]", "", col["key"])
        if anchor_name in used_names:
            raise CreateNKError("Nombre de anchor repetido: %s" % anchor_name)
        used_names.add(anchor_name)
        cloned = clone_trio(
            [chunks[i] for i in source_trio],
            col["key"],
            "Read%d" % next_read,
            anchor_name,
            "Stamp%d" % next_stamp,
        )
        next_read += 1
        next_stamp += 1
        fill_read(cloned[0], col["info"])
        clones[col["key"]] = cloned
        trios[col["key"]] = cloned
        log.append("  CLONAR %s (desde %s)" % (col["key"], source_key))

    # 3. recomputar posiciones de columnas y backdrop input
    x = COLUMN_START_X
    last_x = x
    started_specials = False
    for col in columns:
        base = col["token"].partition("#")[0]
        if not started_specials and base in KNOWN_SPECIALS:
            x += GROUP_GAP
            started_specials = True
        set_trio_xpos(trios[col["key"]], x)
        last_x = x
        x += COLUMN_STEP
    for chunk in chunks:
        if chunk_class(chunk) == "BackdropNode" and normalized_label(chunk) == "input":
            set_chunk_knob(chunk, "bdwidth", str(last_x + BACKDROP_RIGHT_PAD))
            break

    # 4. OCIO CDL / LUT con rutas reales: todo nodo OCIO cuyo file apunte a
    # Look_Files (los del output y los internos del grupo VIEWER_INPUT)
    cdl, clf = resolve_look_files(shot_root)
    for chunk in chunks:
        cls = chunk_class(chunk)
        if cls not in ("OCIOCDLTransform", "OCIOFileTransform"):
            continue
        current = chunk_knob(chunk, "file") or ""
        if LOOK_DIR_NAME not in current:
            continue
        target = cdl if cls == "OCIOCDLTransform" else clf
        if target:
            set_chunk_knob(chunk, "file", quote_if_needed(target))
    if not cdl:
        log.append("  AVISO: no encontre CDL de aPlate en Look_Files")
    if not clf:
        log.append("  AVISO: no encontre .clf en Look_Files")

    # 5. Rango de proyecto: por parametro o rango del aPlate
    a_info = col_by_key["aPlate"]["info"]
    range_first = project_first if project_first is not None else a_info["first"]
    range_last = project_last if project_last is not None else a_info["last"]
    log.append("  Rango de proyecto: %d-%d" % (range_first, range_last))
    for chunk in chunks:
        if chunk_class(chunk) == "Root":
            set_chunk_knob(chunk, "name", quote_if_needed(out_path.replace("\\", "/")))
            set_chunk_knob(chunk, "first_frame", str(range_first))
            set_chunk_knob(chunk, "last_frame", str(range_last))
            set_chunk_knob(chunk, "frame", str(range_first))
            break

    # 5a. Read del publish v000 (CHECK vs EDIT): rango de proyecto
    for chunk in chunks:
        if chunk_class(chunk) == "Read" and "_comp_v000" in (
            chunk_knob(chunk, "file") or ""
        ):
            for knob in ("first", "origfirst"):
                set_chunk_knob(chunk, knob, str(range_first))
            for knob in ("last", "origlast"):
                set_chunk_knob(chunk, knob, str(range_last))

    # 5b. EditRef: duracion real del mov, inicio explicito (timeline) o
    # centrado en el rango (resto impar al lado out, como el import de shots).
    # El write de review se acota a esa ventana.
    if editref_frames is None:
        editref_mov = find_editref(shot_root)
        editref_frames = probe_mov_frames(editref_mov) if editref_mov else None
    if editref_frames:
        range_len = range_last - range_first + 1
        if editref_start is None:
            diff = max(0, range_len - editref_frames)
            editref_start = range_first + diff // 2
        editref_end = editref_start + editref_frames - 1
        for chunk in chunks:
            cls = chunk_class(chunk)
            if cls == "Read" and "editref" in (chunk_knob(chunk, "file") or "").lower():
                set_chunk_knob(chunk, "last", str(editref_frames))
                set_chunk_knob(chunk, "origlast", str(editref_frames))
            elif cls == "TimeClip":
                set_chunk_knob(chunk, "last", str(editref_frames))
                set_chunk_knob(chunk, "origlast", str(editref_frames))
                set_chunk_knob(chunk, "frame", str(editref_start))
            elif cls == "Write" and (chunk_knob(chunk, "name") or "").startswith(
                "WRITE_DNXHD"
            ):
                set_chunk_knob(chunk, "first", str(editref_start))
                set_chunk_knob(chunk, "last", str(editref_end))
        log.append(
            "  EditRef: %d frames, %d-%d" % (editref_frames, editref_start, editref_end)
        )
    else:
        log.append("  AVISO: no pude medir el EditRef; queda el rango del template")

    # 6. reconstruir texto: sin borrados, con clones insertados tras el trio
    # de fDenoised (las posiciones visuales ya estan recalculadas)
    delete_set = set(to_delete)
    insert_after = trio_indices(chunks, reads["fDenoised"])[-1]
    out_lines = []
    for i, chunk in enumerate(chunks):
        if i not in delete_set:
            out_lines.extend(chunk)
        if i == insert_after:
            for col in columns:
                if col["key"] in clones:
                    for cloned_chunk in clones[col["key"]]:
                        out_lines.extend(cloned_chunk)
    text = "\n".join(out_lines)

    # 7. reemplazo global del shot de origen (EditRef, publish, review, mxf)
    # y de su carpeta de secuencia si difiere. Si el shot destino ES el de
    # origen del template, no hay nada que reemplazar ni que controlar.
    same_shot = shot_name.lower() == source_shot.lower()
    if same_shot:
        log.append("  El shot destino es el de origen del template: sin reemplazos")
    else:
        replaced = text.count(source_shot)
        text = text.replace(source_shot, shot_name)
        log.append("  Reemplazos %s -> %s: %d" % (source_shot, shot_name, replaced))
        if source_seq and source_seq != seq_folder:
            text = re.sub(
                r"(?i)([/\\])%s([/\\])%s" % (re.escape(source_seq), re.escape(shot_name)),
                lambda m: "%s%s%s%s" % (m.group(1), seq_folder, m.group(2), shot_name),
                text,
            )

    # 7b. re-quoting: el reemplazo global puede dejar rutas con espacios sin
    # comillas (EditRef, comp_v000, review) si la secuencia/shot los tiene
    fixed_lines = []
    requoted = 0
    for line in text.split("\n"):
        m = re.match(r"^(\s+)file ([^\"].* .*)$", line)
        if m and "addUserKnob" not in line:
            line = '%sfile "%s"' % (m.group(1), m.group(2))
            requoted += 1
        fixed_lines.append(line)
    if requoted:
        text = "\n".join(fixed_lines)
        log.append("  Re-quoteadas %d rutas con espacios" % requoted)

    # 8. controles finales: nada sin resolver, nada del shot de origen
    leftover_placeholder = text.count("PLACEHOLDER")
    if leftover_placeholder:
        raise CreateNKError("Quedaron %d PLACEHOLDER sin resolver" % leftover_placeholder)
    if not same_shot and re.search(re.escape(source_shot), text, re.IGNORECASE):
        raise CreateNKError("Quedaron menciones al shot de origen del template")

    return text


def write_script(template_path, text, out_path):
    """Escribe el .nk preservando los EOLs del template. Nunca pisa."""
    if os.path.exists(out_path):
        raise CreateNKError("Ya existe %s" % out_path)
    out_dir = os.path.dirname(out_path)
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def load_template(template_path):
    """(texto normalizado a LF, usa_crlf). El .nk de Nuke sale en LF."""
    with open(template_path, "r", encoding="utf-8", newline="") as fh:
        raw = fh.read()
    crlf = raw.count("\r\n")
    lf = raw.count("\n") - crlf
    return raw.replace("\r\n", "\n"), crlf > lf


def find_templates(project_root):
    """Los .nk en la raiz de <proyecto>/ASSETS (sin subcarpetas)."""
    assets = os.path.join(project_root, ASSETS_DIR_NAME)
    if not os.path.isdir(assets):
        return []
    return [
        os.path.join(assets, f)
        for f in sorted(os.listdir(assets))
        if f.lower().endswith(".nk")
    ]


def v000_output(shot_root, shot_name):
    """<shot>/Comp/1_projects/<shot>_comp_v000.nk — la herramienta crea
    siempre la v000 del comp; si ya existe, write_script rechaza pisarla."""
    return os.path.join(
        shot_root, *PROJECTS_SUBPATH, "%s_comp_v000.nk" % shot_name
    )


# ============================
# Integracion con Hiero
# ============================


def get_media_path(track_item):
    try:
        return track_item.source().mediaSource().firstpath()
    except Exception as e:
        debug_print("  [WARN] No se pudo leer la media del clip:", e)
        return None


def _find_subdir(parent_dir, wanted_name):
    """Subcarpeta por nombre sin distinguir mayusculas (macOS distingue)."""
    if not parent_dir or not os.path.isdir(parent_dir):
        return None
    wanted = wanted_name.lower()
    try:
        for entry in os.scandir(parent_dir):
            if entry.is_dir() and entry.name.lower() == wanted:
                return entry.path
    except OSError:
        pass
    return None


def resolve_shot_dir(media_path):
    """Carpeta del shot a partir de la ruta de la media (mismo criterio que
    Apply AMF: helper central de naming y fallback estructural por _input)."""
    if not media_path:
        return None
    normalized = re.sub(r"[\\/]+", "/", str(media_path))
    try:
        from LGA_NKS_Shared.LGA_NKS_Flow_NamingUtils import (
            extract_shot_code_from_path,
            extract_project_name_from_path,
        )
    except ImportError:
        extract_shot_code_from_path = None
        extract_project_name_from_path = None
    if extract_shot_code_from_path:
        project_name = (
            extract_project_name_from_path(normalized)
            if extract_project_name_from_path
            else None
        )
        shot_code = extract_shot_code_from_path(normalized, project_name)
        if shot_code:
            segments = normalized.split("/")
            for index in range(len(segments) - 1, -1, -1):
                if segments[index] == shot_code:
                    return "/".join(segments[: index + 1])
    current = os.path.dirname(normalized)
    while current and current != os.path.dirname(current):
        if _find_subdir(current, INPUT_DIR_NAME):
            return re.sub(r"[\\/]+", "/", current)
        current = os.path.dirname(current)
    return None


def get_selected_track_item():
    """El TrackItem seleccionado en el timeline (el primero, sin efectos)."""
    seq = hiero.ui.activeSequence()
    if not seq:
        raise CreateNKError("No hay secuencia activa.")
    te = hiero.ui.getTimelineEditor(seq)
    selection = (te.selection() or []) if te else []
    items = [
        item
        for item in selection
        if isinstance(item, hiero.core.TrackItem)
        and not isinstance(item, hiero.core.EffectTrackItem)
    ]
    if not items:
        raise CreateNKError("No hay ningun clip seleccionado en el timeline.")
    return seq, items[0]


def timeline_plate_counts(seq, selected_item):
    """dict token_de_plate (lower) -> frames que ocupa en el timeline, para
    los tracks *Plate con clip solapado al seleccionado. La duracion del
    timeline manda sobre la de disco: refleja retimes y trims editoriales."""
    counts = {}
    try:
        sel_in = int(selected_item.timelineIn())
        sel_out = int(selected_item.timelineOut())
        for track in seq.videoTracks():
            m = re.search(r"([A-Za-z]{1,4}Plate[0-9]*)\s*$", track.name(), re.IGNORECASE)
            if not m:
                continue
            for item in track:
                if not isinstance(item, hiero.core.TrackItem):
                    continue
                if int(item.timelineOut()) < sel_in or int(item.timelineIn()) > sel_out:
                    continue
                counts[m.group(1).lower()] = (
                    int(item.timelineOut()) - int(item.timelineIn()) + 1
                )
                break
    except Exception as e:
        debug_print("  [WARN] No se pudieron leer los plates del timeline:", e)
    return counts


def timeline_editref_offset(seq, selected_item):
    """Offset (en frames) del EditRef leido del timeline. El ancla es el
    clip del track aPlate solapado con el seleccionado (el rango del
    proyecto esta anclado al aPlate); si no hay track aPlate, se usa el
    clip seleccionado. Devuelve None si no hay EditRef solapado."""
    try:
        sel_in = int(selected_item.timelineIn())
        sel_out = int(selected_item.timelineOut())

        def overlapping_clip(track_regex):
            for track in seq.videoTracks():
                if not re.search(track_regex, track.name(), re.IGNORECASE):
                    continue
                for item in track:
                    if not isinstance(item, hiero.core.TrackItem):
                        continue
                    if int(item.timelineOut()) < sel_in or int(item.timelineIn()) > sel_out:
                        continue
                    return item
            return None

        anchor = overlapping_clip(r"aplate") or selected_item
        editref = overlapping_clip(r"editref")
        if editref is not None:
            return int(editref.timelineIn()) - int(anchor.timelineIn())
    except Exception as e:
        debug_print("  [WARN] No se pudo leer el offset del EditRef:", e)
    return None


# ============================
# UI
# ============================


def _get_hiero_main_window():
    """Parent para dialogos, SOLO en PySide6 (en PySide2 el wrapper SIP de
    hiero.ui.mainWindow() no es compatible como parent)."""
    from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, PYSIDE_VER

    if PYSIDE_VER < 6:
        return None
    try:
        mw = hiero.ui.mainWindow()
        if mw is not None:
            return mw
    except Exception:
        pass
    try:
        app = QtWidgets.QApplication.instance()
        if app is not None and hasattr(app, "activeWindow"):
            return app.activeWindow()
    except Exception:
        pass
    return None


def prompt_template_selection(template_paths):
    """Dialogo con un boton por template (estilo del pack). Devuelve la ruta
    elegida o None. Con un solo template lo devuelve sin UI."""
    if not template_paths:
        return None
    if len(template_paths) == 1:
        return template_paths[0]

    from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtCore
    from LGA_NKS_Shared.LGA_UI_Style_HieroTools import Style, Metric, apply_ui_font

    if QtWidgets.QApplication.instance() is None:
        return None

    parent = _get_hiero_main_window()
    dialog = QtWidgets.QDialog(parent) if parent is not None else QtWidgets.QDialog()
    dialog.setWindowTitle("Create NK v000")
    dialog.setModal(True)
    dialog.setMinimumWidth(340)
    # Hoja de form del modulo: fondo, textos, separadores y campos salen de ahi.
    dialog.setStyleSheet(Style.FORM)
    chosen = {"path": None}

    layout = QtWidgets.QVBoxLayout(dialog)
    layout.setSpacing(8)
    layout.setContentsMargins(*([Metric.WINDOW_MARGIN] * 4))

    label = QtWidgets.QLabel("Select template")
    label.setAlignment(QtCore.Qt.AlignCenter)
    # El titulo lo pinta la regla QLabel[lgaTitle] de Style.FORM.
    label.setProperty("lgaTitle", True)
    layout.addWidget(label)

    sep = QtWidgets.QFrame()
    # Sin hoja propia: Style.FORM ya trae la regla de QFrame HLine/VLine.
    sep.setFrameShape(QtWidgets.QFrame.HLine)
    sep.setFrameShadow(QtWidgets.QFrame.Plain)
    sep.setFixedHeight(1)
    layout.addWidget(sep)

    def make_handler(path):
        def handler():
            chosen["path"] = path
            dialog.accept()
        return handler

    for path in template_paths:
        # Cada template es una opcion equivalente: ninguna es la recomendada,
        # asi que van todas en secundario y no hay boton violeta.
        btn = QtWidgets.QPushButton(os.path.basename(path))
        btn.setMinimumHeight(32)
        btn.setStyleSheet(Style.BTN_SECONDARY)
        btn.clicked.connect(make_handler(path))
        layout.addWidget(btn)

    apply_ui_font(dialog)
    dialog.exec_()
    return chosen["path"]


class RangeDialog(object):
    """Ventana de confirmacion: rango del proyecto (radio por fuente) y
    handle para la opcion EditRef. Devuelve (first, last) o None."""

    def __init__(
        self,
        shot_name,
        columns,
        editref_frames,
        out_path,
        publish_v000=None,
        timeline_counts=None,
    ):
        from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtCore
        from LGA_NKS_Shared.LGA_UI_Style_HieroTools import (
            Style,
            Color,
            Metric,
            colorize_path,
            apply_ui_font,
            semibold_css,
        )

        self.QtWidgets = QtWidgets
        self.result = None

        parent = _get_hiero_main_window()
        dialog = QtWidgets.QDialog(parent) if parent is not None else QtWidgets.QDialog()
        self.dialog = dialog
        dialog.setWindowTitle("Create NK v000")
        dialog.setModal(True)
        dialog.setMinimumWidth(430)
        # Hoja de form del modulo. El QSpinBox del handle queda NATIVO a
        # proposito: Style.FORM le saca de encima la regla de QLineEdit y deja
        # que Qt siga dibujando las flechitas (ver el comentario del modulo).
        dialog.setStyleSheet(Style.FORM)

        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setSpacing(8)
        layout.setContentsMargins(*([Metric.WINDOW_MARGIN] * 4))

        title = QtWidgets.QLabel("%s" % shot_name)
        title.setAlignment(QtCore.Qt.AlignCenter)
        # El titulo lo pinta la regla QLabel[lgaTitle] de Style.FORM.
        title.setProperty("lgaTitle", True)
        layout.addWidget(title)

        dest = QtWidgets.QLabel("Saving to:<br>%s" % colorize_path(out_path.replace("\\", "/")))
        dest.setTextFormat(QtCore.Qt.RichText)
        dest.setWordWrap(True)
        layout.addWidget(dest)

        sep = QtWidgets.QFrame()
        # Sin hoja propia: Style.FORM ya trae la regla de QFrame HLine/VLine.
        sep.setFrameShape(QtWidgets.QFrame.HLine)
        sep.setFrameShadow(QtWidgets.QFrame.Plain)
        sep.setFixedHeight(1)
        layout.addWidget(sep)

        range_label = QtWidgets.QLabel("Project frame range:")
        layout.addWidget(range_label)

        # El modulo no trae Style.RADIO y la regla QWidget{background} de
        # Style.FORM deja el indicador nativo ilegible: se dibuja aca con los
        # tokens del checkbox del pack, igual que en Create v000.
        radio_style = """
QRadioButton { color: %(text)s; padding: 2px; background: transparent; }
QRadioButton::indicator {
    width: 14px;
    height: 14px;
    border-radius: 8px;
    background-color: %(off)s;
    border: 1px solid %(border)s;
}
QRadioButton::indicator:unchecked:hover { background-color: %(off_hover)s; }
QRadioButton::indicator:checked {
    width: 8px;
    height: 8px;
    border: 4px solid %(off)s;
    background-color: %(accent)s;
}
QRadioButton:disabled { color: %(dim)s; }
QRadioButton::indicator:disabled {
    background-color: %(surface)s;
    border-color: %(border_dis)s;
}
""" % {
            "text": Color.TEXT,
            "off": Color.CHECKBOX_OFF,
            "off_hover": Color.CHECKBOX_OFF_HOVER,
            "border": Color.CHECKBOX_BORDER,
            "accent": Color.ACCENT_HOVER,
            "dim": Color.TEXT_DIM,
            "surface": Color.SURFACE,
            "border_dis": Color.BORDER_STRONG,
        }

        self.radio_group = QtWidgets.QButtonGroup(dialog)
        self.options = []  # (radio, cantidad de frames)
        timeline_counts = timeline_counts or {}

        def add_option(label, count, checked=False):
            radio = QtWidgets.QRadioButton(label)
            radio.setStyleSheet(radio_style)
            radio.setChecked(checked)
            self.radio_group.addButton(radio)
            layout.addWidget(radio)
            self.options.append((radio, count))
            return radio

        # el publish comp_v000 (Create EXR v000) es la fuente default si
        # existe: su rango ya fue validado al crear la secuencia negra
        has_publish = publish_v000 is not None
        if has_publish:
            count = publish_v000["last"] - publish_v000["first"] + 1
            add_option("comp_v000 publish  (%d frames)" % count, count, True)

        plate_cols = [c for c in columns if c["kind"] == "plate"]
        for index, col in enumerate(plate_cols):
            info = col["info"]
            disk_count = info["last"] - info["first"] + 1
            tl_count = timeline_counts.get(col["key"].lower())
            if tl_count and tl_count != disk_count:
                # la duracion del timeline manda: refleja retimes y trims
                label = "%s  (%d frames in timeline, %d on disk)" % (
                    col["key"], tl_count, disk_count,
                )
                count = tl_count
            else:
                label = "%s  (%d frames)" % (col["key"], disk_count)
                count = disk_count
            add_option(label, count, checked=(not has_publish and index == 0))

        # opcion EditRef + handle (solo si se pudo medir el mov)
        self.editref_radio = None
        self.handle_spin = None
        self.editref_frames = editref_frames
        if editref_frames:
            row = QtWidgets.QHBoxLayout()
            radio = QtWidgets.QRadioButton(
                "EditRef (%d frames) + handle" % editref_frames
            )
            radio.setStyleSheet(radio_style)
            self.radio_group.addButton(radio)
            self.editref_radio = radio
            spin = QtWidgets.QSpinBox()
            spin.setRange(0, 99)
            spin.setValue(DEFAULT_HANDLE)
            self.handle_spin = spin
            row.addWidget(radio)
            row.addWidget(spin)
            row.addStretch(1)
            layout.addLayout(row)

        # rango resultante en vivo (los .nk arrancan siempre en 1001)
        self.range_label = QtWidgets.QLabel("")
        # El tamanio lo da la hoja; aca solo el peso 600 (que necesita nombrar
        # la familia, ver semibold_css) y el color de lo destacado.
        self.range_label.setStyleSheet(
            "color: %s; padding-top: 4px; %s" % (Color.TEXT_STRONG, semibold_css())
        )
        layout.addWidget(self.range_label)
        for radio, _count in self.options:
            radio.toggled.connect(self._update_range_label)
        if self.editref_radio is not None:
            self.editref_radio.toggled.connect(self._update_range_label)
            self.handle_spin.valueChanged.connect(self._update_range_label)
        self._update_range_label()

        layout.addSpacing(4)
        buttons = QtWidgets.QHBoxLayout()
        buttons.addStretch(1)
        # Create es la accion: unico violeta y ultimo a la derecha.
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setStyleSheet(Style.BTN_SECONDARY)
        create_btn = QtWidgets.QPushButton("Create")
        create_btn.setStyleSheet(Style.BTN_PRIMARY)
        for btn in (cancel_btn, create_btn):
            btn.setMinimumHeight(28)
            btn.setMinimumWidth(90)
        cancel_btn.clicked.connect(dialog.reject)
        create_btn.clicked.connect(self._accept)
        buttons.addWidget(cancel_btn)
        buttons.addSpacing(8)
        buttons.addWidget(create_btn)
        layout.addLayout(buttons)

        apply_ui_font(dialog)

    def _selected_count(self):
        """Cantidad de frames del proyecto segun la opcion elegida."""
        if self.editref_radio is not None and self.editref_radio.isChecked():
            return self.editref_frames + 2 * self.handle_spin.value()
        for radio, count in self.options:
            if radio.isChecked():
                return count
        return None

    def _update_range_label(self, *_args):
        count = self._selected_count()
        if count:
            self.range_label.setText(
                "Project range: %d-%d  (%d frames)"
                % (START_FRAME, START_FRAME + count - 1, count)
            )
        else:
            self.range_label.setText("")

    def _accept(self):
        count = self._selected_count()
        if count:
            self.result = (START_FRAME, START_FRAME + count - 1)
        self.dialog.accept()

    def exec_(self):
        self.dialog.exec_()
        return self.result


# ============================
# Flujo principal
# ============================

# El IO (escaneo del shot en red, ffprobe, lectura del template y escritura
# del .nk) corre en QThreads; las ventanas se abren siempre en el hilo
# principal a traves de las senales de los workers. El controller vive en
# una referencia de modulo para que Qt no lo recolecte a mitad de flujo.
_controller = None


def _make_controller():
    """Construye el controller. Es un QObject del hilo principal a proposito:
    si el receptor de una senal fuera un objeto comun, el slot correria en el
    hilo del worker y las ventanas se abririan fuera del main thread."""
    from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore

    class ScanWorker(QtCore.QThread):
        done = QtCore.Signal(object)
        failed = QtCore.Signal(str)

        def __init__(self, shot_root, shot_name):
            QtCore.QThread.__init__(self)
            self.shot_root = shot_root
            self.shot_name = shot_name

        def run(self):
            try:
                columns, unknown = scan_shot(self.shot_root)
                editref_mov = find_editref(self.shot_root)
                frames = probe_mov_frames(editref_mov) if editref_mov else None
                publish = publish_v000_info(self.shot_root, self.shot_name)
                self.done.emit(
                    {
                        "columns": columns,
                        "unknown": unknown,
                        "editref_frames": frames,
                        "publish_v000": publish,
                    }
                )
            except Exception as error:
                write_log_file("ERROR en el escaneo del shot: %s" % error)
                self.failed.emit(str(error))

    class BuildWorker(QtCore.QThread):
        done = QtCore.Signal(str)
        failed = QtCore.Signal(str)

        def __init__(self, params):
            QtCore.QThread.__init__(self)
            self.params = params

        def run(self):
            log = []
            try:
                p = self.params
                template_text, _uses_crlf = load_template(p["template_path"])
                text = build_script(
                    template_text,
                    os.path.basename(p["template_path"]),
                    p["shot_root"],
                    p["out_path"],
                    log,
                    columns=p["columns"],
                    unknown=p["unknown"],
                    project_first=p["range_first"],
                    project_last=p["range_last"],
                    editref_frames=p["editref_frames"],
                    editref_start=p["editref_start"],
                )
                write_script(p["template_path"], text, p["out_path"])
                for line in log:
                    debug_print(line)
                write_log_file("OK: escrito %s" % p["out_path"], log)
                self.done.emit(p["out_path"])
            except Exception as error:
                write_log_file("ERROR: %s" % error, log)
                self.failed.emit(str(error))

    class Controller(QtCore.QObject):
        """Encadena scan -> dialogo de rango -> build/write -> cartel final."""

        def __init__(self):
            QtCore.QObject.__init__(self)
            self.scan_worker = None
            self.build_worker = None
            self.shot_root = None
            self.shot_name = None
            self.template_path = None
            self.editref_offset = None
            self.scan_data = None

        def start(self):
            seq, item = get_selected_track_item()
            media_path = get_media_path(item)
            shot_root = resolve_shot_dir(media_path)
            if not shot_root:
                raise CreateNKError(
                    "No pude resolver la carpeta del shot desde el clip seleccionado."
                )
            self.shot_root = shot_root.rstrip("/")
            self.shot_name = os.path.basename(self.shot_root)

            # raiz del proyecto: <raiz>/<seq>/<shot>
            project_root = os.path.dirname(os.path.dirname(self.shot_root))
            templates = find_templates(project_root)
            if not templates:
                raise CreateNKError(
                    "No hay templates .nk en %s"
                    % os.path.join(project_root, ASSETS_DIR_NAME).replace("\\", "/")
                )
            self.template_path = prompt_template_selection(templates)
            if not self.template_path:
                return  # cancelado por el usuario

            # lo que sale del timeline se lee ANTES de ir a los hilos
            self.editref_offset = timeline_editref_offset(seq, item)
            self.timeline_counts = timeline_plate_counts(seq, item)

            self.scan_worker = ScanWorker(self.shot_root, self.shot_name)
            self.scan_worker.done.connect(self._on_scan_done)
            self.scan_worker.failed.connect(self._on_failed)
            self.scan_worker.start()

        def _on_scan_done(self, data):
            from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning

            self.scan_data = data
            columns = data["columns"]
            if not any(c["key"] == "aPlate" for c in columns):
                show_warning(
                    _get_hiero_main_window(),
                    "Create NK v000",
                    "El shot no tiene aPlate en %s" % INPUT_DIR_NAME,
                )
                return

            out_path = v000_output(self.shot_root, self.shot_name)
            if os.path.exists(out_path):
                show_warning(
                    _get_hiero_main_window(),
                    "Create NK v000",
                    "Ya existe el script v000 del shot:\n%s\n\nNo se pisa nada."
                    % out_path.replace("\\", "/"),
                )
                return
            dialog = RangeDialog(
                self.shot_name,
                columns,
                data["editref_frames"],
                out_path,
                publish_v000=data.get("publish_v000"),
                timeline_counts=getattr(self, "timeline_counts", None),
            )
            rng = dialog.exec_()
            if rng is None:
                return  # cancelado
            range_first, range_last = rng

            editref_start = None
            if self.editref_offset is not None and data["editref_frames"]:
                editref_start = range_first + self.editref_offset
                editref_end = editref_start + data["editref_frames"] - 1
                if editref_start < range_first or editref_end > range_last:
                    # el offset del timeline cae fuera del rango elegido:
                    # mejor centrar y avisar que escribir un .nk corrido
                    data["unknown"].append(
                        "offset del EditRef en el timeline (%+d) fuera del rango %d-%d; se centro"
                        % (self.editref_offset, range_first, range_last)
                    )
                    editref_start = None

            self.build_worker = BuildWorker(
                {
                    "template_path": self.template_path,
                    "shot_root": self.shot_root,
                    "out_path": out_path,
                    "columns": columns,
                    "unknown": data["unknown"],
                    "range_first": range_first,
                    "range_last": range_last,
                    "editref_frames": data["editref_frames"],
                    "editref_start": editref_start,
                }
            )
            self.build_worker.done.connect(self._on_build_done)
            self.build_worker.failed.connect(self._on_failed)
            self.build_worker.start()

        def _on_build_done(self, out_path):
            from LGA_NKS_Shared.LGA_NKS_MessageBox import show_info

            message = "Script creado:\n%s" % out_path.replace("\\", "/")
            warnings = (self.scan_data or {}).get("unknown") or []
            if warnings:
                message += "\n\nAvisos:\n- " + "\n- ".join(warnings)
            show_info(_get_hiero_main_window(), "Create NK v000", message)

        def _on_failed(self, message):
            from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning

            show_warning(_get_hiero_main_window(), "Create NK v000", message)

    return Controller()


def main():
    """Punto de entrada desde el Edit Panel."""
    global _controller
    from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning, show_error

    try:
        if not HIERO_AVAILABLE:
            raise CreateNKError("Este script corre dentro de Hiero/Nuke Studio.")
        _controller = _make_controller()
        _controller.start()
        return True
    except CreateNKError as e:
        write_log_file("ERROR: %s" % e)
        try:
            show_warning(_get_hiero_main_window(), "Create NK v000", str(e))
        except Exception:
            print("[Create NK Script] %s" % e)
        return False
    except Exception as e:
        import traceback

        traceback.print_exc()
        write_log_file("ERROR inesperado: %s" % e)
        try:
            show_error(
                _get_hiero_main_window(), "Create NK v000", "Error inesperado:\n%s" % e
            )
        except Exception:
            pass
        return False


if __name__ == "__main__":
    main()

