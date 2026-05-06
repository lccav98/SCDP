"""
Autenticação automática no Gov.br.
Preenche CPF e senha automaticamente; pausa para CAPTCHA e 2FA manual.
Salva e reutiliza cookies para evitar login repetido.
"""

import os
import json
import time
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

LOGGED_IN_NAME = os.getenv("SCDP_LOGGED_IN_NAME", "").strip()

log = logging.getLogger(__name__)

COOKIES_FILE = Path(__file__).parent.parent / "session_cookies.json"

GOVBR_CPF_SELECTOR  = "#accountId"
GOVBR_PASS_SELECTOR = "input[type=password]"
CAPTCHA_SELECTORS   = [
    ".captcha",
    "#captcha",
    "img[src*='captcha']",
    "text=Selecione a imagem",
    "text=Digite o código",
    ".wlc-captcha",
]
TWOFACTOR_SELECTORS = [
    "text=código de acesso",
    "text=Código de Acesso",
    "text=código enviado",
    "text=código pelo celular",
    "text=autenticação de dois fatores",
    "text=verificação em duas etapas",
    "input[id*='code']",
    "input[id*='codigo']",
    "input[placeholder*='código']",
    "input[placeholder*='código']",
]

SCDP_LOGGED_IN_INDICATORS = [
    "text=Aprovação",
    ".usuarioLogado",
    "#usuarioLogado",
    "a[href*='logout']",
    "a[href*='sair']",
]


def save_cookies(context, path: Path = COOKIES_FILE):
    """Salva cookies da sessão atual em arquivo JSON."""
    try:
        cookies = context.cookies()
        with open(path, "w") as f:
            json.dump(cookies, f, indent=2)
        log.info("Sessão salva: %d cookies em %s", len(cookies), path)
    except Exception as exc:
        log.warning("Falha ao salvar cookies: %s", exc)


def load_cookies(context, path: Path = COOKIES_FILE) -> bool:
    """Carrega cookies salvos no contexto. Retorna True se carregou."""
    if not path.exists():
        return False
    try:
        with open(path) as f:
            cookies = json.load(f)
        context.add_cookies(cookies)
        log.info("Sessão carregada: %d cookies de %s", len(cookies), path)
        return True
    except Exception as exc:
        log.warning("Falha ao carregar cookies: %s", exc)
        return False


def _has_twofactor(page) -> bool:
    for sel in TWOFACTOR_SELECTORS:
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            pass
    return False


def _wait_for_twofactor(page, timeout_seconds: int = 180):
    """Pausa para o usuário digitar o código de verificação 2FA."""
    print("\n" + "═" * 60)
    print("  CÓDIGO DE ACESSO NECESSÁRIO.")
    print("  Digite o código recebido por SMS/e-mail no navegador.")
    print("  O bot continuará automaticamente após a confirmação.")
    print("═" * 60)

    start = time.time()
    last_url = page.url
    while time.time() - start < timeout_seconds:
        time.sleep(2)
        if page.url != last_url:
            log.info("2FA concluído — URL mudou: %s", page.url)
            return
        if _is_logged_in(page):
            return
        if not _has_twofactor(page):
            time.sleep(2)
            return

    raise TimeoutError("Tempo esgotado aguardando código de acesso 2FA.")


def _has_captcha(page) -> bool:
    for sel in CAPTCHA_SELECTORS:
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            pass
    return False


def _is_logged_in(page) -> bool:
    try:
        url = page.url
        # Se está na tela de login gov.br, não está logado
        if "login" in url.lower() or "acesso.gov.br" in url or "home.xhtml" in url:
            return False
        # Qualquer página do SCDP que não seja tela de login = sessão ativa
        if "scdp.gov.br" in url and "home" not in url:
            return True
    except Exception:
        return False
    return False


