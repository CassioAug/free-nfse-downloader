# free-nfse-downloader

Este é um projeto em Python para automação, sincronização e download de **Notas Fiscais de Serviços Eletrônicas (NFS-e)** de padrão nacional diretamente da API do **Ambiente de Dados Nacional (ADN)**.

O sistema utiliza autenticação mútua via **mTLS** com o certificado digital da empresa (e-CNPJ), permitindo realizar downloads em lote de arquivos **XML** e gerar a **DANFSE (PDF)** de forma totalmente automatizada, **sem a necessidade de digitar captchas**.

---

## Como Funciona o Sistema

O processo é composto por três fluxos principais:

```
[Certificado .pfx/.p12] -> convert_pfx.py -> [Certificado .pem]
                                                |
                                                v
[Periodo / NSU Automatico] -> download_nfse.py -> [XMLs + DANFSE PDF]
                                                  organizados em
                                             prestados/ e tomados/

[XMLs locais ou em lote] -> xml_to_pdf.py -> [DANFSE PDF (Conversao Manual)]
```

1. **Conversao do Certificado:** O script `convert_pfx.py` extrai a chave privada (desprotegida) e a cadeia de certificados do arquivo original da sua empresa (`.pfx` ou `.p12`) e gera um arquivo consolidado em `.pem` exigido pela biblioteca HTTP do Python. Necessario apenas para certificados A1 (arquivo). Para tokens A3, o certificado ja esta no sistema.
2. **Download das Notas:** O script `download_nfse.py` consome a API do governo utilizando o certificado digital para autenticacao de rede (mTLS). As notas sao baixadas em lotes sequenciais de ate 50 documentos controlados por **NSU (Numero Sequencial Unico)**, filtradas pelo periodo escolhido e salvas localmente em subpastas `prestados/` e `tomados/`.
3. **Conversao Manual de XML para PDF:** O script `xml_to_pdf.py` permite converter arquivos XML ja baixados localmente para PDFs (DANFSE) a qualquer momento de forma avulsa ou em lote, sem precisar consultar a API do governo novamente.

### Organizacao por Tipo de Servico

Ao final do download, os arquivos sao automaticamente organizados em:
- **`prestados/`**: Notas em que sua empresa e o prestador do servico
- **`tomados/`**: Notas em que sua empresa e o tomador do servico
- **`sem_data/`**: XMLs de eventos sem data de emissao (cancelamentos, cartas de correcao, etc.)

---

## Pre-requisitos

- **Python 3.8+** instalado
- Certificado Digital **A1 (e-CNPJ em arquivo .pfx/.p12)** ou **A3 (token USB)** da empresa
- Dependencias do projeto (instaladas automaticamente na primeira execucao do script):
  - `requests` (para chamadas HTTP com certificado A1/PEM)
  - `cryptography` (para manuseio seguro do certificado)
  - `brazilfiscalreport[danfse]` (opcional, para renderizar o PDF da DANFSE localmente)
  - `playwright` (apenas para token A3 no Windows - Chrome headful)

---

## Instalacao e Execucao

### Passo 1: Obter o codigo do projeto

```bash
git clone https://github.com/CassioAug/free-nfse-downloader.git
cd free-nfse-downloader
```

### Passo 2: Converter o Certificado (apenas A1/PEM)

Coloque o seu arquivo `.pfx` ou `.p12` na pasta `./certificados`. Para rodar o conversor:

```bash
python convert_pfx.py
```

