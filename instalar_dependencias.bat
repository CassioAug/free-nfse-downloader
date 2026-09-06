@echo off
chcp 65001 >nul
title Free NFS-e Downloader - Instalador de Dependencias

echo ======================================================
echo    Free NFS-e Downloader - Instalador de Dependencias
echo ======================================================
echo.

REM Garantir que estamos no diretorio do script
cd /d "%~dp0"

REM 1. Verificar se o Python esta instalado
echo [1/4] Verificando instalacao do Python...

where python >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=python"
    goto :python_found
)

where py >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set "PYTHON_CMD=py"
    goto :python_found
)

echo.
echo [ERRO] O Python nao foi encontrado no seu computador!
echo.
echo Para utilizar este programa, voce precisa ter o Python 3.8 ou superior instalado.
echo.
echo Como resolver:
echo  1. Acesse: https://www.python.org/downloads/
echo  2. Baixe e instale a versao mais recente do Python.
echo  3. IMPORTANTE: Na tela de instalacao, marque a opcao para adicionar o Python ao PATH.
echo  4. Apos a instalacao, execute este instalador novamente.
echo.
pause
exit /b 1

:python_found
for /f "tokens=*" %%i in ('"%PYTHON_CMD%" --version 2^>^&1') do echo Python detectado: %%i
echo.

REM 2. Criar o ambiente virtual (.venv) se nao existir
echo [2/4] Configurando ambiente virtual .venv...
if exist ".venv\Scripts\python.exe" goto :venv_exists

echo Criando ambiente virtual isolado em .venv...
"%PYTHON_CMD%" -m venv .venv
if errorlevel 1 goto :venv_error

echo Ambiente virtual criado com sucesso.
goto :venv_ready

:venv_exists
echo Ambiente virtual .venv ja existe.

:venv_ready
echo.

REM 3. Atualizar pip e instalar dependencias do requirements.txt
echo [3/4] Instalando dependencias - requirements.txt...
echo Atualizando o pip...
".venv\Scripts\python.exe" -m pip install --upgrade pip --quiet

echo Instalando pacotes necessarios...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :pip_error

echo Pacotes instalados com sucesso!
echo.

REM 4. Configurar navegador para Playwright
echo [4/4] Verificando navegador Chromium para certificados A3 - Playwright...
".venv\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 goto :playwright_warn

echo Navegador Chromium configurado com sucesso!
goto :finish

:playwright_warn
echo.
echo [AVISO] Nao foi possivel instalar o Chromium automaticamente.
echo Se voce nao utiliza certificado em Token USB A3, ignore este aviso.
goto :finish

:venv_error
echo.
echo [ERRO] Falha ao criar o ambiente virtual isolado .venv.
pause
exit /b 1

:pip_error
echo.
echo [ERRO] Ocorreu uma falha ao instalar os pacotes via pip.
echo Verifique sua conexao com a internet e tente novamente.
pause
exit /b 1

:finish
echo.
echo ======================================================
echo    Instalacao concluida com sucesso!
echo ======================================================
echo.
echo Para abrir a interface grafica do programa, basta executar:
echo    iniciar_gui.bat
echo.
echo ======================================================
pause
