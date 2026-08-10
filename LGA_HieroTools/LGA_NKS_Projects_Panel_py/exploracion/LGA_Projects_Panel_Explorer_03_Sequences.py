"""
Script de Exploración 03: Secuencias de Proyectos
==================================================

Este script explora cómo obtener y trabajar con secuencias de proyectos abiertos:
- Cómo obtener lista de secuencias de un proyecto
- Cómo obtener nombre de cada secuencia
- Cómo buscar secuencia por nombre
- Cómo abrir secuencia en timeline
- Métodos disponibles en objetos Sequence

EJECUTAR ESTE SCRIPT EN HIERO (con al menos un proyecto abierto que tenga secuencias) 
Y COMPARTIR LOS RESULTADOS IMPRESOS.

IMPORTANTE: Este script usa LGA_QtAdapter_HieroTools para compatibilidad Nuke 15/16
"""

import hiero.core
import hiero.ui
import os
import sys
from pathlib import Path

print("=" * 80)
print("EXPLORACIÓN 03: Secuencias de Proyectos")
print("=" * 80)
print()

# 1. Obtener proyectos abiertos
print("1. OBTENIENDO PROYECTOS ABIERTOS")
print("-" * 80)

proyectos_abiertos = hiero.core.projects()

if not proyectos_abiertos:
    print("⚠ No hay proyectos abiertos en Hiero")
    print("  Abre al menos un proyecto con secuencias para poder explorar esta funcionalidad")
    print()
    print("=" * 80)
    print("FIN DE EXPLORACIÓN 03 (sin proyectos abiertos)")
    print("=" * 80)
