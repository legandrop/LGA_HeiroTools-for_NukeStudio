"""
____________________________________________________________________

  LGA_import_shots_transcode v1.00 | Lega

  Helper de transcode EXR para LGA_import_shots.

  Proporciona TranscodeWorkerSignals, TranscodeWorker y
  build_manifest_for_sequence. El worker procesa las secuencias
  en serie; el paralelismo por frame lo maneja internamente
  LGA_EXR_Convert.py con concurrent.futures.

____________________________________________________________________
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore, QtWidgets

QObject    = QtCore.QObject
QRunnable  = QtCore.QRunnable
Signal     = QtCore.Signal
Slot       = QtCore.Slot


# ── Señales ───────────────────────────────────────────────────────────────────

class TranscodeWorkerSignals(QObject):
    """
    Señales emitidas por TranscodeWorker hacia el hilo principal de la UI.

    log_message      — línea de texto para el panel de log (plain text)
    sequence_started — (row_index, dst_dir_str, total_frames): archivos preparados,
                       subprocess a punto de arrancar — permite iniciar barra de progreso
    sequence_done    — (row_index, ok, stats_dict): la secuencia terminó
    all_done         — lista de dicts resultado por secuencia (worker terminó)
    error            — mensaje de error fatal (detiene el worker)
    """
    log_message      = Signal(str)
    sequence_started = Signal(int, str, int)   # row_i, dst_dir, total_frames
    sequence_done    = Signal(int, bool, dict)
    all_done         = Signal(list)
    error            = Signal(str)


# ── Manifest builder ──────────────────────────────────────────────────────────

def build_manifest_for_sequence(
    item: dict,
    src_dir: Path,
    dst_dir: Path,
    tw: int | None,
    th: int | None,
    compression: str,
    dwa_level: int,
    resize_filter: str,
    overwrite: bool = True,
    channels: str = "all",
    pixel_aspect_ratio: float | None = None,
) -> dict:
    """
    Construye el manifest dict para LGA_EXR_Convert.py para una sola secuencia EXR.

    Enumera todos los .exr en src_dir y mapea src→dst manteniendo el mismo filename.
    Si tw/th coinciden con las dimensiones originales del item, resize queda null.

    Args:
        item:                dict del item de _convert_rows (necesita 'width', 'height')
        src_dir:             directorio con los EXR fuente
        dst_dir:             directorio destino para los EXR convertidos
        tw, th:              resolución destino (None → no resize)
        compression:         "dwaa", "zip", etc.
        dwa_level:           nivel de compresión DWA (e.g. 45)
        resize_filter:       "lanczos3", "cubic", "box"
        overwrite:           si True, sobreescribe archivos existentes en dst
        channels:            "all" conserva todos; "rgb" descarta alpha y canales extra
        pixel_aspect_ratio:  si no None, escribe la metadata PixelAspectRatio en el output

    Returns:
        manifest dict listo para json.dumps()
    """
    src_path = Path(src_dir)
    dst_path = Path(dst_dir)

    exr_files = sorted(src_path.glob("*.exr"))
    if not exr_files:
        exr_files = sorted(src_path.glob("**/*.exr"))

    tasks = [
        {"src": str(f), "dst": str(dst_path / f.name)}
        for f in exr_files
    ]

    # Solo incluir resize si hay cambio real de dimensiones
    sw, sh = item.get("width"), item.get("height")
    resize = None
    if tw and th and sw and sh and (tw != sw or th != sh):
        resize = {"width": tw, "height": th, "filter": resize_filter}

    manifest: dict = {
        "compression": compression,
        "dwa_level":   dwa_level,
        "resize":      resize,
        "workers":     6,
        "overwrite":   overwrite,
        "channels":    channels,
        "tasks":       tasks,
    }
    if pixel_aspect_ratio is not None:
        manifest["pixel_aspect_ratio"] = pixel_aspect_ratio
    return manifest


# ── Pre-transcode helpers (file-system + UI) ──────────────────────────────────

def _exr_count(path: Path) -> int:
    return sum(1 for _ in Path(path).glob("*.exr")) if Path(path).exists() else 0


def _resolved(path: Path) -> Path:
    return Path(path).resolve()


def _is_inside(child: Path, parent: Path) -> bool:
    child_s = str(_resolved(child)).lower()
    parent_s = str(_resolved(parent)).lower().rstrip("\\/")
    return child_s == parent_s or child_s.startswith(parent_s + "\\") or child_s.startswith(parent_s + "/")


def _ensure_safe_child(path: Path, parent: Path, label: str) -> None:
    if _resolved(path) == _resolved(parent) or not _is_inside(path, parent):
        raise RuntimeError(
            "Ruta insegura para %s: path=%s parent=%s" % (label, _resolved(path), _resolved(parent))
        )


def _safe_rmtree(path: Path, parent: Path, label: str, ignore_errors: bool = False) -> None:
    target = Path(path)
    if not target.exists():
        return
    _ensure_safe_child(target, parent, label)
    shutil.rmtree(str(target), ignore_errors=ignore_errors)


def _safe_remove_exr(path: Path, parent: Path, label: str) -> None:
    target = Path(path)
    _ensure_safe_child(target, parent, label)
    if target.suffix.lower() != ".exr":
        raise RuntimeError("Delete bloqueado: no es EXR (%s)" % target)
    target.unlink()


def _log_optional(log_fn, message: str) -> None:
    if log_fn:
        try:
            log_fn(message)
        except Exception:
            pass


def check_existing_outputs(item: dict, test_mode: bool, move_originals: bool):
    """Detecta si ya existen archivos de un transcode previo para la secuencia.

    Estructura esperada (move_originals):
      _input/
        Originals/
          <nombre_carpeta_plate>/  ← misma subcarpeta que item_path dentro de _input

    Returns:
        (has_conflict: bool, description: str)
    """
    item_path = Path(item["path"])
    if test_mode:
        dst = item_path / "test_transcode"
        if dst.exists():
            count = sum(1 for _ in dst.glob("*.exr"))
            if count > 0:
                return True, "test_transcode/ ya contiene %d archivos EXR" % count
    elif move_originals:
        orig = item_path.parent / "Originals" / item_path.name
        if orig.exists():
            count = sum(1 for _ in orig.glob("*.exr"))
            label = "%d EXR" % count if count else "carpeta vacía"
            return True, "_input/Originals/%s ya existe (%s — transcode anterior)" % (item_path.name, label)
    else:
        tmp = item_path / "_tc_temp_src"
        if tmp.exists():
            return True, "_tc_temp_src/ existe (transcode anterior incompleto)"
    return False, ""


def delete_existing_outputs(item: dict, test_mode: bool, move_originals: bool, log_fn=None) -> int:
    """Elimina EXRs del destino antes de un re-transcode para limpiar el contador.

    - TEST mode:      borra *.exr de test_transcode/
    - no-move mode:   borra _tc_temp_src/ completa (era buffer de run fallido)
    - move_originals: borra la subcarpeta de Originals del plate y los EXR
                      convertidos que quedaron en item_path del run anterior

    Returns:
        Cantidad de archivos/directorios eliminados.
    """
    item_path = Path(item["path"])
    deleted = 0
    if test_mode:
        dst = item_path / "test_transcode"
        if dst.exists():
            _log_optional(log_fn, "cleanup snapshot test dst=%s dst_exr=%d" % (dst, _exr_count(dst)))
            for f in list(dst.glob("*.exr")):
                _safe_remove_exr(f, dst, "test_transcode cleanup")
                deleted += 1
    elif move_originals:
        # Si existe Originals/<plate>/, es un transcode anterior. Para re-transcodear
        # no podemos borrar esos EXR: son la fuente original. Los restauramos a
        # item_path, limpiando antes los EXR convertidos que quedaron ahi.
        orig_plate = item_path.parent / "Originals" / item_path.name
        if orig_plate.exists():
            orig_exrs = sorted(orig_plate.glob("*.exr"))
            item_exr_before = _exr_count(item_path)
            _log_optional(
                log_fn,
                "cleanup snapshot item_path=%s originals_dir=%s item_exr_count=%d originals_exr_count=%d"
                % (item_path, orig_plate, item_exr_before, len(orig_exrs))
            )
            if orig_exrs:
                _ensure_safe_child(orig_plate, item_path.parent / "Originals", "Originals restore")
                # Borra los EXR convertidos que quedaron en item_path del run anterior.
                for f in list(item_path.glob("*.exr")):
                    _safe_remove_exr(f, item_path, "converted output cleanup")
                    deleted += 1
                # Restaura los originales para que TranscodeWorker pueda moverlos de
                # nuevo a Originals/<plate>/ y usarlos como source.
                item_path.mkdir(parents=True, exist_ok=True)
                for f in orig_exrs:
                    dst = item_path / f.name
                    try:
                        os.rename(str(f), str(dst))
                    except OSError:
                        shutil.move(str(f), str(dst))
                restored_count = _exr_count(item_path)
                remaining_orig_count = _exr_count(orig_plate)
                _log_optional(
                    log_fn,
                    "restore snapshot item_path=%s originals_dir=%s restored_item_exr_count=%d remaining_originals_exr_count=%d"
                    % (item_path, orig_plate, restored_count, remaining_orig_count)
                )
                if restored_count < len(orig_exrs) or remaining_orig_count != 0:
                    raise RuntimeError(
                        "Restore inseguro: item_path=%s restored=%d expected=%d remaining_originals=%d"
                        % (item_path, restored_count, len(orig_exrs), remaining_orig_count)
                    )
                _safe_rmtree(orig_plate, item_path.parent / "Originals", "empty Originals plate")
                deleted += 1
            else:
                # Carpeta vacia: limpiarla, pero conservar los EXR actuales de
                # item_path como unica fuente disponible para el re-transcode.
                if item_exr_before <= 0:
                    raise RuntimeError(
                        "Overwrite abortado: no hay EXR en item_path ni en Originals. item_path=%s originals_dir=%s"
                        % (item_path, orig_plate)
                    )
                _safe_rmtree(orig_plate, item_path.parent / "Originals", "empty Originals plate")
                deleted += 1
            try:
                orig_plate.parent.rmdir()
            except Exception:
                pass
    else:
        # Borra la carpeta temporal de buffer si quedó de un run fallido
        tmp = item_path / "_tc_temp_src"
        if tmp.exists():
            tmp_count = _exr_count(tmp)
            item_count = _exr_count(item_path)
            _log_optional(
                log_fn,
                "cleanup snapshot item_path=%s temp_src=%s item_exr_count=%d temp_exr_count=%d"
                % (item_path, tmp, item_count, tmp_count)
            )
            if tmp_count <= 0 and item_count <= 0:
                raise RuntimeError(
                    "Cleanup abortado: no hay EXR en item_path ni en _tc_temp_src. item_path=%s temp=%s"
                    % (item_path, tmp)
                )
            _safe_rmtree(tmp, item_path, "_tc_temp_src cleanup")
            deleted += 1
    return deleted


def show_overwrite_warning(seq_name: str, conflict_desc: str, parent=None) -> bool:
    """Muestra un diálogo personalizado cuando el destino ya tiene archivos.

    Returns:
        True  → el usuario confirma sobreescribir
        False → el usuario cancela esta secuencia
    """
    _BTN_SECONDARY = (
        "QPushButton { background-color:#3a3a3a; border:1px solid #555555;"
        " color:#CCCCCC; padding:7px 18px; border-radius:3px; }"
        "QPushButton:hover { background-color:#4a4a4a; }"
    )
    _BTN_PRIMARY = (
        "QPushButton { background-color:#443a91; border:1px solid #5a4faa;"
        " color:#CCCCCC; padding:7px 18px; border-radius:3px; font-weight:bold; }"
        "QPushButton:hover { background-color:#774dcb; }"
    )

    dlg = QtWidgets.QDialog(parent)
    dlg.setWindowTitle("Archivos existentes")
    dlg.setMinimumWidth(440)
    dlg.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.FramelessWindowHint)
    dlg.setStyleSheet(
        "QDialog { background-color:#2B2B2B; border:1px solid #555555; }"
        "QLabel  { color:#a7a7a7; }"
    )

    layout = QtWidgets.QVBoxLayout(dlg)
    layout.setContentsMargins(24, 20, 24, 20)
    layout.setSpacing(10)

    header_row = QtWidgets.QHBoxLayout()
    icon_lbl  = QtWidgets.QLabel("⚠")
    icon_lbl.setStyleSheet("color:#d9a441; font-size:20px;")
    title_lbl = QtWidgets.QLabel("Archivos existentes")
    title_lbl.setStyleSheet("color:#d9a441; font-size:13px; font-weight:bold;")
    header_row.addWidget(icon_lbl)
    header_row.addSpacing(8)
    header_row.addWidget(title_lbl)
    header_row.addStretch()
    layout.addLayout(header_row)

    sep = QtWidgets.QFrame()
    sep.setFrameShape(QtWidgets.QFrame.HLine)
    sep.setStyleSheet("background:#444444;")
    sep.setFixedHeight(1)
    layout.addWidget(sep)

    name_lbl = QtWidgets.QLabel(seq_name)
    name_lbl.setStyleSheet(
        "color:#cccccc; font-size:12px; font-weight:bold; margin-top:4px;"
    )
    layout.addWidget(name_lbl)

    desc_lbl = QtWidgets.QLabel(conflict_desc)
    desc_lbl.setStyleSheet("color:#999999; font-size:11px;")
    layout.addWidget(desc_lbl)

    q_lbl = QtWidgets.QLabel("¿Desea sobreescribir los archivos existentes?")
    q_lbl.setStyleSheet("color:#a7a7a7; font-size:11px; margin-top:4px;")
    layout.addWidget(q_lbl)

    layout.addSpacing(8)

    btn_row = QtWidgets.QHBoxLayout()
    btn_row.addStretch()
    cancel_btn    = QtWidgets.QPushButton("Cancelar")
    overwrite_btn = QtWidgets.QPushButton("Sobreescribir")
    cancel_btn.setStyleSheet(_BTN_SECONDARY)
    overwrite_btn.setStyleSheet(_BTN_PRIMARY)
    btn_row.addWidget(cancel_btn)
    btn_row.addSpacing(8)
    btn_row.addWidget(overwrite_btn)
    layout.addLayout(btn_row)

    result = [False]
    cancel_btn.clicked.connect(dlg.reject)
    overwrite_btn.clicked.connect(lambda: (result.__setitem__(0, True), dlg.accept()))

    dlg.exec_()
    return result[0]


# ── Worker ────────────────────────────────────────────────────────────────────

class TranscodeWorker(QRunnable):
    """
    Worker de transcode EXR. Diseñado para ejecutarse en QThreadPool.

    Itera las secuencias en serie. Por cada secuencia:
      1. Prepara paths de src/dst según modo (test / move_originals / temp)
      2. Construye el manifest JSON
      3. Llama a LGA_EXR_Convert.py via subprocess con el Python bundled de OIIO
      4. Parsea el resultado JSON y emite señales hacia la UI

    En caso de fallo (no test_mode), restaura los originales automáticamente.
    """

    def __init__(
        self,
        job_sequences: list[tuple[int, dict, int | None, int | None]],
        global_opts: dict,
        test_mode: bool,
        move_originals: bool,
        delete_originals: bool,
        shared_dir: str,
    ):
        """
        Args:
            job_sequences:    lista de (row_index, item_dict, target_w, target_h)
            global_opts:      dict con compression, dwa_level, resize_filter, workers
            test_mode:        si True, output a {seq}/test_transcode/ sin mover nada
            move_originals:   si True, mueve originales a {seq}/Originals/ antes de convertir
            delete_originals: si True (y move_originals), borra Originals/ tras éxito
            shared_dir:       path a LGA_NKS_Shared/ (str)
        """
        super(TranscodeWorker, self).__init__()
        self.job_sequences    = job_sequences
        self.global_opts      = global_opts
        self.test_mode        = test_mode
        self.move_originals   = move_originals
        self.delete_originals = delete_originals
        self.shared_dir       = Path(shared_dir)
        self.signals          = TranscodeWorkerSignals()

        self._convert_script = self.shared_dir / "LGA_EXR_Convert.py"
        # Python bundled con OIIO — garantiza stdlib completa + no depende de sys.executable
        self._python_exe = self.shared_dir / "OIIO_Win" / "bin" / "python" / "python.exe"
        self._start_time: float = 0.0

    # ── Helpers de tiempo ────────────────────────────────────────────────

    def _t(self) -> str:
        """Retorna el tiempo transcurrido desde el inicio del worker como '[N.Ns]'."""
        return "[%.1fs]" % (time.perf_counter() - self._start_time)

    # ── Entry point del hilo secundario ──────────────────────────────────

    @Slot()
    def run(self):
        self._start_time = time.perf_counter()
        total = len(self.job_sequences)
        self.signals.log_message.emit(
            "%s Iniciando transcode — %d secuencia%s" % (
                self._t(), total, "" if total == 1 else "s"
            )
        )

        all_results = []
        try:
            for idx, (row_i, item, tw, th) in enumerate(self.job_sequences, 1):
                seq_name = item.get("name", Path(item["path"]).name)
                self.signals.log_message.emit(
                    "%s [%d/%d] %s" % (self._t(), idx, total, seq_name)
                )
                result = self._transcode_sequence(row_i, item, tw, th, idx, total)
                all_results.append(result)

            ok_count = sum(1 for r in all_results if r.get("ok"))
            self.signals.log_message.emit(
                "%s Transcode completo: %d/%d OK" % (self._t(), ok_count, total)
            )
        except Exception as exc:
            self.signals.error.emit("Error inesperado en worker: %s" % str(exc))
            return

        self.signals.all_done.emit(all_results)

    # ── Proceso de una secuencia ──────────────────────────────────────────

    def _transcode_sequence(
        self,
        row_i: int,
        item: dict,
        tw: int | None,
        th: int | None,
        seq_idx: int,
        seq_total: int,
    ) -> dict:
        item_path = Path(item["path"])
        seq_name  = item.get("name", item_path.name)
        seq_start = time.perf_counter()

        originals_dir: Path | None = None
        temp_src_dir:  Path | None = None

        try:
            # ── 1. Preparar paths de src / dst ────────────────────────
            if self.test_mode:
                src_dir = item_path
                dst_dir = item_path / "test_transcode"
                src_count = _exr_count(src_dir)
                self.signals.log_message.emit(
                    "  %s preflight item_path=%s item_exr_count=%d mode=test" % (
                        self._t(), item_path, src_count
                    )
                )
                if src_count <= 0:
                    raise RuntimeError("No se encontraron EXR fuente en: %s" % item_path)
                dst_dir.mkdir(parents=True, exist_ok=True)

            elif self.move_originals:
                # Mueve los EXR a _input/Originals/<nombre_carpeta_plate>/
                originals_dir = item_path.parent / "Originals" / item_path.name
                originals_parent = originals_dir.parent
                _ensure_safe_child(originals_dir, originals_parent, "Originals plate dir")
                item_count = _exr_count(item_path)
                originals_count = _exr_count(originals_dir)
                self.signals.log_message.emit(
                    "  %s preflight item_path=%s originals_dir=%s item_exr_count=%d originals_exr_count=%d"
                    % (self._t(), item_path, originals_dir, item_count, originals_count)
                )
                if item_count <= 0 and originals_count <= 0:
                    raise RuntimeError(
                        "Preflight abortado: no hay EXR fuente en item_path ni Originals. item_path=%s originals_dir=%s"
                        % (item_path, originals_dir)
                    )
                if originals_count > 0:
                    raise RuntimeError(
                        "Preflight abortado: Originals/%s ya contiene EXR. Debe resolverse por overwrite antes del worker."
                        % item_path.name
                    )
                originals_dir.mkdir(parents=True, exist_ok=True)
                moved = self._move_exrs(item_path, originals_dir)
                if moved == 0:
                    raise RuntimeError("No se encontraron EXR en: %s" % item_path)
                moved_count = _exr_count(originals_dir)
                if moved_count < moved:
                    raise RuntimeError(
                        "Move inseguro: movidos=%d pero Originals tiene %d EXR. originals_dir=%s"
                        % (moved, moved_count, originals_dir)
                    )
                self.signals.log_message.emit(
                    "  %s %d EXR movidos a Originals/%s/" % (self._t(), moved, item_path.name)
                )
                src_dir = originals_dir
                dst_dir = item_path

            else:
                # Sin move_originals: usar carpeta temporal como buffer
                temp_src_dir = item_path / "_tc_temp_src"
                _ensure_safe_child(temp_src_dir, item_path, "_tc_temp_src")
                item_count = _exr_count(item_path)
                temp_count = _exr_count(temp_src_dir)
                self.signals.log_message.emit(
                    "  %s preflight item_path=%s temp_src=%s item_exr_count=%d temp_exr_count=%d"
                    % (self._t(), item_path, temp_src_dir, item_count, temp_count)
                )
                if item_count <= 0 and temp_count <= 0:
                    raise RuntimeError(
                        "Preflight abortado: no hay EXR fuente en item_path ni _tc_temp_src. item_path=%s temp=%s"
                        % (item_path, temp_src_dir)
                    )
                if temp_count > 0:
                    raise RuntimeError(
                        "Preflight abortado: _tc_temp_src ya contiene EXR. Debe resolverse por overwrite antes del worker."
                    )
                temp_src_dir.mkdir(parents=True, exist_ok=True)
                moved = self._move_exrs(item_path, temp_src_dir)
                if moved == 0:
                    raise RuntimeError("No se encontraron EXR en: %s" % item_path)
                src_dir = temp_src_dir
                dst_dir = item_path

            # ── 2. Construir manifest ─────────────────────────────────
            compression        = self.global_opts.get("compression", "dwaa")
            dwa_level          = int(self.global_opts.get("dwa_level", 45))
            resize_filter      = self.global_opts.get("resize_filter", "lanczos3")
            workers            = int(self.global_opts.get("workers", 6))
            exrmetrics_threads = int(self.global_opts.get("exrmetrics_threads", workers))
            cpu_preset         = self.global_opts.get("cpu_preset")
            channels           = self.global_opts.get("channels", "all")
            pixel_aspect_ratio = self.global_opts.get("pixel_aspect_ratio", None)

            manifest = build_manifest_for_sequence(
                item, src_dir, dst_dir, tw, th,
                compression, dwa_level, resize_filter,
                overwrite=True,
                channels=channels,
                pixel_aspect_ratio=pixel_aspect_ratio,
            )
            manifest["workers"] = workers
            manifest["exrmetrics_threads"] = exrmetrics_threads
            has_resize = bool(manifest.get("resize"))
            # hdr_resize y ocio_round_trip NO se fuerzan desde aquí.
            # LGA_EXR_Convert los auto-detecta: si el material es AP0 y hay resize,
            # activa hdr_resize automáticamente sin intervención manual.

            frame_count = len(manifest["tasks"])
            if frame_count == 0:
                raise RuntimeError("No se encontraron frames EXR en: %s" % src_dir)

            # Emitir sequence_started DESPUÉS de preparar archivos y conocer frame_count.
            # La UI puede iniciar la barra de progreso sabiendo dst_dir y total de frames.
            self.signals.sequence_started.emit(row_i, str(dst_dir), frame_count)

            resize_info = (
                "%dx%d · %s" % (tw, th, resize_filter)
                if manifest["resize"] else "resolución original"
            )
            mode_info = " | hdr_mode=auto" if has_resize else ""
            self.signals.log_message.emit(
                "  %s %d frames | %s%s | comp: %s%s | CPU: %s | workers: %d | exrmetrics threads: %d" % (
                    self._t(), frame_count, resize_info, mode_info,
                    compression,
                    (":%d" % dwa_level) if compression.lower().startswith("dwa") else "",
                    cpu_preset or "custom",
                    workers,
                    exrmetrics_threads,
                )
            )

            # ── 3. Escribir manifest a archivo temporal ───────────────
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            ) as tf:
                json.dump(manifest, tf, indent=2)
                manifest_path = Path(tf.name)

            log_json_path = manifest_path.with_suffix(".result.json")

            # ── 4. Ejecutar LGA_EXR_Convert.py ───────────────────────
            python_exe = str(self._python_exe)
            if not self._python_exe.exists():
                # Fallback: Python del PATH (menos confiable en Nuke, pero mejor que nada)
                python_exe = "python"

            cmd = [
                python_exe,
                str(self._convert_script),
                "--manifest", str(manifest_path),
                "--log-json", str(log_json_path),
            ]

            extra = {}
            if platform.system() == "Windows":
                extra["creationflags"] = subprocess.CREATE_NO_WINDOW

            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                **extra,
            )

            # ── 5. Parsear resultado ──────────────────────────────────
            report = None
            if log_json_path.exists():
                try:
                    report = json.loads(log_json_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            if report is None and proc.stdout.strip():
                try:
                    report = json.loads(proc.stdout)
                except Exception:
                    pass
            if report is None:
                stderr_snippet = (proc.stderr or "sin salida")[:300]
                report = {"ok": False, "error": stderr_snippet}

            elapsed   = time.perf_counter() - seq_start
            ok        = bool(report.get("ok", False))
            ok_count  = report.get("ok_count", 0)
            fps_rate  = report.get("fps", 0.0)

            if ok:
                self.signals.log_message.emit(
                    "  %s ✓ OK — %d/%d frames en %.1fs (%.1f fps)" % (
                        self._t(), ok_count, frame_count, elapsed, fps_rate
                    )
                )
            else:
                failed   = report.get("failed_count", frame_count - ok_count)
                err_msg  = report.get("error") or "fallo desconocido"
                self.signals.log_message.emit(
                    "  %s ✗ ERROR — %d frames fallaron: %s" % (
                        self._t(), failed, err_msg[:200]
                    )
                )

            # ── 6. Post-transcode: originales / restauración ──────────
            if ok and not self.test_mode:
                final_count = _exr_count(dst_dir)
                self.signals.log_message.emit(
                    "  %s postflight dst_dir=%s output_exr_count=%d expected_ok_count=%d" % (
                        self._t(), dst_dir, final_count, ok_count
                    )
                )
                if final_count <= 0 or (ok_count and final_count < ok_count):
                    ok = False
                    report["ok"] = False
                    report["error"] = (
                        "Postflight abortado: output incompleto. dst_dir=%s output_exr_count=%d expected=%d"
                        % (dst_dir, final_count, ok_count)
                    )
                    self.signals.log_message.emit("  %s ✗ %s" % (self._t(), report["error"]))

            if ok and not self.test_mode:
                if originals_dir and self.delete_originals:
                    final_count = _exr_count(dst_dir)
                    if final_count <= 0:
                        raise RuntimeError(
                            "Delete Originals bloqueado: output sin EXR. dst_dir=%s originals_dir=%s"
                            % (dst_dir, originals_dir)
                        )
                    _safe_rmtree(originals_dir, originals_dir.parent, "delete Originals after success", ignore_errors=True)
                    self.signals.log_message.emit(
                        "  %s Originals/%s eliminado." % (self._t(), item_path.name)
                    )
                    # Remover la carpeta padre Originals/ si quedó vacía
                    parent_orig = originals_dir.parent
                    try:
                        parent_orig.rmdir()
                    except Exception:
                        pass
                elif temp_src_dir and temp_src_dir.exists():
                    shutil.rmtree(str(temp_src_dir), ignore_errors=True)

            elif not ok and not self.test_mode:
                # Restaurar originales en caso de fallo
                restore_from = originals_dir or temp_src_dir
                if restore_from and restore_from.exists():
                    before_restore = _exr_count(restore_from)
                    restored = self._restore_exrs(restore_from, item_path)
                    item_after_restore = _exr_count(item_path)
                    try:
                        restore_from.rmdir()
                    except Exception:
                        pass
                    if before_restore > 0 and item_after_restore <= 0:
                        raise RuntimeError(
                            "Restore fallido: source=%s item_path=%s restored=%d item_exr_count=%d"
                            % (restore_from, item_path, restored, item_after_restore)
                        )
                    self.signals.log_message.emit(
                        "  %s ↩ %d originales restaurados." % (self._t(), restored)
                    )

            # Limpiar archivos temporales del manifest
            try:
                manifest_path.unlink(missing_ok=True)
                log_json_path.unlink(missing_ok=True)
            except Exception:
                pass

            stats = {
                "ok":              ok,
                "frame_count":     frame_count,
                "ok_count":        ok_count,
                "elapsed_seconds": elapsed,
                "fps":             fps_rate,
            }
            self.signals.sequence_done.emit(row_i, ok, stats)

            return {"row_i": row_i, "ok": ok, "name": seq_name, **stats}

        except Exception as exc:
            elapsed  = time.perf_counter() - seq_start
            err_msg  = str(exc)
            self.signals.log_message.emit(
                "  %s ✗ EXCEPCIÓN: %s" % (self._t(), err_msg)
            )
            # Intentar restaurar si hay carpeta de buffer
            restore_from = originals_dir or temp_src_dir
            if restore_from and restore_from.exists() and not self.test_mode:
                before_restore = _exr_count(restore_from)
                restored = self._restore_exrs(restore_from, item_path)
                item_after_restore = _exr_count(item_path)
                try:
                    restore_from.rmdir()
                except Exception:
                    pass
                self.signals.log_message.emit(
                    "  %s ↩ %d originales restaurados (tras excepción). item_exr_count=%d source_before=%d" % (
                        self._t(), restored, item_after_restore, before_restore
                    )
                )
            stats = {"ok": False, "error": err_msg, "elapsed_seconds": elapsed,
                     "frame_count": 0, "ok_count": 0, "fps": 0.0}
            self.signals.sequence_done.emit(row_i, False, stats)
            return {"row_i": row_i, "ok": False, "name": seq_name, **stats}

    # ── File helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _move_exrs(src_dir: Path, dst_dir: Path) -> int:
        """
        Mueve todos los .exr de src_dir a dst_dir.

        Usa os.rename() cuando es posible (misma unidad — operación atómica a nivel OS,
        libera el GIL). Si falla (e.g. unidades distintas), usa shutil.move() como
        fallback.

        Returns:
            Número de archivos movidos.
        """
        import os
        src_path = Path(src_dir)
        dst_path = Path(dst_dir)
        dst_path.mkdir(parents=True, exist_ok=True)
        moved = 0
        for f in sorted(src_path.glob("*.exr")):
            dst = dst_path / f.name
            try:
                os.rename(str(f), str(dst))
            except OSError:
                shutil.move(str(f), str(dst))
            moved += 1
        return moved

    @staticmethod
    def _restore_exrs(src_dir: Path, dst_dir: Path) -> int:
        """
        Restaura EXR fuente a dst_dir.

        Si hay outputs parciales en dst_dir, los elimina solo despues de confirmar que
        src_dir contiene EXR. Esto evita que un fallo del conversor bloquee el restore
        por archivos con el mismo nombre.
        """
        src_path = Path(src_dir)
        dst_path = Path(dst_dir)
        source_count = _exr_count(src_path)
        if source_count <= 0:
            return 0
        dst_path.mkdir(parents=True, exist_ok=True)
        for f in list(dst_path.glob("*.exr")):
            _safe_remove_exr(f, dst_path, "partial output cleanup before restore")
        restored = TranscodeWorker._move_exrs(src_path, dst_path)
        restored_count = _exr_count(dst_path)
        if restored_count < source_count:
            raise RuntimeError(
                "Restore incompleto: source=%s dst=%s restored_count=%d expected=%d"
                % (src_path, dst_path, restored_count, source_count)
            )
        return restored
