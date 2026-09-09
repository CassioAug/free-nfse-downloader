#!/usr/bin/env python3
# free-nfse-downloader
# Copyright (C) 2026 Cassio Soares
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# -*- coding: utf-8 -*-

"""
Script autônomo de aplicação de atualização do free-nfse-downloader.
Executado após o fechamento da GUI principal para contornar bloqueios de arquivos abertos.
"""

import os
import sys
import time
import shutil
import argparse
import subprocess

# Reconfiguração segura de stream para Windows/consoles legados
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Pastas e arquivos que JAMAIS devem ser excluídos ou sobrescritos
EXCLUDED_DIR_NAMES = {
    "certificados",
    "notas_fiscais",
    "cache_nsu",
    ".venv",
    "venv",
    "env",
    ".git",
    "__pycache__",
    ".idea",
    ".vscode",
}

EXCLUDED_FILE_NAMES = {
    ".env",
    "AGENTS.md",
}


def is_pid_running(pid: int) -> bool:
    """Verifica se um determinado processo ainda está ativo no sistema."""
    if pid <= 0:
        return False
    if sys.platform.startswith("win"):
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            SYNCHRONIZE = 0x00100000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
            if handle == 0:
                return False
            exit_code = ctypes.c_ulong()
            kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            kernel32.CloseHandle(handle)
            STILL_ACTIVE = 259
            return exit_code.value == STILL_ACTIVE
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def wait_for_parent_exit(pid: int, timeout: float = 12.0) -> bool:
    """Aguarda o processo pai (GUI) encerrar completamente."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if not is_pid_running(pid):
            return True
        time.sleep(0.4)
    return not is_pid_running(pid)


def apply_files(staging_dir: str, app_dir: str) -> int:
    """
    Copia os novos arquivos da pasta de staging para a pasta do aplicativo,
    respeitando rigorosamente a lista de exclusão para proteção de dados do usuário.
    Retorna a quantidade de arquivos copiados.
    """
    copied_count = 0
    for root, dirs, files in os.walk(staging_dir):
        # Filtra subdiretórios proibidos in-place
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIR_NAMES]

        rel_dir = os.path.relpath(root, staging_dir)
        if rel_dir == ".":
            target_base = app_dir
        else:
            target_base = os.path.join(app_dir, rel_dir)

        # Evitar copiar se o diretório pai cair em exclusão
        parts = rel_dir.split(os.sep)
        if any(p in EXCLUDED_DIR_NAMES for p in parts):
            continue

        for file_name in files:
            if file_name in EXCLUDED_FILE_NAMES:
                continue

            src_file = os.path.join(root, file_name)
            dst_file = os.path.join(target_base, file_name)

            os.makedirs(os.path.dirname(dst_file), exist_ok=True)
            try:
                shutil.copy2(src_file, dst_file)
                copied_count += 1
            except Exception as e:
                print(f"[AVISO] Falha ao copiar {file_name}: {e}")

    return copied_count


def update_dependencies_if_needed(staging_dir: str, app_dir: str, python_exe: str):
    """
    Verifica se o requirements.txt mudou e, se sim, atualiza as dependências do .venv.
    """
    new_req = os.path.join(staging_dir, "requirements.txt")
    app_req = os.path.join(app_dir, "requirements.txt")

    if not os.path.exists(new_req) or not os.path.exists(app_req):
        return

    try:
        with open(new_req, "r", encoding="utf-8") as f1, open(app_req, "r", encoding="utf-8") as f2:
            if f1.read().strip() != f2.read().strip():
                print("[*] Atualizando dependências (pip install -r requirements.txt)...")
                subprocess.run(
                    [python_exe, "-m", "pip", "install", "-r", app_req, "--quiet"],
                    cwd=app_dir,
                    timeout=180,
                    check=False,
                )
    except Exception as e:
        print(f"[AVISO] Falha ao verificar dependências: {e}")


def restart_application(app_dir: str, python_exe: str):
    """Reinicia a interface gráfica do programa no sistema operacional corrente."""
    if sys.platform.startswith("win"):
        bat_launcher = os.path.join(app_dir, "iniciar_gui.bat")
        if os.path.exists(bat_launcher):
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "", bat_launcher],
                cwd=app_dir,
                shell=True,
            )
        else:
            subprocess.Popen(
                [python_exe, os.path.join(app_dir, "src", "gui.py")],
                cwd=app_dir,
            )
    else:
        sh_launcher = os.path.join(app_dir, "iniciar_gui.sh")
        if os.path.exists(sh_launcher):
            os.chmod(sh_launcher, 0o755)
            subprocess.Popen(
                ["/bin/bash", sh_launcher],
                cwd=app_dir,
            )
        else:
            subprocess.Popen(
                [python_exe, os.path.join(app_dir, "src", "gui.py")],
                cwd=app_dir,
            )


def main():
    parser = argparse.ArgumentParser(description="Aplicador de atualizações do free-nfse-downloader")
    parser.add_argument("--pid", type=int, required=True, help="PID do processo principal para aguardar encerramento")
    parser.add_argument("--staging-dir", type=str, required=True, help="Diretório onde a release foi extraída")
    parser.add_argument("--app-dir", type=str, required=True, help="Diretório raiz da aplicação")
    parser.add_argument("--python-exe", type=str, default=sys.executable, help="Caminho do executável Python")
    args = parser.parse_args()

    print(f"[*] Aguardando encerramento do processo anterior (PID {args.pid})...")
    wait_for_parent_exit(args.pid)

    print("[*] Aplicando arquivos atualizados...")
    update_dependencies_if_needed(args.staging_dir, args.app_dir, args.python_exe)
    copied = apply_files(args.staging_dir, args.app_dir)
    print(f"[OK] {copied} arquivos atualizados com sucesso.")

    # Limpeza segura do diretório temporário
    try:
        parent_temp = os.path.dirname(args.staging_dir)
        if "fnfse_update_" in os.path.basename(parent_temp) or "fnfse_update_" in os.path.basename(args.staging_dir):
            shutil.rmtree(parent_temp if "fnfse_update_" in os.path.basename(parent_temp) else args.staging_dir, ignore_errors=True)
    except Exception:
        pass

    print("[*] Reiniciando Free NFS-e Downloader...")
    restart_application(args.app_dir, args.python_exe)


if __name__ == "__main__":
    main()
