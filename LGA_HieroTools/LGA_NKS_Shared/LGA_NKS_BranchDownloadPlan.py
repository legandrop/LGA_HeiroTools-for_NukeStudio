"""
____________________________________________________________________

  LGA_NKS_BranchDownloadPlan v1.00 | Lega

  Planificacion de la descarga por ramas del boton Download Clip y
  los "intents" que dejan al watcher saber a que version subir el clip.

  Vive aparte de LGA_NKS_FileManager_DownloadClip.py para que toda la
  logica quede sin Qt y se pueda testear fuera de Hiero: el script se
  queda con el dialogo y el lanzamiento, aca esta el que-se-baja.

  Intents: DownloadClip escribe un .json por ruta a descargar y el
  watcher lo lee cuando FileManager avisa que termino. Sin ese dato el
  watcher no puede distinguir "bajaron mi rama, subime la version" de
  "bajaron otra rama, no me toques", porque el marcador de FileManager
  solo trae la ruta descargada.

  v1.00: Version inicial.
____________________________________________________________________
"""

import glob
import hashlib
import json
import os
import time

from LGA_NKS_VersionBranching import compare_branches, format_version


# Seleccion especial del dialogo: bajar la cabeza de todas las ramas.
SELECTION_ALL = "all"

# Los intents viejos se descartan: si el clip ya no esta o FileManager
# nunca aviso, no queremos que revivan en la sesion siguiente.
INTENT_TTL_SECONDS = 6 * 60 * 60


def normalize_path(path):
    """Normaliza para comparar rutas entre Hiero, FileManager y el watcher."""
    return os.path.normpath(str(path or "")).replace("\\", "/").rstrip("/").lower()


def build_clip_branches(entry):
    """Ramas de un clip a partir del listado remoto y lo que hay local.

    `entry` es el dict que arma DownloadClip por clip:
      target_name, target_version, versions {numero: nombre_remoto},
      local_versions [numeros]
    Devuelve la lista de compare_branches() con el nombre remoto de cada
    cabeza agregado como 'remote_name'.
    """
    versions = entry.get("versions") or {}
    branches = compare_branches(
        remote_versions=list(versions.keys()),
        local_versions=entry.get("local_versions") or [],
        current_version=entry.get("target_version"),
    )
    for branch in branches:
        head = branch.get("remote_head")
        branch["remote_name"] = versions.get(head) if head is not None else None
    return branches


def aggregate_branch_options(entries):
    """Opciones del dialogo, una por rama, uniendo todos los clips.

    Devuelve lista ordenada por arranque de rama:
      {'label', 'start', 'heads': [(clip_index, version, remote_name)],
       'has_news', 'is_current_branch'}
    Solo entran ramas con cabeza remota: son las unicas descargables.
    """
    by_label = {}
    for index, entry in enumerate(entries or []):
        for branch in entry.get("branches") or []:
            if branch.get("remote_head") is None:
                continue
            option = by_label.setdefault(
                branch["label"],
                {
                    "label": branch["label"],
                    "start": branch["start"],
                    "heads": [],
                    "has_news": False,
                    "is_current_branch": False,
                },
            )
            option["heads"].append(
                (index, branch["remote_head"], branch.get("remote_name"))
            )
            option["has_news"] = option["has_news"] or bool(branch.get("has_news"))
            option["is_current_branch"] = option["is_current_branch"] or bool(
                branch.get("is_current_branch")
            )
            option["start"] = min(option["start"], branch["start"])

    return sorted(by_label.values(), key=lambda option: option["start"])


def option_summary(option):
    """Texto corto de una opcion: cabezas distintas que se van a bajar."""
    heads = sorted({version for _index, version, _name in option.get("heads") or []})
    return ", ".join(format_version(version) for version in heads)


