"""
Exploración de Métodos del Viewer - Buscando Saturación
======================================================

Script para explorar todos los métodos disponibles en un viewer
para encontrar el knob de saturación.
"""

import hiero.core
import hiero.ui
import time

def explore_viewer_methods():
    """Explora todos los métodos disponibles en el viewer actual."""
    print("🔍 Explorando métodos del viewer...")
    print("=" * 60)

    # Obtener viewer actual
    viewer = hiero.ui.currentViewer()
    if not viewer:
        print("❌ No hay viewer activo")
        return

    print(f"✅ Viewer encontrado: {type(viewer)}")
    print()

    # Obtener todos los métodos/attributes
    methods = []
    for attr in dir(viewer):
        if not attr.startswith('_'):  # Filtrar métodos privados
            try:
                value = getattr(viewer, attr)
                if callable(value):
                    methods.append((attr, "method", None))
                else:
                    # Intentar obtener el valor si es una propiedad
                    try:
                        if attr in ['gain', 'gamma', 'time']:  # Ya sabemos estos
                            val = value()
                            methods.append((attr, "property", val))
                        else:
                            # Para otros, intentar llamarlos sin parámetros
                            val = value()
                            methods.append((attr, "property", val))
                    except:
                        methods.append((attr, "property", "N/A"))
            except Exception as e:
                methods.append((attr, "error", str(e)))

    # Filtrar y ordenar métodos relevantes
    relevant_methods = []
    color_methods = []
    other_methods = []

    for name, mtype, value in methods:
        if any(keyword in name.lower() for keyword in ['color', 'sat', 'hue', 'bright', 'contrast', 'gamma', 'gain']):
            color_methods.append((name, mtype, value))
        elif any(keyword in name.lower() for keyword in ['time', 'frame', 'play']):
            relevant_methods.append((name, mtype, value))
        else:
            other_methods.append((name, mtype, value))

    # Mostrar métodos de color (posibles saturación)
    print("🎨 MÉTODOS DE COLOR (posibles saturación):")
    print("-" * 50)
    for name, mtype, value in sorted(color_methods):
        print(f"  {name:<20} [{mtype:<8}] = {value}")

    print()
    print("⏰ MÉTODOS DE TIEMPO:")
    print("-" * 30)
    for name, mtype, value in sorted(relevant_methods):
        print(f"  {name:<20} [{mtype:<8}] = {value}")

    print()
    print("🔧 OTROS MÉTODOS RELEVANTES:")
    print("-" * 35)

    # Filtrar algunos métodos comunes que queremos ver
    common_methods = ['setGain', 'setGamma', 'setTime', 'player', 'sequence']
    for name, mtype, value in sorted(other_methods):
        if name in common_methods or len([m for m in common_methods if m in name]) > 0:
            print(f"  {name:<20} [{mtype:<8}] = {value}")

    print()
    print("📊 TOTAL MÉTODOS ENCONTRADOS:")
    print(f"  Color/Saturación: {len(color_methods)}")
    print(f"  Tiempo: {len(relevant_methods)}")
    print(f"  Otros: {len(other_methods)}")
    print(f"  TOTAL: {len(methods)}")

    # Intentar encontrar métodos con 'sat' específicamente
    sat_methods = [m for m in methods if 'sat' in m[0].lower()]
    if sat_methods:
        print()
        print("🎯 MÉTODOS CON 'SAT' ENCONTRADOS:")
        print("-" * 40)
        for name, mtype, value in sat_methods:
            print(f"  {name:<20} [{mtype:<8}] = {value}")
            # Intentar ejecutar si es método
            if mtype == "property" and value != "N/A":
                try:
                    result = getattr(viewer, name)()
                    print(f"    Valor actual: {result}")
                except Exception as e:
                    print(f"    Error obteniendo valor: {e}")
    else:
        print()
        print("❌ No se encontraron métodos con 'sat' en el nombre")

    # Buscar patrones comunes de nombres de saturación
    saturation_patterns = ['saturation', 'saturate', 'sat', 'hsl_s', 'hsv_s']
    possible_sat = []
    for pattern in saturation_patterns:
        matches = [m for m in methods if pattern in m[0].lower()]
        if matches:
            possible_sat.extend(matches)

    if possible_sat:
        print()
        print("🎯 POSIBLES MÉTODOS DE SATURACIÓN:")
        print("-" * 40)
        for name, mtype, value in sorted(set(possible_sat)):
            print(f"  {name:<20} [{mtype:<8}] = {value}")

def main():
    print("🔬 EXPLORACIÓN DE MÉTODOS DEL VIEWER")
    print("Buscando knob de saturación...")
    print()

    try:
        explore_viewer_methods()
    except Exception as e:
        print(f"❌ Error en exploración: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
