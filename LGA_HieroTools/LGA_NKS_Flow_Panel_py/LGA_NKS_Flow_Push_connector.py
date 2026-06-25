"""
____________________________________________________________________

  LGA_NKS_Flow_Push_connector v1.01 | Lega

  Conector simple para operaciones de red con Flow
  Este script se ejecuta con Python personalizado para evitar problemas de dependencias
  Actualizado para ser compatible con múltiples sistemas de nomenclatura:
  - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
  - PROYECTO_SEQ_SHOT (3 bloques simplificado)
  - PROYECTO_TEMP_EP_SEQ_SHOT_DESC1_DESC2 (6 bloques con descripción)
  - PROYECTO_TEMP_EP_SEQ_SHOT (4 bloques simplificado)

  v1.01: project_name desde segmento de ruta "VFX-NOMBRE" (fallback al filename).
         normalize_task_name resuelve aliases ("compo"→"comp") para búsquedas en Flow.
         find_highest/specific_version_for_shot incluye aliases inversos en task_tokens.
         file_path se recibe desde el Worker vía JSON para ambas operaciones.
____________________________________________________________________

"""

import os
import re
import sys
import tempfile
import shutil
from pathlib import Path

# Agregar la ruta de shotgun_api3 al sys.path
script_dir = os.path.dirname(__file__)
parent_dir = os.path.dirname(script_dir)  # Un nivel arriba
shared_dir = os.path.join(parent_dir, "LGA_NKS_Shared")
shotgun_path = os.path.join(shared_dir, "shotgun_api3")

# Intentar primero un nivel arriba (ubicación correcta)
if os.path.exists(shotgun_path):
    sys.path.insert(0, shotgun_path)
else:
    # Fallback: buscar en el mismo directorio del script (por compatibilidad)
    shotgun_path_local = os.path.join(script_dir, "shotgun_api3")
    if os.path.exists(shotgun_path_local):
        sys.path.insert(0, shotgun_path_local)

import shotgun_api3


# Variable global para activar o desactivar los prints
DEBUG = False


def debug_print(message):
    """
    Imprime mensajes de debug a stderr para no interferir con el JSON de respuesta
    que se envía por stdout
    """
    if DEBUG:
        print(message, file=sys.stderr)


# Importar utilidades de naming desde shareds globales
flow_shared_dir = shared_dir
sys.path.insert(0, flow_shared_dir)
try:
    from LGA_NKS_Flow_NamingUtils import (
        extract_shot_code,
        extract_project_name,
        extract_project_name_from_path,
        extract_task_name,
        normalize_task_name,
        TASK_NAME_ALIASES,
    )
    debug_print("✅ Usando funciones del módulo LGA_NKS_Flow_NamingUtils")
except ImportError as e:
    debug_print(f"⚠️ ImportError: {e} - Usando funciones fallback")
    # Fallback si no se puede importar (por si acaso)
    # Implementa la misma lógica que LGA_NKS_Flow_NamingUtils.py
except ImportError:
    # Fallback si no se puede importar (por si acaso)
    # Implementa la misma lógica que LGA_NKS_Flow_NamingUtils.py

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

    def detect_shotname_format(base_name):
        """
        Detecta si el shotname contiene descripción (5/6 bloques).
        """
        core_parts, _, has_description, _ = _analyze_shotname(base_name)
        if not core_parts:
            return False
        return has_description

    def extract_shot_code(base_name):
        """
        Extrae el shot_code detectando automáticamente formato y serie.
        """
        core_parts, _, has_description, base_count = _analyze_shotname(base_name)
        if not core_parts:
            return ""

        desc_count = 2 if has_description else 0
        target_count = base_count + desc_count
        if len(core_parts) >= target_count:
            return "_".join(core_parts[:target_count])

        return "_".join(core_parts)

    def extract_project_name(base_name):
        return base_name.split("_")[0] if base_name else ""

    def extract_task_name(base_name):
        """
        Extrae el nombre de la tarea del nombre base del archivo.
        """
        core_parts, _, has_description, base_count = _analyze_shotname(base_name)
        if not core_parts:
            return None

        task_index = base_count + (2 if has_description else 0)
        if len(core_parts) > task_index:
            return core_parts[task_index]

        return None
        return None


# Diccionario de traduccion de estados (igual que en el script principal)
status_translation = {
    "Corrections": "corr",
    "Corrs_Lega": "revleg",
    "Rev Sebas": "rev_su",
    "Rev Charly": "revcha",
    "Rev Juano": "revjua",
    "Rev Javi": "revjav",
    "Rev Lega": "revleg",
    "Rev Dir": "rev_di",
    "Approved": "apr",
    "Delivery Ok": "check",
    "Rev Dir Den": "rev_di",
    "Rev Hold": "revhld",
}


