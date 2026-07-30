"""
____________________________________________________________________

  LGA_NKS_FileManager_DownloadClip v1.02 | Lega

  Descarga el/los clip(s) seleccionado(s) desde Wasabi S3 usando
  FileManager CLI. A diferencia de "Download Shot", descarga solo el
  media del clip, no la carpeta entera del shot.

  - Archivo de video unico (.mov, .mp4)  -> FileManager --download-file <archivo>
  - Secuencia de imagenes (%04d.exr ...) -> FileManager --download <carpeta de la secuencia>
  Todos los clips seleccionados se envian en una sola llamada al CLI.

  Pasa --notify-completion para que FileManager escriba un marcador al terminar
  cada descarga; el watcher LGA_NKS_DownloadClip_Watcher.py lo detecta y reconecta
  el clip offline automaticamente.

  Modo latest y ramas: antes se delegaba en --download-latest, que resuelve el
  maximo global y por lo tanto cruza de rama. Ahora el modo latest lista Wasabi
  desde aca (LGA_NKS_S3VersionLister), detecta ramas y si hay mas de una abre un
  dialogo para elegir cual bajar; despues manda rutas explicitas con los flags
  normales. FileManager no cambia.

  v1.02: Modo latest con ramas. Listado de Wasabi en hilo secundario, dialogo de
         seleccion de rama con teclas numericas e intents para que el watcher
         suba el clip a la version que realmente se bajo.

  v1.01: migra al helper central FileManagerS3 + --context studio/client.
         Conserva --notify-completion y modo latest.

  v1.00: Soporta modo latest (Shift+Click) para descargar la version mas nueva
         via CLI de FileManager (--download-latest / --download-latest-file).

  v0.04: Agrega --notify-completion para reconexion automatica del clip al terminar.

  v0.03: Implementa la descarga real via FileManager CLI.
         Distingue archivo unico (singleFile) vs secuencia.

  v0.02: Usa el Metodo 1 (seleccion pura de clips, sin playhead).
         Soporta uno o varios clips seleccionados a la vez.

  v0.01: Solo imprime via debug_print:
        - Nombre del clip
        - Ruta del clip
        - Estado online/offline del media
____________________________________________________________________
"""

from pathlib import Path
import sys
import os
import subprocess
import logging
import queue
from logging.handlers import QueueHandler, QueueListener
import datetime
import time
import traceback

# Agregar ruta de shared modules
# Qt en None por defecto: si el import falla, el modulo tiene que seguir
# cargando (las clases Qt quedan sin definir y el modo latest cae al flujo
# viejo), como hacen las otras tools del panel.
QtCore = None
QtWidgets = None
Qt = None

utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists():
    if str(utils_path) not in sys.path:
        sys.path.insert(0, str(utils_path))
    from LGA_NKS_Shared.LGA_NKS_FileManagerLauncher import (
        build_filemanager_command,
        resolve_context_mode,
    )
    from LGA_NKS_BranchDownloadPlan import (
        SELECTION_ALL,
        aggregate_branch_options,
        build_clip_branches,
        option_summary,
        plan_downloads,
        prune_intents,
        write_intents,
    )
    from LGA_NKS_S3VersionLister import list_family_versions
    from LGA_NKS_VersionBranching import extract_version_number, format_version

    # Los modulos con Qt van en su propio try: si Qt no esta, el modulo tiene
    # que seguir cargando y el modo latest cae al --download-latest de siempre.
    try:
        from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtCore, QtWidgets, Qt
        from LGA_NKS_VersionBranchesUI import (
            BRANCH_COLOR_CONFLICT,
            BRANCH_COLOR_NEUTRAL,
            branch_pixmap,
            tooltip as branch_tooltip_text,
        )
    except ImportError as _qt_import_error:
        print(f"[DownloadClip] Qt no disponible, modo latest sin ramas: {_qt_import_error}")
        QtCore = None
        QtWidgets = None
        Qt = None

# Variables globales de logging
DEBUG = False
DEBUG_CONSOLE = False
DEBUG_LOG = True
script_start_time = None
debug_log_listener = None
debug_logger = None
_log_file_path_resolved = None

# Variable de desarrollo para cambiar la ruta del ejecutable
Desarrollo = True


def get_notify_dir():
    """Carpeta donde FileManager escribe los marcadores de finalizacion de descarga.

    Es vigilada por LGA_NKS_DownloadClip_Watcher.py. Vive dentro de Startup/logs/.
    """
    notify_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "logs", "download_clip_done"
    )
    return os.path.abspath(notify_dir)


