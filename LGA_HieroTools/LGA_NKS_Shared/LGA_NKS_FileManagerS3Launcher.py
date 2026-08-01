"""
____________________________________________________________________

  LGA_NKS_FileManagerS3Launcher v1.01 | Lega

  Helper central para lanzar FileManager S3 desde HieroTools.
  Resuelve contexto Studio/Client, rutas dev/prod y comando final
  para Windows/macOS sin usar shell=True.

  v1.01: macOS unifica fuente de verdad: el helper resuelve la ruta del
         .app segun Desarrollo y la pasa al wrapper via --app-path.
  v1.00: Version inicial.
____________________________________________________________________
"""

from pathlib import Path
import os
import subprocess
import sys

from LGA_NKS_ContextProfile import get_context_mode


MODE_STUDIO = "studio"
MODE_CLIENT = "client"

WINDOWS_DEV_EXE = r"C:\Portable\LGA_FileManagerS3\build\FileManagerS3.exe"
# La carpeta instalada paso de `LGA\FileManagerS3` a `LGA\FileManagerS3` en
# FileManager S3 v0.906: el nombre viejo queda reservado para la app local que
# viene despues. Requiere que el usuario actualice FileManager S3 y HieroTools
# juntos; con una sola de las dos partes actualizada el exe no se encuentra.
# La ruta de DEV no cambia: apunta al build del repo, que conserva su nombre.
WINDOWS_PROD_EXE = r"C:\Portable\LGA\FileManagerS3\FileManagerS3.exe"

MAC_DEV_APP = "/Users/leg4/Desktop/Codin/LGA_FileManagerS3/build/FileManagerS3.app"
MAC_PROD_APP = "/Applications/FileManagerS3.app"


def normalize_context_mode(raw_mode):
    mode = str(raw_mode or "").strip().lower()
    return MODE_CLIENT if mode == MODE_CLIENT else MODE_STUDIO


def resolve_context_mode():
    return normalize_context_mode(get_context_mode())


def _existing_path(candidates, path_exists):
    for candidate in candidates:
        if candidate and path_exists(candidate):
            return candidate
    return None


def _resolve_windows_executable(desarrollo, path_exists):
    if desarrollo and path_exists(WINDOWS_DEV_EXE):
        return WINDOWS_DEV_EXE
    if path_exists(WINDOWS_PROD_EXE):
        return WINDOWS_PROD_EXE
    if path_exists(WINDOWS_DEV_EXE):
        return WINDOWS_DEV_EXE
    return None


def _resolve_macos_app(desarrollo, script_dir, path_exists):
    script_path = Path(script_dir) if script_dir else None
    local_app = str(script_path / "build" / "FileManagerS3.app") if script_path else None
    if desarrollo:
        return _existing_path((MAC_DEV_APP, MAC_PROD_APP, local_app), path_exists)
    return _existing_path((MAC_PROD_APP, MAC_DEV_APP, local_app), path_exists)


def build_filemanagers3_command(cli_args,
                              desarrollo=True,
                              script_dir=None,
                              context_mode=None,
                              platform_name=None,
                              path_exists=None):
    context = normalize_context_mode(context_mode or resolve_context_mode())

    raw_args = list(cli_args or [])
    if not raw_args:
        raise ValueError("No CLI arguments were provided for FileManagerS3.")

    # No filtrar silenciosamente: un arg vacio deja flags colgados
    # (["--path", ""] -> ["--path"]). Validar y rechazar con error claro.
    args = []
    for index, raw_arg in enumerate(raw_args):
        value = str(raw_arg)
        if not value.strip():
            preceding = str(raw_args[index - 1]).strip() if index > 0 else ""
            if preceding.startswith("-"):
                raise ValueError(
                    "Empty value for flag '{0}' in FileManagerS3 CLI arguments.".format(
                        preceding
                    )
                )
            raise ValueError(
                "Empty CLI argument at position {0} for FileManagerS3.".format(index)
            )
        args.append(value)

    effective_platform = platform_name or sys.platform
    effective_exists = path_exists or os.path.exists

    if effective_platform == "win32":
        executable = _resolve_windows_executable(bool(desarrollo), effective_exists)
        if not executable:
            raise FileNotFoundError(
                "FileManagerS3.exe was not found in dev/prod paths."
            )
        return [executable, "--context", context] + args

    if effective_platform == "darwin":
        script_path = Path(script_dir) if script_dir else None
        # Fuente unica de verdad: el helper resuelve la ruta del .app segun el
        # flag Desarrollo (_resolve_macos_app). El wrapper queda solo como capa
        # de exec (open -na) y recibe la ruta ya resuelta via --app-path.
        app_path = _resolve_macos_app(bool(desarrollo), script_path, effective_exists)
        wrapper_path = script_path / "fm_cli_mac.sh" if script_path else None
        if wrapper_path and effective_exists(str(wrapper_path)):
            if app_path:
                return (
                    ["bash", str(wrapper_path), "--app-path", app_path,
                     "--context", context]
                    + args
                )
            # Sin candidato resuelto: se delega al wrapper para que honre
            # FILEMANAGER_APP_PATH y muestre su error guia.
            return ["bash", str(wrapper_path), "--context", context] + args

        if not app_path:
            raise FileNotFoundError(
                "FileManagerS3.app was not found in dev/prod paths."
            )
        return ["open", "-na", app_path, "--args", "--context", context] + args

    raise RuntimeError(f"Unsupported platform for FileManagerS3 launcher: {effective_platform}")


def launch_filemanagers3(cli_args, desarrollo=True, script_dir=None, context_mode=None):
    command = build_filemanagers3_command(
        cli_args=cli_args,
        desarrollo=desarrollo,
        script_dir=script_dir,
        context_mode=context_mode,
    )
    subprocess.Popen(command, shell=False)
    return command
