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

import os
import sys
import json
import tempfile
import zipfile
import shutil
import subprocess
import urllib.request
import urllib.error

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

DEFAULT_REPO = "CassioAug/free-nfse-downloader"


def parse_version(ver_str: str) -> tuple:
    """
    Extrai tupla de inteiros para comparação semântica de versões.
    Exemplos:
        'v2.1.0' -> (2, 1, 0)
        '2.2'    -> (2, 2, 0)
        '2.10.1-rc1' -> (2, 10, 1)
    """
    if not ver_str:
        return (0, 0, 0)
    cleaned = str(ver_str).strip().lstrip("v").split("-")[0].split("+")[0]
    parts = []
    for p in cleaned.split("."):
        digits = "".join(ch for ch in p if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def is_newer_version(remote_ver: str, local_ver: str) -> bool:
    """Retorna True se remote_ver for estritamente maior que local_ver."""
    return parse_version(remote_ver) > parse_version(local_ver)


def check_for_updates(current_version: str, repo: str = DEFAULT_REPO, timeout: int = 4) -> dict | None:
    """
    Consulta a API pública do GitHub para verificar se há uma nova versão disponível.
    Retorna um dicionário com os detalhes da release se houver versão mais recente,
    ou None se o software já estiver atualizado ou ocorrer falha de rede/timeout.
    """
    url = f"https://api.github.com/repos/{repo}/releases/latest"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "free-nfse-downloader-updater",
            "Accept": "application/vnd.github.v3+json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None

    remote_tag = data.get("tag_name", "")
    if not remote_tag or not is_newer_version(remote_tag, current_version):
        return None

    # Localizar link do arquivo .zip da release
    zip_url = None
    assets = data.get("assets", [])
    for asset in assets:
        name = asset.get("name", "")
        if name.endswith(".zip") and "free-nfse-downloader" in name:
            zip_url = asset.get("browser_download_url")
            break

    if not zip_url:
        for asset in assets:
            if asset.get("name", "").endswith(".zip"):
                zip_url = asset.get("browser_download_url")
                break

    if not zip_url:
        zip_url = data.get("zipball_url")

    clean_version = remote_tag.lstrip("v")
    body_text = data.get("body") or "Nenhuma nota de versão disponibilizada."

    return {
        "version": clean_version,
        "tag_name": remote_tag,
        "title": data.get("name") or f"Release {remote_tag}",
        "body": body_text,
        "html_url": data.get("html_url") or f"https://github.com/{repo}/releases",
        "zip_url": zip_url,
        "published_at": data.get("published_at", ""),
    }


def download_and_extract_update(zip_url: str, progress_callback=None) -> str:
    """
    Baixa o arquivo .zip da release e extrai em diretório temporário de staging.
    Retorna o caminho absoluto do diretório onde residem os arquivos atualizados.
    progress_callback: função opcional chamada com (percent_float_0_to_1, downloaded_bytes, total_bytes)
    """
    temp_dir = tempfile.mkdtemp(prefix="fnfse_update_")
    zip_path = os.path.join(temp_dir, "update.zip")
    extract_dir = os.path.join(temp_dir, "extracted")
    os.makedirs(extract_dir, exist_ok=True)

    req = urllib.request.Request(
        zip_url,
        headers={"User-Agent": "free-nfse-downloader-updater"},
    )

    with urllib.request.urlopen(req, timeout=30) as resp:
        total_size = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 64 * 1024  # 64 KB

        with open(zip_path, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total_size > 0:
                    percent = min(1.0, downloaded / total_size)
                    progress_callback(percent, downloaded, total_size)

    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(extract_dir)

    # Localizar a raiz do projeto no zip descompactado
    app_root = extract_dir
    for root, dirs, files in os.walk(extract_dir):
        if "iniciar_gui.bat" in files or "iniciar_gui.sh" in files or "README.md" in files:
            app_root = root
            break
        elif "version.py" in files or "gui.py" in files:
            app_root = root
            break

    return app_root


def trigger_update_process(staging_dir: str, app_dir: str | None = None) -> bool:
    """
    Dispara o processo desanexado de atualização (apply_update.py) e prepara
    para o encerramento seguro da aplicação atual.
    """
    if not app_dir:
        # Raiz do projeto (pai de src/)
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    python_exe = sys.executable
    current_pid = os.getpid()

    # Copiar o script apply_update.py do staging para uma pasta temporária neutra
    temp_runner_dir = tempfile.mkdtemp(prefix="fnfse_runner_")
    runner_script_src = os.path.join(staging_dir, "scripts", "apply_update.py")
    if not os.path.exists(runner_script_src):
        runner_script_src = os.path.join(app_dir, "scripts", "apply_update.py")

    runner_script_dst = os.path.join(temp_runner_dir, "apply_update.py")
    shutil.copy2(runner_script_src, runner_script_dst)

    if sys.platform.startswith("win"):
        launcher_bat = os.path.join(temp_runner_dir, "run_update.bat")
        with open(launcher_bat, "w", encoding="utf-8") as f:
            f.write("@echo off\n")
            f.write("chcp 65001 >nul\n")
            f.write("timeout /t 1 /nobreak >nul\n")
            f.write(
                f'"{python_exe}" "{runner_script_dst}" --pid {current_pid} '
                f'--staging-dir "{staging_dir}" --app-dir "{app_dir}" --python-exe "{python_exe}"\n'
            )
            f.write('del "%~f0"\n')

        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        subprocess.Popen(
            ["cmd.exe", "/c", launcher_bat],
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP,
            close_fds=True,
            shell=False,
        )
    else:
        launcher_sh = os.path.join(temp_runner_dir, "run_update.sh")
        with open(launcher_sh, "w", encoding="utf-8") as f:
            f.write("#!/bin/bash\n")
            f.write("sleep 1\n")
            f.write(
                f'"{python_exe}" "{runner_script_dst}" --pid {current_pid} '
                f'--staging-dir "{staging_dir}" --app-dir "{app_dir}" --python-exe "{python_exe}"\n'
            )
            f.write('rm -f "$0"\n')
        os.chmod(launcher_sh, 0o755)

        subprocess.Popen(
            ["/bin/bash", launcher_sh],
            start_new_session=True,
            close_fds=True,
        )

    return True
