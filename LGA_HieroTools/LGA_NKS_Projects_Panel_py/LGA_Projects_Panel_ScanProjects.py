# -*- coding: utf-8 -*-
"""
____________________________________________________________________

  LGA_Projects_Panel_ScanProjects v1.07 | Lega

  Módulo de escaneo reutilizable para el Panel de Proyectos LGA.
  - Escanea proyectos en disco
  - Obtiene información de proyectos abiertos en Hiero
  - Verifica si un proyecto está abierto
  - Obtiene secuencias de un proyecto

  v1.07: La clave de agrupacion se delega en LGA_NKS_CheckProjectVersions
  v1.06: Los proyectos abiertos se filtran por el root del contexto activo
  v1.05: Agregado 'project_key' (proyecto de trabajo segun la carpeta VFX-) a cada resultado
  v1.04: Soporte para varios proyectos por carpeta SUP, con su version mas alta cada uno
  v1.03: Normalizados paths, barras y filtros case-insensitive para VFX/SUP/.hrox
  v1.02: Agregados logs de diagnostico para AltTPath, base_path y filtros VFX/SUP
  v1.01: Conectado al logger compartido del Projects Panel para respetar flags y salida a archivo
  v1.00: Versión inicial del módulo de escaneo reutilizable
____________________________________________________________________

"""

import hiero.core
import hiero.ui
import os
import re
import sys
from pathlib import Path
from LGA_NKS_Projects_Panel_py.LGA_NKS_ProjectsPanel_Logging import debug_print
from LGA_NKS_Shared.LGA_NKS_ContextProfile import is_client_context

# Importar funciones de manejo de versiones desde código existente
lga_nks_path = None
script_dir = Path(__file__).resolve().parent

if (script_dir / "LGA_NKS_CheckProjectVersions.py").exists():
    lga_nks_path = script_dir

for path_str in sys.path:
    if lga_nks_path is not None:
        break
    try:
        path = Path(path_str)
        test_file = path / "LGA_NKS_CheckProjectVersions.py"
        if test_file.exists():
            lga_nks_path = path
            break
        if path.parent.exists():
            test_file_parent = path.parent / "LGA_NKS_CheckProjectVersions.py"
            if test_file_parent.exists():
                lga_nks_path = path.parent
                break
        if path.exists() and (path / "LGA_NKS" / "LGA_NKS_CheckProjectVersions.py").exists():
            lga_nks_path = path / "LGA_NKS"
            break
    except Exception:
        continue

if lga_nks_path is None or not lga_nks_path.exists():
    if '__file__' in globals() and __file__:
        try:
            script_dir = Path(__file__).resolve().parent
            potential_startup = script_dir.parent
            potential_lga_nks = potential_startup / "LGA_NKS"
            if (potential_lga_nks / "LGA_NKS_CheckProjectVersions.py").exists():
                lga_nks_path = potential_lga_nks
        except Exception:
            pass

if lga_nks_path is None or not lga_nks_path.exists():
    standard_paths = [
        Path.home() / ".nuke" / "Python" / "Startup" / "LGA_NKS",
        Path(os.path.expanduser("~")) / ".nuke" / "Python" / "Startup" / "LGA_NKS",
    ]
    for test_path in standard_paths:
        if (test_path / "LGA_NKS_CheckProjectVersions.py").exists():
            lga_nks_path = test_path
            break

if lga_nks_path and lga_nks_path.exists():
    if str(lga_nks_path) not in sys.path:
        sys.path.insert(0, str(lga_nks_path))

try:
    from LGA_NKS_CheckProjectVersions import (
        extraer_version,
        comparar_versiones,
        encontrar_version_mas_alta,
        obtener_nombre_base_proyecto,
        obtener_version_completa,
        obtener_clave_proyecto_archivo,
    )
except ImportError as e:
    raise ImportError(f"No se pudo importar funciones de LGA_NKS_CheckProjectVersions: {e}")


