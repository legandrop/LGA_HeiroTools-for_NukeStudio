"""
Script de Exploración 02: Proyectos Abiertos en Hiero
======================================================

Este script explora cómo detectar y trabajar con proyectos abiertos en Hiero:
- Cómo obtener lista de proyectos abiertos
- Cómo obtener información de cada proyecto abierto
- Cómo comparar proyectos abiertos con proyectos encontrados en disco
- Cómo determinar si un proyecto del disco ya está abierto

EJECUTAR ESTE SCRIPT EN HIERO (con al menos un proyecto abierto) Y COMPARTIR LOS RESULTADOS IMPRESOS.

IMPORTANTE: Este script usa LGA_QtAdapter_HieroTools para compatibilidad Nuke 15/16
"""

import hiero.core
import hiero.ui
import os
import sys
from pathlib import Path

# Importar funciones de manejo de versiones desde código existente
# (Mismo código de búsqueda que Exploración 01)
lga_nks_path = None
print("Buscando LGA_NKS_CheckProjectVersions.py en sys.path...")
for path_str in sys.path:
    try:
        path = Path(path_str)
        test_file = path / "LGA_NKS_CheckProjectVersions.py"
        if test_file.exists():
            lga_nks_path = path
            print(f"  ✓ Encontrado en: {lga_nks_path}")
            break
        if path.parent.exists():
            test_file_parent = path.parent / "LGA_NKS_CheckProjectVersions.py"
            if test_file_parent.exists():
                lga_nks_path = path.parent
                print(f"  ✓ Encontrado en (padre): {lga_nks_path}")
                break
        if path.exists() and (path / "LGA_NKS" / "LGA_NKS_CheckProjectVersions.py").exists():
            lga_nks_path = path / "LGA_NKS"
            print(f"  ✓ Encontrado en (subcarpeta LGA_NKS): {lga_nks_path}")
            break
    except Exception as e:
        continue

if lga_nks_path is None or not lga_nks_path.exists():
    if '__file__' in globals() and __file__:
        try:
            script_dir = Path(__file__).resolve().parent
            potential_startup = script_dir.parent.parent
            potential_lga_nks = potential_startup / "LGA_NKS"
            if (potential_lga_nks / "LGA_NKS_CheckProjectVersions.py").exists():
                lga_nks_path = potential_lga_nks
                print(f"  ✓ Encontrado usando __file__: {lga_nks_path}")
        except Exception as e:
            pass

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

if lga_nks_path and lga_nks_path.exists():
    if str(lga_nks_path) not in sys.path:
        sys.path.insert(0, str(lga_nks_path))
    print(f"✓ Directorio LGA_NKS agregado al path: {lga_nks_path}")
else:
    print(f"\n⚠ ADVERTENCIA: No se encontró LGA_NKS_CheckProjectVersions.py")
    print(f"Directorio actual: {os.getcwd()}")
    if '__file__' in globals() and __file__:
        print(f"Ruta del script: {__file__}")

try:
    from LGA_NKS_CheckProjectVersions import (
        extraer_version,
        comparar_versiones,
        obtener_nombre_base_proyecto,
    )
    print("✓ Funciones importadas correctamente desde LGA_NKS_CheckProjectVersions")
except ImportError as e:
    print(f"ERROR al importar funciones: {e}")
    raise

print()
print("=" * 80)
print("EXPLORACIÓN 02: Proyectos Abiertos en Hiero")
print("=" * 80)
print()

# 1. Obtener proyectos abiertos
print("1. OBTENIENDO PROYECTOS ABIERTOS")
print("-" * 80)

proyectos_abiertos = hiero.core.projects()

if not proyectos_abiertos:
    print("⚠ No hay proyectos abiertos en Hiero")
    print("  Abre al menos un proyecto para poder explorar esta funcionalidad")
    print()
    print("=" * 80)
    print("FIN DE EXPLORACIÓN 02 (sin proyectos abiertos)")
    print("=" * 80)
