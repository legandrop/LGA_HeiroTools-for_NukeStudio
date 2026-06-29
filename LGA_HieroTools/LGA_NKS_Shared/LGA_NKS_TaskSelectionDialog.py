"""
____________________________________________________________________

  LGA_NKS_TaskSelectionDialog v1.41 | Lega

  Detección y selección de task entre los tracks EXR del playhead.

  Pensado como helper compartido para herramientas que actúan sobre una sola task
  por ejecución (Shot_info, Push, ReviewPic). Si en la posición del playhead hay
  clips de más de un track de task (`_comp_`, `_roto_`, `_cleanup_`), pide al
  usuario que elija; si hay solo una, la devuelve automáticamente.

  API pública:
  - get_tasks_at_playhead(seq) -> list[str]
  - track_for_task(task_name) -> str | None
  - prompt_task_selection(task_names, title="Select task") -> str | None
  - resolve_task_at_playhead(seq, title="Select task") -> str | None
  - get_valid_tasks_at_playhead_with_check(seq, extract_task_name, clean_base_name)
      -> (valid_tasks: list[str], mismatches: list[dict])
  - resolve_task_with_mismatch_check(seq, extract_task_name, clean_base_name,
      title="Select task") -> str | None

  Convención de nombres de tracks: docs/Docu_Logica_Nombres_Tracks.md

  v1.41: Los mismatches reportados desde el selector incluyen el TrackItem y
        rango de timeline para que la ventana compartida pueda navegar al clip.
  v1.40: Los botones del selector muestran un atajo de teclado (1-9) en un
        cuadradito a la izquierda. Se puede elegir la task con el mouse o
        presionando el numero correspondiente.
  v1.31: Actualizado para usar colores de tasks alineados con los colores de create v000
  v1.30: Corrección de compatibilidad Nuke 15/16. En PySide2 (Nuke 15) el objeto
        devuelto por `hiero.ui.mainWindow()` es un wrapper SIP incompatible con
        el sistema de tipos de PySide2 cuando se pasa como parent a QDialog,
        causando "QWidget: Must construct a QApplication before a QWidget".
        Usa PYSIDE_VER del adaptador para solo usar parent en PySide6 (Nuke 16).
  v1.20: Diálogos parented a la main window de Hiero y guard sobre
        `QApplication.instance()` antes de crear el QDialog.
  v1.10: Agrega `get_valid_tasks_at_playhead_with_check` y
        `resolve_task_with_mismatch_check`.
  v1.00: Versión inicial.
____________________________________________________________________
"""

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtCore, PYSIDE_VER
from LGA_NKS_Shared.LGA_NKS_GetClip import (
    TASK_EXR_TRACKS,
    TRACK_comp_EXR,
    TRACK_roto_EXR,
    TRACK_cleanup_EXR,
    find_clip_at_playhead_in_track,
)
from LGA_NKS_Shared.LGA_NKS_Flow_Task_Config import get_task_color


_TASK_TO_TRACK = {
    "comp": TRACK_comp_EXR,
    "roto": TRACK_roto_EXR,
    "cleanup": TRACK_cleanup_EXR,
}

_TRACK_TO_TASK = {v: k for k, v in _TASK_TO_TRACK.items()}


def _get_hiero_main_window():
    """Devuelve la main window de Hiero como parent para QDialog, SOLO en PySide6.

    En PySide2 (Nuke 15) el objeto devuelto por hiero.ui.mainWindow() es un
    wrapper SIP cuyo tipo no es compatible con el sistema de tipos de PySide2
    al pasarlo como parent a QDialog/QWidget, lo que provoca el error
    "QWidget: Must construct a QApplication before a QWidget".
    En PySide6 (Nuke 16) la conversión de tipos es más robusta y funciona bien.
    """
    if PYSIDE_VER < 6:
        return None  # Evitar incompatibilidad SIP/PySide2 con wrappers de Hiero
    try:
        import hiero.ui
        mw = hiero.ui.mainWindow()
        if mw is not None:
            return mw
    except Exception:
        pass
    try:
        app = QtWidgets.QApplication.instance()
        if app is not None and hasattr(app, "activeWindow"):
            return app.activeWindow()
    except Exception:
        pass
    return None


def track_for_task(task_name):
    """Devuelve el nombre de track EXR para una task ('comp'/'roto'/'cleanup')."""
    return _TASK_TO_TRACK.get(task_name.lower()) if task_name else None


