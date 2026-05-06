from .browser import random_delay, close_modal
from .ocr_engine import download_and_extract_all_attachments
from datetime import datetime
import re

_STOPWORDS_NOME = {"DE", "DA", "DO", "DOS", "DAS", "E", "A", "O", "EM"}

# Palavras comuns que não identificam operações/exercícios
_STOPWORDS = {
    "DIARIA", "DIARIAS", "MILITAR", "MILITARES", "TRIMESTRE", "DESTINADO",
    "CONFORME", "SERVICO", "NACIONAL", "VIAGEM", "CUSTO", "CENTRO",
    "SFPC", "COEX", "PARA", "PASSAGEM", "PASSAGENS", "AGOSTO", "JULHO",
    "ABRIL", "MAIO", "JUNHO", "MARCO", "JANEIRO", "FEVEREIRO", "SETEMBRO",
    "OUTUBRO", "NOVEMBRO", "DEZEMBRO", "EXERCICIO", "INSTRUCAO",
}

_OP_PATTERN = re.compile(
    r'\b(?:OP(?:ERACAO|ERAÇÕES)?\.?\s+|EX(?:ERCICIO)?\.?\s+|INSTR(?:UCAO)?\.?\s+)?'
    r'([A-Z][A-Z0-9]{2,}(?:\s+[IVX]{1,4})?)\b'
)


def _extrair_identificadores(texto):
    """Extrai substantivos próprios/codenames relevantes de um texto."""
    palavras = set()
    for m in _OP_PATTERN.finditer(texto.upper()):
        p = m.group(1).strip()
        if p not in _STOPWORDS and len(p) >= 4:
            palavras.add(p)
    return palavras


