"""
_____________________________________________________________

  LGA_NKS_Flow_Push v3.52 - Lega Pugliese

  **Tiene más opciones de debug y se puede ver el estado de la tarea antes y después de la actualización.**
  ___________________________________________________________

"""

import os
import re
import shotgun_api3
import sqlite3
import platform
import glob
import shutil
import tempfile
from PySide2.QtCore import QRunnable, Slot, QThreadPool, Signal, QObject, Qt
import datetime
import subprocess  # Importar subprocess para abrir archivos

# from PySide2.QtCore import QWaitCondition, QMutex
from PySide2.QtWidgets import (
    QApplication,
    QMessageBox,
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QLabel,
    QShortcut,
    QScrollArea,
    QWidget,
    QCheckBox,
)
from PySide2.QtGui import QKeySequence, QPixmap

# Diccionario de traduccion de estados
status_translation = {
    "Corrections": "corr",
    "Corrs_Lega": "revleg",
    "Rev_Sup": "rev_su",
    "Rev_Lega": "revleg",
    "Rev_Dir": "rev_di",
    "Approved": "pubsh",
    "Rev_Sup_D": "rev_su",
    "Rev_Dir_D": "rev_di",
    "Rev_Hold": "revhld",
}

# Variable global para activar o desactivar los prints // En esta version el Debug se imprime al final del script
DEBUG = True
debug_messages = []


def debug_print(message):
    if DEBUG:
        debug_messages.append(message)


def find_review_images(base_name):
    """
    Busca imagenes de ReviewPic para el shot y version especificados.
    Retorna una lista de rutas de imagenes encontradas.
    """
    try:
        # Extraer informacion del nombre base
        parts = base_name.split("_")

        # Buscar numero de version
        version_number_str = None
        for part in parts:
            if part.startswith("v") and part[1:].isdigit():
                version_number_str = part
                break

        if not version_number_str:
            debug_print("No se encontro numero de version en el nombre base")
            return []

        # Construir el nombre de la carpeta del clip siguiendo el mismo patron que ReviewPic
        # El patron es: {base_name_sin_version}_v{version}
        # Ejemplo: si base_name es "PROJ_SEQ_SHOT_comp_v001_001.exr"
        # necesitamos "PROJ_SEQ_SHOT_comp_v001"

        # Encontrar la posicion de la version en el nombre
        version_index = -1
        for i, part in enumerate(parts):
            if part == version_number_str:
                version_index = i
                break

        if version_index == -1:
            debug_print(
                f"No se pudo encontrar la version {version_number_str} en las partes del nombre"
            )
            return []

        # Tomar todas las partes hasta la version (inclusive)
        base_parts = parts[: version_index + 1]
        clip_folder_name = "_".join(base_parts)

        # Obtener la ruta del script actual
        script_dir = os.path.dirname(__file__)
        cache_dir = os.path.join(script_dir, "ReviewPic_Cache")
        clip_dir = os.path.join(cache_dir, clip_folder_name)

        debug_print(f"Buscando imagenes en: {clip_dir}")
        debug_print(f"Nombre de carpeta construido: {clip_folder_name}")

        # Buscar archivos JPG en la carpeta
        if os.path.exists(clip_dir):
            image_pattern = os.path.join(clip_dir, "*.jpg")
            images = glob.glob(image_pattern)
            debug_print(f"Imagenes encontradas: {len(images)}")
            return sorted(images)  # Ordenar para mostrar en orden consistente
        else:
            debug_print(f"Carpeta no existe: {clip_dir}")
            return []

    except Exception as e:
        debug_print(f"Error buscando imagenes de review: {e}")
        return []


