@echo off
chcp 65001 >nul
title Free NFS-e Downloader

set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

REM Garantir que estamos no diretorio do script
cd /d "%~dp0"

set "VENV_PYTHON="
if exist ".venv\Scripts\python.exe" set "VENV_PYTHON=.venv\Scripts\python.exe"
if "%VENV_PYTHON%"=="" if exist "venv\Scripts\python.exe" set "VENV_PYTHON=venv\Scripts\python.exe"
if "%VENV_PYTHON%"=="" if exist "env\Scripts\python.exe" set "VENV_PYTHON=env\Scripts\python.exe"

if not "%VENV_PYTHON%"=="" goto :run_gui

echo ======================================================
echo           Free NFS-e Downloader - Inicio
echo ======================================================
echo.
echo O ambiente virtual .venv com as dependencias ainda
echo nao foi criado.
echo.
echo Deseja executar a instalacao automatica agora? [S/N]
set /p RESPOSTA="Escolha: "
if /i "%RESPOSTA%"=="S" goto :do_install

echo.
echo Para executar o programa, execute primeiro o arquivo:
echo    instalar_dependencias.bat
echo.
pause
exit /b 1

:do_install
echo.
echo Iniciando instalador de dependencias...
call "%~dp0instalar_dependencias.bat"
if exist ".venv\Scripts\python.exe" goto :install_success

echo.
echo Falha ao preparar o ambiente. Tente executar instalar_dependencias.bat manualmente.
pause
exit /b 1

:install_success
set "VENV_PYTHON=.venv\Scripts\python.exe"

:run_gui
echo Iniciando a interface grafica...
"%VENV_PYTHON%" src\gui.py
if errorlevel 1 goto :gui_error
goto :eof

:gui_error
echo.
echo [ERRO] A interface grafica encerrou com erro.
echo.
pause
