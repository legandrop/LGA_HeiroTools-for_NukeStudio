"""
____________________________________________________________________

  LGA_ViewerPanel v1.69 | Lega

  Panel con herramientas para el viewer y el timeline de Hiero

  v1.69: Agregado Charly a los botones dinamicos de Prev/Next Rev.
  v1.68: Agregado sistema de scroll, logging a archivo y gap vertical
  v1.67: Agregado usuario Juano a botones dinámicos de prev/next rev.
  v1.66: Botones de prev/next rev para usuarios Lega, Javi y Sebas ahora son dinámicos y se muestran solo para el usuario actual.
  v1.65: Actualizado el script LGA_NKS_Viewer_Mask.py para usar el aspect ratio especificado
  v1.64: Actualizado para usar estilos dinámicos con bordes y hover para todos los botones
         Agregado tooltip dinámico para todos los botones
         Optimizado espaciado del layout y dimensiones de botones para mejor UX
  v1.63: Reorganización de scripts - Todos los scripts del viewer movidos
         a LGA_NKS_ViewerTL/ para mejor organización
  v1.62: Se agregó el botón Frame Number
  v1.61: Se agregaron tooltips
____________________________________________________________________

"""

import hiero.ui
import hiero.core
import os
import subprocess
import socket
import sys
import logging
import queue
import time
from logging.handlers import QueueHandler, QueueListener
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore

# Importar funciones de utilidad de estilos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "LGA_NKS_Shared"))
from LGA_NKS_Shared.LGA_NKS_StyleUtils import (
    calculate_dynamic_border,
    calculate_dynamic_hover,
    create_tooltip_stylesheet
)

# Añadir el directorio padre al path para importar módulos de PipeSync
parent_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, parent_dir)

# Variable global para activar o desactivar los prints
DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True

script_start_time = None
debug_log_listener = None


class RelativeTimeFormatter(logging.Formatter):
    """Formatter que incluye tiempo relativo desde el inicio del script."""

    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created
        relative_time = record.created - script_start_time
        record.relative_time = f"{relative_time:.3f}s"
        return super().format(record)


