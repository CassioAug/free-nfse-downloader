# Uso via Linha de Comando (CLI)

Este documento é voltado para desenvolvedores e usuários avançados que desejam executar ou automatizar o **free-nfse-downloader** diretamente pelo terminal, sem a interface gráfica.

---

## 1. Configuração do Ambiente

Recomenda-se utilizar um ambiente virtual isolado (`.venv`):

```bash
# No Windows
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# No Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## 2. Coletor de Notas (`src/download_nfse.py`)

O script principal é responsável por se conectar à API do Ambiente de Dados Nacional (ADN) e baixar as notas em lote.

### Execução Padrão:
```bash
python src/download_nfse.py
```

Você também pode utilizar o argumento opcional:
```bash
python src/download_nfse.py --ignorar-cache
```
- `--ignorar-cache`: Desconsidera o índice local de NSU (`cache_nsu/`) e reinicia a busca a partir do primeiro NSU disponível, garantindo a varredura completa.

O script é guiado e interativo:
1. **Tipo de Certificado:**
   - Digite `1` para Certificado A1 (arquivo `.pem`).
   - Digite `2` para Certificado A3 (Token USB / Windows Certificate Store).
2. **Seleção do Certificado:**
   - Para A1/PEM: selecione o arquivo listado na pasta `./certificados`.
   - Para A3: selecione o certificado listado pelo Windows Certificate Store.
3. **CNPJ da Empresa:**
   - O CNPJ é extraído automaticamente do certificado digital. Se a extração falhar, você poderá digitá-lo manualmente (14 dígitos).
4. **Período de Consulta:**
   - Data Inicial: formato `DD/MM/YYYY` (obrigatória).
   - Data Final: formato `DD/MM/YYYY` (opcional; se deixar em branco, utiliza a data atual).

O NSU (Número Sequencial Único) é **localizado automaticamente** através de cache e busca binária temporal. Não é necessário informá-lo manualmente.

---

## 3. Conversor de Certificado (`src/convert_pfx.py`)

Necessário apenas para certificados do tipo **A1** (arquivos `.pfx` ou `.p12`). O script extrai a chave privada e a cadeia de certificados e gera um arquivo consolidado em `.pem` exigido pelas bibliotecas de rede do Python.

```bash
python src/convert_pfx.py [caminho_pfx] [senha] [caminho_saida_pem]
```

### Exemplos:

- **Modo Interativo (recomendado):**
  Coloque seu arquivo `.pfx` ou `.p12` na pasta `./certificados` e execute:
  ```bash
  python src/convert_pfx.py
  ```
  O script listará os certificados encontrados e solicitará a senha.

- **Modo Direto com argumentos:**
  ```bash
  python src/convert_pfx.py ./certificados/minha_empresa.pfx "minhasenha123"
  ```

---

## 4. Reorganizar XMLs Locais (`src/organize_nfse.py`)

Se você já possui notas baixadas e deseja reorganizá-las em subpastas de serviços prestados e tomados:

```bash
python src/organize_nfse.py --dir ./notas_fiscais/12345678000199 --cnpj 12345678000199
```

### Argumentos:
- `--dir` (obrigatório): Caminho da pasta que contém os arquivos XML.
- `--cnpj` (obrigatório): CNPJ de 14 dígitos da empresa consultante.

Os arquivos serão distribuídos em:
- `prestados/`: Notas em que a empresa é o prestador.
- `tomados/`: Notas em que a empresa é o tomador.
- `sem_data/`: Eventos sem data de emissão identificada.

---

## 5. Conversor de XML para PDF (`src/xml_to_pdf.py`)

Converte arquivos XML de NFS-e salvos localmente em relatórios visuais DANFSE (PDF) utilizando a biblioteca `brazilfiscalreport`, sem precisar consultar os servidores do governo.

```bash
python src/xml_to_pdf.py [caminho_entrada] [opcoes]
```

### Exemplos:

- **Converter todos os XMLs pendentes** na pasta padrão (`./notas_fiscais`):
  ```bash
  python src/xml_to_pdf.py
  ```

- **Forçar a regeneração** de todos os PDFs (sobrescrevendo existentes):
  ```bash
  python src/xml_to_pdf.py -f
  ```

- **Converter um único arquivo XML específico:**
  ```bash
  python src/xml_to_pdf.py ./notas_fiscais/NFSe_20260605_nsu_369.xml
  ```

- **Definir pasta de entrada e pasta de saída personalizadas:**
  ```bash
  python xml_to_pdf.py /caminho/origem -o /caminho/destino
  ```

---

## 6. Observação sobre Token A3 (Windows)

Para utilizar certificados em Token USB (A3), o projeto utiliza automação com o Google Chrome via Playwright no Windows:

```bash
pip install playwright
playwright install chromium
```

No Linux, o uso de tokens físicos A3 não é suportado pelo portal ADN/driver PKCS#11 da mesma maneira; recomenda-se a utilização de certificados digitais do tipo A1 (`.pfx` / `.pem`).
