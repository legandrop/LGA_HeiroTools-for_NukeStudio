"""
______________________________________________________

  LGA_NKS_Flow_Thumbs v0.2 - Lega
  Crea un snapshot del viewer actual con zoom to fill y lo guarda en N:/(proyecto)/Thumbs
  organizando por nombre de proyecto extraido del archivo
  Maneja el track BurnIn temporalmente para la captura
______________________________________________________

"""

import hiero.core
import hiero.ui
import os
import re
import time
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QRect

DEBUG = True


def debug_print(*message):
    if DEBUG:
        print(*message)


def get_project_name_from_clip():
    """
    Obtiene el nombre del proyecto desde el clip seleccionado.
    Busca el primer segmento antes del primer guion bajo en el nombre del archivo.
    """
    sequence = hiero.ui.activeSequence()
    if not sequence:
        debug_print("No se encontró una secuencia activa.")
        return None

    timeline_editor = hiero.ui.getTimelineEditor(sequence)
    selected_clips = timeline_editor.selection()

    if not selected_clips:
        debug_print("No hay clips seleccionados en el timeline.")
        return None

    # Tomar el primer clip seleccionado
    clip = selected_clips[0]

    try:
        # Obtener el path del archivo
        file_path = clip.source().mediaSource().fileinfos()[0].filename()
        debug_print(f"File path: {file_path}")

        # Extraer nombre base del archivo
        filename = os.path.basename(file_path)
        debug_print(f"Filename: {filename}")

        # Buscar el primer guion bajo y extraer la primera parte
        if "_" in filename:
            project_name = filename.split("_")[0]
            debug_print(f"Nombre del proyecto extraído: {project_name}")
            return project_name
        else:
            debug_print("No se encontró guión bajo en el nombre del archivo")
            return None

    except Exception as e:
        debug_print(f"Error extrayendo nombre del proyecto: {e}")
        return None


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


def force_viewer_refresh():
    """
    Fuerza el refresh del viewer usando los métodos disponibles en Hiero.
    """
    try:
        viewer = hiero.ui.currentViewer()
        if viewer:
            # Método 1: flushCache del viewer específico
            viewer.flushCache()
            debug_print("viewer.flushCache() aplicado")

            # Método 2: flush de todos los viewers
            hiero.ui.flushAllViewersCache()
            debug_print("hiero.ui.flushAllViewersCache() aplicado")

            # Método 3: procesar eventos pendientes de Qt
            from PySide2.QtWidgets import QApplication

            QApplication.processEvents()
            debug_print("QApplication.processEvents() ejecutado")

            # Método 4: forzar una actualización moviendo el tiempo y regresando
            current_time = viewer.time()
            if current_time > 0:
                viewer.setTime(current_time - 1)
                QApplication.processEvents()
                viewer.setTime(current_time)
                debug_print("Actualización forzada moviendo tiempo")

        return True
    except Exception as e:
        debug_print(f"Error en force_viewer_refresh: {e}")
        return False


def manage_burnin_track():
    """
    Busca el track llamado BurnIn y lo deshabilita si está habilitado.
    Retorna (track_found, was_enabled) donde:
    - track_found: True si se encontró el track BurnIn
    - was_enabled: True si estaba habilitado antes de deshabilitarlo
    """
    try:
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("No hay una secuencia activa.")
            return False, False

        for index, track in enumerate(seq.videoTracks()):
            if track.name() == "BurnIn":
                was_enabled = track.isEnabled()
                debug_print(f"Track 'BurnIn' encontrado en índice {index}")
                debug_print(
                    f"Estado original: {'Habilitado' if was_enabled else 'Deshabilitado'}"
                )

                # Si está habilitado, deshabilitarlo
                if was_enabled:
                    track.setEnabled(False)
                    debug_print("Track BurnIn deshabilitado para la captura.")

                    # Forzar múltiples actualizaciones del viewer
                    force_viewer_refresh()
                else:
                    debug_print("Track BurnIn ya estaba deshabilitado.")

                return True, was_enabled
        else:
            debug_print("No se encontró un track llamado 'BurnIn'.")
            return False, False

    except Exception as e:
        debug_print(f"Error durante la operación: {e}")
        return False, False


