"""
____________________________________________________________________________________

  LGA_NKS_Flow_FlowProd_Panel v1.0 | Lega Pugliese
  Panel para operaciones de producción con Flow:
  - Revelar clips en Flow
  - Crear shots automáticamente
____________________________________________________________________________________
"""

import hiero.ui
import hiero.core
import sys
import os
from PySide2.QtWidgets import (
    QWidget,
    QPushButton,
    QGridLayout,
    QMessageBox,
    QSpacerItem,
    QSizePolicy,
)
from PySide2.QtCore import Qt
from PySide2.QtGui import QColor, QKeySequence


# Variable global para activar o desactivar los prints
DEBUG = False


def debug_print(*message):
    if DEBUG:
        print(*message)


class FlowProdPanel(QWidget):
    def __init__(self):
        super(FlowProdPanel, self).__init__()
        self.setObjectName("com.lega.FlowProdPanel")
        self.setWindowTitle("Flow Production")
        self.layout = QGridLayout()
        self.setLayout(self.layout)

        # Definir los botones fijos y sus colores/estilos
        self.fixed_buttons = [
            (
                "Reveal in Flow",
                self.show_in_flow_for_selected_clip,
                "#1f1f1f",
                "Shift+F",
                "Shift+F",
            ),
            (
                "Create Shot",
                self.create_shot_for_selected_clip,
                "#2a4d3a",
            ),
        ]

        # Solo botones fijos para este panel
        self.buttons = self.fixed_buttons

        self.num_columns = 1  # Inicialmente una columna
        self.create_buttons()

        # Conectar la senal de cambio de tamano del widget al metodo correspondiente
        self.adjust_columns_on_resize()
        self.resizeEvent = self.adjust_columns_on_resize

    def create_buttons(self):
        # Limpiar el layout actual antes de crear nuevos botones
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        for index, button_info in enumerate(self.buttons):
            name = button_info[0]
            handler = button_info[1]
            style = button_info[2]

            # Solo botones fijos para este panel: (name, handler, style, [shortcut], [tooltip])
            shortcut = button_info[3] if len(button_info) > 3 else None
            tooltip = button_info[4] if len(button_info) > 4 else None

            button = QPushButton(name)
            button.clicked.connect(handler)

            # Agregar shortcut y tooltip si existen
            if shortcut:
                button.setShortcut(QKeySequence(shortcut))
            if tooltip:
                button.setToolTip(tooltip)

            # Aplicar solo el color de fondo, sin negrita ni color de texto blanco
            button.setStyleSheet(f"background-color: {style}")

            row = index // self.num_columns
            column = index % self.num_columns
            self.layout.addWidget(button, row, column)

        # Calcular el numero de filas usadas
        num_rows = (len(self.buttons) + self.num_columns - 1) // self.num_columns

        # Anadir el espaciador vertical al final
        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.layout.addItem(spacer, num_rows, 0, 1, self.num_columns)

    def adjust_columns_on_resize(self, event=None):
        # Obtener el ancho actual del widget
        panel_width = self.width()
        button_width = 100  # Ancho aproximado de cada boton
        min_button_spacing = 10  # Espacio minimo entre botones

        # Calcular el numero de columnas en funcion del ancho del widget
        new_num_columns = max(
            1, (panel_width + min_button_spacing) // (button_width + min_button_spacing)
        )

        if new_num_columns != self.num_columns:
            self.num_columns = new_num_columns
            # Volver a crear los botones con el nuevo numero de columnas
            self.create_buttons()

    def parse_exr_name(self, exr_name):
        # Ajustar el manejo del formato del nombre del archivo EXR
        if "%04d" in exr_name:
            exr_name = exr_name.replace(".%", "_%")  # Reemplazar patron para analisis
        parts = exr_name.split("_")
        if len(parts) < 7 or not parts[-2].startswith("v"):
            raise ValueError(
                f"Nombre del archivo EXR no tiene el formato esperado: {exr_name}"
            )
        base_name = "_".join(parts[:-1])
        return base_name

    def show_in_flow_for_selected_clip(self):
        """Llama al script Show in Flow para abrir la task comp en Chrome"""
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Flow", "LGA_NKS_Flow_ShowInFlow.py"
        )
        if not os.path.exists(script_path):
            QMessageBox.warning(
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
            module.show_in_flow_from_selected_clip()
        except Exception as e:
            QMessageBox.warning(self, "Error al ejecutar", str(e))

    def create_shot_for_selected_clip(self):
        """Llama al script Create Shot para crear shots basado en el clip seleccionado"""
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Flow", "LGA_NKS_Flow_CreateShot.py"
        )
        if not os.path.exists(script_path):
            QMessageBox.warning(
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
            QMessageBox.warning(self, "Error al ejecutar", str(e))


# Crear la instancia del panel y agregarlo al windowManager de Hiero
flowProdPanel = FlowProdPanel()
wm = hiero.ui.windowManager()
wm.addWindow(flowProdPanel)