def get_intent_dir():
    """Carpeta de intents: que hacer con el clip cuando termine cada descarga.

    La escribe este script y la lee LGA_NKS_DownloadClip_Watcher.py. Debe
    coincidir con get_intent_dir() de ese modulo.
    """
    intent_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "logs", "download_clip_intent"
    )
    return os.path.abspath(intent_dir)


class RelativeTimeFormatter(logging.Formatter):
    """Formatter con hora absoluta y tiempo relativo desde el inicio."""

    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created

        relative_time = record.created - script_start_time
        record.relative_time = f"{relative_time:.3f}s"
        return super().format(record)


def setup_debug_logging(script_name="FileManager_DownloadClip"):
    """Configura el logging para escribir SOLO en archivo (limpieza diaria)."""
    global debug_log_listener, _log_file_path_resolved

    log_filename = f"debugPy_{script_name}.log"
    log_file_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "logs", log_filename
    )
    log_file_path = os.path.abspath(log_file_path)
    _log_file_path_resolved = log_file_path

    print(f"[DownloadClip] log target: {log_file_path}")
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

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
            print(f"[DownloadClip] Warning: no se pudo resetear el log: {e}")

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


# Setup del logger con captura de cualquier fallo
try:
    debug_logger = setup_debug_logging(script_name="FileManager_DownloadClip")
    print("[DownloadClip] logger inicializado OK")
except Exception as _e:
    print(f"[DownloadClip] FALLO al inicializar logger: {_e}")
    traceback.print_exc()


def debug_print(*message, level="info"):
    global script_start_time

    msg = " ".join(str(arg) for arg in message)

    if DEBUG and DEBUG_LOG and debug_logger is not None:
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


def _get_selected_clips():
    """Obtiene los clips realmente seleccionados en el timeline (uno o varios).

    Usa el Metodo 1 (seleccion pura, sin playhead, sin filtro de track) via el
    helper compartido get_selected_clips(). Cae a seleccion directa si falla.
    """
    try:
        utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
        if utils_path.exists() and str(utils_path) not in sys.path:
            sys.path.insert(0, str(utils_path))
        from LGA_NKS_Shared.LGA_NKS_GetClip import get_selected_clips
        return get_selected_clips()
    except Exception as e:
        debug_print(
            f"Fallback: no se pudo usar get_selected_clips: {e}", level="warning"
        )

    # Fallback: tomar la seleccion directamente del timeline
    try:
        import hiero.ui
        import hiero.core

        seq = hiero.ui.activeSequence()
        if seq is None:
            debug_print("No hay secuencia activa", level="warning")
            return []
        te = hiero.ui.getTimelineEditor(seq)
        sel = te.selection() if te else []
        return [
            item
            for item in sel
            if not isinstance(item, hiero.core.EffectTrackItem)
        ]
    except Exception as e:
        debug_print(f"Fallback de seleccion fallo: {e}", level="error")
    return []


def _inspect_clip(clip):
    """Devuelve un dict con la info del clip o None si no se pudo resolver.

    Claves del dict:
      - name (str)
      - file_path (str): ruta del media (con token de secuencia si aplica)
      - is_single_file (bool): True si es archivo unico, False si es secuencia
      - online (bool|None): estado del media
    """
    try:
        clip_name = clip.name()
    except Exception as e:
        clip_name = f"<error: {e}>"

    try:
        media_source = clip.source().mediaSource()
    except Exception as e:
        debug_print(f"No se pudo obtener mediaSource: {e}", level="error")
        return None

    file_path = None
    try:
        fileinfos = media_source.fileinfos()
        if fileinfos:
            file_path = fileinfos[0].filename()
    except Exception as e:
        debug_print(f"No se pudieron obtener fileinfos: {e}", level="error")

    if not file_path:
        debug_print(f"Clip '{clip_name}' sin ruta de media", level="warning")
        return None

    # singleFile() True -> archivo unico (.mov); False -> secuencia de imagenes
    try:
        is_single_file = bool(media_source.singleFile())
    except Exception as e:
        debug_print(
            f"No se pudo determinar singleFile(): {e} - se asume secuencia",
            level="warning",
        )
        is_single_file = False

    try:
        online = bool(media_source.isMediaPresent())
    except Exception as e:
        debug_print(
            f"No se pudo determinar online/offline: {e}", level="warning"
        )
        online = None

    return {
        "name": clip_name,
        "file_path": file_path,
        "is_single_file": is_single_file,
        "online": online,
    }


