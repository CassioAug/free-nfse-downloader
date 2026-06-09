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
import argparse
from glob import glob

# Adiciona o diretório atual ao path para garantir importação
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from download_nfse import CustomDanfse, HAS_DANFSE_LIB
except ImportError as e:
    print(f"Erro ao importar dependências do download_nfse.py: {e}")
    sys.exit(1)

def convert_single_xml(xml_path, output_dir=None, overwrite=False):
    """Converte um único arquivo XML para PDF"""
    if not os.path.isfile(xml_path):
        print(f"Erro: O arquivo '{xml_path}' não existe.")
        return False

    if not xml_path.lower().endswith(".xml"):
        print(f"Aviso: O arquivo '{xml_path}' não possui extensão .xml, tentando prosseguir...")

    # Define o nome do PDF de saída
    base_name = os.path.splitext(os.path.basename(xml_path))[0]
    target_dir = output_dir if output_dir else os.path.dirname(os.path.abspath(xml_path))
    pdf_path = os.path.join(target_dir, f"{base_name}.pdf")

    if os.path.exists(pdf_path) and not overwrite:
        print(f"  [PULADO] PDF já existe: {os.path.basename(pdf_path)}")
        return True

    try:
        with open(xml_path, "r", encoding="utf-8") as f:
            xml_content = f.read()

        danfse = CustomDanfse(xml=xml_content)
        danfse.output(pdf_path)
        print(f"  [SUCESSO] PDF gerado: {os.path.basename(pdf_path)}")
        return True
    except Exception as e:
        print(f"  [ERRO] Falha ao converter '{os.path.basename(xml_path)}': {e}")
        return False

def convert_batch(input_path, output_dir=None, overwrite=False):
    """Converte múltiplos arquivos XML contidos em uma pasta"""
    if not os.path.exists(input_path):
        print(f"Erro: O caminho de entrada '{input_path}' não existe.")
        return

    # Se for um arquivo único
    if os.path.isfile(input_path):
        convert_single_xml(input_path, output_dir, overwrite)
        return

    # Se for um diretório, buscar todos os XMLs
    xml_files = glob(os.path.join(input_path, "*.xml"))
    if not xml_files:
        print(f"Nenhum arquivo XML encontrado na pasta '{input_path}'.")
        return

    print(f"Encontrados {len(xml_files)} arquivo(s) XML em '{input_path}'. Iniciando conversão...")
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    success_count = 0
    skipped_count = 0
    error_count = 0

    for xml_path in sorted(xml_files):
        # Determina se vai ser pulado
        base_name = os.path.splitext(os.path.basename(xml_path))[0]
        target_dir = output_dir if output_dir else os.path.dirname(os.path.abspath(xml_path))
        pdf_path = os.path.join(target_dir, f"{base_name}.pdf")

        if os.path.exists(pdf_path) and not overwrite:
            skipped_count += 1
            continue

        res = convert_single_xml(xml_path, output_dir, overwrite)
        if res:
            success_count += 1
        else:
            error_count += 1

    print("-" * 50)
    print("Processo de conversão concluído:")
    print(f"  - PDFs gerados com sucesso: {success_count}")
    print(f"  - Arquivos pulados (já existentes): {skipped_count}")
    print(f"  - Erros na conversão: {error_count}")

def main():
    if not HAS_DANFSE_LIB:
        print("Erro: A biblioteca 'brazilfiscalreport' não está instalada ou configurada.")
        print("Execute 'python download_nfse.py' uma vez para instalar as dependências necessárias.")
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Conversor de Notas Fiscais de Serviço Eletrônicas (NFS-e XML) para DANFSE (PDF)"
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="./notas_fiscais",
        help="Caminho do arquivo XML ou da pasta contendo os XMLs (padrão: ./notas_fiscais)"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Pasta de destino para os PDFs (padrão: mesma pasta dos XMLs)"
    )
    parser.add_argument(
        "-f", "--force",
        action="store_true",
        help="Força a conversão e sobrescreve PDFs já existentes"
    )

    args = parser.parse_args()

    input_path = args.input
    output_dir = args.output
    overwrite = args.force

    print(f"Iniciando conversão de XML para PDF...")
    convert_batch(input_path, output_dir, overwrite)

if __name__ == "__main__":
    main()