def setup_debug_logging(script_name="ViewerPanel"):
    """Configura el logging para escribir SOLO en archivo."""
    global debug_log_listener

    log_filename = f"DebugPy_{script_name}.log"
    log_file_path = os.path.join(os.path.dirname(__file__), "logs", log_filename)

    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    try:
        with open(log_file_path, "w", encoding="utf-8") as f:
            f.write(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    except Exception:
        pass

    logger_name = f"{script_name.lower()}_logger"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:
        logger.handlers.clear()

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    formatter = RelativeTimeFormatter("[%(relative_time)s] %(message)s")
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


debug_logger = setup_debug_logging(script_name="ViewerPanel")

# Umbral de solapamiento vertical permitido antes de activar scroll
SCROLL_OVERLAP_THRESHOLD_PX = 6
# Controla visibilidad de la barra de scroll (True = visible cuando corresponde)
SCROLLBAR_VISIBLE = False


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
        timestamped_msg = f"[{relative_time:.3f}s] {msg}"
        print(timestamped_msg)


def obtener_usuario_actual():
    """
    Obtiene el usuario actual de PipeSync desde la configuración segura.

    Returns:
        str: Login del usuario actual, o None si no se puede determinar
    """
    try:
        from LGA_NKS_Shared.SecureConfig_Reader import get_flow_credentials

        url, login, password = get_flow_credentials()
        if login:
            debug_print(f"Usuario actual determinado: {login}")
            return login
    except Exception as e:
        debug_print(f"Error obteniendo usuario actual: {e}")

    return None


class ViewerPanel(QtWidgets.QWidget):
    def __init__(self):
        super(ViewerPanel, self).__init__()

        self.setObjectName("com.lega.ViewerPanel")
        self.setWindowTitle("ViewerTL")
        debug_print("=== ViewerPanel init ===")

        self.root_layout = QtWidgets.QVBoxLayout()
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.root_layout.setSpacing(0)
        self.setLayout(self.root_layout)

        # Scroll area para evitar solapamiento vertical
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.scroll_area.setWidgetResizable(True)
        self.root_layout.addWidget(self.scroll_area)

        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_widget.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred
        )
        self.layout = QtWidgets.QGridLayout()
        self.layout.setHorizontalSpacing(6)
        self.layout.setVerticalSpacing(3)
        self.scroll_widget.setLayout(self.layout)
        self.scroll_area.setWidget(self.scroll_widget)

        # Obtener usuario actual para crear botones dinámicos
        self.usuario_actual = obtener_usuario_actual()

        # Crear botones dinámicos según el usuario actual
        self.buttons = self.create_dynamic_buttons()

        self.num_columns = 1  # Inicialmente una columna
        self.button_width_hint = 0
        self.create_buttons()

        # Conectar la senal de cambio de tamano del widget al metodo correspondiente
        self.adjust_columns_on_resize()
        self.resizeEvent = self.adjust_columns_on_resize

    def showEvent(self, event):
        super(ViewerPanel, self).showEvent(event)
        # Asegurar tamanos reales al mostrarse el panel
        self.adjust_columns_on_resize()
        self.update_scrollbar_policy()

    def create_dynamic_buttons(self):
        """
        Crea la lista de botones dinámicamente según el usuario actual.
        Solo muestra los botones de navegación del usuario actual.
        """
        # Botones comunes (siempre visibles)
        common_buttons = [
            (
                "&Viewer | Rec709",
                self.rec709_viewer,
                "#311840",
                "Shift+V",
                "Shift+V\nCambia el LUT del viewer a ACES/Rec.709",
            ),
            (
                "Viewer | 2.35:1 ",
                self.viewer_235,
                "#311840",
                None,
                "Ajusta el overlay del viewer a 2.35:1 y alterna los estilos de máscara\n(None, Half, Full) ajustando el efecto Frame del track BurnIn",
            ),
            (
                "Viewer | 2:1 ",
                self.viewer_21,
                "#311840",
                None,
                "Ajusta el overlay del viewer a 2:1 y alterna los estilos de máscara\n(None, Half, Full) ajustando el efecto Frame del track BurnIn",
            ),
            (
                "Refresh Timeline",
                self.refresh_timeline,
                "#4c4350",
                None,
                "Refresca el timeline manteniendo el nivel de zoom original\n(cuando el timeline funciona mal lo resetea)",
            ),
            (
                "Top Track ",
                self.top_track,
                "#4c4350",
                "Ctrl+Shift+T",
                "Ctrl+Shift+T\nScrollea al track superior del timeline",
            ),
            (
                "In Out Editref",
                self.in_out_editref,
                "#4d462b",
                "Ctrl+Shift+U",
                "Ctrl+Shift+U\nEstablece los puntos In y Out de la secuencia basándose\nen el clip más cercano del track EditRef o EditRefClean",
            ),
        ]

        # Botones de usuario (solo del usuario actual)
        user_buttons = []

        if self.usuario_actual:
            # Normalizar el email del usuario (tomar parte antes del @)
            usuario_normalizado = self.usuario_actual.split('@')[0].lower()

            # Manejar caso especial de Sebas
            if usuario_normalizado == "sebasromano_post":
                usuario_normalizado = "sebas"

            # Alias de usuarios (login -> key en usuarios_config)
            usuario_aliases = {
                "juanolivares": "juano",
                "charly_villafane": "charly",
                "charlyvillafane": "charly",
            }
            usuario_normalizado = usuario_aliases.get(
                usuario_normalizado, usuario_normalizado
            )

            debug_print(f"Usuario normalizado: {usuario_normalizado}")

            # Configuración de usuarios con sus emails normalizados
            usuarios_config = {
                "lega": {
                    "nombre": "Lega",
                    "color": "#69135e",
                    "prev_shortcut": "Ctrl+Alt+Shift+,",
                    "next_shortcut": "Ctrl+Alt+Shift+.",
                },
                "javi": {
                    "nombre": "Javi",
                    "color": "#9c3e5e",
                    "prev_shortcut": "Ctrl+Alt+Shift+,",  # Usar shortcuts de Lega
                    "next_shortcut": "Ctrl+Alt+Shift+.",  # Usar shortcuts de Lega
                },
                "sebas": {
                    "nombre": "Sebas",
                    "color": "#bd7f9f",
                    "prev_shortcut": "Ctrl+Alt+Shift+,",  # Usar shortcuts de Lega
                    "next_shortcut": "Ctrl+Alt+Shift+.",  # Usar shortcuts de Lega
                },
                "juano": {
                    "nombre": "Juano",
                    "color": "#7F4B69",
                    "prev_shortcut": "Ctrl+Alt+Shift+,",  # Usar shortcuts de Lega
                    "next_shortcut": "Ctrl+Alt+Shift+.",  # Usar shortcuts de Lega
                },
                "charly": {
                    "nombre": "Charly",
                    "color": "#a9909d",
                    "prev_shortcut": "Ctrl+Alt+Shift+,",  # Usar shortcuts de Lega
                    "next_shortcut": "Ctrl+Alt+Shift+.",  # Usar shortcuts de Lega
                }
            }

            # Verificar si el usuario está en la configuración
            if usuario_normalizado in usuarios_config:
                config = usuarios_config[usuario_normalizado]

                user_buttons.extend([
                    (
                        f"Prev Rev {config['nombre']}",
                        getattr(self, f"prev_rev_{usuario_normalizado}"),
                        config['color'],
                        config['prev_shortcut'],
                        f"{config['prev_shortcut']}\nBusca el clip anterior con estado Rev {config['nombre']} y ajusta la vista\n(establece In/Out desde EditRef, selecciona clip, ajusta zoom)",
                    ),
                    (
                        f"Next Rev {config['nombre']}",
                        getattr(self, f"next_rev_{usuario_normalizado}"),
                        config['color'],
                        config['next_shortcut'],
                        f"{config['next_shortcut']}\nBusca el clip siguiente con estado Rev {config['nombre']} y ajusta la vista\n(establece In/Out desde EditRef, selecciona clip, ajusta zoom)",
                    ),
                ])
                debug_print(f"Mostrando botones para usuario: {config['nombre']}")
            else:
                debug_print(f"Usuario '{usuario_normalizado}' no reconocido en configuración")
        else:
            debug_print("No se pudo determinar usuario actual - no se mostrarán botones de usuario")

        # Botones finales (siempre visibles)
        final_buttons = [
            (
                "Frame Number",
                self.frame_number_position,
                "#0e1f3b",
                "Shift+F",
                "Shift+F\nMueve el burnin de frame number al área visible\nabajo a la izquierda del viewer",
            ),
            (
                "SnapShot",
                self.snapshot,
                "#2d5a3d",
                None,
                "Crea un snapshot de la imagen actual del viewer\n(cropeada al aspect ratio de la secuencia) y lo copia al portapapeles\nIdeal para enviar por telegram con algun comentario",
            ),
        ]

        # Combinar todos los botones
        all_buttons = common_buttons + user_buttons + final_buttons

        debug_print(f"Total de botones creados: {len(all_buttons)}")
        return all_buttons

    def create_buttons(self):
        debug_print("=== create_buttons ===")
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        max_button_width = 0
        for index, button_info in enumerate(self.buttons):
            name = button_info[0]
            handler = button_info[1]
            style = button_info[2]
            shortcut = button_info[3] if len(button_info) > 3 else None
            tooltip = button_info[4] if len(button_info) > 4 else None

            border_color = calculate_dynamic_border(style)
            hover_color = calculate_dynamic_hover(style)

            button_stylesheet = f"""
                QPushButton {{
                    background-color: {style};
                    border: 1px solid {border_color};
                    border-radius: 3px;
                    color: #d8d8d8;
                    padding: 0px 0px;
                    min-height: 20px;
                }}
                QPushButton:hover {{
                    background-color: {hover_color};
                }}
                QPushButton:pressed {{
                    background-color: {style}aa;
                }}
            """

            if tooltip:
                button_object_name = f"button_{index}"
                tooltip_stylesheet = create_tooltip_stylesheet(style)
                tooltip_stylesheet = tooltip_stylesheet.replace("QToolTip", f"#{button_object_name} QToolTip")
                button_stylesheet += tooltip_stylesheet

            button = QtWidgets.QPushButton(name)
            button.setObjectName(f"button_{index}")
            button.setStyleSheet(button_stylesheet)
            button.clicked.connect(handler)

            if tooltip:
                button.setToolTip(tooltip)
            if shortcut:
                button.setShortcut(QtGui.QKeySequence(shortcut))

            max_button_width = max(max_button_width, button.sizeHint().width())
            row = index // self.num_columns
            column = index % self.num_columns
            self.layout.addWidget(button, row, column)

        if max_button_width > 0:
            self.button_width_hint = max_button_width
        debug_print(
            f"layout: buttons={len(self.buttons)} cols={self.num_columns} width_hint={self.button_width_hint}px"
        )

        num_rows = (len(self.buttons) + self.num_columns - 1) // self.num_columns
        spacer = QtWidgets.QSpacerItem(
            20, 20, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.layout.addItem(spacer, num_rows, 0, 1, self.num_columns)

        self.update_scrollbar_policy()

    def update_scrollbar_policy(self):
        content_height = self.layout.sizeHint().height()
        margins = self.layout.contentsMargins()
        content_height += margins.top() + margins.bottom()

        viewport_height = self.scroll_area.viewport().height()
        if viewport_height <= 0:
            return

        overlap = content_height - viewport_height
        if not SCROLLBAR_VISIBLE:
            self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.scroll_widget.setMinimumHeight(0)
            debug_print(
                f"scroll: OFF (forced) overlap={overlap}px content={content_height}px viewport={viewport_height}px"
            )
            return

        if overlap > SCROLL_OVERLAP_THRESHOLD_PX:
            self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            self.scroll_widget.setMinimumHeight(content_height)
            debug_print(
                f"scroll: ON overlap={overlap}px content={content_height}px viewport={viewport_height}px"
            )
        else:
            self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.scroll_widget.setMinimumHeight(0)
            debug_print(
                f"scroll: OFF overlap={overlap}px content={content_height}px viewport={viewport_height}px"
            )

    def adjust_columns_on_resize(self, event=None):
        viewport_width = self.scroll_area.viewport().width() if self.scroll_area else self.width()
        scroll_width = self.scroll_area.width() if self.scroll_area else self.width()
        self_width = self.width()
        panel_width = min(viewport_width, scroll_width, self_width)

        button_width = self.button_width_hint if self.button_width_hint > 0 else 120
        spacing = self.layout.horizontalSpacing()
        if spacing < 0:
            spacing = self.layout.spacing()
        margins = self.layout.contentsMargins()
        available_width = panel_width - (margins.left() + margins.right())
        min_button_spacing = max(0, spacing)

        new_num_columns = max(
            1,
            (available_width + min_button_spacing)
            // (button_width + min_button_spacing),
        )

        if new_num_columns != self.num_columns:
            self.num_columns = new_num_columns
            self.create_buttons()
        else:
            self.update_scrollbar_policy()

        debug_print(
            "resize: "
            f"panel_width={panel_width}px viewport={viewport_width}px "
            f"scroll={scroll_width}px self={self_width}px available={available_width}px "
            f"button_width={button_width}px spacing={min_button_spacing}px cols={self.num_columns}"
        )

    def rec709_viewer(self):

        try:
            current_viewer = hiero.ui.currentViewer()
            if current_viewer:
                current_viewer.player().setLUT("ACES/Rec.709")
                debug_print("LUT set to ACES/Rec.709")
            else:
                debug_print("No active viewer found.")
        except Exception as e:
            debug_print(f"Error setting Rec.709 LUT: {e}")

    def viewer_235(self):
        self.run_viewer_mask_script("2.35:1")

    def viewer_21(self):
        self.run_viewer_mask_script("2:1")

    def run_viewer_mask_script(self, aspect_ratio):
        """
        Ejecuta el script genérico de máscara del viewer con el aspect ratio especificado.

        Args:
            aspect_ratio (str): El aspect ratio a aplicar (ej: "2.35:1", "2:1")
        """
        try:
            script_path = os.path.join(
                os.path.dirname(__file__), "LGA_NKS_ViewerTL_Panel_py", "LGA_NKS_Viewer_Mask.py"
            )
            if os.path.exists(script_path):
                import importlib.util

                spec = importlib.util.spec_from_file_location(
                    "LGA_NKS_Viewer_Mask", script_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Llamar a la funcion main del script con el aspect ratio especificado
                module.main(aspect_ratio)
                debug_print(f"Executed LGA_NKS_Viewer_Mask script with aspect ratio {aspect_ratio}.")
            else:
                debug_print(f"Script not found at path: {script_path}")
        except Exception as e:
            debug_print(f"Error during running Viewer Mask script with aspect ratio {aspect_ratio}: {e}")

    ###### Refresh timeline
    def refresh_timeline(self):
        try:
            script_path = os.path.join(
                os.path.dirname(__file__), "LGA_NKS_ViewerTL_Panel_py", "LGA_NKS_Timeline_Refresh_Wrap.py"
            )
            if os.path.exists(script_path):
                import importlib.util

                spec = importlib.util.spec_from_file_location(
                    "LGA_NKS_Timeline_Refresh_Wrap", script_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Llamar a la función main del script wrapper
                module.main()
                debug_print("Executed Timeline Refresh Wrap script.")
            else:
                debug_print(f"Script not found at path: {script_path}")
        except Exception as e:
            debug_print(f"Error during Timeline Refresh: {e}")

    ###### Top Track
    def top_track(self):
        # Ruta al script dentro de la subcarpeta LGA_NKS
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Shared", "LGA_NKS_ScrollTo_TopTrack.py"
        )
        if os.path.exists(script_path):
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "LGA_NKS_ScrollTo_TopTrack", script_path
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Llamar a la funcion principal del script
            module.main()
        else:
            debug_print(f"Script not found at path: {script_path}")

    ###### In Out Editref
    def in_out_editref(self):
        try:
            script_path = os.path.join(
                os.path.dirname(__file__), "LGA_NKS_ViewerTL_Panel_py", "LGA_NKS_InOut_Editref.py"
            )
            if os.path.exists(script_path):
                import importlib.util

                spec = importlib.util.spec_from_file_location(
                    "LGA_NKS_InOut_Editref", script_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Llamar a la funcion principal del script
                module.main()
                debug_print("Ejecutado LGA_NKS_InOut_Editref script.")
            else:
                debug_print(f"Script no encontrado en la ruta: {script_path}")
        except Exception as e:
            debug_print(f"Error al ejecutar el script In Out Editref: {e}")

    def prev_rev_sup(self):
        self.execute_prevnext_rev("prev", "sup")

    def next_rev_sup(self):
        self.execute_prevnext_rev("next", "sup")

    def prev_rev_lega(self):
        self.execute_prevnext_rev("prev", "lega")

    def next_rev_lega(self):
        self.execute_prevnext_rev("next", "lega")

    def prev_rev_javi(self):
        self.execute_prevnext_rev("prev", "javi")

    def next_rev_javi(self):
        self.execute_prevnext_rev("next", "javi")

    def prev_rev_juano(self):
        self.execute_prevnext_rev("prev", "juano")

    def next_rev_juano(self):
        self.execute_prevnext_rev("next", "juano")

    def prev_rev_charly(self):
        self.execute_prevnext_rev("prev", "charly")

    def next_rev_charly(self):
        self.execute_prevnext_rev("next", "charly")

    # Métodos dinámicos para usuarios - delegan a los métodos existentes
    def prev_rev_sebas(self):
        self.execute_prevnext_rev("prev", "sup")  # Sebas usa "sup"

    def next_rev_sebas(self):
        self.execute_prevnext_rev("next", "sup")  # Sebas usa "sup"

    def execute_prevnext_rev(self, direction, rev_type):
        try:
            script_path = os.path.join(
                os.path.dirname(__file__), "LGA_NKS_ViewerTL_Panel_py", "LGA_NKS_PrevNext_Rev.py"
            )
            if os.path.exists(script_path):
                import importlib.util

                spec = importlib.util.spec_from_file_location(
                    "LGA_NKS_PrevNext_Rev", script_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                module.main(direction, rev_type)
                debug_print(
                    f"Ejecutado LGA_NKS_PrevNext_Rev script con dirección {direction} y tipo {rev_type}."
                )
            else:
                debug_print(f"Script no encontrado en la ruta: {script_path}")
        except Exception as e:
            debug_print(f"Error al ejecutar el script PrevNext Rev: {e}")

    ###### SnapShot
    def snapshot(self):
        try:
            script_path = os.path.join(
                os.path.dirname(__file__), "LGA_NKS_ViewerTL_Panel_py", "LGA_NKS_SnapShot.py"
            )
            if os.path.exists(script_path):
                import importlib.util

                spec = importlib.util.spec_from_file_location(
                    "LGA_NKS_SnapShot", script_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Llamar a la funcion principal del script
                module.main()
                debug_print("Ejecutado LGA_NKS_SnapShot script.")
            else:
                debug_print(f"Script no encontrado en la ruta: {script_path}")
        except Exception as e:
            debug_print(f"Error al ejecutar el script SnapShot: {e}")

    ###### Frame Number Position
    def frame_number_position(self):
        try:
            script_path = os.path.join(
                os.path.dirname(__file__), "LGA_NKS_ViewerTL_Panel_py", "LGA_NKS_FrameNumber.py"
            )
            if os.path.exists(script_path):
                import importlib.util

                spec = importlib.util.spec_from_file_location(
                    "LGA_NKS_FrameNumber", script_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                # Llamar a la funcion principal del script
                module.print_box_values()
                debug_print("Ejecutado LGA_NKS_FrameNumber script.")
            else:
                debug_print(f"Script no encontrado en la ruta: {script_path}")
        except Exception as e:
            debug_print(f"Error al ejecutar el script Frame Number Position: {e}")


# Crear la instancia del widget y anadirlo al gestor de ventanas de Hiero
viewerPanel = ViewerPanel()
wm = hiero.ui.windowManager()
wm.addWindow(viewerPanel)