def _path_has_vfx_root(path):
    """True si alguna parte de la ruta empieza con 'VFX-' (requisito del CLI)."""
    parts = os.path.normpath(path).replace("\\", "/").split("/")
    return any(p.upper().startswith("VFX-") for p in parts)


def _local_versions_for_clip(clip):
    """Versiones que Hiero ya conoce del clip, sin escanear disco.

    No corre VersionScanner a proposito: alcanza para saber que ramas
    tenemos bajadas y evita el costo de un escaneo por clip.
    """
    try:
        bin_item = clip.source().binItem()
    except Exception as e:
        debug_print(f"No se pudo obtener binItem: {e}", level="warning")
        return []
    if not bin_item:
        return []
    try:
        return [extract_version_number(v.name()) for v in bin_item.items()]
    except Exception as e:
        debug_print(f"No se pudieron listar versiones locales: {e}", level="warning")
        return []


# Las clases Qt se definen solo si el adapter cargo: sin Qt el modulo
# igual tiene que importarse (el modo latest cae al flujo viejo), igual
# que hace LGA_NKS_DownloadClip_Watcher.py con su QObject.
if QtCore is not None:

    class BranchScanSignals(QtCore.QObject):
        """Señales del worker de listado de Wasabi."""

        finished = QtCore.Signal(object)  # lista de entries con 'versions' o 'error'


    class BranchScanWorker(QtCore.QRunnable):
        """Lista Wasabi para cada clip en hilo secundario.

        La UI de Hiero no se puede bloquear: el listado es red y va afuera del
        hilo principal; el resultado vuelve por señal y el dialogo se abre alla.
        """

        def __init__(self, entries):
            super(BranchScanWorker, self).__init__()
            self.entries = entries
            self.signals = BranchScanSignals()

        @QtCore.Slot()
        def run(self):
            for entry in self.entries:
                try:
                    result = list_family_versions(
                        entry["target_local"], entry["is_single_file"]
                    )
                except Exception as exc:
                    result = {"ok": False, "error": str(exc)}

                if result.get("ok"):
                    entry["versions"] = result.get("versions") or {}
                    entry["target_version"] = result.get("target_version")
                    entry["parent_local"] = result.get("parent_local")
                    entry["error"] = None
                else:
                    entry["versions"] = {}
                    entry["error"] = result.get("error") or "unknown error"
            self.signals.finished.emit(self.entries)


    class BranchDownloadDialog(QtWidgets.QDialog):
        """Elegir que rama bajar. Se responde con el mouse o con el numero."""

        def __init__(self, options, clip_names, parent=None):
            super(BranchDownloadDialog, self).__init__(parent)
            self.selection = None
            self._shortcuts = {}

            self.setWindowTitle("Download Clip - Version Branches")
            self.setModal(True)

            layout = QtWidgets.QVBoxLayout(self)

            news_count = sum(1 for option in options if option.get("has_news"))
            title = QtWidgets.QLabel()
            title.setTextFormat(Qt.RichText)
            title.setText(
                "<b>New versions in {0} of {1} branches</b>".format(
                    news_count, len(options)
                )
                if news_count
                else "<b>{0} version branches found</b>".format(len(options))
            )
            layout.addWidget(title)

            icon = branch_pixmap(BRANCH_COLOR_CONFLICT if news_count else BRANCH_COLOR_NEUTRAL)
            subtitle_row = QtWidgets.QHBoxLayout()
            if icon is not None:
                icon_label = QtWidgets.QLabel()
                icon_label.setPixmap(icon)
                subtitle_row.addWidget(icon_label)
            subtitle = QtWidgets.QLabel(", ".join(clip_names[:3]) + ("..." if len(clip_names) > 3 else ""))
            subtitle.setStyleSheet("color: #9c9c9c;")
            subtitle_row.addWidget(subtitle)
            subtitle_row.addStretch(1)
            layout.addLayout(subtitle_row)
            self.setToolTip(branch_tooltip_text("download_pick_branch"))

            # Opcion 1 = todas; despues una por rama, en el orden de las ramas.
            all_heads = sorted(
                {
                    version
                    for option in options
                    for _index, version, _name in option.get("heads") or []
                }
            )
            self._add_option_button(
                layout,
                1,
                "All branches",
                "-> " + ", ".join(format_version(version) for version in all_heads),
                SELECTION_ALL,
            )
            for position, option in enumerate(options, start=2):
                detail = "-> {0}".format(option_summary(option))
                if option.get("is_current_branch"):
                    detail += "   (this clip)"
                if not option.get("has_news"):
                    detail += "   (already local)"
                self._add_option_button(
                    layout,
                    position,
                    "Branch {0}".format(option["label"]),
                    detail,
                    option["label"],
                )

            cancel = QtWidgets.QPushButton("Cancel  [ESC]")
            cancel.clicked.connect(self.reject)
            layout.addWidget(cancel)

        def _add_option_button(self, layout, number, label, detail, selection_value):
            button = QtWidgets.QPushButton("{0}   {1}   {2}".format(number, label, detail))
            button.setStyleSheet("text-align: left; padding: 6px;")
            button.clicked.connect(lambda _checked=False, value=selection_value: self._choose(value))
            layout.addWidget(button)
            self._shortcuts[number] = selection_value
            if number == 1:
                button.setDefault(True)

        def _choose(self, value):
            self.selection = value
            debug_print(f"Rama elegida en el dialogo: {value}")
            self.accept()

        def keyPressEvent(self, event):
            """Teclas 1..9 eligen la opcion; ESC cancela."""
            # int() explicito: en Qt6 las teclas son enums y conviene no
            # depender de como se comparan/restan contra enteros.
            key = int(event.key())
            first = int(Qt.Key_1)
            if first <= key <= int(Qt.Key_9):
                number = key - first + 1
                if number in self._shortcuts:
                    self._choose(self._shortcuts[number])
                    return
            if key == int(Qt.Key_Escape):
                self.reject()
                return
            super(BranchDownloadDialog, self).keyPressEvent(event)

        def get_selection(self):
            return self.selection


