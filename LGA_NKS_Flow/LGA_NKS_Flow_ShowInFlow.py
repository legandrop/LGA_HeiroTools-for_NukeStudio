"""
_____________________________________________________________________________________________________

  LGA_NKS_Flow_ShowInFlow v1.2 | Lega Pugliese
  Abre la URL de la task Comp del shot, tomando la informacion del nombre del clip seleccionado
  Verifica si existe más de un shot con el mismo nombre y te pide que selecciones uno
_____________________________________________________________________________________________________
"""

import os
import sys
import re
import platform
import hiero.core
import hiero.ui
import webbrowser
import threading
import subprocess
import base64  # Importar base64
import binascii  # Importar binascii para la excepcion
from PySide2.QtWidgets import (
    QMessageBox,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)
from PySide2.QtCore import Qt

# Variable global para controlar el debug
DEBUG = False  # Poner en False para desactivar los mensajes de debug


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


# Agregar la ruta de la carpeta shotgun_api3 al sys.path
# Buscar en la carpeta LGA_ToolPack donde está el shotgun_api3
toolpack_dir = None
for root, dirs, files in os.walk(os.path.expanduser("~/.nuke")):
    if "LGA_ToolPack" in dirs:
        toolpack_dir = os.path.join(root, "LGA_ToolPack")
        break

if toolpack_dir:
    shotgun_api_path = os.path.join(toolpack_dir, "shotgun_api3")
    if os.path.exists(shotgun_api_path):
        sys.path.append(shotgun_api_path)

# Ahora importamos shotgun_api3
import shotgun_api3

# Constantes para el archivo de configuracion
CONFIG_FILE_NAME = "ShowInFlow.dat"  # Cambiar extension a .dat
CONFIG_URL_KEY = "shotgrid_url"  # Mantener nombres de clave conceptualmente
CONFIG_LOGIN_KEY = "shotgrid_login"
CONFIG_PASSWORD_KEY = "shotgrid_password"


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


# --- Inicio: Funciones de manejo de configuracion (modificadas para base64) ---


def get_config_path():
    """Devuelve la ruta completa al archivo de configuracion."""
    try:
        user_config_dir = get_user_config_dir()
        if not user_config_dir:
            return None
        config_dir = os.path.join(user_config_dir, "LGA", "ToolPack")
        return os.path.join(config_dir, CONFIG_FILE_NAME)
    except Exception as e:
        debug_print(f"Error al obtener la ruta de configuracion: {e}")
        return None


def ensure_config_exists():
    """
    Asegura que el directorio de configuracion y el archivo .dat existan.
    Si no existen, los crea con valores vacios codificados.
    """
    config_file_path = get_config_path()
    if not config_file_path:
        return

    config_dir = os.path.dirname(config_file_path)

    try:
        # Crear el directorio si no existe
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)
            debug_print(f"Directorio de configuracion creado: {config_dir}")

        # Crear el archivo .dat si no existe, con lineas vacias codificadas
        if not os.path.exists(config_file_path):
            # Escribir lineas vacias codificadas para mantener estructura
            empty_encoded = base64.b64encode("".encode("utf-8")).decode("utf-8")
            with open(config_file_path, "w", encoding="utf-8") as configfile:
                configfile.write(f"{empty_encoded}\\n")  # URL
                configfile.write(f"{empty_encoded}\\n")  # Login
                configfile.write(f"{empty_encoded}\\n")  # Password
            debug_print(
                f"Archivo de configuración creado: {config_file_path}. Por favor, complételo usando LGA_ToolPack_settings."
            )

    except Exception as e:
        debug_print(f"Error al asegurar la configuración: {e}")


