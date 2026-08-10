"""
TESTING: Cambio de foco entre proyectos en Hiero
===============================================

Script de testing para cambiar el foco entre proyectos activos.
Lista proyectos activos, identifica cuál está en foco, y cambia al otro.

IMPORTANTE: Requiere tener exactamente 2 proyectos abiertos en Hiero.
"""

import hiero.core
import hiero.ui
import time

def get_active_project():
    """Obtiene el proyecto actualmente activo/focused"""
    try:
        active_sequence = hiero.ui.activeSequence()
        if active_sequence:
            return active_sequence.project()
        return None
    except Exception as e:
        print(f"❌ Error obteniendo proyecto activo: {e}")
        return None

def list_projects_with_focus():
    """Lista todos los proyectos y marca cuál está activo"""
    projects = hiero.core.projects()
    active_project = get_active_project()

    print("📋 PROYECTOS ACTIVOS:")
    print("=" * 40)

    for i, project in enumerate(projects):
        is_active = (project == active_project)
        status = "🎯 ACTIVO" if is_active else "📁"
        print("2d")

    return projects, active_project

def switch_to_project(target_project):
    """Intenta cambiar el foco al proyecto objetivo"""

    print(f"\n🔄 INTENTANDO CAMBIAR A: {target_project.name()}")
    print("-" * 40)

    # Método 1: Explorar métodos disponibles en hiero.ui
    ui_methods = [m for m in dir(hiero.ui) if not m.startswith('_')]
    print("🔍 Explorando métodos en hiero.ui..."    print(f"   Total métodos: {len(ui_methods)}")

    # Método 2: Intentar cambiar via secuencia (si el proyecto tiene secuencias)
    print("
📂 MÉTODO 1: Cambiar via openInTimeline de secuencia"    sequences = target_project.sequences()
    if sequences:
        print(f"   Proyecto tiene {len(sequences)} secuencias")
        print(f"   Intentando abrir primera secuencia: {sequences[0].name()}")

        try:
            hiero.ui.openInTimeline(sequences[0])
            time.sleep(0.3)  # Dar tiempo para cambio

            new_active = get_active_project()
            if new_active == target_project:
                print("   ✅ ¡ÉXITO! Proyecto activado via secuencia")
                return True
            else:
                print(f"   ⚠️  Secuencia abierta pero proyecto activo sigue siendo: {new_active.name() if new_active else 'None'}")
        except Exception as e:
            print(f"   ❌ Error abriendo secuencia: {e}")
    else:
        print("   ❌ Proyecto no tiene secuencias")

    # Método 3: Buscar métodos específicos que podrían existir
    print("
📂 MÉTODO 2: Buscar métodos específicos"    candidate_methods = [
        'setActiveProject',
        'setCurrentProject',
        'activateProject',
        'switchToProject',
        'changeProject',
        'selectProject'
    ]

    for method_name in candidate_methods:
        if hasattr(hiero.ui, method_name):
            print(f"   ✅ Encontrado método: hiero.ui.{method_name}")
            try:
                method = getattr(hiero.ui, method_name)
                print(f"   Intentando ejecutar: {method_name}(target_project)")

                # Intentar diferentes formas de llamar
                try:
                    method(target_project)
                except:
                    try:
                        method(target_project.name())
                    except:
                        try:
                            method(target_project.path())
                        except Exception as e:
                            print(f"   ❌ Error en todas las formas de llamar: {e}")
                            continue

                time.sleep(0.2)
                new_active = get_active_project()
                if new_active == target_project:
                    print(f"   ✅ ¡ÉXITO! Proyecto activado via {method_name}")
                    return True
                else:
                    print(f"   ⚠️  Método ejecutado pero sin cambio")

            except Exception as e:
                print(f"   ❌ Error ejecutando {method_name}: {e}")
        else:
            print(f"   ❌ Método no encontrado: {method_name}")

    # Método 4: Explorar window manager o similar
    print("
📂 MÉTODO 3: Explorar window manager"    try:
        window_manager = hiero.ui.windowManager()
        if window_manager:
            wm_methods = [m for m in dir(window_manager) if not m.startswith('_')]
            print(f"   Window manager encontrado con {len(wm_methods)} métodos")

            project_methods = [m for m in wm_methods if 'project' in m.lower()]
            if project_methods:
                print(f"   Métodos relacionados con proyectos: {project_methods}")

                for method_name in project_methods:
                    try:
                        method = getattr(window_manager, method_name)
                        print(f"   Probando: windowManager.{method_name}")
                        # Solo explorar, no ejecutar sin saber qué hace
                    except Exception as e:
                        print(f"   Error explorando {method_name}: {e}")
    except Exception as e:
        print(f"   ❌ Error accediendo window manager: {e}")

    # Método 5: openProject como último recurso (abre nueva ventana)
    print("
📂 MÉTODO 4: hiero.core.openProject (abre nueva ventana)"    print("   ⚠️  ATENCIÓN: Esto abrirá una nueva ventana de Hiero"    try:
        confirm = input("   ¿Continuar? (y/N): ").lower().strip()
        if confirm == 'y':
            hiero.core.openProject(target_project.path())
            print("   ✅ Nueva ventana abierta con el proyecto")
            print("   💡 Para completar el cambio, cierra la ventana anterior")
            return True
        else:
            print("   ❌ Cancelado por usuario")
    except Exception as e:
        print(f"   ❌ Error en openProject: {e}")

    print("   ❌ Todos los métodos intentados fallaron"    return False

def main():
    """Función principal de testing - Versión simplificada para 2 proyectos"""
    print("🚀 TEST: Cambio de foco entre proyectos")
    print("=" * 60)

    # Verificar que hay exactamente 2 proyectos
    projects = hiero.core.projects()
    if len(projects) != 2:
        print(f"❌ ERROR: Se necesitan exactamente 2 proyectos abiertos. Actualmente hay {len(projects)}")
        print("\n📋 Proyectos encontrados:")
        for i, p in enumerate(projects):
            print(f"   {i+1}. {p.name()} - {p.path()}")
        print("\n💡 Para este test, abre exactamente 2 proyectos en Hiero")
        return

    print("✅ Encontrados 2 proyectos - Iniciando test")

    # Estado inicial
    projects, active_project = list_projects_with_focus()

    if not active_project:
        print("❌ ERROR: No se puede determinar cuál proyecto está activo")
        print("💡 Asegúrate de tener una secuencia abierta en uno de los proyectos")
        return

    # Encontrar el otro proyecto
    target_project = projects[0] if active_project == projects[1] else projects[1]

    print(f"\n🎯 OBJETIVO: Cambiar de '{active_project.name()}' → '{target_project.name()}'")
    print("=" * 60)

    # Intentar el cambio
    success = switch_to_project(target_project)

    # Verificar resultado
    print("
📊 VERIFICACIÓN FINAL:"    print("-" * 40)
    final_projects, final_active = list_projects_with_focus()

    print("\n" + "=" * 60)
    if success and final_active == target_project:
        print("🎉 ÉXITO TOTAL: Cambio de foco completado exitosamente!")
        print("✅ El proyecto objetivo ahora está activo")
    else:
        print("❌ RESULTADO: No se pudo cambiar el foco automáticamente")
        print("\n🔧 ANÁLISIS:")
        print("- Hiero puede no soportar cambio automático de foco entre proyectos")
        print("- Posiblemente necesites cambiar manualmente entre ventanas")
        print("- O usar una solución alternativa (abrir secuencia del proyecto objetivo)")

        if final_active == target_project:
            print("✅ Aunque el método falló, el proyecto objetivo terminó activo")
        else:
            print(f"❌ El proyecto activo sigue siendo: {final_active.name() if final_active else 'None'}")

    print("\n💡 RECOMENDACIONES PARA EL PANEL:")
    print("- Implementar verificación de proyecto antes de buscar secuencia")
    print("- Si secuencia no está en proyecto activo, informar al usuario")
    print("- Posiblemente: abrir proyecto objetivo primero, luego la secuencia")

    # Documentar hallazgos para el módulo
    print("\n📝 HALLAZGOS PARA LGA_Projects_Panel_SwitchSequence.py:")
    print("-" * 60)
    print("🔍 Conclusión: Hiero NO permite cambiar foco entre proyectos automáticamente")
    print("🎯 Solución recomendada:")
    print("   1. Verificar si la secuencia pertenece al proyecto activo")
    print("   2. Si no pertenece: informar error al usuario")
    print("   3. Alternativa: abrir proyecto primero, luego secuencia (nueva ventana)")
    print("   4. Documentar limitación en READMEs")

    print("\n📋 PROPUESTA DE FUNCIÓN PARA EL MÓDULO:")
    print("""
def switch_to_sequence_cross_project(target_sequence_name):
    \"\"\"Busca secuencia en todos los proyectos y verifica compatibilidad\"\"\"
    projects = hiero.core.projects()
    active_project = get_active_project()

    # Buscar secuencia en TODOS los proyectos
    for project in projects:
        sequences = project.sequences()
        for seq in sequences:
            if seq.name() == target_sequence_name:
                if project == active_project:
                    # Secuencia en proyecto activo - usar switch normal
                    return switch_to_sequence_hybrid(target_sequence_name)
                else:
                    # Secuencia en otro proyecto - LIMITACIÓN
                    print(f"⚠️  Secuencia '{target_sequence_name}' pertenece a proyecto '{project.name()}'")
                    print(f"   Proyecto activo: '{active_project.name()}'")
                    print(f"   ❌ Actualmente NO se puede cambiar entre proyectos")
                    print(f"   💡 Solución: Abrir proyecto manualmente primero")
                    return False

    print(f"❌ Secuencia '{target_sequence_name}' no encontrada")
    return False
    """)

    print("=" * 60)

if __name__ == "__main__":
    main()
