"""
____________________________________________________________________

  LGA_NKS_Flow_UpdateThumb v1.04 | Lega

  Reemplaza el thumbnail de un shot existente en Flow (ShotGrid) con un snapshot
  del viewer actual de Hiero. Pensado para el Shift+Click del boton "Thumbnail"
  del Coordination Panel.

  v1.04: La ventana lleva la fuente del pack (apply_ui_font); sin
         eso salia con la fuente del host.
  v1.03: ThumbReplaceDialog migra al modulo de estilo LGA_UI_Style_HieroTools:
         Style.WINDOW, Replace en BTN_PRIMARY, Cancel en BTN_SECONDARY y
         tokens en el HTML y en los pozos de imagen.
  v1.02: Los carteles de aviso pasan al helper LGA_NKS_MessageBox con el
         estilo del pack.
  v1.01: La ventana se auto-cierra tras un reemplazo exitoso, con cuenta regresiva
         en el boton Close. Configurable con AUTO_CLOSE_SECONDS (arriba); 0 lo
         desactiva.
  v1.00: Version inicial. Captura el viewer, compara contra el thumbnail actual
         del shot en Flow y lo reemplaza (upload en hilo separado).

  Flujo:
  1. Toma el clip bajo el playhead (fallback a la seleccion).
  2. Captura un snapshot del viewer (zoom to fill, BurnIn deshabilitado, crop al
     aspecto de la secuencia) a un archivo temporal.
  3. project_name y shot_code se extraen del path del clip (segmento VFX-NOMBRE),
     con fallback al nombre del archivo.
  4. Abre una ventana (estetica Create Shot) que muestra el thumbnail actual del
     shot en Flow vs el nuevo snapshot, con botones Replace / Cancel.
  5. Al confirmar, sube el nuevo thumbnail a Flow en un hilo separado.

  Si el shot no existe en Flow, muestra un error y no hace nada.
  El archivo es temporal: se sube a Flow y se borra (no deja copia en disco).
____________________________________________________________________
"""

import os
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import hiero.core
import hiero.ui

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt
from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import Style, Color, apply_ui_font

QApplication = QtWidgets.QApplication
QDialog = QtWidgets.QDialog
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton
QFrame = QtWidgets.QFrame
QSizePolicy = QtWidgets.QSizePolicy
QFont = QtGui.QFont
QPixmap = QtGui.QPixmap
QObject = QtCore.QObject
QRunnable = QtCore.QRunnable
QThreadPool = QtCore.QThreadPool
QTimer = QtCore.QTimer
Signal = QtCore.Signal
Slot = QtCore.Slot

# Segundos para el auto-cierre de la ventana tras un reemplazo exitoso.
# Poner 0 (o menos) para desactivar el auto-cierre.
AUTO_CLOSE_SECONDS = 4

# shotgun_api3 + utilidades compartidas
shared_dir = Path(__file__).parent.parent / "LGA_NKS_Shared"
sys.path.insert(0, str(shared_dir))
# El directorio propio del script: necesario porque el panel lo carga via
# importlib (spec_from_file_location), que no agrega su carpeta a sys.path.
panel_dir = Path(__file__).parent
sys.path.insert(0, str(panel_dir))
import shotgun_api3  # noqa: E402
from SecureConfig_Reader import get_flow_credentials  # noqa: E402
from LGA_NKS_Flow_NamingUtils import (  # noqa: E402
    extract_shot_code,
    extract_project_name,
    extract_project_name_from_path,
    clean_base_name,
)
from LGA_NKS_Shared.LGA_NKS_GetClip import get_clip_to_process  # noqa: E402

# Reutilizar los helpers de captura del snapshot del viewer (mismo comportamiento
# que el click normal del boton Thumbnail).
from LGA_NKS_Flow_Thumbs import (  # noqa: E402
    disable_burnin_track_simple,
    restore_burnin_track_simple,
    zoom_to_fill_simple,
    crop_to_aspect_ratio,
)


DEBUG = False


def debug_print(*message):
    if DEBUG:
        print("[UpdateThumb]", *message, file=sys.stderr)