else:
    print(f"✓ Encontrados {len(proyectos_abiertos)} proyecto(s) abierto(s)\n")

    # 2. Explorar información de cada proyecto abierto
    print("2. INFORMACIÓN DE CADA PROYECTO ABIERTO")
    print("-" * 80)

    proyectos_info = []

    for i, proyecto in enumerate(proyectos_abiertos, 1):
        print(f"\n📁 Proyecto {i}:")
        
        # Obtener nombre del proyecto
        try:
            nombre_proyecto = proyecto.name()
            print(f"   Nombre (proyecto.name()): {nombre_proyecto}")
        except Exception as e:
            print(f"   ⚠ Error al obtener nombre: {e}")
            nombre_proyecto = "Desconocido"

        # Obtener ruta del proyecto
        try:
            ruta_proyecto = proyecto.path()
            print(f"   Ruta (proyecto.path()): {ruta_proyecto}")
        except Exception as e:
            print(f"   ⚠ Error al obtener ruta: {e}")
            ruta_proyecto = None

        # Extraer información usando funciones existentes
        nombre_base = None
        version_str = None
        version_num = -1

        if ruta_proyecto:
            try:
                nombre_base = obtener_nombre_base_proyecto(ruta_proyecto)
                print(f"   Nombre base extraído: {nombre_base}")
            except Exception as e:
                print(f"   ⚠ Error al extraer nombre base: {e}")

            try:
                version_str = extraer_version(ruta_proyecto)
                print(f"   Versión extraída: {version_str}")
            except Exception as e:
                print(f"   ⚠ Error al extraer versión: {e}")

            if version_str and version_str not in ["No detectada", "Error"]:
                import re
                match = re.search(r"v?(\d+)", version_str)
                if match:
                    version_num = int(match.group(1))
                    print(f"   Número de versión: {version_num}")

        # Explorar métodos disponibles en el objeto proyecto
        print(f"\n   🔍 Métodos disponibles en objeto proyecto:")
        metodos_proyecto = [m for m in dir(proyecto) if not m.startswith("_")]
        metodos_interesantes = [
            "name", "path", "clipsBin", "sequences", "close", 
            "isModified", "save", "rootItem"
        ]
        for metodo in metodos_interesantes:
            if metodo in metodos_proyecto:
                print(f"      ✓ {metodo}()")
        print(f"      ... y {len(metodos_proyecto) - len(metodos_interesantes)} métodos más")

        # Guardar información del proyecto
        proyectos_info.append({
            "proyecto": proyecto,
            "nombre": nombre_proyecto,
            "ruta": ruta_proyecto,
            "nombre_base": nombre_base,
            "version_str": version_str,
            "version_num": version_num,
        })

    # 3. Comparar con proyectos del disco (simulado)
    print()
    print("=" * 80)
    print("3. COMPARACIÓN CON PROYECTOS DEL DISCO")
    print("-" * 80)
    print()
    print("Para esta exploración, simulamos algunos proyectos del disco:")
    print("(En el código final usaremos los resultados de Exploración 01)")
    print()

    # Proyectos simulados del disco (basados en resultados de Exploración 01)
    proyectos_disco = [
        {"nombre_base": "PROJF_SUP", "ruta_hrox": "T:\\VFX-PROJF\\PROJF_SUP\\PROJF_SUP_v050.hrox", "version": "v050"},
        {"nombre_base": "ETDM_SUP", "ruta_hrox": "T:\\VFX-ETDM\\ETDM_SUP\\ETDM_SUP_v472.hrox", "version": "v472"},
        {"nombre_base": "LC_SUP", "ruta_hrox": "T:\\VFX-LC\\LC_SUP\\LC_SUP_v30.hrox", "version": "v30"},
    ]

    print("Proyectos simulados del disco:")
    for proyecto_disco in proyectos_disco:
        print(f"  - {proyecto_disco['nombre_base']} ({proyecto_disco['version']})")
        print(f"    Ruta: {proyecto_disco['ruta_hrox']}")
    print()

    # Comparar proyectos abiertos con proyectos del disco
    print("Comparando proyectos abiertos con proyectos del disco:")
    print()

    for proyecto_info in proyectos_info:
        nombre_base_abierto = proyecto_info["nombre_base"]
        version_abierto = proyecto_info["version_str"]
        version_num_abierto = proyecto_info["version_num"]

        print(f"📋 Proyecto abierto: {proyecto_info['nombre']}")
        print(f"   Nombre base: {nombre_base_abierto}")
        print(f"   Versión: {version_abierto} (número: {version_num_abierto})")
        print(f"   Ruta: {proyecto_info['ruta']}")

        # Buscar coincidencias en proyectos del disco
        coincidencias = []
        for proyecto_disco in proyectos_disco:
            nombre_base_disco = proyecto_disco["nombre_base"]
            version_disco = proyecto_disco["version"]
            
            # Extraer número de versión del disco
            import re
            match_disco = re.search(r"v?(\d+)", version_disco)
            version_num_disco = int(match_disco.group(1)) if match_disco else -1

            # Comparar por nombre base
            if nombre_base_abierto == nombre_base_disco:
                # Mismo proyecto, comparar versiones
                if version_num_abierto == version_num_disco:
                    coincidencias.append({
                        "proyecto_disco": proyecto_disco,
                        "tipo": "misma_version",
                        "mensaje": f"✓ Misma versión ({version_disco})"
                    })
                elif version_num_abierto < version_num_disco:
                    coincidencias.append({
                        "proyecto_disco": proyecto_disco,
                        "tipo": "version_mas_alta_disponible",
                        "mensaje": f"⚠ Versión más alta disponible en disco: {version_disco}"
                    })
                else:
                    coincidencias.append({
                        "proyecto_disco": proyecto_disco,
                        "tipo": "version_mas_alta_abierta",
                        "mensaje": f"ℹ Versión abierta es más alta que la del disco"
                    })

        if coincidencias:
            print(f"   Coincidencias encontradas:")
            for coincidencia in coincidencias:
                print(f"      {coincidencia['mensaje']}")
                print(f"         Ruta disco: {coincidencia['proyecto_disco']['ruta_hrox']}")
        else:
            print(f"   ⚠ No se encontró coincidencia en proyectos del disco")
            print(f"      (Puede ser que el proyecto no esté en T:\\ o tenga nombre diferente)")

        print()

    # 4. Crear diccionario agrupado por nombre base (como en CheckProjectVersions)
    print("=" * 80)
    print("4. AGRUPACIÓN POR NOMBRE BASE")
    print("-" * 80)
    print()
    print("Agrupando proyectos abiertos por nombre base (como en LGA_NKS_CheckProjectVersions):")
    print()

    proyectos_abiertos_por_base = {}

    for proyecto_info in proyectos_info:
        nombre_base = proyecto_info["nombre_base"]
        if nombre_base:
            if nombre_base not in proyectos_abiertos_por_base:
                proyectos_abiertos_por_base[nombre_base] = []

            proyectos_abiertos_por_base[nombre_base].append({
                "proyecto": proyecto_info["proyecto"],
                "ruta": proyecto_info["ruta"],
                "version_num": proyecto_info["version_num"],
                "version_str": proyecto_info["version_str"],
                "nombre": proyecto_info["nombre"],
            })

    for nombre_base, proyectos in proyectos_abiertos_por_base.items():
        print(f"📦 {nombre_base}:")
        for proyecto in proyectos:
            print(f"   - Versión {proyecto['version_str']} (v{proyecto['version_num']})")
            print(f"     Ruta: {proyecto['ruta']}")
            print(f"     Nombre: {proyecto['nombre']}")
        print()

    # 5. Función para verificar si un proyecto del disco está abierto
    print("=" * 80)
    print("5. FUNCIÓN DE VERIFICACIÓN")
    print("-" * 80)
    print()
    print("Probando función para verificar si un proyecto del disco está abierto:")
    print()

    def is_project_open(ruta_hrox, proyectos_abiertos_por_base):
        """
        Verifica si un proyecto (por su ruta .hrox) ya está abierto en Hiero.
        
        Args:
            ruta_hrox: Ruta completa del archivo .hrox del proyecto
            proyectos_abiertos_por_base: Diccionario de proyectos abiertos agrupados por nombre base
            
        Returns:
            bool: True si el proyecto está abierto, False si no
        """
        if not ruta_hrox or not os.path.exists(ruta_hrox):
            return False

        nombre_base = obtener_nombre_base_proyecto(ruta_hrox)
        if not nombre_base:
            return False

        version_str = extraer_version(ruta_hrox)
        if version_str in ["No detectada", "Error"]:
            return False

        import re
        match = re.search(r"v?(\d+)", version_str)
        if not match:
            return False

        version_num = int(match.group(1))

        # Verificar si hay un proyecto abierto con el mismo nombre base y versión
        if nombre_base in proyectos_abiertos_por_base:
            for proyecto_abierto in proyectos_abiertos_por_base[nombre_base]:
                if proyecto_abierto["version_num"] == version_num:
                    return True

        return False

    # Probar la función con proyectos simulados del disco
    for proyecto_disco in proyectos_disco:
        ruta_hrox = proyecto_disco["ruta_hrox"]
        esta_abierto = is_project_open(ruta_hrox, proyectos_abiertos_por_base)
        
        print(f"📄 {os.path.basename(ruta_hrox)}")
        print(f"   Ruta: {ruta_hrox}")
        if esta_abierto:
            print(f"   ✓ ESTÁ ABIERTO en Hiero")
        else:
            print(f"   ✗ NO está abierto en Hiero")
        print()

    # 6. Resumen final
    print("=" * 80)
    print("RESUMEN FINAL")
    print("=" * 80)
    print()
    print(f"✓ Total de proyectos abiertos: {len(proyectos_abiertos)}")
    print(f"✓ Proyectos únicos (por nombre base): {len(proyectos_abiertos_por_base)}")
    print()
    print("Métodos clave descubiertos:")
    print("  - hiero.core.projects() → Lista de proyectos abiertos")
    print("  - proyecto.name() → Nombre del proyecto")
    print("  - proyecto.path() → Ruta completa del archivo .hrox")
    print("  - obtener_nombre_base_proyecto(ruta) → Nombre base sin versión")
    print("  - extraer_version(ruta) → Versión del proyecto")
    print()
    print("Lógica de comparación:")
    print("  - Agrupar proyectos abiertos por nombre base")
    print("  - Comparar por nombre base + número de versión")
    print("  - Un proyecto está abierto si nombre_base y version_num coinciden")
    print()

print("=" * 80)
print("FIN DE EXPLORACIÓN 02")
print("=" * 80)
print()
print("INFORMACIÓN IMPORTANTE:")
print("- Compartir todos los resultados impresos arriba")
print("- Verificar que la comparación de proyectos funcione correctamente")
print("- Verificar que los métodos de proyecto funcionen como se espera")

