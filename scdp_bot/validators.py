from playwright.sync_api import sync_playwright
from .browser import random_delay, close_modal
from datetime import datetime, timedelta
import re

def run_all_validations(page, pcdp_data):
    inconsistencies = []
    financial_data = {}
    pcdp_number = pcdp_data.get("Número da PCDP", "N/A")
    
    # Regra 1: Prazo mínimo de solicitação
    val, inc = validate_request_deadline(page, pcdp_data)
    if inc:
        inconsistencies.append({
            "id": len(inconsistencies)+1,
            "tipo": "PRAZO_SOLICITACAO",
            "gravidade": "GRAVE",
            "descricao": val,
            "campo": "Data da Solicitação",
            "valor_encontrado": pcdp_data.get("Data da Solicitação"),
            "valor_esperado": ">= 15 dias antes da viagem",
            "fundamento_legal": "IN 66/2021-DAF, Manual SCDP",
            "pcdp_numero": pcdp_number
        })
    
    # Regra 2: Prestação de contas pendente
    inc = validate_pending_accounts(page)
    if inc:
        inconsistencies.append({
            "id": len(inconsistencies)+1,
            "tipo": "PC_PENDENTE",
            "gravidade": "CRÍTICA",
            "descricao": inc,
            "campo": "Alertas do Sistema",
            "valor_encontrado": "Alerta: prestações de contas pendentes",
            "fundamento_legal": "Portaria GM-MD 4.074/2024, art. 23",
            "pcdp_numero": pcdp_number
        })
    
    # Regra 5: Justificativas genéricas
    inc = validate_generic_justifications(page)
    if inc:
        inconsistencies.append({
            "id": len(inconsistencies)+1,
            "tipo": "JUSTIFICATIVA_GENERICA",
            "gravidade": "ATENÇÃO",
            "descricao": inc,
            "campo": "Justificativas",
            "valor_encontrado": inc,
            "fundamento_legal": "Lei 9.784/1999, art. 50",
            "pcdp_numero": pcdp_number
        })
    
    # Coletar dados financeiros
    financial_data = collect_financial_data(page)
    return inconsistencies, financial_data

def validate_request_deadline(page, pcdp_data):
    try:
        solic_date_str = pcdp_data.get("Data da Solicitação")
        period = pcdp_data.get("Período da Viagem")
        if not solic_date_str or not period:
            return None, None
        # Parse dates (assuming dd/mm/yyyy)
        solic_date = datetime.strptime(solic_date_str, "%d/%m/%Y")
        # Extract start date from period (e.g., "14/04/2026 a 15/04/2026")
        match = re.search(r"\d{2}/\d{2}/\d{4}", period)
        if not match:
            return None, None
        travel_start = datetime.strptime(match.group(), "%d/%m/%Y")
        delta = (travel_start - solic_date).days
        if delta < 15:
            return f"Solicitação com {delta} dias de antecedência (mínimo 15 dias)", delta
    except Exception:
        pass
    return None, None

def validate_pending_accounts(page):
    try:
        alert_box = page.locator("text=MENSAGENS INFORMATIVAS").locator("..")
        if alert_box.is_visible():
            alert_text = alert_box.inner_text()
            if "prestações de contas pendentes" in alert_text.lower():
                return "Proposto com prestação de contas pendente"
    except Exception:
        pass
    return None

def validate_generic_justifications(page):
    try:
        page.click("text=Justificativas: Clique aqui")
        random_delay()
        generic_terms = ["de acordo com o cronograma", "conforme programação", "conforme cronograma"]
        for term in generic_terms:
            if page.locator(f"text={term}").count() > 0:
                return f"Justificativa genérica encontrada: '{term}'"
        close_modal(page)
    except Exception:
        pass
    return None

def collect_financial_data(page):
    data = {}
    try:
        # Expandir seção QUADRO DE TOTALIZAÇÕES
        page.click("text=QUADRO DE TOTALIZAÇÕES")
        random_delay()
        data["subtotal_diarias"] = page.locator("text=Subtotal Diárias").locator("..").locator("td").last.inner_text()
        data["subtotal_passagens"] = page.locator("text=Subtotal Passagens").locator("..").locator("td").last.inner_text()
    except Exception:
        pass
    return data
