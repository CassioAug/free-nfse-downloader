#!/usr/bin/env python3
import os
import sys
import subprocess
import re
import logging
import time
from datetime import datetime, date, timedelta
from organize_nfse import get_service_type

# Inicializa o logger global
logger = logging.getLogger("free_nfse_downloader")

# --- Validação e Instalação Automática de Dependências ---
def check_install_dependencies():
    required = {
        "requests": "requests",
        "cryptography": "cryptography"
    }
    
    missing = []
    for module, pip_name in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(pip_name)
            
    if missing:
        print(f"Dependências básicas ausentes: {', '.join(missing)}")
        resp = input("Deseja instalá-las automaticamente via pip? (s/n): ").strip().lower()
        if resp == 's':
            try:
                subprocess.run([sys.executable, "-m", "pip", "install"] + missing, check=True)
                print("Dependências básicas instaladas com sucesso!\n")
            except Exception as e:
                print(f"Erro ao instalar: {e}")
                print(f"Instale manualmente rodando: pip install {' '.join(missing)}")
                sys.exit(1)
        else:
            print("Erro: O script necessita dessas dependências para funcionar.")
            sys.exit(1)

    # Verifica a biblioteca opcional/recomendada para geração do DANFSE PDF
    global HAS_DANFSE_LIB
    try:
        import brazilfiscalreport
        from brazilfiscalreport.danfse import Danfse
        HAS_DANFSE_LIB = True
    except ImportError:
        print("\nAviso: A biblioteca 'brazilfiscalreport' (para gerar o PDF da DANF) não está instalada.")
        resp = input("Deseja instalá-la agora com suporte a DANFSE? (s/n): ").strip().lower()
        if resp == 's':
            try:
                print("Instalando 'brazilfiscalreport[danfse]'... (pode demorar um pouco)")
                subprocess.run([sys.executable, "-m", "pip", "install", "brazilfiscalreport[danfse]"], check=True)
                global Danfse
                from brazilfiscalreport.danfse import Danfse
                HAS_DANFSE_LIB = True
                print("Biblioteca 'brazilfiscalreport' instalada com sucesso!\n")
            except Exception as e:
                print(f"Erro ao instalar: {e}")
                print("O script continuará apenas baixando os XMLs (sem gerar PDF).\n")
                HAS_DANFSE_LIB = False
        else:
            print("O script continuará apenas baixando os XMLs (sem gerar PDF).\n")
            HAS_DANFSE_LIB = False

check_install_dependencies()

try:
    import cert_handler
    HAS_CERT_HANDLER = True
except ImportError:
    print("\nAviso: Módulo 'cert_handler' não encontrado. Suporte a token A3 desabilitado.")
    HAS_CERT_HANDLER = False

if HAS_DANFSE_LIB:
    class CustomDanfse(Danfse):
        def _draw_service_provided(self):
            x_margin = self.l_margin
            y_margin = self.y
            page_width = self.epw

            col_width = self.epw / 4
            section_start_y = y_margin + 5

            # SERVIÇO PRESTADO
            self.set_font(self.default_font, "B", 9)
            self.set_xy(x=x_margin + 3, y=section_start_y)
            self.cell(w=col_width, h=1, text="SERVIÇO PRESTADO", align="L")

            # Código de Tributação Nacional
            self.set_font(self.default_font, "B", 7)
            self.set_xy(x=x_margin + 3, y=section_start_y + 4)
            self.cell(w=col_width, h=3, text="Código de Tributação Nacional", align="L")

            # Código de Tributação Nacional - Valor
            self.set_font(self.default_font, "", 8)
            self.set_xy(x=x_margin + 3, y=section_start_y + 7)
            self.multi_cell(
                w=col_width,
                h=2.5,
                text=self.long_field(
                    text=self.data["service"]["national_tax_code"],
                    limit=col_width,
                ),
                align="L",
            )

            # Código de Tributação Municipal
            self.set_font(self.default_font, "B", 7)
            self.set_xy(x=x_margin + col_width, y=section_start_y + 4)
            self.cell(w=col_width, h=3, text="Código de Tributação Municipal", align="L")

            # Código de Tributação Municipal - Valor
            self.set_font(self.default_font, "", 8)
            self.set_xy(x=x_margin + col_width, y=section_start_y + 4)
            self.cell(
                w=col_width, h=8, text=self.data["service"]["municipal_tax_code"], align="L"
            )

            # Local da Prestação
            self.set_font(self.default_font, "B", 7)
            self.set_xy(x=x_margin + (col_width * 2), y=section_start_y + 4)
            self.cell(w=col_width, h=3, text="Local da Prestação", align="L")

            # Local da Prestação - Valor
            self.set_font(self.default_font, "", 8)
            self.set_xy(x=x_margin + (col_width * 2), y=section_start_y + 4)
            self.cell(
                w=col_width, h=8, text=self.data["service"]["place_of_provision"], align="L"
            )

            # País da Prestação
            self.set_font(self.default_font, "B", 7)
            self.set_xy(x=x_margin + (col_width * 3), y=section_start_y + 4)
            self.cell(w=col_width, h=3, text="País da Prestação", align="L")

            # País da Prestação - Valor
            self.set_font(self.default_font, "", 8)
            self.set_xy(x=x_margin + (col_width * 3), y=section_start_y + 4)
            self.cell(w=col_width, h=8, text=self.data["service"]["country"], align="L")

            # Descrição do Serviço Label
            self.set_font(self.default_font, "B", 7)
            self.set_xy(x=x_margin + 3, y=section_start_y + 14)
            self.cell(w=col_width, h=3, text="Descrição do Serviço", align="L")

            # Descrição do Serviço - Valor (Multi-line)
            self.set_font(self.default_font, "", 8)
            self.set_xy(x=x_margin + 3, y=section_start_y + 17.5)
            self.multi_cell(
                w=page_width - 6,
                h=3.5,
                text=self.data["service"]["description"],
                align="L",
            )
            
            description_end_y = self.y
            line_y = max(y_margin + 25, description_end_y + 2)

            self.set_font(self.default_font, "B", 7)
            self.set_dash_pattern(dash=0, gap=0)
            self.line(
                x1=x_margin + 2,
                y1=line_y,
                x2=x_margin + page_width - 2,
                y2=line_y,
            )
            
            self.y = line_y - 6

