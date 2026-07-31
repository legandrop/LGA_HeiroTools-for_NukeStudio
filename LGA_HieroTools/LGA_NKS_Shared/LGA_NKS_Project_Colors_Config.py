# -*- coding: utf-8 -*-
"""
____________________________________________________________________

  LGA_NKS_Project_Colors_Config v1.00 | Lega

  Colores de proyecto para HieroTools.

  La fuente de verdad es FLOW: cada proyecto guarda un envelope en
  `Project.sg_pipesync_project_settings_json` que se edita desde el Project
  Settings tab de PipeSync. PipeSync lo baja en su sync y lo deja en la tabla
  `project_settings_cache` de `pipesync_stats.db`, que es lo que lee este
  modulo. Los nombres visibles salen de la tabla `projects`, no del JSON.

  La DB que se abre depende del contexto (studio o client), porque cada uno
  tiene su propio sitio de Flow y sus propios proyectos.

  NO HAY FALLBACK a un .ini local. Antes los colores vivian en la seccion
  [Colors] de LGA_NKS_Projects_Panel.ini y cada maquina tenia los suyos, asi
  que el mismo proyecto se veia de un color distinto por persona. Si no hay
  datos, se devuelve un dict vacio y el caller usa su color por defecto.

  Usado por runtime activo:
  - LGA_NKS_Projects_Panel.py

  v1.00: Version inicial - lectura de project_settings_cache por contexto.
____________________________________________________________________

"""

import json
import os
import re
import sqlite3

from LGA_NKS_PipeSyncPaths import get_pipesync_db_path

STATS_DB_FILENAME = "pipesync_stats.db"

# Formato que guarda PipeSync en project_color
HEX_COLOR_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


def get_project_colors_db_path():
    """Ruta a la pipesync_stats.db del contexto activo (studio o client)."""
    return get_pipesync_db_path(STATS_DB_FILENAME)


def _extraer_color(settings_json):
    """Saca `project_color` de un envelope de Project Settings, o None si no sirve."""
    if not settings_json:
        return None

    try:
        envelope = json.loads(settings_json)
    except (ValueError, TypeError):
        return None

    if not isinstance(envelope, dict):
        return None

    color = str(envelope.get("project_color") or "").strip()
    if not HEX_COLOR_PATTERN.match(color):
        return None

    return color.upper()


def load_project_colors():
    """
    Devuelve {NOMBRE_PROYECTO_EN_MAYUSCULAS: '#RRGGBB'} para el contexto activo.

    Devuelve {} cuando no hay datos (PipeSync nunca sincronizo, la DB no existe,
    o todavia no tiene las tablas). El caller tiene que poder seguir sin colores.
    """
    db_path = get_project_colors_db_path()
    if not os.path.exists(db_path):
        return {}

    query = (
        "SELECT p.project_name, c.settings_json "
        "FROM projects p "
        "JOIN project_settings_cache c ON c.project_id = p.id"
    )

    connection = None
    try:
        # Read-only: HieroTools nunca escribe en la DB de PipeSync. Si el archivo
        # existe pero todavia no tiene las tablas, sqlite levanta OperationalError
        # y se devuelve {} igual que si no hubiera datos.
        connection = sqlite3.connect("file:{0}?mode=ro".format(db_path), uri=True)
        rows = connection.execute(query).fetchall()
    except sqlite3.Error:
        return {}
    finally:
        if connection is not None:
            connection.close()

    colors = {}
    for project_name, settings_json in rows:
        name = (project_name or "").strip()
        if not name:
            continue
        color = _extraer_color(settings_json)
        if color:
            colors[name.upper()] = color

    return colors


def find_project_color(project_name):
    """Devuelve el color '#RRGGBB' del proyecto, o None si no esta en la DB."""
    target = (project_name or "").strip().upper()
    if not target:
        return None
    return load_project_colors().get(target)
