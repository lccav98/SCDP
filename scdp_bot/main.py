import json
import os
import random
import time
from datetime import datetime
from pathlib import Path

from .auth import _is_logged_in, load_cookies, save_cookies
from .browser import init_browser, navigate_to_scdp, random_delay
from .db import PCDPAnalysis, Session, init_db
from .report_pdf import generate_pdf_report
from .validators import run_all_validations

RELATORIOS_DIR = Path(__file__).parent.parent / "relatorios"
RELATORIOS_DIR.mkdir(exist_ok=True)

SCDP_BASE_URL = "https://www2.scdp.gov.br"

_RECOMENDACOES_MAP = {
    "PRAZO_SOLICITACAO":    "Apresentar justificativa circunstanciada para a urgência da viagem.",
    "PC_PENDENTE":          "Esclarecer e regularizar as prestações de contas pendentes do proposto.",
    "JUSTIFICATIVA_GENERICA": "Substituir as justificativas genéricas por motivações objetivas e circunstanciadas.",
    "DIVERGENCIA_ANEXO_OCR":  "Disponibilizar os documentos anexos para verificação.",
}


def detect_captcha(page):
    for sel in ["text=CAPTCHA", "text=Digite o código", "text=Verificação de segurança",
                "iframe[src*='captcha']", "img[alt*='captcha']", "#captcha", ".g-recaptcha"]:
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            pass
    return False


def human_like_mouse_move(page):
    try:
        for _ in range(2):
            page.mouse.move(random.randrange(100, 800), random.randrange(100, 600))
            time.sleep(random.uniform(0.3, 0.8))
    except Exception:
        pass


def _poll_until_logged_in(page, timeout_minutes=10):
    deadline = time.time() + timeout_minutes * 60
    while time.time() < deadline:
        try:
            if _is_logged_in(page):
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def _wait_captcha(page):
    if detect_captcha(page):
        print("\n⚠️  CAPTCHA detectado! Resolva no navegador e pressione Enter aqui...")
        input()


def _get_current_list_page(page) -> int:
    """Retorna o número da página ativa no paginador PrimeFaces, ou 1 se não detectado."""
    try:
        result = page.evaluate("""() => {
            const active = document.querySelector(
                '.ui-paginator .ui-state-active, '
                + '.ui-paginator-page.ui-state-active'
            );
            if (active) {
                const n = parseInt(active.textContent.trim());
                return isNaN(n) ? 1 : n;
            }
            return 1;
        }""")
        return int(result) if result else 1
    except Exception:
        return 1


def _navigate_to_list_page(page, target_page: int, pesquisar_sels: list) -> bool:
    """Usa PESQUISAR na página atual (edit ou list) para carregar a lista.
    Tenta via seletores Playwright e, como fallback, via JavaScript direto
    (ignora visibilidade — o botão pode estar coberto por um painel aberto).
    Retorna True se os resultados carregaram com sucesso."""
    if page.locator("[id*='otNumeroPcdp']").count() == 0:
        clicou = False

        # Tentativa 1: seletores Playwright com timeout generoso
        for sel in pesquisar_sels:
            try:
                btn = page.locator(sel).first
                if btn.is_visible(timeout=5_000):
                    btn.click()
                    clicou = True
                    break
            except Exception:
                continue

        # Tentativa 2: JavaScript direto (ignora visibilidade)
        if not clicou:
            try:
                clicou = page.evaluate("""() => {
                    var sels = [
                        'button[id*="pesquisar"]', 'input[value="PESQUISAR"]',
                        'input[value="Pesquisar"]', 'button:has-text("PESQUISAR")',
                        'input[type="submit"]'
                    ];
                    for (var sel of sels) {
                        try {
                            var btn = document.querySelector(sel);
                            if (btn) { btn.click(); return true; }
                        } catch(e) {}
                    }
                    return false;
                }""")
            except Exception:
                pass

        if clicou:
            try:
                page.wait_for_selector("[id*='otNumeroPcdp']", timeout=20_000)
            except Exception:
                page.wait_for_load_state("networkidle", timeout=15_000)

    if page.locator("[id*='otNumeroPcdp']").count() == 0:
        return False

    for _ in range(target_page - 1):
        advanced = page.evaluate("""() => {
            const nxt = document.querySelector(
                '.ui-paginator-next:not(.ui-state-disabled), '
                + '[aria-label="Next Page"]:not([aria-disabled="true"])'
            );
            if (nxt) { nxt.click(); return true; }
            return false;
        }""")
        if not advanced:
            break
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass

    return page.locator("[id*='otNumeroPcdp']").count() > 0