class ShotGridManager:
    def __init__(self, url, login, password):
        debug_print("Inicializando conexion a ShotGrid")
        try:
            self.sg = shotgun_api3.Shotgun(url, login=login, password=password)
            debug_print("Conexion a ShotGrid inicializada exitosamente")
        except Exception as e:
            debug_print(f"Error al inicializar la conexion a ShotGrid: {e}")
            self.sg = None

    def find_shot_and_tasks(self, project_name, shot_code):
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return None, None, None
        debug_print(f"Buscando proyecto con nombre: {project_name}")
        try:
            projects = self.sg.find(
                "Project", [["name", "is", project_name]], ["id", "name"]
            )
        except Exception as e:
            debug_print(f"Error buscando proyecto: {e}")
            return None, None, None
        if projects:
            project = projects[0]
            project_id = project["id"]
            debug_print(f"Proyecto encontrado: {project['name']} (ID: {project_id})")
            debug_print(f"DEBUG: Buscando shot con código exacto: '{shot_code}'")
            filters = [
                ["project", "is", {"type": "Project", "id": project_id}],
                ["code", "is", shot_code],
            ]
            fields = ["id", "code", "description"]
            try:
                shots = self.sg.find("Shot", filters, fields)
                debug_print(f"DEBUG: Consulta ShotGrid devolvió {len(shots)} resultados")
                for i, shot in enumerate(shots):
                    debug_print(f"DEBUG: Shot encontrado [{i}]: '{shot['code']}' (ID: {shot['id']})")
            except Exception as e:
                debug_print(f"Error buscando shot: {e}")
                return project, None, None
            if shots:
                # Si hay múltiples shots con el mismo nombre, tomar el primero
                if len(shots) > 1:
                    debug_print(
                        f"Múltiples shots encontrados ({len(shots)}) para el código: {shot_code}, usando el primero"
                    )

                shot = shots[0]
                shot_id = shot["id"]
                debug_print(f"Shot encontrado: {shot['code']} (ID: {shot_id})")
                tasks = self.find_tasks_for_shot(shot_id)
                return project, shot, tasks
            else:
                debug_print(f"DEBUG: No se encontró ningún shot con el código: '{shot_code}'")
                return project, None, None
        else:
            debug_print("No se encontro el proyecto con el nombre especificado.")
            return None, None, None

    def find_tasks_for_shot(self, shot_id):
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return []
        filters = [["entity", "is", {"type": "Shot", "id": shot_id}]]
        fields = ["id", "content", "sg_status_list"]
        try:
            return self.sg.find("Task", filters, fields)
        except Exception as e:
            debug_print(f"Error buscando tareas para shot_id {shot_id}: {e}")
            return []

    def find_highest_version_for_shot(self, shot_id, task_name="comp"):
        """
        Busca la versión más alta para un shot filtrando por la task indicada.
        Para 'comp' también acepta el alias '_cmp_'.
        """
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return None, None, None
        filters = [["entity", "is", {"type": "Shot", "id": shot_id}]]
        fields = ["code", "created_at", "user", "sg_status_list", "description"]
        try:
            versions = self.sg.find("Version", filters, fields)
        except Exception as e:
            debug_print(f"Error buscando versiones para shot_id {shot_id}: {e}")
            return None, None, None

        task_tokens = [f"_{task_name}_"]
        if task_name == "comp":
            task_tokens.append("_cmp_")
        # Aliases inversos: versiones publicadas con nombre alternativo (ej: "_compo_" para task "comp")
        for alias, canonical in TASK_NAME_ALIASES.items():
            if canonical == task_name:
                task_tokens.append(f"_{alias}_")

        matching_versions = [
            v for v in versions
            if any(t in v["code"].lower() for t in task_tokens)
        ]
        if matching_versions:

            def safe_version_num(v):
                m = re.search(r"_v(\d+)", v["code"])
                return int(m.group(1)) if m else -1

            highest_version = max(matching_versions, key=safe_version_num)
            m = re.search(r"_v(\d+)", highest_version["code"])
            version_number = m.group(1) if m else "0"
            user_id = (
                highest_version["user"]["id"]
                if highest_version.get("user") and highest_version["user"].get("id")
                else None
            )
            return highest_version, version_number, user_id
        return None, None, None

    def find_specific_version_for_shot(self, shot_id, version_number, task_name="comp"):
        """
        Busca una versión específica por número de versión para un shot, filtrando por task.
        Para 'comp' también acepta el alias '_cmp_'.

        Args:
            shot_id: ID del shot en ShotGrid
            version_number: Número de versión (ej: 13 para v013)
            task_name: task a buscar ('comp'/'roto'/'cleanup'). Default 'comp'.

        Returns:
            Tupla (version, version_number_str, user_id) o (None, None, None) si no se encuentra
        """
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return None, None, None
        filters = [["entity", "is", {"type": "Shot", "id": shot_id}]]
        fields = ["code", "created_at", "user", "sg_status_list", "description"]
        try:
            versions = self.sg.find("Version", filters, fields)
        except Exception as e:
            debug_print(f"Error buscando versiones para shot_id {shot_id}: {e}")
            return None, None, None

        task_tokens = [f"_{task_name}_"]
        if task_name == "comp":
            task_tokens.append("_cmp_")
        # Aliases inversos: versiones publicadas con nombre alternativo (ej: "_compo_" para task "comp")
        for alias, canonical in TASK_NAME_ALIASES.items():
            if canonical == task_name:
                task_tokens.append(f"_{alias}_")

        version_pattern = re.compile(r"_v(\d+)", re.IGNORECASE)
        matching_versions = []

        for v in versions:
            code_lower = v["code"].lower()
            if any(t in code_lower for t in task_tokens):
                match = version_pattern.search(v["code"])
                if match:
                    v_num = int(match.group(1))
                    if v_num == version_number:
                        matching_versions.append(v)

        if matching_versions:
            specific_version = matching_versions[0]
            m = re.search(r"_v(\d+)", specific_version["code"])
            version_number_str = m.group(1) if m else str(version_number)
            user_id = (
                specific_version["user"]["id"]
                if specific_version.get("user") and specific_version["user"].get("id")
                else None
            )
            debug_print(
                f"Versión específica encontrada: {specific_version['code']} (ID: {specific_version['id']})"
            )
            return specific_version, version_number_str, user_id

        debug_print(
            f"No se encontró versión específica v{version_number:02d} para task '{task_name}' en shot_id {shot_id}"
        )
        return None, None, None

    def list_versions_for_task(self, shot_id, task_name="comp"):
        """
        Lista versiones de un shot filtradas por task, incluyendo uploader y fecha.
        Útil para selector de versión destino en Shift+Click.
        """
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return []

        filters = [["entity", "is", {"type": "Shot", "id": shot_id}]]
        fields = ["id", "code", "created_at", "user", "sg_status_list", "description"]
        try:
            versions = self.sg.find("Version", filters, fields)
        except Exception as e:
            debug_print(f"Error listando versiones para shot_id {shot_id}: {e}")
            return []

        task_tokens = [f"_{task_name}_"]
        if task_name == "comp":
            task_tokens.append("_cmp_")
        for alias, canonical in TASK_NAME_ALIASES.items():
            if canonical == task_name:
                task_tokens.append(f"_{alias}_")

        version_pattern = re.compile(r"_v(\d+)", re.IGNORECASE)
        out = []
        for version in versions:
            code = version.get("code") or ""
            code_lower = code.lower()
            if not any(token in code_lower for token in task_tokens):
                continue

            match = version_pattern.search(code)
            if not match:
                continue

            version_number = int(match.group(1))
            created_at = version.get("created_at")
            if hasattr(created_at, "isoformat"):
                created_at = created_at.isoformat()
            user_name = (
                version.get("user", {}).get("name")
                if isinstance(version.get("user"), dict)
                else ""
            )

            out.append(
                {
                    "id": version.get("id"),
                    "code": code,
                    "version_number": version_number,
                    "version_label": f"v{version_number:03d}",
                    "user_name": user_name or "Desconocido",
                    "created_at": created_at or "",
                }
            )

        out.sort(key=lambda item: item.get("version_number", -1), reverse=True)
        debug_print(
            f"list_versions_for_task: shot_id={shot_id}, task={task_name}, versiones={len(out)}"
        )
        return out

    def update_task_status(self, task_id, new_status):
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return
        try:
            debug_print(
                f"Actualizando estado de la tarea (ID: {task_id}) a: {new_status}"
            )
            self.sg.update("Task", task_id, {"sg_status_list": new_status})
        except Exception as e:
            debug_print(f"Error al actualizar el estado de la tarea: {e}")

    def update_version_status(self, project_name, shot_code, version_str, new_status):
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return
        try:
            debug_print(
                f"Actualizando estado de la version para el Shot: {shot_code}, Version: {version_str} a: {new_status}"
            )
            filters = [
                ["project.Project.name", "is", project_name],
                ["entity.Shot.code", "is", shot_code],
                ["code", "contains", version_str],
            ]
            versions = self.sg.find("Version", filters, ["id"])
            for version in versions:
                debug_print(
                    f"Actualizando version (ID: {version['id']}) a estado: {new_status}"
                )
                self.sg.update("Version", version["id"], {"sg_status_list": new_status})
        except Exception as e:
            debug_print(f"Error al actualizar el estado de la version: {e}")

    def get_task_assignees(self, task_id):
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return []
        try:
            task = self.sg.find_one("Task", [["id", "is", task_id]], ["task_assignees"])
            assignee_ids = []
            if task and task.get("task_assignees"):
                for assignee in task["task_assignees"]:
                    assignee_id = assignee.get("id")
                    if assignee_id and assignee_id not in assignee_ids:
                        assignee_ids.append(assignee_id)
            return assignee_ids
        except Exception as e:
            debug_print(f"Error al obtener los asignados de la tarea: {e}")
            return []

    def get_task_assignee(self, task_id):
        # Compatibilidad con callers legacy.
        assignees = self.get_task_assignees(task_id)
        return assignees[0] if assignees else None

    def add_comment_to_version(
        self, version_id, project_id, comment, user_id, task_assignee_ids=None, shot_id=None
    ):
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return
        try:
            debug_print(
                f"Agregando comentario a la version (ID: {version_id}): {comment}"
            )
            recipient_ids = []
            if user_id:
                recipient_ids.append(user_id)

            for assignee_id in task_assignee_ids or []:
                if assignee_id and assignee_id not in recipient_ids:
                    recipient_ids.append(assignee_id)

            addressings_to = [{"type": "HumanUser", "id": rid} for rid in recipient_ids]
            note_links = [{"type": "Version", "id": version_id}]
            if shot_id:
                note_links.append({"type": "Shot", "id": shot_id})

            note_data = {
                "project": {"type": "Project", "id": project_id},
                "content": comment,
                "note_links": note_links,
                "addressings_to": addressings_to,
            }
            created_note = self.sg.create("Note", note_data)
            return created_note
        except Exception as e:
            debug_print(f"Error al agregar comentario a la version: {e}")
            return None

    def attach_images_to_note(self, note_id, version_id, image_paths):
        """
        Adjunta imagenes a una nota con numeros de frame siguiendo la convencion de ShotGrid.
        Usa upload directo a Note que es el metodo mas simple y efectivo.
        """
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return False

        try:
            debug_print(
                f"=== attach_images_to_note: Iniciando proceso de adjuntar imágenes ==="
            )
            debug_print(
                f"attach_images_to_note: Nota ID: {note_id}, Versión ID: {version_id}"
            )
            debug_print(
                f"attach_images_to_note: Total de imágenes recibidas: {len(image_paths)}"
            )

            # Crear una carpeta temporal para los archivos renombrados
            temp_dir = tempfile.mkdtemp()
            debug_print(f"attach_images_to_note: Carpeta temporal creada: {temp_dir}")

            attached_count = 0
            failed_count = 0
            failed_images = []

            for idx, image_path in enumerate(image_paths, 1):
                debug_print(
                    f"--- Procesando imagen [{idx}/{len(image_paths)}]: {os.path.basename(image_path)} ---"
                )

                if not os.path.exists(image_path):
                    debug_print(
                        f"❌ ERROR: Imagen [{idx}] NO EXISTE en disco: {image_path}"
                    )
                    failed_count += 1
                    failed_images.append(f"[{idx}] {image_path} (no existe)")
                    continue

                # Extraer numero de frame del nombre del archivo
                frame_number = self.extract_frame_number_from_path(image_path)
                debug_print(f"  Frame extraído: {frame_number}")

                # Crear nombre de archivo con convencion de ShotGrid para mostrar frame number
                # Formato: annot_version_<version_id>.<frame_number>.jpg
                file_extension = os.path.splitext(image_path)[1]
                new_filename = (
                    f"annot_version_{version_id}.{frame_number}{file_extension}"
                )
                temp_file_path = os.path.join(temp_dir, new_filename)
                debug_print(f"  Nombre temporal: {new_filename}")

                # Copiar archivo con el nuevo nombre
                try:
                    shutil.copy2(image_path, temp_file_path)
                    debug_print(f"  ✓ Archivo copiado a carpeta temporal")
                except Exception as copy_error:
                    debug_print(f"  ❌ ERROR copiando archivo: {copy_error}")
                    failed_count += 1
                    failed_images.append(
                        f"[{idx}] {image_path} (error al copiar: {copy_error})"
                    )
                    continue

                # Subir archivo directamente a la nota usando el metodo que funciono en exploracion
                try:
                    debug_print(f"  Subiendo a Flow (Note ID: {note_id})...")
                    uploaded_attachment_id = self.sg.upload(
                        "Note", note_id, temp_file_path, field_name="attachments"
                    )

                    if uploaded_attachment_id:
                        attached_count += 1
                        debug_print(
                            f"  ✅ ÉXITO: Imagen [{idx}] adjuntada correctamente (Attachment ID: {uploaded_attachment_id})"
                        )
                    else:
                        debug_print(
                            f"  ❌ ERROR: No se obtuvo ID de attachment para {new_filename}"
                        )
                        failed_count += 1
                        failed_images.append(
                            f"[{idx}] {image_path} (no se obtuvo attachment ID)"
                        )

                except Exception as upload_error:
                    debug_print(
                        f"  ❌ ERROR subiendo archivo {new_filename}: {upload_error}"
                    )
                    failed_count += 1
                    failed_images.append(
                        f"[{idx}] {image_path} (error al subir: {upload_error})"
                    )
                    continue

            # Limpiar carpeta temporal
            try:
                shutil.rmtree(temp_dir)
                debug_print(
                    f"attach_images_to_note: Carpeta temporal eliminada: {temp_dir}"
                )
            except Exception as cleanup_error:
                debug_print(
                    f"attach_images_to_note: Error limpiando carpeta temporal: {cleanup_error}"
                )

            # Resumen final
            debug_print(f"=== attach_images_to_note: RESUMEN FINAL ===")
            debug_print(f"attach_images_to_note: Total recibidas: {len(image_paths)}")
            debug_print(
                f"attach_images_to_note: ✅ Adjuntadas exitosamente: {attached_count}"
            )
            debug_print(f"attach_images_to_note: ❌ Fallidas: {failed_count}")

            if failed_images:
                debug_print(f"attach_images_to_note: Lista de imágenes que fallaron:")
                for failed_img in failed_images:
                    debug_print(f"  - {failed_img}")

            if attached_count == len(image_paths):
                debug_print(
                    f"attach_images_to_note: ✅ TODAS las imágenes se adjuntaron correctamente"
                )
            elif attached_count > 0:
                debug_print(
                    f"attach_images_to_note: ⚠️  ADVERTENCIA: Solo {attached_count} de {len(image_paths)} imágenes se adjuntaron"
                )
            else:
                debug_print(
                    f"attach_images_to_note: ❌ ERROR: Ninguna imagen se pudo adjuntar"
                )

            # Retornar el número de imágenes adjuntadas (no solo booleano)
            return attached_count

        except Exception as e:
            debug_print(f"❌ ERROR CRÍTICO adjuntando imagenes a la nota: {e}")
            import traceback

            debug_print(traceback.format_exc())
            return 0  # Retornar 0 imágenes adjuntadas en caso de error

    def extract_frame_number_from_path(self, image_path):
        """
        Extrae el numero de frame de la ruta de una imagen.
        Busca patrones como _0001.jpg, _1234.jpg, etc.
        """
        try:
            filename = os.path.basename(image_path)
            name_without_ext = os.path.splitext(filename)[0]

            # Buscar el ultimo grupo de 4 digitos precedido por guion bajo
            match = re.search(r"_(\d{4})(?:_\d+)?$", name_without_ext)
            if match:
                return match.group(1)

            # Si no encuentra el patron, buscar cualquier numero al final
            match = re.search(r"_(\d+)(?:_\d+)?$", name_without_ext)
            if match:
                return match.group(1).zfill(4)  # Rellenar con ceros a la izquierda

            return "0001"  # Valor por defecto

        except Exception as e:
            debug_print(f"Error extrayendo numero de frame de {image_path}: {e}")
            return "0001"

    def get_project_id_from_version(self, version_id):
        """
        Obtiene el ID del proyecto a partir del ID de una version.
        """
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return None
        try:
            version = self.sg.find_one(
                "Version", [["id", "is", version_id]], ["project"]
            )
            if version and version.get("project"):
                return version["project"]["id"]
            return None
        except Exception as e:
            debug_print(f"Error obteniendo project_id de version {version_id}: {e}")
            return None


