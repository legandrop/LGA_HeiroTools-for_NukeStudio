"""
____________________________________________________________________

  LGA_NKS_UIManager v1.02 | Lega

  Gestor de interfaz de usuario para el panel de proyectos LGA.
  Centraliza creación de widgets, conexión de señales, y manejo de eventos.

  v1.02: El switch Studio/Client pasa a ser un toggle pill (_build_context_toggle) ubicado a la
         derecha del info_label, en vez del botón en la columna derecha. Conecta ctx_client_btn /
         ctx_studio_btn a panel.set_context_mode() en setup_connections().
  v1.01: Agregado botón de switch Studio/Client en setup_ui() cuando el usuario es lega@wanka.tv.
         Se inicializa con dependencias de funciones (get_normal_pipesync_flow_login, etc.) y se
         conecta en setup_connections(). Incluye debug logging para diagnosticar visibilidad del botón.
  v1.00: Versión inicial - UI manager central
____________________________________________________________________

"""

import os
import configparser
from pathlib import Path
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt

# Importar variable global
# Esta será importada desde el archivo principal cuando se importe este módulo
REIMPORT_BUTTON = None
SWITCH_ALLOWED_LOGIN = None
GET_CONTEXT_MODE = None
FIND_CONTEXT_INI = None
GET_NORMAL_PIPESYNC_LOGIN = None


def initialize_ui_dependencies(reimport_flag, switch_login=None, get_context_fn=None, find_ini_fn=None, get_login_fn=None):
    """Inicializar las dependencias globales necesarias para el UI manager"""
    global REIMPORT_BUTTON, SWITCH_ALLOWED_LOGIN, GET_CONTEXT_MODE, FIND_CONTEXT_INI, GET_NORMAL_PIPESYNC_LOGIN
    REIMPORT_BUTTON = reimport_flag
    SWITCH_ALLOWED_LOGIN = switch_login or "lega@wanka.tv"
    GET_CONTEXT_MODE = get_context_fn
    FIND_CONTEXT_INI = find_ini_fn
    GET_NORMAL_PIPESYNC_LOGIN = get_login_fn


