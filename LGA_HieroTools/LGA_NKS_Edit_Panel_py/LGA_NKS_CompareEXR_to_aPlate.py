"""
____________________________________________________________________

  LGA_NKS_CompareEXR_to_aPlate v1.15 | Lega

  Compara los rangos de frames de los clips del track especificado (por defecto _comp_) con
  los clips correspondientes del track aPlate para verificar coincidencias.

  v1.15: Ramas de version. get_highest_version + change_to_highest_version (copia
         del Pull, sin uso actual) se reemplazan por change_to_branch_head, que
         usa LGA_NKS_ClipVersions y no cruza de rama.
  v1.14: Actualizado para ser compatible con ambos sistemas de nomenclatura:
         - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
         - PROYECTO_SEQ_SHOT (3 bloques simplificado)
  v1.13: Usa el módulo utilitario LGA_NKS_GetClip para obtener clips (permite selecciones múltiples)
         Prioridad: selecciones múltiples > force_all_clips > playhead
____________________________________________________________________

"""

import os
import re
from pathlib import Path
import hiero.core
import hiero.ui
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore
import sys

# Variable global para activar o desactivar los prints
DEBUG = False

# Flag para controlar si se analiza y muestra TC IN en la comparacion
AnalizeTC = True

# Variables globales para mantener la ventana en memoria - COPIADO DEL PULL
app = None
window = None


def debug_print(*message):
    if DEBUG:
        print(*message)


# Importar utilidades para obtener clips
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    # Cambio de version acotado a la rama del clip (ver LGA_NKS_ClipVersions).
    from LGA_NKS_ClipVersions import switch_clip_to_version

    from LGA_NKS_Shared.LGA_NKS_GetClip import get_clips_to_process

    # Sincronizar el debug con el módulo utilitario
    from LGA_NKS_Shared import LGA_NKS_GetClip as clip_utils

    clip_utils.DEBUG = DEBUG
else:
    debug_print("ERROR: No se encontró el módulo LGA_NKS_GetClip")

# Importar utilidades para naming (compatibilidad con ambos formatos)
naming_utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if naming_utils_path.exists():
    sys.path.insert(0, str(naming_utils_path))
    try:
        from LGA_NKS_Flow_NamingUtils import (
            extract_shot_code,
            clean_base_name,
        )
    except ImportError:
        debug_print("ERROR: No se encontró el módulo LGA_NKS_Flow_NamingUtils")
        extract_shot_code = None
        clean_base_name = None
else:
    debug_print("ERROR: No se encontró el directorio LGA_NKS_Shared")
    extract_shot_code = None
    clean_base_name = None


def tc_str_to_frames(tc_str, fps):
    """Convierte string de timecode a frames totales"""
    h, m, s, f = map(int, tc_str.split(":"))
    return int(((h * 3600 + m * 60 + s) * fps) + f)


