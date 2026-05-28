"""Document text extraction for onboarding uploads (C8 / Sprint 7).

Turns an uploaded PDF / Word / Markdown / text file into plain text that gets
written into the memory system as onboarding context. Deliberately simple:
text only, no images/layout, with a size cap so a giant PDF can't blow up a
memory record.
"""
from __future__ import annotations

import io
from dataclasses import dataclass

MAX_CHARS = 100_000
SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".md", ".markdown", ".txt")


class UnsupportedFileType(ValueError):
    pass


@dataclass
class ParsedDocument:
    title: str
    text: str


def _strip_ext(filename: str) -> str:
    name = filename.rsplit("/", 1)[-1]
    for ext in SUPPORTED_EXTENSIONS:
        if name.lower().endswith(ext):
            return name[: -len(ext)]
    return name


def _parse_pdf(content: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(content))
    parts = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(p.strip() for p in parts if p.strip())


def _parse_docx(content: bytes) -> str:
    import docx

    document = docx.Document(io.BytesIO(content))
    return "\n".join(p.text for p in document.paragraphs if p.text.strip())


def parse_upload(filename: str, content: bytes) -> ParsedDocument:
    """Extract text from an uploaded file. Raises UnsupportedFileType for
    anything outside SUPPORTED_EXTENSIONS."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        text = _parse_pdf(content)
    elif lower.endswith(".docx"):
        text = _parse_docx(content)
    elif lower.endswith((".md", ".markdown", ".txt")):
        text = content.decode("utf-8", errors="replace")
    else:
        raise UnsupportedFileType(
            f"Unsupported file type for '{filename}'. "
            f"Supported: {', '.join(SUPPORTED_EXTENSIONS)}."
        )

    text = text.strip()[:MAX_CHARS]
    return ParsedDocument(title=_strip_ext(filename), text=text)
