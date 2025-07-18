"""
______________________________________________________

  LGA_NKS_Flow_Thumbs v0.3 - Lega
  Crea un snapshot del viewer actual con zoom to fill y lo guarda en N:/(proyecto)/Thumbs
  organizando por nombre de proyecto extraido del archivo
  Maneja el track BurnIn temporalmente para la captura - SIN RESTAURAR
______________________________________________________

"""

import hiero.core
import hiero.ui
import os
import re
import time
from PySide2.QtWidgets import QApplication
from PySide2.QtCore import QRect, QTimer

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


def force_viewer_refresh_conservative():
    """
    Fuerza el refresh del viewer usando métodos conservadores que no rompan el player.
    """
    debug_print("🔄 Iniciando refresh conservador del viewer...")

    try:
        viewer = hiero.ui.currentViewer()
        if not viewer:
            debug_print("❌ No hay viewer activo")
            return False

        # Método 1: Solo flush cache básico
        viewer.flushCache()
        debug_print("✅ viewer.flushCache() aplicado")

        # Método 2: Procesar eventos Qt una sola vez
        QApplication.processEvents()
        debug_print("✅ QApplication.processEvents() ejecutado")

        # NO usar hiero.ui.flushAllViewersCache() - puede ser demasiado agresivo
        # NO mover el tiempo del viewer - puede causar problemas
        # NO usar QTimer.singleShot - puede causar conflictos

        return True
    except Exception as e:
        debug_print(f"❌ Error en force_viewer_refresh_conservative: {e}")
        return False


def disable_burnin_track_simple():
    """
    Busca el track llamado BurnIn y lo deshabilita de forma simple.
    NO lo restaura después.
    Retorna True si se encontró y deshabilitó el track.
    """
    debug_print("🔍 Buscando track BurnIn para deshabilitar...")

    try:
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("❌ No hay una secuencia activa.")
            return False

        for index, track in enumerate(seq.videoTracks()):
            if track.name() == "BurnIn":
                was_enabled = track.isEnabled()
                debug_print(f"✅ Track 'BurnIn' encontrado en índice {index}")
                debug_print(
                    f"Estado original: {'Habilitado' if was_enabled else 'Deshabilitado'}"
                )

                if was_enabled:
                    debug_print("🔄 Deshabilitando track BurnIn...")
                    track.setEnabled(False)
                    debug_print("✅ Track BurnIn deshabilitado PERMANENTEMENTE")

                    # Solo un refresh básico, nada agresivo
                    QApplication.processEvents()
                    debug_print("✅ Procesamiento básico de eventos Qt")

                    return True
                else:
                    debug_print("ℹ️ Track BurnIn ya estaba deshabilitado")
                    return True

        debug_print("⚠️ No se encontró un track llamado 'BurnIn'")
        return False

    except Exception as e:
        debug_print(f"❌ Error durante la operación de deshabilitar BurnIn: {e}")
        return False


