import os
import sys
import json
import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.dirname(CURRENT_DIR)
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

from LGA_NKS_BucketResolver import (  # noqa: E402
    is_valid_project_key,
    build_snapshot_from_raw_value,
    load_snapshot,
    normalize_and_validate_overrides,
    resolve_bucket_for_project,
    resolve_bucket_from_local_path,
    resolve_project_folder_from_bucket_and_prefix,
    resolve_project_for_bucket,
)
import LGA_NKS_BucketResolver as bucket_resolver  # noqa: E402
import SecureConfig_Reader as secure_reader  # noqa: E402


def _expect(condition, message):
    if not condition:
        raise AssertionError(message)


def run():
    studio_snapshot = load_snapshot({"Wasabi": {}})
    client_snapshot = load_snapshot(
        {"Wasabi": {"ProjectBucketOverrides": {"ERSO": "vfx-ers0"}}}
    )

    studio_bucket = resolve_bucket_for_project("ERSO", studio_snapshot)
    _expect(studio_bucket["ok"], "Studio: debe resolver bucket")
    _expect(studio_bucket["bucket"] == "vfx-erso", "Studio: fallback legacy incorrecto")

    client_bucket = resolve_bucket_for_project("erso", client_snapshot)
    _expect(client_bucket["ok"], "Client: debe resolver bucket")
    _expect(client_bucket["bucket"] == "vfx-ers0", "Client: override no aplicado")

    local_client = resolve_bucket_from_local_path(
        r"N:\VFX-ERSO\060\ERSO_060_010_WAN", client_snapshot
    )
    _expect(local_client["ok"], "Client: local path no resolvió")
    _expect(local_client["bucket"] == "vfx-ers0", "Client: bucket override incorrecto")
    _expect(
        local_client["prefix"] == "060/ERSO_060_010_WAN",
        "Client: prefix vendor no preservado",
    )

    local_legacy = resolve_bucket_from_local_path(
        r"T:\VFX-MORLASP\1048\MOR_1048_040", client_snapshot
    )
    _expect(local_legacy["ok"], "Legacy: local path no resolvió")
    _expect(local_legacy["bucket"] == "vfx-morlasp", "Legacy: fallback incorrecto")

    reverse_client = resolve_project_folder_from_bucket_and_prefix(
        "vfx-ers0", "060/ERSO_060_010", client_snapshot
    )
    _expect(reverse_client["ok"], "Reverse client: no resolvió")
    _expect(
        reverse_client["project_folder"] == "VFX-ERSO",
        "Reverse client: carpeta local canónica incorrecta",
    )
    _expect(
        reverse_client["local_relative_path"] == "VFX-ERSO/060/ERSO_060_010",
        "Reverse client: path local incorrecto",
    )

    reverse_case = resolve_project_for_bucket("VFX-ERS0", client_snapshot)
    _expect(reverse_case["ok"], "Case-insensitive bucket: no resolvió")
    _expect(reverse_case["project"] == "ERSO", "Case-insensitive bucket: proyecto incorrecto")

    normalized, errors = normalize_and_validate_overrides(
        {
            "erso": "vfx-ers0",
            "VFX-ERSO": "vfx-ers1",
            "MORLASP": "vfx-ers0",
            "BAD": "bad bucket",
        }
    )
    _expect("ERSO" not in normalized, "Overrides: ERSO debe bloquearse por duplicado/colisión")
    _expect(len(errors) >= 2, "Overrides: debería detectar colisiones/errores")

    empty_snapshot = load_snapshot({"Wasabi": {}})
    missing_setting = resolve_bucket_for_project("MORLASP", empty_snapshot)
    _expect(
        missing_setting["bucket"] == "vfx-morlasp",
        "Sin setting nuevo: comportamiento legacy alterado",
    )

    missing_field_snapshot = build_snapshot_from_raw_value(
        {}, False, {"ERSO"}
    )
    missing_field_bucket = resolve_bucket_for_project("ERSO", missing_field_snapshot)
    _expect(missing_field_bucket["ok"], "Campo ausente: debe permitir fallback legacy")
    _expect(
        missing_field_bucket["bucket"] == "vfx-erso",
        "Campo ausente: fallback legacy incorrecto",
    )

    invalid_override_snapshot = build_snapshot_from_raw_value(
        {"ERSO": "BAD BUCKET"},
        True,
        {"ERSO"},
    )
    invalid_override_result = resolve_bucket_for_project("ERSO", invalid_override_snapshot)
    _expect(
        not invalid_override_result["ok"],
        "Override inválido para ERSO debe fallar cerrado",
    )
    _expect(
        "invalid override bucket" in invalid_override_result["warning"].lower(),
        "Override inválido debe devolver warning accionable",
    )
    local_invalid = resolve_bucket_from_local_path(
        r"N:\VFX-ERSO\060\ERSO_060_010", invalid_override_snapshot
    )
    _expect(
        not local_invalid["ok"],
        "Override inválido no debe resolver ruta local",
    )

    empty_project_key_snapshot = build_snapshot_from_raw_value(
        {"VFX-": "vfx-empty"},
        True,
    )
    _expect(
        bool(empty_project_key_snapshot["warnings"]),
        "Clave de proyecto vacía tras normalizar debe devolver warning",
    )

    valid_project_key, project_key_error = is_valid_project_key("ERSO/../../X")
    _expect(not valid_project_key, "Project key insegura debe rechazarse")
    _expect(bool(project_key_error), "Project key insegura debe devolver error accionable")

    unsafe_key_snapshot = build_snapshot_from_raw_value(
        {"ERSO/../../X": "vfx-ers0"},
        True,
    )
    _expect(
        bool(unsafe_key_snapshot["warnings"]),
        "Project key insegura en overrides debe producir warning",
    )
    unsafe_key_result = resolve_bucket_for_project("ERSO/../../X", unsafe_key_snapshot)
    _expect(
        not unsafe_key_result["ok"],
        "Project key insegura debe fallar cerrado en resolución directa",
    )

    schema_invalid_snapshot = build_snapshot_from_raw_value(
        "not-an-object",
        True,
        {"ERSO"},
    )
    schema_invalid_result = resolve_bucket_for_project("ERSO", schema_invalid_snapshot)
    _expect(
        not schema_invalid_result["ok"],
        "Schema no-object debe bloquear resolución",
    )
    _expect(
        "json object" in schema_invalid_result["warning"].lower(),
        "Schema no-object debe advertir error de schema",
    )

    non_string_snapshot = build_snapshot_from_raw_value(
        {"ERSO": 123},
        True,
        {"ERSO"},
    )
    non_string_result = resolve_bucket_for_project("ERSO", non_string_snapshot)
    _expect(
        not non_string_result["ok"],
        "Valor no-string debe bloquear proyecto",
    )

    duplicated_normalized_snapshot = build_snapshot_from_raw_value(
        {"ERSO": "vfx-ers0", "VFX-ERSO": "vfx-ers1"},
        True,
    )
    dup_norm_result = resolve_bucket_for_project("ERSO", duplicated_normalized_snapshot)
    _expect(
        not dup_norm_result["ok"],
        "Duplicado normalizado debe bloquear proyecto",
    )

    duplicated_bucket_snapshot = build_snapshot_from_raw_value(
        {"ERSO": "vfx-dup", "MOR": "vfx-dup"},
        True,
        {"ERSO", "MOR"},
    )
    dup_bucket_erso = resolve_bucket_for_project("ERSO", duplicated_bucket_snapshot)
    dup_bucket_mor = resolve_bucket_for_project("MOR", duplicated_bucket_snapshot)
    _expect(
        not dup_bucket_erso["ok"] and not dup_bucket_mor["ok"],
        "Dos overrides al mismo bucket deben bloquear ambos proyectos",
    )

    collision_snapshot = build_snapshot_from_raw_value(
        {"ERSO": "vfx-mor"},
        True,
        {"ERSO", "MOR"},
    )
    collision_forward = resolve_bucket_for_project("ERSO", collision_snapshot)
    collision_reverse = resolve_project_for_bucket("vfx-mor", collision_snapshot)
    _expect(
        not collision_forward["ok"],
        "Colisión override vs default conocido debe bloquear forward",
    )
    _expect(
        not collision_reverse["ok"],
        "Ambigüedad reverse debe fallar cerrado",
    )

    erso_without_ers0_snapshot = build_snapshot_from_raw_value(
        {"ERSO": "vfx-ers0"},
        True,
        {"ERSO"},
    )
    erso_without_ers0_forward = resolve_bucket_for_project("ERSO", erso_without_ers0_snapshot)
    erso_without_ers0_reverse = resolve_project_for_bucket(
        "vfx-ers0", erso_without_ers0_snapshot
    )
    _expect(
        erso_without_ers0_forward["ok"]
        and erso_without_ers0_forward["bucket"] == "vfx-ers0",
        "ERSO->vfx-ers0 debe ser válido si ERS0 no existe en catálogo",
    )
    _expect(
        erso_without_ers0_reverse["ok"]
        and erso_without_ers0_reverse["project"] == "ERSO",
        "Reverse vfx-ers0 debe resolver ERSO en caso no ambiguo",
    )

    original_reader = bucket_resolver.read_secure_config_with_runtime_metadata
    try:
        bucket_resolver._LAST_VALID_RUNTIME_SNAPSHOTS.clear()
        responses = [
            (
                {"Wasabi": {"ProjectBucketOverrides": {"ERSO": "vfx-ers0"}}},
                "",
                {
                    "cache_key": "studio-key",
                    "context_identity": "pipesync|studio",
                    "config_path": "studio/config.secure",
                },
            ),
            (
                None,
                "config lock busy",
                {
                    "cache_key": "studio-key",
                    "context_identity": "pipesync|studio",
                    "config_path": "studio/config.secure",
                },
            ),
            (
                None,
                "config lock busy",
                {
                    "cache_key": "client-key",
                    "context_identity": "pipesyncclient|client",
                    "config_path": "client/config.secure",
                },
            ),
        ]

        def _fake_reader():
            if not responses:
                raise RuntimeError("No fake responses left")
            return responses.pop(0)

        bucket_resolver.read_secure_config_with_runtime_metadata = _fake_reader

        studio_runtime_snapshot = load_snapshot()
        _expect(
            resolve_bucket_for_project("ERSO", studio_runtime_snapshot)["bucket"] == "vfx-ers0",
            "Runtime studio snapshot debe cargar override",
        )

        studio_fallback_snapshot = load_snapshot()
        _expect(
            resolve_bucket_for_project("ERSO", studio_fallback_snapshot)["bucket"] == "vfx-ers0",
            "Fallo de lectura en mismo contexto debe reutilizar snapshot válido",
        )

        client_failure_snapshot = load_snapshot()
        client_failure_result = resolve_bucket_for_project("ERSO", client_failure_snapshot)
        _expect(
            not client_failure_result["ok"],
            "Fallo de lectura en otro contexto no debe heredar snapshot Studio",
        )
    finally:
        bucket_resolver.read_secure_config_with_runtime_metadata = original_reader

    with TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        config_path = temp_path / "config.secure"
        key_path = temp_path / ".key"
        key = b"test-key-123456"
        key_path.write_bytes(key)

        def _atomic_write(payload_dict, retries=50):
            encrypted = secure_reader.encrypt(json.dumps(payload_dict), key)
            tmp_path = config_path.with_suffix(".tmp")
            tmp_path.write_text(encrypted, encoding="utf-8")
            last_error = None
            for _ in range(max(1, int(retries))):
                try:
                    os.replace(str(tmp_path), str(config_path))
                    return
                except PermissionError as exc:
                    last_error = exc
                    time.sleep(0.003)
            if last_error is not None:
                raise last_error

        payload_a = {"Wasabi": {"ProjectBucketOverrides": {"ERSO": "vfx-ers0"}}, "Version": 1}
        payload_b = {"Wasabi": {"ProjectBucketOverrides": {"ERSO": "vfx-ers1"}}, "Version": 2}
        _atomic_write(payload_a)

        stop_flag = {"stop": False}
        observed_versions = set()
        read_errors = []
        writer_errors = []

        def _writer():
            try:
                for index in range(40):
                    _atomic_write(payload_a if index % 2 == 0 else payload_b)
                    time.sleep(0.005)
            except Exception as exc:  # pragma: no cover - rama defensiva
                writer_errors.append(str(exc))
            finally:
                stop_flag["stop"] = True

        writer_thread = threading.Thread(target=_writer)
        writer_thread.start()

        while not stop_flag["stop"]:
            config_data, _, _ = secure_reader._read_secure_config_from_paths(  # noqa: SLF001
                config_path, key_path
            )
            if config_data is None:
                continue
            version_value = config_data.get("Version")
            if version_value not in (1, 2):
                read_errors.append(version_value)
                break
            observed_versions.add(version_value)

        writer_thread.join()
        _expect(not writer_errors, "Writer concurrente no debe fallar al reemplazar config")
        _expect(not read_errors, "Lectura concurrente no debe devolver payload parcial")
        _expect(observed_versions.issubset({1, 2}), "Solo se deben leer payloads completos")


if __name__ == "__main__":
    run()
    print("test_bucket_resolver: OK")
