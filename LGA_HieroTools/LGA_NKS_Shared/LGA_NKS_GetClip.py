"""
____________________________________________________________________

  LGA_NKS_GetClip v1.84 | Lega

  Usado por runtime activo:
  - LGA_NKS_Assignee_Panel.py
  - LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_Download.py
  - LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_OpenPath.py
  - LGA_NKS_Coordination_Panel_py/LGA_NKS_FileManagerS3_Upload.py
  - LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CheckTimelineShots.py
  - LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py
  - LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShotPriority.py
  - LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_ShowInFlow.py
  - LGA_NKS_Coordination_Panel_py/LGA_NKS_PipeSync_CreatePsync.py
  - LGA_NKS_Coordination_Panel_py/LGA_NKS_PipeSync_OpenPath.py
  - LGA_NKS_Edit_Panel_py/LGA_NKS_CompareEXR_to_aPlate.py
  - LGA_NKS_Edit_Panel_py/LGA_NKS_CompareVerToEditref.py
  - LGA_NKS_Edit_Panel_py/LGA_NKS_MatchVerToEXR.py
  - LGA_NKS_Flow_Panel.py
  - LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Pull.py
  - LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Push.py
  - LGA_NKS_Flow_Panel_py/LGA_NKS_Flow_Shot_info.py
  - LGA_NKS_Flow_Panel_py/LGA_NKS_ReviewPic.py
  - LGA_NKS_Review_Panel_py/LGA_NKS_Clip_DisableEXR.py
  - LGA_NKS_Review_Panel_py/LGA_NKS_Compare_Versions.py
  - LGA_NKS_Review_Panel_py/LGA_NKS_Compare_Versions_OFF.py
  - LGA_NKS_Review_Panel_py/LGA_NKS_EXRTrack_Difference.py
  - LGA_NKS_ViewerTL_Panel_py/LGA_NKS_InOut_Editref.py
  - LGA_NKS_ViewerTL_Panel_py/LGA_NKS_PrevNext_Rev.py

  Utilidades para obtener clips del timeline de Hiero/Nuke Studio.

  Método híbrido inteligente completo:
  1. LÓGICA INTELIGENTE SIMPLE: Si hay un clip seleccionado fuera del
     track objetivo pero del mismo shot, automáticamente usa el clip del
     track correcto (sin mostrar mensaje al usuario).
  2. EXCEPCIÓN PLAYHEAD: Si el clip seleccionado está bajo el playhead,
     no muestra advertencia pero mantiene la selección del track objetivo.
  3. LÓGICA INTELIGENTE MÚLTIPLE: Analiza selecciones múltiples y devuelve
     exactamente un clip por shot único, priorizando clips del track
     objetivo pero incluyendo shots de otros tracks.
  4. Muestra advertencia solo cuando la lógica inteligente NO puede resolver.
  5. Intenta obtener el clip del track especificado en la posición del playhead.
  6. Si no encuentra, usa el clip seleccionado como fallback.

  v1.84: Renombra TRACK_comp_REV de "_compMov_" a "_compRev_" (nueva convención taskRev).
         Agrega TRACK_cleanup_EXR, TRACK_roto_REV, TRACK_cleanup_REV y la lista TASK_REV_TRACKS.
  v1.83: Renombra TRACK_comp_REV de "_rev_" a "_compMov_" para mayor claridad
  v1.82: Agrega TRACK_roto_EXR y TASK_EXR_TRACKS para soporte multi-task
  v1.81: flag _SHOW_WARNINGS para desactivar/activar las advertencias por defecto
  v1.80: EXCEPCIÓN PLAYHEAD: Nueva función is_clip_at_playhead() detecta cuando un clip seleccionado
         está bajo el playhead. En este caso, no muestra advertencia pero mantiene la selección del track
         objetivo. Mensajes de advertencia usan color cyan #6AB5CA (consistente con Create Shot).
  v1.70: LÓGICA INTELIGENTE COMPLETA: Nueva función analyze_multiple_shots_selection()
         implementa selección múltiple inteligente. Devuelve exactamente un clip por shot único,
         priorizando clips del track objetivo pero incluyendo shots sin correspondencia.
  v1.60: LÓGICA INTELIGENTE MEJORADA: Ahora resuelve automáticamente selecciones erróneas
         sin mostrar mensaje informativo al usuario. La advertencia solo aparece cuando
         NO puede resolverse automáticamente. Función específica extract_shot_code_from_filename
         para evitar interferir con otros scripts.
  v1.50: LÓGICA INTELIGENTE: Comparación automática de shots para selecciones simples.
         Si hay un clip seleccionado fuera del track objetivo pero del mismo shot,
         automáticamente usa el clip del track correcto
  v1.40: Agrega advertencia automática cuando hay clips seleccionados en tracks que no son el objetivo
  v1.30: Renombra variables: DEFAULT_TRACK_NAME → TRACK_comp_EXR, DEFAULT_REV_TRACK_NAME → TRACK_comp_REV
  v1.20: Agrega DEFAULT_REV_TRACK_NAME para centralizar el nombre del track REV
  v1.10: Agrega get_clips_to_process para obtener múltiples clips seleccionados en el track
____________________________________________________________________
"""

