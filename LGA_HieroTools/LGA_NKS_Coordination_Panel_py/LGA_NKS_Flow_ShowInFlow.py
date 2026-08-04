"""
____________________________________________________________________

  LGA_NKS_Flow_ShowInFlow v1.31 | Lega

  Abre la URL de la task Comp del shot, tomando información del clip en TRACK_comp_EXR bajo el playhead.
  Si no hay clip en playhead, usa el clip seleccionado como fallback.
  Verifica si existe más de un shot con el mismo nombre y te pide que selecciones uno.
  Usa el módulo utilitario LGA_NKS_GetClip para obtener clips.

  v1.31: Limita máximo 2 threads simultáneos para evitar cuelgues de ShotGrid/navegador.
         Ahora funciona con clips offline (sin media presente).
  v1.30: Eliminado navegador hardcodeado (Chrome). Usa el navegador por defecto del sistema.
  v1.29: Project name extraído desde el segmento VFX-NOMBRE del path del archivo
         (con fallback al primer bloque del filename si el path no contiene VFX-).
         Corrige proyectos como PROJALT cuyos shots tienen prefijo PROJA en el filename.
  v1.28: Actualizado para usar shift+click para abrir el shot completo en Flow
  v1.27: Agrega manejo con hilos secundarios para procesar los clips en paralelo sin bloquear el hilo principal
  v1.26: Actualizado para ser compatible con ambos sistemas de nomenclatura:
         - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
         - PROYECTO_SEQ_SHOT (3 bloques simplificado)
____________________________________________________________________
"""

import os
import sys
import re
import platform
import hiero.core
import hiero.ui
import webbrowser
import base64  # Importar base64
import binascii  # Importar binascii para la excepcion
from pathlib import Path
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt
QMessageBox = QtWidgets.QMessageBox
QDialog = QtWidgets.QDialog
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton
QRunnable = QtCore.QRunnable
Slot = QtCore.Slot
QThreadPool = QtCore.QThreadPool
Signal = QtCore.Signal
QObject = QtCore.QObject

# Variable global para controlar el debug
DEBUG = False  # Poner en False para desactivar los mensajes de debug

# Limitar threads simultáneos para evitar cuelgues de ShotGrid/navegador
MAX_CONCURRENT_THREADS = 2


# Funcion debug_print
def debug_print(*message):
    if DEBUG:
        print(*message)


def get_user_config_dir():
    """
    Obtiene el directorio de configuracion del usuario segun el sistema operativo.
    Windows: %APPDATA%
    Mac: ~/Library/Application Support
    """
    system = platform.system()
    if system == "Windows":
        config_path = os.getenv("APPDATA")
        if not config_path:
            debug_print("Error: No se pudo encontrar la variable de entorno APPDATA.")
            return None
    elif system == "Darwin":  # macOS
        config_path = os.path.expanduser("~/Library/Application Support")
    else:
        # Para otros sistemas, usar el directorio home como fallback
        config_path = os.path.expanduser("~/.config")
        debug_print(
            f"Sistema no reconocido ({system}), usando ~/.config como fallback."
        )

    return config_path


# Agregar la ruta de shotgun_api3 desde Shared
shared_dir = Path(__file__).parent.parent / "LGA_NKS_Shared"
sys.path.insert(0, str(shared_dir))
import shotgun_api3

# --- INICIO: Importar el módulo de configuración segura ---
sys.path.append(str(shared_dir))
from SecureConfig_Reader import get_flow_credentials
# --- FIN: Importar el módulo de configuración segura ---

# Importar funciones de nomenclatura compartidas
from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    extract_project_name_from_path,
    clean_base_name,
)

# Importar utilidades para obtener clips
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    from LGA_NKS_Shared.LGA_NKS_GetClip import get_clips_to_process
    # Sincronizar el debug con el módulo utilitario
    from LGA_NKS_Shared import LGA_NKS_GetClip as clip_utils
    clip_utils.DEBUG = DEBUG
else:
    debug_print("ERROR: No se encontró el módulo LGA_NKS_GetClip")


