"""
____________________________________________________________________________________

  LGA_NKS_Flow_Panel v2.45 | Lega Pugliese
  Panel con herramientas que interactuan con las tasks de Flow Production Tracking
  que fueron descargadas previamente con la app LGA_NKS_Flow_Downloader
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
    QSpacerItem,
    QSizePolicy,
    QMessageBox,
)
from PySide2.QtGui import QColor, QKeySequence
from PySide2.QtCore import Qt


# Variable global para activar o desactivar los prints
DEBUG = False


def debug_print(*message):
    if DEBUG:
        print(*message)


# Clase de botón personalizada que maneja el Shift+Click
class CustomButton(QPushButton):
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
            if modifiers & Qt.ShiftModifier:
                self._shift_click_handler()
            else:
                self._custom_click_handler()
        else:
            super(CustomButton, self).mousePressEvent(event)


class ColorChangeWidget(QWidget):
    def __init__(self):
        super(ColorChangeWidget, self).__init__()

        self.setObjectName("com.lega.FPTPanel")
        self.setWindowTitle("Flow")

        self.layout = QGridLayout()  # Usamos QGridLayout
        self.setLayout(self.layout)

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
                "color": QColor(46, 119, 212),
                "style": "#2e77d4",
                "action": "color",
            },
            # {"name": "Corrs_Lega", "color": QColor(105, 19, 94), "style": "#69135e", "action": "color"},
            {
                "name": "Rev_Sup",
                "color": QColor(163, 85, 126),
                "style": "#a3557e",
                "action": "color",
            },
            {
                "name": "Rev_Lega",
                "color": QColor(105, 19, 94),
                "style": "#69135e",
                "action": "color",
            },
            {
                "name": "Rev_Hold",
                "color": QColor(147, 49, 0),
                "style": "#933100",
                "action": "color",
            },
            {
                "name": "Rev_Dir",
                "color": QColor(152, 192, 84),
                "style": "#98c054",
                "action": "color",
            },
            {
                "name": "Approved",
                "color": QColor(36, 76, 25),
                "style": "#244c19",
                "action": "color",
            },
            {
                "name": "Delivery Ok",
                "color": QColor(82, 194, 51),
                "style": "#52C233",
                "action": "color",
            },
            {
                "name": "Rev_Sup_D",
                "color": QColor(82, 61, 128),
                "style": "#523d80",
                "action": "color",
            },
            {
                "name": "Rev_Dir_D",
                "color": QColor(77, 33, 168),
                "style": "#4d21a8",
                "action": "color",
            },
        ]

        self.num_columns = 1  # Inicialmente una columna
        self.create_buttons()

        # Conectar la senal de cambio de tamano del widget al metodo correspondiente
        self.adjust_columns_on_resize()
        self.resizeEvent = self.adjust_columns_on_resize

    def create_buttons(self):
        for index, button_info in enumerate(self.buttons):
            name = button_info["name"]
            color = button_info["color"]
            style = button_info["style"]
            action = button_info["action"]

            # Crear un botón personalizado que maneje el Shift+Click
            button = CustomButton(name)
            button.setStyleSheet(f"background-color: {style}")
            if action == "color":
                button.clicked.connect(self.handle_color_button_click(color, name))
            elif action == "fpt_pull":
                button.setCustomClickHandler(self.run_FPT_pull)
                button.setShiftClickHandler(self.run_FPT_pull_with_deselect)
            elif action == "review_pic":
                button.clicked.connect(self.run_review_pic_script)
            elif action == "shot_info":
                button.clicked.connect(self.run_shot_info_script)
                if "shortcut" in button_info:
                    button.setShortcut(QKeySequence(button_info["shortcut"]))

            row = index // self.num_columns
            column = index % self.num_columns
            self.layout.addWidget(button, row, column)

    def run_FPT_pull_with_deselect(self):
        """Version del FPT Pull que procesa todos los clips"""
        debug_print("Ejecutando Flow Pull forzando procesamiento de todos los clips...")

        # Obtener el proyecto actual
        project = hiero.core.projects()[0] if hiero.core.projects() else None
        if project:
            project.beginUndo("Run External Script")
            try:
                script_path = os.path.join(
                    os.path.dirname(__file__), "LGA_NKS_Flow", "LGA_NKS_Flow_Pull.py"
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
        # Obtener el proyecto actual
        project = hiero.core.projects()[0] if hiero.core.projects() else None
        if project:
            project.beginUndo("Run External Script")
            try:
                # Importar y ejecutar el script de la subcarpeta
                script_path = os.path.join(
                    os.path.dirname(__file__), "LGA_NKS_Flow", "LGA_NKS_Flow_Pull.py"
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
                    "LGA_NKS_Flow",
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
                                "LGA_NKS_Flow",
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
                os.path.dirname(__file__), "LGA_NKS_Flow", "LGA_NKS_ReviewPic.py"
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
        def button_click_handler(_):
            confirmation = self.confirm_status_application(button_name)
            if confirmation:
                self.change_clip_color_and_push_status(color, button_name)
                if button_name in ["Rev_Dir", "Corrections"]:
                    self.run_clear_tag_script()

        return button_click_handler

    def parse_exr_name(self, exr_name):
        # Ajustar el manejo del formato del nombre del archivo EXR
        if "%04d" in exr_name:
            exr_name = exr_name.replace(".%", "_%")  # Reemplazar patron para analisis

        parts = exr_name.split("_")
        if len(parts) < 7 or not parts[-2].startswith("v"):
            raise ValueError(
                f"Nombre del archivo EXR no tiene el formato esperado: {exr_name}"
            )
        base_name = "_".join(
            parts[:-1]
        )  # Todas las partes excepto la ultima forman el base_name
        return base_name

    def push_task_status(self, button_name, base_name, update_callback=None):
        try:
            # Importar y ejecutar el script de push
            script_path = os.path.join(
                os.path.dirname(__file__), "LGA_NKS_Flow", "LGA_NKS_Flow_Push.py"
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
                            button_name, base_name, update_callback
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

    def change_clip_color_and_push_status(self, color, button_name):
        try:
            seq = hiero.ui.activeSequence()
            if seq:
                te = hiero.ui.getTimelineEditor(seq)
                selected_items = te.selection()

                project = hiero.core.projects()[0]
                project.beginUndo("Change Clip Color")

                for item in selected_items:
                    if not isinstance(item, hiero.core.EffectTrackItem):
                        bin_item = item.source().binItem()
                        if item.source().mediaSource().isMediaPresent():
                            active_version = bin_item.activeVersion()
                            file_path = (
                                item.source().mediaSource().fileinfos()[0].filename()
                                if item.source().mediaSource().fileinfos()
                                else None
                            )
                            if (
                                not file_path
                                or "_comp_" not in os.path.basename(file_path).lower()
                            ):
                                continue
                            exr_name = os.path.basename(file_path)
                            exr_name = exr_name.replace(
                                ".%", "_%"
                            )  # Reemplazar patron para analisis
                            try:
                                base_name = self.parse_exr_name(exr_name)
                                debug_print(f"Estado: {button_name}, Shot: {base_name}")

                                # Definir una funcion de callback para actualizar el color
                                def update_clip_color():
                                    if active_version:
                                        bin_item.setColor(color)

                                push_result = self.push_task_status(
                                    button_name, base_name, update_clip_color
                                )
                                if not push_result:
                                    # Operacion cancelada, continuar sin hacer nada
                                    continue
                            except ValueError as e:
                                debug_print(f"Error: {e}")
                project.endUndo()
            else:
                pass
        except Exception as e:
            debug_print(f"Error durante la operacion: {e}")

    def confirm_status_application(self, status):
        seq = hiero.ui.activeSequence()
        if seq:
            te = hiero.ui.getTimelineEditor(seq)
            selected_items = te.selection()
            if len(selected_items) > 4:
                msg = QMessageBox()
                msg.setIcon(QMessageBox.Question)
                msg.setWindowTitle("Confirm Status Application")
                msg.setText(
                    f"Are you sure you want to apply the status '{status}' to {len(selected_items)} clips?"
                )
                msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
                result = msg.exec_()
                return result == QMessageBox.Yes
        return True

    def adjust_columns_on_resize(self, event=None):
        # Obtener el ancho actual del widget
        panel_width = self.width()
        button_width = 100  # Ancho aproximado de cada boton
        min_button_spacing = 10  # Espacio minimo entre botones

        # Calcular el numero de columnas en funcion del ancho del widget
        self.num_columns = max(
            1, (panel_width + min_button_spacing) // (button_width + min_button_spacing)
        )

        # Limpiar el layout actual y eliminar widgets solo si existen
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Volver a crear los botones con el nuevo numero de columnas
        self.create_buttons()

        # Calcular el numero de filas usadas
        num_rows = (len(self.buttons) + self.num_columns - 1) // self.num_columns

        # Anadir el espaciador vertical
        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        self.layout.addItem(spacer, num_rows, 0, 1, self.num_columns)


# Crear la instancia del widget y anadirlo al gestor de ventanas de Hiero
colorChanger = ColorChangeWidget()
wm = hiero.ui.windowManager()
wm.addWindow(colorChanger)