def plan_downloads(entries, selection):
    """Que se manda a FileManager para la seleccion elegida.

    selection: SELECTION_ALL o el label de una rama.
    Devuelve dict:
      folder_paths, file_paths (rutas locales resueltas para el CLI)
      intents (uno por ruta, para el watcher)
      skipped (clips sin esa rama, para loguear y no descartar en silencio)
    """
    folder_paths = []
    file_paths = []
    intents = []
    skipped = []

    for index, entry in enumerate(entries or []):
        branches = entry.get("branches") or []
        # Sin parent_local no se puede armar la ruta local de destino. No deberia
        # pasar (lo setea el worker al listar), pero un KeyError aca mataba la
        # descarga de TODOS los clips: mejor saltear este y reportarlo.
        if not entry.get("parent_local"):
            skipped.append(entry.get("clip_name") or entry.get("target_name"))
            continue

        if selection == SELECTION_ALL:
            chosen = [b for b in branches if b.get("remote_head") is not None]
        else:
            chosen = [
                b
                for b in branches
                if b.get("label") == selection and b.get("remote_head") is not None
            ]
            if not chosen:
                skipped.append(entry.get("clip_name") or entry.get("target_name"))
                continue

        for branch in chosen:
            remote_name = branch.get("remote_name")
            if not remote_name:
                continue
            resolved_local = os.path.join(entry["parent_local"], remote_name)
            resolved_local = resolved_local.replace("\\", "/")

            # A que version subir el clip cuando termine la descarga:
            #  - eleccion explicita de una rama -> a esa rama (el usuario la pidio)
            #  - "todas" -> solo dentro de la rama del clip, para no moverlo de rama
            #    por un efecto lateral
            if selection == SELECTION_ALL:
                should_switch = bool(branch.get("is_current_branch"))
            else:
                should_switch = True

            kind = "file" if entry.get("is_single_file") else "folder"
            if kind == "file":
                file_paths.append(resolved_local)
            else:
                folder_paths.append(resolved_local)

            intents.append(
                {
                    "path": resolved_local,
                    "kind": kind,
                    "clip_path": entry.get("file_path"),
                    "version": branch.get("remote_head"),
                    "branch_label": branch.get("label"),
                    "switch": should_switch,
                }
            )

    return {
        "folder_paths": folder_paths,
        "file_paths": file_paths,
        "intents": intents,
        "skipped": skipped,
    }


def intent_filename(path):
    """Nombre estable del intent para una ruta descargada."""
    digest = hashlib.md5(normalize_path(path).encode("utf-8")).hexdigest()
    return f"{digest}.json"


def write_intents(intent_dir, intents):
    """Escribe un .json por intent. Devuelve las rutas escritas."""
    if not intents:
        return []
    os.makedirs(intent_dir, exist_ok=True)
    written = []
    now = time.time()
    for intent in intents:
        payload = dict(intent)
        payload["created"] = now
        target = os.path.join(intent_dir, intent_filename(intent.get("path")))
        with open(target, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
        written.append(target)
    return written


def read_intent(intent_dir, path):
    """Intent de una ruta descargada, o None si no hay o esta vencido."""
    if not path:
        return None
    target = os.path.join(intent_dir, intent_filename(path))
    if not os.path.isfile(target):
        return None
    try:
        with open(target, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return None

    created = payload.get("created") or 0
    if created and (time.time() - created) > INTENT_TTL_SECONDS:
        return None
    return payload


def clear_intent(intent_dir, path):
    """Borra el intent de una ruta ya procesada."""
    if not path:
        return False
    target = os.path.join(intent_dir, intent_filename(path))
    try:
        os.remove(target)
        return True
    except Exception:
        return False


def prune_intents(intent_dir, max_age_seconds=INTENT_TTL_SECONDS):
    """Borra intents vencidos. Devuelve cuantos borro."""
    if not os.path.isdir(intent_dir):
        return 0
    removed = 0
    now = time.time()
    for candidate in glob.glob(os.path.join(intent_dir, "*.json")):
        try:
            if (now - os.path.getmtime(candidate)) > max_age_seconds:
                os.remove(candidate)
                removed += 1
        except Exception:
            continue
    return removed