class ShotSelectionDialog(QDialog):
    """Dialogo para seleccionar entre multiples shots encontrados"""

    def __init__(self, shots_with_tasks, parent=None):
        super().__init__(parent)
        self.result_value = None

        self.setWindowTitle("Seleccion de Shot")
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Mensaje
        msg = QLabel(f"Se encontraron {len(shots_with_tasks)} shots. Selecciona uno:")
        layout.addWidget(msg)

        # Botones para cada shot
        for i, (shot, tasks) in enumerate(shots_with_tasks):
            comp_tasks = [t for t in tasks if "Comp" in t["content"]]
            if comp_tasks:
                text = (
                    f"Shot ID: {shot['id']} - Comp: {comp_tasks[0]['sg_status_list']}"
                )
            else:
                text = f"Shot ID: {shot['id']} - Sin Comp"

            btn = QPushButton(text)
            btn.clicked.connect(lambda checked=False, idx=i: self.select_shot(idx))
            layout.addWidget(btn)

        # Boton cancelar
        cancel_btn = QPushButton("Cancelar")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

    def select_shot(self, index):
        self.result_value = index
        self.accept()



class ShotGridManager:
    def __init__(self, url, login, password):
        self.sg = shotgun_api3.Shotgun(url, login=login, password=password)

    def find_shot_and_tasks(self, project_name, shot_code):
        debug_print(f"Buscando proyecto: {project_name}, shot: {shot_code}")

        # Buscar proyecto
        projects = self.sg.find(
            "Project", [["name", "is", project_name]], ["id", "name"]
        )
        if not projects:
            debug_print("No se encontro el proyecto")
            return None, None

        project_id = projects[0]["id"]
        debug_print(f"Proyecto encontrado: {project_id}")

        # Buscar shots
        filters = [
            ["project", "is", {"type": "Project", "id": project_id}],
            ["code", "is", shot_code],
        ]
        fields = ["id", "code", "description"]
        shots = self.sg.find("Shot", filters, fields)

        if not shots:
            debug_print("No se encontro el shot")
            return None, None

        debug_print(f"Encontrados {len(shots)} shots")

        # Si hay un solo shot, usarlo directamente (sin tiempo extra)
        if len(shots) == 1:
            shot = shots[0]
            debug_print(f"Shot unico encontrado: {shot['id']}")
            tasks = self.find_tasks_for_shot(shot["id"])
            return shot, tasks

        # Si hay multiples shots, devolver todos para que se maneje en el hilo principal
        shots_with_tasks = []
        for shot in shots:
            tasks = self.find_tasks_for_shot(shot["id"])
            shots_with_tasks.append((shot, tasks))
            debug_print(f"Shot {shot['id']} tiene {len(tasks)} tasks")

        # Devolver estructura especial que indica multiples shots
        return "MULTIPLE_SHOTS", shots_with_tasks

    def find_tasks_for_shot(self, shot_id):
        debug_print(f"Buscando tareas para el shot: {shot_id}")
        filters = [["entity", "is", {"type": "Shot", "id": shot_id}]]
        fields = ["id", "content", "sg_status_list"]
        tasks = self.sg.find("Task", filters, fields)
        debug_print(f"Tareas encontradas: {tasks}")
        return tasks

    def get_task_url(self, task_id):
        return f"{self.sg.base_url}/detail/Task/{task_id}"

    def get_shot_url(self, shot_id):
        return f"{self.sg.base_url}/detail/Shot/{shot_id}"


