"""
____________________________________________________________________

  LGA_NKS_Wasabi_PolicyUnassign v0.63 | Lega

  Muestra y gestiona shots asignados en políticas IAM de Wasabi

  v0.63: La ventana lleva la fuente del pack (apply_ui_font), al
         armarla y de nuevo al redibujar las tarjetas de shot; sin
         eso salian con la fuente del host.
  v0.62: La ventana de shots migra al modulo de estilo LGA_UI_Style_HieroTools:
         Style.WINDOW, tokens en el HTML, filas sobre SURFACE y el boton de
         quitar por fila pasa de violeta a BTN_ICON (el violeta queda reservado
         a una accion global unica, que esta ventana no tiene).
  v0.61: El nombre y el color del usuario se resuelven por wasabi_user contra la
         DB de PipeSync (tabla flow_users), en vez del JSON local.
____________________________________________________________________
"""

import os
import sys
import json
import hiero.core
import hiero.ui
# Importar compatibilidad Qt para Hiero Panels
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore
from LGA_NKS_Shared.LGA_NKS_Flow_Users_Config import find_user_by_wasabi_user
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import Style, Color, apply_ui_font

# Reasignar clases para compatibilidad con código existente
QApplication = QtWidgets.QApplication
QDialog = QtWidgets.QDialog
QVBoxLayout = QtWidgets.QVBoxLayout
QHBoxLayout = QtWidgets.QHBoxLayout
QGridLayout = QtWidgets.QGridLayout
QLabel = QtWidgets.QLabel
QPushButton = QtWidgets.QPushButton
QScrollArea = QtWidgets.QScrollArea
QWidget = QtWidgets.QWidget
QFrame = QtWidgets.QFrame

Qt = QtCore.Qt
QRunnable = QtCore.QRunnable
Slot = QtCore.Slot
QThreadPool = QtCore.QThreadPool
Signal = QtCore.Signal
QObject = QtCore.QObject

QFont = QtGui.QFont

# Mantener el runtime Wasabi autocontenido dentro de Assignees.
current_dir = os.path.dirname(os.path.abspath(__file__))
startup_dir = os.path.dirname(os.path.dirname(__file__))
flow_shared_dir = os.path.join(startup_dir, "LGA_NKS_Shared")

sys.path.insert(0, current_dir)
sys.path.insert(0, flow_shared_dir)

import boto3
from boto3 import Session
from SecureConfig_Reader import get_s3_credentials

# Importar funciones auxiliares
from wasabi_policy_utils import (
    get_existing_policy_document,
    manage_policy_versions,
    read_user_policy_shots,
    remove_shot_from_policy,
)

# Configuracion
DEBUG = False


def debug_print(*message):
    if DEBUG:
        print(*message)