def get_tasks_at_playhead(seq):
    """Lista las tasks (lowercase) que tienen un clip en el playhead.

    Recorre TASK_EXR_TRACKS en orden y devuelve solo las tasks cuyos tracks
    tienen un clip activo en la posición del playhead.
    """
    tasks = []
    for track_name in TASK_EXR_TRACKS:
        if find_clip_at_playhead_in_track(seq, track_name) is not None:
            task = _TRACK_TO_TASK.get(track_name)
            if task:
                tasks.append(task)
    return tasks


class _TaskSelectionDialog(QtWidgets.QDialog):
    """Diálogo modal de selección de task.

    Permite elegir la task con el mouse (click en el botón) o con el teclado
    presionando el número de atajo que muestra cada botón (1-9).
    """

    def __init__(self, task_names, parent=None):
        super(_TaskSelectionDialog, self).__init__(parent)
        self._task_names = task_names
        self.selected_task = None

    def select_task(self, task):
        self.selected_task = task
        self.accept()

    def keyPressEvent(self, event):
        key = event.key()
        if QtCore.Qt.Key_1 <= key <= QtCore.Qt.Key_9:
            index = key - QtCore.Qt.Key_1
            if index < len(self._task_names):
                self.select_task(self._task_names[index])
                return
        super(_TaskSelectionDialog, self).keyPressEvent(event)


def prompt_task_selection(task_names, title="Select task"):
    """Muestra un diálogo modal con un botón por task y devuelve la elegida.

    Cada botón muestra un número de atajo (1-9) en un cuadradito a la izquierda:
    la task se puede elegir con el mouse o presionando esa tecla.

    Si la lista trae una sola task, la devuelve sin mostrar UI.
    Devuelve None si el usuario cierra el diálogo sin elegir.
    """
    if not task_names:
        return None
    if len(task_names) == 1:
        return task_names[0]

    # Guard: sin QApplication no se puede crear el diálogo (evita crash en startup).
    if QtWidgets.QApplication.instance() is None:
        return None

    parent = _get_hiero_main_window()
    dialog = (
        _TaskSelectionDialog(task_names, parent)
        if parent is not None
        else _TaskSelectionDialog(task_names)
    )
    dialog.setWindowTitle("Select Task")
    dialog.setModal(True)
    dialog.setMinimumWidth(240)
    dialog.setStyleSheet(
        """
        QDialog {
            background-color: #2B2B2B;
            border: 1px solid #555555;
        }
        """
    )

    layout = QtWidgets.QVBoxLayout(dialog)
    layout.setSpacing(8)
    layout.setContentsMargins(16, 14, 16, 14)

    label = QtWidgets.QLabel(title)
    label.setAlignment(QtCore.Qt.AlignCenter)
    label.setStyleSheet("color: #CCCCCC; font-weight: bold; font-size: 12px; padding: 2px 0px;")
    layout.addWidget(label)

    sep = QtWidgets.QFrame()
    sep.setFrameShape(QtWidgets.QFrame.HLine)
    sep.setFrameShadow(QtWidgets.QFrame.Sunken)
    sep.setStyleSheet("color: #444444; margin: 0px;")
    layout.addWidget(sep)

    def make_handler(task):
        def handler():
            dialog.select_task(task)
        return handler

    for index, task in enumerate(task_names):
        task_color = get_task_color(task)
        shortcut = index + 1

        btn = QtWidgets.QPushButton()
        btn.setMinimumHeight(32)
        btn.setStyleSheet(
            """
            QPushButton {
                background-color: #2B2B2B;
                border: 1px solid #444444;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
                border: 1px solid %(color)s;
            }
            QPushButton:pressed {
                background-color: #333333;
            }
            """
            % {"color": task_color}
        )

        # Layout interno: cuadradito de atajo a la izquierda y nombre centrado.
        btn_layout = QtWidgets.QHBoxLayout(btn)
        btn_layout.setContentsMargins(8, 0, 8, 0)
        btn_layout.setSpacing(0)

        # Cuadradito con el numero de atajo de teclado (1-9).
        shortcut_label = QtWidgets.QLabel(str(shortcut))
        shortcut_label.setFixedSize(18, 18)
        shortcut_label.setAlignment(QtCore.Qt.AlignCenter)
        # Transparente al mouse para que el click/hover llegue al boton.
        shortcut_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        shortcut_label.setStyleSheet(
            "background: transparent; border: 1px solid #666666; "
            "border-radius: 2px; color: #999999; font-size: 10px; font-weight: normal;"
        )

        # Nombre de la task, centrado en el ancho total del boton.
        name_label = QtWidgets.QLabel(task.capitalize())
        name_label.setAlignment(QtCore.Qt.AlignCenter)
        name_label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        name_label.setStyleSheet(
            "background: transparent; color: %s; font-weight: bold; font-size: 12px;"
            % task_color
        )

        # Spacer del mismo ancho que el cuadradito para centrar el nombre.
        spacer = QtWidgets.QWidget()
        spacer.setFixedSize(18, 18)
        spacer.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)

        btn_layout.addWidget(shortcut_label)
        btn_layout.addWidget(name_label, 1)
        btn_layout.addWidget(spacer)

        btn.clicked.connect(make_handler(task))
        layout.addWidget(btn)

    dialog.exec_()
    return dialog.selected_task


