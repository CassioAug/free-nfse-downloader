# free-nfse-downloader

Este é um projeto em Python para automação, sincronização e download de **Notas Fiscais de Serviços Eletrônicas (NFS-e)** de padrão nacional diretamente da API do **Ambiente de Dados Nacional (ADN)**.

O sistema utiliza autenticação mútua via **mTLS** com o certificado digital da empresa (e-CNPJ), permitindo realizar downloads em lote de arquivos **XML** e gerar a **DANFSE (PDF)** de forma totalmente automatizada, **sem a necessidade de digitar captchas**.

---

## 🚀 Como Funciona o Sistema

O processo é composto por dois passos simples:

```
[Certificado .pfx/.p12] ➔ convert_pfx.py ➔ [Certificado .pem]
                                                  │
                                                  ▼
[Período / NSU Inicial] ➔ download_nfse.py ➔ [Downloads de XML e DANFSE PDF]
```

1. **Conversão do Certificado:** O script `convert_pfx.py` extrai a chave privada (desprotegida) e a cadeia de certificados do arquivo original da sua empresa (`.pfx` ou `.p12`) e gera um arquivo consolidado em `.pem` exigido pela biblioteca HTTP do Python.
2. **Download das Notas:** O script `download_nfse.py` consome a API do governo utilizando o arquivo `.pem` para autenticação de rede (mTLS). As notas são baixadas em lotes sequenciais de até 50 documentos controlados por **NSU (Número Sequencial Único)**, filtradas pelo período escolhido e salvas localmente.

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

### Passo 1: Preparar o ambiente
Clone ou baixe o código para sua máquina local.

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
4. Defina o **NSU Inicial** de busca. *Se for a primeira execução do CNPJ no sistema nacional, inicie com `1`. Para buscas futuras, utilize o último NSU impresso pelo script ao final da execução anterior.*
5. Informe o nome da pasta de destino onde os arquivos serão salvos (padrão: `./notas_fiscais`).

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