def main():
    init_db()
    playwright, browser, context, page, connection_type = init_browser()
    pcdp_count = 0

    try:
        # ── SELECIONA A MELHOR PÁGINA ABERTA ──────────────────────────────────
        # Se houver múltiplas abas SCDP, prefere a que já tem o menu de aprovação
        if context:
            for pg in context.pages:
                if ("scdp.gov.br" in pg.url and
                        pg.locator("text=Aprovação").count() > 0):
                    page = pg
                    page.bring_to_front()
                    break

        # ── LOGIN ─────────────────────────────────────────────────────────────
        # Navega ao SCDP se não estiver em nenhuma página do sistema
        on_scdp = SCDP_BASE_URL.replace("https://", "").split("/")[0] in page.url
        if not on_scdp:
            navigate_to_scdp(page)

        human_like_mouse_move(page)

        if connection_type == "cdp":
            print("Conectado ao Chrome via CDP.")

        # Tenta restaurar sessão via cookies salvos
        if not _is_logged_in(page):
            if load_cookies(context):
                navigate_to_scdp(page)

        if _is_logged_in(page):
            print("Sessão ativa — já logado.")
        else:
            print("\n" + "=" * 70)
            print("  CHROME ABERTO — use ESSA janela para fazer login.")
            print("  Faça login com CPF, senha, CAPTCHA e 2FA se necessário.")
            print("  Aguardando (até 10 min)...")
            print("=" * 70 + "\n")
            if not _poll_until_logged_in(page, timeout_minutes=10):
                print("Tempo esgotado aguardando login.")
                return
            print("✅ Login detectado!")
            try:
                save_cookies(context)
            except Exception:
                pass

        # ── NAVEGAR ATÉ A FILA DE APROVAÇÃO ──────────────────────────────────
        already_on_list = "aprovar_viagem_list" in page.url

        if not already_on_list:
            print("\nNavegando para Aprovação → Autoridade Superior...")
            # Tenta menu JS primeiro
            navigated = False
            try:
                navigated = page.evaluate("""() => {
                    const el = document.getElementById('formMenu:aprovacaoAutoridadeSuperior');
                    if (el) { el.click(); return true; }
                    const a = document.querySelector('a[href*="aprovar_viagem_list"]');
                    if (a) { a.click(); return true; }
                    return false;
                }""")
                if navigated:
                    # Aguarda a lista aparecer em vez de networkidle (que pode nunca chegar)
                    try:
                        page.wait_for_selector(
                            "input[value='PESQUISAR'], [id*='otNumeroPcdp']",
                            timeout=15_000
                        )
                    except Exception:
                        pass
            except Exception:
                pass
            # Fallback: navegação direta via URL
            if not navigated or "aprovar_viagem_list" not in page.url:
                try:
                    page.goto(
                        SCDP_BASE_URL + "/novoscdp/pages/aprovar/autoridade_superior/aprovar_viagem_list.xhtml",
                        timeout=20_000, wait_until="load"
                    )
                except Exception:
                    pass
            _wait_captcha(page)
        else:
            print("\n✅ Já na página de listagem — iniciando análise diretamente.")

        # ── PESQUISAR: tenta múltiplos seletores + fallback JS ───────────────
        pesquisar_sels = [
            "input[value='PESQUISAR']",
            "input[value='Pesquisar']",
            "button:has-text('PESQUISAR')",
            "input[type='submit']",
            "button[type='submit']",
        ]
        if page.locator("[id*='otNumeroPcdp']").count() == 0:
            _navigate_to_list_page(page, 1, pesquisar_sels)
        _wait_captcha(page)

        # Salva URL da lista para navegação direta após cada PCDP
        list_url = page.url

        # ── LOOP PRINCIPAL: página por página, span por span ─────────────────
        list_page = 1
        global_idx = 0

        while True:
            n_spans = page.locator("[id*='otNumeroPcdp']").count()
            if not n_spans:
                try:
                    print(f"Página {list_page}: sem PCDPs visíveis (URL: {page.url[-80:]}). Encerrando.")
                except Exception:
                    print(f"Página {list_page}: sem PCDPs visíveis. Encerrando.")
                break
            print(f"\nPágina {list_page}: {n_spans} PCDP(s)")

            for span_idx in range(n_spans):
                global_idx += 1
                try:
                    _wait_captcha(page)

                    span = page.locator("[id*='otNumeroPcdp']").nth(span_idx)
                    pcdp_label = span.inner_text().strip()

                    # Pula PCDPs já analisados (qualquer sessão anterior)
                    _db = Session()
                    _existing = (_db.query(PCDPAnalysis)
                                 .filter(PCDPAnalysis.pcdp_number == pcdp_label)
                                 .first())
                    _db.close()
                    if _existing:
                        print(f"[{global_idx}] PCDP {pcdp_label} — já analisado, pulando.")
                        continue

                    print(f"[{global_idx}] PCDP {pcdp_label}...")

                    span.click()
                    page.wait_for_load_state("networkidle", timeout=20_000)

                    pcdp_data = collect_pcdp_data(page)
                    print(f"      {pcdp_data.get('Nome do Proposto', '?')}")

                    inconsistencies, financial_data = run_all_validations(page, pcdp_data)
                    report = generate_report(pcdp_data, inconsistencies, financial_data)

                    try:
                        pdf_path = generate_pdf_report(report, str(RELATORIOS_DIR))
                        print(f"      PDF: {os.path.basename(pdf_path)}")
                    except Exception as e:
                        print(f"      PDF falhou: {e}")

                    save_analysis(report)
                    icon = "✅" if report["status"] == "APROVAR" else "⚠️ "
                    print(f"      {icon} {report['status']} — "
                          f"{len(inconsistencies)} inconsistência(s)\n")
                    pcdp_count += 1

                    # Retorna à lista via goto direto (mais confiável que go_back em JSF)
                    try:
                        page.goto(list_url, timeout=20_000, wait_until="load")
                    except Exception:
                        pass

                    try:
                        on_list = page.locator("[id*='otNumeroPcdp']").count() > 0
                    except Exception:
                        on_list = False

                    if not on_list:
                        try:
                            if not _navigate_to_list_page(page, list_page, pesquisar_sels):
                                print(f"      Aviso: lista irrecuperável na pág. {list_page}.")
                                break
                        except Exception as _e:
                            print(f"      Erro ao restaurar lista: {_e}")
                            break

                    try:
                        if list_page > 1 and _get_current_list_page(page) != list_page:
                            _navigate_to_list_page(page, list_page, pesquisar_sels)
                    except Exception:
                        pass

                    random_delay()

                except Exception as e:
                    print(f"      Erro: {e}\n")
                    try:
                        on_list = page.locator("[id*='otNumeroPcdp']").count() > 0
                    except Exception:
                        on_list = False
                    if not on_list:
                        try:
                            if not _navigate_to_list_page(page, list_page, pesquisar_sels):
                                print(f"      Aviso: lista irrecuperável na pág. {list_page}. Abortando página.")
                                break
                        except Exception:
                            print(f"      Aviso: lista irrecuperável na pág. {list_page}. Abortando página.")
                            break

            # Garante que a lista está visível antes de tentar avançar página
            if page.locator("[id*='otNumeroPcdp']").count() == 0:
                try:
                    page.goto(list_url, timeout=20_000, wait_until="load")
                except Exception:
                    pass
                if page.locator("[id*='otNumeroPcdp']").count() == 0:
                    _navigate_to_list_page(page, list_page, pesquisar_sels)
                # Reposiciona no paginador na página atual
                for _ in range(list_page - 1):
                    ok = page.evaluate("""() => {
                        const nxt = document.querySelector(
                            '.ui-paginator-next:not(.ui-state-disabled), '
                            + '[aria-label="Next Page"]:not([aria-disabled="true"])'
                        );
                        if (nxt) { nxt.click(); return true; }
                        return false;
                    }""")
                    if not ok:
                        break
                    try:
                        page.wait_for_load_state("networkidle", timeout=10_000)
                    except Exception:
                        pass

            # Avança para a próxima página via paginador
            try:
                has_next = page.evaluate("""() => {
                    const nxt = document.querySelector(
                        '.ui-paginator-next:not(.ui-state-disabled), '
                        + '[aria-label="Next Page"]:not([aria-disabled="true"])'
                    );
                    if (nxt) { nxt.click(); return true; }
                    return false;
                }""")
                if has_next:
                    page.wait_for_load_state("networkidle", timeout=15_000)
                    new_page = _get_current_list_page(page)
                    if new_page > list_page:
                        list_page = new_page
                    else:
                        list_page += 1
                else:
                    break
            except Exception as _e:
                print(f"Erro ao avançar paginador: {_e}")
                break

        print(f"{'='*60}")
        print(f"  Análise concluída: {pcdp_count} PCDP(s) processada(s)")
        print(f"  Relatórios em: {RELATORIOS_DIR}")
        print(f"  Painel:        http://localhost:8080")
        print(f"{'='*60}\n")

    except Exception as e:
        print(f"Erro geral: {e}")
    finally:
        try:
            context.close()
        except Exception:
            pass
        playwright.stop()


