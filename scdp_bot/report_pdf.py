from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle,
    Spacer, HRFlowable, Flowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import os

PAGE_W, PAGE_H = A4
MARGIN = 1.5 * cm

NAVY       = colors.HexColor('#1B3A5E')
LIGHT_BLUE = colors.HexColor('#E8EEF4')
RED        = colors.HexColor('#C0392B')
RED_LIGHT  = colors.HexColor('#FDECEA')
ORANGE     = colors.HexColor('#D35400')
ORANGE_LIGHT = colors.HexColor('#FEF5EC')
GREEN      = colors.HexColor('#1E8449')
LIGHT_GRAY = colors.HexColor('#F5F5F5')
MID_GRAY   = colors.HexColor('#CCCCCC')
DARK_GRAY  = colors.HexColor('#444444')
WHITE      = colors.white


class _SectionHeader(Flowable):
    def __init__(self, text, width):
        Flowable.__init__(self)
        self.text = text
        self.width = width
        self.height = 22

    def draw(self):
        self.canv.setFillColor(NAVY)
        self.canv.rect(0, 3, 4, 14, fill=1, stroke=0)
        self.canv.setFont('Helvetica-Bold', 10)
        self.canv.setFillColor(NAVY)
        self.canv.drawString(12, 6, self.text)


def _styles():
    s = {}
    s['title'] = ParagraphStyle(
        'title', fontSize=16, fontName='Helvetica-Bold',
        textColor=NAVY, alignment=TA_CENTER, spaceAfter=4)
    s['subtitle'] = ParagraphStyle(
        'subtitle', fontSize=11, fontName='Helvetica-Bold',
        textColor=NAVY, alignment=TA_CENTER, spaceAfter=4)
    s['meta'] = ParagraphStyle(
        'meta', fontSize=8, fontName='Helvetica',
        textColor=DARK_GRAY, alignment=TA_CENTER, spaceAfter=2)
    s['body'] = ParagraphStyle(
        'body', fontSize=9, fontName='Helvetica',
        textColor=DARK_GRAY, spaceAfter=2)
    s['footer'] = ParagraphStyle(
        'footer', fontSize=7, fontName='Helvetica-Oblique',
        textColor=colors.HexColor('#888888'), alignment=TA_CENTER)
    return s


def _info_table(rows, usable_w):
    col_w = [4.5 * cm, usable_w - 4.5 * cm]
    lbl_s = ParagraphStyle('lbl', fontSize=8, fontName='Helvetica',
                           textColor=colors.HexColor('#888888'))
    val_s = ParagraphStyle('val', fontSize=9, fontName='Helvetica-Bold',
                           textColor=DARK_GRAY)
    data = [[Paragraph(lbl, lbl_s), Paragraph(str(val or '—'), val_s)]
            for lbl, val in rows]
    t = Table(data, colWidths=col_w)
    style = [
        ('GRID', (0, 0), (-1, -1), 0.5, MID_GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 7),
        ('RIGHTPADDING', (0, 0), (-1, -1), 7),
    ]
    for i in range(0, len(data), 2):
        style.append(('BACKGROUND', (0, i), (-1, i), LIGHT_GRAY))
    t.setStyle(TableStyle(style))
    return t


def _generic_table(headers, rows, col_widths):
    hdr_s = ParagraphStyle('th', fontSize=8, fontName='Helvetica-Bold',
                           textColor=DARK_GRAY)
    cel_s = ParagraphStyle('td', fontSize=8, fontName='Helvetica',
                           textColor=DARK_GRAY)
    data = [[Paragraph(h, hdr_s) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c or '—'), cel_s) for c in row])
    t = Table(data, colWidths=col_widths)
    style = [
        ('BACKGROUND', (0, 0), (-1, 0), LIGHT_BLUE),
        ('GRID', (0, 0), (-1, -1), 0.5, MID_GRAY),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(data), 2):
        style.append(('BACKGROUND', (0, i), (-1, i), LIGHT_GRAY))
    t.setStyle(TableStyle(style))
    return t