import hiero.core
import hiero.ui
import re

# Control interno del debug para este módulo (no se puede sobrescribir desde fuera)
_GETCLIP_DEBUG_ENABLED = False

# Control de advertencias del módulo (False = nunca mostrar advertencias)
_SHOW_WARNINGS = False


def debug_print(*message):
    """Función para imprimir mensajes de debug del módulo GetClip."""
    if _GETCLIP_DEBUG_ENABLED:
        print("[GetClip]", *message)


# Convención de nombres de tracks por task:
#   - EXR render  → "_{task}_"      (ej: "_comp_", "_roto_", "_cleanup_")
#   - Review MOV/MXF → "_{task}Rev_" (ej: "_compRev_", "_rotoRev_", "_cleanupRev_")
# El track Rev contiene .mov o .mxf indistintamente según el proyecto.

# Tracks EXR por task
TRACK_comp_EXR = "_comp_"        # EXR con el render de COMP
TRACK_roto_EXR = "_roto_"        # EXR con el render de ROTO
TRACK_cleanup_EXR = "_cleanup_"  # EXR con el render de CLEANUP

# Tracks Review (MOV/MXF) por task
TRACK_comp_REV = "_compRev_"         # MOV/MXF de review de COMP
TRACK_roto_REV = "_rotoRev_"         # MOV/MXF de review de ROTO
TRACK_cleanup_REV = "_cleanupRev_"   # MOV/MXF de review de CLEANUP

# Listas centralizadas. Para agregar soporte a una nueva task, sumar su track aquí.
TASK_EXR_TRACKS = [TRACK_comp_EXR, TRACK_roto_EXR, TRACK_cleanup_EXR]
TASK_REV_TRACKS = [TRACK_comp_REV, TRACK_roto_REV, TRACK_cleanup_REV]

# Intentar importar funciones de naming para comparación inteligente de shots
try:
    from LGA_NKS_Shared.LGA_NKS_Flow_NamingUtils import extract_shot_code, clean_base_name, detect_shotname_format
    NAMING_UTILS_AVAILABLE = True
    debug_print("NamingUtils importado correctamente")
