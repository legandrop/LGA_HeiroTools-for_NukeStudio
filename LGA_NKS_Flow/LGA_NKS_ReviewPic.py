"""
_______________________________________________________________________________________

  LGA_NKS_ReviewPic v0.3 - Lega
  Crea un snapshot de la imagen actual del viewer y lo guarda en ReviewPic_Cache
  organizando por clips del track EXR con numeracion de frames
_______________________________________________________________________________________

"""

import hiero.core
import hiero.ui
import os
import re
import glob
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QRect
import subprocess

DEBUG = True


def debug_print(*message):
    if DEBUG:
        print(*message)


def parse_exr_name(file_name):
    """
    Extrae el nombre base y numero de version de un archivo EXR.
    """
    version_match = re.search(r"_v(\d+)", file_name)
    version_number = version_match.group(1) if version_match else "Unknown"
    base_name = re.sub(r"_v\d+_%04d\.exr", "", file_name)
    return base_name, version_number


def get_clip_info_at_playhead():
    """
    Obtiene informacion del clip en el track EXR en la posicion actual del playhead.
    Retorna (base_name, version_number, frame_number) o None si no encuentra clip.
    """
    sequence = hiero.ui.activeSequence()
    if not sequence:
        debug_print("No se encontró una secuencia activa.")
        return None

    viewer = hiero.ui.currentViewer()
    if not viewer:
        debug_print("No se encontró un visor activo.")
        return None

    current_time = viewer.time()
    debug_print(f"Tiempo actual del playhead: {current_time}")

    exr_track = next((t for t in sequence.videoTracks() if t.name() == "EXR"), None)
    if not exr_track:
        debug_print("No se encontró un track llamado 'EXR'.")
        return None

    for clip in exr_track:
        if clip.timelineIn() <= current_time < clip.timelineOut():
            file_path = clip.source().mediaSource().fileinfos()[0].filename()
            fileinfo = clip.source().mediaSource().fileinfos()[0]
            exr_name = os.path.basename(file_path)
            base_name, version_number = parse_exr_name(exr_name)

            start_frame = fileinfo.startFrame()
            frame_offset = current_time - clip.timelineIn()
            frame_number = int(start_frame + frame_offset)

            debug_print(f"Clip encontrado: {base_name}_v{version_number}")
            debug_print(f"Frame calculado: {frame_number:04d}")

            return base_name, version_number, frame_number

    debug_print(
        "No se encontró un clip en el track 'EXR' en la posición actual del playhead."
    )
    return None


def get_next_available_filename(base_path, base_name, frame_number):
    """
    Obtiene el siguiente nombre de archivo disponible.
    Si existe, agrega _2, _3, etc.
    """
    # Nombre base: clipname_vXX_frameXXXX.jpg
    base_filename = f"{base_name}_{frame_number:04d}.jpg"
    full_path = os.path.join(base_path, base_filename)

    if not os.path.exists(full_path):
        return full_path, base_filename

    # Si existe, probar con sufijos
    counter = 2
    while True:
        suffix_filename = f"{base_name}_{frame_number:04d}_{counter}.jpg"
        full_path = os.path.join(base_path, suffix_filename)

        if not os.path.exists(full_path):
            debug_print(f"Archivo con sufijo generado: {suffix_filename}")
            return full_path, suffix_filename

        counter += 1
        if counter > 999:  # Seguridad para evitar bucle infinito
            raise Exception("Demasiados archivos duplicados")


def crop_to_aspect_ratio(qimage, target_aspect):
    """
    Recorta la imagen a la relacion de aspecto especificada.
    """
    width = qimage.width()
    height = qimage.height()

    current_aspect = width / height

    if current_aspect > target_aspect:
        new_width = int(height * target_aspect)
        offset_x = int((width - new_width) / 2)
        rect = QRect(offset_x, 0, new_width, height)
        cropped = qimage.copy(rect)
        return cropped
    else:
        new_height = int(width / target_aspect)
        offset_y = int((height - new_height) / 2)
        rect = QRect(0, offset_y, width, new_height)
        cropped = qimage.copy(rect)
        return cropped


def main():
    # Obtener informacion del clip actual
    clip_info = get_clip_info_at_playhead()
    if not clip_info:
        print("❌ No se pudo obtener información del clip en el track EXR")
        return

    base_name, version_number, frame_number = clip_info
    clip_folder_name = f"{base_name}_v{version_number}"

    # Crear carpeta de cache relativa al script
    script_dir = os.path.dirname(__file__)
    cache_dir = os.path.join(script_dir, "ReviewPic_Cache")
    clip_dir = os.path.join(cache_dir, clip_folder_name)

    # Crear directorios si no existen
    os.makedirs(clip_dir, exist_ok=True)
    debug_print(f"Carpeta de destino: {clip_dir}")

    # Obtener imagen del viewer
    viewer = hiero.ui.currentViewer()
    if not viewer:
        print("❌ No hay viewer activo")
        return

    qimage = viewer.image()
    if qimage is None or qimage.isNull():
        print("❌ viewer.image() devolvió None o imagen nula")
        return

    # Obtener la secuencia activa y su relacion de aspecto
    sequence = hiero.ui.activeSequence()
    if sequence is None:
        debug_print("No hay ninguna secuencia activa, usando 16:9 por defecto.")
        target_aspect = 16 / 9
    else:
        format = sequence.format()
        width = format.width()
        height = format.height()
        target_aspect = width / height
        debug_print(
            f"Relación de aspecto de la secuencia: {width} x {height} ({target_aspect:.2f})"
        )

    # Aplicar crop
    qimage_cropped = crop_to_aspect_ratio(qimage, target_aspect)
    debug_print(
        f"Snapshot size (cropped): {qimage_cropped.width()} × {qimage_cropped.height()}"
    )

    # Generar nombre de archivo con verificacion de duplicados
    try:
        full_path, filename = get_next_available_filename(
            clip_dir, clip_folder_name, frame_number
        )
        debug_print(f"Archivo de destino: {filename}")

        # Guardar imagen
        ok = qimage_cropped.save(full_path, "JPEG")

        if ok and os.path.exists(full_path):
            print(f"✅ ReviewPic guardado: {clip_folder_name}/{filename}")
            debug_print(f"Ruta completa: {full_path}")

            # Ruta al ejecutable de ShareX_ImageEditor_LGA
            # Se calcula la ruta relativa al directorio del script.
            editor_dir = os.path.abspath(
                os.path.join(script_dir, "..", "ShareX_ImageEditor_LGA")
            )
            editor_path = os.path.join(editor_dir, "ShareX_ImageEditor_LGA.exe")

            # Abrir el JPG con el editor de imagenes
            try:
                subprocess.Popen([editor_path, full_path])
                debug_print(f"Abriendo {full_path} con {editor_path}")
            except Exception as e:
                print(f"❌ Error al intentar abrir el editor de imágenes: {e}")
                debug_print(f"Error completo al abrir editor: {e}")

        else:
            print("❌ No se pudo crear el archivo.")
            debug_print(f"save() result: {ok}, exists: {os.path.exists(full_path)}")

    except Exception as e:
        print(f"❌ Error al guardar: {e}")
        debug_print(f"Error completo: {e}")


# --- Main Execution ---
if __name__ == "__main__":
    main()