def resolve_task_at_playhead(seq, title="Select task"):
    """Resuelve la task a usar en función del playhead.

    - 0 tasks bajo el playhead -> None
    - 1 task -> esa task
    - >1 tasks -> abre prompt y devuelve la elegida (o None si se canceló)
    """
    tasks = get_tasks_at_playhead(seq)
    if not tasks:
        return None
    if len(tasks) == 1:
        return tasks[0]
    return prompt_task_selection(tasks, title=title)


def get_valid_tasks_at_playhead_with_check(seq, extract_task_name, clean_base_name):
    """Recorre los tracks de task con clip en el playhead y separa los válidos de los incorrectos.

    Para cada track con clip, verifica que la task del filename coincida con la del track.
    Los clips donde hay discrepancia se reportan como mismatches y NO se ofrecen como opción.

    Args:
        seq: Sequence activa de Hiero.
        extract_task_name: función que extrae la task del base_name (de NamingUtils).
        clean_base_name: función que limpia el filename (de NamingUtils).

    Returns:
        Tupla (valid_tasks: list[str], mismatches: list[dict]).
        Cada dict de mismatch tiene claves 'clip', 'task' (del filename) y 'track'.
    """
    import os

    valid_tasks = []
    mismatches = []

    for track_name in TASK_EXR_TRACKS:
        clip = find_clip_at_playhead_in_track(seq, track_name)
        if clip is None:
            continue
        task_from_track = _TRACK_TO_TASK.get(track_name)
        if not task_from_track:
            continue

        try:
            fileinfos = clip.source().mediaSource().fileinfos()
            if not fileinfos:
                valid_tasks.append(task_from_track)
                continue
            filename = os.path.basename(fileinfos[0].filename())
            base = clean_base_name(filename)
            task_from_name = extract_task_name(base)
            if task_from_name and task_from_name.lower() != task_from_track:
                mismatches.append({
                    "clip": clip.name(),
                    "clip_item": clip,
                    "sequence": seq,
                    "task": task_from_name.lower(),
                    "track": track_name,
                    "timeline_in": clip.timelineIn(),
                    "timeline_out": clip.timelineOut(),
                })
                continue
        except Exception:
            pass

        valid_tasks.append(task_from_track)

    return valid_tasks, mismatches


def resolve_task_with_mismatch_check(seq, extract_task_name, clean_base_name, title="Select task"):
    """Resuelve la task mostrando advertencia si hay clips con filename/track inconsistentes.

    Flujo:
    1. Detecta tasks válidas e inconsistentes en el playhead.
    2. Si hay mismatches, muestra la advertencia (sin bloquear).
    3. Ofrece solo las tasks válidas en el selector.
    4. Devuelve la task elegida o None si no hay tasks válidas o el usuario cancela.

    Args:
        seq: Sequence activa de Hiero.
        extract_task_name: función del módulo NamingUtils.
        clean_base_name: función del módulo NamingUtils.
        title: título del diálogo de selección.

    Returns:
        str con el nombre de la task ('comp'/'roto'/'cleanup') o None.
    """
    from LGA_NKS_Shared.LGA_NKS_TaskMismatchDialog import show_task_mismatch_warning

    valid_tasks, mismatches = get_valid_tasks_at_playhead_with_check(
        seq, extract_task_name, clean_base_name
    )

    if mismatches:
        parent_win = _get_hiero_main_window()
        show_task_mismatch_warning(mismatches, parent=parent_win)

    if not valid_tasks:
        return None

    return prompt_task_selection(valid_tasks, title=title)
