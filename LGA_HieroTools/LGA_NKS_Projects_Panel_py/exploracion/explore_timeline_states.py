"""
Exploración de Estados de Timeline en Hiero
=============================================

Script que analiza y reporta el estado de todos los timelines en Hiero:
- Secuencias que tienen timeline abierto
- Secuencias que existen pero no tienen timeline abierto
- Estado de integración (integrado vs flotante)
- Información detallada de cada timeline encontrado

EJECUTAR EN HIERO para explorar el estado actual de los timelines.
"""

import hiero.core
import hiero.ui

def _is_timeline_integrated(ed):
    """Verifica si el timeline editor está integrado o flotante."""
    if not ed:
        return False, "No editor"

    try:
        w = ed.window()
        if not w:
            return True, "Integrado (sin ventana)"

        # Verificar título de ventana
        window_title = w.windowTitle() if hasattr(w, 'windowTitle') else "Sin título"
        is_main_window = w.isWindow() and not w.parent()

        # Si el título contiene indicadores de timeline flotante
        if "timeline" in window_title.lower() or "editor" in window_title.lower():
            return False, f"Flotante ('{window_title}')"

        # Si es main window pero tiene título de secuencia
        if is_main_window and window_title:
            try:
                active_seq = hiero.ui.activeSequence()
                if active_seq and active_seq.name() in window_title:
                    return False, f"Flotante (main window con título '{window_title}')"
            except:
                pass

        return True, f"Integrado (ventana principal)"

    except Exception as e:
        return False, f"Error: {e}"


def _get_timeline_info(ed, seq):
    """Obtiene información detallada de un timeline editor."""
    info = {
        'secuencia': seq.name() if seq else "Desconocida",
        'editor_id': str(id(ed)) if ed else "None",
        'integrado': False,
        'estado_integracion': "No disponible",
        'tiene_ventana': False,
        'titulo_ventana': "Sin título",
        'es_main_window': False,
        'tiene_parent': False
    }

    if not ed:
        return info

    try:
        w = ed.window()
        info['tiene_ventana'] = w is not None

        if w:
            info['titulo_ventana'] = w.windowTitle() if hasattr(w, 'windowTitle') else "Sin título"
            info['es_main_window'] = w.isWindow()
            info['tiene_parent'] = w.parent() is not None

        info['integrado'], info['estado_integracion'] = _is_timeline_integrated(ed)

    except Exception as e:
        info['estado_integracion'] = f"Error analizando: {e}"

    return info


def analyze_all_sequences():
    """Analiza todas las secuencias del proyecto y su estado de timeline."""
    print("=" * 100)
    print("🔍 ANÁLISIS COMPLETO DE SECUENCIAS Y TIMELINES")
    print("=" * 100)

    # Obtener proyecto
    projects = hiero.core.projects()
    if not projects:
        print("❌ No hay proyectos abiertos.")
        return

    project = projects[0]
    print(f"📁 Proyecto: {project.name()}")
    print()

    # Obtener todas las secuencias
    all_sequences = project.sequences()
    print(f"📋 Total de secuencias en proyecto: {len(all_sequences)}")

    # Obtener secuencia activa
    active_seq = None
    try:
        active_seq = hiero.ui.activeSequence()
        if active_seq:
            print(f"🎯 Secuencia activa actual: '{active_seq.name()}'")
        else:
            print("🎯 No hay secuencia activa")
    except Exception as e:
        print(f"⚠️ Error obteniendo secuencia activa: {e}")

    print()

    # Analizar cada secuencia
    sequences_with_timeline = []
    sequences_without_timeline = []

    print("🔎 ANALIZANDO CADA SECUENCIA:")
    print("-" * 80)

    for seq in all_sequences:
        try:
            seq_name = seq.name()
            print(f"\n📝 Secuencia: '{seq_name}'")

            # Intentar obtener timeline editor
            try:
                ed = hiero.ui.getTimelineEditor(seq)
                if ed:
                    print("  ✅ Tiene timeline editor abierto")
                    timeline_info = _get_timeline_info(ed, seq)
                    print(f"  🔧 Editor ID: {timeline_info['editor_id']}")
                    print(f"  🔗 Integrado: {timeline_info['integrado']} ({timeline_info['estado_integracion']})")
                    print(f"  🪟 Tiene ventana: {timeline_info['tiene_ventana']}")
                    if timeline_info['tiene_ventana']:
                        print(f"  📋 Título: '{timeline_info['titulo_ventana']}'")
                        print(f"  🏠 Main window: {timeline_info['es_main_window']}")
                        print(f"  👨‍👩‍👧‍👦 Tiene parent: {timeline_info['tiene_parent']}")

                    sequences_with_timeline.append((seq, ed, timeline_info))
                else:
                    print("  ❌ No tiene timeline editor abierto")
                    sequences_without_timeline.append(seq)

            except Exception as e:
                print(f"  ❌ Error obteniendo timeline editor: {e}")
                sequences_without_timeline.append(seq)

        except Exception as e:
            print(f"❌ Error procesando secuencia: {e}")

    print()
    print("=" * 100)
    print("📊 RESUMEN FINAL")
    print("=" * 100)

    print(f"🎬 Secuencias con timeline abierto: {len(sequences_with_timeline)}")
    for seq, ed, info in sequences_with_timeline:
        status = "✅ Integrado" if info['integrado'] else "⚠️ Flotante"
        print(f"  - '{seq.name()}': {status} ({info['estado_integracion']})")

    print()
    print(f"📭 Secuencias sin timeline abierto: {len(sequences_without_timeline)}")
    for seq in sequences_without_timeline:
        try:
            print(f"  - '{seq.name()}'")
        except:
            print("  - [Error obteniendo nombre]")

    print()
    print("💡 CONCLUSIONES:")
    if len(sequences_with_timeline) == 0:
        print("  - No hay ningún timeline abierto actualmente")
    elif len(sequences_with_timeline) == 1:
        seq, ed, info = sequences_with_timeline[0]
        if info['integrado']:
            print(f"  - Hay 1 timeline integrado abierto para '{seq.name()}'")
        else:
            print(f"  - Hay 1 timeline flotante abierto para '{seq.name()}'")
    else:
        integrados = sum(1 for _, _, info in sequences_with_timeline if info['integrado'])
        flotantes = len(sequences_with_timeline) - integrados
        print(f"  - Hay {len(sequences_with_timeline)} timelines abiertos: {integrados} integrados, {flotantes} flotantes")
        if flotantes > 0:
            print("  - ⚠️ HAY TIMELINES DUPLICADOS/FLOTANTES - Esto puede causar problemas")

    print("=" * 100)


def main():
    """Función principal."""
    try:
        analyze_all_sequences()
    except Exception as e:
        print(f"❌ Error general: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
