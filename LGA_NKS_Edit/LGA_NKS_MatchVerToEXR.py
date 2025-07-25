"""
_______________________________________________________________________________________

  LGA_NKS_MatchVerToEXR v0.4 | Lega
  Busca la version actual de todos los clips del track llamado EXR e
  intenta subir la versión de todos los clips del track llamado REV a la misma versión.
_______________________________________________________________________________________

"""

import os
import re
import hiero.core
import hiero.ui
from PySide2.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QHBoxLayout,
)
from PySide2.QtWidgets import QStyledItemDelegate, QStyle
from PySide2.QtGui import QColor, QBrush, QFont, QPalette
from PySide2.QtCore import Qt
import sys

# Variable global para activar o desactivar los prints
DEBUG = True

# Variables globales para mantener la ventana en memoria - COPIADO DEL PULL
app = None
window = None


def debug_print(*message):
    if DEBUG:
        print(*message)


def extract_version_number(version_str):
    """Extrae el numero de version numerico de un string de version."""
    match = re.search(r"_v(\d+)(?:[-\(][^)]+)?", version_str)
    if match:
        try:
            version_num = int(match.group(1))
            return version_num
        except ValueError:
            pass
    return 0


class VersionMatcherGUI(QWidget):
    def __init__(self, parent=None):
        super(VersionMatcherGUI, self).__init__(parent)
        self.row_background_colors = []  # COPIADO DEL PULL para el delegado
        self.hiero_ops = None
        self.initUI()

    def set_hiero_ops(self, hiero_ops):
        """COPIADO DEL PULL - Asignar instancia de HieroOperations"""
        self.hiero_ops = hiero_ops
        self.update_table()

    def update_table(self):
        """COPIADO DEL PULL - Actualizar tabla y mostrar si hay cambios"""
        if self.hiero_ops:
            changes_exist = self.hiero_ops.process_tracks(self.table, self)
            if changes_exist:
                self.adjust_window_size()  # COPIADO DEL PULL
                self.show()
            else:
                QMessageBox.information(
                    self,
                    "No Changes",
                    "No se encontraron clips EXR con correspondientes clips REV.",
                )

    def add_color_to_background_list(self, row_colors):
        """COPIADO DEL PULL - Agrega una lista de colores de fondo para una nueva fila."""
        self.row_background_colors.append(row_colors)

    def initUI(self):
        self.setWindowTitle("EXR to REV Version Matcher - Results")
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(
            ["Shot", "EXR Version", "REV Was", "Status"]
        )

        # COPIADO DEL PULL - Configuracion de tabla
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setFocusPolicy(Qt.NoFocus)
        self.table.setStyleSheet(
            """
            QTableView::item:selected {
                color: black;
                background-color: transparent;
            }
        """
        )

        # COPIADO DEL PULL - Asignar delegado personalizado
        delegate = ColorMixDelegate(self.table, self.row_background_colors)
        self.table.setItemDelegate(delegate)

        layout.addWidget(self.table)
        self.setLayout(layout)

        # COPIADO DEL PULL - Estilo para headers
        font = QFont()
        font.setBold(True)
        self.table.horizontalHeader().setFont(font)

    def add_result(self, shot_base, exr_version, rev_was_version, status):
        """Anadir una fila a la tabla con el resultado."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Agregar items a la tabla
        shot_item = QTableWidgetItem(shot_base + "   ")  # COPIADO DEL PULL - espacios
        exr_item = QTableWidgetItem(f"v{exr_version:02d}")
        rev_item = QTableWidgetItem(f"v{rev_was_version:02d}")
        status_item = QTableWidgetItem(status)

        # COPIADO DEL PULL - Centrado
        exr_item.setTextAlignment(Qt.AlignCenter)
        rev_item.setTextAlignment(Qt.AlignCenter)

        # Colorear segun el estado
        if status == "Updated":
            status_color = "#7d4cff"  # Morado
        elif status == "Version Not Available":
            status_color = "#933100"  # Rojo oscuro
        elif status == "Already Matched":
            status_color = "#244c19"  # Verde oscuro
        else:
            status_color = "#8a8a8a"  # Gris por defecto

        # COPIADO DEL PULL - Configuracion de colores
        status_bg_color = QColor(status_color)
        status_text_color = self.color_for_background(status_color)
        status_item.setBackground(QBrush(status_bg_color))
        status_item.setForeground(QBrush(QColor(status_text_color)))
        status_item.setTextAlignment(Qt.AlignCenter)

        # Agregar items
        self.table.setItem(row, 0, shot_item)
        self.table.setItem(row, 1, exr_item)
        self.table.setItem(row, 2, rev_item)
        self.table.setItem(row, 3, status_item)

        # COPIADO DEL PULL - Configuracion de colores para delegado
        row_colors = ["#8a8a8a"] * 4  # Color por defecto
        row_colors[3] = status_color  # Color para la columna de status
        self.add_color_to_background_list(row_colors)

        self.table.resizeColumnsToContents()

    def luminance(self, color):
        """COPIADO DEL PULL - Calcula la luminancia de un color para determinar si es claro u oscuro."""
        red = color.red()
        green = color.green()
        blue = color.blue()
        return 0.299 * red + 0.587 * green + 0.114 * blue

    def color_for_background(self, hex_color):
        """COPIADO DEL PULL - Determina el color del texto basado en el color de fondo."""
        color = QColor(hex_color)
        return "#ffffff" if self.luminance(color) < 128 else "#000000"

    def adjust_window_size(self):
        """COPIADO EXACTO DEL PULL - Ajustes para cambiar el tamano y posicion de la ventana"""
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.resizeColumnsToContents()
        width = self.table.verticalHeader().width() - 30
        for i in range(self.table.columnCount()):
            width += self.table.columnWidth(i) + 20
        screen = QApplication.primaryScreen()
        screen_rect = screen.availableGeometry()
        max_width = screen_rect.width() * 0.8
        final_width = min(width, max_width)
        height = self.table.horizontalHeader().height() + 20
        for i in range(self.table.rowCount()):
            height += self.table.rowHeight(i) + 4
        max_height = screen_rect.height() * 0.8
        final_height = min(height, max_height)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.resize(final_width, final_height)
        self.move(
            (screen_rect.width() - final_width) // 2,
            (screen_rect.height() - final_height) // 2,
        )

    def keyPressEvent(self, event):
        """COPIADO DEL PULL - Cerrar la ventana con ESC."""
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super(VersionMatcherGUI, self).keyPressEvent(event)


class ColorMixDelegate(QStyledItemDelegate):
    """COPIADO EXACTO DEL PULL - Delegado para mezclar colores en selecciones"""

    def __init__(
        self, table_widget, background_colors, mix_color=(88, 88, 88), parent=None
    ):
        super(ColorMixDelegate, self).__init__(parent)
        self.table_widget = table_widget
        self.background_colors = background_colors
        self.mix_color = mix_color

    def paint(self, painter, option, index):
        row = index.row()
        column = index.column()
        if option.state & QStyle.State_Selected:
            original_color = QColor(self.background_colors[row][column])
            mixed_color = self.mix_colors(
                (original_color.red(), original_color.green(), original_color.blue()),
                self.mix_color,
            )
            option.palette.setColor(QPalette.Highlight, QColor(*mixed_color))
        else:
            original_color = QColor(self.background_colors[row][column])
            option.palette.setColor(QPalette.Base, original_color)
        super(ColorMixDelegate, self).paint(painter, option, index)

    def mix_colors(self, original_color, mix_color):
        r1, g1, b1 = original_color
        r2, g2, b2 = mix_color
        return ((r1 + r2) // 2, (g1 + g2) // 2, (b1 + b2) // 2)


class HieroOperations:
    """Clase para manejar operaciones en Hiero - COPIADA de LGA_NKS_Flow_Pull.py"""

    def __init__(self, gui_table):
        self.gui_table = gui_table  # COPIADO DEL PULL - referencia a GUI_Table
        self.force_all_clips = (
            False  # Parametro para forzar procesamiento de todos los clips
        )

    def parse_exr_name(self, file_name):
        """Extrae el nombre base del archivo y el numero de version con prefijo - COPIADO del Pull"""
        # Remover extension y secuencia numerica para archivos EXR
        base_name = re.sub(r"_%04d\.exr$", "", file_name)
        # Si no cambio, puede ser un archivo de video (mxf, mov, etc)
        if base_name == file_name:
            # Remover extension para archivos de video
            base_name = re.sub(r"\.[^.]+$", "", file_name)

        version_match = re.search(r"(_v\d+)", base_name)
        version_str = version_match.group(1) if version_match else "_vUnknown"

        return base_name, version_str

    def get_highest_version(self, binItem):
        """Obtiene la version mas alta de un binItem - COPIADO EXACTO del Pull"""
        versions = binItem.items()
        try:
            highest_version = max(
                versions, key=lambda v: extract_version_number(v.name())
            )
            return highest_version
        except Exception as e:
            debug_print(f"Error al obtener la version mas alta: {e}")
            return None

    def change_to_highest_version(self, clip):
        """Cambia el clip a la version mas alta disponible - COPIADO EXACTO del Pull"""
        binItem = clip.source().binItem()
        activeVersion = binItem.activeVersion()
        vc = hiero.core.VersionScanner()
        vc.doScan(activeVersion)
        highest_version = self.get_highest_version(binItem)
        if highest_version:
            binItem.setActiveVersion(highest_version)
        return highest_version

    def add_custom_tag_to_clip(self, clip, tag_name, tag_description, tag_icon):
        """Anade un tag personalizado a un clip - COPIADO del Pull"""
        new_tag = hiero.core.Tag(tag_name)
        new_tag.setIcon(tag_icon)
        safe_description = str(tag_description) if tag_description is not None else "-"
        new_tag.setNote(safe_description)
        clip.addTag(new_tag)

    def delete_version_mismatch_tags(self, clip):
        """Elimina tags de Version Mismatch de un clip"""
        tags = clip.tags()
        if tags:
            for tag in list(
                tags
            ):  # Usar list() para evitar modificar durante iteración
                if tag.name() == "Version Mismatch":
                    clip.removeTag(tag)
                    debug_print(f"→ Eliminado tag 'Version Mismatch' del clip")

    def process_tracks(self, table, gui_table):
        """MODIFICADO - Procesar clips de tracks EXR y REV devolviendo si hay cambios"""
        seq = hiero.ui.activeSequence()
        if not seq:
            QMessageBox.warning(None, "Error", "No hay secuencia activa en Hiero.")
            return False

        te = hiero.ui.getTimelineEditor(seq)
        selected_clips = te.selection()

        # Encontrar tracks EXR y REV
        exr_track = None
        rev_track = None

        for track in seq.videoTracks():
            if track.name().upper() == "EXR":
                exr_track = track
            elif track.name().upper() == "REV":
                rev_track = track

        if not exr_track:
            QMessageBox.warning(None, "Error", "No se encontró el track EXR.")
            return False

        if not rev_track:
            QMessageBox.warning(None, "Error", "No se encontró el track REV.")
            return False

        # Obtener clips a procesar - MODIFICADO para force_all_clips
        if self.force_all_clips or not selected_clips:
            # Procesar todos los clips del track EXR
            exr_clips = exr_track.items()
            debug_print(
                f">>> Procesando todos los {len(exr_clips)} clips del track EXR"
                + (" (forzado por shift+click)" if self.force_all_clips else "")
            )
        else:
            # Solo procesar clips seleccionados que estén en el track EXR
            exr_clips = [
                clip for clip in selected_clips if clip.parentTrack() == exr_track
            ]
            debug_print(f">>> Procesando {len(exr_clips)} clips EXR seleccionados")

        # Crear diccionario de clips REV por base name
        rev_clips_dict = {}
        for clip in rev_track.items():
            if isinstance(clip, hiero.core.EffectTrackItem):
                continue

            file_path = self.get_file_path(clip)
            if not file_path:
                continue

            base_name, version_str = self.parse_exr_name(os.path.basename(file_path))
            base_without_version = base_name.replace(version_str, "")

            if base_without_version not in rev_clips_dict:
                rev_clips_dict[base_without_version] = clip

        # Variable para saber si se encontraron resultados
        results_found = False

        # Procesar clips EXR - USANDO MISMA LOGICA QUE EL PULL
        for exr_clip in exr_clips:
            if isinstance(exr_clip, hiero.core.EffectTrackItem):
                continue

            file_path = self.get_file_path(exr_clip)
            if not file_path:
                continue

            # Solo procesar archivos que contengan "_comp_"
            if "_comp_" not in os.path.basename(file_path).lower():
                continue

            base_name, version_str = self.parse_exr_name(os.path.basename(file_path))
            exr_version = extract_version_number(version_str)
            base_without_version = base_name.replace(version_str, "")

            debug_print(f"\n=== PROCESANDO SHOT: {base_without_version} ===")
            debug_print(
                f"- Version actual del {base_without_version} del track EXR: v{exr_version:02d}"
            )

            # Buscar clip correspondiente en REV
            if base_without_version in rev_clips_dict:
                rev_clip = rev_clips_dict[base_without_version]

                rev_file_path = self.get_file_path(rev_clip)
                if not rev_file_path:
                    continue

                rev_base_name, rev_version_str = self.parse_exr_name(
                    os.path.basename(rev_file_path)
                )
                rev_current_version = extract_version_number(rev_version_str)

                debug_print(
                    f"- Version actual del {base_without_version} del track REV: v{rev_current_version:02d}"
                )

                # Mostrar versiones disponibles
                binItem = rev_clip.source().binItem()
                versions = binItem.items()
                available_versions = [
                    extract_version_number(v.name()) for v in versions
                ]
                available_versions_str = ", ".join(
                    [f"v{v:02d}" for v in sorted(available_versions)]
                )
                debug_print(
                    f"- Versiones existentes para el REV: {available_versions_str}"
                )

                # LOGICA PRINCIPAL - IGUAL QUE EL PULL
                if rev_current_version == exr_version:
                    debug_print(f"✓ Ya coinciden las versiones v{exr_version:02d}")
                    # Limpiar cualquier tag de Version Mismatch existente
                    self.delete_version_mismatch_tags(rev_clip)
                    gui_table.add_result(
                        base_without_version,
                        exr_version,
                        rev_current_version,
                        "Already Matched",
                    )
                    results_found = True
                else:
                    debug_print(
                        f"! Necesita cambiar de v{rev_current_version:02d} a v{exr_version:02d}"
                    )

                    # USAR MISMA LOGICA QUE EL PULL - cambiar a highest y verificar
                    original_version = rev_current_version
                    highest_version = self.change_to_highest_version(rev_clip)

                    if highest_version:
                        new_version_number = extract_version_number(
                            highest_version.name()
                        )
                        debug_print(
                            f"→ Subido a version mas alta disponible: v{new_version_number:02d}"
                        )

                        # Verificar si la nueva version coincide con la del EXR
                        if new_version_number == exr_version:
                            debug_print(
                                f"✓ EXITO: Actualizado de v{original_version:02d} a v{exr_version:02d}"
                            )
                            # Limpiar cualquier tag de Version Mismatch existente
                            self.delete_version_mismatch_tags(rev_clip)
                            gui_table.add_result(
                                base_without_version,
                                exr_version,
                                original_version,
                                "Updated",
                            )
                        else:
                            debug_print(
                                f"✗ Version v{exr_version:02d} no disponible, quedó en v{new_version_number:02d}"
                            )
                            # Agregar tag rojo como en el Pull
                            self.add_custom_tag_to_clip(
                                rev_clip,
                                "Version Mismatch",
                                f"EXR requires v{exr_version:02d}",
                                "icons:TagRed.png",
                            )
                            debug_print(
                                f"→ Agregado tag rojo 'Version Mismatch' al clip REV"
                            )
                            gui_table.add_result(
                                base_without_version,
                                exr_version,
                                original_version,
                                "Version Not Available",
                            )

                        results_found = True
                    else:
                        debug_print(f"✗ No se pudo cambiar la version")
            else:
                debug_print(
                    f"- No se encontro clip REV correspondiente para: {base_without_version}"
                )

        return results_found

    def get_file_path(self, clip):
        """Obtener la ruta del archivo de un clip."""
        try:
            file_path = clip.source().mediaSource().fileinfos()[0].filename()
            return file_path
        except:
            return None


def match_exr_to_rev(force_all_clips=False):
    """MODIFICADO - Funcion principal siguiendo el patron del Pull"""
    global app, window  # COPIADO DEL PULL - usar variables globales

    app = QApplication.instance() if QApplication.instance() else QApplication(sys.argv)
    window = VersionMatcherGUI()
    hiero_ops = HieroOperations(window)
    hiero_ops.force_all_clips = force_all_clips  # Pasar el parametro al HieroOperations
    window.set_hiero_ops(hiero_ops)  # COPIADO DEL PULL - usar set_hiero_ops


# Para testing
if __name__ == "__main__":
    match_exr_to_rev()