class DBManager:
    """Clase para manejar operaciones con la base de datos SQLite local."""

    def __init__(self):
        # Selecciona la ruta de la base de datos segun el sistema operativo
        if platform.system() == "Windows":
            self.db_path = r"C:/Portable/LGA/PipeSync/cache/pipesync.db"
        elif platform.system() == "Darwin":
            self.db_path = "/Users/leg4/Library/Caches/LGA/PipeSync/pipesync.db"
        else:
            debug_print(f"Sistema operativo no soportado: {platform.system()}")
            self.db_path = None

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
    def __init__(self, base_name):
        super(InputDialog, self).__init__()
        self.setWindowTitle("Input Dialog")
        self.base_name = base_name
        self.review_images = []
        self.delete_images_checkbox = None

        self.layout = QVBoxLayout(self)

        # Label para el mensaje
        self.label = QLabel(f"Message for {base_name}:")
        self.layout.addWidget(self.label)

        # Area de texto para el mensaje
        self.text_edit = QPlainTextEdit(self)
        self.text_edit.setFixedHeight(120)  # Ajustar la altura de la caja de texto
        self.layout.addWidget(self.text_edit)

        # Buscar imagenes de ReviewPic y mostrar thumbnails si existen
        self.review_images = find_review_images(base_name)
        if self.review_images:
            self.add_thumbnails_section(self.review_images)
            self.adjust_window_size()  # Esto establece el ancho y la altura actual
            self.setFixedWidth(
                self.width()
            )  # Fijar el ancho para que adjustSize solo afecte la altura

        # Boton OK
        self.ok_button = QPushButton("OK", self)
        self.ok_button.clicked.connect(self.accept)
        self.layout.addWidget(self.ok_button)

        # Conectar Ctrl+Enter al metodo accept
        shortcut = QShortcut(QKeySequence(Qt.CTRL + Qt.Key_Return), self)
        shortcut.activated.connect(self.accept)

        # Ajustar el tamaño del diálogo para que se ajuste a su contenido (ahora solo ajusta la altura)
        self.adjustSize()

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

                        # Agregar numero de frame debajo de la imagen
                        frame_number = self.extract_frame_number_from_filename(
                            image_path
                        )
                        frame_label = QLabel(f"Frame: {frame_number}")
                        frame_label.setStyleSheet(
                            "color: #9c9c9c; font-size: 11px; margin-left: 4px;"
                        )
                        frame_label.setAlignment(Qt.AlignLeft)
                        container_layout.addWidget(frame_label)

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
    def __init__(self, url, script_name, api_key, sudo_login):
        debug_print("Inicializando conexion a ShotGrid")
        try:
            self.sg = shotgun_api3.Shotgun(
                url, script_name=script_name, api_key=api_key, sudo_as_login=sudo_login
            )
            debug_print("Conexion a ShotGrid inicializada exitosamente")
        except Exception as e:
            debug_print(f"Error al inicializar la conexion a ShotGrid: {e}")
            self.sg = None

    def find_shot_and_tasks(self, project_name, shot_code):
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return None, None, None
        debug_print(f"Buscando proyecto con nombre: {project_name}")
        try:
            projects = self.sg.find(
                "Project", [["name", "is", project_name]], ["id", "name"]
            )
        except Exception as e:
            debug_print(f"Error buscando proyecto: {e}")
            return None, None, None
        if projects:
            project_id = projects[0]["id"]
            debug_print(
                f"Proyecto encontrado: {projects[0]['name']} (ID: {project_id})"
            )
            filters = [
                ["project", "is", {"type": "Project", "id": project_id}],
                ["code", "is", shot_code],
            ]
            fields = ["id", "code", "description"]
            try:
                shots = self.sg.find("Shot", filters, fields)
            except Exception as e:
                debug_print(f"Error buscando shot: {e}")
                return projects[0], None, None
            if shots:
                shot_id = shots[0]["id"]
                debug_print(f"Shot encontrado: {shots[0]['code']} (ID: {shot_id})")
                tasks = self.find_tasks_for_shot(shot_id)
                return projects[0], shots[0], tasks
            else:
                debug_print("No se encontro el Shot con el codigo especificado.")
                return projects[0], None, None
        else:
            debug_print("No se encontro el proyecto con el nombre especificado.")
            return None, None, None

    def find_tasks_for_shot(self, shot_id):
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return []
        filters = [["entity", "is", {"type": "Shot", "id": shot_id}]]
        fields = ["id", "content", "sg_status_list"]
        try:
            tasks = self.sg.find("Task", filters, fields)
            # Debug: mostrar estados actuales de las tasks
            for task in tasks:
                debug_print(
                    f"Task encontrada: {task['content']} (ID: {task['id']}) - Estado actual: {task['sg_status_list']}"
                )
            return tasks
        except Exception as e:
            debug_print(f"Error buscando tareas para shot_id {shot_id}: {e}")
            return []

    def find_highest_version_for_shot(self, shot_id):
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return None, None, None
        filters = [["entity", "is", {"type": "Shot", "id": shot_id}]]
        fields = ["code", "created_at", "user", "sg_status_list", "description"]
        try:
            versions = self.sg.find("Version", filters, fields)
        except Exception as e:
            debug_print(f"Error buscando versiones para shot_id {shot_id}: {e}")
            return None, None, None

        # Debug: mostrar todas las versiones encontradas
        debug_print(
            f"Total de versiones encontradas para shot_id {shot_id}: {len(versions)}"
        )
        for v in versions:
            debug_print(f"Version encontrada: {v['code']}")

        # Buscar versiones que contengan "comp" (más flexible)
        comp_versions = [v for v in versions if "comp" in v["code"].lower()]
        debug_print(f"Versiones con 'comp' encontradas: {len(comp_versions)}")

        # Si no hay versiones con comp, usar todas las versiones
        if not comp_versions:
            debug_print(
                "No se encontraron versiones con 'comp', usando todas las versiones"
            )
            comp_versions = versions

        if comp_versions:

            def safe_version_num(v):
                m = re.search(r"_v(\d+)", v["code"])
                return int(m.group(1)) if m else -1

            highest_version = max(comp_versions, key=safe_version_num)
            m = re.search(r"_v(\d+)", highest_version["code"])
            version_number = m.group(1) if m else "0"
            user_id = (
                highest_version["user"]["id"]
                if highest_version.get("user") and highest_version["user"].get("id")
                else None
            )
            debug_print(
                f"Version mas alta encontrada: {highest_version['code']} (v{version_number})"
            )
            return highest_version, version_number, user_id

        debug_print("No se encontraron versiones validas para el shot")
        return None, None, None

    def find_version_by_code_pattern(self, project_name, shot_code, version_str):
        """
        Busca una version especifica usando patron de codigo mas flexible.
        Usado como fallback cuando find_highest_version_for_shot falla.
        """
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return None
        try:
            debug_print(
                f"Buscando version especifica con patron: {shot_code}*{version_str}"
            )
            filters = [
                ["project.Project.name", "is", project_name],
                ["entity.Shot.code", "is", shot_code],
                ["code", "contains", version_str],
            ]
            fields = [
                "id",
                "code",
                "created_at",
                "user",
                "sg_status_list",
                "description",
            ]
            versions = self.sg.find("Version", filters, fields)

            if versions:
                # Buscar la version que coincida mas exactamente
                for version in versions:
                    debug_print(f"Version encontrada en fallback: {version['code']}")
                    if version_str in version["code"]:
                        debug_print(
                            f"Usando version fallback: {version['code']} (ID: {version['id']})"
                        )
                        return version

                # Si no encuentra coincidencia exacta, usar la primera
                debug_print(
                    f"Usando primera version encontrada: {versions[0]['code']} (ID: {versions[0]['id']})"
                )
                return versions[0]

            debug_print("No se encontraron versiones en fallback")
            return None
        except Exception as e:
            debug_print(f"Error en busqueda fallback de version: {e}")
            return None

    def update_task_status(self, task_id, new_status):
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return
        try:
            debug_print(
                f"Actualizando estado de la tarea (ID: {task_id}) a: {new_status}"
            )

            # FORZAR VERIFICACION ANTES DEL UPDATE
            debug_print("=== VERIFICACION PRE-UPDATE ===")
            pre_task = self.sg.find_one(
                "Task",
                [["id", "is", task_id]],
                ["sg_status_list"],
                order=[{"field_name": "id", "direction": "asc"}],
            )
            debug_print(
                f"Estado PRE-update desde ShotGrid: {pre_task['sg_status_list'] if pre_task else 'NO_ENCONTRADO'}"
            )

            # REALIZAR EL UPDATE
            debug_print("=== EJECUTANDO UPDATE ===")
            result = self.sg.update("Task", task_id, {"sg_status_list": new_status})
            debug_print(f"Resultado de actualizacion de task: {result}")

            # FORZAR VERIFICACION POST-UPDATE (sin cache)
            debug_print("=== VERIFICACION POST-UPDATE (FRESH) ===")
            import time

            time.sleep(1)  # Pequeña pausa para asegurar consistencia
            post_task = self.sg.find_one(
                "Task",
                [["id", "is", task_id]],
                ["sg_status_list"],
                order=[{"field_name": "id", "direction": "asc"}],
            )
            debug_print(
                f"Estado POST-update desde ShotGrid: {post_task['sg_status_list'] if post_task else 'NO_ENCONTRADO'}"
            )

            # VERIFICAR SI REALMENTE CAMBIO
            if pre_task and post_task:
                if pre_task["sg_status_list"] != post_task["sg_status_list"]:
                    debug_print(
                        f"✅ CAMBIO CONFIRMADO: {pre_task['sg_status_list']} -> {post_task['sg_status_list']}"
                    )
                else:
                    debug_print(
                        f"❌ NO HUBO CAMBIO REAL: Se mantuvo en {post_task['sg_status_list']}"
                    )
                    debug_print("❌ EL UPDATE FALLO SILENCIOSAMENTE")

        except Exception as e:
            debug_print(f"Error al actualizar el estado de la tarea: {e}")
            import traceback

            debug_print(f"Traceback completo: {traceback.format_exc()}")

    def get_valid_task_statuses(self, task_id):
        """Obtiene los estados válidos para una task específica"""
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return []
        try:
            # Intentar obtener el schema de la entidad Task para ver estados válidos
            schema = self.sg.schema_field_read("Task", "sg_status_list")
            debug_print(f"Schema obtenido para Task.sg_status_list: {type(schema)}")
            # Simplificado para evitar errores de linter - solo reportar que se intentó
            return []
        except Exception as e:
            debug_print(f"Error obteniendo estados válidos para Task: {e}")
            return []

    def update_version_status(self, project_name, shot_code, version_str, new_status):
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return
        try:
            debug_print(
                f"Actualizando estado de la version para el Shot: {shot_code}, Version: {version_str} a: {new_status}"
            )

            # Metodo 1: Buscar por vinculacion al shot (metodo original)
            filters = [
                ["project.Project.name", "is", project_name],
                ["entity.Shot.code", "is", shot_code],
                ["code", "contains", version_str],
            ]
            fields = ["id", "code"]
            versions = self.sg.find("Version", filters, fields)
            debug_print(
                f"Versiones encontradas por vinculacion al shot: {len(versions)}"
            )

            # Metodo 2: Si no se encuentran versiones, buscar por patron de codigo (fallback)
            if not versions:
                debug_print(
                    "No se encontraron versiones vinculadas al shot, usando busqueda por patron de codigo"
                )
                filters_fallback = [
                    ["project.Project.name", "is", project_name],
                    ["code", "contains", shot_code],
                    ["code", "contains", version_str],
                ]
                versions = self.sg.find("Version", filters_fallback, fields)
                debug_print(
                    f"Versiones encontradas por patron de codigo: {len(versions)}"
                )

            # Actualizar las versiones encontradas
            for version in versions:
                debug_print(
                    f"Actualizando version (ID: {version['id']}, codigo: {version['code']}) a estado: {new_status}"
                )
                self.sg.update("Version", version["id"], {"sg_status_list": new_status})

            if not versions:
                debug_print(
                    f"No se encontraron versiones para actualizar con patron: {shot_code}*{version_str}"
                )

        except Exception as e:
            debug_print(f"Error al actualizar el estado de la version: {e}")

    def get_task_assignee(self, task_id):
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return None
        try:
            task = self.sg.find_one("Task", [["id", "is", task_id]], ["task_assignees"])
            if task and task["task_assignees"]:
                return task["task_assignees"][0]["id"]
            return None
        except Exception as e:
            debug_print(f"Error al obtener el asignado de la tarea: {e}")
            return None

    def add_comment_to_version(
        self, version_id, project_id, comment, user_id, task_assignee_id, shot_id=None
    ):
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return
        try:
            debug_print(
                f"Agregando comentario a la version (ID: {version_id}): {comment}"
            )
            addressings_to = [{"type": "HumanUser", "id": user_id}]
            if task_assignee_id and task_assignee_id != user_id:
                addressings_to.append({"type": "HumanUser", "id": task_assignee_id})
            note_data = {
                "project": {"type": "Project", "id": project_id},
                "content": comment,
                "note_links": [
                    {"type": "Version", "id": version_id},
                    {"type": "Shot", "id": shot_id},
                ],
                "addressings_to": addressings_to,
            }
            created_note = self.sg.create("Note", note_data)
            return created_note
        except Exception as e:
            debug_print(f"Error al agregar comentario a la version: {e}")
            return None

    def attach_images_to_note(self, note_id, version_id, image_paths):
        """
        Adjunta imagenes a una nota con numeros de frame siguiendo la convencion de ShotGrid.
        Usa upload directo a Note que es el metodo mas simple y efectivo.
        """
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return False

        try:
            # Crear una carpeta temporal para los archivos renombrados
            temp_dir = tempfile.mkdtemp()
            debug_print(f"Carpeta temporal creada: {temp_dir}")

            attached_count = 0

            for image_path in image_paths:
                if not os.path.exists(image_path):
                    debug_print(f"Imagen no encontrada: {image_path}")
                    continue

                # Extraer numero de frame del nombre del archivo
                frame_number = self.extract_frame_number_from_path(image_path)

                # Crear nombre de archivo con convencion de ShotGrid para mostrar frame number
                # Formato: annot_version_<version_id>.<frame_number>.jpg
                file_extension = os.path.splitext(image_path)[1]
                new_filename = (
                    f"annot_version_{version_id}.{frame_number}{file_extension}"
                )
                temp_file_path = os.path.join(temp_dir, new_filename)

                # Copiar archivo con el nuevo nombre
                shutil.copy2(image_path, temp_file_path)
                debug_print(f"Archivo copiado: {image_path} -> {temp_file_path}")

                # Subir archivo directamente a la nota usando el metodo que funciono en exploracion
                try:
                    uploaded_attachment_id = self.sg.upload(
                        "Note", note_id, temp_file_path, field_name="attachments"
                    )

                    if uploaded_attachment_id:
                        attached_count += 1
                        debug_print(
                            f"Imagen adjuntada exitosamente: {new_filename} (ID: {uploaded_attachment_id})"
                        )
                    else:
                        debug_print(
                            f"Error: No se obtuvo ID de attachment para {new_filename}"
                        )

                except Exception as upload_error:
                    debug_print(
                        f"Error subiendo archivo {new_filename}: {upload_error}"
                    )
                    continue

            # Limpiar carpeta temporal
            try:
                shutil.rmtree(temp_dir)
                debug_print(f"Carpeta temporal eliminada: {temp_dir}")
            except Exception as cleanup_error:
                debug_print(f"Error limpiando carpeta temporal: {cleanup_error}")

            debug_print(
                f"Adjuntadas {attached_count} imagenes de {len(image_paths)} totales"
            )
            return attached_count > 0

        except Exception as e:
            debug_print(f"Error adjuntando imagenes a la nota: {e}")
            return False

    def extract_frame_number_from_path(self, image_path):
        """
        Extrae el numero de frame de la ruta de una imagen.
        Busca patrones como _0001.jpg, _1234.jpg, etc.
        """
        try:
            filename = os.path.basename(image_path)
            name_without_ext = os.path.splitext(filename)[0]

            # Buscar el ultimo grupo de 4 digitos precedido por guion bajo
            match = re.search(r"_(\d{4})(?:_\d+)?$", name_without_ext)
            if match:
                return match.group(1)

            # Si no encuentra el patron, buscar cualquier numero al final
            match = re.search(r"_(\d+)(?:_\d+)?$", name_without_ext)
            if match:
                return match.group(1).zfill(4)  # Rellenar con ceros a la izquierda

            return "0001"  # Valor por defecto

        except Exception as e:
            debug_print(f"Error extrayendo numero de frame de {image_path}: {e}")
            return "0001"

    def get_project_id_from_version(self, version_id):
        """
        Obtiene el ID del proyecto a partir del ID de una version.
        """
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return None
        try:
            version = self.sg.find_one(
                "Version", [["id", "is", version_id]], ["project"]
            )
            if version and version.get("project"):
                return version["project"]["id"]
            return None
        except Exception as e:
            debug_print(f"Error obteniendo project_id de version {version_id}: {e}")
            return None


