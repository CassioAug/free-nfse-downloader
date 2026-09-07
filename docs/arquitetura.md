# Arquitetura e Funcionamento Técnico

Este documento descreve os detalhes internos de comunicação, segurança e persistência do **free-nfse-downloader**.

---

## 1. Visão Geral

O sistema consome a API do **Ambiente de Dados Nacional (ADN)** da NFS-e, mantida pela Receita Federal do Brasil e Serpro. 

O fluxo de coleta automatizada opera sem interfaces web ou preenchimento de captchas, realizando requisições HTTP seguras com autenticação mútua baseada em certificados digitais (e-CNPJ padrão ICP-Brasil).

---

## 2. Autenticação mTLS (Mutual TLS)

Para acessar os endpoints restritos do ADN, a aplicação realiza autenticação no handshake da camada de transporte (TLS):

- **Certificados A1 (`.pem`):** A chave privada e a cadeia de certificados são extraídas pelo `convert_pfx.py` e passadas como parâmetros de sessão HTTP no Python (`requests.Session(cert=(cert_path, key_path))`).
- **Certificados A3 (Token USB no Windows):** Como drivers de tokens criptográficos (SafeSign, Cryptolib) frequentemente utilizam algoritmos com restrições em OpenSSL nativo (ex.: RSASSA-PSS / TLS 1.3), o sistema utiliza uma ponte com o navegador Chromium via Playwright. A sessão TLS 1.2 é negociada diretamente com a CryptoAPI / Windows Certificate Store, solicitando o PIN uma única vez ao usuário e reutilizando as credenciais de sessão.

---

## 3. Algoritmo de Busca e Paginação por NSU

As notas fiscais na API do ADN são distribuídas em sequência linear através de um **NSU (Número Sequencial Único)**. Cada requisição retorna até 50 documentos em ordem crescente de NSU.

Para evitar varrer milhões de registros antigos e economizar tráfego:

```
[ Consulta de Data ]
         |
         v
[ Cache Exato (data -> NSU)? ] ──(Sim)──> Inicia download diretamente
         |
       (Não)
         v
[ Busca Binária no Índice Local (NSU <-> data) ]
         |
         v
[ Encontra NSU inicial mais próximo em ~7 requisições ]
         |
         v
[ Download em Lote (lotes de 50 notas) ]
```

1. **Cache Exato (`data -> NSU`):** Se a data inicial desejada já foi consultada em execuções anteriores, o NSU inicial é obtido instantaneamente com zero requisições.
2. **Índice NSU <-> Data:** O sistema mantém amostras regulares (de 100 em 100 NSUs). Através de busca binária no índice, descobre o NSU correspondente à data com aproximadamente 6 a 8 requisições.
3. **Extensão Automática:** Caso o período desejado seja mais recente do que o índice local, a aplicação consulta a ponta final da API e expande o índice progressivamente.
4. **Alimentação Contínua:** Cada novo lote de notas baixado salva seus marcos temporais no índice, tornando consultas futuras instantâneas.

---

## 4. Persistência de Dados e Cache Local

- **`cache_nsu/`**: Armazena os arquivos de mapeamento `{CNPJ}_{ambiente}_index.json` contendo o histórico de NSUs e datas verificadas.
- **`coletor_nfse.log`**: Registro rotativo detalhado das operações, requisições HTTP e eventuais alertas da API.
- **`notas_fiscais/{CNPJ}/`**: Diretório onde os arquivos são salvos:
  - `prestados/`: Notas em que a empresa é emitente.
  - `tomados/`: Notas em que a empresa é destinatária/tomadora.
  - `sem_data/`: Eventos adicionais (cancelamentos, cartas de correção).

---

## 5. Rate Limiting e Resiliência (HTTP 429)

A infraestrutura da Receita Federal implementa controles severos de taxa de requisições por minuto (**Rate Limiting**).

- Ao receber uma resposta com status `429 (Too Many Requests)`, o coletor entra em estado de espera com backoff exponencial (iniciando em 2 segundos e escalando progressivamente até 15 segundos).
- O download retoma automaticamente assim que o limite temporal do servidor é restabelecido, sem necessidade de intervenção do usuário ou perda do progresso já baixado.
