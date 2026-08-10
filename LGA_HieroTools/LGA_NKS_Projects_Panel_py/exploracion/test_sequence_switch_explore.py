"""
Script de Exploración: Métodos Alternativos para Cambiar Secuencia
===================================================================

Explora métodos alternativos para cambiar de secuencia sin usar openInTimeline().
Busca formas de cambiar la secuencia activa del timeline existente.
"""

import hiero.core
import hiero.ui

def explore_timeline_methods():
    """Explora métodos disponibles en el timeline editor"""
    print("🔍 Explorando métodos del Timeline Editor...")

    try:
        # Obtener timeline editor
        active_seq = hiero.ui.activeSequence()
        if not active_seq:
            print("❌ No hay secuencia activa")
            return

        timeline_editor = hiero.ui.getTimelineEditor(active_seq)
        if not timeline_editor:
            print("❌ No se pudo obtener timeline editor")
            return

        print(f"✅ Timeline editor obtenido: {type(timeline_editor)}")

        # Explorar métodos disponibles
        methods = [m for m in dir(timeline_editor) if not m.startswith('_')]
        print(f"📋 Métodos disponibles ({len(methods)}):")

        interesting_methods = [
            'sequence', 'setSequence', 'activeSequence', 'setActiveSequence',
            'currentSequence', 'setCurrentSequence', 'openSequence', 'switchToSequence',
            'changeSequence', 'loadSequence', 'activateSequence'
        ]

        for method in interesting_methods:
            if method in methods:
                print(f"  ✅ {method}")
                try:
                    # Intentar obtener información del método
                    attr = getattr(timeline_editor, method)
                    if callable(attr):
                        print(f"      - Es callable")
                    else:
                        try:
                            value = attr
                            print(f"      - Valor: {value}")
                        except:
                            print(f"      - No se puede acceder al valor")
                except Exception as e:
                    print(f"      - Error: {e}")
            else:
                print(f"  ❌ {method}")

        # Ver si hay métodos relacionados con secuencias
        seq_methods = [m for m in methods if 'sequence' in m.lower()]
        if seq_methods:
            print(f"\n🔍 Métodos relacionados con 'sequence' ({len(seq_methods)}):")
            for method in seq_methods:
                print(f"  - {method}")

        # Explorar la jerarquía del timeline editor
        print(f"\n🏗️ Jerarquía del Timeline Editor:")
        print(f"  - Tipo: {type(timeline_editor)}")
        print(f"  - MRO: {[cls.__name__ for cls in type(timeline_editor).__mro__]}")

        # Ver atributos importantes
        print(f"\n📊 Atributos importantes:")
        attrs_to_check = ['sequence', 'activeSequence', 'currentSequence']
        for attr in attrs_to_check:
            if hasattr(timeline_editor, attr):
                try:
                    value = getattr(timeline_editor, attr)
                    print(f"  - {attr}: {value}")
                except Exception as e:
                    print(f"  - {attr}: Error al acceder ({e})")

    except Exception as e:
        print(f"❌ Error explorando timeline: {e}")
        import traceback
        traceback.print_exc()

def explore_hiero_ui_methods():
    """Explora métodos disponibles en hiero.ui relacionados con secuencias"""
    print("\n🔍 Explorando métodos de hiero.ui...")

    try:
        ui_methods = [m for m in dir(hiero.ui) if not m.startswith('_')]
        seq_related_methods = [m for m in ui_methods if 'sequence' in m.lower() or 'timeline' in m.lower()]

        print(f"✅ Métodos en hiero.ui relacionados con sequence/timeline ({len(seq_related_methods)}):")
        for method in seq_related_methods:
            print(f"  - {method}")

        # Verificar si hay métodos alternativos a openInTimeline
        alt_methods = ['openSequence', 'switchToSequence', 'activateSequence', 'setActiveSequence']
        print(f"\n🎯 Métodos alternativos potenciales:")
        for method in alt_methods:
            if method in ui_methods:
                print(f"  ✅ {method} - disponible")
            else:
                print(f"  ❌ {method} - no disponible")

    except Exception as e:
        print(f"❌ Error explorando hiero.ui: {e}")

def explore_sequence_switching():
    """Explora cómo cambiar secuencias sin openInTimeline"""
    print("\n🔄 Explorando formas de cambiar secuencia...")

    try:
        # Obtener información actual
        active_seq = hiero.ui.activeSequence()
        if not active_seq:
            print("❌ No hay secuencia activa")
            return

        print(f"📋 Secuencia actual: {active_seq.name()}")

        # Obtener proyecto y todas las secuencias
        projects = hiero.core.projects()
        if not projects:
            print("❌ No hay proyectos")
            return

        project = projects[0]
        sequences = project.sequences()
        print(f"📂 Total de secuencias en proyecto: {len(sequences)}")

        # Encontrar otra secuencia
        target_seq = None
        for seq in sequences:
            if seq.name() != active_seq.name():
                target_seq = seq
                break

        if not target_seq:
            print("❌ No hay otras secuencias para probar")
            return

        print(f"🎯 Secuencia objetivo: {target_seq.name()}")

        # Explorar métodos del proyecto
        print(f"\n🔧 Explorando métodos del proyecto...")
        project_methods = [m for m in dir(project) if 'sequence' in m.lower() or 'active' in m.lower()]
        print(f"  Métodos relacionados: {project_methods}")

        # Ver si hay forma de cambiar la secuencia activa del proyecto
        if hasattr(project, 'setActiveSequence'):
            print(f"  ✅ proyecto.setActiveSequence() encontrado")
        else:
            print(f"  ❌ proyecto.setActiveSequence() no encontrado")

        # Explorar si hay métodos en hiero.ui para cambiar secuencia
        ui_alt_methods = []
        for attr_name in dir(hiero.ui):
            if 'active' in attr_name.lower() and 'sequence' in attr_name.lower():
                ui_alt_methods.append(attr_name)

        if ui_alt_methods:
            print(f"  ✅ Métodos alternativos en hiero.ui: {ui_alt_methods}")
            for method in ui_alt_methods:
                try:
                    attr = getattr(hiero.ui, method)
                    if callable(attr):
                        print(f"    - {method} es callable")
                    else:
                        print(f"    - {method} = {attr}")
                except Exception as e:
                    print(f"    - {method} error: {e}")
        else:
            print(f"  ❌ No se encontraron métodos alternativos en hiero.ui")

    except Exception as e:
        print(f"❌ Error explorando cambio de secuencia: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Función principal"""
    print("=" * 70)
    print("EXPLORACIÓN: Métodos Alternativos para Cambiar Secuencia")
    print("=" * 70)

    explore_timeline_methods()
    explore_hiero_ui_methods()
    explore_sequence_switching()

    print("\n" + "=" * 70)
    print("FIN DE EXPLORACIÓN")
    print("=" * 70)

if __name__ == "__main__":
    main()