def normalize_scan_path(path_value):
    """Normaliza un path de escaneo sin alterar el casing real de carpetas listadas."""
    if path_value is None:
        return None

    normalized = os.path.expanduser(str(path_value).strip().strip('"').strip("'"))
    if not normalized:
        return ""

    normalized = normalized.replace("/", os.sep).replace("\\", os.sep)
    normalized = os.path.normpath(normalized)

    if re.match(r"^[A-Za-z]:$", normalized):
        normalized += os.sep

    return normalized


def _is_vfx_folder_name(name):
    return str(name).casefold().startswith("vfx-")


def _is_sup_folder_name(name):
    return str(name).casefold().endswith("_sup")


def _is_hrox_file_name(name):
    return str(name).casefold().endswith(".hrox")


def obtener_clave_proyecto(ruta=None, nombre_base=""):
    """
    Devuelve el nombre del proyecto de trabajo al que pertenece un .hrox.

    Sale de la carpeta 'VFX-<proyecto>' de la ruta, porque varios .hrox distintos
    de una misma carpeta SUP pertenecen al mismo proyecto: ERSO_SUP y
    ERSO_Breakdown son los dos ERSO y comparten el color del .ini.
    Si la ruta no sirve, se cae al nombre base recortado en '_SUP'.
    """
    if ruta:
        partes = str(ruta).replace("/", os.sep).replace("\\", os.sep).split(os.sep)
        for parte in partes:
            if _is_vfx_folder_name(parte):
                return parte[4:]  # Saca el prefijo 'VFX-' sin depender del casing

    nombre_base = str(nombre_base or "")
    posicion_sup = nombre_base.upper().find("_SUP")
    if posicion_sup > 0:
        return nombre_base[:posicion_sup]

    return nombre_base


def _clave_agrupacion_proyecto(hrox_file):
    """
    Clave para agrupar versiones del mismo proyecto, ignorando version y sufijos.

    'ERSO_SUP_v040' y 'ERSO_SUP_v41_Mac' comparten clave; 'ERSO_Breakdown_v004' no.
    Delega en LGA_NKS_CheckProjectVersions para que el escaneo y la busqueda de
    version mas alta usen exactamente el mismo criterio.
    """
    return obtener_clave_proyecto_archivo(hrox_file)


def _agrupar_hrox_por_proyecto(hrox_files):
    """
    Agrupa archivos .hrox por proyecto, preservando el orden de aparicion.

    Una misma carpeta SUP puede contener varios proyectos distintos (por ejemplo
    ERSO_SUP_v040.hrox y ERSO_Breakdown_v004.hrox). Cada uno es un grupo aparte,
    para que despues se elija la version mas alta de cada uno.

    Returns:
        dict: clave = clave de agrupacion, valor = lista de rutas .hrox
    """
    grupos = {}

    for hrox_file in hrox_files:
        clave = _clave_agrupacion_proyecto(hrox_file)
        grupos.setdefault(clave, []).append(hrox_file)

    return grupos


def _elegir_version_mas_alta(hrox_files):
    """
    Elige el .hrox de version mas alta dentro de una lista de archivos del mismo proyecto.

    Returns:
        tuple: (ruta del archivo elegido | None, version completa para mostrar)
    """
    mejor_archivo = None
    mejor_version = None

    for archivo in hrox_files:
        version = extraer_version(archivo)
        if version in ["No detectada", "Error"]:
            continue

        if mejor_version is None:
            mejor_version = version
            mejor_archivo = archivo
            continue

        version_ganadora = comparar_versiones(mejor_version, version)
        if version_ganadora != mejor_version:
            mejor_version = version
            mejor_archivo = archivo

    if mejor_archivo is None:
        # Ningun archivo del grupo tiene version legible: usar el primero como fallback
        mejor_archivo = hrox_files[0] if hrox_files else None

    if mejor_archivo is None:
        return None, "No detectada"

    return mejor_archivo, obtener_version_completa(mejor_archivo)


