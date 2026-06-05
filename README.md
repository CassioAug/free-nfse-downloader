# free-nfse-downloader

Este é um projeto em Python para automação, sincronização e download de **Notas Fiscais de Serviços Eletrônicas (NFS-e)** de padrão nacional diretamente da API do **Ambiente de Dados Nacional (ADN)**.

O sistema utiliza autenticação mútua via **mTLS** com o certificado digital da empresa (e-CNPJ), permitindo realizar downloads em lote de arquivos **XML** e gerar a **DANFSE (PDF)** de forma totalmente automatizada, **sem a necessidade de digitar captchas**.

---

## 🚀 Como Funciona o Sistema

O processo é composto por três fluxos principais:

```
[Certificado .pfx/.p12] ➔ convert_pfx.py ➔ [Certificado .pem]
                                                  │
                                                  ▼
[Período / NSU Inicial] ➔ download_nfse.py ➔ [Downloads de XML e DANFSE PDF]

[XMLs locais ou em lote] ➔ xml_to_pdf.py   ➔ [DANFSE PDF (Conversão Manual)]
```

1. **Conversão do Certificado:** O script `convert_pfx.py` extrai a chave privada (desprotegida) e a cadeia de certificados do arquivo original da sua empresa (`.pfx` ou `.p12`) e gera um arquivo consolidado em `.pem` exigido pela biblioteca HTTP do Python.
2. **Download das Notas:** O script `download_nfse.py` consome a API do governo utilizando o arquivo `.pem` para autenticação de rede (mTLS). As notas são baixadas em lotes sequenciais de até 50 documentos controlados por **NSU (Número Sequencial Único)**, filtradas pelo período escolhido e salvas localmente.
3. **Conversão Manual de XML para PDF:** O script `xml_to_pdf.py` permite converter arquivos XML já baixados localmente para PDFs (DANFSE) a qualquer momento de forma avulsa ou em lote, sem precisar consultar a API do governo novamente.

---

## 🛠️ Pré-requisitos

- **Python 3.8+** instalado.
- Certificado Digital do tipo **A1 (e-CNPJ)** da empresa.
- Dependências do projeto (instaladas automaticamente na primeira execução do script, ou manualmente):
  - `requests` (para chamadas HTTP)
  - `cryptography` (para manuseio seguro do certificado)
  - `brazilfiscalreport[danfse]` (opcional, para renderizar o PDF da DANFSE localmente)

---

## 📦 Instalação e Execução

### Passo 1: Obter o código do projeto
Você pode obter os arquivos do projeto de duas formas simples:

#### Opção A: Clonando via Git (Recomendado)
Se você já possui o **Git** instalado:
1. Abra o seu terminal (Prompt de Comando / PowerShell no Windows, ou Terminal no macOS/Linux).
2. Vá até a pasta onde deseja salvar o projeto (ex: `cd Documents`) e execute:
   ```bash
   git clone https://github.com/CassioAug/free-nfse-downloader.git
   ```
3. Entre na pasta criada pelo Git:
   ```bash
   cd free-nfse-downloader
   ```

#### Opção B: Baixando o arquivo ZIP (Para quem não usa Git)
Se você não tem o Git ou prefere baixar manualmente:
1. No topo desta página do repositório no GitHub, clique no botão verde **Code** e depois em **Download ZIP**.
2. Salve o arquivo no seu computador e **extraia (descompacte)** a pasta ZIP na sua pasta de preferência (ex: Documentos ou Área de Trabalho).
3. Abra a pasta que você acabou de extrair.
4. Abra o terminal diretamente nesta pasta:
   - **No Windows:** Dentro da pasta, clique no espaço em branco da barra de endereços no topo da janela (onde fica o caminho da pasta), digite `cmd` e aperte `Enter`. O Prompt de Comando abrirá diretamente na pasta certa.
   - **No macOS / Linux:** Clique com o botão direito em um espaço vazio dentro da pasta e selecione **Abrir no Terminal** (ou "Open in Terminal").

