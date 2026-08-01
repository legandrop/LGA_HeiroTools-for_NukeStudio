#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_DEV_APP="/Users/leg4/Desktop/Codin/LGA_FileManagerS3/build/FileManagerS3.app"
DEFAULT_PROD_APP="/Applications/FileManagerS3.app"
DEFAULT_LOCAL_APP="$SCRIPT_DIR/build/FileManagerS3.app"

# El launcher central (LGA_NKS_FileManagerS3Launcher) es la unica fuente de verdad
# de la ruta del .app: resuelve dev/prod segun el flag Desarrollo y la pasa aca
# como "--app-path <ruta>". Se consume y NO se reenvia a la app. El fallback
# dev/prod de abajo queda solo para uso manual del wrapper (sin --app-path).
APP_PATH_OVERRIDE=""
if [ "${1:-}" = "--app-path" ]; then
    if [ $# -lt 2 ]; then
        echo "Falta la ruta despues de --app-path."
        exit 1
    fi
    APP_PATH_OVERRIDE="$2"
    shift 2
fi

if [ -n "${FILEMANAGER_APP_PATH:-}" ]; then
    APP_PATH="$FILEMANAGER_APP_PATH"
elif [ -n "$APP_PATH_OVERRIDE" ]; then
    APP_PATH="$APP_PATH_OVERRIDE"
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
    echo "Uso: $0 [--app-path <ruta>] [--path <ruta>] [--download <ruta>] [--upload <ruta>] [--fm-path <ruta>] ..."
    exit 1
fi

# Forzar nueva instancia para que macOS entregue args incluso con app abierta.
open -na "$APP_PATH" --args "$@"
