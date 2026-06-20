# -*- coding: utf-8 -*-
"""
____________________________________________________________________

  LGA_NKS_Projects_Panel v2.24 | Lega

  Panel de Proyectos LGA integrado para Hiero con recarga inteligente.
  - Escanea proyectos en AltTPath (PipeSync) o T:\ como fallback.
  - Permite abrir proyectos y secuencias (cross-project) sin perder ajustes de viewer.
  - Incluye botón de reimport/redock para aplicar cambios al vuelo.
  - Toggle pill Studio/Client (alineado a la derecha del contador) visible para lega@wanka.tv.

  v2.24: Reemplazado el botón de switch por un toggle pill Client/Studio alineado a la derecha
         de la línea de proyectos encontrados. Nuevos métodos set_context_mode() (cambio directo
         sin popup) y _refresh_context_toggle() (estilo activo/inactivo). Se eliminó el botón viejo.
  v2.23: Agregado botón de switch Studio/Client: lee login de PipeSync normal y muestra botón
         debajo de refresh solo para lega@wanka.tv, permitiendo cambiar entre contextos studio/client
         con persistencia en INI y ENV. Se migró lógica de UIManager para inicializar dependencias
         correctamente. Se agregó debug logging detallado en _get_normal_pipesync_login().
  v2.22: Migrado al sistema de logging a archivo con flags de debug compartidas para Projects Panel
  v2.21: Mejorada lógica de versiones: búsqueda en anteúltimo bloque y priorización de sufijos (_Mac)
         Las versiones ahora se detectan correctamente cuando están en bloques anteriores
         Ejemplo: v40_Mac > v40 (prioriza sufijos), v040_Mac detecta v040 correctamente
  v2.20: Display formateado: PROYECTO (vXXX), emojis ▼▶, sin _SUP_
____________________________________________________________________
"""

import hiero.ui
import hiero.core
import os
import importlib
import sys
import configparser
from pathlib import Path
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt
from LGA_NKS_Shared.LGA_NKS_ContextProfile import get_context_mode, find_context_ini
from LGA_NKS_Shared.LGA_NKS_PipeSyncPreflight import get_normal_pipesync_flow_login
from LGA_NKS_Projects_Panel_py.LGA_NKS_ProjectsPanel_Logging import (
    DEBUG,
    DEBUG_CONSOLE,
    DEBUG_LOG,
    debug_print,
    print_debug_messages,
)

# Importar funciones de utilidad de estilos
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "LGA_NKS_Shared"))
from LGA_NKS_Shared.LGA_NKS_StyleUtils import calculate_dynamic_border, calculate_dynamic_hover

# Variable global para controlar si se debe crear panel automáticamente
# Se usa en smart reload para evitar creación duplicada
AUTO_CREATE_PANEL = True

# Flag para controlar si mostrar el botón de reimport
REIMPORT_BUTTON = True
SWITCH_ALLOWED_LOGIN = "lega@wanka.tv"

# Opciones de intervalo de auto-refresh (minutos)
AUTO_REFRESH_OPTIONS = {
    "never": 0,
    "5min": 5,
    "10min": 10,
    "15min": 15,
    "30min": 30,
    "1h": 60,
    "2h": 120,
}

# Configuración de colores desde archivo .ini
PROJECT_COLORS = {}


def load_project_colors():
    """Carga los colores de proyectos desde el archivo .ini"""
    global PROJECT_COLORS
    PROJECT_COLORS.clear()
    debug_print("🔧 Iniciando carga de colores desde .ini...")

    ini_path = Path(__file__).parent / "LGA_NKS_Projects_Panel.ini"
    debug_print(f"📁 Ruta del archivo .ini: {ini_path}")
    debug_print(f"📁 Archivo .ini existe: {ini_path.exists()}")

    if not ini_path.exists():
        debug_print(f"❌ Archivo de configuración no encontrado: {ini_path}")
        return

    try:
        config = configparser.ConfigParser()
        config.read(ini_path, encoding='utf-8')
        debug_print("📖 Archivo .ini leído correctamente")

        if 'Colors' in config:
            debug_print("🎨 Sección [Colors] encontrada")
            for project_name, color in config['Colors'].items():
                clean_name = project_name.strip().upper()  # Convertir a mayúsculas
                clean_color = color.strip()
                PROJECT_COLORS[clean_name] = clean_color
                debug_print(f"✅ Color cargado para {clean_name}: {clean_color}")
        else:
            debug_print("❌ Sección [Colors] no encontrada en el archivo .ini")

        debug_print(f"📊 Total colores cargados: {len(PROJECT_COLORS)}")
        debug_print(f"📋 Colores cargados: {sorted(PROJECT_COLORS.keys())}")

    except Exception as e:
        debug_print(f"💥 Error al cargar configuración de colores: {e}")
        import traceback
        debug_print(f"Traceback: {traceback.format_exc()}")


