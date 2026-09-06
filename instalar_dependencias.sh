#!/usr/bin/env bash
set -e

# Navega até o diretório do script
cd "$(dirname "$0")"

echo "======================================================"
echo "   Free NFS-e Downloader - Instalador de Dependências"
echo "======================================================"
echo ""

# 1. Verificar se o Python 3 está instalado
echo "[1/3] Verificando instalação do Python..."
if ! command -v python3 &>/dev/null; then
    echo "[ERRO] python3 não foi encontrado. Instale o Python 3.8+ antes de prosseguir."
    exit 1
fi
echo "Python detectado: $(python3 --version)"
echo ""

# 2. Criar ambiente virtual se não existir
echo "[2/3] Configurando ambiente virtual (.venv)..."
if [ ! -f ".venv/bin/python" ]; then
    echo "Criando ambiente virtual isolado em .venv..."
    python3 -m venv .venv
    echo "Ambiente virtual criado com sucesso."
else
    echo "Ambiente virtual (.venv) já existe."
fi
echo ""

# 3. Atualizar pip e instalar dependências
echo "[3/3] Instalando dependências (requirements.txt)..."
.venv/bin/python -m pip install --upgrade pip --quiet
.venv/bin/python -m pip install -r requirements.txt

echo ""
echo "======================================================"
echo "   Instalação concluída com sucesso!"
echo "======================================================"
echo "Para abrir a interface gráfica, execute: ./iniciar_gui.sh"
echo "======================================================"