# Clase de ventana para mostrar y gestionar shots asignados en policy de Wasabi
class WasabiShotsWindow(QDialog):
    def __init__(self, user_name, user_color, wasabi_user, parent=None):
        super(WasabiShotsWindow, self).__init__(parent)
        self.setWindowTitle(f"Wasabi Policy Shots - {user_name}")
        self.setModal(False)
        self.wasabi_user = wasabi_user

        # Calcular altura máxima basada en la pantalla
        screen = QApplication.primaryScreen()
        screen_rect = screen.availableGeometry()
        max_height = screen_rect.height() - 300

        # Configurar tamaño inicial y máximo
        self.setMinimumWidth(900)
        self.resize(900, 400)  # Ancho inicial 900px, altura inicial 400px
        self.setMaximumHeight(max_height)

        # Evitar que la ventana se cierre automáticamente
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        # Estilo del pack: sin esto la ventana hereda el tema del host
        self.setStyleSheet(Style.WINDOW)

        # Layout principal
        layout = QVBoxLayout()
        self.setLayout(layout)

        # Etiqueta de estado inicial con formato HTML para múltiples colores
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setTextFormat(Qt.RichText)

        # Mensaje inicial
        # user_color es DATA (el color de la persona en la DB de PipeSync)
        initial_message = (
            f"<div style='text-align: center;'>"
            f"<span style='color: {Color.TEXT}; '>Shots asignados en la policy del usuario </span>"
            f"<span style='color: {Color.TEXT_ON_ACCENT}; background-color: {user_color}; padding: 2px 6px; '>{user_name}</span>"
            f"</div>"
        )

        font = QFont()
        font.setPointSize(10)
        self.status_label.setFont(font)
        self.status_label.setText(initial_message)
        self.status_label.setStyleSheet("padding: 10px;")

        layout.addWidget(self.status_label)

        # Etiqueta para mensajes de estado
        self.result_label = QLabel("")
        self.result_label.setAlignment(Qt.AlignCenter)
        self.result_label.setWordWrap(True)
        self.result_label.setTextFormat(Qt.RichText)
        layout.addWidget(self.result_label)

        # Área de scroll para los shots
        self.scroll_area = QScrollArea()
        self.scroll_widget = QWidget()
        self.shots_layout = QGridLayout()
        self.scroll_widget.setLayout(self.shots_layout)
        self.scroll_area.setWidget(self.scroll_widget)
        self.scroll_area.setWidgetResizable(True)
        layout.addWidget(self.scroll_area)

        # Botón de Close, secundario y a la derecha como en el resto del pack
        self.close_button = QPushButton("Close")
        self.close_button.setStyleSheet(Style.BTN_SECONDARY)
        self.close_button.clicked.connect(self.close)
        self.close_button.setEnabled(
            False
        )  # Deshabilitado hasta que termine el procesamiento
        buttons_row = QHBoxLayout()
        buttons_row.addStretch()
        buttons_row.addWidget(self.close_button)
        layout.addLayout(buttons_row)

        # Fuente del pack al final del armado: recorre los hijos ya creados.
        apply_ui_font(self)

        # Diccionario para mantener referencia a los widgets de shots
        self.shot_widgets = {}
        # Lista para mantener la referencia de los shots actualmente mostrados
        self.current_shots_list = []

    def resizeEvent(self, event):
        """Maneja el evento de redimensionamiento de la ventana."""
        super(WasabiShotsWindow, self).resizeEvent(event)
        # Solo recalcular y mostrar si ya tenemos shots cargados
        if self.current_shots_list:
            self.show_shots(self.current_shots_list, update_window_size=False)

    def show_processing_message(self):
        """Muestra el mensaje de procesamiento"""
        processing_html = (
            f"<span style='color: {Color.TEXT}; '>Leyendo policy del usuario...</span>"
        )
        self.result_label.setText(processing_html)
        self.result_label.setStyleSheet("padding: 10px;")

    def show_removing_shot_message(self, shot_name):
        """Muestra el mensaje de eliminación de shot"""
        removing_html = f"<span style='color: {Color.TEXT}; '>Borrando shot {shot_name} de la policy...</span>"
        self.result_label.setText(removing_html)
        self.result_label.setStyleSheet("padding: 10px;")

    def show_shots(self, shots_list, update_window_size=True):
        """Muestra la lista de shots con botones para eliminar"""
        self.current_shots_list = shots_list  # Guardar la lista para redimensionamiento
        if not shots_list:
            self.result_label.setText(
                f"<span style='color: {Color.TEXT}; '>No se encontraron shots asignados en la policy.</span>"
            )
            self.close_button.setEnabled(True)
            return

        self.result_label.setText("")

        # Limpiar layout anterior
        while self.shots_layout.count():
            item = self.shots_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        self.shot_widgets.clear()

        # Calcular número de columnas basado en el ancho de la ventana
        window_width = self.width()
        button_width = 400
        margin_per_button = 20  # Margen entre botones
        columns = max(
            1, (window_width - 40) // (button_width + margin_per_button)
        )  # 40px de margen total

        debug_print(f"Ventana ancho: {window_width}, columnas calculadas: {columns}")

        # Crear widget para cada shot
        for i, shot_name in enumerate(shots_list):
            row = i // columns
            col = i % columns

            shot_frame = QFrame()
            shot_frame.setFrameStyle(QFrame.StyledPanel)
            shot_frame.setFixedWidth(button_width)
            shot_frame.setFixedHeight(40)  # Altura fija para evitar flex
            shot_frame.setStyleSheet(
                "QFrame { background-color: %s; padding: 2px; margin: 1px; }"
                % Color.SURFACE
            )

            shot_layout = QHBoxLayout()
            shot_layout.setContentsMargins(0, 0, 0, 0)
            shot_layout.setSpacing(0)
            shot_frame.setLayout(shot_layout)

            # Label con el nombre del shot
            shot_label = QLabel(shot_name)
            shot_label.setStyleSheet(f"color: {Color.TEXT}; font-size: 12px;")
            shot_label.setAlignment(
                Qt.AlignVCenter | Qt.AlignLeft
            )  # Centrar verticalmente y alinear a la izquierda
            shot_layout.addWidget(shot_label)

            # Espaciador
            shot_layout.addStretch()

            # Botón X para eliminar. Va en BTN_ICON y no en violeta: hay uno
            # por fila y el violeta del pack se reserva para una accion global
            # unica, que esta ventana no tiene.
            remove_button = QPushButton("✕")
            remove_button.setFixedSize(25, 25)
            remove_button.setStyleSheet(Style.BTN_ICON)
            remove_button.clicked.connect(
                lambda checked=False, shot=shot_name: self.remove_shot(shot)
            )
            shot_layout.addWidget(remove_button)

            self.shots_layout.addWidget(shot_frame, row, col)
            self.shot_widgets[shot_name] = shot_frame

        # Las tarjetas de shot se recrean en cada refresco: hay que volver a
        # pasar la fuente del pack para que no salgan con la del host.
        apply_ui_font(self)

        # Calcular y ajustar altura de la ventana basado en el número de filas
        rows_needed = (len(shots_list) + columns - 1) // columns
        shot_height = 40 + 2  # Altura del shot + margen
        content_height = (
            rows_needed * shot_height + 170
        )  # 200px para header, botones, etc.

        # Limitar altura máxima
        max_height = self.maximumHeight()
        new_height = min(content_height, max_height)

        debug_print(
            f"Filas necesarias: {rows_needed}, altura calculada: {content_height}, altura final: {new_height}"
        )

        # Ajustar altura de la ventana solo si se solicita
        if update_window_size:
            current_width = self.width()
            self.resize(current_width, new_height)

        self.close_button.setEnabled(True)

    def remove_shot(self, shot_name):
        """Elimina un shot específico de la policy"""
        debug_print(f"Eliminando shot: {shot_name}")

        # Mostrar mensaje de estado
        self.show_removing_shot_message(shot_name)

        # Deshabilitar el botón X para este shot
        if shot_name in self.shot_widgets:
            shot_frame = self.shot_widgets[shot_name]
            shot_layout = shot_frame.layout()
            remove_button = shot_layout.itemAt(shot_layout.count() - 1).widget()
            remove_button.setEnabled(False)
            remove_button.setText("...")
            # El estado apagado lo dibuja la propia hoja BTN_ICON (:disabled)
            remove_button.setStyleSheet(Style.BTN_ICON)

        # Crear worker para eliminar el shot en hilo separado
        worker = WasabiRemoveShotWorker(self.wasabi_user, shot_name, self)
        worker.signals.finished.connect(self.on_shot_removed)
        worker.signals.error.connect(self.on_shot_removal_error)
        QThreadPool.globalInstance().start(worker)

    def on_shot_removed(self, shot_name):
        """Callback cuando se elimina exitosamente un shot"""
        debug_print(f"Shot {shot_name} eliminado exitosamente")

        # Mostrar mensaje de éxito
        self.show_success(f"Shot {shot_name} eliminado exitosamente de la policy")

        # Eliminar el widget del shot de la interfaz
        if shot_name in self.shot_widgets:
            shot_frame = self.shot_widgets[shot_name]
            self.shots_layout.removeWidget(shot_frame)
            shot_frame.deleteLater()
            del self.shot_widgets[shot_name]

    def on_shot_removal_error(self, shot_name, error_msg):
        """Callback cuando hay error eliminando un shot"""
        debug_print(f"Error eliminando shot {shot_name}: {error_msg}")

        # Rehabilitar el botón X
        if shot_name in self.shot_widgets:
            shot_frame = self.shot_widgets[shot_name]
            shot_layout = shot_frame.layout()
            remove_button = shot_layout.itemAt(shot_layout.count() - 1).widget()
            remove_button.setEnabled(True)
            remove_button.setText("✕")
            # Boton en rojo de error, armado con los tokens del pack
            remove_button.setStyleSheet(
                "QPushButton { background-color: %s; color: %s; border: none; font-weight: bold; }"
                "QPushButton:hover { background-color: %s; }"
                % (Color.ERROR, Color.TEXT_ON_ACCENT, Color.DOT_ERROR)
            )

    def show_success(self, message):
        """Muestra mensaje de éxito en verde"""
        success_html = f"<span style='color: {Color.OK_TEXT}; '>{message}</span>"
        self.result_label.setText(success_html)
        self.result_label.setStyleSheet("padding: 10px;")
        self.close_button.setEnabled(True)

    def show_error(self, message):
        """Muestra mensaje de error en rojo"""
        error_html = f"<span style='color: {Color.ERROR_TEXT}; '>{message}</span>"
        self.result_label.setText(error_html)
        self.result_label.setStyleSheet("padding: 10px;")
        self.close_button.setEnabled(True)

    def closeEvent(self, event):
        """Manejar el evento de cierre"""
        if not self.close_button.isEnabled():
            event.ignore()
        else:
            event.accept()