def collect_pcdp_data(page):
    fields = [
        "Solicitado por", "Data da Solicitação", "Número da PCDP",
        "Nome do Proposto", "Tipo de Proposto", "Período da Viagem",
        "Motivo da Viagem", "Descrição do Motivo da Viagem",
        "Órgão Solicitante", "Status no Fluxo",
    ]
    data = {}
    for field in fields:
        try:
            locator = (page.locator(f"text={field}")
                       .locator("..").locator("span, td").last)
            data[field] = locator.inner_text().strip()
        except Exception:
            data[field] = None
    return data


def generate_report(pcdp_data, inconsistencies, financial_data):
    status = ("DEVOLVER"
              if any(i["gravidade"] in ["CRÍTICA", "GRAVE"] for i in inconsistencies)
              else "APROVAR")

    recomendacoes = []
    if status == "DEVOLVER":
        seen = set()
        for inc in inconsistencies:
            tip = inc.get("tipo", "")
            rec = _RECOMENDACOES_MAP.get(tip)
            if rec and rec not in seen:
                recomendacoes.append(rec)
                seen.add(rec)

    report = {
        # Metadados
        "auditor":              "Assistente Especialista SCDP",
        "data_analise":         datetime.now().strftime("%d/%m/%Y"),
        "autoridade_aprovadora": os.getenv("SCDP_LOGGED_IN_NAME", "").strip() or None,

        # Identificação
        "pcdp_numero":    pcdp_data.get("Número da PCDP"),
        "proposto":       pcdp_data.get("Nome do Proposto"),
        "solicitante":    pcdp_data.get("Solicitado por"),
        "orgao_solicitante": pcdp_data.get("Órgão Solicitante"),
        "tipo_proposto":  pcdp_data.get("Tipo de Proposto"),
        "periodo_viagem": pcdp_data.get("Período da Viagem"),
        "data_solicitacao": pcdp_data.get("Data da Solicitação"),
        "motivo_viagem":  pcdp_data.get("Motivo da Viagem"),
        "descricao":      pcdp_data.get("Descrição do Motivo da Viagem"),
        "status_fluxo":   pcdp_data.get("Status no Fluxo"),

        # Financeiro (preenchido pelo SCDP ou OCR futuro)
        "total_diarias":      financial_data.get("subtotal_diarias"),
        "total_passagens":    financial_data.get("subtotal_passagens"),
        "empenho":            financial_data.get("empenho"),
        "ptres":              financial_data.get("ptres"),
        "descricao_empenho":  financial_data.get("descricao_empenho"),
        "parcela_prevista":   financial_data.get("parcela_prevista"),
        "roteiro":            [],
        "diarias":            [],
        "pontos_conformes":   [],

        # Resultado
        "status":          status,
        "inconsistencias": inconsistencies,
        "dados_financeiros": financial_data,
        "recomendacoes":   recomendacoes,
        "texto_devolucao": generate_devolution_text(inconsistencies),
    }
    return report


