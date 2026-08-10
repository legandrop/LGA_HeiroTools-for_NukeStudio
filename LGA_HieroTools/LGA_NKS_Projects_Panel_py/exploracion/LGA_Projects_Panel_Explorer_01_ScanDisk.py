"""
Script de Exploración 01: Escaneo de Disco T:
==============================================

Este script explora la estructura de carpetas en T:\ para entender:
- Cómo encontrar carpetas VFX-*
- Cómo encontrar carpetas *_SUP dentro de cada proyecto
- Cómo listar archivos .hrox en cada carpeta SUP
- Formato de nombres de archivos y versiones

EJECUTAR ESTE SCRIPT EN HIERO Y COMPARTIR LOS RESULTADOS IMPRESOS.

IMPORTANTE: Este script usa LGA_QtAdapter_HieroTools para compatibilidad Nuke 15/16
"""

import hiero.core
import hiero.ui
import os
import glob
import re
import sys
from pathlib import Path

# Obtener la ruta del directorio Startup (donde están todos los scripts)
# El directorio Startup está en: C:\Users\leg4-pc\.nuke\Python\Startup\LGA_HieroTools\
# Y dentro está la carpeta LGA_NKS

lga_nks_path = None

# Método 1: Buscar el archivo directamente en sys.path
# Esto es más confiable porque sys.path ya tiene las rutas correctas
print("Buscando LGA_NKS_CheckProjectVersions.py en sys.path...")
for path_str in sys.path:
    try:
        path = Path(path_str)
        # Buscar el archivo directamente
        test_file = path / "LGA_NKS_CheckProjectVersions.py"
        if test_file.exists():
            lga_nks_path = path
            print(f"  ✓ Encontrado en: {lga_nks_path}")
            break
        # Buscar en el directorio padre (por si la ruta apunta a una subcarpeta)
        if path.parent.exists():
            test_file_parent = path.parent / "LGA_NKS_CheckProjectVersions.py"
            if test_file_parent.exists():
                lga_nks_path = path.parent
                print(f"  ✓ Encontrado en (padre): {lga_nks_path}")
                break
        # Buscar si esta ruta es Startup y contiene LGA_NKS
        if path.exists() and (path / "LGA_NKS" / "LGA_NKS_CheckProjectVersions.py").exists():
            lga_nks_path = path / "LGA_NKS"
            print(f"  ✓ Encontrado en (subcarpeta LGA_NKS): {lga_nks_path}")
            break
    except Exception as e:
        continue

# Método 2: Buscar usando __file__ si está disponible
if lga_nks_path is None or not lga_nks_path.exists():
    if '__file__' in globals() and __file__:
        try:
            script_dir = Path(__file__).resolve().parent
            # El script está en: LGA_Projects_Panel/exploracion/
            # Necesitamos subir dos niveles para llegar a Startup
            potential_startup = script_dir.parent.parent
            potential_lga_nks = potential_startup / "LGA_NKS"
            if (potential_lga_nks / "LGA_NKS_CheckProjectVersions.py").exists():
                lga_nks_path = potential_lga_nks
                print(f"  ✓ Encontrado usando __file__: {lga_nks_path}")
        except Exception as e:
            pass

# Método 3: Buscar en la ruta estándar de Startup
if lga_nks_path is None or not lga_nks_path.exists():
    standard_paths = [
        Path.home() / ".nuke" / "Python" / "Startup" / "LGA_NKS",
        Path(os.path.expanduser("~")) / ".nuke" / "Python" / "Startup" / "LGA_NKS",
    ]
    for test_path in standard_paths:
        if (test_path / "LGA_NKS_CheckProjectVersions.py").exists():
            lga_nks_path = test_path
            print(f"  ✓ Encontrado en ruta estándar: {lga_nks_path}")
            break

# Agregar ruta de LGA_NKS al path
if lga_nks_path and lga_nks_path.exists():
    if str(lga_nks_path) not in sys.path:
        sys.path.insert(0, str(lga_nks_path))
    print(f"✓ Directorio LGA_NKS agregado al path: {lga_nks_path}")
