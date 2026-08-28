"""
____________________________________________________________________

  LGA_NKS_Flow_ShotPriority v1.02 | Lega

  Script para cambiar la prioridad de shots en ShotGrid basado en el clip seleccionado.
  - Si la prioridad es normal (o no existe) → cambia a alta
  - Si la prioridad es alta → cambia a normal
  Usa el método híbrido centralizado de selección de clips.
  Compatible con ambos sistemas de nomenclatura:
  - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
  - PROYECTO_SEQ_SHOT (3 bloques simplificado)

  v1.02: Los carteles de aviso pasan al helper LGA_NKS_MessageBox con el
         estilo del pack.
  v1.01: Extrae project_name desde el segmento VFX-NOMBRE del path en lugar
         del primer bloque del filename (corrige proyectos como PROJALT cuyos
         shots tienen prefijo PROJA en el filename).
____________________________________________________________________
"""

import hiero.core
import os
import sys
from pathlib import Path
from LGA_NKS_Shared.LGA_QtAdapter_HieroTools import QtWidgets, QtGui, QtCore, Qt
from LGA_NKS_Shared.LGA_NKS_MessageBox import show_info, show_warning
QMessageBox = QtWidgets.QMessageBox
QApplication = QtWidgets.QApplication

# Agregar la ruta de shotgun_api3 al sys.path
shared_dir = Path(__file__).parent.parent / "LGA_NKS_Shared"
sys.path.insert(0, str(shared_dir))
import shotgun_api3

# Importar el modulo de configuracion segura
sys.path.append(str(shared_dir))
from SecureConfig_Reader import get_flow_credentials

# Importar utilidades de naming
from LGA_NKS_Flow_NamingUtils import (
    extract_shot_code,
    extract_project_name,
    extract_project_name_from_path,
    clean_base_name,
)

# Importar módulo centralizado para obtener clips
utils_path = Path(__file__).parent.parent / "LGA_NKS_Shared"
if utils_path.exists():
    sys.path.insert(0, str(utils_path))
    from LGA_NKS_Shared.LGA_NKS_GetClip import get_clips_to_process


DEBUG = False


def debug_print(message):
    """Imprime un mensaje de debug si la variable DEBUG es True."""
    if DEBUG:
        print(message)


class ShotGridManager:
    """Clase para manejar operaciones de prioridad en ShotGrid."""

    def __init__(self, url, login, password):
        debug_print("Inicializando conexion a ShotGrid para cambiar prioridad")
        try:
            self.sg = shotgun_api3.Shotgun(url, login=login, password=password)
            debug_print("Conexion a ShotGrid inicializada exitosamente")
        except Exception as e:
            debug_print(f"Error al inicializar la conexion a ShotGrid: {e}")
            self.sg = None

    def find_shot(self, project_name, shot_code):
        """Encuentra el shot en ShotGrid."""
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return None

        projects = self.sg.find(
            "Project", [["name", "is", project_name]], ["id", "name"]
        )
        if not projects:
            debug_print(f"No se encontro el proyecto '{project_name}' en ShotGrid.")
            return None

        project_id = projects[0]["id"]
        filters = [
            ["project", "is", {"type": "Project", "id": project_id}],
            ["code", "is", shot_code],
        ]
        fields = ["id", "code", "sg_prioridad"]
        shots = self.sg.find("Shot", filters, fields)
        
        if shots:
            return shots[0]
        else:
            debug_print(f"No se encontro el shot '{shot_code}' en el proyecto '{project_name}'.")
            return None

    def toggle_shot_priority(self, shot_id):
        """Cambia la prioridad del shot: high -> normal, normal/None -> high.
        Retorna: (nueva_prioridad, mensaje)"""
        if not self.sg:
            debug_print("Conexion a ShotGrid no esta inicializada")
            return None, "Error: Conexión a ShotGrid no inicializada"

        try:
            # Obtener shot actual para ver su prioridad
            shot = self.sg.find_one("Shot", [["id", "is", shot_id]], ["sg_prioridad"])
            if not shot:
                return None, f"Error: No se encontró el shot con ID {shot_id}"

            current_priority = shot.get("sg_prioridad")
            debug_print(f"Prioridad actual: {current_priority}")

            # Determinar nueva prioridad
            if current_priority == "high":
                new_priority = None  # None = normal en ShotGrid
                message = "Prioridad cambiada de ALTA a NORMAL"
            else:
                new_priority = "high"
                message = "Prioridad cambiada de NORMAL a ALTA"

            # Actualizar prioridad
            update_data = {"sg_prioridad": new_priority}
            self.sg.update("Shot", shot_id, update_data)
            debug_print(f"Prioridad actualizada a: {new_priority}")

            return new_priority, message

        except Exception as e:
            debug_print(f"ERROR al cambiar prioridad: {e}")
            return None, f"Error al cambiar prioridad: {str(e)}"


