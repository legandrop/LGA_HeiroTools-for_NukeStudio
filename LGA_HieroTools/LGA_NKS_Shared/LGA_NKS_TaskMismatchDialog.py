"""
____________________________________________________________________

  LGA_NKS_TaskMismatchDialog v1.02 | Lega

  Ventana de advertencia compartida para cuando la task detectada en
  el filename de un clip NO coincide con el nombre del track donde
  esta ubicado. La funcion principal es show_task_mismatch_warning().
  No bloquea ni modifica el procesamiento: solo informa al usuario.

  Usado por runtime activo:
  - LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py
  - LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py

  Convencion de nombres de tracks: docs/Docu_Logica_Nombres_Tracks.md

  v1.02: Emite senial closed para encadenar la ventana siguiente al cierre,
         aclara que se puede clickear una fila para navegar al clip y usa
         seleccion gris/blanca en la tabla.
  v1.01: La ventana pasa a ser no modal, suma checkbox persistente "Keep this
         window on top" abajo a la izquierda, y permite navegar al clip al hacer
         click en una fila usando el In/Out del propio clip.
  v1.00: Version inicial
____________________________________________________________________
"""

import configparser
import ctypes
import ctypes.wintypes
import os
import sys
from pathlib import Path

import hiero.ui
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtCore, Qt

_CONFIG_DIR_NAME = "LGA"
_CONFIG_SUBDIR_NAME = "HieroTools"
_CONFIG_FILE_NAME = "TaskMismatchDialog.ini"
_CONFIG_SECTION = "Window"
_OPEN_MISMATCH_WINDOWS = []


def _settings_root():
    if sys.platform.startswith("win"):
        value = os.getenv("APPDATA")
        if value:
            return value
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support")
    return os.path.expanduser("~/.config")


def _settings_path():
    return Path(_settings_root()) / _CONFIG_DIR_NAME / _CONFIG_SUBDIR_NAME / _CONFIG_FILE_NAME


def _load_keep_on_top():
    try:
        cfg = configparser.ConfigParser()
        path = _settings_path()
        if path.exists():
            cfg.read(str(path), encoding="utf-8")
        return cfg.getboolean(_CONFIG_SECTION, "keep_on_top", fallback=True)
    except Exception:
        return True


def _save_keep_on_top(value):
    try:
        path = _settings_path()
        cfg = configparser.ConfigParser()
        if path.exists():
            cfg.read(str(path), encoding="utf-8")
        if not cfg.has_section(_CONFIG_SECTION):
            cfg.add_section(_CONFIG_SECTION)
        cfg.set(_CONFIG_SECTION, "keep_on_top", "true" if value else "false")
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(path), "w", encoding="utf-8") as handle:
            cfg.write(handle)
    except Exception:
        pass


def collect_task_mismatches(
    selected_clips,
    seq,
    task_exr_tracks,
    extract_task_name,
    clean_base_name,
    debug_log=None,
):
    """
    Recorre los clips y devuelve los que tienen inconsistencia entre la task del
    filename y el nombre del track donde estan ubicados.
    """
    import os
    import hiero.core

    def _dlog(msg):
        if debug_log:
            try:
                debug_log(msg)
            except Exception:
                pass

    _dlog(f"[MismatchFn] version=v1.2 nonmodal-nav selected={len(selected_clips)}")

    def _key(item):
        try:
            guid = item.guid()
            if guid:
                return ("guid", guid)
        except Exception:
            pass
        return ("id", id(item))

    clip_track_map = {}
    for track in seq.videoTracks():
        for item in track.items():
            clip_track_map[_key(item)] = track.name()

    mismatches = []
    seen_keys = set()
    for clip in selected_clips:
        if isinstance(clip, hiero.core.EffectTrackItem):
            continue
        key = _key(clip)
        if key in seen_keys:
            continue
        seen_keys.add(key)

        track_name = clip_track_map.get(key)
        if track_name is None:
            try:
                parent = clip.parentTrack()
                if parent is not None:
                    track_name = parent.name()
            except Exception:
                track_name = None

        _dlog(f"[MismatchFn] clip='{clip.name()}' track_resuelto='{track_name}'")
        if track_name is None or track_name not in task_exr_tracks:
            _dlog("[MismatchFn]   -> skip (track None o fuera de TASK_EXR_TRACKS)")
            continue

        try:
            fileinfos = clip.source().mediaSource().fileinfos()
            if not fileinfos:
                _dlog("[MismatchFn]   -> skip (sin fileinfos)")
                continue
            filename = os.path.basename(fileinfos[0].filename())
            base_name = clean_base_name(filename)
            task_from_name = extract_task_name(base_name)
            _dlog(
                f"[MismatchFn]   filename='{filename}' task_from_name='{task_from_name}'"
            )
            if not task_from_name:
                continue
            task_from_name = task_from_name.lower()
            expected_track = f"_{task_from_name}_"
            _dlog(
                f"[MismatchFn]   expected_track='{expected_track}' vs "
                f"track='{track_name}' -> match={expected_track == track_name}"
            )
            if expected_track != track_name:
                mismatches.append(
                    _build_mismatch_data(clip, seq, task_from_name, track_name)
                )
        except Exception as exc:
            _dlog(f"[MismatchFn]   -> excepcion: {exc}")
            continue

    return mismatches


