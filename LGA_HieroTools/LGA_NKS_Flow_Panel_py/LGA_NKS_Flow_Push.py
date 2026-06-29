"""
____________________________________________________________________

  LGA_NKS_Flow_Push v4.02 | Lega

  Envia a flow nuevos estados de las tasks comps.
  En algunos estados permite enviar un mensaje a la version
  También actualiza la base de datos local para mantenerla sincronizada
  Muestra thumbnails de imagenes capturadas en el dialogo de notas para referencia visual
  y envía las imagenes a la nota en Flow
  Actualizado para ser compatible con ambos sistemas de nomenclatura:
  - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
  - PROYECTO_SEQ_SHOT (3 bloques simplificado)

  v4.02: Los errores del Worker de Push y del callback post-push se muestran con
         QMessageBox, evitando fallos silenciosos cuando el conector no completa.

  v4.01: file_path propagado al conector (LGA_NKS_Flow_Push_connector) vía JSON
         para que también use extract_project_name_from_path. El conector además
         normaliza task_name y busca versiones con aliases inversos (_compo_, _cmp_).
  v4.00: Extracción de project_name desde el segmento de ruta "VFX-NOMBRE"
         en lugar del prefijo del filename. file_path se propaga por toda la
         cadena: push_from_selected_clips → Push_Task_Status → Worker/InputDialog.
         Fallback al método anterior si no se encuentra el patrón VFX-.
         Ver docs/Docu_ProjectName_Extraction.md.
  v3.99: Muestra ventana al iniciar el push listando clips cuya task en el filename no coincide con el nombre del track. Solo avisa, no bloquea ni modifica el push.
  v3.98: Prioriza selección explícita del usuario sobre playhead en push multi-task.
         Mejora logs para detallar clips seleccionados, filtrados y procesados.
  v3.97: Soporte multi-task: Push busca clips en todos los TASK_EXR_TRACKS (comp + roto).
         Cuando hay clips de múltiples tasks, muestra dialog para elegir a cuál aplicar el status.
  v3.96: Actualiza el módulo LGA_NKS_Flow_Push_connector.py para que funcione con el sistema de nombres sin descripción.
  v3.95: Agrega aplicación de tags en xyplorer después de actualizar estados exitosamente.
         Si xyplorer no está abierto, simplemente no aplica el tag sin dar error ni crashear el script.
  v3.94: Agrega ruta principal de Python dentro de PipeSync.app para macOS
  v3.93: Agrega método centralizado de selección con función push_from_selected_clips() que usa LGA_NKS_GetClip (Método 2 híbrido).
         Soporta selecciones múltiples del track TRACK_comp_EXR con límite de 4 clips (requiere confirmación).
         Mantiene compatibilidad con Push_Task_Status() para llamadas desde paneles.
  v3.91: Elimina la verificación de versiones con Flow duplicada en el Worker y envía comentarios a la version correcta del clip
  v3.90: Verifica si la version actual es la más alta y muestra un dialogo de advertencia si no lo es
  v3.89: Sistema de resumen con DEBUG_RESUMEN para mostrar solo información esencial
  v3.88: Fix timeout + detección correcta de shot_code con base_name sin versión
  v3.87: Logs detallados de envío de imágenes + Fix extracción de versión
____________________________________________________________________

"""

import os
import re
import sqlite3
import platform
import glob
import shutil
import tempfile
import json
import logging
import queue
from logging.handlers import QueueHandler, QueueListener
# QtCore classes ahora vienen del adapter (se asignarán después del import)
import datetime
import time
import subprocess  # Importar subprocess para abrir archivos
import sys
from pathlib import Path
import hiero.core
import hiero.ui
import ctypes
import ctypes.wintypes
import threading

shared_dir = Path(__file__).parent.parent / "LGA_NKS_Shared"
sys.path.insert(0, str(shared_dir))
import shotgun_api3

# Importar shareds de dominio Flow
flow_shared_dir = shared_dir
sys.path.append(str(flow_shared_dir))
from SecureConfig_Reader import get_flow_credentials

# Importar utilidades de naming
from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    extract_project_name_from_path,
    extract_task_name,
    clean_base_name,
    TASK_NAME_ALIASES,
    normalize_task_name,
)

# Importar utilidades para obtener clips
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    from LGA_NKS_Shared.LGA_NKS_GetClip import (
        get_clips_to_process,
        get_selected_clips,
        TASK_EXR_TRACKS,
    )

    # Sincronizar el debug con el módulo utilitario
    from LGA_NKS_Shared import LGA_NKS_GetClip as clip_utils

    # Se sincronizará después cuando DEBUG se defina
else:
    debug_print("ERROR: No se encontró el módulo LGA_NKS_GetClip")

# LGA_NKS_TaskSelectionDialog y LGA_NKS_TaskMismatchDialog se importan de forma lazy
# (dentro de push_from_selected_clips) para evitar problemas de inicialización Qt.

# Importar compatibilidad Qt para Hiero Panels
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt, QShortcut
from LGA_NKS_Shared.LGA_NKS_PipeSyncPreflight import validate_push_preflight
from LGA_NKS_Shared.LGA_NKS_PipeSyncPaths import get_pipesync_db_path

# Reasignar clases para compatibilidad con código existente
QRunnable = QtCore.QRunnable
Slot = QtCore.Slot
QThreadPool = QtCore.QThreadPool
Signal = QtCore.Signal
QObject = QtCore.QObject
QApplication = QtWidgets.QApplication
QMessageBox = QtWidgets.QMessageBox
QDialog = QtWidgets.QDialog
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QPlainTextEdit = QtWidgets.QPlainTextEdit
QPushButton = QtWidgets.QPushButton
QLabel = QtWidgets.QLabel
QScrollArea = QtWidgets.QScrollArea
QWidget = QtWidgets.QWidget
QCheckBox = QtWidgets.QCheckBox

QKeySequence = QtGui.QKeySequence
QPixmap = QtGui.QPixmap
QIcon = QtGui.QIcon

# Diccionario de traduccion de estados
status_translation = {
    "Corrections": "corr",
    "Corrs_Lega": "revleg",
    "Rev Sebas": "rev_su",
    "Rev Charly": "revcha",
    "Rev Juano": "revjua",
    "Rev Javi": "revjav",
    "Rev Lega": "revleg",
    "Rev Dir": "rev_di",
    "Approved": "apr",
    "Delivery Ok": "check",
    "Rev Dir Den": "rev_di",
    "Rev Hold": "revhld",
}

# Diccionario de estados con tags de xyplorer (igual que en Pull)
# El orden de los valores es:
# (nombre en Flow/ShotGrid, color_hex[, tag XYplorer])
task_status_dict = {
    "noread": ("Not Ready To Start", "#000000", None),
    "wts": ("Waiting to start", "#000000", None),
    "ready": ("Ready To Start", "#8a8a8a", None),
    "progre": ("In Progress", "#7d4cff", None),
    "corr": ("Corrections", "#2e77d4", "Corrections"),
    "rev_su": ("Review Sup", "#bd7f9f", "Rev_Sup"),
    "revcha": ("Review Charly", "#a9909d", "Rev_Sup"),
    "review_charly": ("Review Charly", "#a9909d", "Rev_Sup"),
    "revjua": ("Review Juano", "#7F4B69", "Rev_Sup"),
    "revjav": ("Review Javi", "#9c3e5e", "Rev_Sup"),
    "revleg": ("Review Lega", "#69135e", "Rev_Lega"),
    "revhld": ("Review Hold", "#933100", "Rev Hold"),
    "rev_di": ("Review Dir", "#98c054", "ReviewDir"),
    "pubsh": ("Publish", "#244c19", "Approved"),
    "pbshed": ("Published", "#244c19", "Approved"),
    "apr": ("Approved", "#244c19", "Approved"),
    "check": ("Delivery Checked", "#52c233", "Approved"),
    "omit": ("Omitted", "#244c19", "Approved"),
    "enviad": ("Enviado", "#000000", "Approved"),
    "rev": ("Pending Review", "#000000", None),
    "vwd": ("Viewed", "#000000", None),
}

# Variable global para activar/desactivar tags de XYplorer
XYPlorer_Tags = True

# Variables globales de logging (valores por defecto del MD)
DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True
DEBUG_RESUMEN = False
script_start_time = None
debug_log_listener = None
debug_messages = []
resumen_messages = []
_ACTIVE_FLOW_VERSION_LOAD_WORKERS = []

# Sincronizar debug con el módulo utilitario
try:
    clip_utils.DEBUG = DEBUG
except:
    pass  # Si no se importó el módulo, ignorar


class RelativeTimeFormatter(logging.Formatter):
    """Formatter con hora absoluta y tiempo relativo desde el inicio."""

    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created

        relative_time = record.created - script_start_time
        record.relative_time = f"{relative_time:.3f}s"
        return super().format(record)


