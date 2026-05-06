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

---

## Instalação

```bash
# 1. Clonar o repositório
git clone <url-do-repositorio>
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
TESSERACT_PATH=/opt/homebrew/bin/tesseract   # ajuste conforme seu sistema
```

Para encontrar o caminho do Tesseract:
```bash
which tesseract
```

---

## Como usar

### 1. Abrir o Chrome com depuração remota

**macOS** — use o script incluso:
```bash
bash start_chrome_cdp.sh
```

**Linux/Windows** — abra o Chrome manualmente:
```bash
google-chrome --remote-debugging-port=9222 --profile-directory="Default"
# ou
"C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222
```

### 2. Fazer login no SCDP

No Chrome que abriu, acesse o SCDP e faça login normalmente (CPF, senha, CAPTCHA, 2FA). Navegue até **Aprovação → Autoridade Superior**.

### 3. Rodar o bot

Com o ambiente virtual ativo:
```bash
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