def _list_hrox_files(folder_path):
    try:
        return [
            os.path.join(folder_path, item)
            for item in os.listdir(folder_path)
            if os.path.isfile(os.path.join(folder_path, item)) and _is_hrox_file_name(item)
        ]
    except Exception as e:
        debug_print(f"      ⚠️ Error listando archivos .hrox en {folder_path}: {type(e).__name__}: {e}")
        return []


def get_base_scan_path(default_path=None):
    """
    Obtiene la ruta base para escaneo desde PipeSync (AltTPath) si existe y es valida.
    Si no hay configuracion o la ruta no existe, usa el default.
    """
    if default_path is None:
        default_path = "N:\\" if is_client_context() else "T:\\"

    try:
        from LGA_NKS_Shared.SecureConfig_Reader import read_secure_config
    except Exception as e:
        debug_print(f"⚠️ No se pudo importar SecureConfig_Reader: {e}")
        return normalize_scan_path(default_path)

    config = read_secure_config()
    if not isinstance(config, dict):
        debug_print("⚠️ Configuracion segura no disponible; usando default.")
        return normalize_scan_path(default_path)

    app_cfg = config.get("App", {})
    debug_print(f"🔎 Config segura leida. Secciones disponibles: {sorted(config.keys())}")
    if isinstance(app_cfg, dict):
        debug_print(f"🔎 Config App keys: {sorted(app_cfg.keys())}")
    else:
        debug_print(f"⚠️ Config App no es dict: {type(app_cfg).__name__}")

    alt_path = app_cfg.get("AltTPath") if isinstance(app_cfg, dict) else None
    debug_print(f"🔎 AltTPath raw: {repr(alt_path)}")
    if not alt_path:
        debug_print("⚠️ AltTPath no configurado; usando default.")
        return normalize_scan_path(default_path)

    alt_path = normalize_scan_path(alt_path)
    debug_print(f"🔎 AltTPath normalizado: {repr(alt_path)}")
    debug_print(f"🔎 AltTPath exists={os.path.exists(alt_path)} isdir={os.path.isdir(alt_path)}")
    if os.path.isdir(alt_path):
        debug_print(f"✅ Usando AltTPath normalizado: {alt_path}")
        return alt_path

    debug_print(f"⚠️ AltTPath configurado pero no existe: {alt_path}")
    return normalize_scan_path(default_path)


def _log_base_path_diagnostics(base_path):
    """Loguea diagnostico de acceso/listado para entender fallas de escaneo."""
    try:
        debug_print(f"🧭 cwd: {os.getcwd()}")
    except Exception as e:
        debug_print(f"⚠️ No se pudo obtener cwd: {e}")

    try:
        debug_print(f"🧭 base_path repr: {repr(base_path)}")
        debug_print(f"🧭 base_path abspath: {os.path.abspath(base_path)}")
        debug_print(f"🧭 base_path normpath: {os.path.normpath(base_path)}")
        debug_print(f"🧭 base_path exists={os.path.exists(base_path)} isdir={os.path.isdir(base_path)}")
    except Exception as e:
        debug_print(f"⚠️ No se pudo diagnosticar base_path: {e}")


