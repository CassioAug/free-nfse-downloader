#!/bin/bash
# Free NFS-e Downloader - Script auxiliar de atualizacao Linux

PID="$1"
STAGING_DIR="$2"
APP_DIR="$3"
PY_EXE="${4:-python3}"

if [ -z "$PID" ] || [ -z "$STAGING_DIR" ] || [ -z "$APP_DIR" ]; then
    echo "Uso: ./run_updater.sh <PID> <STAGING_DIR> <APP_DIR> [<PYTHON_EXE>]"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$PY_EXE" "$SCRIPT_DIR/apply_update.py" --pid "$PID" --staging-dir "$STAGING_DIR" --app-dir "$APP_DIR" --python-exe "$PY_EXE"