# Clases para procesamiento en hilos
class WasabiWorkerSignals(QObject):
    shots_ready = Signal(list)  # Para enviar la lista de shots
    finished = Signal(bool, str)  # success, message
    error = Signal(str)


class WasabiRemoveShotSignals(QObject):
    finished = Signal(str)  # shot_name
    error = Signal(str, str)  # shot_name, error_message


class WasabiWorker(QRunnable):
    def __init__(self, wasabi_user, shots_window):
        super(WasabiWorker, self).__init__()
        self.wasabi_user = wasabi_user
        self.shots_window = shots_window
        self.signals = WasabiWorkerSignals()

    @Slot()
    def run(self):
        try:
            debug_print(
                f"=== Iniciando lectura de policy para usuario: {self.wasabi_user} ==="
            )

            # Verificar credenciales de Wasabi desde SecureConfig
            access_key, secret_key, endpoint, region = get_s3_credentials()
            if not access_key or not secret_key:
                self.signals.error.emit(
                    "ERROR: No se pudieron obtener las credenciales de Wasabi desde SecureConfig."
                )
                return

            # Leer la policy del usuario
            shots_list = read_user_policy_shots(self.wasabi_user)

            if shots_list is None:
                self.signals.error.emit(
                    f"No se pudo leer la policy del usuario {self.wasabi_user}"
                )
                return

            # Enviar la lista de shots
            self.signals.shots_ready.emit(shots_list)

            # Si llegamos aquí, fue exitoso
            self.signals.finished.emit(
                True, f"Policy leída exitosamente para {self.wasabi_user}"
            )

        except Exception as e:
            debug_print(f"Error en WasabiWorker: {e}")
            self.signals.error.emit(f"Error: {str(e)}")


