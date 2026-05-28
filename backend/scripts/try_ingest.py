"""Smoke test: document ingestion (C8 onboarding upload).

Generates a small .md, .txt (and a .docx if python-docx is available),
parses each through parse_upload, then saves one as a `reference` memory
record for the seeded project. Requires Postgres + a seeded project.

Usage:
  .venv/bin/python -m scripts.try_ingest
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.default_user import get_default_project, get_default_user
from app.core.ingest import UnsupportedFileType, parse_upload
from app.core.memory.store import project_memory_dir, save_memory
from app.dependencies import SessionLocal

MD = b"# Q3 Strategy\n\nFocus: retention. Key bet: onboarding revamp.\n"
TXT = b"Stakeholders: Sarah (VP Eng), Priya (Head of Data)."


async def main() -> None:
    # 1) parser dispatch
    for name, data in [("strategy.md", MD), ("notes.txt", TXT)]:
        parsed = parse_upload(name, data)
        print(f"  parsed {name}: title={parsed.title!r} chars={len(parsed.text)}")

    # docx if available
    try:
        import io

        import docx

        buf = io.BytesIO()
        d = docx.Document()
        d.add_paragraph("Roadmap H2: ship desktop app.")
        d.save(buf)
        parsed = parse_upload("roadmap.docx", buf.getvalue())
        print(f"  parsed roadmap.docx: title={parsed.title!r} chars={len(parsed.text)} text={parsed.text!r}")
    except Exception as e:  # noqa: BLE001
        print(f"  docx skipped: {e}")

    # unsupported type
    try:
        parse_upload("image.png", b"\x89PNG")
    except UnsupportedFileType as e:
        print(f"  unsupported rejected OK: {str(e)[:50]}…")

    # 2) save one as a reference memory record
    async with SessionLocal() as db:
        user = await get_default_user(db)
        project = await get_default_project(db, user.organization_id)
        parsed = parse_upload("onboarding_strategy.md", MD)
        record = await save_memory(
            db=db,
            project=project,
            mem_type="reference",
            title=parsed.title,
            content=parsed.text,
            summary="try_ingest smoke",
            tags=["onboarding", "upload"],
        )
        await db.commit()
        print(f"\n  saved memory record id={record.id} type=reference")
        files = sorted(p.name for p in project_memory_dir(project).glob("reference_*.md"))
        print(f"  reference files on disk: {files}")


if __name__ == "__main__":
    asyncio.run(main())
