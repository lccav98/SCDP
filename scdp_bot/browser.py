from playwright.sync_api import sync_playwright
import random
import time
import os
from .config import SCDP_URL, HEADLESS, DELAY_MIN, DELAY_MAX

def init_browser():
    playwright = sync_playwright().start()
    
    print("Iniciando Chrome com perfil persistente local...")
    user_data_dir = os.path.join(os.getcwd(), "chrome_bot_profile")
    
    try:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            channel="chrome",  # Usa o Chrome real do Mac, não o Chromium (evita o crash SIGTRAP)
            headless=False,
            args=[
                '--disable-infobars',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ],
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.bring_to_front()
        # Força o Mac a trazer o Chrome para o primeiro plano
        os.system('open -a "Google Chrome"')
        return playwright, context.browser, context, page, "persistent"
    except Exception as e:
        print("Erro ao iniciar o Chrome:", str(e))
        playwright.stop()
        exit(1)

def navigate_to_scdp(page):
    page.goto(SCDP_URL, timeout=30000)
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

def random_delay():
    time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))

def close_modal(page):
    try:
        close_btn = page.locator("button:has-text('Fechar')").first
        if close_btn.is_visible():
            close_btn.click()
            random_delay()
    except Exception:
        pass