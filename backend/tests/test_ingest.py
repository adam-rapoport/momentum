"""Unit tests for document ingestion (C8 onboarding upload)."""
from __future__ import annotations

import io

import pytest

from app.core.ingest import MAX_CHARS, UnsupportedFileType, parse_upload


def test_parse_markdown():
    parsed = parse_upload("Q3 Plan.md", b"# Heading\n\nbody text")
    assert parsed.title == "Q3 Plan"
    assert "body text" in parsed.text


def test_parse_txt():
    parsed = parse_upload("notes.txt", b"plain notes")
    assert parsed.title == "notes"
    assert parsed.text == "plain notes"


def test_parse_docx_roundtrip():
    docx = pytest.importorskip("docx")
    buf = io.BytesIO()
    doc = docx.Document()
    doc.add_paragraph("Roadmap: ship desktop app.")
    doc.save(buf)
    parsed = parse_upload("roadmap.docx", buf.getvalue())
    assert parsed.title == "roadmap"
    assert "desktop app" in parsed.text


def test_parse_pptx_roundtrip():
    pptx = pytest.importorskip("pptx")
    prs = pptx.Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])  # Title and Content
    slide.shapes.title.text = "Q3 Kickoff"
    slide.placeholders[1].text_frame.text = "Ship the desktop app"
    slide.notes_slide.notes_text_frame.text = "mention the beta list"
    buf = io.BytesIO()
    prs.save(buf)
    parsed = parse_upload("kickoff.pptx", buf.getvalue())
    assert parsed.title == "kickoff"
    assert "Slide 1:" in parsed.text
    assert "Q3 Kickoff" in parsed.text
    assert "Ship the desktop app" in parsed.text
    assert "Notes: mention the beta list" in parsed.text


def test_parse_xlsx_roundtrip():
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Metrics"
    ws.append(["Metric", "Value"])
    ws.append(["Weekly actives", 1250])
    ws2 = wb.create_sheet("Notes")
    ws2.append(["Churn ticked up in June"])
    buf = io.BytesIO()
    wb.save(buf)
    parsed = parse_upload("metrics.xlsx", buf.getvalue())
    assert parsed.title == "metrics"
    assert "Sheet: Metrics" in parsed.text
    assert "Metric | Value" in parsed.text
    assert "Weekly actives | 1250" in parsed.text
    assert "Sheet: Notes" in parsed.text
    assert "Churn ticked up in June" in parsed.text


def test_parse_xlsx_row_cap():
    openpyxl = pytest.importorskip("openpyxl")
    from app.core.ingest import MAX_ROWS_PER_SHEET

    wb = openpyxl.Workbook()
    ws = wb.active
    for i in range(MAX_ROWS_PER_SHEET + 50):
        ws.append([f"row-{i}"])
    buf = io.BytesIO()
    wb.save(buf)
    parsed = parse_upload("big.xlsx", buf.getvalue())
    assert f"[truncated at {MAX_ROWS_PER_SHEET} rows]" in parsed.text
    assert f"row-{MAX_ROWS_PER_SHEET}" not in parsed.text


def test_parse_csv():
    parsed = parse_upload("okrs.csv", b'objective,owner\n"Grow, fast",adam\n')
    assert parsed.title == "okrs"
    assert "objective | owner" in parsed.text
    assert "Grow, fast | adam" in parsed.text


def test_parse_tsv():
    parsed = parse_upload("list.tsv", b"a\tb\n1\t2\n")
    assert parsed.text == "a | b\n1 | 2"


def test_unsupported_type_raises():
    with pytest.raises(UnsupportedFileType):
        parse_upload("photo.png", b"\x89PNG\r\n")


def test_legacy_office_formats_rejected():
    for name in ("deck.ppt", "sheet.xls"):
        with pytest.raises(UnsupportedFileType):
            parse_upload(name, b"\xd0\xcf\x11\xe0")


def test_text_is_capped():
    big = ("x" * (MAX_CHARS + 5000)).encode()
    parsed = parse_upload("big.txt", big)
    assert len(parsed.text) == MAX_CHARS


def test_title_strips_path_and_ext():
    parsed = parse_upload("/tmp/sub/My Doc.markdown", b"hi")
    assert parsed.title == "My Doc"
