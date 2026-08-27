"""
____________________________________________________________________

  LGA_NKS_ApplyAMF v0.40 | Lega

  Crea los soft effects de color sobre los clips seleccionados del timeline,
  siguiendo lo que declara el .amf que viene con el shot.

  El .amf (ACES Metadata File) describe la cadena entera del plate y es la
  fuente de verdad. De ahi salen tres cosas:

    - QUE aplicar: cada <lookTransform> trae applied="true|false". Los que
      ya vienen horneados en el plate (IDT, Reference Gamut Compress) se
      saltean; solo se crean los que estan en false.
    - EN QUE ORDEN: los <lookTransform> vienen en orden de cadena. El
      primero que se crea queda en el subtrack de abajo, o sea que se
      aplica antes.
    - CON QUE PARAMETROS: el <cdlWorkingSpace> dice en que espacio opera el
      CDL (ej. ACEScct, NO el scene_linear que trae el nodo por defecto), y
      el <file> del LMT nombra el .clf a cargar.

  Efectos que sabe crear:
    OCIOCDLTransform  <- el .cdl del shot (grade)
    OCIOFileTransform <- el .clf que nombra el .amf (LMT)

  Si no hay .amf en la carpeta se cae a un plan fijo: un archivo por
  extension, sin tocar el working space. Queda avisado por consola.

  Flujo por clip:
    1. Ruta de la media del clip.
    2. Carpeta del shot, via extract_shot_code_from_path() de NamingUtils,
       que valida el vendor code contra la DB de PipeSync. Fallback: subir
       directorios hasta encontrar uno que tenga _input adentro.
    3. <shot>/_input/Look_Files/
    4. Leer el .amf y armar el plan de efectos.
    5. Crear (o reusar) cada soft effect linkeado al clip y setear sus knobs.

  Ejemplo de estructura esperada:
    T:/VFX-PROJA/101/PROJA_1013_0800_VND/_input/Look_Files/
        PROJA_1013_0800_VND_aPlate_v001.amf
        PROJA_1013_0800_VND_aPlate_v001.cdl
        algun_lmt_acesap0_linear.clf

  API relevante (Nuke 16 PythonDevGuide / Hiero / api_core):
    VideoTrack.createEffect(effectType=None, cloneFrom=None, copyFrom=None,
                            trackItem=None, timelineIn=None, timelineOut=None,
                            subTrackIndex=None) -> EffectTrackItem
    Pasando trackItem, el efecto queda LINKEADO al clip y toma su mismo
    timing. Sin trackItem hay que dar timelineIn/timelineOut, y el efecto
    queda suelto en el track (es lo que hace LGA_NKS_FrameNumber_Create).

  PENDIENTE (manejo de errores, se trabaja al final):
    - Cartel de aviso cuando hay mas de un archivo de la misma extension.
      Hoy solo avisa por consola y usa el primero.

  v0.40: El .amf pasa a ser la fuente de verdad: de ahi salen el orden, el
         applied de cada transform, el working space del CDL y el nombre
         del .clf. El working space se matchea contra las opciones reales
         del knob, para no depender del nombre que use el OCIO config.
  v0.30: Suma el OCIOFileTransform con el .clf, despues del CDL. La eleccion
         de archivo pasa a ser "el unico de esa extension".
  v0.20: Resuelve el .cdl de <shot>/_input/Look_Files y lo carga en el
         efecto (file + cccid + read_from_file). Reusa el efecto si el clip
         ya tiene uno. No crea nada si no encuentra el .cdl.
  v0.10: Version inicial exploratoria.
____________________________________________________________________

"""

import os
import re
import sys
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path

import hiero.core
import hiero.ui

# ============================
# Configuracion
# ============================

DEBUG = True

# Nombres de carpeta donde viven los archivos de look, colgando del shot.
INPUT_DIR_NAME = "_input"
LOOK_DIR_NAME = "Look_Files"