class HieroOperations:
    """Clase para manejar operaciones en Hiero."""

    def get_selected_clips_info(self):
        """Obtiene informacion de los clips usando el método híbrido centralizado.
        Permite selección múltiple: si hay múltiples clips seleccionados en el track,
        procesa todos ellos. Si no, usa el clip del playhead."""
        seq = hiero.ui.activeSequence()
        if not seq:
            debug_print("No se encontro una secuencia activa en Hiero.")
            return []

        # Usar módulo centralizado con selección múltiple habilitada
        # track_name=None para respetar TRACK_comp_EXR del módulo
        clips = get_clips_to_process(track_name=None, prioritize_multiple_selection=True)

        if not clips:
            debug_print("No se encontraron clips para procesar (ni en playhead ni seleccionados).")
            return []

        clips_info = []
        for clip in clips:
            try:
                file_path = clip.source().mediaSource().fileinfos()[0].filename()
                exr_name = os.path.basename(file_path)
                base_name = clean_base_name(exr_name)

                # Usar funciones de naming utils para extraer información
                project_name = extract_project_name_from_path(file_path)
                if project_name:
                    debug_print(f"Project name (from path): {project_name}")
                else:
                    project_name = extract_project_name(base_name)
                    debug_print(f"Project name (from filename fallback): {project_name}")
                shot_code = extract_shot_code(base_name)

                clips_info.append(
                    {
                        "base_name": base_name,
                        "project_name": project_name,
                        "shot_code": shot_code,
                    }
                )
            except Exception as e:
                debug_print(f"Error procesando clip {clip.name()}: {e}")
                continue

        return clips_info


def get_flow_credentials_secure():
    """Obtiene las credenciales de Flow de forma segura."""
    sg_url, sg_login, sg_password = get_flow_credentials()
    if not sg_url or not sg_login or not sg_password:
        debug_print("No se pudieron obtener las credenciales de Flow desde SecureConfig.")
        return None, None, None

    # Para Flow, usamos login directo en lugar de API key
    return sg_url, sg_login, sg_password


def toggle_shot_priority_from_selected_clip():
    """
    Función principal del script de cambio de prioridad.
    Obtiene el clip seleccionado, encuentra el shot en ShotGrid y cambia su prioridad.
    """
    debug_print("=== Iniciando LGA_NKS_Flow_ShotPriority ===")

    # Crear aplicación Qt si no existe
    app = QApplication.instance()
    if app is None:
        app = QApplication([])

    # Obtener información de clips
    hiero_ops = HieroOperations()
    clips_info = hiero_ops.get_selected_clips_info()

    if not clips_info:
        show_warning(
            None, "Error", "No se encontraron clips seleccionados en Hiero."
        )
        return

    # Obtener credenciales de Flow
    sg_url, sg_login, sg_password = get_flow_credentials_secure()
    if not all([sg_url, sg_login, sg_password]):
        show_warning(
            None,
            "Error",
            "No se pudieron obtener las credenciales de Flow desde SecureConfig.",
        )
        return

    # Crear manager ShotGrid
    sg_manager = ShotGridManager(sg_url, sg_login, sg_password)
    if not sg_manager.sg:
        show_warning(
            None, "Error", "No se pudo inicializar la conexión a ShotGrid."
        )
        return

    # Procesar cada clip
    results = []
    for clip_info in clips_info:
        project_name = clip_info["project_name"]
        shot_code = clip_info["shot_code"]

        # Buscar shot en ShotGrid
        shot = sg_manager.find_shot(project_name, shot_code)
        if not shot:
            results.append(
                {
                    "shot_code": shot_code,
                    "project_name": project_name,
                    "success": False,
                    "message": f"Shot '{shot_code}' no encontrado en proyecto '{project_name}'",
                }
            )
            continue

        # Cambiar prioridad
        new_priority, message = sg_manager.toggle_shot_priority(shot["id"])
        if new_priority is not None:
            results.append(
                {
                    "shot_code": shot_code,
                    "project_name": project_name,
                    "success": True,
                    "message": message,
                }
            )
        else:
            results.append(
                {
                    "shot_code": shot_code,
                    "project_name": project_name,
                    "success": False,
                    "message": message,
                }
            )

    # Mostrar resultados
    if len(results) == 1:
        # Un solo shot: mostrar mensaje simple
        result = results[0]
        if result["success"]:
            show_info(
                None,
                "Prioridad Cambiada",
                f"Shot: {result['shot_code']}\n{result['message']}",
            )
        else:
            show_warning(None, "Error", result["message"])
    else:
        # Múltiples shots: mostrar resumen
        success_count = sum(1 for r in results if r["success"])
        total_count = len(results)

        if success_count == total_count:
            # Todos exitosos
            message = f"Se cambiaron las prioridades de {success_count} shots:\n\n"
            for result in results:
                message += f"• {result['shot_code']}: {result['message']}\n"
            show_info(None, "Prioridades Cambiadas", message)
        else:
            # Algunos fallaron
            message = f"Resultados ({success_count}/{total_count} exitosos):\n\n"
            for result in results:
                status = "✓" if result["success"] else "✗"
                message += f"{status} {result['shot_code']}: {result['message']}\n"
            show_warning(None, "Resultados", message)


def main():
    """Función principal para compatibilidad hacia atrás."""
    toggle_shot_priority_from_selected_clip()


if __name__ == "__main__":
    main()