else:
    print(f"✓ Encontrados {len(proyectos_abiertos)} proyecto(s) abierto(s)\n")

    # 2. Explorar secuencias usando diferentes métodos
    print("=" * 80)
    print("2. MÉTODOS PARA OBTENER SECUENCIAS")
    print("-" * 80)
    print()

    for i, proyecto in enumerate(proyectos_abiertos, 1):
        print(f"📁 Proyecto {i}: {proyecto.name()}")
        print(f"   Ruta: {proyecto.path()}")
        print()

        # Método 1: Usar proyecto.sequences()
        print("   🔍 Método 1: proyecto.sequences()")
        try:
            sequences_method = proyecto.sequences()
            print(f"      Tipo de retorno: {type(sequences_method)}")
            if hasattr(sequences_method, '__iter__'):
                sequences_list = list(sequences_method)
                print(f"      ✓ Retorna {len(sequences_list)} secuencia(s)")
                for seq in sequences_list[:5]:  # Mostrar solo las primeras 5
                    if hasattr(seq, 'name'):
                        print(f"         - {seq.name()}")
                if len(sequences_list) > 5:
                    print(f"         ... y {len(sequences_list) - 5} más")
            else:
                print(f"      ⚠ No es iterable directamente")
        except Exception as e:
            print(f"      ⚠ Error: {e}")

        print()

        # Método 2: Usar hiero.core.findItems(project, "Sequences")
        print("   🔍 Método 2: hiero.core.findItems(project, 'Sequences')")
        try:
            sequences_find = hiero.core.findItems(proyecto, "Sequences")
            print(f"      Tipo de retorno: {type(sequences_find)}")
            if sequences_find:
                sequences_list = list(sequences_find) if hasattr(sequences_find, '__iter__') else [sequences_find]
                print(f"      ✓ Retorna {len(sequences_list)} secuencia(s)")
                for seq in sequences_list[:5]:  # Mostrar solo las primeras 5
                    if hasattr(seq, 'name'):
                        print(f"         - {seq.name()}")
                if len(sequences_list) > 5:
                    print(f"         ... y {len(sequences_list) - 5} más")
            else:
                print(f"      ⚠ No se encontraron secuencias")
        except Exception as e:
            print(f"      ⚠ Error: {e}")

        print()

        # Método 3: Usar find_sequences() desde proyecto.clipsBin() (como en LGA_H-Bin-Print_Only_Sequences.py)
        print("   🔍 Método 3: find_sequences(proyecto.clipsBin())")
        try:
            def find_sequences(bin_item):
                """
                Busca recursivamente todas las secuencias en un Bin y sus sub-Bins.
                Basado en LGA_H-Bin-Print_Only_Sequences.py
                """
                sequences = []
                for item in bin_item.items():
                    if isinstance(item, hiero.core.BinItem) and isinstance(item.activeItem(), hiero.core.Sequence):
                        sequences.append(item)
                    elif isinstance(item, hiero.core.Bin):
                        sequences.extend(find_sequences(item))
                return sequences

            clips_bin = proyecto.clipsBin()
            sequences_bin = find_sequences(clips_bin)
            print(f"      ✓ Retorna {len(sequences_bin)} secuencia(s)")
            for seq_item in sequences_bin[:5]:  # Mostrar solo las primeras 5
                if hasattr(seq_item, 'name'):
                    print(f"         - {seq_item.name()} (BinItem)")
                    if hasattr(seq_item, 'activeItem'):
                        active_seq = seq_item.activeItem()
                        if active_seq and hasattr(active_seq, 'name'):
                            print(f"           Secuencia activa: {active_seq.name()}")
            if len(sequences_bin) > 5:
                print(f"         ... y {len(sequences_bin) - 5} más")
        except Exception as e:
            print(f"      ⚠ Error: {e}")
            import traceback
            traceback.print_exc()

        print()

    # 3. Explorar información detallada de secuencias
    print("=" * 80)
    print("3. INFORMACIÓN DETALLADA DE SECUENCIAS")
    print("-" * 80)
    print()

    # Usar el método más confiable (find_sequences desde clipsBin)
    def find_sequences_detailed(bin_item):
        """Busca secuencias y retorna información detallada"""
        sequences = []
        for item in bin_item.items():
            if isinstance(item, hiero.core.BinItem) and isinstance(item.activeItem(), hiero.core.Sequence):
                sequences.append(item)
            elif isinstance(item, hiero.core.Bin):
                sequences.extend(find_sequences_detailed(item))
        return sequences

    for proyecto in proyectos_abiertos:
        print(f"📁 Proyecto: {proyecto.name()}")
        print()

        try:
            sequences = find_sequences_detailed(proyecto.clipsBin())
            
            if not sequences:
                print("   ⚠ No se encontraron secuencias en este proyecto")
                print()
                continue

            print(f"   ✓ Total de secuencias encontradas: {len(sequences)}\n")

            for seq_item in sequences:
                try:
                    # Obtener información del BinItem
                    bin_item_name = seq_item.name() if hasattr(seq_item, 'name') else "Sin nombre"
                    print(f"   📋 Secuencia: {bin_item_name}")
                    
                    # Obtener la secuencia activa
                    if hasattr(seq_item, 'activeItem'):
                        active_seq = seq_item.activeItem()
                        if active_seq:
                            print(f"      Tipo de objeto Sequence: {type(active_seq).__name__}")
                            
                            # Explorar métodos disponibles
                            seq_methods = [m for m in dir(active_seq) if not m.startswith("_")]
                            metodos_interesantes = [
                                "name", "videoTracks", "audioTracks", "duration", 
                                "timecodeStart", "fps", "format"
                            ]
                            print(f"      Métodos disponibles:")
                            for metodo in metodos_interesantes:
                                if metodo in seq_methods:
                                    try:
                                        # Intentar llamar al método si no requiere parámetros
                                        if metodo == "name":
                                            valor = active_seq.name()
                                            print(f"         ✓ {metodo}() → '{valor}'")
                                        elif metodo == "videoTracks":
                                            tracks = active_seq.videoTracks()
                                            print(f"         ✓ {metodo}() → {len(tracks)} track(s)")
                                        elif metodo == "audioTracks":
                                            tracks = active_seq.audioTracks()
                                            print(f"         ✓ {metodo}() → {len(tracks)} track(s)")
                                        elif metodo == "duration":
                                            valor = active_seq.duration()
                                            print(f"         ✓ {metodo}() → {valor}")
                                        elif metodo == "fps":
                                            valor = active_seq.fps()
                                            print(f"         ✓ {metodo}() → {valor}")
                                        else:
                                            print(f"         ✓ {metodo}()")
                                    except Exception as e:
                                        print(f"         ⚠ {metodo}() → Error: {e}")
                            
                            print(f"      ... y {len(seq_methods) - len(metodos_interesantes)} métodos más")
                    
                    print()
                    
                except Exception as e:
                    print(f"      ⚠ Error al procesar secuencia: {e}")
                    print()

        except Exception as e:
            print(f"   ⚠ Error al obtener secuencias: {e}")
            import traceback
            traceback.print_exc()
            print()

    # 4. Probar función find_sequence_by_name
    print("=" * 80)
    print("4. BÚSQUEDA DE SECUENCIA POR NOMBRE")
    print("-" * 80)
    print()

    def find_sequence_by_name(project, sequence_name):
        """
        Busca una secuencia específica por nombre en el proyecto.
        Basado en LGA_Abrir_Nuevo_CompTimelineViewers.py
        """
        def search_in_bin(bin_item):
            for item in bin_item.items():
                if isinstance(item, hiero.core.BinItem) and isinstance(item.activeItem(), hiero.core.Sequence):
                    if item.name() == sequence_name:
                        return item.activeItem()
                elif isinstance(item, hiero.core.Bin):
                    result = search_in_bin(item)
                    if result:
                        return result
            return None

        return search_in_bin(project.clipsBin())

    for proyecto in proyectos_abiertos:
        print(f"📁 Proyecto: {proyecto.name()}")
        
        # Obtener lista de nombres de secuencias
        try:
            sequences = find_sequences_detailed(proyecto.clipsBin())
            if sequences:
                # Probar buscar la primera secuencia por nombre
                primera_secuencia = sequences[0]
                nombre_primera = primera_secuencia.name() if hasattr(primera_secuencia, 'name') else None
                
                if nombre_primera:
                    print(f"   Probando buscar secuencia: '{nombre_primera}'")
                    secuencia_encontrada = find_sequence_by_name(proyecto, nombre_primera)
                    
                    if secuencia_encontrada:
                        print(f"   ✓ Secuencia encontrada: {secuencia_encontrada.name() if hasattr(secuencia_encontrada, 'name') else 'Sin nombre'}")
                        print(f"   ✓ Tipo: {type(secuencia_encontrada).__name__}")
                    else:
                        print(f"   ⚠ Secuencia no encontrada")
                else:
                    print(f"   ⚠ No se pudo obtener nombre de la primera secuencia")
            else:
                print(f"   ⚠ No hay secuencias en este proyecto para probar")
        except Exception as e:
            print(f"   ⚠ Error: {e}")
        
        print()

    # 5. Probar apertura de secuencia en timeline (sin ejecutar realmente)
    print("=" * 80)
    print("5. MÉTODO PARA ABRIR SECUENCIA EN TIMELINE")
    print("-" * 80)
    print()

    print("Método disponible:")
    print("  - hiero.ui.openInTimeline(sequence)")
    print()
    print("Nota: No ejecutamos esta función en el script de exploración para evitar")
    print("      abrir timelines automáticamente. Se probará en el código final.")
    print()

    # 6. Resumen final
    print("=" * 80)
    print("RESUMEN FINAL")
    print("=" * 80)
    print()

    total_secuencias = 0
    for proyecto in proyectos_abiertos:
        try:
            sequences = find_sequences_detailed(proyecto.clipsBin())
            total_secuencias += len(sequences)
        except:
            pass

    print(f"✓ Total de proyectos abiertos: {len(proyectos_abiertos)}")
    print(f"✓ Total de secuencias encontradas: {total_secuencias}")
    print()
    print("Métodos clave descubiertos:")
    print("  - hiero.core.findItems(project, 'Sequences') → Lista de secuencias")
    print("  - proyecto.sequences() → Lista de secuencias (método alternativo)")
    print("  - find_sequences(proyecto.clipsBin()) → Búsqueda recursiva en bins")
    print("  - sequence.name() → Nombre de la secuencia")
    print("  - sequence.videoTracks() → Tracks de video")
    print("  - find_sequence_by_name(project, name) → Buscar secuencia por nombre")
    print("  - hiero.ui.openInTimeline(sequence) → Abrir secuencia en timeline")
    print()
    print("Estructura de datos:")
    print("  - BinItem contiene Sequence (usar activeItem() para obtener Sequence)")
    print("  - Sequence es el objeto real con métodos name(), videoTracks(), etc.")
    print()

print("=" * 80)
print("FIN DE EXPLORACIÓN 03")
print("=" * 80)
print()
print("INFORMACIÓN IMPORTANTE:")
print("- Compartir todos los resultados impresos arriba")
print("- Verificar que los métodos de secuencias funcionen correctamente")
print("- Verificar que la búsqueda por nombre funcione")
print("- Verificar estructura de datos (BinItem vs Sequence)")

