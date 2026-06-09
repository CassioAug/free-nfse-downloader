#!/usr/bin/env python3
"""
cert_handler.py - Módulo de handling de certificados digitais
Suporta:
  - Certificados em arquivo PEM/PFX (fluxo original)
  - Certificados A3 via Windows Certificate Store (curl + Schannel)
"""
import subprocess
import os
import json
import re
import tempfile

CURL_PATH = r"C:\Windows\System32\curl.exe"

def check_curl_available():
    """Verifica se curl está disponível no sistema"""
    try:
        result = subprocess.run(
            [CURL_PATH, "--version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False

def list_windows_store_certs(store_location="My", use_current_user=True):
    """
    Lista certificados do Windows Certificate Store via certutil.

    Args:
        store_location: Nome do repositório (default: "My" = Pessoal)
        use_current_user: Se True, usa repositório do usuário atual

    Returns:
        list: Lista de dicts com info dos certificados
    """
    cmd = [r"C:\Windows\System32\certutil.exe"]
    if use_current_user:
        cmd.append("-user")
    cmd.append("-store")
    cmd.append(store_location)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=30
        )
    except Exception as e:
        print(f"Erro ao executar certutil: {e}")
        return []

    if result.returncode != 0:
        print(f"certutil retornou código: {result.returncode}")
        return []

    output = result.stdout
    certs = []

    cert_pattern = re.compile(
        r'================ Certificado \d+ ================\s*'
        r'(?:N[^\n]+\n)?'
        r'(?:Issuer:[^\n]+\n)?'
        r'(?:NotBefore:[^\n]+\n)?'
        r'(?:NotAfter:[^\n]+\n)?'
        r'Requerente:[^\n]+\n'
        r'(?:Certificado[^\n]+\n)?'
        r'(?:Hash Cert\(sha1\):[^\n]+\n)?'
        r'(?:  Cont[^\n]+\n)?'
        r'(?:  Provider = [^\n]+)?',
        re.IGNORECASE | re.MULTILINE
    )

    serial_pattern = re.compile(r'N[^\n]+: ([0-9a-fA-F]+)', re.IGNORECASE)
    issuer_pattern = re.compile(r'Issuer: (.+)', re.IGNORECASE)
    notbefore_pattern = re.compile(r'NotBefore: ([^\n]+)', re.IGNORECASE)
    notafter_pattern = re.compile(r'NotAfter: ([^\n]+)', re.IGNORECASE)
    req_pattern = re.compile(r'Requerente: (.+)', re.IGNORECASE)
    hash_pattern = re.compile(r'Hash Cert\(sha1\): ([0-9a-fA-F]+)', re.IGNORECASE)
    provider_pattern = re.compile(r'Provider = (.+)', re.IGNORECASE)
    key_exportable_pattern = re.compile(r'chave privada (.+) export', re.IGNORECASE)

    lines = output.split('\n')
    current_cert = None

    for line in lines:
        line = line.strip()

        if line.startswith('================ Certificado'):
            if current_cert:
                certs.append(current_cert)
            current_cert = {
                'raw': line,
                'serial': None,
                'issuer': None,
                'notbefore': None,
                'notafter': None,
                'subject': None,
                'thumbprint': None,
                'provider': None,
                'key_exportable': None,
            }
        elif current_cert is None:
            continue

        serial_match = serial_pattern.search(line)
        if serial_match:
            current_cert['serial'] = serial_match.group(1).strip()

        issuer_match = issuer_pattern.search(line)
        if issuer_match:
            current_cert['issuer'] = issuer_match.group(1).strip()

        notbefore_match = notbefore_pattern.search(line)
        if notbefore_match:
            current_cert['notbefore'] = notbefore_match.group(1).strip()

        notafter_match = notafter_pattern.search(line)
        if notafter_match:
            current_cert['notafter'] = notafter_match.group(1).strip()

        req_match = req_pattern.search(line)
        if req_match:
            current_cert['subject'] = req_match.group(1).strip()

        hash_match = hash_pattern.search(line)
        if hash_match:
            current_cert['thumbprint'] = hash_match.group(1).strip().lower()

        provider_match = provider_pattern.search(line)
        if provider_match:
            current_cert['provider'] = provider_match.group(1).strip()

        key_export_match = key_exportable_pattern.search(line)
        if key_export_match:
            current_cert['key_exportable'] = key_export_match.group(1).strip()

    if current_cert:
        certs.append(current_cert)

    return certs

def is_token_certificate(cert_info):
    """Verifica se o certificado é de um token (A3) baseado no Provider"""
    if not cert_info:
        return False
    provider = cert_info.get('provider', '') or ''
    return 'SafeSign' in provider or 'IC Standard' in provider

def list_token_certs():
    """Lista apenas certificados de token (A3) no Windows Store"""
    all_certs = list_windows_store_certs()
    token_certs = [c for c in all_certs if is_token_certificate(c)]
    return token_certs

def list_a3_certs_pretty():
    """Lista certificados A3 de forma formatada para seleção"""
    token_certs = list_token_certs()

    if not token_certs:
        print("Nenhum certificado de token (A3) encontrado no Windows Certificate Store.")
        print("Verifique se o token está conectado e se o driver SafeSign está instalado.")
        return []

    print(f"\nEncontrados {len(token_certs)} certificado(s) de token (A3):\n")

    for idx, cert in enumerate(token_certs, 1):
        subject = cert.get('subject', 'Desconhecido')
        thumbprint = cert.get('thumbprint', 'N/A')
        provider = cert.get('provider', 'N/A')
        notafter = cert.get('notafter', 'N/A')
        key_export = cert.get('key_exportable', 'N/A')

        print(f"  {idx} - {subject}")
        print(f"      Thumbprint: {thumbprint}")
        print(f"      Provider: {provider}")
        print(f"      Validade: {notafter}")
        print(f"      Chave Privada: {key_export}")
        print()

    return token_certs

def get_thumbprint_by_index(cert_list, index):
    """Retorna o thumbprint do certificado baseado no índice da lista"""
    if not cert_list or index < 0 or index >= len(cert_list):
        return None
    return cert_list[index].get('thumbprint')

def download_with_curl(url, thumbprint, output_path, extra_args=None):
    """
    Faz download usando curl com certificado do Windows Certificate Store.

    Args:
        url: URL para download
        thumbprint: Thumbprint SHA1 do certificado (ignorado, usa auto-client-cert)
        output_path: Arquivo de saída
        extra_args: Lista extra de argumentos para o curl

    Returns:
        tuple: (success: bool, message: str)
    """
    if not os.path.exists(CURL_PATH):
        return False, f"curl.exe não encontrado em {CURL_PATH}"

    cmd = [
        CURL_PATH,
        '-s', '-k',
        '--ssl-auto-client-cert',
        '-o', output_path,
        url
    ]

    if extra_args:
        cmd.extend(extra_args)

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=60
        )

        if result.returncode == 0:
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return True, "Download realizado com sucesso"
            else:
                return False, "Arquivo de saída vazio ou não criado"
        else:
            error_msg = result.stderr or result.stdout or "Erro desconhecido"
            if "SSL certificate problem" in error_msg or "client certificate" in error_msg.lower():
                return False, f"Erro de certificado: {error_msg}"
            return False, f"curl retornou código {result.returncode}: {error_msg}"

    except subprocess.TimeoutExpired:
        return False, "Timeout na requisição"
    except Exception as e:
        return False, f"Exceção: {str(e)}"