class HieroOperations:
    def __init__(self, shotgrid_manager):
        self.sg_manager = shotgrid_manager

    def parse_exr_name(self, file_name):
        """Extrae el nombre base del archivo EXR usando funciones compartidas de NamingUtils."""
        # Usar función compartida para limpiar el nombre base (compatible con ambos formatos)
        base_name = clean_base_name(file_name)
        # Buscar versión en el nombre original (antes de limpiar)
        version_match = re.search(r"_v(\d+)", file_name)
        version_number = version_match.group(1) if version_match else "Unknown"
        return base_name, version_number

    def process_clip(self, clip):
        """Procesa un clip específico y abre la URL correspondiente."""
        if not clip:
            debug_print("No se proporciono un clip para procesar.")
            return False

        if isinstance(clip, hiero.core.EffectTrackItem):
            debug_print("El clip es un efecto, se omite.")
            return False

        if not clip.source().mediaSource().isMediaPresent():
            debug_print("El clip no tiene media presente.")
            return False

        fileinfos = clip.source().mediaSource().fileinfos()
        if not fileinfos:
            debug_print("No se encontraron fileinfos para el clip.")
            return False

        file_path = fileinfos[0].filename()
        exr_name = os.path.basename(file_path)
        debug_print(f"Hiero clip file path: {file_path}")
        debug_print(f"Hiero clip name: {exr_name}")

        base_name, hiero_version_number = self.parse_exr_name(exr_name)
        debug_print(
            f"Parsed base name: {base_name}, version number: {hiero_version_number}"
        )

        # Usar funciones compartidas para extraer información (compatible con ambos formatos)
        project_name = extract_project_name_from_path(file_path)
        if project_name:
            debug_print(f"Project name (from path): {project_name}")
        else:
            project_name = extract_project_name(base_name)
            debug_print(f"Project name (from filename fallback): {project_name}")
        shot_code = extract_shot_code(base_name)
        debug_print(f"Project name: {project_name}, shot code: {shot_code}")

        shot, tasks = self.sg_manager.find_shot_and_tasks(
            project_name, shot_code
        )

        # Verificar si tenemos multiples shots
        if shot == "MULTIPLE_SHOTS":
            # Devolver informacion para manejar en el hilo principal
            return ("MULTIPLE_SHOTS", tasks)

        if shot:
            # Buscar task Comp
            comp_task = None
            for task in tasks:
                if task["content"] == "Comp":
                    comp_task = task
                    break

            if comp_task:
                # Si hay task Comp, abrir la URL de la task
                task_url = self.sg_manager.get_task_url(comp_task["id"])
                debug_print(
                    f"  - Task: {comp_task['content']} (Status: {comp_task['sg_status_list']}) URL: {task_url}"
                )
                target_url = task_url
            else:
                # Si no hay task Comp, abrir la URL del shot
                shot_url = self.sg_manager.get_shot_url(shot["id"])
                debug_print(
                    f"No hay task Comp. Abriendo URL del shot: {shot_url}"
                )
                target_url = shot_url

            webbrowser.open(target_url)
            return True
        else:
            debug_print(
                "No se encontro el shot correspondiente en ShotGrid."
            )
            return False


    def open_url_in_browser(self, url):
        webbrowser.open(url)
        debug_print(f"Opening {url} in default browser...")


class ShowInFlowWorkerSignals(QObject):
    """Señales para comunicar resultados del worker"""
    result_ready = Signal(object, object)  # result, clip_info
    error = Signal(str, object)  # error_message, clip_info


class ShowInFlowWorker(QRunnable):
    """Worker para procesar un clip en hilo secundario sin bloquear el principal"""
    
    def __init__(self, clip_info):
        super(ShowInFlowWorker, self).__init__()
        self.clip_info = clip_info
        self.signals = ShowInFlowWorkerSignals()
    
    @Slot()
    def run(self):
        """Procesa el clip en un hilo secundario."""
        file_path, exr_name = self.clip_info
        
        # Leer credenciales desde el archivo .dat usando la funcion adaptada
        url, login, password = get_flow_credentials()
        if not url or not login or not password:
            config_path = get_user_config_dir() or "LGA/ToolPack/ShowInFlow.dat"
            error_msg = f"No se pudieron leer las credenciales desde: {config_path}\nRevise la consola para detalles y asegúrese de que el archivo esté completo usando LGA_ToolPack_settings."
            self.signals.error.emit(error_msg, self.clip_info)
            return

        # Si las credenciales son validas, proceder con la logica original
        try:
            debug_print(f"Conectando a ShotGrid URL: {url} con login: {login}")
            sg_manager = ShotGridManager(url, login, password)
            hiero_ops = HieroOperations(sg_manager)
            
            # Extraer información del clip
            base_name, hiero_version_number = hiero_ops.parse_exr_name(exr_name)
            debug_print(
                f"Parsed base name: {base_name}, version number: {hiero_version_number}"
            )

            # Usar funciones compartidas para extraer información (compatible con ambos formatos)
            project_name = extract_project_name_from_path(file_path)
            if project_name:
                debug_print(f"Project name (from path): {project_name}")
            else:
                project_name = extract_project_name(base_name)
                debug_print(f"Project name (from filename fallback): {project_name}")
            shot_code = extract_shot_code(base_name)
            debug_print(f"Project name: {project_name}, shot code: {shot_code}")

            shot, tasks = sg_manager.find_shot_and_tasks(
                project_name, shot_code
            )

            # Verificar si tenemos multiples shots
            if shot == "MULTIPLE_SHOTS":
                # Devolver informacion para manejar en el hilo principal
                self.signals.result_ready.emit(("MULTIPLE_SHOTS", tasks), self.clip_info)
                return

            if shot:
                # Buscar task Comp
                comp_task = None
                for task in tasks:
                    if task["content"] == "Comp":
                        comp_task = task
                        break

                if comp_task:
                    # Si hay task Comp, abrir la URL de la task
                    task_url = sg_manager.get_task_url(comp_task["id"])
                    debug_print(
                        f"  - Task: {comp_task['content']} (Status: {comp_task['sg_status_list']}) URL: {task_url}"
                    )
                    target_url = task_url
                else:
                    # Si no hay task Comp, abrir la URL del shot
                    shot_url = sg_manager.get_shot_url(shot["id"])
                    debug_print(
                        f"No hay task Comp. Abriendo URL del shot: {shot_url}"
                    )
                    target_url = shot_url

                # Abrir URL en el hilo principal usando señal
                self.signals.result_ready.emit(("OPEN_URL", target_url), self.clip_info)
                return
            
            # No se encontró el shot
            error_msg = "No se pudo procesar el clip. Verifique que haya un clip en el track bajo el playhead o que haya seleccionado un clip válido."
            debug_print("No se encontro el shot correspondiente en ShotGrid.")
            self.signals.error.emit(error_msg, self.clip_info)

        except shotgun_api3.AuthenticationFault:
            # Error especifico de autenticacion
            error_message = f"Error de autenticación con ShotGrid.\nVerifique las credenciales en:\n{get_user_config_dir()}"
            debug_print("Error de autenticación con ShotGrid.")
            self.signals.error.emit(error_message, self.clip_info)

        except Exception as e:
            # Otros errores durante la conexion o procesamiento
            error_message = (
                f"Ocurrió un error al conectar o procesar la información de ShotGrid: {e}"
            )
            debug_print(f"Error detallado: {e}")
            self.signals.error.emit(error_message, self.clip_info)