def run_all_validations(page, pcdp_data):
    inconsistencies = []
    pcdp_number = pcdp_data.get("Número da PCDP", "N/A")

    # ── Coleta financeira (precisa dos dados para algumas regras) ─────────────
    financial_data = collect_financial_data(page)

    # ── Regra 1: Prazo mínimo de solicitação ──────────────────────────────────
    val, inc = validate_request_deadline(pcdp_data)
    if inc is not None:
        inconsistencies.append({
            "id": len(inconsistencies) + 1,
            "tipo": "PRAZO_SOLICITACAO",
            "titulo": "PRAZO INFERIOR A 15 DIAS",
            "gravidade": "GRAVE",
            "descricao": val,
            "impacto": "O sistema emitiu alerta automático de prazo inferior a 15 dias. "
                       "Indica planejamento inadequado da viagem.",
            "campo": "Data da Solicitação",
            "valor_encontrado": pcdp_data.get("Data da Solicitação"),
            "valor_esperado": ">= 15 dias antes da viagem",
            "fundamento_legal": "IN 66/2021-DAF, Manual SCDP",
            "pcdp_numero": pcdp_number,
        })

    # ── Regra 2: Prestação de contas pendente ─────────────────────────────────
    inc = validate_pending_accounts(page)
    if inc:
        inconsistencies.append({
            "id": len(inconsistencies) + 1,
            "tipo": "PC_PENDENTE",
            "titulo": "PROPOSTO COM PRESTAÇÃO DE CONTAS PENDENTE",
            "gravidade": "CRÍTICA",
            "descricao": inc,
            "impacto": "Impedimento regulamentar à concessão de novas diárias. "
                       "Requer regularização antes da aprovação.",
            "campo": "Alertas do Sistema",
            "valor_encontrado": "Alerta: prestações de contas pendentes",
            "fundamento_legal": "Portaria GM-MD 4.074/2024, art. 23",
            "pcdp_numero": pcdp_number,
        })

    # ── Regra 3: Empenho vs Motivo da Viagem (leitura de página) ─────────────
    inc = validate_empenho_vs_motivo(pcdp_data, financial_data)
    if inc:
        inconsistencies.append({
            "id": len(inconsistencies) + 1,
            "tipo": "DIVERGENCIA_EMPENHO_MOTIVO",
            "titulo": "DIVERGÊNCIA ENTRE EMPENHO E OBJETIVO DA VIAGEM",
            "gravidade": "CRÍTICA",
            "descricao": inc,
            "impacto": "Alta gravidade. Indica possível vínculo indevido de recursos "
                       "orçamentários. Requer esclarecimento formal.",
            "campo": "Descrição do Empenho / Motivo da Viagem",
            "valor_encontrado": financial_data.get("descricao_empenho", ""),
            "valor_esperado": "Compatível com o motivo da viagem",
            "fundamento_legal": "Lei 4.320/1964, art. 60; Decreto 93.872/1986",
            "pcdp_numero": pcdp_number,
        })

    # ── Regra 4: Data de vencimento da parcela anterior à viagem ─────────────
    inc = validate_data_parcela(pcdp_data, financial_data)
    if inc:
        inconsistencies.append({
            "id": len(inconsistencies) + 1,
            "tipo": "VENCIMENTO_ANTERIOR_VIAGEM",
            "titulo": "DATA DE VENCIMENTO DA PARCELA ANTERIOR À VIAGEM",
            "gravidade": "CRÍTICA",
            "descricao": inc,
            "impacto": "Alta gravidade. Indica possível irregularidade no processamento "
                       "financeiro. A diária é devida após o afastamento.",
            "campo": "Parcela Prevista",
            "valor_encontrado": financial_data.get("parcela_vencimento", ""),
            "valor_esperado": "Vencimento >= data de início da viagem",
            "fundamento_legal": "Decreto 11.872/2023, art. 4º",
            "pcdp_numero": pcdp_number,
        })

    # ── Regra 5: PTRES de unidade diferente do órgão solicitante ─────────────
    inc = validate_ptres_orgao(pcdp_data, financial_data)
    if inc:
        inconsistencies.append({
            "id": len(inconsistencies) + 1,
            "tipo": "PTRES_ORGAO_DIVERGENTE",
            "titulo": "INCONSISTÊNCIA ENTRE ÓRGÃO DO PTRES E ÓRGÃO SOLICITANTE",
            "gravidade": "ATENÇÃO",
            "descricao": inc,
            "impacto": "Merece verificação quanto à regularidade da cessão orçamentária.",
            "campo": "PTRES / Órgão Solicitante",
            "valor_encontrado": financial_data.get("ptres", ""),
            "valor_esperado": "PTRES da mesma unidade do órgão solicitante",
            "fundamento_legal": "Lei 4.320/1964; Normas de execução orçamentária",
            "pcdp_numero": pcdp_number,
        })

    # ── Regra 6: Justificativas genéricas ────────────────────────────────────
    inc = validate_generic_justifications(page)
    if inc:
        inconsistencies.append({
            "id": len(inconsistencies) + 1,
            "tipo": "JUSTIFICATIVA_GENERICA",
            "titulo": "JUSTIFICATIVA GENÉRICA NAS SOLICITAÇÕES",
            "gravidade": "ATENÇÃO",
            "descricao": inc,
            "justificativa": f"{inc} — Genérica. Não demonstra objetivamente a "
                            "necessidade ou urgência da viagem.",
            "campo": "Justificativas",
            "valor_encontrado": inc,
            "fundamento_legal": "Lei 9.784/1999, art. 50",
            "pcdp_numero": pcdp_number,
        })

    # ── Regra 7: Conferência de documentos anexos via OCR ────────────────────
    ocr_text = download_and_extract_all_attachments(page)
    if ocr_text:
        for desc in validate_ocr_divergences(pcdp_data, financial_data, ocr_text):
            inconsistencies.append({
                "id": len(inconsistencies) + 1,
                "tipo": "DIVERGENCIA_ANEXO_OCR",
                "titulo": "DIVERGÊNCIA NOS DOCUMENTOS ANEXOS",
                "gravidade": "GRAVE",
                "descricao": desc,
                "impacto": "O conteúdo dos anexos não confere com os dados do formulário.",
                "campo": "Anexos da Viagem",
                "valor_encontrado": desc,
                "valor_esperado": "Dados do formulário confirmados nos anexos",
                "fundamento_legal": "IN 66/2021-DAF, art. 12",
                "pcdp_numero": pcdp_number,
            })

    return inconsistencies, financial_data


# ── VALIDADORES ───────────────────────────────────────────────────────────────