class UIManager:
    """Clase para manejar la configuración y gestión de la interfaz de usuario"""

    @staticmethod
    def setup_ui(panel):
        """Configurar la interfaz de usuario del panel"""
        # Layout principal horizontal para dividir en dos columnas
        panel.main_layout = QtWidgets.QHBoxLayout(panel)

        # Columna izquierda: proyectos y settings (stack)
        left_column = QtWidgets.QVBoxLayout()

        panel.content_stack = QtWidgets.QStackedWidget()

        # Contenedor de proyectos
        panel.projects_container = QtWidgets.QWidget()
        projects_container_layout = QtWidgets.QVBoxLayout(panel.projects_container)
        projects_container_layout.setContentsMargins(0, 0, 0, 0)

        # Área de scroll para la lista de proyectos
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        panel.projects_widget = QtWidgets.QWidget()
        panel.projects_layout = QtWidgets.QVBoxLayout(panel.projects_widget)
        panel.projects_layout.setAlignment(QtCore.Qt.AlignTop)

        scroll_area.setWidget(panel.projects_widget)
        projects_container_layout.addWidget(scroll_area)

        # Información de estado + toggle de contexto (alineado a la derecha)
        info_row = QtWidgets.QHBoxLayout()
        info_row.setContentsMargins(0, 0, 0, 0)
        info_row.setSpacing(6)

        panel.info_label = QtWidgets.QLabel("")
        panel.info_label.setStyleSheet("color: #666; font-size: 11px; margin-top: 6px;")
        panel.info_label.setAlignment(QtCore.Qt.AlignCenter)
        info_row.addWidget(panel.info_label, 1)

        context_toggle = UIManager._build_context_toggle(panel)
        if context_toggle is not None:
            info_row.addWidget(context_toggle, 0, QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)

        projects_container_layout.addLayout(info_row)

        panel.content_stack.addWidget(panel.projects_container)
        left_column.addWidget(panel.content_stack)

        # Añadir columna izquierda al layout principal (con stretch para que tome el espacio disponible)
        panel.main_layout.addLayout(left_column, 1)  # stretch factor 1

        # Columna derecha: botones
        right_column = QtWidgets.QVBoxLayout()
        right_column.setAlignment(QtCore.Qt.AlignTop)
        right_column.setSpacing(2)  # Espacio pequeño entre botones

        # Configurar iconos para el botón refresh
        refresh_icon_path = os.path.join(os.path.dirname(__file__), "..", "LGA_NKS_Projects_Panel_py", "refresh.svg")
        refresh_hover_icon_path = os.path.join(os.path.dirname(__file__), "..", "LGA_NKS_Projects_Panel_py", "refresh_white.svg")

        panel.refresh_button = QtWidgets.QPushButton()
        panel.refresh_button.setToolTip("Re-escanear proyectos")
        panel.refresh_button.setStyleSheet("""
            QPushButton {
                border: none;
                padding: 5px;
                background: transparent;
            }
        """)

        # Cargar iconos SVG si existen
        if os.path.exists(refresh_icon_path) and os.path.exists(refresh_hover_icon_path):
            panel.refresh_icon_normal = QtGui.QIcon(refresh_icon_path)
            panel.refresh_icon_hover = QtGui.QIcon(refresh_hover_icon_path)
            panel.refresh_button.setIcon(panel.refresh_icon_normal)
            panel.refresh_button.setIconSize(QtCore.QSize(20, 20))  # Tamaño aproximado al botón original

            # Instalar event filter para manejar hover
            panel.refresh_button.installEventFilter(panel)
        else:
            # Fallback si no se encuentran los iconos
            panel.refresh_button.setText("🔄 Refresh")

        # Añadir botón refresh a la columna derecha
        right_column.addWidget(panel.refresh_button)

        # Botón Settings
        settings_icon_path = os.path.join(os.path.dirname(__file__), "..", "LGA_NKS_Projects_Panel_py", "settings.svg")
        settings_hover_icon_path = os.path.join(os.path.dirname(__file__), "..", "LGA_NKS_Projects_Panel_py", "settings_white.svg")

        panel.settings_button = QtWidgets.QPushButton()
        panel.settings_button.setToolTip("Settings")
        panel.settings_button.setStyleSheet("""
            QPushButton {
                border: none;
                padding: 5px;
                background: transparent;
            }
        """)

        if os.path.exists(settings_icon_path) and os.path.exists(settings_hover_icon_path):
            panel.settings_icon_normal = QtGui.QIcon(settings_icon_path)
            panel.settings_icon_hover = QtGui.QIcon(settings_hover_icon_path)
            panel.settings_button.setIcon(panel.settings_icon_normal)
            panel.settings_button.setIconSize(QtCore.QSize(20, 20))
            panel.settings_button.installEventFilter(panel)
        else:
            panel.settings_button.setText("⚙ Settings")

        right_column.addWidget(panel.settings_button)

        # Configurar iconos para el botón reimport
        reimport_icon_path = os.path.join(os.path.dirname(__file__), "..", "LGA_NKS_Projects_Panel_py", "recargar_script.svg")
        reimport_hover_icon_path = os.path.join(os.path.dirname(__file__), "..", "LGA_NKS_Projects_Panel_py", "recargar_script_white.svg")

        # Botón de reimport con iconos SVG (solo si la flag está activada)
        if REIMPORT_BUTTON:
            panel.reimport_button = QtWidgets.QPushButton()
            panel.reimport_button.setToolTip("Recarga y redockea el panel con el script externo")
            panel.reimport_button.setStyleSheet("""
                QPushButton {
                    border: none;
                    padding: 5px;
                    background: transparent;
                }
            """)

            # Cargar iconos SVG si existen
            if os.path.exists(reimport_icon_path) and os.path.exists(reimport_hover_icon_path):
                panel.reimport_icon_normal = QtGui.QIcon(reimport_icon_path)
                panel.reimport_icon_hover = QtGui.QIcon(reimport_hover_icon_path)
                panel.reimport_button.setIcon(panel.reimport_icon_normal)
                panel.reimport_button.setIconSize(QtCore.QSize(20, 20))  # Tamaño aproximado al botón original

                # Instalar event filter para manejar hover
                panel.reimport_button.installEventFilter(panel)
            else:
                # Fallback si no se encuentran los iconos
                panel.reimport_button.setText("♻")

            right_column.addWidget(panel.reimport_button)

        # Añadir columna derecha al layout principal (sin stretch para mantener tamaño pequeño)
        panel.main_layout.addLayout(right_column, 0)  # stretch factor 0

    @staticmethod
    def _build_context_toggle(panel):
        """Construye el toggle pill Client/Studio. Devuelve el widget o None si no aplica."""
        if not GET_NORMAL_PIPESYNC_LOGIN:
            return None
        try:
            normal_login = str(GET_NORMAL_PIPESYNC_LOGIN() or "").strip().lower()
            can_show = normal_login == SWITCH_ALLOWED_LOGIN
            if hasattr(panel, "debug_print"):
                panel.debug_print(f"Context toggle visible={can_show} login='{normal_login}' allowed='{SWITCH_ALLOWED_LOGIN}'")
            if not can_show:
                return None
        except Exception as e:
            if hasattr(panel, "debug_print"):
                import traceback
                panel.debug_print(f"Error evaluando login para toggle: {e}")
                panel.debug_print(f"Traceback: {traceback.format_exc()}")
            return None

        container = QtWidgets.QWidget()
        container.setObjectName("ctxToggle")
        container.setStyleSheet("""
            QWidget#ctxToggle {
                background: #1c1c1c;
                border: none;
                border-radius: 13px;
            }
        """)
        h = QtWidgets.QHBoxLayout(container)
        h.setContentsMargins(2, 2, 2, 2)
        h.setSpacing(2)

        panel.ctx_client_btn = QtWidgets.QPushButton("client")
        panel.ctx_studio_btn = QtWidgets.QPushButton("studio")
        for btn in (panel.ctx_client_btn, panel.ctx_studio_btn):
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setFlat(True)
            btn.setMinimumHeight(22)
        h.addWidget(panel.ctx_client_btn)
        h.addWidget(panel.ctx_studio_btn)

        panel.context_toggle_widget = container
        if hasattr(panel, "_refresh_context_toggle"):
            panel._refresh_context_toggle()
        return container

    @staticmethod
    def setup_connections(panel):
        """Configurar las conexiones de señales del panel"""
        panel.refresh_button.clicked.connect(panel.start_scan)
        if hasattr(panel, 'settings_button'):
            panel.settings_button.clicked.connect(panel.show_settings_view)
        if REIMPORT_BUTTON and hasattr(panel, 'reimport_button'):
            panel.reimport_button.clicked.connect(panel.reimport_panel)
        if hasattr(panel, 'ctx_client_btn') and hasattr(panel, 'ctx_studio_btn'):
            panel.ctx_client_btn.clicked.connect(lambda: panel.set_context_mode("client"))
            panel.ctx_studio_btn.clicked.connect(lambda: panel.set_context_mode("studio"))

    @staticmethod
    def eventFilter(panel, obj, event):
        """Manejar eventos de hover para botones y labels"""
        # Manejar hover del botón refresh
        if obj == panel.refresh_button:
            if event.type() == QtCore.QEvent.Enter:
                if hasattr(panel, 'refresh_icon_hover'):
                    panel.refresh_button.setIcon(panel.refresh_icon_hover)
            elif event.type() == QtCore.QEvent.Leave:
                if hasattr(panel, 'refresh_icon_normal'):
                    panel.refresh_button.setIcon(panel.refresh_icon_normal)

        # Hover botón settings
        elif obj == getattr(panel, "settings_button", None):
            if event.type() == QtCore.QEvent.Enter:
                if hasattr(panel, 'settings_icon_hover'):
                    panel.settings_button.setIcon(panel.settings_icon_hover)
            elif event.type() == QtCore.QEvent.Leave:
                if hasattr(panel, 'settings_icon_normal'):
                    panel.settings_button.setIcon(panel.settings_icon_normal)

        # Manejar hover del botón reimport
        elif obj == getattr(panel, "reimport_button", None):
            if event.type() == QtCore.QEvent.Enter:
                if hasattr(panel, 'reimport_icon_hover'):
                    panel.reimport_button.setIcon(panel.reimport_icon_hover)
            elif event.type() == QtCore.QEvent.Leave:
                if hasattr(panel, 'reimport_icon_normal'):
                    panel.reimport_button.setIcon(panel.reimport_icon_normal)

        # Manejar hover del botón update (buscar en todos los project items)
        elif hasattr(obj, 'toolTip') and obj.toolTip() == "Actualizar a versión más nueva":
            # Es un botón de update
            if event.type() == QtCore.QEvent.Enter:
                # Cambiar a ícono hover
                if hasattr(obj, 'update_icon_hover'):
                    obj.setIcon(obj.update_icon_hover)
            elif event.type() == QtCore.QEvent.Leave:
                # Cambiar a ícono normal
                if hasattr(obj, 'update_icon_normal'):
                    obj.setIcon(obj.update_icon_normal)

        # Manejar hover de los project labels y sequence labels
        elif hasattr(obj, 'setStyleSheet') and obj != panel.refresh_button:
            # Verificar si es un label con cursor de pointing hand
            if obj.cursor().shape() == QtCore.Qt.PointingHandCursor:
                if event.type() == QtCore.QEvent.Enter:
                    # Cambiar a color hover usando las propiedades guardadas
                    hover_color = obj.property("hover_color")
                    if hover_color:
                        if obj.property("is_project_label"):
                            # Project label: mantener font-size
                            obj.setStyleSheet(f"font-size: 13px; color: {hover_color};")
                        else:
                            # Sequence label: solo color
                            obj.setStyleSheet(f"color: {hover_color};")
                elif event.type() == QtCore.QEvent.Leave:
                    # Volver a color base usando las propiedades guardadas
                    base_color = obj.property("base_color")
                    if base_color:
                        if obj.property("is_project_label"):
                            # Project label: mantener font-size
                            obj.setStyleSheet(f"font-size: 13px; color: {base_color};")
                        else:
                            # Sequence label: solo color
                            obj.setStyleSheet(f"color: {base_color};")

        return super(panel.__class__, panel).eventFilter(obj, event)