# ----------------------------------------------------------------------------
# Captura del snapshot del viewer
# ----------------------------------------------------------------------------
def capture_viewer_snapshot_to_temp():
    """Captura el viewer actual a un JPG temporal (zoom to fill + crop al aspecto
    de la secuencia, con el track BurnIn deshabilitado temporalmente).

    Returns:
        str | None: ruta del JPG temporal, o None si fallo la captura.
    """
    track_found, was_enabled = disable_burnin_track_simple()
    try:
        if not zoom_to_fill_simple():
            debug_print("No se pudo aplicar zoom to fill")
            # Continuar igual: zoom to fill es deseable pero no critico
        time.sleep(0.5)

        viewer = hiero.ui.currentViewer()
        if not viewer:
            debug_print("No hay viewer activo")
            return None

        qimage = viewer.image()
        if qimage is None or qimage.isNull():
            debug_print("viewer.image() devolvio None o imagen nula")
            return None

        # Crop al aspecto de la secuencia
        sequence = hiero.ui.activeSequence()
        if sequence is None:
            target_aspect = 16 / 9
        else:
            fmt = sequence.format()
            target_aspect = fmt.width() / fmt.height()
        qimage_cropped = crop_to_aspect_ratio(qimage, target_aspect)

        # Guardar a archivo temporal
        fd, temp_path = tempfile.mkstemp(prefix="LGA_FlowThumb_", suffix=".jpg")
        os.close(fd)
        ok = qimage_cropped.save(temp_path, "JPEG")
        if not ok or not os.path.exists(temp_path):
            debug_print("No se pudo guardar el JPG temporal")
            return None
        debug_print(f"Snapshot temporal guardado: {temp_path}")
        return temp_path

    except Exception as e:
        debug_print(f"Error capturando snapshot: {e}")
        return None
    finally:
        restore_burnin_track_simple(track_found, was_enabled)


def get_playhead_clip_info():
    """Obtiene info del clip bajo el playhead (fallback a seleccion).

    Returns:
        dict | None: {file_path, project_name, shot_code} o None.
    """
    sequence = hiero.ui.activeSequence()
    if not sequence:
        debug_print("No hay secuencia activa")
        return None

    clip = get_clip_to_process(track_name=None, prioritize_multiple_selection=False)
    if not clip:
        debug_print("No hay clip en playhead ni seleccionado")
        return None

    try:
        file_path = clip.source().mediaSource().fileinfos()[0].filename()
    except Exception as e:
        debug_print(f"No se pudo obtener file_path del clip: {e}")
        return None

    base_name = clean_base_name(os.path.basename(file_path))
    project_name = extract_project_name_from_path(file_path)
    if not project_name:
        project_name = extract_project_name(base_name)
    shot_code = extract_shot_code(base_name)

    return {
        "file_path": file_path,
        "project_name": project_name,
        "shot_code": shot_code,
    }


# ----------------------------------------------------------------------------
# Flow / ShotGrid
# ----------------------------------------------------------------------------
class FlowThumbManager:
    """Operaciones de ShotGrid necesarias para reemplazar el thumbnail de un shot."""

    def __init__(self, url, login, password):
        try:
            self.sg = shotgun_api3.Shotgun(url, login=login, password=password)
        except Exception as e:
            debug_print(f"Error inicializando conexion a ShotGrid: {e}")
            self.sg = None

    def get_project_id(self, project_name):
        if not self.sg or not project_name:
            return None
        projects = self.sg.find("Project", [["name", "is", project_name]], ["id"])
        return projects[0]["id"] if projects else None

    def find_shot(self, project_name, shot_code):
        """Devuelve el shot {id, code, image} o None si no existe."""
        if not self.sg:
            return None
        project_id = self.get_project_id(project_name)
        if not project_id:
            debug_print(f"Proyecto no encontrado en Flow: {project_name}")
            return None
        filters = [
            ["project", "is", {"type": "Project", "id": project_id}],
            ["code", "is", shot_code],
        ]
        shots = self.sg.find("Shot", filters, ["id", "code", "image"])
        return shots[0] if shots else None

    def upload_thumbnail(self, shot_id, thumbnail_path):
        if not self.sg or not shot_id or not thumbnail_path:
            return False
        if not os.path.exists(thumbnail_path):
            debug_print(f"No existe el archivo a subir: {thumbnail_path}")
            return False
        try:
            self.sg.upload_thumbnail("Shot", shot_id, thumbnail_path)
            return True
        except Exception as e:
            debug_print(f"Error subiendo thumbnail: {e}")
            return False


def download_thumbnail(image_url):
    """Descarga la URL del thumbnail actual a un JPG temporal.

    Returns:
        str | None: ruta temporal o None si no hay URL o falla la descarga.
    """
    if not image_url:
        return None
    try:
        fd, temp_path = tempfile.mkstemp(prefix="LGA_FlowThumbCur_", suffix=".jpg")
        os.close(fd)
        with urllib.request.urlopen(image_url, timeout=15) as resp:
            data = resp.read()
        with open(temp_path, "wb") as f:
            f.write(data)
        if os.path.getsize(temp_path) > 0:
            return temp_path
        return None
    except Exception as e:
        debug_print(f"No se pudo descargar el thumbnail actual: {e}")
        return None


