"""Markdown → Word (.docx) / PDF conversion for local documents (v0.3).

Markdown on disk stays the source of truth; these converters run on demand
from POST /documents/export. Word rendering walks mistune's AST into
python-docx; PDF goes markdown → HTML → xhtml2pdf. Both engines are
pure-Python on purpose: prettier HTML→PDF engines (WeasyPrint et al.) need
system cairo/pango libraries the self-contained desktop backend can't
assume on a user's machine.

Known limits (fine for text-first business docs, revisit if users hit them):
- emoji render as boxes in the PDF (the base-14 fonts have no emoji glyphs)
- images are skipped (nothing in the app writes local images into docs)
- ordered lists in Word use literal "1." prefixes so numbering can never
  bleed across lists (python-docx can't restart real numbering without
  numbering.xml surgery)
"""
from __future__ import annotations

import io
from html import escape as html_escape

import mistune

_FORMAT_MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}
SUPPORTED_FORMATS = tuple(_FORMAT_MEDIA_TYPES)

_MISTUNE_PLUGINS = ["table", "strikethrough"]


def media_type_for(fmt: str) -> str:
    return _FORMAT_MEDIA_TYPES[fmt]


def export_markdown(body: str, title: str, fmt: str) -> bytes:
    """Convert a document's markdown body to the requested format."""
    if fmt == "docx":
        return _to_docx(body, title)
    if fmt == "pdf":
        return _to_pdf(body, title)
    raise ValueError(f"unsupported export format '{fmt}' (supported: {', '.join(SUPPORTED_FORMATS)})")


def _ast(markdown: str) -> list[dict]:
    parse = mistune.create_markdown(renderer=None, plugins=_MISTUNE_PLUGINS)
    return parse(markdown) or []


def _starts_with_h1(tokens: list[dict]) -> bool:
    """Whether the document body opens with its own top-level heading. If it
    doesn't, the exporters prepend the artifact title so the file isn't
    headless when it lands on someone's desk."""
    for tok in tokens:
        if tok.get("type") == "blank_line":
            continue
        return tok.get("type") == "heading" and tok.get("attrs", {}).get("level") == 1
    return False


def _plain_text(tokens: list[dict]) -> str:
    parts: list[str] = []
    for tok in tokens:
        raw = tok.get("raw")
        if isinstance(raw, str):
            parts.append(raw)
        parts.append(_plain_text(tok.get("children", [])))
    return "".join(parts)


# ── Word ────────────────────────────────────────────────────────────────────


