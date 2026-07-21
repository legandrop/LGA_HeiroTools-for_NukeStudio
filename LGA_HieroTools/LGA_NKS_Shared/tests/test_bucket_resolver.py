import os
import sys


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.dirname(CURRENT_DIR)
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

from LGA_NKS_BucketResolver import (  # noqa: E402
    load_snapshot,
    normalize_and_validate_overrides,
    resolve_bucket_for_project,
    resolve_bucket_from_local_path,
    resolve_project_folder_from_bucket_and_prefix,
    resolve_project_for_bucket,
)


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
    _expect("ERSO" in normalized, "Overrides: debería conservar entrada válida")
    _expect(len(errors) >= 2, "Overrides: debería detectar colisiones/errores")

    empty_snapshot = load_snapshot({"Wasabi": {}})
    missing_setting = resolve_bucket_for_project("MORLASP", empty_snapshot)
    _expect(
        missing_setting["bucket"] == "vfx-morlasp",
        "Sin setting nuevo: comportamiento legacy alterado",
    )


if __name__ == "__main__":
    run()
    print("test_bucket_resolver: OK")
