@echo off
chcp 65001 >nul
title Free NFS-e Downloader - Atualizador

set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

REM Argumentos:
REM %1 = PID do processo principal
REM %2 = Diretorio de staging com os novos arquivos
REM %3 = Diretorio raiz da aplicacao
REM %4 = Executavel Python (opcional)

if "%~1"=="" goto :usage
if "%~2"=="" goto :usage
if "%~3"=="" goto :usage

set "PY_EXE=%~4"
if "%PY_EXE%"=="" set "PY_EXE=python"

echo [*] Executando atualizador em segundo plano...
"%PY_EXE%" "%~dp0apply_update.py" --pid %1 --staging-dir "%~2" --app-dir "%~3" --python-exe "%PY_EXE%"
goto :eof

:usage
echo Uso: run_updater.bat ^<PID^> ^<STAGING_DIR^> ^<APP_DIR^> [^<PYTHON_EXE^>]
pause
