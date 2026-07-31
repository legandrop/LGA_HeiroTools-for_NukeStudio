"""
____________________________________________________________________

  LGA_NKS_Workers v1.01 | Lega

  Workers para operaciones en background en el panel de proyectos LGA.

  v1.01: Se pasa el base_path del contexto a get_open_projects_info()
____________________________________________________________________

"""

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore

# Importar funciones necesarias del módulo principal
# Estas serán importadas desde el archivo principal cuando se importe este módulo
scan_projects_on_disk = None
get_open_projects_info = None
debug_print = None


def initialize_dependencies(scan_func, get_open_func, debug_func):
    """Inicializar las dependencias externas necesarias para los workers"""
    global scan_projects_on_disk, get_open_projects_info, debug_print
    scan_projects_on_disk = scan_func
    get_open_projects_info = get_open_func
    debug_print = debug_func


class WorkerSignals(QtCore.QObject):
    """Señales para comunicar resultados del worker de escaneo"""

    scan_finished = QtCore.Signal(list, dict)  # proyectos_encontrados, proyectos_abiertos
    error = QtCore.Signal(str)
    debug_output = QtCore.Signal()  # Señal para imprimir logs al final


class ScanWorker(QtCore.QRunnable):
    """Worker para escanear proyectos en background"""

    def __init__(self, base_path=None):
        super(ScanWorker, self).__init__()
        self.base_path = base_path
        self.signals = WorkerSignals()

    def run(self):
        """Ejecuta el escaneo en hilo secundario"""
        debug_print(f"⚙️ ScanWorker.run() ejecutándose en hilo secundario...")
        base_path = self.base_path
        if base_path is None:
            try:
                from LGA_Projects_Panel_ScanProjects import get_base_scan_path
                base_path = get_base_scan_path()
            except Exception:
                base_path = None
        debug_print(f"   📍 Base path: {base_path}")
        try:
            debug_print("🔍 Ejecutando scan_projects_on_disk()...")
            proyectos_encontrados = scan_projects_on_disk(base_path)
            debug_print("📂 Ejecutando get_open_projects_info()...")
            # Mismo base_path que el escaneo: los abiertos del otro contexto no entran.
            proyectos_abiertos = get_open_projects_info(base_path)
            debug_print("📡 Emitiendo señal scan_finished...")
            self.signals.scan_finished.emit(proyectos_encontrados, proyectos_abiertos)
            debug_print("✅ ScanWorker completado exitosamente")
            # Emitir señal para imprimir logs al final
            self.signals.debug_output.emit()
        except Exception as e:
            debug_print(f"💥 ERROR en ScanWorker: {str(e)}")
            import traceback
            debug_print(f"Traceback: {traceback.format_exc()}")
            self.signals.error.emit(f"Error durante escaneo: {str(e)}")
            # Emitir señal para imprimir logs al final incluso en error
            self.signals.debug_output.emit()