# Plan de respaldo, para cuando el shot no trae .amf. Mismo orden que el .amf
# de referencia: primero el grade, despues el LMT.
FALLBACK_EFFECTS = (
    {"type": "OCIOCDLTransform", "extension": ".cdl"},
    {"type": "OCIOFileTransform", "extension": ".clf"},
)

# Si el clip ya tiene un efecto de ese tipo linkeado, se actualiza ese en vez de
# crear otro. Asi el boton es idempotente y no apila efectos al reintentar.
REUSE_EXISTING = True


def debug_print(*message):
    if DEBUG:
        print(*message)


# ============================
# Naming centralizado
# ============================

# La carpeta del shot se detecta por NOMBRE y no por profundidad de ruta. El
# helper central valida ademas el vendor code contra la DB de PipeSync, que es
# lo que un conteo de segmentos no puede saber (naming PROYECTO_SEQ_SHOT_VENDOR).
_shared_dir = Path(__file__).parent.parent / "LGA_NKS_Shared"
if _shared_dir.exists():
    sys.path.insert(0, str(_shared_dir))
try:
    from LGA_NKS_Flow_NamingUtils import (
        extract_shot_code_from_path,
        extract_project_name_from_path,
    )
except ImportError:
    extract_shot_code_from_path = None
    extract_project_name_from_path = None
    debug_print("[WARN] No se pudo importar LGA_NKS_Flow_NamingUtils")


# ============================
# Helpers genericos
# ============================


def _safe_name(obj):
    """name() sin romper si el objeto no lo tiene o esta invalidado."""
    try:
        return obj.name()
    except Exception:
        return repr(obj)


def _safe_call(obj, method_name, default="<n/a>"):
    """Llama a un metodo sin argumentos y devuelve default si falla."""
    try:
        method = getattr(obj, method_name, None)
        if method is None:
            return default
        return method()
    except Exception as e:
        return f"<error: {e}>"


def _find_subdir(parent_dir, wanted_name):
    """Busca una subcarpeta por nombre sin distinguir mayusculas.

    En Windows daria igual, pero este repo tambien corre en macOS, donde el
    filesystem si distingue.
    """
    if not parent_dir or not os.path.isdir(parent_dir):
        return None
    wanted = wanted_name.lower()
    try:
        for entry in os.scandir(parent_dir):
            if entry.is_dir() and entry.name.lower() == wanted:
                return entry.path
    except OSError as e:
        debug_print(f"  [WARN] No se pudo listar '{parent_dir}': {e}")
    return None


def _local_tag(element):
    """Nombre del tag sin el namespace.

    Los XML de ACES declaran namespace (urn:ampas:aces:amf:v2.0,
    urn:ASC:CDL:v1.01), asi que los tags vienen como '{urn:...}lookTransform'.
    """
    return element.tag.split("}")[-1]


def _normalize(text):
    """Deja solo letras y numeros en minuscula, para comparar nombres de espacios."""
    return re.sub(r"[^a-z0-9]", "", str(text).lower())


# ============================
# Resolucion de rutas
# ============================


def get_media_path(track_item):
    """Ruta en disco de la media del clip."""
    try:
        return track_item.source().mediaSource().firstpath()
    except Exception as e:
        debug_print(f"  [WARN] No se pudo leer la media del clip: {e}")
        return None


def resolve_shot_dir(media_path):
    """Carpeta del shot a partir de la ruta de la media.

    Sirve tanto para una media de _input como para un publish de Comp: en los
    dos casos la carpeta del shot esta mas arriba en la misma ruta.
    """
    if not media_path:
        return None

    normalized = re.sub(r"[\\/]+", "/", str(media_path))

    # Camino 1: el helper central, que reconoce el vendor code.
    if extract_shot_code_from_path:
        project_name = (
            extract_project_name_from_path(normalized)
            if extract_project_name_from_path
            else None
        )
        shot_code = extract_shot_code_from_path(normalized, project_name)
        debug_print(f"  project (de la ruta) : {project_name}")
        debug_print(f"  shot code            : {shot_code or '<no reconocido>'}")
        if shot_code:
            segments = normalized.split("/")
            for index in range(len(segments) - 1, -1, -1):
                if segments[index] == shot_code:
                    return "/".join(segments[: index + 1])

    # Camino 2: fallback estructural. Subir hasta el directorio que tenga _input
    # adentro. Cubre los shots con bloques de descripcion, que es el limite
    # conocido de is_shot_folder_name().
    debug_print("  [INFO] Fallback: buscando el directorio que contenga _input")
    current = os.path.dirname(normalized)
    while current and current != os.path.dirname(current):
        if _find_subdir(current, INPUT_DIR_NAME):
            return re.sub(r"[\\/]+", "/", current)
        current = os.path.dirname(current)

    return None