else:
    print(f"\n⚠ ADVERTENCIA: No se encontró LGA_NKS_CheckProjectVersions.py")
    print(f"Directorio actual: {os.getcwd()}")
    if '__file__' in globals() and __file__:
        print(f"Ruta del script: {__file__}")
    print(f"\nRutas en sys.path (primeras 10):")
    for i, p in enumerate(sys.path[:10], 1):
        print(f"  {i}. {p}")

# Importar funciones de manejo de versiones desde código existente
try:
    from LGA_NKS_CheckProjectVersions import (
        extraer_version,
        comparar_versiones,
        encontrar_version_mas_alta,
        obtener_nombre_base_proyecto,
    )
    print("✓ Funciones importadas correctamente desde LGA_NKS_CheckProjectVersions")
except ImportError as e:
    print(f"ERROR al importar funciones de LGA_NKS_CheckProjectVersions: {e}")
    print(f"\nRutas en sys.path (primeras 10):")
    for i, p in enumerate(sys.path[:10], 1):
        print(f"  {i}. {p}")
    print(f"\nBuscando archivo LGA_NKS_CheckProjectVersions.py...")
    # Intentar buscar el archivo manualmente
    for path_str in sys.path:
        test_path = Path(path_str) / "LGA_NKS_CheckProjectVersions.py"
        if test_path.exists():
            print(f"  ✓ Encontrado en: {test_path}")
            break
    else:
        print("  ✗ No se encontró el archivo")
    raise

# Base path donde están los proyectos VFX
BASE_PATH = "T:\\"

print("=" * 80)
print("EXPLORACIÓN 01: Escaneo de Disco T:")
print("=" * 80)
print()

# 1. Explorar estructura de T:\
print("1. EXPLORANDO ESTRUCTURA DE T:\\")
print("-" * 80)

if not os.path.exists(BASE_PATH):
    print(f"ERROR: No se encontró la ruta {BASE_PATH}")
    print("Verificar que la unidad T: esté disponible")
