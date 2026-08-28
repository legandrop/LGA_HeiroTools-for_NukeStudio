"""
____________________________________________________________________

  LGA_import_shots_transcode_queue_ui v0.04 | Lega

  Ventana no modal para visualizar la cola global de Transcode Plates.
  Muestra jobs activos, pendientes y completados en una tabla unica
  ordenada globalmente, sin modificar la cola ni ejecutar transcodes.

  v0.04: La ventana lleva la fuente del pack (apply_ui_font), al
         armarla y de nuevo en cada render de la tabla; sin eso
         salia con la fuente del host.
  v0.03: Migracion al modulo de estilo LGA_UI_Style_HieroTools: la
         ventana usa Style.FORM y las hojas locales (_BTN_SMALL,
         _COMBO_STYLE, _TABLE_STYLE, _PBAR_STYLE) pasan a las del
         modulo. Los colores de shot alternado pasan a ENTITY/INFO y
         los de estado DONE/Error a OK/ERROR (mismo valor); el azul de
         Queued y el hover/pressed del link de shot quedan como hex
         porque no tienen token del mismo matiz.
  v0.02: Show All Import Windows y el foco por shot dejan de barrer
         QApplication.topLevelWidgets() a pelo y pasan por
         iter_live_widgets(only_top_level=True) + safe_widget_call.
  v0.01: UI inicial de Open Queue. Tabla Shot/Plate/Duracion/Estado,
         Show All Import Windows, Clear Completed y Keep this window on top persistente.

____________________________________________________________________
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import (
    QtCore,
    QtGui,
    QtWidgets,
    is_widget_alive,
    iter_live_widgets,
    safe_widget_call,
    widget_property,
)
from LGA_NKS_Edit_Panel_py import LGA_import_shots_settings as settings_mod
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import Style, Color, apply_ui_font


# Nombre de shot alternado por fila: entidad del pipeline y el celeste
# informativo, mismos roles que en los headers de Import Shots / CreateV000.
SHOTNAME_COLOR = Color.ENTITY
SHOTNAME_COLOR_ALT = Color.INFO

_CLR_TABLE_BG = Color.SURFACE  # fondo de los cell widgets HTML de la tabla
_CLR_TEXT = Color.TEXT         # texto de contenido en las celdas
_CLR_DIM = Color.TEXT          # etiquetas de la ventana (era el mismo gris)
# Ambar de frames/duracion. Es el mismo valor que Color.WARNING; se usa como
# dato de metadata, no como estado.
_CLR_FRAMES = Color.WARNING
# Azul de "Queued": no hay token del mismo matiz (Color.INFO es mucho mas
# saturado para este texto chico), se deja el hex y se reporta.
_CLR_PENDING = "#5a9ab5"
_CLR_DONE = Color.OK       # mismo valor que el hex anterior (#6a9960)
_CLR_ERROR = Color.ERROR   # mismo valor que el hex anterior (#a06060)

# Hojas del modulo de estilo del pack; este archivo ya no define QSS propio.
_BTN_SMALL = Style.BTN_SMALL
_COMBO_STYLE = Style.COMBO
_TABLE_STYLE = Style.TABLE
_PBAR_STYLE = Style.PROGRESS

_WINDOW = None


def _settings_path():
    return settings_mod.get_settings_path()


def _load_keep_on_top():
    cfg = configparser.ConfigParser()
    p = _settings_path()
    if p.exists():
        cfg.read(str(p), encoding="utf-8")
    return cfg.getboolean("TranscodeQueueWindow", "keep_on_top", fallback=False)


def _load_cpu_preset():
    cfg = configparser.ConfigParser()
    p = _settings_path()
    if p.exists():
        cfg.read(str(p), encoding="utf-8")
    return cfg.get("TranscodeQueueWindow", "cpu_preset", fallback="High")


def _save_window_setting(key, value):
    p = _settings_path()
    cfg = configparser.ConfigParser()
    if p.exists():
        cfg.read(str(p), encoding="utf-8")
    if not cfg.has_section("TranscodeQueueWindow"):
        cfg.add_section("TranscodeQueueWindow")
    cfg.set("TranscodeQueueWindow", key, str(value))
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(str(p), "w", encoding="utf-8") as fh:
        cfg.write(fh)


def _save_keep_on_top(value):
    _save_window_setting("keep_on_top", "true" if value else "false")


def _save_cpu_preset(value):
    _save_window_setting("cpu_preset", value)


def _escape(text):
    return (
        str(text or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _duration_text(frame_count, fps):
    try:
        frames = int(frame_count)
    except Exception:
        frames = 0
    if frames <= 0:
        return ""
    try:
        fps_v = float(fps)
    except Exception:
        fps_v = 0.0
    if fps_v > 0.0:
        return "%df - %.1fs" % (frames, frames / fps_v)
    return "%df" % frames


def _elapsed_text(seconds):
    try:
        elapsed = float(seconds)
    except Exception:
        elapsed = 0.0
    if elapsed <= 0.0:
        return ""
    return "%.1fs" % elapsed


def _make_html_label(html):
    lbl = QtWidgets.QLabel(html)
    lbl.setTextFormat(QtCore.Qt.RichText)
    lbl.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
    lbl.setStyleSheet("background:%s; padding:0px 6px;" % _CLR_TABLE_BG)
    return lbl


def _job_key(job):
    return str((job or {}).get("job_id") or "%s:%s:%s" % (
        (job or {}).get("window_id", ""),
        (job or {}).get("row_i", ""),
        (job or {}).get("name", ""),
    ))



class TranscodeQueueWindow(QtWidgets.QDialog):
    def __init__(self, manager, parent=None, focus_window_callback=None):
        super(TranscodeQueueWindow, self).__init__(parent)
        self.manager = manager
        self.focus_window_callback = focus_window_callback
        self._completed = {}
        self._row_order = []
        self._progress_timers = {}
        self._progress_bars = {}
        self._progress_dirs = {}
        self._last_snapshot = []
        self._keep_on_top = _load_keep_on_top()
        self._cpu_preset = _load_cpu_preset()
        try:
            self.manager.set_cpu_preset(self._cpu_preset)
            self._cpu_preset = self.manager.cpu_preset()
        except Exception:
            self._cpu_preset = "High"

        self.setObjectName("LGA_TranscodeQueueWindow")
        self.setWindowTitle("Import Shots - Transcode Queue")
        self.setModal(False)
        self.setMinimumSize(720, 360)
        # Hoja completa del pack: fondo de ventana, labels y checkbox salen
        # de Style.FORM en lugar del QSS local con hexes.
        self.setStyleSheet(Style.FORM)
        self._apply_window_flags(initial=True)
        self._build_ui()
        self._connect_manager()
        self._set_keep_on_top(self._keep_on_top, save=False)
        self._render(self.manager.snapshot())

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        self.table = QtWidgets.QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Shot", "Plate", "Duracion", "Estado"])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setFocusPolicy(QtCore.Qt.NoFocus)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(False)
        self.table.setStyleSheet(_TABLE_STYLE)
        self.table.setColumnWidth(0, 150)
        self.table.setColumnWidth(1, 300)
        self.table.setColumnWidth(2, 105)
        self.table.setColumnWidth(3, 130)
        hdr = self.table.horizontalHeader()
        hdr.setStretchLastSection(False)
        try:
            hdr.setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
        except Exception:
            pass
        layout.addWidget(self.table, 1)

        btn_row = QtWidgets.QHBoxLayout()
        self.show_windows_btn = QtWidgets.QPushButton("Show All Import Windows")
        self.show_windows_btn.setStyleSheet(_BTN_SMALL)
        self.show_windows_btn.clicked.connect(self._show_import_shot_windows)
        self.clear_btn = QtWidgets.QPushButton("Clear Completed")
        self.clear_btn.setStyleSheet(_BTN_SMALL)
        self.clear_btn.clicked.connect(self._clear_completed)
        btn_row.addWidget(self.show_windows_btn)
        btn_row.addWidget(self.clear_btn)

        cpu_label = QtWidgets.QLabel("CPU")
        cpu_label.setStyleSheet("color:%s; font-size:11px; padding-left:6px;" % _CLR_DIM)
        btn_row.addWidget(cpu_label)

        self.cpu_combo = QtWidgets.QComboBox()
        self.cpu_combo.setStyleSheet(_COMBO_STYLE)
        self._populate_cpu_combo()
        self.cpu_combo.currentIndexChanged.connect(self._on_cpu_combo_changed)
        btn_row.addWidget(self.cpu_combo)
        btn_row.addStretch(1)

        self.keep_chk = QtWidgets.QCheckBox("Keep this window on top")
        # Checkbox con texto: el del pack usa spacing 0 salvo esta propiedad.
        self.keep_chk.setProperty("lgaLabeled", True)
        self.keep_chk.setChecked(bool(self._keep_on_top))
        self.keep_chk.stateChanged.connect(lambda _state: self._set_keep_on_top(self.keep_chk.isChecked()))
        btn_row.addWidget(self.keep_chk)
        layout.addLayout(btn_row)

        # Fuente del pack al final del armado: recorre los hijos ya creados.
        apply_ui_font(self)

    def _connect_manager(self):
        self.manager.queue_changed.connect(self._render)
        self.manager.sequence_started.connect(self._on_sequence_started)
        self.manager.sequence_done.connect(self._on_sequence_done)
        self.manager.job_cancelled.connect(self._on_job_cancelled)
        if hasattr(self.manager, "cpu_preset_changed"):
            self.manager.cpu_preset_changed.connect(self._on_cpu_preset_changed)

    def _populate_cpu_combo(self):
        presets = self.manager.cpu_presets() if hasattr(self.manager, "cpu_presets") else ["High", "Medium", "Low", "Minimal"]
        self.cpu_combo.blockSignals(True)
        self.cpu_combo.clear()
        for preset in presets:
            try:
                opts = self.manager.cpu_options_for_preset(preset)
            except Exception:
                opts = {"workers": "", "exrmetrics_threads": ""}
            label = "%s (%s/%s)" % (preset, opts.get("workers", ""), opts.get("exrmetrics_threads", ""))
            self.cpu_combo.addItem(label, preset)
        self._set_cpu_combo_value(self._cpu_preset)
        self.cpu_combo.blockSignals(False)

    def _set_cpu_combo_value(self, preset):
        for i in range(self.cpu_combo.count()):
            if str(self.cpu_combo.itemData(i)) == str(preset):
                self.cpu_combo.setCurrentIndex(i)
                return
        self.cpu_combo.setCurrentIndex(0)

    def _on_cpu_combo_changed(self, _index):
        preset = self.cpu_combo.itemData(self.cpu_combo.currentIndex())
        if not preset:
            return
        self._cpu_preset = str(preset)
        try:
            self.manager.set_cpu_preset(self._cpu_preset)
            self._cpu_preset = self.manager.cpu_preset()
        except Exception:
            pass
        _save_cpu_preset(self._cpu_preset)

    def _on_cpu_preset_changed(self, preset, _opts):
        self._cpu_preset = str(preset or "High")
        self.cpu_combo.blockSignals(True)
        self._set_cpu_combo_value(self._cpu_preset)
        self.cpu_combo.blockSignals(False)

    def _apply_window_flags(self, initial=False):
        flags = QtCore.Qt.Window
        flags |= QtCore.Qt.WindowMinimizeButtonHint
        flags |= QtCore.Qt.WindowCloseButtonHint
        if self._keep_on_top:
            flags |= QtCore.Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        if not initial:
            self.show()
            self.raise_()

    def _set_keep_on_top(self, value, save=True):
        value = bool(value)
        if self._keep_on_top == value:
            if save:
                _save_keep_on_top(value)
            return
        self._keep_on_top = value
        if self.keep_chk.isChecked() != value:
            self.keep_chk.blockSignals(True)
            self.keep_chk.setChecked(value)
            self.keep_chk.blockSignals(False)
        if save:
            _save_keep_on_top(value)
        geom = self.geometry()
        self._apply_window_flags(initial=False)
        self.setGeometry(geom)

    def _show_import_shot_windows(self):
        # iter_live_widgets(only_top_level=True) descarta los wrappers de
        # widgets que Qt ya destruyo del lado C++. Se los saltea de una, por
        # consistencia con el fix de allWidgets() y para no depender del
        # try/except de cada lectura.
        for widget in iter_live_widgets(only_top_level=True):
            if safe_widget_call(widget, "objectName") != "LGA_ImportShotDialog":
                continue
            try:
                widget.show()
                if safe_widget_call(widget, "isMinimized", False):
                    widget.showNormal()
                widget.raise_()
                widget.activateWindow()
            except Exception:
                pass

    def _focus_window(self, window_id, shot_name):
        if self.focus_window_callback:
            self.focus_window_callback(window_id, shot_name)
            return
        shot_key = (shot_name or "").strip().lower()
        for widget in iter_live_widgets(only_top_level=True):
            if safe_widget_call(widget, "objectName") != "LGA_ImportShotDialog":
                continue
            if not safe_widget_call(widget, "isVisible", False):
                continue
            match = bool(window_id) and widget_property(widget, "window_id") == window_id
            if not match:
                match = (
                    bool(shot_key)
                    and widget_property(widget, "shot_name").strip().lower() == shot_key
                )
            if not match:
                continue
            try:
                widget.show()
                widget.raise_()
                widget.activateWindow()
            except Exception:
                pass
            return

    def _clear_completed(self):
        self._completed.clear()
        live_keys = set(_job_key(j) for j in self._last_snapshot)
        self._row_order = [k for k in self._row_order if k in live_keys]
        self._render(self._last_snapshot)

    def _on_sequence_started(self, window_id, row_i, dst_dir, total_frames):
        for job in self._last_snapshot:
            if job.get("window_id") == window_id and job.get("row_i") == row_i:
                job["dst_dir"] = dst_dir
                job["total_frames"] = total_frames
                break
        self._render(self._last_snapshot)

    def _on_sequence_done(self, window_id, row_i, ok, stats):
        item = dict(stats or {})
        item["window_id"] = item.get("window_id") or window_id
        item["row_i"] = row_i
        item["status"] = "done" if ok else "error"
        if not item.get("shot_name"):
            known = self._find_known_job(item)
            if known:
                item.update({k: v for k, v in known.items() if k not in item or item.get(k) in (None, "")})
        self._completed[_job_key(item)] = item
        self._render(self.manager.snapshot())

    def _on_job_cancelled(self, window_id, row_i, result):
        item = dict(result or {})
        item["window_id"] = item.get("window_id") or window_id
        item["row_i"] = row_i
        item["status"] = "cancelled"
        if not item.get("shot_name"):
            known = self._find_known_job(item)
            if known:
                item.update({k: v for k, v in known.items() if k not in item or item.get(k) in (None, "")})
        self._completed[_job_key(item)] = item
        self._render(self.manager.snapshot())

    def _find_known_job(self, item):
        key = item.get("job_id")
        for job in self._last_snapshot:
            if key and job.get("job_id") == key:
                return job
            if job.get("window_id") == item.get("window_id") and job.get("row_i") == item.get("row_i"):
                return job
        return None

    def _render(self, snapshot):
        self._last_snapshot = [dict(j) for j in (snapshot or [])]
        live_by_key = {_job_key(j): j for j in self._last_snapshot}
        all_known = dict(self._completed)
        all_known.update(live_by_key)
        for job in self._last_snapshot:
            key = _job_key(job)
            if key not in self._row_order:
                self._row_order.append(key)
        for key in self._completed:
            if key not in self._row_order:
                self._row_order.append(key)
        self._row_order = [key for key in self._row_order if key in all_known]
        rows = [all_known[key] for key in self._row_order]
        self._stop_progress_timers()

        self.table.setRowCount(len(rows))
        shot_colors = self._shot_colors(rows)
        for row_i, job in enumerate(rows):
            self._populate_row(row_i, job, shot_colors.get(_job_key(job), SHOTNAME_COLOR))
        # Las celdas de la tabla se recrean en cada render: hay que volver a
        # pasar la fuente del pack para que no salgan con la del host.
        apply_ui_font(self)
        self.clear_btn.setEnabled(bool(self._completed))

    def _shot_colors(self, rows):
        colors = {}
        current = object()
        idx = -1
        for job in rows:
            shot = job.get("shot_name", "")
            if shot != current:
                idx += 1
                current = shot
            colors[_job_key(job)] = SHOTNAME_COLOR if idx % 2 == 0 else SHOTNAME_COLOR_ALT
        return colors

    def _populate_row(self, row_i, job, shot_color):
        shot = job.get("shot_name", "")
        window_id = job.get("window_id", "")

        shot_btn = QtWidgets.QPushButton(shot)
        shot_btn.setFlat(True)
        shot_btn.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        # Hover/pressed del link: variantes clara y oscura del magenta de
        # entidad; la paleta no tiene tokens para esos dos matices.
        shot_btn.setStyleSheet(
            "QPushButton { background: transparent; border:0px; padding:0px 6px;"
            " color:%s; text-align:left; }"
            "QPushButton:hover { color:#e2a2e2; text-decoration:none; }"
            "QPushButton:pressed { color:#9f529f; }" % shot_color
        )
        shot_btn.clicked.connect(lambda _checked=False, wid=window_id, sh=shot: self._focus_window(wid, sh))
        self.table.setCellWidget(row_i, 0, shot_btn)

        plate = job.get("name", "")
        plate_html = self._plate_html(plate, shot, shot_color)
        self.table.setCellWidget(row_i, 1, _make_html_label(plate_html))

        dur = _duration_text(job.get("frame_count"), job.get("source_fps") or job.get("fps"))
        dur_html = "<span style='color:%s;'>%s</span>" % (_CLR_FRAMES, _escape(dur))
        self.table.setCellWidget(row_i, 2, _make_html_label(dur_html))

        self._set_status_widget(row_i, job)

    def _plate_html(self, plate, shot, shot_color):
        plate = str(plate or "")
        shot = str(shot or "")
        if shot and plate.startswith(shot):
            return (
                "<span style='color:%s;'>%s</span>"
                "<span style='color:%s;'>%s</span>"
                % (shot_color, _escape(shot), _CLR_TEXT, _escape(plate[len(shot):]))
            )
        return "<span style='color:%s;'>%s</span>" % (_CLR_TEXT, _escape(plate))

    def _set_status_widget(self, row_i, job):
        status = job.get("status", "")
        if status in ("running", "starting"):
            pbar = QtWidgets.QProgressBar()
            total = int(job.get("total_frames") or job.get("frame_count") or 1)
            pbar.setRange(0, max(total, 1))
            pbar.setValue(0)
            pbar.setFormat("%v/%m")
            pbar.setStyleSheet(_PBAR_STYLE)
            self.table.setCellWidget(row_i, 3, pbar)
            dst = job.get("dst_dir")
            if dst:
                self._start_progress_timer(_job_key(job), Path(dst), total, pbar)
            return

        if status == "queued":
            text = "Queued #%d" % int(job.get("position") or 0)
            color = _CLR_PENDING
        elif status == "done":
            elapsed = _elapsed_text(job.get("elapsed_seconds"))
            text = "DONE (%s)" % elapsed if elapsed else "DONE"
            color = _CLR_DONE
        elif status == "cancelled":
            text = "Cancelado"
            color = _CLR_ERROR
        elif status == "error":
            text = "Error"
            color = _CLR_ERROR
        else:
            text = ""
            color = _CLR_DIM
        self.table.setCellWidget(row_i, 3, _make_html_label("<span style='color:%s;'>%s</span>" % (color, text)))

    def _start_progress_timer(self, key, dst_dir, total, pbar):
        timer = QtCore.QTimer(self)
        timer.timeout.connect(lambda: self._poll_progress(key, dst_dir, total, pbar))
        self._progress_timers[key] = timer
        self._progress_bars[key] = pbar
        self._progress_dirs[key] = dst_dir
        timer.start(300)
        self._poll_progress(key, dst_dir, total, pbar)

    def _poll_progress(self, key, dst_dir, total, pbar):
        if not pbar:
            return
        try:
            count = sum(1 for _ in Path(dst_dir).glob("*.exr")) if Path(dst_dir).exists() else 0
            pbar.setValue(min(count, max(total, 1)))
        except Exception:
            pass

    def _stop_progress_timers(self):
        for timer in self._progress_timers.values():
            try:
                timer.stop()
            except Exception:
                pass
        self._progress_timers.clear()
        self._progress_bars.clear()
        self._progress_dirs.clear()

    def closeEvent(self, event):
        self._stop_progress_timers()
        super(TranscodeQueueWindow, self).closeEvent(event)


def show_queue_window(manager, parent=None, focus_window_callback=None):
    global _WINDOW
    try:
        if _WINDOW is not None and _WINDOW.isVisible():
            _WINDOW.show()
            if hasattr(_WINDOW, "showNormal") and _WINDOW.isMinimized():
                _WINDOW.showNormal()
            _WINDOW.raise_()
            _WINDOW.activateWindow()
            return _WINDOW
    except Exception:
        _WINDOW = None

    _WINDOW = TranscodeQueueWindow(manager, parent=parent, focus_window_callback=focus_window_callback)
    _WINDOW.show()
    _WINDOW.raise_()
    _WINDOW.activateWindow()
    return _WINDOW
