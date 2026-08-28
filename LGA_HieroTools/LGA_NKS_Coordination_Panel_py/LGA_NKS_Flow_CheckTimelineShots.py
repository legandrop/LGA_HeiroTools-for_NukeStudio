"""
____________________________________________________________________

  LGA_NKS_Flow_CheckTimelineShots v1.02 | Lega

  Chequea si los shots del track comp del timeline existen en Flow.
  Muestra una ventana con la lista de shots existentes y los faltantes.

  v1.02: Los carteles de aviso pasan al helper LGA_NKS_MessageBox con el
         estilo del pack.
  v1.01: Project name extraído desde el segmento VFX-NOMBRE del path del archivo
         (con fallback al primer bloque del filename si el path no contiene VFX-).
         Corrige proyectos como PROJALT cuyos shots tienen prefijo PROJA en el filename.
____________________________________________________________________
"""

import hiero.core
import hiero.ui
import os
import sys
from pathlib import Path
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt
from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning

QApplication = QtWidgets.QApplication
QMessageBox = QtWidgets.QMessageBox
QDialog = QtWidgets.QDialog
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QLabel = QtWidgets.QLabel
QListWidget = QtWidgets.QListWidget
QPushButton = QtWidgets.QPushButton
QSizePolicy = QtWidgets.QSizePolicy
QFrame = QtWidgets.QFrame
QFont = QtGui.QFont
QRunnable = QtCore.QRunnable
QThreadPool = QtCore.QThreadPool
Signal = QtCore.Signal
Slot = QtCore.Slot
QObject = QtCore.QObject

# Agregar el directorio actual al sys.path para importar módulos locales
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

# Reutilizar utilidades desde Create Shot
from LGA_NKS_Flow_CreateShot import (
    FlowStatusWindow,
    ShotGridManager,
    debug_print,
    get_flow_credentials_secure,
    print_debug_messages,
)

# Importar utilidades de naming
sys.path.append(str(Path(__file__).parent.parent / "LGA_NKS_Shared"))
from LGA_NKS_Flow_NamingUtils import (
    extract_project_name,
    extract_project_name_from_path,
    extract_shot_code,
    clean_base_name,
)

# Importar variable de track centralizada
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    from LGA_NKS_Shared.LGA_NKS_GetClip import TRACK_comp_EXR
else:
    TRACK_comp_EXR = "_comp_"

# Mantener referencia a la ventana de resultados para evitar GC
_results_window = None


class ShotCheckSignals(QObject):
    finished = Signal(list, list, list)  # existing, missing, unresolved
    error = Signal(str)
    debug_output = Signal()


class ShotCheckWorker(QRunnable):
    def __init__(self, shots_info):
        super(ShotCheckWorker, self).__init__()
        self.shots_info = shots_info
        self.signals = ShotCheckSignals()

    @Slot()
    def run(self):
        try:
            sg_url, sg_login, sg_password = get_flow_credentials_secure()
            if not all([sg_url, sg_login, sg_password]):
                self.signals.debug_output.emit()
                self.signals.error.emit(
                    "No se pudieron obtener las credenciales de Flow desde SecureConfig."
                )
                return

            sg_manager = ShotGridManager(sg_url, sg_login, sg_password)
            if not sg_manager.sg:
                self.signals.debug_output.emit()
                self.signals.error.emit("No se pudo inicializar la conexión a ShotGrid.")
                return

            existing = []
            missing = []
            unresolved = []

            for shot_info in self.shots_info:
                project_name = shot_info.get("project_name")
                shot_code = shot_info.get("shot_code")

                if not project_name or not shot_code:
                    unresolved.append(shot_info)
                    continue

                exists, _ = sg_manager.shot_exists(project_name, shot_code)
                if exists:
                    existing.append(shot_info)
                else:
                    missing.append(shot_info)

            self.signals.debug_output.emit()
            self.signals.finished.emit(existing, missing, unresolved)
        except Exception as e:
            debug_print(f"Error en ShotCheckWorker: {e}")
            self.signals.debug_output.emit()
            self.signals.error.emit(str(e))


