"""
____________________________________________________________________

  LGA_NKS_Flow_Task_Config v1.25 | Lega

  Usado por runtime activo:
  - LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assignee.py
  - LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assign_Assignee.py
  - LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Clear_Assignees.py
  - LGA_NKS_Coordination_Panel_py/LGA_NKS_Flow_CreateShot.py

  Configuración centralizada de tasks del pipeline usadas por los paneles de Flow.
  La lista está sincronizada con los scripts de creación/modificación de shots y
  provee colores consistentes para las UIs compactas (assignee panel, create shot, etc.).

  1.25: Actualizado para usar colores de tasks alineados con los colores de create v000
  v1.24: Actualiza la UI para mostrar las tasks y los asignados en Flow.
         Funciona con todas las tasks disponibles en Flow.
____________________________________________________________________

"""

from typing import Dict, List


AVAILABLE_TASKS: List[Dict[str, str]] = [
    {
        "name": "Comp",
        "pipeline_step": "Comp",
        "enabled_by_default": True,
        "color": "#3381e0",  # Azul
    },
    {
        "name": "Roto",
        "pipeline_step": "Roto",
        "enabled_by_default": False,
        "color": "#2abf7e",  # Verde
    },
    {
        "name": "Cleanup",
        "pipeline_step": "Cleanup",
        "enabled_by_default": False,
        "color": "#27c8c3",  # Cyan
    },
    {
        "name": "DMP",
        "pipeline_step": "DMP",
        "enabled_by_default": False,
        "color": "#CACA3B",  # Amarillo
    },
    {
        "name": "Model",
        "pipeline_step": "Model",
        "enabled_by_default": False,
        "color": "#CA7A3B",  # Naranja
    },
    {
        "name": "Retopo",
        "pipeline_step": "Retopo",
        "enabled_by_default": False,
        "color": "#CA7A3B",  # Naranja
    },
    {
        "name": "Rigging",
        "pipeline_step": "Rigging",
        "enabled_by_default": False,
        "color": "#3BCA7A",  # Verde
    },
    {
        "name": "Shaders",
        "pipeline_step": "Shaders",
        "enabled_by_default": False,
        "color": "#3BCA7A",  # Verde
    },
    {
        "name": "Match Move",
        "pipeline_step": "Match Move",
        "enabled_by_default": False,
        "color": "#9A3BCA",  # Morado/Púrpura
    },
    {
        "name": "Animation",
        "pipeline_step": "Animation",
        "enabled_by_default": False,
        "color": "#CA7A3B",  # Naranja
    },
    {
        "name": "FX",
        "pipeline_step": "FX",
        "enabled_by_default": False,
        "color": "#CA3B9A",  # Magenta/Fucsia
    },
    {
        "name": "Lighting",
        "pipeline_step": "Lighting",
        "enabled_by_default": False,
        "color": "#3BCA7A",  # Verde
    },
]

DEFAULT_TASK_NAME = "Comp"
_TASK_ORDER = {task["name"].lower(): index for index, task in enumerate(AVAILABLE_TASKS)}
_TASK_COLOR_MAP = {task["name"].lower(): task["color"] for task in AVAILABLE_TASKS}


def get_task_color(task_name: str, fallback: str = "#4A4A4A") -> str:
    """Devuelve el color configurado para la task (case insensitive)."""
    if not task_name:
        return fallback
    return _TASK_COLOR_MAP.get(task_name.lower(), fallback)


def sort_tasks_by_pipeline(tasks: List[Dict]) -> List[Dict]:
    """
    Ordena la lista de tasks respetando el orden definido en AVAILABLE_TASKS.
    Tasks que no pertenecen a la lista quedan al final de forma alfabética.
    """

    def sort_key(task: Dict) -> tuple:
        name = (task.get("name") or task.get("content") or "").lower()
        order = _TASK_ORDER.get(name, len(_TASK_ORDER) + 1)
        return (order, name)

    return sorted(tasks, key=sort_key)


__all__ = ["AVAILABLE_TASKS", "DEFAULT_TASK_NAME", "get_task_color", "sort_tasks_by_pipeline"]