def resolve_look_dir(shot_dir):
    """<shot>/_input/Look_Files"""
    if not shot_dir:
        return None
    input_dir = _find_subdir(shot_dir, INPUT_DIR_NAME)
    if not input_dir:
        debug_print(f"  [ERROR] No existe '{INPUT_DIR_NAME}' en {shot_dir}")
        return None
    look_dir = _find_subdir(input_dir, LOOK_DIR_NAME)
    if not look_dir:
        debug_print(f"  [ERROR] No existe '{LOOK_DIR_NAME}' en {input_dir}")
        return None
    return re.sub(r"[\\/]+", "/", look_dir)


def find_look_file(look_dir, extension, quiet=False):
    """El unico archivo de esa extension en la carpeta de look.

    Los nombres no siempre vienen bien armados, asi que no se filtra por
    nombre: se busca por extension y se espera que haya uno solo.

    PENDIENTE: si hay mas de uno hay que mostrar un cartel. Por ahora avisa
    por consola y devuelve el primero, para no frenar el resto del flujo.
    """
    if not look_dir:
        return None

    try:
        candidates = sorted(
            entry.path
            for entry in os.scandir(look_dir)
            if entry.is_file() and entry.name.lower().endswith(extension)
        )
    except OSError as e:
        debug_print(f"  [ERROR] No se pudo listar '{look_dir}': {e}")
        return None

    if not candidates:
        if not quiet:
            debug_print(f"  [ERROR] No hay ningun '*{extension}' en {look_dir}")
        return None

    if len(candidates) > 1:
        debug_print(f"  [AVISO] Hay {len(candidates)} archivos '{extension}', deberia haber uno solo:")
        for path in candidates:
            debug_print(f"      - {os.path.basename(path)}")
        debug_print(f"  [AVISO] Por ahora se usa: {os.path.basename(candidates[0])}")

    return re.sub(r"[\\/]+", "/", candidates[0])


def read_cccid(cdl_path):
    """Atributo id del primer <ColorCorrection> del .cdl.

    Es lo que el OCIOCDLTransform espera en el knob cccid para elegir que
    correccion aplicar dentro del archivo. No se arma con el nombre del clip:
    el archivo puede tener otra version que la media (v001 contra V002).
    """
    try:
        root = ET.parse(cdl_path).getroot()
    except Exception as e:
        debug_print(f"  [WARN] No se pudo parsear el .cdl: {e}")
        return None

    ids = [
        element.get("id")
        for element in root.iter()
        if _local_tag(element) == "ColorCorrection" and element.get("id")
    ]

    if not ids:
        debug_print("  [WARN] El .cdl no declara ningun ColorCorrection id")
        return None

    if len(ids) > 1:
        debug_print(f"  [INFO] El .cdl tiene {len(ids)} ids, se usa el primero: {ids}")
    return ids[0]


# ============================
# Lectura del .amf
# ============================


def _target_space_from_transform_id(transform_id):
    """Espacio destino de un ACEScsc.

    'urn:ampas:aces:transformId:v1.5:ACEScsc.Academy.ACES_to_ACEScct.a1.0.3'
    devuelve 'ACEScct'.
    """
    if not transform_id:
        return None
    match = re.search(r"ACES_to_([A-Za-z0-9]+)", transform_id)
    return match.group(1) if match else None


def _target_space_from_description(description):
    """Espacio destino de una descripcion tipo 'ACES2065-1 to ACEScct'."""
    if not description or " to " not in description:
        return None
    return description.split(" to ")[-1].strip() or None


