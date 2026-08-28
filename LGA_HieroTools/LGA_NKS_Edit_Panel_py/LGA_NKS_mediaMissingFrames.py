"""
____________________________________________________________________

  LGA_NKS_mediaMissingFrames v1.52 | Lega

  Escanea los clips seleccionados en Hiero para secuencias EXR con frames faltantes o corruptos

  v1.52: La ventana de tabla y el QProgressDialog migran al modulo de
         estilo del pack (Style.WINDOW + Style.TABLE / Style.FORM + PROGRESS)
  v1.51: Actualizada la ruta de openexr a shared
____________________________________________________________________

"""

import hiero.core
import hiero.ui
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt
from LGA_NKS_Shared.LGA_UI_Style_HieroTools import Style

# Qt ya está disponible desde LGA_QtAdapter_HieroTools
import os
import re
import subprocess
import traceback
import hashlib
import logging

# Configurar el logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WorkerThread(QtCore.QThread):
    update_progress = QtCore.Signal(int)
    update_table = QtCore.Signal(list)
    finished = QtCore.Signal()

    def __init__(self, selected_items):
        QtCore.QThread.__init__(self)
        self.selected_items = selected_items
        self.exr_cache = {}

    def run(self):
        for index, item in enumerate(self.selected_items):
            if isinstance(item, hiero.core.TrackItem):
                try:
                    clip = item.source()
                    file_path = clip.mediaSource().fileinfos()[0].filename()
                    if file_path.endswith('.exr'):
                        clip_info = self.process_clip(clip, file_path)
                        self.update_table.emit(clip_info)
                except Exception as e:
                    print(f"Error procesando clip: {str(e)}")
                    print(traceback.format_exc())
            self.update_progress.emit(index + 1)
        self.finished.emit()

    def process_clip(self, clip, file_path):
        first_frame = int(clip.mediaSource().startTime())
        last_frame = int(clip.mediaSource().startTime() + clip.mediaSource().duration() - 1)
        total_frames = last_frame - first_frame + 1
        
        directory = os.path.dirname(file_path)
        filename_pattern = os.path.basename(file_path)
        filename_pattern = re.sub(r'%0\d+d', r'%d', filename_pattern)
        
        missing_frames, corrupt_frames = self.check_frames(directory, filename_pattern, first_frame, last_frame)
        
        return [file_path, clip.name(), str(first_frame), str(last_frame), str(total_frames),
                ", ".join(map(str, missing_frames)) if missing_frames else "Ninguno",
                ", ".join(map(str, corrupt_frames)) if corrupt_frames else "Ninguno"]

    def check_frames(self, directory, filename_pattern, first_frame, last_frame):
        missing_frames = []
        corrupt_frames = []
        try:
            for frame in range(first_frame, last_frame + 1):
                expected_filename = os.path.join(directory, filename_pattern % frame)
                if not os.path.exists(expected_filename):
                    missing_frames.append(frame)
                    logger.warning(f"Frame faltante: {expected_filename}")
                elif not self.is_exr_valid(expected_filename):
                    corrupt_frames.append(frame)
                    logger.warning(f"Frame corrupto: {expected_filename}")
        except Exception as e:
            logger.error(f"Error verificando frames: {str(e)}")
            logger.error(traceback.format_exc())
        return missing_frames, corrupt_frames

    def is_exr_valid(self, file_path):
        file_hash = hashlib.md5(file_path.encode()).hexdigest()
        if file_hash in self.exr_cache:
            return self.exr_cache[file_hash]

        exrheader_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'LGA_NKS_Shared', 'OpenEXR_Win', 'exrheader.exe')
        try:
            result = subprocess.run([exrheader_path, file_path], capture_output=True, text=True, timeout=5)
            
            # Registrar la salida completa para depuracion
            logger.debug(f"Salida de exrheader para {file_path}:\n{result.stdout}")
            
            # Verificar si hay errores especificos en la salida
            is_valid = result.returncode == 0 and "ERROR" not in result.stdout and "invalid" not in result.stdout.lower()
            
            if not is_valid:
                logger.warning(f"Archivo potencialmente corrupto: {file_path}")
                logger.warning(f"Codigo de retorno: {result.returncode}")
                logger.warning(f"Salida de error: {result.stderr}")
            
            self.exr_cache[file_hash] = is_valid
            return is_valid
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout al verificar el archivo: {file_path}")
            self.exr_cache[file_hash] = False
            return False
        except Exception as e:
            logger.error(f"Error al verificar el archivo {file_path}: {str(e)}")
            logger.error(traceback.format_exc())
            self.exr_cache[file_hash] = False
            return False