class WorkerSignals(QObject):
    result_ready = Signal(str, int, int)
    task_finished = Signal(bool)  # Ahora incluye el estado de exito
    debug_output = Signal()  # Nueva señal para imprimir logs


class Worker(QRunnable):
    def __init__(
        self,
        button_name,
        base_name,
        sg_manager,
        message,
        review_images=None,
        should_delete_images=False,
    ):
        super(Worker, self).__init__()
        self.button_name = button_name
        self.base_name = base_name
        self.sg_manager = sg_manager
        self.message = message
        self.review_images = review_images or []
        self.should_delete_images = should_delete_images
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        db_manager = DBManager()  # Crear la conexión en el hilo correcto
        try:
            project_name = self.base_name.split("_")[0]
            parts = self.base_name.split("_")
            shot_code = "_".join(parts[:5])

            version_number_str = None
            for part in parts:
                if part.startswith("v") and part[1:].isdigit():
                    version_number_str = part
                    break

            if version_number_str:
                version_number = int(version_number_str.replace("v", ""))
                debug_print(f"Shot code: {shot_code}, Version number: {version_number}")
            else:
                debug_print(
                    "Error: No se encontro un numero de version valido en el nombre del archivo."
                )
                return

            version_index = parts.index(version_number_str)
            task_name = parts[version_index - 1].lower()

            debug_print(
                f"Buscando shot y tareas para el proyecto: {project_name}, Shot: {shot_code}"
            )
            project, shot, tasks = self.sg_manager.find_shot_and_tasks(
                project_name, shot_code
            )

            if shot:
                debug_print(f"Shot encontrado: {shot['code']} (ID: {shot['id']})")

                # Realizar las actualizaciones en ShotGrid
                sg_status = status_translation.get(self.button_name, None)
                if sg_status:
                    task_id = None
                    task_assignee_id = None
                    for task in tasks:
                        if task["content"].lower() == task_name:
                            current_status = task["sg_status_list"]
                            debug_print(
                                f"Actualizando tarea: {task['content']} (ID: {task['id']}) - Estado actual: {current_status} -> Nuevo estado: {sg_status}"
                            )

                            # Verificar si realmente hay un cambio
                            if current_status == sg_status:
                                debug_print(
                                    f"ADVERTENCIA: La tarea ya está en estado '{sg_status}'. No hay cambio real."
                                )
                            else:
                                debug_print(
                                    f"CAMBIO DETECTADO: '{current_status}' -> '{sg_status}'"
                                )

                            # Debug: verificar estados válidos antes de actualizar
                            valid_statuses = self.sg_manager.get_valid_task_statuses(
                                task["id"]
                            )
                            if sg_status not in valid_statuses and valid_statuses:
                                debug_print(
                                    f"ADVERTENCIA: '{sg_status}' no está en los estados válidos: {valid_statuses}"
                                )

                            self.sg_manager.update_task_status(task["id"], sg_status)
                            task_id = task["id"]
                            task_assignee_id = self.sg_manager.get_task_assignee(
                                task_id
                            )

                            # Actualizar en base de datos local si existe
                            db_shot = db_manager.find_shot(project_name, shot_code)
                            if db_shot:
                                db_task = db_manager.find_task(db_shot["id"], task_name)
                                if db_task:
                                    debug_print(
                                        f"Actualizando estado de tarea local (ID: {db_task['id']}) a: {sg_status}"
                                    )
                                    db_manager.update_task_status(
                                        db_task["id"], sg_status
                                    )

                                    # Obtener la última versión para esta tarea
                                    latest_version = db_manager.find_latest_version(
                                        db_task["id"]
                                    )
                                    if latest_version:
                                        # Decidir qué estado aplicar a la versión dependiendo del estado de la tarea
                                        version_status = None
                                        if sg_status == "rev_di" or sg_status == "corr":
                                            version_status = "vwd"
                                        elif sg_status == "rev_su":
                                            version_status = "rev"
                                        elif sg_status == "revleg":
                                            version_status = "unvleg"

                                        if version_status:
                                            debug_print(
                                                f"Actualizando estado de versión local (ID: {latest_version['id']}, version: {latest_version['version_number']}) a: {version_status}"
                                            )
                                            db_manager.update_version_status(
                                                db_task["id"],
                                                latest_version["version_number"],
                                                version_status,
                                            )

                                        # Añadir nota si hay mensaje
                                        if self.message:
                                            debug_print(
                                                f"Añadiendo nota a versión local (ID: {latest_version['id']})"
                                            )
                                            db_manager.add_version_note(
                                                latest_version["id"], self.message
                                            )
                                else:
                                    debug_print(
                                        f"No se encontró la tarea: {task_name} en la base de datos local"
                                    )
                            else:
                                debug_print(
                                    f"No se encontró el shot: {shot_code} en la base de datos local"
                                )
                            break

                    # Buscar la versión más alta para obtener su ID y usuario para los comentarios
                    sg_highest_version, sg_version_number, user_id = (
                        self.sg_manager.find_highest_version_for_shot(shot["id"])
                    )

                    # Si no se encuentra la version mas alta, usar fallback
                    if not sg_highest_version:
                        debug_print(
                            "No se encontro version mas alta, usando busqueda fallback"
                        )
                        sg_highest_version = (
                            self.sg_manager.find_version_by_code_pattern(
                                project_name, shot_code, version_number_str
                            )
                        )
                        if sg_highest_version:
                            # Extraer user_id de la version encontrada
                            user_id = (
                                sg_highest_version["user"]["id"]
                                if sg_highest_version.get("user")
                                and sg_highest_version["user"].get("id")
                                else None
                            )
                            debug_print(
                                f"Version encontrada por fallback: {sg_highest_version['code']} (ID: {sg_highest_version['id']})"
                            )

                    if sg_status == "rev_di" or sg_status == "corr":
                        debug_print(
                            f"Actualizando version del Shot: {shot_code}, Version: {version_number_str} a: vwd"
                        )
                        self.sg_manager.update_version_status(
                            project_name, shot_code, version_number_str, "vwd"
                        )
                        project_id = project["id"]
                        try:
                            if self.message and sg_highest_version:
                                debug_print(
                                    f"Agregando comentario a la version (ID: {sg_highest_version['id']}): {self.message}"
                                )
                                created_note = self.sg_manager.add_comment_to_version(
                                    sg_highest_version["id"],
                                    project_id,
                                    self.message,
                                    user_id,
                                    task_assignee_id,
                                    shot["id"],
                                )

                                # Adjuntar imagenes si existen y se creo la nota
                                if created_note and self.review_images:
                                    debug_print(
                                        f"Adjuntando {len(self.review_images)} imagenes a la nota"
                                    )
                                    self.sg_manager.attach_images_to_note(
                                        created_note["id"],
                                        sg_highest_version["id"],
                                        self.review_images,
                                    )
                            elif self.message and not sg_highest_version:
                                debug_print(
                                    "No se pudo encontrar version para agregar comentario"
                                )
                        except Exception as e:
                            debug_print(f"Error while adding comment to version: {e}")
                    elif sg_status == "rev_su":
                        debug_print(
                            f"Actualizando version del Shot: {shot_code}, Version: {version_number_str} a: rev"
                        )
                        self.sg_manager.update_version_status(
                            project_name, shot_code, version_number_str, "rev"
                        )
                    elif sg_status == "revleg":
                        debug_print(
                            f"Actualizando version del Shot: {shot_code}, Version: {version_number_str} a: unvleg"
                        )
                        self.sg_manager.update_version_status(
                            project_name, shot_code, version_number_str, "unvleg"
                        )
                        project_id = project["id"]
                        try:
                            if self.message and sg_highest_version:
                                debug_print(
                                    f"Agregando comentario a la version (ID: {sg_highest_version['id']}): {self.message}"
                                )
                                created_note = self.sg_manager.add_comment_to_version(
                                    sg_highest_version["id"],
                                    project_id,
                                    self.message,
                                    user_id,
                                    task_assignee_id,
                                    shot["id"],
                                )

                                # Adjuntar imagenes si existen y se creo la nota
                                if created_note and self.review_images:
                                    debug_print(
                                        f"Adjuntando {len(self.review_images)} imagenes a la nota"
                                    )
                                    self.sg_manager.attach_images_to_note(
                                        created_note["id"],
                                        sg_highest_version["id"],
                                        self.review_images,
                                    )
                            elif self.message and not sg_highest_version:
                                debug_print(
                                    "No se pudo encontrar version para agregar comentario"
                                )
                        except Exception as e:
                            debug_print(f"Error while adding comment to version: {e}")
                else:
                    debug_print(
                        f"No se encontro un estado valido para: {self.button_name}"
                    )
            else:
                debug_print(f"No se encontro el Shot con el codigo: {shot_code}")
            # Marcar como exitoso si llegamos hasta aqui sin excepciones
            success = True
        except Exception as e:
            debug_print(f"Exception in Worker.run: {e}")
            success = False
        finally:
            # Cerrar la conexión a la base de datos
            if db_manager:
                db_manager.close()

            # Borrar imagenes SOLO si se completó exitosamente y el usuario lo solicitó
            if success and self.should_delete_images:
                debug_print(
                    "Operacion exitosa: Borrando carpeta ReviewPic_Cache como solicitó el usuario"
                )
                delete_review_pic_cache()
            elif not success and self.should_delete_images:
                debug_print("Operacion fallida: NO se borra la carpeta ReviewPic_Cache")

            self.signals.task_finished.emit(success)
            self.signals.debug_output.emit()  # Emitir señal al finalizar


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


