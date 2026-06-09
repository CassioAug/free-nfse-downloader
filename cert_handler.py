#!/usr/bin/env python3
"""
cert_handler.py - Módulo de handling de certificados digitais
Suporta:
  - Certificados em arquivo PEM/PFX (fluxo original)
  - Certificados A3 via Windows Certificate Store (PowerShell + .NET/Schannel)
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

def safe_print(text):
    """Imprime texto de forma segura no console Windows, tratando erros de encoding"""
    import sys
    try:
        print(text)
    except UnicodeEncodeError:
        encoding = sys.stdout.encoding or 'utf-8'
        try:
            print(text.encode(encoding, errors='replace').decode(encoding))
        except Exception:
            print(text.encode('ascii', errors='replace').decode('ascii'))

def list_a3_certs_pretty():
    """Lista certificados A3 de forma formatada para seleção"""
    token_certs = list_token_certs()

    if not token_certs:
        safe_print("Nenhum certificado de token (A3) encontrado no Windows Certificate Store.")
        safe_print("Verifique se o token está conectado e se o driver SafeSign está instalado.")
        return []

    safe_print(f"\nEncontrados {len(token_certs)} certificado(s) de token (A3):\n")

    for idx, cert in enumerate(token_certs, 1):
        subject = cert.get('subject', 'Desconhecido')
        thumbprint = cert.get('thumbprint', 'N/A')
        provider = cert.get('provider', 'N/A')
        notafter = cert.get('notafter', 'N/A')
        key_export = cert.get('key_exportable', 'N/A')

        safe_print(f"  {idx} - {subject}")
        safe_print(f"      Thumbprint: {thumbprint}")
        safe_print(f"      Provider: {provider}")
        safe_print(f"      Validade: {notafter}")
        safe_print(f"      Chave Privada: {key_export}")
        safe_print("")

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
        thumbprint: Thumbprint SHA1 do certificado (usado com store: prefix)
        output_path: Arquivo de saída
        extra_args: Lista extra de argumentos para o curl

    Returns:
        tuple: (success: bool, message: str)
    """
    if not os.path.exists(CURL_PATH):
        return False, f"curl.exe não encontrado em {CURL_PATH}"

    cmd = [
        CURL_PATH,
        '-sS', '-k',
    ]

    if thumbprint:
        clean_thumbprint = re.sub(r'[^a-fA-F0-9]', '', thumbprint).upper()
        cmd.append('--cert')
        cmd.append(f"CurrentUser\\My\\{clean_thumbprint}")
        # Força o uso do TLS 1.2, pois tokens A3 costumam falhar no TLS 1.3
        # devido à exigência do algoritmo de assinatura RSASSA-PSS (não suportado).
        cmd.append('--tls-max')
        cmd.append('1.2')
    else:
        cmd.append('--ssl-auto-client-cert')

    cmd.extend([
        '-o', output_path,
        url
    ])

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

def download_json_with_winhttp(url, cert_name):
    """
    Faz download de JSON utilizando a API WinHTTP COM nativa do Windows.
    Bypass de erros do Schannel em tokens A3 e controle nativo de PIN.
    """
    import win32com.client
    
    # Extrai o Common Name (CN) do cert_name se for um Distinguished Name completo
    cn_match = re.search(r'CN\s*=\s*([^,]+)', cert_name, re.IGNORECASE)
    clean_cert_name = cn_match.group(1).strip() if cn_match else cert_name.strip()
    
    try:
        # Cria o objeto WinHttpRequest
        req = win32com.client.Dispatch("WinHttp.WinHttpRequest.5.1")
        
        # Opção 18: EnableCertificateRevocationCheck (False desativa a validação de revogação de CRL)
        req.SetOption(18, False)
        
        # Opção 4: SslErrorIgnoreFlags (13056 ignora erros de certificado do servidor)
        req.SetOption(4, 13056)
        
        # Abre a conexão síncrona
        req.Open("GET", url, False)
        
        # Define o certificado do cliente
        cert_path = f"CURRENT_USER\\MY\\{clean_cert_name}"
        req.SetClientCertificate(cert_path)
        
        # Envia a requisição
        req.Send()
        
        if req.Status == 200:
            return True, req.ResponseText
        else:
            return False, f"HTTP {req.Status} - {req.StatusText}: {req.ResponseText[:200]}"
    except Exception as e:
        return False, f"Erro WinHTTP COM: {str(e)}"

# --- Download via PowerShell + .NET (suporte a PIN do token A3) ---