def _read_look_transform(element):
    """Interpreta un <lookTransform> del .amf.

    Devuelve un dict con lo que se pudo reconocer: si es el CDL (trae
    cdlWorkingSpace), si es un LMT de archivo (trae file), y si ya viene
    aplicado en el plate.
    """
    info = {
        "applied": (element.get("applied") or "").strip().lower() == "true",
        "description": None,
        "working_space": None,
        "file": None,
        "has_cdl": False,
    }

    for child in element.iter():
        tag = _local_tag(child)
        text = (child.text or "").strip() if child.text else ""

        if tag == "description" and not info["description"]:
            info["description"] = text
        elif tag == "file" and text:
            info["file"] = text
        elif tag in ("SOPNode", "SatNode", "SATNode", "cdlWorkingSpace"):
            info["has_cdl"] = True

    # El working space del CDL: se prefiere el transformId, que es estructurado.
    for child in element.iter():
        if _local_tag(child) != "toCdlWorkingSpace":
            continue
        for sub in child.iter():
            sub_tag = _local_tag(sub)
            sub_text = (sub.text or "").strip() if sub.text else ""
            if sub_tag == "transformId":
                info["working_space"] = _target_space_from_transform_id(sub_text)
            elif sub_tag == "description" and not info["working_space"]:
                info["working_space"] = _target_space_from_description(sub_text)

    return info


def read_amf(amf_path):
    """Lee el .amf y devuelve la lista de <lookTransform> en orden de cadena."""
    try:
        root = ET.parse(amf_path).getroot()
    except Exception as e:
        debug_print(f"  [WARN] No se pudo parsear el .amf: {e}")
        return []

    return [
        _read_look_transform(element)
        for element in root.iter()
        if _local_tag(element) == "lookTransform"
    ]


def build_effect_plan(look_dir):
    """Arma la lista de efectos a crear, en orden.

    Con .amf: se respeta el orden y el applied de cada lookTransform, y se
    toman working space y nombre de archivo de ahi. Sin .amf: plan fijo por
    extension.
    """
    amf_path = find_look_file(look_dir, ".amf", quiet=True)
    if not amf_path:
        debug_print("  [AVISO] El shot no trae .amf: se usa el plan fijo por extension.")
        return _fallback_plan(look_dir)

    debug_print(f"  amf                  : {amf_path}")
    look_transforms = read_amf(amf_path)
    if not look_transforms:
        debug_print("  [AVISO] El .amf no declara lookTransform: se usa el plan fijo.")
        return _fallback_plan(look_dir)

    plan = []
    for index, info in enumerate(look_transforms, start=1):
        etiqueta = info["description"] or "<sin descripcion>"

        if info["applied"]:
            debug_print(f"    {index}. [YA APLICADO] {etiqueta}")
            continue

        if info["has_cdl"]:
            cdl_path = find_look_file(look_dir, ".cdl")
            if not cdl_path:
                debug_print(f"    {index}. [ERROR] El .amf pide un CDL y no hay .cdl en la carpeta")
                continue
            debug_print(
                f"    {index}. [APLICAR] CDL -> {os.path.basename(cdl_path)} "
                f"(working space: {info['working_space'] or 'sin declarar'})"
            )
            plan.append(
                {
                    "type": "OCIOCDLTransform",
                    "file": cdl_path,
                    "cccid": read_cccid(cdl_path),
                    "working_space": info["working_space"],
                }
            )
            continue

        if info["file"]:
            # El .amf nombra el archivo; se resuelve contra la carpeta de look.
            lmt_path = os.path.join(look_dir, info["file"])
            if not os.path.isfile(lmt_path):
                debug_print(
                    f"    {index}. [AVISO] El .amf nombra '{info['file']}' y no esta en la carpeta"
                )
                lmt_path = find_look_file(look_dir, os.path.splitext(info["file"])[1])
                if not lmt_path:
                    debug_print(f"    {index}. [ERROR] Tampoco hay otro archivo de esa extension")
                    continue
            lmt_path = re.sub(r"[\\/]+", "/", lmt_path)
            debug_print(f"    {index}. [APLICAR] LMT -> {os.path.basename(lmt_path)}")
            plan.append(
                {
                    "type": "OCIOFileTransform",
                    "file": lmt_path,
                    "cccid": None,
                    "working_space": info["working_space"],
                }
            )
            continue

        # Transforms que el .amf declara solo por transformId (built-in del
        # config OCIO, sin archivo). No se pueden cargar en un nodo de archivo.
        debug_print(f"    {index}. [SALTEADO] Sin archivo asociado: {etiqueta}")

    return plan


