# -*- coding: utf-8 -*-
"""
____________________________________________________________________

  LGA_NKS_PipeSyncPaths v1.01 | Lega

  Helpers de rutas de PipeSync para LGA_HieroTools.
  Centraliza resolución de DB/cache por contexto (studio/client).

  IMPORTANTE: La ruta de la DB/cache se resuelve SIEMPRE a la instalación
  estándar de PipeSync (C:/Portable/LGA/PipeSync/...), nunca al CachePath
  guardado en config.secure. Ese CachePath puede apuntar a un build de
  desarrollo (C:/Portable/LGA_PipeSync_2/...) cuando se corrió el PipeSync de
  dev, y no queremos que HieroTools lea/escriba ahí.

  v1.01: get_pipesync_db_path resuelve siempre a la instalación estándar e ignora
         el CachePath del config.secure (que podía apuntar al build de dev).
         Eliminados helpers de fallback (_legacy_cache_candidates, get_db_path).
  v1.00: Versión inicial - resolución de DB/cache y AltTPath por contexto.
____________________________________________________________________

"""

import os
import sys
from pathlib import Path

from LGA_NKS_ContextProfile import is_client_context
from SecureConfig_Reader import read_secure_config


def _installed_cache_dir():
    """Directorio de cache INSTALADO estándar de PipeSync, por plataforma y contexto."""
    if sys.platform == "win32":
        cache_name = "cacheClient" if is_client_context() else "cache"
        return Path("C:/Portable/LGA/PipeSync") / cache_name

    if sys.platform == "darwin":
        profile_name = "PipeSyncClient" if is_client_context() else "PipeSync"
        return Path.home() / "Library" / "Caches" / "LGA" / profile_name

    profile_name = "PipeSyncClient" if is_client_context() else "PipeSync"
    return Path.home() / ".cache" / "LGA" / profile_name


def get_pipesync_db_path(filename="pipesync.db"):
    """Devuelve la ruta de una DB de PipeSync en la instalación estándar.

    Ignora a propósito el CachePath del config.secure (ver nota del módulo).
    """
    return os.path.normpath(str(_installed_cache_dir() / filename))


def get_alt_work_root(default_root=None):
    if default_root is None:
        default_root = "N:\\" if is_client_context() else "T:\\"

    config = read_secure_config() or {}
    app_cfg = config.get("App", {}) if isinstance(config, dict) else {}
    raw_alt = str(app_cfg.get("AltTPath", "")).strip()
    if raw_alt:
        return os.path.normpath(raw_alt)
    return os.path.normpath(default_root)