def execute_full_push_operation(
    sg_manager,
    button_name,
    base_name,
    message,
    review_images,
    original_file_name=None,
    file_path=None,
    target_version_number=None,
):
    """
    Ejecuta todo el proceso de push en una sola operación para mayor eficiencia
    """
    try:
        debug_print(f"Ejecutando push completo: {button_name} para {base_name}")

        # Si original_file_name tiene la versión, usarlo para detección correcta del formato
        base_name_for_detection = base_name
        if original_file_name:
            version_match = re.search(r"_v(\d+)", original_file_name)
            if version_match:
                # Si base_name no tiene versión pero original_file_name sí, usar original_file_name para detección
                if not any(
                    part.startswith("v") and part[1:].isdigit()
                    for part in base_name.split("_")
                ):
                    # Construir base_name_for_detection con la versión
                    version_str = version_match.group(0)  # Ya incluye el "_vXXX"
                    base_name_for_detection = base_name + version_str
                    debug_print(
                        f"execute_full_push: Usando base_name con versión para detección: {base_name_for_detection}"
                    )

        # Extraer project_name desde el segmento "VFX-NOMBRE" de la ruta (fallback al filename)
        project_name = extract_project_name_from_path(file_path)
        if project_name:
            debug_print(f"execute_full_push: project_name (from path): {project_name}")
        else:
            project_name = extract_project_name(base_name_for_detection)
            debug_print(f"execute_full_push: project_name (from filename fallback): {project_name}")
        shot_code = extract_shot_code(base_name_for_detection)

        debug_print(
            f"execute_full_push: base_name_for_detection='{base_name_for_detection}'"
        )
        debug_print(
            f"execute_full_push: project_name={project_name}, shot_code={shot_code}"
        )

        # Extraer task_name y normalizar aliases ("compo"→"comp") para búsqueda en Flow
        task_name_extracted = extract_task_name(base_name)
        if task_name_extracted:
            task_name = normalize_task_name(task_name_extracted)
        else:
            # Fallback: buscar task antes de la versión
            parts = base_name.split("_")
            version_number_str = None
            for part in parts:
                if part.startswith("v") and part[1:].isdigit():
                    version_number_str = part
                    break

            if version_number_str:
                try:
                    version_index = parts.index(version_number_str)
                    if version_index > 0:
                        task_name = parts[version_index - 1].lower()
                    else:
                        task_name = "comp"  # Fallback por defecto
                except ValueError:
                    task_name = "comp"  # Fallback por defecto
            else:
                task_name = "comp"  # Fallback por defecto

        # Extraer número de versión para logging
        parts = base_name.split("_")
        version_number_str = None
        for part in parts:
            if part.startswith("v") and part[1:].isdigit():
                version_number_str = part
                break

        # Si no encontramos versión en base_name, intentar extraerla de original_file_name
        if not version_number_str and original_file_name:
            debug_print(
                f"execute_full_push: No se encontró versión en base_name, intentando extraer de original_file_name: {original_file_name}"
            )
            version_match = re.search(r"_v(\d+)", original_file_name)
            if version_match:
                version_number_str = f"v{version_match.group(1)}"
                debug_print(
                    f"execute_full_push: Versión extraída de original_file_name: {version_number_str}"
                )
                # Actualizar base_name para incluir la versión
                base_name = f"{base_name}_{version_number_str}"
                debug_print(f"execute_full_push: base_name actualizado: {base_name}")

        if not version_number_str:
            error_msg = (
                f"No se encontró número de versión válido en base_name '{base_name}'"
            )
            if original_file_name:
                error_msg += f" ni en original_file_name '{original_file_name}'"
            debug_print(f"execute_full_push: ERROR: {error_msg}")
            return {"success": False, "error": error_msg}

        version_number = int(version_number_str.replace("v", ""))
        requested_version_number = (
            int(target_version_number)
            if target_version_number is not None
            else version_number
        )

        debug_print(
            f"Proyecto: {project_name}, Shot: {shot_code}, Task: {task_name}, "
            f"Version clip: {version_number}, Version objetivo: {requested_version_number}"
        )

        # Buscar proyecto, shot y tareas
        project, shot, tasks = sg_manager.find_shot_and_tasks(project_name, shot_code)
        if not shot:
            return {"success": False, "error": f"No se encontró el shot {shot_code}"}

        # Encontrar la tarea correspondiente
        sg_status = status_translation.get(button_name)
        if not sg_status:
            return {
                "success": False,
                "error": f"No se encontró estado válido para {button_name}",
            }

        task_id = None
        task_assignee_ids = []

        for task in tasks:
            if task["content"].lower() == task_name:
                task_id = task["id"]
                task_assignee_ids = sg_manager.get_task_assignees(task_id)
                break

        if not task_id:
            return {"success": False, "error": f"No se encontró la tarea {task_name}"}

        # Buscar versión objetivo explícita (Shift+Click) o la del clip actual.
        sg_specific_version, sg_version_number_str, user_id = (
            sg_manager.find_specific_version_for_shot(
                shot["id"], requested_version_number, task_name
            )
        )

        # En modo Shift+Click (target_version_number), NO fallback silencioso.
        if target_version_number is not None and not sg_specific_version:
            return {
                "success": False,
                "error": (
                    f"No se encontró la versión objetivo v{requested_version_number:03d} "
                    f"para la task '{task_name}'"
                ),
            }

        # Si no hay versión específica y no se pidió target explícito, fallback a la más alta.
        if not sg_specific_version:
            debug_print(
                f"No se encontró versión específica v{requested_version_number:02d} "
                f"para task '{task_name}', usando versión más alta como fallback"
            )
            sg_specific_version, sg_version_number_str, user_id = (
                sg_manager.find_highest_version_for_shot(shot["id"], task_name)
            )

        if not sg_specific_version:
            return {
                "success": False,
                "error": (
                    f"No se encontró ninguna versión en Flow para shot {shot_code} "
                    f"y task {task_name}"
                ),
            }

        debug_print(f"Actualizando tarea: {task_name} (ID: {task_id})")
        sg_manager.update_task_status(task_id, sg_status)

        effective_version_number = requested_version_number
        try:
            if sg_version_number_str:
                effective_version_number = int(str(sg_version_number_str))
        except Exception:
            pass

        target_version_label = f"v{effective_version_number:03d}"

        if sg_status in ["rev_di", "corr", "revleg", "revcha", "revjua", "revjav"]:
            debug_print(f"Actualizando versión a vwd")
            sg_manager.update_version_status(
                project_name, shot_code, target_version_label, "vwd"
            )

            # Agregar comentario si hay mensaje - usar la versión específica, no la más alta
            if message and sg_specific_version:
                debug_print(
                    f"Agregando comentario a versión específica {sg_specific_version['id']} "
                    f"(v{requested_version_number:02d})"
                )
                created_note = sg_manager.add_comment_to_version(
                    sg_specific_version["id"],
                    project["id"],
                    message,
                    user_id,
                    task_assignee_ids,
                    shot["id"],
                )

                # Adjuntar imágenes si existen y se creó la nota
                if created_note and review_images:
                    debug_print(
                        f"=== execute_full_push: Iniciando envío de imágenes ==="
                    )
                    debug_print(
                        f"execute_full_push: Nota creada con ID: {created_note['id']}"
                    )
                    debug_print(
                        f"execute_full_push: Versión ID: {sg_specific_version['id']}"
                    )
                    debug_print(
                        f"execute_full_push: Total de imágenes a adjuntar: {len(review_images)}"
                    )
                    debug_print(f"execute_full_push: Lista de imágenes a enviar:")
                    for idx, img_path in enumerate(review_images, 1):
                        debug_print(f"  [{idx}] {img_path}")
                        if not os.path.exists(img_path):
                            debug_print(
                                f"  ⚠️  ADVERTENCIA: La imagen [{idx}] NO EXISTE: {img_path}"
                            )

                    attach_result = sg_manager.attach_images_to_note(
                        created_note["id"], sg_specific_version["id"], review_images
                    )
                    debug_print(
                        f"execute_full_push: Resultado de attach_images_to_note: {attach_result} imágenes adjuntadas"
                    )
                    # Retornar información sobre imágenes adjuntadas en el resultado
                    return {
                        "success": True,
                        "message": "Push completado exitosamente",
                        "images_attached": attach_result,  # attach_result ahora es el número de imágenes adjuntadas
                    }
                elif created_note and not review_images:
                    debug_print(
                        f"execute_full_push: Nota creada pero no hay imágenes para adjuntar"
                    )
                    return {
                        "success": True,
                        "message": "Push completado exitosamente",
                        "images_attached": 0,
                    }
                elif not created_note and review_images:
                    debug_print(
                        f"⚠️  ADVERTENCIA: Hay {len(review_images)} imágenes pero no se creó la nota, no se pueden adjuntar"
                    )
                    return {
                        "success": True,
                        "message": "Push completado exitosamente (nota no creada, imágenes no adjuntadas)",
                        "images_attached": 0,
                    }

        elif sg_status == "rev_su":
            debug_print(f"Actualizando versión a rev")
            sg_manager.update_version_status(
                project_name, shot_code, target_version_label, "rev"
            )

        elif sg_status == "revleg":
            debug_print(f"Actualizando versión a unvleg")
            sg_manager.update_version_status(
                project_name, shot_code, target_version_label, "unvleg"
            )

        debug_print("execute_full_push: Push completado exitosamente")
        return {
            "success": True,
            "message": "Push completado exitosamente",
            "images_attached": 0,  # No hay imágenes para este tipo de estado
        }

    except Exception as e:
        error_msg = f"Error en push completo: {str(e)}"
        debug_print(error_msg)
        return {"success": False, "error": error_msg}