def get_credentials_from_config():
    """
    Lee las credenciales de ShotGrid desde el archivo .dat codificado.
    Devuelve (url, login, password) decodificados o (None, None, None) si hay errores.
    """
    config_file_path = get_config_path()
    if not config_file_path or not os.path.exists(config_file_path):
        debug_print(
            f"Archivo de configuración (.dat) no encontrado en la ruta esperada: {config_file_path}"
        )
        return None, None, None

    try:
        with open(config_file_path, "r", encoding="utf-8") as configfile:
            lines = configfile.readlines()

        if len(lines) < 3:
            debug_print(
                f"Archivo de configuración {config_file_path} está incompleto o corrupto."
            )
            return None, None, None

        # Decodificar cada linea
        sg_url_encoded = lines[0].strip()
        sg_login_encoded = lines[1].strip()
        sg_password_encoded = lines[2].strip()

        sg_url = base64.b64decode(sg_url_encoded).decode("utf-8")
        sg_login = base64.b64decode(sg_login_encoded).decode("utf-8")
        sg_password = base64.b64decode(sg_password_encoded).decode("utf-8")

        # Validar que los valores no esten vacios despues de decodificar
        if sg_url and sg_login and sg_password:
            return sg_url, sg_login, sg_password
        else:
            debug_print(
                f"Una o más credenciales en {config_file_path} están vacías (después de decodificar)."
            )
            return None, None, None

    except (binascii.Error, UnicodeDecodeError) as e:  # Usar binascii.Error
        debug_print(
            f"Error al decodificar el archivo de configuración {config_file_path}: {e}"
        )
        return None, None, None
    except Exception as e:
        debug_print(f"Error inesperado al leer la configuración codificada: {e}")
        return None, None, None


# Asegurarse de que el archivo de configuracion existe al iniciar
ensure_config_exists()

# Verificacion del sistema operativo y configuracion de la ruta del navegador
if platform.system() == "Windows":
    browser_path = "C:/Program Files/Google/Chrome/Application/chrome.exe %s"
elif platform.system() == "Darwin":  # macOS
    browser_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
else:
    browser_path = ""

use_default_browser = False  # Si esta en True, usa el navegador por defecto


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
        # Ajustar el manejo del formato del nombre del archivo EXR
        if "%04d" in file_name:
            file_name = file_name.replace(".%", "_%")  # Reemplazar patron para analisis

        base_name = re.sub(r"_%04d\.exr$", "", file_name)
        version_match = re.search(r"_v(\d+)", base_name)
        version_number = version_match.group(1) if version_match else "Unknown"
        return base_name, version_number

    def process_selected_clips(self):
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("No se encontro una secuencia activa en Hiero.")
            return False

        te = hiero.ui.getTimelineEditor(seq)
        selected_clips = te.selection()

        if not selected_clips:
            debug_print("No se han seleccionado clips en el timeline.")
            return False

        for clip in selected_clips:
            if not isinstance(clip, hiero.core.EffectTrackItem):
                if clip.source().mediaSource().isMediaPresent():
                    fileinfos = clip.source().mediaSource().fileinfos()
                    if not fileinfos:
                        continue

                    file_path = fileinfos[0].filename()
                    exr_name = os.path.basename(file_path)
                    debug_print(f"Hiero clip file path: {file_path}")
                    debug_print(f"Hiero clip name: {exr_name}")

                    base_name, hiero_version_number = self.parse_exr_name(exr_name)
                    debug_print(
                        f"Parsed base name: {base_name}, version number: {hiero_version_number}"
                    )

                    project_name = base_name.split("_")[0]
                    parts = base_name.split("_")
                    shot_code = "_".join(parts[:5])
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

                        if use_default_browser:
                            webbrowser.open(target_url)
                        else:
                            self.open_url_in_browser(target_url)
                        return True
                    else:
                        debug_print(
                            "No se encontro el shot correspondiente en ShotGrid."
                        )
                        return False
        return False

    def open_url_in_browser(self, url):
        if platform.system() == "Darwin":  # macOS
            try:
                subprocess.run([browser_path, url])
                debug_print(f"Opening {url} in specified browser on macOS...")
            except Exception as e:
                debug_print(f"Failed to open URL in specified browser on macOS: {e}")
        elif platform.system() == "Windows":
            debug_print("Windows")
            try:
                webbrowser.get(browser_path).open(url)
                debug_print(f"Opening {url} in specified browser on Windows...")
            except Exception as e:
                debug_print(f"Failed to open URL in specified browser on Windows: {e}")