else:
    print(f"✓ Ruta base encontrada: {BASE_PATH}")
    print()

    # Buscar carpetas que empiecen con VFX-
    print("2. BUSCANDO CARPETAS VFX-*")
    print("-" * 80)

    try:
        # Listar todos los directorios en T:\
        items = os.listdir(BASE_PATH)
        vfx_folders = [item for item in items if os.path.isdir(os.path.join(BASE_PATH, item)) and item.startswith("VFX-")]

        if not vfx_folders:
            print("⚠ No se encontraron carpetas que empiecen con 'VFX-'")
        else:
            print(f"✓ Encontradas {len(vfx_folders)} carpetas VFX-*:")
            for folder in sorted(vfx_folders):
                print(f"  - {folder}")
        print()

        # 3. Para cada carpeta VFX-, buscar carpeta *_SUP
        print("3. BUSCANDO CARPETAS *_SUP DENTRO DE CADA PROYECTO")
        print("-" * 80)

        proyectos_encontrados = []

        for vfx_folder in sorted(vfx_folders):
            vfx_path = os.path.join(BASE_PATH, vfx_folder)
            print(f"\n📁 Proyecto: {vfx_folder}")
            print(f"   Ruta completa: {vfx_path}")

            # Buscar carpetas que terminen con _SUP
            try:
                subitems = os.listdir(vfx_path)
                sup_folders = [
                    item
                    for item in subitems
                    if os.path.isdir(os.path.join(vfx_path, item)) and item.endswith("_SUP")
                ]

                if not sup_folders:
                    print(f"   ⚠ No se encontró carpeta *_SUP en {vfx_folder}")
                else:
                    print(f"   ✓ Encontradas {len(sup_folders)} carpetas *_SUP:")
                    for sup_folder in sup_folders:
                        sup_path = os.path.join(vfx_path, sup_folder)
                        print(f"      - {sup_folder}")
                        print(f"        Ruta: {sup_path}")

                        # 4. Buscar archivos .hrox en cada carpeta SUP
                        print(f"\n        📄 Buscando archivos .hrox en {sup_folder}...")
                        hrox_pattern = os.path.join(sup_path, "*.hrox")
                        hrox_files = glob.glob(hrox_pattern)

                        if not hrox_files:
                            print(f"        ⚠ No se encontraron archivos .hrox")
                        else:
                            print(f"        ✓ Encontrados {len(hrox_files)} archivos .hrox:")
                            for hrox_file in sorted(hrox_files):
                                nombre_archivo = os.path.basename(hrox_file)
                                version = extraer_version(hrox_file)
                                nombre_base = obtener_nombre_base_proyecto(hrox_file)
                                print(f"          - {nombre_archivo}")
                                print(f"            Versión extraída: {version}")
                                print(f"            Nombre base: {nombre_base}")

                            # Encontrar la versión más alta
                            if len(hrox_files) > 1:
                                # Usar el primer archivo como referencia
                                ruta_referencia = hrox_files[0]
                                version_mas_alta = encontrar_version_mas_alta(ruta_referencia)
                                if version_mas_alta not in ["No detectada", "Error", "No disponible", "No hay otras versiones"]:
                                    nombre_alta = os.path.basename(version_mas_alta)
                                    version_alta = extraer_version(version_mas_alta)
                                    print(f"\n        🏆 Versión más alta encontrada:")
                                    print(f"          - Archivo: {nombre_alta}")
                                    print(f"          - Versión: {version_alta}")
                                    print(f"          - Ruta completa: {version_mas_alta}")

                                    # Guardar información del proyecto
                                    proyectos_encontrados.append({
                                        "vfx_folder": vfx_folder,
                                        "sup_folder": sup_folder,
                                        "nombre_base": nombre_base if nombre_base else sup_folder,
                                        "ruta_hrox": version_mas_alta,
                                        "version": version_alta,
                                        "ruta_proyecto": sup_path,
                                    })
                                else:
                                    print(f"\n        ⚠ No se pudo determinar la versión más alta: {version_mas_alta}")
                            elif len(hrox_files) == 1:
                                # Solo hay un archivo
                                hrox_file = hrox_files[0]
                                nombre_base = obtener_nombre_base_proyecto(hrox_file)
                                version = extraer_version(hrox_file)
                                print(f"\n        ℹ Solo hay un archivo .hrox:")
                                print(f"          - Versión: {version}")

                                proyectos_encontrados.append({
                                    "vfx_folder": vfx_folder,
                                    "sup_folder": sup_folder,
                                    "nombre_base": nombre_base if nombre_base else sup_folder,
                                    "ruta_hrox": hrox_file,
                                    "version": version,
                                    "ruta_proyecto": sup_path,
                                })

            except PermissionError:
                print(f"   ⚠ Error de permisos al acceder a {vfx_path}")
            except Exception as e:
                print(f"   ⚠ Error al explorar {vfx_folder}: {e}")

        # 5. Resumen de proyectos encontrados
        print()
        print("=" * 80)
        print("RESUMEN DE PROYECTOS ENCONTRADOS")
        print("=" * 80)

        if not proyectos_encontrados:
            print("⚠ No se encontraron proyectos válidos")
        else:
            print(f"✓ Total de proyectos encontrados: {len(proyectos_encontrados)}\n")
            for i, proyecto in enumerate(proyectos_encontrados, 1):
                print(f"{i}. {proyecto['nombre_base']}")
                print(f"   - Carpeta VFX: {proyecto['vfx_folder']}")
                print(f"   - Carpeta SUP: {proyecto['sup_folder']}")
                print(f"   - Versión: {proyecto['version']}")
                print(f"   - Archivo .hrox: {os.path.basename(proyecto['ruta_hrox'])}")
                print(f"   - Ruta completa: {proyecto['ruta_hrox']}")
                print()

    except Exception as e:
        print(f"ERROR al explorar {BASE_PATH}: {e}")
        import traceback
        traceback.print_exc()

print("=" * 80)
print("FIN DE EXPLORACIÓN 01")
print("=" * 80)
print()
print("INFORMACIÓN IMPORTANTE:")
print("- Compartir todos los resultados impresos arriba")
print("- Verificar que los nombres de proyectos y versiones se extraigan correctamente")
print("- Verificar que las rutas sean accesibles")

