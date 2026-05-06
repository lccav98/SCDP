import os
import tempfile
from pathlib import Path

import pdfplumber
import pytesseract
from PIL import Image

from .config import TESSERACT_PATH

if os.path.exists(TESSERACT_PATH):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH


def extract_text_from_pdf(pdf_path: Path) -> str:
    full_text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for pg in pdf.pages:
                text = pg.extract_text()
                if text and len(text.strip()) > 20:
                    full_text += text + "\n"
                else:
                    full_text += pytesseract.image_to_string(
                        pg.to_image(resolution=300).original, lang="por"
                    ) + "\n"
    except Exception as e:
        print(f"    Erro ao ler PDF: {e}")
    return full_text


def extract_text_from_image(img_path: Path) -> str:
    try:
        return pytesseract.image_to_string(Image.open(img_path), lang="por")
    except Exception as e:
        print(f"    Erro ao ler imagem: {e}")
        return ""


def _text_from_bytes(content: bytes, fname: str = "") -> str:
    ext = Path(fname).suffix.lower() if fname else ".pdf"
    try:
        with tempfile.NamedTemporaryFile(suffix=ext or ".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            if ext in (".png", ".jpg", ".jpeg", ".tif", ".tiff"):
                return extract_text_from_image(tmp_path)
            return extract_text_from_pdf(tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)
    except Exception as e:
        print(f"    Erro ao extrair texto: {e}")
        return ""


def _expand_anexos_panel(page) -> bool:
    """
    Expande o painel ANEXOS DA VIAGEM na página de aprovação.
    O painel pode estar colapsado (ícone +). Retorna True se visível após tentativa.
    """
    # Seletores do painel ANEXOS DA VIAGEM (não navega para outra página)
    PANEL_SELS = [
        "text=ANEXOS DA VIAGEM",
        "span:has-text('ANEXOS DA VIAGEM')",
        "a:has-text('ANEXOS DA VIAGEM')",
        "h3:has-text('ANEXOS DA VIAGEM')",
        "[id*='anexosViagem']",
        "[id*='AnexosViagem']",
        "[id*='anexos_viagem']",
    ]
    for sel in PANEL_SELS:
        try:
            el = page.locator(sel).first
            if el.is_visible(timeout=2_000):
                el.click()
                page.wait_for_timeout(1_000)
                return True
        except Exception:
            continue
    return False


def _find_abrir_buttons(page):
    """
    Localiza os botões Abrir (seta de download) dentro do painel ANEXOS DA VIAGEM.
    Retorna lista de (locator, nome_documento).
    """
    # Tenta encontrar as linhas da tabela do painel ANEXOS DA VIAGEM
    # O painel pode ter ID/classe específica — tentamos várias abordagens

    result = page.evaluate("""() => {
        // Localiza o painel ANEXOS DA VIAGEM (contêiner com tabela)
        var panel = null;
        var allEls = document.querySelectorAll('*');
        for (var el of allEls) {
            var t = (el.innerText || el.textContent || '').trim();
            if (t === 'ANEXOS DA VIAGEM') {
                var p = el;
                for (var i = 0; i < 8; i++) {
                    if (p && p.querySelector('table')) { panel = p; break; }
                    if (p) p = p.parentElement;
                }
                if (panel) break;
            }
        }

        var debug = {panelFound: !!panel, abrirColIdx: -1, nomeColIdx: 1, rowCount: 0, firstRowCells: []};
        if (!panel) return {items: [], debug: debug};

        // Descobre índice das colunas pelo cabeçalho
        var headerRow = panel.querySelector('thead tr, tr:first-child');
        if (headerRow) {
            var ths = headerRow.querySelectorAll('th, td');
            for (var i = 0; i < ths.length; i++) {
                var hText = (ths[i].textContent || '').trim().toUpperCase();
                if (hText === 'ABRIR') debug.abrirColIdx = i;
                if (hText.includes('NOME') && hText.includes('DOCUMENT')) debug.nomeColIdx = i;
            }
        }

        var rows = panel.querySelectorAll('tbody tr');
        debug.rowCount = rows.length;

        // Diagnóstico da primeira linha
        if (rows.length > 0) {
            var firstCells = rows[0].querySelectorAll('td');
            for (var ci = 0; ci < firstCells.length; ci++) {
                var cellElems = firstCells[ci].querySelectorAll('a,button');
                debug.firstRowCells.push({idx: ci});
            }
        }

        var items = [];
        rows.forEach(function(row) {
            var cells = row.querySelectorAll('td');
            if (cells.length < 2) return;
            var nome = cells[debug.nomeColIdx] ? cells[debug.nomeColIdx].textContent.trim() : '';
            var btn = null;

            // Estratégia 1: coluna Abrir pelo índice do cabeçalho
            // O botão é <input type="image" id="...:linkDownload">
            if (debug.abrirColIdx >= 0 && cells[debug.abrirColIdx]) {
                var es = cells[debug.abrirColIdx].querySelectorAll('input[type="image"],a,button,span[onclick],div[onclick]');
                if (es.length > 0) btn = es[0];
            }
            // Estratégia 2: busca por ID com padrão "linkDownload" em qualquer célula
            if (!btn) {
                var dl = row.querySelector('[id*="linkDownload"],[id*="LinkDownload"]');
                if (dl) btn = dl;
            }

            if (btn) {
                items.push({
                    nome: nome,
                    btnId: btn.id,
                    btnTag: btn.tagName,
                    btnClass: btn.className,
                    btnOnclick: (btn.getAttribute('onclick') || '').substring(0, 100),
                });
            }
        });
        return {items: items, debug: debug};
    }""")
    if not result:
        return []
    return result.get("items", [])


def download_and_extract_all_attachments(page) -> str:
    """
    Lê os documentos da seção ANEXOS DA VIAGEM diretamente na página de aprovação.
    Expande o painel se necessário, clica em cada seta Abrir e intercepta
    a resposta de rede para extrair o texto sem navegar para outra página.
    """
    print("  Coletando anexos da viagem...")
    full_text = ""

    try:
        # Expande o painel ANEXOS DA VIAGEM APENAS se estiver colapsado.
        # Verificamos primeiro se as linhas da tabela já estão visíveis;
        # clicar no cabeçalho quando já expandido o colapsaria, ocultando os botões.
        try:
            rows_visible = page.evaluate("""() => {
                var all = document.querySelectorAll('*');
                for (var el of all) {
                    if ((el.innerText || el.textContent || '').trim() === 'ANEXOS DA VIAGEM') {
                        var p = el;
                        for (var i = 0; i < 8; i++) {
                            if (p && p.querySelector('tbody tr')) return true;
                            if (p) p = p.parentElement;
                        }
                    }
                }
                return false;
            }""")
        except Exception:
            rows_visible = False

        if not rows_visible:
            _expand_anexos_panel(page)

        # Localiza os botões Abrir
        items = _find_abrir_buttons(page)

        if not items:
            print("  Nenhum anexo identificado na viagem.")
            return ""

        print(f"  {len(items)} anexo(s) encontrado(s).")

        for item in items:
            nome = item.get("nome", "")
            btn_id = item.get("btnId", "")

            if not btn_id:
                print(f"    Sem ID para botão de '{nome}', pulando.")
                continue

            before_url = page.url
            captured_responses = []
            captured_downloads = []

            def on_response(response):
                ct = response.headers.get("content-type", "")
                cd = response.headers.get("content-disposition", "")
                if ("pdf" in ct or "attachment" in cd or
                        ("octet-stream" in ct and "html" not in ct)):
                    try:
                        body = response.body()
                        if body:
                            captured_responses.append((response.url, body))
                    except Exception:
                        pass

            def on_download(download):
                captured_downloads.append(download)

            page.context.on("response", on_response)
            page.on("download", on_download)
            try:
                page.locator(f'[id="{btn_id}"]').first.click(force=True, timeout=3_000)
            except Exception:
                try:
                    page.evaluate(
                        f'var el=document.querySelector(\'[id="{btn_id}"]\'); if(el) el.click();'
                    )
                except Exception:
                    pass
            try:
                page.wait_for_timeout(5_000)
            finally:
                page.context.remove_listener("response", on_response)
                page.remove_listener("download", on_download)

            # Volta ao PCDP se a página navegou
            if page.url != before_url:
                try:
                    page.goto(before_url, timeout=15_000, wait_until="load")
                except Exception:
                    pass

            # Processa o que foi capturado
            if captured_downloads:
                dl = captured_downloads[0]
                fname = dl.suggested_filename or f"{nome}.pdf"
                path = dl.path()
                if path:
                    text = extract_text_from_pdf(Path(path)) if fname.lower().endswith(".pdf") else extract_text_from_image(Path(path))
                    if text.strip():
                        full_text += f"\n--- {nome} ---\n{text}\n"
            elif captured_responses:
                _, content = captured_responses[0]
                text = _text_from_bytes(content, f"{nome}.pdf")
                if text.strip():
                    full_text += f"\n--- {nome} ---\n{text}\n"

    except Exception as e:
        print(f"  Aviso: erro ao processar anexos: {e}")

    return full_text
