#!/usr/bin/env python3
"""
Classifica NFS-e em serviços prestados ou tomados e organiza em subpastas.
Pode ser usado como módulo (import get_service_type) ou como script independente.

Uso standalone:
    python3 organize_nfse.py --dir ./notas_fiscais/12345678000199 --cnpj 12345678000199
    python3 organize_nfse.py --dir ./notas_fiscais/12345678000199 --cnpj 12345678000199 --log ./organizar.log
"""
import os
import sys
import re
import shutil
import logging
import xml.etree.ElementTree as ET

logger = logging.getLogger("free_nfse_downloader")


def get_service_type(xml_str, cnpj_label):
    """
    Determina se a NFS-e é um serviço prestado ou tomado, comparando
    o CNPJ da empresa com o CNPJ do emitente/prestador e do tomador no XML.

    Estratégia:
    1. Procura CNPJ dentro de tags-filhas de <emit>, <prest>, <PrestadorServico>
       (prestador) e <toma>, <tomador>, <TomadorServico> (tomador)
    2. Se não encontrar, varre o XML inteiro por tags <CNPJ> e tenta
       inferir pela ordem (primeiro CNPJ é do prestador, segundo é tomador)

    Retorna 'prestado', 'tomado' ou None (indeterminado).
    """
    if not cnpj_label or not xml_str:
        return None

    try:
        root = ET.fromstring(xml_str)
        cnpjs_emit = []
        cnpjs_toma = []

        for el in root.iter():
            tag_local = el.tag.split('}')[-1] if '}' in el.tag else el.tag

            if tag_local.lower() in ('emit', 'prest', 'prestadorservico'):
                for child in el.iter():
                    child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    if child_tag.upper() == 'CNPJ' and child.text:
                        cnpjs_emit.append(re.sub(r'\D', '', child.text))

            if tag_local.lower() in ('toma', 'tomador', 'tomadorservico'):
                for child in el.iter():
                    child_tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                    if child_tag.upper() == 'CNPJ' and child.text:
                        cnpjs_toma.append(re.sub(r'\D', '', child.text))

        if cnpj_label in cnpjs_emit:
            logger.info(f"    -> CNPJ {cnpj_label} é PRESTADOR (encontrado em emit/prest)")
            return 'prestado'

        if cnpj_label in cnpjs_toma:
            logger.info(f"    -> CNPJ {cnpj_label} é TOMADOR (encontrado em toma)")
            return 'tomado'

        # --- FALLBACK: varre o XML inteiro por tags CNPJ ---
        todos_cnpjs = []
        for el in root.iter():
            tag_local = el.tag.split('}')[-1] if '}' in el.tag else el.tag
            if tag_local.upper() == 'CNPJ' and el.text:
                todos_cnpjs.append(re.sub(r'\D', '', el.text))

        vistos = set()
        cnpj_ordenados = []
        for c in todos_cnpjs:
            if c not in vistos:
                vistos.add(c)
                cnpj_ordenados.append(c)

        if cnpj_label in cnpj_ordenados:
            idx = cnpj_ordenados.index(cnpj_label)
            if idx == 0:
                logger.info(f"    -> CNPJ {cnpj_label} é o primeiro CNPJ do XML → PRESTADOR (fallback)")
                return 'prestado'
            elif idx >= 1:
                logger.info(f"    -> CNPJ {cnpj_label} é o {idx+1}º CNPJ do XML → TOMADOR (fallback)")
                return 'tomado'

        logger.warning(f"Não foi possível classificar serviço. "
                       f"cnpj_label={cnpj_label}, "
                       f"emit={cnpjs_emit}, toma={cnpjs_toma}, "
                       f"todos_CNPJs={cnpj_ordenados}")
        return None

    except Exception as e:
        logger.warning(f"Erro ao classificar tipo de serviço: {e}")
        return None


def organize_directory(directory, cnpj_label):
    """
    Varre um diretório por arquivos XML de NFS-e, classifica cada um
    como serviço prestado ou tomado, e move para a subpasta correspondente.

    Args:
        directory: Caminho do diretório raiz (ex: ./notas_fiscais/12345678000199)
        cnpj_label: CNPJ da empresa (apenas dígitos, 14 caracteres)
    """
    if not os.path.isdir(directory):
        logger.error(f"Diretório não encontrado: {directory}")
        return

    prestados_dir = os.path.join(directory, "prestados")
    tomados_dir = os.path.join(directory, "tomados")

    for d in (prestados_dir, tomados_dir):
        os.makedirs(d, exist_ok=True)

    prestados = tomados = indeterminados = erros = 0

    for fname in sorted(os.listdir(directory)):
        fpath = os.path.join(directory, fname)

        if not os.path.isfile(fpath) or not fname.lower().endswith('.xml'):
            continue

        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                xml_str = f.read()
        except Exception as e:
            logger.error(f"  {fname}: erro ao ler arquivo: {e}")
            erros += 1
            continue

        tipo = get_service_type(xml_str, cnpj_label)

        if tipo == 'prestado':
            shutil.move(fpath, os.path.join(prestados_dir, fname))
            prestados += 1
            logger.info(f"  {fname} → prestados/")
        elif tipo == 'tomado':
            shutil.move(fpath, os.path.join(tomados_dir, fname))
            tomados += 1
            logger.info(f"  {fname} → tomados/")
        else:
            indeterminados += 1
            logger.warning(f"  {fname} → indeterminado (mantido na raiz)")

    total = prestados + tomados + indeterminados + erros
    logger.info(f"Organização concluída: {prestados} prestados, {tomados} tomados, "
                f"{indeterminados} indeterminados, {erros} erros ({total} arquivos)")

    print(f"\nResumo:")
    print(f"  Serviços prestados: {prestados}")
    print(f"  Serviços tomados:  {tomados}")
    print(f"  Indeterminados:    {indeterminados}")
    if erros:
        print(f"  Erros:             {erros}")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Classifica NFS-e em serviços prestados/tomados e organiza em subpastas"
    )
    parser.add_argument(
        "--dir", "-d", required=True,
        help="Diretório com os XMLs das NFS-e (ex: ./notas_fiscais/12345678000199)"
    )
    parser.add_argument(
        "--cnpj", "-c", required=True,
        help="CNPJ da empresa (apenas números, 14 dígitos)"
    )
    parser.add_argument(
        "--log", "-l",
        help="Arquivo de log (opcional; se omitido, exibe apenas no terminal)"
    )

    args = parser.parse_args()

    cnpj = re.sub(r'\D', '', args.cnpj)
    if len(cnpj) != 14:
        print("Erro: CNPJ deve ter 14 dígitos.")
        return 1

    # Configura logging para execução standalone
    log_format = "%(asctime)s [%(levelname)s] %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"
    handlers = [logging.StreamHandler(sys.stdout)]
    if args.log:
        handlers.append(logging.FileHandler(args.log, encoding="utf-8"))

    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt=date_format,
        handlers=handlers
    )

    logger.info(f"Organizando NFS-e em: {args.dir}")
    logger.info(f"CNPJ da empresa: {cnpj}")

    organize_directory(args.dir, cnpj)

    return 0


if __name__ == "__main__":
    sys.exit(main())