def setup_debug_logging(script_name="FlowPush"):
    """Configura el logging para escribir SOLO en archivo."""
    global debug_log_listener

    log_filename = f"debugPy_{script_name}.log"
    log_file_path = os.path.join(
        os.path.dirname(__file__), "..", "logs", log_filename
    )

    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    # Limpieza diaria: si el log no es de hoy, se borra y se agrega encabezado con fecha
    today_str = datetime.date.today().isoformat()
    should_reset = True
    if os.path.exists(log_file_path):
        try:
            with open(log_file_path, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
            should_reset = first_line != f"Fecha: {today_str}"
        except Exception:
            should_reset = True

    if should_reset:
        try:
            with open(log_file_path, "w", encoding="utf-8") as f:
                f.write(f"Fecha: {today_str}\n")
        except Exception as e:
            print(f"Warning: No se pudo resetear el log: {e}")

    logger_name = f"{script_name.lower()}_logger"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:
        logger.handlers.clear()

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    formatter = RelativeTimeFormatter(
        "[%(asctime)s] [%(relative_time)s] %(message)s", datefmt="%H:%M:%S"
    )
    file_handler.setFormatter(formatter)

    log_queue = queue.Queue()
    queue_handler = QueueHandler(log_queue)
    queue_handler.setLevel(logging.DEBUG)
    logger.addHandler(queue_handler)

    if debug_log_listener:
        try:
            debug_log_listener.stop()
        except Exception:
            pass

    debug_log_listener = QueueListener(
        log_queue, file_handler, respect_handler_level=True
    )
    debug_log_listener.daemon = True
    debug_log_listener.start()

    return logger


debug_logger = setup_debug_logging(script_name="FlowPush")


def debug_print(*message, level="info"):
    global script_start_time

    msg = " ".join(str(arg) for arg in message)

    if DEBUG:
        debug_messages.append(msg)

    if DEBUG and DEBUG_LOG:
        if script_start_time is None:
            script_start_time = time.time()
        if level == "debug":
            debug_logger.debug(msg)
        elif level == "warning":
            debug_logger.warning(msg)
        elif level == "error":
            debug_logger.error(msg)
        else:
            debug_logger.info(msg)

    if DEBUG and DEBUG_CONSOLE:
        if script_start_time is None:
            script_start_time = time.time()
        relative_time = time.time() - script_start_time
        print(f"[{relative_time:.3f}s] {msg}")


def debug_resumen_print(message):
    """Imprime mensajes de resumen que se mostrarán al final"""
    if DEBUG_RESUMEN:
        resumen_messages.append(message)


def call_flow_connector(operation, **kwargs):
    """
    Llama al conector de Flow usando el Python personalizado
    Esta es la función más simple posible para delegar operaciones de red
    """
    import shutil
    
    try:
        # Configuración del Python personalizado para Windows
        WINDOWS_PYTHON_PATH = (
            r"C:\Portable\LGA\PipeSync\python_runtime\windows\python.exe"
        )
        
        # Configuración del Python personalizado para macOS
        # Ruta principal: Python dentro de PipeSync.app
        MACOS_PYTHON_PATH = (
            "/Users/leg4/Desktop/Codin/LGA_PipeSync_2/deploy-MacOS-OLD/PipeSync.app/Contents/Resources/python_runtime/macos/python3/bin/python3"
        )

        # Obtener credenciales y agregarlas a los parámetros
        sg_url, sg_login, sg_password = get_flow_credentials()
        kwargs["url"] = sg_url
        kwargs["login"] = sg_login
        kwargs["password"] = sg_password

        # Ruta al script conector
        connector_script = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Flow_Push_connector.py"
        )

        if not os.path.exists(connector_script):
            debug_print(f"Conector no encontrado: {connector_script}")
            return {"success": False, "error": "Conector no encontrado"}

        # Preparar comando según el sistema operativo
        
        if platform.system() == "Windows":
            if os.path.exists(WINDOWS_PYTHON_PATH):
                cmd = [WINDOWS_PYTHON_PATH, connector_script, operation]
            else:
                debug_print(f"WARNING: Python personalizado no encontrado en {WINDOWS_PYTHON_PATH}")
                python3_path = shutil.which("python3")
                if python3_path:
                    cmd = [python3_path, connector_script, operation]
                    debug_print(f"Usando python3 del sistema: {python3_path}")
                else:
                    debug_print("ERROR: No se encontró Python personalizado ni python3 del sistema")
                    return {"success": False, "error": "No se encontró intérprete de Python válido"}
        elif platform.system() == "Darwin":  # macOS
            # Buscar Python personalizado en múltiples ubicaciones posibles
            possible_paths = [
                MACOS_PYTHON_PATH,  # Ruta principal de PipeSync.app
                "/Users/leg4/Desktop/Codin/LGA_PipeSync_2/deploy-MacOS-OLD/PipeSync.app/Contents/Resources/python_runtime/macos/python3/bin/python3.10",
                "/Users/leg4/Portable/LGA/PipeSync/python_runtime/macos/bin/python3",
                "/Users/leg4/Portable/LGA/PipeSync/python_runtime/macos/bin/python",
                os.path.expanduser("~/Portable/LGA/PipeSync/python_runtime/macos/python"),
                os.path.expanduser("~/Portable/LGA/PipeSync/python_runtime/macos/bin/python3"),
            ]
            
            python_path = None
            for path in possible_paths:
                if os.path.exists(path):
                    python_path = path
                    debug_print(f"Python personalizado encontrado: {python_path}")
                    break
            
            if python_path:
                cmd = [python_path, connector_script, operation]
            else:
                # Fallback: intentar usar python3 del sistema
                debug_print(f"WARNING: Python personalizado no encontrado en ninguna de las rutas:")
                for path in possible_paths:
                    debug_print(f"  - {path}")
                python3_path = shutil.which("python3")
                if python3_path:
                    cmd = [python3_path, connector_script, operation]
                    debug_print(f"Usando python3 del sistema: {python3_path}")
                else:
                    debug_print("ERROR: No se encontró Python personalizado ni python3 del sistema")
                    return {"success": False, "error": "No se encontró intérprete de Python válido"}
        else:
            # Linux u otros sistemas
            python3_path = shutil.which("python3")
            if python3_path:
                cmd = [python3_path, connector_script, operation]
            else:
                debug_print("ERROR: No se encontró python3 del sistema")
                return {"success": False, "error": "No se encontró intérprete de Python válido"}

        debug_print(f"Llamando conector: {' '.join(cmd)}")

        # Timeout dinámico basado en la operación
        if operation == "attach_images":
            timeout_seconds = 30  # Más tiempo para subir imágenes
        elif operation == "execute_full_push":
            # Calcular timeout basado en número de imágenes a enviar
            num_images = len(kwargs.get("review_images", []))
            if num_images > 0:
                # 10 segundos base + 10 segundos por imagen (para copiar, subir, etc.)
                timeout_seconds = 10 + (num_images * 10)
                debug_print(
                    f"Timeout ajustado para execute_full_push: {timeout_seconds}s ({num_images} imágenes)"
                )
            else:
                timeout_seconds = 10  # Sin imágenes, timeout normal
        else:
            timeout_seconds = 10  # Tiempo normal para otras operaciones

        # Ejecutar conector
        result = subprocess.run(
            cmd,
            input=json.dumps(kwargs),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

        if result.returncode == 0:
            # Capturar logs de debug del stderr
            if result.stderr:
                for line in result.stderr.strip().split("\n"):
                    if line:
                        debug_print(f"[Conector] {line}")

            try:
                response = json.loads(result.stdout.strip())
                debug_print(f"Conector completado: {response}")
                return response
            except json.JSONDecodeError:
                debug_print(f"Error parseando respuesta JSON")
                debug_print(f"STDOUT recibido: {result.stdout}")
                return {
                    "success": False,
                    "error": f"Respuesta inválida: {result.stdout}",
                }
        else:
            error_msg = f"Conector falló: {result.stderr}"
            debug_print(error_msg)
            return {"success": False, "error": error_msg}

    except subprocess.TimeoutExpired:
        debug_print("Timeout en conector")
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        debug_print(f"Error llamando conector: {e}")
        return {"success": False, "error": str(e)}


def find_review_images(base_name, original_file_name=None):
    """
    Busca imagenes de ReviewPic para el shot y version especificados.
    Retorna una lista de rutas de imagenes encontradas.

    Args:
        base_name: Nombre base sin versión (ej: "BRDA_080_010_comp")
        original_file_name: Nombre original del archivo con versión (opcional, ej: "BRDA_080_010_comp_v007_%04d.exr")
    """
    try:
        # Obtener la ruta del script actual
        script_dir = os.path.dirname(__file__)
        cache_dir = os.path.join(script_dir, "ReviewPic_Cache")

        # Si tenemos el nombre original, extraer la versión de ahí
        version_number_str = None
        if original_file_name:
            import re

            version_match = re.search(r"_v(\d+)", original_file_name)
            if version_match:
                version_number_str = f"v{version_match.group(1)}"
                # Construir el nombre de carpeta exacto: {base_name}_v{version}
                clip_folder_name = f"{base_name}_{version_number_str}"
                clip_dir = os.path.join(cache_dir, clip_folder_name)

                debug_print(f"Buscando imagenes en carpeta específica: {clip_dir}")
                debug_print(f"Nombre de carpeta construido: {clip_folder_name}")

                if os.path.exists(clip_dir):
                    image_pattern = os.path.join(clip_dir, "*.jpg")
                    images = glob.glob(image_pattern)
                    debug_print(
                        f"Imagenes encontradas en {clip_folder_name}: {len(images)}"
                    )
                    return sorted(images)
                else:
                    debug_print(f"Carpeta específica no existe: {clip_dir}")

        # Fallback: buscar en todas las carpetas que coincidan con el patrón {base_name}_v*
        debug_print(f"Buscando en todas las carpetas que coincidan con: {base_name}_v*")
        pattern = os.path.join(cache_dir, f"{base_name}_v*")
        matching_folders = glob.glob(pattern)

        all_images = []
        for folder in matching_folders:
            if os.path.isdir(folder):
                image_pattern = os.path.join(folder, "*.jpg")
                images = glob.glob(image_pattern)
                all_images.extend(images)
                debug_print(
                    f"Encontradas {len(images)} imágenes en {os.path.basename(folder)}"
                )

        if all_images:
            debug_print(f"Total de imagenes encontradas: {len(all_images)}")
            return sorted(all_images)
        else:
            debug_print(
                f"No se encontraron imagenes en ninguna carpeta que coincida con {base_name}_v*"
            )
            return []

    except Exception as e:
        debug_print(f"Error buscando imagenes de review: {e}")
        import traceback

        debug_print(traceback.format_exc())
        return []


class DBManager:
    """Clase para manejar operaciones con la base de datos SQLite local."""

    def __init__(self):
        self.db_path = get_pipesync_db_path("pipesync.db")

        if self.db_path and os.path.exists(self.db_path):
            try:
                self.conn = sqlite3.connect(self.db_path)
                self.conn.row_factory = sqlite3.Row
                debug_print(f"Conexión exitosa a la base de datos: {self.db_path}")
            except Exception as e:
                debug_print(f"Error al conectar a la base de datos: {e}")
                self.conn = None
        else:
            debug_print(f"DB file not found at path: {self.db_path}")
            self.conn = None

    def find_project(self, project_name):
        """Busca un proyecto por nombre en la base de datos."""
        if not self.conn:
            debug_print("No hay conexión a la base de datos")
            return None

        try:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT * FROM projects WHERE project_name = ?", (project_name,)
            )
            return cur.fetchone()
        except Exception as e:
            debug_print(f"Error al buscar proyecto {project_name}: {e}")
            return None

    def find_shot(self, project_name, shot_code):
        """Busca un shot por nombre y código en la base de datos."""
        if not self.conn:
            debug_print("No hay conexión a la base de datos")
            return None

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT s.* FROM shots s
                JOIN projects p ON s.project_id = p.id
                WHERE p.project_name = ? AND s.shot_name = ?
                """,
                (project_name, shot_code),
            )
            return cur.fetchone()
        except Exception as e:
            debug_print(
                f"Error al buscar shot {shot_code} en proyecto {project_name}: {e}"
            )
            return None

    def find_task(self, shot_id, task_name):
        """Busca una tarea específica por nombre y shot_id."""
        if not self.conn:
            debug_print("No hay conexión a la base de datos")
            return None

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT * FROM tasks 
                WHERE shot_id = ? AND LOWER(task_type) = LOWER(?)
                """,
                (shot_id, task_name),
            )
            return cur.fetchone()
        except Exception as e:
            debug_print(
                f"Error al buscar tarea {task_name} para shot_id {shot_id}: {e}"
            )
            return None

    def update_task_status(self, task_id, status):
        """Actualiza el estado de una tarea en la base de datos."""
        if not self.conn:
            debug_print("No hay conexión a la base de datos")
            return False

        try:
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE tasks SET task_status = ? WHERE id = ?", (status, task_id)
            )
            self.conn.commit()
            debug_print(
                f"Estado de la tarea (ID: {task_id}) actualizado a '{status}' en la base de datos local"
            )
            return True
        except Exception as e:
            debug_print(
                f"Error al actualizar el estado de la tarea en la DB local: {e}"
            )
            return False

    def update_version_status(self, task_id, version_number, status):
        """Actualiza el estado de una versión específica en la base de datos."""
        if not self.conn:
            debug_print("No hay conexión a la base de datos")
            return False

        try:
            cur = self.conn.cursor()
            cur.execute(
                "UPDATE versions SET status = ? WHERE task_id = ? AND version_number = ?",
                (status, task_id, version_number),
            )
            self.conn.commit()
            debug_print(
                f"Estado de la versión {version_number} (task_id: {task_id}) actualizado a '{status}' en la base de datos local"
            )
            return True
        except Exception as e:
            debug_print(
                f"Error al actualizar el estado de la versión en la DB local: {e}"
            )
            return False

    def get_user_name(self):
        """Obtiene el nombre del usuario actual desde app_settings."""
        if not self.conn:
            debug_print("No hay conexión a la base de datos para obtener user_name")
            return "Desconocido"
        try:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT setting_value FROM app_settings WHERE setting_key = 'user_name'"
            )
            row = cur.fetchone()
            if row and row[0]:
                return row[0]
            else:
                return "Desconocido"
        except Exception as e:
            debug_print(f"Error al obtener user_name de app_settings: {e}")
            return "Desconocido"

    def get_task_assignee(self, task_id):
        """Obtiene el assignee de una tarea específica."""
        if not self.conn:
            debug_print("No hay conexión a la base de datos")
            return None
        try:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT assigned_to FROM task_assignments WHERE task_id = ?",
                (task_id,),
            )
            assign = cur.fetchone()
            if assign and assign[0]:
                return assign[0]
            else:
                return None
        except Exception as e:
            debug_print(f"Error al obtener assignee de task_id {task_id}: {e}")
            return None

    def add_version_note(self, version_id, content, created_by=None):
        """Añade una nota a una versión en la base de datos."""
        if not self.conn:
            debug_print("No hay conexión a la base de datos")
            return False
        if created_by is None:
            created_by = self.get_user_name()
        # Obtener fecha y hora local con zona horaria en formato igual a Flow
        created_on = (
            datetime.datetime.now().astimezone().isoformat(sep=" ", timespec="seconds")
        )
        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO version_notes (version_id, content, created_by, created_on) 
                VALUES (?, ?, ?, ?)
                """,
                (version_id, content, created_by, created_on),
            )
            self.conn.commit()
            debug_print(
                f"Nota añadida a la versión (ID: {version_id}) en la base de datos local por {created_by} en {created_on}"
            )
            return True
        except Exception as e:
            debug_print(f"Error al añadir nota a la versión en la DB local: {e}")
            return False

    def find_latest_version(self, task_id):
        """Encuentra la versión más reciente para una tarea específica."""
        if not self.conn:
            debug_print("No hay conexión a la base de datos")
            return None

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT * FROM versions 
                WHERE task_id = ? 
                ORDER BY version_number DESC 
                LIMIT 1
                """,
                (task_id,),
            )
            return cur.fetchone()
        except Exception as e:
            debug_print(
                f"Error al buscar la última versión para task_id {task_id}: {e}"
            )
            return None

    def find_version_by_number(self, task_id, version_number):
        """Busca una versión específica por número para una tarea."""
        if not self.conn:
            debug_print("No hay conexión a la base de datos")
            return None

        try:
            cur = self.conn.cursor()
            cur.execute(
                """
                SELECT * FROM versions
                WHERE task_id = ? AND version_number = ?
                LIMIT 1
                """,
                (task_id, version_number),
            )
            return cur.fetchone()
        except Exception as e:
            debug_print(
                f"Error al buscar versión {version_number} para task_id {task_id}: {e}"
            )
            return None

    def close(self):
        """Cierra la conexión a la base de datos."""
        if hasattr(self, "conn") and self.conn:
            try:
                self.conn.close()
                self.conn = None
                debug_print("Conexión a la base de datos cerrada")
            except Exception as e:
                debug_print(f"Error al cerrar la conexión a la base de datos: {e}")


