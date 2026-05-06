# SCDP Bot — Auditoria Automática de PCDPs

Bot para análise automatizada de Processos de Concessão de Diárias e Passagens (PCDPs) no sistema SCDP, com geração de relatórios PDF e painel web.

---

## Pré-requisitos

- Python 3.9+
- Google Chrome instalado
- [Tesseract OCR](https://tesseract-ocr.github.io/tessdoc/Installation.html) com suporte a português

### macOS
```bash
brew install tesseract tesseract-lang
```

### Linux (Ubuntu/Debian)
```bash
sudo apt install tesseract-ocr tesseract-ocr-por
```

### Windows 11
1. Instalar [Python 3.9+](https://python.org/downloads) — marcar **"Add to PATH"**
2. Instalar [Git](https://git-scm.com)
3. Instalar [Tesseract OCR para Windows](https://github.com/UB-Mannheim/tesseract/wiki) — durante a instalação marcar **"Additional language data → Portuguese"**
4. Anotar o caminho de instalação (ex: `C:\Program Files\Tesseract-OCR\tesseract.exe`)

---

## Instalação

```bash
# 1. Clonar o repositório
git clone https://github.com/lccav98/SCDP.git
cd SCDP

# 2. Criar e ativar ambiente virtual
python3 -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Instalar o Playwright e o Chromium
playwright install chromium
```

---

## Configuração

Crie um arquivo `.env` na raiz do projeto (opcional — os valores padrão já funcionam):

```env
SCDP_URL=https://www2.scdp.gov.br/novoscdp/
HEADLESS=false
DELAY_MIN=0.3
DELAY_MAX=0.8

# Ajuste conforme seu sistema:
# macOS:   TESSERACT_PATH=/opt/homebrew/bin/tesseract
# Linux:   TESSERACT_PATH=/usr/bin/tesseract
# Windows: TESSERACT_PATH=C:\Program Files\Tesseract-OCR\tesseract.exe
TESSERACT_PATH=/opt/homebrew/bin/tesseract
```

Para encontrar o caminho do Tesseract:
```bash
which tesseract          # macOS / Linux
where tesseract          # Windows
```

---

## Como usar

### 1. Abrir o Chrome com depuração remota

**macOS** — use o script incluso:
```bash
bash start_chrome_cdp.sh
```

**Windows** — use o script PowerShell incluso (executar como Administrador se necessário):
```powershell
.\start_chrome_cdp.ps1
```

**Linux** — abra o Chrome manualmente:
```bash
google-chrome --remote-debugging-port=9222 --profile-directory="Default"
```

### 2. Fazer login no SCDP

No Chrome que abriu, acesse o SCDP e faça login normalmente (CPF, senha, CAPTCHA, 2FA). Navegue até **Aprovação → Autoridade Superior**.

### 3. Rodar o bot

Com o ambiente virtual ativo:
```bash
# macOS / Linux
python -m scdp_bot

# Windows (PowerShell)
venv\Scripts\activate
python -m scdp_bot
```

O bot vai:
- Detectar a sessão aberta no Chrome
- Percorrer todos os PCDPs pendentes de aprovação
- Ler os documentos anexados (OCR)
- Gerar relatórios PDF em `relatorios/`
- Salvar os resultados no banco de dados local (`scdp_bot.db`)

### 4. Acessar o painel web

Em outro terminal:
```bash
# macOS / Linux
python run_dashboard.py 8080

# Windows (PowerShell)
venv\Scripts\activate
python run_dashboard.py 8080
```

Acesse **http://localhost:8080** para visualizar os processos analisados com filtros por status e gravidade.

---

## Estrutura do projeto

```
SCDP/
├── scdp_bot/
│   ├── main.py          # loop principal de análise
│   ├── validators.py    # regras de validação (prazo, PC pendente, etc.)
│   ├── ocr_engine.py    # leitura de documentos anexados via OCR
│   ├── auth.py          # detecção de sessão e cookies
│   ├── browser.py       # conexão com o Chrome via CDP
│   ├── dashboard.py     # servidor Flask do painel
│   ├── db.py            # modelos e banco de dados SQLite
│   ├── report_pdf.py    # geração de relatórios PDF
│   ├── config.py        # configurações via .env
│   └── templates/       # templates HTML do painel
├── run_dashboard.py     # script para iniciar o painel
├── start_chrome_cdp.sh  # script macOS para abrir o Chrome com CDP
├── requirements.txt
└── README.md
```

---

## Observações

- O bot nunca aprova nem rejeita PCDPs — apenas lê e analisa.
- Os relatórios PDF ficam na pasta `relatorios/` (não versionada).
- O banco de dados `scdp_bot.db` é local e não é versionado.
- PCDPs já analisados são pulados automaticamente em novas execuções.
- Se a internet cair, basta rodar `python -m scdp_bot` novamente — ele retoma de onde parou.
