#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_DEV_APP="/Users/leg4/Desktop/Codin/LGA_FileManager/build/FileManagerS3.app"
DEFAULT_PROD_APP="/Applications/FileManagerS3.app"
DEFAULT_LOCAL_APP="$SCRIPT_DIR/build/FileManagerS3.app"

if [ -n "${FILEMANAGER_APP_PATH:-}" ]; then
    APP_PATH="$FILEMANAGER_APP_PATH"
elif [ -d "$DEFAULT_DEV_APP" ]; then
    APP_PATH="$DEFAULT_DEV_APP"
elif [ -d "$DEFAULT_PROD_APP" ]; then
    APP_PATH="$DEFAULT_PROD_APP"
else
    APP_PATH="$DEFAULT_LOCAL_APP"
fi

if [ ! -d "$APP_PATH" ]; then
    echo "FileManagerS3.app no encontrada en: $APP_PATH"
    echo "Definí FILEMANAGER_APP_PATH con la ruta del .app (build o deploy)."
    exit 1
fi

if [ $# -eq 0 ]; then
    echo "Uso: $0 [--path <ruta>] [--download <ruta>] [--upload <ruta>] [--fm-path <ruta>] ..."
    exit 1
fi

# Forzar nueva instancia para que macOS entregue args incluso con app abierta.
open -na "$APP_PATH" --args "$@"
