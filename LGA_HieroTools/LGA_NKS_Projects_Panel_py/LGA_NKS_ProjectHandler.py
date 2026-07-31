# -*- coding: utf-8 -*-

"""
____________________________________________________________________

  LGA_NKS_ProjectHandler v1.01 | Lega

  Gestor de manejo de proyectos para el panel de proyectos LGA.

  v1.01: 'project_key' y 'vfx_folder' de los proyectos abiertos salen de la ruta en disco
____________________________________________________________________

"""

import os
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtCore
import hiero.core

# Importar funciones necesarias del módulo principal
# Estas serán importadas desde el archivo principal cuando se importe este módulo
ProjectItem = None
is_project_open = None
get_project_sequences = None
debug_print = None


def initialize_project_dependencies(project_item_class, is_open_func, get_seq_func, debug_func):
    """Inicializar las dependencias externas necesarias para el project handler"""
    global ProjectItem, is_project_open, get_project_sequences, debug_print
    ProjectItem = project_item_class
    is_project_open = is_open_func
    get_project_sequences = get_seq_func
    debug_print = debug_func


class ProjectHandler:
    """Clase para manejar las operaciones relacionadas con proyectos"""

    @staticmethod
    def update_projects_display(panel):
        """Actualizar la visualización de la lista de proyectos"""
        debug_print("🔄 Actualizando display de proyectos...")
        debug_print(f"   📊 Proyectos encontrados: {len(panel.proyectos_encontrados)}")
        debug_print(f"   📂 Proyectos abiertos: {len(panel.proyectos_abiertos)} grupos")

        from LGA_Projects_Panel_ScanProjects import obtener_clave_proyecto

        # Limpiar items anteriores
        for i in reversed(range(panel.projects_layout.count())):
            item = panel.projects_layout.itemAt(i)
            if item.widget():
                item.widget().setParent(None)

        panel.project_items.clear()

        if not panel.proyectos_encontrados:
            no_projects_label = QtWidgets.QLabel("No se encontraron proyectos en T:\\")
            no_projects_label.setStyleSheet("color: #666; font-style: italic;")
            no_projects_label.setAlignment(QtCore.Qt.AlignCenter)
            panel.projects_layout.addWidget(no_projects_label)
            panel.info_label.setText("")
            return

        # Crear lista combinada de proyectos a mostrar
        proyectos_a_mostrar = []

        # Primero, agregar proyectos que están abiertos (incluso si tienen versiones más nuevas)
        for nombre_base, proyectos_grupo in panel.proyectos_abiertos.items():
            # Usar el proyecto más reciente del grupo
            proyecto_mas_reciente = proyectos_grupo[0]  # Ya están ordenados por versión

            # Verificar si este proyecto tiene una versión más nueva
            has_newer_version = nombre_base in panel.proyectos_con_version_nueva
            newer_version_info = panel.proyectos_con_version_nueva.get(nombre_base) if has_newer_version else None

            # El proyecto de trabajo sale de la carpeta VFX- de la ruta, no del nombre del
            # archivo: ERSO_SUP y ERSO_Breakdown son los dos ERSO y comparten color.
            project_key = obtener_clave_proyecto(proyecto_mas_reciente["ruta"], nombre_base)

            # Crear info del proyecto basado en el proyecto abierto
            proyecto_info = {
                "nombre_base": nombre_base,
                "version": proyecto_mas_reciente["version_str"],
                "ruta_hrox": proyecto_mas_reciente["ruta"],
                "vfx_folder": f"VFX-{project_key}",
                "sup_folder": nombre_base,
                "project_key": project_key,
                "proyecto_abierto": proyecto_mas_reciente["proyecto"],
                "has_newer_version": has_newer_version,
                "newer_version_info": newer_version_info
            }
            proyectos_a_mostrar.append(proyecto_info)
            debug_print(f"   ➕ Agregando proyecto ABIERTO: {nombre_base} {proyecto_mas_reciente['version_str']}")

        # Segundo, agregar proyectos que NO están abiertos (versiones del disco)
        for proyecto_info in panel.proyectos_encontrados:
            nombre_base = proyecto_info.get("nombre_base", "")

            # Si este proyecto ya está en la lista como abierto, saltarlo
            proyecto_ya_agregado = any(p.get("nombre_base") == nombre_base for p in proyectos_a_mostrar)
            if proyecto_ya_agregado:
                debug_print(f"   ⏭️ Saltando proyecto del disco (ya agregado como abierto): {nombre_base}")
                continue

            # Verificar si tiene versión más nueva (no debería, ya que no está abierto)
            has_newer_version = False
            newer_version_info = None

            proyecto_info_copy = proyecto_info.copy()
            proyecto_info_copy["has_newer_version"] = has_newer_version
            proyecto_info_copy["newer_version_info"] = newer_version_info

            proyectos_a_mostrar.append(proyecto_info_copy)
            debug_print(f"   ➕ Agregando proyecto del disco: {nombre_base} {proyecto_info.get('version')}")

        # Ahora mostrar todos los proyectos
        for proyecto_info in sorted(proyectos_a_mostrar, key=lambda x: x.get("nombre_base", "")):
            nombre_base = proyecto_info.get("nombre_base", "")
            version = proyecto_info.get("version", "")
            ruta_hrox = proyecto_info.get("ruta_hrox", "")
            vfx_folder = proyecto_info.get("vfx_folder", "")
            sup_folder = proyecto_info.get("sup_folder", "")

            # Calcular el display formateado
            project_display_name = nombre_base
            if "_SUP" in nombre_base:
                project_display_name = nombre_base.split("_SUP")[0]
            clean_ver = version.lstrip('v')
            formatted_display = f"{project_display_name} (v{clean_ver})"

            debug_print(f"   Creando item UI para: {nombre_base} {version}")
            debug_print(f"      Origen: {vfx_folder}/{sup_folder}")
            debug_print(f"      Archivo: {os.path.basename(ruta_hrox) if ruta_hrox else 'N/A'}")
            debug_print(f"      Display: {formatted_display}")

            # Usar las flags que ya calculamos
            has_newer_version = proyecto_info.get("has_newer_version", False)
            newer_version_info = proyecto_info.get("newer_version_info", None)

            debug_print(f"   🔍 Proyecto {nombre_base}: has_newer_version={has_newer_version}, is_open={isinstance(proyecto_info.get('proyecto_abierto'), hiero.core.Project)}")

            item = ProjectItem(proyecto_info, panel, has_newer_version, newer_version_info)
            item.project_label.mousePressEvent = lambda e, p=proyecto_info: ProjectHandler.on_project_click(panel, p)
            # Instalar event filter para hover del project label
            item.project_label.installEventFilter(panel)

            # Verificar si este proyecto está abierto
            is_open = "proyecto_abierto" in proyecto_info
            debug_print(f"      Estado abierto: {is_open}")

            if is_open:
                debug_print("      Este proyecto aparecera como ABIERTO en la UI")
                proyecto_obj = proyecto_info["proyecto_abierto"]
                sequences = get_project_sequences(proyecto_obj)
                item.set_open_state(True, sequences, proyecto_obj)

            panel.project_items[proyecto_info.get("nombre_base", "")] = item
            panel.projects_layout.addWidget(item)

        total_proyectos = len(proyectos_a_mostrar)
        proyectos_abiertos_count = sum(1 for item in panel.project_items.values() if item.is_open)
        panel.info_label.setText(f"{total_proyectos} proyectos encontrados, {proyectos_abiertos_count} abiertos")

        debug_print(f"✅ UI actualizada completamente!")
        debug_print(f"   📊 Total items en UI: {len(panel.project_items)}")
        debug_print(f"   📂 Proyectos marcados como abiertos: {proyectos_abiertos_count}")
        debug_print(f"   📋 Etiqueta inferior: '{panel.info_label.text()}'")

        # Mostrar resumen detallado de lo que se muestra en UI
        debug_print("RESUMEN DE PROYECTOS EN UI:")
        for nombre_base, item in sorted(panel.project_items.items()):
            version = item.project_info.get("version", "")
            estado = "ABIERTA" if item.is_open else "cerrada"
            update_indicator = " (🔼 UPDATE disponible)" if item.has_newer_version and item.is_open else ""

            # Calcular display formateado igual que en UI
            project_display_name = nombre_base
            if "_SUP" in nombre_base:
                project_display_name = nombre_base.split("_SUP")[0]
            clean_ver = version.lstrip('v')
            formatted_display = f"{project_display_name} (v{clean_ver})"
            icono = "▼" if item.is_open else "▶"

            debug_print(f"   {icono} {formatted_display} ({estado}){update_indicator}")

    @staticmethod
    def on_project_click(panel, proyecto_info):
        """Manejar el click en un proyecto para abrirlo"""
        ruta_hrox = proyecto_info.get("ruta_hrox", "")
        nombre_base = proyecto_info.get("nombre_base", "")
        version = proyecto_info.get("version", "")
        vfx_folder = proyecto_info.get("vfx_folder", "")
        sup_folder = proyecto_info.get("sup_folder", "")

        debug_print(f"🖱️ Click en proyecto: {nombre_base}")
        debug_print(f"   📁 Origen: {vfx_folder}/{sup_folder}")
        debug_print(f"   📄 Archivo: {os.path.basename(ruta_hrox) if ruta_hrox else 'N/A'}")
        debug_print(f"   🔢 Versión en UI: v{version}")

        try:
            debug_print(f"📂 Abriendo proyecto desde: {ruta_hrox}")
            proyecto = hiero.core.openProject(ruta_hrox)
            debug_print(f"✅ Proyecto abierto exitosamente: {proyecto.name()}")
            debug_print("🔄 Iniciando re-escaneo automático...")
            panel.start_scan()
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                panel,
                "Error al abrir proyecto",
                f"No se pudo abrir el proyecto {nombre_base}:\n{str(e)}",
            )

    @staticmethod
    def on_update_project_click(panel, newer_version_info):
        """Manejar el click en el botón de update para actualizar proyecto a versión más nueva"""
        proyecto_actual = newer_version_info.get("proyecto_abierto")
        ruta_nueva_version = newer_version_info.get("ruta_version_nueva")
        version_actual = newer_version_info.get("version_actual")
        version_nueva = newer_version_info.get("version_nueva")

        debug_print(f"🔄 Click en botón update: {proyecto_actual.name()}")
        debug_print(f"   📊 Versión actual: {version_actual}")
        debug_print(f"   🎯 Nueva versión: {version_nueva}")
        debug_print(f"   📁 Ruta nueva: {ruta_nueva_version}")

        # Verificar que la ruta de la nueva versión existe
        import os
        if not os.path.exists(ruta_nueva_version):
            QtWidgets.QMessageBox.warning(
                panel,
                "Error",
                f"No se puede encontrar el archivo de la nueva versión:\n{ruta_nueva_version}"
            )
            return

        try:
            # Paso 1: Cerrar el proyecto actual
            debug_print(f"📂 Cerrando proyecto actual: {proyecto_actual.name()}")
            print(f"Cerrando proyecto: {proyecto_actual.name()}")

            # Cerrar el proyecto usando el método close()
            proyecto_actual.close()

            # Paso 2: Abrir el proyecto de la nueva versión
            debug_print(f"📂 Abriendo nueva versión: {ruta_nueva_version}")
            print(f"Abriendo nueva versión: {os.path.basename(ruta_nueva_version)}")

            nuevo_proyecto = hiero.core.openProject(ruta_nueva_version)

            if nuevo_proyecto:
                print(
                    f"Proyecto actualizado exitosamente a: {os.path.basename(ruta_nueva_version)}"
                )
                debug_print(f"✅ Nuevo proyecto cargado: {nuevo_proyecto.name()}")

                # Iniciar re-escaneo automático para actualizar la UI
                panel.start_scan()
            else:
                print(f"Error al abrir el proyecto: {ruta_nueva_version}")
                # Si no se pudo abrir la nueva versión, intentar reabrir la original
                try:
                    print("Intentando reabrir el proyecto original...")
                    hiero.core.openProject(newer_version_info.get("ruta_version_actual", ""))
                except Exception as restore_e:
                    print(f"Error al restaurar proyecto original: {str(restore_e)}")

        except Exception as e:
            print(f"Error durante el proceso de cambio de versión: {str(e)}")
            debug_print(f"❌ Excepción al cambiar versión: {str(e)}")
            # Intentar reabrir el proyecto original si algo salió mal
            try:
                print("Intentando reabrir el proyecto original debido al error...")
                ruta_original = newer_version_info.get("ruta_version_actual", "")
                if ruta_original:
                    hiero.core.openProject(ruta_original)
            except Exception as restore_e:
                print(f"Error al restaurar proyecto original: {str(restore_e)}")