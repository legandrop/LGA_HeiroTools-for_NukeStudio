# -*- coding: utf-8 -*-

"""
____________________________________________________________________

  LGA_NKS_ScanManager v1.01 | Lega

  Gestor de escaneo para el panel de proyectos LGA.

  v1.01: Los carteles de aviso pasan al helper LGA_NKS_MessageBox con el estilo del pack.
____________________________________________________________________

"""

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtCore
from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning

# Importar funciones necesarias del módulo principal
# Estas serán importadas desde el archivo principal cuando se importe este módulo
ScanWorker = None
debug_print = None
print_debug_messages = None


def initialize_scan_dependencies(scan_worker_class, debug_func, print_debug_func):
    """Inicializar las dependencias externas necesarias para el scan manager"""
    global ScanWorker, debug_print, print_debug_messages
    ScanWorker = scan_worker_class
    debug_print = debug_func
    print_debug_messages = print_debug_func


class ScanManager:
    """Clase para manejar las operaciones de escaneo"""

    @staticmethod
    def start_scan(panel):
        """Iniciar el proceso de escaneo"""
        debug_print("🚀 Iniciando escaneo desde botón refresh...")
        panel.refresh_button.setEnabled(False)

        debug_print("👷 Creando ScanWorker...")
        worker = ScanWorker()
        worker.signals.scan_finished.connect(lambda proyectos, abiertos: ScanManager.on_scan_finished(panel, proyectos, abiertos))
        worker.signals.error.connect(lambda error: ScanManager.on_scan_error(panel, error))
        worker.signals.debug_output.connect(lambda: print_debug_messages())
        debug_print("🏃 Ejecutando ScanWorker en thread pool...")
        QtCore.QThreadPool.globalInstance().start(worker)
        debug_print("✅ ScanWorker enviado a thread pool")

    @staticmethod
    def on_scan_finished(panel, proyectos_encontrados, proyectos_abiertos):
        """Callback cuando el escaneo se completa exitosamente"""
        debug_print("🎉 Escaneo completado exitosamente!")
        debug_print(f"   📊 Proyectos encontrados: {len(proyectos_encontrados)}")
        debug_print(f"   📂 Grupos de proyectos abiertos: {len(proyectos_abiertos)}")

        panel.proyectos_encontrados = proyectos_encontrados
        panel.proyectos_abiertos = proyectos_abiertos

        # Obtener información de proyectos con versiones más nuevas
        debug_print("🔍 Buscando proyectos con versiones más nuevas...")
        from LGA_Projects_Panel_ScanProjects import get_projects_with_newer_versions
        proyectos_con_version_nueva = get_projects_with_newer_versions()
        panel.proyectos_con_version_nueva = proyectos_con_version_nueva
        debug_print(f"   📈 Proyectos con versiones nuevas: {len(proyectos_con_version_nueva)}")

        panel.refresh_button.setEnabled(True)

        debug_print("🔄 Llamando a update_projects_display...")
        panel.update_projects_display()

    @staticmethod
    def on_scan_error(panel, error_msg):
        """Callback cuando ocurre un error durante el escaneo"""
        debug_print(f"❌ ERROR durante el escaneo: {error_msg}")
        panel.refresh_button.setEnabled(True)
        show_warning(panel, "Error de Escaneo", error_msg)
