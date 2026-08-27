"""
____________________________________________________________________

  LGA_NKS_Flow_Push_connector v1.09 | Lega

  Conector simple para operaciones de red con Flow
  Este script se ejecuta con Python personalizado para evitar problemas de dependencias
  Actualizado para ser compatible con múltiples sistemas de nomenclatura:
  - PROYECTO_SEQ_SHOT_DESC1_DESC2 (5 bloques con descripción)
  - PROYECTO_SEQ_SHOT (3 bloques simplificado)
  - PROYECTO_TEMP_EP_SEQ_SHOT_DESC1_DESC2 (6 bloques con descripción)
  - PROYECTO_TEMP_EP_SEQ_SHOT (4 bloques simplificado)

  v1.09: La Version destino se desempata por NOMBRE. El filtro por token y por
         numero puede matchear mas de una Version cuando conviven dos
         convenciones de naming que solo difieren en el orden del vendor code
         (PROJA_..._comp_VND_v003 y PROJA_..._VND_comp_v003): las dos tienen
         "_comp_" y las dos son v003. find_specific/highest_version_for_shot
         se quedaban con matching_versions[0], o sea la del ID mas bajo, y la
         nota del push se colgaba de la Version equivocada. Ahora gana la que
         coincide exacto con el stem del filename del clip, y si quedan varias
         sin match exacto se elige una pero se avisa por warnings en vez de
         resolverlo en silencio. update_version_status tambien se acota por
         nombre: antes escribia el estado en TODAS las coincidencias, y eso
         pintaba de `vwd` la Version que el usuario miraba y tapaba que la nota
         se habia ido a la otra. Los dos resolvers devuelven un elemento mas.
  v1.08: El branch que crea la nota y manda la Version a `vwd` se decide con
         is_note_capable() de LGA_NKS_Flow_Status_Config, no con una lista
         propia. La copia de aca no tenia "revhld": el push abria el dialogo,
         el usuario escribia la nota y este archivo la descartaba devolviendo
         success con applied.note en False y sin un solo warning. Es la misma
         desincronizacion que la v1.05 arreglo para status_translation.
         "revprd" no estaba en ninguna de las cinco copias.
  v1.07: execute_full_push acepta extra_images: la media que el usuario
         arrastra al dialogo de notas. La sube el metodo nuevo
         attach_files_to_note, que la adjunta con su nombre original en vez
         de renombrarla con la convencion annot_version_<id>.<frame>, que es
         para anotaciones de un frame. Las cuatro ramas del attach se
         unifican en un bloque y ahora avisan por warnings si alguna imagen
         no llego a la nota. La nota se crea tambien cuando el mensaje esta
         vacio pero hay imagenes que adjuntar.
  v1.06: Task CG (client): los codigos de Version en Flow llevan la DISCIPLINA
         del clip, asi que las busquedas se filtran por el stream extraido del
         filename (version_filter_token) y update_version_status acepta
         require_token para no pisar el otro stream que comparte numero.
  v1.05: status_translation sale de LGA_NKS_Flow_Status_Config en vez de una copia
         propia que ya se habia desincronizado de la del panel.

  v1.04: Limpieza de codigo muerto: se eliminan las operaciones inalcanzables del
         dispatcher (find_shot_and_tasks, find_highest_version, update_task,
         update_version, get_task_assignee, add_comment, attach_images,
         check_version; quedan list_versions_for_task y execute_full_push), el
         segundo bloque "except ImportError" con el fallback de naming que nunca
         se ejecutaba y los metodos get_task_assignee/get_project_id_from_version.
         El import de naming ahora falla explicito con raise en vez de seguir
         hasta un NameError posterior.
  v1.03: update_task_status y update_version_status devuelven (ok, error) en vez
         de tragarse los errores. execute_full_push aborta si falla la Task y
         devuelve el dict "applied" con lo realmente escrito en Flow, para que
         la DB local (cache de Flow) nunca guarde algo que Flow no recibió.
  v1.02: Agrega modo allow_task_only para actualizar solo la Task cuando existe
         proyecto/shot/task pero no existe Version en Flow.
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


# Los logs del conector van SIEMPRE prendidos. Este proceso corre aparte, en el
# python de PipeSync, y es el unico que ve lo que Flow contesta de verdad: los
# IDs de Note y Version, y el resultado de cada upload. Con esto apagado, un
# push que perdia la nota se veia desde Hiero como un exito sin un solo warning
# y no habia forma de saber a que entidad se habia linkeado nada.
# debug_print escribe a stderr, y Flow_Push lo recoge y lo vuelca al .log
# prefijado con [Conector] (ver call_flow_connector).
DEBUG = True


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
    # No hay fallback local: el conector depende de LGA_NKS_Flow_NamingUtils.
    debug_print(f"⚠️ ImportError: {e} - LGA_NKS_Flow_NamingUtils no disponible")
    raise


# Traduccion label -> codigo de Flow. Fuente unica compartida con el panel y con
# Flow_Push; tener una copia propia aca ya hizo que el conector empujara codigos
# distintos a los que el panel creia estar mandando.
try:
    from LGA_NKS_Flow_Status_Config import get_status_translation, is_note_capable
except ImportError as e:
    debug_print(f"⚠️ ImportError: {e} - LGA_NKS_Flow_Status_Config no disponible")
    raise

status_translation = get_status_translation()

# Nombre de la task CG (contexto client). Import tolerante: sin GetClip el
# conector sigue funcionando y la regla CG simplemente no aplica.
try:
    from LGA_NKS_GetClip import CG_TASK_NAME
except ImportError:
    try:
        from LGA_NKS_Shared.LGA_NKS_GetClip import CG_TASK_NAME
    except ImportError:
        CG_TASK_NAME = "cg"


def pick_version_by_expected_code(candidates, expected_code, contexto=""):
    """Desempata entre Versions que matchean el mismo numero de version.

    El filtro por token ("_comp_") y por numero no alcanza para elegir: un
    mismo (shot, version) puede tener DOS entidades en Flow cuando conviven dos
    convenciones de naming que solo difieren en el orden del vendor code:

        PROJA_1013_0800_comp_VND_v003     <- task antes del vendor
        PROJA_1013_0800_VND_comp_v003     <- vendor antes de la task

    Las dos contienen "_comp_" y las dos son v003, asi que quedarse con la
    primera es una moneda al aire que siempre cae del lado del ID mas bajo. Eso
    mandaba las notas del push a la Version equivocada mientras el estado se
    escribia en las dos, que es lo que lo mantuvo invisible.

    `expected_code` es el stem del filename del clip, que identifica sin
    ambiguedad cual de las dos corresponde. Devuelve (elegida, warning):
      - hay match exacto de code           -> esa, sin warning
      - una sola candidata                 -> esa, sin warning
      - varias y ninguna matchea exacto    -> la primera + warning explicito
    """
    if not candidates:
        return None, None

    if expected_code:
        objetivo = str(expected_code).strip().lower()
        for v in candidates:
            if (v.get("code") or "").strip().lower() == objetivo:
                debug_print(
                    f"Desempate por nombre{contexto}: '{v['code']}' (ID: {v['id']}) "
                    f"coincide exacto con el filename del clip"
                )
                return v, None

    if len(candidates) == 1:
        return candidates[0], None

    codes = ", ".join(f"{v['code']} (ID: {v['id']})" for v in candidates)
    warning = (
        f"En Flow hay {len(candidates)} Versions que coinciden{contexto} y ninguna "
        f"tiene el nombre del clip"
        + (f" ('{expected_code}')" if expected_code else "")
        + f". Se usa la primera. Candidatas: {codes}"
    )
    debug_print(f"ADVERTENCIA: {warning}")
    return candidates[0], warning


def version_filter_token(task_name, extracted_task):
    """Token con el que se filtran los CODIGOS de Version en Flow.

    Las tasks clasicas llevan su nombre en el codigo (_comp_); la task CG lleva
    la DISCIPLINA del clip (layout, lighting, ...), asi que se filtra por el
    token crudo extraido del filename (el stream). Si no hay token extraido se
    devuelve el nombre de la task (para CG no va a matchear nada y el flujo cae
    a los caminos de fallback/task-only existentes).
    """
    if task_name == CG_TASK_NAME and extracted_task:
        return extracted_task.lower()
    return task_name


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

    def find_highest_version_for_shot(self, shot_id, task_name="comp", expected_code=None):
        """
        Busca la versión más alta para un shot filtrando por la task indicada.
        Para 'comp' también acepta el alias '_cmp_'.

        Devuelve (version, version_number_str, user_id, warning). El warning
        avisa cuando el numero mas alto lo comparten varias Versions y ninguna
        coincide con el nombre del clip (ver pick_version_by_expected_code).
        """
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return None, None, None, None
        filters = [["entity", "is", {"type": "Shot", "id": shot_id}]]
        fields = ["code", "created_at", "user", "sg_status_list", "description"]
        try:
            versions = self.sg.find("Version", filters, fields)
        except Exception as e:
            debug_print(f"Error buscando versiones para shot_id {shot_id}: {e}")
            return None, None, None, None

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

            # El numero mas alto puede estar repetido en varias Versions: se
            # juntan todas las que lo tienen y se desempata por nombre.
            tope = safe_version_num(max(matching_versions, key=safe_version_num))
            empatadas = [v for v in matching_versions if safe_version_num(v) == tope]
            highest_version, warning = pick_version_by_expected_code(
                empatadas, expected_code, f" con la version mas alta (v{tope:03d})"
            )
            m = re.search(r"_v(\d+)", highest_version["code"])
            version_number = m.group(1) if m else "0"
            user_id = (
                highest_version["user"]["id"]
                if highest_version.get("user") and highest_version["user"].get("id")
                else None
            )
            return highest_version, version_number, user_id, warning
        return None, None, None, None

    def find_specific_version_for_shot(self, shot_id, version_number, task_name="comp",
                                       expected_code=None):
        """
        Busca una versión específica por número de versión para un shot, filtrando por task.
        Para 'comp' también acepta el alias '_cmp_'.

        Args:
            shot_id: ID del shot en ShotGrid
            version_number: Número de versión (ej: 13 para v013)
            task_name: task a buscar ('comp'/'roto'/'cleanup'). Default 'comp'.
            expected_code: stem del filename del clip. Es lo unico que desempata
                cuando el token y el numero matchean mas de una Version.

        Returns:
            Tupla (version, version_number_str, user_id, warning), o
            (None, None, None, None) si no se encuentra.
        """
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return None, None, None, None
        filters = [["entity", "is", {"type": "Shot", "id": shot_id}]]
        fields = ["code", "created_at", "user", "sg_status_list", "description"]
        try:
            versions = self.sg.find("Version", filters, fields)
        except Exception as e:
            debug_print(f"Error buscando versiones para shot_id {shot_id}: {e}")
            return None, None, None, None

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
            specific_version, warning = pick_version_by_expected_code(
                matching_versions, expected_code, f" con v{version_number:03d}"
            )
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
            return specific_version, version_number_str, user_id, warning

        debug_print(
            f"No se encontró versión específica v{version_number:02d} para task '{task_name}' en shot_id {shot_id}"
        )
        return None, None, None, None

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
        """Actualiza el estado de la Task en Flow.

        Devuelve (ok, error). La DB local es un cache de Flow: solo debe
        escribirse si esta escritura devolvió ok=True.
        """
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return False, "ShotGrid no inicializado"
        try:
            debug_print(
                f"Actualizando estado de la tarea (ID: {task_id}) a: {new_status}"
            )
            self.sg.update("Task", task_id, {"sg_status_list": new_status})
            return True, None
        except Exception as e:
            debug_print(f"Error al actualizar el estado de la tarea: {e}")
            return False, f"Error al actualizar el estado de la tarea: {e}"

    def update_version_status(self, project_name, shot_code, version_str, new_status,
                              require_token=None, expected_code=None):
        """Actualiza el estado de la/las Version en Flow.

        Devuelve (ok, error). Si no se encontró ninguna Version que coincida
        se considera fallo: no hubo escritura real en Flow y por lo tanto la
        DB local no debe reflejar el nuevo estado.

        require_token (task CG): dentro de CG conviven streams que repiten
        numero (layout_v003 y lighting_v003), y el filtro por "contains vNNN"
        solo tocaria las dos. Con el token, solo se actualizan las versiones
        cuyo codigo contiene _<token>_.

        expected_code: stem del filename del clip. Si entre las coincidencias
        hay una con ese nombre exacto, se escribe SOLO en esa. Antes se escribia
        en todas, y con dos convenciones de naming conviviendo eso pintaba de
        `vwd` una Version que no era la del clip: el estado se veia bien en la
        que el usuario miraba y tapaba que la nota se habia ido a la otra.
        """
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return False, "ShotGrid no inicializado"
        try:
            debug_print(
                f"Actualizando estado de la version para el Shot: {shot_code}, Version: {version_str} a: {new_status}"
            )
            filters = [
                ["project.Project.name", "is", project_name],
                ["entity.Shot.code", "is", shot_code],
                ["code", "contains", version_str],
            ]
            versions = self.sg.find("Version", filters, ["id", "code"])
            if require_token:
                token_pattern = f"_{require_token.lower()}_"
                versions = [
                    v for v in versions
                    if token_pattern in (v.get("code") or "").lower()
                ]
            if not versions:
                msg = (
                    f"No se encontró ninguna Version en Flow para {shot_code} "
                    f"{version_str}"
                )
                debug_print(msg)
                return False, msg

            # Si el nombre del clip identifica una sola de las coincidencias, el
            # estado se escribe unicamente ahi. Sin expected_code se conserva el
            # comportamiento historico de actualizar todas.
            if expected_code and len(versions) > 1:
                objetivo = str(expected_code).strip().lower()
                exacta = [
                    v for v in versions
                    if (v.get("code") or "").strip().lower() == objetivo
                ]
                if exacta:
                    descartadas = [
                        f"{v['code']} (ID: {v['id']})"
                        for v in versions if v["id"] != exacta[0]["id"]
                    ]
                    debug_print(
                        f"Estado acotado por nombre a '{exacta[0]['code']}' "
                        f"(ID: {exacta[0]['id']}). No se tocan: {', '.join(descartadas)}"
                    )
                    versions = exacta

            for version in versions:
                debug_print(
                    f"Actualizando version (ID: {version['id']}) a estado: {new_status}"
                )
                self.sg.update("Version", version["id"], {"sg_status_list": new_status})
            return True, None
        except Exception as e:
            debug_print(f"Error al actualizar el estado de la version: {e}")
            return False, f"Error al actualizar el estado de la version: {e}"

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

    def attach_files_to_note(self, note_id, file_paths):
        """
        Adjunta archivos a una nota tal cual, con su nombre original.

        Es la media que el usuario arrastro al dialogo de notas: no son
        anotaciones de un frame, asi que no se renombran con la convencion
        annot_version_<id>.<frame> que usa attach_images_to_note. Devuelve
        cuantos archivos se subieron.
        """
        if not self.sg:
            debug_print("ShotGrid no inicializado")
            return 0

        debug_print(
            f"=== attach_files_to_note: {len(file_paths)} archivo(s) para la nota {note_id} ==="
        )

        attached_count = 0
        failed_files = []

        for idx, file_path in enumerate(file_paths, 1):
            if not os.path.exists(file_path):
                debug_print(
                    f"  ❌ ERROR: El archivo [{idx}] NO EXISTE en disco: {file_path}"
                )
                failed_files.append(f"[{idx}] {file_path} (no existe)")
                continue

            try:
                debug_print(
                    f"  Subiendo {os.path.basename(file_path)} a Flow (Note ID: {note_id})..."
                )
                uploaded_attachment_id = self.sg.upload(
                    "Note", note_id, file_path, field_name="attachments"
                )

                if uploaded_attachment_id:
                    attached_count += 1
                    debug_print(
                        f"  ✅ ÉXITO: Archivo [{idx}] adjuntado (Attachment ID: {uploaded_attachment_id})"
                    )
                else:
                    debug_print(
                        f"  ❌ ERROR: No se obtuvo ID de attachment para {os.path.basename(file_path)}"
                    )
                    failed_files.append(
                        f"[{idx}] {file_path} (no se obtuvo attachment ID)"
                    )

            except Exception as upload_error:
                debug_print(
                    f"  ❌ ERROR subiendo {os.path.basename(file_path)}: {upload_error}"
                )
                failed_files.append(
                    f"[{idx}] {file_path} (error al subir: {upload_error})"
                )

        debug_print(
            f"attach_files_to_note: adjuntados {attached_count} de {len(file_paths)}"
        )
        if failed_files:
            debug_print("attach_files_to_note: Lista de archivos que fallaron:")
            for failed in failed_files:
                debug_print(f"  {failed}")

        return attached_count

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


def execute_full_push_operation(
    sg_manager,
    button_name,
    base_name,
    message,
    review_images,
    original_file_name=None,
    file_path=None,
    target_version_number=None,
    allow_task_only=False,
    extra_images=None,
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

        # Token de filtrado de codigos de Version: para CG es el stream del clip
        # (los codigos llevan la disciplina, no "cg").
        version_token = version_filter_token(task_name, task_name_extracted)
        if version_token != task_name:
            debug_print(f"Task CG: filtrando versiones por stream '{version_token}'")

        # Nombre esperado de la Version: el stem del filename del clip. Es lo
        # unico que desempata cuando conviven dos convenciones de naming y las
        # dos matchean el mismo token y el mismo numero.
        expected_version_code = base_name_for_detection
        version_warnings = []

        # Buscar versión objetivo explícita (Shift+Click) o la del clip actual.
        sg_specific_version, sg_version_number_str, user_id, version_warning = (
            sg_manager.find_specific_version_for_shot(
                shot["id"], requested_version_number, version_token,
                expected_code=expected_version_code,
            )
        )
        if version_warning:
            version_warnings.append(version_warning)

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
            sg_specific_version, sg_version_number_str, user_id, version_warning = (
                sg_manager.find_highest_version_for_shot(
                    shot["id"], version_token, expected_code=expected_version_code
                )
            )
            if version_warning:
                version_warnings.append(version_warning)

        if not sg_specific_version:
            if allow_task_only:
                debug_print(
                    "No se encontro version en Flow. allow_task_only=True: "
                    f"actualizando solo la tarea {task_name} (ID: {task_id})."
                )
                task_ok, task_error = sg_manager.update_task_status(task_id, sg_status)
                if not task_ok:
                    return {"success": False, "error": task_error}
                return {
                    "success": True,
                    "message": "Task actualizada sin Version en Flow",
                    "task_only": True,
                    "images_attached": 0,
                    "applied": {
                        "task_status": True,
                        "version_status": False,
                        "note": False,
                    },
                }
            return {
                "success": False,
                "error": (
                    f"No se encontró ninguna versión en Flow para shot {shot_code} "
                    f"y task {task_name}"
                ),
            }

        debug_print(f"Actualizando tarea: {task_name} (ID: {task_id})")
        # La DB local es cache de Flow: si falla la escritura en Flow se aborta
        # el push y el caller no debe escribir nada en la DB.
        task_ok, task_error = sg_manager.update_task_status(task_id, sg_status)
        if not task_ok:
            return {"success": False, "error": task_error}

        # applied refleja qué se escribió realmente en Flow. El caller usa esto
        # para actualizar la DB local solo con lo confirmado.
        applied = {
            "task_status": True,
            "version_status": False,
            "version_status_value": None,
            "note": False,
        }
        # Los avisos del resolver de Version viajan al usuario: si quedaron
        # varias candidatas y ninguna coincidia con el nombre del clip, el push
        # eligio una y hay que decirlo, no tragarselo.
        warnings = list(version_warnings)

        effective_version_number = requested_version_number
        try:
            if sg_version_number_str:
                effective_version_number = int(str(sg_version_number_str))
        except Exception:
            pass

        target_version_label = f"v{effective_version_number:03d}"

        # Para CG el update de Version discrimina por stream; en las tasks
        # clasicas se conserva el comportamiento historico (sin token).
        version_require_token = version_token if version_token != task_name else None

        if is_note_capable(sg_status):
            debug_print(f"Actualizando versión a vwd")
            version_ok, version_error = sg_manager.update_version_status(
                project_name, shot_code, target_version_label, "vwd",
                require_token=version_require_token,
                expected_code=expected_version_code,
            )
            if version_ok:
                applied["version_status"] = True
                applied["version_status_value"] = "vwd"
            else:
                warnings.append(version_error)

            # Nota en la version especifica, no en la mas alta. Alcanza con que
            # haya mensaje O imagenes: arrastrar una referencia y apretar OK sin
            # escribir nada es un flujo normal, y si se pidiera mensaje la media
            # se perdia sin que el push diera un solo error.
            if (message or review_images or extra_images) and sg_specific_version:
                debug_print(
                    f"Agregando comentario a versión específica {sg_specific_version['id']} "
                    f"(v{requested_version_number:02d})"
                )
                created_note = sg_manager.add_comment_to_version(
                    sg_specific_version["id"],
                    project["id"],
                    message or "",
                    user_id,
                    task_assignee_ids,
                    shot["id"],
                )

                # Adjuntar imagenes si se creo la nota. Son dos listas: las
                # capturas de ReviewPic, que suben con la convencion de
                # anotaciones de Flow, y la media que el usuario arrastro al
                # dialogo de notas, que sube con su nombre original.
                pending_images = list(review_images or []) + list(extra_images or [])

                if created_note:
                    applied["note"] = True
                    images_attached = 0

                    if pending_images:
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
                            f"execute_full_push: Total de imágenes a adjuntar: "
                            f"{len(pending_images)} ({len(review_images or [])} de ReviewPic, "
                            f"{len(extra_images or [])} arrastradas)"
                        )
                        debug_print(f"execute_full_push: Lista de imágenes a enviar:")
                        for idx, img_path in enumerate(pending_images, 1):
                            debug_print(f"  [{idx}] {img_path}")
                            if not os.path.exists(img_path):
                                debug_print(
                                    f"  ⚠️  ADVERTENCIA: La imagen [{idx}] NO EXISTE: {img_path}"
                                )

                    if review_images:
                        images_attached += int(
                            sg_manager.attach_images_to_note(
                                created_note["id"],
                                sg_specific_version["id"],
                                review_images,
                            )
                            or 0
                        )

                    if extra_images:
                        images_attached += int(
                            sg_manager.attach_files_to_note(
                                created_note["id"], extra_images
                            )
                            or 0
                        )

                    if pending_images:
                        debug_print(
                            f"execute_full_push: Imágenes adjuntadas: "
                            f"{images_attached} de {len(pending_images)}"
                        )
                        if images_attached < len(pending_images):
                            warnings.append(
                                f"Solo se adjuntaron {images_attached} de "
                                f"{len(pending_images)} imágenes a la nota"
                            )

                    return {
                        "success": True,
                        "message": "Push completado exitosamente",
                        "images_attached": images_attached,
                        "applied": applied,
                        "warnings": warnings,
                    }

                if pending_images:
                    debug_print(
                        f"⚠️  ADVERTENCIA: Hay {len(pending_images)} imágenes pero no se "
                        f"creó la nota, no se pueden adjuntar"
                    )
                    warnings.append(
                        "No se pudo crear la nota en Flow; imágenes no adjuntadas"
                    )
                    return {
                        "success": True,
                        "message": "Push completado exitosamente (nota no creada, imágenes no adjuntadas)",
                        "images_attached": 0,
                        "applied": applied,
                        "warnings": warnings,
                    }

                # No se creó la nota y no había imágenes.
                warnings.append("No se pudo crear la nota en Flow")

        elif sg_status == "rev_su":
            debug_print(f"Actualizando versión a rev")
            version_ok, version_error = sg_manager.update_version_status(
                project_name, shot_code, target_version_label, "rev",
                require_token=version_require_token,
                expected_code=expected_version_code,
            )
            if version_ok:
                applied["version_status"] = True
                applied["version_status_value"] = "rev"
            else:
                warnings.append(version_error)

        debug_print("execute_full_push: Push completado exitosamente")
        return {
            "success": True,
            "message": "Push completado exitosamente",
            "images_attached": 0,  # No hay imágenes para este tipo de estado
            "applied": applied,
            "warnings": warnings,
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

        if operation == "list_versions_for_task":
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
            list_token = version_filter_token(task_name, extracted_task)

            project, shot, _ = sg_manager.find_shot_and_tasks(project_name, shot_code)
            if not shot:
                return {
                    "success": False,
                    "error": (
                        f"No se encontró el shot {shot_code} en proyecto {project_name}"
                    ),
                }

            versions = sg_manager.list_versions_for_task(shot["id"], list_token)
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
            # Media arrastrada al dialogo de notas por el usuario
            extra_images = kwargs.get("extra_images", [])
            original_file_name = kwargs.get("original_file_name")
            file_path = kwargs.get("file_path")
            target_version_number = kwargs.get("target_version_number")
            allow_task_only = bool(kwargs.get("allow_task_only"))

            return execute_full_push_operation(
                sg_manager,
                button_name,
                base_name,
                message,
                review_images,
                original_file_name,
                file_path=file_path,
                target_version_number=target_version_number,
                allow_task_only=allow_task_only,
                extra_images=extra_images,
            )

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
