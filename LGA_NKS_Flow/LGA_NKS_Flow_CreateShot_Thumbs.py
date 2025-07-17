"""
______________________________________________________

  LGA_NKS_Flow_CreateShot_Thumbs v0.1 - Lega
  Crea un snapshot del viewer actual con zoom to fill y lo guarda en ShotThumbs_Cache
  organizando por nombre de shot
______________________________________________________

"""

import hiero.core
import hiero.ui
import os
import re
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QRect

DEBUG = False


def debug_print(*message):
    if DEBUG:
        print(*message)


def zoom_to_fill_in_viewer():
    """Aplica zoom to fill al viewer actual"""
    viewer = hiero.ui.currentViewer()
    if not viewer:
        debug_print("❌ No hay viewer activo")
        return False

    try:
        player = viewer.player()
        if not player:
            debug_print("❌ No se encontró el player del viewer")
            return False

        player.zoomToFill()
        debug_print("✅ Zoom to Fill aplicado con éxito")
        return True
    except Exception as e:
        debug_print(f"❌ Error aplicando zoomToFill: {e}")
        return False


def get_shot_name_from_selected_clip():
    """
    Obtiene el nombre del shot desde el clip seleccionado o desde el path del archivo.
    Retorna el shot name o None si no se encuentra.
    """
    sequence = hiero.ui.activeSequence()
    if not sequence:
        debug_print("No se encontró una secuencia activa.")
        return None

    timeline_editor = hiero.ui.getTimelineEditor(sequence)
    selected_clips = timeline_editor.selection()

    if not selected_clips:
        debug_print("No hay clips seleccionados en el timeline.")
        # Si no hay clips seleccionados, usar el nombre de la secuencia
        sequence_name = sequence.name()
        debug_print(f"Usando nombre de secuencia: {sequence_name}")
        return sequence_name

    # Tomar el primer clip seleccionado
    clip = selected_clips[0]

    try:
        # Intentar obtener el shot name del clip
        shot_name = clip.name()
        if shot_name:
            debug_print(f"Shot name desde clip.name(): {shot_name}")
            return shot_name
    except:
        pass

    try:
        # Si no hay shot name, extraerlo del path del archivo
        file_path = clip.source().mediaSource().fileinfos()[0].filename()
        debug_print(f"File path: {file_path}")

        # Extraer nombre base del archivo
        exr_name = os.path.basename(file_path)
        base_name = re.sub(r"_%04d\.exr$", "", exr_name)
        base_name = re.sub(r"_v\d+$", "", base_name)  # Remover version si existe

        # Si el nombre base contiene guiones bajos, tomar las primeras partes como shot code
        parts = base_name.split("_")
        if len(parts) >= 5:
            shot_code = "_".join(parts[:5])
            debug_print(f"Shot code extraído del path: {shot_code}")
            return shot_code
        else:
            debug_print(f"Nombre base del archivo: {base_name}")
            return base_name

    except Exception as e:
        debug_print(f"Error extrayendo shot name del path: {e}")

    # Como último recurso, usar el nombre de la secuencia
    sequence_name = sequence.name()
    debug_print(f"Usando nombre de secuencia como fallback: {sequence_name}")
    return sequence_name


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


def get_next_available_filename(base_path, shot_name):
    """
    Obtiene el siguiente nombre de archivo disponible.
    Si existe, agrega _2, _3, etc.
    """
    # Nombre base: shotname.jpg
    base_filename = f"{shot_name}.jpg"
    full_path = os.path.join(base_path, base_filename)

    if not os.path.exists(full_path):
        return full_path, base_filename

    # Si existe, probar con sufijos
    counter = 2
    while True:
        suffix_filename = f"{shot_name}_{counter}.jpg"
        full_path = os.path.join(base_path, suffix_filename)

        if not os.path.exists(full_path):
            debug_print(f"Archivo con sufijo generado: {suffix_filename}")
            return full_path, suffix_filename

        counter += 1
        if counter > 999:  # Seguridad para evitar bucle infinito
            raise Exception("Demasiados archivos duplicados")


def main():
    # Aplicar zoom to fill primero
    if not zoom_to_fill_in_viewer():
        print("❌ No se pudo aplicar zoom to fill")
        return

    # Obtener el shot name
    shot_name = get_shot_name_from_selected_clip()
    if not shot_name:
        print("❌ No se pudo obtener el nombre del shot")
        return

    # Limpiar el shot name para usarlo como nombre de archivo
    shot_name = re.sub(r'[<>:"/\\|?*]', "_", shot_name)  # Remover caracteres inválidos
    debug_print(f"Shot name limpio: {shot_name}")

    # Crear carpeta de cache relativa al script
    script_dir = os.path.dirname(__file__)
    cache_dir = os.path.join(script_dir, "ShotThumbs_Cache")

    # Crear directorio si no existe
    os.makedirs(cache_dir, exist_ok=True)
    debug_print(f"Carpeta de destino: {cache_dir}")

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
        full_path, filename = get_next_available_filename(cache_dir, shot_name)
        debug_print(f"Archivo de destino: {filename}")

        # Guardar imagen
        ok = qimage_cropped.save(full_path, "JPEG")

        if ok and os.path.exists(full_path):
            print(f"✅ Shot Thumbnail guardado: {filename}")
            debug_print(f"Ruta completa: {full_path}")
        else:
            print("❌ No se pudo crear el archivo.")
            debug_print(f"save() result: {ok}, exists: {os.path.exists(full_path)}")

    except Exception as e:
        print(f"❌ Error al guardar: {e}")
        debug_print(f"Error completo: {e}")


# --- Main Execution ---
if __name__ == "__main__":
    main()
