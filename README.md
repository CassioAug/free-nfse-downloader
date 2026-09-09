# Free NFS-e Downloader (v2.1.0)

[![CI](https://github.com/CassioAug/free-nfse-downloader/actions/workflows/ci.yml/badge.svg)](https://github.com/CassioAug/free-nfse-downloader/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/CassioAug/free-nfse-downloader?color=blue)](https://github.com/CassioAug/free-nfse-downloader/releases)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

O **Free NFS-e Downloader** é uma ferramenta gratuita e de código aberto para sincronização e download em lote de **Notas Fiscais de Serviços Eletrônicas (NFS-e)** de padrão nacional diretamente da Receita Federal (Ambiente de Dados Nacional - ADN).

Com ele, você baixa os arquivos **XML** e gera os **PDFs (DANFSE)** automaticamente, **sem digitar captchas e sem pagar mensalidades**.

---

## 🖥️ Interface do Aplicativo

![Interface Gráfica do Free NFS-e Downloader](docs/images/gui_preview.png)

---

## ✨ Principais Recursos

- **Interface Gráfica Intuitiva:** Faça tudo com poucos cliques, sem necessidade de digitar comandos no terminal.
- **Download em Lote com PDFs:** Baixa os arquivos XML oficiais e gera o relatório DANFSE em PDF de cada nota automaticamente.
- **Organização Inteligente:** Separa automaticamente as notas em pastas de **serviços prestados** e **serviços tomados**.
- **Busca por Período:** Basta informar a data inicial e final desejada (o sistema localiza as notas automaticamente).
- **Suporte a Certificados Digitais:** Compatível com certificados **A1 (arquivo .pfx)** e **A3 (token USB)**.
- **Ferramentas Inclusas:**
  - Conversor de certificado PFX/P12 para PEM.
  - Conversor manual de XMLs locais para PDF.
  - Reorganizador de notas já baixadas.
- **Privacidade e Segurança Total:** O programa roda **100% no seu computador**. Nenhum certificado, senha ou nota fiscal é enviado para servidores externos ou nuvem.

---

## 🚀 Como Usar (Passo a Passo Rápido)

### 1. Baixar o Aplicativo

Baixe a versão mais recente pronta para uso:
- Acesse a página de **[Releases](https://github.com/CassioAug/free-nfse-downloader/releases)** e baixe o arquivo `.zip` da versão mais recente, descompactando-o em uma pasta no seu computador.
- *(Ou, se for desenvolvedor, use `git clone https://github.com/CassioAug/free-nfse-downloader.git`)*

---

### 2. Instalação Automática

Abra a pasta do projeto e execute o instalador correspondente ao seu sistema operacional:

- **No Windows:** Dê dois cliques em **`instalar_dependencias.bat`**.
- **No Linux:** Abra o terminal na pasta e execute **`./instalar_dependencias.sh`**.

> O instalador criará um ambiente isolado (`.venv`) e baixará automaticamente todos os componentes necessários, sem alterar as configurações do seu computador.

---

### 3. Abrir e Utilizar

Para iniciar a tela do programa:
- **No Windows:** Dê dois cliques em **`iniciar_gui.bat`**.
- **No Linux:** Execute **`./iniciar_gui.sh`**.

#### Baixando suas notas fiscais:
1. **Se você tem certificado A1 (`.pfx`):**
   - Caso ainda não tenha o arquivo `.pem`, vá na aba **Converter PFX/P12**, selecione o arquivo do seu certificado, digite a senha e clique em converter.
   - Na aba **Download NFS-e**, selecione a opção **Arquivo PEM (A1)**.
2. **Se você tem certificado A3 (Token USB no Windows):**
   - Conecte seu token na porta USB e selecione a opção **Token USB (A3)**.
3. **Informe o período:**
   - Digite a **Data Inicial** (ex: `01/01/2026`) e a **Data Final** (deixe vazio se quiser baixar até hoje).
4. Clique em **Iniciar Download** e acompanhe o progresso na caixa de mensagens!

---

## 📁 Onde Ficam Salvas as Notas?

As notas fiscais baixadas são salvas automaticamente dentro da pasta do projeto em:

```
notas_fiscais/
└── SEU_CNPJ/
    ├── prestados/   <-- Notas emitidas pela sua empresa (XML e PDF)
    ├── tomados/     <-- Notas recebidas de fornecedores (XML e PDF)
    └── sem_data/    <-- Eventos auxiliares (cancelamentos, etc.)
```

---

## 📋 Pré-requisitos Básicos

- **Python 3.8 ou superior** instalado no computador ([Baixar Python](https://www.python.org/downloads/)).
  *(No Windows, marque a opção "Add Python to PATH" durante a instalação)*.
- **No Linux:** Caso seu sistema não tenha o Tkinter instalado, utilize:
  - *Ubuntu / Debian / Mint:* `sudo apt install python3-tk python3-venv`
  - *Arch Linux / CachyOS:* `sudo pacman -S tk`
  - *Fedora:* `sudo dnf install python3-tkinter`
- **Certificado Digital e-CNPJ** da empresa (A1 em arquivo ou A3 em token).

---

## 📚 Documentação Técnica (Para Desenvolvedores)

Se você deseja automatizar processos via terminal, agendar rotinas de download ou entender a arquitetura da API governamental:

- **[Uso via Linha de Comando (CLI)](docs/cli.md):** Comandos, argumentos e exemplos de execução via terminal.
- **[Arquitetura e Funcionamento Técnico](docs/arquitetura.md):** Detalhes sobre mTLS, paginação de NSU, cache e tratamento de limites de requisições (Rate Limiting).

---

## ⚖️ Licença

Este projeto é um software livre distribuído sob a licença **GNU General Public License v3.0**. Consulte o arquivo [LICENSE](LICENSE) para mais informações.