except ImportError as e:
    NAMING_UTILS_AVAILABLE = False
    debug_print(f"NamingUtils NO importado, usando fallback: {e}")

    # OJO: este fallback es CODIGO MUERTO y esta DESACTUALIZADO a proposito.
    # extract_shot_code_from_filename() corta antes con "" cuando
    # NAMING_UTILS_AVAILABLE es False, asi que nada de esto llega a ejecutarse.
    # Ademas no reconoce el naming PROYECTO_SEQ_SHOT_VENDOR (v1.14 de
    # NamingUtils), porque los vendor codes salen de la DB de PipeSync y no se
    # pueden adivinar por estructura. Si algun dia se reactiva esta rama, hay
    # que borrarla y resolver el import, no sincronizar la copia a mano.
    _VERSION_RE = re.compile(r"^v\d+$", re.IGNORECASE)

    def _strip_version_suffix(parts):
        if parts and _VERSION_RE.match(parts[-1]):
            return parts[:-1]
        return parts

    def _is_numeric_block(value):
        return bool(value) and value[0].isdigit()

    def _is_series_format(parts):
        return len(parts) >= 4 and all(_is_numeric_block(p) for p in parts[1:4])

    def _is_vendor_format(parts):
        return (
            len(parts) >= 4
            and parts[1].isalpha()
            and _is_numeric_block(parts[2])
            and _is_numeric_block(parts[3])
        )

    def _analyze_shotname(base_name):
        if not base_name:
            return [], False, False, 0
        parts = base_name.split("_")
        core_parts = _strip_version_suffix(parts)
        if not core_parts:
            return [], False, False, 0
        is_series = _is_series_format(core_parts) or _is_vendor_format(core_parts)
        base_count = 4 if is_series else 3
        has_description = len(core_parts) >= (base_count + 2)
        return core_parts, is_series, has_description, base_count

    def extract_shot_code(base_name):
        """Fallback básico si no hay módulo naming"""
        core_parts, _, has_description, base_count = _analyze_shotname(base_name)
        if not core_parts:
            return ""
        desc_count = 2 if has_description else 0
        target_count = base_count + desc_count
        if len(core_parts) >= target_count:
            return "_".join(core_parts[:target_count])
        return "_".join(core_parts)

    def clean_base_name(file_name):
        """Fallback básico si no hay módulo naming"""
        import os
        return os.path.splitext(file_name)[0]

    def detect_shotname_format(base_name):
        """Fallback básico si no hay módulo naming"""
        core_parts, _, has_description, _ = _analyze_shotname(base_name)
        if not core_parts:
            return False
        return has_description


def extract_shot_code_from_filename(file_path):
    """
    Función específica para GetClip: extrae shot code de un filename completo (con ruta).
    Usa NamingUtils pero maneja correctamente filenames con rutas completas.

    Args:
        file_path (str): Ruta completa del archivo

    Returns:
        str: Shot code extraído o cadena vacía si error
    """
    if not file_path or not NAMING_UTILS_AVAILABLE:
        return ""

    try:
        # Limpiar el filename: remover ruta, extensión, versión
        import os
        filename_only = os.path.basename(file_path)  # Solo nombre del archivo sin ruta

        # Remover extensión de secuencia EXR y versión
        import re
        clean_name = re.sub(r"_%04d\.exr$", "", filename_only)
        clean_name = re.sub(r"_\d{4}\.exr$", "", clean_name)
        clean_name = re.sub(r"_v\d+$", "", clean_name)
        clean_name = os.path.splitext(clean_name)[0]

        debug_print(f"[GetClip] Filename limpio para shot code: {clean_name}")

        # Extraer shot code usando NamingUtils
        shot_code = extract_shot_code(clean_name)
        debug_print(f"[GetClip] Shot code extraído: {shot_code}")

        return shot_code

    except Exception as e:
        debug_print(f"[GetClip] Error extrayendo shot code de {file_path}: {e}")
        return ""