# Agora podemos importar com segurança
import requests
import base64
import gzip
import xml.etree.ElementTree as ET

# URLs Oficiais da API Nacional
API_URLS = {
    "1": "https://adn.nfse.gov.br/contribuintes",               # Produção
    "2": "https://adn.producaorestrita.nfse.gov.br/contribuintes" # Homologação
}

def parse_date(date_str):
    try:
        return datetime.strptime(date_str.strip(), "%d/%m/%Y").date()
    except ValueError:
        return None

def extract_xml(data):
    """Varre o JSON da resposta procurando pelo conteúdo XML codificado ou limpo"""
    if not isinstance(data, dict):
        return None
        
    keys_to_check = ['xmlB64', 'xmlNfse', 'xml', 'conteudo', 'conteudoXml', 'documento', 'xml_documento']
    for k in list(data.keys()):
        if k not in keys_to_check and ('xml' in k.lower() or 'conteudo' in k.lower()):
            keys_to_check.append(k)
            
    for key in keys_to_check:
        val = data.get(key)
        if not val or not isinstance(val, str):
            continue
            
        val_stripped = val.strip()
        if val_stripped.startswith("<?xml") or val_stripped.startswith("<"):
            return val_stripped
            
        try:
            decoded_bytes = base64.b64decode(val_stripped)
            if decoded_bytes.startswith(b'\x1f\x8b'):
                decoded_bytes = gzip.decompress(decoded_bytes)
            decoded_str = decoded_bytes.decode('utf-8', errors='ignore').strip()
            if decoded_str.startswith("<?xml") or decoded_str.startswith("<"):
                return decoded_str
        except Exception:
            pass
            
    return None

def get_emission_date(xml_str):
    """Encontra a data de emissão no XML independente do namespace"""
    try:
        root = ET.fromstring(xml_str)
        elem = None
        for el in root.iter():
            tag_local = el.tag.split('}')[-1] if '}' in el.tag else el.tag
            if tag_local.lower() in ['dhemi', 'dataemissao', 'dtemissao', 'dtemi']:
                elem = el
                break
        if elem is not None and elem.text:
            date_str = elem.text.strip()
            match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', date_str)
            if match:
                return datetime.strptime(match.group(0), "%Y-%m-%d").date()
    except Exception as e:
        logger.debug(f"Erro ao parsear data do XML: {e}")
    return None

def get_nfse_number(xml_str):
    """Encontra o número da NFS-e no XML independente do namespace"""
    try:
        root = ET.fromstring(xml_str)
        elem = None
        for el in root.iter():
            tag_local = el.tag.split('}')[-1] if '}' in el.tag else el.tag
            if tag_local.lower() in ['nnfse', 'numeronfse', 'numero']:
                elem = el
                break
        if elem is not None and elem.text:
            return elem.text.strip()
    except Exception as e:
        logger.debug(f"Erro ao parsear número do XML: {e}")
    return None