def _inconsistency_card(inc, badge_text, badge_num, usable_w):
    is_critica = badge_text == 'CRÍTICA'
    badge_color = RED if is_critica else ORANGE
    card_bg = RED_LIGHT if is_critica else ORANGE_LIGHT

    titulo = inc.get('titulo', inc.get('descricao', '')[:60].upper())
    descricao = inc.get('descricao', '')
    impacto = inc.get('impacto', '')
    justificativa = inc.get('justificativa', '')

    badge_s = ParagraphStyle('bg', fontSize=7, fontName='Helvetica-Bold',
                             textColor=WHITE, alignment=TA_CENTER)
    title_s = ParagraphStyle('ct', fontSize=9, fontName='Helvetica-Bold',
                             textColor=DARK_GRAY)
    lbl_s   = ParagraphStyle('cl', fontSize=8, fontName='Helvetica-Bold',
                             textColor=DARK_GRAY)
    body_s  = ParagraphStyle('cb', fontSize=8.5, fontName='Helvetica',
                             textColor=DARK_GRAY, spaceAfter=2)

    col_badge = 1.6 * cm
    col_rest  = usable_w - col_badge

    header_data = [[
        Paragraph(badge_text, badge_s),
        Paragraph(f'N {badge_num} - {titulo}', title_s),
    ]]
    header_t = Table(header_data, colWidths=[col_badge, col_rest])
    header_t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), badge_color),
        ('BACKGROUND', (1, 0), (1, 0), card_bg),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (0, 0), 4),
        ('RIGHTPADDING', (0, 0), (0, 0), 4),
        ('LEFTPADDING', (1, 0), (1, 0), 8),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
    ]))

    col_lbl  = 3.2 * cm
    col_body = usable_w - col_lbl

    body_rows = []
    if descricao:
        body_rows.append([Paragraph('Descrição:', lbl_s),
                          Paragraph(descricao, body_s)])
    if impacto:
        body_rows.append([Paragraph('Impacto:', lbl_s),
                          Paragraph(impacto, body_s)])
    if justificativa:
        body_rows.append([Paragraph('Justificativa apresentada:', lbl_s),
                          Paragraph(justificativa, body_s)])

    elements = [header_t]
    if body_rows:
        body_t = Table(body_rows, colWidths=[col_lbl, col_body])
        body_t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), card_bg),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 7),
            ('RIGHTPADDING', (0, 0), (-1, -1), 7),
            ('LINEBELOW', (0, -1), (-1, -1), 0.5, badge_color),
            ('LINEBEFORE', (0, 0), (-1, -1), 3, badge_color),
        ]))
        elements.append(body_t)

    elements.append(Spacer(1, 8))
    return elements