def _write_and_run_ps(ps_script, env_extra=None, timeout=120):
    """
    Escreve um script .ps1 temporário com um .log sidecar (definido via env_extra['LOG_PATH']),
    executa com timeout, e retorna (stdout, stderr, returncode, log_content).

    O .log é lido mesmo em caso de timeout para diagnóstico.
    """
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ps1', delete=False, encoding='utf-8') as f:
        ps1_path = f.name

    log_path = ps1_path.replace('.ps1', '.log')
    env = os.environ.copy()
    env['LOG_PATH'] = log_path
    if env_extra:
        env.update(env_extra)

    try:
        with open(ps1_path, 'w', encoding='utf-8') as f:
            f.write(ps_script)

        proc = subprocess.run(
            ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', ps1_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=timeout,
            env=env,
        )
        rc = proc.returncode
        stdout, stderr = proc.stdout, proc.stderr

    except subprocess.TimeoutExpired:
        stdout, stderr, rc = "", "TIMEOUT_EXPIRED", -1
    except Exception as e:
        stdout, stderr, rc = "", f"EXCEPTION: {e}", -2

    log_text = ""
    if os.path.exists(log_path):
        try:
            with open(log_path, 'r', encoding='utf-8', errors='replace') as lf:
                log_text = lf.read()
        except Exception:
            pass

    for p in [ps1_path, log_path]:
        try:
            os.unlink(p)
        except Exception:
            pass

    return stdout, stderr, rc, log_text


def download_json_with_powershell(url, thumbprint):
    """
    Faz download usando .NET WebRequest com certificado A3.
    Gera log detalhado para diagnóstico mesmo em caso de timeout.
    """
    thumb_upper = thumbprint.upper()
    url_escaped = url.replace('"', '`"')

    ps_script = (
        'function Write-Log($m) {\n'
        '    $ts = Get-Date -Format "HH:mm:ss.fff"\n'
        '    "$ts $m" | Out-File -FilePath $env:LOG_PATH -Append -Encoding UTF8\n'
        '}\n'
        'Write-Log "INICIADO thumbprint=' + thumb_upper + '"\n'
        'Write-Log "URL=' + url_escaped + '"\n'
        '[Console]::OutputEncoding = [System.Text.Encoding]::UTF8\n'
        '[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12\n'
        '[Net.ServicePointManager]::ServerCertificateValidationCallback = { $true }\n'
        'Write-Log "TLS_CONFIG OK"\n'
        # certificado
        'try {\n'
        '    $cert = Get-ChildItem -Path "Cert:\\CurrentUser\\My\\' + thumb_upper + '" -ErrorAction Stop\n'
        '    Write-Log "CERT subject=$($cert.Subject)"\n'
        '} catch {\n'
        '    Write-Log "CERT_ERR $($_.Exception.Message)"\n'
        '    [Console]::Error.Write("ERRO_CERT:" + $_.Exception.Message)\n'
        '    exit 1\n'
        '}\n'
        # request via HttpClient (evita deadlock do HttpWebRequest com CSP de token)
        'try {\n'
        '    Add-Type -AssemblyName System.Net.Http -ErrorAction Stop | Out-Null\n'
        '    $handler = New-Object System.Net.Http.HttpClientHandler\n'
        '    $handler.ClientCertificates.Add($cert)\n'
        '    $client = New-Object System.Net.Http.HttpClient($handler)\n'
        '    $client.Timeout = [System.TimeSpan]::FromSeconds(90)\n'
        '    Write-Log "REQ chamando HttpClient.GetAsync()..."\n'
        '    $resp = $client.GetAsync("' + url_escaped + '").GetAwaiter().GetResult()\n'
        '    Write-Log "RESP StatusCode=$([int]$resp.StatusCode)"\n'
        '    $content = $resp.Content.ReadAsStringAsync().GetAwaiter().GetResult()\n'
        '    $resp.Dispose()\n'
        '    $client.Dispose()\n'
        '    Write-Log "CONTEUDO Length=$($content.Length)"\n'
        '    $bytes = [System.Text.Encoding]::UTF8.GetBytes($content)\n'
        '    $sout = [System.Console]::OpenStandardOutput()\n'
        '    $sout.Write($bytes, 0, $bytes.Length)\n'
        '    $sout.Flush()\n'
        '    Write-Log "SUCESSO"\n'
        '} catch {\n'
        '    $msg = $_.Exception.Message\n'
        '    if ($_.Exception.InnerException) { $msg += " | INNER:" + $_.Exception.InnerException.Message }\n'
        '    if ($_.Exception.InnerException.InnerException) { $msg += " | INNER2:" + $_.Exception.InnerException.InnerException.Message }\n'
        '    Write-Log "ERRO_REQ $msg"\n'
        '    [Console]::Error.Write("ERRO_REQ:" + $msg)\n'
        '    exit 1\n'
        '}\n'
    )

    stdout, stderr, rc, log_text = _write_and_run_ps(ps_script, timeout=120)

    diag_parts = []
    if log_text:
        diag_parts.append("[LOG]" + log_text.strip())
    if stderr and stderr not in ("TIMEOUT_EXPIRED",):
        diag_parts.append("[STDERR]" + stderr.strip())
    diag = "\n".join(diag_parts)

    if rc == 0 and stdout:
        return True, stdout

    if stderr == "TIMEOUT_EXPIRED":
        return False, f"Timeout 120s.{diag}"
    if rc == -2:
        return False, f"Exceção:{diag}"

    if "ERRO_CERT:" in stderr:
        return False, f"Falha ao carregar certificado.{diag}"
    if "ERRO_CADEIA:" in stderr:
        return False, f"Falha ao montar cadeia.{diag}"
    if "ERRO_REQ:" in stderr:
        return False, f"Erro HTTP.{diag}"

    return False, f"Erro.{diag}"


