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


def test_unsupported_type_raises():
    with pytest.raises(UnsupportedFileType):
        parse_upload("photo.png", b"\x89PNG\r\n")


def test_text_is_capped():
    big = ("x" * (MAX_CHARS + 5000)).encode()
    parsed = parse_upload("big.txt", big)
    assert len(parsed.text) == MAX_CHARS


def test_title_strips_path_and_ext():
    parsed = parse_upload("/tmp/sub/My Doc.markdown", b"hi")
    assert parsed.title == "My Doc"
