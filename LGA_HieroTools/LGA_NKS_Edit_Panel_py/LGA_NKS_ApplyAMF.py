"""
____________________________________________________________________

  LGA_NKS_ApplyAMF v0.90 | Lega

  Pone y saca los soft effects de color de un shot, siguiendo lo que
  declara el .amf que viene con el shot.

  Con TOGGLE_CREATE_DELETE en True (el default) el boton es un TOGGLE:
  si los clips objetivo YA tienen la cadena AMF, la BORRA; si no la
  tienen, la crea. Tener soft effects colgados en el timeline todo el
  tiempo estorba, y con un solo boton se ponen y se sacan.

  De donde salen los clips objetivo (regla por CANTIDAD, no por
  presencia):

    - DOS o mas clips seleccionados -> se opera solo sobre esos.
    - UNO o ninguno -> se ignora la seleccion y se barren todos los
      tracks bajo el PLAYHEAD, tomando solo los .exr.

  El umbral esta en dos porque Hiero AUTOSELECCIONA el clip bajo el
  playhead: parado sobre un shot y sin tocar nada, selection() ya
  devuelve un item, asi que "uno seleccionado" y "ninguno seleccionado"
  son el mismo caso desde la API. Ver SELECCION_MINIMA.

  Esa regla NO depende del flag: el flag decide crear o borrar, no de
  donde salen los clips. Con el flag en False la tool solo crea, nunca
  borra.

  El boton tiene el atajo Shift+L.

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

  PENDIENTE: cartel cuando hay mas de un archivo de la misma extension
  en Look_Files. Hoy eso solo avisa por log y usa el primero.

  v0.90: Los clips objetivo salen del playhead salvo que haya DOS o mas
         seleccionados. Con uno solo la tool creia estar respetando una
         seleccion del usuario, pero era la autoseleccion de Hiero, y
         terminaba tocando un solo track en vez del shot entero. Del
         playhead se toman solo los .exr, para no meterle la cadena a un
         EditRef. La tool absorbe el atajo Shift+L, que deja de estar en
         Toggle AMF.
  v0.80: El boton pasa a ser un toggle de crear/borrar (flag
         TOGGLE_CREATE_DELETE) y, sin seleccion, opera sobre el
         playhead en todos los tracks. El borrado va con
         eDontRemoveLinkedItems: los efectos se crean LINKEADOS al
         clip, y removeSubTrackItem sin esa opcion se lleva puesto el
         CLIP del timeline. Solo se borra lo que apunta a Look_Files,
         asi un efecto de la misma clase puesto a mano no se pierde.
  v0.70: Avisa por cartel cuando no puede resolver un shot, en vez de
         terminar en silencio. UN solo cartel por corrida y agrupado
         por SHOT, no por clip: un shot suele tener clips en aPlate,
         bPlate y _comp_, y repetir el mismo nombre tres veces hace
         el aviso ilegible.
  v0.62: Cada corrida escribe su log a logs/DebugPy_LGA_NKS_ApplyAMF.log,
         prendido o no el debug por consola. Sin eso la tool era
         una caja negra cuando no hacia nada.
  v0.61: El debug por consola queda apagado por default.
  v0.60: Los efectos van a un subtrack FIJO (el indice de la cadena)
         y no a uno nuevo por llamada. Sin pasar subTrackIndex, cada
         createEffect abria un subtrack propio: el segundo clip del
         track quedaba con sus efectos en s1/s2 y un s0 vacio debajo,
         que se veia como una franja muerta entre el clip y su cadena.
  v0.50: No vuelve a crear un efecto que el clip ya tiene: se saltea y se
         crea solo el que falta. La deteccion no se queda con linkedItems():
         tambien barre los subtracks del track, porque un efecto creado a
         mano queda suelto y ahi no figura.
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

DEBUG = False

# Nombres de carpeta donde viven los archivos de look, colgando del shot.
INPUT_DIR_NAME = "_input"
LOOK_DIR_NAME = "Look_Files"

# Plan de respaldo, para cuando el shot no trae .amf. Mismo orden que el .amf
# de referencia: primero el grade, despues el LMT.
FALLBACK_EFFECTS = (
    {"type": "OCIOCDLTransform", "extension": ".cdl"},
    {"type": "OCIOFileTransform", "extension": ".clf"},
)

# Si el clip ya tiene un efecto de ese tipo, se lo deja como esta y se crea solo
# el que falta. Asi el boton es idempotente y no apila efectos al reintentar, ni
# pisa un archivo que alguien haya cambiado a mano.
SKIP_IF_EXISTS = True

# El boton como TOGGLE: si los clips objetivo ya tienen la cadena AMF, la borra;
# si no la tienen, la crea. Ademas, sin seleccion opera sobre el playhead.
#
# En False queda el comportamiento viejo -crear sobre la seleccion, nunca
# borrar-. El codigo de creacion es el mismo en los dos casos: el flag no
# bifurca la logica de creacion, solo decide si ademas se puede borrar y de
# donde salen los clips.
TOGGLE_CREATE_DELETE = True

# Los tipos que pone esta tool. Es la lista que mira el toggle para saber si un
# clip "ya tiene AMF", y la unica que se borra. Tiene que coincidir con la de
# LGA_NKS_ToggleAMF: son las dos puntas de la misma herramienta.
AMF_EFFECT_TYPES = ("OCIOCDLTransform", "OCIOFileTransform")

# Cuantos clips seleccionados hacen falta para creerle a la seleccion.
#
# Hiero AUTOSELECCIONA el clip que esta bajo el playhead: parado sobre un shot
# y sin haber hecho click en nada, selection() ya devuelve UN item. O sea que
# "un clip seleccionado" y "ningun clip seleccionado" son indistinguibles desde
# la API, y por eso la tool tomaba la autoseleccion como si fuera una eleccion
# del usuario y nunca llegaba a mirar los demas tracks.
#
# Con DOS o mas, en cambio, la seleccion es deliberada: eso no lo hace solo.
SELECCION_MINIMA = 2

# Extensiones que se aceptan al barrer por playhead. El barrido mira TODOS los
# tracks, asi que sin filtro se lleva puesto lo que no es un plate -un EditRef
# .mov, un audio-, y la cadena del .amf no tiene sentido ahi.
#
# NO se aplica a la seleccion explicita: si el usuario eligio esos clips a
# mano, manda el. El filtro esta para el barrido a ciegas, no para
# contradecirlo.
PLAYHEAD_EXTENSIONS = (".exr",)

# La corrida SIEMPRE deja su log, este o no prendido el debug por consola. Sin
# esto la tool era una caja negra: si no hacia nada, no habia donde mirar por
# que -y justamente el caso mas comun, "el clip ya tenia los efectos y se
# saltearon", es silencioso-.
LOG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "logs", "DebugPy_LGA_NKS_ApplyAMF.log"
)

_LOG_LINES = []


def debug_print(*message):
    """Acumula para el .log y, si DEBUG, ademas escribe en la consola."""
    linea = " ".join(str(m) for m in message)
    _LOG_LINES.append(linea)
    if DEBUG:
        print(linea)


def _volcar_log():
    """Escribe el log de la corrida, pisando el anterior. Nunca rompe la tool."""
    try:
        os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
        with open(LOG_PATH, "w", encoding="utf-8", newline="\n") as handle:
            handle.write("\n".join(_LOG_LINES) + "\n")
    except Exception:
        pass
    del _LOG_LINES[:]


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


def _guid(obj):
    """guid() del objeto, para comparar identidad entre dos barridos distintos."""
    try:
        return obj.guid()
    except Exception:
        return None


def _node_class(effect):
    """Clase del nodo de un EffectTrackItem ('OCIOCDLTransform', ...)."""
    node = _safe_call(effect, "node", None)
    try:
        return node.Class() if node else None
    except Exception:
        return None


def _node_file(effect):
    """Valor del knob file, para poder mostrar a que archivo apunta el efecto."""
    node = _safe_call(effect, "node", None)
    if not node:
        return None
    try:
        return node["file"].value()
    except Exception:
        return None


def scan_clip_effects(track_item):
    """Todos los soft effects que afectan al clip, con como fueron encontrados.

    Hay dos formas de que un efecto quede sobre un clip y solo una figura en
    linkedItems():

      - LINKEADO: creado con createEffect(trackItem=...). Se mueve con el clip.
      - SUELTO: creado con timelineIn/timelineOut, o arrastrado a mano en la
        UI. Vive en un subtrack del track y afecta al clip por solaparse en
        tiempo, pero el clip no sabe nada de el.

    Si solo miraramos linkedItems(), un efecto hecho a mano no se veria y el
    boton crearia un duplicado encima.

    Devuelve una lista de dicts con effect, class, linked, same_range, in, out
    y file.
    """
    resultado = []
    vistos = set()

    try:
        clip_in = track_item.timelineIn()
        clip_out = track_item.timelineOut()
    except Exception as e:
        debug_print(f"  [WARN] No se pudo leer el rango del clip: {e}")
        clip_in = clip_out = None

    def _agregar(effect, linked):
        guid = _guid(effect)
        if guid is not None and guid in vistos:
            return
        if guid is not None:
            vistos.add(guid)
        try:
            efecto_in = effect.timelineIn()
            efecto_out = effect.timelineOut()
        except Exception:
            efecto_in = efecto_out = None
        resultado.append(
            {
                "effect": effect,
                "class": _node_class(effect),
                "linked": linked,
                "same_range": (
                    clip_in is not None
                    and efecto_in == clip_in
                    and efecto_out == clip_out
                ),
                "in": efecto_in,
                "out": efecto_out,
                "file": _node_file(effect),
            }
        )

    # 1. Los linkeados al clip.
    try:
        for item in track_item.linkedItems():
            if isinstance(item, hiero.core.EffectTrackItem):
                _agregar(item, linked=True)
    except Exception as e:
        debug_print(f"  [WARN] No se pudo leer linkedItems(): {e}")

    # 2. Los sueltos del track que se solapan en tiempo con el clip.
    track = track_item.parent()
    if track and clip_in is not None:
        try:
            sub_tracks = track.subTrackItems()
        except Exception as e:
            debug_print(f"  [WARN] No se pudo leer subTrackItems(): {e}")
            sub_tracks = ()

        for sub_track in sub_tracks:
            items = sub_track if isinstance(sub_track, (list, tuple)) else [sub_track]
            for item in items:
                if not isinstance(item, hiero.core.EffectTrackItem):
                    continue
                try:
                    if item.timelineIn() <= clip_out and item.timelineOut() >= clip_in:
                        _agregar(item, linked=False)
                except Exception:
                    continue

    return resultado


def report_clip_effects(efectos):
    """Vuelca lo que hay sobre el clip antes de tocar nada."""
    if not efectos:
        debug_print("  [EFECTOS EN EL CLIP] ninguno")
        return

    debug_print(f"  [EFECTOS EN EL CLIP] {len(efectos)}")
    for info in efectos:
        origen = "linkeado" if info["linked"] else "suelto en el track"
        rango = f"{info['in']}-{info['out']}"
        exacto = "" if info["same_range"] else " (otro rango que el clip)"
        debug_print(
            f"      {info['class'] or '<sin nodo>':<20} {origen:<18} {rango}{exacto}"
        )
        if info["file"]:
            debug_print(f"      {'':<20} file: {info['file']}")


def find_existing_effect(efectos, effect_type):
    """El efecto de ese tipo que ya esta sobre el clip, o None.

    Cuenta como propio del clip el que esta linkeado y el que cubre exactamente
    su rango. Uno que solapa parcial se reporta pero no bloquea: puede ser un
    grade que abarca varios clips del track y no tiene por que ser este.
    """
    for info in efectos:
        if info["class"] != effect_type:
            continue
        if info["linked"] or info["same_range"]:
            return info
    return None


def create_effect_on_track_item(track_item, effect_type, sub_track_index):
    """Crea un soft effect linkeado al TrackItem. Devuelve el EffectTrackItem o None.

    `sub_track_index` NO es opcional a proposito. La doc de createEffect dice:
    "subTrackIndex - if specified, will be placed on the appropriate sub-track,
    otherwise will be placed on a NEW sub-track". O sea que sin pasarlo, CADA
    llamada abre un subtrack nuevo en vez de reusar el que ya esta.

    Eso dejaba un hueco VERTICAL en el track: el primer clip con AMF ocupaba
    los subtracks 0 y 1, y el segundo clip -que en s0 y s1 tiene lugar libre,
    porque los del primero estan en otro rango de tiempo- se iba igual a s1 y
    s2, dejando s0 vacio debajo de sus efectos. Se veia como una franja muerta
    entre el clip y sus propios efectos, y crecia con cada clip.

    Pasando el indice, todos los clips del track usan los MISMOS dos subtracks
    y la cadena queda pegada al clip en todos.
    """
    track = track_item.parent()
    if not track:
        debug_print("    [ERROR] El clip no tiene track padre.")
        return None

    if not hasattr(track, "createEffect"):
        debug_print("    [ERROR] El track no expone createEffect(). Version de Hiero muy vieja.")
        return None

    # Intento 1: linkeado al trackItem (hereda el timing del clip).
    try:
        effect = track.createEffect(
            effectType=effect_type,
            trackItem=track_item,
            subTrackIndex=sub_track_index,
        )
        if effect:
            debug_print(
                f"    [OK] Creado y linkeado: {_safe_name(effect)} (subtrack {sub_track_index})"
            )
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
            subTrackIndex=sub_track_index,
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


def apply_effect(track_item, spec, efectos_existentes, sub_track_index):
    """Crea el soft effect si falta. Devuelve 'creado', 'salteado' o 'error'.

    `sub_track_index` es la posicion del efecto en la cadena del .amf, y se
    usa tal cual como subtrack: asi el mismo eslabon cae siempre en el mismo
    subtrack en todos los clips del track.
    """
    effect_type = spec["type"]
    debug_print(f"\n  --- {effect_type} ---")

    if SKIP_IF_EXISTS:
        existente = find_existing_effect(efectos_existentes, effect_type)
        if existente:
            origen = "linkeado" if existente["linked"] else "suelto en el track"
            debug_print(
                f"    [SALTEADO] El clip ya tiene un {effect_type} ({origen}): "
                f"'{_safe_name(existente['effect'])}'"
            )
            if existente["file"]:
                debug_print(f"               apunta a: {existente['file']}")
            return "salteado"

    debug_print(f"    archivo   : {spec['file']}")
    if spec.get("cccid"):
        debug_print(f"    cccid     : {spec['cccid']}")

    effect = create_effect_on_track_item(track_item, effect_type, sub_track_index)
    if not effect:
        return "error"

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

    return "creado" if ok else "error"


# ============================
# Borrado (la otra mitad del toggle)
# ============================


def _remove_options():
    """La opcion que impide que borrar el efecto se lleve puesto el CLIP.

    Esto NO es defensivo de mas: los efectos de esta tool se crean con
    createEffect(trackItem=...), o sea LINKEADOS al clip, y
    removeSubTrackItem por defecto borra tambien lo linkeado. Sin esta
    opcion, apretar el boton para sacar los efectos borraria el clip del
    timeline.

    Medido en +Building_Blocks/Hiero/Timeline/LGA_H-DeleteAll_TransformSoftEffects.py.

    Si la enum no esta (otra version de Hiero), se devuelve None y el
    borrado se CANCELA. No hay fallback a removeSubTrackItem(effect) a
    secas: ese "fallback" es justamente el accidente.
    """
    try:
        return hiero.core.TrackBase.RemoveItemOptions.eDontRemoveLinkedItems
    except Exception as e:
        debug_print("  [ERROR] No se pudo obtener eDontRemoveLinkedItems: %s" % e)
        return None


def _apunta_al_look(info):
    """True si el efecto carga un archivo de la carpeta de look del shot.

    Es lo que distingue un efecto NUESTRO de uno que el usuario puso a
    mano: los que crea esta tool siempre quedan con el knob file apuntando
    a <shot>/_input/Look_Files/. Un OCIOCDLTransform que alguien agrego
    por su cuenta -para probar un grade, con el archivo vacio o con un
    .cdl de otro lado- no cae ahi.

    Sin esto alcanzaba con que la clase del nodo coincidiera, y el toggle
    borraba trabajo ajeno.

    Se prefirio esto antes que marcar los efectos propios con un tag: los
    timelines que ya existen tienen efectos creados por las versiones
    anteriores, sin tag, y una marca nueva los dejaria fuera del alcance
    del boton. La ruta, en cambio, ya esta puesta desde la v0.20.
    """
    ruta = info.get("file") or ""
    if not ruta:
        return False
    normalizada = re.sub(r"[\\/]+", "/", str(ruta)).lower()
    return ("/%s/" % LOOK_DIR_NAME.lower()) in normalizada


def collect_amf_effects(track_item):
    """Los efectos de ESTA tool que hay sobre el clip.

    Tres condiciones, y las tres tienen que darse:

      1. La clase del nodo es una de las que crea la tool.
      2. Esta linkeado al clip, o cubre exactamente su rango. Un efecto
         que solapa PARCIAL queda afuera a proposito: puede ser un grade
         que abarca varios clips del track.
      3. Apunta a la carpeta de look del shot (ver _apunta_al_look).

    La condicion 3 NO esta del lado de la creacion, y la asimetria es
    deliberada: para CREAR, un efecto ajeno de la misma clase igual
    cuenta y frena la creacion, porque apilar dos grades encima del
    mismo clip es peor que no hacer nada. Los dos lados erran hacia no
    tocar lo que el usuario puso a mano.
    """
    return [
        info
        for info in scan_clip_effects(track_item)
        if info["class"] in AMF_EFFECT_TYPES
        and (info["linked"] or info["same_range"])
        and _apunta_al_look(info)
    ]


def clip_has_amf(track_item):
    """True si el clip ya tiene al menos un efecto de la cadena AMF."""
    try:
        return bool(collect_amf_effects(track_item))
    except Exception as e:
        debug_print("  [WARN] No se pudo mirar '%s': %s" % (_safe_name(track_item), e))
        return False


def remove_amf_effects(track_items):
    """Saca la cadena AMF de todos los clips. Devuelve (borrados, errores).

    Los efectos se juntan primero y se borran despues, deduplicados por
    guid: un mismo efecto puede aparecer al mirar dos clips distintos, y
    borrarlo dos veces es un error garantizado.
    """
    opciones = _remove_options()
    if opciones is None:
        debug_print("[ERROR] Borrado cancelado: sin eDontRemoveLinkedItems se borraria el clip.")
        return 0, 1

    # guid -> (track, effect). El guid es lo unico que identifica al mismo
    # efecto encontrado desde dos clips.
    objetivo = {}
    for track_item in track_items:
        track = track_item.parent()
        if not track:
            continue
        for info in collect_amf_effects(track_item):
            effect = info["effect"]
            clave = _guid(effect)
            if clave is None:
                clave = id(effect)
            if clave not in objetivo:
                objetivo[clave] = (track, effect, info["class"])

    debug_print("\n  [A BORRAR] %d efecto(s)" % len(objetivo))

    borrados = 0
    errores = 0
    for track, effect, clase in objetivo.values():
        nombre = _safe_name(effect)
        try:
            track.removeSubTrackItem(effect, opciones)
            borrados += 1
            debug_print("    [OK] borrado %-20s %s" % (clase or "<sin nodo>", nombre))
        except Exception as e:
            errores += 1
            debug_print("    [ERROR] no se pudo borrar '%s': %s" % (nombre, e))
            debug_print(traceback.format_exc())

    return borrados, errores


# ============================
# Proceso por clip
# ============================


def _anotar_fallo(fallos, shot, motivo):
    """Registra el motivo por el que un shot no se pudo resolver.

    Se queda con el PRIMER motivo de cada shot: si el shot no tiene
    Look_Files, todos sus clips van a fallar por lo mismo y no aporta
    nada repetirlo.
    """
    if shot not in fallos:
        fallos[shot] = motivo


def _avisar_fallos(fallos, total_clips):
    """UN cartel al final con los shots que no se pudieron resolver.

    Uno solo y por shot, no por clip: con una seleccion de veinte clips de
    cinco shots, veinte carteles -o veinte lineas repetidas- no se leen.
    """
    if not fallos:
        return

    # El texto va en ingles, como todo lo visible del pack.
    plural = "s" if len(fallos) > 1 else ""
    lineas = [
        "Apply AMF could not run on %d shot%s:" % (len(fallos), plural),
        "",
    ]
    MAX = 12
    for shot in sorted(fallos)[:MAX]:
        lineas.append("    %s  -  %s" % (shot, fallos[shot]))
    if len(fallos) > MAX:
        lineas.append("    ... and %d more" % (len(fallos) - MAX))
    lineas.append("")
    lineas.append(
        "The look files live in <shot>/%s/%s (.amf, .cdl and .clf)."
        % (INPUT_DIR_NAME, LOOK_DIR_NAME)
    )

    mensaje = "\n".join(lineas)
    debug_print("\n[AVISO AL USUARIO]\n" + mensaje)
    try:
        from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning

        show_warning(hiero.ui.mainWindow(), "Apply AMF", mensaje)
    except Exception as e:
        debug_print("[WARN] No se pudo mostrar el cartel: %s" % e)


def process_track_item(track_item, fallos):
    """Resuelve el look del clip y le crea los efectos que le falten.

    Devuelve un dict con cuantos quedaron creados, salteados y con error.

    Los motivos por los que un clip no se pudo resolver se anotan en
    `fallos`, indexados por SHOT y no por clip: un mismo shot suele tener
    clips en aPlate, bPlate y _comp_, y al usuario le sirve saber que le
    falta el look a ESE shot, no verlo repetido tres veces.
    """
    debug_print("\n" + "-" * 70)
    debug_print(f"[CLIP] {_safe_name(track_item)}")
    debug_print("-" * 70)

    resumen = {"creado": 0, "salteado": 0, "error": 0}

    track = track_item.parent()
    debug_print(f"  track                : {_safe_name(track) if track else '<sin track>'}")

    # Se mira que hay sobre el clip ANTES de tocar nada, asi el barrido no ve
    # los efectos que estamos por crear en esta misma pasada.
    efectos_existentes = scan_clip_effects(track_item)
    report_clip_effects(efectos_existentes)

    media_path = get_media_path(track_item)
    debug_print(f"  media                : {media_path}")
    if not media_path:
        _anotar_fallo(fallos, _safe_name(track_item), "the clip has no media on disk")
        resumen["error"] += 1
        return resumen

    shot_dir = resolve_shot_dir(media_path)
    debug_print(f"  shot dir             : {shot_dir}")
    if not shot_dir:
        debug_print("  [ERROR] No se pudo resolver la carpeta del shot.")
        _anotar_fallo(fallos, _safe_name(track_item), "could not resolve the shot folder")
        resumen["error"] += 1
        return resumen

    # De aca en adelante el fallo es DEL SHOT, no del clip.
    shot = os.path.basename(shot_dir.rstrip("/"))

    look_dir = resolve_look_dir(shot_dir)
    debug_print(f"  look dir             : {look_dir}")
    if not look_dir:
        _anotar_fallo(fallos, shot, f"no {LOOK_DIR_NAME} folder in {INPUT_DIR_NAME}")
        resumen["error"] += 1
        return resumen

    debug_print("  [PLAN SEGUN EL AMF]")
    plan = build_effect_plan(look_dir)
    if not plan:
        debug_print("  [ERROR] No quedo ningun efecto por aplicar en este clip.")
        _anotar_fallo(fallos, shot, f"no .cdl in {LOOK_DIR_NAME}")
        resumen["error"] += 1
        return resumen

    # Los efectos se crean en el orden del plan: el primero queda en el
    # subtrack de abajo, o sea que se aplica antes. El indice del plan ES el
    # subtrack, y va explicito: sin eso cada llamada abre un subtrack nuevo y
    # los clips terminan con sus efectos a distinta altura, con subtracks
    # vacios en el medio.
    for indice, spec in enumerate(plan):
        resumen[apply_effect(track_item, spec, efectos_existentes, indice)] += 1

    debug_print("")
    debug_print(
        f"  [CLIP LISTO] creados: {resumen['creado']} | "
        f"ya estaban: {resumen['salteado']} | errores: {resumen['error']}"
    )
    return resumen


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


def get_playhead_time():
    """Frame del playhead, o None si no hay viewer activo."""
    try:
        viewer = hiero.ui.currentViewer()
        if not viewer:
            return None
        return viewer.time()
    except Exception as e:
        debug_print("[WARN] No se pudo leer el playhead: %s" % e)
        return None


def _extension_aceptada(track_item):
    """True si la media del clip es de un tipo al que aplicarle la cadena."""
    media_path = get_media_path(track_item)
    if not media_path:
        return False
    return str(media_path).lower().endswith(PLAYHEAD_EXTENSIONS)


def get_track_items_at_playhead(seq, tiempo):
    """Los clips bajo el playhead, en TODOS los tracks, filtrados por extension.

    Los descartados por extension se loguean uno por uno: cuando el usuario
    espera que el boton toque un clip y no lo toca, tiene que poder ver por
    que en el .log en vez de quedarse con un silencio.
    """
    encontrados = []
    descartados = []
    for track in seq.videoTracks():
        try:
            items = track.items()
        except Exception:
            continue
        for item in items:
            # track.items() da clips, no efectos, pero el guard no cuesta nada
            # y esta tool no tiene por que aplicarse sobre otro soft effect.
            if isinstance(item, hiero.core.EffectTrackItem):
                continue
            if not isinstance(item, hiero.core.TrackItem):
                continue
            try:
                if not (item.timelineIn() <= tiempo <= item.timelineOut()):
                    continue
            except Exception:
                continue
            if _extension_aceptada(item):
                encontrados.append(item)
            else:
                descartados.append(item)

    for item in descartados:
        debug_print(
            "  [SALTEADO] '%s' no es %s"
            % (_safe_name(item), "/".join(PLAYHEAD_EXTENSIONS))
        )

    return encontrados


def get_target_track_items():
    """Los clips sobre los que hay que trabajar, y de donde salieron.

    La regla es por CANTIDAD, no por presencia, y el motivo es que Hiero
    autoselecciona el clip bajo el playhead (ver SELECCION_MINIMA):

      - DOS o mas clips seleccionados -> se usan esos y nada mas. Eso solo
        pasa si el usuario los eligio.
      - UNO o ninguno -> se ignora la seleccion y se barren todos los
        tracks bajo el playhead. Con un solo clip no hay forma de saber si
        lo eligio el usuario o lo puso ahi la autoseleccion, y suponer lo
        primero dejaba la tool operando sobre un track cuando el gesto
        natural -parado sobre un shot, sin seleccionar nada- es que opere
        sobre el shot entero.

    Esta regla NO depende de TOGGLE_CREATE_DELETE: ese flag decide si se
    crea o se borra, no de donde salen los clips.

    Devuelve (seq, track_items, origen), con origen en {'seleccion',
    'playhead'} para que el cartel y el log digan de donde salio la lista.
    """
    seq, seleccionados = get_selected_track_items()
    if not seq:
        return None, [], None

    if len(seleccionados) >= SELECCION_MINIMA:
        debug_print("[INFO] Seleccion deliberada: %d clips." % len(seleccionados))
        return seq, seleccionados, "seleccion"

    if len(seleccionados) == 1:
        debug_print(
            "[INFO] Un solo clip seleccionado ('%s'): puede ser la autoseleccion "
            "de Hiero, asi que se barre el playhead." % _safe_name(seleccionados[0])
        )

    tiempo = get_playhead_time()
    if tiempo is None:
        debug_print("[ERROR] No hay viewer activo: no se puede saber donde esta el playhead.")
        return seq, [], None

    track_items = get_track_items_at_playhead(seq, tiempo)
    debug_print(
        "[INFO] %d clip(s) bajo el playhead (frame %s)" % (len(track_items), tiempo)
    )
    return seq, track_items, "playhead"


def _avisar_sin_clips():
    """Cartel para cuando no hay nada sobre lo que trabajar."""
    mensaje = (
        "Nothing to work on.\n\n"
        "Place the playhead over a shot, or select two or more clips.\n"
        "Only %s clips are picked up from the playhead."
        % "/".join(ext.lstrip(".").upper() for ext in PLAYHEAD_EXTENSIONS)
    )
    debug_print("[ERROR] No hay clips ni en la seleccion ni bajo el playhead.")
    try:
        from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning

        show_warning(hiero.ui.mainWindow(), "Apply AMF", mensaje)
    except Exception as e:
        debug_print("[WARN] No se pudo mostrar el cartel: %s" % e)


def decidir_modo(track_items):
    """'borrar' si ALGUN clip objetivo ya tiene la cadena AMF; si no, 'crear'.

    La decision se toma UNA vez para toda la tanda, no clip por clip. Con
    una seleccion mezclada -tres clips con efectos y dos sin- decidir por
    clip crearia en unos y borraria en otros en la misma pasada, que es
    justo el resultado que nadie quiere ver.

    Y unifica hacia abajo (alguno prendido -> apagar todos), igual que
    LGA_NKS_ToggleAMF, para que los dos botones se comporten igual.
    """
    for track_item in track_items:
        if clip_has_amf(track_item):
            debug_print(
                "[MODO] BORRAR: '%s' ya tiene la cadena AMF." % _safe_name(track_item)
            )
            return "borrar"
    debug_print("[MODO] CREAR: ningun clip objetivo tiene la cadena AMF.")
    return "crear"


def _main_interno():
    debug_print("\n" + "=" * 70)
    debug_print("  LGA_NKS_ApplyAMF - soft effects de color segun el .amf del shot")
    debug_print(f"  desde {INPUT_DIR_NAME}/{LOOK_DIR_NAME}")
    debug_print("=" * 70)

    seq, track_items, origen = get_target_track_items()
    if not seq:
        return

    if not track_items:
        _avisar_sin_clips()
        return

    debug_print("  clips objetivo : %d (por %s)" % (len(track_items), origen))

    # --- Rama de BORRADO -------------------------------------------------
    # Sacar los efectos no necesita ni el shot ni el disco: se trabaja solo
    # con lo que ya esta en el timeline. Por eso sale por aca antes de todo
    # el camino de resolucion de rutas.
    if TOGGLE_CREATE_DELETE and decidir_modo(track_items) == "borrar":
        project = seq.project()
        if project:
            project.beginUndo("Apply AMF - remove")
        try:
            borrados, errores = remove_amf_effects(track_items)
        finally:
            if project:
                project.endUndo()

        debug_print("\n" + "=" * 70)
        debug_print("  RESUMEN (borrado) sobre %d clip(s):" % len(track_items))
        debug_print("    efectos borrados : %d" % borrados)
        debug_print("    con error        : %d" % errores)
        debug_print("=" * 70 + "\n")
        return

    # --- Rama de CREACION ------------------------------------------------
    project = seq.project()
    total = {"creado": 0, "salteado": 0, "error": 0}
    # shot -> motivo. Se llena en process_track_item y se avisa UNA vez al final.
    fallos = {}

    if project:
        project.beginUndo("Apply AMF")
    try:
        for track_item in track_items:
            try:
                for clave, cantidad in process_track_item(track_item, fallos).items():
                    total[clave] += cantidad
            except Exception as e:
                debug_print(f"[ERROR] Fallo procesando '{_safe_name(track_item)}': {e}")
                debug_print(traceback.format_exc())
                _anotar_fallo(fallos, _safe_name(track_item), "unexpected error (see the log)")
                total["error"] += 1
    finally:
        if project:
            project.endUndo()

    debug_print("\n" + "=" * 70)
    debug_print(f"  RESUMEN sobre {len(track_items)} clip(s):")
    debug_print(f"    efectos creados : {total['creado']}")
    debug_print(f"    ya estaban      : {total['salteado']}")
    debug_print(f"    con error       : {total['error']}")
    debug_print("=" * 70 + "\n")

    # El cartel va DESPUES del endUndo y del resumen: primero se termina el
    # trabajo sobre el timeline, despues se le habla al usuario.
    _avisar_fallos(fallos, len(track_items))

    # Salir sin haber hecho NADA y sin nada que avisar es el peor final: el
    # boton parece roto. Pasa cuando todos los clips ya tenian su cadena, o
    # cuando tienen un efecto de la misma clase puesto a mano -que frena la
    # creacion pero no cuenta como nuestro para borrarlo-.
    if not fallos and total["creado"] == 0 and total["error"] == 0:
        mensaje = (
            "Nothing to do: the %d selected clip%s already had their color effects.\n\n"
            "If you expected them to be removed, they were not created by Apply AMF: "
            "only effects loading a file from %s are removed."
            % (
                len(track_items),
                "s" if len(track_items) > 1 else "",
                LOOK_DIR_NAME,
            )
        )
        debug_print("\n[AVISO AL USUARIO] No se creo ni se borro nada.")
        try:
            from LGA_NKS_Shared.LGA_NKS_MessageBox import show_info

            show_info(hiero.ui.mainWindow(), "Apply AMF", mensaje)
        except Exception as e:
            debug_print("[WARN] No se pudo mostrar el cartel: %s" % e)


def main():
    """Envoltorio: corra bien o falle, la corrida SIEMPRE deja su log.

    El try/finally cubre tambien los return tempranos de _main_interno
    (sin secuencia activa, sin clips seleccionados, sin .cdl), que son
    justo los casos en los que la tool "no hace nada" y hay que poder
    ver por que.
    """
    try:
        _main_interno()
    except Exception:
        debug_print("[ERROR] Excepcion no atrapada:")
        debug_print(traceback.format_exc())
        raise
    finally:
        _volcar_log()


if __name__ == "__main__":
    main()
