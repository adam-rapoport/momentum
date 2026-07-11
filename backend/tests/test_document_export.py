"""Markdown → Word/PDF export (v0.3 chunk 2): converter + endpoint."""
from __future__ import annotations

import io

import pytest

from app.core.documents.export import export_markdown

# Exercises every construct the skills actually emit: headings, inline
# formatting, links, nested + ordered lists, a GFM table, blockquote, hr,
# and a fenced code block.
MD = """# Q3 Roadmap

Intro with **bold**, *italic*, `code`, ~~dropped~~ and a [link](https://example.com).

## Items

- First bullet
  - Nested bullet
- Second bullet

1. Step one
2. Step two

| Item | Owner | Notes |
| ---- | ----- | ----- |
| Onboarding revamp | Dana | Q3 |
| Billing fix | Lee | blocked |

> A quoted decision.

---

```
code block here
```
"""


def test_docx_structure_roundtrip():
    docx = pytest.importorskip("docx")
    data = export_markdown(MD, "Q3 Roadmap", "docx")
    doc = docx.Document(io.BytesIO(data))
    paras = [p.text for p in doc.paragraphs]
    text = "\n".join(paras)

    # Body starts with its own H1 — the title must NOT be duplicated.
    assert paras[0] == "Q3 Roadmap"
    assert text.count("Q3 Roadmap") == 1

    assert "First bullet" in text
    assert "Nested bullet" in text
    assert "1. Step one" in text and "2. Step two" in text
    assert "A quoted decision." in text
    assert "code block here" in text

    assert doc.tables, "expected the GFM table to become a Word table"
    cells = [c.text for row in doc.tables[0].rows for c in row.cells]
    assert "Owner" in cells and "Onboarding revamp" in cells and "blocked" in cells

    bold_runs = [r.text for p in doc.paragraphs for r in p.runs if r.bold]
    assert any("bold" in t for t in bold_runs)


def test_docx_title_injected_only_when_missing():
    docx = pytest.importorskip("docx")
    with_title = docx.Document(io.BytesIO(export_markdown("just a paragraph", "My Title", "docx")))
    assert with_title.paragraphs[0].text == "My Title"

    own_h1 = docx.Document(io.BytesIO(export_markdown("# Own Title\n\nbody", "My Title", "docx")))
    texts = [p.text for p in own_h1.paragraphs]
    assert texts[0] == "Own Title"
    assert "My Title" not in texts


def test_pdf_contains_content():
    pypdf = pytest.importorskip("pypdf")
    data = export_markdown(MD, "Q3 Roadmap", "pdf")
    assert data.startswith(b"%PDF")
    text = "".join(p.extract_text() for p in pypdf.PdfReader(io.BytesIO(data)).pages)
    assert "Q3 Roadmap" in text
    assert "Onboarding revamp" in text and "blocked" in text
    assert "Step one" in text
    assert "A quoted decision." in text


def test_unsupported_format_raises():
    with pytest.raises(ValueError):
        export_markdown("body", "t", "rtf")


# ── endpoint (runs the real app against the migrated test DB) ──────────────

API = "/api/v1/documents/export"


def _write_doc(tmp_path, slug="q3-roadmap", title="Q3 Roadmap"):
    """Drop a document file where the seeded default project will find it.
    The `client` fixture points memory_root at tmp_path/memory, so the
    documents root resolves to tmp_path/documents (see local_store)."""
    doc_dir = tmp_path / "documents" / "default"
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / f"{slug}.md").write_text(
        f"---\ntitle: {title}\nslug: {slug}\n"
        f"created_at: 2026-07-10T00:00:00+00:00\nupdated_at: 2026-07-10T00:00:00+00:00\n---\n\n{MD}",
        encoding="utf-8",
    )


def test_export_endpoint_streams_docx_download(client, tmp_path):
    _write_doc(tmp_path)
    r = client.post(API, json={"document_id": "q3-roadmap", "format": "docx"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/vnd.openxmlformats")
    assert 'filename="q3-roadmap.docx"' in r.headers["content-disposition"]
    assert r.content[:2] == b"PK"


def test_export_endpoint_writes_dest_path(client, tmp_path):
    _write_doc(tmp_path)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    target = out_dir / "roadmap.pdf"
    r = client.post(
        API,
        json={"document_id": "q3-roadmap", "format": "pdf", "dest_path": str(target)},
    )
    assert r.status_code == 200
    assert r.json()["file_path"] == str(target)
    assert target.read_bytes().startswith(b"%PDF")


def test_export_endpoint_missing_document_404(client):
    r = client.post(API, json={"document_id": "nope", "format": "docx"})
    assert r.status_code == 404


def test_export_endpoint_rejects_bad_destinations(client, tmp_path):
    _write_doc(tmp_path)
    missing_dir = tmp_path / "not-there" / "x.docx"
    r = client.post(
        API, json={"document_id": "q3-roadmap", "format": "docx", "dest_path": str(missing_dir)}
    )
    assert r.status_code == 400

    r = client.post(
        API, json={"document_id": "q3-roadmap", "format": "docx", "dest_path": "relative/x.docx"}
    )
    assert r.status_code == 400