def zoom_to_fill_simple():
    """Aplica zoom to fill al viewer actual de forma simple"""
    debug_print("🔍 Aplicando zoom to fill...")

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

        # Solo un procesamiento básico de eventos
        QApplication.processEvents()
        debug_print("✅ Procesamiento básico de eventos Qt después del zoom")

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
    debug_print("🚀 Iniciando LGA_NKS_Flow_Thumbs v0.3...")

    # Obtener el nombre del proyecto
    project_name = get_project_name_from_clip()
    if not project_name:
        print("❌ No se pudo obtener el nombre del proyecto")
        return

    # Crear la ruta semi-hardcodeada
    thumbs_dir = f"N:/{project_name}/Thumbs"
    debug_print(f"📁 Carpeta de destino: {thumbs_dir}")

    # Crear directorio si no existe
    try:
        os.makedirs(thumbs_dir, exist_ok=True)
        debug_print(f"✅ Directorio verificado/creado: {thumbs_dir}")
    except Exception as e:
        print(f"❌ No se pudo crear el directorio {thumbs_dir}: {e}")
        return

    # PASO 1: Deshabilitar track BurnIn PERMANENTEMENTE
    debug_print("📋 PASO 1: Deshabilitando track BurnIn...")
    burnin_disabled = disable_burnin_track_simple()
    if burnin_disabled:
        debug_print("✅ Track BurnIn deshabilitado correctamente")
    else:
        debug_print("ℹ️ No se encontró track BurnIn o ya estaba deshabilitado")

    try:
        # PASO 2: Aplicar zoom to fill con actualización del viewer
        debug_print("🔍 PASO 2: Aplicando zoom to fill...")
        if not zoom_to_fill_simple():
            print("❌ No se pudo aplicar zoom to fill")
            return

        # PASO 3: Espera mínima sin refresh agresivo
        debug_print("⏱️ PASO 3: Espera mínima antes de captura...")
        time.sleep(0.5)  # Solo una espera, sin refresh adicional

        # PASO 4: Obtener información del shot
        debug_print("📸 PASO 4: Obteniendo información del shot...")
        shot_name = get_shot_name_from_selected_clip()
        if not shot_name:
            print("❌ No se pudo obtener el nombre del shot")
            return

        # Limpiar el shot name para usarlo como nombre de archivo
        shot_name = re.sub(
            r'[<>:"/\\|?*]', "_", shot_name
        )  # Remover caracteres inválidos
        debug_print(f"🎬 Shot name limpio: {shot_name}")

        # PASO 5: Capturar imagen del viewer
        debug_print("📷 PASO 5: Capturando imagen del viewer...")
        viewer = hiero.ui.currentViewer()
        if not viewer:
            print("❌ No hay viewer activo")
            return

        qimage = viewer.image()
        if qimage is None or qimage.isNull():
            print("❌ viewer.image() devolvió None o imagen nula")
            return

        debug_print(f"✅ Imagen capturada: {qimage.width()} × {qimage.height()}")

        # PASO 6: Obtener relación de aspecto y crop
        debug_print("✂️ PASO 6: Aplicando crop de aspecto...")
        sequence = hiero.ui.activeSequence()
        if sequence is None:
            debug_print("⚠️ No hay ninguna secuencia activa, usando 16:9 por defecto")
            target_aspect = 16 / 9
        else:
            format = sequence.format()
            width = format.width()
            height = format.height()
            target_aspect = width / height
            debug_print(
                f"📐 Relación de aspecto de la secuencia: {width} x {height} ({target_aspect:.2f})"
            )

        # Aplicar crop
        qimage_cropped = crop_to_aspect_ratio(qimage, target_aspect)
        debug_print(
            f"✅ Imagen cropped: {qimage_cropped.width()} × {qimage_cropped.height()}"
        )

        # PASO 7: Guardar archivo
        debug_print("💾 PASO 7: Guardando thumbnail...")
        try:
            full_path, filename = get_next_available_filename(thumbs_dir, shot_name)
            debug_print(f"📄 Archivo de destino: {filename}")

            # Guardar imagen
            ok = qimage_cropped.save(full_path, "JPEG")

            if ok and os.path.exists(full_path):
                print(
                    f"✅ Shot Thumbnail guardado en {project_name}/Thumbs: {filename}"
                )
                debug_print(f"📍 Ruta completa: {full_path}")
            else:
                print("❌ No se pudo crear el archivo")
                debug_print(
                    f"❌ save() result: {ok}, exists: {os.path.exists(full_path)}"
                )

        except Exception as e:
            print(f"❌ Error al guardar: {e}")
            debug_print(f"❌ Error completo: {e}")

    except Exception as e:
        print(f"❌ Error durante la operación principal: {e}")
        debug_print(f"❌ Error completo: {e}")

    finally:
        # IMPORTANTE: NO restaurar el estado del track BurnIn
        debug_print("🚫 Track BurnIn NO será restaurado - permanece deshabilitado")
        debug_print("🏁 Script completado")


# --- Main Execution ---
if __name__ == "__main__":
    main()
