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

# 1.1 Verificar suporte a interface gráfica (Tkinter) no Linux
if ! python3 -c "import tkinter" &>/dev/null && [ ! -f ".venv/lib/libtk8.6.so" ]; then
    echo ""
    echo "------------------------------------------------------"
    if [ -f /etc/os-release ] && grep -qiE "arch|cachyos|manjaro|endeavouros" /etc/os-release; then
        echo "[INFO] O módulo 'tk' não está no sistema. Ele será isolado automaticamente em .venv/lib."
    else
        echo "[AVISO] O módulo 'tkinter' não foi encontrado no Python do sistema."
        echo "A interface gráfica necessita dos pacotes de interface da sua distribuição."
        
        DISTRO_CMD=""
        if [ -f /etc/os-release ]; then
            # shellcheck disable=SC1091
            . /etc/os-release
            case "$ID $ID_LIKE" in
                *ubuntu*|*debian*|*linuxmint*|*pop*)
                    DISTRO_CMD="sudo apt install python3-tk python3-venv" ;;
                *fedora*|*rhel*|*centos*)
                    DISTRO_CMD="sudo dnf install python3-tkinter" ;;
                *suse*)
                    DISTRO_CMD="sudo zypper install python3-tk" ;;
            esac
        fi

        if [ -n "$DISTRO_CMD" ]; then
            echo "Para instalar no seu sistema, execute no terminal:"
            echo "   $DISTRO_CMD"
        else
            echo "Instale o pacote 'tk' ou 'python3-tk' via o gerenciador de pacotes da sua distribuição."
        fi
    fi
    echo "------------------------------------------------------"
    echo ""
fi

# 2. Criar ambiente virtual se não existir
echo "[2/3] Configurando ambiente virtual (.venv)..."
if [ ! -f ".venv/bin/python" ]; then
    echo "Criando ambiente virtual isolado em .venv..."
    if ! python3 -m venv .venv; then
        echo ""
        echo "[ERRO] Falha ao criar o ambiente virtual com 'python3 -m venv'."
        echo "Se estiver no Debian/Ubuntu, instale: sudo apt install python3-venv"
        exit 1
    fi
    echo "Ambiente virtual criado com sucesso."
else
    echo "Ambiente virtual (.venv) já existe."
fi

# 2.1 Isolamento local do Tk no .venv se ausente no sistema
if ! python3 -c "import tkinter" &>/dev/null && [ ! -f ".venv/lib/libtk8.6.so" ]; then
    if [ -f /etc/os-release ] && grep -qiE "arch|cachyos|manjaro|endeavouros" /etc/os-release; then
        echo "Configurando bibliotecas do Tk exclusivamente dentro de .venv/lib (sem necessidade de root)..."
        mkdir -p .venv/lib
        TK_URL=$(pacman -Sp tk 2>/dev/null || echo "https://mirror.krfoss.org/cachyos/repo/x86_64_v3/cachyos-extra-v3/tk-8.6.16-1.1-x86_64.pkg.tar.zst")
        curl -sL "$TK_URL" 2>/dev/null | tar --zstd -xC .venv/lib --strip-components=2 usr/lib/libtk8.6* usr/lib/tk8.6 2>/dev/null || true
        if [ -f ".venv/lib/libtk8.6.so" ]; then
            echo "Tk configurado com sucesso dentro do ambiente virtual."
        fi
    fi
fi
echo ""

# 3. Atualizar pip e instalar dependências
echo "[3/3] Instalando dependências (requirements.txt)..."
if ! .venv/bin/python -m pip --version &>/dev/null; then
    echo "pip não encontrado no ambiente virtual. Instalando com ensurepip..."
    .venv/bin/python -m ensurepip --default-pip
fi
.venv/bin/python -m pip install --upgrade pip --quiet
.venv/bin/python -m pip install -r requirements.txt

echo ""
echo "======================================================"
echo "   Instalação concluída com sucesso!"
echo "======================================================"
echo "Para abrir a interface gráfica, execute: ./iniciar_gui.sh"
echo "======================================================"