def _fallback_plan(look_dir):
    """Plan fijo por extension, para shots sin .amf."""
    plan = []
    for spec in FALLBACK_EFFECTS:
        file_path = find_look_file(look_dir, spec["extension"])
        if not file_path:
            continue
        plan.append(
            {
                "type": spec["type"],
                "file": file_path,
                "cccid": read_cccid(file_path) if spec["type"] == "OCIOCDLTransform" else None,
                "working_space": None,
            }
        )
    return plan


# ============================
# Soft effects
# ============================


def find_linked_effect(track_item, effect_type):
    """Devuelve el soft effect del tipo pedido ya linkeado al clip, si existe."""
    try:
        linked = track_item.linkedItems()
    except Exception as e:
        debug_print(f"  [WARN] No se pudo leer linkedItems(): {e}")
        return None

    for item in linked:
        if not isinstance(item, hiero.core.EffectTrackItem):
            continue
        node = _safe_call(item, "node", None)
        try:
            if node and node.Class() == effect_type:
                return item
        except Exception:
            continue
    return None


def create_effect_on_track_item(track_item, effect_type):
    """Crea un soft effect linkeado al TrackItem. Devuelve el EffectTrackItem o None."""
    track = track_item.parent()
    if not track:
        debug_print("    [ERROR] El clip no tiene track padre.")
        return None

    if not hasattr(track, "createEffect"):
        debug_print("    [ERROR] El track no expone createEffect(). Version de Hiero muy vieja.")
        return None

    # Intento 1: linkeado al trackItem (hereda el timing del clip).
    try:
        effect = track.createEffect(effectType=effect_type, trackItem=track_item)
        if effect:
            debug_print(f"    [OK] Creado y linkeado: {_safe_name(effect)}")
            return effect
        debug_print("    [WARN] createEffect() devolvio None con trackItem.")
    except Exception as e:
        debug_print(f"    [ERROR] Fallo createEffect() con trackItem: {e}")
        debug_print(traceback.format_exc())

    # Intento 2: por timing explicito, como hace LGA_NKS_FrameNumber_Create.
    timeline_in = _safe_call(track_item, "timelineIn", None)
    timeline_out = _safe_call(track_item, "timelineOut", None)
    try:
        effect = track.createEffect(
            effectType=effect_type,
            timelineIn=timeline_in,
            timelineOut=timeline_out,
        )
        if effect:
            debug_print(f"    [OK] Creado (sin linkear): {_safe_name(effect)}")
            return effect
        debug_print("    [WARN] createEffect() devolvio None tambien con timing explicito.")
    except Exception as e:
        debug_print(f"    [ERROR] Fallo createEffect() con timing explicito: {e}")
        debug_print(traceback.format_exc())

    return None


def _set_knob(node, knob_name, value):
    """setValue con log. True si se pudo."""
    try:
        node[knob_name].setValue(value)
        debug_print(f"    [OK] {knob_name} = {value!r}")
        return True
    except Exception as e:
        debug_print(f"    [ERROR] No se pudo setear {knob_name}: {e}")
        return False