def handle_results(info, sg_version_number, version_number):
    if sg_version_number > version_number:
        msg_manager.show_warning_message(info)


def Push_Task_Status(button_name, base_name, update_callback=None):
    global msg_manager

    # Obtener las credenciales del script desde las variables de entorno
    sg_url = os.getenv("SHOTGRID_URL")
    sg_script_name = os.getenv("SHOTGRID_SCRIPT_NAME")
    sg_api_key = os.getenv("SHOTGRID_API_KEY")
    sg_login = os.getenv("SHOTGRID_LOGIN")  # Para sudo_as_login

    if not sg_url or not sg_script_name or not sg_api_key or not sg_login:
        debug_print(
            "Las variables de entorno SHOTGRID_URL, SHOTGRID_SCRIPT_NAME, SHOTGRID_API_KEY y SHOTGRID_LOGIN deben estar configuradas."
        )
        return False  # Retornar False si faltan variables de entorno

    sg_manager = ShotGridManager(sg_url, sg_script_name, sg_api_key, sg_login)

    # Primero solicitar el mensaje al usuario para ciertos estados
    message = None
    review_images = []
    should_delete_images = False
    sg_status = status_translation.get(button_name, None)
    if sg_status in ["rev_di", "corr", "revleg", "revhld"]:
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        input_dialog = InputDialog(base_name)
        message = input_dialog.get_text()
        if message is None:
            # Operación cancelada por el usuario al cerrar el diálogo de comentarios
            print_debug_messages()  # Imprimir logs si el usuario cancela
            return False

        # Obtener información adicional del diálogo
        review_images = input_dialog.get_review_images()
        should_delete_images = bool(input_dialog.should_delete_images())
        print_debug_messages()  # Imprimir logs después de obtener la información del diálogo

    # Ahora extraer información del nombre base y verificar versiones
    try:
        project_name = base_name.split("_")[0]
        parts = base_name.split("_")
        shot_code = "_".join(parts[:5])

        # Extraer número de versión
        version_number_str = None
        for part in parts:
            if part.startswith("v") and part[1:].isdigit():
                version_number_str = part
                break

        if not version_number_str:
            debug_print(
                "Error: No se encontró un número de versión válido en el nombre del archivo."
            )
            return False

        local_version = int(version_number_str.replace("v", ""))

        # Verificar versión en Flow ANTES de hacer cualquier cambio
        project, shot, _ = sg_manager.find_shot_and_tasks(project_name, shot_code)
        if not shot:
            debug_print(f"No se encontró el Shot con el código: {shot_code}")
            return False

        sg_highest_version, sg_version_number, _ = (
            sg_manager.find_highest_version_for_shot(shot["id"])
        )
        if not sg_highest_version:
            debug_print(
                f"No se encontró la versión más alta para el Shot (ID: {shot['id']})"
            )
        elif sg_version_number and int(sg_version_number) > local_version:
            # Si la versión en Flow es mayor, mostrar el diálogo y preguntar si desea continuar
            debug_print(
                f"Versión local ({local_version}) es menor que la versión en Flow ({sg_version_number})"
            )
            if not show_version_dialog(base_name, local_version, sg_version_number):
                debug_print(
                    "Usuario canceló la operación debido a diferencia de versiones"
                )
                return False  # El usuario decidió no continuar
    except Exception as e:
        debug_print(f"Error durante la verificación de versiones: {e}")
        # Continuamos con el proceso aunque falle la verificación

    # Una vez que el usuario ha confirmado (o no hay problema de versiones), proceder con las actualizaciones
    if sg_status in ["rev_di", "corr", "revleg", "revhld"]:
        worker = Worker(
            button_name,
            base_name,
            sg_manager,
            message,
            review_images,
            should_delete_images,
        )
        worker.signals.result_ready.connect(handle_results)
        worker.signals.debug_output.connect(
            lambda: print_debug_messages()
        )  # Conectar nueva señal
        if update_callback:
            worker.signals.task_finished.connect(update_callback)
        QThreadPool.globalInstance().start(worker)
    else:
        worker = Worker(button_name, base_name, sg_manager, None, [], False)
        worker.signals.result_ready.connect(handle_results)
        worker.signals.debug_output.connect(lambda: print_debug_messages())
        if update_callback:
            worker.signals.task_finished.connect(update_callback)
        QThreadPool.globalInstance().start(worker)

    return True  # Retornar True indicando que la operación fue iniciada


def print_debug_messages():
    if DEBUG:
        print("\n".join(debug_messages))
        debug_messages.clear()  # Limpiar mensajes después de imprimir


msg_manager = MessageBoxManager()