def analyze_multiple_shots_selection(all_selected_clips, track_name=None):
    """
    Analiza selección múltiple inteligente: devuelve exactamente un clip por shot único.
    Prioriza clips del track objetivo, pero incluye shots de otros tracks si no hay correspondencia.

    Args:
        all_selected_clips: Lista de todos los clips seleccionados
        track_name: Nombre del track objetivo (usa TRACK_comp_EXR si None)

    Returns:
        Lista de clips óptimos (uno por shot único)
    """
    if not track_name:
        track_name = TRACK_comp_EXR

    if not all_selected_clips:
        debug_print(f"[GetClip] No hay clips seleccionados para analizar")
        return []

    debug_print(f"[GetClip] === INICIANDO ANÁLISIS MÚLTIPLE ===")
    debug_print(f"[GetClip] Analizando {len(all_selected_clips)} clips seleccionados")
    debug_print(f"[GetClip] Track objetivo: '{track_name}'")

    # Agrupar clips por shot
    shots_dict = {}  # shot_code -> lista de clips para ese shot

    for clip in all_selected_clips:
        if isinstance(clip, hiero.core.EffectTrackItem):
            continue

        shot_code = extract_shot_code_from_clip(clip)
        track_name_clip = clip.parentTrack().name() if clip.parentTrack() else "Unknown"

        if shot_code:
            if shot_code not in shots_dict:
                shots_dict[shot_code] = []
            shots_dict[shot_code].append(clip)
            debug_print(f"[GetClip] Clip '{clip.name()}' -> Shot '{shot_code}' (track: '{track_name_clip}')")
        else:
            debug_print(f"[GetClip] Clip '{clip.name()}' -> Shot NO IDENTIFICADO (track: '{track_name_clip}')")

    debug_print(f"[GetClip] === RESULTADO AGRUPACIÓN ===")
    debug_print(f"[GetClip] Shots únicos encontrados: {len(shots_dict)}")
    for shot_code, clips in shots_dict.items():
        debug_print(f"[GetClip] Shot '{shot_code}': {len(clips)} clips disponibles")

    # Para cada shot, seleccionar el mejor clip
    result_clips = []

    for shot_code, clips_for_shot in shots_dict.items():
        debug_print(f"[GetClip] --- Procesando shot '{shot_code}' ---")

        # Buscar si hay clips de este shot en el track objetivo
        clips_in_target_track = [
            clip for clip in clips_for_shot
            if clip.parentTrack() and clip.parentTrack().name().upper() == track_name.upper()
        ]

        if clips_in_target_track:
            # Usar el primer clip encontrado en el track objetivo (debería ser solo uno)
            selected_clip = clips_in_target_track[0]
            debug_print(f"[GetClip] ✅ Shot '{shot_code}': USANDO clip del track '{track_name}': '{selected_clip.name()}'")
        else:
            # Usar el primer clip disponible para este shot
            selected_clip = clips_for_shot[0]
            track_origen = selected_clip.parentTrack().name() if selected_clip.parentTrack() else "Unknown"
            debug_print(f"[GetClip] 🔄 Shot '{shot_code}': USANDO clip de track '{track_origen}': '{selected_clip.name()}' (sin correspondencia en '{track_name}')")

        result_clips.append(selected_clip)

    debug_print(f"[GetClip] === RESULTADO FINAL ===")
    debug_print(f"[GetClip] Selección múltiple inteligente: {len(result_clips)} clips finales de {len(shots_dict)} shots únicos")

    for i, clip in enumerate(result_clips):
        track_name_clip = clip.parentTrack().name() if clip.parentTrack() else "Unknown"
        shot_code = extract_shot_code_from_clip(clip)
        debug_print(f"[GetClip] Resultado {i+1}: '{clip.name()}' (shot: '{shot_code}', track: '{track_name_clip}')")

    return result_clips


def extract_shot_code_from_clip(clip):
    """
    Extrae el shot code de un clip usando función específica de GetClip.
    Maneja errores gracefully si no hay media o el archivo no existe.

    Args:
        clip: Clip de Hiero

    Returns:
        str: Shot code extraído o cadena vacía si hay error
    """
    try:
        if not clip or not clip.source() or not clip.source().mediaSource():
            debug_print(f"[GetClip] Clip '{clip.name() if clip else 'None'}' no tiene source o mediaSource")
            return ""

        fileinfos = clip.source().mediaSource().fileinfos()
        if not fileinfos:
            debug_print(f"[GetClip] Clip '{clip.name()}' no tiene fileinfos")
            return ""

        filename = fileinfos[0].filename()
        debug_print(f"[GetClip] Procesando filename: {filename}")

        # Usar función específica de GetClip que maneja rutas completas correctamente
        shot_code = extract_shot_code_from_filename(filename)

        return shot_code

    except Exception as e:
        debug_print(f"[GetClip] Error extrayendo shot code del clip '{clip.name() if clip else 'None'}': {e}")
        return ""


