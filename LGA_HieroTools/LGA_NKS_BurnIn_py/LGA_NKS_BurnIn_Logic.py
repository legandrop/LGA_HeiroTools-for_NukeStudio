"""
____________________________________________________________________

  LGA_NKS_BurnIn_Logic v1.01 | Lega

  Logica viva del soft effect LGA_BurnIn. Las expresiones [python ...]
  de los Text2 internos del gizmo llaman a bi_text() y bi_ok() en cada
  evaluacion del timeline, asi que todo aca tiene que ser rapido y no
  tirar nunca una excepcion (un error devuelve texto vacio / ok=1.0 y
  se loguea una sola vez).

  La config se resuelve en LGA_NKS_BurnIn_Config y se cachea por
  proyecto; el modulo de registro invalida el cache en los eventos de
  load/save de proyecto.

  v1.01: Frame y TC como campos separados, campo colorspace (por API
         con cache) y registro de llamadas en el log para diagnostico.
  v1.00: Version inicial. Campos res (rojo condicional, solo EXR),
         fps (rojo condicional), frametc y clip.
____________________________________________________________________
"""

import os
import time

import LGA_NKS_BurnIn_Config as bi_config

DEBUG = False  # Consola apagada por default; el .log se escribe siempre.

_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
_LOG_PATH = os.path.join(_LOG_DIR, "DebugPy_LGA_NKS_BurnIn.log")
_MAX_LOGGED_ERRORS = 20

_log_started = False
_logged_error_keys = set()

# Cache de config: {project_name: config_dict}. Se invalida entero cuando
# cambia el mtime del BurnIn.json o cuando el registro avisa un evento de
# proyecto (load/save/close).
_config_cache = {}
_config_file_mtime = None


# ── Debug con archivo (convencion del pack) ───────────────────────────────────


def _log(message):
    """Escribe SIEMPRE al .log (pisado por sesion); consola solo si DEBUG."""
    global _log_started
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        mode = "a" if _log_started else "w"
        with open(_LOG_PATH, mode, newline="\n", encoding="utf-8") as f:
            f.write("[{}] {}\n".format(time.strftime("%H:%M:%S"), message))
        _log_started = True
    except Exception:
        pass
    if DEBUG:
        print("[LGA_BurnIn] {}".format(message))


def _log_error_once(key, message):
    """Loguea un error una sola vez por key para no inundar el log por frame."""
    if key in _logged_error_keys or len(_logged_error_keys) >= _MAX_LOGGED_ERRORS:
        return
    _logged_error_keys.add(key)
    _log("ERROR {}: {}".format(key, message))


# ── Config cacheada ───────────────────────────────────────────────────────────


def invalidate_cache():
    """Vacia los caches. Lo llama el registro en eventos de proyecto."""
    _config_cache.clear()
    _colorspace_cache.clear()
    _logged_error_keys.clear()
    _log("Cache de config invalidado")


def _file_mtime():
    try:
        return os.path.getmtime(bi_config.get_settings_path())
    except OSError:
        return None


def _read_project_tag_json(project_name):
    """JSON del tag LGA_BurnIn_Settings del proyecto, via el modulo de tag."""
    try:
        import LGA_NKS_BurnIn_ProjectTag as bi_tag

        return bi_tag.read_config_json(bi_tag.find_project(project_name))
    except ImportError:
        return None
    except Exception as exc:
        _log_error_once("tag:" + str(project_name), str(exc))
        return None


def get_config(project_name):
    """Config efectiva para un proyecto, cacheada."""
    global _config_file_mtime
    mtime = _file_mtime()
    if mtime != _config_file_mtime:
        _config_file_mtime = mtime
        _config_cache.clear()

    key = project_name or ""
    cfg = _config_cache.get(key)
    if cfg is not None:
        return cfg

    user_data, error = bi_config.load_user_file()
    if error:
        _log_error_once("config_file", error)
    tag_json = _read_project_tag_json(project_name) if project_name else None
    cfg, warnings = bi_config.resolve(user_data, project_name, tag_json)
    for warning in warnings:
        _log_error_once("config_warn:" + warning[:40], warning)
    _config_cache[key] = cfg
    _log(
        "Config resuelta para '{}' (tag del proyecto: {})".format(
            key, "si" if tag_json else "no"
        )
    )
    return cfg


# ── Acceso a metadata del stream ──────────────────────────────────────────────


def _meta(parent, key, frame=None):
    """Metadata del input del gizmo (el stream visible del timeline)."""
    try:
        input_node = parent.node("Input1")
        if input_node is None:
            return None
        if frame is None:
            return input_node.metadata(key)
        return input_node.metadata(key, frame)
    except Exception as exc:
        _log_error_once("meta:" + key, str(exc))
        return None


def _project_name(parent):
    return _meta(parent, "hiero/project")


def _clip_res(parent):
    try:
        w = _meta(parent, "input/width")
        h = _meta(parent, "input/height")
        if w is None or h is None:
            return None
        return (int(float(w)), int(float(h)))
    except (TypeError, ValueError):
        return None


