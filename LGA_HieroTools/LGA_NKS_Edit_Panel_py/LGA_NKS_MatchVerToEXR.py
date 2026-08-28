"""
____________________________________________________________________

  LGA_NKS_MatchVerToEXR v0.83 | Lega

  Busca la version actual de los clips del track _comp_ (TRACK_comp_EXR) e
  intenta subir la versión de los clips correspondientes del track _compRev_ (TRACK_comp_REV) a la misma versión.

  v0.83: La ventana de resultados migra al modulo de estilo
         LGA_UI_Style_HieroTools: fondo Style.WINDOW y marco/header/
         scrollbars de la tabla con tokens. Los colores de CELDA por
         estado son data y no se tocan; por eso NO se aplica Style.TABLE
         y se conserva la regla item:selected transparente que deja
         pintar al ColorMixDelegate.
  v0.82: Los carteles de aviso pasan al helper LGA_NKS_MessageBox con el estilo del pack.
  v0.81: Expande el filtro de clips EXR para incluir aliases de task name
         (compo → comp) evitando descartar clips con _Compo_ en el filename
         que están correctamente en el track _comp_.
  v0.80: Renombra TRACK_comp_REV de "_compMov_" a "_compRev_" (nueva convención taskRev)
  v0.70: Actualiza fallback de TRACK_comp_REV a "_compMov_" (renombrado desde "_rev_")
  v0.60: Usa módulo centralizado LGA_NKS_GetClip para obtener clips (método híbrido: selecciones múltiples > playhead > selección)
  v0.50: Actualizado para ser compatible con ambos sistemas de nomenclatura:
         - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
         - PROYECTO_SEQ_SHOT (3 bloques simplificado)
____________________________________________________________________

"""

import os
import re
from pathlib import Path
import hiero.core
import hiero.ui
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import Style, Color as UIColor
import sys

# Variable global para activar o desactivar los prints
DEBUG = False

# Importar utilidades para naming (compatibilidad con ambos formatos)
naming_utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if naming_utils_path.exists():
    sys.path.insert(0, str(naming_utils_path))
    try:
        from LGA_NKS_Flow_NamingUtils import (
            extract_shot_code,
            clean_base_name,
            TASK_NAME_ALIASES,
        )
    except ImportError:
        if DEBUG:
            print("ERROR: No se encontró el módulo LGA_NKS_Flow_NamingUtils")
        extract_shot_code = None
        clean_base_name = None
        TASK_NAME_ALIASES = {}
else:
    if DEBUG:
        print("ERROR: No se encontró el directorio LGA_NKS_Shared")
    extract_shot_code = None
    clean_base_name = None

# Importar utilidades para obtener clips y variables centralizadas para nombres de tracks
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    try:
        from LGA_NKS_Shared.LGA_NKS_GetClip import get_clips_to_process
        from LGA_NKS_Shared import LGA_NKS_GetClip as clip_utils

        TRACK_comp_EXR = clip_utils.TRACK_comp_EXR
        TRACK_comp_REV = clip_utils.TRACK_comp_REV
        # Sincronizar el debug con el módulo utilitario
        clip_utils.DEBUG = DEBUG
    except ImportError:
        if DEBUG:
            print("ERROR: No se encontró el módulo LGA_NKS_GetClip")
        TRACK_comp_EXR = "_comp_"  # Fallback
        TRACK_comp_REV = "_compRev_"  # Fallback
        get_clips_to_process = None
else:
    if DEBUG:
        print("ERROR: No se encontró el directorio LGA_NKS_Shared")
    TRACK_comp_EXR = "_comp_"  # Fallback
    TRACK_comp_REV = "_compRev_"  # Fallback
    get_clips_to_process = None

# Importar carteles estilados del pack (fallback a los estaticos de Qt)
try:
    from LGA_NKS_Shared.LGA_NKS_MessageBox import show_info, show_warning
except ImportError:
    if DEBUG:
        print("ERROR: No se encontró el módulo LGA_NKS_MessageBox")

    def show_info(parent, title, text):
        QtWidgets.QMessageBox.information(parent, title, text)

    def show_warning(parent, title, text):
        QtWidgets.QMessageBox.warning(parent, title, text)

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


