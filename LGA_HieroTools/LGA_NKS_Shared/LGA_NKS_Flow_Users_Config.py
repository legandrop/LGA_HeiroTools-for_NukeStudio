"""
____________________________________________________________________

  LGA_NKS_Flow_Users_Config v2.02 | Lega

  Usuarios de Flow (nombre, color y usuario de Wasabi) para HieroTools.

  La fuente de verdad es FLOW: cada persona tiene un envelope en
  `HumanUser.sg_pipesync_user_json` que se edita desde el Projects tab de
  PipeSync. PipeSync lo baja en su sync y lo deja plano en la tabla
  `flow_users` de `pipesync_stats.db`, que es lo que lee este modulo.

  NO HAY FALLBACK a un JSON local. Antes existia LGA_NKS_Flow_Users.json y
  terminaba desincronizado de PipeSync sin que nadie se enterara: cada app
  mostraba a la misma persona de un color distinto. Si no hay datos, las
  funciones devuelven una lista vacia y el caller tiene que avisar.

  Usado por runtime activo:
  - LGA_NKS_Assignee_Panel.py
  - LGA_NKS_Assignee_Panel_py/LGA_NKS_Flow_Assign_Assignee.py
  - LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyAssign.py
  - LGA_NKS_Assignee_Panel_py/LGA_NKS_Wasabi_PolicyUnassign.py

  v2.02: se expone `skip_wasabi_policy`. Marca a quien NO se le administran
         policies por shot -admins y accesos por proyecto completo-, y las
         herramientas de Wasabi lo necesitan para no crearle una policy que
         despues nadie recalcula ni borra.

  v2.01: el orden de los usuarios sale de `panel_order`: los que lo tienen van
         primero por ese numero, el resto alfabetico.
  v2.00: la fuente pasa a ser pipesync_stats.db; se elimina el JSON local.
  v1.00: Version inicial (JSON local).
____________________________________________________________________

"""

import os
import sqlite3

from LGA_NKS_PipeSyncPaths import get_pipesync_db_path

STATS_DB_FILENAME = "pipesync_stats.db"
DEFAULT_USER_COLOR = "#666666"


def get_flow_users_db_path():
    """Ruta a la pipesync_stats.db de la instalacion estandar de PipeSync."""
    return get_pipesync_db_path(STATS_DB_FILENAME)


def load_flow_users(assignable_only=True):
    """
    Devuelve [{'name', 'color', 'wasabi_user', 'short_name'}, ...] ordenado por nombre.

    `assignable_only` filtra a la gente marcada como assignable y activa en Flow, que
    es lo que corresponde para el panel de assignees. Los scripts de Wasabi que buscan
    a una persona puntual pasan False: alguien puede tener policy de Wasabi sin estar
    en la lista de assignees.

    Devuelve [] cuando no hay datos (PipeSync nunca sincronizo, o la DB no existe).
    El caller tiene que distinguir ese caso y avisar, no seguir como si simplemente no
    hubiera usuarios configurados.
    """
    db_path = get_flow_users_db_path()
    if not os.path.exists(db_path):
        return []

    # El orden lo decide `panel_order`: los > 0 primero por ese numero, el resto
    # alfabetico. Se resuelve en el SQL con un CASE porque 0 significa "sin orden" y
    # ordenar por el numero crudo pondria a esos primeros. Es la MISMA regla que aplica
    # PipeSync en `FlowUsersStore::assignableNames()`.
    query = (
        "SELECT user_name, color, vendor_color, wasabi_user, short_name, "
        "skip_wasabi_policy FROM flow_users"
    )
    if assignable_only:
        query += " WHERE assignable = 1 AND status = 'act'"
    query += (
        " ORDER BY CASE WHEN panel_order > 0 THEN panel_order ELSE 999999 END,"
        " user_name COLLATE NOCASE"
    )

    connection = None
    try:
        # Read-only: HieroTools nunca escribe en la DB de PipeSync. Si el archivo
        # existe pero todavia no tiene la tabla, sqlite levanta OperationalError y se
        # devuelve [] igual que si no hubiera datos.
        connection = sqlite3.connect("file:{0}?mode=ro".format(db_path), uri=True)
        rows = connection.execute(query).fetchall()
    except sqlite3.Error:
        return []
    finally:
        if connection is not None:
            connection.close()

    users = []
    for (
        user_name,
        color,
        vendor_color,
        wasabi_user,
        short_name,
        skip_wasabi_policy,
    ) in rows:
        name = (user_name or "").strip()
        if not name:
            continue
        # El color de vendor gana siempre sobre el personal: misma regla que aplica
        # PipeSync en las ShotCards (FlowUsersStore::backgroundColorFor).
        resolved_color = (vendor_color or "").strip() or (color or "").strip()
        users.append(
            {
                "name": name,
                "color": resolved_color or DEFAULT_USER_COLOR,
                "wasabi_user": (wasabi_user or "").strip(),
                "short_name": (short_name or "").strip(),
                "skip_wasabi_policy": bool(skip_wasabi_policy),
            }
        )
    return users


def find_user_by_name(user_name):
    """Busca por nombre de Flow. Devuelve el dict del usuario o None."""
    target = (user_name or "").strip().casefold()
    if not target:
        return None
    for user in load_flow_users(assignable_only=False):
        if user["name"].casefold() == target:
            return user
    return None


def find_user_by_wasabi_user(wasabi_user):
    """Busca por usuario IAM de Wasabi. Devuelve el dict del usuario o None."""
    target = (wasabi_user or "").strip().casefold()
    if not target:
        return None
    for user in load_flow_users(assignable_only=False):
        if user["wasabi_user"].casefold() == target:
            return user
    return None
