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

"""
Módulo de persistência em banco de dados SQLite para o Free NFS-e Downloader.
Gerencia as tabelas de notas fiscais, índices de NSU e histórico de sincronização.
"""

import os
import sys
import re
import json
import shutil
import sqlite3
import logging
from datetime import datetime, date
import xml.etree.ElementTree as ET

try:
    import setup_dirs
    DEFAULT_DB_PATH = setup_dirs.DB_PATH
except Exception:
    DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dados", "nfse.db")

logger = logging.getLogger("free_nfse_downloader")

NON_DIGITS = re.compile(r'\D')


def get_connection(db_path=None):
    """
    Retorna uma conexão SQLite configurada com modo WAL e row_factory como sqlite3.Row.
    """
    path = db_path or DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    return conn


def init_db(db_path=None):
    """
    Inicializa o schema do banco de dados SQLite criando as tabelas e índices se não existirem.
    """
    conn = get_connection(db_path)
    try:
        with conn:
            # 1. Tabela de Notas Fiscais
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notas_fiscais (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chave_acesso TEXT UNIQUE,
                    numero_nfse TEXT,
                    serie TEXT,
                    tipo TEXT,
                    status TEXT DEFAULT 'autorizada',
                    data_emissao TEXT,
                    data_competencia TEXT,
                    nsu INTEGER,
                    cnpj_consultado TEXT,
                    prestador_cnpj_cpf TEXT,
                    prestador_nome TEXT,
                    prestador_im TEXT,
                    prestador_municipio TEXT,
                    tomador_cnpj_cpf TEXT,
                    tomador_nome TEXT,
                    tomador_im TEXT,
                    tomador_municipio TEXT,
                    valor_servico REAL DEFAULT 0.0,
                    valor_liquido REAL DEFAULT 0.0,
                    valor_iss REAL DEFAULT 0.0,
                    iss_retido INTEGER DEFAULT 0,
                    aliquota_iss REAL DEFAULT 0.0,
                    valor_pis REAL DEFAULT 0.0,
                    valor_cofins REAL DEFAULT 0.0,
                    valor_inss REAL DEFAULT 0.0,
                    valor_ir REAL DEFAULT 0.0,
                    valor_csll REAL DEFAULT 0.0,
                    codigo_tributacao_nacional TEXT,
                    discriminacao_servico TEXT,
                    motivo_cancelamento TEXT,
                    data_cancelamento TEXT,
                    nsu_cancelamento INTEGER,
                    caminho_xml TEXT,
                    caminho_pdf TEXT,
                    created_at TEXT,
                    updated_at TEXT
                );
            """)

            # Migração dinâmica de colunas para tabelas já existentes
            cursor = conn.execute("PRAGMA table_info(notas_fiscais);")
            existing_cols = {row["name"] for row in cursor.fetchall()}
            if "motivo_cancelamento" not in existing_cols:
                conn.execute("ALTER TABLE notas_fiscais ADD COLUMN motivo_cancelamento TEXT;")
            if "data_cancelamento" not in existing_cols:
                conn.execute("ALTER TABLE notas_fiscais ADD COLUMN data_cancelamento TEXT;")
            if "nsu_cancelamento" not in existing_cols:
                conn.execute("ALTER TABLE notas_fiscais ADD COLUMN nsu_cancelamento INTEGER;")

            # Índices de performance para notas fiscais
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notas_cnpj_data ON notas_fiscais(cnpj_consultado, data_emissao);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notas_chave ON notas_fiscais(chave_acesso);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notas_numero ON notas_fiscais(numero_nfse);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notas_tipo ON notas_fiscais(tipo);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notas_status ON notas_fiscais(status);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notas_prestador ON notas_fiscais(prestador_cnpj_cpf);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_notas_tomador ON notas_fiscais(tomador_cnpj_cpf);")

            # 2. Tabela de Índice de NSUs
            conn.execute("""
                CREATE TABLE IF NOT EXISTS nsu_index (
                    cnpj TEXT,
                    ambiente TEXT,
                    nsu INTEGER,
                    data_emissao TEXT,
                    created_at TEXT,
                    PRIMARY KEY (cnpj, ambiente, nsu)
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_nsu_lookup ON nsu_index(cnpj, ambiente, data_emissao);")

            # 3. Tabela de Histórico de Sincronizações
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sync_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cnpj TEXT,
                    ambiente TEXT,
                    data_inicio_consulta TEXT,
                    data_fim_consulta TEXT,
                    nsu_inicial INTEGER,
                    nsu_final INTEGER,
                    total_baixadas INTEGER DEFAULT 0,
                    status TEXT,
                    mensagem_erro TEXT,
                    created_at TEXT
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sync_cnpj ON sync_history(cnpj, created_at);")

        logger.debug(f"Banco de dados inicializado com sucesso em: '{db_path or DEFAULT_DB_PATH}'")
    finally:
        conn.close()


def _clean_str(val):
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


def _to_float(val):
    if val is None:
        return 0.0
    try:
        if isinstance(val, (int, float)):
            return float(val)
        s = str(val).strip().replace(',', '.')
        return float(s) if s else 0.0
    except (ValueError, TypeError):
        return 0.0


def extract_event_metadata(xml_str):
    """
    Extrai metadados de um XML de Evento da NFS-e (ex: Cancelamento de NFS-e).
    Retorna um dicionário com os detalhes do evento ou None se não for um evento válido.
    """
    if not xml_str:
        return None

    if isinstance(xml_str, bytes):
        try:
            xml_str = xml_str.decode('utf-8', errors='replace')
        except Exception:
            return None

    try:
        root = ET.fromstring(xml_str)
    except Exception as e:
        logger.debug(f"Erro ao parsear XML de evento: {e}")
        return None

    # Verifica se a raiz ou algum elemento é evento
    root_tag = root.tag.split('}')[-1] if '}' in root.tag else root.tag
    is_event = root_tag.lower() in ('evento', 'infevento', 'pedregevento', 'procevento')
    if not is_event:
        for el in root.iter():
            t = el.tag.split('}')[-1].lower()
            if t in ('evento', 'infevento', 'pedregevento'):
                is_event = True
                break
    if not is_event:
        return None

    event_data = {
        "tipo_evento": "outro",
        "codigo_evento": None,
        "descricao_evento": None,
        "chave_acesso": None,
        "motivo": None,
        "data_evento": None,
        "cnpj_autor": None,
        "versao": root.attrib.get("versao", "1.00")
    }

    for el in root.iter():
        tag_local = el.tag.split('}')[-1] if '}' in el.tag else el.tag
        tag_lower = tag_local.lower()

        # Identificação de Cancelamento (e101101, infPedCan, etc.)
        if tag_lower in ('e101101', 'cancnfse', 'cancelamento', 'infpedcan'):
            event_data["tipo_evento"] = "cancelamento"
            event_data["codigo_evento"] = "101101"

        if tag_lower in ('tpevento', 'tp_evento') and el.text:
            code = el.text.strip()
            event_data["codigo_evento"] = code
            if code in ('101101', '101'):
                event_data["tipo_evento"] = "cancelamento"

        if tag_lower in ('xdesc', 'descri') and el.text:
            desc = el.text.strip()
            event_data["descricao_evento"] = desc
            if 'cancel' in desc.lower():
                event_data["tipo_evento"] = "cancelamento"

        if tag_lower in ('xmotivo', 'justificativa', 'motivo') and el.text and not event_data["motivo"]:
            event_data["motivo"] = el.text.strip()

        if tag_lower in ('chnfse', 'chavenfse', 'chdfe') and el.text:
            clean_ch = NON_DIGITS.sub('', el.text)
            if len(clean_ch) >= 40:
                event_data["chave_acesso"] = clean_ch

        if tag_lower in ('dhevento', 'dhproc', 'dhregevento', 'datahora') and el.text and not event_data["data_evento"]:
            m = re.match(r'^(\d{4}-\d{2}-\d{2})', el.text.strip())
            if m:
                event_data["data_evento"] = m.group(1)

        if tag_lower in ('cnpjautor', 'cnpj') and el.text and not event_data["cnpj_autor"]:
            event_data["cnpj_autor"] = NON_DIGITS.sub('', el.text)

    # Fallback para chave de acesso a partir de atributos Id (ex: EVT... ou PRE...)
    if not event_data["chave_acesso"]:
        for el in root.iter():
            if 'Id' in el.attrib:
                val_id = el.attrib['Id']
                clean_id = re.sub(r'^[a-zA-Z]+', '', val_id)
                if len(clean_id) >= 50:
                    event_data["chave_acesso"] = clean_id[:50]
                    break
                elif len(clean_id) >= 40:
                    event_data["chave_acesso"] = clean_id
                    break

    return event_data


def cancel_nota_by_key(chave_acesso, motivo=None, data_cancelamento=None, nsu_evento=None, db_path=None):
    """
    Marca uma nota fiscal como cancelada no banco de dados e renomeia
    os arquivos XML e PDF existentes em disco para incluir o sufixo '_cancelada'.
    
    Retorna o dicionário atualizado da nota ou None.
    """
    if not chave_acesso:
        return None

    chave_clean = NON_DIGITS.sub('', str(chave_acesso))
    conn = get_connection(db_path)
    now_iso = datetime.now().isoformat()
    try:
        with conn:
            row = conn.execute("SELECT * FROM notas_fiscais WHERE chave_acesso = ?", (chave_clean,)).fetchone()
            if not row:
                row = conn.execute("SELECT * FROM notas_fiscais WHERE chave_acesso LIKE ?", (f"%{chave_clean}%",)).fetchone()

            if not row:
                logger.debug(f"Nota com chave {chave_clean} não encontrada no banco para cancelamento imediato.")
                return None

            nota_dict = dict(row)
            old_xml = nota_dict.get("caminho_xml")
            old_pdf = nota_dict.get("caminho_pdf")

            new_xml = old_xml
            new_pdf = old_pdf

            # 1. Renomeia arquivo XML se existir e ainda não tiver '_cancelada'
            if old_xml and os.path.isfile(old_xml):
                dir_name, file_name = os.path.split(old_xml)
                base, ext = os.path.splitext(file_name)
                if not base.endswith("_cancelada"):
                    new_xml = os.path.join(dir_name, f"{base}_cancelada{ext}")
                    try:
                        if os.path.exists(new_xml) and os.path.abspath(new_xml) != os.path.abspath(old_xml):
                            os.remove(new_xml)
                        os.replace(old_xml, new_xml)
                        logger.info(f"    -> XML renomeado para cancelada: {os.path.basename(new_xml)}")
                    except Exception as e:
                        logger.warning(f"Erro ao renomear XML para cancelada: {e}")
                        new_xml = old_xml

            # 2. Renomeia arquivo PDF se existir e ainda não tiver '_cancelada'
            if old_pdf and os.path.isfile(old_pdf):
                dir_name, file_name = os.path.split(old_pdf)
                base, ext = os.path.splitext(file_name)
                if not base.endswith("_cancelada"):
                    new_pdf = os.path.join(dir_name, f"{base}_cancelada{ext}")
                    try:
                        if os.path.exists(new_pdf) and os.path.abspath(new_pdf) != os.path.abspath(old_pdf):
                            os.remove(new_pdf)
                        os.replace(old_pdf, new_pdf)
                        logger.info(f"    -> PDF renomeado para cancelada: {os.path.basename(new_pdf)}")
                    except Exception as e:
                        logger.warning(f"Erro ao renomear PDF para cancelada: {e}")
                        new_pdf = old_pdf
            elif old_xml:
                # Verifica se há PDF no mesmo diretório com nome base antigo
                dir_name, file_name = os.path.split(old_xml)
                base_orig = os.path.splitext(file_name)[0].replace("_cancelada", "")
                candidate_pdf = os.path.join(dir_name, f"{base_orig}.pdf")
                if os.path.isfile(candidate_pdf):
                    new_candidate = os.path.join(dir_name, f"{base_orig}_cancelada.pdf")
                    try:
                        if os.path.exists(new_candidate) and os.path.abspath(new_candidate) != os.path.abspath(candidate_pdf):
                            os.remove(new_candidate)
                        os.replace(candidate_pdf, new_candidate)
                        new_pdf = new_candidate
                    except Exception:
                        pass

            # 3. Atualiza banco de dados
            dt_canc = data_cancelamento or nota_dict.get("data_cancelamento") or now_iso[:10]
            mot_canc = motivo or nota_dict.get("motivo_cancelamento")

            conn.execute("""
                UPDATE notas_fiscais SET
                    status = 'cancelada',
                    motivo_cancelamento = COALESCE(?, motivo_cancelamento),
                    data_cancelamento = COALESCE(?, data_cancelamento),
                    nsu_cancelamento = COALESCE(?, nsu_cancelamento),
                    caminho_xml = ?,
                    caminho_pdf = ?,
                    updated_at = ?
                WHERE id = ?;
            """, (
                mot_canc,
                dt_canc,
                nsu_evento,
                new_xml,
                new_pdf,
                now_iso,
                nota_dict["id"]
            ))

            nota_dict["status"] = "cancelada"
            nota_dict["motivo_cancelamento"] = mot_canc
            nota_dict["data_cancelamento"] = dt_canc
            nota_dict["caminho_xml"] = new_xml
            nota_dict["caminho_pdf"] = new_pdf
            return nota_dict
    finally:
        conn.close()


def extract_nota_metadata(xml_str, cnpj_consultado=None):
    """
    Extrai todos os metadados cadastrais, fiscais e tributários do XML de uma NFS-e
    no padrão nacional ADN ou municipal.

    Retorna um dicionário estruturado com as colunas correspondentes à tabela notas_fiscais.
    """
    if not xml_str:
        return None

    if isinstance(xml_str, bytes):
        try:
            xml_str = xml_str.decode('utf-8', errors='replace')
        except Exception:
            return None

    cnpj_clean = NON_DIGITS.sub('', str(cnpj_consultado)) if cnpj_consultado else None

    try:
        root = ET.fromstring(xml_str)
    except Exception as e:
        logger.warning(f"Erro ao parsear XML para extração de metadados: {e}")
        return None

    data = {
        "chave_acesso": None,
        "numero_nfse": None,
        "serie": None,
        "tipo": None,
        "status": "autorizada",
        "data_emissao": None,
        "data_competencia": None,
        "nsu": None,
        "cnpj_consultado": cnpj_clean,
        "prestador_cnpj_cpf": None,
        "prestador_nome": None,
        "prestador_im": None,
        "prestador_municipio": None,
        "tomador_cnpj_cpf": None,
        "tomador_nome": None,
        "tomador_im": None,
        "tomador_municipio": None,
        "valor_servico": 0.0,
        "valor_liquido": 0.0,
        "valor_iss": 0.0,
        "iss_retido": 0,
        "aliquota_iss": 0.0,
        "valor_pis": 0.0,
        "valor_cofins": 0.0,
        "valor_inss": 0.0,
        "valor_ir": 0.0,
        "valor_csll": 0.0,
        "codigo_tributacao_nacional": None,
        "discriminacao_servico": None,
        "motivo_cancelamento": None,
        "data_cancelamento": None,
        "nsu_cancelamento": None,
        "caminho_xml": None,
        "caminho_pdf": None
    }

    # 1. Chave de acesso (Id em <infNFSe>, <NFSe>, <chNFSe>, etc.)
    for el in root.iter():
        tag_local = el.tag.split('}')[-1] if '}' in el.tag else el.tag
        tag_lower = tag_local.lower()

        if tag_lower in ('infnfse', 'dps', 'infdps') and 'Id' in el.attrib:
            val_id = el.attrib['Id']
            clean_id = re.sub(r'^[a-zA-Z]+', '', val_id)
            if len(clean_id) >= 40:
                data["chave_acesso"] = clean_id
                break

        if tag_lower in ('chnfse', 'chavenfse', 'chave'):
            if el.text and len(NON_DIGITS.sub('', el.text)) >= 40:
                data["chave_acesso"] = NON_DIGITS.sub('', el.text)
                break

    if not data["chave_acesso"]:
        match = re.search(r'\b\d{50}\b', xml_str)
        if match:
            data["chave_acesso"] = match.group(0)

    # 2. Número da NFS-e e Série
    for el in root.iter():
        tag_local = el.tag.split('}')[-1] if '}' in el.tag else el.tag
        tag_lower = tag_local.lower()

        if not data["numero_nfse"] and tag_lower in ('nnfse', 'numeronfse', 'numero', 'ndps'):
            if el.text:
                data["numero_nfse"] = el.text.strip()

        if not data["serie"] and tag_lower in ('serie', 'serienfse', 'seriedps', 'sdps'):
            if el.text:
                data["serie"] = el.text.strip()

    # 3. Datas (Emissão e Competência)
    for el in root.iter():
        tag_local = el.tag.split('}')[-1] if '}' in el.tag else el.tag
        tag_lower = tag_local.lower()

        if not data["data_emissao"] and tag_lower in ('dhemi', 'dataemissao', 'dtemissao', 'dtemi'):
            if el.text:
                m = re.match(r'^(\d{4}-\d{2}-\d{2})', el.text.strip())
                if m:
                    data["data_emissao"] = m.group(1)

        if not data["data_competencia"] and tag_lower in ('dcompet', 'dtcompetencia', 'competencia', 'dhcompet'):
            if el.text:
                m = re.match(r'^(\d{4}-\d{2}-\d{2})', el.text.strip())
                if m:
                    data["data_competencia"] = m.group(1)

    # Se data de competência não foi encontrada, usa data de emissão
    if not data["data_competencia"]:
        data["data_competencia"] = data["data_emissao"]

    # 4. Prestador e Tomador
    for el in root.iter():
        tag_local = el.tag.split('}')[-1] if '}' in el.tag else el.tag
        tag_lower = tag_local.lower()

        # Prestador / Emitente
        if tag_lower in ('emit', 'prest', 'prestadorservico', 'prestador'):
            for child in el.iter():
                ctag = (child.tag.split('}')[-1] if '}' in child.tag else child.tag).lower()
                if ctag in ('cnpj', 'cpf') and child.text and not data["prestador_cnpj_cpf"]:
                    data["prestador_cnpj_cpf"] = NON_DIGITS.sub('', child.text)
                elif ctag in ('xnome', 'razaosocial', 'nome') and child.text and not data["prestador_nome"]:
                    data["prestador_nome"] = child.text.strip()
                elif ctag in ('im', 'inscricaomunicipal') and child.text and not data["prestador_im"]:
                    data["prestador_im"] = child.text.strip()
                elif ctag in ('xmun', 'municipio') and child.text and not data["prestador_municipio"]:
                    data["prestador_municipio"] = child.text.strip()

        # Tomador
        if tag_lower in ('toma', 'tomador', 'tomadorservico'):
            for child in el.iter():
                ctag = (child.tag.split('}')[-1] if '}' in child.tag else child.tag).lower()
                if ctag in ('cnpj', 'cpf') and child.text and not data["tomador_cnpj_cpf"]:
                    data["tomador_cnpj_cpf"] = NON_DIGITS.sub('', child.text)
                elif ctag in ('xnome', 'razaosocial', 'nome') and child.text and not data["tomador_nome"]:
                    data["tomador_nome"] = child.text.strip()
                elif ctag in ('im', 'inscricaomunicipal') and child.text and not data["tomador_im"]:
                    data["tomador_im"] = child.text.strip()
                elif ctag in ('xmun', 'municipio') and child.text and not data["tomador_municipio"]:
                    data["tomador_municipio"] = child.text.strip()

    # 5. Classificação do Tipo (Prestado x Tomado)
    if cnpj_clean:
        if data["prestador_cnpj_cpf"] == cnpj_clean:
            data["tipo"] = "prestado"
        elif data["tomador_cnpj_cpf"] == cnpj_clean:
            data["tipo"] = "tomado"
        else:
            try:
                from organize_nfse import get_service_type
                data["tipo"] = get_service_type(xml_str, cnpj_clean)
            except Exception:
                pass

    # 6. Valores, Tributos e Status de Cancelamento
    for el in root.iter():
        tag_local = el.tag.split('}')[-1] if '}' in el.tag else el.tag
        tag_lower = tag_local.lower()

        if tag_lower in ('vserv', 'valorservicos', 'vservprest') and el.text:
            data["valor_servico"] = _to_float(el.text)
        elif tag_lower in ('vliq', 'valorliquidonfse') and el.text:
            data["valor_liquido"] = _to_float(el.text)
        elif tag_lower in ('viss', 'vissqn', 'valoriss') and el.text:
            data["valor_iss"] = _to_float(el.text)
        elif tag_lower in ('tpretiss', 'issretido') and el.text:
            txt = el.text.strip().lower()
            data["iss_retido"] = 1 if txt in ('1', 'true', 'sim', 's') else 0
        elif tag_lower in ('paliq', 'aliquota', 'paliqissqn') and el.text:
            data["aliquota_iss"] = _to_float(el.text)
        elif tag_lower in ('vpis', 'valorpis') and el.text:
            data["valor_pis"] = _to_float(el.text)
        elif tag_lower in ('vcofins', 'valorcofins') and el.text:
            data["valor_cofins"] = _to_float(el.text)
        elif tag_lower in ('vinss', 'valorinss') and el.text:
            data["valor_inss"] = _to_float(el.text)
        elif tag_lower in ('vir', 'valorir', 'virrf') and el.text:
            data["valor_ir"] = _to_float(el.text)
        elif tag_lower in ('vcsll', 'valorcsll') and el.text:
            data["valor_csll"] = _to_float(el.text)
        elif tag_lower in ('ctribnac', 'codigotributacaonacional') and el.text and not data["codigo_tributacao_nacional"]:
            data["codigo_tributacao_nacional"] = el.text.strip()
        elif tag_lower in ('xdescserv', 'discriminacao', 'discserv') and el.text and not data["discriminacao_servico"]:
            data["discriminacao_servico"] = el.text.strip()
        elif tag_lower in ('e101101', 'cancnfse', 'cancelamento', 'infpedcan'):
            data["status"] = "cancelada"

    # Se valor líquido não estiver explícito, calcula aproximado (vServ - retenções)
    if data["valor_liquido"] == 0.0 and data["valor_servico"] > 0:
        retencoes = (data["valor_pis"] + data["valor_cofins"] + data["valor_inss"] +
                     data["valor_ir"] + data["valor_csll"] + (data["valor_iss"] if data["iss_retido"] else 0))
        data["valor_liquido"] = max(0.0, data["valor_servico"] - retencoes)

    return data


def upsert_nota_fiscal(dados, db_path=None):
    """
    Insere ou atualiza um registro de NFS-e na tabela notas_fiscais.
    Garante a integridade por chave_acesso ou (numero_nfse, cnpj_consultado).
    Preserva o status 'cancelada' se a nota já tiver sido cancelada.
    """
    if not isinstance(dados, dict):
        return None

    conn = get_connection(db_path)
    now_iso = datetime.now().isoformat()
    try:
        with conn:
            chave = _clean_str(dados.get("chave_acesso"))
            numero = _clean_str(dados.get("numero_nfse"))
            cnpj_consultado = _clean_str(dados.get("cnpj_consultado"))

            existing = None
            if chave:
                existing = conn.execute("SELECT id, status, caminho_xml, caminho_pdf FROM notas_fiscais WHERE chave_acesso = ?", (chave,)).fetchone()
            elif numero and cnpj_consultado:
                existing = conn.execute(
                    "SELECT id, status, caminho_xml, caminho_pdf FROM notas_fiscais WHERE numero_nfse = ? AND cnpj_consultado = ?",
                    (numero, cnpj_consultado)
                ).fetchone()

            if existing:
                row_id = existing["id"]
                c_xml = dados.get("caminho_xml") or existing["caminho_xml"]
                c_pdf = dados.get("caminho_pdf") or existing["caminho_pdf"]

                novo_status = dados.get("status")
                # Se a nota existente já for cancelada e o dado recebido for 'autorizada', preserva 'cancelada'
                if existing["status"] == "cancelada" and (not novo_status or novo_status == "autorizada"):
                    status_final = "cancelada"
                else:
                    status_final = novo_status or existing["status"] or "autorizada"

                conn.execute("""
                    UPDATE notas_fiscais SET
                        numero_nfse = COALESCE(?, numero_nfse),
                        serie = COALESCE(?, serie),
                        tipo = COALESCE(?, tipo),
                        status = ?,
                        data_emissao = COALESCE(?, data_emissao),
                        data_competencia = COALESCE(?, data_competencia),
                        nsu = COALESCE(?, nsu),
                        cnpj_consultado = COALESCE(?, cnpj_consultado),
                        prestador_cnpj_cpf = COALESCE(?, prestador_cnpj_cpf),
                        prestador_nome = COALESCE(?, prestador_nome),
                        prestador_im = COALESCE(?, prestador_im),
                        prestador_municipio = COALESCE(?, prestador_municipio),
                        tomador_cnpj_cpf = COALESCE(?, tomador_cnpj_cpf),
                        tomador_nome = COALESCE(?, tomador_nome),
                        tomador_im = COALESCE(?, tomador_im),
                        tomador_municipio = COALESCE(?, tomador_municipio),
                        valor_servico = CASE WHEN ? > 0 THEN ? ELSE valor_servico END,
                        valor_liquido = CASE WHEN ? > 0 THEN ? ELSE valor_liquido END,
                        valor_iss = CASE WHEN ? > 0 THEN ? ELSE valor_iss END,
                        iss_retido = COALESCE(?, iss_retido),
                        aliquota_iss = CASE WHEN ? > 0 THEN ? ELSE aliquota_iss END,
                        valor_pis = CASE WHEN ? > 0 THEN ? ELSE valor_pis END,
                        valor_cofins = CASE WHEN ? > 0 THEN ? ELSE valor_cofins END,
                        valor_inss = CASE WHEN ? > 0 THEN ? ELSE valor_inss END,
                        valor_ir = CASE WHEN ? > 0 THEN ? ELSE valor_ir END,
                        valor_csll = CASE WHEN ? > 0 THEN ? ELSE valor_csll END,
                        codigo_tributacao_nacional = COALESCE(?, codigo_tributacao_nacional),
                        discriminacao_servico = COALESCE(?, discriminacao_servico),
                        motivo_cancelamento = COALESCE(?, motivo_cancelamento),
                        data_cancelamento = COALESCE(?, data_cancelamento),
                        nsu_cancelamento = COALESCE(?, nsu_cancelamento),
                        caminho_xml = ?,
                        caminho_pdf = ?,
                        updated_at = ?
                    WHERE id = ?;
                """, (
                    dados.get("numero_nfse"),
                    dados.get("serie"),
                    dados.get("tipo"),
                    status_final,
                    dados.get("data_emissao"),
                    dados.get("data_competencia"),
                    dados.get("nsu"),
                    dados.get("cnpj_consultado"),
                    dados.get("prestador_cnpj_cpf"),
                    dados.get("prestador_nome"),
                    dados.get("prestador_im"),
                    dados.get("prestador_municipio"),
                    dados.get("tomador_cnpj_cpf"),
                    dados.get("tomador_nome"),
                    dados.get("tomador_im"),
                    dados.get("tomador_municipio"),
                    _to_float(dados.get("valor_servico")), _to_float(dados.get("valor_servico")),
                    _to_float(dados.get("valor_liquido")), _to_float(dados.get("valor_liquido")),
                    _to_float(dados.get("valor_iss")), _to_float(dados.get("valor_iss")),
                    dados.get("iss_retido"),
                    _to_float(dados.get("aliquota_iss")), _to_float(dados.get("aliquota_iss")),
                    _to_float(dados.get("valor_pis")), _to_float(dados.get("valor_pis")),
                    _to_float(dados.get("valor_cofins")), _to_float(dados.get("valor_cofins")),
                    _to_float(dados.get("valor_inss")), _to_float(dados.get("valor_inss")),
                    _to_float(dados.get("valor_ir")), _to_float(dados.get("valor_ir")),
                    _to_float(dados.get("valor_csll")), _to_float(dados.get("valor_csll")),
                    dados.get("codigo_tributacao_nacional"),
                    dados.get("discriminacao_servico"),
                    dados.get("motivo_cancelamento"),
                    dados.get("data_cancelamento"),
                    dados.get("nsu_cancelamento"),
                    c_xml,
                    c_pdf,
                    now_iso,
                    row_id
                ))
                return row_id
            else:
                cursor = conn.execute("""
                    INSERT INTO notas_fiscais (
                        chave_acesso, numero_nfse, serie, tipo, status,
                        data_emissao, data_competencia, nsu, cnpj_consultado,
                        prestador_cnpj_cpf, prestador_nome, prestador_im, prestador_municipio,
                        tomador_cnpj_cpf, tomador_nome, tomador_im, tomador_municipio,
                        valor_servico, valor_liquido, valor_iss, iss_retido, aliquota_iss,
                        valor_pis, valor_cofins, valor_inss, valor_ir, valor_csll,
                        codigo_tributacao_nacional, discriminacao_servico,
                        motivo_cancelamento, data_cancelamento, nsu_cancelamento,
                        caminho_xml, caminho_pdf, created_at, updated_at
                    ) VALUES (
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?, ?,
                        ?, ?, ?,
                        ?, ?, ?, ?
                    );
                """, (
                    chave,
                    dados.get("numero_nfse"),
                    dados.get("serie"),
                    dados.get("tipo"),
                    dados.get("status", "autorizada"),
                    dados.get("data_emissao"),
                    dados.get("data_competencia"),
                    dados.get("nsu"),
                    dados.get("cnpj_consultado"),
                    dados.get("prestador_cnpj_cpf"),
                    dados.get("prestador_nome"),
                    dados.get("prestador_im"),
                    dados.get("prestador_municipio"),
                    dados.get("tomador_cnpj_cpf"),
                    dados.get("tomador_nome"),
                    dados.get("tomador_im"),
                    dados.get("tomador_municipio"),
                    _to_float(dados.get("valor_servico")),
                    _to_float(dados.get("valor_liquido")),
                    _to_float(dados.get("valor_iss")),
                    dados.get("iss_retido", 0),
                    _to_float(dados.get("aliquota_iss")),
                    _to_float(dados.get("valor_pis")),
                    _to_float(dados.get("valor_cofins")),
                    _to_float(dados.get("valor_inss")),
                    _to_float(dados.get("valor_ir")),
                    _to_float(dados.get("valor_csll")),
                    dados.get("codigo_tributacao_nacional"),
                    dados.get("discriminacao_servico"),
                    dados.get("motivo_cancelamento"),
                    dados.get("data_cancelamento"),
                    dados.get("nsu_cancelamento"),
                    dados.get("caminho_xml"),
                    dados.get("caminho_pdf"),
                    now_iso,
                    now_iso
                ))
                return cursor.lastrowid
    finally:
        conn.close()


def update_nota_paths(chave_acesso=None, numero_nfse=None, cnpj_consultado=None, caminho_xml=None, caminho_pdf=None, tipo=None, db_path=None):
    """
    Atualiza os caminhos de arquivos (XML/PDF) e tipo para uma nota já existente.
    """
    conn = get_connection(db_path)
    now_iso = datetime.now().isoformat()
    try:
        with conn:
            where_clauses = []
            params = []
            if chave_acesso:
                where_clauses.append("chave_acesso = ?")
                params.append(chave_acesso)
            elif numero_nfse and cnpj_consultado:
                where_clauses.append("numero_nfse = ? AND cnpj_consultado = ?")
                params.extend([numero_nfse, cnpj_consultado])
            elif caminho_xml:
                where_clauses.append("caminho_xml = ?")
                params.append(caminho_xml)
            else:
                return False

            set_clauses = ["updated_at = ?"]
            set_params = [now_iso]

            if caminho_xml:
                set_clauses.append("caminho_xml = ?")
                set_params.append(caminho_xml)
            if caminho_pdf:
                set_clauses.append("caminho_pdf = ?")
                set_params.append(caminho_pdf)
            if tipo:
                set_clauses.append("tipo = ?")
                set_params.append(tipo)

            query = f"UPDATE notas_fiscais SET {', '.join(set_clauses)} WHERE {' AND '.join(where_clauses)};"
            cursor = conn.execute(query, set_params + params)
            return cursor.rowcount > 0
    finally:
        conn.close()


# --- Funções do Índice de NSU ---

def save_nsu_index_entry(cnpj, ambiente, nsu_val, emission_date, db_path=None):
    """
    Grava ou atualiza uma entrada de NSU na tabela nsu_index.
    """
    if not cnpj or not nsu_val or not emission_date:
        return

    cnpj_clean = NON_DIGITS.sub('', str(cnpj))
    date_str = emission_date.isoformat() if hasattr(emission_date, 'isoformat') else str(emission_date)
    now_iso = datetime.now().isoformat()

    conn = get_connection(db_path)
    try:
        with conn:
            conn.execute("""
                INSERT INTO nsu_index (cnpj, ambiente, nsu, data_emissao, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(cnpj, ambiente, nsu) DO UPDATE SET
                    data_emissao = excluded.data_emissao;
            """, (cnpj_clean, str(ambiente), int(nsu_val), date_str, now_iso))
    finally:
        conn.close()


def load_nsu_index(cnpj, ambiente, db_path=None):
    """
    Carrega o índice completo de NSUs para um dado CNPJ e ambiente como um dicionário {nsu: date_obj}.
    """
    if not cnpj:
        return {}

    cnpj_clean = NON_DIGITS.sub('', str(cnpj))
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT nsu, data_emissao FROM nsu_index WHERE cnpj = ? AND ambiente = ? ORDER BY nsu ASC;",
            (cnpj_clean, str(ambiente))
        ).fetchall()

        index = {}
        for row in rows:
            try:
                index[int(row["nsu"])] = date.fromisoformat(row["data_emissao"])
            except Exception:
                pass
        return index
    finally:
        conn.close()