def download_json_with_curl(url, thumbprint):
    """
    Faz download e retorna o conteúdo como texto (para respostas JSON).

    Args:
        url: URL para download
        thumbprint: Thumbprint SHA1 do certificado

    Returns:
        tuple: (success: bool, data: str or error_message)
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        temp_path = f.name

    try:
        success, msg = download_with_curl(url, thumbprint, temp_path)
        if not success:
            return False, msg

        with open(temp_path, 'r', encoding='utf-8', errors='replace') as f:
            data = f.read()

        return True, data
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass

def main():
    """Teste direto do módulo"""
    print("=== cert_handler.py - Teste de Módulo ===\n")

    print("1. Verificando curl...")
    if check_curl_available():
        print("   OK - curl disponível\n")
    else:
        print("   ERRO - curl não disponível\n")
        return 1

    print("2. Listando certificados no Windows Store (usuário atual)...")
    all_certs = list_windows_store_certs()
    print(f"   Encontrados {len(all_certs)} certificado(s) total\n")

    print("3. Listando certificados de token (A3)...")
    token_certs = list_token_certs()
    if token_certs:
        list_a3_certs_pretty()
    else:
        print("   Nenhum certificado de token encontrado\n")

    if token_certs:
        print("4. Testando download com curl + A3...")
        test_url = "https://adn.nfse.gov.br/contribuintes/DFe/1"
        thumbprint = token_certs[0].get('thumbprint')
        if thumbprint:
            success, data = download_json_with_curl(test_url, thumbprint)
            if success:
                print(f"   OK - Resposta recebida ({len(data)} bytes)")
                try:
                    json_data = json.loads(data)
                    print(f"   Keys no JSON: {list(json_data.keys())}")
                except json.JSONDecodeError:
                    print("   (não é JSON válido)")
            else:
                print(f"   ERRO: {data}")
        else:
            print("   ERRO - Sem thumbprint para testar")
    else:
        print("4. Teste pulado (sem certificados A3 disponíveis)")

    print("\n=== Teste concluído ===")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