def _build_mismatch_data(clip, seq, task_name, track_name):
    data = {
        "clip": clip.name() if clip is not None else "",
        "clip_item": clip,
        "sequence": seq,
        "task": task_name,
        "track": track_name,
    }
    try:
        data["timeline_in"] = clip.timelineIn()
        data["timeline_out"] = clip.timelineOut()
    except Exception:
        pass
    return data


class _TaskMismatchDialog(QtWidgets.QDialog):
    closed = QtCore.Signal()

    def __init__(self, mismatches, parent=None):
        super(_TaskMismatchDialog, self).__init__(parent)
        self.setWindowTitle("Task / Track Mismatch")
        self.setModal(False)
        self._mismatches = list(mismatches or [])
        self._keep_on_top = _load_keep_on_top()
        self._build_ui()
        self._apply_window_flags(initial=True)
        self._adjust_window_size()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        header = QtWidgets.QLabel(
            "Se encontraron clips donde la <b>task del filename</b> no coincide con el "
            "<b>nombre del track</b> donde el clip esta ubicado.<br>"
            "Revisa si hay que renombrar el clip o moverlo de track.<br>"
            "Puedes clickear una fila para ubicar ese clip en el timeline y setear su In/Out."
        )
        header.setWordWrap(True)
        layout.addWidget(header)

        self.table = QtWidgets.QTableWidget(len(self._mismatches), 3, self)
        self.table.setHorizontalHeaderLabels(["Clip", "Task (filename)", "Track"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.cellClicked.connect(self.navigate_to_table_row)
        self.table.setStyleSheet(
            """
            QTableView::item:selected {
                color: black;
                background-color: #b8b8b8;
            }
            """
        )

        for row, mismatch in enumerate(self._mismatches):
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(mismatch.get("clip", "")))
            task_item = QtWidgets.QTableWidgetItem(f"_{mismatch.get('task', '')}_")
            task_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 1, task_item)
            track_item = QtWidgets.QTableWidgetItem(mismatch.get("track", ""))
            track_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 2, track_item)

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        bottom_row = QtWidgets.QHBoxLayout()
        self.keep_on_top_chk = QtWidgets.QCheckBox("Keep this window on top")
        self.keep_on_top_chk.setChecked(bool(self._keep_on_top))
        self.keep_on_top_chk.stateChanged.connect(
            lambda _state: self._set_keep_on_top(self.keep_on_top_chk.isChecked())
        )
        bottom_row.addWidget(self.keep_on_top_chk, 0, Qt.AlignLeft | Qt.AlignVCenter)
        bottom_row.addStretch(1)
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.close)
        bottom_row.addWidget(close_btn, 0, Qt.AlignRight | Qt.AlignVCenter)
        layout.addLayout(bottom_row)

    def navigate_to_table_row(self, row, column=None):
        if row < 0 or row >= len(self._mismatches):
            return
        navigate_to_mismatch(self._mismatches[row])

    def _apply_window_flags(self, initial=False):
        flags = Qt.Window
        flags |= Qt.WindowMinimizeButtonHint
        flags |= Qt.WindowCloseButtonHint
        if self._keep_on_top and not sys.platform.startswith("win"):
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if not initial:
            self.show()
            self.raise_()

    def _set_topmost_native(self, value):
        try:
            user32 = ctypes.windll.user32
            set_window_pos = user32.SetWindowPos
            set_window_pos.restype = ctypes.wintypes.BOOL
            set_window_pos.argtypes = [
                ctypes.wintypes.HWND,
                ctypes.wintypes.HWND,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.c_int,
                ctypes.wintypes.UINT,
            ]
            hwnd_topmost = ctypes.wintypes.HWND(-1)
            hwnd_notopmost = ctypes.wintypes.HWND(-2)
            swp_nomove = 0x0002
            swp_nosize = 0x0001
            swp_noactivate = 0x0010
            return bool(
                set_window_pos(
                    int(self.winId()),
                    hwnd_topmost if value else hwnd_notopmost,
                    0,
                    0,
                    0,
                    0,
                    swp_nomove | swp_nosize | swp_noactivate,
                )
            )
        except Exception:
            return False

    def _set_keep_on_top(self, value, save=True):
        value = bool(value)
        if self._keep_on_top == value:
            if save:
                _save_keep_on_top(value)
            return
        self._keep_on_top = value
        if save:
            _save_keep_on_top(value)

        applied = False
        if sys.platform.startswith("win"):
            applied = self._set_topmost_native(value)
        if not applied:
            geom = self.geometry()
            self._apply_window_flags(initial=False)
            self.setGeometry(geom)

    def _adjust_window_size(self):
        width = self.table.verticalHeader().width() + 40
        for index in range(self.table.columnCount()):
            width += self.table.columnWidth(index) + 20

        rows_height = self.table.horizontalHeader().height() + self.table.frameWidth() * 2
        for index in range(self.table.rowCount()):
            rows_height += self.table.rowHeight(index)

        layout = self.layout()
        margins = layout.getContentsMargins()
        spacing = layout.spacing() if layout.spacing() > 0 else 0
        extra_height = margins[1] + margins[3] + max(0, layout.count() - 1) * spacing + 90
        self.resize(min(width, 900), min(rows_height + extra_height, 600))

    def showEvent(self, event):
        super(_TaskMismatchDialog, self).showEvent(event)
        if sys.platform.startswith("win") and self._keep_on_top:
            QtCore.QTimer.singleShot(0, lambda: self._set_topmost_native(True))

    def closeEvent(self, event):
        try:
            if self in _OPEN_MISMATCH_WINDOWS:
                _OPEN_MISMATCH_WINDOWS.remove(self)
        except Exception:
            pass
        try:
            self.closed.emit()
        except Exception:
            pass
        super(_TaskMismatchDialog, self).closeEvent(event)


