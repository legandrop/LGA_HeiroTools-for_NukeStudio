"""
____________________________________________________________________

  LGA_EditToolsPanel v3.05 | Lega

  Tools panel for Hiero / Nuke Studio

  v3.05: Nuevo boton Toggle AMF (Shift+L), debajo de Apply AMF
  v3.04: Nuevo boton Create NK v000, que llama a LGA_NKS_CreateNKScript.py.
         El boton Create v000 pasa a llamarse Create EXR v000.
  v3.03: Nuevo boton Apply AMF, que llama a LGA_NKS_ApplyAMF.py
  v3.02: Movido boton Self ReplaceClip desde el Review Panel, debajo de Reconnect Media.
  v3.01: Nuevo boton de import shot
  v3.00: Reconnect colapsado en un solo botón con submenu flotante (T>N, N>T, Win>Mac)
  v2.99: Create v000
  v2.98: Agregado sistema de scroll, logging a archivo y gap vertical
  v2.97: Actualizado para usar estilos dinámicos con bordes y hover para todos los botones
         Agregado tooltip dinámico para todos los botones
  v2.96: Extracción de funcionalidades embebidas - Creados LGA_NKS_SetShotName.py
         y LGA_NKS_OrganizeProject.py como scripts independientes
  v2.95: Reorganización de scripts - Movidos 7 scripts de edición desde LGA_NKS/
         a LGA_NKS_Edit/ para mejor organización: FixColorspaces, CreateNewTrack,
         Trim_In, Trim_Out, Reconnect, SelfReplaceClip, mediaMissingFrames
  v2.94: Clean Project mejora borrado de clips con múltiples BinItems y logs numerados
  v2.93: Agregado botón "Compositing Log | Clip" que cambia el color transform
         de los clips seleccionados a compositing_log
  v2.92: Invertido comportamiento del botón Reconnect Win > Mac:
         Click: Reconecta todos los clips del timeline
         Shift+Click: Reconecta solo los clips seleccionados
         Agregado método execute_external_script_with_param para pasar parámetros a scripts
  v2.91: Se agregaron tooltips mejorados y descriptivos para todos los botones del panel
____________________________________________________________________

"""

import hiero.ui
import hiero.core
import os
import re
import subprocess
import socket
import sys
import hiero
import logging
import queue
import time
from logging.handlers import QueueHandler, QueueListener
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore

# Tooltips fuera del widget (capa intermedia para la futura migracion bilingue)
TOOLTIP_CREATE_NK_SCRIPT = (
    "Crea el script de comp de Nuke del shot activo desde el template del proyecto "
    "(ASSETS), con los plates y denoised reales, el CDL/CLF del shot y el EditRef centrado"
)
import importlib.util
import importlib.machinery
from pathlib import Path

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


def setup_debug_logging(script_name="EditToolsPanel"):
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


debug_logger = setup_debug_logging(script_name="EditToolsPanel")

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


def debug_print_b(*message, level="info"):
    debug_print(*message, level=level)


# Importar utilidades de naming centralizadas
naming_utils_path = Path(__file__).parent / "LGA_NKS_Shared"
if naming_utils_path.exists():
    sys.path.insert(0, str(naming_utils_path))
    try:
        from LGA_NKS_Flow_NamingUtils import (
            extract_shot_code,
            clean_base_name,
        )
        HAS_NAMING_UTILS = True
    except ImportError:
        HAS_NAMING_UTILS = False
        debug_print("Warning: No se pudo importar LGA_NKS_Flow_NamingUtils")
else:
    HAS_NAMING_UTILS = False

# Importar funciones de utilidad de estilos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "LGA_NKS_Shared"))
from LGA_NKS_Shared.LGA_NKS_StyleUtils import (
    calculate_dynamic_border,
    calculate_dynamic_hover,
    create_tooltip_stylesheet
)


# Clase de botón personalizada que maneja el Shift+Click
class CustomButton(QtWidgets.QPushButton):
    def __init__(self, text):
        super(CustomButton, self).__init__(text)
        self._custom_click_handler = None
        self._shift_click_handler = None

    def setCustomClickHandler(self, handler):
        self._custom_click_handler = handler

    def setShiftClickHandler(self, handler):
        self._shift_click_handler = handler

    def mousePressEvent(self, event):
        if self._custom_click_handler and self._shift_click_handler:
            modifiers = event.modifiers()
            if modifiers & QtCore.Qt.ShiftModifier:
                self._shift_click_handler()
            else:
                self._custom_click_handler()
        else:
            super(CustomButton, self).mousePressEvent(event)