def match_colorspace_option(node, knob_name, wanted):
    """Encuentra en el enum del knob la opcion que corresponde a `wanted`.

    El nombre exacto del espacio depende del OCIO config del proyecto: el
    mismo ACEScct puede figurar como 'ACEScct' o 'ACES - ACEScct'. Por eso no
    se hardcodea el string, se busca contra las opciones reales del knob.
    """
    if not wanted:
        return None

    try:
        options = list(node[knob_name].values())
    except Exception as e:
        debug_print(f"    [WARN] No se pudieron leer las opciones de {knob_name}: {e}")
        return None

    target = _normalize(wanted)

    # De mas estricto a mas laxo. El orden importa: buscando 'ACEScc' primero
    # por igualdad y sufijo se evita que matchee 'ACEScct' por contencion.
    for opcion in options:
        if _normalize(opcion) == target:
            return opcion
    for opcion in options:
        if _normalize(opcion).endswith(target):
            return opcion
    for opcion in options:
        if target in _normalize(opcion):
            return opcion

    debug_print(f"    [WARN] '{wanted}' no figura entre las opciones de {knob_name}")
    return None


def configure_effect_node(node, spec):
    """Carga el archivo de look y los parametros del .amf en el nodo."""
    if not node:
        debug_print("    [ERROR] El efecto no tiene nodo.")
        return False

    effect_type = spec["type"]
    ok = True

    if effect_type == "OCIOCDLTransform":
        # read_from_file va PRIMERO: con el knob en False, file y cccid quedan
        # deshabilitados y el nodo ignora el archivo.
        ok &= _set_knob(node, "read_from_file", True)
        ok &= _set_knob(node, "file", spec["file"])
        if spec.get("cccid"):
            ok &= _set_knob(node, "cccid", spec["cccid"])
        else:
            debug_print("    [WARN] Sin cccid: el nodo toma la primera correccion del archivo.")
    else:
        ok &= _set_knob(node, "file", spec["file"])

    # El working space lo declara el .amf. El default del nodo (scene_linear)
    # no es el que pide la cadena ACES, y con un grade real da distinto.
    wanted = spec.get("working_space")
    if wanted:
        opcion = match_colorspace_option(node, "working_space", wanted)
        if opcion:
            ok &= _set_knob(node, "working_space", opcion)
        else:
            debug_print(f"    [WARN] Se deja el working_space por defecto (el .amf pedia '{wanted}')")

    return ok


def print_node_knobs(node, titulo):
    """Vuelca los knobs del nodo. Sirve para ver que queda por configurar."""
    if not node:
        return
    try:
        knobs = node.knobs()
    except Exception as e:
        debug_print(f"    [WARN] No se pudieron leer los knobs: {e}")
        return

    debug_print(f"    [KNOBS DE {titulo}] ({len(knobs)} en total)")
    for knob_name in sorted(knobs.keys()):
        try:
            value = knobs[knob_name].value()
        except Exception as e:
            value = f"<no legible: {e}>"
        try:
            knob_class = knobs[knob_name].Class()
        except Exception:
            knob_class = "?"
        debug_print(f"      {knob_name:<26} [{knob_class}] = {value!r}")


def verify_node(node, effect_type):
    """Relee los knobs que nos importan para confirmar que quedo lo que queriamos."""
    if not node:
        return
    if effect_type == "OCIOCDLTransform":
        knob_names = ("read_from_file", "file", "cccid", "working_space", "slope", "offset", "power", "saturation")
    else:
        knob_names = ("file", "working_space", "direction", "interpolation")

    debug_print("    [VERIFICACION]")
    for knob_name in knob_names:
        try:
            debug_print(f"      {knob_name:<16} = {node[knob_name].value()!r}")
        except Exception as e:
            debug_print(f"      {knob_name:<16} = <no legible: {e}>")


