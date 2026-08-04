"""
____________________________________________________________________

  LGA_NKS_Flow_Thumbs v1.02 | Lega

  Crea un snapshot del viewer actual con zoom to fill y lo guarda en <drive>/<proyecto>/Thumbs.
  Organiza por nombre de proyecto extraído del archivo.
  Maneja el track BurnIn temporalmente para la captura y lo restaura al final.
  Actualizado para ser compatible con ambos sistemas de nomenclatura:
  - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
  - PROYECTO_SEQ_SHOT (3 bloques simplificado)

  v1.02: Project name extraído desde el segmento VFX-NOMBRE del path del archivo
         (con fallback al primer bloque del filename si el path no contiene VFX-).
         Corrige proyectos como PROJALT cuyos shots tienen prefijo PROJA en el filename.
____________________________________________________________________
"""

import hiero.core
import hiero.ui
import os
import re
import sys
import time
from pathlib import Path
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt
QApplication = QtWidgets.QApplication
QRect = QtCore.QRect
QTimer = QtCore.QTimer

# Importar utilidades de naming
sys.path.append(str(Path(__file__).parent.parent / "LGA_NKS_Shared"))
from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    extract_project_name_from_path,
    clean_base_name,
)
from SecureConfig_Reader import read_secure_config

DEBUG = False


def debug_print(*message):
    if DEBUG:
        print(*message)


def get_work_root_drive():
    """
    Obtiene el root de trabajo desde App.AltTPath en config.secure.
    Fallback: T:
    """
    try:
        config = read_secure_config() or {}
        app_cfg = config.get("App", {}) if isinstance(config, dict) else {}
        raw_path = str(app_cfg.get("AltTPath", "")).strip()
        if raw_path:
            normalized = raw_path.replace("\\", "/").rstrip("/")
            if re.match(r"^[A-Za-z]:$", normalized):
                return normalized
            if re.match(r"^[A-Za-z]:/.*", normalized):
                return normalized
    except Exception as exc:
        debug_print(f"No se pudo leer AltTPath desde config.secure: {exc}")
    return "T:"


def get_project_name_from_clip():
    """
    Obtiene el nombre del proyecto desde el clip seleccionado.
    Usa funciones compartidas para extraer el nombre del proyecto.
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

        # Extraer nombre base del archivo usando función compartida
        filename = os.path.basename(file_path)
        base_name = clean_base_name(filename)
        
        # Usar función compartida para extraer el nombre del proyecto
        project_name = extract_project_name_from_path(file_path)
        if project_name:
            debug_print(f"Nombre del proyecto extraído (from path): {project_name}")
            return project_name
        project_name = extract_project_name(base_name)
        if project_name:
            debug_print(f"Nombre del proyecto extraído (from filename fallback): {project_name}")
            return project_name
        debug_print("No se pudo extraer el nombre del proyecto")
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

        # Extraer nombre base del archivo usando utilidades de naming
        exr_name = os.path.basename(file_path)
        base_name = clean_base_name(exr_name)

        # Extraer shot_code usando detección automática de formato
        shot_code = extract_shot_code(base_name)
        if shot_code:
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
    Retorna (track_found, was_enabled) para poder restaurarlo después.
    """
    debug_print("🔍 Buscando track BurnIn para deshabilitar...")

    try:
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("❌ No hay una secuencia activa.")
            return False, False

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
                    debug_print("✅ Track BurnIn deshabilitado temporalmente")

                    # Solo un refresh básico, nada agresivo
                    QApplication.processEvents()
                    debug_print("✅ Procesamiento básico de eventos Qt")

                    return True, True  # track found, was enabled
                else:
                    debug_print("ℹ️ Track BurnIn ya estaba deshabilitado")
                    return True, False  # track found, was not enabled

        debug_print("⚠️ No se encontró un track llamado 'BurnIn'")
        return False, False

    except Exception as e:
        debug_print(f"❌ Error durante la operación de deshabilitar BurnIn: {e}")
        return False, False


