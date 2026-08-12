"""
____________________________________________________________________

  LGA_NKS_Vendors_Config v1.00 | Lega

  Vendor codes por proyecto para HieroTools.

  La fuente de verdad es FLOW: los vendor codes se cargan en el Projects tab
  de PipeSync y viajan en el envelope de Project Settings. PipeSync los baja en
  su sync y los deja en `project_settings_cache.settings_json` de
  `pipesync_stats.db`, bajo la clave `vendors` (lista de strings). Este modulo
  solo lee esa tabla; misma mecanica que LGA_NKS_Project_Colors_Config.

  PARA QUE SIRVE: el naming de shots es PROYECTO_SEQ_SHOT_VENDOR, y sin saber
  cuales son los vendor codes validos no hay forma segura de distinguir ese
  cuarto bloque de una task. Ejemplo real del problema: "PROJA_1048_060_Compo"
  tiene un bloque alfabetico despues de dos numeros igual que
  "PROJA_1013_0800_VEN", pero "Compo" es una TASK. Una regla estructural los
  confunde; la lista de la DB no.

  NO HAY FALLBACK estructural ni JSON local: si la DB no tiene el proyecto o
  PipeSync nunca sincronizo, se devuelve vacio y el naming se comporta como
  antes (sin soporte de vendor). Ver LGA_NKS_Flow_NamingUtils.

  Usado por runtime activo:
  - LGA_NKS_Shared/LGA_NKS_Flow_NamingUtils.py

  v1.00: Version inicial.
____________________________________________________________________

"""

import json
import os
import sqlite3
import time

try:
    from LGA_NKS_PipeSyncPaths import get_pipesync_db_path
except ImportError:  # importado como paquete desde afuera de LGA_NKS_Shared
    from LGA_NKS_Shared.LGA_NKS_PipeSyncPaths import get_pipesync_db_path

STATS_DB_FILENAME = "pipesync_stats.db"

# Cache de proceso. El parseo de nombres corre dos veces por clip (cientos de
# veces en un pull), asi que no se puede pegar a sqlite en cada llamada. Se
# invalida sola mirando mtime+size de la DB y de su `-wal` (ver _db_stamp), para
# que un sync de PipeSync se note sin tener que reiniciar Hiero.
_cache_vendors = None
_cache_stamp = None
_cache_checked_at = None

# Cada cuanto, como maximo, se vuelve a mirar el estado de la DB. Sin esto, el
# chequeo corre 2 veces por clip (shot code + task) y resolver la ruta de la DB
# cuesta ~0.4 ms, o sea ~0.8 s de puro overhead en un pull de 400 clips. Con el
# debounce, un pull entero hace UN solo chequeo y el costo desaparece; el precio
# es que un cambio en PipeSync puede tardar hasta este tiempo en verse.
_STAMP_TTL_SEGUNDOS = 2.0


def get_vendors_db_path():
    """Ruta a la pipesync_stats.db del contexto activo (studio o client)."""
    return get_pipesync_db_path(STATS_DB_FILENAME)


def _db_stamp(db_path):
    """
    Huella de la DB para invalidar el cache: (mtime, size) del archivo principal
    Y del `-wal`.

    El `-wal` NO es opcional: pipesync_stats.db esta en journal_mode=wal, asi que
    los commits de PipeSync se escriben ahi y el .db principal no cambia ni de
    mtime ni de tamanio hasta el checkpoint, que puede tardar dias. Mirando solo
    el .db, un vendor code cargado hoy en el Projects tab no se veria hasta
    reiniciar Hiero.

    Devuelve None si no existe el archivo principal.
    """
    try:
        info = os.stat(db_path)
    except OSError:
        return None

    stamp = [info.st_mtime, info.st_size]
    try:
        wal = os.stat(db_path + "-wal")
        stamp += [wal.st_mtime, wal.st_size]
    except OSError:
        stamp += [None, None]

    return tuple(stamp)


def _extraer_vendors(settings_json):
    """Saca la lista `vendors` de un envelope de Project Settings."""
    if not settings_json:
        return []

    try:
        envelope = json.loads(settings_json)
    except (ValueError, TypeError):
        return []

    if not isinstance(envelope, dict):
        return []

    raw = envelope.get("vendors")
    if not isinstance(raw, list):
        return []

    vendors = []
    for item in raw:
        code = str(item or "").strip()
        if code:
            vendors.append(code.upper())
    return vendors


