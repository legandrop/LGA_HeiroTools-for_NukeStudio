"""
____________________________________________________________________

  LGA_NKS_Flow_Assignee_Panel v1.60 | Lega

  Panel para obtener los asignados de la tarea del clip seleccionado en Flow,
  limpiarlos o sumar asignados a la tarea comp.

  v1.60: Los carteles de aviso pasan al helper LGA_NKS_MessageBox con el
         estilo del pack.

  v1.59: Techo de luminancia al fondo de los botones de usuario
         (MAX_USER_BG_LUMINANCE). El texto es claro y los colores mas brillantes
         de Flow lo dejaban ilegible. Borde y hover se derivan del color ya
         corregido. Solo aplica a botones de usuario con color solido.

  v1.58: En contexto Client el panel queda deshabilitado con el motivo a la vista.
         Antes mostraba los dos botones fijos y ningun usuario, indistinguible
         de "PipeSync todavia no sincronizo". Tampoco abre ya la DB en Client.

  v1.57: los botones de usuario salen de la DB de PipeSync (flow_users); se elimina el JSON local y la config por defecto.
  v1.56: Propaga file_path junto con base_name a los tres scripts del panel
         para permitir extracción de project_name desde el segmento VFX-NOMBRE
         del path (corrige proyectos como PROJALT con prefijo PROJA en el filename).
  v1.55: Permite get/clear/assign de assignees en clips offline usando la ruta
         registrada en mediaSource().fileinfos(), sin exigir media presente.
  v1.54: Agregado logging a archivo con switches de debug
  v1.53: Actualizado para usar scroll bar cuando es necesario
  v1.52: Actualizado para usar estilos dinámicos con bordes y hover para todos los botones
         Agregado tooltip dinámico para todos los botones
  v1.51: Actualiza la UI para mostrar las tasks y los asignados en Flow.
         Funciona con todas las tasks disponibles en Flow.
  v1.50: Actualizado para ser compatible con ambos sistemas de nomenclatura:
         - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
         - PROYECTO_SEQ_SHOT (3 bloques simplificado)
____________________________________________________________________
"""

import hiero.ui
import hiero.core
import sys
import os
import json
import logging
import queue
import time
from logging.handlers import QueueHandler, QueueListener
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore

# Importar función de limpieza de nombres desde NamingUtils
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "LGA_NKS_Shared"))
from LGA_NKS_Flow_NamingUtils import clean_base_name

# Importar módulo utilitario para selección de clips
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "LGA_NKS_Shared"))
from LGA_NKS_Shared.LGA_NKS_GetClip import get_clips_to_process
from LGA_NKS_Shared import LGA_NKS_GetClip as clip_utils
from LGA_NKS_Shared.LGA_NKS_Flow_Users_Config import (
    get_flow_users_db_path,
    load_flow_users,
)
from LGA_NKS_Shared.LGA_NKS_ContextProfile import MODE_CLIENT, get_context_mode
from LGA_NKS_Shared.LGA_NKS_ContextSwitch import subscribe as subscribe_context_change
from LGA_NKS_Shared.LGA_NKS_MessageBox import show_warning

# Importar funciones de utilidad de estilos
from LGA_NKS_Shared.LGA_NKS_StyleUtils import (
    calculate_dynamic_border,
    calculate_dynamic_hover,
    create_tooltip_stylesheet,
    ensure_max_luminance,
)


# Techo de luminancia (0-255) para el fondo de los botones de usuario.
#
# El texto de los botones es #d8d8d8, casi blanco, asi que un fondo muy claro lo
# vuelve ilegible. Los colores vienen de Flow, donde se eligen como color
# identitario de la persona y no pensando en que llevan texto claro encima.
# El valor sale de medir los colores reales: los que hoy se leen bien llegan
# hasta ~135, y a partir de ahi empiezan a molestar.
#
# Es la operacion inversa a la del Projects Panel, que usa un PISO porque ahi el
# color va como texto sobre fondo oscuro. Las dos viven en StyleUtils.
MAX_USER_BG_LUMINANCE = 135