def restore_burnin_track(track_found, was_enabled):
    """
    Restaura el track BurnIn a su estado original usando múltiples métodos de refresh.
    """
    if not track_found:
        debug_print("No hay track BurnIn que restaurar.")
        return

    try:
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("No hay una secuencia activa.")
            return

        for index, track in enumerate(seq.videoTracks()):
            if track.name() == "BurnIn":
                # Solo restaurar si originalmente estaba habilitado
                if was_enabled:
                    track.setEnabled(True)
                    debug_print(
                        f"Track 'BurnIn' restaurado a habilitado en índice {index}"
                    )

                    # Forzar múltiples actualizaciones del viewer
                    force_viewer_refresh()
                else:
                    debug_print(
                        f"Track 'BurnIn' mantenido deshabilitado en índice {index}"
                    )
                break
        else:
            debug_print("No se encontró un track llamado 'BurnIn' para restaurar.")

    except Exception as e:
        debug_print(f"Error durante la operación: {e}")


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
    # Obtener el nombre del proyecto
    project_name = get_project_name_from_clip()
    if not project_name:
        print("❌ No se pudo obtener el nombre del proyecto")
        return

    # Crear la ruta semi-hardcodeada
    thumbs_dir = f"N:/{project_name}/Thumbs"
    debug_print(f"Carpeta de destino: {thumbs_dir}")

    # Crear directorio si no existe
    try:
        os.makedirs(thumbs_dir, exist_ok=True)
    except Exception as e:
        print(f"❌ No se pudo crear el directorio {thumbs_dir}: {e}")
        return

    # Manejar el track BurnIn
    track_found, was_enabled = manage_burnin_track()

    try:
        # Esperar para que se actualice el viewer después de deshabilitar BurnIn
        if track_found and was_enabled:
            time.sleep(1.0)  # Aumentar el tiempo de espera
            debug_print(
                "Esperando para que se actualice el viewer después de deshabilitar BurnIn"
            )

        # Aplicar zoom to fill
        if not zoom_to_fill_in_viewer():
            print("❌ No se pudo aplicar zoom to fill")
            return

        # Esperar un momento adicional para que se actualice el viewer
        time.sleep(0.5)

        # Obtener el shot name
        shot_name = get_shot_name_from_selected_clip()
        if not shot_name:
            print("❌ No se pudo obtener el nombre del shot")
            return

        # Limpiar el shot name para usarlo como nombre de archivo
        shot_name = re.sub(
            r'[<>:"/\\|?*]', "_", shot_name
        )  # Remover caracteres inválidos
        debug_print(f"Shot name limpio: {shot_name}")

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
            full_path, filename = get_next_available_filename(thumbs_dir, shot_name)
            debug_print(f"Archivo de destino: {filename}")

            # Guardar imagen
            ok = qimage_cropped.save(full_path, "JPEG")

            if ok and os.path.exists(full_path):
                print(
                    f"✅ Shot Thumbnail guardado en {project_name}/Thumbs: {filename}"
                )
                debug_print(f"Ruta completa: {full_path}")
            else:
                print("❌ No se pudo crear el archivo.")
                debug_print(f"save() result: {ok}, exists: {os.path.exists(full_path)}")

        except Exception as e:
            print(f"❌ Error al guardar: {e}")
            debug_print(f"Error completo: {e}")

    finally:
        # Restaurar el estado del track BurnIn
        restore_burnin_track(track_found, was_enabled)
        debug_print("Track BurnIn restaurado a su estado original")


# --- Main Execution ---
if __name__ == "__main__":
    main()
