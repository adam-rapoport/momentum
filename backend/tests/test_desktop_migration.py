"""The 2026-07 pMomentum→Momentum rename must not strand an existing install's
data: app.desktop._migrate_legacy_data renames the old default data folder and
the SQLite files inside whatever folder was resolved. Pure-rename semantics:
never merge, never clobber, never copy or delete.
"""
from pathlib import Path

from app.desktop import _migrate_legacy_data


def _make_legacy_dir(parent: Path) -> Path:
    legacy = parent / "pMomentum"
    legacy.mkdir()
    (legacy / "pmomentum.db").write_bytes(b"db")
    (legacy / "pmomentum.db-wal").write_bytes(b"wal")
    (legacy / "memory").mkdir()
    (legacy / "memory" / "note.md").write_text("hi", encoding="utf-8")
    return legacy


def test_default_dir_and_db_files_renamed(tmp_path):
    _make_legacy_dir(tmp_path)
    new_dir = tmp_path / "Momentum"

    _migrate_legacy_data(new_dir, explicit=False)

    assert not (tmp_path / "pMomentum").exists()
    assert (new_dir / "momentum.db").read_bytes() == b"db"
    assert (new_dir / "momentum.db-wal").read_bytes() == b"wal"
    # Everything else (memory, documents, vault.key) rides along untouched.
    assert (new_dir / "memory" / "note.md").read_text(encoding="utf-8") == "hi"


def test_explicit_data_dir_folder_left_alone_but_db_renamed(tmp_path):
    # An explicit DATA_DIR points at the user's own folder: not ours to move,
    # but the DB inside it still needs its new name.
    explicit_dir = _make_legacy_dir(tmp_path)

    _migrate_legacy_data(explicit_dir, explicit=True)

    assert explicit_dir.exists()
    assert (explicit_dir / "momentum.db").read_bytes() == b"db"
    assert not (explicit_dir / "pmomentum.db").exists()


def test_existing_new_dir_never_merged_or_clobbered(tmp_path):
    _make_legacy_dir(tmp_path)
    new_dir = tmp_path / "Momentum"
    new_dir.mkdir()
    (new_dir / "momentum.db").write_bytes(b"new")

    _migrate_legacy_data(new_dir, explicit=False)

    # Both survive: legacy folder is not merged in, the new DB not clobbered.
    assert (tmp_path / "pMomentum" / "pmomentum.db").read_bytes() == b"db"
    assert (new_dir / "momentum.db").read_bytes() == b"new"


def test_new_db_name_never_clobbered_inside_one_dir(tmp_path):
    d = tmp_path / "Momentum"
    d.mkdir()
    (d / "pmomentum.db").write_bytes(b"old")
    (d / "momentum.db").write_bytes(b"new")

    _migrate_legacy_data(d, explicit=False)

    assert (d / "pmomentum.db").read_bytes() == b"old"
    assert (d / "momentum.db").read_bytes() == b"new"


def test_noop_on_fresh_install(tmp_path):
    new_dir = tmp_path / "Momentum"
    _migrate_legacy_data(new_dir, explicit=False)
    assert not new_dir.exists()  # bootstrap_data_dir creates it later