def _clip_fps(parent):
    try:
        v = _meta(parent, "input/frame_rate")
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


# El colorspace no viaja en la metadata del stream del timeline, asi que se
# resuelve por API: se ubica el clip por nombre y se le pregunta su transform.
# Cacheado por (proyecto, clip); se limpia junto con el cache de config.
_colorspace_cache = {}


def _clip_colorspace(parent):
    proj_name = _project_name(parent)
    clip_name = _meta(parent, "hiero/clip")
    if not clip_name:
        return ""
    key = (proj_name, clip_name)
    if key in _colorspace_cache:
        return _colorspace_cache[key]
    value = ""
    try:
        import hiero.core

        for proj in hiero.core.projects():
            if proj_name and proj.name() != proj_name:
                continue
            for clip in hiero.core.findItemsInProject(proj, "Clips"):
                if clip.name() == clip_name:
                    value = str(clip.sourceMediaColourTransform() or "")
                    break
            break
    except Exception as exc:
        _log_error_once("cspace:" + str(clip_name), str(exc))
    _colorspace_cache[key] = value
    return value


def _is_plate(parent, cfg):
    """True si el archivo visible entra en la comparacion de resolucion (EXR)."""
    filename = _meta(parent, "input/filename") or ""
    ext = os.path.splitext(str(filename))[1].lstrip(".").lower()
    exts = [str(e).lstrip(".").lower() for e in cfg.get("compare_res_exts", [])]
    return ext in exts


def _target_res(parent, cfg):
    """Resolucion objetivo: explicita de config, o el formato del timeline."""
    explicit = bi_config.parse_res(cfg.get("res_target"))
    if explicit:
        return explicit
    try:
        return (int(parent.width()), int(parent.height()))
    except Exception as exc:
        _log_error_once("target_res", str(exc))
        return None


def _target_fps(parent, cfg):
    explicit = bi_config.parse_fps(cfg.get("fps_target"))
    if explicit is not None:
        return explicit
    try:
        v = _meta(parent, "hiero/sequence/frame_rate")
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


# ── API para las expresiones del gizmo ────────────────────────────────────────


_call_counts = {}


def _log_call(kind, field, result):
    """Registra las primeras llamadas por campo para diagnosticar evaluacion."""
    key = kind + ":" + str(field)
    count = _call_counts.get(key, 0) + 1
    _call_counts[key] = count
    if count <= 3 or count % 500 == 0:
        _log("{} #{} -> {!r}".format(key, count, result))


def bi_text(field, parent, frame=None):
    """Texto de un campo. La llama la expresion del message de cada Text2."""
    try:
        result = ""
        if field == "clip":
            result = str(_meta(parent, "hiero/clip") or "")
        elif field == "res":
            res = _clip_res(parent)
            result = "{}x{}".format(res[0], res[1]) if res else ""
        elif field == "fps":
            fps = _clip_fps(parent)
            result = "{} fps".format("%g" % fps) if fps is not None else ""
        elif field == "frame":
            frame_str = _meta(parent, "input/frame", frame)
            result = "Frame: {}".format(frame_str) if frame_str else ""
        elif field == "tc":
            tc = _meta(parent, "input/timecode", frame)
            result = "TC: {}".format(tc) if tc else ""
        elif field == "cspace":
            result = _clip_colorspace(parent)
        elif field == "frametc":
            # Compatibilidad con instancias viejas del gizmo (campo unificado).
            frame_str = _meta(parent, "input/frame", frame)
            tc = _meta(parent, "input/timecode", frame)
            result = "Frame: {}        TC: {}".format(frame_str or "", tc or "")
        _log_call("text", field, result)
        return result
    except Exception as exc:
        _log_error_once("text:" + str(field), str(exc))
        return ""


def bi_ok(field, parent, frame=None):
    """1.0 si el campo esta OK, 0.0 si hay mismatch (pinta rojo).

    La llaman las expresiones de los knobs bi_res_ok / bi_fps_ok del gizmo.
    El parametro frame no se usa: esta para que la expresion dependa del
    frame y Nuke la re-evalue (sin eso se evalua una sola vez, al cargar).
    Ante cualquier duda devuelve 1.0: un burn-in roto no debe gritar rojo.
    """
    try:
        cfg = get_config(_project_name(parent))
        result = 1.0
        if field == "res":
            if _is_plate(parent, cfg):
                clip = _clip_res(parent)
                target = _target_res(parent, cfg)
                if clip is not None and target is not None and clip != target:
                    result = 0.0
        elif field == "fps":
            clip = _clip_fps(parent)
            target = _target_fps(parent, cfg)
            if clip is not None and target is not None:
                if abs(clip - target) >= 0.001:
                    result = 0.0
        _log_call("ok", field, result)
        return result
    except Exception as exc:
        _log_error_once("ok:" + str(field), str(exc))
        return 1.0


_log("Modulo de logica cargado")
