"""
____________________________________________________________________

  LGA_NKS_ContextProfile v1.00 | Lega

  Resolver de contexto Studio/Client para LGA_HieroTools.

  Lee un INI junto a LGA_HieroTools_Startup.py para decidir qué perfil de
  PipeSync debe usarse al resolver config.secure y bases locales.

  v1.00: La cache client de Windows se resuelve en la instalación hermana
         `PipeSync_Client/cacheClient`.
____________________________________________________________________
"""

import configparser
import os
import sys
from pathlib import Path

MODE_STUDIO = "studio"
MODE_CLIENT = "client"

ENV_CONTEXT_INI = "LGA_HIEROTOOLS_CONTEXT_INI"
DEFAULT_CONTEXT_FILES = ("LGA_HieroTools_context.ini", "context.ini")


def _normalize_mode(raw_mode):
    mode = (raw_mode or "").strip().lower()
    return MODE_CLIENT if mode == MODE_CLIENT else MODE_STUDIO


def _startup_root():
    # .../Startup/LGA_HieroTools/LGA_NKS_Shared/LGA_NKS_ContextProfile.py
    # -> .../Startup
    return Path(__file__).resolve().parents[2]


def _candidate_context_paths():
    env_path = (os.getenv(ENV_CONTEXT_INI) or "").strip()
    if env_path:
        yield Path(env_path)

    startup_root = _startup_root()
    for file_name in DEFAULT_CONTEXT_FILES:
        yield startup_root / file_name


def find_context_ini():
    seen = set()
    for candidate in _candidate_context_paths():
        try:
            candidate = candidate.resolve()
        except Exception:
            continue
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists() and candidate.is_file():
            return candidate
    return None


def get_context_mode():
    ini_path = find_context_ini()
    if not ini_path:
        return MODE_STUDIO

    parser = configparser.ConfigParser()
    try:
        parser.read(ini_path, encoding="utf-8")
    except Exception:
        return MODE_STUDIO

    candidates = [
        parser.get("Context", "mode", fallback=""),
        parser.get("Context", "Mode", fallback=""),
        parser.get("DEFAULT", "mode", fallback=""),
        parser.get("DEFAULT", "Mode", fallback=""),
    ]
    for value in candidates:
        if value:
            return _normalize_mode(value)
    return MODE_STUDIO


def is_client_context():
    return get_context_mode() == MODE_CLIENT


def get_pipesync_profile_folder():
    return "PipeSyncClient" if is_client_context() else "PipeSync"


def get_lga_appdata_root():
    if sys.platform == "win32":
        app_data = os.getenv("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(app_data) / "LGA"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "LGA"
    return Path.home() / ".config" / "LGA"


def get_pipesync_config_dir():
    return get_lga_appdata_root() / get_pipesync_profile_folder()


def get_secure_config_path():
    return get_pipesync_config_dir() / "config.secure"


def get_key_path():
    return get_pipesync_config_dir() / ".key"


def _default_cache_dir():
    if sys.platform == "win32":
        # Mantenemos compatibilidad con el layout histórico del entorno portable.
        if is_client_context():
            return Path("C:/Portable/LGA/PipeSync_Client/cacheClient")
        return Path("C:/Portable/LGA/PipeSync/cache")
    if sys.platform == "darwin":
        if is_client_context():
            return Path.home() / "Library" / "Caches" / "LGA" / "PipeSyncClient"
        return Path.home() / "Library" / "Caches" / "LGA" / "PipeSync"
    if is_client_context():
        return Path.home() / ".cache" / "LGA" / "PipeSyncClient"
    return Path.home() / ".cache" / "LGA" / "PipeSync"


def get_cache_dir_from_config(config_dict):
    if isinstance(config_dict, dict):
        app_cfg = config_dict.get("App", {})
        if isinstance(app_cfg, dict):
            cache_path = str(app_cfg.get("CachePath") or "").strip()
            if cache_path:
                normalized = cache_path.replace("\\", "/").rstrip("/").lower()
                if is_client_context() and (
                    normalized.endswith("/cacheproject")
                    or normalized.endswith("/cache/project")
                ):
                    return _default_cache_dir()
                return Path(cache_path)
    return _default_cache_dir()


def get_db_path(config_dict=None, filename="pipesync.db"):
    return get_cache_dir_from_config(config_dict) / filename