def _to_docx(body: str, title: str) -> bytes:
    import docx
    from docx.shared import Inches, Pt

    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    doc = docx.Document()
    tokens = _ast(body)

    def run_of(paragraph, text, *, bold=False, italic=False, strike=False, code=False):
        if not text:
            return
        run = paragraph.add_run(text)
        run.bold = bold or None
        run.italic = italic or None
        run.font.strike = strike or None
        if code:
            run.font.name = "Courier New"

    def hyperlink(paragraph, url: str, text: str):
        from docx.opc.constants import RELATIONSHIP_TYPE as RT

        r_id = paragraph.part.relate_to(url, RT.HYPERLINK, is_external=True)
        link = OxmlElement("w:hyperlink")
        link.set(qn("r:id"), r_id)
        run = OxmlElement("w:r")
        rpr = OxmlElement("w:rPr")
        color = OxmlElement("w:color")
        color.set(qn("w:val"), "0563C1")
        rpr.append(color)
        underline = OxmlElement("w:u")
        underline.set(qn("w:val"), "single")
        rpr.append(underline)
        run.append(rpr)
        text_el = OxmlElement("w:t")
        text_el.text = text
        run.append(text_el)
        link.append(run)
        paragraph._p.append(link)

    def inline(paragraph, toks, *, bold=False, italic=False, strike=False, code=False):
        for tok in toks:
            t = tok.get("type")
            children = tok.get("children", [])
            if t == "text":
                run_of(paragraph, tok.get("raw", ""), bold=bold, italic=italic, strike=strike, code=code)
            elif t == "strong":
                inline(paragraph, children, bold=True, italic=italic, strike=strike, code=code)
            elif t == "emphasis":
                inline(paragraph, children, bold=bold, italic=True, strike=strike, code=code)
            elif t == "strikethrough":
                inline(paragraph, children, bold=bold, italic=italic, strike=True, code=code)
            elif t == "codespan":
                run_of(paragraph, tok.get("raw", ""), bold=bold, italic=italic, strike=strike, code=True)
            elif t == "link":
                url = tok.get("attrs", {}).get("url", "")
                hyperlink(paragraph, url, _plain_text(children) or url)
            elif t == "image":
                alt = _plain_text(children)
                run_of(paragraph, alt or tok.get("attrs", {}).get("url", ""), italic=True)
            elif t == "linebreak":
                paragraph.add_run().add_break()
            elif t == "softbreak":
                run_of(paragraph, " ", bold=bold, italic=italic, strike=strike, code=code)
            elif t == "inline_html":
                run_of(paragraph, tok.get("raw", ""), bold=bold, italic=italic, strike=strike, code=code)
            elif children:
                inline(paragraph, children, bold=bold, italic=italic, strike=strike, code=code)

    bullet_styles = ("List Bullet", "List Bullet 2", "List Bullet 3")

    def render_list(tok, depth):
        ordered = tok.get("attrs", {}).get("ordered", False)
        number = 1
        for item in tok.get("children", []):
            first_paragraph_done = False
            for child in item.get("children", []):
                ct = child.get("type")
                if ct == "list":
                    render_list(child, depth + 1)
                elif ct in ("block_text", "paragraph"):
                    if ordered:
                        p = doc.add_paragraph()
                        p.paragraph_format.left_indent = Inches(0.25 * (depth + 1))
                        if not first_paragraph_done:
                            run_of(p, f"{number}. ")
                        inline(p, child.get("children", []))
                    else:
                        p = doc.add_paragraph(style=bullet_styles[min(depth, 2)])
                        inline(p, child.get("children", []))
                    first_paragraph_done = True
                else:
                    blocks([child], depth + 1)
            if ordered:
                number += 1

    def render_table(tok):
        head_cells: list[dict] = []
        body_rows: list[list[dict]] = []
        for child in tok.get("children", []):
            if child.get("type") == "table_head":
                head_cells = child.get("children", [])
            elif child.get("type") == "table_body":
                body_rows = [row.get("children", []) for row in child.get("children", [])]
        cols = max([len(head_cells)] + [len(r) for r in body_rows], default=0)
        if cols == 0:
            return
        table = doc.add_table(rows=(1 if head_cells else 0) + len(body_rows), cols=cols)
        table.style = "Table Grid"
        row_idx = 0
        if head_cells:
            for col, cell in enumerate(head_cells):
                inline(table.rows[0].cells[col].paragraphs[0], cell.get("children", []), bold=True)
            row_idx = 1
        for row in body_rows:
            for col, cell in enumerate(row[:cols]):
                inline(table.rows[row_idx].cells[col].paragraphs[0], cell.get("children", []))
            row_idx += 1

    def horizontal_rule():
        p = doc.add_paragraph()
        p_pr = p._p.get_or_add_pPr()
        border = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "6")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), "999999")
        border.append(bottom)
        p_pr.append(border)

    def blocks(toks, depth=0, quote=False):
        for tok in toks:
            t = tok.get("type")
            if t == "blank_line":
                continue
            if t == "heading":
                level = tok.get("attrs", {}).get("level", 2)
                p = doc.add_paragraph(style=f"Heading {min(level, 4)}")
                inline(p, tok.get("children", []))
            elif t in ("paragraph", "block_text"):
                p = doc.add_paragraph(style="Quote" if quote else None)
                inline(p, tok.get("children", []))
            elif t == "list":
                render_list(tok, depth)
            elif t == "block_quote":
                blocks(tok.get("children", []), depth, quote=True)
            elif t == "block_code":
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Inches(0.25)
                run = p.add_run(tok.get("raw", "").rstrip("\n"))
                run.font.name = "Courier New"
                run.font.size = Pt(9)
            elif t == "thematic_break":
                horizontal_rule()
            elif t == "table":
                render_table(tok)
            elif t == "block_html":
                run_of(doc.add_paragraph(), tok.get("raw", ""))
            elif tok.get("children"):
                inline(doc.add_paragraph(), tok["children"])

    if title and not _starts_with_h1(tokens):
        doc.add_paragraph(title, style="Heading 1")
    blocks(tokens)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


# ── PDF ─────────────────────────────────────────────────────────────────────

# Conservative CSS2 subset — xhtml2pdf ignores what it doesn't know, so keep
# to properties it demonstrably supports (verified in the export tests).
_PDF_CSS = """
@page { size: a4; margin: 2cm 1.8cm; }
body { font-family: Helvetica; font-size: 10.5pt; color: #1a1a1a; line-height: 1.45; }
h1 { font-size: 19pt; margin: 0 0 8pt 0; }
h2 { font-size: 14.5pt; margin: 14pt 0 5pt 0; }
h3 { font-size: 12pt; margin: 11pt 0 4pt 0; }
h4, h5, h6 { font-size: 10.5pt; margin: 9pt 0 3pt 0; }
p { margin: 0 0 7pt 0; }
ul, ol { margin: 0 0 7pt 0; }
li { margin: 0 0 3pt 0; }
table { margin: 4pt 0 10pt 0; }
th, td { border: 0.6pt solid #aaaaaa; padding: 3pt 5pt; font-size: 9.5pt; }
th { background-color: #eeeeee; font-weight: bold; }
pre { font-family: Courier; font-size: 9pt; background-color: #f4f4f4; padding: 6pt; margin: 0 0 8pt 0; }
code { font-family: Courier; font-size: 9.5pt; }
blockquote { margin: 0 0 7pt 14pt; color: #444444; font-style: italic; }
hr { border: 0; border-top: 0.6pt solid #999999; margin: 10pt 0; }
a { color: #0563C1; text-decoration: underline; }
"""


def _to_pdf(body: str, title: str) -> bytes:
    from xhtml2pdf import pisa

    # escape=True HTML-escapes any raw HTML in the markdown — predictable
    # output beats passing arbitrary tags into the PDF engine.
    render = mistune.create_markdown(escape=True, plugins=_MISTUNE_PLUGINS)
    html_body = render(body)
    if title and not _starts_with_h1(_ast(body)):
        html_body = f"<h1>{html_escape(title)}</h1>\n{html_body}"
    html_doc = f"<html><head><style>{_PDF_CSS}</style></head><body>{html_body}</body></html>"

    buf = io.BytesIO()
    status = pisa.CreatePDF(src=html_doc, dest=buf)
    if status.err:
        raise RuntimeError("PDF rendering failed")
    return buf.getvalue()