def generate_pdf_report(report: dict, output_dir: str = ".") -> str:
    pcdp_num = report.get('pcdp_numero', 'sem_numero').replace('/', '_')
    filename = f"Relatorio_PCDP_{pcdp_num}.pdf"
    filepath = os.path.join(output_dir, filename)

    usable_w = PAGE_W - 2 * MARGIN
    doc = SimpleDocTemplate(
        filepath, pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
    )

    st = _styles()
    story = []

    # ── CABEÇALHO ────────────────────────────────────────────────────────────
    story.append(Paragraph('RELATÓRIO DE AUDITORIA SCDP', st['title']))
    story.append(Paragraph(
        f"PCDP N {report.get('pcdp_numero', '')} - Análise de Conformidade",
        st['subtitle']))
    story.append(Paragraph(
        f"Auditor: {report.get('auditor', 'Assistente Especialista SCDP')} | "
        f"Data da Auditoria: {report.get('data_analise', '')}",
        st['meta']))
    if report.get('autoridade_aprovadora'):
        story.append(Paragraph(
            f"Autoridade Aprovadora Logada: {report['autoridade_aprovadora']}",
            st['meta']))
    story.append(HRFlowable(width=usable_w, thickness=1.5,
                            color=NAVY, spaceAfter=10))

    # ── 1. IDENTIFICAÇÃO DO PROCESSO ─────────────────────────────────────────
    story.append(_SectionHeader('1. IDENTIFICAÇÃO DO PROCESSO', usable_w))
    story.append(Spacer(1, 4))
    id_rows = [
        ('N da PCDP',           report.get('pcdp_numero')),
        ('Solicitante',          report.get('solicitante')),
        ('Órgão Solicitante',    report.get('orgao_solicitante')),
        ('Proposto',             report.get('proposto')),
        ('Tipo de Proposto',     report.get('tipo_proposto')),
        ('Período da Viagem',    report.get('periodo_viagem')),
        ('Data da Solicitação',  report.get('data_solicitacao')),
        ('Motivo da Viagem',     report.get('motivo_viagem')),
        ('Descrição',            report.get('descricao')),
        ('Status no Fluxo',      report.get('status_fluxo')),
    ]
    story.append(_info_table([(l, v) for l, v in id_rows if v], usable_w))
    story.append(Spacer(1, 10))

    # ── 2. ROTEIRO DA VIAGEM ─────────────────────────────────────────────────
    roteiro = report.get('roteiro', [])
    if roteiro:
        story.append(_SectionHeader('2. ROTEIRO DA VIAGEM', usable_w))
        story.append(Spacer(1, 4))
        headers = ['Trecho', 'Origem', 'Destino', 'Permanência',
                   'Tipo', 'Transporte', 'Início Trabalho']
        rows = [[r.get('trecho'), r.get('origem'), r.get('destino'),
                 r.get('permanencia'), r.get('tipo'),
                 r.get('transporte'), r.get('inicio_trabalho')]
                for r in roteiro]
        col_w = [1.2*cm, 2.8*cm, 2.8*cm, 3.4*cm,
                 1.5*cm, 2.8*cm, 2.9*cm]
        story.append(_generic_table(headers, rows, col_w))
        story.append(Spacer(1, 10))

    # ── 3. DIÁRIAS E RECURSOS ─────────────────────────────────────────────────
    diarias = report.get('diarias', [])
    empenho_rows = [
        ('Empenho',              report.get('empenho')),
        ('PTRES',                report.get('ptres')),
        ('Descrição do Empenho', report.get('descricao_empenho')),
        ('Parcela Prevista',     report.get('parcela_prevista')),
    ]
    has_empenho = any(v for _, v in empenho_rows)
    if diarias or has_empenho:
        story.append(_SectionHeader('3. DIÁRIAS NACIONAIS E RECURSOS', usable_w))
        story.append(Spacer(1, 4))

    if diarias:
        headers = ['Trecho', 'Cidade', 'Dias', '% Diária',
                   'N Diárias', 'Valor Unitário', 'Valor Total']
        rows = [[d.get('trecho'), d.get('cidade'), d.get('dias'),
                 d.get('percentual'), d.get('n_diarias'),
                 d.get('valor_unitario'), d.get('valor_total')]
                for d in diarias]
        col_w = [1.4*cm, 3.4*cm, 1.2*cm, 1.8*cm,
                 1.8*cm, 2.9*cm, 2.9*cm]
        story.append(_generic_table(headers, rows, col_w))

        total = report.get('total_diarias')
        if total:
            tot_s = ParagraphStyle('tot', fontSize=9, fontName='Helvetica-Bold',
                                   textColor=NAVY)
            tot_data = [['', '', '', '', '',
                         Paragraph('Total', tot_s),
                         Paragraph(total, tot_s)]]
            tot_t = Table(tot_data, colWidths=col_w)
            tot_t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), LIGHT_BLUE),
                ('GRID', (0, 0), (-1, -1), 0.5, MID_GRAY),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ]))
            story.append(tot_t)
        story.append(Spacer(1, 6))

    if has_empenho:
        story.append(_info_table([(l, v) for l, v in empenho_rows if v], usable_w))

    if diarias or has_empenho:
        story.append(Spacer(1, 10))

    # ── 4. INCONSISTÊNCIAS IDENTIFICADAS ──────────────────────────────────────
    inconsistencias = report.get('inconsistencias', [])
    if inconsistencias:
        story.append(_SectionHeader('4. INCONSISTÊNCIAS IDENTIFICADAS', usable_w))
        story.append(Spacer(1, 4))
        critica_n = alerta_n = 0
        for inc in inconsistencias:
            gravidade = inc.get('gravidade', 'ATENÇÃO')
            is_critica = gravidade in ['CRÍTICA', 'GRAVE']
            if is_critica:
                critica_n += 1
                badge_text, badge_num = 'CRÍTICA', critica_n
            else:
                alerta_n += 1
                badge_text, badge_num = 'ALERTA', alerta_n
            for el in _inconsistency_card(inc, badge_text, badge_num, usable_w):
                story.append(el)
        story.append(Spacer(1, 4))

    # ── 5. PONTOS CONFORMES ───────────────────────────────────────────────────
    pontos = report.get('pontos_conformes', [])
    if pontos:
        story.append(_SectionHeader('5. PONTOS CONFORMES', usable_w))
        story.append(Spacer(1, 4))
        for p in pontos:
            story.append(Paragraph(f'• {p}', st['body']))
        story.append(Spacer(1, 10))

    # ── 6. RESUMO DAS INCONSISTÊNCIAS ────────────────────────────────────────
    if inconsistencias:
        sec_num = 6 if pontos else 5
        story.append(_SectionHeader(f'{sec_num}. RESUMO DAS INCONSISTÊNCIAS', usable_w))
        story.append(Spacer(1, 4))

        hdr_s = ParagraphStyle('th', fontSize=8, fontName='Helvetica-Bold',
                               textColor=DARK_GRAY)
        cel_s = ParagraphStyle('td', fontSize=8, fontName='Helvetica',
                               textColor=DARK_GRAY)
        col_w = [0.8*cm, 2.8*cm, usable_w - 0.8*cm - 2.8*cm - 2.6*cm, 2.6*cm]
        data = [[Paragraph(h, hdr_s)
                 for h in ['#', 'Tipo', 'Descrição Resumida', 'Severidade']]]

        for i, inc in enumerate(inconsistencias, 1):
            gravidade = inc.get('gravidade', 'ATENÇÃO')
            is_critica = gravidade in ['CRÍTICA', 'GRAVE']
            tipo = 'Inconsistência' if is_critica else 'Alerta'
            desc = inc.get('descricao', '')[:90]
            sev_color = RED if is_critica else ORANGE
            sev_label = 'CRÍTICA' if is_critica else 'MÉDIA'
            data.append([
                Paragraph(str(i), cel_s),
                Paragraph(tipo, cel_s),
                Paragraph(desc, cel_s),
                Paragraph(sev_label, ParagraphStyle(
                    'sev', fontSize=8, fontName='Helvetica-Bold',
                    textColor=sev_color)),
            ])

        t = Table(data, colWidths=col_w)
        ts = [
            ('BACKGROUND', (0, 0), (-1, 0), LIGHT_BLUE),
            ('GRID', (0, 0), (-1, -1), 0.5, MID_GRAY),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ]
        for i in range(1, len(data), 2):
            ts.append(('BACKGROUND', (0, i), (-1, i), LIGHT_GRAY))
        t.setStyle(TableStyle(ts))
        story.append(t)
        story.append(Spacer(1, 14))

    # ── RECOMENDAÇÃO ─────────────────────────────────────────────────────────
    is_devolver = report.get('status') == 'DEVOLVER'
    rec_color = RED if is_devolver else GREEN
    rec_title_text = ('RECOMENDAÇÃO: DEVOLVER PARA CORREÇÃO / NÃO APROVAR'
                      if is_devolver else 'RECOMENDAÇÃO: APROVAR')

    rt_s = ParagraphStyle('rt', fontSize=11, fontName='Helvetica-Bold',
                          textColor=rec_color, alignment=TA_CENTER, spaceAfter=6)
    ri_s = ParagraphStyle('ri', fontSize=9, fontName='Helvetica',
                          textColor=DARK_GRAY, spaceAfter=4)
    rl_s = ParagraphStyle('rl', fontSize=9, fontName='Helvetica-Bold',
                          textColor=DARK_GRAY, spaceAfter=4)
    rb_s = ParagraphStyle('rb', fontSize=9, fontName='Helvetica',
                          textColor=DARK_GRAY, spaceAfter=3)

    box_rows = [[Paragraph(rec_title_text, rt_s)]]

    recs = report.get('recomendacoes', [])
    if is_devolver and recs:
        intro = 'Este processo apresenta inconsistências que impedem a aprovação imediata.'
        box_rows.append([Paragraph(intro, ri_s)])
        box_rows.append([Paragraph('Recomenda-se devolver a PCDP ao solicitante para:', rl_s)])
        for r in recs:
            box_rows.append([Paragraph(f'• {r}', rb_s)])

    rec_t = Table(box_rows, colWidths=[usable_w])
    rec_t.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1.5, rec_color),
        ('BACKGROUND', (0, 0), (-1, -1), WHITE),
        ('TOPPADDING', (0, 0), (-1, -1), 7),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
    ]))
    story.append(rec_t)
    story.append(Spacer(1, 14))

    # ── RODAPÉ ───────────────────────────────────────────────────────────────
    footer = (
        f"Relatório gerado com base nos dados disponíveis no SCDP em "
        f"{report.get('data_analise', '')}. "
        "Os dados apresentados refletem as informações do sistema no momento da análise."
    )
    story.append(HRFlowable(width=usable_w, thickness=0.5,
                            color=MID_GRAY, spaceAfter=4))
    story.append(Paragraph(footer, st['footer']))

    doc.build(story)
    return filepath
