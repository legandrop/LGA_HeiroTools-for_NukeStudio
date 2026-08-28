"""
____________________________________________________________________________________

  LGA_NKS_Flow_FlowProd_Panel v1.26 | Lega
  Panel para operaciones de producción con Flow:
  - Revelar clips en Flow
  - Crear shots automáticamente
  - Crear thumbnails
  - Cambiar prioridad de shots
  - Integración con FileManagerS3 (Open, Download, Upload)


  v1.26: Los carteles de aviso pasan al helper LGA_NKS_MessageBox con el
         estilo del pack.
  v1.25: Invertido comportamiento del boton Download Clip:
         Click ahora descarga la ultima version, Shift+Click la version seleccionada.
  v1.24: El boton "Thumbnail" ahora soporta Shift+Click: reemplaza el thumbnail
         del shot en Flow con un snapshot del viewer, mostrando una ventana de
         comparacion (actual vs nuevo) y subiendo en un hilo separado.
         Ver LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_UpdateThumb.py.
         Tooltip del boton actualizado (Click vs Shift+Click).
  v1.23: Agregado sistema de scroll, logging a archivo y gap vertical
  v1.22: Boton Check Shots Exist para chequear si los shots del track comp existen en Flow
  v1.21: Actualizado para usar estilos dinámicos con bordes y hover para todos los botones
         Agregado tooltip dinámico para todos los botones
         
  v1.20: Agregados botones de integración con FileManagerS3 CLI
         - Open in FileManagerS3: Abre carpeta del shot en FileManagerS3
         - Download Shot: Descarga shot desde Wasabi S3
         - Upload Shot: Sube shot a Wasabi S3
         Funcionan sobre la ruta del shot (unidad/proyecto/grupo/shot)

  v1.10: Actualizado para usar shift+click para abrir el shot completo en Flow

  v1.09: Agregado modo de modificación de shots existentes
         Reutiliza la misma UI compacta de creación
         Permite agregar/eliminar tasks y actualizar la descripción
         No afecta estados ni tiempos de las tasks existentes

  v1.08: Actualizado para ser compatible con ambos sistemas de nomenclatura:
        - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
        - PROYECTO_SEQ_SHOT (3 bloques simplificado)
____________________________________________________________________________________
"""

import hiero.ui
import hiero.core
import sys
import os
import re
import logging
import queue
import time
from logging.handlers import QueueHandler, QueueListener
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore
from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning


# Clase de botón personalizada que maneja el Shift+Click
class CustomButton(QtWidgets.QPushButton):
    def __init__(self, text):
        super(CustomButton, self).__init__(text)
        self._custom_click_handler = None
        self._shift_click_handler = None
        # Conectar la señal clicked para manejar tanto clicks normales como shortcuts
        self.clicked.connect(self._handle_click)

    def setCustomClickHandler(self, handler):
        self._custom_click_handler = handler

    def setShiftClickHandler(self, handler):
        self._shift_click_handler = handler

    def _handle_click(self):
        """Maneja los clicks del botón, verificando si es Shift+Click"""
        if self._custom_click_handler and self._shift_click_handler:
            modifiers = QtWidgets.QApplication.keyboardModifiers()
            if modifiers & QtCore.Qt.ShiftModifier:
                self._shift_click_handler()
            else:
                self._custom_click_handler()
        else:
            # Si no hay handlers personalizados, comportamiento normal
            pass

# Importar función de limpieza de nombres desde NamingUtils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "LGA_NKS_Shared"))
from LGA_NKS_Flow_NamingUtils import clean_base_name


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


def setup_debug_logging(script_name="FlowProdPanel"):
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


debug_logger = setup_debug_logging(script_name="FlowProdPanel")

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


# Importar funciones de utilidad de estilos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "LGA_NKS_Shared"))
from LGA_NKS_Shared.LGA_NKS_StyleUtils import (
    calculate_dynamic_border,
    calculate_dynamic_hover,
    create_tooltip_stylesheet
)


