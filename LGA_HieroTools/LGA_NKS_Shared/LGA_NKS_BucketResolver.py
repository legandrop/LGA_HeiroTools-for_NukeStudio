"""
____________________________________________________________________

  LGA_NKS_BucketResolver v1.00 | Lega

  Resolver central de mapeo Proyecto <-> Bucket Wasabi para HieroTools.
____________________________________________________________________
"""

import os
import re

from SecureConfig_Reader import read_secure_config


_BUCKET_ALLOWED_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$")
_BUCKET_IPV4_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")


def normalize_project_key(project_name):
    """Normaliza project name a clave canónica (uppercase, sin prefijo VFX-)."""
    normalized = str(project_name or "").strip()
    if normalized.upper().startswith("VFX-"):
        normalized = normalized[4:].strip()
    return normalized.upper()


def project_folder_for_project(project_name):
    """Construye carpeta local canónica VFX-{PROJECT}."""
    project_key = normalize_project_key(project_name)
    if not project_key:
        return ""
    return f"VFX-{project_key}"


def normalize_bucket_name(bucket_name):
    """Normaliza bucket a lowercase."""
    return str(bucket_name or "").strip().lower()


def is_valid_bucket_name(bucket_name):
    """Valida bucket DNS/S3 (Wasabi compatible)."""
    normalized = normalize_bucket_name(bucket_name)
    if not normalized:
        return False, "Bucket name is empty."
    if len(normalized) < 3 or len(normalized) > 63:
        return False, "Bucket name must be between 3 and 63 characters."
    if not _BUCKET_ALLOWED_RE.match(normalized):
        return (
            False,
            "Bucket name can only contain lowercase letters, numbers, dots and hyphens.",
        )
    if ".." in normalized or ".-" in normalized or "-." in normalized:
        return False, "Bucket name cannot contain '..', '.-' or '-.' patterns."
    if _BUCKET_IPV4_RE.match(normalized):
        return False, "Bucket name cannot be an IPv4 address."
    return True, ""


def default_bucket_for_project(project_name):
    """Fallback legacy: vfx-{project_lower}."""
    project_key = normalize_project_key(project_name)
    if not project_key:
        return ""
    candidate = f"vfx-{project_key.lower()}"
    is_valid, _ = is_valid_bucket_name(candidate)
    return candidate if is_valid else ""


def normalize_and_validate_overrides(raw_overrides):
    """
    Normaliza/valida overrides y devuelve:
        (normalized_overrides, errors)
    """
    normalized_overrides = {}
    bucket_owners = {}
    errors = []

    if not isinstance(raw_overrides, dict):
        return normalized_overrides, ["ProjectBucketOverrides must be a JSON object."]

    for raw_project, raw_bucket in raw_overrides.items():
        project_key = normalize_project_key(raw_project)
        if not project_key:
            errors.append(
                f"Project override key '{raw_project}' is empty after normalization."
            )
            continue

        bucket_name = normalize_bucket_name(raw_bucket)
        is_valid, reason = is_valid_bucket_name(bucket_name)
        if not is_valid:
            errors.append(
                f"Project '{project_key}' has invalid override bucket "
                f"'{str(raw_bucket).strip()}': {reason}"
            )
            continue

        existing_bucket = normalized_overrides.get(project_key)
        if existing_bucket and existing_bucket != bucket_name:
            errors.append(
                f"Project '{project_key}' is duplicated with different buckets "
                f"('{existing_bucket}' vs '{bucket_name}')."
            )
            continue

        owner = bucket_owners.get(bucket_name)
        if owner and owner != project_key:
            errors.append(
                f"Bucket '{bucket_name}' is assigned to multiple projects "
                f"('{owner}' and '{project_key}')."
            )
            continue

        normalized_overrides[project_key] = bucket_name
        bucket_owners[bucket_name] = project_key

    return normalized_overrides, errors


def load_snapshot(config_dict=None):
    """
    Carga snapshot de mapping contextual desde config.secure activo.
    """
    if config_dict is None:
        config_dict = read_secure_config() or {}

    wasabi_cfg = config_dict.get("Wasabi", {}) if isinstance(config_dict, dict) else {}
    raw_overrides = (
        wasabi_cfg.get("ProjectBucketOverrides", {})
        if isinstance(wasabi_cfg, dict)
        else {}
    )

    project_to_bucket, errors = normalize_and_validate_overrides(raw_overrides)
    bucket_to_project = {}
    for project_key, bucket_name in project_to_bucket.items():
        bucket_to_project[bucket_name] = project_key

    return {
        "project_to_bucket": project_to_bucket,
        "bucket_to_project": bucket_to_project,
        "warnings": errors,
    }


