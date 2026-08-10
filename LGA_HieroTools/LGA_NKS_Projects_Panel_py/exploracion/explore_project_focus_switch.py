"""
Exploración: Cambio de foco entre proyectos en Hiero
===================================================

Objetivo: Entender cómo cambiar el foco/activo entre proyectos abiertos en Hiero.

Necesidades:
- Listar proyectos activos
- Identificar cuál está en foco
- Cambiar foco a otro proyecto
"""

import hiero.core
import hiero.ui

def explore_projects_info():
    """Explora información básica de proyectos"""
    print("🔍 EXPLORACIÓN: Información de proyectos")
    print("=" * 50)

    projects = hiero.core.projects()
    print(f"📊 Número de proyectos: {len(projects)}")

    for i, project in enumerate(projects):
        print(f"\n📁 Proyecto {i}:")
        print(f"   Nombre: {project.name()}")
        print(f"   Path: {project.path()}")
        print(f"   Tipo: {type(project)}")

        # Explorar métodos disponibles
        methods = [method for method in dir(project) if not method.startswith('_')]
        print(f"   Métodos disponibles: {len(methods)}")
        print(f"   Primeros 10 métodos: {methods[:10]}")

        # Verificar si hay algún indicador de "activo"
        try:
            active_seq = hiero.ui.activeSequence()
            if active_seq:
                active_project = active_seq.project()
                is_active = active_project == project
                print(f"   ¿Es el proyecto activo? {is_active}")
                print(f"   Secuencia activa: {active_seq.name()}")
            else:
                print("   No hay secuencia activa")
        except Exception as e:
            print(f"   Error verificando activo: {e}")

def explore_ui_methods():
    """Explora métodos de hiero.ui relacionados con proyectos"""
    print("\n🔍 EXPLORACIÓN: Métodos de hiero.ui")
    print("=" * 50)

    ui_methods = [method for method in dir(hiero.ui) if 'project' in method.lower()]
    print(f"📋 Métodos con 'project' en hiero.ui: {ui_methods}")

    # Explorar todos los métodos de hiero.ui
    all_ui_methods = [method for method in dir(hiero.ui) if not method.startswith('_')]
    print(f"📊 Total métodos en hiero.ui: {len(all_ui_methods)}")

    # Buscar métodos relacionados con cambio de foco o activación
    focus_methods = [m for m in all_ui_methods if any(keyword in m.lower() for keyword in ['focus', 'active', 'current', 'switch', 'set'])]
    print(f"🎯 Métodos potenciales para cambio de foco: {focus_methods}")

def explore_open_project():
    """Explora cómo abrir proyectos y si eso cambia el foco"""
    print("\n🔍 EXPLORACIÓN: Abrir proyectos")
    print("=" * 50)

    # Verificar si hiero.core.openProject existe
    if hasattr(hiero.core, 'openProject'):
        print("✅ hiero.core.openProject existe")
    else:
        print("❌ hiero.core.openProject NO existe")

    # Verificar otros métodos de apertura
    open_methods = [method for method in dir(hiero.core) if 'open' in method.lower()]
    print(f"📂 Métodos de apertura en hiero.core: {open_methods}")

def test_project_switching():
    """Prueba diferentes formas de cambiar entre proyectos"""
    print("\n🧪 TESTING: Cambio entre proyectos")
    print("=" * 50)

    projects = hiero.core.projects()
    if len(projects) < 2:
        print("❌ Necesito al menos 2 proyectos para testing")
        return

    print(f"✅ Encontrados {len(projects)} proyectos")

    # Mostrar estado inicial
    print("\n📊 ESTADO INICIAL:")
    for i, project in enumerate(projects):
        try:
            active_seq = hiero.ui.activeSequence()
            is_active = active_seq and active_seq.project() == project
            status = "🎯 ACTIVO" if is_active else "📁"
            print(f"   {status} Proyecto {i}: {project.name()}")
        except:
            print(f"   📁 Proyecto {i}: {project.name()}")

    # Intentar diferentes métodos para cambiar de proyecto
    print("\n🔄 INTENTANDO CAMBIOS DE PROYECTO:")

    # Método 1: Intentar openProject (si existe)
    if hasattr(hiero.core, 'openProject'):
        print("📂 Método 1: hiero.core.openProject()")
        try:
            # Tomar el segundo proyecto (índice 1)
            target_project = projects[1]
            print(f"   Intentando abrir: {target_project.name()}")

            # Esto probablemente va a abrir el proyecto en una nueva ventana
            # pero tal vez también cambie el foco
            # hiero.core.openProject(target_project.path())

            print("   ⚠️  Comentado para evitar abrir nueva ventana")
        except Exception as e:
            print(f"   ❌ Error: {e}")

    # Método 2: Buscar en hiero.ui
    print("📂 Método 2: Buscar en hiero.ui")
    ui_methods = [m for m in dir(hiero.ui) if not m.startswith('_')]
    set_methods = [m for m in ui_methods if m.startswith('set') or 'active' in m.lower()]
    print(f"   Métodos candidatos: {set_methods}")

    # Método 3: Verificar si hay algún método para setActiveProject o similar
    print("📂 Método 3: Explorar setActive o similares")
    for method_name in ['setActiveProject', 'setCurrentProject', 'activateProject', 'switchToProject']:
        if hasattr(hiero.ui, method_name):
            print(f"   ✅ Encontrado: hiero.ui.{method_name}")
        else:
            print(f"   ❌ No encontrado: hiero.ui.{method_name}")

def main():
    """Función principal de exploración"""
    print("🚀 EXPLORACIÓN: Cambio de foco entre proyectos")
    print("=" * 60)

    explore_projects_info()
    explore_ui_methods()
    explore_open_project()
    test_project_switching()

    print("\n" + "=" * 60)
    print("✅ EXPLORACIÓN COMPLETADA")
    print("💡 Siguientes pasos: Analizar resultados y crear script de switching")

if __name__ == "__main__":
    main()