class FlowProdPanel(QtWidgets.QWidget):
    def __init__(self):
        super(FlowProdPanel, self).__init__()
        self.setObjectName("com.lega.FlowProdPanel")
        self.setWindowTitle("Coordination")
        debug_print("=== FlowProdPanel init ===")
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

        # Definir los botones fijos y sus colores/estilos
        self.fixed_buttons = [
            (
                "Thumbnail",
                self.create_thumbnail_for_selected_clip,
                "#3a2a4d",
                None,
                "Click: reemplazar el thumbnail del shot en Flow con un snapshot\n"
                "Shift+Click: guardar snapshot del viewer en N:/proyecto/Thumbs",
            ),
            (
                "Create Shot",
                self.create_shot_for_selected_clip,
                "#2a4d3a",
                None,
                "Crear shot en Flow basado en el clip seleccionado",
            ),
            (
                "Modify Shot",
                self.modify_shot_for_selected_clip,
                "#2a4d3a",
                None,
                "Modificar shot existente en Flow (1 clip a la vez)",
            ),
            (
                "Check Shots Exist",
                self.check_timeline_shots,
                "#2a4d3a",
                None,
                "Chequear si los shots del track comp existen en Flow",
            ),
            (
                "Shot Priority",
                self.toggle_shot_priority_for_selected_clip,
                "#450101",
                None,
                "Cambiar prioridad del shot (alta ↔ normal)",
            ),
            (
                ".Psync",
                self.create_pipesync_token_file,
                "gradient_magenta_violet",
                None,
                "Generar archivo .psync para compartir",
            ),
            (
                "FileManagerS3",
                self.open_shot_in_filemanagers3,
                "gradient_magenta_violet",
                None,
                "Abrir carpeta del shot en FileManagerS3",
            ),
            (
                "Download Shot",
                self.download_shot_from_filemanagers3,
                "gradient_magenta_violet",
                None,
                "Descargar shot desde Wasabi S3",
            ),
            (
                "Upload Shot",
                self.upload_shot_to_filemanagers3,
                "gradient_magenta_violet",
                None,
                "Subir shot a Wasabi S3",
            ),
            (
                "Download Clip",
                self.download_latest_clip_from_filemanagers3,
                "gradient_magenta_violet",
                None,
                "Click: Descargar ultima version del clip\nShift+Click: Descargar clip seleccionado",
            ),
            (
                "Reveal in Flow",
                self.show_in_flow_for_selected_clip,
                "#1f1f1f",
                "Ctrl+Shift+F",
                "Click: Abrir task comp en Flow\nShift+Click: Abrir Shot completo en Flow (Ctrl+Shift+F)",
            ),
        ]

        # Solo botones fijos para este panel
        self.buttons = self.fixed_buttons

        self.num_columns = 1  # Inicialmente una columna
        self.button_width_hint = 0
        self.create_buttons()

        # Conectar la senal de cambio de tamano del widget al metodo correspondiente
        self.adjust_columns_on_resize()
        self.resizeEvent = self.adjust_columns_on_resize

    def showEvent(self, event):
        super(FlowProdPanel, self).showEvent(event)
        # Asegurar tamanos reales al mostrarse el panel
        self.adjust_columns_on_resize()
        self.update_scrollbar_policy()

    def create_buttons(self):
        debug_print("=== create_buttons ===")
        # Limpiar el layout actual antes de crear nuevos botones
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

            # Solo botones fijos para este panel: (name, handler, style, [shortcut], [tooltip])
            shortcut = button_info[3] if len(button_info) > 3 else None
            tooltip = button_info[4] if len(button_info) > 4 else None

            # Determinar el estilo del bot?n
            if style == "gradient_magenta_violet":
                border_color = calculate_dynamic_border(style)
                hover_colors = calculate_dynamic_hover(style)

                button_stylesheet = f"""
                    QPushButton {{
                        background-color: qlineargradient(
                            x1: 0, y1: 0, x2: 1, y2: 0,
                            stop: 0 #443a91,
                            stop: 0.5 #543a91,
                            stop: 1 #5b3a91
                        );
                        border: 1px solid {border_color};
                        border-radius: 3px;
                        color: #d8d8d8;
                        padding: 0px 0px;
                        min-height: 20px;
                    }}
                    QPushButton:hover {{
                        background-color: qlineargradient(
                            x1: 0, y1: 1, x2: 1, y2: 0,
                            stop: 0 {hover_colors['inicio']},
                            stop: 0.5 #9a6cd8,
                            stop: 1 {hover_colors['fin']}
                        );
                    }}
                    QPushButton:pressed {{
                        background-color: qlineargradient(
                            x1: 0, y1: 1, x2: 1, y2: 0,
                            stop: 0 #5145ac,
                            stop: 0.5 #6a49b5,
                            stop: 1 #5b3a91
                        );
                    }}
                """
            else:
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

            # Usar CustomButton para el bot?n "Reveal in Flow" para soportar Shift+Click
            if name == "Thumbnail":
                button = CustomButton(name)
                button.setCustomClickHandler(
                    self.update_thumbnail_in_flow_for_selected_clip
                )
                button.setShiftClickHandler(handler)
            elif name == "Reveal in Flow":
                button = CustomButton(name)
                button.setCustomClickHandler(handler)
                button.setShiftClickHandler(self.show_shot_in_flow_for_selected_clip)
            elif name == ".Psync":
                button = CustomButton(name)
                button.setCustomClickHandler(self.create_pipesync_token_file)
                button.setShiftClickHandler(self.open_shot_in_pipesync)
            elif name == "Download Clip":
                button = CustomButton(name)
                button.setCustomClickHandler(self.download_latest_clip_from_filemanagers3)
                button.setShiftClickHandler(self.download_clip_from_filemanagers3)
            else:
                button = QtWidgets.QPushButton(name)
                button.clicked.connect(handler)

            # Aplicar estilos del bot?n
            button.setStyleSheet(button_stylesheet)

            # Agregar estilos de tooltip din?micos si hay tooltip
            if tooltip:
                # Crear un selector ?nico para este bot?n usando su objectName
                button_object_name = f"button_{index}"
                button.setObjectName(button_object_name)

                # Crear stylesheet de tooltip din?mico
                tooltip_stylesheet = create_tooltip_stylesheet(style)
                # Modificar el tooltip stylesheet para usar el selector del bot?n
                tooltip_stylesheet = tooltip_stylesheet.replace("QToolTip", f"#{button_object_name} QToolTip")

                # Combinar estilos del bot?n con estilos de tooltip
                full_stylesheet = button_stylesheet + tooltip_stylesheet
                button.setStyleSheet(full_stylesheet)

                # Agregar el tooltip
                button.setToolTip(tooltip)

            # Agregar shortcut si existe
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

        # Calcular el numero de filas usadas
        num_rows = (len(self.buttons) + self.num_columns - 1) // self.num_columns

        # Anadir el espaciador vertical al final
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

    def parse_exr_name(self, exr_name):
        """Extrae el nombre base del archivo EXR usando funciones compartidas de NamingUtils."""
        # Usar función compartida para limpiar el nombre base (compatible con ambos formatos)
        base_name = clean_base_name(exr_name)
        return base_name

    def show_in_flow_for_selected_clip(self):
        """Llama al script Show in Flow para abrir la task comp en Chrome"""
        debug_print("=== CLICK NORMAL: Show in Flow (Task Comp) ===")
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Coordination_Panel_py", "LGA_NKS_Flow_ShowInFlow.py"
        )
        if not os.path.exists(script_path):
            show_warning(
                self,
                "Script no encontrado",
                f"No se encontró el script en la ruta: {script_path}",
            )
            return
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "LGA_NKS_Flow_ShowInFlow", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_Flow_ShowInFlow.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Llamar a la función principal
            debug_print("Llamando a show_in_flow_from_selected_clip()")
            module.show_in_flow_from_selected_clip()
        except Exception as e:
            debug_print(f"Error al ejecutar show_in_flow_from_selected_clip: {e}")
            show_warning(self, "Error al ejecutar", str(e))

    def show_shot_in_flow_for_selected_clip(self):
        """Llama al script Show in Flow para abrir el Shot completo en Chrome (Shift+Click)"""
        debug_print("=== SHIFT+CLICK: Show Shot in Flow (Shot completo) ===")
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Coordination_Panel_py", "LGA_NKS_Flow_ShowInFlow.py"
        )
        if not os.path.exists(script_path):
            show_warning(
                self,
                "Script no encontrado",
                f"No se encontró el script en la ruta: {script_path}",
            )
            return
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "LGA_NKS_Flow_ShowInFlow", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_Flow_ShowInFlow.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Llamar a la función para abrir el Shot (no la task comp)
            debug_print("Llamando a show_shot_in_flow_from_selected_clip()")
            module.show_shot_in_flow_from_selected_clip()
        except Exception as e:
            debug_print(f"Error al ejecutar show_shot_in_flow_from_selected_clip: {e}")
            show_warning(self, "Error al ejecutar", str(e))

    def create_thumbnail_for_selected_clip(self):
        """Llama al script Thumbnail para crear un thumbnail del clip seleccionado"""
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Coordination_Panel_py", "LGA_NKS_Flow_Thumbs.py"
        )
        if not os.path.exists(script_path):
            show_warning(
                self,
                "Script no encontrado",
                f"No se encontró el script en la ruta: {script_path}",
            )
            return
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "LGA_NKS_Flow_Thumbs", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError("No se pudo cargar el módulo LGA_NKS_Flow_Thumbs.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Llamar a la función principal
            module.main()
        except Exception as e:
            show_warning(self, "Error al ejecutar", str(e))

    def update_thumbnail_in_flow_for_selected_clip(self):
        """Shift+Click del boton Thumbnail: reemplaza el thumbnail del shot en Flow
        con un snapshot del viewer (abre ventana de confirmacion)."""
        script_path = os.path.join(
            os.path.dirname(__file__),
            "LGA_NKS_Coordination_Panel_py",
            "LGA_NKS_Flow_UpdateThumb.py",
        )
        if not os.path.exists(script_path):
            show_warning(
                self,
                "Script no encontrado",
                f"No se encontró el script en la ruta: {script_path}",
            )
            return
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "LGA_NKS_Flow_UpdateThumb", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_Flow_UpdateThumb.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.main()
        except Exception as e:
            show_warning(self, "Error al ejecutar", str(e))

    def create_shot_for_selected_clip(self):
        """Llama al script Create Shot para crear shots basado en el clip seleccionado"""
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Coordination_Panel_py", "LGA_NKS_Flow_CreateShot.py"
        )
        if not os.path.exists(script_path):
            show_warning(
                self,
                "Script no encontrado",
                f"No se encontró el script en la ruta: {script_path}",
            )
            return
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "LGA_NKS_Flow_CreateShot", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_Flow_CreateShot.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Llamar a la función principal
            module.main()
        except Exception as e:
            show_warning(self, "Error al ejecutar", str(e))

    def modify_shot_for_selected_clip(self):
        """Llama al script Modify Shot para ajustar shots existentes"""
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Coordination_Panel_py", "LGA_NKS_Flow_ModifyShot.py"
        )
        if not os.path.exists(script_path):
            show_warning(
                self,
                "Script no encontrado",
                f"No se encontró el script en la ruta: {script_path}",
            )
            return
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "LGA_NKS_Flow_ModifyShot", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_Flow_ModifyShot.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.main()
        except Exception as e:
            show_warning(self, "Error al ejecutar", str(e))

    def toggle_shot_priority_for_selected_clip(self):
        """Llama al script Shot Priority para cambiar la prioridad del shot seleccionado"""
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Coordination_Panel_py", "LGA_NKS_Flow_ShotPriority.py"
        )
        if not os.path.exists(script_path):
            show_warning(
                self,
                "Script no encontrado",
                f"No se encontró el script en la ruta: {script_path}",
            )
            return
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "LGA_NKS_Flow_ShotPriority", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_Flow_ShotPriority.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Llamar a la función principal
            module.toggle_shot_priority_from_selected_clip()
        except Exception as e:
            show_warning(self, "Error al ejecutar", str(e))

    def open_shot_in_pipesync(self):
        """Llama al script PipeSync para abrir la carpeta del shot seleccionado"""
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Coordination_Panel_py", "LGA_NKS_PipeSync_OpenPath.py"
        )
        if not os.path.exists(script_path):
            show_warning(
                self,
                "Script no encontrado",
                f"No se encontró el script en la ruta: {script_path}",
            )
            return
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "LGA_NKS_PipeSync_OpenPath", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_PipeSync_OpenPath.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.main()
        except Exception as e:
            show_warning(self, "Error al ejecutar", str(e))

    def create_pipesync_token_file(self):
        """Genera un archivo .psync para compartir el shot"""
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Coordination_Panel_py", "LGA_NKS_PipeSync_CreatePsync.py"
        )
        if not os.path.exists(script_path):
            show_warning(
                self,
                "Script no encontrado",
                f"No se encontró el script en la ruta: {script_path}",
            )
            return
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "LGA_NKS_PipeSync_CreatePsync", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_PipeSync_CreatePsync.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.main()
        except Exception as e:
            show_warning(self, "Error al ejecutar", str(e))

    def open_shot_in_filemanagers3(self):
        """Llama al script FileManagerS3 para abrir la carpeta del shot seleccionado"""
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Coordination_Panel_py", "LGA_NKS_FileManagerS3_OpenPath.py"
        )
        if not os.path.exists(script_path):
            show_warning(
                self,
                "Script no encontrado",
                f"No se encontró el script en la ruta: {script_path}",
            )
            return
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "LGA_NKS_FileManagerS3_OpenPath", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_FileManagerS3_OpenPath.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Llamar a la función principal
            module.main()
        except Exception as e:
            show_warning(self, "Error al ejecutar", str(e))

    def download_shot_from_filemanagers3(self):
        """Llama al script FileManagerS3 para descargar el shot seleccionado"""
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Coordination_Panel_py", "LGA_NKS_FileManagerS3_Download.py"
        )
        if not os.path.exists(script_path):
            show_warning(
                self,
                "Script no encontrado",
                f"No se encontró el script en la ruta: {script_path}",
            )
            return
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "LGA_NKS_FileManagerS3_Download", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_FileManagerS3_Download.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Llamar a la función principal
            module.main()
        except Exception as e:
            show_warning(self, "Error al ejecutar", str(e))

    def upload_shot_to_filemanagers3(self):
        """Llama al script FileManagerS3 para subir el shot seleccionado"""
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Coordination_Panel_py", "LGA_NKS_FileManagerS3_Upload.py"
        )
        if not os.path.exists(script_path):
            show_warning(
                self,
                "Script no encontrado",
                f"No se encontró el script en la ruta: {script_path}",
            )
            return
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "LGA_NKS_FileManagerS3_Upload", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_FileManagerS3_Upload.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Llamar a la función principal
            module.main()
        except Exception as e:
            show_warning(self, "Error al ejecutar", str(e))

    def _run_download_clip_from_filemanagers3(self, download_latest=False):
        """Llama al script FileManagerS3 para descargar clip(s) seleccionado(s)."""
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Coordination_Panel_py", "LGA_NKS_FileManagerS3_DownloadClip.py"
        )
        if not os.path.exists(script_path):
            show_warning(
                self,
                "Script no encontrado",
                f"No se encontró el script en la ruta: {script_path}",
            )
            return
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "LGA_NKS_FileManagerS3_DownloadClip", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_FileManagerS3_DownloadClip.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.main(download_latest=download_latest)
        except Exception as e:
            show_warning(self, "Error al ejecutar", str(e))

    def download_clip_from_filemanagers3(self):
        """Descarga el clip seleccionado en modo normal."""
        self._run_download_clip_from_filemanagers3(download_latest=False)

    def download_latest_clip_from_filemanagers3(self):
        """Descarga la ultima version disponible del clip (Shift+Click)."""
        self._run_download_clip_from_filemanagers3(download_latest=True)

    def check_timeline_shots(self):
        """Llama al script de chequeo de shots en el timeline."""
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Coordination_Panel_py", "LGA_NKS_Flow_CheckTimelineShots.py"
        )
        if not os.path.exists(script_path):
            show_warning(
                self,
                "Script no encontrado",
                f"No se encontró el script en la ruta: {script_path}",
            )
            return
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "LGA_NKS_Flow_CheckTimelineShots", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_Flow_CheckTimelineShots.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.main()
        except Exception as e:
            show_warning(self, "Error al ejecutar Check Shots", str(e))


