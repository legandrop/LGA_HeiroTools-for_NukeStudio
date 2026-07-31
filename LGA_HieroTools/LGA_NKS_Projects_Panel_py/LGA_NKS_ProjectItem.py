# -*- coding: utf-8 -*-

"""
____________________________________________________________________

  LGA_NKS_ProjectItem v1.01 | Lega

  Widget personalizado para mostrar proyectos y secuencias en el panel de proyectos LGA.

  v1.01: El color sale de 'project_key' (carpeta VFX-) y no del nombre del archivo
____________________________________________________________________

"""

# Forzar recarga del módulo para evitar problemas de cache en Nuke
import sys
if 'LGA_NKS_ProjectItem' in sys.modules:
    import importlib
    importlib.reload(sys.modules['LGA_NKS_ProjectItem'])

from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt, horizontal_advance

# Importar funciones necesarias del módulo principal
# Estas serán importadas desde el archivo principal cuando se importe este módulo
get_project_colors = None
debug_print = None
switch_to_sequence = None


def initialize_dependencies(colors_func, debug_func, switch_func):
    """Inicializar las dependencias externas necesarias para ProjectItem"""
    global get_project_colors, debug_print, switch_to_sequence
    get_project_colors = colors_func
    debug_print = debug_func
    switch_to_sequence = switch_func


