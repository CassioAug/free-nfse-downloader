#!/usr/bin/env python3
import os
import sys
import subprocess
import re
import logging
import time
from datetime import datetime, date, timedelta
from organize_nfse import get_service_type
from nsu_index import locate_nsu_by_date, save_nsu_index_entry, save_nsu_location_cache

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



def main():
    print("=== free-nfse-downloader ===")
    print("Este script consome a API do Ambiente de Dados Nacional.\n")

    cert_type = None
    pem_path = None
    a3_thumbprint = None
    a3_cert_info = None

    # --- Certificado: PEM ou A3 ---
    print("Tipo de certificado:")
    print("  1 - Arquivo PEM (./certificados/)")
    if HAS_CERT_HANDLER:
        print("  2 - Token A3 (USB)")
    opcao_cert = input("Opção [Padrão: 1]: ").strip() or "1"

    if HAS_CERT_HANDLER and opcao_cert == "2":
        cert_type = "A3"
        print("\n[Modo: Token A3 - Windows Certificate Store]")
        token_certs = cert_handler.list_token_certs()
        if not token_certs:
            print("Erro: Nenhum certificado de token (A3) encontrado.")
            return 1

        print(f"\nEncontrado(s) {len(token_certs)} certificado(s):\n")
        for idx, cert in enumerate(token_certs, 1):
            print(f"  {idx} - {cert.get('subject', 'Desconhecido')}  (válido até {cert.get('notafter', 'N/A')})")

        if len(token_certs) == 1:
            selected_index = 0
        else:
            try:
                s = input(f"Selecione (1-{len(token_certs)}): ").strip()
                if not s.isdigit() or not (1 <= int(s) <= len(token_certs)):
                    print("Opção inválida.")
                    return 1
                selected_index = int(s) - 1
            except (KeyboardInterrupt, SystemExit):
                print("\nOperação cancelada.")
                return 1

        a3_cert_info = token_certs[selected_index]
        a3_thumbprint = a3_cert_info.get('thumbprint')
        if not a3_thumbprint:
            print("Erro: Certificado sem thumbprint.")
            return 1
        cnpj = extract_cnpj_from_subject(a3_cert_info.get('subject', ''))
        state_key = f"A3_{a3_thumbprint}"
    else:
        cert_type = "PEM"
        pem_dir = "./certificados"
        if not os.path.isdir(pem_dir):
            print(f"Erro: Diretório '{pem_dir}' não encontrado.")
            return 1

        arquivos = [f for f in os.listdir(pem_dir) if f.lower().endswith('.pem')]
        if not arquivos:
            print(f"Erro: Nenhum .pem em '{pem_dir}'.")
            return 1
        elif len(arquivos) == 1:
            pem_path = os.path.join(pem_dir, arquivos[0])
            print(f"Certificado: {arquivos[0]}")
        else:
            print(f"\nCertificados em {pem_dir}/:")
            for idx, arq in enumerate(arquivos, 1):
                print(f"  {idx} - {arq}")
            try:
                s = input(f"Selecione (1-{len(arquivos)}): ").strip()
                if not s.isdigit() or not (1 <= int(s) <= len(arquivos)):
                    print("Opção inválida.")
                    return 1
                pem_path = os.path.join(pem_dir, arquivos[int(s) - 1])
            except (KeyboardInterrupt, SystemExit):
                print("\nOperação cancelada.")
                return 1

        cnpj = extract_cnpj_from_pem(pem_path)
        state_key = os.path.basename(pem_path)

    # CNPJ
    cnpj_label = None
    if cnpj:
        cnpj_label = re.sub(r'\D', '', cnpj)
        print(f"CNPJ: {cnpj_label}")
    else:
        print("\nAviso: Não foi possível extrair o CNPJ.")
        if input("Digitar manualmente? (s/N): ").strip().lower() == 's':
            m = re.sub(r'\D', '', input("CNPJ (14 dígitos): ").strip())
            if len(m) == 14:
                cnpj_label = m

    # Ambiente: sempre produção
    env_choice = "1"
    base_url = API_URLS["1"]

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
    output_dir = "./notas_fiscais"
    if cnpj_label:
        output_dir = os.path.join(output_dir, cnpj_label)
    print(f"\nDiretório de saída: {output_dir}")
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

    # 6. Localização automática do NSU (baseada no índice)
    print("\n[Busca] Localizando NSU inicial para o período...")
    nsu = locate_nsu_by_date(do_download, base_url, start_date, cnpj_label, env_choice)

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
                        
                    # Alimenta o índice NSU com todos os NSUs encontrados
                    if cnpj_label and env_choice:
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