def _load_vendors_uncached():
    """
    Lee la DB y devuelve (vendors, leyo_ok).

    `leyo_ok` distingue "lei la DB y no hay datos" de "no pude leer la DB". La
    diferencia importa porque el resultado se cachea: un error transitorio
    (p. ej. `database is locked` con PipeSync escribiendo) no puede quedar
    congelado como "este proyecto no tiene vendors" hasta el proximo cambio de
    la DB. El sintoma seria exactamente el bug que este modulo vino a arreglar,
    y sin ningun aviso.
    """
    db_path = get_vendors_db_path()
    if not os.path.exists(db_path):
        # No es un error: PipeSync todavia no sincronizo en esta maquina. Se
        # cachea, porque el stamp cambia solo con que aparezca el archivo.
        return {}, True

    query = (
        "SELECT p.project_name, c.settings_json "
        "FROM projects p "
        "JOIN project_settings_cache c ON c.project_id = p.id"
    )

    connection = None
    try:
        # Read-only: HieroTools nunca escribe en la DB de PipeSync.
        connection = sqlite3.connect("file:{0}?mode=ro".format(db_path), uri=True)
        rows = connection.execute(query).fetchall()
    except sqlite3.Error:
        # Incluye el caso de que el archivo exista pero todavia no tenga las
        # tablas (OperationalError). Se reintenta en la proxima consulta.
        return {}, False
    finally:
        if connection is not None:
            connection.close()

    vendors_por_proyecto = {}
    for project_name, settings_json in rows:
        name = (project_name or "").strip()
        if not name:
            continue
        vendors_por_proyecto[name.upper()] = _extraer_vendors(settings_json)

    return vendors_por_proyecto, True


def load_project_vendors():
    """
    Devuelve {PROYECTO_EN_MAYUSCULAS: [VENDOR, ...]} para el contexto activo.

    Un proyecto sin vendors configurados aparece con lista vacia; un proyecto que
    no esta en la DB no aparece. Esa diferencia importa: ver get_vendor_codes().
    """
    global _cache_vendors, _cache_stamp, _cache_checked_at

    ahora = time.monotonic()
    if (
        _cache_vendors is not None
        and _cache_checked_at is not None
        and (ahora - _cache_checked_at) < _STAMP_TTL_SEGUNDOS
    ):
        return _cache_vendors

    _cache_checked_at = ahora
    stamp = _db_stamp(get_vendors_db_path())
    if _cache_vendors is not None and stamp == _cache_stamp:
        return _cache_vendors

    vendors, leyo_ok = _load_vendors_uncached()
    if not leyo_ok:
        # Lectura fallida: se devuelve lo que haya (o vacio) SIN cachear, asi el
        # proximo llamado reintenta en vez de quedarse pegado al error. Tambien
        # se limpia el debounce, para que el reintento no espere el TTL.
        _cache_checked_at = None
        return _cache_vendors if _cache_vendors is not None else {}

    _cache_vendors = vendors
    _cache_stamp = stamp
    return _cache_vendors


def refresh_vendors_cache():
    """Fuerza la relectura de la DB en la proxima consulta."""
    global _cache_vendors, _cache_stamp, _cache_checked_at
    _cache_vendors = None
    _cache_stamp = None
    _cache_checked_at = None


def get_vendor_codes(project_name):
    """
    Devuelve el set de vendor codes (en mayusculas) validos para un proyecto.

    Si el proyecto SI esta en la DB, se devuelven SOLO sus vendors (un set vacio
    si no tiene ninguno cargado): ahi la DB es la respuesta correcta y no hay
    que inventar.

    Si el proyecto NO esta en la DB, se devuelve la union de los vendors de
    todos los proyectos. Es un compromiso deliberado:

    - A favor: el nombre que llega puede no coincidir con el de la DB. El
      prefijo del filename y el segmento VFX-NOMBRE de la ruta no siempre son
      iguales (ver extract_project_name_from_path), y _analyze_shotname solo
      tiene el filename. Sin la union, esos proyectos se quedarian sin soporte
      de vendor y volveria el bug original.
    - En contra: si algun dia se registra un vendor code que coincide con una
      palabra que OTRO proyecto usa como bloque de descripcion, ese otro
      proyecto empieza a parsear mal. Hoy no pasa, pero es la falla a vigilar si
      aparece un shot code raro despues de agregar un vendor nuevo.
    """
    vendors_por_proyecto = load_project_vendors()
    if not vendors_por_proyecto:
        return set()

    target = (project_name or "").strip().upper()
    if target in vendors_por_proyecto:
        return set(vendors_por_proyecto[target])

    todos = set()
    for codes in vendors_por_proyecto.values():
        todos.update(codes)
    return todos


def is_vendor_code(block, project_name=None):
    """True si `block` es un vendor code conocido (del proyecto, o de cualquiera)."""
    code = (block or "").strip().upper()
    if not code:
        return False
    return code in get_vendor_codes(project_name)
