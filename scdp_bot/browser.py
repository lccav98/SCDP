from playwright.sync_api import sync_playwright
import random
import time
import os
from .config import SCDP_URL, DELAY_MIN, DELAY_MAX

CDP_PORTS = [int(os.getenv("CDP_PORT", "9222")), 9223, 9224]


def init_browser():
    playwright = sync_playwright().start()

    for port in CDP_PORTS:
        try:
            browser = playwright.chromium.connect_over_cdp(f"http://localhost:{port}")
            # Procura página que não seja home.xhtml (já logada)
            for ctx in browser.contexts:
                for pg in ctx.pages:
                    if "home.xhtml" not in pg.url and "pages/" in pg.url:
                        print(f"✅ Conectado ao Chrome existente via CDP (porta {port}).")
                        return playwright, browser, ctx, pg, "cdp"
                # Se nenhuma for pages/, usa a primeira que não for home
                for pg in ctx.pages:
                    if "home.xhtml" not in pg.url:
                        print(f"✅ Conectado ao Chrome existente via CDP (porta {port}).")
                        return playwright, browser, ctx, pg, "cdp"
            # Se todas forem home, usa a primeira
            if browser.contexts:
                context = browser.contexts[0]
                page = context.pages[0] if context.pages else context.new_page()
                page.bring_to_front()
                print(f"✅ Conectado ao Chrome existente via CDP (porta {port}).")
                return playwright, browser, context, page, "cdp"
        except Exception:
            continue

    # Modo 2: abrir Chrome com perfil persistente (bot_profile)
    print("Iniciando Chrome com perfil persistente local...")
    user_data_dir = os.path.join(os.getcwd(), "chrome_bot_profile")
    try:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
            ignore_default_args=["--enable-automation"],
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.bring_to_front()
        return playwright, None, context, page, "persistent"
    except Exception as e:
        print(f"Erro ao iniciar o Chrome: {e}")
        playwright.stop()
        exit(1)


def navigate_to_scdp(page):
    page.goto(SCDP_URL, timeout=30000)
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


def random_delay():
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))


def close_modal(page):
    # Restringe o clique de "Fechar" a elementos DENTRO de diálogos PrimeFaces.
    # Usar o seletor global 'button:has-text(Fechar)' pode clicar em botões de
    # fechamento de página inteira (window.close()), encerrando a aba.
    MODAL_CLOSE_SELS = [
        ".ui-dialog button:has-text('Fechar')",
        ".ui-dialog-buttonpane button:has-text('Fechar')",
        ".modal button:has-text('Fechar')",
        ".ui-dialog .ui-dialog-titlebar-close",
    ]
    try:
        for sel in MODAL_CLOSE_SELS:
            btn = page.locator(sel).first
            if btn.is_visible(timeout=300):
                btn.click()
                random_delay()
                return
    except Exception:
        pass
