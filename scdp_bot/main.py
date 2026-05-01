from playwright.sync_api import sync_playwright
from .browser import init_browser, navigate_to_scdp, random_delay, close_modal
from .db import init_db, Session, PCDPAnalysis
from .validators import run_all_validations
from .auth import login, save_cookies, load_cookies, _is_logged_in
import json
import time
import random
from datetime import datetime

def detect_captcha(page):
    """Detecta presença de CAPTCHA na página"""
    captcha_indicators = [
        "text=CAPTCHA",
        "text=Digite o código",
        "text=Verificação de segurança",
        "iframe[src*='captcha']",
        "img[alt*='captcha']",
        "#captcha",
        ".g-recaptcha"
    ]
    for indicator in captcha_indicators:
        try:
            if page.locator(indicator).count() > 0:
                return True
        except Exception:
            pass
    return False

def human_like_mouse_move(page):
    """Move o mouse de forma humanizada"""
    try:
        # Move para posições aleatórias na página
        for _ in range(2):
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            page.mouse.move(x, y)
            time.sleep(random.uniform(0.3, 0.8))
    except Exception:
        pass

def main():
    init_db()
    playwright, browser, context, page, connection_type = init_browser()
    
    try:
        if connection_type != "cdp":
            navigate_to_scdp(page)
            
        human_like_mouse_move(page)
        
        # Verifica login baseado no tipo de conexão
        if connection_type == "cdp":
            print("Conectado ao Chrome via CDP. Assumindo que está logado e na página certa.")
        else:
            if _is_logged_in(page):
                print("✅ Sessão reutilizada ou já logado.")
            else:
                print("\n" + "="*80)
                print("Aguardando você fazer o login manualmente.")
                print("Faça o login com CPF e Senha, resolva o CAPTCHA e 2FA se necessário.")
                print("Quando chegar na tela principal do SCDP, o bot assumirá o controle automaticamente.")
                print("="*80 + "\n")
                
                # Espera até 5 minutos para o usuário logar
                page.wait_for_selector("a:has-text('APROVAÇÃO'), a:has-text('Aprovação'), a:has-text('aprovação'), .usuarioLogado", timeout=300000)
                print("✅ Login detectado! Iniciando automação...")
                
                # Opcional: tentar salvar cookies para não precisar logar de novo
                try:
                    save_cookies(context)
                except Exception:
                    pass
        
        # Navegação com comportamento humano
        human_like_mouse_move(page)
        # O menu pode estar em maiúsculas (APROVAÇÃO) — usa seletor case-insensitive
        page.locator("a:has-text('APROVAÇÃO'), a:has-text('Aprovação'), a:has-text('aprovação')").first.click()
        random_delay()
        human_like_mouse_move(page)
        page.locator("a:has-text('Autoridade Superior')").first.click()
        random_delay()
        
        # Verifica CAPTCHA após navegação
        if detect_captcha(page):
            print("CAPTCHA DETECTADO após navegação! Resolva manualmente e aperte Enter...")
            input()
        
        # Capturar lista de PCDPs pendentes
        pcdp_links = page.locator("table tbody tr td a[href*='aprovar_viagem_edit.xhtml']").all()
        print(f"Encontradas {len(pcdp_links)} PCDPs pendentes")
        
        for link in pcdp_links:
            # Verifica CAPTCHA antes de cada ação
            if detect_captcha(page):
                print("CAPTCHA DETECTADO! Resolva e aperte Enter...")
                input()
            
            pcdp_number = link.inner_text()
            print(f"Analisando PCDP {pcdp_number}")
            human_like_mouse_move(page)
            link.click()
            random_delay()
            
            # Coletar dados base
            pcdp_data = collect_pcdp_data(page)
            # Executar validações
            inconsistencies, financial_data = run_all_validations(page, pcdp_data)
            # Gerar relatório
            report = generate_report(pcdp_data, inconsistencies, financial_data)
            # Salvar no banco
            save_analysis(report)
            print(f"PCDP {pcdp_number} analisada. Status: {report['status']}")
            
            # Voltar para lista com comportamento humano
            human_like_mouse_move(page)
            page.go_back()
            random_delay()
        
    finally:
        # Limpeza baseada no tipo de conexão
        if connection_type == "cdp":
            # Não fechamos o browser se conectado via CDP (usuário pode estar usando)
            print("Desconectando do Chrome (não fechando o navegador)...")
            browser.close()
        elif connection_type == "persistent":
            context.close()
        else:  # clean
            browser.close()
        playwright.stop()

def collect_pcdp_data(page):
    data = {}
    # Extrair campos da seção INFORMAÇÕES DA VIAGEM
    fields = [
        "Solicitado por", "Data da Solicitação", "Número da PCDP",
        "Nome do Proposto", "Período da Viagem", "Motivo da Viagem",
        "Descrição do Motivo da Viagem"
    ]
    for field in fields:
        try:
            locator = page.locator(f"text={field}").locator("..").locator("span, td").last
            data[field] = locator.inner_text().strip()
        except Exception:
            data[field] = None
    return data

def generate_report(pcdp_data, inconsistencies, financial_data):
    report = {
        "pcdp_numero": pcdp_data.get("Número da PCDP"),
        "proposto": pcdp_data.get("Nome do Proposto"),
        "data_analise": datetime.now().strftime("%Y-%m-%d"),
        "status": "DEVOLVER" if any(i["gravidade"] in ["CRÍTICA", "GRAVE"] for i in inconsistencies) else "APROVAR",
        "inconsistencias": inconsistencies,
        "dados_financeiros": financial_data,
        "texto_devolucao": generate_devolution_text(inconsistencies)
    }
    return report

def generate_devolution_text(inconsistencies):
    if not inconsistencies:
        return ""
    text = f"JUSTIFICATIVA DE DEVOLUÇÃO — PCDP nº {inconsistencies[0].get('pcdp_numero', '')}\n\n"
    for i in inconsistencies:
        text += f"{i['id']}. {i['descricao']} (Gravidade: {i['gravidade']})\n"
        text += f"Fundamento: {i['fundamento_legal']}\n\n"
    text += "Solicito a correção das inconsistências apontadas para nova análise."
    return text

def save_analysis(report):
    session = Session()
    analysis = PCDPAnalysis(
        pcdp_number=report["pcdp_numero"],
        proposto=report["proposto"],
        status=report["status"],
        inconsistencies=json.dumps(report["inconsistencias"]),
        financial_data=json.dumps(report["dados_financeiros"]),
        report_json=json.dumps(report)
    )
    session.add(analysis)
    session.commit()
    session.close()

if __name__ == "__main__":
    main()
