"""
____________________________________________________________________________________

  LGA_NKS_Flow_CreateShot v1.0 | Lega Pugliese
  Script para crear shots en ShotGrid basado en el nombre del clip seleccionado en Hiero
____________________________________________________________________________________
"""

import hiero.core
import os
import re
import sys
from pathlib import Path

# Agregar la ruta de shotgun_api3 al sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "LGA_ToolPack"))

import shotgun_api3

# Importar el modulo de configuracion segura
sys.path.append(str(Path(__file__).parent))
from SecureConfig_Reader import get_flow_credentials


class ShotGridManager:
    """Clase para manejar operaciones en ShotGrid."""

    def __init__(self, url, login, password):
        self.sg = shotgun_api3.Shotgun(url, login=login, password=password)

    def find_shot_and_tasks(self, project_name, shot_code):
        """Encuentra el shot en ShotGrid y sus tareas asociadas. Si no existe, lo crea."""
        projects = self.sg.find(
            "Project", [["name", "is", project_name]], ["id", "name"]
        )
        if projects:
            project_id = projects[0]["id"]
            filters = [
                ["project", "is", {"type": "Project", "id": project_id}],
                ["code", "is", shot_code],
            ]
            fields = ["id", "code", "description"]
            shots = self.sg.find("Shot", filters, fields)
            if shots:
                shot_id = shots[0]["id"]
                tasks = self.find_tasks_for_shot(shot_id)
                return shots[0], tasks
            else:
                print("No se encontro el shot. Creando shot...")
                created_shot = self.create_shot(project_id, shot_code)
                if created_shot:
                    tasks = self.find_tasks_for_shot(created_shot["id"])
                    return created_shot, tasks
                return None, None
        else:
            print("No se encontro el proyecto en ShotGrid.")
        return None, None

    def find_tasks_for_shot(self, shot_id):
        """Encuentra las tareas asociadas a un shot."""
        filters = [["entity", "is", {"type": "Shot", "id": shot_id}]]
        fields = ["id", "content", "sg_status_list"]
        return self.sg.find("Task", filters, fields)

    def create_shot(self, project_id, shot_code):
        """Crea un shot en ShotGrid con los parametros predefinidos."""
        # Parametros predefinidos
        sequence_name = "103"
        description = "Descripcion test"
        task_template_name = "Template_comp"

        print(f"Creando shot '{shot_code}' con parametros predefinidos...")

        # Buscar secuencia
        sequence_filters = [
            ["project", "is", {"type": "Project", "id": project_id}],
            ["code", "is", sequence_name],
        ]
        sequences = self.sg.find("Sequence", sequence_filters, ["id", "code"])
        if not sequences:
            print(f"ERROR: No se encontro la secuencia '{sequence_name}'")
            return None

        sequence_id = sequences[0]["id"]
        print(f"Secuencia encontrada: {sequences[0]['code']} (ID: {sequence_id})")

        # Buscar task template
        task_templates = self.sg.find(
            "TaskTemplate", [["code", "is", task_template_name]], ["id", "code"]
        )
        if not task_templates:
            print(f"ERROR: No se encontro el task template '{task_template_name}'")
            return None

        task_template_id = task_templates[0]["id"]
        print(
            f"Task Template encontrado: {task_templates[0]['code']} (ID: {task_template_id})"
        )

        # Crear el shot
        shot_data = {
            "project": {"type": "Project", "id": project_id},
            "code": shot_code,
            "description": description,
            "sg_sequence": {"type": "Sequence", "id": sequence_id},
            "task_template": {"type": "TaskTemplate", "id": task_template_id},
        }

        try:
            new_shot = self.sg.create("Shot", shot_data)
            print(
                f"Shot creado exitosamente: {new_shot['code']} (ID: {new_shot['id']})"
            )
            return new_shot
        except Exception as e:
            print(f"ERROR al crear el shot: {e}")
            return None


class HieroOperations:
    """Clase para manejar operaciones en Hiero."""

    def __init__(self, shotgrid_manager):
        self.sg_manager = shotgrid_manager

    def parse_exr_name(self, file_name):
        """Extrae el nombre base del archivo EXR y el numero de version."""
        base_name = re.sub(r"_%04d\.exr$", "", file_name)
        version_match = re.search(r"_v(\d+)", base_name)
        version_number = version_match.group(1) if version_match else "Unknown"
        return base_name, version_number

    def process_selected_clips(self):
        """Procesa los clips seleccionados en el timeline de Hiero."""
        seq = hiero.ui.activeSequence()
        if seq:
            te = hiero.ui.getTimelineEditor(seq)
            selected_clips = te.selection()
            if selected_clips:
                for clip in selected_clips:
                    file_path = clip.source().mediaSource().fileinfos()[0].filename()
                    exr_name = os.path.basename(file_path)
                    base_name, version_number = self.parse_exr_name(exr_name)

                    project_name = base_name.split("_")[0]
                    parts = base_name.split("_")
                    shot_code = "_".join(parts[:5])

                    shot, tasks = self.sg_manager.find_shot_and_tasks(
                        project_name, shot_code
                    )
                    if shot:
                        print("Clip seleccionado:", base_name)
                        print("Shot de SG encontrado:", shot["code"])
                        print("Descripcion del shot:", shot["description"])
                        print("Tareas asociadas:")
                        if tasks:
                            for task in tasks:
                                print("- Nombre:", task["content"])
                                print("  Estado:", task["sg_status_list"])
                        else:
                            print("No hay tareas asociadas a este shot.")
                    else:
                        print("No se encontro el shot correspondiente en ShotGrid.")
            else:
                print("No se han seleccionado clips en el timeline.")
        else:
            print("No se encontro una secuencia activa en Hiero.")


def main():
    # Obtener las credenciales desde la configuracion encriptada
    sg_url, sg_login, sg_password = get_flow_credentials()

    if not sg_url or not sg_login or not sg_password:
        print(
            "No se pudieron obtener las credenciales de Flow desde la configuracion encriptada."
        )
        return

    sg_manager = ShotGridManager(sg_url, sg_login, sg_password)
    hiero_ops = HieroOperations(sg_manager)
    hiero_ops.process_selected_clips()


if __name__ == "__main__":
    main()