def is_clip_at_playhead(clip):
    """
    Verifica si un clip específico está posicionado bajo el playhead actual.

    Args:
        clip: Clip de Hiero a verificar

    Returns:
        bool: True si el clip está bajo el playhead, False en caso contrario
    """
    try:
        viewer = hiero.ui.currentViewer()
        if not viewer:
            debug_print("No se encontró un viewer activo.")
            return False

        current_time = viewer.time()
        if clip.timelineIn() <= current_time < clip.timelineOut():
            debug_print(f"Clip '{clip.name()}' SÍ está bajo el playhead en posición {current_time}")
            return True
        else:
            debug_print(f"Clip '{clip.name()}' NO está bajo el playhead (playhead: {current_time}, clip: {clip.timelineIn()}-{clip.timelineOut()})")
            return False

    except Exception as e:
        debug_print(f"Error verificando si clip está bajo playhead: {e}")
        return False


def find_clip_at_playhead_in_track(seq, track_name=None):
    """
    Busca el clip en un track dado que coincide con la posicion del playhead.
    Evita efectos y devuelve el primer clip que cumpla la condicion o None.

    Args:
        seq: Secuencia activa de Hiero
        track_name (str, optional): Nombre del track a buscar. Si es None, usa TRACK_comp_EXR.

    Returns:
        Clip encontrado o None si no se encuentra.
    """
    if track_name is None:
        track_name = TRACK_comp_EXR
    
    try:
        viewer = hiero.ui.currentViewer()
        if not viewer:
            debug_print("No se encontró un viewer activo.")
            return None
        
        current_time = viewer.time()
        debug_print(f"Buscando clip en track '{track_name}' en posición {current_time}")
        
        for track in seq.videoTracks():
            if track.name().upper() == track_name.upper():
                for clip in track:
                    if isinstance(clip, hiero.core.EffectTrackItem):
                        continue
                    if clip.timelineIn() <= current_time < clip.timelineOut():
                        debug_print(
                            f">>> Clip encontrado en track {track_name} en posicion {current_time}: {clip.name()}"
                        )
                        return clip
                debug_print(f"No se encontró clip en track '{track_name}' en la posición del playhead.")
                return None
        
        debug_print(f"No se encontró el track '{track_name}' en la secuencia.")
        return None
        
    except Exception as e:
        debug_print(f"Error buscando clip por playhead en track {track_name}: {e}")
        return None


def get_selected_clips_in_track(seq, track_name=None):
    """
    Obtiene todos los clips seleccionados que pertenecen al track especificado.
    
    Args:
        seq: Secuencia activa de Hiero
        track_name (str, optional): Nombre del track. Si es None, usa TRACK_comp_EXR.
    
    Returns:
        Lista de clips seleccionados en el track especificado (excluyendo efectos) o lista vacía.
    """
    if track_name is None:
        track_name = TRACK_comp_EXR
    
    te = hiero.ui.getTimelineEditor(seq)
    selected_clips = te.selection() if te else []
    
    # Encontrar el track especificado
    target_track = None
    for track in seq.videoTracks():
        if track.name().upper() == track_name.upper():
            target_track = track
            break
    
    if not target_track:
        debug_print(f"No se encontró el track '{track_name}' en la secuencia.")
        return []
    
    # Filtrar clips seleccionados que pertenecen al track especificado
    clips_in_track = []
    for clip in selected_clips:
        if isinstance(clip, hiero.core.EffectTrackItem):
            continue
        # Verificar si el clip pertenece al track especificado
        if clip.parentTrack() == target_track:
            clips_in_track.append(clip)
    
    return clips_in_track