# Clase de botón personalizada que maneja el Shift+Click y Ctrl+Shift+Click
class CustomButton(QtWidgets.QPushButton):
    def __init__(self, text):
        super(CustomButton, self).__init__(text)
        self._custom_click_handler = None
        self._shift_click_handler = None
        self._ctrl_shift_click_handler = None

    def setCustomClickHandler(self, handler):
        self._custom_click_handler = handler

    def setShiftClickHandler(self, handler):
        self._shift_click_handler = handler

    def setCtrlShiftClickHandler(self, handler):
        self._ctrl_shift_click_handler = handler

    def mousePressEvent(self, event):
        if self._custom_click_handler and self._shift_click_handler:
            modifiers = event.modifiers()
            if modifiers & QtCore.Qt.ControlModifier and modifiers & QtCore.Qt.ShiftModifier:
                if self._ctrl_shift_click_handler:
                    self._ctrl_shift_click_handler()
            elif modifiers & QtCore.Qt.ShiftModifier:
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


def setup_debug_logging(script_name="AsigneePanel"):
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


debug_logger = setup_debug_logging(script_name="AsigneePanel")

# Umbral de solapamiento vertical permitido antes de activar scroll
SCROLL_OVERLAP_THRESHOLD_PX = 6
# Controla visibilidad de la barra de scroll (True = visible cuando corresponde)
SCROLLBAR_VISIBLE = False

# Textos del panel deshabilitado en contexto Client. Van por constante y no
# hardcodeados en el widget para que la migracion a tooltips bilingues sea un
# cambio de datos. Texto visible en ingles, tooltip en castellano.
CLIENT_NOTICE_TEXT = "Assignees are not available in Client mode."
CLIENT_NOTICE_TOOLTIP = (
    "En Client no hay assignees: el sitio de Flow del cliente no tiene el campo "
    "del envelope de usuario, todos los usuarios llegan sin marcar como "
    "assignable, y el acceso a Wasabi se resuelve con Vendor Groups en vez de "
    "policies por shot.\n\n"
    "Asignaciones y policies se manejan desde el contexto Studio."
)


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


