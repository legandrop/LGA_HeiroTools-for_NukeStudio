"""
____________________________________________________________________

  LGA_Contact_Sheet_OpenInNukeX v0.04 | Lega

  Copia los clips seleccionados en Hiero/Nuke Studio y le pide a NukeX,
  por el puerto de LGA_OpenInNukeX, que pegue el contenido del clipboard.

  v0.04 - show_message pasa al helper LGA_NKS_MessageBox con el estilo del pack
  v0.03 - Fix copy: key event Ctrl+C al QAbstractScrollArea del timeline
  v0.02 - Logging system + multiple approaches para trigger_hiero_copy
____________________________________________________________________

"""

import socket
import logging
import queue
import os
import time
import traceback
import threading
from logging.handlers import QueueHandler, QueueListener

import hiero.core
import hiero.ui
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtCore, QtGui
from LGA_NKS_Shared.LGA_NKS_MessageBox import styled_message_box


HOST = "localhost"
PORT = 54325

DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True

script_start_time = None
debug_log_listener = None
_debug_file_handler = None


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

class RelativeTimeFormatter(logging.Formatter):
    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created
        relative_time = record.created - script_start_time
        record.relative_time = f"{relative_time:.3f}s"
        return super().format(record)


def setup_debug_logging(script_name="ContactSheet"):
    global debug_log_listener, _debug_file_handler

    log_filename = f"debugPy_{script_name}.log"
    log_file_path = os.path.join(
        os.path.dirname(__file__), "..", "logs", log_filename
    )
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    try:
        with open(log_file_path, "w", encoding="utf-8") as f:
            f.write(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    except Exception as e:
        print(f"Warning: No se pudo limpiar el log: {e}")

    logger_name = f"{script_name.lower()}_logger"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:
        logger.handlers.clear()

    _debug_file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    _debug_file_handler.setLevel(logging.DEBUG)
    formatter = RelativeTimeFormatter("[%(relative_time)s] %(message)s")
    _debug_file_handler.setFormatter(formatter)

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
        log_queue, _debug_file_handler, respect_handler_level=True
    )
    debug_log_listener.daemon = True
    debug_log_listener.start()

    return logger


debug_logger = setup_debug_logging(script_name="ContactSheet")


def debug_print(*message, level="info"):
    global script_start_time
    msg = " ".join(str(arg) for arg in message)

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


def _flush_log():
    try:
        if debug_log_listener and hasattr(debug_log_listener, "queue"):
            deadline = time.time() + 0.5
            while not debug_log_listener.queue.empty() and time.time() < deadline:
                time.sleep(0.005)
        if _debug_file_handler:
            _debug_file_handler.flush()
            if hasattr(_debug_file_handler, "stream"):
                os.fsync(_debug_file_handler.stream.fileno())
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------

def show_message(title, message):
    # Cartel estandar con el estilo del pack (LGA_NKS_MessageBox)
    msg_box = styled_message_box(None, title, message)
    msg_box.setTextFormat(QtCore.Qt.TextFormat.PlainText)
    msg_box.setText(message)
    msg_box.setStandardButtons(QtWidgets.QMessageBox.Ok)
    msg_box.exec_()


def get_selected_clips():
    debug_print("=== get_selected_clips ===")
    seq = hiero.ui.activeSequence()
    if not seq:
        debug_print("No hay secuencia activa", level="warning")
        show_message("Contact Sheet", "No hay una secuencia activa.")
        return []

    timeline_editor = hiero.ui.getTimelineEditor(seq)
    if not timeline_editor:
        debug_print("No se pudo obtener el Timeline Editor", level="warning")
        show_message("Contact Sheet", "No se pudo obtener el Timeline Editor.")
        return []

    selected_items = timeline_editor.selection()
    selected_clips = [
        item
        for item in selected_items
        if not isinstance(item, hiero.core.EffectTrackItem)
    ]

    debug_print(f"Items totales: {len(selected_items)}  Clips (sin efectos): {len(selected_clips)}")

    if not selected_clips:
        debug_print("No hay clips seleccionados", level="warning")
        show_message("Contact Sheet", "No hay clips seleccionados.")
        return []

    return selected_clips


def _get_clipboard_formats():
    """Lee formatos MIME actuales. Mantiene referencia para evitar GC crash de PySide2."""
    app = QtWidgets.QApplication.instance()
    if not app:
        return set()
    clipboard = app.clipboard()
    mime = clipboard.mimeData()
    if mime is None:
        return set()
    try:
        return set(list(mime.formats()))
    except RuntimeError:
        return set()


