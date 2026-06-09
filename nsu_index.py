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
Gerencia o índice de NSUs (NSU → data de emissão) e a localização
do NSU correspondente a uma data.

O índice é construído varrendo NSUs de 100 em 100 (1, 100, 200, 300...)
e salvando a data de cada NSU que possui documentos. O índice é
persistido em cache_nsu/{cnpj}_{env}_index.json.

Uso:
    from nsu_index import locate_nsu_by_date, save_nsu_index_entry
"""
import os
import json
import re
import time
import logging
import gzip
import base64
from datetime import date, datetime, timedelta

logger = logging.getLogger("free_nfse_downloader")

NSU_CACHE_DIR = "./cache_nsu"
NSU_INDEX_STEP = 100


# --- Cache data → NSU (para localização exata por data) ---

def _nsu_cache_path(cnpj, env_choice, start_date):
    key = f"{cnpj}_{env_choice}_{start_date.strftime('%Y-%m-%d')}"
    safe_key = re.sub(r'[^a-zA-Z0-9_.-]', '_', key)
    return os.path.join(NSU_CACHE_DIR, f"{safe_key}.json")


def load_nsu_location_cache(cnpj, env_choice, start_date):
    if not cnpj:
        return None, None

    cache_path = _nsu_cache_path(cnpj, env_choice, start_date)
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            nsu = data.get("nsu_encontrado")
            if nsu:
                return nsu, "exato"
        except Exception:
            pass

    best_nsu = None
    best_diff = None
    for day_offset in range(1, 8):
        test_date = start_date - timedelta(days=day_offset)
        test_path = _nsu_cache_path(cnpj, env_choice, test_date)
        if os.path.exists(test_path):
            try:
                with open(test_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                nsu = data.get("nsu_encontrado")
                if nsu and (best_diff is None or day_offset < best_diff):
                    best_nsu = nsu
                    best_diff = day_offset
            except Exception:
                pass

    if best_nsu:
        return best_nsu, f"aproximado ({best_diff} dias de diferença)"

    return None, None


def save_nsu_location_cache(cnpj, env_choice, start_date, nsu_encontrado):
    if not cnpj or not nsu_encontrado:
        return

    os.makedirs(NSU_CACHE_DIR, exist_ok=True)
    cache_path = _nsu_cache_path(cnpj, env_choice, start_date)

    try:
        data = {
            "cnpj": cnpj,
            "ambiente": env_choice,
            "data_inicial": start_date.strftime("%d/%m/%Y"),
            "nsu_encontrado": nsu_encontrado,
            "timestamp": datetime.now().isoformat()
        }
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.info(f"Cache de localização NSU salvo: '{cache_path}'")
    except Exception as e:
        logger.warning(f"Não foi possível salvar cache de localização: {e}")


# --- Índice NSU → data (construído de 100 em 100) ---

def _nsu_index_path(cnpj, env_choice):
    return os.path.join(NSU_CACHE_DIR, f"{cnpj}_{env_choice}_index.json")


def load_nsu_index(cnpj, env_choice):
    if not cnpj:
        return {}
    path = _nsu_index_path(cnpj, env_choice)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        index = {}
        for nsu_str, date_str in data.items():
            index[int(nsu_str)] = date.fromisoformat(date_str)
        return index
    except Exception:
        return {}


def save_nsu_index_entry(cnpj, env_choice, nsu_val, emission_date):
    if not cnpj or not nsu_val or not emission_date:
        return
    os.makedirs(NSU_CACHE_DIR, exist_ok=True)
    path = _nsu_index_path(cnpj, env_choice)
    index = {}
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                index = json.load(f)
        except Exception:
            index = {}
    nsu_key = str(nsu_val)
    date_str = emission_date.isoformat()
    if index.get(nsu_key) != date_str:
        index[nsu_key] = date_str
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(index, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


def find_nsu_range_by_date(cnpj, env_choice, target_date):
    """
    Usa o índice de NSUs para encontrar o range [low, high] que contém
    a data alvo. Retorna (low_nsu, high_nsu) ou (1, None) se não houver
    índice suficiente.
    """
    index = load_nsu_index(cnpj, env_choice)
    if not index:
        return 1, None

    nsus = sorted(index.keys())
    low_nsu = 1
    high_nsu = None

    for nsu in nsus:
        nsu_date = index[nsu]
        if nsu_date < target_date:
            low_nsu = nsu
        elif nsu_date >= target_date:
            high_nsu = nsu
            break

    if high_nsu is None:
        return low_nsu, None

    return low_nsu, high_nsu


# --- Consulta à API ---

def check_nsu_status_for_date(download_func, base_url, nsu_val, start_date):
    from download_nfse import extract_xml, get_emission_date

    url = f"{base_url}/DFe/{nsu_val}"
    for attempt in range(3):
        try:
            time.sleep(0.5)
            status_code, response_text, error_msg = download_func(url)
            if status_code == 200:
                try:
                    data = json.loads(response_text)
                except json.JSONDecodeError:
                    return "no_data", None

                lote = data.get("LoteDFe")
                if not lote:
                    xml_content = extract_xml(data)
                    if xml_content:
                        lote = [{"NSU": nsu_val, "ArquivoXml": base64.b64encode(gzip.compress(xml_content.encode('utf-8'))).decode('utf-8')}]

                if not lote:
                    return "no_data", None

                dates = []
                max_nsu = nsu_val
                for item in lote:
                    nsu_item = item.get("NSU", nsu_val)
                    max_nsu = max(max_nsu, nsu_item)
                    xml_b64 = item.get("ArquivoXml")
                    if xml_b64:
                        try:
                            conteudo_gzip = base64.b64decode(xml_b64.strip())
                            if conteudo_gzip.startswith(b'\x1f\x8b'):
                                xml_content = gzip.decompress(conteudo_gzip).decode('utf-8')
                            else:
                                xml_content = conteudo_gzip.decode('utf-8')
                            dt = get_emission_date(xml_content)
                            if dt:
                                dates.append(dt)
                        except Exception:
                            pass
                    else:
                        xml_content = extract_xml(item)
                        if xml_content:
                            dt = get_emission_date(xml_content)
                            if dt:
                                dates.append(dt)

                if not dates:
                    return "no_dates", max_nsu

                if any(d >= start_date for d in dates):
                    return "before_or_within", max_nsu
                else:
                    return "after", max_nsu
            elif status_code == 404:
                return "404", None
            elif status_code == 429:
                sleep_time = 10 * (2 ** attempt)
                logger.warning(f"Limite de requisições (429). Aguardando {sleep_time}s (tentativa {attempt+1}/3)...")
                time.sleep(sleep_time)
            else:
                time.sleep(2)
        except Exception:
            time.sleep(2)
    return "error", None


def _get_nsu_date(download_func, base_url, nsu_val):
    from download_nfse import extract_xml, get_emission_date

    url = f"{base_url}/DFe/{nsu_val}"
    for attempt in range(3):
        try:
            time.sleep(0.3)
            status_code, response_text, error_msg = download_func(url)
            if status_code == 200:
                try:
                    data = json.loads(response_text)
                except json.JSONDecodeError:
                    return None, nsu_val

                lote = data.get("LoteDFe")
                if not lote:
                    xml_content = extract_xml(data)
                    if xml_content:
                        lote = [{"NSU": nsu_val, "ArquivoXml": base64.b64encode(gzip.compress(xml_content.encode('utf-8'))).decode('utf-8')}]

                if not lote:
                    return None, nsu_val

                dates = []
                max_nsu = nsu_val
                for item in lote:
                    nsu_item = item.get("NSU", nsu_val)
                    max_nsu = max(max_nsu, nsu_item)
                    xml_b64 = item.get("ArquivoXml")
                    if xml_b64:
                        try:
                            conteudo_gzip = base64.b64decode(xml_b64.strip())
                            if conteudo_gzip.startswith(b'\x1f\x8b'):
                                xml_content = gzip.decompress(conteudo_gzip).decode('utf-8')
                            else:
                                xml_content = conteudo_gzip.decode('utf-8')
                            dt = get_emission_date(xml_content)
                            if dt:
                                dates.append(dt)
                        except Exception:
                            pass
                    else:
                        xml_content = extract_xml(item)
                        if xml_content:
                            dt = get_emission_date(xml_content)
                            if dt:
                                dates.append(dt)

                if not dates:
                    return None, max_nsu

                return min(dates), max_nsu

            elif status_code == 404:
                return None, None
            elif status_code == 429:
                sleep_time = 10 * (2 ** attempt)
                logger.warning(f"Limite de requisições (429). Aguardando {sleep_time}s (tentativa {attempt+1}/3)...")
                time.sleep(sleep_time)
            else:
                time.sleep(2)
        except Exception:
            time.sleep(2)
    return None, nsu_val


# --- Construção do índice ---

def _extend_nsu_index(download_func, base_url, cnpj_label, env_choice):
    """
    Varre NSUs de 100 em 100 (1, 100, 200, 300...)
    até encontrar 3 NSUs consecutivos sem dados.
    Atualiza o índice NSU→data para cada NSU que encontrar dados.
    """
    index = load_nsu_index(cnpj_label, env_choice)
    indexed_nsus = sorted(int(k) for k in index.keys())
    last_indexed = indexed_nsus[-1] if indexed_nsus else 0

    print(f"\n[Índice] Varrendo NSUs ({len(indexed_nsus)} entradas existentes)...")

    if last_indexed == 0:
        nsu = 1
    else:
        nsu = last_indexed + NSU_INDEX_STEP

    empty_count = 0
    novas = 0

    while empty_count < 3:
        data_encontrada, max_nsu = _get_nsu_date(download_func, base_url, nsu)

        if data_encontrada:
            save_nsu_index_entry(cnpj_label, env_choice, nsu, data_encontrada)
            novas += 1
            empty_count = 0
            print(f"  NSU {nsu}: {data_encontrada.strftime('%d/%m/%Y')} ✓")
        else:
            empty_count += 1
            print(f"  NSU {nsu}: sem dados ({empty_count}/3)")

        if nsu == 1:
            nsu = NSU_INDEX_STEP  # 1 → 100
        else:
            nsu += NSU_INDEX_STEP

    print(f"  Índice atualizado: {novas} novas entradas, {empty_count} vazios consecutivos")
    return load_nsu_index(cnpj_label, env_choice)


# --- Localização principal ---

def locate_nsu_by_date(download_func, base_url, start_date, cnpj_label=None, env_choice=None):
    """
    Localiza o NSU correspondente à data inicial usando o índice.

    1. Cache exato (data→NSU) → 0 requisições
    2. Índice cobre a data → busca binária entre as entradas (~7 req)
    3. Índice não cobre → estende com varredura de 100 em 100, depois binária
    """
    print(f"\n[Busca] Localizando NSU para {start_date.strftime('%d/%m/%Y')}...")

    # Nível 1: Cache exato
    if cnpj_label and env_choice:
        cached_nsu, origem = load_nsu_location_cache(cnpj_label, env_choice, start_date)
        if cached_nsu and origem == "exato":
            print(f"  Cache exato: NSU {cached_nsu}")
            return cached_nsu

    # Nível 2: Índice
    if cnpj_label and env_choice:
        idx_low, idx_high = find_nsu_range_by_date(cnpj_label, env_choice, start_date)

        if idx_high is None:
            print(f"  Índice não cobre {start_date.strftime('%d/%m/%Y')}. Estendendo...")
            _extend_nsu_index(download_func, base_url, cnpj_label, env_choice)
            idx_low, idx_high = find_nsu_range_by_date(cnpj_label, env_choice, start_date)

            if idx_high is None:
                print(f"  Índice não cobre a data alvo após extensão. Retornando NSU {idx_low} como aproximação.")
                safety = 30
                nsu_final = max(1, idx_low - safety)
                return nsu_final

        if idx_high is not None:
            print(f"  Índice: NSU {idx_low} a {idx_high}")
            low, high = idx_low, idx_high
            best_nsu = low
            nsu_encontrado = False

            while low <= high:
                mid = (low + high) // 2
                status, _ = check_nsu_status_for_date(download_func, base_url, mid, start_date)
                if status == "before_or_within":
                    best_nsu = mid
                    nsu_encontrado = True
                    high = mid - 1
                elif status == "after":
                    low = mid + 1
                else:
                    high = mid - 1

            safety = 30
            nsu_final = max(1, best_nsu - safety)
            print(f"  NSU exato: {best_nsu} → inicial: {nsu_final}")
            if nsu_encontrado:
                save_nsu_location_cache(cnpj_label, env_choice, start_date, best_nsu)
            return nsu_final

    # Fallback: sem CNPJ ou sem índice
    print("  Sem índice. Iniciando varredura do NSU 1...")
    return 1
