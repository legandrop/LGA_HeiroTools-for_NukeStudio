"""
____________________________________________________________________________________

  LGA_NKS_Flow_Assignee_Panel v1.4 | Lega Pugliese
  Panel para obtener los asignados de la tarea del clip seleccionado en Flow,
  limpiarlos o sumar asignados a la tarea comp.
____________________________________________________________________________________
"""

import hiero.ui
import hiero.core
import sys
import os
import json
from PySide2.QtWidgets import (
    QWidget,
    QPushButton,
    QGridLayout,
    QMessageBox,
    QSpacerItem,
    QSizePolicy,
)
from PySide2.QtCore import Qt
from PySide2.QtGui import QColor


# Variable global para activar o desactivar los prints
DEBUG = True


def debug_print(*message):
    if DEBUG:
        print(*message)


class AssigneePanel(QWidget):
    def __init__(self):
        super(AssigneePanel, self).__init__()
        self.setObjectName("com.lega.FPTAssigneePanel")
        self.setWindowTitle("Assignees")
        self.layout = QGridLayout()
        self.setLayout(self.layout)

        # Cargar usuarios desde el archivo JSON
        self.users = self.load_users_from_config()
        debug_print(f"Usuarios cargados: {self.users}")

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
                "Get Assignees",
                self.get_assignees_for_selected_clip,
                "#202233",
            ),
            (
                "Clear Assignees",
                self.clear_assignees_for_selected_clip,
                "#202233",
            ),
        ]

        # Crear la lista completa de botones (fijos + usuarios)
        self.buttons = self.fixed_buttons + self.create_user_buttons()

        self.num_columns = 1  # Inicialmente una columna
        self.create_buttons()

        # Conectar la senal de cambio de tamano del widget al metodo correspondiente
        self.adjust_columns_on_resize()
        self.resizeEvent = self.adjust_columns_on_resize

    def load_users_from_config(self):
        """Carga la lista de usuarios desde el archivo JSON de configuracion"""
        config_path = os.path.join(os.path.dirname(__file__), "LGA_NKS_Flow_Users.json")
        try:
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    return config.get("users", [])
            else:
                debug_print(f"Archivo de configuracion no encontrado: {config_path}")
                # Crear archivo de configuracion por defecto si no existe
                self.create_default_config(config_path)
                return self.load_users_from_config()  # Intentar cargar nuevamente
        except Exception as e:
            debug_print(f"Error al cargar configuracion de usuarios: {e}")
            return []

    def create_default_config(self, config_path):
        """Crea un archivo de configuracion por defecto"""
        default_config = {
            "users": [
                {"name": "Lega Pugliese", "color": "#69135e"},
                {"name": "Sebas Romano", "color": "#a3557e"},
                {"name": "Patricio Barreiro", "color": "#19335D"},
                {"name": "Mariel Falco", "color": "#665621"},
            ]
        }
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
            debug_print(f"Archivo de configuracion creado: {config_path}")
        except Exception as e:
            debug_print(f"Error al crear archivo de configuracion: {e}")

    def reload_config(self):
        """Recarga la configuracion de usuarios y actualiza los botones"""
        self.users = self.load_users_from_config()
        self.buttons = self.fixed_buttons + self.create_user_buttons()
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
            debug_print(f"Usuario {i}: name='{user_name}', color='{user_color}'")

            # Crear un callback usando una funcion auxiliar para evitar problemas con lambda
            callback = self.create_user_callback(user_name)

            user_button = (
                user_name,
                callback,
                user_color,
            )
            user_buttons.append(user_button)

        debug_print(f"Botones de usuario creados: {len(user_buttons)}")
        return user_buttons

    def create_user_callback(self, user_name):
        """Crea un callback especifico para un usuario"""

        def callback():
            debug_print(f"Boton presionado para usuario: {user_name}")
            self.assign_assignee_for_selected_clip(user_name)

        return callback

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
            shortcut = button_info[3] if len(button_info) > 3 else None
            tooltip = button_info[4] if len(button_info) > 4 else None

            button = QPushButton(name)
            # Aplicar solo el color de fondo, sin negrita ni color de texto blanco
            button.setStyleSheet(f"background-color: {style}")
            button.clicked.connect(handler)

            # Agregar shortcut y tooltip si existen
            if shortcut:
                button.setShortcut(shortcut)
            if tooltip:
                button.setToolTip(tooltip)

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

    def get_assignees_for_selected_clip(self):
        seq = hiero.ui.activeSequence()
        if not seq:
            QMessageBox.warning(self, "No Sequence", "No hay una secuencia activa.")
            return
        te = hiero.ui.getTimelineEditor(seq)
        selected_items = te.selection()
        if not selected_items:
            QMessageBox.warning(
                self, "No Selection", "Selecciona un clip en el timeline."
            )
            return
        for item in selected_items:
            if not isinstance(item, hiero.core.EffectTrackItem):
                if item.source().mediaSource().isMediaPresent():
                    fileinfos = item.source().mediaSource().fileinfos()
                    if not fileinfos:
                        continue
                    file_path = fileinfos[0].filename()
                    exr_name = os.path.basename(file_path)
                    exr_name = exr_name.replace(".%", "_%")
                    try:
                        base_name = self.parse_exr_name(exr_name)
                        self.call_assignee_script(base_name)
                    except Exception as e:
                        QMessageBox.warning(self, "Formato Incorrecto", str(e))
                else:
                    QMessageBox.warning(
                        self, "Media Missing", "El clip no tiene media presente."
                    )

    def call_assignee_script(self, base_name):
        # Importar y ejecutar la funcion del script LGA_NKS_Flow_Assignee.py directamente
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Flow", "LGA_NKS_Flow_Assignee.py"
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
                "LGA_NKS_Flow_Assignee", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_Flow_Assignee.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Llamar a la función principal pasando el base_name
            module.show_task_assignees_from_base_name(base_name)
        except Exception as e:
            QMessageBox.warning(self, "Error al ejecutar", str(e))

    def clear_assignees_for_selected_clip(self):
        seq = hiero.ui.activeSequence()
        if not seq:
            QMessageBox.warning(self, "No Sequence", "No hay una secuencia activa.")
            return
        te = hiero.ui.getTimelineEditor(seq)
        selected_items = te.selection()
        if not selected_items:
            QMessageBox.warning(
                self, "No Selection", "Selecciona un clip en el timeline."
            )
            return
        for item in selected_items:
            if not isinstance(item, hiero.core.EffectTrackItem):
                if item.source().mediaSource().isMediaPresent():
                    fileinfos = item.source().mediaSource().fileinfos()
                    if not fileinfos:
                        continue
                    file_path = fileinfos[0].filename()
                    exr_name = os.path.basename(file_path)
                    exr_name = exr_name.replace(".%", "_%")
                    try:
                        base_name = self.parse_exr_name(exr_name)
                        self.call_clear_assignees_script(base_name)
                    except Exception as e:
                        QMessageBox.warning(self, "Formato Incorrecto", str(e))
                else:
                    QMessageBox.warning(
                        self, "Media Missing", "El clip no tiene media presente."
                    )

    def call_clear_assignees_script(self, base_name):
        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Flow", "LGA_NKS_Flow_Clear_Assignees.py"
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
                "LGA_NKS_Flow_Clear_Assignees", script_path
            )
            if spec is None or spec.loader is None:
                raise ImportError(
                    "No se pudo cargar el módulo LGA_NKS_Flow_Clear_Assignees.py"
                )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            # Llamar a la función principal pasando el base_name
            module.clear_task_assignees_from_base_name(base_name)
        except Exception as e:
            QMessageBox.warning(self, "Error al ejecutar", str(e))

    def assign_assignee_for_selected_clip(self, user_name):
        debug_print(
            f"=== assign_assignee_for_selected_clip llamado con user_name: {user_name} ==="
        )
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("No hay secuencia activa")
            QMessageBox.warning(self, "No Sequence", "No hay una secuencia activa.")
            return
        te = hiero.ui.getTimelineEditor(seq)
        selected_items = te.selection()
        if not selected_items:
            debug_print("No hay items seleccionados")
            QMessageBox.warning(
                self, "No Selection", "Selecciona un clip en el timeline."
            )
            return
        debug_print(f"Procesando {len(selected_items)} items seleccionados")
        for item in selected_items:
            if not isinstance(item, hiero.core.EffectTrackItem):
                if item.source().mediaSource().isMediaPresent():
                    fileinfos = item.source().mediaSource().fileinfos()
                    if not fileinfos:
                        debug_print("No hay fileinfos para este item")
                        continue
                    file_path = fileinfos[0].filename()
                    exr_name = os.path.basename(file_path)
                    exr_name = exr_name.replace(".%", "_%")
                    debug_print(f"Procesando archivo: {exr_name}")
                    try:
                        base_name = self.parse_exr_name(exr_name)
                        debug_print(f"Base name extraido: {base_name}")
                        debug_print(
                            f"Llamando call_assign_assignee_script con user_name: {user_name}"
                        )
                        self.call_assign_assignee_script(base_name, user_name)
                    except Exception as e:
                        debug_print(f"Error parseando nombre: {e}")
                        QMessageBox.warning(self, "Formato Incorrecto", str(e))
                else:
                    debug_print("El clip no tiene media presente")
                    QMessageBox.warning(
                        self, "Media Missing", "El clip no tiene media presente."
                    )

    def call_assign_assignee_script(self, base_name, user_name):
        debug_print(f"=== call_assign_assignee_script llamado ===")
        debug_print(f"base_name: {base_name}")
        debug_print(f"user_name: {user_name}")
        debug_print(f"Tipo de user_name: {type(user_name)}")

        script_path = os.path.join(
            os.path.dirname(__file__), "LGA_NKS_Flow", "LGA_NKS_Flow_Assign_Assignee.py"
        )
        debug_print(f"Script path: {script_path}")

        if not os.path.exists(script_path):
            debug_print("Script no encontrado")
            QMessageBox.warning(
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
            module.assign_assignee_to_task(base_name, user_name)
        except Exception as e:
            debug_print(f"Error ejecutando script: {e}")
            QMessageBox.warning(self, "Error al ejecutar", str(e))

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


# Crear la instancia del panel y agregarlo al windowManager de Hiero
assigneePanel = AssigneePanel()
wm = hiero.ui.windowManager()
wm.addWindow(assigneePanel)