def show_in_flow_from_selected_clip():
    """
    Funcion principal que puede ser llamada desde el panel.
    Procesa los clips seleccionados en el track TRACK_comp_EXR (o el clip en playhead) y abre la task comp en Flow.
    Si hay múltiples clips seleccionados en el track TRACK_comp_EXR, procesa todos ellos.
    """
    # Obtener los clips en el hilo principal ANTES de entrar al hilo secundario
    # Usa prioritize_multiple_selection=True para priorizar múltiples clips seleccionados sobre playhead
    # ⚠️ IMPORTANTE: Usar track_name=None para respetar TRACK_comp_EXR del módulo
    clips = get_clips_to_process(track_name=None, prioritize_multiple_selection=True)
    
    if not clips:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Show in Flow - Error")
        msg.setText("No se pudo obtener ningún clip. Verifique que haya un clip en el track bajo el playhead o que haya seleccionado clips válidos.")
        msg.exec_()
        return

    # Función para manejar resultados cuando lleguen
    def handle_result(result, clip_info):
        """Maneja el resultado del procesamiento de un clip"""
        file_path, exr_name = clip_info
        
        # Si es una tupla con múltiples shots, manejar en el hilo principal
        if isinstance(result, tuple) and result[0] == "MULTIPLE_SHOTS":
            shots_with_tasks = result[1]

            # Mostrar dialogo de seleccion en el hilo principal
            dialog = ShotSelectionDialog(shots_with_tasks)
            if dialog.exec_() == QDialog.Accepted and dialog.result_value is not None:
                selected_shot, selected_tasks = shots_with_tasks[dialog.result_value]
                debug_print(f"Shot seleccionado: {selected_shot['id']}")

                # Buscar task Comp y abrir URL
                url, login, password = get_flow_credentials()
                if url and login and password:
                    sg_manager = ShotGridManager(url, login, password)

                    # Intentar encontrar task Comp
                    comp_task = None
                    for task in selected_tasks:
                        if task["content"] == "Comp":
                            comp_task = task
                            break

                    if comp_task:
                        # Si hay task Comp, abrir la URL de la task
                        task_url = sg_manager.get_task_url(comp_task["id"])
                        debug_print(f"Abriendo URL de la task Comp: {task_url}")
                        target_url = task_url
                    else:
                        # Si no hay task Comp, abrir la URL del shot
                        shot_url = sg_manager.get_shot_url(selected_shot["id"])
                        debug_print(f"No hay task Comp. Abriendo URL del shot: {shot_url}")
                        target_url = shot_url

                    # Abrir URL con el navegador por defecto
                    webbrowser.open(target_url)

        elif isinstance(result, tuple) and result[0] == "OPEN_URL":
            # Abrir URL directamente
            target_url = result[1]
            webbrowser.open(target_url)

    def handle_error(error_msg, clip_info):
        """Maneja errores del procesamiento de un clip"""
        file_path, exr_name = clip_info
        debug_print(f"Error procesando clip {os.path.basename(file_path)}: {error_msg}")
        # No mostrar mensaje de error para cada clip, solo loguear
    
    # Procesar todos los clips en paralelo sin bloquear el hilo principal
    for clip in clips:
        try:
            fileinfos = clip.source().mediaSource().fileinfos()
            if not fileinfos:
                debug_print(f"No se encontraron fileinfos para el clip {clip.name()}. Saltando...")
                continue

            # Extraer información del clip en el hilo principal
            file_path = fileinfos[0].filename()
            exr_name = os.path.basename(file_path)
            clip_info = (file_path, exr_name)

            # Crear worker para procesar este clip
            worker = ShowInFlowWorker(clip_info)

            # Conectar señales para manejar resultados cuando lleguen
            worker.signals.result_ready.connect(handle_result)
            worker.signals.error.connect(handle_error)

            # Ejecutar en hilo separado sin bloquear (con límite de threads)
            thread_pool = QThreadPool.globalInstance()
            thread_pool.setMaxThreadCount(MAX_CONCURRENT_THREADS)
            thread_pool.start(worker)
        except Exception as e:
            debug_print(f"Error procesando clip {clip.name()}: {e}")
            continue