class WasabiRemoveShotWorker(QRunnable):
    def __init__(self, wasabi_user, shot_name, shots_window):
        super(WasabiRemoveShotWorker, self).__init__()
        self.wasabi_user = wasabi_user
        self.shot_name = shot_name
        self.shots_window = shots_window
        self.signals = WasabiRemoveShotSignals()

    @Slot()
    def run(self):
        try:
            debug_print(
                f"=== Eliminando shot {self.shot_name} del usuario {self.wasabi_user} ==="
            )

            # Verificar credenciales de Wasabi desde SecureConfig
            access_key, secret_key, endpoint, region = get_s3_credentials()
            if not access_key or not secret_key:
                self.signals.error.emit(
                    self.shot_name,
                    "No se pudieron obtener credenciales de Wasabi desde SecureConfig",
                )
                return

            # Eliminar el shot de la policy
            success = remove_shot_from_policy(self.wasabi_user, self.shot_name)

            if success:
                self.signals.finished.emit(self.shot_name)
            else:
                self.signals.error.emit(
                    self.shot_name, "No se pudo eliminar el shot de la policy"
                )

        except Exception as e:
            debug_print(f"Error eliminando shot {self.shot_name}: {e}")
            self.signals.error.emit(self.shot_name, str(e))


def get_user_info_from_config(wasabi_user):
    """
    Obtiene nombre y color de una persona a partir de su usuario de Wasabi.

    La fuente es la DB de PipeSync (tabla flow_users), alimentada desde Flow. Si la
    persona no esta ahi, se devuelve el propio wasabi_user y el gris neutro: la policy
    se puede asignar igual, solo se pierde el color en la ventana de estado.

    Returns:
        tuple: (user_name, user_color)
    """
    try:
        user = find_user_by_wasabi_user(wasabi_user)
        if user:
            return user["name"], user["color"]
        debug_print(
            f"'{wasabi_user}' no esta en la DB de PipeSync; se usa el nombre crudo."
        )
        return wasabi_user, Color.TEXT_DIM
    except Exception as e:
        debug_print(f"Error leyendo usuarios de PipeSync: {e}")
        return wasabi_user, Color.TEXT_DIM


# Variable global para mantener referencia a la ventana
_shots_window = None


def main(username=None):
    """
    Función principal del script.

    Args:
        username (str): Nombre del usuario de Wasabi. Si no se proporciona, usa "TestPoli" por defecto.
    """
    global _shots_window

    # Usar TestPoli por defecto si no se proporciona usuario
    if username is None:
        username = "TestPoli"

    debug_print(
        f"=== Iniciando LGA_NKS_Wasabi_PolicyUnassign para usuario: {username} ==="
    )

    # Obtener información del usuario para la ventana
    user_name, user_color = get_user_info_from_config(username)

    # Crear aplicación Qt si no existe
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    # Crear y mostrar ventana de shots
    _shots_window = WasabiShotsWindow(user_name, user_color, username)
    _shots_window.show()
    _shots_window.show_processing_message()  # Mostrar mensaje de procesamiento

    # Crear worker para procesamiento en hilo separado
    worker = WasabiWorker(username, _shots_window)

    # Conectar señales
    worker.signals.shots_ready.connect(
        lambda shots_list, window=_shots_window: window.show_shots(shots_list)
    )
    worker.signals.finished.connect(
        lambda success, message, window=_shots_window: (
            window.show_success(message) if success else window.show_error(message)
        )
    )
    worker.signals.error.connect(
        lambda error_msg, window=_shots_window: window.show_error(error_msg)
    )

    # Ejecutar en hilo separado
    QThreadPool.globalInstance().start(worker)

    debug_print("=== Worker iniciado en hilo separado ===")


if __name__ == "__main__":
    main()