def trigger_hiero_copy(timeline_editor):
    """
    Copia los clips seleccionados al clipboard usando un Ctrl+C key event
    dirigido al QAbstractScrollArea interno del timeline de Hiero.

    Descubrimiento (v0.03): ui.TimelineEditor NO es un QWidget. Su .window()
    devuelve la ventana principal de Hiero. Tras activarla y llamar setFocus(),
    el focusWidget() pasa a ser el QAbstractScrollArea interno del timeline,
    que es quien maneja los key events. Enviarle Ctrl+C produce el formato
    correcto en el clipboard: {'x-foundry/x-clips', 'text/x-nuke-script'}.
    """
    debug_print("=== trigger_hiero_copy ===")

    app = QtWidgets.QApplication.instance()
    if not app:
        raise RuntimeError("No se pudo obtener la instancia de QApplication.")

    main_window = timeline_editor.window()
    if not main_window:
        raise RuntimeError("No se pudo obtener la ventana principal de Hiero.")

    debug_print(f"main_window tipo: {type(main_window).__name__}")
    debug_print(f"focusWidget antes: {type(app.focusWidget()).__name__ if app.focusWidget() else 'None'}")

    # Activar la ventana principal para que Qt redirija el foco al timeline
    main_window.raise_()
    main_window.activateWindow()
    main_window.setFocus()
    app.processEvents()

    focus_widget = app.focusWidget()
    debug_print(f"focusWidget despues de activateWindow: {type(focus_widget).__name__ if focus_widget else 'None'}")

    if focus_widget is None:
        raise RuntimeError(
            "No hay focusWidget activo tras activar la ventana de Hiero."
        )

    formats_antes = _get_clipboard_formats()
    debug_print(f"Formatos clipboard antes del copy: {formats_antes}")

    key_press = QtGui.QKeyEvent(
        QtCore.QEvent.KeyPress,
        QtCore.Qt.Key_C,
        QtCore.Qt.ControlModifier,
        ""
    )
    key_release = QtGui.QKeyEvent(
        QtCore.QEvent.KeyRelease,
        QtCore.Qt.Key_C,
        QtCore.Qt.ControlModifier,
        ""
    )

    app.sendEvent(focus_widget, key_press)
    app.sendEvent(focus_widget, key_release)
    app.processEvents()

    formats_despues = _get_clipboard_formats()
    debug_print(f"Formatos clipboard despues del copy: {formats_despues}")

    hiero_formats = {"x-foundry/x-clips", "text/x-nuke-script"}
    if not hiero_formats.intersection(formats_despues):
        raise RuntimeError(
            f"El clipboard no tiene formatos de Hiero tras el Ctrl+C.\n"
            f"focusWidget target: {type(focus_widget).__name__}\n"
            f"Formatos obtenidos: {formats_despues}"
        )

    debug_print(f"Copy exitoso. Formatos Hiero en clipboard: {hiero_formats.intersection(formats_despues)}")


def _ping_nukex():
    """Verifica que NukeX este disponible. Bloquea hasta 10s. Lanza RuntimeError si falla."""
    debug_print(f"Ping a {HOST}:{PORT}...")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(10)
        s.connect((HOST, PORT))
        s.sendall("ping".encode())
        response = s.recv(1024).decode()
    debug_print(f"Respuesta ping: '{response}'")
    if "pong" not in response:
        raise RuntimeError("NukeX no respondio al ping de OpenInNukeX.")


def _send_paste_in_thread():
    """
    Envia paste_clipboard a NukeX en un thread separado para no bloquear
    el hilo principal de Hiero mientras NukeX ejecuta nodePaste (~10s+).
    """
    def _worker():
        try:
            debug_print("Thread paste: conectando...")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(120)
                s.connect((HOST, PORT))
                s.sendall("paste_clipboard".encode())
                response = s.recv(4096).decode()
            debug_print(f"Thread paste: respuesta recibida: '{response[:80]}'")
            if "successfully" not in response.lower():
                debug_print(f"Thread paste: NukeX no confirmo el paste: {response.strip()}", level="warning")
            else:
                debug_print("Thread paste: paste_clipboard completado exitosamente")
        except (socket.timeout, ConnectionRefusedError) as e:
            debug_print(f"Thread paste: error de conexion: {e}", level="error")
        except Exception as e:
            debug_print(f"Thread paste: error inesperado: {e}", level="error")
            debug_print(traceback.format_exc(), level="error")
        finally:
            _flush_log()

    t = threading.Thread(target=_worker, name="ContactSheet-paste", daemon=True)
    t.start()
    debug_print("Thread paste lanzado, Hiero continua sin bloqueo")


def main():
    debug_print("=== LGA_Contact_Sheet_OpenInNukeX v0.03: main ===")
    _flush_log()

    seq = hiero.ui.activeSequence()
    if not seq:
        show_message("Contact Sheet", "No hay una secuencia activa.")
        return

    timeline_editor = hiero.ui.getTimelineEditor(seq)
    if not timeline_editor:
        show_message("Contact Sheet", "No se pudo obtener el Timeline Editor.")
        return

    selected_items = timeline_editor.selection()
    selected_clips = [
        item for item in selected_items
        if not isinstance(item, hiero.core.EffectTrackItem)
    ]

    debug_print(f"Clips seleccionados: {len(selected_clips)}")

    if not selected_clips:
        show_message("Contact Sheet", "No hay clips seleccionados.")
        return

    try:
        trigger_hiero_copy(timeline_editor)
        _flush_log()
        # Ping en main thread (rapido, <10s) para validar que NukeX este disponible
        # antes de soltar el thread, asi el error de "NukeX no disponible" se ve al usuario.
        _ping_nukex()
        # El paste bloquea ~10s en NukeX: lo mandamos en un thread para no freezar Hiero
        _send_paste_in_thread()
        debug_print("=== main: copy OK, paste enviado en background ===")
    except (socket.timeout, ConnectionRefusedError) as e:
        debug_print(f"Error de conexion TCP: {e}", level="error")
        show_message(
            "Contact Sheet",
            "No se pudo conectar con NukeX en el puerto de OpenInNukeX.",
        )
    except Exception as exc:
        debug_print(f"Error en main: {exc}", level="error")
        debug_print(traceback.format_exc(), level="error")
        show_message("Contact Sheet", f"Error creando Contact Sheet:\n{exc}")
    finally:
        _flush_log()


if __name__ == "__main__":
    main()