def get_clip_to_process(track_name=None, prioritize_multiple_selection=False):
    """
    Obtiene el clip a procesar usando el método híbrido inteligente:
    1. LÓGICA INTELIGENTE: Si hay un clip seleccionado fuera del track objetivo pero del mismo shot,
       automáticamente usa el clip del track correcto (sin mensaje informativo al usuario)
    2. Muestra advertencia automática SOLO cuando la lógica inteligente NO puede resolver automáticamente
    3. Si prioritize_multiple_selection=True y hay múltiples clips seleccionados en el track, devuelve lista
    4. Si no, primero intenta obtener el clip del track especificado en la posición del playhead
    5. Si no encuentra, usa el primer clip seleccionado como fallback

    Debe ejecutarse en el hilo principal de Hiero.

    Args:
        track_name (str, optional): Nombre del track a buscar. Si es None, usa TRACK_comp_EXR.
        prioritize_multiple_selection (bool): Si True y hay múltiples clips seleccionados en el track,
            devuelve lista de esos clips en lugar de usar playhead. Si False, usa playhead primero.

    Returns:
        Clip encontrado, lista de clips, o None si no se encuentra ningún clip.
        Si prioritize_multiple_selection=True y hay múltiples clips, siempre devuelve lista.
    """
    if track_name is None:
        track_name = TRACK_comp_EXR
    
    seq = hiero.ui.activeSequence()
    if not seq:
        debug_print("No se encontro una secuencia activa en Hiero.")
        return None

    # Obtener información de selección
    all_selected_clips = get_selected_clips()
    selected_clips_in_track = get_selected_clips_in_track(seq, track_name=track_name)

    # LÓGICA INTELIGENTE PARA SELECCIONES:
    # Si hay un solo clip seleccionado que NO es del track objetivo, verificar si es del mismo shot
    # (se aplica tanto para prioritize_multiple_selection=True como False)
    intelligent_selection_applied = False
    if len(selected_clips_in_track) == 0 and len(all_selected_clips) == 1:
        debug_print("Activando lógica inteligente: un clip seleccionado fuera del track objetivo")
        selected_clip = all_selected_clips[0]

        # Obtener clip del playhead en el track objetivo
        playhead_clip = find_clip_at_playhead_in_track(seq, track_name=track_name)

        if playhead_clip:
            # Comparar shot codes
            selected_shot = extract_shot_code_from_clip(selected_clip)
            playhead_shot = extract_shot_code_from_clip(playhead_clip)

            debug_print(f"Comparando shots - seleccionado: '{selected_shot}', playhead: '{playhead_shot}'")

            if selected_shot and playhead_shot and selected_shot == playhead_shot:
                # 2a: Los shots coinciden, usar el clip del track correcto automáticamente
                debug_print(f"Shots coinciden ({selected_shot}). Usando clip del track '{track_name}' automáticamente.")
                intelligent_selection_applied = True
                if prioritize_multiple_selection:
                    return [playhead_clip]  # Devolver como lista
                else:
                    return playhead_clip
            else:
                # EXCEPCIÓN: Si el clip seleccionado está bajo el playhead, no mostrar advertencia
                # pero aún usar el clip del track objetivo
                if is_clip_at_playhead(selected_clip):
                    debug_print("EXCEPCIÓN: Clip seleccionado está bajo el playhead, usando clip del track objetivo sin advertencia")
                    intelligent_selection_applied = True
                    if prioritize_multiple_selection:
                        return [playhead_clip]  # Devolver como lista
                    else:
                        return playhead_clip
                else:
                    # 2c: Los shots no coinciden y el clip seleccionado no está bajo playhead, mostrar mensaje informativo
                    debug_print(f"Shots diferentes - seleccionado: {selected_shot}, playhead: {playhead_shot}")
                    if _SHOW_WARNINGS:
                        # Importar compatibilidad Qt
                        import sys
                        sys.path.insert(0, r"C:\Users\leg4-pc\.nuke\Python\Startup")
                        from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtCore
                        QMessageBox = QtWidgets.QMessageBox
                        Qt = QtCore.Qt

                        msg_box = QMessageBox()
                        msg_box.setIcon(QMessageBox.Warning)
                        msg_box.setWindowTitle("Shots diferentes")
                        msg_box.setTextFormat(Qt.RichText)
                        msg_box.setText(
                            f"El clip seleccionado pertenece al shot<br>"
                            f"<font color=\"#6AB5CA\">{selected_shot}</font>,<br>"
                            f"pero el playhead está posicionado sobre el shot<br>"
                            f"<font color=\"#6AB5CA\">{playhead_shot}</font> (del track '{track_name}')<br><br>"
                            f"Se usará el clip del track '{track_name}' (playhead)."
                        )
                        msg_box.exec_()
                    if prioritize_multiple_selection:
                        return [playhead_clip]  # Devolver como lista
                    else:
                        return playhead_clip

        # 2b: No hay clip en playhead del track objetivo, usar el seleccionado como fallback
        debug_print(f"No hay clip en playhead del track '{track_name}', usando clip seleccionado como fallback.")
        intelligent_selection_applied = True  # También cuenta como selección inteligente
        if prioritize_multiple_selection:
            return [selected_clip]  # Devolver como lista
        else:
            return selected_clip

    # Si prioritize_multiple_selection=True, aplicar lógica inteligente múltiple
    if prioritize_multiple_selection:
        selected_clips_in_track = get_selected_clips_in_track(seq, track_name=track_name)
        if len(selected_clips_in_track) > 0:
            # Hay al menos un clip seleccionado en el track objetivo
            # Aplicar lógica inteligente múltiple: analizar todos los clips seleccionados
            debug_print(f">>> {len(selected_clips_in_track)} clips seleccionados en track '{track_name}'. Aplicando lógica inteligente múltiple.")
            intelligent_clips = analyze_multiple_shots_selection(all_selected_clips, track_name=track_name)
            return intelligent_clips
        elif len(selected_clips_in_track) == 0 and len(all_selected_clips) > 1:
            # No hay clips en el track objetivo pero hay múltiples clips seleccionados
            # Aplicar lógica inteligente múltiple para clips fuera del track objetivo
            debug_print(f">>> Múltiples clips ({len(all_selected_clips)}) seleccionados fuera del track '{track_name}'. Aplicando lógica inteligente múltiple.")
            intelligent_clips = analyze_multiple_shots_selection(all_selected_clips, track_name=track_name)
            return intelligent_clips
        # Si no hay múltiples clips seleccionados, continuar con lógica normal
        if len(all_selected_clips) == 0:
            debug_print(f"ERROR: No hay clips seleccionados en el timeline")
            return None
        selected_clip = all_selected_clips[0]
        debug_print(f"Solo un clip seleccionado fuera del track '{track_name}': {selected_clip.name()}")

        # Obtener clip del playhead en el track objetivo
        playhead_clip = find_clip_at_playhead_in_track(seq, track_name=track_name)

        if playhead_clip:
            # Comparar shot codes
            selected_shot = extract_shot_code_from_clip(selected_clip)
            playhead_shot = extract_shot_code_from_clip(playhead_clip)

            if selected_shot and playhead_shot and selected_shot == playhead_shot:
                # 2a: Los shots coinciden, usar el clip del track correcto automáticamente
                debug_print(f"Shots coinciden ({selected_shot}). Usando clip del track '{track_name}' en lugar del seleccionado.")
                intelligent_selection_applied = True
                if prioritize_multiple_selection:
                    return [playhead_clip]  # Devolver como lista
                else:
                    return playhead_clip
            else:
                # 2c: Los shots no coinciden, mostrar mensaje informativo
                debug_print(f"Shots diferentes - seleccionado: {selected_shot}, playhead: {playhead_shot}")
                if _SHOW_WARNINGS:
                    # Importar compatibilidad Qt
                    import sys
                    sys.path.insert(0, r"C:\Users\leg4-pc\.nuke\Python\Startup")
                    from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets
                    QMessageBox = QtWidgets.QMessageBox
                    QMessageBox.warning(
                        None,
                        "Shots diferentes",
                        f"El clip seleccionado pertenece al shot '{selected_shot}',\n"
                        f"pero el playhead está posicionado sobre el shot '{playhead_shot}' en el track '{track_name}'.\n\n"
                        f"Se usará el clip del track '{track_name}' (playhead)."
                    )
                intelligent_selection_applied = True  # También resuelve automáticamente
                if prioritize_multiple_selection:
                    return [playhead_clip]  # Devolver como lista
                else:
                    return playhead_clip

        # 2b: No hay clip en playhead del track objetivo, usar el seleccionado como fallback
        debug_print(f"No hay clip en playhead del track '{track_name}', usando clip seleccionado como fallback.")
        intelligent_selection_applied = True  # También cuenta como selección inteligente
        if prioritize_multiple_selection:
            return [selected_clip]  # Devolver como lista
        else:
            return selected_clip

    # Verificar si hay clips seleccionados en otros tracks y mostrar advertencia
    # (solo si la lógica inteligente no resolvió el problema automáticamente)
    if not intelligent_selection_applied and len(all_selected_clips) > len(selected_clips_in_track) and _SHOW_WARNINGS:
        clips_in_other_tracks = len(all_selected_clips) - len(selected_clips_in_track)
        # Importar compatibilidad Qt
        import sys
        sys.path.insert(0, r"C:\Users\leg4-pc\.nuke\Python\Startup")
        from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets
        QMessageBox = QtWidgets.QMessageBox
        QMessageBox.information(
            None,
            "Selección filtrada por track",
            f"Se detectaron {clips_in_other_tracks} clip(s) seleccionado(s) en tracks que no son '{track_name}'.\n\n"
            f"Solo se procesarán los clips seleccionados en el track '{track_name}'."
        )

    # Intentar obtener clip por playhead en el track especificado (lógica normal)
    playhead_clip = find_clip_at_playhead_in_track(seq, track_name=track_name)

    # Fallback a seleccion
    if not playhead_clip:
        te = hiero.ui.getTimelineEditor(seq)
        selected_clips = te.selection() if te else []
        if selected_clips:
            # Tomar el primer clip seleccionado que no sea un efecto
            for clip in selected_clips:
                if not isinstance(clip, hiero.core.EffectTrackItem):
                    debug_print(
                        f">>> No hay clip en playhead sobre track '{track_name}'; usando clip seleccionado como fallback: {clip.name()}"
                    )
                    return clip
        debug_print("No se encontró clip en playhead ni clips seleccionados.")
    else:
        debug_print(
            f">>> Usando clip del playhead en track '{track_name}': {playhead_clip.name()}"
        )

    return playhead_clip


