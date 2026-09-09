#!/usr/bin/env bash

# Navega até o diretório do script
cd "$(dirname "$0")"

VENV_PYTHON=""
if [ -f ".venv/bin/python" ]; then
    VENV_PYTHON=".venv/bin/python"
elif [ -f "venv/bin/python" ]; then
    VENV_PYTHON="venv/bin/python"
elif [ -f "env/bin/python" ]; then
    VENV_PYTHON="env/bin/python"
fi

if [ -z "$VENV_PYTHON" ]; then
    echo "======================================================"
    echo "       Free NFS-e Downloader - Início"
    echo "======================================================"
    echo "Ambiente virtual (.venv) não encontrado."
    echo "Deseja instalar as dependências agora? (s/n)"
    read -r RESPOSTA
    if [[ "$RESPOSTA" =~ ^[Ss]$ ]]; then
        bash ./instalar_dependencias.sh
        VENV_PYTHON=".venv/bin/python"
    else
        echo "Execute ./instalar_dependencias.sh antes de iniciar."
        exit 1
    fi
fi

# Configurar bibliotecas locais do Tk (isoladas no .venv), se existirem
SCRIPT_DIR="$(pwd)"
if [ -f "$SCRIPT_DIR/.venv/lib/libtk8.6.so" ]; then
    export LD_LIBRARY_PATH="$SCRIPT_DIR/.venv/lib:${LD_LIBRARY_PATH:-}"
    export TK_LIBRARY="$SCRIPT_DIR/.venv/lib/tk8.6"
fi

echo "Iniciando a interface gráfica..."
"$VENV_PYTHON" src/gui.py
