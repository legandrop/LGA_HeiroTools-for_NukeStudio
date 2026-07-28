"""
____________________________________________________________________

  LGA_ReviewPanel v2.82 | Lega

  Tools panel for Hiero / Nuke Studio

  v2.82: Movido boton Self ReplaceClip al Edit Panel.
  v2.81: Agregados botones Next Annotation y Previous Annotation para navegar
         las anotaciones del clip seleccionado.
  v2.80: Agregado boton Contact Sheet para pegar clips seleccionados en NukeX

  v2.79: Agregado botón ON OFF _roto_ con shortcut Ctrl+Shift+D
  v2.78: Agregado sistema de scroll, logging a archivo y gap vertical
  v2.77: Sin botón Check Project Versions
  v2.76: Actualizado para usar estilos dinámicos con bordes y hover para todos los botones
         Agregado tooltip dinámico para todos los botones
         Optimizado espaciado del layout y dimensiones de botones para mejor UX
____________________________________________________________________

"""

import hiero.ui
import hiero.core
import os
import re
import subprocess
import socket
import importlib.util
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


def setup_debug_logging(script_name="ReviewPanel"):
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


debug_logger = setup_debug_logging(script_name="ReviewPanel")

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


class ReviewPanel(QtWidgets.QWidget):
    def __init__(self):
        super(ReviewPanel, self).__init__()

        self.setObjectName("com.lega.RevtoolPanel")
        self.setWindowTitle("Review")
        debug_print("=== ReviewPanel init ===")

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
            ("ON Clips | OFF v00", self.execute_EnableOrDisableClips, "#0e1f3a", None, "Click: Activa todos los clips del timeline y desactiva los clips v00\nShift+Click: Solo en los clips seleccionados"),
            ("ON OFF _comp_", self.execute_DisableEXR, "#0e1f3a", "Shift+D", "Shift+D\nHabilita/deshabilita el clip del track _comp_"),
            ("ON OFF _roto_", self.execute_DisableRoto, "#0e1f3a", "Ctrl+Shift+D", "Ctrl+Shift+D\nHabilita/deshabilita el clip del track _roto_"),
            (
                "Difference Mode",
                self.execute_ToggleBlendModeForEXRTrack,
                "#283526",
                None,
                "Toggle del modo Difference del track _comp_",
            ),
            ("Compare Versions", self.execute_CompareVersions, "#273c24", None, "Crea un nuevo track 'COMPARE' con una versión anterior del clip seleccionado y pone al track en modo difference"),
            ("Compare OFF", self.execute_CompareVersionsOff, "#273c24", None, "Remueve el track 'COMPARE' y desactiva el modo Difference"),
            ("Contact Sheet", self.execute_ContactSheet, "#273c24", None, "Crear en NukeX un LGA_Contact_Sheet con los clips seleccionados"),
            (
                "Reveal in &Explorer",
                self.execute_RevealInExplorer,
                "#321a1a",
                "Shift+E",
                "Shift+E\nRevela los archivos de los clips seleccionados en el explorer",
            ),
            ("Reveal NKS Project", self.execute_RevealNKSProject, "#321a1a", None, "Revela el proyecto NKS activo en el explorer"),
            (
                "Reveal NK Sc&ript",
                self.execute_RevealNKScript,
                "#321a1a",
                "Shift+R",
                "Shift+R\nAbre la carpeta que contiene al script de Nuke asociado al clip seleccionado",
            ),
            ("OpenInNuke&X", self.execute_OpenInNukeX, "#493800", "Shift+X", "Shift+X\nAbre en Nuke el script asociado al clip seleccionado"),
            (
                "Next Annotation",
                self.execute_NextAnnotation,
                "#283526",
                None,
                "Salta a la proxima anotacion del clip seleccionado. Al llegar al final vuelve a la primera.",
            ),
            (
                "Previous Annotation",
                self.execute_PreviousAnnotation,
                "#283526",
                None,
                "Salta a la anotacion anterior del clip seleccionado. Al llegar al inicio vuelve a la ultima.",
            ),
        ]

        self.num_columns = 1  # Inicialmente una columna
        self.button_width_hint = 0
        self.create_buttons()

        # Conectar la senal de cambio de tamano del widget al metodo correspondiente
        self.adjust_columns_on_resize()
        self.resizeEvent = self.adjust_columns_on_resize

    def showEvent(self, event):
        super(ReviewPanel, self).showEvent(event)
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
                button_object_name = f"button_{index}"
                # Crear stylesheet de tooltip din?mico
                tooltip_stylesheet = create_tooltip_stylesheet(style)
                tooltip_stylesheet = tooltip_stylesheet.replace("QToolTip", f"#{button_object_name} QToolTip")
                button_stylesheet += tooltip_stylesheet

            if name == "ON Clips | OFF v00":
                button = CustomButton(name)
                button.setCustomClickHandler(self.execute_EnableOrDisableClips_all_clips)
                button.setShiftClickHandler(handler)
            else:
                button = QtWidgets.QPushButton(name)
                button.clicked.connect(handler)

            button.setObjectName(f"button_{index}")
            button.setStyleSheet(button_stylesheet)

            if tooltip:
                button.setToolTip(tooltip)
            if shortcut:
                button.setShortcut(shortcut)

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

    # Metodo generico para ejecutar scripts externos
    def execute_external_script(self, script_name, *args):
        script_path = os.path.join(os.path.dirname(__file__), "LGA_NKS_Review_Panel_py", script_name)
        if os.path.exists(script_path):
            try:
                spec = importlib.util.spec_from_file_location(
                    script_name[:-3], script_path
                )
                if spec is not None and spec.loader is not None:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    module.main(*args)
                else:
                    debug_print(
                        f"El modulo o loader no se encontraron para el script {script_name}"
                    )
            except Exception as e:
                debug_print(f"Error ejecutando el script {script_name}: {e}")
        else:
            debug_print(f"Script no encontrado en la ruta: {script_path}")

    def execute_external_script_from_edit(self, script_name):
        script_path = os.path.join(os.path.dirname(__file__), "LGA_NKS_Shared", script_name)
        if os.path.exists(script_path):
            try:
                spec = importlib.util.spec_from_file_location(
                    script_name[:-3], script_path
                )
                if spec is not None and spec.loader is not None:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    module.main()
                else:
                    debug_print(
                        f"El modulo o loader no se encontraron para el script {script_name}"
                    )
            except Exception as e:
                debug_print(f"Error ejecutando el script {script_name}: {e}")
        else:
            debug_print(f"Script no encontrado en la ruta: {script_path}")

    # Handlers para cada boton que ejecutan scripts externos
    def execute_EnableOrDisableClips(self):
        self.execute_external_script("LGA_NKS_ON_Clips_OFF_v00-Clips.py")
    
    def execute_EnableOrDisableClips_all_clips(self):
        """Versión que procesa todos los clips del timeline, no solo los seleccionados"""
        script_path = os.path.join(
            os.path.dirname(__file__),
            "LGA_NKS_Review_Panel_py",
            "LGA_NKS_ON_Clips_OFF_v00-Clips.py",
        )
        if os.path.exists(script_path):
            try:
                spec = importlib.util.spec_from_file_location(
                    "LGA_NKS_ON_Clips_OFF_v00-Clips", script_path
                )
                if spec is not None and spec.loader is not None:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    # Llamar a main con force_all_clips=True
                    module.main(force_all_clips=True)
                else:
                    debug_print(
                        f"El módulo o loader no se encontraron para el script LGA_NKS_ON_Clips_OFF_v00-Clips.py"
                    )
            except Exception as e:
                debug_print(f"Error ejecutando el script con todos los clips: {e}")
        else:
            debug_print(f"Script no encontrado en la ruta: {script_path}")

    def execute_ToggleBlendModeForEXRTrack(self):
        self.execute_external_script("LGA_NKS_EXRTrack_Difference.py")

    def execute_CompareVersions(self):
        self.execute_external_script("LGA_NKS_Compare_Versions.py")

    def execute_CompareVersionsOff(self):
        self.execute_external_script("LGA_NKS_Compare_Versions_OFF.py")

    def execute_ContactSheet(self):
        self.execute_external_script("LGA_Contact_Sheet_OpenInNukeX.py")

    def execute_RevealInExplorer(self):
        self.execute_external_script("LGA_NKS_RevealInExplorer.py")

    def execute_RevealNKSProject(self):
        self.execute_external_script("LGA_NKS_RevealNKS_Project.py")

    def execute_RevealNKScript(self):
        self.execute_external_script("LGA_NKS_RevealNK_Script.py")

    def execute_OpenInNukeX(self):
        self.execute_external_script("LGA_NKS_OpenInNukeX.py")

    def execute_DisableEXR(self):
        self.execute_external_script("LGA_NKS_Clip_DisableEXR.py")

    def execute_DisableRoto(self):
        self.execute_external_script("LGA_NKS_Clip_DisableRoto.py")

    def execute_NextAnnotation(self):
        self.execute_external_script("LGA_NKS_NextPrev_Annotation.py")

    def execute_PreviousAnnotation(self):
        self.execute_external_script("LGA_NKS_NextPrev_Annotation.py", "previous")


# Crear la instancia del widget y anadirlo al gestor de ventanas de Hiero
reconnectWidget = ReviewPanel()
wm = hiero.ui.windowManager()
wm.addWindow(reconnectWidget)
