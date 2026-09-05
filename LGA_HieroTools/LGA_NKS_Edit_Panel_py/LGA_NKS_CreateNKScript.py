"""
____________________________________________________________________

  LGA_NKS_CreateNKScript v1.12 | Lega

  Crea el script de comp de Nuke de un shot a partir del template .nk
  del proyecto (<raiz>/ASSETS/*.nk), editandolo como texto plano:
  reemplaza los Reads de plates/denoised por las rutas reales del shot
  (version mas alta con EXR), borra los trios Read+Anchor+Stamp de los
  plates que no existen, clona trios para plates extra, apunta los
  OCIO (CDL/CLF) a los Look_Files del shot, centra el EditRef y ajusta
  el frame range del proyecto. El resultado se escribe en
  <shot>/Comp/1_projects/<shot>_comp_v000.nk (si existe, pregunta antes de pisar).

  v1.12: Una sola confirmacion para todos los denoised faltantes de los
         plates del shot; permite conservar sus rutas originales del template.
         El cartel destaca los denoised faltantes y las rutas que se conservan.
  v1.11: El TimeClip del EditRef vuelve a llevar el rango REAL del clip
         (1 - N frames del mov, el mismo que el Read) y se posiciona en el
         timeline con frame_mode "start at". Llevaba el rango ya corrido Y
         el "start at": el corrimiento se aplicaba dos veces y el TimeClip
         le pedia al Read frames que el Read no tiene.
  v1.10: Un nodo de color SIN knob file tambien es del look. Nuke no
         escribe el knob que quedo en su default, asi que un template
         donde se borraron las expresiones TCL deja tres de los cuatro
         nodos sin file, y quedaban intactos.
  v1.09: El log dice que hizo con CADA nodo de color: cual es, si estaba
         suelto o adentro de un grupo, y si se reemplazo o quedo intacto
         y por que. Antes no registraba nada y no habia forma de
         diagnosticar el reporte de un usuario. Ademas el criterio ya no
         depende solo de que el path diga Look_Files -tambien entra la
         expresion TCL que resuelve desde root.name- y los nodos que
         quedan intactos se avisan.
  v1.08: ffprobe sale del pack y no del PATH del sistema. Se llamaba por
         nombre pelado, asi que en una maquina sin ffprobe instalado la
         duracion del EditRef no se podia medir en NINGUN shot y el rango
         de review quedaba el del template. El aviso ahora distingue si
         falta ffprobe.
  v1.07: El boton del cartel final abre la carpeta con el explorador POR
         DEFAULT del sistema, sin nombrar explorer.exe. El TimeClip del
         EditRef recibe first/last del rango ya colocado (1001 + handle),
         no la duracion cruda del mov. Y todo lo que puede salir mal
         -sin CDL, sin LUT, sin AMF, sin publish v000, EditRef no medible,
         plates sin frames- se junta y se muestra en el cartel final.
  v1.06: Si el v000 ya existe se pregunta si sobreescribir en vez de
         abortar; el .nk que estaba se conserva como .nk~ y el boton de
         la ventana de rango pasa a decir Overwrite.
  v1.05: Las ventanas dejan de bloquear Hiero (no-modales, como Create
         EXR v000). La caja del handle se agranda y muestra al lado el
         total que da la cuenta. El cartel final trae la ruta coloreada y
         un boton para abrirla en el explorador. En el script generado:
         se borra el StickyNote SCRIPT BASE_v del template y ya no se
         arrastran los stamps de aPlate/aDenoised que viven fuera de la
         columna de input.
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
import shutil
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

# aPlate es obligatorio. aDenoised conserva su trio si se acepta continuar.
NEVER_DELETE = {"aPlate"}

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
# Primer frame del clip del EditRef tal como lo entrega el Read del .mov.
# Es el rango REAL del clip, no su lugar en el timeline: eso lo resuelve el
# frame_mode "start at" del TimeClip.
EDITREF_CLIP_FIRST = 1

# Tamanio de la caja del handle en la ventana de rango. Se ajusta A MANO
# desde aca: el spinbox va NATIVO a proposito (Style.FORM no lo pinta, ver
# su comentario), asi que lo unico que agranda las flechitas es la
# geometria del widget.
HANDLE_SPIN_WIDTH = 78
HANDLE_SPIN_HEIGHT = 28

# Nombre de shot tipo PROJ_1234_5678_VND (vendor al final)
SHOT_NAME_RE = re.compile(r"^[A-Za-z0-9]+_\d{3,4}_\d{3,4}_[A-Za-z0-9]{2,4}$")
SHOT_TOKEN_RE = re.compile(r"[A-Za-z0-9]+_\d{3,4}_\d{3,4}_[A-Za-z0-9]{2,4}")

PLATE_FOLDER_RE = re.compile(r"_([A-Za-z][A-Za-z0-9]*?Plate[0-9]*)_v\d+", re.IGNORECASE)


class CreateNKError(Exception):
    """Error esperado del flujo, para mostrar en un dialogo."""


# ============================
# Escaneo del shot
# ============================


def _warn(log, warnings, message):
    """Aviso que el usuario TIENE que ver: va al log Y al cartel final.

    El texto va en ingles porque termina a la vista en el cartel; el log
    lo envuelve con su propia marca.
    """
    log.append("  AVISO: %s" % message)
    if message not in warnings:
        warnings.append(message)


def find_amf(shot_root):
    """(ruta con extension .amf o None, ruta con sufijo _amf o None).

    Se devuelven por separado a proposito: Apply AMF busca por extension
    (.amf) y NO reconoce la forma vieja con sufijo, asi que un shot que solo
    tenga _amf hay que avisarlo distinto a uno que no tenga ninguno.
    """
    look_dir = os.path.join(shot_root, INPUT_DIR_NAME, LOOK_DIR_NAME)
    con_extension = None
    con_sufijo = None
    if os.path.isdir(look_dir):
        for entry in sorted(os.listdir(look_dir)):
            low = entry.lower()
            ruta = os.path.join(look_dir, entry).replace("\\", "/")
            if low.endswith(".amf") and con_extension is None:
                con_extension = ruta
            elif low.endswith("_amf") and con_sufijo is None:
                con_sufijo = ruta
    return con_extension, con_sufijo


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
                    "%s: newest version has no EXR frames (%s), using %s"
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


def missing_denoised_keys(columns):
    """Slots denoised del template que corresponden a plates reales sin render."""
    present = {col["key"] for col in columns}
    return [letter + "Denoised" for letter in KNOWN_LETTERS
            if letter + "Plate" in present and letter + "Denoised" not in present]


def confirm_missing_denoised(parent, missing):
    """Una unica decision para conservar todos los Reads denoised faltantes."""
    from LGA_NKS_Shared.LGA_NKS_MessageBox import ask_question
    from LGA_NKS_Shared.LGA_UI_Style_HieroTools import emphasis

    return ask_question(
        parent, "Create NK v000",
        "%s<br>No EXR sequence was found for:<br>%s<br><br>"
        "Create the script keeping the %s<br>"
        "in these denoised Reads?"
        % (emphasis("Missing denoised"),
           "<br>".join(emphasis(key) for key in missing),
           emphasis("original template paths")),
        yes_text="Continue", no_text="Cancel",
    )


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
            unknown.append("%s: folder has no EXR frames" % token_to_key(token))
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
            unknown.append("%s: folder has no EXR frames" % token_to_key(token))
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
                unknown.append(
                    "Orphan denoised render with no plate in %s: %s"
                    % (INPUT_DIR_NAME, entry)
                )
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


def ffprobe_path():
    """Ruta del ffprobe a usar, o None si no hay ninguno.

    Primero el que VIAJA EN EL PACK, con ruta armada desde __file__: es
    el unico que existe seguro en la maquina de un artista. Confiar en el
    PATH del sistema era el bug -en la maquina de quien escribio la tool
    ffprobe estaba instalado aparte, en la de los demas no, y el EditRef
    no se podia medir en NINGUN shot-. El del PATH queda solo de
    respaldo, para macOS, donde el pack todavia no trae binarios.
    """
    shared = Path(__file__).parent.parent / "LGA_NKS_Shared"
    if os.name == "nt":
        del_pack = shared / "FFmpeg_Win" / "bin" / "ffprobe.exe"
    else:
        del_pack = shared / "FFmpeg_Mac" / "bin" / "ffprobe"
    if del_pack.is_file():
        return str(del_pack)
    return shutil.which("ffprobe")


def probe_mov_frames(mov_path):
    """Cantidad de frames de un mov via ffprobe, o None si no se pudo."""
    binario = ffprobe_path()
    if not binario:
        return None
    # CREATE_NO_WINDOW: sin esto Windows abre una consola negra por cada
    # llamada, igual que en Import Shot.
    extra = {}
    if os.name == "nt":
        extra["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        out = subprocess.run(
            [
                binario, "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=nb_frames",
                "-of", "default=nw=1:nk=1", mov_path,
            ],
            capture_output=True, text=True, timeout=60, **extra
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


def set_or_add_chunk_knob(chunk, knob, value):
    """Setea el knob y, si el nodo no lo trae, lo agrega.

    Nuke omite al guardar los knobs que estan en su valor default, asi
    que un TimeClip sin 'first' es lo normal: hay que insertarlo.
    """
    if set_chunk_knob(chunk, knob, value):
        return True
    pat = _knob_re("name")
    for index, line in enumerate(chunk):
        match = pat.match(line)
        if match:
            chunk.insert(index, "%s%s %s" % (match.group(1), knob, value))
            return True
    return False


def grupo_de_cada_chunk(chunks):
    """Lista paralela a chunks con el nombre del Group que contiene a cada
    uno, o None si esta en el nivel de arriba.

    Los Group se anidan (DasGrain trae otro adentro), asi que se rastrea
    con una pila. Sirve para que el log diga si un nodo estaba suelto o
    adentro de un grupo, que es justo lo que no se podia saber cuando un
    usuario reporto que los OCIO del grupo no se le reemplazaban.
    """
    pila = []
    resultado = []
    for chunk in chunks:
        primera = chunk[0].strip() if chunk else ""
        if primera.startswith("end_group"):
            resultado.append(pila[-1] if pila else None)
            if pila:
                pila.pop()
            continue
        resultado.append(pila[-1] if pila else None)
        if chunk_class(chunk) == "Group":
            pila.append(chunk_knob(chunk, "name") or "?")
    return resultado


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
    """Mueve la columna del trio a la x nueva.

    Solo se mueven los nodos que estaban en la MISMA x que el Read: el
    Stamp adyacente de aPlate y aDenoised no vive en la columna de input
    sino en otra zona del graph (junto al CopyMetaData y adentro del
    backdrop Regrain), y arrastrarlo ahi descolocaba el comp.
    """
    origin = chunk_knob(chunks_of_trio[0], "xpos")
    for chunk in chunks_of_trio:
        if chunk_knob(chunk, "xpos") == origin:
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
    warnings=None,
    keep_missing_denoised=False,
):
    """Genera el texto del .nk nuevo a partir del template.

    columns/unknown pueden venir de un scan_shot() previo (para no re-escanear).
    project_first/last: rango del proyecto (default: rango del aPlate).
    editref_frames: duracion del EditRef en frames (default: ffprobe).
    editref_start: frame de inicio del EditRef (default: centrado)."""
    warnings = warnings if warnings is not None else []
    shot_root = shot_root.rstrip("\\/")
    shot_name = os.path.basename(shot_root)
    if not SHOT_NAME_RE.match(shot_name):
        raise CreateNKError("El nombre del shot no es reconocible: %s" % shot_name)
    seq_folder = os.path.basename(os.path.dirname(shot_root))
    source_shot, source_seq = detect_source_shot(template_text, template_name)
    log.append("Shot: %s (seq %s) | origen del template: %s" % (shot_name, seq_folder, source_shot))
    log.append("  ffprobe: %s" % (ffprobe_path() or "NO ENCONTRADO"))

    if columns is None:
        columns, unknown = scan_shot(shot_root)
    unknown = unknown or []
    missing_denoised = missing_denoised_keys(columns)
    if missing_denoised and not keep_missing_denoised:
        raise CreateNKError(
            "Missing denoised renders require confirmation: %s"
            % ", ".join(missing_denoised)
        )
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
    preserved_files = {}
    for key in known_keys:
        keep_template = key in missing_denoised
        trio = trio_indices(
            chunks, reads[key], for_delete=key not in col_by_key and not keep_template
        )
        if key in col_by_key:
            fill_read(chunks[reads[key]], col_by_key[key]["info"])
            trios[key] = [chunks[i] for i in trio]
            log.append("  SET %s" % key)
        elif keep_template:
            trios[key] = [chunks[i] for i in trio]
            log.append("  CONSERVAR %s: ruta original del template" % key)
            warnings.append("%s: kept the original template path (denoised missing)" % key)
        else:
            to_delete.extend(trio)
            log.append("  BORRAR %s" % key)

    orphans = check_anchor_orphans(chunks, set(to_delete))
    if orphans:
        raise CreateNKError("Referencias a anchors borrados: %s" % orphans)

    # 1b. El StickyNote que versiona el template (SCRIPT BASE_vNNN) habla
    # del template, no del shot: no viaja al script nuevo.
    for index, chunk in enumerate(chunks):
        if chunk_class(chunk) != "StickyNote":
            continue
        if (normalized_label(chunk) or "").startswith("SCRIPT BASE_v"):
            to_delete.append(index)
            log.append("  BORRAR StickyNote de version del template")

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
    layout_columns = list(columns)
    for key in missing_denoised:
        plate_index = next(i for i, col in enumerate(layout_columns)
                           if col["key"] == key.replace("Denoised", "Plate"))
        layout_columns.insert(plate_index + 1, {"key": key, "token": key[0]})
    for col in layout_columns:
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

    # 4. OCIO CDL / LUT con rutas reales. Se toca todo nodo de color cuyo
    # file apunte a Look_Files O sea una expresion TCL que resuelve el look
    # desde root.name: las dos formas son 'el look del shot'. Un OCIO que
    # apunte a un archivo fijo puesto a mano NO se pisa.
    cdl, clf = resolve_look_files(shot_root)
    log.append("  CDL del shot: %s" % (cdl or "NINGUNO"))
    log.append("  CLF del shot: %s" % (clf or "NINGUNO"))
    grupos = grupo_de_cada_chunk(chunks)
    ocio_total = 0
    ocio_tocados = 0
    ocio_intactos = []
    for index, chunk in enumerate(chunks):
        cls = chunk_class(chunk)
        if cls not in ("OCIOCDLTransform", "OCIOFileTransform"):
            continue
        ocio_total += 1
        nombre = chunk_knob(chunk, "name") or "?"
        grupo = grupos[index] if index < len(grupos) else None
        donde = "en el grupo %s" % grupo if grupo else "suelto"
        current = chunk_knob(chunk, "file") or ""
        target = cdl if cls == "OCIOCDLTransform" else clf
        # Tres formas de que un nodo sea "del look del shot":
        #   - su path nombra Look_Files
        #   - es la expresion TCL que resuelve desde root.name
        #   - esta VACIO: Nuke no escribe el knob file cuando quedo en su
        #     default, y un CDL con read_from_file y sin archivo esta
        #     justamente esperando que se le ponga uno. El template v016
        #     dejo asi a tres de los cuatro nodos.
        # Un file que apunta a un archivo concreto FUERA de Look_Files no se
        # toca: eso lo puso alguien a mano y no es el look del shot.
        es_del_look = (
            not current.strip()
            or LOOK_DIR_NAME in current
            or ("root.name" in current and "glob" in current)
        )
        if not es_del_look:
            ocio_intactos.append(nombre)
            log.append(
                "  OCIO %s (%s): INTACTO, su file no apunta al look del shot -> %s"
                % (nombre, donde, current[:120])
            )
            continue
        if not target:
            # No se suma a ocio_intactos: la falta de CDL/CLF ya tiene su
            # propio aviso y repetirla por nodo seria ruido.
            log.append(
                "  OCIO %s (%s): INTACTO, no hay archivo de look en el shot"
                % (nombre, donde)
            )
            continue
        if current.strip():
            set_chunk_knob(chunk, "file", quote_if_needed(target))
            motivo = ""
        else:
            # Sin knob file en el template: hay que agregarlo, no reemplazarlo.
            set_or_add_chunk_knob(chunk, "file", quote_if_needed(target))
            motivo = " [venia sin file]"
        ocio_tocados += 1
        log.append("  OCIO %s (%s)%s -> %s" % (nombre, donde, motivo, target))
    log.append("  OCIO: %d nodos, %d reemplazados" % (ocio_total, ocio_tocados))
    if ocio_intactos:
        # Solo llega aca el caso raro: HAY archivo de look pero el nodo no se
        # reconocio como del look. Es el sintoma que hay que poder ver.
        _warn(
            log, warnings,
            "%d color node(s) were not recognized as look nodes and kept the "
            "template path (%s): check their CDL/LUT by hand"
            % (len(ocio_intactos), ", ".join(ocio_intactos)),
        )
    if not cdl:
        _warn(
            log, warnings,
            "No aPlate .cdl found in %s/%s: the CDL nodes keep the template path"
            % (INPUT_DIR_NAME, LOOK_DIR_NAME),
        )
    if not clf:
        _warn(
            log, warnings,
            "No .clf LUT found in %s/%s: the LUT nodes keep the template path"
            % (INPUT_DIR_NAME, LOOK_DIR_NAME),
        )
    amf_con_extension, amf_con_sufijo = find_amf(shot_root)
    if not amf_con_extension:
        if amf_con_sufijo:
            _warn(
                log, warnings,
                "The .amf files in %s/%s have no extension (%s): Apply AMF "
                "looks for .amf and will not find them"
                % (INPUT_DIR_NAME, LOOK_DIR_NAME,
                   os.path.basename(amf_con_sufijo)),
            )
        else:
            _warn(
                log, warnings,
                "No .amf found in %s/%s: Apply AMF will not find the look chain"
                % (INPUT_DIR_NAME, LOOK_DIR_NAME),
            )

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

    # 5a. Read del publish v000 (CHECK vs EDIT): rango de proyecto. Si la
    # secuencia todavia no existe, el Read va a dar error al abrir: se
    # avisa, porque es lo que hace Create EXR v000 y puede faltar.
    if publish_v000_info(shot_root, shot_name) is None:
        _warn(
            log, warnings,
            "No comp_v000 publish yet: the CHECK vs EDIT Read will show an "
            "error until you run Create EXR v000",
        )
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
    editref_mov = find_editref(shot_root)
    if editref_frames is None:
        editref_frames = probe_mov_frames(editref_mov) if editref_mov else None
    if not editref_mov:
        _warn(
            log, warnings,
            "No EditRef .mov found in %s: the Read keeps the template path and "
            "will error" % INPUT_DIR_NAME,
        )
    if editref_frames:
        range_len = range_last - range_first + 1
        if editref_start is None:
            diff = max(0, range_len - editref_frames)
            editref_start = range_first + diff // 2
        editref_end = editref_start + editref_frames - 1
        # Rango REAL del clip, el que ve el Read del mov. El Write de review
        # sigue trabajando en frames de timeline (editref_start/editref_end).
        editref_clip_last = EDITREF_CLIP_FIRST + editref_frames - 1
        for chunk in chunks:
            cls = chunk_class(chunk)
            if cls == "Read" and "editref" in (chunk_knob(chunk, "file") or "").lower():
                # La ruta REAL del mov, no la del template con el shot
                # cambiado: el reemplazo global no toca la VERSION, asi que
                # un shot con EditRef_v002 quedaba apuntando al v001 del
                # template y el Read nacia roto.
                if editref_mov:
                    set_chunk_knob(chunk, "file", quote_if_needed(editref_mov))
                set_chunk_knob(chunk, "first", str(EDITREF_CLIP_FIRST))
                set_chunk_knob(chunk, "origfirst", str(EDITREF_CLIP_FIRST))
                set_chunk_knob(chunk, "last", str(editref_clip_last))
                set_chunk_knob(chunk, "origlast", str(editref_clip_last))
            elif cls == "TimeClip":
                # El rango del TimeClip es el REAL del clip del EditRef, el
                # mismo que entrega el Read (1 - N frames del mov). Quien lo
                # ubica en el timeline es frame_mode "start at": si ademas se
                # le escribe el rango ya corrido, el corrimiento se aplica dos
                # veces y el TimeClip le pide al Read frames que no tiene.
                set_or_add_chunk_knob(chunk, "first", str(EDITREF_CLIP_FIRST))
                set_or_add_chunk_knob(chunk, "last", str(editref_clip_last))
                set_or_add_chunk_knob(chunk, "origfirst", str(EDITREF_CLIP_FIRST))
                set_or_add_chunk_knob(chunk, "origlast", str(editref_clip_last))
                set_or_add_chunk_knob(chunk, "frame_mode", '"start at"')
                set_or_add_chunk_knob(chunk, "frame", str(editref_start))
            elif cls == "Write" and (chunk_knob(chunk, "name") or "").startswith(
                "WRITE_DNXHD"
            ):
                set_chunk_knob(chunk, "first", str(editref_start))
                set_chunk_knob(chunk, "last", str(editref_end))
        log.append(
            "  EditRef: %d frames, clip %d-%d, start at %d (timeline %d-%d)"
            % (editref_frames, EDITREF_CLIP_FIRST, editref_clip_last,
               editref_start, editref_start, editref_end)
        )
    elif editref_mov:
        # Solo si el mov EXISTE pero no se pudo medir: si no existe, ya se
        # aviso arriba y dos lineas para la misma causa es ruido. Se
        # distingue la causa: sin ffprobe falla en TODOS los shots y eso
        # hay que poder leerlo en el cartel, no deducirlo.
        if not ffprobe_path():
            _warn(
                log, warnings,
                "ffprobe not found: the EditRef duration could not be measured "
                "in any shot, so the review range is the template's. Reinstall "
                "the pack: ffprobe ships with it",
            )
        else:
            _warn(
                log, warnings,
                "Could not read the EditRef duration: the review range is the template's, check it by hand",
            )

    # Proteger rutas despues de clonar: fDenoised sigue sirviendo de modelo.
    for key in missing_denoised:
        for line_index, line in enumerate(chunks[reads[key]]):
            if re.match(r"^\s+file\s", line):
                marker = "__LGA_KEEP_DENOISED_%s_%d__" % (key, line_index)
                if marker in template_text:
                    raise CreateNKError("Marcador reservado presente en el template")
                preserved_files[marker] = line
                chunks[reads[key]][line_index] = marker

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
    # Un plate que el template contempla y el shot no tiene NO es aviso:
    # es el caso normal y su columna se borra.
    if not same_shot and re.search(re.escape(source_shot), text, re.IGNORECASE):
        raise CreateNKError("Quedaron menciones al shot de origen del template")

    # Restaurar solo las rutas aprobadas, despues de validar el resto del script.
    for marker, original_line in preserved_files.items():
        text = text.replace(marker, original_line)
    return text


def write_script(template_path, text, out_path, overwrite=False):
    """Escribe el .nk preservando los EOLs del template.

    Sin overwrite no pisa nada. Con overwrite, el .nk que estaba se
    conserva como <nombre>.nk~ antes de escribir: es la misma convencion
    de respaldo que deja Nuke al guardar, asi que pisar es reversible.
    """
    if os.path.exists(out_path):
        if not overwrite:
            raise CreateNKError("Ya existe %s" % out_path)
        backup = out_path + "~"
        try:
            if os.path.exists(backup):
                os.remove(backup)
            os.replace(out_path, backup)
        except OSError as error:
            raise CreateNKError(
                "No pude respaldar el .nk que estaba (%s): %s" % (backup, error)
            )
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


def prompt_template_selection(template_paths, on_choice):
    """Pide elegir template y llama on_choice(ruta) con la elegida.

    Con un solo template llama directo, sin UI. La ventana es NO-MODAL:
    Hiero sigue usable mientras esta abierta, igual que Create EXR v000.
    Devuelve el dialogo (o None) para que el llamador lo mantenga vivo.
    """
    if not template_paths:
        return None
    if len(template_paths) == 1:
        on_choice(template_paths[0])
        return None

    from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtCore
    from LGA_NKS_Shared.LGA_UI_Style_HieroTools import Style, Metric, apply_ui_font

    if QtWidgets.QApplication.instance() is None:
        return None

    parent = _get_hiero_main_window()
    dialog = QtWidgets.QDialog(parent) if parent is not None else QtWidgets.QDialog()
    dialog.setWindowTitle("Create NK v000")
    dialog.setModal(False)
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
            on_choice(path)
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
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    return dialog


def reveal_in_file_manager(path):
    """Abre la carpeta del archivo con el explorador POR DEFAULT.

    NUNCA se nombra explorer.exe: el usuario puede tener otro file
    manager y hay que respetar el suyo. En Windows eso lo da
    os.startfile() sobre la CARPETA (sobre el archivo lo abriria con su
    programa asociado, que para un .nk seria Nuke). Es el mismo patron
    que ya usa el resto del pack.
    """
    folder = os.path.dirname(os.path.normpath(path))
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", folder])
        elif os.name == "nt":
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open", folder])
    except (OSError, subprocess.SubprocessError) as error:
        debug_print("  [WARN] No se pudo abrir el explorador:", error)


def reveal_button_text():
    """Nombre del explorador segun la plataforma (texto de UI, en ingles)."""
    return "Show in Finder" if sys.platform == "darwin" else "Show in Explorer"


def show_created_dialog(parent, out_path, warnings):
    """Cartel final: ruta coloreada, boton para abrirla en el explorador y OK.

    Se arma a mano en vez de con show_info porque lleva un boton de mas: un
    QMessageBox en Windows pone el boton de accion a la izquierda, y la regla
    del pack lo quiere ultimo a la derecha (mismo motivo por el que
    ask_question del helper de carteles tampoco usa QMessageBox). NO-MODAL,
    como el resto de las ventanas de la tool.
    """
    from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtCore
    from LGA_NKS_Shared.LGA_UI_Style_HieroTools import (
        Style,
        Color,
        colorize_path,
        apply_ui_font,
        semibold_css,
    )

    if QtWidgets.QApplication.instance() is None:
        return None

    dialog = QtWidgets.QDialog(parent) if parent is not None else QtWidgets.QDialog()
    dialog.setWindowTitle("Create NK v000")
    dialog.setModal(False)
    dialog.setMinimumWidth(430)
    dialog.setStyleSheet(Style.FORM)

    layout = QtWidgets.QVBoxLayout(dialog)
    layout.setContentsMargins(18, 16, 18, 14)
    layout.setSpacing(10)

    layout.addWidget(QtWidgets.QLabel("Script created:"))

    path_label = QtWidgets.QLabel(colorize_path(out_path.replace("\\", "/")))
    path_label.setTextFormat(QtCore.Qt.RichText)
    path_label.setWordWrap(True)
    path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
    layout.addWidget(path_label)

    if warnings:
        # Los avisos son informacion de estado: van con el color del pack
        # para warning, no en el gris del cuerpo, porque el usuario tiene
        # que verlos si o si.
        titulo = QtWidgets.QLabel(
            "%d warning%s:" % (len(warnings), "" if len(warnings) == 1 else "s")
        )
        titulo.setStyleSheet("color: %s; %s" % (Color.WARNING_TEXT, semibold_css()))
        layout.addWidget(titulo)
        notes = QtWidgets.QLabel("\n".join("- %s" % w for w in warnings))
        notes.setWordWrap(True)
        notes.setStyleSheet("color: %s;" % Color.WARNING_TEXT)
        layout.addWidget(notes)

    row = QtWidgets.QHBoxLayout()
    reveal_btn = QtWidgets.QPushButton(reveal_button_text())
    reveal_btn.setStyleSheet(Style.BTN_SECONDARY)
    ok_btn = QtWidgets.QPushButton("OK")
    ok_btn.setStyleSheet(Style.BTN_PRIMARY)
    ok_btn.setDefault(True)
    for btn in (reveal_btn, ok_btn):
        btn.setMinimumHeight(28)
        btn.setMinimumWidth(90)
    reveal_btn.clicked.connect(lambda: reveal_in_file_manager(out_path))
    ok_btn.clicked.connect(dialog.accept)
    row.addWidget(reveal_btn)
    row.addStretch(1)
    row.addWidget(ok_btn)
    layout.addLayout(row)

    apply_ui_font(dialog)
    dialog.show()
    dialog.raise_()
    dialog.activateWindow()
    return dialog


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
        overwrite=False,
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
        self._on_accept = None
        self.editref_total_label = None
        self.create_btn = None

        parent = _get_hiero_main_window()
        dialog = QtWidgets.QDialog(parent) if parent is not None else QtWidgets.QDialog()
        self.dialog = dialog
        dialog.setWindowTitle("Create NK v000")
        dialog.setModal(False)
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
            # Geometria, no QSS: el spinbox va nativo (ver HANDLE_SPIN_WIDTH).
            spin.setFixedWidth(HANDLE_SPIN_WIDTH)
            spin.setFixedHeight(HANDLE_SPIN_HEIGHT)
            self.handle_spin = spin
            # Total que da la cuenta: el EditRef mas el handle de cada lado.
            self.editref_total_label = QtWidgets.QLabel("")
            row.addWidget(radio)
            row.addWidget(spin)
            row.addWidget(self.editref_total_label)
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
        # El boton nombra lo que va a pasar: si el v000 ya estaba, pisa.
        create_btn = QtWidgets.QPushButton("Overwrite" if overwrite else "Create")
        create_btn.setStyleSheet(Style.BTN_PRIMARY)
        for btn in (cancel_btn, create_btn):
            btn.setMinimumHeight(28)
            btn.setMinimumWidth(90)
        cancel_btn.clicked.connect(dialog.reject)
        create_btn.clicked.connect(self._accept)
        # Se guarda para poder apagarlo al aceptar: dos clicks rapidos
        # lanzarian dos veces el worker sobre el mismo .nk.
        self.create_btn = create_btn
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
        if self.editref_total_label is not None:
            self.editref_total_label.setText(
                "(%d frames)"
                % (self.editref_frames + 2 * self.handle_spin.value())
            )
        if count:
            self.range_label.setText(
                "Project range: %d-%d  (%d frames)"
                % (START_FRAME, START_FRAME + count - 1, count)
            )
        else:
            self.range_label.setText("")

    def _accept(self):
        if self.create_btn is not None:
            self.create_btn.setEnabled(False)
        count = self._selected_count()
        if count:
            self.result = (START_FRAME, START_FRAME + count - 1)
        self.dialog.accept()
        if self.result is not None and self._on_accept is not None:
            self._on_accept(self.result[0], self.result[1])

    def open(self, on_accept):
        """Muestra la ventana SIN bloquear Hiero y llama on_accept(first,
        last) cuando el usuario aprieta Create. Si cancela no llama a nadie."""
        self._on_accept = on_accept
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()


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
        done = QtCore.Signal(str, object)
        failed = QtCore.Signal(str)

        def __init__(self, params):
            QtCore.QThread.__init__(self)
            self.params = params

        def run(self):
            log = []
            try:
                p = self.params
                build_warnings = []
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
                    warnings=build_warnings,
                    keep_missing_denoised=p.get("keep_missing_denoised", False),
                )
                write_script(
                    p["template_path"], text, p["out_path"],
                    overwrite=p.get("overwrite", False),
                )
                for line in log:
                    debug_print(line)
                write_log_file("OK: escrito %s" % p["out_path"], log)
                self.done.emit(p["out_path"], build_warnings)
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
            self.out_path = None
            # los dialogos no-modales se guardan para que Qt no los
            # recolecte mientras estan abiertos
            self.template_dialog = None
            self.range_dialog = None
            self.created_dialog = None

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
            # lo que sale del timeline se lee ANTES de ir a los hilos
            self.editref_offset = timeline_editref_offset(seq, item)
            self.timeline_counts = timeline_plate_counts(seq, item)

            # el selector es NO-MODAL: sigue por callback, no por retorno
            self.template_dialog = prompt_template_selection(
                templates, self._on_template_chosen
            )

        def _on_template_chosen(self, template_path):
            self.template_path = template_path
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

            missing = missing_denoised_keys(columns)
            self.keep_missing_denoised = False
            if missing:
                if not confirm_missing_denoised(_get_hiero_main_window(), missing):
                    write_log_file("Cancelado: faltan denoised %s" % ", ".join(missing))
                    return
                self.keep_missing_denoised = True

            out_path = v000_output(self.shot_root, self.shot_name)
            # Si el v000 ya existe se pregunta, no se aborta: rehacerlo es
            # un caso normal. Sin recomendada, porque pisar es destructivo
            # y el cartel no tiene que empujar a ninguna de las dos.
            self.overwrite = os.path.exists(out_path)
            if self.overwrite:
                from LGA_NKS_Shared.LGA_NKS_MessageBox import ask_question

                if not ask_question(
                    _get_hiero_main_window(),
                    "Create NK v000",
                    "This v000 already exists:\n%s\n\nOverwrite it?\n"
                    "The current one is kept as .nk~"
                    % out_path.replace("\\", "/"),
                    yes_text="Overwrite",
                    no_text="Cancel",
                    recommended=False,
                ):
                    return
            # NO-MODAL: Hiero queda usable y el flujo sigue por callback
            self.out_path = out_path
            self.range_dialog = RangeDialog(
                self.shot_name,
                columns,
                data["editref_frames"],
                out_path,
                publish_v000=data.get("publish_v000"),
                timeline_counts=getattr(self, "timeline_counts", None),
                overwrite=self.overwrite,
            )
            self.range_dialog.open(self._on_range_chosen)

        def _on_range_chosen(self, range_first, range_last):
            data = self.scan_data
            columns = data["columns"]
            out_path = self.out_path

            editref_start = None
            if self.editref_offset is not None and data["editref_frames"]:
                editref_start = range_first + self.editref_offset
                editref_end = editref_start + data["editref_frames"] - 1
                if editref_start < range_first or editref_end > range_last:
                    # el offset del timeline cae fuera del rango elegido:
                    # mejor centrar y avisar que escribir un .nk corrido
                    data["unknown"].append(
                        "EditRef offset taken from the timeline (%+d) falls "
                        "outside %d-%d: centered instead"
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
                    "overwrite": getattr(self, "overwrite", False),
                    "keep_missing_denoised": self.keep_missing_denoised,
                }
            )
            self.build_worker.done.connect(self._on_build_done)
            self.build_worker.failed.connect(self._on_failed)
            self.build_worker.start()

        def _on_build_done(self, out_path, build_warnings):
            # Todo lo que el usuario tiene que saber, junto: lo que salio
            # del escaneo del shot y lo que salio de armar el script.
            warnings = list((self.scan_data or {}).get("unknown") or [])
            for message in build_warnings or []:
                if message not in warnings:
                    warnings.append(message)
            self.created_dialog = show_created_dialog(
                _get_hiero_main_window(), out_path, warnings
            )

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