def show_shot_in_flow_from_selected_clip():
    """
    Funcion principal que puede ser llamada desde el panel con Shift+Click.
    Procesa los clips seleccionados en el track TRACK_comp_EXR (o el clip en playhead) y abre el shot completo en Flow (sin task específica).
    Si hay múltiples clips seleccionados en el track TRACK_comp_EXR, procesa todos ellos.
    """
    debug_print("=== SHOW SHOT IN FLOW (Shift+Click) ===")

    # Obtener los clips en el hilo principal ANTES de entrar al hilo secundario
    # Usa prioritize_multiple_selection=True para priorizar múltiples clips seleccionados sobre playhead
    # ⚠️ IMPORTANTE: Usar track_name=None para respetar TRACK_comp_EXR del módulo
    clips = get_clips_to_process(track_name=None, prioritize_multiple_selection=True)

    if not clips:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Show Shot in Flow - Error")
        msg.setText("No se pudo obtener ningún clip. Verifique que haya un clip en el track bajo el playhead o que haya seleccionado clips válidos.")
        msg.exec_()
        return

    # Función para manejar resultados cuando lleguen
    def handle_result(result, clip_info):
        """Maneja el resultado del procesamiento de un clip"""
        file_path, exr_name = clip_info

        # Si es una tupla con múltiples shots, manejar en el hilo principal
        if isinstance(result, tuple) and result[0] == "MULTIPLE_SHOTS":
            shots_with_tasks = result[1]

            # Mostrar dialogo de seleccion en el hilo principal
            dialog = ShotSelectionDialog(shots_with_tasks)
            if dialog.exec_() == QDialog.Accepted and dialog.result_value is not None:
                selected_shot, selected_tasks = shots_with_tasks[dialog.result_value]
                debug_print(f"Shot seleccionado: {selected_shot['id']}")

                # Abrir URL del shot directamente (no buscar task Comp)
                url, login, password = get_flow_credentials()
                if url and login and password:
                    sg_manager = ShotGridManager(url, login, password)

                    # Abrir la URL del shot directamente
                    shot_url = sg_manager.get_shot_url(selected_shot["id"])
                    debug_print(f"Abriendo URL del shot: {shot_url}")
                    target_url = shot_url

                    # Abrir URL con el navegador por defecto
                    webbrowser.open(target_url)

        elif isinstance(result, tuple) and result[0] == "OPEN_URL":
            # Abrir URL directamente
            target_url = result[1]
            webbrowser.open(target_url)

    def handle_error(error_msg, clip_info):
        """Maneja errores del procesamiento de un clip"""
        file_path, exr_name = clip_info
        debug_print(f"Error procesando clip {os.path.basename(file_path)}: {error_msg}")
        # No mostrar mensaje de error para cada clip, solo loguear

    # Procesar todos los clips en paralelo sin bloquear el hilo principal
    for clip in clips:
        try:
            fileinfos = clip.source().mediaSource().fileinfos()
            if not fileinfos:
                debug_print(f"No se encontraron fileinfos para el clip {clip.name()}. Saltando...")
                continue

            # Extraer información del clip en el hilo principal
            file_path = fileinfos[0].filename()
            exr_name = os.path.basename(file_path)
            clip_info = (file_path, exr_name)

            # Crear worker para procesar este clip
            worker = ShowShotInFlowWorker(clip_info)

            # Conectar señales para manejar resultados cuando lleguen
            worker.signals.result_ready.connect(handle_result)
            worker.signals.error.connect(handle_error)

            # Ejecutar en hilo separado sin bloquear (con límite de threads)
            thread_pool = QThreadPool.globalInstance()
            thread_pool.setMaxThreadCount(MAX_CONCURRENT_THREADS)
            thread_pool.start(worker)
        except Exception as e:
            debug_print(f"Error procesando clip {clip.name()}: {e}")
            continue