def navigate_to_mismatch(mismatch):
    clip = mismatch.get("clip_item")
    seq = mismatch.get("sequence") or hiero.ui.activeSequence()
    if not clip or not seq:
        return

    try:
        timeline_editor = hiero.ui.getTimelineEditor(seq)
        if timeline_editor:
            timeline_editor.setSelection([clip])
            window = timeline_editor.window()
            if window:
                window.activateWindow()
                window.setFocus()

        in_point = clip.timelineIn()
        out_point = clip.timelineOut()
        try:
            seq.setInTime(in_point)
            seq.setOutTime(out_point)
        except Exception:
            pass

        viewer = hiero.ui.currentViewer()
        if viewer:
            viewer.setTime(in_point)

        QtCore.QTimer.singleShot(
            0, lambda: hiero.ui.findMenuAction("Zoom to Fit").trigger()
        )
    except Exception:
        pass


def show_task_mismatch_warning(mismatches, parent=None):
    """
    Muestra una ventana no modal listando los clips donde la task del filename
    no coincide con el track. Si la lista esta vacia, no hace nada.
    """
    if not mismatches:
        return None

    dialog = _TaskMismatchDialog(mismatches, parent)
    _OPEN_MISMATCH_WINDOWS.append(dialog)
    dialog.show()
    dialog.raise_()
    return dialog