def _dedupe_preserve_order(paths):
    """Devuelve la lista sin duplicados preservando el orden de aparicion."""
    seen = set()
    out = []
    for p in paths:
        key = os.path.normpath(str(p)).replace("\\", "/").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def build_filemanager_cmd(folder_paths, file_paths, notify_dir=None, download_latest=False):
    """Construye el comando del CLI para modo normal o latest.

    - Modo normal:
      --download (carpetas) y --download-file (archivos)
    - Modo latest:
      --download-latest (carpetas) y --download-latest-file (archivos)

    Si notify_dir esta dado, agrega --notify-completion para que FileManager
    escriba un marcador al terminar cada descarga.
    Devuelve la lista de argumentos o None si no se puede construir.
    """
    folder_paths = _dedupe_preserve_order(folder_paths)
    file_paths = _dedupe_preserve_order(file_paths)

    folder_flag = "--download-latest" if download_latest else "--download"
    file_flag = "--download-latest-file" if download_latest else "--download-file"

    cli_args = []
    if folder_paths:
        cli_args.append(folder_flag)
        cli_args.extend(folder_paths)
    if file_paths:
        cli_args.append(file_flag)
        cli_args.extend(file_paths)

    if not cli_args:
        return None

    if notify_dir:
        cli_args.append("--notify-completion")
        cli_args.append(notify_dir)

    try:
        context_mode = resolve_context_mode()
        cmd = build_filemanager_command(
            cli_args,
            desarrollo=Desarrollo,
            script_dir=Path(__file__).parent,
            context_mode=context_mode,
        )
        debug_print(f"Contexto FileManager resuelto: {context_mode}")
        return cmd
    except Exception as exc:
        debug_print(
            f"No se pudo construir comando de FileManagerS3: {exc}",
            level="error",
        )
        return None


def _ensure_notify_dir():
    """Crea (si falta) y devuelve la carpeta de marcadores."""
    notify_dir = get_notify_dir()
    try:
        os.makedirs(notify_dir, exist_ok=True)
    except Exception as e:
        debug_print(
            f"No se pudo crear la carpeta de notificacion: {e}", level="warning"
        )
    debug_print(f"Notify dir: {notify_dir}")
    return notify_dir


def _launch_filemanager(folder_paths, file_paths, notify_dir, download_latest, mode_label):
    """Arma y lanza el comando. Devuelve True si se pudo lanzar."""
    if not folder_paths and not file_paths:
        return False

    cmd = build_filemanager_cmd(
        folder_paths, file_paths, notify_dir, download_latest=download_latest
    )
    if not cmd:
        debug_print("No se pudo construir el comando de FileManager", level="error")
        return False

    debug_print(f"Ejecutando: {' '.join(cmd)}")
    try:
        subprocess.Popen(cmd, shell=False)
        debug_print(
            f"FileManager iniciado ({mode_label}): {len(folder_paths)} secuencia(s), "
            f"{len(file_paths)} archivo(s)"
        )
        return True
    except Exception as cmd_error:
        debug_print(f"Error al ejecutar FileManager: {cmd_error}", level="error")
        return False