def get_brighter_color(base_color):
    """Devuelve un color más brillante para hover basado en el color base"""
    if not base_color.startswith('#') or len(base_color) != 7:
        return "#FFFFFF"  # Color por defecto si el formato es inválido

    try:
        # Convertir de hex a RGB
        r = int(base_color[1:3], 16)
        g = int(base_color[3:5], 16)
        b = int(base_color[5:7], 16)

        # Aumentar el brillo (mezclar con blanco)
        factor = 0.4  # Cuánto brillo añadir (0.0 = sin cambio, 1.0 = blanco puro)
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))

        # Convertir de vuelta a hex
        return f"#{r:02X}{g:02X}{b:02X}"

    except ValueError:
        return "#FFFFFF"  # Color por defecto si hay error


def get_project_colors(project_name):
    """Devuelve los colores (base, hover) para un proyecto específico"""
    project_name_upper = project_name.upper()  # Buscar en mayúsculas
    debug_print(f"🎨 get_project_colors() llamado para: '{project_name}' (buscando como: '{project_name_upper}')")
    debug_print(f"📋 PROJECT_COLORS disponibles: {sorted(PROJECT_COLORS.keys())}")

    if project_name_upper in PROJECT_COLORS:
        base_color = PROJECT_COLORS[project_name_upper]
        hover_color = get_brighter_color(base_color)
        debug_print(f"✅ Proyecto '{project_name}' encontrado - Base: {base_color}, Hover: {hover_color}")
        return base_color, hover_color
    else:
        # Colores por defecto
        debug_print(f"⚪ Proyecto '{project_name}' no encontrado en .ini - Usando colores por defecto")
        return "#cccccc", "#ffffff"


# Buscar y añadir la ruta del módulo de escaneo al sys.path
projects_panel_path = None

# Método 1: carpeta LGA_NKS_Projects_Panel_py junto a este script
try:
    script_dir = Path(__file__).resolve().parent
    candidate = script_dir / "LGA_NKS_Projects_Panel_py"
    if (candidate / "LGA_Projects_Panel_ScanProjects.py").exists():
        projects_panel_path = candidate
except Exception:
    pass

# Método 2: Buscar en sys.path y subcarpetas LGA_*
if projects_panel_path is None:
    for path_str in sys.path:
        try:
            path = Path(path_str)
            if (path / "LGA_Projects_Panel_ScanProjects.py").exists():
                projects_panel_path = path
                break
            if path.exists():
                for subdir in path.iterdir():
                    if subdir.is_dir() and subdir.name.startswith("LGA_"):
                        if (subdir / "LGA_Projects_Panel_ScanProjects.py").exists():
                            projects_panel_path = subdir
                            break
                if projects_panel_path:
                    break
        except Exception:
            continue

# Método 3: rutas estándar en .nuke
if projects_panel_path is None:
    standard_paths = [
        Path.home() / ".nuke" / "Python" / "Startup" / "LGA_NKS_Projects_Panel_py",
        Path(os.path.expanduser("~")) / ".nuke" / "Python" / "Startup" / "LGA_NKS_Projects_Panel_py",
    ]
    for test_path in standard_paths:
        if (test_path / "LGA_Projects_Panel_ScanProjects.py").exists():
            projects_panel_path = test_path
            break

# Añadir al sys.path si se encontró
if projects_panel_path and projects_panel_path.exists():
    if str(projects_panel_path) not in sys.path:
        sys.path.insert(0, str(projects_panel_path))

# Importar funciones del módulo de escaneo
try:
    from LGA_Projects_Panel_ScanProjects import (
        scan_projects_on_disk,
        get_open_projects_info,
        is_project_open,
        get_project_sequences,
        get_projects_with_newer_versions,
    )