class ProjectItem(QtWidgets.QWidget):
    """Widget personalizado para mostrar un proyecto y sus secuencias"""

    def __init__(self, project_info, panel=None, has_newer_version=False, newer_version_info=None, parent=None):
        super(ProjectItem, self).__init__(parent)
        self.project_info = project_info
        self.panel = panel  # Referencia al ProjectsPanel para el event filter
        self.is_open = False
        self.sequences = []
        self.has_newer_version = has_newer_version
        self.newer_version_info = newer_version_info  # Dict con info de versión más nueva
        self.setup_ui()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 2, 5, 2)

        # Contenedor horizontal para el proyecto (para evitar expansión horizontal)
        project_container = QtWidgets.QWidget()
        project_layout = QtWidgets.QHBoxLayout(project_container)
        project_layout.setContentsMargins(0, 0, 0, 0)
        project_layout.setSpacing(0)

        # Nombre del proyecto (clickable)
        self.project_label = QtWidgets.QLabel()
        self.project_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.project_label.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        self.project_label.setWordWrap(False)  # No word wrap para mantener en una línea
        self.project_label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
        # Asegurar que el texto no se trunque
        self.project_label.setTextFormat(QtCore.Qt.PlainText)
        # El event filter se instalará desde ProjectsPanel
        project_layout.addWidget(self.project_label)

        # Botón de update (siempre creado, inicialmente oculto)
        self.update_button = QtWidgets.QPushButton()
        self.update_button.setToolTip("Actualizar a versión más nueva")
        self.update_button.setStyleSheet("""
            QPushButton {
                border: none;
                padding: 2px;
                background: transparent;
            }
        """)
        self.update_button.setVisible(False)  # Inicialmente oculto
        self.update_button.setFixedSize(20, 20)  # Tamaño fijo pequeño

        # Configurar iconos SVG para el botón de update
        import os
        update_icon_path = os.path.join(os.path.dirname(__file__), "update.svg")
        update_hover_icon_path = os.path.join(os.path.dirname(__file__), "update_white.svg")

        if os.path.exists(update_icon_path) and os.path.exists(update_hover_icon_path):
            self.update_icon_normal = QtGui.QIcon(update_icon_path)
            self.update_icon_hover = QtGui.QIcon(update_hover_icon_path)
            self.update_button.setIcon(self.update_icon_normal)
            self.update_button.setIconSize(QtCore.QSize(16, 16))
            # Guardar referencias de iconos en el propio botón para el event filter
            self.update_button.update_icon_normal = self.update_icon_normal
            self.update_button.update_icon_hover = self.update_icon_hover

            # Instalar event filter para manejar hover
            if self.panel:
                self.update_button.installEventFilter(self.panel)

        # Conectar el click del botón
        self.update_button.clicked.connect(self.on_update_click)
        project_layout.addWidget(self.update_button)

        # Spacer horizontal para empujar los elementos a la izquierda
        spacer = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        project_layout.addItem(spacer)

        layout.addWidget(project_container)

        # Contenedor para secuencias
        self.sequences_widget = QtWidgets.QWidget()
        self.sequences_layout = QtWidgets.QVBoxLayout(self.sequences_widget)
        self.sequences_layout.setContentsMargins(20, 0, 0, 0)
        self.sequences_widget.hide()
        layout.addWidget(self.sequences_widget)

        self.update_display()

    def update_display(self):
        nombre = self.project_info.get("nombre_base", "")
        version = self.project_info.get("version", "")

        # Extraer nombre del proyecto (antes de _SUP_)
        project_name = nombre
        if "_SUP" in nombre:
            project_name = nombre.split("_SUP")[0]

        # Limpiar versión (quitar 'v' inicial)
        clean_version = version.lstrip('v')

        # Crear texto formateado: "NOMBRE (vXXX)"
        formatted_text = f"{project_name} (v{clean_version})"

        # Obtener colores para este proyecto. El color es del proyecto de trabajo
        # (carpeta VFX-), no del nombre del archivo: ERSO_SUP y ERSO_Breakdown son ERSO.
        color_key = self.project_info.get("project_key") or project_name
        debug_print(f"🎨 Aplicando colores para proyecto: '{color_key}' (desde nombre_base: '{nombre}')")
        base_color, hover_color = get_project_colors(color_key)
        debug_print(f"🎨 Colores aplicados - Base: {base_color}, Hover: {hover_color}")

        # Agregar emoji según estado
        if self.is_open and self.sequences:
            display_text = f"▼ {formatted_text}"
            self.project_label.setStyleSheet(f"font-size: 13px; color: {base_color};")
            # Guardar colores para el event filter
            self.project_label.setProperty("base_color", base_color)
            self.project_label.setProperty("hover_color", hover_color)
            self.project_label.setProperty("is_project_label", True)  # Para distinguir del resto
            self.show_sequences()
        else:
            display_text = f"▶ {formatted_text}"
            self.project_label.setStyleSheet(f"font-size: 13px; color: {base_color};")
            # Guardar colores para el event filter
            self.project_label.setProperty("base_color", base_color)
            self.project_label.setProperty("hover_color", hover_color)
            self.project_label.setProperty("is_project_label", True)  # Para distinguir del resto
            self.sequences_widget.hide()

        # Debug: mostrar exactamente qué texto se está configurando
        debug_print(f"UI: Configurando texto para {project_name}: '{display_text}' (longitud: {len(display_text)})")

        self.project_label.setText(display_text)

        # Forzar actualización del tamaño del label para asegurar que muestre todo el texto
        self.project_label.adjustSize()

        # Calcular el tamaño necesario para el texto usando la función compatible del adapter
        font_metrics = self.project_label.fontMetrics()
        text_width = horizontal_advance(font_metrics, display_text)
        text_height = font_metrics.height()

        # Establecer tamaño mínimo basado en el texto
        min_width = text_width + 20  # +20 para padding
        self.project_label.setMinimumWidth(min_width)

        # Manejar visibilidad del botón de update
        should_show_update = self.has_newer_version and self.is_open
        self.update_button.setVisible(should_show_update)
        debug_print(f"UI: Botón update visible: {should_show_update} (has_newer: {self.has_newer_version}, is_open: {self.is_open})")

        # Debug adicional para entender por qué aparece siempre
        if should_show_update:
            debug_print(f"   🔍 DEBUG: Botón VISIBLE - Proyecto: {self.project_info.get('nombre_base', '')}, versión: {self.project_info.get('version', '')}")
        elif self.has_newer_version:
            debug_print(f"   🔍 DEBUG: Botón OCULTO pero has_newer=True - Proyecto no abierto: {self.project_info.get('nombre_base', '')}")
        elif self.is_open:
            debug_print(f"   🔍 DEBUG: Botón OCULTO pero is_open=True - Proyecto sin versión nueva: {self.project_info.get('nombre_base', '')}")

        # Forzar actualización del layout
        self.project_label.update()
        self.update()

        # Verificar que el texto se aplicó correctamente
        actual_text = self.project_label.text()
        debug_print(f"UI: Texto aplicado al QLabel: '{actual_text}' (longitud: {len(actual_text)})")
        if actual_text != display_text:
            debug_print(f"ERROR: Texto aplicado difiere del esperado!")
            # Debug detallado carácter por carácter
            debug_print(f"Esperado: {[c for c in display_text]}")
            debug_print(f"Actual:   {[c for c in actual_text]}")

        # Información adicional de debug
        size = self.project_label.size()
        debug_print(f"UI: QLabel size: {size.width()}x{size.height()}, texto requiere: {text_width}x{text_height}")

        # Información adicional de debug
        size = self.project_label.size()
        min_size = self.project_label.minimumSize()
        debug_print(f"UI: QLabel size: {size.width()}x{size.height()}, min_size: {min_size.width()}x{min_size.height()}")

    def show_sequences(self):
        # Limpiar secuencias anteriores
        for i in reversed(range(self.sequences_layout.count())):
            self.sequences_layout.itemAt(i).widget().setParent(None)

        proyecto_obj = self.project_info.get("proyecto_obj")
        sequences_dict = {}

        if proyecto_obj:
            try:
                for seq in proyecto_obj.sequences():
                    try:
                        sequences_dict[seq.name()] = seq
                    except Exception:
                        continue
            except Exception:
                pass

        # Obtener colores para las secuencias (mismo que el proyecto padre)
        project_name = self.project_info.get("nombre_base", "")
        if "_SUP" in project_name:
            project_name = project_name.split("_SUP")[0]
        color_key = self.project_info.get("project_key") or project_name
        base_color, hover_color = get_project_colors(color_key)

        for seq_name in sorted(self.sequences):
            # Contenedor horizontal para la secuencia
            seq_container = QtWidgets.QWidget()
            seq_layout = QtWidgets.QHBoxLayout(seq_container)
            seq_layout.setContentsMargins(0, 0, 0, 0)
            seq_layout.setSpacing(0)

            seq_label = QtWidgets.QLabel(f"> {seq_name}")
            seq_label.setStyleSheet(f"color: {base_color};")
            seq_label.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
            seq_label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Preferred)
            seq_label.adjustSize()  # Ajustar tamaño al contenido del texto
            # Guardar colores para el event filter
            seq_label.setProperty("base_color", base_color)
            seq_label.setProperty("hover_color", hover_color)

            # Instalar event filter para hover (si hay panel disponible)
            if self.panel:
                seq_label.installEventFilter(self.panel)

            seq_obj = sequences_dict.get(seq_name)
            seq_label.mousePressEvent = (
                lambda e, name=seq_name, so=seq_obj, po=self.project_info.get("proyecto_obj"): self.on_sequence_click(name, so, po)
            )

            seq_layout.addWidget(seq_label)

            # Spacer horizontal para empujar el label a la izquierda
            seq_spacer = QtWidgets.QSpacerItem(0, 0, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
            seq_layout.addItem(seq_spacer)

            self.sequences_layout.addWidget(seq_container)

        self.sequences_widget.show()

    def on_sequence_click(self, sequence_name, sequence_obj=None, proyecto_obj=None):
        """Abrir secuencia en timeline preservando ajustes (cross-project)"""
        try:
            success = switch_to_sequence(sequence_name, target_project=proyecto_obj)
            if success:
                debug_print(f"✅ Secuencia '{sequence_name}' cambiada exitosamente")
            else:
                debug_print(f"❌ Error cambiando a secuencia '{sequence_name}'")
        except Exception as e:
            debug_print(f"❌ Error en cambio de secuencia '{sequence_name}': {e}")
            import traceback

            debug_print(traceback.format_exc())

    def set_open_state(self, is_open, sequences=None, proyecto_obj=None):
        self.is_open = is_open
        if sequences is not None:
            self.sequences = sequences
        if proyecto_obj:
            self.project_info["proyecto_obj"] = proyecto_obj
        self.update_display()

    def on_update_click(self):
        """Manejar el click en el botón de update para abrir la versión más nueva"""
        if self.panel and self.newer_version_info:
            # Llamar al método del panel para manejar la actualización
            if hasattr(self.panel, 'on_update_project_click'):
                self.panel.on_update_project_click(self.newer_version_info)