class VersionMatcherGUI(QtWidgets.QWidget):
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
                show_info(
                    self,
                    "No Changes",
                    f"No se encontraron clips del track {TRACK_comp_EXR} con correspondientes clips del track {TRACK_comp_REV}.",
                )

    def add_color_to_background_list(self, row_colors):
        """COPIADO DEL PULL - Agrega una lista de colores de fondo para una nueva fila."""
        self.row_background_colors.append(row_colors)

    def initUI(self):
        self.setWindowTitle(
            f"{TRACK_comp_EXR} to {TRACK_comp_REV} Version Matcher - Results"
        )
        # Fondo de la ventana con el estilo del pack
        self.setStyleSheet(Style.WINDOW)
        layout = QtWidgets.QVBoxLayout(self)

        self.table = QtWidgets.QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(
            ["Shot", "EXR Version", "REV Was", "Status"]
        )

        # COPIADO DEL PULL - Configuracion de tabla
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.table.setSelectionMode(QtWidgets.QTableWidget.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setFocusPolicy(QtCore.Qt.NoFocus)
        # NO se aplica Style.TABLE: los fondos de las celdas son DATA (colores
        # de estado del match de versiones) y los pinta el ColorMixDelegate;
        # una regla item:selected con fondo del tema los pisaria justo al
        # seleccionar. Se estila solo el marco, la cabecera y las scrollbars
        # con tokens, y se conserva la seleccion transparente (misma tecnica
        # que la GUI_Table del Flow Pull).
        self.table.setStyleSheet(
            "QTableWidget { background-color: %(surface)s;"
            " border: 1px solid %(border)s;"
            " gridline-color: %(border)s;"
            " color: %(text)s; }"
            " QHeaderView::section { background-color: %(header_bg)s;"
            " color: %(header_fg)s; padding: 4px 8px; border: 0px;"
            " border-bottom: 1px solid %(border_strong)s; font-weight: bold; }"
            " QTableView::item:selected { color: black;"
            " background-color: transparent; }"
            % {
                "surface": UIColor.SURFACE,
                "border": UIColor.BORDER,
                "border_strong": UIColor.BORDER_STRONG,
                "text": UIColor.TEXT,
                "header_bg": UIColor.SURFACE_HEADER,
                "header_fg": UIColor.TEXT_HEADER,
            }
            + Style.SCROLLBAR
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

    def add_result(self, shot_base, exr_version, rev_was_version, status):
        """Anadir una fila a la tabla con el resultado."""
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Agregar items a la tabla
        shot_item = QtWidgets.QTableWidgetItem(shot_base + "   ")  # COPIADO DEL PULL - espacios
        exr_item = QtWidgets.QTableWidgetItem(f"v{exr_version:02d}")
        rev_item = QtWidgets.QTableWidgetItem(f"v{rev_was_version:02d}")
        status_item = QtWidgets.QTableWidgetItem(status)

        # COPIADO DEL PULL - Centrado
        exr_item.setTextAlignment(QtCore.Qt.AlignCenter)
        rev_item.setTextAlignment(QtCore.Qt.AlignCenter)

        # Colorear segun el estado. Son colores de DATA (resultado del match)
        # y no de estilo: se dejan como hex, salvo el verde de Already
        # Matched, que coincide EXACTO con el token OK_BG del modulo de
        # estilo.
        if status == "Updated":
            status_color = "#7d4cff"  # Morado
        elif status == "Version Not Available":
            status_color = "#933100"  # Rojo oscuro
        elif status == "Already Matched":
            status_color = UIColor.OK_BG  # Verde oscuro (#244C19)
        else:
            status_color = "#8a8a8a"  # Gris por defecto

        # COPIADO DEL PULL - Configuracion de colores
        status_bg_color = QtGui.QColor(status_color)
        status_text_color = self.color_for_background(status_color)
        status_item.setBackground(QtGui.QBrush(status_bg_color))
        status_item.setForeground(QtGui.QBrush(QtGui.QColor(status_text_color)))
        status_item.setTextAlignment(QtCore.Qt.AlignCenter)

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
            super(VersionMatcherGUI, self).keyPressEvent(event)


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

    def parse_exr_name(self, file_name):
        """Extrae el nombre base del archivo y el numero de version usando funciones centralizadas"""
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

        version_match = re.search(r"(_v\d+)", file_name)
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
        """MODIFICADO - Procesar clips de tracks _comp_ y _rev_ usando método híbrido, devolviendo si hay cambios"""
        seq = hiero.ui.activeSequence()
        if not seq:
            show_warning(None, "Error", "No hay secuencia activa en Hiero.")
            return False

        # Encontrar tracks usando variables centralizadas
        exr_track = None
        rev_track = None

        for track in seq.videoTracks():
            if track.name().upper() == TRACK_comp_EXR.upper():
                exr_track = track
            elif track.name().upper() == TRACK_comp_REV.upper():
                rev_track = track

        if not exr_track:
            show_warning(
                None, "Error", f"No se encontró el track {TRACK_comp_EXR}."
            )
            return False

        if not rev_track:
            show_warning(
                None, "Error", f"No se encontró el track {TRACK_comp_REV}."
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
                f">>> Procesando todos los {len(exr_clips)} clips del track {TRACK_comp_EXR} (forzado por shift+click)"
            )
        else:
            # Usar módulo centralizado que prioriza selecciones múltiples sobre playhead
            if get_clips_to_process:
                exr_clips = get_clips_to_process(
                    track_name=None, prioritize_multiple_selection=True
                )
            else:
                # Fallback manual si no está disponible el módulo
                te = hiero.ui.getTimelineEditor(seq)
                selected_clips = te.selection() if te else []
                exr_clips = [
                    clip
                    for clip in selected_clips
                    if clip.parentTrack() == exr_track
                    and not isinstance(clip, hiero.core.EffectTrackItem)
                ]
                if not exr_clips:
                    # Fallback a playhead
                    viewer = hiero.ui.currentViewer()
                    if viewer:
                        current_time = viewer.time()
                        for clip in exr_track:
                            if isinstance(clip, hiero.core.EffectTrackItem):
                                continue
                            if clip.timelineIn() <= current_time < clip.timelineOut():
                                exr_clips = [clip]
                                break

            if not exr_clips:
                show_warning(
                    None,
                    "Error",
                    f"No se encontró ningún clip en el track {TRACK_comp_EXR} en la posición del playhead o seleccionado.",
                )
                return False

            debug_print(
                f">>> Procesando {len(exr_clips)} clip(s) del track {TRACK_comp_EXR}"
            )

        # Crear diccionario de clips REV por base name
        rev_clips_dict = {}
        for clip in rev_track.items():
            if isinstance(clip, hiero.core.EffectTrackItem):
                continue

            file_path = self.get_file_path(clip)
            if not file_path:
                continue

            base_name, version_str = self.parse_exr_name(os.path.basename(file_path))
            # Usar función centralizada para extraer shot_code (base sin versión)
            if extract_shot_code:
                base_without_version = extract_shot_code(base_name)
            else:
                # Fallback: remover versión manualmente
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

            # Solo procesar archivos que contengan "_comp_" o un alias conocido (ej. "_compo_")
            exr_basename = os.path.basename(file_path).lower()
            comp_patterns = ["_comp_"] + [f"_{alias}_" for alias in TASK_NAME_ALIASES.keys()]
            if not any(pat in exr_basename for pat in comp_patterns):
                continue

            base_name, version_str = self.parse_exr_name(os.path.basename(file_path))
            exr_version = extract_version_number(version_str)
            # Usar función centralizada para extraer shot_code (base sin versión)
            if extract_shot_code:
                base_without_version = extract_shot_code(base_name)
            else:
                # Fallback: remover versión manualmente
                base_without_version = base_name.replace(version_str, "")

            debug_print(f"\n=== PROCESANDO SHOT: {base_without_version} ===")
            debug_print(
                f"- Version actual del {base_without_version} del track {TRACK_comp_EXR}: v{exr_version:02d}"
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
                    f"- Version actual del {base_without_version} del track {TRACK_comp_REV}: v{rev_current_version:02d}"
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
                    f"- Versiones existentes para el {TRACK_comp_REV}: {available_versions_str}"
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
                                f"{TRACK_comp_EXR} requires v{exr_version:02d}",
                                "icons:TagRed.png",
                            )
                            debug_print(
                                f"→ Agregado tag rojo 'Version Mismatch' al clip {TRACK_comp_REV}"
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
                    f"- No se encontro clip {TRACK_comp_REV} correspondiente para: {base_without_version}"
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

    app = QtWidgets.QApplication.instance() if QtWidgets.QApplication.instance() else QtWidgets.QApplication(sys.argv)
    window = VersionMatcherGUI()
    hiero_ops = HieroOperations(window)
    hiero_ops.force_all_clips = force_all_clips  # Pasar el parametro al HieroOperations
    window.set_hiero_ops(hiero_ops)  # COPIADO DEL PULL - usar set_hiero_ops


# Para testing
if __name__ == "__main__":
    match_exr_to_rev()
