import os
import sys
from pathlib import Path


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SHARED_DIR = os.path.dirname(CURRENT_DIR)
if SHARED_DIR not in sys.path:
    sys.path.insert(0, SHARED_DIR)

import LGA_NKS_FileManagerLauncher as launcher  # noqa: E402


def _expect(condition, message):
    if not condition:
        raise AssertionError(message)


def _exists_factory(paths):
    normalized = {
        str(path).replace("\\", "/").lower()
        for path in paths
    }

    def _exists(path):
        return str(path).replace("\\", "/").lower() in normalized

    return _exists


def _assert_no_legacy_targets(command):
    joined = " ".join(command)
    _expect("FileManager.exe" not in joined, "No debe usar FileManager.exe legacy")
    _expect("FileManager.app" not in joined, "No debe usar FileManager.app legacy")
    _expect("FileManagerS3_Client" not in joined, "No debe usar binario client separado")


def run():
    cli_args = ["--download", r"T:\VFX-ERSO\060\ERSO_060_010"]

    win_exists = _exists_factory(
        {
            launcher.WINDOWS_DEV_EXE,
            launcher.WINDOWS_PROD_EXE,
        }
    )
    win_dev_cmd = launcher.build_filemanager_command(
        cli_args,
        desarrollo=True,
        context_mode="studio",
        platform_name="win32",
        path_exists=win_exists,
    )
    _expect(
        win_dev_cmd[0] == launcher.WINDOWS_DEV_EXE,
        "Windows dev debe priorizar FileManagerS3.exe de build",
    )
    _expect(win_dev_cmd[1:3] == ["--context", "studio"], "Debe propagar --context studio")
    _assert_no_legacy_targets(win_dev_cmd)

    win_prod_only_exists = _exists_factory({launcher.WINDOWS_PROD_EXE})
    win_prod_cmd = launcher.build_filemanager_command(
        cli_args,
        desarrollo=True,
        context_mode="CLIENT",
        platform_name="win32",
        path_exists=win_prod_only_exists,
    )
    _expect(
        win_prod_cmd[0] == launcher.WINDOWS_PROD_EXE,
        "Windows debe caer a FileManagerS3.exe de producción si falta dev",
    )
    _expect(win_prod_cmd[1:3] == ["--context", "client"], "Debe normalizar --context client")
    _assert_no_legacy_targets(win_prod_cmd)

    fake_script_dir = Path("/tmp/fm_launcher_test")
    wrapper_path = str(fake_script_dir / "fm_cli_mac.sh")
    mac_wrapper_exists = _exists_factory({wrapper_path})
    mac_wrapper_cmd = launcher.build_filemanager_command(
        cli_args,
        desarrollo=True,
        script_dir=fake_script_dir,
        context_mode="studio",
        platform_name="darwin",
        path_exists=mac_wrapper_exists,
    )
    _expect(mac_wrapper_cmd[0:2] == ["bash", wrapper_path], "macOS debe usar wrapper si existe")
    _expect(
        mac_wrapper_cmd[2:4] == ["--context", "studio"],
        "Wrapper macOS debe recibir --context",
    )
    _assert_no_legacy_targets(mac_wrapper_cmd)

    mac_app_exists = _exists_factory({launcher.MAC_DEV_APP})
    mac_app_cmd = launcher.build_filemanager_command(
        cli_args,
        desarrollo=True,
        script_dir=fake_script_dir,
        context_mode="client",
        platform_name="darwin",
        path_exists=mac_app_exists,
    )
    _expect(
        launcher.MAC_DEV_APP in mac_app_cmd,
        "macOS sin wrapper debe usar FileManagerS3.app",
    )
    _expect(
        "--context" in mac_app_cmd and "client" in mac_app_cmd,
        "macOS app launch debe incluir --context client",
    )
    _assert_no_legacy_targets(mac_app_cmd)


if __name__ == "__main__":
    run()
    print("test_filemanager_launcher: OK")