def scan_projects_on_disk(base_path=None):
    """
    Escanea el disco buscando proyectos VFX y retorna información de cada uno.

    Busca carpetas tipo 'VFX-' y dentro carpetas '*_SUP' sin depender del casing.
    En cada carpeta SUP puede haber varios proyectos distintos (por ejemplo
    ERSO_SUP y ERSO_Breakdown): se agrupan por nombre base y se devuelve la
    versión más alta de cada uno, como entradas separadas.

    Args:
        base_path (str|None): Ruta base donde buscar proyectos. Si es None,
            se usa AltTPath de PipeSync cuando existe, o "T:\\" como fallback.

    Returns:
        list: Lista de diccionarios con información de proyectos encontrados.
              Cada diccionario contiene:
              - nombre_base (str): Nombre base del proyecto (ej: "BRDA_SUP")
              - vfx_folder (str): Nombre de la carpeta VFX (ej: "VFX-BRDA")
              - sup_folder (str): Nombre de la carpeta SUP (ej: "BRDA_SUP")
              - ruta_hrox (str): Ruta completa del archivo .hrox con versión más alta
              - version (str): Versión extraída (ej: "v050")
              - ruta_proyecto (str): Ruta completa de la carpeta SUP
    """
    if base_path is None:
        base_path = get_base_scan_path()
    else:
        original_base_path = base_path
        base_path = normalize_scan_path(base_path)
        debug_print(f"🔧 Base path recibido normalizado: {repr(original_base_path)} -> {repr(base_path)}")

    debug_print("🔍 Iniciando escaneo de proyectos en:", base_path)
    _log_base_path_diagnostics(base_path)
    proyectos_encontrados = []
    
    if not os.path.exists(base_path):
        debug_print(f"❌ Base path no existe, se omite escaneo: {base_path}")
        return proyectos_encontrados
    if not os.path.isdir(base_path):
        debug_print(f"❌ Base path existe pero no es directorio, se omite escaneo: {base_path}")
        return proyectos_encontrados
    
    try:
        # Buscar carpetas que empiecen con VFX-
        items = os.listdir(base_path)
        debug_print(f"📋 os.listdir({repr(base_path)}) devolvio {len(items)} item(s)")
        debug_print(f"📋 Primeros items top-level: {items[:50]}")
        vfx_like_items = [item for item in items if "vfx" in item.casefold()]
        debug_print(f"📋 Items que contienen 'vfx' (case-insensitive): {vfx_like_items}")

        for item in sorted(items, key=lambda value: value.casefold()):
            item_path = os.path.join(base_path, item)
            try:
                is_dir = os.path.isdir(item_path)
                starts_exact = item.startswith("VFX-")
                starts_ci = _is_vfx_folder_name(item)
                debug_print(
                    f"   🔎 Top-level item: {repr(item)} "
                    f"isdir={is_dir} startswith_VFX_exact={starts_exact} "
                    f"startswith_VFX_casefold={starts_ci}"
                )
            except Exception as e:
                debug_print(f"   ⚠️ Error evaluando item top-level {repr(item)}: {e}")

        vfx_folders = [
            item
            for item in items
            if os.path.isdir(os.path.join(base_path, item)) and _is_vfx_folder_name(item)
        ]
        debug_print(f"📁 Encontradas {len(vfx_folders)} carpetas VFX:", vfx_folders)
        if vfx_folders:
            debug_print("✅ Filtro VFX case-insensitive aplicado. Se conservan los nombres reales del disco.")
        elif vfx_like_items:
            debug_print("⚠️ Hay items tipo VFX pero ninguno paso el filtro case-insensitive.")
        
        for vfx_folder in sorted(vfx_folders, key=lambda value: value.casefold()):
            vfx_path = os.path.join(base_path, vfx_folder)
            debug_print(f"🔍 Procesando VFX: {vfx_folder}")

            try:
                # Buscar carpetas que terminen con _SUP
                subitems = os.listdir(vfx_path)
                debug_print(f"   📋 os.listdir({repr(vfx_path)}) devolvio {len(subitems)} item(s)")
                debug_print(f"   📋 Primeros items dentro de VFX: {subitems[:50]}")
                sup_like_items = [item for item in subitems if "sup" in item.casefold()]
                debug_print(f"   📋 Items que contienen 'sup' (case-insensitive): {sup_like_items}")
                for item in sorted(subitems, key=lambda value: value.casefold()):
                    item_path = os.path.join(vfx_path, item)
                    try:
                        is_dir = os.path.isdir(item_path)
                        ends_exact = item.endswith("_SUP")
                        ends_ci = _is_sup_folder_name(item)
                        debug_print(
                            f"      🔎 VFX child item: {repr(item)} "
                            f"isdir={is_dir} endswith_SUP_exact={ends_exact} "
                            f"endswith_SUP_casefold={ends_ci}"
                        )
                    except Exception as e:
                        debug_print(f"      ⚠️ Error evaluando item VFX {repr(item)}: {e}")

                sup_folders = [
                    item
                    for item in subitems
                    if os.path.isdir(os.path.join(vfx_path, item)) and _is_sup_folder_name(item)
                ]
                debug_print(f"   📂 Encontradas {len(sup_folders)} carpetas SUP:", sup_folders)
                if sup_folders:
                    debug_print("   ✅ Filtro SUP case-insensitive aplicado. Se conservan los nombres reales del disco.")
                elif sup_like_items:
                    debug_print("   ⚠️ Hay items tipo SUP pero ninguno paso el filtro case-insensitive.")
                
                for sup_folder in sorted(sup_folders, key=lambda value: value.casefold()):
                    sup_path = os.path.join(vfx_path, sup_folder)
                    debug_print(f"   🔎 Procesando SUP: {sup_folder}")

                    # Buscar archivos .hrox sin depender del casing de la extension
                    hrox_files = _list_hrox_files(sup_path)
                    debug_print(f"      📄 Encontrados {len(hrox_files)} archivos .hrox:", [os.path.basename(f) for f in hrox_files])
                    
                    if not hrox_files:
                        debug_print(f"      ⚠️ No se encontraron archivos .hrox en {sup_path}")
                        continue

                    # Una carpeta SUP puede tener varios proyectos distintos:
                    # se agrupa por proyecto y se elige la version mas alta de cada grupo.
                    grupos = _agrupar_hrox_por_proyecto(hrox_files)
                    debug_print(f"      🗂️ {len(grupos)} proyecto(s) distinto(s) en la carpeta: {sorted(grupos.keys())}")

                    for clave in sorted(grupos.keys()):
                        archivos_grupo = grupos[clave]
                        debug_print(
                            f"      🔄 Grupo '{clave}': {len(archivos_grupo)} archivo(s) "
                            f"{[os.path.basename(f) for f in archivos_grupo]}"
                        )

                        ruta_elegida, version = _elegir_version_mas_alta(archivos_grupo)
                        if not ruta_elegida:
                            debug_print(f"         ❌ No se pudo elegir archivo para '{clave}', omitiendo")
                            continue

                        nombre_base = obtener_nombre_base_proyecto(ruta_elegida)
                        debug_print(
                            f"         📄 Archivo elegido: {os.path.basename(ruta_elegida)}, "
                            f"Nombre base: {nombre_base}, Versión: {version}"
                        )

                        proyectos_encontrados.append({
                            "nombre_base": nombre_base if nombre_base else sup_folder,
                            "vfx_folder": vfx_folder,
                            "sup_folder": sup_folder,
                            "ruta_hrox": ruta_elegida,
                            "version": version,
                            "ruta_proyecto": sup_path,
                            "project_key": obtener_clave_proyecto(ruta_elegida, nombre_base),
                        })
                        debug_print(f"         ➕ Proyecto agregado: {nombre_base} {version}")


            except PermissionError:
                # Ignorar carpetas sin permisos
                debug_print(f"   ⚠️ PermissionError al acceder a VFX: {vfx_path}")
                continue
            except Exception as e:
                # Ignorar errores en carpetas individuales
                debug_print(f"   ⚠️ Error procesando VFX {vfx_path}: {type(e).__name__}: {e}")
                continue
                
    except Exception as e:
        # Retornar lista vacía si hay error general
        debug_print(f"💥 Error general durante scan_projects_on_disk: {type(e).__name__}: {e}")
        import traceback
        debug_print(f"Traceback scan_projects_on_disk: {traceback.format_exc()}")
        pass

    debug_print(f"✅ Escaneo completado. Proyectos encontrados: {len(proyectos_encontrados)}")
    for proyecto in proyectos_encontrados:
        debug_print(f"   • {proyecto['nombre_base']} {proyecto['version']} ({proyecto['vfx_folder']}/{proyecto['sup_folder']})")

    return proyectos_encontrados