class ShowShotInFlowWorkerSignals(QObject):
    """Señales para comunicar resultados del worker de shot"""
    result_ready = Signal(object, object)  # result, clip_info
    error = Signal(str, object)  # error_message, clip_info


class ShowShotInFlowWorker(QRunnable):
    """Worker para procesar un clip en hilo secundario sin bloquear el principal - Versión para Shot"""

    def __init__(self, clip_info):
        super(ShowShotInFlowWorker, self).__init__()
        self.clip_info = clip_info
        self.signals = ShowShotInFlowWorkerSignals()

    @Slot()
    def run(self):
        """Procesa el clip en un hilo secundario."""
        file_path, exr_name = self.clip_info

        # Leer credenciales desde el archivo .dat usando la funcion adaptada
        url, login, password = get_flow_credentials()
        if not url or not login or not password:
            config_path = get_user_config_dir() or "LGA/ToolPack/ShowInFlow.dat"
            error_msg = f"No se pudieron leer las credenciales desde: {config_path}\nRevise la consola para detalles y asegúrese de que el archivo esté completo usando LGA_ToolPack_settings."
            self.signals.error.emit(error_msg, self.clip_info)
            return

        # Si las credenciales son validas, proceder con la logica original
        try:
            debug_print(f"Conectando a ShotGrid URL: {url} con login: {login}")
            sg_manager = ShotGridManager(url, login, password)
            hiero_ops = HieroOperations(sg_manager)

            # Extraer información del clip
            base_name, hiero_version_number = hiero_ops.parse_exr_name(exr_name)
            debug_print(
                f"Parsed base name: {base_name}, version number: {hiero_version_number}"
            )

            # Usar funciones compartidas para extraer información (compatible con ambos formatos)
            project_name = extract_project_name_from_path(file_path)
            if project_name:
                debug_print(f"Project name (from path): {project_name}")
            else:
                project_name = extract_project_name(base_name)
                debug_print(f"Project name (from filename fallback): {project_name}")
            shot_code = extract_shot_code(base_name)
            debug_print(f"Project name: {project_name}, shot code: {shot_code}")

            shot, tasks = sg_manager.find_shot_and_tasks(
                project_name, shot_code
            )

            # Verificar si tenemos multiples shots
            if shot == "MULTIPLE_SHOTS":
                # Devolver informacion para manejar en el hilo principal
                self.signals.result_ready.emit(("MULTIPLE_SHOTS", tasks), self.clip_info)
                return

            if shot:
                # Siempre abrir la URL del shot (sin buscar task específica)
                shot_url = sg_manager.get_shot_url(shot["id"])
                debug_print(f"Abriendo URL del shot: {shot_url}")
                target_url = shot_url

                # Abrir URL en el hilo principal usando señal
                self.signals.result_ready.emit(("OPEN_URL", target_url), self.clip_info)
                return

            # No se encontró el shot
            error_msg = "No se pudo procesar el clip. Verifique que haya un clip en el track bajo el playhead o que haya seleccionado un clip válido."
            debug_print("No se encontro el shot correspondiente en ShotGrid.")
            self.signals.error.emit(error_msg, self.clip_info)

        except shotgun_api3.AuthenticationFault:
            # Error especifico de autenticacion
            error_message = f"Error de autenticación con ShotGrid.\nVerifique las credenciales en:\n{get_user_config_dir()}"
            debug_print("Error de autenticación con ShotGrid.")
            self.signals.error.emit(error_message, self.clip_info)

        except Exception as e:
            # Otros errores durante la conexion o procesamiento
            error_message = (
                f"Ocurrió un error al conectar o procesar la información de ShotGrid: {e}"
            )
            debug_print(f"Error detallado: {e}")
            self.signals.error.emit(error_message, self.clip_info)


if __name__ == "__main__":
    show_in_flow_from_selected_clip()
