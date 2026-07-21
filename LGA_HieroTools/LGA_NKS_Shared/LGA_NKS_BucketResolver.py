"""
____________________________________________________________________

  LGA_NKS_BucketResolver v1.02 | Lega

  v1.02 (2026-07-21)
  - Aísla cache runtime por ruta/perfil/contexto para evitar fugas Studio↔Client.
  - Valida project keys como segmento local seguro en snapshot y resolución.

  v1.01 (2026-07-21)
  - Endurece ProjectBucketOverrides con contrato fail-closed, detección
    de colisiones en buckets efectivos y cache de último snapshot válido.

  v1.00:
  - Resolver central de mapeo Proyecto <-> Bucket Wasabi para HieroTools.
____________________________________________________________________
"""

import copy
import os
import re

from SecureConfig_Reader import read_secure_config_with_runtime_metadata


_BUCKET_ALLOWED_RE = re.compile(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$")
_BUCKET_IPV4_RE = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
_PROJECT_ALLOWED_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{0,63}$")
_LAST_VALID_RUNTIME_SNAPSHOTS = {}


def _new_snapshot():
    return {
        "project_to_bucket": {},
        "bucket_to_project": {},
        "effective_project_to_bucket": {},
        "project_errors": {},
        "bucket_errors": {},
        "general_errors": [],
        "known_projects": set(),
        "override_projects": set(),
        "blocked_projects": set(),
        "ambiguous_buckets": set(),
        "warnings": [],
        "schema_error": "",
        "overrides_field_present": False,
        "overrides_schema_valid": True,
    }


def _append_unique(target_list, message):
    text = str(message or "").strip()
    if not text:
        return
    if text not in target_list:
        target_list.append(text)


def _append_project_error(snapshot, project_key, message):
    errors = snapshot["project_errors"].setdefault(project_key, [])
    _append_unique(errors, message)


def _append_bucket_error(snapshot, bucket_name, message):
    errors = snapshot["bucket_errors"].setdefault(bucket_name, [])
    _append_unique(errors, message)


def _describe_json_type(value):
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    if value is None:
        return "null"
    return "unknown"


def _first_project_error(snapshot, project_key):
    errors = snapshot.get("project_errors", {}).get(project_key) or []
    return errors[0] if errors else ""


def _first_bucket_error(snapshot, bucket_name):
    errors = snapshot.get("bucket_errors", {}).get(bucket_name) or []
    return errors[0] if errors else ""


def _blocked_project_message(snapshot, project_key):
    first_error = _first_project_error(snapshot, project_key)
    if first_error:
        return first_error
    return f"Project '{project_key}' is blocked by ProjectBucketOverrides validation."


def _normalize_known_projects(known_projects):
    normalized = set()
    for project in known_projects or []:
        project_key = normalize_project_key(project)
        is_valid, _ = is_valid_project_key(project_key)
        if is_valid:
            normalized.add(project_key)
    return normalized


def _rebuild_warning_list(snapshot):
    warnings = []
    if snapshot.get("schema_error"):
        _append_unique(warnings, snapshot["schema_error"])

    for error in snapshot.get("general_errors", []):
        _append_unique(warnings, error)

    for errors in snapshot.get("project_errors", {}).values():
        for error in errors:
            _append_unique(warnings, error)

    for errors in snapshot.get("bucket_errors", {}).values():
        for error in errors:
            _append_unique(warnings, error)

    snapshot["warnings"] = warnings


def normalize_project_key(project_name):
    """Normaliza project name a clave canónica (uppercase, sin prefijo VFX-)."""
    normalized = str(project_name or "").strip()
    if normalized.upper().startswith("VFX-"):
        normalized = normalized[4:].strip()
    return normalized.upper()


def is_valid_project_key(project_name):
    """Valida que la clave sea un único segmento seguro de carpeta local."""
    project_key = normalize_project_key(project_name)
    if not project_key:
        return False, "Project key is empty."
    if project_key in (".", ".."):
        return False, "Project key cannot be '.' or '..'."
    if "/" in project_key or "\\" in project_key:
        return False, "Project key cannot contain '/' or '\\'. Use a single folder segment."
    for char in project_key:
        code_point = ord(char)
        if code_point < 32 or code_point == 127:
            return False, "Project key cannot contain control characters."
    if not _PROJECT_ALLOWED_RE.match(project_key):
        return (
            False,
            "Project key can only contain letters, numbers, '-' and '_' (1-64 chars).",
        )
    return True, ""


def project_folder_for_project(project_name):
    """Construye carpeta local canónica VFX-{PROJECT}."""
    project_key = normalize_project_key(project_name)
    is_valid, _ = is_valid_project_key(project_key)
    if not is_valid:
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
    is_valid_project, _ = is_valid_project_key(project_key)
    if not is_valid_project:
        return ""
    candidate = f"vfx-{project_key.lower()}"
    is_valid, _ = is_valid_bucket_name(candidate)
    return candidate if is_valid else ""


def build_snapshot_from_raw_value(
    raw_overrides_value, overrides_field_present, known_projects=None
):
    snapshot = _new_snapshot()
    snapshot["overrides_field_present"] = bool(overrides_field_present)
    snapshot["known_projects"] = _normalize_known_projects(known_projects)

    if overrides_field_present and not isinstance(raw_overrides_value, dict):
        snapshot["overrides_schema_valid"] = False
        snapshot["schema_error"] = "ProjectBucketOverrides must be a JSON object."
        _rebuild_warning_list(snapshot)
        return snapshot

    raw_object = raw_overrides_value if overrides_field_present else {}
    valid_overrides = {}
    raw_keys_per_project = {}

    for raw_project_key, raw_bucket_value in raw_object.items():
        project_key = normalize_project_key(raw_project_key)
        is_valid_project, project_error = is_valid_project_key(project_key)
        if not is_valid_project:
            _append_unique(
                snapshot["general_errors"],
                "Project override key "
                f"'{raw_project_key}' is invalid after normalization "
                f"('{project_key}'): {project_error}",
            )
            continue

        snapshot["known_projects"].add(project_key)
        raw_keys_per_project.setdefault(project_key, []).append(raw_project_key)

        if not isinstance(raw_bucket_value, str):
            _append_project_error(
                snapshot,
                project_key,
                f"Project '{project_key}' has a non-string override bucket value "
                f"({_describe_json_type(raw_bucket_value)}).",
            )
            continue

        original_bucket = raw_bucket_value
        bucket_name = normalize_bucket_name(original_bucket)
        is_valid, reason = is_valid_bucket_name(bucket_name)
        if not is_valid:
            _append_project_error(
                snapshot,
                project_key,
                f"Project '{project_key}' has invalid override bucket "
                f"'{original_bucket.strip()}': {reason}",
            )
            continue

        existing_bucket = valid_overrides.get(project_key)
        if existing_bucket and existing_bucket != bucket_name:
            _append_project_error(
                snapshot,
                project_key,
                f"Project '{project_key}' is duplicated with different buckets "
                f"('{existing_bucket}' vs '{bucket_name}').",
            )
            continue

        valid_overrides[project_key] = bucket_name

    for project_key, raw_keys in raw_keys_per_project.items():
        if len(raw_keys) > 1:
            _append_project_error(
                snapshot,
                project_key,
                f"Project '{project_key}' is duplicated after normalization "
                f"({', '.join(raw_keys)}).",
            )

    override_bucket_owners = {}
    for project_key, bucket_name in valid_overrides.items():
        owner = override_bucket_owners.get(bucket_name)
        if owner and owner != project_key:
            _append_project_error(
                snapshot,
                project_key,
                f"Bucket '{bucket_name}' is assigned to multiple projects "
                f"('{owner}' and '{project_key}').",
            )
            _append_project_error(
                snapshot,
                owner,
                f"Bucket '{bucket_name}' is assigned to multiple projects "
                f"('{owner}' and '{project_key}').",
            )
            _append_bucket_error(
                snapshot,
                bucket_name,
                f"Bucket '{bucket_name}' is ambiguous because it is assigned to "
                f"'{owner}' and '{project_key}'.",
            )
            snapshot["ambiguous_buckets"].add(bucket_name)
            continue
        override_bucket_owners[bucket_name] = project_key

    for project_key, errors in snapshot["project_errors"].items():
        if errors:
            snapshot["blocked_projects"].add(project_key)

    effective_bucket_by_project = {}
    effective_bucket_owners = {}
    for project_key in sorted(snapshot["known_projects"]):
        if project_key in snapshot["blocked_projects"]:
            continue

        if project_key in valid_overrides:
            effective_bucket = valid_overrides[project_key]
        else:
            effective_bucket = default_bucket_for_project(project_key)

        if not effective_bucket:
            _append_project_error(
                snapshot,
                project_key,
                f"Project '{project_key}' cannot produce a valid effective bucket.",
            )
            snapshot["blocked_projects"].add(project_key)
            continue

        effective_bucket_by_project[project_key] = effective_bucket
        effective_bucket_owners.setdefault(effective_bucket, []).append(project_key)

    for bucket_name, projects in effective_bucket_owners.items():
        if len(projects) <= 1:
            continue

        snapshot["ambiguous_buckets"].add(bucket_name)
        _append_bucket_error(
            snapshot,
            bucket_name,
            f"Bucket '{bucket_name}' is shared by multiple effective projects "
            f"({', '.join(projects)}).",
        )

        for project_key in projects:
            others = [other for other in projects if other != project_key]
            _append_project_error(
                snapshot,
                project_key,
                f"Project '{project_key}' collides on effective bucket '{bucket_name}' "
                f"with project(s): {', '.join(others)}.",
            )
            snapshot["blocked_projects"].add(project_key)

    for project_key, bucket_name in effective_bucket_by_project.items():
        if project_key in snapshot["blocked_projects"]:
            continue
        if bucket_name in snapshot["ambiguous_buckets"]:
            continue

        snapshot["effective_project_to_bucket"][project_key] = bucket_name
        snapshot["bucket_to_project"][bucket_name] = project_key

        if project_key in valid_overrides:
            snapshot["project_to_bucket"][project_key] = valid_overrides[project_key]
            snapshot["override_projects"].add(project_key)

    _rebuild_warning_list(snapshot)
    return snapshot


def build_snapshot(raw_overrides, known_projects=None):
    if raw_overrides is None:
        return build_snapshot_from_raw_value({}, True, known_projects)
    return build_snapshot_from_raw_value(dict(raw_overrides), True, known_projects)


def normalize_and_validate_overrides(raw_overrides):
    snapshot = build_snapshot(raw_overrides)
    return dict(snapshot["project_to_bucket"]), list(snapshot["warnings"])


def _discover_known_projects_from_local_root(config_dict):
    known_projects = set()
    if not isinstance(config_dict, dict):
        return known_projects

    wasabi_cfg = config_dict.get("Wasabi", {})
    if isinstance(wasabi_cfg, dict):
        raw_overrides = wasabi_cfg.get("ProjectBucketOverrides")
        if isinstance(raw_overrides, dict):
            for raw_project in raw_overrides.keys():
                project_key = normalize_project_key(raw_project)
                is_valid, _ = is_valid_project_key(project_key)
                if is_valid:
                    known_projects.add(project_key)

    app_cfg = config_dict.get("App", {})
    local_root = ""
    if isinstance(app_cfg, dict):
        local_root = str(app_cfg.get("AltTPath", "")).strip()
    if not local_root:
        local_root = "T:/"

    normalized_root = os.path.normpath(local_root)
    if not os.path.isdir(normalized_root):
        return known_projects

    try:
        for folder_name in os.listdir(normalized_root):
            folder_path = os.path.join(normalized_root, folder_name)
            if not os.path.isdir(folder_path):
                continue
            if not folder_name.upper().startswith("VFX-"):
                continue
            project_key = normalize_project_key(folder_name)
            is_valid, _ = is_valid_project_key(project_key)
            if is_valid:
                known_projects.add(project_key)
    except Exception:
        return known_projects

    return known_projects


def load_snapshot(config_dict=None, known_projects=None):
    """
    Carga snapshot de mapping contextual desde config.secure activo.

    - Si falla la lectura de config en runtime, conserva el último snapshot válido.
    - Si no hay snapshot previo, devuelve snapshot inválido (fail-closed).
    """
    global _LAST_VALID_RUNTIME_SNAPSHOTS

    runtime_mode = config_dict is None
    config_error = ""
    runtime_metadata = {
        "cache_key": "manual|snapshot",
        "context_identity": "manual|snapshot",
        "config_path": "",
    }
    if runtime_mode:
        config_dict, config_error, runtime_metadata = (
            read_secure_config_with_runtime_metadata()
        )
        runtime_cache_key = str(runtime_metadata.get("cache_key") or "").strip()
        if not runtime_cache_key:
            runtime_cache_key = str(runtime_metadata.get("context_identity") or "").strip()
        if not runtime_cache_key:
            runtime_cache_key = "runtime|unknown"
        if config_dict is None:
            cached_snapshot = _LAST_VALID_RUNTIME_SNAPSHOTS.get(runtime_cache_key)
            if cached_snapshot is not None:
                snapshot = copy.deepcopy(cached_snapshot)
                detail = config_error.strip() or "unknown error"
                _append_unique(
                    snapshot["warnings"],
                    "Could not refresh ProjectBucketOverrides from config.secure; "
                    f"using last valid snapshot: {detail}",
                )
                return snapshot

            snapshot = _new_snapshot()
            snapshot["overrides_schema_valid"] = False
            detail = config_error.strip() or "unknown error"
            snapshot["schema_error"] = (
                "Could not read ProjectBucketOverrides from config.secure: "
                f"{detail}"
            )
            _append_unique(snapshot["warnings"], snapshot["schema_error"])
            return snapshot
    else:
        runtime_cache_key = "manual|snapshot"

    config = config_dict if isinstance(config_dict, dict) else {}
    wasabi_cfg = config.get("Wasabi", {}) if isinstance(config, dict) else {}

    overrides_field_present = False
    raw_overrides_value = {}
    if isinstance(wasabi_cfg, dict) and "ProjectBucketOverrides" in wasabi_cfg:
        overrides_field_present = True
        raw_overrides_value = wasabi_cfg.get("ProjectBucketOverrides")

    discovered_known_projects = _discover_known_projects_from_local_root(config)
    discovered_known_projects.update(_normalize_known_projects(known_projects))
    snapshot = build_snapshot_from_raw_value(
        raw_overrides_value, overrides_field_present, discovered_known_projects
    )
    snapshot["runtime_metadata"] = {
        "cache_key": runtime_cache_key,
        "context_identity": runtime_metadata.get("context_identity", ""),
        "config_path": runtime_metadata.get("config_path", ""),
    }

    if runtime_mode and snapshot.get("overrides_schema_valid", True):
        _LAST_VALID_RUNTIME_SNAPSHOTS[runtime_cache_key] = copy.deepcopy(snapshot)
    return snapshot


def resolve_bucket_for_project(project_name, snapshot=None):
    """Resuelve bucket físico para un proyecto lógico."""
    if snapshot is None:
        snapshot = load_snapshot()

    project_key = normalize_project_key(project_name)
    is_valid_project, project_error = is_valid_project_key(project_key)
    if not is_valid_project:
        return {
            "ok": False,
            "project": "",
            "bucket": "",
            "warning": project_error,
        }

    if not snapshot.get("overrides_schema_valid", True):
        return {
            "ok": False,
            "project": project_key,
            "bucket": "",
            "warning": snapshot.get("schema_error")
            or "ProjectBucketOverrides has an invalid schema.",
        }

    if project_key in snapshot.get("blocked_projects", set()):
        return {
            "ok": False,
            "project": project_key,
            "bucket": "",
            "warning": _blocked_project_message(snapshot, project_key),
        }

    explicit_bucket = snapshot.get("project_to_bucket", {}).get(project_key)
    if explicit_bucket:
        return {"ok": True, "project": project_key, "bucket": explicit_bucket, "warning": ""}

    effective_bucket = snapshot.get("effective_project_to_bucket", {}).get(project_key)
    if effective_bucket:
        return {"ok": True, "project": project_key, "bucket": effective_bucket, "warning": ""}

    fallback_bucket = default_bucket_for_project(project_key)
    if not fallback_bucket:
        return {
            "ok": False,
            "project": project_key,
            "bucket": "",
            "warning": "Could not build a valid fallback bucket.",
        }

    return {"ok": True, "project": project_key, "bucket": fallback_bucket, "warning": ""}


def resolve_project_for_bucket(bucket_name, snapshot=None):
    """Resuelve proyecto lógico para bucket físico."""
    if snapshot is None:
        snapshot = load_snapshot()

    if not snapshot.get("overrides_schema_valid", True):
        return {
            "ok": False,
            "bucket": "",
            "project": "",
            "from_override": False,
            "warning": snapshot.get("schema_error")
            or "ProjectBucketOverrides has an invalid schema.",
        }

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

    if normalized_bucket in snapshot.get("ambiguous_buckets", set()):
        return {
            "ok": False,
            "bucket": normalized_bucket,
            "project": "",
            "from_override": False,
            "warning": _first_bucket_error(snapshot, normalized_bucket)
            or f"Bucket '{normalized_bucket}' is ambiguous in the current mapping.",
        }

    mapped_project = snapshot.get("bucket_to_project", {}).get(normalized_bucket)
    if mapped_project:
        if mapped_project in snapshot.get("blocked_projects", set()):
            return {
                "ok": False,
                "bucket": normalized_bucket,
                "project": "",
                "from_override": False,
                "warning": _blocked_project_message(snapshot, mapped_project),
            }

        from_override = (
            mapped_project in snapshot.get("override_projects", set())
            and snapshot.get("project_to_bucket", {}).get(mapped_project) == normalized_bucket
        )
        return {
            "ok": True,
            "bucket": normalized_bucket,
            "project": mapped_project,
            "from_override": from_override,
            "warning": "",
        }

    if normalized_bucket.startswith("vfx-"):
        candidate_project = normalize_project_key(normalized_bucket[4:])
        is_valid_project, project_error = is_valid_project_key(candidate_project)
        if not is_valid_project:
            return {
                "ok": False,
                "bucket": normalized_bucket,
                "project": "",
                "from_override": False,
                "warning": project_error,
            }

        if candidate_project in snapshot.get("blocked_projects", set()):
            return {
                "ok": False,
                "bucket": normalized_bucket,
                "project": "",
                "from_override": False,
                "warning": _blocked_project_message(snapshot, candidate_project),
            }

        return {
            "ok": True,
            "bucket": normalized_bucket,
            "project": candidate_project,
            "from_override": False,
            "warning": "",
        }

    return {
        "ok": False,
        "bucket": normalized_bucket,
        "project": "",
        "from_override": False,
        "warning": f"Bucket '{normalized_bucket}' is not mapped to any known project.",
    }


def _sanitize_prefix(prefix):
    normalized_prefix = str(prefix or "").strip().replace("\\", "/")
    normalized_prefix = normalized_prefix.strip("/")
    if not normalized_prefix:
        return True, "", []

    parts = [part.strip() for part in normalized_prefix.split("/") if part.strip()]
    for part in parts:
        if part in (".", ".."):
            return False, "", []

    return True, "/".join(parts), parts


def resolve_bucket_from_local_path(local_path, snapshot=None):
    """Resuelve bucket/prefix/proyecto desde una ruta local que contiene VFX-*."""
    if snapshot is None:
        snapshot = load_snapshot()

    normalized_path = os.path.normpath(str(local_path or "").strip()).replace("\\", "/")
    if not normalized_path:
        return {"ok": False, "error": "Local path is empty."}

    parts = [part.strip() for part in normalized_path.split("/") if part.strip()]
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
    is_valid_project, project_error = is_valid_project_key(project_key)
    if not is_valid_project:
        return {
            "ok": False,
            "error": project_error,
        }

    bucket_result = resolve_bucket_for_project(project_key, snapshot=snapshot)
    if not bucket_result.get("ok"):
        return {
            "ok": False,
            "error": bucket_result.get("warning")
            or "Could not resolve project bucket.",
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
