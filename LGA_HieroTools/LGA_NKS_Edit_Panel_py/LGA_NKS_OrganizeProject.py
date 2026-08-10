"""
____________________________________________________________________

  LGA_NKS_OrganizeProject v1.00 | Lega

  Script para organizar clips en bins basado en rutas de archivos.
____________________________________________________________________

"""

import hiero.ui
import hiero.core
import logging
import os
import queue
import time
from logging.handlers import QueueHandler, QueueListener

# Variables globales de logging (valores por defecto)
DEBUG = True
DEBUG_CONSOLE = False
DEBUG_LOG = True
script_start_time = None
debug_log_listener = None


class RelativeTimeFormatter(logging.Formatter):
    """Formatter que incluye tiempo relativo desde el inicio del script."""
    def format(self, record):
        global script_start_time
        if script_start_time is None:
            script_start_time = record.created

        relative_time = record.created - script_start_time
        record.relative_time = f"{relative_time:.3f}s"
        return super().format(record)


def setup_debug_logging(script_name="OrganizeProject"):
    """Configura el logging para escribir SOLO en archivo."""
    global debug_log_listener

    log_filename = f"debugPy_{script_name}.log"
    log_file_path = os.path.join(
        os.path.dirname(__file__), "..", "logs", log_filename
    )

    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)

    try:
        with open(log_file_path, "w", encoding="utf-8") as f:
            f.write(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    except Exception:
        pass

    logger_name = f"{script_name.lower()}_logger"
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:
        logger.handlers.clear()

    file_handler = logging.FileHandler(log_file_path, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    formatter = RelativeTimeFormatter("[%(relative_time)s] %(message)s")
    file_handler.setFormatter(formatter)

    log_queue = queue.Queue()
    queue_handler = QueueHandler(log_queue)
    queue_handler.setLevel(logging.DEBUG)
    logger.addHandler(queue_handler)

    if debug_log_listener:
        try:
            debug_log_listener.stop()
        except Exception:
            pass

    debug_log_listener = QueueListener(
        log_queue, file_handler, respect_handler_level=True
    )
    debug_log_listener.daemon = True
    debug_log_listener.start()

    return logger


debug_logger = setup_debug_logging(script_name="OrganizeProject")


def debug_print(*message, level="info"):
    global script_start_time

    msg = " ".join(str(arg) for arg in message)

    if DEBUG and DEBUG_LOG:
        if script_start_time is None:
            script_start_time = time.time()
        if level == "debug":
            debug_logger.debug(msg)
        elif level == "warning":
            debug_logger.warning(msg)
        elif level == "error":
            debug_logger.error(msg)
        else:
            debug_logger.info(msg)

    if DEBUG and DEBUG_CONSOLE:
        if script_start_time is None:
            script_start_time = time.time()
        relative_time = time.time() - script_start_time
        print(f"[{relative_time:.3f}s] {msg}")

def get_active_project():
    """
    Obtiene el proyecto activo en Hiero.

    Returns:
    - hiero.core.Project o None: El proyecto activo, o None si no se encuentra ninguno.
    """
    projects = hiero.core.projects()
    if projects:
        return projects[0]  # Devuelve el primer proyecto en la lista
    else:
        return None

class OrganizeProject:
    def find_or_create_bin(self, root_bin, bin_name):
        for item in root_bin.items():
            if isinstance(item, hiero.core.Bin) and item.name() == bin_name:
                return item
        new_bin = hiero.core.Bin(bin_name)
        root_bin.addItem(new_bin)
        return new_bin

    def move_clips_from_bin(self, bin_item):
        if (
            bin_item.name() == "Published"
        ):  # Ignorar el bin 'Published' y sus subcarpetas
            return
        for item in bin_item.items():
            if isinstance(item, hiero.core.BinItem) and isinstance(
                item.activeItem(), hiero.core.Clip
            ):
                clip = item.activeItem()
                media_source = clip.mediaSource()
                if media_source and media_source.fileinfos():
                    file_path = media_source.fileinfos()[0].filename()
                    parts = file_path.split("/")
                    if len(parts) > 3:
                        folder_name = f"F {parts[2]}"
                        shot_name = parts[3]
                        folder_bin = self.find_or_create_bin(
                            self.project.clipsBin(), folder_name
                        )
                        shot_bin = self.find_or_create_bin(folder_bin, shot_name)
                        clip_item = clip.binItem()
                        if clip_item.parentBin() != shot_bin:
                            clip_item.parentBin().removeItem(clip_item)
                            shot_bin.addItem(clip_item)
            elif isinstance(item, hiero.core.Bin):
                self.move_clips_from_bin(item)

    def clean_empty_bins(self, bin_item):
        if bin_item.name() == "Published":
            return
        items_to_check = list(bin_item.items())
        for item in items_to_check:
            if isinstance(item, hiero.core.Bin):
                self.clean_empty_bins(item)
        if not bin_item.items() and bin_item.parentBin():
            bin_item.parentBin().removeItem(bin_item)

    def move_clips_based_on_path(self, project):
        self.project = project
        with project.beginUndo("Reorganize Clips Based on Path"):
            for bin_item in project.clipsBin().items():
                if isinstance(bin_item, hiero.core.Bin):
                    self.move_clips_from_bin(bin_item)

            for bin_item in list(project.clipsBin().items()):
                if isinstance(bin_item, hiero.core.Bin):
                    self.clean_empty_bins(bin_item)

    def organize_project(self):
        project = get_active_project()
        if project:
            self.move_clips_based_on_path(project)
        else:
            debug_print("No se encontro un proyecto abierto en Hiero.")

def main():
    """Función principal que ejecuta organize_project."""
    organizer = OrganizeProject()
    organizer.organize_project()

if __name__ == "__main__":
    main()