def is_path_under_root(path_value, root_value):
    """
    Indica si un path cuelga de un root, comparando por componentes.

    Se compara componente a componente y no por prefijo de texto, para que
    'T:\\VFX-ABC' no cuente como hijo de 'T:\\VFX-AB'.
    """
    if not path_value or not root_value:
        return False

    path_norm = os.path.normcase(normalize_scan_path(path_value) or "")
    root_norm = os.path.normcase(normalize_scan_path(root_value) or "")
    if not path_norm or not root_norm:
        return False

    if path_norm == root_norm:
        return True

    root_con_sep = root_norm if root_norm.endswith(os.sep) else root_norm + os.sep
    return path_norm.startswith(root_con_sep)


def get_open_projects_info(base_path=None):
    """
    Obtiene información de los proyectos abiertos en Hiero que pertenecen al contexto.

    Agrupa proyectos por nombre base y extrae información de versión.

    Solo entran los proyectos cuyo .hrox cuelga del root del contexto activo (T:\\ en
    studio, N:\\ en client). Sin ese filtro, al pasar de studio a client se seguian
    viendo como abiertos los proyectos del otro contexto, que no estan en la lista de
    disco de la pestaña en la que estas parado.

    Args:
        base_path (str|None): Root del contexto. Si es None se resuelve con
            get_base_scan_path(). Si queda vacio, no se filtra.

    Returns:
        dict: Diccionario agrupado por nombre base. Cada entrada contiene:
              nombre_base: [
                  {
                      "proyecto": proyecto_obj,
                      "ruta": str,
                      "version_num": int,
                      "version_str": str,
                      "nombre": str
                  },
                  ...
              ]
    """
    debug_print("🔍 Obteniendo información de proyectos abiertos...")
    proyectos_abiertos_por_base = {}

    if base_path is None:
        base_path = get_base_scan_path()
    else:
        base_path = normalize_scan_path(base_path)
    debug_print(f"   📍 Root del contexto para filtrar abiertos: {repr(base_path)}")

    proyectos = hiero.core.projects()
    debug_print(f"📂 Proyectos obtenidos de Hiero: {len(proyectos)}")
    if not proyectos:
        debug_print("⚠️ No hay proyectos abiertos")
        return proyectos_abiertos_por_base

    for proyecto in proyectos:
        try:
            ruta_disco_raw = proyecto.path()
            ruta_disco = normalize_scan_path(ruta_disco_raw)
            if ruta_disco != ruta_disco_raw:
                debug_print(f"      🔧 Ruta de proyecto normalizada: {repr(ruta_disco_raw)} -> {repr(ruta_disco)}")
            nombre_base = obtener_nombre_base_proyecto(ruta_disco)
            debug_print(f"   🔎 Procesando proyecto: {proyecto.name()} - Ruta: {ruta_disco}")

            # Un proyecto abierto desde el otro contexto no pertenece a esta pestaña.
            if base_path and not is_path_under_root(ruta_disco, base_path):
                debug_print(
                    f"      ⏭️ Fuera del contexto ({base_path}), se omite: {ruta_disco}"
                )
                continue

            if nombre_base:
                if nombre_base not in proyectos_abiertos_por_base:
                    proyectos_abiertos_por_base[nombre_base] = []
                
                version_num = -1
                version_str = extraer_version(ruta_disco)
                debug_print(f"      📝 Nombre base: {nombre_base}, Versión extraída: {version_str}")
                if version_str not in ["No detectada", "Error"]:
                    match = re.search(r"v?(\d+)", version_str)
                    if match:
                        version_num = int(match.group(1))
                        debug_print(f"         🔢 Versión numérica: {version_num}")

                proyectos_abiertos_por_base[nombre_base].append({
                    "proyecto": proyecto,
                    "ruta": ruta_disco,
                    "version_num": version_num,
                    "version_str": version_str,
                    "nombre": proyecto.name(),
                })
                debug_print(f"         ➕ Proyecto agregado al grupo: {nombre_base}")
        except Exception:
            # Ignorar proyectos con errores
            continue

    debug_print(f"✅ Procesamiento de proyectos abiertos completado. Grupos encontrados: {len(proyectos_abiertos_por_base)}")
    for nombre_base, proyectos in proyectos_abiertos_por_base.items():
        debug_print(f"   📁 Grupo '{nombre_base}': {len(proyectos)} proyecto(s)")
        for proyecto in proyectos:
            debug_print(f"      • {proyecto['nombre']} v{proyecto['version_str']} (num: {proyecto['version_num']})")

    return proyectos_abiertos_por_base