def validate_ocr_divergences(pcdp_data, financial_data, ocr_text) -> list:
    """
    Compara o texto extraído dos anexos (OCR/pdfplumber) com os dados do formulário.
    Retorna lista de descrições de divergências encontradas.
    Só reporta quando há evidência clara — falsos positivos prejudicam a confiança.
    """
    if not ocr_text or len(ocr_text.strip()) < 60:
        return []

    divergencias = []
    ocr_upper = ocr_text.upper()

    # ── 1. Nome do proposto ────────────────────────────────────────────────────
    nome = (pcdp_data.get("Nome do Proposto") or "").strip().upper()
    if nome:
        partes = [p for p in nome.split() if p not in _STOPWORDS_NOME and len(p) > 2]
        if partes:
            encontradas = sum(1 for p in partes if p in ocr_upper)
            # Divergência apenas se nenhuma palavra significativa do nome foi encontrada
            if encontradas == 0:
                divergencias.append(
                    f"Nome do proposto '{pcdp_data.get('Nome do Proposto')}' não "
                    f"localizado em nenhum documento anexo."
                )

    # ── 2. Número da PCDP ─────────────────────────────────────────────────────
    pcdp_num = (pcdp_data.get("Número da PCDP") or "").strip()
    if pcdp_num:
        # Aceita formatos: "012099/26", "012099-26", "012099 26"
        num_normalizado = re.sub(r"[\s/\-]", "", pcdp_num)
        ocr_sem_sep = re.sub(r"[\s/\-]", "", ocr_upper)
        if num_normalizado and num_normalizado not in ocr_sem_sep:
            divergencias.append(
                f"Número da PCDP '{pcdp_num}' não identificado nos documentos anexos."
            )

    # ── 3. Datas do período da viagem ─────────────────────────────────────────
    periodo = (pcdp_data.get("Período da Viagem") or "").strip()
    if periodo:
        datas = re.findall(r"\d{2}/\d{2}/\d{4}", periodo)
        if datas:
            # Normaliza datas no OCR para comparação (aceita DD/MM/AAAA, DD-MM-AAAA, DDMMAAAA)
            ocr_datas_norm = re.sub(r"[/\-\.]", "", ocr_upper)
            datas_norm = [re.sub(r"[/\-\.]", "", d) for d in datas]
            encontradas = sum(1 for d in datas_norm if d in ocr_datas_norm)
            if encontradas == 0:
                divergencias.append(
                    f"Nenhuma das datas do período '{periodo}' foi encontrada nos anexos."
                )

    # ── 4. Valor total de diárias (se disponível) ─────────────────────────────
    total_diarias = (financial_data.get("subtotal_diarias") or "").strip()
    if total_diarias:
        # Remove R$, pontos de milhar; mantém o valor numérico para comparação
        valor_limpo = re.sub(r"[R$\s\.]", "", total_diarias).replace(",", ".")
        if valor_limpo and valor_limpo not in ocr_upper.replace(",", "."):
            # Só reporta se o texto OCR menciona algum valor monetário mas diverge
            if re.search(r"R\$|REAIS|VALOR", ocr_upper):
                divergencias.append(
                    f"Valor de diárias '{total_diarias}' não confirmado nos documentos anexos."
                )

    return divergencias


def validate_request_deadline(pcdp_data):
    try:
        solic_date_str = pcdp_data.get("Data da Solicitação")
        period = pcdp_data.get("Período da Viagem")
        if not solic_date_str or not period:
            return None, None
        solic_date = datetime.strptime(solic_date_str, "%d/%m/%Y")
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


def validate_empenho_vs_motivo(pcdp_data, financial_data):
    """Detecta divergência entre operação/exercício no empenho e no motivo da viagem."""
    try:
        desc_empenho = financial_data.get("descricao_empenho", "")
        desc_motivo  = (pcdp_data.get("Descrição do Motivo da Viagem") or
                        pcdp_data.get("Motivo da Viagem") or "")

        if not desc_empenho or not desc_motivo:
            return None

        ids_empenho = _extrair_identificadores(desc_empenho)
        ids_motivo  = _extrair_identificadores(desc_motivo)

        if not ids_empenho or not ids_motivo:
            return None

        # Considera divergência se os conjuntos são completamente disjuntos
        if ids_empenho.isdisjoint(ids_motivo):
            return (
                f"A Descrição do Motivo da Viagem registra termos {ids_motivo}, "
                f"enquanto o empenho vinculado refere-se a {ids_empenho}. "
                f"São objetivos distintos."
            )
    except Exception:
        pass
    return None


def validate_data_parcela(pcdp_data, financial_data):
    """Detecta parcela com vencimento anterior à data de início da viagem."""
    try:
        vencimento_str = financial_data.get("parcela_vencimento", "")
        period = pcdp_data.get("Período da Viagem") or ""

        if not vencimento_str or not period:
            return None

        data_venc   = datetime.strptime(vencimento_str, "%d/%m/%Y")
        match_inicio = re.search(r"\d{2}/\d{2}/\d{4}", period)
        if not match_inicio:
            return None
        data_inicio = datetime.strptime(match_inicio.group(), "%d/%m/%Y")

        if data_venc < data_inicio:
            return (
                f"A parcela prevista tem vencimento em {vencimento_str}, "
                f"sendo que a viagem ocorreu em {match_inicio.group()}. "
                f"A diária é devida após o afastamento."
            )
    except Exception:
        pass
    return None


