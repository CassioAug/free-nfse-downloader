#!/usr/bin/env python3
import os
import sys
import subprocess
import re
import logging
import time
from datetime import datetime, date

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

import json

def load_last_nsu(pem_path, env_choice):
    state_file = "nsu_state.json"
    if not os.path.exists(state_file):
        return None
    try:
        with open(state_file, "r", encoding="utf-8") as f:
            state = json.load(f)
            key = f"{os.path.basename(pem_path)}_{env_choice}"
            return state.get(key)
    except Exception as e:
        logger.debug(f"Erro ao carregar nsu_state.json: {e}")
        return None

def save_last_nsu(pem_path, env_choice, last_nsu):
    state_file = "nsu_state.json"
    state = {}
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
        except Exception:
            state = {}
    key = f"{os.path.basename(pem_path)}_{env_choice}"
    state[key] = last_nsu
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=4, ensure_ascii=False)
        logger.info(f"Último NSU ({last_nsu}) salvo com sucesso em '{state_file}'.")
    except Exception as e:
        logger.warning(f"Não foi possível salvar o estado do NSU em '{state_file}': {e}")

def check_nsu_status_for_date(session, base_url, nsu_val, start_date):
    url = f"{base_url}/DFe/{nsu_val}"
    for attempt in range(3):
        try:
            response = session.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
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
            elif response.status_code == 404:
                return "404", None
            elif response.status_code == 429:
                time.sleep(10)
            else:
                time.sleep(2)
        except Exception:
            time.sleep(2)
    return "error", None

def locate_nsu_by_date(session, base_url, start_date):
    print("\n[Busca Automática de NSU]")
    print(f"Buscando o NSU correspondente à data inicial {start_date.strftime('%d/%m/%Y')}...")
    
    low = 1
    high = 1
    
    print("Identificando limite superior de NSUs cadastrados...")
    while True:
        status, max_nsu = check_nsu_status_for_date(session, base_url, high, start_date)
        if status == "404":
            break
        elif status in ["error", "no_data"]:
            break
        else:
            if status == "before_or_within":
                break
            high = max(high * 2, (max_nsu or high) + 1)
            print(f"  - Verificando lote em NSU {high}...")
            
    print(f"Faixa de busca de NSUs definida: de {low} a {high}")
    
    best_nsu = 1
    print("Iniciando pesquisa binária...")
    while low <= high:
        mid = (low + high) // 2
        print(f"  - Analisando NSU {mid}... ", end="", flush=True)
        status, max_nsu = check_nsu_status_for_date(session, base_url, mid, start_date)
        
        if status == "before_or_within":
            print("contém notas do período ou posteriores. Buscando mais abaixo...")
            best_nsu = mid
            high = mid - 1
        elif status == "after":
            print("apenas notas anteriores ao período. Buscando mais acima...")
            low = mid + 1
        elif status == "404":
            print("fora da faixa (fim dos registros). Buscando mais abaixo...")
            high = mid - 1
        else:
            print("sem dados suficientes. Buscando mais abaixo por segurança...")
            high = mid - 1
            
    safety_margin = 100
    nsu_com_seguranca = max(1, best_nsu - safety_margin)
    print(f"\nBusca concluída!")
    print(f"  - NSU mais próximo encontrado: {best_nsu}")
    print(f"  - Aplicando margem de segurança de {safety_margin} NSUs para cobrir notas fora de ordem.")
    print(f"  - NSU Inicial sugerido: {nsu_com_seguranca}")
    return nsu_com_seguranca