def restore_burnin_track_simple(track_found, was_enabled):
    """
    Restaura el track BurnIn a su estado original si era necesario.
    """
    if not track_found:
        debug_print("ℹ️ No hay track BurnIn que restaurar")
        return

    if not was_enabled:
        debug_print("ℹ️ Track BurnIn originalmente estaba deshabilitado, no se restaura")
        return

    debug_print("🔄 Restaurando track BurnIn...")

    try:
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("❌ No hay una secuencia activa")
            return

        for index, track in enumerate(seq.videoTracks()):
            if track.name() == "BurnIn":
                track.setEnabled(True)
                debug_print(
                    f"✅ Track 'BurnIn' restaurado a habilitado en índice {index}"
                )

                # Solo un procesamiento básico de eventos
                QApplication.processEvents()
                debug_print(
                    "✅ Procesamiento básico de eventos Qt después de restaurar"
                )
                break
        else:
            debug_print("⚠️ No se encontró un track llamado 'BurnIn' para restaurar")

    except Exception as e:
        debug_print(f"❌ Error durante la restauración del track BurnIn: {e}")


def zoom_to_fill_simple():
    """
    Aplica zoom to fill al viewer actual (compatible con Nuke 15/16).
    En Nuke 16: viewer.zoomToFill()
    En Nuke 15: viewer.player().zoomToFill()
    """
    debug_print("🔍 Aplicando zoom to fill...")

    viewer = hiero.ui.currentViewer()
    if not viewer:
        debug_print("❌ No hay viewer activo")
        return False

    try:
        # Intentar método de Nuke 16 primero (viewer.zoomToFill)
        if hasattr(viewer, 'zoomToFill'):
            viewer.zoomToFill()
            debug_print("✅ Zoom to Fill aplicado con éxito (Nuke 16)")

        # Fallback a método de Nuke 15 (player.zoomToFill)
        elif hasattr(viewer, 'player'):
            player = viewer.player()
            if player and hasattr(player, 'zoomToFill'):
                player.zoomToFill()
                debug_print("✅ Zoom to Fill aplicado con éxito (Nuke 15)")
            else:
                debug_print("⚠️ zoomToFill no disponible en player - continuando sin zoom")
                return False
        else:
            debug_print("⚠️ zoomToFill no disponible en viewer - continuando sin zoom")
            return False

        # Solo un procesamiento básico de eventos
        QApplication.processEvents()
        debug_print("✅ Procesamiento básico de eventos Qt después del zoom")

        return True
    except Exception as e:
        debug_print(f"❌ Error aplicando zoom: {e}")
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

    # Resolver drive de trabajo por perfil (studio/project) desde config.secure.
    work_root = get_work_root_drive()
    if re.match(r"^[A-Za-z]:$", work_root):
        thumbs_dir = f"{work_root}/{project_name}/Thumbs"
    else:
        thumbs_dir = os.path.join(work_root, project_name, "Thumbs")
    debug_print(f"📁 Carpeta de destino: {thumbs_dir}")

    # Crear directorio si no existe
    try:
        os.makedirs(thumbs_dir, exist_ok=True)
        debug_print(f"✅ Directorio verificado/creado: {thumbs_dir}")
    except Exception as e:
        print(f"❌ No se pudo crear el directorio {thumbs_dir}: {e}")
        return

    # PASO 1: Deshabilitar track BurnIn temporalmente
    debug_print("📋 PASO 1: Deshabilitando track BurnIn...")
    track_found, was_enabled = disable_burnin_track_simple()
    if track_found:
        debug_print("✅ Track BurnIn manejado correctamente")
    else:
        debug_print("ℹ️ No se encontró track BurnIn")

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
        # PASO 8: Restaurar el estado del track BurnIn
        debug_print("🔄 PASO 8: Restaurando track BurnIn...")
        restore_burnin_track_simple(track_found, was_enabled)
        debug_print("🏁 Script completado")


# --- Main Execution ---
if __name__ == "__main__":
    main()
