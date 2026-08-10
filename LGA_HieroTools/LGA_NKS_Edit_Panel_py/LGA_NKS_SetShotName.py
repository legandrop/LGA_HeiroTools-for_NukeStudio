"""
____________________________________________________________________

  LGA_NKS_SetShotName v1.00 | Lega

  Script para establecer nombres de shots basado en rutas de archivos.
____________________________________________________________________

"""

import hiero.ui
import hiero.core
import os
import sys
from pathlib import Path

# Variable global para activar o desactivar los prints
DEBUG = False

def debug_print(*message):
    if DEBUG:
        print(*message)

# Importar utilidades de naming centralizadas
naming_utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if naming_utils_path.exists():
    sys.path.insert(0, str(naming_utils_path))
    try:
        from LGA_NKS_Flow_NamingUtils import (
            extract_shot_code,
            clean_base_name,
        )
        HAS_NAMING_UTILS = True
    except ImportError:
        HAS_NAMING_UTILS = False
        debug_print("Warning: No se pudo importar LGA_NKS_Flow_NamingUtils")
else:
    HAS_NAMING_UTILS = False

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

def get_shot_name_fallback(file_path):
    """
    Método fallback para extraer el shot name cuando no está disponible
    el módulo centralizado. Usa el método anterior basado en la posición
    del path (tercera parte).
    """
    try:
        # Dividir el path en partes usando '/' como separador
        path_parts = file_path.split("/")
        # El shot name seria la tercera parte del path (índice 3)
        if len(path_parts) > 3:
            shot_name = path_parts[3]
            return shot_name
        else:
            debug_print(f"Warning: Path no tiene suficientes partes: {file_path}")
            return None
    except Exception as e:
        debug_print(f"Error en get_shot_name_fallback: {e}")
        return None

def set_shot_name():
    """
    Establece el nombre del shot basándose en la ruta del archivo.
    Usa el módulo centralizado LGA_NKS_Flow_NamingUtils para detectar
    automáticamente el formato de nomenclatura (con o sin descripción).
    Compatible con ambos sistemas:
    - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
    - PROYECTO_SEQ_SHOT (3 bloques simplificado)
    """
    try:
        project = get_active_project()
        if not project:  # Comprobacion de proyecto activo
            debug_print("No active project found for Set Shot Name.")
            return

        with project.beginUndo("Set Shot Name"):
            seq = hiero.ui.activeSequence()
            if not seq:
                debug_print("No active sequence found.")
                return

            te = hiero.ui.getTimelineEditor(seq)
            selected_clips = te.selection()

            if len(selected_clips) == 0:
                debug_print("*** No clips selected on the track ***")
            else:
                for shot in selected_clips:
                    try:
                        # Obtener el file path del clip seleccionado
                        file_path = (
                            shot.source().mediaSource().fileinfos()[0].filename()
                        )
                        debug_print("Original file path:", file_path)

                        # Extraer el nombre del archivo del path completo
                        file_name = os.path.basename(file_path)
                        debug_print("File name:", file_name)

                        # Usar el módulo centralizado si está disponible
                        if HAS_NAMING_UTILS:
                            # Limpiar el nombre del archivo (remover extensión y versión)
                            base_name = clean_base_name(file_name)
                            debug_print("Base name (cleaned):", base_name)

                            # Extraer el shot code usando detección automática de formato
                            shot_name = extract_shot_code(base_name)
                            debug_print("Shot name (extracted):", shot_name)
                        else:
                            # Fallback al método anterior si no hay módulo centralizado
                            debug_print("Warning: Usando método fallback para extraer shot name")
                            shot_name = get_shot_name_fallback(file_path)

                        # Cambiar el nombre del plano al clip seleccionado
                        if shot_name:
                            shot.setName(shot_name)
                            debug_print("Shot name changed successfully.")
                        else:
                            debug_print("Warning: No se pudo extraer el shot name")
                    except Exception as e:
                        debug_print(f"Error procesando clip {shot.name()}: {e}")
    except Exception as e:
        debug_print(f"Error: {e}")

def main():
    """Función principal que ejecuta set_shot_name."""
    set_shot_name()

if __name__ == "__main__":
    main()