def main():
    print("=== free-nfse-downloader ===")
    print("Este script consome a API do Ambiente de Dados Nacional utilizando seu certificado PEM.\n")
    
    # 1. Caminho do Certificado PEM
    pem_path = input("Caminho para o certificado PEM (gerado pelo conversor): ").strip().strip("'\"")
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
    session = requests.Session()
    session.cert = (pem_path, pem_path)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Content-Type": "application/json"
    })

    # 6. Definição do NSU Inicial
    saved_nsu = load_last_nsu(pem_path, env_choice)
    
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
            nsu = locate_nsu_by_date(session, base_url, start_date)
        elif choice == 3:
            nsu = 1
            print("Iniciando do NSU 1.")
        else:
            nsu_input = input("Digite o NSU Inicial manualmente: ").strip()
            nsu = int(nsu_input) if nsu_input.isdigit() else 1
    else:
        if choice == 1:
            nsu = locate_nsu_by_date(session, base_url, start_date)
        elif choice == 2:
            nsu = 1
            print("Iniciando do NSU 1.")
        else:
            nsu_input = input("Digite o NSU Inicial manualmente: ").strip()
            nsu = int(nsu_input) if nsu_input.isdigit() else 1

    logger.info(f"\nIniciando busca no período: {start_date.strftime('%d/%m/%Y')} até {end_date.strftime('%d/%m/%Y')}")
    logger.info(f"Começando do NSU {nsu}. Salvando em: '{output_dir}'")
    logger.info(f"Arquivo de log: '{log_file}'")
    logger.info("-" * 60)

    consecutive_after_period = 0
    downloaded_count = 0

    while True:
        url = f"{base_url}/DFe/{nsu}"
        try:
            logger.info(f"Consultando lote de documentos a partir do NSU {nsu}...")
            response = session.get(url, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                lote = data.get("LoteDFe")
                
                # Se o lote estiver vazio ou não existir, tenta ler o XML diretamente (fallback)
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
                        
                    # Regras de Filtro por Data
                    if dt < start_date:
                        consecutive_after_period = 0
                        logger.info(f"  [NSU {nsu_item}] Nota de {dt.strftime('%d/%m/%Y')} (Antes do período, pulando...)")
                        
                    elif start_date <= dt <= end_date:
                        consecutive_after_period = 0
                        logger.info(f"  [NSU {nsu_item}] Nota de {dt.strftime('%d/%m/%Y')} (DENTRO DO PERÍODO!)")
                        
                        nfse_num = get_nfse_number(xml_content)
                        if nfse_num:
                            try:
                                formatted_num = f"{int(nfse_num):06d}"
                            except ValueError:
                                formatted_num = nfse_num.zfill(6)[-6:]
                            file_base = f"NFSe_{dt.strftime('%Y%m%d')}_{formatted_num}"
                        else:
                            file_base = f"NFSe_{dt.strftime('%Y%m%d')}_nsu_{nsu_item}"
                        xml_file_path = os.path.join(output_dir, f"{file_base}.xml")
                        
                        with open(xml_file_path, "w", encoding="utf-8") as f:
                            f.write(xml_content)
                            
                        if HAS_DANFSE_LIB:
                            pdf_file_path = os.path.join(output_dir, f"{file_base}.pdf")
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
                
            elif response.status_code == 404:
                # 404 significa que atingimos o fim da fila de NSUs cadastrados no Ambiente Nacional
                logger.info(f"\nFim da fila: O NSU {nsu} não foi encontrado (fim dos registros).")
                break
            elif response.status_code == 429:
                logger.warning("Alerta: Bloqueio temporário por limite de requisições (429). Aguardando 10 segundos...")
                time.sleep(10)
            else:
                logger.error(f"Erro ao buscar NSU {nsu}: Status {response.status_code} - {response.text}")
                nsu += 1
                
        except Exception as e:
            logger.error(f"Falha de conexão no NSU {nsu}: {e}. Tentando novamente em 5 segundos...")
            time.sleep(5)

    logger.info("-" * 60)
    logger.info(f"Processo finalizado. Total de notas baixadas no período: {downloaded_count}")
    
    last_processed_nsu = nsu - 1
    logger.info(f"Último NSU processado: {last_processed_nsu}")
    
    # Salva o último NSU no estado
    save_last_nsu(pem_path, env_choice, last_processed_nsu)
    
    logger.info("Estado do NSU atualizado. Pronto para o próximo download!")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nOperação cancelada pelo usuário.")
        sys.exit(0)