# --- Histórico de Sincronizações ---

def record_sync_history(cnpj, ambiente, start_date, end_date, nsu_ini, nsu_fim, total, status, error_msg=None, db_path=None):
    """
    Registra uma sessão de sincronização na tabela sync_history.
    """
    cnpj_clean = NON_DIGITS.sub('', str(cnpj)) if cnpj else None
    d_ini = start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else str(start_date)
    d_fim = end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else str(end_date)
    now_iso = datetime.now().isoformat()

    conn = get_connection(db_path)
    try:
        with conn:
            cursor = conn.execute("""
                INSERT INTO sync_history (
                    cnpj, ambiente, data_inicio_consulta, data_fim_consulta,
                    nsu_inicial, nsu_final, total_baixadas, status,
                    mensagem_erro, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (
                cnpj_clean, str(ambiente), d_ini, d_fim,
                nsu_ini, nsu_fim, int(total or 0), status,
                error_msg, now_iso
            ))
            return cursor.lastrowid
    finally:
        conn.close()


# --- Consultas e Relatórios ---

def query_notas(cnpj=None, tipo=None, status=None, start_date=None, end_date=None, search_text=None, limit=500, offset=0, db_path=None):
    """
    Consulta notas fiscais com filtros dinâmicos de CNPJ, tipo, status, período e texto de busca.
    """
    conn = get_connection(db_path)
    try:
        clauses = []
        params = []

        if cnpj:
            cnpj_clean = NON_DIGITS.sub('', str(cnpj))
            clauses.append("cnpj_consultado = ?")
            params.append(cnpj_clean)

        if tipo and tipo in ('prestado', 'tomado'):
            clauses.append("tipo = ?")
            params.append(tipo)

        if status and status in ('autorizada', 'cancelada'):
            clauses.append("status = ?")
            params.append(status)

        if start_date:
            d_ini = start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else str(start_date)
            clauses.append("data_emissao >= ?")
            params.append(d_ini)

        if end_date:
            d_fim = end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else str(end_date)
            clauses.append("data_emissao <= ?")
            params.append(d_fim)

        if search_text:
            s = f"%{search_text.strip()}%"
            clauses.append("""(
                numero_nfse LIKE ? OR
                chave_acesso LIKE ? OR
                prestador_nome LIKE ? OR
                prestador_cnpj_cpf LIKE ? OR
                tomador_nome LIKE ? OR
                tomador_cnpj_cpf LIKE ? OR
                discriminacao_servico LIKE ? OR
                motivo_cancelamento LIKE ?
            )""")
            params.extend([s, s, s, s, s, s, s, s])

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT * FROM notas_fiscais
            {where_sql}
            ORDER BY data_emissao DESC, numero_nfse DESC
            LIMIT ? OFFSET ?;
        """
        params.extend([limit, offset])

        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_financial_summary(cnpj=None, start_date=None, end_date=None, db_path=None):
    """
    Calcula os totais financeiros. Exclui notas canceladas do faturamento e tributos
    e contabiliza o número e valor de notas canceladas separadamente.
    """
    conn = get_connection(db_path)
    try:
        clauses = []
        params = []

        if cnpj:
            cnpj_clean = NON_DIGITS.sub('', str(cnpj))
            clauses.append("cnpj_consultado = ?")
            params.append(cnpj_clean)

        if start_date:
            d_ini = start_date.strftime("%Y-%m-%d") if hasattr(start_date, "strftime") else str(start_date)
            clauses.append("data_emissao >= ?")
            params.append(d_ini)

        if end_date:
            d_fim = end_date.strftime("%Y-%m-%d") if hasattr(end_date, "strftime") else str(end_date)
            clauses.append("data_emissao <= ?")
            params.append(d_fim)

        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = f"""
            SELECT 
                COUNT(*) as total_notas,
                SUM(CASE WHEN tipo = 'prestado' AND status != 'cancelada' THEN 1 ELSE 0 END) as total_prestadas,
                SUM(CASE WHEN tipo = 'tomado' AND status != 'cancelada' THEN 1 ELSE 0 END) as total_tomadas,
                SUM(CASE WHEN status = 'cancelada' THEN 1 ELSE 0 END) as total_canceladas,
                SUM(CASE WHEN status = 'cancelada' THEN valor_servico ELSE 0.0 END) as valor_canceladas,
                SUM(CASE WHEN tipo = 'prestado' AND status != 'cancelada' THEN valor_servico ELSE 0.0 END) as total_faturado,
                SUM(CASE WHEN tipo = 'tomado' AND status != 'cancelada' THEN valor_servico ELSE 0.0 END) as total_tomado_servico,
                SUM(CASE WHEN status != 'cancelada' THEN valor_servico ELSE 0.0 END) as total_valor_servico,
                SUM(CASE WHEN status != 'cancelada' THEN valor_liquido ELSE 0.0 END) as total_valor_liquido,
                SUM(CASE WHEN status != 'cancelada' THEN valor_iss ELSE 0.0 END) as total_iss,
                SUM(CASE WHEN status != 'cancelada' THEN valor_pis ELSE 0.0 END) as total_pis,
                SUM(CASE WHEN status != 'cancelada' THEN valor_cofins ELSE 0.0 END) as total_cofins,
                SUM(CASE WHEN status != 'cancelada' THEN valor_inss ELSE 0.0 END) as total_inss,
                SUM(CASE WHEN status != 'cancelada' THEN valor_ir ELSE 0.0 END) as total_ir,
                SUM(CASE WHEN status != 'cancelada' THEN valor_csll ELSE 0.0 END) as total_csll
            FROM notas_fiscais
            {where_sql};
        """
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


# --- Importação e Migração de Dados Existentes ---

def import_existing_data(notas_dir=None, cache_dir=None, db_path=None, verbose=False):
    """
    Varre os diretórios 'notas_fiscais/' e 'cache_nsu/' para popular o SQLite
    com notas já baixadas, processar eventos de cancelamento e indexar NSUs.
    """
    init_db(db_path)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    notas_dir = notas_dir or os.path.join(base_dir, "notas_fiscais")
    cache_dir = cache_dir or os.path.join(base_dir, "cache_nsu")

    stats = {
        "xmls_importados": 0,
        "canceladas_atualizadas": 0,
        "nsu_index_importados": 0,
        "erros": 0
    }

    # 1. Importa índices NSU existentes em cache_nsu/
    if os.path.isdir(cache_dir):
        for fname in os.listdir(cache_dir):
            if fname.endswith("_index.json"):
                parts = fname.replace("_index.json", "").split("_")
                if len(parts) >= 2:
                    cnpj, ambiente = parts[0], parts[1]
                    fpath = os.path.join(cache_dir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        for nsu_str, date_str in data.items():
                            save_nsu_index_entry(cnpj, ambiente, int(nsu_str), date_str, db_path=db_path)
                            stats["nsu_index_importados"] += 1
                    except Exception as e:
                        if verbose:
                            print(f"Erro ao importar índice '{fname}': {e}")
                        stats["erros"] += 1

    # 2. Primeira passagem: Importa todas as notas fiscais (<NFSe>)
    eventos_encontrados = []
    if os.path.isdir(notas_dir):
        for root, _, files in os.walk(notas_dir):
            rel = os.path.relpath(root, notas_dir)
            parts = rel.split(os.sep)
            cnpj_inferred = None
            for p in parts:
                digits = NON_DIGITS.sub('', p)
                if len(digits) == 14:
                    cnpj_inferred = digits
                    break

            for fname in files:
                if fname.lower().endswith('.xml'):
                    xml_path = os.path.join(root, fname)
                    try:
                        with open(xml_path, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read()

                        # Verifica se é um evento
                        evt_meta = extract_event_metadata(content)
                        if evt_meta and evt_meta.get("tipo_evento") == "cancelamento":
                            # Extrai NSU se presente no nome do arquivo (ex: nsu_304.xml)
                            m_nsu = re.search(r'nsu_(\d+)', fname, re.IGNORECASE)
                            nsu_val = int(m_nsu.group(1)) if m_nsu else None
                            eventos_encontrados.append((xml_path, evt_meta, nsu_val))
                            continue

                        meta = extract_nota_metadata(content, cnpj_consultado=cnpj_inferred)
                        if meta:
                            meta["caminho_xml"] = os.path.abspath(xml_path)
                            if "_cancelada" in fname.lower():
                                meta["status"] = "cancelada"

                            pdf_path = os.path.splitext(xml_path)[0] + ".pdf"
                            if os.path.isfile(pdf_path):
                                meta["caminho_pdf"] = os.path.abspath(pdf_path)

                            upsert_nota_fiscal(meta, db_path=db_path)
                            stats["xmls_importados"] += 1
                    except Exception as e:
                        if verbose:
                            print(f"Erro ao importar XML '{xml_path}': {e}")
                        stats["erros"] += 1

        # 3. Segunda passagem: Processa todos os eventos de cancelamento encontrados
        for xml_path, evt_meta, nsu_val in eventos_encontrados:
            chave = evt_meta.get("chave_acesso")
            motivo = evt_meta.get("motivo")
            dt_evt = evt_meta.get("data_evento")

            if chave:
                res = cancel_nota_by_key(
                    chave_acesso=chave,
                    motivo=motivo,
                    data_cancelamento=dt_evt,
                    nsu_evento=nsu_val,
                    db_path=db_path
                )
                if res:
                    stats["canceladas_atualizadas"] += 1
                    if verbose:
                        print(f"  [CANCELADA] Nota chave {chave} marcada como cancelada (Motivo: {motivo})")

            # Se o arquivo de evento estiver em 'sem_data', move para 'eventos/'
            parent_dir = os.path.dirname(xml_path)
            if os.path.basename(parent_dir).lower() == "sem_data":
                cnpj_folder = os.path.dirname(parent_dir)
                eventos_folder = os.path.join(cnpj_folder, "eventos")
                os.makedirs(eventos_folder, exist_ok=True)
                dest_file = os.path.join(eventos_folder, os.path.basename(xml_path))
                try:
                    shutil.move(xml_path, dest_file)
                    if not os.listdir(parent_dir):
                        os.rmdir(parent_dir)
                except Exception as e:
                    if verbose:
                        print(f"  Aviso ao mover {xml_path} para {dest_file}: {e}")

    return stats


# Inicializa as tabelas ao carregar o módulo
init_db()


if __name__ == "__main__":
    print("=== Inicializando Banco de Dados SQLite ===")
    init_db()
    print(f"Banco inicializado em: {DEFAULT_DB_PATH}")
    print("\nExecutando migração/importação de dados existentes...")
    res = import_existing_data(verbose=True)
    print("Resultado da importação:")
    print(f"  - XMLs importados/atualizados:        {res['xmls_importados']}")
    print(f"  - Notas canceladas atualizadas:      {res['canceladas_atualizadas']}")
    print(f"  - Entradas de NSU indexadas:          {res['nsu_index_importados']}")
    print(f"  - Erros:                              {res['erros']}")
