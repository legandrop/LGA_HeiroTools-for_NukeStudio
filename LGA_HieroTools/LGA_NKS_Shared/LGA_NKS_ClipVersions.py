"""
____________________________________________________________________

  LGA_NKS_ClipVersions v1.00 | Lega

  Cambio de version de un clip del timeline, acotado a su rama.

  Reemplaza el bloque get_highest_version + change_to_highest_version que
  estaba copiado identico ("COPIADO EXACTO del Pull") en MatchVerToEXR,
  CompareVerToEditref y CompareEXR_to_aPlate. Las tres copias hacian
  max() sobre todas las versiones del bin y por lo tanto podian saltar a
  la rama de otro compositor.

  Flow Pull y el watcher de Download Clip tienen su propia version de
  esta operacion porque agregan manejo de clips offline (reconnectMedia /
  refresh) y logging propio; comparten la regla de ramas, no el codigo.

  v1.00: Version inicial.
____________________________________________________________________
"""

from LGA_NKS_VersionBranching import extract_version_number, head_of_branch_containing


def local_version_numbers(bin_item):
    """Numeros de version que Hiero ya conoce del binItem."""
    try:
        return [extract_version_number(version.name()) for version in bin_item.items()]
    except Exception:
        return []


def pick_branch_version(bin_item, current_version, target_version=None):
    """Version del bin a la que conviene cambiar.

    - `target_version`: si esa version existe, se usa tal cual (es lo que
      pidio el llamador, por ejemplo igualar la version del EXR).
    - Si no, la cabeza de la rama de `current_version`. Nunca el maximo
      global: puede ser de la rama de otro compositor.
    """
    try:
        versions = list(bin_item.items())
    except Exception:
        return None
    if not versions:
        return None

    numbers = [extract_version_number(version.name()) for version in versions]

    if target_version is not None:
        for version, number in zip(versions, numbers):
            if number == target_version:
                return version

    head = head_of_branch_containing(numbers, current_version)
    for version, number in zip(versions, numbers):
        if number == head:
            return version
    return None


def switch_clip_to_version(clip, target_version=None, debug=None):
    """Escanea versiones y cambia el clip, sin salirse de su rama.

    Devuelve la Version aplicada o None. `debug` es un callable opcional
    para loguear con el debug_print del script llamador.
    """

    def _log(message):
        if debug:
            debug(message)

    try:
        import hiero.core
    except Exception as e:
        _log(f"hiero.core no disponible para versionado: {e}")
        return None

    try:
        bin_item = clip.source().binItem()
    except Exception as e:
        _log(f"No se pudo obtener binItem: {e}")
        return None
    if not bin_item:
        return None

    try:
        active_version = bin_item.activeVersion()
    except Exception:
        active_version = None
    if not active_version:
        _log("El clip no tiene version activa")
        return None

    current_version = extract_version_number(active_version.name())

    try:
        scanner = hiero.core.VersionScanner()
        scanner.doScan(active_version)
    except Exception as scan_error:
        _log(f"VersionScanner.doScan fallo: {scan_error}")

    chosen = pick_branch_version(
        bin_item, current_version, target_version=target_version
    )
    if not chosen:
        _log("No se pudo determinar la version destino")
        return None

    try:
        bin_item.setActiveVersion(chosen)
        _log(f"setActiveVersion: {active_version.name()} -> {chosen.name()}")
    except Exception as set_error:
        _log(f"No se pudo setActiveVersion: {set_error}")
        return None

    return chosen