def resolve_bucket_for_project(project_name, snapshot=None):
    """Resuelve bucket físico para un proyecto lógico."""
    if snapshot is None:
        snapshot = load_snapshot()

    project_key = normalize_project_key(project_name)
    if not project_key:
        return {
            "ok": False,
            "project": "",
            "bucket": "",
            "warning": "Project name is empty.",
        }

    bucket_name = snapshot.get("project_to_bucket", {}).get(project_key)
    if not bucket_name:
        bucket_name = default_bucket_for_project(project_key)

    if not bucket_name:
        return {
            "ok": False,
            "project": project_key,
            "bucket": "",
            "warning": "Could not build a valid fallback bucket.",
        }

    return {"ok": True, "project": project_key, "bucket": bucket_name, "warning": ""}


def resolve_project_for_bucket(bucket_name, snapshot=None):
    """Resuelve proyecto lógico para bucket físico."""
    if snapshot is None:
        snapshot = load_snapshot()

    normalized_bucket = normalize_bucket_name(bucket_name)
    is_valid, reason = is_valid_bucket_name(normalized_bucket)
    if not is_valid:
        return {
            "ok": False,
            "bucket": "",
            "project": "",
            "from_override": False,
            "warning": reason,
        }

    project_key = snapshot.get("bucket_to_project", {}).get(normalized_bucket)
    from_override = bool(project_key)

    if not project_key and normalized_bucket.startswith("vfx-"):
        project_key = normalize_project_key(normalized_bucket[4:])

    if not project_key:
        return {
            "ok": False,
            "bucket": normalized_bucket,
            "project": "",
            "from_override": False,
            "warning": "Bucket is not mapped to any known project.",
        }

    return {
        "ok": True,
        "bucket": normalized_bucket,
        "project": project_key,
        "from_override": from_override,
        "warning": "",
    }


def _sanitize_prefix(prefix):
    normalized_prefix = str(prefix or "").strip().replace("\\", "/")
    normalized_prefix = normalized_prefix.strip("/")
    if not normalized_prefix:
        return True, "", []

    parts = [p.strip() for p in normalized_prefix.split("/") if p.strip()]
    for part in parts:
        if part in (".", ".."):
            return False, "", []

    return True, "/".join(parts), parts


def resolve_bucket_from_local_path(local_path, snapshot=None):
    """Resuelve bucket/prefix/proyecto desde una ruta local que contiene VFX-*."""
    if snapshot is None:
        snapshot = load_snapshot()

    normalized = os.path.normpath(str(local_path or "").strip()).replace("\\", "/")
    if not normalized:
        return {"ok": False, "error": "Local path is empty."}

    parts = [p.strip() for p in normalized.split("/") if p.strip()]
    project_folder_index = -1
    for index, part in enumerate(parts):
        if part.upper().startswith("VFX-"):
            project_folder_index = index
            break

    if project_folder_index < 0:
        return {
            "ok": False,
            "error": "Local path does not contain a VFX-* project folder.",
        }

    project_key = normalize_project_key(parts[project_folder_index])
    if not project_key:
        return {"ok": False, "error": "Could not normalize project name from local path."}

    bucket_result = resolve_bucket_for_project(project_key, snapshot=snapshot)
    if not bucket_result.get("ok"):
        return {
            "ok": False,
            "error": bucket_result.get("warning") or "Could not resolve project bucket.",
        }

    raw_prefix = "/".join(parts[project_folder_index + 1 :])
    prefix_ok, safe_prefix, prefix_parts = _sanitize_prefix(raw_prefix)
    if not prefix_ok:
        return {"ok": False, "error": "Prefix contains unsafe path segments."}

    return {
        "ok": True,
        "project": project_key,
        "project_folder": project_folder_for_project(project_key),
        "bucket": bucket_result["bucket"],
        "prefix": safe_prefix,
        "prefix_parts": prefix_parts,
    }


def resolve_project_folder_from_bucket_and_prefix(bucket_name, prefix="", snapshot=None):
    """Resuelve carpeta local canónica desde bucket/prefix remoto."""
    if snapshot is None:
        snapshot = load_snapshot()

    project_result = resolve_project_for_bucket(bucket_name, snapshot=snapshot)
    if not project_result.get("ok"):
        return {
            "ok": False,
            "error": project_result.get("warning")
            or "Bucket is not mapped to any known project.",
        }

    prefix_ok, safe_prefix, _ = _sanitize_prefix(prefix)
    if not prefix_ok:
        return {"ok": False, "error": "Prefix contains unsafe path segments."}

    project_key = project_result["project"]
    project_folder = project_folder_for_project(project_key)
    local_relative_path = project_folder
    if safe_prefix:
        local_relative_path = f"{project_folder}/{safe_prefix}"

    return {
        "ok": True,
        "project": project_key,
        "project_folder": project_folder,
        "local_relative_path": local_relative_path,
        "bucket": normalize_bucket_name(bucket_name),
        "prefix": safe_prefix,
        "from_override": bool(project_result.get("from_override")),
    }