### Passo 2: Converter o Certificado Digital
Para rodar o conversor:
```bash
python convert_pfx.py
```
*O script é interativo:*
1. Informe o caminho do seu arquivo `.pfx` ou `.p12` (ou informe a pasta para que ele liste os certificados encontrados).
2. Digite a senha do certificado.
3. Defina o nome do arquivo de saída (ex: `certificado.pem`).

### Passo 3: Executar o Coletor de Notas
Para iniciar o download:
```bash
python download_nfse.py
```
1. Informe o caminho do certificado `.pem` gerado no passo anterior (digite `.` para que o script liste os arquivos `.pem` da pasta atual).
2. Escolha o ambiente: `1` para Produção ou `2` para Homologação/Testes.
3. Informe a data inicial e data final do período desejado (Formato: `DD/MM/YYYY`).
4. Defina o **NSU Inicial** de busca. *Se for a primeira execução do CNPJ no sistema nacional, inicie com `1`. Para buscas futures, utilize o último NSU impresso pelo script ao final da execução anterior.*
5. Informe o nome da pasta de destino onde os arquivos serão salvos (padrão: `./notas_fiscais`).

### Passo 4: Converter XMLs Locais para PDF (Opcional)
Se você já possui os arquivos XML e deseja apenas gerar os PDFs (ou regenerá-los para atualizar as descrições dos serviços):
```bash
python xml_to_pdf.py [caminho_entrada] [opções]
```
Exemplos de uso:
- **Converter todos os XMLs pendentes** na pasta padrão (`./notas_fiscais`):
  ```bash
  python xml_to_pdf.py
  ```
- **Forçar a regeneração** de todos os PDFs (sobrescrevendo os existentes):
  ```bash
  python xml_to_pdf.py -f
  ```
- **Converter um único arquivo XML específico**:
  ```bash
  python xml_to_pdf.py ./notas_fiscais/NFSe_20260605_nsu_369.xml
  ```
- **Definir pasta de entrada e pasta de saída personalizadas**:
  ```bash
  python xml_to_pdf.py /caminho/origem -o /caminho/destino
  ```

---

## 📁 Estrutura dos Arquivos Salvos

Os arquivos serão baixados e organizados na pasta de destino configurada:
- **`NFSe_[DATA]_nsu_[NUMERO].xml`**: Arquivo XML original e completo da NFS-e.
- **`NFSe_[DATA]_nsu_[NUMERO].pdf`**: Documento auxiliar da nota (DANFSE) gerado localmente em PDF.
- **`coletor_nfse.log`**: Arquivo com o histórico detalhado da execução e logs de erros.
- **`sem_data/`**: Subpasta contendo XMLs de eventos e outras transações do repositório nacional que não são notas fiscais comuns (como cancelamentos e cartas de correção).

---

## ⚠️ Notas Importantes e Boas Práticas

### Controle de NSU
O NSU (Número Sequencial Único) é incremental por CNPJ dentro do banco de dados do governo. Sempre guarde o **último NSU processado** exibido pelo script no final da execução. Na próxima vez que for rodar o coletor, use esse número como ponto de partida para evitar reprocessar notas antigas, prevenindo bloqueios do servidor.

### Limite de Requisições (Erro 429) e Instabilidades
As APIs da Receita Federal implementam limites severos de requisições por minuto (**Rate Limiting**). 
- Caso o script receba um erro `429 (Too Many Requests)`, ele irá pausar a execução automaticamente por 10 segundos antes de tentar a próxima chamada. **Não interrompa o processo**, o script retomará sozinho.
- Quedas de conexão e timeouts curtos são normais devido à instabilidade frequente dos servidores governamentais. O script possui tratamento de exceções com tentativas automáticas a cada 5 segundos.

### Segurança (Git / GitHub)
O projeto já conta com um arquivo `.gitignore` configurado. **Nunca remova as regras de ignore**. Elas impedem que os arquivos confidenciais do seu certificado (`.pfx` ou `.pem`), as notas fiscais baixadas e os logs de execução sejam enviados para repositórios públicos.

---

## 📄 Licença

Este projeto está licenciado sob a licença MIT. Consulte o arquivo [LICENSE](LICENSE) para obter mais detalhes.