def validate_ptres_orgao(pcdp_data, financial_data):
    """Detecta divergência entre a unidade do PTRES e o órgão solicitante."""
    try:
        ptres = financial_data.get("ptres", "")
        orgao = pcdp_data.get("Órgão Solicitante") or pcdp_data.get("Solicitado por", "")

        if not ptres or not orgao:
            return None

        # Extrai a sigla da unidade do PTRES (antes do " - PTRES")
        ptres_unidade = re.split(r'\s*[-–]\s*PTRES', ptres, flags=re.IGNORECASE)[0].strip()

        # Normaliza para comparação
        def normalizar(s):
            return re.sub(r'\s+', ' ', s.upper().strip())

        ptres_n = normalizar(ptres_unidade)
        orgao_n = normalizar(orgao)

        # Só reporta se a unidade do PTRES não está contida no órgão (nem vice-versa)
        if ptres_n and orgao_n and ptres_n not in orgao_n and orgao_n not in ptres_n:
            return (
                f"O PTRES pertence a '{ptres_unidade}', enquanto o órgão "
                f"solicitante é '{orgao}'. Merece verificação quanto à "
                f"regularidade da cessão orçamentária."
            )
    except Exception:
        pass
    return None


def validate_generic_justifications(page):
    generic_terms = [
        "de acordo com o cronograma",
        "conforme programação",
        "conforme cronograma",
    ]
    url_before = page.url

    try:
        page.click("text=Justificativas: Clique aqui")
        random_delay()
    except Exception:
        return None

    # Se o clique abriu um popup (nova aba), lê e fecha o popup
    try:
        popups = [pg for pg in page.context.pages if pg != page]
        if popups:
            popup = popups[-1]
            result = None
            try:
                popup.wait_for_load_state("domcontentloaded", timeout=5_000)
                popup_text = popup.content().lower()
                for term in generic_terms:
                    if term in popup_text:
                        result = f"Justificativa genérica encontrada: '{term}'"
                        break
            except Exception:
                pass
            finally:
                try:
                    popup.close()
                except Exception:
                    pass
            return result
    except Exception:
        pass

    # Proteção: se o clique navegou a própria página, volta imediatamente
    if page.url != url_before:
        try:
            page.go_back()
            page.wait_for_load_state("networkidle", timeout=10_000)
        except Exception:
            pass
        return None

    try:
        for term in generic_terms:
            if page.locator(f"text={term}").count() > 0:
                close_modal(page)
                return f"Justificativa genérica encontrada: '{term}'"
        close_modal(page)
    except Exception:
        pass
    return None


def collect_financial_data(page):
    """Coleta dados financeiros e de empenho diretamente da página."""
    data = {}

    # Expande o quadro de totalizações se necessário
    try:
        page.click("text=QUADRO DE TOTALIZAÇÕES")
        random_delay()
    except Exception:
        pass

    # Coleta tudo em um único round-trip ao browser
    try:
        result = page.evaluate(r"""() => {
            const out = {};

            function findByLabel(labels) {
                for (const lbl of labels) {
                    const xp = document.evaluate(
                        `//*[normalize-space(.)="${lbl}"]`,
                        document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
                    );
                    const el = xp.singleNodeValue;
                    if (!el) continue;
                    const parent = el.parentElement;
                    if (!parent) continue;
                    const targets = parent.querySelectorAll('span, td');
                    if (targets.length > 0)
                        return targets[targets.length - 1].textContent.trim();
                    const sib = el.nextElementSibling;
                    if (sib) return sib.textContent.trim();
                }
                return null;
            }

            out.subtotal_diarias   = findByLabel(['Subtotal Diárias']);
            out.subtotal_passagens = findByLabel(['Subtotal Passagens']);
            out.empenho            = findByLabel(['Empenho', 'Número do Empenho', 'N° do Empenho']);
            out.ptres              = findByLabel(['PTRES']);
            out.descricao_empenho  = findByLabel(['Descrição do Empenho', 'Descrição']);

            const bodyText = document.body.innerText;
            const m = bodyText.match(/Vencimento[:\s]+(\d{2}\/\d{2}\/\d{4})/);
            if (m) {
                out.parcela_vencimento = m[1];
                out.parcela_prevista   = m[0].trim();
            }

            return out;
        }""")
        if result:
            data.update({k: v for k, v in result.items() if v})
    except Exception:
        pass

    # Fallback individual para campos ainda ausentes
    if not data.get("empenho"):
        _coleta_campo(page, data, "empenho",
                      ["Empenho", "Número do Empenho", "N° do Empenho"])
    if not data.get("ptres"):
        _coleta_campo(page, data, "ptres", ["PTRES"])
    if not data.get("descricao_empenho"):
        _coleta_campo(page, data, "descricao_empenho",
                      ["Descrição do Empenho", "Descrição"])

    return data


def _coleta_campo(page, data, chave, labels):
    """Fallback: coleta individual por rótulo."""
    for label in labels:
        try:
            valor = (
                page.locator(f"text={label}")
                .locator("..").locator("span, td").last
                .inner_text().strip()
            )
            if valor:
                data[chave] = valor
                return
        except Exception:
            pass
