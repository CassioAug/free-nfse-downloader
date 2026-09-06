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

echo "Iniciando a interface gráfica..."
"$VENV_PYTHON" gui.py