class ClipMediaInfo(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(ClipMediaInfo, self).__init__(parent)
        self.initUI()

    def initUI(self):
        try:
            self.setWindowTitle("Informacion de Clips EXR")
            # Estilo del pack: un QWidget pelado necesita WA_StyledBackground
            # para pintar el fondo que le da la hoja
            self.setAttribute(Qt.WA_StyledBackground, True)
            self.setStyleSheet(Style.WINDOW)
            layout = QtWidgets.QVBoxLayout(self)

            self.table = QtWidgets.QTableWidget(0, 7, self)
            self.table.setStyleSheet(Style.TABLE)
            self.table.setHorizontalHeaderLabels(['Ruta', 'Nombre del Clip', 'IN', 'OUT', 'Frames', 'Frames Faltantes', 'Frames Corruptos'])
            self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)

            layout.addWidget(self.table)
            self.setLayout(layout)
            
            QtCore.QTimer.singleShot(0, self.load_data)
        except Exception as e:
            print(f"Error en initUI: {str(e)}")
            print(traceback.format_exc())

    def load_data(self):
        try:
            seq = hiero.ui.activeSequence()
            if seq:
                te = hiero.ui.getTimelineEditor(seq)
                selected_items = te.selection()

                self.progress = QtWidgets.QProgressDialog("Verificando clips...", "Cancelar", 0, len(selected_items), self)
                self.progress.setWindowModality(Qt.WindowModal)
                # Estilo del pack para el dialogo y su barra de progreso; el
                # boton de cancelar se reemplaza para que no quede con el host
                self.progress.setStyleSheet(Style.FORM + Style.PROGRESS)
                cancel_button = QtWidgets.QPushButton("Cancelar")
                cancel_button.setStyleSheet(Style.BTN_SECONDARY)
                self.progress.setCancelButton(cancel_button)

                self.worker = WorkerThread(selected_items)
                self.worker.update_progress.connect(self.update_progress)
                self.worker.update_table.connect(self.update_table)
                self.worker.finished.connect(self.on_finished)
                self.worker.start()

        except Exception as e:
            print(f"Error en load_data: {str(e)}")
            print(traceback.format_exc())

    def update_progress(self, value):
        self.progress.setValue(value)
        QtWidgets.QApplication.processEvents()  # Permite que la interfaz de usuario se actualice

    def update_table(self, clip_info):
        row_count = self.table.rowCount()
        self.table.insertRow(row_count)
        for col, value in enumerate(clip_info):
            item = QtWidgets.QTableWidgetItem(value)
            item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_count, col, item)
        QtWidgets.QApplication.processEvents()  # Permite que la interfaz de usuario se actualice

    def on_finished(self):
        self.progress.close()
        self.table.resizeColumnsToContents()
        self.adjust_window_size()

    def adjust_window_size(self):
        try:
            self.table.horizontalHeader().setStretchLastSection(False)
            self.table.resizeColumnsToContents()

            width = self.table.verticalHeader().width() - 40
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
            self.move((screen_rect.width() - final_width) // 2, (screen_rect.height() - final_height) // 2)
        except Exception as e:
            print(f"Error ajustando el tamano de la ventana: {str(e)}")
            print(traceback.format_exc())

def showClipMediaInfo():
    try:
        global clipMediaInfoWindow
        clipMediaInfoWindow = ClipMediaInfo()
        clipMediaInfoWindow.show()
    except Exception as e:
        print(f"Error mostrando la ventana de informacion de clips: {str(e)}")
        print(traceback.format_exc())

def run_script():
    try:
        showClipMediaInfo()
    except Exception as e:
        print(f"Error ejecutando el script: {str(e)}")
        print(traceback.format_exc())

# Registrar la funcion como una accion en Hiero
action = hiero.ui.createMenuAction("Mostrar Informacion de Clips EXR", run_script)
hiero.ui.registerAction(action)

# Agregar la accion al menu de Hiero
menuBar = hiero.ui.menuBar()
toolsMenu = menuBar.addMenu("Herramientas")
toolsMenu.addAction(action)

# Ejecutar el script automaticamente al cargar
run_script()