O script e interativo:
1. Informe o caminho do arquivo `.pfx` ou `.p12` (Enter para listar em `./certificados`).
2. Digite a senha do certificado.
3. Defina o nome do arquivo de saida (padrao: `./certificados/`.

*Para token A3, pule esta etapa - o certificado ja esta no Windows Certificate Store.*

### Passo 3: Executar o Coletor de Notas

```bash
python download_nfse.py
```

O script e guiado, mas com opcoes simplificadas:

1. **Tipo de certificado:** `1` para certificado A1 (arquivo `.pem`) ou `2` para token A3 (USB).
2. **Selecao do certificado:** Para A1/PEM, escolha o arquivo na pasta `./certificados`. Para A3, escolha o certificado no Windows Certificate Store.
3. **CNPJ:** Extraido automaticamente do certificado. Se falhar, e possivel digitar manualmente.
4. **Periodo:** Informe a data inicial e final do periodo desejado (Formato: `DD/MM/YYYY`).

O NSU inicial e **localizado automaticamente** atraves de um indice em cache e busca binaria. Nao e necessario informa-lo manualmente.

#### Para token A3 (Windows)

Ao selecionar token A3, o script:
1. Abre o Google Chrome automaticamente (via Playwright)
2. Exibe o popup do driver SafeSign para insercao do PIN (uma unica vez)
3. Mantem a sessao TLS ativa no Chrome e faz as requisicoes via `fetch()` interno
4. Fecha o Chrome ao finalizar

**Requisitos adicionais para A3:**
```bash
pip install playwright
playwright install chromium
```

### Passo 4: Reorganizar XMLs ja baixados (Opcional)

Se voce ja possui XMLs baixados e quer classificar/separar por tipo de servico sem baixar novamente:

```bash
python organize_nfse.py --dir ./notas_fiscais/SEU_CNPJ --cnpj SEU_CNPJ
```

### Passo 5: Converter XMLs Locais para PDF (Opcional)

```bash
python xml_to_pdf.py [caminho_entrada] [opcoes]
```

Exemplos:
- **Converter todos os XMLs pendentes** na pasta padrao (`./notas_fiscais`):
  ```bash
  python xml_to_pdf.py
  ```
- **Forcar a regeneracao** de todos os PDFs (sobrescrevendo os existentes):
  ```bash
  python xml_to_pdf.py -f
  ```
- **Converter um unico arquivo XML especifico**:
  ```bash
  python xml_to_pdf.py ./notas_fiscais/NFSe_20260605_nsu_369.xml
  ```
- **Definir pasta de entrada e pasta de saida personalizadas**:
  ```bash
  python xml_to_pdf.py /caminho/origem -o /caminho/destino
  ```

---

## Fluxo de Busca de NSU

O sistema utiliza um indice local para evitar requisicoes desnecessarias ao servidor:

1. **Cache exato (data->NSU):** Se a data inicial ja foi consultada antes, usa o NSU salvo em cache. Zero requisicoes.
2. **Indice NSU->data:** Varredura de 100 em 100 (NSU 1, 100, 200...) construida ao longo das execucoes. Faz busca binaria (~7 requisicoes) para encontrar o NSU ideal.
3. **Extensao automatica:** Se o indice nao cobre a data, o script estende o indice automaticamente e faz a busca.
4. **Salvamento continuo:** Cada NSU encontrado durante o download e adicionado ao indice para acelerar execucoes futuras.

---

## Logs e Cache

- **`coletor_nfse.log`:** Historico detalhado da execucao.
- **`cache_nsu/`:** Indice NSU->data e cache data->NSU (persistido entre execucoes).
- **`nsu_state.json`:** Ultimo NSU processado por chave de certificado.
- **`./notas_fiscais/{CNPJ}/`:** Diretorio de saida com subpastas `prestados/`, `tomados/`, `sem_data/`.

---

## Notas Importantes e Boas Praticas

### Limite de Requisicoes (Erro 429) e Instabilidades

As APIs da Receita Federal implementam limites severos de requisicoes por minuto (**Rate Limiting**).
- Caso o script receba um erro `429 (Too Many Requests)`, ele dobra o intervalo entre requisicoes (ate 15s maximo) e retoma automaticamente.
- Quedas de conexao e timeouts sao normais devido a instabilidade dos servidores governamentais. O script possui tratamento de excecoes com tentativas automaticas.

### Seguranca (Git / GitHub)

O projeto ja conta com um arquivo `.gitignore` configurado. **Nunca remova as regras de ignore**. Elas impedem que os arquivos confidenciais do seu certificado (`.pfx` ou `.pem`), as notas fiscais baixadas, cache e logs sejam enviados para o repositorio.

---

## Licenca

Este projeto esta licenciado sob a licenca MIT. Consulte o arquivo [LICENSE](LICENSE) para obter mais detalhes.
