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

# Diretório base do projeto (onde este script reside)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Pastas padrão do projeto
CERT_DIR = os.path.join(BASE_DIR, "certificados")
NOTAS_DIR = os.path.join(BASE_DIR, "notas_fiscais")


def ensure_directories(base_dir=None, verbose=False):
    """
    Verifica se as pastas essenciais ('certificados' e 'notas_fiscais')
    existem e as cria caso ainda não existam.
    
    Args:
        base_dir (str, optional): Caminho base onde as pastas devem existir.
                                  Se None, usa o diretório do projeto.
        verbose (bool): Se True, imprime mensagem ao criar diretórios.
        
    Returns:
        tuple: (caminho_certificados, caminho_notas_fiscais)
    """
    if base_dir is None:
        base_dir = BASE_DIR

    cert_path = os.path.join(base_dir, "certificados")
    notas_path = os.path.join(base_dir, "notas_fiscais")

    dirs_to_create = [
        ("certificados", cert_path),
        ("notas_fiscais", notas_path),
    ]

    for name, path in dirs_to_create:
        if not os.path.exists(path):
            os.makedirs(path, exist_ok=True)
            if verbose:
                print(f"[setup_dirs] Pasta '{name}' criada em: {path}")

    return cert_path, notas_path


# Garante automaticamente a criação das pastas ao importar o módulo
ensure_directories()


if __name__ == "__main__":
    print("Verificando e configurando pastas padrão...")
    c_dir, n_dir = ensure_directories(verbose=True)
    print("Pastas configuradas com sucesso:")
    print(f"  - Certificados:  {c_dir}")
    print(f"  - Notas Fiscais: {n_dir}")