class AssigneePanel(QtWidgets.QWidget):
    def __init__(self):
        super(AssigneePanel, self).__init__()
        self.setObjectName("com.lega.FPTAssigneePanel")
        self.setWindowTitle("Assignees")
        debug_print("=== AssigneePanel init ===")
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

        # En Client el panel entero queda deshabilitado, asi que ni siquiera se
        # abre la DB de PipeSync para buscar usuarios que no van a existir.
        self.context_mode = get_context_mode()
        self.users = (
            [] if self.is_client_context() else self.load_users_from_config()
        )
        debug_print(f"Contexto: {self.context_mode} | usuarios cargados: {self.users}")

        # Sincronizar debug con el módulo de clips
        clip_utils.DEBUG = DEBUG and DEBUG_CONSOLE

        # Definir los botones fijos y sus colores/estilos
        self.fixed_buttons = [
            (
                "Get Assignees",
                self.get_assignees_for_selected_clip,
                "#202233",
                None,
                "Obtiene los usuarios asignados en Flow para las tasks seleccionadas (comp por defecto). Si hay múltiples clips seleccionados, procesa todos; si hay uno solo, usa el playhead.",
            ),
            (
                "Clear Assignees",
                self.clear_assignees_for_selected_clip,
                "#202233",
                self.clear_wasabi_policies_for_completed_shots,
                "Click: Elimina los asignados en Flow para las tasks seleccionadas (comp por defecto). Si hay múltiples clips seleccionados, procesa todos; si hay uno solo, usa el playhead.\n"
                "Shift+Click: Escanea shots approved/delivery_checked en pipesync.db y permite limpiar sus líneas en policies de Wasabi.",
            ),
        ]

        # Crear la lista completa de botones (fijos + usuarios)
        self.buttons = self.build_buttons()

        self.num_columns = 1  # Inicialmente una columna
        self.button_width_hint = 0
        self.create_buttons()

        # Conectar la senal de cambio de tamano del widget al metodo correspondiente
        self.adjust_columns_on_resize()
        self.resizeEvent = self.adjust_columns_on_resize

        # Solo se conecta para el usuario que tiene el switch Studio/Client; para
        # el resto es un no-op y no queda ningun callback vivo.
        subscribe_context_change(self.on_context_changed)

    def is_client_context(self):
        return self.context_mode == MODE_CLIENT

    def build_buttons(self):
        """Botones fijos + de usuario. En Client no hay ninguno: el panel se deshabilita."""
        if self.is_client_context():
            return []
        return self.fixed_buttons + self.create_user_buttons()

    def on_context_changed(self, mode):
        """Rearma el panel al cambiar de contexto."""
        if mode == self.context_mode:
            return
        debug_print(f"Contexto cambiado: {self.context_mode} -> {mode}")
        self.context_mode = mode
        self.users = (
            [] if self.is_client_context() else self.load_users_from_config()
        )
        self.buttons = self.build_buttons()
        # El ancho medido corresponde al set anterior de botones.
        self.button_width_hint = 0
        self.create_buttons()
        self.adjust_columns_on_resize()

    def showEvent(self, event):
        super(AssigneePanel, self).showEvent(event)
        # Asegurar tamanos reales al mostrarse el panel
        self.adjust_columns_on_resize()
        self.update_scrollbar_policy()

    def load_users_from_config(self):
        """
        Carga los usuarios desde la DB de PipeSync (tabla flow_users).

        La fuente de verdad es Flow y se edita desde el Projects tab de PipeSync.
        No hay JSON local ni lista por defecto: si no hay datos, el panel se queda
        sin botones de usuario y lo avisa, en vez de mostrar una lista compilada que
        puede estar anos desactualizada.
        """
        try:
            users = load_flow_users(assignable_only=True)
        except Exception as e:
            debug_print(f"Error al cargar usuarios desde PipeSync: {e}")
            return []

        if not users:
            debug_print(
                "Sin usuarios en la DB de PipeSync "
                f"({get_flow_users_db_path()}). Abri PipeSync y esperá un sync."
            )
        else:
            debug_print(f"{len(users)} usuarios cargados desde {get_flow_users_db_path()}")
        return users

    def reload_config(self):
        """Recarga la configuracion de usuarios y actualiza los botones"""
        self.context_mode = get_context_mode()
        self.users = (
            [] if self.is_client_context() else self.load_users_from_config()
        )
        self.buttons = self.build_buttons()
        self.create_buttons()
        debug_print("Configuracion de usuarios recargada")

    def create_user_buttons(self):
        """Crea los botones de usuario dinamicamente basado en la configuracion"""
        debug_print(f"=== create_user_buttons llamado ===")
        debug_print(f"Numero de usuarios: {len(self.users)}")

        user_buttons = []
        for i, user in enumerate(self.users):
            user_name = user.get("name", "Unknown")
            user_color = user.get("color", "#666666")
            wasabi_user = user.get("wasabi_user", "Unknown")
            debug_print(
                f"Usuario {i}: name='{user_name}', color='{user_color}', wasabi_user='{wasabi_user}'"
            )

            # Crear callbacks usando una funcion auxiliar para evitar problemas con lambda
            normal_callback, shift_callback, ctrl_shift_callback = (
                self.create_user_callback(user_name, wasabi_user)
            )

            user_button = (
                user_name,
                normal_callback,
                user_color,
                shift_callback,  # Agregar el callback de Shift+Click
                ctrl_shift_callback,  # Agregar el callback de Ctrl+Shift+Click
            )
            user_buttons.append(user_button)

        debug_print(f"Botones de usuario creados: {len(user_buttons)}")
        return user_buttons

    def create_user_callback(self, user_name, wasabi_user):
        """Crea callbacks especificos para un usuario (normal, Shift+Click y Ctrl+Shift+Click)"""

        def normal_callback():
            debug_print(f"Boton presionado para usuario: {user_name}")
            self.assign_assignee_for_selected_clip(user_name)

        def shift_callback():
            debug_print(
                f"Shift+Click presionado para usuario: {user_name} (Wasabi: {wasabi_user})"
            )
            self.create_wasabi_policy_for_user(wasabi_user)

        def ctrl_shift_callback():
            debug_print(
                f"Ctrl+Shift+Click presionado para usuario: {user_name} (Wasabi: {wasabi_user})"
            )
            self.unassign_wasabi_policy_for_user(wasabi_user)

        return normal_callback, shift_callback, ctrl_shift_callback

    def create_client_notice(self):
        """
        Panel deshabilitado en Client, con el motivo a la vista.

        Antes en Client no fallaba nada visible: `load_flow_users` devolvia lista
        vacia y el panel quedaba con los dos botones fijos y ningun usuario, que
        se lee igual que "todavia no sincronizo PipeSync". Son cosas distintas y
        la segunda tiene arreglo; esta no.
        """
        notice = QtWidgets.QLabel(CLIENT_NOTICE_TEXT)
        notice.setWordWrap(True)
        notice.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        notice.setStyleSheet("color: #8a8a8a; padding: 8px;")
        notice.setToolTip(CLIENT_NOTICE_TOOLTIP)
        self.layout.addWidget(notice, 0, 0, 1, max(1, self.num_columns))

        spacer = QtWidgets.QSpacerItem(
            20, 20, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding
        )
        self.layout.addItem(spacer, 1, 0, 1, max(1, self.num_columns))
        self.update_scrollbar_policy()
        debug_print("layout: contexto client, panel deshabilitado")

    def create_buttons(self):
        debug_print("=== create_buttons ===")
        # Limpiar el layout actual antes de crear nuevos botones
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if self.is_client_context():
            self.create_client_notice()
            return

        max_button_width = 0
        for index, button_info in enumerate(self.buttons):
            name = button_info[0]
            handler = button_info[1]
            style = button_info[2]

            # Determinar si es un boton de usuario (tiene shift_handler y ctrl_shift_handler) o un boton fijo
            is_user_button = (
                len(button_info) == 5
                and callable(button_info[3])
                and callable(button_info[4])
            )

            # Determinar si el botón tiene tooltip
            has_tooltip = is_user_button or (len(button_info) > 4 and button_info[4])

            if is_user_button:
                # Boton de usuario: (name, handler, style, shift_handler, ctrl_shift_handler)
                shift_handler = button_info[3]
                ctrl_shift_handler = button_info[4]
                button = CustomButton(name)
                button.setCustomClickHandler(handler)
                button.setShiftClickHandler(shift_handler)
                button.setCtrlShiftClickHandler(ctrl_shift_handler)
            else:
                # Boton fijo: (name, handler, style, [shortcut], [tooltip])
                shortcut = button_info[3] if len(button_info) > 3 else None
                tooltip = button_info[4] if len(button_info) > 4 else None

                # Si el 4to argumento es callable, se interpreta como Shift+Click para botón fijo
                if callable(shortcut):
                    button = CustomButton(name)
                    button.setCustomClickHandler(handler)
                    button.setShiftClickHandler(shortcut)
                else:
                    button = QtWidgets.QPushButton(name)
                    button.clicked.connect(handler)

                # Agregar shortcut si existe
                if shortcut and not callable(shortcut):
                    button.setShortcut(QtGui.QKeySequence(shortcut))

            # Obtener el texto del tooltip para asignarlo después
            if is_user_button:
                tooltip_text = (
                    "Click: Asigna el usuario a las tasks seleccionadas (comp por defecto) en Flow Production Tracking\n"
                    "Shift+Click: Crea/actualiza políticas IAM de Wasabi para el usuario\n"
                    "Ctrl+Shift+Click: Abre ventana de gestión de shots asignados en policy de Wasabi"
                )
            else:
                tooltip_text = tooltip if tooltip else None

            # Techo de brillo al fondo de los botones de usuario: el texto es
            # claro y contra un fondo muy claro no se lee. Solo se tocan los
            # colores solidos de usuario; los botones fijos del panel llevan
            # colores propios ya elegidos para este fondo, y los gradientes se
            # dejan pasar sin cambios.
            if is_user_button:
                style = ensure_max_luminance(style, MAX_USER_BG_LUMINANCE)

            # Aplicar estilos dinámicos con bordes, hover y tooltips
            # (se derivan del color ya corregido, para que borde y hover
            # acompañen al fondo en vez de contradecirlo)
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

            # Agregar estilos de tooltip dinámicos si hay tooltip
            if has_tooltip:
                # Crear un selector único para este botón usando su objectName
                button_object_name = f"button_{index}"
                button.setObjectName(button_object_name)

                # Crear stylesheet de tooltip dinámico
                tooltip_stylesheet = create_tooltip_stylesheet(style)
                # Modificar el tooltip stylesheet para usar el selector del botón
                tooltip_stylesheet = tooltip_stylesheet.replace("QToolTip", f"#{button_object_name} QToolTip")

                # Combinar estilos del botón con estilos de tooltip
                button_stylesheet += tooltip_stylesheet

            button.setStyleSheet(button_stylesheet)

            # Asignar tooltips después de configurar el objectName (para que los estilos dinámicos funcionen)
            if tooltip_text:
                button.setToolTip(tooltip_text)

            max_button_width = max(max_button_width, button.sizeHint().width())
            row = index // self.num_columns
            column = index % self.num_columns
            self.layout.addWidget(button, row, column)

        # Calcular el numero de filas usadas
        num_rows = (len(self.buttons) + self.num_columns - 1) // self.num_columns
        debug_print(
            f"layout: buttons={len(self.buttons)} rows={num_rows} cols={self.num_columns}"
        )
        if max_button_width > 0:
            self.button_width_hint = max_button_width
            debug_print(f"layout: button_width_hint={self.button_width_hint}px")

        # Anadir el espaciador vertical al final (espacio reducido entre botones)
        spacer = QtWidgets.QSpacerItem(20, 20, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.layout.addItem(spacer, num_rows, 0, 1, self.num_columns)

        # Ajustar politica de scroll segun el solapamiento permitido
        self.update_scrollbar_policy()

    def update_scrollbar_policy(self):
        # Altura real requerida por el contenido
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
            # Activar scroll vertical manteniendo el ancho del viewport
            self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            self.scroll_widget.setMinimumHeight(content_height)
            debug_print(
                f"scroll: ON overlap={overlap}px content={content_height}px viewport={viewport_height}px"
            )
        else:
            # Permitir leve compresion sin scroll
            self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.scroll_widget.setMinimumHeight(0)
            debug_print(
                f"scroll: OFF overlap={overlap}px content={content_height}px viewport={viewport_height}px"
            )

    def adjust_columns_on_resize(self, event=None):
        # Obtener el ancho actual del widget
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

        # Calcular el numero de columnas en funcion del ancho del widget
        new_num_columns = max(
            1,
            (available_width + min_button_spacing)
            // (button_width + min_button_spacing),
        )

        if new_num_columns != self.num_columns:
            self.num_columns = new_num_columns
            # Volver a crear los botones con el nuevo numero de columnas
            self.create_buttons()
        else:
            self.update_scrollbar_policy()
        debug_print(
            "resize: "
            f"panel_width={panel_width}px viewport={viewport_width}px scroll={scroll_width}px self={self_width}px "
            f"available={available_width}px "
            f"button_width={button_width}px spacing={min_button_spacing}px cols={self.num_columns}"
        )

    def parse_exr_name(self, exr_name):
        """Extrae el nombre base del archivo EXR usando funciones compartidas de NamingUtils."""
        # Usar función compartida para limpiar el nombre base (compatible con ambos formatos)
        base_name = clean_base_name(exr_name)
        return base_name

    def _get_base_name_from_clip(self, item):
        """Obtiene (base_name, file_path) desde la ruta registrada, aunque el media este offline."""
        media_source = item.source().mediaSource()

        try:
            online = bool(media_source.isMediaPresent())
            debug_print(
                f"Estado del media para '{item.name()}': {'ONLINE' if online else 'OFFLINE'}"
            )
        except Exception as e:
            debug_print(
                f"No se pudo determinar online/offline para '{item.name()}': {e}",
                level="warning",
            )

        fileinfos = media_source.fileinfos()
        if not fileinfos:
            raise RuntimeError("El clip no tiene ruta de media registrada.")

        file_path = fileinfos[0].filename()
        exr_name = os.path.basename(file_path)
        exr_name = exr_name.replace(".%", "_%")
        debug_print(f"Ruta registrada del clip: {file_path}")
        debug_print(f"Procesando archivo: {exr_name}")
        return self.parse_exr_name(exr_name), file_path

    def get_assignees_for_selected_clip(self):
        seq = hiero.ui.activeSequence()
        if not seq:
            show_warning(self, "No Sequence", "No hay una secuencia activa.")
            return

        # Usar método híbrido: selección múltiple prioritaria, playhead para selección simple
        clips_to_process = get_clips_to_process(track_name=None, prioritize_multiple_selection=True)
        if not clips_to_process:
            show_warning(
                self, "No Clips", "No se encontraron clips para procesar. Selecciona clips o posiciona el playhead sobre un clip en el track _comp_."
            )
            return

        for item in clips_to_process:
            if not isinstance(item, hiero.core.EffectTrackItem):
                try:
                    base_name, file_path = self._get_base_name_from_clip(item)
                    self.call_assignee_script(base_name, file_path)
                except Exception as e:
                    show_warning(self, "Formato Incorrecto", str(e))

    def call_assignee_script(self, base_name, file_path=None):
        # Importar y ejecutar la funcion del script LGA_NKS_Flow_Assignee.py directamente
        script_path = os.path.join(
            os.path.dirname(__file__),
            "LGA_NKS_Assignee_Panel_py",
            "LGA_NKS_Flow_Assignee.py",
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
                "LGA_NKS_Flow_Assignee", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_Flow_Assignee.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Llamar a la función principal pasando el base_name y file_path
            module.show_task_assignees_from_base_name(base_name, file_path=file_path)
        except Exception as e:
            show_warning(self, "Error al ejecutar", str(e))

    def clear_assignees_for_selected_clip(self):
        seq = hiero.ui.activeSequence()
        if not seq:
            show_warning(self, "No Sequence", "No hay una secuencia activa.")
            return

        # Usar método híbrido: selección múltiple prioritaria, playhead para selección simple
        clips_to_process = get_clips_to_process(track_name=None, prioritize_multiple_selection=True)
        if not clips_to_process:
            show_warning(
                self, "No Clips", "No se encontraron clips para procesar. Selecciona clips o posiciona el playhead sobre un clip en el track _comp_."
            )
            return

        for item in clips_to_process:
            if not isinstance(item, hiero.core.EffectTrackItem):
                try:
                    base_name, file_path = self._get_base_name_from_clip(item)
                    self.call_clear_assignees_script(base_name, file_path)
                except Exception as e:
                    show_warning(self, "Formato Incorrecto", str(e))

    def call_clear_assignees_script(self, base_name, file_path=None):
        script_path = os.path.join(
            os.path.dirname(__file__),
            "LGA_NKS_Assignee_Panel_py",
            "LGA_NKS_Flow_Clear_Assignees.py",
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
                "LGA_NKS_Flow_Clear_Assignees", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_Flow_Clear_Assignees.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Llamar a la función principal pasando el base_name y file_path
            module.clear_task_assignees_from_base_name(base_name, file_path=file_path)
        except Exception as e:
            show_warning(self, "Error al ejecutar", str(e))

    def assign_assignee_for_selected_clip(self, user_name):
        debug_print(
            f"=== assign_assignee_for_selected_clip llamado con user_name: {user_name} ==="
        )
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("No hay secuencia activa")
            show_warning(self, "No Sequence", "No hay una secuencia activa.")
            return

        # Usar método híbrido: selección múltiple prioritaria, playhead para selección simple
        clips_to_process = get_clips_to_process(track_name=None, prioritize_multiple_selection=True)
        if not clips_to_process:
            debug_print("No hay clips para procesar")
            show_warning(
                self, "No Clips", "No se encontraron clips para procesar. Selecciona clips o posiciona el playhead sobre un clip en el track _comp_."
            )
            return

        debug_print(f"Procesando {len(clips_to_process)} clips")
        for item in clips_to_process:
            if not isinstance(item, hiero.core.EffectTrackItem):
                try:
                    base_name, file_path = self._get_base_name_from_clip(item)
                    debug_print(f"Base name extraido: {base_name}")
                    debug_print(
                        f"Llamando call_assign_assignee_script con user_name: {user_name}"
                    )
                    self.call_assign_assignee_script(base_name, user_name, file_path)
                except Exception as e:
                    debug_print(f"Error resolviendo nombre del clip: {e}")
                    show_warning(self, "Formato Incorrecto", str(e))

    def call_assign_assignee_script(self, base_name, user_name, file_path=None):
        debug_print(f"=== call_assign_assignee_script llamado ===")
        debug_print(f"base_name: {base_name}")
        debug_print(f"user_name: {user_name}")
        debug_print(f"Tipo de user_name: {type(user_name)}")

        script_path = os.path.join(
            os.path.dirname(__file__),
            "LGA_NKS_Assignee_Panel_py",
            "LGA_NKS_Flow_Assign_Assignee.py",
        )
        debug_print(f"Script path: {script_path}")

        if not os.path.exists(script_path):
            debug_print("Script no encontrado")
            show_warning(
                self,
                "Script no encontrado",
                f"No se encontró el script en la ruta: {script_path}",
            )
            return
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "LGA_NKS_Flow_Assign_Assignee", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_Flow_Assign_Assignee.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Llamar a la función principal pasando el base_name y el nombre del usuario
            debug_print(
                f"Llamando assign_assignee_to_task con: '{base_name}', '{user_name}'"
            )
            module.assign_assignee_to_task(base_name, user_name, file_path=file_path)
        except Exception as e:
            debug_print(f"Error ejecutando script: {e}")
            show_warning(self, "Error al ejecutar", str(e))

    def create_wasabi_policy_for_user(self, wasabi_user):
        """Llama al script de Wasabi Policy Assign para crear/actualizar políticas IAM para un usuario específico"""
        debug_print(
            f"=== create_wasabi_policy_for_user llamado con wasabi_user: {wasabi_user} ==="
        )
        script_path = os.path.join(
            os.path.dirname(__file__),
            "LGA_NKS_Assignee_Panel_py",
            "LGA_NKS_Wasabi_PolicyAssign.py",
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
                "LGA_NKS_Wasabi_PolicyAssign", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_Wasabi_PolicyAssign.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Llamar a la función principal pasando el usuario de Wasabi
            debug_print(f"Llamando module.main con usuario: {wasabi_user}")
            module.main(wasabi_user)
        except Exception as e:
            debug_print(f"Error ejecutando script de Wasabi: {e}")
            show_warning(self, "Error al ejecutar", str(e))

    def unassign_wasabi_policy_for_user(self, wasabi_user):
        """Llama al script de Wasabi Policy Unassign para mostrar y gestionar shots asignados"""
        debug_print(
            f"=== unassign_wasabi_policy_for_user llamado con wasabi_user: {wasabi_user} ==="
        )
        script_path = os.path.join(
            os.path.dirname(__file__),
            "LGA_NKS_Assignee_Panel_py",
            "LGA_NKS_Wasabi_PolicyUnassign.py",
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
                "LGA_NKS_Wasabi_PolicyUnassign", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_Wasabi_PolicyUnassign.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Llamar a la función principal pasando el usuario de Wasabi
            debug_print(f"Llamando module.main con usuario: {wasabi_user}")
            module.main(wasabi_user)
        except Exception as e:
            debug_print(f"Error ejecutando script de Wasabi Unassign: {e}")
            show_warning(self, "Error al ejecutar", str(e))

    def clear_wasabi_policies_for_completed_shots(self):
        """Shift+Click en Clear Assignees: abre ventana para limpiar policies por estado de shot en DB."""
        debug_print("=== clear_wasabi_policies_for_completed_shots llamado ===")
        script_path = os.path.join(
            os.path.dirname(__file__),
            "LGA_NKS_Assignee_Panel_py",
            "LGA_NKS_Wasabi_PolicyUnassign_CompletedShots.py",
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
                "LGA_NKS_Wasabi_PolicyUnassign_CompletedShots", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_Wasabi_PolicyUnassign_CompletedShots.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            module.main()
        except Exception as e:
            debug_print(f"Error ejecutando script de limpieza global de Wasabi: {e}")
            show_warning(self, "Error al ejecutar", str(e))


# Crear la instancia del panel y agregarlo al windowManager de Hiero
assigneePanel = AssigneePanel()
wm = hiero.ui.windowManager()
wm.addWindow(assigneePanel)