# Crear la instancia del panel y agregarlo al windowManager de Hiero
flowProdPanel = FlowProdPanel()
wm = hiero.ui.windowManager()
wm.addWindow(flowProdPanel)


# Iniciar el watcher de reconexion automatica de "Download Clip".
# Se carga aca (el panel siempre se ejecuta al iniciar Hiero) para que el
# watcher arranque junto con Hiero. Se mantiene una referencia al modulo
# para evitar que el garbage collector detenga el QTimer.
download_clip_watcher_module = None
try:
    import importlib.util

    _watcher_path = os.path.join(
        os.path.dirname(__file__),
        "LGA_NKS_Coordination_Panel_py",
        "LGA_NKS_DownloadClip_Watcher.py",
    )
    if os.path.exists(_watcher_path):
        _watcher_spec = importlib.util.spec_from_file_location(
            "LGA_NKS_DownloadClip_Watcher", _watcher_path
        )
        if _watcher_spec is not None and _watcher_spec.loader is not None:
            download_clip_watcher_module = importlib.util.module_from_spec(_watcher_spec)
            _watcher_spec.loader.exec_module(download_clip_watcher_module)
            debug_print("Watcher de Download Clip iniciado")
    else:
        debug_print(
            f"Watcher de Download Clip no encontrado: {_watcher_path}", level="warning"
        )
except Exception as e:
    debug_print(f"No se pudo iniciar el watcher de Download Clip: {e}", level="error")