def get_clips_to_process(track_name=None, prioritize_multiple_selection=False):
    """
    Obtiene los clips a procesar usando el método híbrido inteligente.
    Siempre devuelve una lista (puede contener 0, 1 o más clips).

    Args:
        track_name (str, optional): Nombre del track a buscar. Si es None, usa TRACK_comp_EXR.
        prioritize_multiple_selection (bool): Si True y hay múltiples clips seleccionados en el track,
            prioriza esos clips sobre el playhead.

    Returns:
        Lista de clips encontrados (puede estar vacía).
    """
    debug_print(f"get_clips_to_process llamado con track_name={track_name}, prioritize_multiple_selection={prioritize_multiple_selection}")
    result = get_clip_to_process(track_name=track_name, prioritize_multiple_selection=prioritize_multiple_selection)

    # Si el resultado es una lista, devolverla directamente
    if isinstance(result, list):
        debug_print(f"Resultado es lista con {len(result)} clips")
        return result

    # Si es un clip único, devolverlo en una lista
    if result is not None:
        debug_print(f"Resultado es un clip único: {result.name() if hasattr(result, 'name') else result}")
        return [result]

    # Si es None, devolver lista vacía
    debug_print("Resultado es None, devolviendo lista vacía")
    return []


def get_selected_clips():
    """
    Obtiene todos los clips seleccionados en el timeline.
    
    Returns:
        Lista de clips seleccionados (excluyendo efectos) o lista vacía.
    """
    seq = hiero.ui.activeSequence()
    if not seq:
        debug_print("No se encontro una secuencia activa en Hiero.")
        return []
    
    te = hiero.ui.getTimelineEditor(seq)
    selected_clips = te.selection() if te else []
    
    # Filtrar efectos
    valid_clips = [
        clip for clip in selected_clips 
        if not isinstance(clip, hiero.core.EffectTrackItem)
    ]
    
    return valid_clips