def apply_effect(track_item, spec):
    """Crea/actualiza un soft effect del clip con su archivo de look. True si ok."""
    effect_type = spec["type"]
    debug_print(f"\n  --- {effect_type} ---")
    debug_print(f"    archivo   : {spec['file']}")
    if spec.get("cccid"):
        debug_print(f"    cccid     : {spec['cccid']}")

    effect = find_linked_effect(track_item, effect_type) if REUSE_EXISTING else None
    if effect:
        debug_print(f"    [INFO] El clip ya tenia uno: se actualiza '{_safe_name(effect)}'")
    else:
        effect = create_effect_on_track_item(track_item, effect_type)
        if not effect:
            return False

    debug_print(f"    subTrackIndex : {_safe_call(effect, 'subTrackIndex')}")
    debug_print(f"    timelineIn/Out: {_safe_call(effect, 'timelineIn')} / {_safe_call(effect, 'timelineOut')}")

    node = _safe_call(effect, "node", None)
    ok = configure_effect_node(node, spec)

    # El OCIOFileTransform todavia no esta afinado: mostramos todos sus knobs
    # para decidir que mas hay que setear (direction, interpolation...).
    if effect_type == "OCIOFileTransform":
        print_node_knobs(node, effect_type)
    else:
        verify_node(node, effect_type)

    if _safe_call(effect, "nodeHasError", False):
        debug_print("    [WARN] El nodo quedo en error. Revisar la ruta del archivo.")

    return ok


# ============================
# Proceso por clip
# ============================


def process_track_item(track_item):
    """Resuelve el look del clip y le aplica los soft effects. True si todos ok."""
    debug_print("\n" + "-" * 70)
    debug_print(f"[CLIP] {_safe_name(track_item)}")
    debug_print("-" * 70)

    track = track_item.parent()
    debug_print(f"  track                : {_safe_name(track) if track else '<sin track>'}")

    media_path = get_media_path(track_item)
    debug_print(f"  media                : {media_path}")
    if not media_path:
        return False

    shot_dir = resolve_shot_dir(media_path)
    debug_print(f"  shot dir             : {shot_dir}")
    if not shot_dir:
        debug_print("  [ERROR] No se pudo resolver la carpeta del shot.")
        return False

    look_dir = resolve_look_dir(shot_dir)
    debug_print(f"  look dir             : {look_dir}")
    if not look_dir:
        return False

    debug_print("  [PLAN SEGUN EL AMF]")
    plan = build_effect_plan(look_dir)
    if not plan:
        debug_print("  [ERROR] No quedo ningun efecto por aplicar en este clip.")
        return False

    # Los efectos se crean en el orden del plan: el primero queda en el
    # subtrack de abajo, o sea que se aplica antes.
    resultados = [apply_effect(track_item, spec) for spec in plan]
    return all(resultados)


# ============================
# Entrada
# ============================


def get_selected_track_items():
    """Devuelve los TrackItem seleccionados en el timeline, sin soft effects."""
    seq = hiero.ui.activeSequence()
    if not seq:
        debug_print("[ERROR] No hay secuencia activa.")
        return None, []

    te = hiero.ui.getTimelineEditor(seq)
    if not te:
        debug_print("[ERROR] No se pudo obtener el timeline editor.")
        return seq, []

    selection = te.selection() or []
    track_items = [
        item
        for item in selection
        if isinstance(item, hiero.core.TrackItem)
        and not isinstance(item, hiero.core.EffectTrackItem)
    ]
    debug_print(f"[INFO] Clips seleccionados: {len(track_items)} (de {len(selection)} items)")
    return seq, track_items


def main():
    debug_print("\n" + "=" * 70)
    debug_print("  LGA_NKS_ApplyAMF - soft effects de color segun el .amf del shot")
    debug_print(f"  desde {INPUT_DIR_NAME}/{LOOK_DIR_NAME}")
    debug_print("=" * 70)

    seq, track_items = get_selected_track_items()
    if not seq:
        return

    if not track_items:
        debug_print("[ERROR] No hay clips seleccionados en el timeline.")
        return

    project = seq.project()
    aplicados = 0

    if project:
        project.beginUndo("Apply AMF")
    try:
        for track_item in track_items:
            try:
                if process_track_item(track_item):
                    aplicados += 1
            except Exception as e:
                debug_print(f"[ERROR] Fallo procesando '{_safe_name(track_item)}': {e}")
                debug_print(traceback.format_exc())
    finally:
        if project:
            project.endUndo()

    debug_print("\n" + "=" * 70)
    debug_print(f"  RESUMEN: {aplicados} de {len(track_items)} clips con el look completo")
    debug_print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