def is_project_open(ruta_hrox, proyectos_abiertos_info):
    """
    Verifica si un proyecto (por su ruta .hrox) ya está abierto en Hiero.

    Compara por nombre base + número de versión.

    Args:
        ruta_hrox (str): Ruta completa del archivo .hrox del proyecto
        proyectos_abiertos_info (dict): Diccionario retornado por get_open_projects_info()

    Returns:
        bool: True si el proyecto está abierto, False si no
    """
    ruta_hrox_original = ruta_hrox
    ruta_hrox = normalize_scan_path(ruta_hrox)
    if ruta_hrox != ruta_hrox_original:
        debug_print(f"   🔧 Ruta .hrox normalizada: {repr(ruta_hrox_original)} -> {repr(ruta_hrox)}")

    debug_print(f"🔍 Verificando si proyecto está abierto: {os.path.basename(ruta_hrox) if ruta_hrox else 'None'}")

    if not ruta_hrox or not os.path.exists(ruta_hrox):
        debug_print("   ❌ Ruta inválida o archivo no existe")
        return False

    nombre_base = obtener_nombre_base_proyecto(ruta_hrox)
    debug_print(f"   📝 Nombre base extraído: {nombre_base}")
    if not nombre_base:
        debug_print("   ❌ No se pudo extraer nombre base")
        return False

    version_str = extraer_version(ruta_hrox)
    debug_print(f"   🔢 Versión extraída: {version_str}")
    if version_str in ["No detectada", "Error"]:
        debug_print("   ❌ Versión inválida")
        return False

    match = re.search(r"v?(\d+)", version_str)
    if not match:
        debug_print("   ❌ No se pudo extraer número de versión")
        return False

    version_num = int(match.group(1))
    debug_print(f"   ✅ Versión numérica: {version_num}")

    # Verificar si hay un proyecto abierto con el mismo nombre base y versión
    if nombre_base in proyectos_abiertos_info:
        debug_print(f"   📁 Nombre base encontrado en proyectos abiertos: {len(proyectos_abiertos_info[nombre_base])} proyecto(s)")
        for i, proyecto_abierto in enumerate(proyectos_abiertos_info[nombre_base]):
            debug_print(f"      • Comparando v{version_num} con proyecto abierto #{i+1}: v{proyecto_abierto['version_num']}")
            if proyecto_abierto["version_num"] == version_num:
                debug_print("         ✅ ¡MATCH! Proyecto está abierto")
                return True
        debug_print("   ❌ No hay match de versión exacta")
    else:
        debug_print(f"   ❌ Nombre base '{nombre_base}' no encontrado en proyectos abiertos")

    debug_print("   ❌ Proyecto no está abierto")
    return False