class InputDialog(QDialog):
    def __init__(self, base_name, original_file_name=None, task_name=None, file_path=None):
        super(InputDialog, self).__init__()
        self.setWindowTitle("Input Dialog")
        self.base_name = base_name
        self.original_file_name = original_file_name
        self.file_path = file_path
        self.review_images = []
        self.delete_images_checkbox = None
        # task_name puede venir explícito o se extrae del base_name.
        # normalize_task_name resuelve aliases del filename ("compo" → "comp")
        # para que la búsqueda en DB use siempre el nombre canonical.
        if task_name:
            self.task_name = normalize_task_name(task_name)
        else:
            extracted = extract_task_name(base_name)
            self.task_name = normalize_task_name(extracted) if extracted else "comp"

        self.layout = QVBoxLayout(self)

        # Obtener información del shot y assignee desde la DB
        assignee = self.get_shot_assignee(base_name, file_path=file_path)

        # Label para el mensaje con formato HTML usando los mismos colores que Shot_info
        task_label = f"<span style='color:#AA88FF; font-weight:bold;'>[{self.task_name}]</span>"
        if assignee:
            label_text = (
                f"Message for <b style='color:#CCCC00;'>{base_name}</b> {task_label} | "
                f"<span style='color:#007ACC; font-weight:bold;'>{assignee}</span>:"
            )
        else:
            label_text = f"Message for <b style='color:#CCCC00;'>{base_name}</b> {task_label}:"

        self.label = QLabel(label_text)
        self.label.setTextFormat(Qt.RichText)  # Permitir formato HTML
        self.layout.addWidget(self.label)

        # Area de texto para el mensaje
        self.text_edit = QPlainTextEdit(self)
        self.text_edit.setFixedHeight(120)  # Ajustar la altura de la caja de texto
        self.layout.addWidget(self.text_edit)

        # Buscar imagenes de ReviewPic y mostrar thumbnails si existen
        self.review_images = find_review_images(base_name, original_file_name)
        debug_print(f"=== InputDialog: Búsqueda de imágenes completada ===")
        debug_print(
            f"InputDialog: Total de imágenes encontradas: {len(self.review_images)}"
        )
        if self.review_images:
            debug_print(
                f"InputDialog: Lista de imágenes que se mostrarán en la ventana:"
            )
            for idx, img_path in enumerate(self.review_images, 1):
                debug_print(f"  [{idx}] {os.path.basename(img_path)}")
            self.add_thumbnails_section(self.review_images)
            self.adjust_window_size()  # Esto establece el ancho y la altura actual
            self.setFixedWidth(
                self.width()
            )  # Fijar el ancho para que adjustSize solo afecte la altura
        else:
            debug_print(f"InputDialog: No se encontraron imágenes para mostrar")

        # Boton OK
        self.ok_button = QPushButton("OK", self)
        self.ok_button.clicked.connect(self.accept)
        self.layout.addWidget(self.ok_button)

        # Conectar Ctrl+Enter al metodo accept
        shortcut = QShortcut(QKeySequence(Qt.CTRL | Qt.Key_Return), self)
        shortcut.activated.connect(self.accept)

        # Ajustar el tamaño del diálogo para que se ajuste a su contenido (ahora solo ajusta la altura)
        self.adjustSize()

    def get_shot_assignee(self, base_name, file_path=None):
        """
        Obtiene el assignee de la task activa para el shot especificado.
        Retorna el nombre del assignee o None si no se encuentra.
        """
        try:
            # Extraer project_name desde la ruta (VFX-NOMBRE) o fallback al filename
            project_name = extract_project_name_from_path(file_path)
            if project_name:
                debug_print(f"get_shot_assignee: project_name (from path): {project_name}")
            else:
                project_name = extract_project_name(base_name)
                debug_print(f"get_shot_assignee: project_name (from filename fallback): {project_name}")
            shot_code = extract_shot_code(base_name)

            if not project_name or not shot_code:
                debug_print(
                    f"No se pudo extraer project_name o shot_code de: {base_name}"
                )
                return None

            # Conectar a la base de datos
            db_manager = DBManager()
            if not db_manager.conn:
                debug_print("No hay conexión a la base de datos para obtener assignee")
                return None

            # Buscar el shot
            db_shot = db_manager.find_shot(project_name, shot_code)
            if not db_shot:
                debug_print(
                    f"No se encontró el shot {shot_code} en proyecto {project_name}"
                )
                db_manager.close()
                return None

            # Buscar la task activa (usa self.task_name en lugar de "comp" hardcodeado)
            db_task = db_manager.find_task(db_shot["id"], self.task_name)
            if not db_task:
                debug_print(f"No se encontró la task '{self.task_name}' para shot_id {db_shot['id']}")
                db_manager.close()
                return None

            # Obtener el assignee
            assignee = db_manager.get_task_assignee(db_task["id"])
            db_manager.close()

            if assignee:
                debug_print(f"Assignee encontrado para {base_name}: {assignee}")
            else:
                debug_print(f"No se encontró assignee para {base_name}")

            return assignee

        except Exception as e:
            debug_print(f"Error obteniendo assignee para {base_name}: {e}")
            import traceback

            debug_print(traceback.format_exc())
            return None

    def add_thumbnails_section(self, image_paths):
        """
        Agrega una seccion con thumbnails de las imagenes encontradas.
        """
        try:
            # Label para la seccion de thumbnails
            """ "
            thumbnails_label = QLabel("Review Images:")
            thumbnails_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
            self.layout.addWidget(thumbnails_label)
            """

            # Crear scroll area para los thumbnails
            scroll_area = QScrollArea()
            scroll_area.setMaximumHeight(
                220
            )  # Aumentar altura para incluir numeros de frame
            scroll_area.setWidgetResizable(True)
            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

            # Widget contenedor para los thumbnails
            thumbnails_widget = QWidget()
            thumbnails_layout = QHBoxLayout(thumbnails_widget)
            thumbnails_layout.setSpacing(10)

            # Crear thumbnails con numeros de frame
            for image_path in image_paths:
                if os.path.exists(image_path):
                    # Crear contenedor vertical para imagen + numero de frame
                    thumbnail_container = QWidget()
                    container_layout = QVBoxLayout(thumbnail_container)
                    container_layout.setSpacing(2)
                    container_layout.setContentsMargins(0, 0, 0, 0)
                    # Asegurar que el contenedor tenga un ancho fijo basado en el ancho de la imagen
                    thumbnail_container.setFixedWidth(150)

                    # Crear label para mostrar la imagen
                    image_label = QLabel()

                    # Cargar y redimensionar la imagen
                    pixmap = QPixmap(image_path)
                    if not pixmap.isNull():
                        # Redimensionar manteniendo aspecto, ancho maximo 150px
                        scaled_pixmap = pixmap.scaledToWidth(
                            150, Qt.SmoothTransformation
                        )
                        image_label.setPixmap(scaled_pixmap)
                        image_label.setToolTip(
                            os.path.basename(image_path)
                        )  # Mostrar nombre al hacer hover
                        image_label.setAlignment(Qt.AlignCenter)

                        # Agregar borde al thumbnail
                        image_label.setStyleSheet(
                            "border: 1px solid #ccc; padding: 2px;"
                        )

                        # Conectar el evento de clic del thumbnail
                        image_label.mousePressEvent = lambda event, path=image_path: self.open_image_with_default_viewer(
                            path
                        )

                        container_layout.addWidget(
                            image_label, alignment=Qt.AlignCenter
                        )

                        # Crear layout horizontal para botón de borrar y label de frame
                        frame_container_layout = QHBoxLayout()
                        frame_container_layout.setContentsMargins(4, 0, 0, 0)
                        frame_container_layout.setSpacing(4)

                        # Botón de tachito para borrar imagen
                        delete_button = QPushButton()
                        delete_button.setFixedSize(16, 16)
                        delete_button.setStyleSheet(
                            """
                            QPushButton {
                                background-color: transparent;
                                border: none;
                                color: #ff4444;
                                font-size: 12px;
                                font-weight: bold;
                            }
                            QPushButton:hover {
                                background-color: #ffcccc;
                                border-radius: 2px;
                            }
                            """
                        )
                        delete_button.setText("×")  # Usar símbolo × como tachito
                        delete_button.setToolTip("Borrar esta imagen")

                        # Conectar el botón para borrar la imagen
                        delete_button.clicked.connect(
                            lambda checked=False, path=image_path, container=thumbnail_container: self.delete_single_image(
                                path, container
                            )
                        )

                        frame_container_layout.addWidget(delete_button)

                        # Agregar numero de frame
                        frame_number = self.extract_frame_number_from_filename(
                            image_path
                        )
                        frame_label = QLabel(f"Frame: {frame_number}")
                        frame_label.setStyleSheet("color: #9c9c9c; font-size: 11px;")
                        frame_label.setAlignment(Qt.AlignLeft)
                        frame_container_layout.addWidget(frame_label)
                        frame_container_layout.addStretch()  # Empujar contenido a la izquierda

                        # Widget contenedor para el layout horizontal
                        frame_container_widget = QWidget()
                        frame_container_widget.setLayout(frame_container_layout)
                        # Asegurar que el widget no se expanda más allá del ancho de la imagen
                        frame_container_widget.setMaximumWidth(150)
                        container_layout.addWidget(frame_container_widget)

                        thumbnails_layout.addWidget(thumbnail_container)
                        debug_print(
                            f"Thumbnail agregado: {os.path.basename(image_path)} - Frame: {frame_number}"
                        )

            # Agregar stretch al final para alinear thumbnails a la izquierda
            thumbnails_layout.addStretch()

            # Configurar el scroll area
            scroll_area.setWidget(thumbnails_widget)
            self.layout.addWidget(scroll_area)

            # Agregar checkbox para borrar imagenes
            self.delete_images_checkbox = QCheckBox(
                "Delete all saved review images from disk"
            )
            self.delete_images_checkbox.setChecked(True)  # Tildado por defecto
            self.delete_images_checkbox.setStyleSheet("margin-top: 5px;")
            self.layout.addWidget(self.delete_images_checkbox)

            debug_print(
                f"Seccion de thumbnails agregada con {len(image_paths)} imagenes"
            )

        except Exception as e:
            debug_print(f"Error agregando seccion de thumbnails: {e}")

    def extract_frame_number_from_filename(self, filename):
        """
        Extrae el numero de frame de un nombre de archivo.
        Busca patrones como _0001.jpg, _1234.jpg, etc.
        """
        try:
            # Obtener solo el nombre sin extension
            name_without_ext = os.path.splitext(os.path.basename(filename))[0]

            # Buscar el ultimo grupo de 4 digitos precedido por guion bajo
            import re

            match = re.search(r"_(\d{4})(?:_\d+)?$", name_without_ext)
            if match:
                return match.group(1)

            # Si no encuentra el patron, buscar cualquier numero al final
            match = re.search(r"_(\d+)(?:_\d+)?$", name_without_ext)
            if match:
                return match.group(1).zfill(4)  # Rellenar con ceros a la izquierda

            return "----"

        except Exception as e:
            debug_print(f"Error extrayendo numero de frame: {e}")
            return "----"

    def adjust_window_size(self):
        """
        Ajusta el ancho de la ventana basado en el numero de thumbnails.
        Minimo: ancho actual, Maximo: 1500px
        """
        try:
            if not self.review_images:
                return

            # Calcular ancho necesario basado en thumbnails
            thumbnail_width = 150
            thumbnail_spacing = 10
            margin = 40  # Margen total (izquierda + derecha)

            num_images = len(self.review_images)
            required_width = (
                (num_images * thumbnail_width)
                + ((num_images - 1) * thumbnail_spacing)
                + margin
            )

            # Obtener ancho actual de la ventana
            current_width = self.width() if hasattr(self, "width") else 400

            # Aplicar limites: minimo el ancho actual, maximo 1500
            min_width = max(current_width, 400)
            max_width = 1500

            new_width = max(min_width, min(required_width, max_width))

            debug_print(
                f"Ajustando ancho de ventana: {num_images} imagenes, ancho requerido: {required_width}, nuevo ancho: {new_width}"
            )

            self.resize(new_width, self.height())

        except Exception as e:
            debug_print(f"Error ajustando tamaño de ventana: {e}")

    def delete_single_image(self, image_path, container_widget):
        """
        Borra una imagen individual del disco y la remueve de la UI.

        Args:
            image_path: Ruta completa del archivo de imagen a borrar
            container_widget: Widget contenedor del thumbnail a remover
        """
        try:
            # Confirmar borrado
            reply = QMessageBox.question(
                self,
                "Confirmar borrado",
                f"¿Estás seguro de que quieres borrar esta imagen?\n{os.path.basename(image_path)}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )

            if reply == QMessageBox.Yes:
                # Borrar archivo del disco
                if os.path.exists(image_path):
                    os.remove(image_path)
                    debug_print(f"Imagen borrada del disco: {image_path}")

                # Remover de la lista de review_images
                if image_path in self.review_images:
                    self.review_images.remove(image_path)
                    debug_print(
                        f"Imagen removida de la lista. Quedan {len(self.review_images)} imágenes"
                    )

                # Remover el widget del thumbnail de la UI
                container_widget.setParent(None)
                container_widget.deleteLater()

                # Actualizar tamaño de ventana si es necesario
                self.adjust_window_size()

                debug_print(f"Thumbnail removido de la UI")
            else:
                debug_print("Borrado cancelado por el usuario")

        except Exception as e:
            debug_print(f"Error borrando imagen individual: {e}")
            import traceback

            debug_print(traceback.format_exc())
            QMessageBox.warning(
                self, "Error", f"No se pudo borrar la imagen:\n{str(e)}"
            )

    def get_text(self):
        if self.exec_() == QDialog.Accepted:
            return self.text_edit.toPlainText()
        else:
            return None

    def should_delete_images(self):
        """
        Retorna True si el usuario marco el checkbox para borrar imagenes.
        """
        return self.delete_images_checkbox and self.delete_images_checkbox.isChecked()

    def get_review_images(self):
        """
        Retorna la lista de imagenes de review encontradas.
        """
        return self.review_images

    def open_image_with_default_viewer(self, image_path):
        """
        Abre la imagen especificada con el visor de imagenes predeterminado del sistema operativo.
        """
        debug_print(f"Intentando abrir imagen: {image_path}")
        try:
            if platform.system() == "Windows":
                os.startfile(image_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.call(["open", image_path])
            else:  # Linux y otros
                subprocess.call(["xdg-open", image_path])
            debug_print(f"Imagen abierta exitosamente: {image_path}")
        except Exception as e:
            debug_print(f"Error al abrir la imagen {image_path}: {e}")


def delete_review_pic_cache():
    """
    Borra completamente la carpeta ReviewPic_Cache y todo su contenido.
    """
    try:
        script_dir = os.path.dirname(__file__)
        cache_dir = os.path.join(script_dir, "ReviewPic_Cache")

        if os.path.exists(cache_dir):
            shutil.rmtree(cache_dir)
            debug_print(f"Carpeta ReviewPic_Cache borrada: {cache_dir}")
            return True
        else:
            debug_print(f"Carpeta ReviewPic_Cache no existe: {cache_dir}")
            return False

    except Exception as e:
        debug_print(f"Error borrando carpeta ReviewPic_Cache: {e}")
        return False


class ShotGridManager:
    def __init__(self, url, login, password):
        debug_print("Inicializando conexion a ShotGrid (usando conector externo)")
        # Ya no necesitamos inicializar shotgun_api3 aquí
        # Las operaciones se delegarán al conector externo
        self.url = url
        self.login = login
        self.password = password

    def find_shot_and_tasks(self, project_name, shot_code):
        debug_print(
            f"Buscando proyecto y shot usando conector externo: {project_name} / {shot_code}"
        )
        result = call_flow_connector(
            "find_shot_and_tasks", project_name=project_name, shot_code=shot_code
        )

        if result["success"]:
            project = result.get("project")
            shot = result.get("shot")
            tasks = result.get("tasks")
            debug_print(
                f"Resultado: project={project is not None}, shot={shot is not None}, tasks={len(tasks) if tasks else 0}"
            )
            return project, shot, tasks
        else:
            debug_print(
                f"Error en find_shot_and_tasks: {result.get('error', 'Unknown error')}"
            )
            return None, None, None

    def find_tasks_for_shot(self, shot_id):
        debug_print(f"Buscando tareas para shot_id {shot_id} usando conector externo")
        # Este método se llama desde find_shot_and_tasks, así que las tareas ya están incluidas en el resultado
        # Por simplicidad, devolveremos una lista vacía ya que no necesitamos este método por separado
        debug_print(
            "find_tasks_for_shot: método simplificado, tareas obtenidas en find_shot_and_tasks"
        )
        return []

    def find_highest_version_for_shot(self, shot_id):
        debug_print(
            f"Buscando versión más alta para shot_id {shot_id} usando conector externo"
        )
        result = call_flow_connector("find_highest_version", shot_id=shot_id)

        if result["success"]:
            version = result.get("version")
            version_number = result.get("version_number")
            user_id = result.get("user_id")
            debug_print(f"Versión encontrada: {version_number}, user_id: {user_id}")
            return version, version_number, user_id
        else:
            debug_print(
                f"Error en find_highest_version_for_shot: {result.get('error', 'Unknown error')}"
            )
            return None, None, None

    def update_task_status(self, task_id, new_status):
        debug_print(
            f"Actualizando tarea {task_id} a {new_status} usando conector externo"
        )
        result = call_flow_connector("update_task", task_id=task_id, status=new_status)

        if not result["success"]:
            debug_print(
                f"Error en update_task_status: {result.get('error', 'Unknown error')}"
            )

    def update_version_status(self, project_name, shot_code, version_str, new_status):
        debug_print(
            f"Actualizando versión {version_str} de {shot_code} a {new_status} usando conector externo"
        )
        result = call_flow_connector(
            "update_version",
            project_name=project_name,
            shot_code=shot_code,
            version_str=version_str,
            status=new_status,
        )

        if not result["success"]:
            debug_print(
                f"Error en update_version_status: {result.get('error', 'Unknown error')}"
            )

    def get_task_assignee(self, task_id):
        debug_print(f"Obteniendo asignado de tarea {task_id} usando conector externo")
        result = call_flow_connector("get_task_assignee", task_id=task_id)

        if result["success"]:
            return result.get("assignee_id")
        else:
            debug_print(
                f"Error en get_task_assignee: {result.get('error', 'Unknown error')}"
            )
            return None

    def add_comment_to_version(
        self, version_id, project_id, comment, user_id, task_assignee_id, shot_id=None
    ):
        debug_print(
            f"Agregando comentario a versión {version_id} usando conector externo"
        )
        result = call_flow_connector(
            "add_comment",
            version_id=version_id,
            project_id=project_id,
            comment=comment,
            user_id=user_id,
            task_assignee_id=task_assignee_id,
            shot_id=shot_id,
        )

        if result["success"]:
            return result.get("note")
        else:
            debug_print(
                f"Error en add_comment_to_version: {result.get('error', 'Unknown error')}"
            )
            return None

    def attach_images_to_note(self, note_id, version_id, image_paths):
        debug_print(
            f"Adjuntando {len(image_paths)} imágenes a nota {note_id} usando conector externo"
        )
        result = call_flow_connector(
            "attach_images",
            note_id=note_id,
            version_id=version_id,
            image_paths=image_paths,
        )

        if result["success"]:
            debug_print("Imágenes adjuntadas exitosamente")
            return True
        else:
            debug_print(
                f"Error en attach_images_to_note: {result.get('error', 'Unknown error')}"
            )
            return False

    def extract_frame_number_from_path(self, image_path):
        """
        Método simplificado - la lógica real está en el conector externo
        """
        debug_print("extract_frame_number_from_path: método simplificado")
        return "0001"

    def get_project_id_from_version(self, version_id):
        """
        Método simplificado - obtiene el ID del proyecto usando conector externo
        """
        debug_print(
            f"Obteniendo project_id de versión {version_id} usando conector externo"
        )
        # Este método no se usa frecuentemente, devolver None por simplicidad
        debug_print("get_project_id_from_version: método simplificado, retornando None")
        return None


##### Funciones para comunicación con XYplorer (copiadas de Pull)
##### Estas funciones aplican tags en xyplorer de forma segura sin crashear si xyplorer no está abierto

def get_xy_hwnd(xy_class="ThunderRT6FormDC"):
    """Obtiene el handle de la ventana de XYplorer. Retorna None si no está abierto."""
    try:
        if platform.system() != "Windows":
            return None  # Solo funciona en Windows
        
        user32 = ctypes.windll.user32
        EnumWindows = user32.EnumWindows
        EnumWindowsProc = ctypes.WINFUNCTYPE(
            ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
        )
        GetClassName = user32.GetClassNameW
        EnumChildWindows = user32.EnumChildWindows
        found_hwnd = None

        def enum_windows_callback(hwnd, lParam):
            nonlocal found_hwnd
            class_name = ctypes.create_unicode_buffer(256)
            GetClassName(hwnd, class_name, 256)
            if class_name.value == xy_class:
                child_count = [0]

                def enum_child_windows_callback(hwnd_child, lParam_child):
                    child_count[0] += 1
                    return True

                EnumChildWindows(hwnd, EnumWindowsProc(enum_child_windows_callback), 0)
                if child_count[0] >= 10:
                    found_hwnd = hwnd
                    return False
            return True

        EnumWindows(EnumWindowsProc(enum_windows_callback), 0)
        return found_hwnd
    except Exception as e:
        debug_print(f"Error obteniendo handle de XYplorer: {e}")
        return None


# Determina la arquitectura del sistema y define COPYDATASTRUCT
# Solo se usa en Windows, pero la definimos siempre para evitar errores
if platform.system() == "Windows":
    if platform.architecture()[0] == "32bit":
        ULONG_PTR = ctypes.wintypes.ULONG
    else:
        ULONG_PTR = ctypes.c_uint64
else:
    # Valores por defecto para sistemas no-Windows (no se usarán)
    ULONG_PTR = ctypes.c_uint64

# Define la estructura COPYDATASTRUCT (siempre definida, pero solo usada en Windows)
class COPYDATASTRUCT(ctypes.Structure):
    _fields_ = [
        ("dwData", ULONG_PTR),
        ("cbData", ctypes.wintypes.DWORD),
        ("lpData", ctypes.c_void_p),
    ]


def Send_WM_COPYDATA(xyHwnd, message):
    """Envía un mensaje WM_COPYDATA a XYplorer. Retorna None si falla."""
    try:
        if not xyHwnd or platform.system() != "Windows":
            return None
        
        cds = COPYDATASTRUCT()
        cds.dwData = 4194305
        cds.cbData = len(message.encode("utf-16-le"))
        cds_data = ctypes.create_unicode_buffer(message)
        cds.lpData = ctypes.cast(ctypes.addressof(cds_data), ctypes.c_void_p)
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        result = user32.SendMessageW(xyHwnd, 0x004A, 0, ctypes.byref(cds))  # 0x004A = WM_COPYDATA
        return result
    except Exception as e:
        debug_print(f"Error enviando mensaje a XYplorer: {e}")
        return None


def _tag_shot_folder_thread(shot_base_path, tag):
    """Función que ejecuta el tagging de XYplorer en un thread separado para no bloquear Hiero."""
    try:
        debug_print(f"tag_shot_folder_thread started with shot_base_path='{shot_base_path}', tag='{tag}'")
        if tag is None:
            debug_print("Tag is None, returning without action")
            return
        
        debug_print("Getting XYplorer window handle...")
        hwnd = get_xy_hwnd()
        debug_print(f"XYplorer hwnd: {hwnd}")
        
        if hwnd:
            tag_command = f"::tag '{tag}', '{shot_base_path}';"
            debug_print(f"Sending command to XYplorer: {tag_command}")
            result = Send_WM_COPYDATA(hwnd, tag_command)
            debug_print(f"Send_WM_COPYDATA result: {result}")
            if result:
                debug_print(f"Tag '{tag}' applied to {shot_base_path}")
            else:
                debug_print(f"Failed to apply tag '{tag}' to {shot_base_path}")
        else:
            debug_print("XYplorer window not found - tag no aplicado (esto es normal si xyplorer no está abierto)")
    except Exception as e:
        debug_print(f"Error applying tag in XYplorer: {e}")
        # No re-lanzar la excepción para evitar crashear el script


def tag_shot_folder(shot_base_path, tag):
    """Inicia el tagging de XYplorer en un thread separado para no bloquear Hiero."""
    try:
        debug_print(f"tag_shot_folder called with shot_base_path='{shot_base_path}', tag='{tag}' - starting thread")
        xyplorer_thread = threading.Thread(
            target=_tag_shot_folder_thread,
            args=(shot_base_path, tag),
            daemon=True  # Thread daemon para que termine cuando termine el programa principal
        )
        xyplorer_thread.start()
        debug_print("XYplorer tagging thread started successfully")
    except Exception as e:
        debug_print(f"Error starting XYplorer tagging thread: {e}")
        # No re-lanzar la excepción para evitar crashear el script

##### Fin de funciones para XYplorer


class WorkerSignals(QObject):
    result_ready = Signal(str, int, int)
    task_finished = Signal(bool)  # Ahora incluye el estado de exito
    error = Signal(str)
    debug_output = Signal()  # Nueva señal para imprimir logs
    version_check_result = Signal(
        dict
    )  # Nueva señal para resultado de verificación de versiones
    resumen_output = Signal()  # Nueva señal para imprimir resumen


class FlowVersionListSignals(QObject):
    loaded = Signal(list)
    error = Signal(str)


class LoadFlowVersionsWorker(QRunnable):
    """Worker en background para listar versiones Flow sin bloquear UI."""

    def __init__(self, base_name, original_file_name=None, file_path=None):
        super(LoadFlowVersionsWorker, self).__init__()
        self.base_name = base_name
        self.original_file_name = original_file_name
        self.file_path = file_path
        self.signals = FlowVersionListSignals()

    @Slot()
    def run(self):
        try:
            result = call_flow_connector(
                "list_versions_for_task",
                base_name=self.base_name,
                original_file_name=self.original_file_name,
                file_path=self.file_path,
            )
            if result.get("success"):
                versions = result.get("versions", []) or []
                self.signals.loaded.emit(versions)
            else:
                self.signals.error.emit(result.get("error", "Error desconocido"))
        except Exception as exc:
            self.signals.error.emit(str(exc))


class Worker(QRunnable):
    def __init__(
        self,
        button_name,
        base_name,
        message,
        review_images=None,
        should_delete_images=False,
        original_file_name=None,
        file_path=None,
        target_version_number=None,
    ):
        super(Worker, self).__init__()
        self.button_name = button_name
        self.base_name = base_name
        self.message = message
        self.review_images = review_images or []
        self.should_delete_images = should_delete_images
        self.original_file_name = original_file_name
        self.file_path = file_path
        self.target_version_number = target_version_number
        self.last_error_message = None
        self.signals = WorkerSignals()

    def _push_context_lines(self):
        project_name = extract_project_name_from_path(self.file_path)
        if not project_name:
            project_name = extract_project_name(self.base_name)

        shot_code = extract_shot_code(self.base_name) or "No detectado"
        task_name = extract_task_name(self.base_name)
        task_name = normalize_task_name(task_name) if task_name else "No detectada"

        version_label = None
        if self.target_version_number is not None:
            try:
                version_label = f"v{int(self.target_version_number):03d}"
            except Exception:
                version_label = str(self.target_version_number)
        if not version_label and self.original_file_name:
            match = re.search(r"_v(\d+)", self.original_file_name, re.IGNORECASE)
            if match:
                version_label = f"v{int(match.group(1)):03d}"
        if not version_label:
            match = re.search(r"_v(\d+)", self.base_name, re.IGNORECASE)
            if match:
                version_label = f"v{int(match.group(1)):03d}"
        if not version_label:
            version_label = "No detectada"

        return [
            f"Proyecto buscado: {project_name or 'No detectado'}",
            f"Shot buscado: {shot_code}",
            f"Task buscada: {task_name}",
            f"Version buscada: {version_label}",
            f"Estado solicitado: {self.button_name}",
            f"Archivo: {self.original_file_name or os.path.basename(self.file_path or '') or 'No disponible'}",
        ]

    def _format_error_with_context(self, error_message):
        context = "\n".join(self._push_context_lines())
        return f"{error_message}\n\nContexto de busqueda:\n{context}"

    @Slot()
    def run(self):
        db_manager = DBManager()  # Crear la conexión en el hilo correcto
        success = False

        try:
            debug_print(
                f"Worker: Iniciando operación {self.button_name} para {self.base_name}"
            )

            # La verificación de versiones ya se hizo en el timeline antes de crear el Worker
            # No es necesario hacer otra verificación con Flow aquí (era redundante)
            debug_print(
                "Worker: Verificación de versiones ya realizada en timeline, procediendo con push"
            )

            # Usar la operación optimizada que hace todo en una sola llamada
            debug_print(f"=== Worker: Preparando envío de imágenes ===")
            debug_print(
                f"Worker: Total de imágenes a enviar: {len(self.review_images)}"
            )
            if self.review_images:
                debug_print(f"Worker: Lista de imágenes que se enviarán a Flow:")
                for idx, img_path in enumerate(self.review_images, 1):
                    debug_print(f"  [{idx}] {img_path}")
                    if not os.path.exists(img_path):
                        debug_print(
                            f"  ⚠️  ADVERTENCIA: La imagen [{idx}] NO EXISTE en disco: {img_path}"
                        )
            else:
                debug_print(f"Worker: No hay imágenes para enviar")

            result = call_flow_connector(
                "execute_full_push",
                button_name=self.button_name,
                base_name=self.base_name,
                message=self.message,
                review_images=self.review_images,
                original_file_name=getattr(self, "original_file_name", None),
                file_path=getattr(self, "file_path", None),
                target_version_number=getattr(self, "target_version_number", None),
            )

            # Capturar información para el resumen
            images_total = len(self.review_images)
            images_attached = 0
            error_message = None

            if result["success"]:
                debug_print("Worker: Operación de red completada exitosamente")
                # Verificar si hay información sobre imágenes adjuntadas en el resultado
                if "images_attached" in result:
                    images_attached = result["images_attached"]
                    debug_print(
                        f"Worker: Imágenes adjuntadas según Flow: {images_attached} de {images_total} enviadas"
                    )
                success = True

                # Si fue exitoso, actualizar también la base de datos local
                self.update_local_database(db_manager)
                
                # Aplicar tag en xyplorer después de actualizar exitosamente
                self.apply_xyplorer_tag()
            else:
                error_message = result.get("error", "Unknown error")
                self.last_error_message = self._format_error_with_context(error_message)
                debug_print(f"Worker: Error en operación de red: {error_message}")
                debug_print(self.last_error_message)
                success = False

            # Generar resumen
            self.generate_resumen(success, images_total, images_attached, error_message)

        except Exception as e:
            debug_print(f"Worker: Exception in Worker.run: {e}")
            success = False
            self.last_error_message = self._format_error_with_context(
                f"Excepcion: {str(e)}"
            )
            # Generar resumen incluso en caso de excepción
            images_total = len(self.review_images)
            self.generate_resumen(success, images_total, 0, f"Excepción: {str(e)}")
        finally:
            # Cerrar la conexión a la base de datos
            if db_manager:
                db_manager.close()

            # Borrar imagenes SOLO si se completó exitosamente y el usuario lo solicitó
            if success and self.should_delete_images:
                debug_print(
                    "Worker: Operacion exitosa: Borrando carpeta ReviewPic_Cache como solicitó el usuario"
                )
                delete_review_pic_cache()
            elif not success and self.should_delete_images:
                debug_print(
                    "Worker: Operacion fallida: NO se borra la carpeta ReviewPic_Cache"
                )

            if not success and self.last_error_message:
                self.signals.error.emit(self.last_error_message)
            self.signals.task_finished.emit(success)
            self.signals.debug_output.emit()  # Emitir señal al finalizar
            self.signals.resumen_output.emit()  # Emitir señal para imprimir resumen

    def continue_after_version_check(self):
        """Método para continuar la operación después de que el usuario confirme la versión"""
        debug_print("Worker: Continuando después de verificación de versiones")

        # Crear una nueva instancia del Worker con skip_version_check=True
        new_worker = Worker(
            self.button_name,
            self.base_name,
            self.message,
            self.review_images,
            self.should_delete_images,
            self.original_file_name,
            self.file_path,
            target_version_number=self.target_version_number,
        )

        # Conectar las mismas señales
        new_worker.signals.result_ready.connect(self.signals.result_ready)
        new_worker.signals.task_finished.connect(self.signals.task_finished)
        new_worker.signals.debug_output.connect(self.signals.debug_output)
        new_worker.signals.resumen_output.connect(self.signals.resumen_output)
        new_worker.signals.version_check_result.connect(
            self.signals.version_check_result
        )

        # Marcar que debe saltar la verificación de versiones
        new_worker.skip_version_check = True

        # Ejecutar el nuevo Worker
        QThreadPool.globalInstance().start(new_worker)

    def update_local_database(self, db_manager):
        """Actualiza la base de datos local con los cambios"""
        try:
            # Extraer project_name desde la ruta (VFX-NOMBRE) o fallback al filename
            project_name = extract_project_name_from_path(self.file_path)
            if project_name:
                debug_print(f"Worker: project_name (from path): {project_name}")
            else:
                project_name = extract_project_name(self.base_name)
                debug_print(f"Worker: project_name (from filename fallback): {project_name}")
            shot_code = extract_shot_code(self.base_name)

            # Extraer task_name usando función compartida.
            # normalize_task_name resuelve aliases ("compo" → "comp") para la búsqueda en DB.
            task_name_extracted = extract_task_name(self.base_name)
            if task_name_extracted:
                task_name = normalize_task_name(task_name_extracted)
            else:
                # Fallback: buscar task antes de la versión
                parts = self.base_name.split("_")
                version_number_str = None
                for part in parts:
                    if part.startswith("v") and part[1:].isdigit():
                        version_number_str = part
                        break

                if version_number_str:
                    try:
                        version_index = parts.index(version_number_str)
                        if version_index > 0:
                            task_name = parts[version_index - 1].lower()
                        else:
                            task_name = "comp"  # Fallback por defecto
                    except ValueError:
                        task_name = "comp"  # Fallback por defecto
                else:
                    task_name = "comp"  # Fallback por defecto

            sg_status = status_translation.get(self.button_name, None)

            if not sg_status:
                return

            # Buscar shot en base de datos local
            db_shot = db_manager.find_shot(project_name, shot_code)
            if not db_shot:
                debug_print(
                    f"Worker: No se encontró el shot {shot_code} en la base de datos local"
                )
                return

            # Buscar tarea en base de datos local
            db_task = db_manager.find_task(db_shot["id"], task_name)
            if not db_task:
                debug_print(
                    f"Worker: No se encontró la tarea {task_name} en la base de datos local"
                )
                return

            # Actualizar estado de tarea local
            debug_print(
                f"Worker: Actualizando estado de tarea local (ID: {db_task['id']}) a: {sg_status}"
            )
            db_manager.update_task_status(db_task["id"], sg_status)

            # Obtener versión target (Shift+Click) o fallback a la más reciente.
            target_version = None
            if self.target_version_number is not None:
                target_version = db_manager.find_version_by_number(
                    db_task["id"], int(self.target_version_number)
                )
                if target_version:
                    debug_print(
                        f"Worker: Usando versión target local v{target_version['version_number']} (ID: {target_version['id']})"
                    )
                else:
                    debug_print(
                        f"Worker: No se encontró versión target v{self.target_version_number} en DB local, fallback a latest"
                    )

            if not target_version:
                target_version = db_manager.find_latest_version(db_task["id"])

            if target_version:
                # Decidir qué estado aplicar a la versión dependiendo del estado de la tarea
                version_status = None
                if sg_status in ["rev_di", "corr", "revcha"]:
                    version_status = "vwd"
                elif sg_status == "rev_su":
                    version_status = "rev"
                elif sg_status == "revleg":
                    version_status = "unvleg"

                if version_status:
                    debug_print(
                        f"Worker: Actualizando estado de versión local (ID: {target_version['id']}, "
                        f"version: {target_version['version_number']}) a: {version_status}"
                    )
                    db_manager.update_version_status(
                        db_task["id"],
                        target_version["version_number"],
                        version_status,
                    )

                # Añadir nota si hay mensaje
                if self.message:
                    debug_print(
                        f"Worker: Añadiendo nota a versión local (ID: {target_version['id']})"
                    )
                    db_manager.add_version_note(target_version["id"], self.message)

        except Exception as e:
            debug_print(f"Worker: Error actualizando base de datos local: {e}")

    def apply_xyplorer_tag(self):
        """Aplica el tag correspondiente en xyplorer basándose en el estado.
        Si xyplorer no está abierto, simplemente no aplica el tag sin dar error."""
        try:
            # Obtener el tag de xyplorer del diccionario de estados
            sg_status = status_translation.get(self.button_name, None)
            if not sg_status:
                debug_print("Worker: No se encontró estado válido para aplicar tag")
                return
            
            # Buscar el tag en el diccionario
# El orden de los valores es:
            # (nombre en Flow/ShotGrid, color_hex[, tag XYplorer])
            task_status_name, new_color_hex, xyplorer_tag = task_status_dict.get(
                sg_status,
                ("Estado desconocido", "#000000", None),
            )
            
            if not xyplorer_tag:
                debug_print(f"Worker: No hay tag de xyplorer para el estado '{sg_status}'")
                return
            
            # Obtener el file_path del clip para calcular shot_base_path
            if not hasattr(self, 'original_file_name') or not self.original_file_name:
                debug_print("Worker: No se tiene original_file_name para calcular shot_base_path")
                return
            
            # Buscar el clip en el timeline para obtener su file_path completo
            seq = hiero.ui.activeSequence()
            if not seq:
                debug_print("Worker: No hay secuencia activa")
                return
            
            # Buscar el clip que coincida con original_file_name
            file_path = None
            for track in seq.videoTracks():
                for clip in track.items():
                    if isinstance(clip, hiero.core.EffectTrackItem):
                        continue
                    try:
                        if not clip.source().mediaSource().isMediaPresent():
                            continue
                        clip_file_path = clip.source().mediaSource().fileinfos()[0].filename()
                        if self.original_file_name in clip_file_path or os.path.basename(clip_file_path) == self.original_file_name:
                            file_path = clip_file_path
                            break
                    except Exception:
                        continue
                if file_path:
                    break
            
            if not file_path:
                debug_print(f"Worker: No se pudo encontrar el file_path para {self.original_file_name}")
                return
            
            # Calcular shot_base_path (igual que en Pull)
            normalized_path = os.path.normpath(file_path)
            path_parts = normalized_path.split(os.sep)
            
            if os.path.isabs(file_path) and len(path_parts) >= 5:
                shot_base_path = os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.dirname(file_path)))
                )
                debug_print(f"Worker: shot_base_path calculado: {shot_base_path}")
            else:
                debug_print("Worker: No se puede calcular shot_base_path (ruta inválida)")
                return
            
            # Aplicar el tag en xyplorer (solo si está habilitado y tenemos los datos necesarios)
            if XYPlorer_Tags and shot_base_path and xyplorer_tag:
                debug_print(f"Worker: Aplicando tag '{xyplorer_tag}' a '{shot_base_path}'")
                tag_shot_folder(shot_base_path, xyplorer_tag)
            else:
                debug_print(f"Worker: No se aplicará tag - XYPlorer_Tags: {XYPlorer_Tags}, shot_base_path: {shot_base_path}, xyplorer_tag: {xyplorer_tag}")
        
        except Exception as e:
            debug_print(f"Worker: Error aplicando tag en xyplorer: {e}")
            import traceback
            debug_print(traceback.format_exc())
            # No re-lanzar la excepción para evitar crashear el script

    def generate_resumen(self, success, images_total, images_attached, error_message):
        """Genera un resumen del proceso de push"""
        debug_resumen_print("=" * 70)
        debug_resumen_print("RESUMEN DEL PUSH")
        debug_resumen_print("=" * 70)
        debug_resumen_print(f"Shot: {self.base_name}")
        debug_resumen_print(f"Estado: {self.button_name}")

        if success:
            debug_resumen_print("✅ RESULTADO: ÉXITO")
        else:
            debug_resumen_print("❌ RESULTADO: ERROR")
            if error_message:
                debug_resumen_print(f"   Error: {error_message}")

        debug_resumen_print("")
        debug_resumen_print("IMÁGENES:")
        debug_resumen_print(f"   Total encontradas: {images_total}")
        if images_total > 0:
            debug_resumen_print(f"   Subidas exitosamente: {images_attached}")
            if images_attached < images_total:
                debug_resumen_print(f"   ⚠️  FALLIDAS: {images_total - images_attached}")
            elif images_attached == images_total:
                debug_resumen_print(
                    f"   ✅ Todas las imágenes se subieron correctamente"
                )
        else:
            debug_resumen_print("   No había imágenes para enviar")

        debug_resumen_print("=" * 70)