except ImportError as e:
    raise ImportError(
        f"No se pudo importar LGA_Projects_Panel_ScanProjects: {e}. Buscado en: {projects_panel_path}"
    )

# Importar función de cambio de secuencia V3 híbrida
try:
    import importlib

    import LGA_Projects_Panel_SwitchSequence

    importlib.reload(LGA_Projects_Panel_SwitchSequence)
    from LGA_Projects_Panel_SwitchSequence import switch_to_sequence_hybrid as switch_to_sequence

    debug_print("✅ Módulo LGA_Projects_Panel_SwitchSequence recargado exitosamente")
except ImportError as e:
    raise ImportError(f"No se pudo importar LGA_Projects_Panel_SwitchSequence: {e}")

# Importar módulo ProjectItem
try:
    from LGA_NKS_Projects_Panel_py.LGA_NKS_ProjectItem import ProjectItem, initialize_dependencies
    # Inicializar dependencias del módulo ProjectItem
    initialize_dependencies(get_project_colors, debug_print, switch_to_sequence)
    debug_print("✅ Módulo LGA_NKS_ProjectItem importado exitosamente")
except ImportError as e:
    debug_print(f"❌ Error importando LGA_NKS_ProjectItem: {e}")
    raise

# Importar módulo Workers
try:
    from LGA_NKS_Projects_Panel_py.LGA_NKS_Workers import WorkerSignals, ScanWorker, initialize_dependencies as initialize_workers_dependencies
    # Inicializar dependencias del módulo Workers
    initialize_workers_dependencies(scan_projects_on_disk, get_open_projects_info, debug_print)
    debug_print("✅ Módulo LGA_NKS_Workers importado exitosamente")
except ImportError as e:
    debug_print(f"❌ Error importando LGA_NKS_Workers: {e}")
    raise

# Importar módulo UIManager
try:
    from LGA_NKS_Projects_Panel_py.LGA_NKS_UIManager import UIManager, initialize_ui_dependencies
    # Inicializar dependencias del módulo UI
    initialize_ui_dependencies(
        REIMPORT_BUTTON,
        switch_login=SWITCH_ALLOWED_LOGIN,
        get_context_fn=get_context_mode,
        find_ini_fn=find_context_ini,
        get_login_fn=get_normal_pipesync_flow_login
    )
    debug_print("✅ Módulo LGA_NKS_UIManager importado exitosamente")
except ImportError as e:
    debug_print(f"❌ Error importando LGA_NKS_UIManager: {e}")
    raise

# Importar módulo ScanManager
try:
    from LGA_NKS_Projects_Panel_py.LGA_NKS_ScanManager import ScanManager, initialize_scan_dependencies
    # Inicializar dependencias del módulo ScanManager
    initialize_scan_dependencies(ScanWorker, debug_print, print_debug_messages)
    debug_print("✅ Módulo LGA_NKS_ScanManager importado exitosamente")
except ImportError as e:
    debug_print(f"❌ Error importando LGA_NKS_ScanManager: {e}")
    raise

# Importar módulo ProjectHandler
try:
    from LGA_NKS_Projects_Panel_py.LGA_NKS_ProjectHandler import ProjectHandler, initialize_project_dependencies
    # Inicializar dependencias del módulo ProjectHandler
    initialize_project_dependencies(ProjectItem, is_project_open, get_project_sequences, debug_print)
    debug_print("✅ Módulo LGA_NKS_ProjectHandler importado exitosamente")
except ImportError as e:
    debug_print(f"❌ Error importando LGA_NKS_ProjectHandler: {e}")
    raise