def frame_to_tc(frame, fps):
    """Convierte frames totales a string de timecode"""
    frame = int(frame)
    fps = int(fps)
    h = frame // (3600 * fps)
    m = (frame // (60 * fps)) % 60
    s = (frame // fps) % 60
    f = frame % fps
    return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"


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


class FrameRangeComparisonGUI(QtWidgets.QWidget):
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
                # Obtener nombre del track dinámicamente
                track_name = (
                    self.hiero_ops.track_name if self.hiero_ops.track_name else "_comp_"
                )
                QtWidgets.QMessageBox.information(
                    self,
                    "No Changes",
                    f"No se encontraron clips '{track_name}' con correspondientes clips aPlate.",
                )

    def add_color_to_background_list(self, row_colors):
        """COPIADO DEL PULL - Agrega una lista de colores de fondo para una nueva fila."""
        self.row_background_colors.append(row_colors)

    def initUI(self):
        self.setWindowTitle("EXR to aPlate Frame Range Comparison - Results")
        layout = QtWidgets.QVBoxLayout(self)

        # Ajustar columnas segun la flag AnalizeTC
        if AnalizeTC:
            self.table = QtWidgets.QTableWidget(0, 8, self)
            self.table.setHorizontalHeaderLabels(
                [
                    "Shot",
                    "EXR Range",
                    "aPlate Range",
                    "EXR TC IN",
                    "aPlate TC IN",
                    "EXR FPS",
                    "aPlate FPS",
                    "Status",
                ]
            )
        else:
            self.table = QtWidgets.QTableWidget(0, 6, self)
            self.table.setHorizontalHeaderLabels(
                [
                    "Shot",
                    "EXR Range",
                    "aPlate Range",
                    "EXR FPS",
                    "aPlate FPS",
                    "Status",
                ]
            )

        # COPIADO DEL PULL - Configuracion de tabla
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.table.setSelectionMode(QtWidgets.QTableWidget.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setFocusPolicy(QtCore.Qt.NoFocus)
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
        font = QtGui.QFont()
        font.setBold(True)
        self.table.horizontalHeader().setFont(font)

    def add_result(
        self,
        shot_base,
        exr_range,
        aplate_range,
        exr_tc_in,
        aplate_tc_in,
        exr_fps,
        aplate_fps,
        status,
    ):
        """Anadir una fila a la tabla con el resultado."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Agregar items a la tabla
        shot_item = QtWidgets.QTableWidgetItem(shot_base + "   ")  # COPIADO DEL PULL - espacios
        exr_item = QtWidgets.QTableWidgetItem(exr_range)
        aplate_item = QtWidgets.QTableWidgetItem(aplate_range)
        exr_fps_item = QtWidgets.QTableWidgetItem(exr_fps)
        aplate_fps_item = QtWidgets.QTableWidgetItem(aplate_fps)
        status_item = QtWidgets.QTableWidgetItem(status)

        # Items de TC solo si AnalizeTC esta activado
        if AnalizeTC:
            exr_tc_item = QtWidgets.QTableWidgetItem(exr_tc_in)
            aplate_tc_item = QtWidgets.QTableWidgetItem(aplate_tc_in)

        # COPIADO DEL PULL - Centrado
        exr_item.setTextAlignment(QtCore.Qt.AlignCenter)
        aplate_item.setTextAlignment(QtCore.Qt.AlignCenter)
        exr_fps_item.setTextAlignment(QtCore.Qt.AlignCenter)
        aplate_fps_item.setTextAlignment(QtCore.Qt.AlignCenter)

        if AnalizeTC:
            exr_tc_item.setTextAlignment(QtCore.Qt.AlignCenter)
            aplate_tc_item.setTextAlignment(QtCore.Qt.AlignCenter)

        # Colorear segun el estado
        if status == "Match":
            status_color = "#244c19"  # Verde oscuro
        elif status == "Range Mismatch":
            status_color = "#933100"  # Rojo oscuro
        elif status == "TC Mismatch":
            status_color = "#8a4500"  # Naranja oscuro
        elif status == "FPS Mismatch":
            status_color = "#663399"  # Purpura oscuro
        elif status == "Multiple Mismatches":
            status_color = "#660000"  # Rojo muy oscuro
        elif status == "No aPlate Found":
            status_color = "#8a4500"  # Naranja oscuro
        else:
            status_color = "#8a8a8a"  # Gris por defecto

        # COPIADO DEL PULL - Configuracion de colores
        status_bg_color = QtGui.QColor(status_color)
        status_text_color = self.color_for_background(status_color)
        status_item.setBackground(QtGui.QBrush(status_bg_color))
        status_item.setForeground(QtGui.QBrush(QtGui.QColor(status_text_color)))
        status_item.setTextAlignment(QtCore.Qt.AlignCenter)

        # Agregar items segun la flag AnalizeTC
        if AnalizeTC:
            # Modo con TC IN (8 columnas)
            self.table.setItem(row, 0, shot_item)
            self.table.setItem(row, 1, exr_item)
            self.table.setItem(row, 2, aplate_item)
            self.table.setItem(row, 3, exr_tc_item)
            self.table.setItem(row, 4, aplate_tc_item)
            self.table.setItem(row, 5, exr_fps_item)
            self.table.setItem(row, 6, aplate_fps_item)
            self.table.setItem(row, 7, status_item)

            # COPIADO DEL PULL - Configuracion de colores para delegado
            row_colors = ["#8a8a8a"] * 8  # Color por defecto para 8 columnas
            row_colors[7] = status_color  # Color para la columna de status
        else:
            # Modo sin TC IN (5 columnas)
            self.table.setItem(row, 0, shot_item)
            self.table.setItem(row, 1, exr_item)
            self.table.setItem(row, 2, aplate_item)
            self.table.setItem(row, 3, exr_fps_item)
            self.table.setItem(row, 4, aplate_fps_item)
            self.table.setItem(row, 5, status_item)

            # COPIADO DEL PULL - Configuracion de colores para delegado
            row_colors = ["#8a8a8a"] * 6  # Color por defecto para 6 columnas
            row_colors[5] = status_color  # Color para la columna de status

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
        color = QtGui.QColor(hex_color)
        return "#ffffff" if self.luminance(color) < 128 else "#000000"

    def adjust_window_size(self):
        """COPIADO EXACTO DEL PULL - Ajustes para cambiar el tamano y posicion de la ventana"""
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.resizeColumnsToContents()
        width = self.table.verticalHeader().width() - 30
        for i in range(self.table.columnCount()):
            width += self.table.columnWidth(i) + 20
        screen = QtWidgets.QApplication.primaryScreen()
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
        if event.key() == QtCore.Qt.Key_Escape:
            self.close()
        else:
            super(FrameRangeComparisonGUI, self).keyPressEvent(event)


class ColorMixDelegate(QtWidgets.QStyledItemDelegate):
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
        if option.state & QtWidgets.QStyle.State_Selected:
            original_color = QtGui.QColor(self.background_colors[row][column])
            mixed_color = self.mix_colors(
                (original_color.red(), original_color.green(), original_color.blue()),
                self.mix_color,
            )
            option.palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(*mixed_color))
        else:
            original_color = QtGui.QColor(self.background_colors[row][column])
            option.palette.setColor(QtGui.QPalette.Base, original_color)
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
        self.track_name = (
            None  # Nombre del track principal (se establece en process_tracks)
        )

    def parse_clip_name(self, file_name):
        """Extrae el nombre base usando funciones centralizadas (compatible con ambos formatos)"""
        # Usar función centralizada para limpiar el nombre
        if clean_base_name:
            base_name = clean_base_name(file_name)
        else:
            # Fallback si no está disponible el módulo
            base_name = re.sub(r"_%04d\.exr$", "", file_name)
            if base_name == file_name:
                base_name = re.sub(r"\.[^.]+$", "", file_name)
            base_name = re.sub(r"_v\d+$", "", base_name)
            base_name = os.path.splitext(base_name)[0]

        # Usar función centralizada para extraer shot_code (detecta automáticamente formato)
        if extract_shot_code:
            base_identifier = extract_shot_code(base_name)
        else:
            # Fallback: usar primeros 4 bloques (comportamiento antiguo)
            parts = base_name.split("_")
            if len(parts) >= 4:
                base_identifier = "_".join(parts[:4])
            else:
                base_identifier = base_name

        version_match = re.search(r"(_v\d+)", file_name)
        version_str = version_match.group(1) if version_match else "_vUnknown"

        return base_identifier, version_str

    def change_to_branch_head(self, clip):
        """Sube el clip a la cabeza de SU rama.

        Antes era una copia del max() global del Pull: con ramas podia
        saltar el clip a la rama de otro compositor. Hoy nadie la llama,
        pero queda con la regla correcta para el que la use.
        """
        return switch_clip_to_version(clip, debug=debug_print)

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

    def delete_range_mismatch_tags(self, clip):
        """Elimina tags de Range Mismatch de un clip"""
        tags = clip.tags()
        if tags:
            for tag in list(
                tags
            ):  # Usar list() para evitar modificar durante iteración
                if tag.name() == "Range Mismatch":
                    clip.removeTag(tag)
                    debug_print(f"→ Eliminado tag 'Range Mismatch' del clip")

    def process_tracks(self, table, gui_table):
        """MODIFICADO - Procesar clips usando módulo centralizado con prioridad: selecciones múltiples > force_all_clips > playhead"""
        seq = hiero.ui.activeSequence()
        if not seq:
            QtWidgets.QMessageBox.warning(None, "Error", "No hay secuencia activa en Hiero.")
            return False

        # Obtener el proyecto para el manejo de UNDO
        project = seq.project()
        if not project:
            QtWidgets.QMessageBox.warning(None, "Error", "No se encontró el proyecto.")
            return False

        # Encontrar track aPlate (el track principal se obtiene del módulo centralizado)
        aplate_track = None
        for track in seq.videoTracks():
            if track.name().upper() == "APLATE":
                aplate_track = track
                break

        if not aplate_track:
            QtWidgets.QMessageBox.warning(None, "Error", "No se encontró el track aPlate.")
            return False

        # Obtener el track principal usando el módulo centralizado para obtener su nombre
        from LGA_NKS_Shared import LGA_NKS_GetClip as clip_utils

        track_name = clip_utils.TRACK_comp_EXR
        self.track_name = track_name  # Guardar para uso en la GUI

        # Encontrar el track principal
        exr_track = None
        for track in seq.videoTracks():
            if track.name().upper() == track_name.upper():
                exr_track = track
                break

        if not exr_track:
            QtWidgets.QMessageBox.warning(
                None,
                "Error",
                f"No se encontró el track '{track_name}' (configurado en TRACK_comp_EXR).",
            )
            return False

        # Obtener clips a procesar usando módulo centralizado
        # Prioridad: selecciones múltiples > force_all_clips > playhead
        if self.force_all_clips:
            # Si force_all_clips=True, procesar todos los clips del track
            exr_clips = [
                clip
                for clip in exr_track.items()
                if not isinstance(clip, hiero.core.EffectTrackItem)
            ]
            debug_print(
                f">>> Procesando todos los {len(exr_clips)} clips del track '{track_name}' (forzado por shift+click)"
            )
        else:
            # Usar módulo centralizado que prioriza selecciones múltiples sobre playhead
            exr_clips = get_clips_to_process(
                track_name=None, prioritize_multiple_selection=True
            )

            if not exr_clips:
                QtWidgets.QMessageBox.warning(
                    None,
                    "Error",
                    f"No se encontró ningún clip en el track '{track_name}' en la posición del playhead o seleccionado.",
                )
                return False

            debug_print(
                f">>> Procesando {len(exr_clips)} clip(s) del track '{track_name}'"
            )

        # Crear diccionario de clips aPlate por base name
        aplate_clips_dict = {}
        for clip in aplate_track.items():
            if isinstance(clip, hiero.core.EffectTrackItem):
                continue

            file_path = self.get_file_path(clip)
            if not file_path:
                continue

            base_identifier, version_str = self.parse_clip_name(
                os.path.basename(file_path)
            )

            if base_identifier not in aplate_clips_dict:
                aplate_clips_dict[base_identifier] = clip

        # Variable para saber si se encontraron resultados
        results_found = False

        # Iniciar operacion de UNDO para agrupar todos los cambios de tags
        project.beginUndo("Compare EXR to aPlate - Add Tags")

        try:
            # Procesar clips EXR - COMPARANDO CON aPlate
            for exr_clip in exr_clips:
                if isinstance(exr_clip, hiero.core.EffectTrackItem):
                    continue

                file_path = self.get_file_path(exr_clip)
                if not file_path:
                    continue

                # Verificar si el archivo contiene exactamente _v00 (no _v007, _v001, etc.) y saltearlo
                # Busca _v seguido de uno o más ceros seguido de delimitador (_ o .) o final del string
                file_basename = os.path.basename(file_path)
                if re.search(r"_v0+(_|\.|$)", file_basename):
                    debug_print(f">>> SALTEANDO clip v00: {file_basename}")
                    continue

                base_identifier, version_str = self.parse_clip_name(
                    os.path.basename(file_path)
                )

                debug_print(f"\n=== PROCESANDO SHOT: {base_identifier} ===")

                # Obtener rangos del clip EXR
                exr_fileinfos = exr_clip.source().mediaSource().fileinfos()
                if not exr_fileinfos:
                    debug_print("⚠️ No se encontraron fileinfos para el clip EXR.")
                    continue

                exr_start_frame = exr_fileinfos[0].startFrame()
                exr_end_frame = exr_fileinfos[0].endFrame()
                exr_range = f"{exr_start_frame}-{exr_end_frame}"

                # Obtener TC IN y FPS del clip EXR
                if AnalizeTC:
                    exr_tc_in, exr_fps = self.get_tc_in_and_fps(exr_clip)
                else:
                    # Solo obtener FPS cuando no se analiza TC
                    try:
                        media_source = exr_clip.source().mediaSource()
                        metadata = media_source.metadata()
                        if "foundry.source.framerate" in metadata:
                            fps = float(metadata["foundry.source.framerate"])
                            exr_fps = f"{fps:.3f}"
                        else:
                            exr_fps = "N/A"
                        exr_tc_in = "N/A"  # No analizar TC
                    except:
                        exr_fps = "N/A"
                        exr_tc_in = "N/A"

                debug_print(f"- Rango de frames del EXR: {exr_range}")
                if AnalizeTC:
                    debug_print(f"- TC IN del EXR: {exr_tc_in}")
                debug_print(f"- FPS del EXR: {exr_fps}")

                # Buscar clip correspondiente en aPlate
                if base_identifier in aplate_clips_dict:
                    aplate_clip = aplate_clips_dict[base_identifier]

                    aplate_fileinfos = aplate_clip.source().mediaSource().fileinfos()
                    if not aplate_fileinfos:
                        debug_print(
                            "⚠️ No se encontraron fileinfos para el clip aPlate."
                        )
                        continue

                    aplate_start_frame = aplate_fileinfos[0].startFrame()
                    aplate_end_frame = aplate_fileinfos[0].endFrame()
                    aplate_range = f"{aplate_start_frame}-{aplate_end_frame}"

                    # Obtener TC IN y FPS del clip aPlate
                    if AnalizeTC:
                        aplate_tc_in, aplate_fps = self.get_tc_in_and_fps(aplate_clip)
                    else:
                        # Solo obtener FPS cuando no se analiza TC
                        try:
                            media_source = aplate_clip.source().mediaSource()
                            metadata = media_source.metadata()
                            if "foundry.source.framerate" in metadata:
                                fps = float(metadata["foundry.source.framerate"])
                                aplate_fps = f"{fps:.3f}"
                            else:
                                aplate_fps = "N/A"
                            aplate_tc_in = "N/A"  # No analizar TC
                        except:
                            aplate_fps = "N/A"
                            aplate_tc_in = "N/A"

                    debug_print(f"- Rango de frames del aPlate: {aplate_range}")
                    if AnalizeTC:
                        debug_print(f"- TC IN del aPlate: {aplate_tc_in}")
                    debug_print(f"- FPS del aPlate: {aplate_fps}")

                    # Comparar todos los aspectos
                    range_match = (
                        exr_start_frame == aplate_start_frame
                        and exr_end_frame == aplate_end_frame
                    )
                    tc_match = exr_tc_in == aplate_tc_in
                    fps_match = exr_fps == aplate_fps

                    # Determinar el status basado en las comparaciones
                    mismatches = []
                    if not range_match:
                        mismatches.append("Range")
                    # Solo comparar TC si la flag AnalizeTC esta activada
                    if (
                        AnalizeTC
                        and not tc_match
                        and exr_tc_in != "N/A"
                        and aplate_tc_in != "N/A"
                    ):
                        mismatches.append("TC")
                    if not fps_match and exr_fps != "N/A" and aplate_fps != "N/A":
                        mismatches.append("FPS")

                    if not mismatches:
                        debug_print(f"✓ Todo coincide perfectamente: {base_identifier}")
                        # Limpiar cualquier tag de mismatch existente
                        self.delete_range_mismatch_tags(exr_clip)
                        status = "Match"
                        tag_description = "Perfecto match con aPlate"
                        tag_icon = "icons:TagGreen.png"
                    elif len(mismatches) == 1:
                        if "Range" in mismatches:
                            debug_print(
                                f"✗ Range mismatch: EXR({exr_range}) vs aPlate({aplate_range})"
                            )
                            status = "Range Mismatch"
                            tag_description = f"aPlate range: {aplate_range}"
                        elif "TC" in mismatches:
                            debug_print(
                                f"✗ TC mismatch: EXR({exr_tc_in}) vs aPlate({aplate_tc_in})"
                            )
                            status = "TC Mismatch"
                            tag_description = f"aPlate TC IN: {aplate_tc_in}"
                        elif "FPS" in mismatches:
                            debug_print(
                                f"✗ FPS mismatch: EXR({exr_fps}) vs aPlate({aplate_fps})"
                            )
                            status = "FPS Mismatch"
                            tag_description = f"aPlate FPS: {aplate_fps}"
                        tag_icon = "icons:TagYellow.png"
                    else:
                        debug_print(
                            f"✗ Multiple mismatches ({', '.join(mismatches)}): {base_identifier}"
                        )
                        status = "Multiple Mismatches"
                        tag_description = f"Mismatches: {', '.join(mismatches)}"
                        tag_icon = "icons:TagRed.png"

                    # Agregar tag solo si hay mismatches
                    if mismatches:
                        self.add_custom_tag_to_clip(
                            exr_clip,
                            "Range Mismatch",
                            tag_description,
                            tag_icon,
                        )
                        debug_print(f"→ Agregado tag '{status}' al clip EXR")

                    self.gui_table.add_result(
                        base_identifier,
                        exr_range,
                        aplate_range,
                        exr_tc_in,
                        aplate_tc_in,
                        exr_fps,
                        aplate_fps,
                        status,
                    )
                    results_found = True
                else:
                    debug_print(
                        f"- No se encontró clip aPlate correspondiente para: {base_identifier}"
                    )
                    # Agregar tag amarillo para clip aPlate no encontrado
                    self.add_custom_tag_to_clip(
                        exr_clip,
                        "Range Mismatch",
                        f"No aPlate found for {base_identifier}",
                        "icons:TagYellow.png",
                    )
                    debug_print(
                        f"→ Agregado tag amarillo 'Range Mismatch' al clip EXR (aPlate no encontrado)"
                    )
                    self.gui_table.add_result(
                        base_identifier,
                        exr_range,
                        "N/A",
                        exr_tc_in if AnalizeTC else "N/A",
                        "N/A",
                        exr_fps,
                        "N/A",
                        "No aPlate Found",
                    )
                    results_found = True

        except Exception as e:
            debug_print(f"Error durante el procesamiento: {e}")
        finally:
            # Finalizar operacion de UNDO
            project.endUndo()

        return results_found

    def get_file_path(self, clip):
        """Obtener la ruta del archivo de un clip."""
        try:
            file_path = clip.source().mediaSource().fileinfos()[0].filename()
            return file_path
        except:
            return None

    def get_tc_in_and_fps(self, clip):
        """Obtener TC IN y FPS confiables desde timecodeStart()."""
        try:
            source = clip.source()
            media_source = source.mediaSource()
            metadata = media_source.metadata()

            fps = (
                float(metadata["foundry.source.framerate"])
                if "foundry.source.framerate" in metadata
                else 25.0
            )
            tc_start = int(source.timecodeStart())
            tc_in_frames = tc_start + int(clip.sourceIn())
            tc_in_str = frame_to_tc(tc_in_frames, fps)
            fps_str = f"{fps:.3f}"
            return tc_in_str, fps_str
        except Exception as e:
            debug_print(f"Error obteniendo TC IN y FPS: {e}")
            return "N/A", "N/A"


def compare_exr_to_aplate(force_all_clips=False):
    """MODIFICADO - Funcion principal para comparar rangos entre EXR y aPlate basado en playhead"""
    global app, window  # COPIADO DEL PULL - usar variables globales

    app = QtWidgets.QApplication.instance() if QtWidgets.QApplication.instance() else QtWidgets.QApplication(sys.argv)
    window = FrameRangeComparisonGUI()
    hiero_ops = HieroOperations(window)
    hiero_ops.force_all_clips = force_all_clips  # Pasar el parametro al HieroOperations
    window.set_hiero_ops(hiero_ops)  # COPIADO DEL PULL - usar set_hiero_ops


# Para testing
if __name__ == "__main__":
    compare_exr_to_aplate()