class ReconnectPopup(QtWidgets.QFrame):
    def __init__(self, parent=None):
        super(ReconnectPopup, self).__init__(parent, QtCore.Qt.Popup)
        self.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                background-color: #2a2a2a;
                border: 1px solid #6a5a30;
                border-radius: 4px;
            }
        """)
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(3)
        self.setLayout(layout)

    def add_button(self, text, callback, style="#4a4329", tooltip=None, shift_callback=None):
        border_color = calculate_dynamic_border(style)
        hover_color = calculate_dynamic_hover(style)
        btn_stylesheet = f"""
            QPushButton {{
                background-color: {style};
                border: 1px solid {border_color};
                border-radius: 3px;
                color: #d8d8d8;
                padding: 0px 8px;
                min-height: 20px;
                min-width: 110px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {style}aa;
            }}
        """
        popup = self
        if shift_callback:
            button = CustomButton(text)
            def make_handlers(cb, scb):
                def on_click():
                    cb()
                    popup.hide()
                def on_shift():
                    scb()
                    popup.hide()
                return on_click, on_shift
            on_click, on_shift = make_handlers(callback, shift_callback)
            button.setCustomClickHandler(on_click)
            button.setShiftClickHandler(on_shift)
        else:
            button = QtWidgets.QPushButton(text)
            def make_handler(cb):
                def on_click():
                    cb()
                    popup.hide()
                return on_click
            button.clicked.connect(make_handler(callback))
        button.setStyleSheet(btn_stylesheet)
        if tooltip:
            button.setToolTip(tooltip)
        self.layout().addWidget(button)
        return button


class ReconnectMediaWidget(QtWidgets.QWidget):
    def __init__(self):
        super(ReconnectMediaWidget, self).__init__()

        self.setObjectName("com.lega.toolPanel")
        self.setWindowTitle("Edit")
        debug_print("=== EditToolsPanel init ===")
        self.setStyleSheet(
            "QToolTip { color: #ffffff; background-color: #2a2a2a; border: 1px solid white; }"
        )

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
        self.layout = QtWidgets.QGridLayout()  # Usamos QGridLayout en lugar de QVBoxLayout
        self.layout.setHorizontalSpacing(6)
        self.layout.setVerticalSpacing(3)
        self.scroll_widget.setLayout(self.layout)
        self.scroll_area.setWidget(self.scroll_widget)


        # Crear botones y agregarlos al layout
        self.buttons = [
            ("Organize Project", self.organize_project, "#283548", None, "Organiza los clips en bins basándose en su ruta de archivo"),
            ("Clean Project", self.clean_project, "#283548", None, "Elimina clips no usados del proyecto"),
            ("Rec709 | Clip", self.rec709_clip, "#434c41", None, "Cambia el color transform a Rec.709 en los clips seleccionados"),
            ("Default | Clip", self.default_clip, "#434c41", None, "Cambia el color transform a default en los clips seleccionados"),
            ("Compositing Log | Clip", self.set_compositing_log, "#434c41", None, "Cambia el color transform a compositing_log en los clips seleccionados"),
            ("Fix Colorspaces", self.fix_colorspaces, "#434c41", None, "Detecta y corrige clips con colorspace rec709 o gamma2.2"),
            ("Apply AMF", self.apply_amf, "#434c41", None, "Crea los soft effects de color en los clips seleccionados siguiendo el .amf del shot (.cdl y .clf de _input/Look_Files)"),
            ("Togg&le AMF", self.toggle_amf, "#434c41", "Shift+L", "Shift+L\nHabilita o deshabilita los soft effects de Apply AMF que esten bajo el playhead, en todos los tracks"),
            ("Import shot", self.import_shot, "#2a4d3a", None, "Importa shots al proyecto"),
            ("Set Shot Name", self.set_shot_name, "#2a4d3a", None, "Establece el nombre del shot basándose en la ruta del archivo"),
            ("Create EXR v000", self.create_v000, "#2a4d3a", None, "Abre el validador para preparar una secuencia negra v000 del shot activo"),
            ("Create NK v000", self.create_nk_script, "#2a4d3a", None, TOOLTIP_CREATE_NK_SCRIPT),
            ("New Video Track", self.create_new_track, "#3a2a4d", None, "Crea un nuevo track de video encima del track seleccionado"),
            ("Extend &Edit", self.extend_edit_to_playhead, "#453434", "Alt+E", "Alt+E\nExtiende el punto de salida del clip hasta el playhead (cambiando su velocidad)"),
            ("Trim &In", self.trim_in, "#453434", "Alt+[", "Alt+[\nTrimea el IN del clip a la posicion del playhead"),
            ("Trim &Out", self.trim_out, "#453434", "Alt+]", "Alt+]\nTrimea el OUT del clip a la posicion del playhead"),
            ("Reconnect ▸", self.show_reconnect_popup, "#4a4329", None, "Despliega las opciones de reconexión de media"),
            (
                "Reconnect Media",
                self.reconnectMediaFromTimeline,
                "#4a4329",
                "Alt+M",
                "Alt+M\nAbre un diálogo para reconectar media manualmente",
            ),
            ("Self ReplaceClip", self.execute_SelfReplaceClip, "#4a4329", None, "Crea una nueva versión duplicada del clip seleccionado para que sea única (a veces arregla problemas)"),
            (
                "Clear Tag",
                self.run_clear_tag_script,
                "#1f1f1f",
                None,
                "Elimina todos los tags de los clips seleccionados",
            ),
            (
                "Match Rev Ver",
                self.match_rev_version,
                "#3d2a47",
                None,
                "Click: Iguala la versión de los clips del track _rev_ (mov o mxf) con la versión de los EXR correspondientes\nShift+Click: Procesa todos los clips del timeline",
            ),
            (
                "Compare Rev EdRef",
                self.compare_rev_editref,
                "#3d2a47",
                None,
                "Click: Compara los rangos de frames entre clips del track _rev_ (mov o mxf) y el track EditRef\nShift+Click: Compara todos los clips del timeline",
            ),
            (
                "Compare EXR aPlate",
                self.compare_exr_aplate,
                "#3d2a47",
                None,
                "Click: Compara los rangos de frames entre clips del track _comp_ (exr) y el track aPlate\nShift+Click: Compara todos los clips del timeline",
            ),
            ("Check Frames", self.check_frames, "#4a4329", None, "Revisa los clips seleccionados para ver si tienen frames faltantes o corruptos"),
        ]

        self.reconnect_btn_ref = None
        self._build_reconnect_popup()

        self.num_columns = 1  # Inicialmente una columna
        self.button_width_hint = 0
        self.create_buttons()

        # Conectar la senal de cambio de tamano del widget al metodo correspondiente
        self.adjust_columns_on_resize()
        self.resizeEvent = self.adjust_columns_on_resize

    def showEvent(self, event):
        super(ReconnectMediaWidget, self).showEvent(event)
        # Asegurar tamanos reales al mostrarse el panel
        self.adjust_columns_on_resize()
        self.update_scrollbar_policy()

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

            # Usar CustomButton para el boton Match Rev Ver, Compare Rev EdRef, Compare EXR aPlate y Reconnect Win > Mac
            if name == "Match Rev Ver":
                button = CustomButton(name)
                button.setCustomClickHandler(self.match_rev_version)
                button.setShiftClickHandler(self.match_rev_version_force_all)
            elif name == "Compare Rev EdRef":
                button = CustomButton(name)
                button.setCustomClickHandler(self.compare_rev_editref)
                button.setShiftClickHandler(self.compare_rev_editref_force_all)
            elif name == "Compare EXR aPlate":
                button = CustomButton(name)
                button.setCustomClickHandler(self.compare_exr_aplate)
                button.setShiftClickHandler(self.compare_exr_aplate_force_all)
            elif name == "Reconnect ▸":
                button = QtWidgets.QPushButton(name)
                button.clicked.connect(handler)
                self.reconnect_btn_ref = button
            else:
                button = QtWidgets.QPushButton(name)
                button.clicked.connect(handler)

            # Aplicar estilos din?micos con bordes, hover y tooltips
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
                button_stylesheet += tooltip_stylesheet

            button.setStyleSheet(button_stylesheet)

            if shortcut:
                button.setShortcut(shortcut)
            if tooltip:
                button.setToolTip(tooltip)

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

    ###### Rec 709 en clips seleccionados
    def rec709_clip(self):
        """Cambia clips seleccionados a Rec.709 usando el módulo unificado"""
        try:
            # Importar y ejecutar el script desde la carpeta LGA_NKS_Edit
            script_path = os.path.join(
                os.path.dirname(__file__),
                "LGA_NKS_Edit_Panel_py",
                "LGA_NKS_ColorTransforms.py",
            )
            if os.path.exists(script_path):
                try:
                    spec = importlib.util.spec_from_file_location(
                        "LGA_NKS_ColorTransforms", script_path
                    )
                    if spec is not None and spec.loader is not None:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        # Llamar a la función específica
                        if hasattr(module, "set_rec709"):
                            module.set_rec709()
                        else:
                            debug_print("El módulo LGA_NKS_ColorTransforms.py no tiene función 'set_rec709'")
                    else:
                        debug_print("No se pudo crear el spec o loader para el módulo: LGA_NKS_ColorTransforms.py")
                except Exception as e:
                    debug_print(f"Error al ejecutar set_rec709: {e}")
            else:
                debug_print(f"Módulo no encontrado en la ruta: {script_path}")
        except Exception as e:
            debug_print(f"Error cambiando a Rec.709: {e}")

    ###### Compositing Log en clips seleccionados
    def set_compositing_log(self):
        """Cambia clips seleccionados a compositing_log usando el módulo unificado"""
        try:
            # Importar y ejecutar el script desde la carpeta LGA_NKS_Edit
            script_path = os.path.join(
                os.path.dirname(__file__),
                "LGA_NKS_Edit_Panel_py",
                "LGA_NKS_ColorTransforms.py",
            )
            if os.path.exists(script_path):
                try:
                    spec = importlib.util.spec_from_file_location(
                        "LGA_NKS_ColorTransforms", script_path
                    )
                    if spec is not None and spec.loader is not None:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        # Llamar a la función específica
                        if hasattr(module, "set_compositing_log"):
                            module.set_compositing_log()
                        else:
                            debug_print("El módulo LGA_NKS_ColorTransforms.py no tiene función 'set_compositing_log'")
                    else:
                        debug_print("No se pudo crear el spec o loader para el módulo: LGA_NKS_ColorTransforms.py")
                except Exception as e:
                    debug_print(f"Error al ejecutar set_compositing_log: {e}")
            else:
                debug_print(f"Módulo no encontrado en la ruta: {script_path}")
        except Exception as e:
            debug_print(f"Error cambiando a compositing_log: {e}")

    ###### Default space color en clips seleccionados
    def default_clip(self):
        """Cambia clips seleccionados a default usando el módulo unificado"""
        try:
            # Importar y ejecutar el script desde la carpeta LGA_NKS_Edit
            script_path = os.path.join(
                os.path.dirname(__file__),
                "LGA_NKS_Edit_Panel_py",
                "LGA_NKS_ColorTransforms.py",
            )
            if os.path.exists(script_path):
                try:
                    spec = importlib.util.spec_from_file_location(
                        "LGA_NKS_ColorTransforms", script_path
                    )
                    if spec is not None and spec.loader is not None:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        # Llamar a la función específica
                        if hasattr(module, "set_default"):
                            module.set_default()
                        else:
                            debug_print("El módulo LGA_NKS_ColorTransforms.py no tiene función 'set_default'")
                    else:
                        debug_print("No se pudo crear el spec o loader para el módulo: LGA_NKS_ColorTransforms.py")
                except Exception as e:
                    debug_print(f"Error al ejecutar set_default: {e}")
            else:
                debug_print(f"Módulo no encontrado en la ruta: {script_path}")
        except Exception as e:
            debug_print(f"Error cambiando a default: {e}")

    ###### Fix Colorspaces
    def fix_colorspaces(self):
        """Ejecuta el script LGA_NKS_FixColorspaces.py para corregir colorspaces rec709 y gamma2.2"""
        debug_print_b("\n>>> Ejecutando Fix Colorspaces script...")

        try:
            # Obtenemos el proyecto activo y comenzamos un bloque de undo
            project = get_active_project()
            if not project:  # Comprobacion de proyecto activo
                debug_print_b("No active project found for Fix Colorspaces.")
                return

            with project.beginUndo("Fix Colorspaces"):
                # Ejecutamos el script dentro del bloque de undo
                result = self.execute_external_script("LGA_NKS_FixColorspaces.py")
                if result:
                    debug_print_b(">>> Fix Colorspaces script completado")
                else:
                    debug_print_b(">>> Error al ejecutar Fix Colorspaces script")
        except Exception as e:
            debug_print_b(f"Error durante la ejecución de Fix Colorspaces: {e}")
            import traceback

            debug_print_b(traceback.format_exc())

    ###### Apply AMF
    def apply_amf(self):
        """Ejecuta LGA_NKS_ApplyAMF.py para crear los soft effects de color en los clips seleccionados."""
        debug_print_b("\n>>> Ejecutando Apply AMF script...")

        try:
            # El undo lo maneja el propio script, para no anidar bloques
            result = self.execute_external_script("LGA_NKS_ApplyAMF.py")
            if result:
                debug_print_b(">>> Apply AMF script completado")
            else:
                debug_print_b(">>> Error al ejecutar Apply AMF script")
        except Exception as e:
            debug_print_b(f"Error durante la ejecución de Apply AMF: {e}")
            import traceback

            debug_print_b(traceback.format_exc())

    ###### Toggle AMF
    def toggle_amf(self):
        """Ejecuta LGA_NKS_ToggleAMF.py para habilitar/deshabilitar los efectos de Apply AMF."""
        debug_print_b("\n>>> Ejecutando Toggle AMF script...")

        try:
            # El undo lo maneja el propio script, para no anidar bloques
            result = self.execute_external_script("LGA_NKS_ToggleAMF.py")
            if result:
                debug_print_b(">>> Toggle AMF script completado")
            else:
                debug_print_b(">>> Error al ejecutar Toggle AMF script")
        except Exception as e:
            debug_print_b(f"Error durante la ejecución de Toggle AMF: {e}")
            import traceback

            debug_print_b(traceback.format_exc())

    ###### Import shot
    def import_shot(self):
        """Ejecuta el script LGA_import_shots.py para importar shots al proyecto."""
        debug_print_b("\n>>> Ejecutando Import shot script...")

        try:
            result = self.execute_external_script("LGA_import_shots.py")
            if result:
                debug_print_b(">>> Import shot script completado")
            else:
                debug_print_b(">>> Error al ejecutar Import shot script")
        except Exception as e:
            debug_print_b(f"Error durante la ejecución de Import shot: {e}")
            import traceback
            debug_print_b(traceback.format_exc())

    def create_new_track(self):
        """Ejecuta el script LGA_NKS_CreateNewTrack.py para crear un nuevo track de video"""
        debug_print_b("\n>>> Ejecutando Create New Track script...")

        try:
            # Obtenemos el proyecto activo y comenzamos un bloque de undo
            project = get_active_project()
            if not project:  # Comprobacion de proyecto activo
                debug_print_b("No active project found for Create New Track.")
                return

            with project.beginUndo("Create New Track"):
                # Ejecutamos el script dentro del bloque de undo
                result = self.execute_external_script("LGA_NKS_CreateNewTrack.py")
                if result:
                    debug_print_b(">>> Create New Track script completado")
                else:
                    debug_print_b(">>> Error al ejecutar Create New Track script")
        except Exception as e:
            debug_print_b(f"Error durante la ejecución de Create New Track: {e}")
            import traceback

            debug_print_b(traceback.format_exc())

    ###### Organize Project
    def organize_project(self):
        """Ejecuta el script LGA_NKS_OrganizeProject.py para organizar clips en bins."""
        debug_print_b("\n>>> Ejecutando Organize Project script...")

        try:
            # Ejecutamos el script externo
            result = self.execute_external_script("LGA_NKS_OrganizeProject.py")
            if result:
                debug_print_b(">>> Organize Project script completado")
            else:
                debug_print_b(">>> Error al ejecutar Organize Project script")
        except Exception as e:
            debug_print_b(f"Error durante la ejecución de Organize Project: {e}")
            import traceback
            debug_print_b(traceback.format_exc())

    ###### Shot name
    def set_shot_name(self):
        """Ejecuta el script LGA_NKS_SetShotName.py para establecer nombres de shots."""
        debug_print_b("\n>>> Ejecutando Set Shot Name script...")

        try:
            # Obtenemos el proyecto activo y comenzamos un bloque de undo
            project = get_active_project()
            if not project:  # Comprobacion de proyecto activo
                debug_print_b("No active project found for Set Shot Name.")
                return

            with project.beginUndo("Set Shot Name"):
                # Ejecutamos el script dentro del bloque de undo
                result = self.execute_external_script("LGA_NKS_SetShotName.py")
                if result:
                    debug_print_b(">>> Set Shot Name script completado")
                else:
                    debug_print_b(">>> Error al ejecutar Set Shot Name script")
        except Exception as e:
            debug_print_b(f"Error durante la ejecución de Set Shot Name: {e}")
            import traceback
            debug_print_b(traceback.format_exc())

    ###### Create v000
    def create_v000(self):
        """Abre el dialogo Create v000 para validar parametros del shot activo."""
        debug_print_b("\n>>> Ejecutando Create v000 dialog...")

        try:
            result = self.execute_external_script("LGA_NKS_CreateV000.py")
            if result:
                debug_print_b(">>> Create v000 dialog completado")
            else:
                debug_print_b(">>> Error al ejecutar Create v000 dialog")
        except Exception as e:
            debug_print_b(f"Error durante la ejecucion de Create v000: {e}")
            import traceback
            debug_print_b(traceback.format_exc())

    ###### Create NK Script
    def create_nk_script(self):
        """Abre el dialogo Create NK Script para armar el comp del shot activo."""
        debug_print_b("\n>>> Ejecutando Create NK Script...")

        try:
            result = self.execute_external_script("LGA_NKS_CreateNKScript.py")
            if result:
                debug_print_b(">>> Create NK Script completado")
            else:
                debug_print_b(">>> Error al ejecutar Create NK Script")
        except Exception as e:
            debug_print_b(f"Error durante la ejecucion de Create NK Script: {e}")
            import traceback
            debug_print_b(traceback.format_exc())

    ###### Extend edit
    def extend_edit_to_playhead(self):
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("\nNo active sequence found.")
            return

        te = hiero.ui.getTimelineEditor(seq)
        selected_clips = te.selection()

        current_viewer = hiero.ui.currentViewer()
        player = current_viewer.player() if current_viewer else None
        playhead_frame = player.time() if player else None

        if selected_clips and playhead_frame is not None:
            for shot in selected_clips:
                try:
                    shot.setTimelineOut(playhead_frame + 1)
                    debug_print(
                        f"DST Out extended to {playhead_frame + 1} for clip: {shot.name()}"
                    )
                except Exception as e:
                    debug_print(f"Error setting DST Out: {e}")
        else:
            debug_print("No clips selected or playhead position unavailable.")

    ###### Trim In
    def trim_in(self):
        """Ejecuta el script LGA_NKS_Trim_In.py para recortar el material antes del playhead."""
        debug_print_b("\n>>> Ejecutando Trim In script...")

        try:
            # Obtenemos el proyecto activo y comenzamos un bloque de undo
            project = get_active_project()
            if not project:  # Comprobacion de proyecto activo
                debug_print_b("No active project found for Trim In.")
                return

            with project.beginUndo("Trim In to Playhead"):
                # Ejecutamos el script dentro del bloque de undo
                result = self.execute_external_script("LGA_NKS_Trim_In.py")
                if result:
                    debug_print_b(">>> Trim In script completado")
                else:
                    debug_print_b(">>> Error al ejecutar Trim In script")
        except Exception as e:
            debug_print_b(f"Error durante la ejecución de Trim In: {e}")
            import traceback

            debug_print_b(traceback.format_exc())

    ###### Trim Out
    def trim_out(self):
        """Ejecuta el script LGA_NKS_Trim_Out.py para recortar el material después del playhead."""
        debug_print_b("\n>>> Ejecutando Trim Out script...")

        try:
            # Obtenemos el proyecto activo y comenzamos un bloque de undo
            project = get_active_project()
            if not project:  # Comprobacion de proyecto activo
                debug_print_b("No active project found for Trim Out.")
                return

            with project.beginUndo("Trim Out to Playhead"):
                # Ejecutamos el script dentro del bloque de undo
                result = self.execute_external_script("LGA_NKS_Trim_Out.py")
                if result:
                    debug_print_b(">>> Trim Out script completado")
                else:
                    debug_print_b(">>> Error al ejecutar Trim Out script")
        except Exception as e:
            debug_print_b(f"Error durante la ejecución de Trim Out: {e}")
            import traceback

            debug_print_b(traceback.format_exc())

    def _build_reconnect_popup(self):
        self.reconnect_popup = ReconnectPopup(self)
        self.reconnect_popup.add_button(
            "T > N", self.reconnect_t_to_n, "#4a4329",
            "Reconecta clips cambiando rutas de t: a n:"
        )
        self.reconnect_popup.add_button(
            "N > T", self.reconnect_n_to_t, "#4a4329",
            "Reconecta clips cambiando rutas de n: a t:"
        )
        self.reconnect_popup.add_button(
            "Win > Mac", self.execute_reconnect_win_to_mac, "#4a4329",
            "Click: Reconecta todos los clips del timeline\nShift+Click: Reconecta solo los clips seleccionados",
            shift_callback=self.execute_reconnect_win_to_mac_selected
        )

    def show_reconnect_popup(self):
        if self.reconnect_btn_ref is None:
            return
        btn = self.reconnect_btn_ref
        global_pos = btn.mapToGlobal(QtCore.QPoint(btn.width() + 2, 0))
        self.reconnect_popup.move(global_pos)
        self.reconnect_popup.show()

    ###### Reconnect
    def reconnect_t_to_n(self):
        try:
            project = get_active_project()
            if not project:  # Comprobacion de proyecto activo
                debug_print(f"No active project found for Reconnect T > N.")
                return

            with project.beginUndo("Reconnect T > N"):
                self.reconnect_media("t:", "n:")
        except Exception as e:
            debug_print(f"Error: {e}")

    def reconnect_n_to_t(self):
        try:
            project = get_active_project()
            if not project:  # Comprobacion de proyecto activo
                debug_print(f"No active project found for Reconnect N > T.")
                return

            with project.beginUndo("Reconnect N > T"):
                self.reconnect_media("n:", "t:")
        except Exception as e:
            debug_print(f"Error: {e}")

    def execute_reconnect_win_to_mac(self):
        """Ejecuta reconnect y selfreplace para todos los clips del timeline."""
        debug_print_b("\n=== INICIANDO PROCESO DE RECONNECT + REPLACE (TODOS LOS CLIPS) ===")

        try:
            debug_print_b("\n>>> Ejecutando Reconnect script (todos los clips)...")
            self.execute_external_script_with_param("LGA_NKS_Reconnect.py", force_all_clips=True)
            debug_print_b(">>> Reconnect script completado")
        except Exception as e:
            debug_print_b(f"Error en Reconnect: {e}")

        try:
            debug_print_b("\n>>> Ejecutando SelfReplace script (todos los clips)...")
            self.execute_external_script_with_param("LGA_NKS_SelfReplaceClip.py", force_all_clips=True)
            debug_print_b(">>> SelfReplace script completado")
        except Exception as e:
            debug_print_b(f"Error en SelfReplace: {e}")

        debug_print_b("\n=== PROCESO COMPLETO ===")

    def execute_reconnect_win_to_mac_selected(self):
        """Ejecuta reconnect y selfreplace solo para los clips seleccionados."""
        debug_print_b("\n=== INICIANDO PROCESO DE RECONNECT + REPLACE (CLIPS SELECCIONADOS) ===")

        try:
            debug_print_b("\n>>> Ejecutando Reconnect script (clips seleccionados)...")
            self.execute_external_script_with_param("LGA_NKS_Reconnect.py", force_all_clips=False)
            debug_print_b(">>> Reconnect script completado")
        except Exception as e:
            debug_print_b(f"Error en Reconnect: {e}")

        try:
            debug_print_b("\n>>> Ejecutando SelfReplace script (clips seleccionados)...")
            self.execute_external_script_with_param("LGA_NKS_SelfReplaceClip.py", force_all_clips=False)
            debug_print_b(">>> SelfReplace script completado")
        except Exception as e:
            debug_print_b(f"Error en SelfReplace: {e}")

        debug_print_b("\n=== PROCESO COMPLETO ===")

    def reconnect_media(self, old_prefix, new_prefix):
        try:
            seq = hiero.ui.activeSequence()
            if not seq:
                debug_print("No active sequence found.")
                return

            te = hiero.ui.getTimelineEditor(seq)
            selected_clips = te.selection()

            if len(selected_clips) == 0:
                debug_print("*** No clips selected on the track ***")
            else:
                for shot in selected_clips:
                    # Obtener el file path del clip seleccionado
                    file_path = shot.source().mediaSource().fileinfos()[0].filename()
                    debug_print("Original file path:", file_path)

                    # Normalizar el path convirtiendo todo a minusculas
                    normalized_file_path = file_path.lower()

                    # Reemplazar el prefijo antiguo por el nuevo
                    new_file_path = normalized_file_path.replace(old_prefix, new_prefix)
                    debug_print("Modified file path:", new_file_path)

                    # Obtener solo la ruta del directorio sin el nombre del archivo
                    directory_path = os.path.dirname(new_file_path)

                    # Reemplazar el clip por el del nuevo path
                    try:
                        shot.reconnectMedia(directory_path)
                        debug_print("Clip reconnected successfully.")
                    except Exception as e:
                        debug_print(f"Error reconnecting clip: {e}")
        except Exception as e:
            debug_print(f"Error: {e}")

    def reconnectMediaFromTimeline(self):
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("\nNo active sequence found.")
            return

        te = hiero.ui.getTimelineEditor(seq)
        selected_track_items = te.selection()

        if len(selected_track_items) == 0:
            debug_print("*** No track items selected ***")
            return

        # Obtener la ruta del clip seleccionado
        selected_clip = selected_track_items[
            0
        ]  # Solo usaremos el primer clip seleccionado
        file_path = selected_clip.source().mediaSource().fileinfos()[0].filename()
        initial_path = os.path.dirname(file_path)

        # Agregar una barra al final del path si no esta presente
        if not initial_path.endswith("/"):
            initial_path += "/"

        # Abrir el file browser con la ruta inicial del clip seleccionado
        search_path = hiero.ui.openFileBrowser(
            "Choose directory to search for media", mode=3, initialPath=initial_path
        )[0]

        for track_item in selected_track_items:
            track_item.reconnectMedia(search_path)

    ###### Self ReplaceClip
    def execute_SelfReplaceClip(self):
        self.execute_external_script("LGA_NKS_SelfReplaceClip.py")

    ###### Clean Project
    def clean_project(self):
        """Ejecuta el script externo de limpieza de clips no usados."""
        debug_print_b("\n>>> Ejecutando Clean Project script...")
        try:
            result = self.execute_external_script("LGA_NKS_CleanProject.py")
            if result:
                debug_print_b(">>> Clean Project script completado")
            else:
                debug_print_b(">>> Error al ejecutar Clean Project script")
        except Exception as e:
            debug_print_b(f"Error durante la ejecución de Clean Project: {e}")

    # Metodo para ejecutar scripts externos con parametros
    def execute_external_script_with_param(self, script_name, force_all_clips=False):
        # Intentamos varias rutas posibles para encontrar el script
        script_paths = [
            os.path.join(
                os.path.dirname(__file__), "LGA_NKS_Edit_Panel_py", script_name
            ),
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "LGA_NKS_Edit_Panel_py",
                script_name,
            ),
            os.path.join(
                os.path.dirname(__file__), "LGA_NKS_Shared", script_name
            ),
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "LGA_NKS_Shared",
                script_name,
            ),
            os.path.join(
                os.path.dirname(__file__), "LGA_NKS", script_name
            ),  # Ruta estándar
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "LGA_NKS", script_name
            ),  # Ruta absoluta
            os.path.join(
                os.path.dirname(__file__), "LGA_NKS_Edit", script_name
            ),  # Scripts en la carpeta Edit
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "LGA_NKS_Edit",
                script_name,
            ),  # Scripts en la carpeta Edit (absoluta)
            os.path.join(
                os.path.dirname(__file__), script_name
            ),  # Directamente en la carpeta del panel
            os.path.join(
                "Python/Startup/LGA_NKS", script_name
            ),  # Ruta directa a la carpeta de scripts
        ]

        debug_print_b(f"Intentando localizar script: {script_name}")
        debug_print_b(f"Directorio actual: {os.path.dirname(__file__)}")

        # Probamos con cada posible ruta
        for script_path in script_paths:
            debug_print_b(f"Intentando ruta: {script_path}")
            if os.path.exists(script_path):
                debug_print_b(f"Script encontrado en: {script_path}")
                try:
                    spec = importlib.util.spec_from_file_location(
                        script_name[:-3], script_path
                    )
                    if spec is not None and isinstance(
                        spec.loader, importlib.machinery.SourceFileLoader
                    ):  # Añadir isinstance para el linter
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        # Llamar a la función 'main' con el parámetro force_all_clips
                        if hasattr(module, "main"):
                            module.main(force_all_clips=force_all_clips)
                        else:
                            debug_print_b(f"El script {script_name} no tiene función 'main'")
                            return False

                        return True
                    else:
                        debug_print_b(
                            f"No se pudo crear el spec o loader para el script: {script_name}"
                        )
                        return False
                except Exception as e:
                    debug_print_b(f"Error ejecutando el script {script_name}: {e}")
                    return False

        # Si llegamos aquí, no encontramos el script
        debug_print_b(
            f"Script no encontrado en ninguna de las rutas probadas: {script_name}"
        )
        return False

    # Metodo para ejecutar scripts externos
    def execute_external_script(self, script_name):
        # Intentamos varias rutas posibles para encontrar el script
        script_paths = [
            os.path.join(
                os.path.dirname(__file__), "LGA_NKS_Edit_Panel_py", script_name
            ),
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "LGA_NKS_Edit_Panel_py",
                script_name,
            ),
            os.path.join(
                os.path.dirname(__file__), "LGA_NKS_Shared", script_name
            ),
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "LGA_NKS_Shared",
                script_name,
            ),
            os.path.join(
                os.path.dirname(__file__), "LGA_NKS", script_name
            ),  # Ruta estándar
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "LGA_NKS", script_name
            ),  # Ruta absoluta
            os.path.join(
                os.path.dirname(__file__), "LGA_NKS_Edit", script_name
            ),  # Scripts en la carpeta Edit
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)),
                "LGA_NKS_Edit",
                script_name,
            ),  # Scripts en la carpeta Edit (absoluta)
            os.path.join(
                os.path.dirname(__file__), script_name
            ),  # Directamente en la carpeta del panel
            os.path.join(
                "Python/Startup/LGA_NKS", script_name
            ),  # Ruta directa a la carpeta de scripts
        ]

        debug_print_b(f"Intentando localizar script: {script_name}")
        debug_print_b(f"Directorio actual: {os.path.dirname(__file__)}")

        # Probamos con cada posible ruta
        for script_path in script_paths:
            debug_print_b(f"Intentando ruta: {script_path}")
            if os.path.exists(script_path):
                debug_print_b(f"Script encontrado en: {script_path}")
                try:
                    spec = importlib.util.spec_from_file_location(
                        script_name[:-3], script_path
                    )
                    if spec is not None and isinstance(
                        spec.loader, importlib.machinery.SourceFileLoader
                    ):  # Añadir isinstance para el linter
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)

                        # Tratamos de llamar a la función 'main' o 'test_trim_in'/'test_trim_out' si existe
                        if hasattr(module, "main"):
                            module.main()
                        elif (
                            hasattr(module, "test_trim_in")
                            and script_name == "LGA_NKS_Trim_In.py"
                        ):
                            module.test_trim_in()
                        elif (
                            hasattr(module, "test_trim_out")
                            and script_name == "LGA_NKS_Trim_Out.py"
                        ):
                            module.test_trim_out()

                        return True
                    else:
                        debug_print_b(
                            f"No se pudo crear el spec o loader para el script: {script_name}"
                        )
                        return False
                except Exception as e:
                    debug_print_b(f"Error ejecutando el script {script_name}: {e}")
                    return False

        # Si llegamos aquí, no encontramos el script
        debug_print_b(
            f"Script no encontrado en ninguna de las rutas probadas: {script_name}"
        )
        return False

    # Nuevo metodo para ejecutar LGA_NKS_mediaMissingFrames.py
    def check_frames(self):
        self.execute_external_script("LGA_NKS_mediaMissingFrames.py")

    #### Clear Tag - Movido desde Flow Panel
    def run_clear_tag_script(self):
        project = get_active_project()
        if project:
            with project.beginUndo("Run External Script"):
                seq = hiero.ui.activeSequence()
                if seq:
                    te = hiero.ui.getTimelineEditor(seq)
                    selected_items = te.selection()

                    for item in selected_items:
                        if not isinstance(
                            item, hiero.core.EffectTrackItem
                        ):  # Verificacion de que el clip no sea un efecto
                            # Importar y ejecutar el script de la subcarpeta para cada clip valido
                            script_path = os.path.join(
                                os.path.dirname(__file__),
                                "LGA_NKS_Shared",
                                "LGA_NKS_Delete_ClipTags.py",
                            )
                            if os.path.exists(script_path):
                                try:
                                    spec = importlib.util.spec_from_file_location(
                                        "LGA_H_DeleteClipTags", script_path
                                    )
                                    if spec is not None and isinstance(
                                        spec.loader,
                                        importlib.machinery.SourceFileLoader,
                                    ):  # Añadir isinstance para el linter
                                        module = importlib.util.module_from_spec(spec)
                                        spec.loader.exec_module(module)
                                        module.delete_tags_from_clip(
                                            item
                                        )  # Pasar el clip valido como parametro
                                        # debug_print("Script ejecutado correctamente.")
                                    else:
                                        debug_print_b(
                                            f"No se pudo crear el spec o loader para el script: LGA_H_DeleteClipTags.py"
                                        )
                                except Exception as e:
                                    debug_print_b(
                                        f"Error al ejecutar el script para el clip {item}: {e}"
                                    )
                            else:
                                debug_print_b(
                                    f"Script no encontrado en la ruta: {script_path}"
                                )
        else:
            debug_print("No active project found for Clear Tag.")

    #### Match Rev Ver - Nuevo boton para EXR to REV Version Matcher
    def match_rev_version(self):
        """Ejecuta el script de match de versiones EXR to REV."""
        debug_print_b("Ejecutando Match Rev Ver (modo normal)...")
        self._execute_match_rev_version(force_all_clips=False)

    def match_rev_version_force_all(self):
        """Ejecuta el script de match de versiones EXR to REV forzando todos los clips."""
        debug_print_b("Ejecutando Match Rev Ver (forzando todos los clips)...")
        self._execute_match_rev_version(force_all_clips=True)

    def _execute_match_rev_version(self, force_all_clips=False):
        """Ejecuta el script de match de versiones con parametro force_all_clips."""
        debug_print_b(f"DEBUG: Iniciando _execute_match_rev_version con force_all_clips={force_all_clips}")
        try:
            # Importar y ejecutar el script desde la carpeta LGA_NKS_Edit
            script_path = os.path.join(
                os.path.dirname(__file__),
                "LGA_NKS_Edit_Panel_py",
                "LGA_NKS_MatchVerToEXR.py",
            )
            debug_print_b(f"DEBUG: Script path: {script_path}")
            debug_print_b(f"DEBUG: Script exists: {os.path.exists(script_path)}")
            if os.path.exists(script_path):
                try:
                    spec = importlib.util.spec_from_file_location(
                        "LGA_NKS_MatchVerToEXR", script_path
                    )
                    if spec is not None and spec.loader is not None:
                        debug_print_b("DEBUG: Spec y loader válidos, ejecutando módulo...")
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        # Llamar a la funcion principal con el parametro
                        module.match_exr_to_rev(force_all_clips=force_all_clips)
                        debug_print_b("Match Rev Ver script ejecutado correctamente.")
                    else:
                        debug_print_b(
                            f"DEBUG: Spec o loader inválidos. Spec: {spec}, Loader: {spec.loader if spec else None}"
                        )
                except Exception as e:
                    debug_print_b(f"Error al ejecutar el script Match Rev Ver: {e}")
            else:
                debug_print_b(f"Script no encontrado en la ruta: {script_path}")
        except Exception as e:
            debug_print_b(f"Error general en _execute_match_rev_version: {e}")

    #### Compare Rev EdRef - Nuevo boton para comparar REV con EditRef
    def compare_rev_editref(self):
        """Ejecuta el script de comparacion REV vs EditRef (modo playhead)."""
        debug_print_b("Ejecutando Compare Rev EdRef (modo playhead)...")
        self._execute_compare_rev_editref(force_all_clips=False)

    def compare_rev_editref_force_all(self):
        """Ejecuta el script de comparacion REV vs EditRef forzando todos los clips."""
        debug_print_b("Ejecutando Compare Rev EdRef (forzando todos los clips)...")
        self._execute_compare_rev_editref(force_all_clips=True)

    def _execute_compare_rev_editref(self, force_all_clips=False):
        """Ejecuta el script de comparacion con parametro force_all_clips."""
        try:
            # Importar y ejecutar el script desde la carpeta LGA_NKS_Edit
            script_path = os.path.join(
                os.path.dirname(__file__),
                "LGA_NKS_Edit_Panel_py",
                "LGA_NKS_CompareVerToEditref.py",
            )
            if os.path.exists(script_path):
                try:
                    spec = importlib.util.spec_from_file_location(
                        "LGA_NKS_CompareVerToEditref", script_path
                    )
                    if spec is not None and isinstance(
                        spec.loader,
                        importlib.machinery.SourceFileLoader,
                    ):
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        # Llamar a la funcion principal con el parametro
                        module.compare_rev_to_editref(force_all_clips=force_all_clips)
                        debug_print_b(
                            "Compare Rev EdRef script ejecutado correctamente."
                        )
                    else:
                        debug_print_b(
                            f"No se pudo crear el spec o loader para el script: LGA_NKS_CompareVerToEditref.py"
                        )
                except Exception as e:
                    debug_print_b(f"Error al ejecutar el script Compare Rev EdRef: {e}")
            else:
                debug_print_b(f"Script no encontrado en la ruta: {script_path}")
        except Exception as e:
            debug_print_b(f"Error general en _execute_compare_rev_editref: {e}")

    #### Compare EXR aPlate - Nuevo boton para comparar EXR con aPlate
    def compare_exr_aplate(self):
        """Ejecuta el script de comparacion EXR vs aPlate (modo playhead)."""
        debug_print_b("Ejecutando Compare EXR aPlate (modo playhead)...")
        self._execute_compare_exr_aplate(force_all_clips=False)

    def compare_exr_aplate_force_all(self):
        """Ejecuta el script de comparacion EXR vs aPlate forzando todos los clips."""
        debug_print_b("Ejecutando Compare EXR aPlate (forzando todos los clips)...")
        self._execute_compare_exr_aplate(force_all_clips=True)

    def _execute_compare_exr_aplate(self, force_all_clips=False):
        """Ejecuta el script de comparacion EXR vs aPlate con parametro force_all_clips."""
        debug_print_b(f"DEBUG: Iniciando _execute_compare_exr_aplate con force_all_clips={force_all_clips}")
        try:
            # Importar y ejecutar el script desde la carpeta LGA_NKS_Edit
            script_path = os.path.join(
                os.path.dirname(__file__),
                "LGA_NKS_Edit_Panel_py",
                "LGA_NKS_CompareEXR_to_aPlate.py",
            )
            debug_print_b(f"DEBUG: Script path: {script_path}")
            debug_print_b(f"DEBUG: Script exists: {os.path.exists(script_path)}")
            if os.path.exists(script_path):
                try:
                    spec = importlib.util.spec_from_file_location(
                        "LGA_NKS_CompareEXR_to_aPlate", script_path
                    )
                    if spec is not None and spec.loader is not None:
                        debug_print_b("DEBUG: Spec y loader válidos, ejecutando módulo...")
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        # Llamar a la funcion principal con el parametro
                        module.compare_exr_to_aplate(force_all_clips=force_all_clips)
                        debug_print_b(
                            "Compare EXR aPlate script ejecutado correctamente."
                        )
                    else:
                        debug_print_b(
                            f"DEBUG: Spec o loader inválidos. Spec: {spec}, Loader: {spec.loader if spec else None}"
                        )
                except Exception as e:
                    debug_print_b(
                        f"Error al ejecutar el script Compare EXR aPlate: {e}"
                    )
            else:
                debug_print_b(f"Script no encontrado en la ruta: {script_path}")
        except Exception as e:
            debug_print_b(f"Error general en _execute_compare_exr_aplate: {e}")
def get_active_project():
    """
    Obtiene el proyecto activo en Hiero.

    Returns:
    - hiero.core.Project o None: El proyecto activo, o None si no se encuentra ningun proyecto activo.
    """
    projects = hiero.core.projects()
    if projects:
        return projects[0]  # Devuelve el primer proyecto en la lista
    else:
        return None

# Crear la instancia del widget y anadirlo al gestor de ventanas de Hiero
reconnectWidget = ReconnectMediaWidget()
wm = hiero.ui.windowManager()
wm.addWindow(reconnectWidget)