def extract_cnpj_from_subject(subject_str):
    """
    Extrai o CNPJ (14 dígitos) do campo Subject de um certificado digital.
    
    Estratégias por ordem de prioridade:
      1. CNPJ após ':' no campo CN (commonName) — formato típico de e-CNPJ:
         "CN=Nome da Empresa:12345678000199"
      2. Padrão explícito 'CNPJ: 12345678000199' ou 'CPF/CNPJ: 12345678000199'
      3. Primeiro grupo de 14 dígitos dentro de campos OU (OrganizationalUnit)
      4. Primeiro grupo de 14 dígitos em qualquer parte do subject (fallback original)
    """
    if not subject_str:
        return None

    # 1. CNPJ após ':' no campo CN: "CN=Nome:12345678000199"
    match = re.search(r'(?:^|[\s,])CN\s*=\s*[^:]*:(\d{14})(?:\s*[)>,\s]|$)', subject_str, re.IGNORECASE)
    if match:
        return match.group(1)

    # 2. Padrão explícito "CNPJ:" ou "CPF/CNPJ:" seguido de 14 dígitos
    match = re.search(r'(?:CPF\s*/\s*CNPJ|CNPJ)\s*:\s*(\d{14})', subject_str, re.IGNORECASE)
    if match:
        return match.group(1)

    # 3. CNPJ em campos OU: "OU=12345678000199"
    match = re.search(r'(?:^|[\s,])OU\s*=\s*(\d{14})(?:\s*[)>,\s]|$)', subject_str, re.IGNORECASE)
    if match:
        return match.group(1)

    # 4. Fallback: primeiro grupo de 14 dígitos no subject todo
    match = re.search(r'(\d{14})', subject_str)
    if match:
        return match.group(1)

    return None