def _safe_remove(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception as e:
            debug_print(f"No se pudo borrar temp {path}: {e}")


# ----------------------------------------------------------------------------
# Workers (hilos)
# ----------------------------------------------------------------------------
class LoadSignals(QObject):
    loaded = Signal(object)  # dict: {shot_id, code, current_thumb_path}
    failed = Signal(str)
    debug_output = Signal()


class LoadShotWorker(QRunnable):
    """Conecta a Flow, busca el shot y baja su thumbnail actual (si tiene)."""

    def __init__(self, project_name, shot_code):
        super(LoadShotWorker, self).__init__()
        self.project_name = project_name
        self.shot_code = shot_code
        self.signals = LoadSignals()

    @Slot()
    def run(self):
        try:
            url, login, password = get_flow_credentials()
            if not url or not login or not password:
                self.signals.failed.emit(
                    "No se pudieron obtener las credenciales de Flow."
                )
                return
            manager = FlowThumbManager(url, login, password)
            if not manager.sg:
                self.signals.failed.emit("No se pudo conectar a Flow.")
                return
            shot = manager.find_shot(self.project_name, self.shot_code)
            if not shot:
                self.signals.failed.emit(
                    f"El shot '{self.shot_code}' no existe en el proyecto "
                    f"'{self.project_name}' en Flow."
                )
                return
            current_thumb_path = download_thumbnail(shot.get("image"))
            self.signals.loaded.emit(
                {
                    "shot_id": shot["id"],
                    "code": shot.get("code", self.shot_code),
                    "current_thumb_path": current_thumb_path,
                }
            )
        except Exception as e:
            self.signals.failed.emit(f"Error buscando el shot en Flow: {e}")


class UploadSignals(QObject):
    finished = Signal(bool, str)
    debug_output = Signal()


class UploadThumbWorker(QRunnable):
    """Sube el nuevo thumbnail al shot en Flow."""

    def __init__(self, shot_id, thumbnail_path):
        super(UploadThumbWorker, self).__init__()
        self.shot_id = shot_id
        self.thumbnail_path = thumbnail_path
        self.signals = UploadSignals()

    @Slot()
    def run(self):
        try:
            url, login, password = get_flow_credentials()
            if not url or not login or not password:
                self.signals.finished.emit(
                    False, "No se pudieron obtener las credenciales de Flow."
                )
                return
            manager = FlowThumbManager(url, login, password)
            if not manager.sg:
                self.signals.finished.emit(False, "No se pudo conectar a Flow.")
                return
            ok = manager.upload_thumbnail(self.shot_id, self.thumbnail_path)
            if ok:
                self.signals.finished.emit(True, "Thumbnail actualizado en Flow.")
            else:
                self.signals.finished.emit(
                    False, "No se pudo subir el thumbnail a Flow."
                )
        except Exception as e:
            self.signals.finished.emit(False, f"Error subiendo el thumbnail: {e}")


# ----------------------------------------------------------------------------
# Ventana de comparacion / confirmacion
# ----------------------------------------------------------------------------
THUMB_W = 280


class ThumbReplaceDialog(QDialog):
    def __init__(self, project_name, shot_code, new_thumb_path, parent=None):
        super(ThumbReplaceDialog, self).__init__(parent)
        self.project_name = project_name
        self.shot_code = shot_code
        self.new_thumb_path = new_thumb_path
        self.replace_callback = None
        self._uploading = False
        self._countdown_timer = None
        self._countdown_remaining = 0

        self.setWindowTitle("Flow | Update Thumbnail")
        self.setModal(False)
        self.setWindowModality(Qt.NonModal)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self.setMinimumWidth(640)

        layout = QVBoxLayout()
        self.setLayout(layout)

        # Titulo
        title_label = QLabel("Reemplazar thumbnail del shot en Flow")
        title_font = QFont()
        title_font.setPointSize(12)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setStyleSheet(f"color: {Color.TEXT_STRONG}; padding: 5px;")
        layout.addWidget(title_label)

        # Subtitulo: proyecto / shot
        subtitle = QLabel(
            f"<span style='color: {Color.INFO};'>{project_name}</span> / "
            f"<span style='color: {Color.ENTITY};'>{shot_code}</span>"
        )
        subtitle.setTextFormat(Qt.RichText)
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("padding: 2px 5px 8px 5px;")
        layout.addWidget(subtitle)

        # Fila de imagenes: actual  ->  nuevo
        images_layout = QHBoxLayout()

        images_layout.addStretch()
        images_layout.addLayout(self._build_image_column("Actual en Flow", is_current=True))

        arrow = QLabel("→")  # flecha
        arrow_font = QFont()
        arrow_font.setPointSize(22)
        arrow_font.setBold(True)
        arrow.setFont(arrow_font)
        arrow.setStyleSheet(f"color: {Color.TEXT}; padding: 0px 12px;")
        arrow.setAlignment(Qt.AlignCenter)
        images_layout.addWidget(arrow)

        images_layout.addLayout(self._build_image_column("Nuevo (snapshot)", is_current=False))
        images_layout.addStretch()

        layout.addLayout(images_layout)

        # Cargar la imagen nueva inmediatamente
        self._set_pixmap(self.new_image_label, self.new_thumb_path)

        # Etiqueta de estado/resultado
        self.status_label = QLabel("Buscando el shot en Flow...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.RichText)
        self.status_label.setStyleSheet(f"color: {Color.TEXT}; padding: 8px;")
        layout.addWidget(self.status_label)

        # Botones alineados a la derecha, con el de accion ultimo y en violeta
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.close)
        self.cancel_button.setStyleSheet(Style.BTN_SECONDARY)
        button_layout.addWidget(self.cancel_button)
        button_layout.addSpacing(10)

        self.replace_button = QPushButton("Replace")
        self.replace_button.setEnabled(False)
        self.replace_button.clicked.connect(self._on_replace_clicked)
        self.replace_button.setStyleSheet(Style.BTN_PRIMARY)
        button_layout.addWidget(self.replace_button)
        layout.addLayout(button_layout)

        # Estilo general: la hoja de ventana del pack
        self.setStyleSheet(Style.WINDOW)
        # Fuente del pack al final del armado: recorre los hijos ya creados.
        apply_ui_font(self)

    def _build_image_column(self, header_text, is_current):
        col = QVBoxLayout()
        header = QLabel(header_text)
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet(
            f"color: {Color.TEXT_STRONG}; font-weight: bold; padding: 2px;"
        )
        col.addWidget(header)

        image_label = QLabel("Cargando..." if is_current else "")
        image_label.setAlignment(Qt.AlignCenter)
        image_label.setFixedWidth(THUMB_W)
        image_label.setMinimumHeight(int(THUMB_W * 9 / 16))
        image_label.setStyleSheet(
            "background-color: %s; border: 1px solid %s; color: %s;"
            % (Color.SURFACE_SUNKEN, Color.BORDER_STRONG, Color.TEXT_DIM)
        )
        col.addWidget(image_label)

        if is_current:
            self.current_image_label = image_label
        else:
            self.new_image_label = image_label
        return col

    def _set_pixmap(self, label, path):
        if path and os.path.exists(path):
            pix = QPixmap(path)
            if not pix.isNull():
                label.setPixmap(
                    pix.scaledToWidth(THUMB_W, Qt.SmoothTransformation)
                )
                label.setText("")
                return True
        return False

    # --- API publica usada por el orquestador ---
    def set_current_thumb(self, path):
        if not self._set_pixmap(self.current_image_label, path):
            self.current_image_label.setText("Sin thumbnail")

    def set_replace_callback(self, callback):
        self.replace_callback = callback

    def show_ready(self):
        self.replace_button.setEnabled(True)
        self.status_label.setText(
            f"<span style='color: {Color.TEXT};'>Se reemplazara el thumbnail actual por el nuevo snapshot.</span>"
        )

    def show_step(self, message):
        self.status_label.setText(f"<span style='color: {Color.TEXT};'>{message}</span>")

    def show_success(self, message):
        self._uploading = False
        self.status_label.setText(f"<span style='color: {Color.OK_TEXT};'>{message}</span>")
        self.replace_button.setEnabled(False)
        self.cancel_button.setText("Close")
        self._start_auto_close()

    def _start_auto_close(self):
        """Inicia la cuenta regresiva que auto-cierra la ventana."""
        if AUTO_CLOSE_SECONDS <= 0:
            return  # Auto-cierre desactivado
        self._countdown_remaining = AUTO_CLOSE_SECONDS
        self.cancel_button.setText(f"Close ({self._countdown_remaining})")
        self._countdown_timer = QTimer(self)
        self._countdown_timer.setInterval(1000)
        self._countdown_timer.timeout.connect(self._on_countdown_tick)
        self._countdown_timer.start()

    def _on_countdown_tick(self):
        self._countdown_remaining -= 1
        if self._countdown_remaining <= 0:
            if self._countdown_timer:
                self._countdown_timer.stop()
            self.close()
        else:
            self.cancel_button.setText(f"Close ({self._countdown_remaining})")

    def show_error(self, message):
        self._uploading = False
        self.status_label.setText(f"<span style='color: {Color.ERROR_TEXT};'>{message}</span>")
        self.replace_button.setEnabled(False)
        self.cancel_button.setText("Close")

    def set_uploading(self):
        self._uploading = True
        self.replace_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.show_step("Subiendo thumbnail a Flow...")

    def _on_replace_clicked(self):
        if self.replace_callback:
            self.replace_callback()

    def closeEvent(self, event):
        # No permitir cerrar mientras se esta subiendo a Flow
        if self._uploading:
            event.ignore()
            return
        # Detener la cuenta regresiva si el usuario cierra manualmente antes de tiempo
        if self._countdown_timer:
            self._countdown_timer.stop()
            self._countdown_timer = None
        event.accept()


# ----------------------------------------------------------------------------
# Orquestacion
# ----------------------------------------------------------------------------
# Referencias globales para evitar que el GC cierre la ventana / cancele el worker
_dialog = None
_load_worker = None
_upload_worker = None
_temp_new_thumb = None
_temp_current_thumb = None
_shot_id = None


def _warn(message):
    """Muestra un aviso simple cuando no se puede ni abrir la ventana."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    show_warning(None, "Flow | Update Thumbnail", message)


def _cleanup_temps():
    global _temp_new_thumb, _temp_current_thumb
    _safe_remove(_temp_new_thumb)
    _safe_remove(_temp_current_thumb)
    _temp_new_thumb = None
    _temp_current_thumb = None


def _on_dialog_finished(_result):
    """Al cerrar la ventana: limpiar temporales e invalidar refs para que los
    callbacks tardios de los workers no actuen sobre una ventana cerrada."""
    global _dialog, _shot_id
    _cleanup_temps()
    _dialog = None
    _shot_id = None


def update_thumbnail_in_flow():
    """Entry point del Shift+Click: captura el viewer y abre la ventana de
    reemplazo del thumbnail del shot en Flow."""
    global _dialog, _load_worker, _upload_worker
    global _temp_new_thumb, _temp_current_thumb, _shot_id

    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    # 1) Info del clip (playhead-first)
    info = get_playhead_clip_info()
    if not info:
        _warn("No se encontro un clip bajo el playhead ni seleccionado.")
        return
    if not info["project_name"] or not info["shot_code"]:
        _warn("No se pudo extraer el proyecto o el shot del clip seleccionado.")
        return

    # 2) Capturar snapshot a temp
    _temp_new_thumb = capture_viewer_snapshot_to_temp()
    if not _temp_new_thumb:
        _warn("No se pudo capturar el snapshot del viewer.")
        return

    # 3) Abrir ventana de comparacion
    _shot_id = None
    _temp_current_thumb = None
    _dialog = ThumbReplaceDialog(
        info["project_name"], info["shot_code"], _temp_new_thumb
    )
    _dialog.finished.connect(_on_dialog_finished)
    _dialog.show()

    # 4) Buscar shot + bajar thumbnail actual en hilo
    _load_worker = LoadShotWorker(info["project_name"], info["shot_code"])
    _load_worker.signals.loaded.connect(_on_shot_loaded)
    _load_worker.signals.failed.connect(_on_load_failed)
    QThreadPool.globalInstance().start(_load_worker)


def _on_shot_loaded(data):
    global _shot_id, _temp_current_thumb
    if not _dialog:
        return
    _shot_id = data["shot_id"]
    _temp_current_thumb = data.get("current_thumb_path")
    _dialog.set_current_thumb(_temp_current_thumb)
    _dialog.set_replace_callback(_on_replace_confirmed)
    _dialog.show_ready()


def _on_load_failed(message):
    if _dialog:
        _dialog.set_current_thumb(None)
        _dialog.show_error(message)


def _on_replace_confirmed():
    global _upload_worker
    if not _dialog or not _shot_id or not _temp_new_thumb:
        return
    _dialog.set_uploading()
    _upload_worker = UploadThumbWorker(_shot_id, _temp_new_thumb)
    _upload_worker.signals.finished.connect(_on_upload_finished)
    QThreadPool.globalInstance().start(_upload_worker)


def _on_upload_finished(success, message):
    if not _dialog:
        return
    _dialog.cancel_button.setEnabled(True)
    if success:
        _dialog.show_success(message)
    else:
        _dialog.show_error(message)


def main():
    """Compatibilidad: el panel llama main() para el Shift+Click."""
    update_thumbnail_in_flow()


if __name__ == "__main__":
    main()