class ShotCheckResultsDialog(QDialog):
    def __init__(self, existing, missing, unresolved, parent=None):
        super(ShotCheckResultsDialog, self).__init__(parent)
        self.setWindowTitle("Flow | Check Shots")
        self.setModal(False)
        self.setMinimumWidth(640)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        layout = QVBoxLayout()
        self.setLayout(layout)

        header = QLabel("Resultados de chequeo de shots en Flow")
        header_font = QFont()
        header_font.setPointSize(11)
        header.setFont(header_font)
        layout.addWidget(header)

        lists_layout = QHBoxLayout()
        layout.addLayout(lists_layout)

        existing_layout = QVBoxLayout()
        missing_layout = QVBoxLayout()

        existing_label = QLabel(f"Existe en Flow ({len(existing)})")
        missing_label = QLabel(f"No existe en Flow ({len(missing)})")
        existing_layout.addWidget(existing_label)
        missing_layout.addWidget(missing_label)

        existing_list = QListWidget()
        missing_list = QListWidget()

        for item in existing:
            existing_list.addItem(item["shot_code"])
        for item in missing:
            missing_list.addItem(item["shot_code"])

        existing_layout.addWidget(existing_list)
        missing_layout.addWidget(missing_list)

        lists_layout.addLayout(existing_layout)
        lists_layout.addLayout(missing_layout)

        if unresolved:
            unresolved_label = QLabel(
                f"Sin info suficiente ({len(unresolved)}): "
                + ", ".join([item.get("clip_name", "N/A") for item in unresolved])
            )
            unresolved_label.setWordWrap(True)
            unresolved_label.setStyleSheet("color: #C05050;")
            layout.addWidget(unresolved_label)

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.close)
        layout.addWidget(close_button)


def _collect_shots_from_track(seq, track_name):
    """Obtiene los shots únicos desde un track específico del timeline."""
    if not seq:
        return []

    target_track = None
    for track in seq.videoTracks():
        if track.name().upper() == track_name.upper():
            target_track = track
            break

    if not target_track:
        return []

    shots_info = []
    seen = set()

    for clip in target_track:
        if isinstance(clip, hiero.core.EffectTrackItem):
            continue

        clip_name = clip.name()
        file_path = ""
        try:
            if clip.source() and clip.source().mediaSource():
                fileinfos = clip.source().mediaSource().fileinfos()
                if fileinfos:
                    file_path = fileinfos[0].filename()
        except Exception:
            file_path = ""

        base_source = os.path.basename(file_path) if file_path else clip_name
        base_name = clean_base_name(base_source)
        project_name = extract_project_name_from_path(file_path)
        if project_name:
            debug_print(f"Project name (from path): {project_name}")
        else:
            project_name = extract_project_name(base_name)
            debug_print(f"Project name (from filename fallback): {project_name}")
        shot_code = extract_shot_code(base_name)

        if shot_code and shot_code not in seen:
            seen.add(shot_code)
            shots_info.append(
                {
                    "shot_code": shot_code,
                    "project_name": project_name,
                    "clip_name": clip_name,
                    "file_path": file_path,
                }
            )
        elif not shot_code:
            shots_info.append(
                {
                    "shot_code": "",
                    "project_name": project_name,
                    "clip_name": clip_name,
                    "file_path": file_path,
                }
            )

    return shots_info


def _show_error_message(title, message, status_window=None):
    if status_window:
        status_window.show_error(message)
    else:
        show_warning(None, title, message)


def check_timeline_shots():
    """Función principal del script de chequeo de shots."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    seq = hiero.ui.activeSequence()
    if not seq:
        show_warning(None, "Flow | Check Shots", "No hay secuencia activa.")
        return

    shots_info = _collect_shots_from_track(seq, TRACK_comp_EXR)
    if not shots_info:
        show_warning(
            None,
            "Flow | Check Shots",
            f"No se encontraron clips en el track '{TRACK_comp_EXR}'.",
        )
        return

    status_window = FlowStatusWindow("check shots")
    status_window.show()
    status_window.show_step_message("Comprobando existencia de los shots en Flow...")

    worker = ShotCheckWorker(shots_info)
    worker.signals.finished.connect(
        lambda existing, missing, unresolved: _handle_results(
            status_window, existing, missing, unresolved
        )
    )
    worker.signals.error.connect(
        lambda message: _show_error_message("Flow | Check Shots", message, status_window)
    )
    worker.signals.debug_output.connect(lambda: print_debug_messages())

    QThreadPool.globalInstance().start(worker)


def _handle_results(status_window, existing, missing, unresolved):
    if status_window:
        status_window.close()

    global _results_window
    _results_window = ShotCheckResultsDialog(existing, missing, unresolved)
    _results_window.show()


def main():
    check_timeline_shots()