class MessageBoxManager:
    def __init__(self):
        self.message_boxes = []

    def show_warning_message(self, info):
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        msg_box = QMessageBox()
        msg_box.setTextFormat(Qt.RichText)  # Permite el formato HTML
        msg_box.setText(info)
        msg_box.setWindowTitle("ShotGrid Version Warning")
        msg_box.setWindowModality(Qt.NonModal)
        msg_box.show()
        self.message_boxes.append(msg_box)


class MultipleShotsDialog(QDialog):
    """Diálogo para informar sobre múltiples shots encontrados"""

    def __init__(self, shots, shot_code, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Múltiples Shots Encontrados")
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Mensaje principal
        msg = QLabel(f"Se encontraron {len(shots)} shots con el nombre '{shot_code}':")
        msg.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        layout.addWidget(msg)

        # Lista de shots con sus IDs
        for shot in shots:
            shot_info = QLabel(f"• Shot ID: {shot['id']} - {shot['code']}")
            shot_info.setStyleSheet("margin-left: 20px; margin-bottom: 5px;")
            layout.addWidget(shot_info)

        # Mensaje de error
        error_msg = QLabel(
            "No se puede proceder con la operación cuando existen múltiples shots con el mismo nombre."
        )
        error_msg.setStyleSheet(
            "color: #B95C5C; margin-top: 10px; margin-bottom: 10px;"
        )
        layout.addWidget(error_msg)

        # Botón OK
        ok_btn = QPushButton("OK")
        ok_btn.clicked.connect(self.accept)
        layout.addWidget(ok_btn)

        self.adjustSize()


def extract_version_number_from_string(version_str):
    """Extrae el número de versión de una cadena como 'LC_4007_010_DeAging_Pamela_comp_v05'."""
    # Buscar el patrón _v\d+ al final del nombre (igual que en LGA_NKS_Flow_Pull.py)
    match = re.search(r"_v(\d+)(?:[-\(][^)]+)?", version_str)
    if match:
        try:
            version_num = int(match.group(1))
            debug_print(f"Versión extraída de '{version_str}': v{version_num:02d}")
            return version_num
        except ValueError:
            debug_print(f"Error convirtiendo versión a número: {match.group(1)}")
            return 0
    debug_print(f"No se encontró versión en: {version_str}")
    return 0


def get_clip_versions_from_timeline():
    """
    Obtiene las versiones disponibles del clip seleccionado en el timeline usando la API de Hiero.
    Retorna: (current_version_number, highest_version_number, all_versions_list)
    """
    try:
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("No hay secuencia activa")
            return None, None, []

        te = hiero.ui.getTimelineEditor(seq)
        selected_clips = te.selection()

        if not selected_clips:
            debug_print("No hay clips seleccionados")
            return None, None, []

        # Tomar el primer clip seleccionado
        clip = selected_clips[0]
        if isinstance(clip, hiero.core.EffectTrackItem):
            debug_print("El clip seleccionado es un efecto, ignorando")
            return None, None, []

        # Obtener el binItem del clip
        bin_item = clip.source().binItem()
        if not bin_item:
            debug_print("No se pudo obtener binItem del clip")
            return None, None, []

        # Obtener todas las versiones disponibles
        existing_versions = list(bin_item.items())
        debug_print(f"=== Versiones encontradas para el clip ===")
        debug_print(f"Total de versiones: {len(existing_versions)}")

        version_numbers = []
        for idx, version in enumerate(existing_versions):
            version_name = version.name()
            version_num = extract_version_number_from_string(version_name)
            version_numbers.append(version_num)
            debug_print(f"  [{idx}] {version_name} -> v{version_num:02d}")

        if not version_numbers:
            debug_print("No se encontraron versiones con números válidos")
            return None, None, []

        # Obtener versión actual (activa)
        current_version_item = bin_item.activeVersion()
        current_version_name = (
            current_version_item.name() if current_version_item else None
        )
        current_version_number = (
            extract_version_number_from_string(current_version_name)
            if current_version_name
            else None
        )

        # Encontrar versión más alta
        highest_version_number = max(version_numbers)

        debug_print(
            f"Versión actual: v{current_version_number:02d}"
            if current_version_number is not None
            else "Versión actual: No detectada"
        )
        debug_print(f"Versión más alta: v{highest_version_number:02d}")

        return (
            current_version_number,
            highest_version_number,
            sorted(version_numbers, reverse=True),
        )

    except Exception as e:
        debug_print(f"Error obteniendo versiones del timeline: {e}")
        import traceback

        debug_print(traceback.format_exc())
        return None, None, []


class PushVersionDialog(QDialog):
    """Diálogo personalizado para verificación de versión antes del push"""

    def __init__(
        self, base_name, current_version, highest_version, all_versions, parent=None
    ):
        super().__init__(parent)
        self.result_value = (
            None  # None = cancelado, True = continuar con versión actual
        )

        self.setWindowTitle("Verificación de Versión")
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Mensaje HTML
        message_label = QLabel()
        message_label.setTextFormat(Qt.RichText)

        # Formatear el nombre base con la versión resaltada
        base_version_highlighted = re.sub(
            r"(_)(v\d+)", r'\1<span style="color: #ff9900;">\2</span>', base_name
        )

        # Lista de versiones disponibles
        versions_list = ", ".join([f"v{v:02d}" for v in all_versions])

        message_label.setText(
            f"<div style='text-align: center;'>"
            f"<span style='color: #ff9900;'><b>¡Atención!</b></span><br><br>"
            f"La versión que intentas actualizar no es la más reciente:<br><br>"
            f"<span style='font-weight: bold;'>{base_version_highlighted}</span><br><br>"
            f"Versión actual en timeline: <span style='color: #ff9900;'>v{current_version:02d}</span><br>"
            f"Última versión disponible: <span style='color: #00ff00;'>v{highest_version:02d}</span><br>"
            f"Versiones disponibles: <span style='color: #9c9c9c; font-size: 0.9em;'>{versions_list}</span><br><br>"
            f"¿Deseas continuar con el push de la versión actual de todos modos?</div>"
        )
        layout.addWidget(message_label)

        # Botones
        button_layout = QHBoxLayout()

        self.yes_button = QPushButton("Continuar con versión actual")
        self.no_button = QPushButton("Cancelar")

        self.yes_button.clicked.connect(self.accept_continue)
        self.no_button.clicked.connect(self.reject)

        button_layout.addWidget(self.yes_button)
        button_layout.addWidget(self.no_button)
        layout.addLayout(button_layout)

        # Hacer que "Cancelar" sea el botón por defecto
        self.no_button.setDefault(True)

    def accept_continue(self):
        debug_print("Usuario eligió continuar con versión actual")
        self.result_value = True
        self.accept()

    def closeEvent(self, event):
        debug_print("Usuario cerró el diálogo con X o ESC, cancelando operación")
        self.result_value = None
        event.accept()

    def get_result(self):
        return self.result_value


def show_version_dialog(base_name, local_version, flow_version):
    """Muestra un diálogo preguntando si se desea continuar cuando la versión local es más antigua."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    msgBox = QMessageBox()
    msgBox.setWindowTitle("Verificación de Versión")
    msgBox.setTextFormat(Qt.RichText)

    # Formatear el nombre base con la versión resaltada
    base_version_highlighted = re.sub(
        r"(_)(v\d+)", r'\1<span style="color: #ff9900;">\2</span>', base_name
    )

    msgBox.setText(
        f"<div style='text-align: center;'>"
        f"<span style='color: #ff9900;'><b>¡Atención!</b></span><br><br>"
        f"La versión que intentas actualizar no es la más reciente:<br><br>"
        f"<span style='font-weight: bold;'>{base_version_highlighted}</span><br><br>"
        f"Versión local: <span style='color: #ff9900;'>v{local_version}</span><br>"
        f"Última versión en Flow: <span style='color: #00ff00;'>v{flow_version}</span><br><br>"
        f"¿Deseas continuar de todos modos?</div>"
    )

    msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msgBox.setDefaultButton(QMessageBox.No)
    msgBox.button(QMessageBox.Yes).setText("Continuar de todos modos")
    msgBox.button(QMessageBox.No).setText("Cancelar")

    response = msgBox.exec_()
    return response == QMessageBox.Yes


def show_flow_version_selection_dialog(base_name, versions):
    """Selector modal de versión destino para Shift+Click."""
    if not versions:
        return None

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    dialog = QDialog()
    dialog.setWindowTitle("Seleccionar versión de Flow")
    layout = QVBoxLayout(dialog)

    title = QLabel(
        f"Elegí la versión destino para <b>{base_name}</b><br/>"
        f"<span style='color:#9a9a9a'>Shift+Click: la nota se enviará a esta versión.</span>"
    )
    title.setTextFormat(Qt.RichText)
    layout.addWidget(title)

    list_widget = QtWidgets.QListWidget(dialog)
    list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
    for version in versions:
        version_number = version.get("version_number")
        if version_number is None:
            continue
        try:
            version_number = int(version_number)
        except Exception:
            continue

        version_label = version.get("version_label") or f"v{version_number:03d}"
        user_name = version.get("user_name") or "Desconocido"
        created_at = str(version.get("created_at") or "")
        created_short = created_at.replace("T", " ")[:16] if created_at else ""
        code = version.get("code") or ""

        line = f"{version_label}  |  {user_name}"
        if created_short:
            line += f"  |  {created_short}"
        if code:
            line += f"  |  {code}"

        item = QtWidgets.QListWidgetItem(line)
        item.setData(Qt.UserRole, version_number)
        list_widget.addItem(item)

    if list_widget.count() > 0:
        list_widget.setCurrentRow(0)
    layout.addWidget(list_widget)

    buttons_layout = QHBoxLayout()
    cancel_button = QPushButton("Cancelar", dialog)
    ok_button = QPushButton("OK", dialog)
    cancel_button.clicked.connect(dialog.reject)
    ok_button.clicked.connect(dialog.accept)
    buttons_layout.addWidget(cancel_button)
    buttons_layout.addWidget(ok_button)
    layout.addLayout(buttons_layout)

    dialog.resize(760, 380)
    if dialog.exec_() != QDialog.Accepted:
        return None

    current_item = list_widget.currentItem()
    if not current_item:
        return None
    return current_item.data(Qt.UserRole)


def handle_results(info, sg_version_number, version_number):
    if sg_version_number > version_number:
        msg_manager.show_warning_message(info)


def show_push_error_message(error_text):
    debug_print(f"Mostrando error de Push al usuario: {error_text}")
    QMessageBox.critical(
        None,
        "Flow Push - Error",
        f"No se pudo completar el Push:\n\n{error_text}",
    )


def handle_version_check_result(version_check_result, worker, update_callback):
    """Maneja el resultado de la verificación de versiones desde el Worker"""
    debug_print("Manejando resultado de verificación de versiones")

    if version_check_result["needs_confirmation"]:
        # Mostrar diálogo de confirmación en el hilo principal
        local_version = version_check_result["local_version"]
        flow_version = version_check_result["flow_version"]
        base_name = version_check_result["base_name"]

        debug_print(
            f"Mostrando diálogo de confirmación: v{local_version} vs v{flow_version}"
        )

        # Mostrar el diálogo y esperar respuesta del usuario
        if show_version_dialog(base_name, local_version, flow_version):
            # Usuario confirmó, continuar con la operación
            debug_print("Usuario confirmó, continuando con la operación")
            # Aquí podríamos crear un nuevo Worker o continuar el actual
            # Por simplicidad, vamos a crear un nuevo Worker sin verificación
            worker.continue_after_version_check()
        else:
            debug_print("Usuario canceló la operación")
            # Emitir señal de finalización con fallo
            worker.signals.task_finished.emit(False)
            worker.signals.debug_output.emit()


def Push_Task_Status(
    button_name,
    base_name,
    update_callback=None,
    original_file_name=None,
    file_path=None,
    target_version_number=None,
):
    global msg_manager
    debug_print(
        f"Push solicitado: estado='{button_name}', shot='{base_name}'"
    )

    is_valid, error_text, _state = validate_push_preflight()
    if not is_valid:
        debug_print(f"Preflight Push falló:\n{error_text}")
        QMessageBox.warning(None, "PipeSync no configurado", error_text)
        return False

    # Verificar que tengamos las credenciales disponibles
    sg_url, sg_login, sg_password = get_flow_credentials()

    if not sg_url or not sg_login or not sg_password:
        debug_print(
            "No se pudieron obtener las credenciales de Flow desde la configuración encriptada."
        )
        return False  # Retornar False si faltan credenciales

    # PRIMERO: Verificar versiones del timeline ANTES de abrir el diálogo de notas
    sg_status = status_translation.get(button_name, None)
    if (
        sg_status in ["rev_di", "corr", "revleg", "revhld", "revcha", "revjua", "revjav"]
        and target_version_number is None
    ):
        debug_print("=== Verificando versiones del timeline antes del push ===")

        # Obtener versiones del clip seleccionado
        current_version, highest_version, all_versions = (
            get_clip_versions_from_timeline()
        )

        if current_version is not None and highest_version is not None:
            debug_print(
                f"Versión actual detectada: v{current_version:02d}, Versión más alta: v{highest_version:02d}"
            )

            # Si la versión actual no es la más alta, mostrar diálogo de advertencia
            if current_version < highest_version:
                debug_print(
                    f"⚠️  ADVERTENCIA: La versión actual (v{current_version:02d}) no es la más alta (v{highest_version:02d})"
                )

                # Construir base_name con versión para el diálogo
                version_base_name = base_name
                if not any(
                    part.startswith("v") and part[1:].isdigit()
                    for part in base_name.split("_")
                ):
                    version_base_name = f"{base_name}_v{current_version:02d}"

                # Mostrar diálogo personalizado
                app = QApplication.instance()
                if app is None:
                    app = QApplication([])

                dialog = PushVersionDialog(
                    version_base_name, current_version, highest_version, all_versions
                )
                dialog.exec_()
                result = dialog.get_result()

                if result is None:
                    # Usuario cerró el diálogo sin confirmar
                    debug_print(
                        "Usuario canceló la operación cerrando el diálogo de versión"
                    )
                    debug_resumen_print("=" * 70)
                    debug_resumen_print("RESUMEN DEL PUSH")
                    debug_resumen_print("=" * 70)
                    debug_resumen_print(f"Shot: {base_name}")
                    debug_resumen_print(f"Estado: {button_name}")
                    debug_resumen_print("⚠️  RESULTADO: OPERACIÓN CANCELADA")
                    debug_resumen_print("")
                    debug_resumen_print(
                        "El usuario canceló porque la versión actual no es la más reciente."
                    )
                    debug_resumen_print(
                        f"Versión actual en timeline: v{current_version:02d}"
                    )
                    debug_resumen_print(
                        f"Última versión disponible: v{highest_version:02d}"
                    )
                    debug_resumen_print("")
                    debug_resumen_print("Ningún cambio se aplicó en Flow.")
                    debug_resumen_print("=" * 70)
                    print_debug_messages()
                    print_resumen()
                    return False
                elif not result:
                    # Usuario canceló explícitamente
                    debug_print("Usuario canceló la operación")
                    debug_resumen_print("=" * 70)
                    debug_resumen_print("RESUMEN DEL PUSH")
                    debug_resumen_print("=" * 70)
                    debug_resumen_print(f"Shot: {base_name}")
                    debug_resumen_print(f"Estado: {button_name}")
                    debug_resumen_print("⚠️  RESULTADO: OPERACIÓN CANCELADA")
                    debug_resumen_print("")
                    debug_resumen_print(
                        "El usuario canceló porque la versión actual no es la más reciente."
                    )
                    debug_resumen_print("=" * 70)
                    print_debug_messages()
                    print_resumen()
                    return False
                else:
                    debug_print("Usuario confirmó continuar con la versión actual")
            else:
                debug_print(
                    f"✓ Versión actual (v{current_version:02d}) es la más alta, continuando sin advertencia"
                )
        else:
            debug_print(
                "No se pudieron obtener versiones del timeline, continuando sin verificación"
            )

    # SEGUNDO: Solicitar el mensaje al usuario para ciertos estados
    message = None
    review_images = []
    should_delete_images = False
    if sg_status in ["rev_di", "corr", "revleg", "revhld", "revcha", "revjua", "revjav"]:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        input_dialog = InputDialog(base_name, original_file_name, file_path=file_path)
        message = input_dialog.get_text()
        if message is None:
            # Operación cancelada por el usuario al cerrar el diálogo de comentarios
            debug_print("Usuario canceló la operación cerrando el diálogo")
            # Generar resumen de cancelación
            debug_resumen_print("=" * 70)
            debug_resumen_print("RESUMEN DEL PUSH")
            debug_resumen_print("=" * 70)
            debug_resumen_print(f"Shot: {base_name}")
            debug_resumen_print(f"Estado: {button_name}")
            debug_resumen_print("⚠️  RESULTADO: OPERACIÓN CANCELADA")
            debug_resumen_print("")
            debug_resumen_print("El usuario cerró el diálogo sin confirmar.")
            debug_resumen_print("Ningún cambio se aplicó en Flow.")
            debug_resumen_print(
                "Todo permanece como estaba antes de ejecutar el script."
            )
            debug_resumen_print("")
            images_found = (
                len(input_dialog.get_review_images())
                if hasattr(input_dialog, "get_review_images")
                else 0
            )
            debug_resumen_print("IMÁGENES:")
            debug_resumen_print(f"   Total encontradas: {images_found}")
            debug_resumen_print("   No se enviaron (operación cancelada)")
            debug_resumen_print("=" * 70)
            print_debug_messages()  # Imprimir logs si el usuario cancela
            print_resumen()  # Imprimir resumen de cancelación
            return False

        # Obtener información adicional del diálogo
        review_images = input_dialog.get_review_images()
        should_delete_images = bool(input_dialog.should_delete_images())
        print_debug_messages()  # Imprimir logs después de obtener la información del diálogo

    # No hacer verificación de versiones aquí - se hace en el Worker
    # Esto evita congelar la UI mientras se consulta Flow

    # Una vez que el usuario ha confirmado (o no hay problema de versiones), proceder con las actualizaciones
    if sg_status in ["rev_di", "corr", "revleg", "revhld", "revcha", "revjua", "revjav"]:
        worker = Worker(
            button_name,
            base_name,
            message,
            review_images,
            should_delete_images,
            original_file_name,
            file_path=file_path,
            target_version_number=target_version_number,
        )
        # Conectar señales
        worker.signals.result_ready.connect(handle_results)
        worker.signals.error.connect(show_push_error_message)
        worker.signals.debug_output.connect(lambda: print_debug_messages())
        worker.signals.resumen_output.connect(lambda: print_resumen())
        worker.signals.version_check_result.connect(
            lambda result: handle_version_check_result(result, worker, update_callback)
        )
        if update_callback:
            worker.signals.task_finished.connect(update_callback)
        QThreadPool.globalInstance().start(worker)
    else:
        worker = Worker(
            button_name,
            base_name,
            None,
            [],
            False,
            original_file_name,
            file_path=file_path,
            target_version_number=target_version_number,
        )
        worker.signals.result_ready.connect(handle_results)
        worker.signals.error.connect(show_push_error_message)
        worker.signals.debug_output.connect(lambda: print_debug_messages())
        worker.signals.resumen_output.connect(lambda: print_resumen())
        worker.signals.version_check_result.connect(
            lambda result: handle_version_check_result(result, worker, update_callback)
        )
        if update_callback:
            worker.signals.task_finished.connect(update_callback)
        QThreadPool.globalInstance().start(worker)

    return True  # Retornar True indicando que la operación fue iniciada


def print_debug_messages():
    if DEBUG and DEBUG_CONSOLE and debug_messages:
        print("\n".join(debug_messages))
    debug_messages.clear()  # Limpiar mensajes después de imprimir


def print_resumen():
    """Imprime el resumen del push"""
    if DEBUG_RESUMEN and resumen_messages:
        print("\n".join(resumen_messages))
        resumen_messages.clear()  # Limpiar mensajes después de imprimir


def _show_task_selection_dialog(button_name, task_names):
    """
    Muestra dialog de selección de task cuando hay clips de múltiples tasks presentes.
    Retorna set de tasks seleccionadas, o None si el usuario canceló.
    """
    QRadioButton = QtWidgets.QRadioButton

    dialog = QDialog()
    dialog.setWindowTitle("Seleccionar Task")
    layout = QVBoxLayout(dialog)

    label = QLabel(f"¿A qué task aplicar <b>{button_name}</b>?")
    label.setTextFormat(Qt.RichText)
    layout.addWidget(label)

    radio_buttons = {}
    for i, task in enumerate(sorted(task_names)):
        rb = QRadioButton(task)
        if i == 0:
            rb.setChecked(True)
        layout.addWidget(rb)
        radio_buttons[task] = rb

    rb_all = QRadioButton("Todas")
    layout.addWidget(rb_all)

    btn_layout = QHBoxLayout()
    ok_btn = QPushButton("OK")
    cancel_btn = QPushButton("Cancelar")
    ok_btn.clicked.connect(dialog.accept)
    cancel_btn.clicked.connect(dialog.reject)
    btn_layout.addWidget(ok_btn)
    btn_layout.addWidget(cancel_btn)
    layout.addLayout(btn_layout)

    if dialog.exec_() != QDialog.Accepted:
        return None

    if rb_all.isChecked():
        return set(task_names)
    for task, rb in radio_buttons.items():
        if rb.isChecked():
            return {task}
    return None


def _describe_clip_for_log(clip):
    """Devuelve una descripción compacta del clip para debug."""
    try:
        clip_name = clip.name() if hasattr(clip, "name") else "<sin nombre>"
        track_name = (
            clip.parentTrack().name()
            if hasattr(clip, "parentTrack") and clip.parentTrack()
            else "<sin track>"
        )
        timeline_in = clip.timelineIn() if hasattr(clip, "timelineIn") else "?"
        timeline_out = clip.timelineOut() if hasattr(clip, "timelineOut") else "?"

        file_path = ""
        try:
            media_source = clip.source().mediaSource() if clip.source() else None
            fileinfos = media_source.fileinfos() if media_source else []
            if fileinfos:
                file_path = fileinfos[0].filename()
        except Exception:
            file_path = ""

        file_name = os.path.basename(file_path) if file_path else "<sin fileinfo>"
        return (
            f"clip='{clip_name}' track='{track_name}' "
            f"range=[{timeline_in}-{timeline_out}] file='{file_name}'"
        )
    except Exception as e:
        return f"<error describiendo clip: {e}>"


def push_from_selected_clips(
    button_name, per_clip_callback=None, flow_target_version_mode=False
):
    """
    Función principal que usa el método centralizado para obtener clips.
    Resuelve la task activa en el playhead mediante el selector compartido antes de
    recopilar clips, de modo que solo se procesan clips del track de la task elegida.
    Si hay mismatch filename/track, avisa y excluye las opciones incorrectas del selector.

    Args:
        button_name: Nombre del botón de estado (ej: "Corrections", "Rev Dir", etc.)
        per_clip_callback: Función opcional que se ejecuta después de cada push exitoso.
                          Recibe (clip, base_name, exr_name) como parámetros.
                          Se ejecuta SOLO cuando el push es exitoso (no se cancela).
        flow_target_version_mode: Si True, activa el flujo Shift+Click para elegir
                          versión destino en Flow (solo permitido con 1 clip).

    Returns:
        bool: True si se inició la operación exitosamente, False si se canceló o hubo error
    """
    debug_print(f"push_from_selected_clips iniciado: estado='{button_name}'")

    is_valid, error_text, _state = validate_push_preflight()
    if not is_valid:
        debug_print(f"Preflight Push (entrypoint) falló:\n{error_text}")
        QMessageBox.warning(None, "PipeSync no configurado", error_text)
        return False

    # Imports locales (lazy) para evitar problemas de inicialización Qt al cargar el módulo.
    from LGA_NKS_Shared.LGA_NKS_TaskSelectionDialog import (
        resolve_task_with_mismatch_check,
        track_for_task,
    )

    # Resolver la task a usar mediante el selector compartido (con chequeo de mismatch).
    # Esto muestra el diálogo de mismatch si hay clips con filename/track inconsistentes,
    # y luego pide elegir task si hay más de una válida en el playhead.
    seq = hiero.ui.activeSequence()
    if not seq:
        debug_print("Push cancelado: no hay secuencia activa")
        return False

    def _extract_task_normalized(base_name):
        """Wrapper local: extrae task del filename y aplica aliases (compo→comp)."""
        raw = extract_task_name(base_name)
        return normalize_task_name(raw) if raw else raw

    resolved_task = resolve_task_with_mismatch_check(
        seq, _extract_task_normalized, clean_base_name,
        title="Push — Seleccionar task"
    )
    if resolved_task is None:
        debug_print("Push cancelado: no se seleccionó ninguna task")
        return False

    task_track = track_for_task(resolved_task)
    debug_print(f"Task resuelta para push: '{resolved_task}' → track '{task_track}'")

    # Regla de prioridad:
    # 1. Si hay selección explícita del usuario, filtrar al track de la task resuelta.
    # 2. Solo si no hay selección explícita, usar la lógica por playhead / método híbrido.
    explicitly_selected_clips = get_selected_clips()
    debug_print(f"Selección explícita detectada: {len(explicitly_selected_clips)} clip(s)")
    for idx, clip in enumerate(explicitly_selected_clips, start=1):
        debug_print(f"  [selección {idx}] {_describe_clip_for_log(clip)}")

    all_clips = []
    if explicitly_selected_clips:
        for clip in explicitly_selected_clips:
            clip_track_name = clip.parentTrack().name() if clip.parentTrack() else ""
            if clip_track_name == task_track:
                all_clips.append(clip)
                debug_print(
                    f"Clip seleccionado aceptado por track task: {_describe_clip_for_log(clip)}"
                )
            else:
                debug_print(
                    f"Clip seleccionado descartado (track '{clip_track_name}' ≠ '{task_track}'): {_describe_clip_for_log(clip)}"
                )
    else:
        debug_print(
            f"No hay selección explícita. Se busca clip(s) por playhead/método híbrido en '{task_track}'."
        )
        track_clips = get_clips_to_process(
            track_name=task_track, prioritize_multiple_selection=True
        )
        debug_print(
            f"Track '{task_track}': método híbrido devolvió {len(track_clips)} clip(s)"
        )
        for idx, clip in enumerate(track_clips, start=1):
            debug_print(f"  [híbrido {task_track} #{idx}] {_describe_clip_for_log(clip)}")
        all_clips.extend(track_clips)

    # Deduplicar por id (por si algún clip aparece en múltiples llamadas)
    seen_ids = set()
    clips = []
    for c in all_clips:
        if id(c) not in seen_ids:
            seen_ids.add(id(c))
            clips.append(c)
        else:
            debug_print(f"Clip duplicado descartado: {_describe_clip_for_log(c)}")

    debug_print(f"Clips candidatos luego de deduplicar: {len(clips)}")
    for idx, clip in enumerate(clips, start=1):
        debug_print(f"  [candidato {idx}] {_describe_clip_for_log(clip)}")

    if not clips:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Push to Flow - Error")
        msg.setText(
            "No se pudo obtener ningún clip. Verifique que haya un clip en los tracks de task bajo el playhead o que haya seleccionado clips válidos."
        )
        msg.exec_()
        return False

    # Patrones válidos de task: nombres de TASK_EXR_TRACKS + alias _cmp_ + aliases de naming
    task_name_patterns = [t.strip("_") for t in TASK_EXR_TRACKS] + ["cmp"] + list(TASK_NAME_ALIASES.keys())

    # Filtrar clips que corresponden a algún task track registrado
    valid_clips = []
    for clip in clips:
        if isinstance(clip, hiero.core.EffectTrackItem):
            debug_print(f"Clip es un efecto, se omite: {_describe_clip_for_log(clip)}")
            continue

        if not clip.source().mediaSource().isMediaPresent():
            debug_print(
                f"Clip no tiene media presente, se omite: {_describe_clip_for_log(clip)}"
            )
            continue

        fileinfos = clip.source().mediaSource().fileinfos()
        if not fileinfos:
            debug_print(f"Clip no tiene fileinfos, se omite: {_describe_clip_for_log(clip)}")
            continue

        file_path = fileinfos[0].filename()
        exr_name = os.path.basename(file_path)

        # Filtrar solo clips cuyo filename corresponde a un task track registrado
        if not any(f"_{p}_" in exr_name.lower() for p in task_name_patterns):
            debug_print(
                f"Clip no corresponde a ningún task track, se omite: {_describe_clip_for_log(clip)}"
            )
            continue

        valid_clips.append((clip, file_path, exr_name))
        debug_print(
            f"Clip válido para push: {_describe_clip_for_log(clip)} task_patterns={task_name_patterns}"
        )

    if not valid_clips:
        task_names_str = ", ".join(f"_{n}_" for n in task_name_patterns if n != "cmp")
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Warning)
        msg.setWindowTitle("Push to Flow - Error")
        msg.setText(
            f"No se encontraron clips válidos de task tracks ({task_names_str})."
        )
        msg.exec_()
        return False

    debug_print(f"Task resuelta '{resolved_task}': clips finales a procesar: {len(valid_clips)}")
    for idx, (clip, _fp, _en) in enumerate(valid_clips, start=1):
        debug_print(f"  [final {idx}] {_describe_clip_for_log(clip)}")

    # Determinar si el estado requiere comentario.
    sg_status = status_translation.get(button_name, None)
    note_capable_statuses = [
        "rev_di",
        "corr",
        "revleg",
        "revhld",
        "revcha",
        "revjua",
        "revjav",
    ]
    needs_message = sg_status in note_capable_statuses

    def create_clip_callback(current_clip, current_base_name, current_exr_name):
        """Crea un callback que ejecuta per_clip_callback si existe."""
        def callback_wrapper(success):
            if success and per_clip_callback:
                try:
                    per_clip_callback(current_clip, current_base_name, current_exr_name)
                except Exception as e:
                    debug_print(f"Error ejecutando per_clip_callback: {e}")
                    QMessageBox.critical(
                        None,
                        "Flow Push - Error post-push",
                        f"El Push termino, pero fallo la actualizacion local:\n\n{e}",
                    )
        return callback_wrapper

    # Shift+Click: elegir versión destino en Flow en background (solo 1 clip).
    if flow_target_version_mode:
        if not needs_message:
            debug_print(
                f"Shift+Click ignorado para estado '{button_name}' (no requiere comentario); se usa flujo normal."
            )
        elif len(valid_clips) != 1:
            QMessageBox.warning(
                None,
                "Shift+Click - Selección inválida",
                "Shift+Click para elegir versión de Flow solo admite 1 clip seleccionado.",
            )
            return False
        else:
            clip, file_path, exr_name = valid_clips[0]
            exr_name_processed = exr_name.replace(".%", "_%")
            base_name = clean_base_name(exr_name_processed)
            clip_callback = create_clip_callback(clip, base_name, exr_name)

            loader_worker = LoadFlowVersionsWorker(
                base_name, exr_name, file_path=file_path
            )
            _ACTIVE_FLOW_VERSION_LOAD_WORKERS.append(loader_worker)

            def _cleanup_loader():
                if loader_worker in _ACTIVE_FLOW_VERSION_LOAD_WORKERS:
                    _ACTIVE_FLOW_VERSION_LOAD_WORKERS.remove(loader_worker)

            def _on_versions_loaded(versions):
                _cleanup_loader()
                if not versions:
                    QMessageBox.warning(
                        None,
                        "Shift+Click - Sin versiones",
                        "No se encontraron versiones en Flow para esta task.",
                    )
                    return

                selected_version = show_flow_version_selection_dialog(base_name, versions)
                if selected_version is None:
                    debug_print("Shift+Click cancelado por el usuario en selector de versión.")
                    return

                result = Push_Task_Status(
                    button_name,
                    base_name,
                    clip_callback,
                    exr_name,
                    file_path=file_path,
                    target_version_number=selected_version,
                )
                if not result:
                    debug_print("Shift+Click: push no iniciado después de seleccionar versión.")

            def _on_versions_error(error_text):
                _cleanup_loader()
                QMessageBox.warning(
                    None,
                    "Shift+Click - Error",
                    f"No se pudieron listar versiones de Flow:\n{error_text}",
                )

            loader_worker.signals.loaded.connect(_on_versions_loaded)
            loader_worker.signals.error.connect(_on_versions_error)
            QThreadPool.globalInstance().start(loader_worker)
            debug_print(
                f"Shift+Click iniciado en background para '{base_name}' (estado '{button_name}')"
            )
            return True

    # Confirmar si hay más de 4 clips (igual que en el panel)
    if len(valid_clips) > 4:
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Question)
        msg.setWindowTitle("Confirm Status Application")
        msg.setText(
            f"¿Estás seguro de que quieres aplicar el estado '{button_name}' a {len(valid_clips)} clips?"
        )
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        result = msg.exec_()
        if result != QMessageBox.Yes:
            debug_print("Usuario canceló la operación (más de 4 clips)")
            return False

    # Para múltiples clips con mensaje, usar un mensaje compartido
    shared_message = None
    shared_review_images = []
    should_delete_images = False

    if needs_message and len(valid_clips) > 1:
        # Mostrar un diálogo simplificado sin imágenes específicas de clip
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        # Crear un diálogo simple sin imágenes
        dialog = QDialog()
        dialog.setWindowTitle("Input Dialog")
        layout = QVBoxLayout(dialog)

        # Label con información de cuántos clips se procesarán
        label_text = f"Mensaje para <b>{len(valid_clips)} clips</b>:"
        label = QLabel(label_text)
        label.setTextFormat(Qt.RichText)
        layout.addWidget(label)

        # Area de texto para el mensaje
        text_edit = QPlainTextEdit(dialog)
        text_edit.setFixedHeight(120)
        layout.addWidget(text_edit)

        # Botón OK
        ok_button = QPushButton("OK", dialog)
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)

        # Conectar Ctrl+Enter
        shortcut = QShortcut(QKeySequence(Qt.CTRL | Qt.Key_Return), dialog)
        shortcut.activated.connect(dialog.accept)

        dialog.adjustSize()

        if dialog.exec_() == QDialog.Accepted:
            shared_message = text_edit.toPlainText()
        else:
            debug_print(
                f"Usuario canceló el diálogo de mensaje compartido para {len(valid_clips)} clip(s)"
            )
            # Generar resumen de cancelación
            debug_resumen_print("=" * 70)
            debug_resumen_print("RESUMEN DEL PUSH")
            debug_resumen_print("=" * 70)
            debug_resumen_print(f"Clips a procesar: {len(valid_clips)}")
            debug_resumen_print(f"Estado: {button_name}")
            for idx, (clip, _fp, _en) in enumerate(valid_clips, start=1):
                debug_resumen_print(f"  - Clip {idx}: {_describe_clip_for_log(clip)}")
            debug_resumen_print("⚠️  RESULTADO: OPERACIÓN CANCELADA")
            debug_resumen_print("")
            debug_resumen_print("El usuario cerró el diálogo sin confirmar.")
            debug_resumen_print("=" * 70)
            print_debug_messages()
            print_resumen()
            return False

    # Procesar cada clip
    success_count = 0
    failed_count = 0

    for clip, file_path, exr_name in valid_clips:
        try:
            # Extraer base_name del clip
            # Reemplazar patrón .% por _% para análisis
            exr_name_processed = exr_name.replace(".%", "_%")

            # Usar la función del módulo de naming para obtener base_name
            base_name = clean_base_name(exr_name_processed)

            debug_print(f"Procesando clip: {base_name}")

            # Llamar a Push_Task_Status para cada clip
            # Si es un solo clip con mensaje, usar el diálogo completo (con imágenes)
            # Si son múltiples clips, ya tenemos el mensaje compartido
            if len(valid_clips) == 1:
                # Un solo clip: usar Push_Task_Status con callback
                clip_callback = create_clip_callback(clip, base_name, exr_name)
                result = Push_Task_Status(
                    button_name, base_name, clip_callback, exr_name, file_path=file_path
                )
            else:
                # Múltiples clips: pasar el mensaje compartido directamente
                # Necesitamos crear un worker manualmente porque ya tenemos el mensaje
                if needs_message:
                    # Estados que necesitan mensaje: usar el mensaje compartido
                    clip_callback = create_clip_callback(clip, base_name, exr_name)
                    worker = Worker(
                        button_name,
                        base_name,
                        shared_message,
                        shared_review_images,
                        should_delete_images,
                        exr_name,
                        file_path=file_path,
                    )
                    worker.signals.result_ready.connect(handle_results)
                    worker.signals.error.connect(show_push_error_message)
                    worker.signals.debug_output.connect(lambda: print_debug_messages())
                    worker.signals.resumen_output.connect(lambda: print_resumen())
                    # Conectar el callback para ejecutarse cuando el push sea exitoso
                    worker.signals.task_finished.connect(clip_callback)
                    QThreadPool.globalInstance().start(worker)
                    result = True
                else:
                    # Estados que NO necesitan mensaje: usar Push_Task_Status con callback
                    clip_callback = create_clip_callback(clip, base_name, exr_name)
                    result = Push_Task_Status(
                        button_name, base_name, clip_callback, exr_name, file_path=file_path
                    )

            if result:
                success_count += 1
            else:
                failed_count += 1

        except Exception as e:
            debug_print(f"Error procesando clip {os.path.basename(file_path)}: {e}")
            failed_count += 1

    # Resumen final si procesamos múltiples clips
    if len(valid_clips) > 1:
        debug_resumen_print("=" * 70)
        debug_resumen_print("RESUMEN DEL PUSH MÚLTIPLE")
        debug_resumen_print("=" * 70)
        debug_resumen_print(f"Total de clips procesados: {len(valid_clips)}")
        debug_resumen_print(f"Estado aplicado: {button_name}")
        debug_resumen_print(f"✅ Exitosos: {success_count}")
        if failed_count > 0:
            debug_resumen_print(f"❌ Fallidos: {failed_count}")
        debug_resumen_print("=" * 70)
        print_resumen()

    return success_count > 0


msg_manager = MessageBoxManager()