class ProjectsPanel(QtWidgets.QWidget):
    """Panel final integrado: escaneo, apertura y cambio de secuencias"""

    def __init__(self):
        super(ProjectsPanel, self).__init__()

        self.setObjectName("com.lega.ProjectsPanel")
        self.setWindowTitle("Projects")
        self.setAttribute(Qt.WA_DeleteOnClose, False)

        # Cargar configuración de colores
        debug_print("🏗️ Inicializando ProjectsPanel - cargando colores...")
        load_project_colors()
        debug_print("✅ Carga de colores completada")

        # Estado
        self.proyectos_encontrados = []
        self.proyectos_abiertos = {}
        self.project_items = {}
        self.content_stack = None
        self.projects_container = None
        self.settings_widget = None
        self.settings_rows = []
        self.settings_timer_dropdown = None
        self.auto_refresh_timer = QtCore.QTimer(self)
        self.auto_refresh_timer.timeout.connect(self._on_auto_refresh_timeout)
        self.ctx_client_btn = None
        self.ctx_studio_btn = None
        self.normal_pipesync_login = self._get_normal_pipesync_login()

        UIManager.setup_ui(self)
        UIManager.setup_connections(self)

        # Aplicar intervalo de auto-refresh desde .ini
        interval_key = self._load_auto_refresh_interval()
        self._apply_auto_refresh_interval(interval_key)

        # Delay antes de iniciar escaneo para que Qt esté completamente inicializado
        QtCore.QTimer.singleShot(500, self.start_scan)  # 500ms delay


    def _get_normal_pipesync_login(self):
        try:
            result = str(get_normal_pipesync_flow_login() or "").strip().lower()
            debug_print(f"Login de PipeSync normal: '{result}'")
            return result
        except Exception as e:
            debug_print(f"❌ No se pudo leer login de PipeSync normal: {e}")
            import traceback
            debug_print(f"Traceback: {traceback.format_exc()}")
            return ""

    def _get_context_ini_path(self):
        ini_path = find_context_ini()
        if ini_path:
            return Path(ini_path)
        return Path(__file__).resolve().parent.parent / "LGA_HieroTools_context.ini"

    def _refresh_context_toggle(self):
        """Actualiza el estilo del toggle pill segun el contexto activo."""
        if not hasattr(self, "ctx_client_btn") or self.ctx_client_btn is None:
            return
        current_mode = get_context_mode()
        active_style = (
            "QPushButton { background: #443a91; color: #cccccc; border: none;"
            " border-radius: 11px; padding: 3px 14px; font-size: 12px; }"
        )
        inactive_style = (
            "QPushButton { background: transparent; color: #8a8a8a; border: none;"
            " border-radius: 11px; padding: 3px 14px; font-size: 12px; }"
            " QPushButton:hover { color: #c8c8c8; }"
        )
        if current_mode == "client":
            self.ctx_client_btn.setStyleSheet(active_style)
            self.ctx_studio_btn.setStyleSheet(inactive_style)
        else:
            self.ctx_studio_btn.setStyleSheet(active_style)
            self.ctx_client_btn.setStyleSheet(inactive_style)
        self.ctx_client_btn.setToolTip("Contexto Client (PipeSyncClient)")
        self.ctx_studio_btn.setToolTip("Contexto Studio (PipeSync normal)")

    def _write_context_mode(self, mode):
        ini_path = self._get_context_ini_path()
        ini_path.parent.mkdir(parents=True, exist_ok=True)

        parser = configparser.ConfigParser()
        if ini_path.exists():
            parser.read(str(ini_path), encoding="utf-8")
        if not parser.has_section("Context"):
            parser.add_section("Context")
        parser.set("Context", "mode", mode)

        with open(ini_path, "w", encoding="utf-8") as ini_file:
            parser.write(ini_file)

        os.environ["LGA_HIEROTOOLS_CONTEXT_INI"] = str(ini_path)
        os.environ["PIPESYNC_CONTEXT"] = mode
        debug_print(f"Contexto actualizado a '{mode}' en {ini_path}")
        return ini_path

    def _reload_after_context_switch(self):
        self.start_scan()
        QtCore.QTimer.singleShot(150, self.start_scan)

    def set_context_mode(self, mode):
        """Cambia el contexto al modo indicado (studio|client) si difiere del actual."""
        new_mode = "client" if mode == "client" else "studio"
        current_mode = get_context_mode()
        if new_mode == current_mode:
            return
        try:
            self._write_context_mode(new_mode)
            self._reload_after_context_switch()
            self._refresh_context_toggle()
            debug_print(f"Contexto cambiado a '{new_mode}' desde toggle")
        except Exception as e:
            debug_print(f"Error al cambiar contexto: {e}")
            self._refresh_context_toggle()
            QtWidgets.QMessageBox.warning(
                self, "Error al cambiar contexto", f"No se pudo cambiar el contexto:\n{e}"
            )

    def eventFilter(self, obj, event):
        """Manejar eventos de hover para botones y labels"""
        return UIManager.eventFilter(self, obj, event)

    def start_scan(self):
        ScanManager.start_scan(self)
        self._restart_auto_refresh_timer()

    def on_scan_finished(self, proyectos_encontrados, proyectos_abiertos):
        ScanManager.on_scan_finished(self, proyectos_encontrados, proyectos_abiertos)

    def on_scan_error(self, error_msg):
        ScanManager.on_scan_error(self, error_msg)

    def update_projects_display(self):
        ProjectHandler.update_projects_display(self)
        # Siempre volver a la vista principal después de actualizar
        self.show_projects_view()

    def on_project_click(self, proyecto_info):
        ProjectHandler.on_project_click(self, proyecto_info)

    def reimport_panel(self):
        """Recarga el panel usando el script externo de smart reload"""
        debug_print("🔄 BOTÓN REIMPORT PRESIONADO - Iniciando recarga del panel...")
        try:
            # 🔄 RECARGAR COLORES DESDE .INI ANTES DEL RELOAD
            debug_print("🔄 Recargando colores desde .ini antes del reimport...")
            load_project_colors()
            debug_print("✅ Colores recargados desde .ini")

            script_path = os.path.join(
                os.path.dirname(__file__), "LGA_NKS_Projects_Panel_py", "LGA_NKS_Projects_Panel_Smart_Reload.py"
            )
            if os.path.exists(script_path):
                import importlib.util

                spec = importlib.util.spec_from_file_location(
                    "LGA_NKS_Projects_Panel_Smart_Reload", script_path
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                module.main()
                debug_print("Ejecutado LGA_NKS_Projects_Panel_Smart_Reload script.")
            else:
                debug_print(f"Script not found at path: {script_path}")
        except Exception as e:
            debug_print(f"Error durante reimportación: {e}")
            QtWidgets.QMessageBox.warning(self, "Error", f"Error durante reimportación:\n{str(e)}")

    def on_update_project_click(self, newer_version_info):
        """Manejar el click en el botón de update para actualizar proyecto a versión más nueva"""
        ProjectHandler.on_update_project_click(self, newer_version_info)

    # =========================
    #       SETTINGS VIEW
    # =========================
    def show_settings_view(self):
        if not self.settings_widget:
            self._build_settings_view()
        if self.content_stack and self.settings_widget:
            self.content_stack.setCurrentWidget(self.settings_widget)
            # Actualizar la etiqueta de cuenta regresiva cada vez que se muestra settings
            self._update_next_refresh_label()

    def show_projects_view(self):
        if self.content_stack and self.projects_container:
            self.content_stack.setCurrentWidget(self.projects_container)

    def _build_settings_view(self):
        self.settings_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(self.settings_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)  # Espaciado más pequeño entre items

        # IMPORTANTE: Configurar para que NO expanda espacios automáticamente
        self.settings_widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)

        # Auto-refresh interval (label + dropdown en fila horizontal)
        interval_row = QtWidgets.QHBoxLayout()
        interval_row.setContentsMargins(0, 0, 0, 0)
        interval_row.setSpacing(8)

        interval_label = QtWidgets.QLabel("Auto-refresh")

        # Ruta para icono SVG de flecha (triángulo sólido)
        arrow_icon_path = os.path.join(os.path.dirname(__file__), "LGA_NKS_Projects_Panel_py", "down_arrow.svg")
        arrow_icon_url = QtCore.QUrl.fromLocalFile(arrow_icon_path).toString()

        # Aplicar estilo elegante al dropdown con flecha y separador DENTRO del botón
        dropdown_stylesheet = f"""
            QComboBox {{
                background-color: #2d2d2d;
                border: 1px solid #555555;
                border-radius: 3px;
                color: #d8d8d8;
                padding: 2px 24px 2px 8px;  /* espacio derecho para separador + flecha */
                min-height: 24px;
            }}
            QComboBox:hover {{
                background-color: #3d3d3d;
                border: 1px solid #777777;
            }}
            QComboBox::drop-down {{
                border-left: 1px solid #555555; /* separador vertical interno */
                background: transparent;
                width: 20px;
                subcontrol-origin: padding;
                subcontrol-position: right center;
            }}
            QComboBox::down-arrow {{
                image: url("{arrow_icon_url}");
                width: 10px;
                height: 6px;
                margin-right: 4px;
                margin-top: 3px;
            }}
            QComboBox QAbstractItemView {{
                background-color: #2d2d2d;
                border: 1px solid #555555;
                border-radius: 3px;
                color: #d8d8d8;
                selection-background-color: #443a91;
                selection-color: #ffffff;
            }}
        """

        self.settings_timer_dropdown = QtWidgets.QComboBox()
        self.settings_timer_dropdown.setFixedWidth(95)  # Ancho suficiente para texto + flecha integrada
        self.settings_timer_dropdown.setStyleSheet(dropdown_stylesheet)
        for key in ["never", "5min", "10min", "15min", "30min", "1h", "2h"]:
            self.settings_timer_dropdown.addItem(key, key)

        # Orden correcto: label primero, luego dropdown
        interval_row.addWidget(interval_label)
        interval_row.addWidget(self.settings_timer_dropdown)
        interval_row.addStretch(1)  # Empujar elementos a la izquierda

        current_interval_key = self._load_auto_refresh_interval()
        idx = self.settings_timer_dropdown.findData(current_interval_key)
        if idx >= 0:
            self.settings_timer_dropdown.setCurrentIndex(idx)

        layout.addLayout(interval_row)

        # Línea de próximo auto-refresh
        self.next_refresh_label = QtWidgets.QLabel("Next in: --")
        self.next_refresh_label.setStyleSheet("color: #888888; font-size: 13px; margin: 0px;")
        self.next_refresh_label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
        self.next_refresh_label.setMinimumHeight(20)
        layout.addWidget(self.next_refresh_label, alignment=QtCore.Qt.AlignLeft)

        # Actualizar la etiqueta con el estado actual del timer
        self._update_next_refresh_label()

        # Línea en blanco antes del título de projects colors
        layout.addWidget(QtWidgets.QLabel(""))

        # Projects colors list
        colors_label = QtWidgets.QLabel("Project colors")
        colors_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #d8d8d8;")
        layout.addWidget(colors_label)

        self.settings_rows = []
        self.settings_list_container = QtWidgets.QWidget()
        self.settings_list_layout = QtWidgets.QVBoxLayout(self.settings_list_container)
        self.settings_list_layout.setContentsMargins(0, 0, 0, 0)
        self.settings_list_layout.setSpacing(4)  # Reducir espacios entre filas de colores
        layout.addWidget(self.settings_list_container)

        for name, color in sorted(PROJECT_COLORS.items()):
            self._add_settings_row(name, color)

        # Aplicar estilo dinámico al botón Add project con color gris oscuro
        add_button_style = "#3f3f3f"
        add_border_color = calculate_dynamic_border(add_button_style)
        add_hover_color = calculate_dynamic_hover(add_button_style)

        add_button_stylesheet = f"""
            QPushButton {{
                background-color: {add_button_style};
                border: 1px solid {add_border_color};
                border-radius: 3px;
                color: #d8d8d8;
                padding: 0px 0px;
                min-height: 24px;
            }}
            QPushButton:hover {{
                background-color: {add_hover_color};
            }}
            QPushButton:pressed {{
                background-color: {add_button_style}aa;
            }}
        """

        add_button = QtWidgets.QPushButton("+ Add project")
        add_button.setFixedWidth(188)  # Ancho para el botón
        add_button.setStyleSheet(add_button_stylesheet)
        add_button.clicked.connect(lambda: self._add_settings_row("", "#cccccc"))
        layout.addWidget(add_button)

        # Línea en blanco antes de los botones Cancel y Save
        layout.addWidget(QtWidgets.QLabel(""))

        # Save / Cancel buttons - alineados con los botones X de las filas
        # El layout padre ya tiene 10px de margen izquierdo, así que ajustamos
        # ancho real necesario: 140 + 4 + 40 + 4 + 30 - 10 = 208px
        buttons_container = QtWidgets.QHBoxLayout()
        buttons_container.setContentsMargins(40, 0, 0, 0)  # ✅✅ Margen izquierdo para alinear con botones X
        buttons_container.setSpacing(10)

        # Aplicar estilo dinámico a los botones Cancel y Save
        button_style = "#443a91"
        border_color = calculate_dynamic_border(button_style)
        hover_color = calculate_dynamic_hover(button_style)

        button_stylesheet = f"""
            QPushButton {{
                background-color: {button_style};
                border: 1px solid {border_color};
                border-radius: 3px;
                color: #d8d8d8;
                padding: 0px 0px;
                min-height: 24px;
            }}
            QPushButton:hover {{
                background-color: {hover_color};
            }}
            QPushButton:pressed {{
                background-color: {button_style}aa;
            }}
        """

        cancel_btn = QtWidgets.QPushButton("Cancel")
        save_btn = QtWidgets.QPushButton("Save")
        cancel_btn.setFixedWidth(70)
        save_btn.setFixedWidth(70)
        cancel_btn.setStyleSheet(button_stylesheet)
        save_btn.setStyleSheet(button_stylesheet)
        cancel_btn.clicked.connect(self._on_settings_cancel)
        save_btn.clicked.connect(self._on_settings_save)

        buttons_container.addWidget(cancel_btn)
        buttons_container.addWidget(save_btn)
        buttons_container.addStretch(1)  # Empujar botones a la izquierda dentro del margen

        layout.addLayout(buttons_container)

        # AÑADIR STRETCH AL FINAL PARA EVITAR ESPACIOS FLEX ENTRE ELEMENTOS
        layout.addStretch(1)

        # Insert settings widget into stack
        if self.content_stack:
            self.content_stack.addWidget(self.settings_widget)

    def _add_settings_row(self, name, color):
        row_widget = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)  # Espacio de 3px entre elementos de cada fila

        name_edit = QtWidgets.QLineEdit(name)
        name_edit.setPlaceholderText("Project name (e.g. BRDA)")
        name_edit.setFixedWidth(140)

        # Aplicar estilo dinámico al botón de color manteniendo el color actual
        color_border_color = calculate_dynamic_border(color)
        color_hover_color = calculate_dynamic_hover(color)

        color_button_stylesheet = f"""
            QPushButton {{
                background-color: {color};
                border: 1px solid {color_border_color};
                border-radius: 3px;
                color: #d8d8d8;
                padding: 0px 0px;
            }}
            QPushButton:hover {{
                background-color: {color_hover_color};
            }}
            QPushButton:pressed {{
                background-color: {color}aa;
            }}
        """

        color_btn = QtWidgets.QPushButton()
        color_btn.setFixedSize(16, 16)
        color_btn.setStyleSheet(color_button_stylesheet)

        def pick_color():
            dlg = QtWidgets.QColorDialog(QtGui.QColor(color_btn.palette().button().color()))
            dlg.setOption(QtWidgets.QColorDialog.ShowAlphaChannel, False)
            if dlg.exec_():
                chosen = dlg.selectedColor().name()
                # Aplicar el nuevo estilo dinámico con el color elegido
                new_border_color = calculate_dynamic_border(chosen)
                new_hover_color = calculate_dynamic_hover(chosen)
                new_stylesheet = f"""
                    QPushButton {{
                        background-color: {chosen};
                        border: 1px solid {new_border_color};
                        border-radius: 3px;
                        color: #d8d8d8;
                        padding: 0px 0px;
                    }}
                    QPushButton:hover {{
                        background-color: {new_hover_color};
                    }}
                    QPushButton:pressed {{
                        background-color: {chosen}aa;
                    }}
                """
                color_btn.setStyleSheet(new_stylesheet)

        color_btn.clicked.connect(pick_color)

        # Aplicar estilo dinámico al botón delete con color rojo no saturado
        delete_button_style = "#a33333"
        delete_border_color = calculate_dynamic_border(delete_button_style)
        delete_hover_color = calculate_dynamic_hover(delete_button_style)

        delete_button_stylesheet = f"""
            QPushButton {{
                background-color: {delete_button_style};
                border: 1px solid {delete_border_color};
                border-radius: 3px;
                color: #d8d8d8;
                padding: 0px 0px;
            }}
            QPushButton:hover {{
                background-color: {delete_hover_color};
            }}
            QPushButton:pressed {{
                background-color: {delete_button_style}aa;
            }}
        """

        delete_btn = QtWidgets.QPushButton("✕")
        delete_btn.setFixedSize(16, 16)
        delete_btn.setStyleSheet(delete_button_stylesheet)

        def delete_row():
            self.settings_list_layout.removeWidget(row_widget)
            row_widget.deleteLater()
            self.settings_rows[:] = [r for r in self.settings_rows if r["widget"] != row_widget]

        delete_btn.clicked.connect(delete_row)

        row_layout.addWidget(name_edit)
        row_layout.addWidget(color_btn)
        row_layout.addWidget(delete_btn)
        row_layout.addStretch(1)

        self.settings_list_layout.addWidget(row_widget)
        self.settings_rows.append({"widget": row_widget, "name": name_edit, "color_btn": color_btn})

    def _on_settings_cancel(self):
        self.show_projects_view()

    def _on_settings_save(self):
        interval_key = self.settings_timer_dropdown.currentData()
        self._save_auto_refresh_interval(interval_key)

        # Leer colores
        new_colors = {}
        for row in self.settings_rows:
            name = row["name"].text().strip().upper()
            if not name:
                continue
            color = row["color_btn"].palette().button().color().name()
            new_colors[name] = color

        self._save_colors_to_ini(new_colors)
        load_project_colors()
        self._apply_auto_refresh_interval(interval_key)
        self.show_projects_view()
        self.start_scan()

    # --- Auto refresh helpers ---
    def _load_auto_refresh_interval(self):
        ini_path = Path(__file__).parent / "LGA_NKS_Projects_Panel.ini"
        if not ini_path.exists():
            return "never"
        config = configparser.ConfigParser()
        config.read(ini_path, encoding="utf-8")
        return config.get("General", "AutoRefreshInterval", fallback="never")

    def _save_auto_refresh_interval(self, key):
        ini_path = Path(__file__).parent / "LGA_NKS_Projects_Panel.ini"
        config = configparser.ConfigParser()
        if ini_path.exists():
            config.read(ini_path, encoding="utf-8")
        if "General" not in config:
            config["General"] = {}
        config["General"]["AutoRefreshInterval"] = key
        with open(ini_path, "w", encoding="utf-8") as f:
            config.write(f)

    def _apply_auto_refresh_interval(self, key):
        minutes = AUTO_REFRESH_OPTIONS.get(key, 0)
        if minutes <= 0:
            self.auto_refresh_timer.stop()
            self._update_next_refresh_label()
            return
        self.auto_refresh_timer.start(minutes * 60 * 1000)
        self._update_next_refresh_label()

    def _restart_auto_refresh_timer(self):
        if self.auto_refresh_timer.isActive():
            self.auto_refresh_timer.start(self.auto_refresh_timer.interval())
        self._update_next_refresh_label()

    def _on_auto_refresh_timeout(self):
        if self.refresh_button.isEnabled():
            self.start_scan()
        self._update_next_refresh_label()

    def _update_next_refresh_label(self):
        """Actualiza la etiqueta de cuenta regresiva del auto-refresh."""
        if not hasattr(self, "next_refresh_label") or self.next_refresh_label is None:
            return
        if not self.auto_refresh_timer.isActive():
            self.next_refresh_label.setText("Next in: --")
            return
        remaining_ms = self.auto_refresh_timer.remainingTime()
        if remaining_ms < 0:
            self.next_refresh_label.setText("Next in: --")
            return
        minutes = max(1, int(round(remaining_ms / 60000.0)))
        self.next_refresh_label.setText(f"Next in: {minutes} min")

    def _save_colors_to_ini(self, colors_dict):
        ini_path = Path(__file__).parent / "LGA_NKS_Projects_Panel.ini"
        config = configparser.ConfigParser()
        if ini_path.exists():
            config.read(ini_path, encoding="utf-8")
        if "Colors" not in config:
            config["Colors"] = {}
        config["Colors"].clear()
        for name, color in colors_dict.items():
            config["Colors"][name] = color
        with open(ini_path, "w", encoding="utf-8") as f:
            config.write(f)


# Crear la instancia del widget y añadirlo al gestor de ventanas de Hiero
# SOLO si AUTO_CREATE_PANEL está activado (controlado por smart reload)
if AUTO_CREATE_PANEL:
    projectsPanel = ProjectsPanel()
    wm = hiero.ui.windowManager()
    wm.addWindow(projectsPanel)