def _collect_clip_entries(clips):
    """Datos de cada clip seleccionado que sirven para las dos rutas de descarga."""
    entries = []
    total = len(clips)
    for index, clip in enumerate(clips, start=1):
        debug_print(f"--- Clip {index}/{total} ---")
        info = _inspect_clip(clip)
        if info is None:
            continue

        debug_print(f"Nombre del clip: {info['name']}")
        debug_print(f"Ruta del clip: {info['file_path']}")
        if info["online"] is None:
            debug_print("Estado del media: DESCONOCIDO")
        else:
            debug_print(
                f"Estado del media: {'ONLINE' if info['online'] else 'OFFLINE'}"
            )

        file_path = info["file_path"]
        if not _path_has_vfx_root(file_path):
            debug_print(
                f"Ruta sin raiz 'VFX-', se omite (FileManager la rechazaria): {file_path}",
                level="warning",
            )
            continue

        # El "target" es la entidad versionada: el archivo para media unico,
        # la carpeta de la secuencia para EXR. Es la misma distincion que hace
        # FileManager al resolver --download-latest.
        target_local = (
            file_path if info["is_single_file"] else os.path.dirname(file_path)
        )
        entries.append(
            {
                "clip": clip,
                "clip_name": info["name"],
                "file_path": file_path,
                "is_single_file": info["is_single_file"],
                "target_local": target_local,
                "local_versions": _local_versions_for_clip(clip),
            }
        )
    return entries


if QtCore is not None:

    class BranchScanReceiver(QtCore.QObject):
        """Recibe el resultado del worker EN EL HILO PRINCIPAL.

        Conectar la señal directamente a una funcion suelta no alcanza: sin un
        QObject receptor Qt no sabe a que hilo pertenece el destino y ejecuta el
        slot en el hilo que emite, o sea el dialogo se crearia en el hilo
        secundario. Este objeto se instancia en el hilo principal, asi que la
        conexion queda queued y la UI abre donde debe.
        """

        @QtCore.Slot(object)
        def on_finished(self, entries):
            _apply_branch_scan(entries)


# Referencias vivas mientras corre el listado: sin esto el garbage collector
# puede matar el QObject de señales o el receptor antes de que llegue el
# resultado, y la descarga nunca se dispara.
_active_branch_worker = None
_active_branch_receiver = None


def _download_current_version(entries):
    """Modo normal: baja la version que el clip tiene puesta ahora."""
    folder_paths = []
    file_paths = []
    for entry in entries:
        if entry["is_single_file"]:
            debug_print("Tipo: archivo unico -> --download-file")
            file_paths.append(entry["file_path"])
        else:
            debug_print(f"Tipo: secuencia -> --download carpeta: {entry['target_local']}")
            folder_paths.append(entry["target_local"])

    notify_dir = _ensure_notify_dir()
    _launch_filemanager(folder_paths, file_paths, notify_dir, False, "NORMAL")


def _download_latest_legacy(entries, reason):
    """Fallback: delega en --download-latest de FileManager (maximo global).

    Se usa solo cuando no se pudo listar Wasabi (sin credenciales, sin red,
    ruta que no resuelve bucket). Es el comportamiento anterior: puede cruzar
    de rama, asi que queda logueado con el motivo.
    """
    debug_print(
        f"Fallback a --download-latest para {len(entries)} clip(s): {reason}",
        level="warning",
    )
    folder_paths = []
    file_paths = []
    for entry in entries:
        if entry["is_single_file"]:
            file_paths.append(entry["file_path"])
        else:
            folder_paths.append(entry["target_local"])

    notify_dir = _ensure_notify_dir()
    _launch_filemanager(folder_paths, file_paths, notify_dir, True, "LATEST-FALLBACK")