def extract_cnpj_from_pem(pem_path):
    """
    Extrai o CNPJ de um arquivo PEM de certificado digital.
    Usa a biblioteca cryptography para ler o certificado e obter o subject.
    
    Estratégias por ordem de prioridade:
      1. CNPJ após ':' no campo CN (commonName) — via OID estruturado
      2. CNPJ em campos OU (organizationalUnitName) — via OID estruturado
      3. Fallback para extract_cnpj_from_subject com string do subject
      4. Extração do nome do arquivo PEM (padrão: *_{CNPJ}.pem)
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from cryptography.x509.oid import NameOID

        with open(pem_path, "rb") as f:
            pem_data = f.read()

        cert = None
        try:
            cert = x509.load_pem_x509_certificate(pem_data, default_backend())
        except Exception:
            # PEM pode conter chave privada + certificado. Extrai apenas o bloco BEGIN/END CERTIFICATE
            cert_match = re.search(
                r'-----BEGIN CERTIFICATE-----\n.*?-----END CERTIFICATE-----',
                pem_data.decode('utf-8', errors='ignore'),
                re.DOTALL
            )
            if cert_match:
                cert = x509.load_pem_x509_certificate(
                    cert_match.group(0).encode('utf-8'),
                    default_backend()
                )

        if cert:
            # 1. CNPJ após ':' no campo CN: "CN=Nome:12345678000199"
            cn_attrs = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
            if cn_attrs:
                match = re.search(r':(\d{14})', cn_attrs[0].value)
                if match:
                    return match.group(1)

            # 2. CNPJ em campos OU
            ou_attrs = cert.subject.get_attributes_for_oid(NameOID.ORGANIZATIONAL_UNIT_NAME)
            for ou in ou_attrs:
                match = re.search(r'(\d{14})', ou.value)
                if match:
                    return match.group(1)

            # 3. Fallback string-based
            cnpj = extract_cnpj_from_subject(str(cert.subject))
            if cnpj:
                return cnpj

        # 4. Último recurso: extrair do nome do arquivo
        match = re.search(r'_(\d{14})\.pem$', os.path.basename(pem_path))
        if match:
            return match.group(1)

        return None

    except ImportError:
        logger.warning("Biblioteca cryptography não disponível para extrair CNPJ do PEM.")
        return None
    except Exception as e:
        logger.debug(f"Erro ao extrair CNPJ do PEM: {e}")
        return None


import json

def load_last_nsu(state_key, env_choice):
    state_file = "nsu_state.json"
    if not os.path.exists(state_file):
        return None
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
            key = f"{state_key}_{env_choice}"
            return state.get(key)
    except Exception as e:
        logger.debug(f"Erro ao carregar nsu_state.json: {e}")
        return None

def save_last_nsu(state_key, env_choice, last_nsu):
    state_file = "nsu_state.json"
    state = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            state = {}
    key = f"{state_key}_{env_choice}"
    state[key] = last_nsu
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4, ensure_ascii=False)
        logger.info(f"Último NSU ({last_nsu}) salvo com sucesso em '{state_file}'.")
    except Exception as e:
        logger.warning(f"Não foi possível salvar o estado do NSU em '{state_file}': {e}")

# Cache de localização automática de NSU por data
NSU_CACHE_DIR = "./cache_nsu"

def _nsu_cache_path(cnpj, env_choice, start_date):
    """Retorna o caminho do arquivo de cache para uma determinada (cnpj, ambiente, data)"""
    key = f"{cnpj}_{env_choice}_{start_date.strftime('%Y-%m-%d')}"
    safe_key = re.sub(r'[^a-zA-Z0-9_.-]', '_', key)
    return os.path.join(NSU_CACHE_DIR, f"{safe_key}.json")

def load_nsu_location_cache(cnpj, env_choice, start_date):
    """
    Verifica se existe cache de localização para (cnpj, ambiente, data_inicial).
    
    Retorna (nsu_encontrado, origem) ou (None, None) se não houver cache.
    origem descreve se foi 'exato' (mesma data) ou 'aproximado' (data próxima).
    """
    if not cnpj:
        return None, None
    
    # 1. Cache exato: mesma data já foi buscada antes
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
    
    # 2. Cache aproximado: verifica se há caches de datas próximas (7 dias antes)
    #    Útil para evitar busca binária completa quando se avança o período aos poucos
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
    """Salva o resultado de uma localização de NSU no cache."""
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

# --- Índice de NSUs (NSU → data, a cada 100 NSUs) ---
NSU_INDEX_STEP = 100

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


def check_nsu_status_for_date(download_func, base_url, nsu_val, start_date):
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

def locate_nsu_by_date(download_func, base_url, start_date, cnpj_label=None, env_choice=None):
    """
    Localiza o NSU correspondente à data inicial.
    
    Estratégia em 3 níveis, do mais rápido ao mais lento:
    1. Cache exato (data → NSU) → 0 requisições
    2. Índice de NSUs (a cada 100) → busca binária em ~7 requisições
    3. Galloping partir do NSU 1 → ~log(N) requisições (apenas se não há índice)
    """
    print(f"\n[Busca] Localizando NSU para {start_date.strftime('%d/%m/%Y')}...")

    # --- Nível 1: Cache exato ---
    if cnpj_label and env_choice:
        cached_nsu, origem = load_nsu_location_cache(cnpj_label, env_choice, start_date)
        if cached_nsu and origem == "exato":
            print(f"  Cache exato: NSU {cached_nsu}")
            return cached_nsu

    # --- Nível 2: Índice de NSUs (a cada 100) ---
    idx_low = 1
    if cnpj_label and env_choice:
        idx_low, idx_high = find_nsu_range_by_date(cnpj_label, env_choice, start_date)
        if idx_high is not None:
            print(f"  Índice: NSU {idx_low} a {idx_high} (diferença ≤ {NSU_INDEX_STEP})")
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
        elif idx_low > 1:
            print(f"  Índice: último NSU indexado {idx_low} (anterior à data alvo)")

    # --- Nível 3: Galloping (sem índice ou data além do índice) ---
    low = idx_low if cnpj_label and env_choice and idx_low > 1 else 1
    if cnpj_label and env_choice:
        cached_nsu, _ = load_nsu_location_cache(cnpj_label, env_choice, start_date)
        if cached_nsu and not idx_low > 1:
            low = max(1, cached_nsu - 200)
            print(f"  Cache aprox: NSU {cached_nsu} - 200")
        elif low == 1:
            print("  Sem índice. Busca exponencial a partir do NSU 1.")
        else:
            print(f"  Último NSU indexado: {low}")

    nsu = low
    step = 1
    found_upper = False

    while not found_upper:
        status, max_nsu = check_nsu_status_for_date(download_func, base_url, nsu, start_date)
        if status == "before_or_within":
            found_upper = True
        elif status in ("after", "no_data", "no_dates"):
            low = nsu
            step = min(step * 2, 5000)
            nsu += step
            print(f"  → NSU {nsu} (passo {step})")
        elif status == "404":
            nsu = max(low, nsu - 1)
            found_upper = True
        else:
            nsu = max(low, nsu - 1)
            found_upper = True

    high = nsu
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

    safety = 50 if cnpj_label else 100
    nsu_final = max(1, best_nsu - safety)
    print(f"  NSU exato: {best_nsu} → inicial: {nsu_final}")

    if cnpj_label and env_choice and nsu_encontrado:
        save_nsu_location_cache(cnpj_label, env_choice, start_date, best_nsu)

    return nsu_final

def main():
    print("=== free-nfse-downloader ===")
    print("Este script consome a API do Ambiente de Dados Nacional.\n")

    cert_type = None
    pem_path = None
    a3_thumbprint = None
    a3_cert_info = None

    print("Selecione o tipo de certificado:")
    print("1 - Arquivo PEM (certificado em arquivo .pem)")
    if HAS_CERT_HANDLER:
        print("2 - Token A3 (GD Burti / SafeSign - USB)")

    default_cert_option = "1"
    if HAS_CERT_HANDLER:
        default_cert_option = input(f"Opção [Padrão: {default_cert_option}]: ").strip() or default_cert_option
    else:
        input(f"Opção [Padrão: {default_cert_option}]: ").strip() or default_cert_option

    if HAS_CERT_HANDLER and default_cert_option == "2":
        cert_type = "A3"
        print("\n[Modo: Token A3 - Windows Certificate Store]")

        token_certs = cert_handler.list_token_certs()
        if not token_certs:
            print("Erro: Nenhum certificado de token (A3) encontrado.")
            print("Verifique se:")
            print("  1. O token USB está conectado")
            print("  2. O driver SafeSign está instalado")
            print("  3. O certificado foi importado para o Windows Certificate Store")
            return 1

        print(f"\nEncontrado(s) {len(token_certs)} certificado(s) de token:\n")
        for idx, cert in enumerate(token_certs, 1):
            subject = cert.get('subject', 'Desconhecido')
            thumbprint = cert.get('thumbprint', 'N/A')
            notafter = cert.get('notafter', 'N/A')
            print(f"  {idx} - {subject}")
            print(f"      Validade: {notafter}")
            print(f"      Thumbprint: {thumbprint}")
            print()

        if len(token_certs) == 1:
            selected_index = 0
            print(f"Auto-selecionado certificado único: {token_certs[0].get('subject', 'N/A')}")
        else:
            try:
                selected_str = input(f"Selecione o número do certificado (1-{len(token_certs)}): ").strip()
                if not selected_str.isdigit() or not (1 <= int(selected_str) <= len(token_certs)):
                    print("Opção inválida.")
                    return 1
                selected_index = int(selected_str) - 1
            except (KeyboardInterrupt, SystemExit):
                print("\nOperação cancelada.")
                return 1

        a3_cert_info = token_certs[selected_index]
        a3_thumbprint = a3_cert_info.get('thumbprint')
        if not a3_thumbprint:
            print("Erro: Certificado selecionado não possui thumbprint.")
            return 1

        print(f"Certificado selecionado: {a3_cert_info.get('subject', 'N/A')}")
        print(f"Thumbprint: {a3_thumbprint}")

        # Extrai CNPJ do subject do certificado A3
        cnpj = extract_cnpj_from_subject(a3_cert_info.get('subject', ''))

    else:
        cert_type = "PEM"
        print("\n[Modo: Certificado em arquivo PEM]")
        pem_path = input("Caminho para o certificado PEM (gerado pelo conversor) [Padrão: ./certificados]: ").strip().strip("'\"")
        if not pem_path:
            pem_path = "./certificados"

        if not os.path.exists(pem_path):
            print(f"Erro: O arquivo ou diretório do certificado '{pem_path}' não foi encontrado.")
            return 1

        if os.path.isdir(pem_path):
            print(f"\nO caminho informado é um diretório. Procurando certificados PEM (.pem) em '{pem_path}'...")
            arquivos = [f for f in os.listdir(pem_path) if f.lower().endswith('.pem')]
            if not arquivos:
                print("Nenhum arquivo .pem foi encontrado neste diretório.")
                return 1
            print("Certificados PEM encontrados:")
            for idx, arq in enumerate(arquivos, 1):
                print(f"  {idx} - {arq}")
            try:
                opcao = input(f"Selecione o número do certificado (1-{len(arquivos)}): ").strip()
                if not opcao.isdigit() or not (1 <= int(opcao) <= len(arquivos)):
                    print("Opção inválida.")
                    return 1
                pem_path = os.path.join(pem_path, arquivos[int(opcao) - 1])
                print(f"Arquivo selecionado: {pem_path}")
            except (KeyboardInterrupt, SystemExit):
                print("\nOperação cancelada.")
                return 1

        # Extrai CNPJ do certificado PEM
        cnpj = extract_cnpj_from_pem(pem_path)

    if cert_type == "PEM":
        state_key = os.path.basename(pem_path)
    else:
        state_key = f"A3_{a3_thumbprint}"

    # Aplica subpasta com CNPJ no diretório de saída
    cnpj_label = None
    if cnpj:
        cnpj_label = re.sub(r'\D', '', cnpj)  # garante só dígitos
        print(f"\nCNPJ detectado no certificado: {cnpj_label}")
    else:
        print("\nAviso: Não foi possível extrair o CNPJ do certificado.")
        resp = input("Deseja digitar o CNPJ manualmente? (s/N): ").strip().lower()
        if resp == 's':
            cnpj_manual = input("CNPJ (apenas números, 14 dígitos): ").strip()
            cnpj_manual = re.sub(r'\D', '', cnpj_manual)
            if len(cnpj_manual) == 14:
                cnpj_label = cnpj_manual
            else:
                print("CNPJ inválido. As notas serão salvas na raiz da pasta de saída.")
        else:
            print("As notas serão salvas na raiz da pasta de saída.")
        
    # 2. Escolha do Ambiente
    print("\nEscolha o Ambiente:")
    print("1 - Produção (adn.nfse.gov.br)")
    print("2 - Homologação / Produção Restrita (adn.producaorestrita.nfse.gov.br)")
    env_choice = input("Opção [Padrão: 1]: ").strip() or "1"
    base_url = API_URLS.get(env_choice, API_URLS["1"])

    # 3. Período das Notas
    print("\nInforme o período desejado (Formato: DD/MM/YYYY):")
    start_date = None
    while not start_date:
        start_date = parse_date(input("Data Inicial: "))
        if not start_date:
            print("Formato inválido! Use DD/MM/YYYY (Ex: 01/05/2026)")
            
    end_date = None
    while not end_date:
        end_date = parse_date(input("Data Final: "))
        if not end_date:
            print("Formato inválido! Use DD/MM/YYYY (Ex: 31/05/2026)")
            
    if start_date > end_date:
        print("Erro: A data inicial não pode ser maior que a data final.")
        return 1

    # 4. Diretório de Saída
    output_dir = input("\nPasta para salvar as notas [Padrão: ./notas_fiscais]: ").strip().strip("'\"") or "./notas_fiscais"
    
    # Cria subpasta com CNPJ se disponível
    if cnpj_label:
        output_dir = os.path.join(output_dir, cnpj_label)
        print(f"As notas serão salvas em: '{output_dir}'")
    
    os.makedirs(output_dir, exist_ok=True)
    
    # --- Configuração do Logger ---
    log_file = os.path.join(output_dir, "coletor_nfse.log")
    for h in logger.handlers[:]:
        logger.removeHandler(h)
    logger.setLevel(logging.INFO)
    
    # Handler para o arquivo (formato detalhado)
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S"))
    logger.addHandler(file_handler)
    
    # Handler para o console (exibe a mensagem limpa)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(console_handler)

    # 5. Inicialização da Sessão HTTP com mTLS e User-Agent
    if cert_type == "PEM":
        session = requests.Session()
        session.cert = (pem_path, pem_path)
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
    else:
        session = None

    def do_download(url):
        """Executa o download usando o método apropriado (PEM ou A3)"""
        if cert_type == "PEM":
            response = session.get(url, timeout=30)
            return response.status_code, response.text, None
        else:
            success, data = cert_handler.download_json_with_curl(url, a3_thumbprint)
            if success:
                return 200, data, None
            else:
                return 0, None, data

    # 6. Definição do NSU Inicial
    saved_nsu = load_last_nsu(state_key, env_choice)
    
    print("\nDefinição do NSU Inicial de busca:")
    options = []
    
    if saved_nsu is not None:
        options.append(f"Continuar a partir do último NSU processado salvo ({saved_nsu}) [Recomendado]")
        options.append(f"Localizar automaticamente com base na Data Inicial ({start_date.strftime('%d/%m/%Y')})")
        options.append("Começar do início (NSU 1)")
        options.append("Digitar um NSU manualmente")
    else:
        options.append(f"Localizar automaticamente com base na Data Inicial ({start_date.strftime('%d/%m/%Y')}) [Recomendado]")
        options.append("Começar do início (NSU 1)")
        options.append("Digitar um NSU manualmente")
        
    for i, opt in enumerate(options, 1):
        print(f"  {i} - {opt}")
        
    choice_input = input(f"Escolha uma opção (1-{len(options)}) [Padrão: 1]: ").strip()
    choice = int(choice_input) if choice_input.isdigit() and 1 <= int(choice_input) <= len(options) else 1
    
    if saved_nsu is not None:
        if choice == 1:
            nsu = saved_nsu
            print(f"Utilizando NSU salvo: {nsu}")
        elif choice == 2:
            nsu = locate_nsu_by_date(do_download, base_url, start_date, cnpj_label, env_choice)
        elif choice == 3:
            nsu = 1
            print("Iniciando do NSU 1.")
        else:
            nsu_input = input("Digite o NSU Inicial manualmente: ").strip()
            nsu = int(nsu_input) if nsu_input.isdigit() else 1
    else:
        if choice == 1:
            nsu = locate_nsu_by_date(do_download, base_url, start_date, cnpj_label, env_choice)
        elif choice == 2:
            nsu = 1
            print("Iniciando do NSU 1.")
        else:
            nsu_input = input("Digite o NSU Inicial manualmente: ").strip()
            nsu = int(nsu_input) if nsu_input.isdigit() else 1

    cert_label = pem_path if cert_type == "PEM" else a3_cert_info.get('subject', 'A3 Token')
    if cnpj_label:
        logger.info(f"CNPJ da empresa: {cnpj_label}")
    logger.info(f"\nIniciando busca no período: {start_date.strftime('%d/%m/%Y')} até {end_date.strftime('%d/%m/%Y')}")
    logger.info(f"Começando do NSU {nsu}. Salvando em: '{output_dir}'")
    logger.info(f"Arquivo de log: '{log_file}'")
    logger.info(f"Tipo de certificado: {cert_type} - {cert_label}")
    logger.info("-" * 60)

    consecutive_after_period = 0
    downloaded_count = 0
    first_nsu_in_period = None
    request_delay = 1.0

    while True:
        url = f"{base_url}/DFe/{nsu}"
        time.sleep(request_delay)
        try:
            logger.info(f"Consultando lote de documentos a partir do NSU {nsu}...")
            status_code, response_text, error_msg = do_download(url)

            if status_code == 200:
                try:
                    data = json.loads(response_text)
                except json.JSONDecodeError as e:
                    logger.error(f"  [NSU {nsu}] Erro ao parsear JSON: {e}")
                    nsu += 1
                    continue

                lote = data.get("LoteDFe")

                if not lote:
                    xml_content = extract_xml(data)
                    if xml_content:
                        lote = [{"NSU": nsu, "ArquivoXml": base64.b64encode(gzip.compress(xml_content.encode('utf-8'))).decode('utf-8')}]
                    else:
                        logger.warning(f"\nNenhum documento retornado no lote para o NSU {nsu}. Chaves no JSON: {list(data.keys())}")
                        break
                
                logger.info(f"Lote recebido com {len(lote)} documento(s). Processando...")
                
                max_nsu_in_batch = nsu
                stop_loop = False
                
                for item in lote:
                    nsu_item = item.get("NSU", nsu)
                    max_nsu_in_batch = max(max_nsu_in_batch, nsu_item)
                    
                    xml_b64 = item.get("ArquivoXml")
                    if not xml_b64:
                        xml_content = extract_xml(item)
                    else:
                        try:
                            conteudo_gzip = base64.b64decode(xml_b64.strip())
                            if conteudo_gzip.startswith(b'\x1f\x8b'):
                                xml_content = gzip.decompress(conteudo_gzip).decode('utf-8')
                            else:
                                xml_content = conteudo_gzip.decode('utf-8')
                        except Exception as e:
                            logger.error(f"  [NSU {nsu_item}] Erro ao decodificar/decomprimir XML: {e}")
                            continue
                            
                    if not xml_content:
                        logger.error(f"  [NSU {nsu_item}] Não foi possível extrair o XML do documento.")
                        continue
                        
                    dt = get_emission_date(xml_content)
                    if not dt:
                        logger.warning(f"  [NSU {nsu_item}] Data de emissão não encontrada no XML. Salvando em 'sem_data'.")
                        sem_data_dir = os.path.join(output_dir, "sem_data")
                        os.makedirs(sem_data_dir, exist_ok=True)
                        with open(os.path.join(sem_data_dir, f"nsu_{nsu_item}.xml"), "w", encoding="utf-8") as f:
                            f.write(xml_content)
                        continue
                        
                    # Alimenta o índice NSU (a cada 100)
                    if cnpj_label and env_choice and nsu_item % NSU_INDEX_STEP < 3:
                        save_nsu_index_entry(cnpj_label, env_choice, nsu_item, dt)

                    # Regras de Filtro por Data
                    if dt < start_date:
                        consecutive_after_period = 0
                        logger.info(f"  [NSU {nsu_item}] Nota de {dt.strftime('%d/%m/%Y')} (Antes do período, pulando...)")
                        
                    elif start_date <= dt <= end_date:
                        consecutive_after_period = 0
                        if first_nsu_in_period is None or nsu_item < first_nsu_in_period:
                            first_nsu_in_period = nsu_item
                        logger.info(f"  [NSU {nsu_item}] Nota de {dt.strftime('%d/%m/%Y')} (DENTRO DO PERÍODO!)")
                        
                        # Classifica o tipo de serviço (prestado ou tomado)
                        tipo_servico = get_service_type(xml_content, cnpj_label)
                        if tipo_servico == 'prestado':
                            tipo_subdir = "prestados"
                        elif tipo_servico == 'tomado':
                            tipo_subdir = "tomados"
                        else:
                            tipo_subdir = None
                        
                        if tipo_subdir:
                            tipo_dir = os.path.join(output_dir, tipo_subdir)
                            os.makedirs(tipo_dir, exist_ok=True)
                            logger.info(f"    -> Serviço {tipo_servico}")
                        else:
                            tipo_dir = output_dir
                            logger.info(f"    -> Tipo de serviço indeterminado, salvando na raiz")
                        
                        nfse_num = get_nfse_number(xml_content)
                        if nfse_num:
                            try:
                                formatted_num = f"{int(nfse_num):06d}"
                            except ValueError:
                                formatted_num = nfse_num.zfill(6)[-6:]
                            file_base = f"NFSe_{dt.strftime('%Y%m%d')}_{formatted_num}"
                        else:
                            file_base = f"NFSe_{dt.strftime('%Y%m%d')}_nsu_{nsu_item}"
                        xml_file_path = os.path.join(tipo_dir, f"{file_base}.xml")
                        
                        with open(xml_file_path, "w", encoding="utf-8") as f:
                            f.write(xml_content)
                            
                        if HAS_DANFSE_LIB:
                            pdf_file_path = os.path.join(tipo_dir, f"{file_base}.pdf")
                            try:
                                danfse = CustomDanfse(xml=xml_content)
                                danfse.output(pdf_file_path)
                                logger.info(f"    -> XML e DANF (PDF) salvos.")
                            except Exception as e:
                                logger.error(f"    -> XML salvo. Erro ao gerar DANF PDF: {e}")
                        else:
                            logger.warning(f"    -> XML salvo. (PDF não gerado - biblioteca ausente)")
                            
                        downloaded_count += 1
                        
                    else:
                        consecutive_after_period += 1
                        logger.info(f"  [NSU {nsu_item}] Nota de {dt.strftime('%d/%m/%Y')} (Após o período, consecutivo: {consecutive_after_period})")
                        
                        days_after = (dt - end_date).days
                        if days_after > 3:
                            logger.info(f"\nBusca finalizada: A nota do NSU {nsu_item} é de {dt.strftime('%d/%m/%Y')}, que é mais de 3 dias posterior à data final.")
                            stop_loop = True
                            break
                        if consecutive_after_period >= 10:
                            logger.info("\nBusca finalizada: Encontrados 10 documentos consecutivos posteriores ao período informado.")
                            stop_loop = True
                            break
                            
                if stop_loop:
                    nsu = max_nsu_in_batch
                    break
                    
                # Avança a busca. Se o maior NSU no lote for maior que o atual, avançamos para ele
                if max_nsu_in_batch == nsu:
                    nsu += 1
                else:
                    nsu = max_nsu_in_batch

            elif status_code == 404:
                logger.info(f"\nFim da fila: O NSU {nsu} não foi encontrado (fim dos registros).")
                break
            elif status_code == 429:
                request_delay = min(request_delay * 2, 15.0)
                logger.warning(f"Limite de requisições (429). Aguardando {request_delay:.0f}s e reduzindo ritmo...")
                time.sleep(request_delay)
            elif error_msg:
                logger.error(f"Erro ao buscar NSU {nsu}: {error_msg}")
                nsu += 1
            else:
                logger.error(f"Erro ao buscar NSU {nsu}: Status {status_code}")
                nsu += 1

        except Exception as e:
            logger.error(f"Falha de conexão no NSU {nsu}: {e}. Tentando novamente em 5 segundos...")
            time.sleep(5)

    logger.info("-" * 60)
    logger.info(f"Processo finalizado. Total de notas baixadas no período: {downloaded_count}")

    last_processed_nsu = nsu - 1
    logger.info(f"Último NSU processado: {last_processed_nsu}")

    save_last_nsu(state_key, env_choice, last_processed_nsu)

    # Salva cache NSU->data para localização futura sem busca
    if first_nsu_in_period and cnpj_label and env_choice:
        save_nsu_location_cache(cnpj_label, env_choice, start_date, first_nsu_in_period)
        logger.info(f"Cache de data salvo: {start_date.strftime('%d/%m/%Y')} → NSU {first_nsu_in_period}")

    logger.info("Estado do NSU atualizado. Pronto para o próximo download!")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nOperação cancelada pelo usuário.")
        sys.exit(0)