def threaded_function():
    # Leer credenciales desde el archivo .dat usando la funcion adaptada
    url, login, password = get_credentials_from_config()
    if not url or not login or not password:
        config_path = get_config_path() or "LGA/ToolPack/ShowInFlow.dat"
        return f"No se pudieron leer las credenciales desde: {config_path}\nRevise la consola para detalles y asegúrese de que el archivo esté completo usando LGA_ToolPack_settings."

    # Si las credenciales son validas, proceder con la logica original
    try:
        debug_print(f"Conectando a ShotGrid URL: {url} con login: {login}")
        sg_manager = ShotGridManager(url, login, password)
        hiero_ops = HieroOperations(sg_manager)
        result = hiero_ops.process_selected_clips()  # Ejecutar la lógica principal

        if result is True:
            return None  # Indicar éxito

        if result is False:
            return "No se pudo procesar el clip seleccionado. Verifique que haya seleccionado un clip válido."

        # Si result es una tupla, significa que hay múltiples shots
        if isinstance(result, tuple) and result[0] == "MULTIPLE_SHOTS":
            return result  # Devolver la información para manejar en el hilo principal

    except shotgun_api3.AuthenticationFault:
        # Error especifico de autenticacion
        error_message = f"Error de autenticación con ShotGrid.\nVerifique las credenciales en:\n{get_config_path()}"
        debug_print("Error de autenticación con ShotGrid.")
        return error_message  # Devolver el mensaje de error

    except Exception as e:
        # Otros errores durante la conexion o procesamiento
        error_message = (
            f"Ocurrió un error al conectar o procesar la información de ShotGrid: {e}"
        )
        debug_print(f"Error detallado: {e}")
        return error_message  # Devolver el mensaje de error


def show_in_flow_from_selected_clip():
    """
    Funcion principal que puede ser llamada desde el panel.
    Procesa el clip seleccionado y abre la task comp en Flow.
    """
    # Crear un objeto para almacenar el resultado del hilo
    result_container = {}

    def run_in_thread():
        result_container["result"] = threaded_function()

    thread = threading.Thread(target=run_in_thread)
    thread.start()
    thread.join()  # Esperar a que el hilo termine

    # Verificar el resultado del hilo
    result = result_container["result"]

    # Si es None, todo fue exitoso
    if result is None:
        return

    # Si es una tupla con múltiples shots, manejar en el hilo principal
    if isinstance(result, tuple) and result[0] == "MULTIPLE_SHOTS":
        shots_with_tasks = result[1]

        # Mostrar dialogo de seleccion en el hilo principal
        dialog = ShotSelectionDialog(shots_with_tasks)
        if dialog.exec_() == QDialog.Accepted and dialog.result_value is not None:
            selected_shot, selected_tasks = shots_with_tasks[dialog.result_value]
            debug_print(f"Shot seleccionado: {selected_shot['id']}")

            # Buscar task Comp y abrir URL
            url, login, password = get_credentials_from_config()
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

                # Usar la misma lógica que en el flujo normal
                if use_default_browser:
                    webbrowser.open(target_url)
                else:
                    hiero_ops = HieroOperations(sg_manager)
                    hiero_ops.open_url_in_browser(target_url)
                return
        return

    # Si es un string, es un mensaje de error
    if isinstance(result, str):
        # Mostrar el error usando QMessageBox
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Show in Flow - Error")
        msg.setText(result)
        msg.exec_()


if __name__ == "__main__":
    show_in_flow_from_selected_clip()
