"""
____________________________________________________________________

  LGA_NKS_Flow_Panel v2.52 | Lega

  Panel con herramientas que interactuan con las tasks de Flow Production Tracking
  que fueron descargadas previamente con la app LGA_NKS_Flow_Downloader
  Actualizado para ser compatible con ambos sistemas de nomenclatura:
  - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
  - PROYECTO_SEQ_SHOT (3 bloques simplificado)

  v2.52: Agregado Rev Charly a la lista de botones
  v2.51: Agregado logging a archivo con switches de debug
  v2.50: Actualizado para usar scroll bar cuando es necesario
  v2.49: Actualizado para usar estilos dinámicos con bordes y hover para todos los botones
         Agregado tooltip dinámico para todos los botones
         Optimizado espaciado del layout y dimensiones de botones para mejor UX
  v2.48: Actualizado para usar método centralizado de selección de clips (LGA_NKS_GetClip).
         Ahora usa el Método 2 híbrido (playhead primero, luego selección como fallback)
         para obtener clips del track TRACK_comp_EXR. Soporta selecciones múltiples.
____________________________________________________________________
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
from pathlib import Path
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore
from LGA_NKS_Shared.LGA_NKS_PipeSyncPreflight import (
    validate_pull_preflight,
    validate_push_preflight,
)

# Importar utilidades de naming
sys.path.append(str(Path(__file__).parent / "LGA_NKS_Shared"))
from LGA_NKS_Flow_NamingUtils import clean_base_name

# Importar funciones de utilidad de estilos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "LGA_NKS_Shared"))
from LGA_NKS_Shared.LGA_NKS_StyleUtils import (
    calculate_dynamic_border,
    calculate_dynamic_hover,
    create_tooltip_stylesheet
)


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


def setup_debug_logging(script_name="FlowPanel"):
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


debug_logger = setup_debug_logging(script_name="FlowPanel")

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


class ColorChangeWidget(QtWidgets.QWidget):
    def __init__(self):
        super(ColorChangeWidget, self).__init__()

        self.setObjectName("com.lega.FPTPanel")
        self.setWindowTitle("Flow")
        debug_print("=== FlowPanel init ===")

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
        self.layout = QtWidgets.QGridLayout()  # Usamos QGridLayout
        self.layout.setHorizontalSpacing(6)
        self.layout.setVerticalSpacing(3)
        self.scroll_widget.setLayout(self.layout)
        self.scroll_area.setWidget(self.scroll_widget)

        # Crear botones y agregarlos al layout con coordenadas especificas
        self.buttons = [
            {
                "name": "Flow Pull",
                "color": None,
                "style": "#1f1f1f",
                "action": "fpt_pull",
            },
            {
                "name": "Sho&t Info",
                "color": None,
                "style": "#1f1f1f",
                "action": "shot_info",
                "shortcut": "Shift+T",
            },
            {
                "name": "Review Pic",
                "color": None,
                "style": "#1f1f1f",
                "action": "review_pic",
            },  # Reemplazado Clear Tag
            {
                "name": "Corrections",
                "color": QtGui.QColor(46, 119, 212),
                "style": "#2e77d4",
                "action": "color",
            },
            # {"name": "Corrs_Lega", "color": QtGui.QColor(105, 19, 94), "style": "#69135e", "action": "color"},
            {
                "name": "Rev Sebas",
                "color": QtGui.QColor(189, 127, 159),
                "style": "#bd7f9f",
                "action": "color",
            },
            {
                "name": "Rev Charly",
                "color": QtGui.QColor(169, 144, 157),
                "style": "#a9909d",
                "action": "color",
            },
            {
                "name": "Rev Juano",
                "color": QtGui.QColor(64, 34, 52),
                "style": "#7F4B69",
                "action": "color",
            },
            {
                "name": "Rev Javi",
                "color": QtGui.QColor(156, 62, 94),
                "style": "#9c3e5e",
                "action": "color",
            },
            {
                "name": "Rev Lega",
                "color": QtGui.QColor(105, 19, 94),
                "style": "#69135e",
                "action": "color",
            },
            {
                "name": "Rev Hold",
                "color": QtGui.QColor(147, 49, 0),
                "style": "#933100",
                "action": "color",
            },
            {
                "name": "Rev Dir",
                "color": QtGui.QColor(152, 192, 84),
                "style": "#98c054",
                "action": "color",
            },
            {
                "name": "Approved",
                "color": QtGui.QColor(36, 76, 25),
                "style": "#244c19",
                "action": "color",
            },
            {
                "name": "Delivery Ok",
                "color": QtGui.QColor(82, 194, 51),
                "style": "#52C233",
                "action": "color",
            },
            {
                "name": "Rev Dir Den",
                "color": QtGui.QColor(77, 33, 168),
                "style": "#4d21a8",
                "action": "color",
            },
        ]

        self.num_columns = 1  # Inicialmente una columna
        self.button_width_hint = 0
        self.create_buttons()

        # Conectar la senal de cambio de tamano del widget al metodo correspondiente
        self.adjust_columns_on_resize()
        self.resizeEvent = self.adjust_columns_on_resize

    def showEvent(self, event):
        super(ColorChangeWidget, self).showEvent(event)
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
            name = button_info["name"]
            color = button_info["color"]
            style = button_info["style"]
            action = button_info["action"]

            # Crear un bot?n personalizado que maneje el Shift+Click
            button = CustomButton(name)

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
            has_tooltip = (
                action == "fpt_pull" or
                action == "review_pic" or
                action == "shot_info"
            )

            if has_tooltip:
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
            if action == "color":
                button.setCustomClickHandler(self.handle_color_button_click(color, name))
                button.setShiftClickHandler(
                    self.handle_color_button_shift_click(color, name)
                )
            elif action == "fpt_pull":
                button.setCustomClickHandler(self.run_FPT_pull_with_deselect)
                button.setShiftClickHandler(self.run_FPT_pull)
                # Tooltip que explica las dos funcionalidades del bot?n Flow Pull
                tooltip_text = (
                    "Click: Pull de todos los shots del timeline\n"
                    "Shift+Click: Pull solo del shot seleccionado"
                )
                button.setToolTip(tooltip_text)
            elif action == "review_pic":
                button.clicked.connect(self.run_review_pic_script)
                button.setToolTip(
                    "Crea snapshot del viewer y lo guarda con su n?mero de frame para ser enviado junto con los comentarios"
                )
            elif action == "shot_info":
                button.clicked.connect(self.run_shot_info_script)
                if "shortcut" in button_info:
                    button.setShortcut(QtGui.QKeySequence(button_info["shortcut"]))
                button.setToolTip(
                    "Muestra informaci?n del shot y comentarios de las versiones de la task comp"
                )

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

    def run_FPT_pull_with_deselect(self):

        """Version del FPT Pull que procesa todos los clips"""
        debug_print("Ejecutando Flow Pull forzando procesamiento de todos los clips...")
        is_valid, error_text, _state = validate_pull_preflight()
        if not is_valid:
            QtWidgets.QMessageBox.warning(self, "PipeSync no configurado", error_text)
            return

        # Obtener el proyecto actual
        project = hiero.core.projects()[0] if hiero.core.projects() else None
        if project:
            project.beginUndo("Run External Script")
            try:
                script_path = os.path.join(
                    os.path.dirname(__file__), "LGA_NKS_Flow_Panel_py", "LGA_NKS_Flow_Pull.py"
                )
                if os.path.exists(script_path):
                    try:
                        import importlib.util

                        spec = importlib.util.spec_from_file_location(
                            "LGA_NKS_Flow_Pull", script_path
                        )
                        if spec is not None and spec.loader is not None:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            # Llamar a FPT_Hiero con force_all_clips=True
                            module.FPT_Hiero(force_all_clips=True)
                    except Exception as e:
                        debug_print(f"Error al ejecutar el script: {e}")
                else:
                    debug_print(f"Script no encontrado en la ruta: {script_path}")
            finally:
                project.endUndo()

    #### Pull
    def run_FPT_pull(self):
        is_valid, error_text, _state = validate_pull_preflight()
        if not is_valid:
            QtWidgets.QMessageBox.warning(self, "PipeSync no configurado", error_text)
            return

        # Obtener el proyecto actual
        project = hiero.core.projects()[0] if hiero.core.projects() else None
        if project:
            project.beginUndo("Run External Script")
            try:
                # Importar y ejecutar el script de la subcarpeta
                script_path = os.path.join(
                    os.path.dirname(__file__), "LGA_NKS_Flow_Panel_py", "LGA_NKS_Flow_Pull.py"
                )
                if os.path.exists(script_path):
                    try:
                        import importlib.util

                        spec = importlib.util.spec_from_file_location(
                            "LGA_NKS_Flow_Pull", script_path
                        )
                        if spec is not None and spec.loader is not None:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            module.FPT_Hiero()
                            # debug_print("Script ejecutado correctamente.")
                    except Exception as e:
                        debug_print(f"Error al ejecutar el script: {e}")
                else:
                    debug_print(f"Script no encontrado en la ruta: {script_path}")
            finally:
                project.endUndo()

    #### Shot info
    def run_shot_info_script(self):
        project = hiero.core.projects()[0] if hiero.core.projects() else None
        if project:
            project.beginUndo("Run External Script")
            try:
                script_path = os.path.join(
                    os.path.dirname(__file__),
                    "LGA_NKS_Flow_Panel_py",
                    "LGA_NKS_Flow_Shot_info.py",
                )
                if os.path.exists(script_path):
                    try:
                        import importlib.util

                        spec = importlib.util.spec_from_file_location(
                            "LGA_NKS_Flow_Shot_info", script_path
                        )
                        if spec is not None and spec.loader is not None:
                            module = importlib.util.module_from_spec(spec)
                            spec.loader.exec_module(module)
                            module.main()  # Asumimos que el script tiene un metodo main
                    except Exception as e:
                        debug_print(f"Error al ejecutar el script: {e}")
                else:
                    debug_print(f"Script no encontrado en la ruta: {script_path}")
            finally:
                project.endUndo()

    #### Clear Tag
    def run_clear_tag_script(self):
        project = hiero.core.projects()[0] if hiero.core.projects() else None
        if project:
            project.beginUndo("Run External Script")
            try:
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
                                    import importlib.util

                                    spec = importlib.util.spec_from_file_location(
                                        "LGA_H_DeleteClipTags", script_path
                                    )
                                    if spec is not None and spec.loader is not None:
                                        module = importlib.util.module_from_spec(spec)
                                        spec.loader.exec_module(module)
                                        module.delete_tags_from_clip(
                                            item
                                        )  # Pasar el clip valido como parametro
                                        # debug_print("Script ejecutado correctamente.")
                                    else:
                                        debug_print(
                                            f"Script no encontrado o loader no disponible en la ruta: {script_path}"
                                        )
                                except Exception as e:
                                    debug_print(
                                        f"Error al ejecutar el script para el clip {item}: {e}"
                                    )
                            else:
                                debug_print(
                                    f"Script no encontrado en la ruta: {script_path}"
                                )
            finally:
                project.endUndo()

    #### Review Pic - Copiado de ViewerPanel SnapShot
    def run_review_pic_script(self):
        try:
            script_path = os.path.join(
                    os.path.dirname(__file__), "LGA_NKS_Flow_Panel_py", "LGA_NKS_ReviewPic.py"
            )
            if os.path.exists(script_path):
                import importlib.util

                spec = importlib.util.spec_from_file_location(
                    "LGA_NKS_ReviewPic", script_path
                )
                if spec is not None and spec.loader is not None:
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    # Llamar a la funcion principal del script
                    module.main()
                    debug_print("Ejecutado LGA_NKS_ReviewPic script.")
            else:
                debug_print(f"Script no encontrado en la ruta: {script_path}")
        except Exception as e:
            debug_print(f"Error al ejecutar el script ReviewPic: {e}")

    #### Push
    def handle_color_button_click(self, color, button_name):
        def button_click_handler(_=None):
            confirmation = self.confirm_status_application(button_name)
            if confirmation:
                self.change_clip_color_and_push_status(color, button_name)
                if button_name in ["Rev_Dir", "Corrections"]:
                    self.run_clear_tag_script()

        return button_click_handler

    def handle_color_button_shift_click(self, color, button_name):
        def button_shift_click_handler():
            confirmation = self.confirm_status_application(button_name)
            if confirmation:
                self.change_clip_color_and_push_status(
                    color,
                    button_name,
                    flow_target_version_mode=True,
                )
                if button_name in ["Rev_Dir", "Corrections"]:
                    self.run_clear_tag_script()

        return button_shift_click_handler

    def parse_exr_name(self, exr_name):
        """
        Extrae el nombre base del archivo EXR.
        Compatible con ambos sistemas de nomenclatura.
        """
        try:
            # Guardar el nombre original para validación
            original_name = exr_name

            # Ajustar el manejo del formato del nombre del archivo EXR
            if "%04d" in exr_name:
                exr_name = exr_name.replace(
                    ".%", "_%"
                )  # Reemplazar patron para analisis

            # Verificar que tenga una versión en el nombre original ANTES de limpiar
            version_match = re.search(r"_v(\d+)", original_name)
            if not version_match:
                raise ValueError(
                    f"Nombre del archivo EXR no tiene versión válida: {original_name}"
                )

            # Usar función compartida para limpiar el nombre base
            base_name = clean_base_name(original_name)

            # Validar que tenga al menos los campos básicos (proyecto_seq_shot_task)
            parts = base_name.split("_")
            if len(parts) < 3:
                raise ValueError(
                    f"Nombre del archivo EXR no tiene el formato esperado (muy corto): {original_name}"
                )

            return base_name
        except ValueError:
            # Re-lanzar ValueError tal cual
            raise
        except Exception as e:
            debug_print(f"Error en parse_exr_name: {e}")
            raise ValueError(
                f"Nombre del archivo EXR no tiene el formato esperado: {exr_name}"
            )

    def push_task_status(
        self, button_name, base_name, update_callback=None, original_file_name=None
    ):
        try:
            # Importar y ejecutar el script de push
            script_path = os.path.join(
                os.path.dirname(__file__), "LGA_NKS_Flow_Panel_py", "LGA_NKS_Flow_Push.py"
            )
            if os.path.exists(script_path):
                try:
                    import importlib.util

                    spec = importlib.util.spec_from_file_location(
                        "LGA_NKS_Flow_Push", script_path
                    )
                    if spec is not None and spec.loader is not None:
                        module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(module)
                        result = module.Push_Task_Status(
                            button_name, base_name, update_callback, original_file_name
                        )
                        return result  # Retornar el resultado de la operacion (True o False)
                    else:
                        debug_print(
                            f"Script no encontrado o loader no disponible en la ruta: {script_path}"
                        )
                        return False
                except Exception as e:
                    debug_print(f"Error durante la operacion de push: {e}")
                    return False
            else:
                debug_print(f"Script no encontrado en la ruta: {script_path}")
                return False
        except Exception as e:
            debug_print(f"Error durante la operacion de push: {e}")
            return False

    def change_clip_color_and_push_status(
        self, color, button_name, flow_target_version_mode=False
    ):
        """
        Ejecuta el push usando el método centralizado. La resolución de task y la
        recopilación de clips se delegan a push_from_selected_clips (que usa el
        TaskSelectionDialog para elegir la task activa en el playhead).
        El color del clip se cambia SOLO si el push es exitoso (vía callback).
        """
        try:
            is_valid, error_text, _state = validate_push_preflight()
            if not is_valid:
                QtWidgets.QMessageBox.warning(self, "PipeSync no configurado", error_text)
                return

            # Importar el módulo Push para usar el método centralizado
            script_path = os.path.join(
                os.path.dirname(__file__), "LGA_NKS_Flow_Panel_py", "LGA_NKS_Flow_Push.py"
            )
            if not os.path.exists(script_path):
                debug_print(f"Script no encontrado en la ruta: {script_path}")
                return

            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "LGA_NKS_Flow_Push", script_path
            )
            if spec is None or spec.loader is None:
                debug_print("No se pudo cargar el módulo LGA_NKS_Flow_Push")
                return

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Definir callback que cambia el color SOLO después de push exitoso
            def change_color_callback(clip, base_name, exr_name):
                """Callback que cambia el color del clip después de push exitoso"""
                try:
                    project = (
                        hiero.core.projects()[0] if hiero.core.projects() else None
                    )
                    if project:
                        project.beginUndo("Change Clip Color")
                        try:
                            bin_item = clip.source().binItem()
                            if bin_item:
                                active_version = bin_item.activeVersion()
                                if active_version:
                                    bin_item.setColor(color)
                                    debug_print(
                                        f"Color cambiado para clip (después de push exitoso): {exr_name}"
                                    )
                        finally:
                            project.endUndo()
                except Exception as e:
                    debug_print(f"Error cambiando color del clip {exr_name}: {e}")

            # La task se resuelve internamente en push_from_selected_clips
            result = module.push_from_selected_clips(
                button_name,
                change_color_callback,
                flow_target_version_mode=flow_target_version_mode,
            )
            if not result:
                debug_print("Push cancelado o fallido")

        except Exception as e:
            debug_print(f"Error durante la operacion: {e}")
            import traceback

            debug_print(traceback.format_exc())

    def confirm_status_application(self, status):
        """
        La confirmación para más de 4 clips es manejada internamente por
        push_from_selected_clips (después de resolver la task activa).
        Este método siempre retorna True para no bloquear el flujo.
        """
        return True

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

# Crear la instancia del widget y anadirlo al gestor de ventanas de Hiero
colorChanger = ColorChangeWidget()
wm = hiero.ui.windowManager()
wm.addWindow(colorChanger)