def execute_flow_operation(operation, **kwargs):
    """
    Función principal que ejecuta operaciones de Flow
    Se llama desde el script principal usando subprocess
    """
    try:
        # Obtener credenciales
        url = kwargs.get("url")
        login = kwargs.get("login")
        password = kwargs.get("password")

        if not url or not login or not password:
            print("ERROR: Credenciales faltantes")
            return {"success": False, "error": "Credenciales faltantes"}

        # Crear manager
        sg_manager = ShotGridManager(url, login, password)

        if operation == "find_shot_and_tasks":
            project_name = kwargs.get("project_name")
            shot_code = kwargs.get("shot_code")
            project, shot, tasks = sg_manager.find_shot_and_tasks(
                project_name, shot_code
            )

            # Convertir objetos datetime a strings para JSON serialization
            def convert_datetime(obj):
                if isinstance(obj, dict):
                    return {
                        k: (v.isoformat() if hasattr(v, "isoformat") else v)
                        for k, v in obj.items()
                    }
                elif isinstance(obj, list):
                    return [convert_datetime(item) for item in obj]
                else:
                    return obj

            return {
                "success": True,
                "project": convert_datetime(project) if project else None,
                "shot": convert_datetime(shot) if shot else None,
                "tasks": convert_datetime(tasks) if tasks else [],
            }

        elif operation == "find_highest_version":
            shot_id = kwargs.get("shot_id")
            version, version_num, user_id = sg_manager.find_highest_version_for_shot(
                shot_id
            )

            # Convertir objetos datetime a strings para JSON serialization
            if version:
                version = {
                    k: (v.isoformat() if hasattr(v, "isoformat") else v)
                    for k, v in version.items()
                }

            return {
                "success": True,
                "version": version,
                "version_number": version_num,
                "user_id": user_id,
            }

        elif operation == "update_task":
            task_id = kwargs.get("task_id")
            status = kwargs.get("status")
            sg_manager.update_task_status(task_id, status)
            return {"success": True}

        elif operation == "update_version":
            project_name = kwargs.get("project_name")
            shot_code = kwargs.get("shot_code")
            version_str = kwargs.get("version_str")
            status = kwargs.get("status")
            sg_manager.update_version_status(
                project_name, shot_code, version_str, status
            )
            return {"success": True}

        elif operation == "get_task_assignee":
            task_id = kwargs.get("task_id")
            assignee_id = sg_manager.get_task_assignee(task_id)
            return {"success": True, "assignee_id": assignee_id}

        elif operation == "add_comment":
            version_id = kwargs.get("version_id")
            project_id = kwargs.get("project_id")
            comment = kwargs.get("comment")
            user_id = kwargs.get("user_id")
            task_assignee_ids = kwargs.get("task_assignee_ids")
            if task_assignee_ids is None:
                legacy_assignee_id = kwargs.get("task_assignee_id")
                task_assignee_ids = [legacy_assignee_id] if legacy_assignee_id else []
            shot_id = kwargs.get("shot_id")
            note = sg_manager.add_comment_to_version(
                version_id, project_id, comment, user_id, task_assignee_ids, shot_id
            )

            # Convertir objetos datetime a strings para JSON serialization
            if note:
                note = {
                    k: (v.isoformat() if hasattr(v, "isoformat") else v)
                    for k, v in note.items()
                }

            return {"success": True, "note": note}

        elif operation == "attach_images":
            note_id = kwargs.get("note_id")
            version_id = kwargs.get("version_id")
            image_paths = kwargs.get("image_paths", [])
            success = sg_manager.attach_images_to_note(note_id, version_id, image_paths)
            return {"success": success}

        elif operation == "list_versions_for_task":
            base_name = kwargs.get("base_name", "")
            original_file_name = kwargs.get("original_file_name")
            file_path_lv = kwargs.get("file_path")

            base_name_for_detection = base_name
            if original_file_name:
                version_match = re.search(r"_v(\d+)", original_file_name)
                if version_match and not any(
                    part.startswith("v") and part[1:].isdigit()
                    for part in base_name.split("_")
                ):
                    base_name_for_detection = f"{base_name}{version_match.group(0)}"

            project_name = extract_project_name_from_path(file_path_lv)
            if not project_name:
                project_name = extract_project_name(base_name_for_detection)
            shot_code = extract_shot_code(base_name_for_detection)

            extracted_task = extract_task_name(base_name_for_detection or base_name)
            task_name = normalize_task_name(extracted_task) if extracted_task else "comp"

            project, shot, _ = sg_manager.find_shot_and_tasks(project_name, shot_code)
            if not shot:
                return {
                    "success": False,
                    "error": (
                        f"No se encontró el shot {shot_code} en proyecto {project_name}"
                    ),
                }

            versions = sg_manager.list_versions_for_task(shot["id"], task_name)
            return {
                "success": True,
                "versions": versions,
                "task_name": task_name,
                "shot_id": shot["id"],
                "project_id": project["id"] if project else None,
            }

        elif operation == "execute_full_push":
            # Operación optimizada que hace todo el push de una vez
            button_name = kwargs.get("button_name")
            base_name = kwargs.get("base_name")
            message = kwargs.get("message")
            review_images = kwargs.get("review_images", [])
            original_file_name = kwargs.get("original_file_name")
            file_path = kwargs.get("file_path")
            target_version_number = kwargs.get("target_version_number")

            return execute_full_push_operation(
                sg_manager,
                button_name,
                base_name,
                message,
                review_images,
                original_file_name,
                file_path=file_path,
                target_version_number=target_version_number,
            )

        elif operation == "check_version":
            # Verificación de versiones para evitar congelar UI
            base_name = kwargs.get("base_name")
            original_file_name = kwargs.get("original_file_name")

            # Si original_file_name tiene la versión, usarlo para detección correcta del formato
            base_name_for_detection = base_name
            if original_file_name:
                version_match = re.search(r"_v(\d+)", original_file_name)
                if version_match:
                    # Si base_name no tiene versión pero original_file_name sí, usar original_file_name para detección
                    if not any(
                        part.startswith("v") and part[1:].isdigit()
                        for part in base_name.split("_")
                    ):
                        # Construir base_name_for_detection con la versión
                        base_name_for_detection = (
                            f"{base_name}_{version_match.group(0)}"
                        )
                        debug_print(
                            f"check_version: Usando base_name con versión para detección: {base_name_for_detection}"
                        )

            # Extraer project_name desde el segmento "VFX-NOMBRE" de la ruta (fallback al filename)
            file_path_cv = kwargs.get("file_path")
            project_name = extract_project_name_from_path(file_path_cv)
            if not project_name:
                project_name = extract_project_name(base_name_for_detection)
            shot_code = extract_shot_code(base_name_for_detection)

            # Extraer número de versión
            parts = base_name.split("_")
            version_number_str = None
            for part in parts:
                if part.startswith("v") and part[1:].isdigit():
                    version_number_str = part
                    break

            # Si no encontramos versión en base_name, intentar extraerla de original_file_name
            if not version_number_str and original_file_name:
                debug_print(
                    f"check_version: No se encontró versión en base_name, intentando extraer de original_file_name: {original_file_name}"
                )
                version_match = re.search(r"_v(\d+)", original_file_name)
                if version_match:
                    version_number_str = f"v{version_match.group(1)}"
                    debug_print(
                        f"check_version: Versión extraída de original_file_name: {version_number_str}"
                    )
                    # Actualizar base_name para incluir la versión para el diálogo
                    base_name = f"{base_name}_{version_number_str}"
                    debug_print(
                        f"check_version: base_name actualizado para diálogo: {base_name}"
                    )

            if not version_number_str:
                return {
                    "success": True,
                    "needs_confirmation": False,
                }  # Continuar sin verificación

            local_version = int(version_number_str.replace("v", ""))

            # Buscar shot en Flow
            project, shot, _ = sg_manager.find_shot_and_tasks(project_name, shot_code)
            if not shot:
                return {
                    "success": True,
                    "needs_confirmation": False,
                }  # Continuar sin verificación

            # Extraer task_name y normalizar aliases para comparar con la versión correcta
            check_task = extract_task_name(base_name)
            check_task_name = normalize_task_name(check_task) if check_task else "comp"

            # Buscar versión más alta de la task activa
            sg_highest_version, sg_version_number, _ = (
                sg_manager.find_highest_version_for_shot(shot["id"], check_task_name)
            )

            if (
                sg_highest_version
                and sg_version_number
                and int(sg_version_number) > local_version
            ):
                return {
                    "success": True,
                    "needs_confirmation": True,
                    "local_version": local_version,
                    "flow_version": int(sg_version_number),
                    "base_name": base_name,
                }

            return {"success": True, "needs_confirmation": False}

        else:
            return {"success": False, "error": f"Operación no soportada: {operation}"}

    except Exception as e:
        print(f"ERROR en LGA_NKS_Flow_Push_connector: {str(e)}")
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    # Este código se ejecuta cuando se llama el script directamente
    import json
    import sys

    if len(sys.argv) < 2:
        print("ERROR: Falta operación")
        sys.exit(1)

    operation = sys.argv[1]

    # Leer parámetros desde stdin como JSON
    try:
        params = json.loads(sys.stdin.read())
        result = execute_flow_operation(operation, **params)
        print(json.dumps(result))
    except Exception as e:
        print(
            json.dumps(
                {"success": False, "error": f"Error procesando parámetros: {str(e)}"}
            )
        )
