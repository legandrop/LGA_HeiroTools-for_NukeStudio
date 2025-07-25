"""
_______________________________________________________________________________________

  LGA_NKS_CompareVerToEditref v1.0 | Lega
  Compara los rangos de frames de todos los clips del track REV con
  los clips correspondientes del track EditRef para verificar coincidencias.
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


class FrameRangeComparisonGUI(QWidget):
    def __init__(self, parent=None):
        super(FrameRangeComparisonGUI, self).__init__(parent)
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
                    "No se encontraron clips REV con correspondientes clips EditRef.",
                )

    def add_color_to_background_list(self, row_colors):
        """COPIADO DEL PULL - Agrega una lista de colores de fondo para una nueva fila."""
        self.row_background_colors.append(row_colors)

    def initUI(self):
        self.setWindowTitle("REV to EditRef Frame Range Comparison - Results")
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 5, self)
        self.table.setHorizontalHeaderLabels(
            ["Shot", "REV Range", "EditRef Range", "Timeline Range", "Status"]
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

    def add_result(self, shot_base, rev_range, editref_range, timeline_range, status):
        """Anadir una fila a la tabla con el resultado."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Agregar items a la tabla
        shot_item = QTableWidgetItem(shot_base + "   ")  # COPIADO DEL PULL - espacios
        rev_item = QTableWidgetItem(rev_range)
        editref_item = QTableWidgetItem(editref_range)
        timeline_item = QTableWidgetItem(timeline_range)
        status_item = QTableWidgetItem(status)

        # COPIADO DEL PULL - Centrado
        rev_item.setTextAlignment(Qt.AlignCenter)
        editref_item.setTextAlignment(Qt.AlignCenter)
        timeline_item.setTextAlignment(Qt.AlignCenter)

        # Colorear segun el estado
        if status == "Match":
            status_color = "#244c19"  # Verde oscuro
        elif status == "Range Mismatch":
            status_color = "#933100"  # Rojo oscuro
        elif status == "No EditRef Found":
            status_color = "#8a4500"  # Naranja oscuro
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
        self.table.setItem(row, 1, rev_item)
        self.table.setItem(row, 2, editref_item)
        self.table.setItem(row, 3, timeline_item)
        self.table.setItem(row, 4, status_item)

        # COPIADO DEL PULL - Configuracion de colores para delegado
        row_colors = ["#8a8a8a"] * 5  # Color por defecto
        row_colors[4] = status_color  # Color para la columna de status
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
            super(FrameRangeComparisonGUI, self).keyPressEvent(event)


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

    def parse_clip_name(self, file_name):
        """Extrae el nombre base usando los primeros 4 bloques separados por guiones bajos"""
        # Remover extension y secuencia numerica para archivos EXR
        base_name = re.sub(r"_%04d\.exr$", "", file_name)
        # Si no cambio, puede ser un archivo de video (mxf, mov, etc)
        if base_name == file_name:
            # Remover extension para archivos de video
            base_name = re.sub(r"\.[^.]+$", "", file_name)

        # Extraer los primeros 4 bloques separados por guiones bajos
        parts = base_name.split("_")
        if len(parts) >= 4:
            base_identifier = "_".join(parts[:4])
        else:
            base_identifier = base_name

        version_match = re.search(r"(_v\d+)", base_name)
        version_str = version_match.group(1) if version_match else "_vUnknown"

        return base_identifier, version_str

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
        """MODIFICADO - Procesar clip del track REV basado en posicion del playhead"""
        seq = hiero.ui.activeSequence()
        if not seq:
            QMessageBox.warning(None, "Error", "No hay secuencia activa en Hiero.")
            return False

        viewer = hiero.ui.currentViewer()
        if not viewer:
            QMessageBox.warning(None, "Error", "No se encontró un visor activo.")
            return False

        current_time = viewer.time()
        debug_print(f"Tiempo actual del playhead: {current_time}")

        # Encontrar tracks REV y EditRef
        rev_track = None
        editref_track = None

        for track in seq.videoTracks():
            if track.name().upper() == "REV":
                rev_track = track
            elif track.name().upper() == "EDITREF":
                editref_track = track

        if not rev_track:
            QMessageBox.warning(None, "Error", "No se encontró el track REV.")
            return False

        if not editref_track:
            QMessageBox.warning(None, "Error", "No se encontró el track EditRef.")
            return False

        # Obtener clips a procesar - basado en force_all_clips o playhead
        if self.force_all_clips:
            # Procesar todos los clips del track REV
            rev_clips = rev_track.items()
            debug_print(
                f">>> Procesando todos los {len(rev_clips)} clips del track REV (forzado por shift+click)"
            )
        else:
            # Buscar clip en track REV en la posicion del playhead
            rev_clip_at_playhead = None
            for clip in rev_track:
                if clip.timelineIn() <= current_time < clip.timelineOut():
                    rev_clip_at_playhead = clip
                    break

            if not rev_clip_at_playhead:
                QMessageBox.warning(
                    None,
                    "Error",
                    "No se encontró un clip en el track REV en la posición actual del playhead.",
                )
                return False

            # Procesar solo el clip encontrado en el playhead
            rev_clips = [rev_clip_at_playhead]
            debug_print(
                f">>> Procesando clip REV en posicion del playhead: {current_time}"
            )

        # Crear diccionario de clips EditRef por base name
        editref_clips_dict = {}
        for clip in editref_track.items():
            if isinstance(clip, hiero.core.EffectTrackItem):
                continue

            file_path = self.get_file_path(clip)
            if not file_path:
                continue

            base_identifier, version_str = self.parse_clip_name(
                os.path.basename(file_path)
            )

            if base_identifier not in editref_clips_dict:
                editref_clips_dict[base_identifier] = clip

        # Variable para saber si se encontraron resultados
        results_found = False

        # Procesar clips REV - COMPARANDO CON EditRef
        for rev_clip in rev_clips:
            if isinstance(rev_clip, hiero.core.EffectTrackItem):
                continue

            file_path = self.get_file_path(rev_clip)
            if not file_path:
                continue

            base_identifier, version_str = self.parse_clip_name(
                os.path.basename(file_path)
            )

            debug_print(f"\n=== PROCESANDO SHOT: {base_identifier} ===")

            # Obtener rangos del clip REV
            rev_fileinfos = rev_clip.source().mediaSource().fileinfos()
            if not rev_fileinfos:
                debug_print("⚠️ No se encontraron fileinfos para el clip REV.")
                continue

            rev_start_frame = rev_fileinfos[0].startFrame()
            rev_end_frame = rev_fileinfos[0].endFrame()
            rev_range = f"{rev_start_frame}-{rev_end_frame}"

            # Obtener posición en timeline del clip REV
            rev_timeline_in = rev_clip.timelineIn()
            rev_timeline_out = rev_clip.timelineOut()
            timeline_range = f"{rev_timeline_in}-{rev_timeline_out}"

            debug_print(f"- Rango de frames del REV: {rev_range}")
            debug_print(f"- Posición en timeline del REV: {timeline_range}")

            # Buscar clip correspondiente en EditRef
            if base_identifier in editref_clips_dict:
                editref_clip = editref_clips_dict[base_identifier]

                editref_fileinfos = editref_clip.source().mediaSource().fileinfos()
                if not editref_fileinfos:
                    debug_print("⚠️ No se encontraron fileinfos para el clip EditRef.")
                    continue

                editref_start_frame = editref_fileinfos[0].startFrame()
                editref_end_frame = editref_fileinfos[0].endFrame()
                editref_range = f"{editref_start_frame}-{editref_end_frame}"

                debug_print(f"- Rango de frames del EditRef: {editref_range}")

                # Comparar rangos
                if (
                    rev_start_frame == editref_start_frame
                    and rev_end_frame == editref_end_frame
                ):
                    debug_print(f"✓ Los rangos coinciden: {rev_range}")
                    gui_table.add_result(
                        base_identifier,
                        rev_range,
                        editref_range,
                        timeline_range,
                        "Match",
                    )
                    results_found = True
                else:
                    debug_print(
                        f"✗ Los rangos NO coinciden: REV({rev_range}) vs EditRef({editref_range})"
                    )
                    gui_table.add_result(
                        base_identifier,
                        rev_range,
                        editref_range,
                        timeline_range,
                        "Range Mismatch",
                    )
                    results_found = True
            else:
                debug_print(
                    f"- No se encontró clip EditRef correspondiente para: {base_identifier}"
                )
                gui_table.add_result(
                    base_identifier,
                    rev_range,
                    "N/A",
                    timeline_range,
                    "No EditRef Found",
                )
                results_found = True

        return results_found

    def get_file_path(self, clip):
        """Obtener la ruta del archivo de un clip."""
        try:
            file_path = clip.source().mediaSource().fileinfos()[0].filename()
            return file_path
        except:
            return None


def compare_rev_to_editref(force_all_clips=False):
    """MODIFICADO - Funcion principal para comparar rangos entre REV y EditRef basado en playhead"""
    global app, window  # COPIADO DEL PULL - usar variables globales

    app = QApplication.instance() if QApplication.instance() else QApplication(sys.argv)
    window = FrameRangeComparisonGUI()
    hiero_ops = HieroOperations(window)
    hiero_ops.force_all_clips = force_all_clips  # Pasar el parametro al HieroOperations
    window.set_hiero_ops(hiero_ops)  # COPIADO DEL PULL - usar set_hiero_ops


# Para testing
if __name__ == "__main__":
    compare_rev_to_editref()