def _apply_branch_scan(entries):
    """Con el listado de Wasabi ya hecho: decide, pregunta y lanza.

    Corre en el hilo principal (llega por señal del worker) porque abre un
    dialogo Qt y toca la seleccion del usuario.
    """
    try:
        scanned = [entry for entry in entries if not entry.get("error")]
        failed = [entry for entry in entries if entry.get("error")]

        for entry in failed:
            debug_print(
                f"No se pudo listar ramas de '{entry['clip_name']}': {entry['error']}",
                level="warning",
            )

        if scanned:
            for entry in scanned:
                entry["branches"] = build_clip_branches(entry)
                debug_print(
                    f"'{entry['clip_name']}' ramas: "
                    + " | ".join(
                        "{0}-> Wasabi {1} / local {2}".format(
                            branch["label"],
                            format_version(branch["remote_head"])
                            if branch["remote_head"] is not None
                            else "-",
                            format_version(branch["local_head"])
                            if branch["local_head"] is not None
                            else "-",
                        )
                        for branch in entry["branches"]
                    )
                )

            options = aggregate_branch_options(scanned)
            if len(options) <= 1:
                # Una sola rama: es el caso de siempre, sin preguntar nada.
                selection = SELECTION_ALL
                debug_print("Una sola rama detectada: se baja su cabeza sin preguntar")
            else:
                dialog = BranchDownloadDialog(
                    options, [entry["clip_name"] for entry in scanned]
                )
                dialog.exec_()
                selection = dialog.get_selection()
                if selection is None:
                    debug_print("Usuario cancelo el dialogo de ramas")
                    return

            plan = plan_downloads(scanned, selection)
            for skipped in plan["skipped"]:
                debug_print(
                    f"'{skipped}' no tiene la rama {selection}: se saltea",
                    level="warning",
                )

            if plan["folder_paths"] or plan["file_paths"]:
                intent_dir = get_intent_dir()
                try:
                    prune_intents(intent_dir)
                    write_intents(intent_dir, plan["intents"])
                    debug_print(
                        f"Intents escritos en {intent_dir}: {len(plan['intents'])}"
                    )
                except Exception as intent_error:
                    # Sin intents la descarga igual sirve: el watcher se limita
                    # a reconectar y el clip queda en su version actual.
                    debug_print(
                        f"No se pudieron escribir los intents: {intent_error}",
                        level="warning",
                    )

                notify_dir = _ensure_notify_dir()
                _launch_filemanager(
                    plan["folder_paths"],
                    plan["file_paths"],
                    notify_dir,
                    False,
                    f"BRANCH:{selection}",
                )
            else:
                debug_print("El plan de ramas no dejo nada para descargar", level="warning")

        if failed:
            _download_latest_legacy(failed, "listado de Wasabi fallido")

    except Exception as e:
        debug_print(f"Error aplicando el plan de ramas: {e}", level="error")
        debug_print(traceback.format_exc(), level="error")


def main(download_latest=False):
    """Descarga el/los clip(s) seleccionado(s) desde Wasabi S3."""
    mode_label = "LATEST" if download_latest else "NORMAL"
    debug_print(f"=== FILEMANAGER DOWNLOAD CLIP ({mode_label}) ===")
    debug_print(f"log file: {_log_file_path_resolved}")

    global _active_branch_worker, _active_branch_receiver

    try:
        clips = _get_selected_clips()

        if not clips:
            debug_print(
                "No hay clips seleccionados en el timeline", level="warning"
            )
            return

        debug_print(f"Clips seleccionados: {len(clips)}")
        entries = _collect_clip_entries(clips)
        if not entries:
            debug_print("No hay nada para descargar", level="warning")
            return

        if not download_latest:
            _download_current_version(entries)
            return

        if QtCore is None:
            # Sin Qt no hay worker ni dialogo posible: se delega en el
            # --download-latest de FileManager como antes.
            _download_latest_legacy(entries, "Qt no disponible en este entorno")
            return

        # Modo latest: primero hay que saber que ramas hay en Wasabi. El
        # listado es red, asi que va a un hilo secundario y el dialogo se
        # abre cuando vuelve el resultado.
        receiver = BranchScanReceiver()
        worker = BranchScanWorker(entries)
        worker.signals.finished.connect(receiver.on_finished)
        _active_branch_receiver = receiver
        _active_branch_worker = worker
        QtCore.QThreadPool.globalInstance().start(worker)
        debug_print("Listado de ramas en Wasabi lanzado en hilo secundario")

    except Exception as e:
        debug_print(f"Error al procesar los clips: {e}", level="error")
        debug_print(traceback.format_exc(), level="error")


if __name__ == "__main__":
    latest_arg = any(
        arg in ("--latest", "--download-latest", "--download-latest-file")
        for arg in sys.argv[1:]
    )
    main(download_latest=latest_arg)