def _wait_for_captcha_resolution(page, timeout_seconds: int = 120):
    """Aguarda o usuário resolver o CAPTCHA monitorando a URL."""
    print("\n" + "═" * 60)
    print("  CAPTCHA DETECTADO — resolva no navegador.")
    print("  O bot continuará automaticamente após a resolução.")
    print("═" * 60)

    start = time.time()
    last_url = page.url
    while time.time() - start < timeout_seconds:
        time.sleep(1)
        current_url = page.url
        # Saiu da tela de captcha (URL mudou ou campo de senha apareceu)
        if current_url != last_url:
            log.info("URL mudou após captcha: %s", current_url)
            return
        try:
            if page.locator(GOVBR_PASS_SELECTOR).is_visible():
                return
        except Exception:
            pass
        if not _has_captcha(page):
            time.sleep(3)  # aguarda página carregar após captcha sumir
            return

    raise TimeoutError("Tempo esgotado aguardando resolução do CAPTCHA.")


def login(page) -> bool:
    """
    Realiza login automático no Gov.br.
    Retorna True se login bem-sucedido, False caso contrário.
    """
    cpf   = os.getenv("SCDP_CPF", "").strip()
    senha = os.getenv("SCDP_SENHA", "").strip()

    if not cpf or not senha:
        raise ValueError(
            "SCDP_CPF e SCDP_SENHA não definidos no .env"
        )

    log.info("Iniciando login Gov.br...")

    # ── Etapa 1: CPF ─────────────────────────────────────────────────────────
    try:
        page.wait_for_selector(GOVBR_CPF_SELECTOR, timeout=10000)
        page.locator(GOVBR_CPF_SELECTOR).fill(cpf)
        time.sleep(0.5)
        log.info("CPF preenchido.")
    except Exception as exc:
        log.error("Campo CPF não encontrado: %s", exc)
        return False

    # ── Etapa 2: CAPTCHA antes de enviar CPF ─────────────────────────────────
    if _has_captcha(page):
        _wait_for_captcha_resolution(page)

    # ── Etapa 3: Submete CPF ──────────────────────────────────────────────────
    try:
        page.locator("button[type=submit]").first.click()
        time.sleep(2)
        log.info("CPF submetido.")
    except Exception as exc:
        log.error("Erro ao submeter CPF: %s", exc)
        return False

    # ── Etapa 4: CAPTCHA pós-CPF (Gov.br exibe antes da senha) ───────────────
    if _has_captcha(page):
        _wait_for_captcha_resolution(page)

    time.sleep(1)

    # ── Etapa 5: Senha ────────────────────────────────────────────────────────
    try:
        page.wait_for_selector(GOVBR_PASS_SELECTOR, timeout=30000)
        page.locator(GOVBR_PASS_SELECTOR).fill(senha)
        time.sleep(0.5)
        log.info("Senha preenchida.")
    except Exception as exc:
        log.error("Campo de senha não encontrado: %s", exc)
        return False

    # ── Etapa 6: CAPTCHA antes de submeter senha ──────────────────────────────
    if _has_captcha(page):
        _wait_for_captcha_resolution(page)

    # ── Etapa 7: Submete senha ────────────────────────────────────────────────
    try:
        page.locator("button[type=submit]").first.click()
        log.info("Senha submetida. Aguardando redirecionamento...")
        time.sleep(5)
    except Exception as exc:
        log.error("Erro ao submeter senha: %s", exc)
        return False

    # ── Etapa 8: 2FA / código de acesso ──────────────────────────────────────
    if _has_twofactor(page):
        _wait_for_twofactor(page)

    # ── Etapa 9: Verifica login ───────────────────────────────────────────────
    for _ in range(15):
        if _is_logged_in(page):
            log.info("✅ Login realizado com sucesso. URL: %s", page.url)
            return True
        if _has_captcha(page):
            _wait_for_captcha_resolution(page)
        if _has_twofactor(page):
            _wait_for_twofactor(page)
        time.sleep(2)

    log.warning("Não foi possível confirmar login. URL: %s", page.url)
    return False