def get_project_sequences(proyecto):
    """
    Obtiene lista de nombres de secuencias de un proyecto.

    Args:
        proyecto: Objeto proyecto de Hiero (hiero.core.Project)

    Returns:
        list: Lista de nombres de secuencias (strings)
    """
    sequences_names = []

    try:
        sequences = proyecto.sequences()
        sequences_names = [seq.name() for seq in sequences if hasattr(seq, 'name')]
    except Exception:
        # Retornar lista vacía si hay error
        pass

    return sequences_names


def get_projects_with_newer_versions(base_path=None):
    """
    Detecta proyectos abiertos que tienen versiones más nuevas disponibles en disco.

    Args:
        base_path (str|None): Root del contexto. Si es None se resuelve solo. Antes el
            default era "T:\\" hardcodeado, que en client no corresponde.

    Returns:
        dict: Diccionario con información de proyectos que tienen versiones más nuevas.
              Clave: nombre_base del proyecto
              Valor: {
                  "proyecto_abierto": objeto proyecto abierto,
                  "version_actual": str (ej: "v003"),
                  "version_nueva": str (ej: "v007"),
                  "ruta_version_nueva": str (ruta completa al archivo .hrox)
              }
    """
    debug_print("🔍 Buscando proyectos abiertos con versiones más nuevas disponibles...")

    proyectos_con_version_nueva = {}

    # Obtener información de proyectos abiertos (solo los del contexto activo)
    proyectos_abiertos_info = get_open_projects_info(base_path)

    if not proyectos_abiertos_info:
        debug_print("⚠️ No hay proyectos abiertos para verificar versiones")
        return proyectos_con_version_nueva

    # Para cada grupo de proyectos abiertos (por nombre base)
    for nombre_base, proyectos_grupo in proyectos_abiertos_info.items():
        debug_print(f"📁 Verificando grupo: {nombre_base} ({len(proyectos_grupo)} proyecto(s) abierto(s))")

        # Encontrar la versión más alta entre los proyectos abiertos de este grupo
        version_mas_alta_abierta = None
        proyecto_mas_reciente = None

        for proyecto_info in proyectos_grupo:
            version_actual = proyecto_info["version_str"]
            if version_mas_alta_abierta is None:
                version_mas_alta_abierta = version_actual
                proyecto_mas_reciente = proyecto_info
            else:
                if comparar_versiones(version_mas_alta_abierta, version_actual) == version_actual:
                    version_mas_alta_abierta = version_actual
                    proyecto_mas_reciente = proyecto_info

        debug_print(f"   📊 Versión más alta abierta: {version_mas_alta_abierta}")

        # Usar el proyecto más reciente como referencia para buscar versiones más nuevas
        ruta_referencia = proyecto_mas_reciente["ruta"]
        ruta_version_mas_alta = encontrar_version_mas_alta(ruta_referencia)

        if ruta_version_mas_alta not in ["No detectada", "Error", "No disponible", "No hay otras versiones"]:
            version_nueva_str = extraer_version(ruta_version_mas_alta)
            debug_print(f"   🔍 Versión más alta en disco: {version_nueva_str}")

            # Comparar versiones
            version_mas_alta_resultado = comparar_versiones(version_mas_alta_abierta, version_nueva_str)

            # Solo considerar "nueva" si la versión de disco es distinta y mayor
            if version_nueva_str != version_mas_alta_abierta and version_mas_alta_resultado == version_nueva_str:
                # Hay una versión más nueva disponible
                debug_print(f"   ✅ ¡VERSIÓN MÁS NUEVA ENCONTRADA! {version_mas_alta_abierta} → {version_nueva_str}")

                proyectos_con_version_nueva[nombre_base] = {
                    "proyecto_abierto": proyecto_mas_reciente["proyecto"],
                    "version_actual": version_mas_alta_abierta,
                    "version_nueva": version_nueva_str,
                    "ruta_version_nueva": ruta_version_mas_alta,
                    "ruta_version_actual": proyecto_mas_reciente["ruta"]
                }
            else:
                debug_print(f"   ✅ Versión abierta ya es la más actual: {version_mas_alta_abierta}")
        else:
            debug_print(f"   ⚠️ No se pudo determinar versión más alta en disco para {nombre_base}")

    debug_print(f"✅ Verificación completada. Proyectos con versiones nuevas: {len(proyectos_con_version_nueva)}")
    for nombre_base, info in proyectos_con_version_nueva.items():
        debug_print(f"   • {nombre_base}: {info['version_actual']} → {info['version_nueva']}")

    return proyectos_con_version_nueva