class PlaywrightA3Client:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None

    def initialize(self, initial_url):
        from playwright.sync_api import sync_playwright
        print("\n[Playwright] Inicializando Chrome para conexão segura com token A3...")
        self.playwright = sync_playwright().start()
        
        # Lançamos o Google Chrome instalado no sistema (channel="chrome")
        # em modo headful (headless=False) para mostrar o PIN popup
        self.browser = self.playwright.chromium.launch(
            channel="chrome",
            headless=False
        )
        self.context = self.browser.new_context(
            ignore_https_errors=True
        )
        self.page = self.context.new_page()
        
        print(f"[Playwright] Navegando para URL de autenticação: {initial_url}")
        print("[Token A3] Por favor, digite a senha (PIN) do token se solicitado na tela...")
        
        # Faz a primeira carga para autenticar e disparar o PIN
        self.page.goto(initial_url, timeout=90000)
        print("[Playwright] Canal SSL/TLS estabelecido com sucesso!")

    def download_url(self, url):
        # Executa o fetch dentro do contexto da página já autenticada
        res = self.page.evaluate("""async (targetUrl) => {
            try {
                const r = await fetch(targetUrl);
                const text = await r.text();
                return { status: r.status, text: text, error: null };
            } catch (e) {
                return { status: 0, text: null, error: e.toString() };
            }
        }""", url)
        
        status_code = res.get("status", 0)
        text = res.get("text", "")
        error = res.get("error")
        return status_code, text, error

    def close(self):
        try:
            if self.browser:
                self.browser.close()
            if self.playwright:
                self.playwright.stop()
            print("[Playwright] Sessão finalizada com sucesso.")
        except Exception:
            pass


def cleanup_powershell_client():
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
        safe_print("4. Testando download com Playwright + Chrome + A3...")
        safe_print("   (Um diálogo de PIN do token A3 deve aparecer na tela)")
        test_url = "https://adn.nfse.gov.br/contribuintes/DFe/1"
        subject = token_certs[0].get('subject')
        if subject:
            try:
                client = PlaywrightA3Client()
                client.initialize(test_url)
                status_code, data, error = client.download_url(test_url)
                client.close()
                
                if status_code == 200:
                    safe_print(f"   OK - Resposta recebida ({len(data)} bytes)")
                    try:
                        json_data = json.loads(data)
                        safe_print(f"   Keys no JSON: {list(json_data.keys())}")
                    except json.JSONDecodeError:
                        safe_print("   (não é JSON válido)")
                elif status_code > 0:
                    safe_print(f"   OK (Status HTTP {status_code}) - Conexão mTLS e TLS Handshake funcionaram!")
                    safe_print(f"   Resposta: {data[:200]}")
                else:
                    safe_print(f"   ERRO de Rede/Chrome: {error}")
            except Exception as e:
                safe_print(f"   ERRO ao testar: {e}")
        else:
            safe_print("   ERRO - Sem subject para testar")
    else:
        safe_print("4. Teste pulado (sem certificados A3 disponíveis)")

    print("\n=== Teste concluído ===")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