def generate_devolution_text(inconsistencies):
    if not inconsistencies:
        return ""
    pcdp = inconsistencies[0].get("pcdp_numero", "")
    text = f"JUSTIFICATIVA DE DEVOLUÇÃO — PCDP nº {pcdp}\n\n"
    for i in inconsistencies:
        text += f"{i['id']}. {i['descricao']} (Gravidade: {i['gravidade']})\n"
        text += f"Fundamento: {i['fundamento_legal']}\n\n"
    text += "Solicito a correção das inconsistências apontadas para nova análise."
    return text


def save_analysis(report):
    session = Session()
    # Upsert: atualiza se o número da PCDP já existe
    existing = (session.query(PCDPAnalysis)
                .filter_by(pcdp_number=report["pcdp_numero"])
                .first())
    if existing:
        existing.proposto        = report["proposto"]
        existing.status          = report["status"]
        existing.inconsistencies = json.dumps(report["inconsistencias"], ensure_ascii=False)
        existing.financial_data  = json.dumps(report["dados_financeiros"], ensure_ascii=False)
        existing.report_json     = json.dumps(report, ensure_ascii=False)
        existing.analysis_date   = datetime.now()
    else:
        session.add(PCDPAnalysis(
            pcdp_number=report["pcdp_numero"],
            proposto=report["proposto"],
            status=report["status"],
            inconsistencies=json.dumps(report["inconsistencias"], ensure_ascii=False),
            financial_data=json.dumps(report["dados_financeiros"], ensure_ascii=False),
            report_json=json.dumps(report, ensure_ascii=False),
        ))
    session.commit()
    session.close()


if __name__ == "__main__":
    main()
