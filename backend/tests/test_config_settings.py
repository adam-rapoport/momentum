"""Desktop-mode config resolution tests (plan item 31 / T4).

Covers Settings' DATA_DIR-driven path precedence (pure, no disk), the
vault-key minting in _load_or_create_vault_key / bootstrap_data_dir
(tmp_path only — never the real data dir), and the keychain preference
order (item 23 / P3) against a fake keyring backend.
"""
from __future__ import annotations

import os

import pytest
from cryptography.fernet import Fernet

from app import config
from app.config import Settings, _load_or_create_vault_key, bootstrap_data_dir, settings


@pytest.fixture(autouse=True)
def _no_real_keyring(monkeypatch):
    """Never touch a developer machine's real keychain from the test suite.
    Tests that want a keychain opt in via `fake_keyring`."""
    monkeypatch.setattr(config, "_keyring_module", lambda: None)


class _FakeKeyring:
    """In-memory stand-in for the `keyring` module's get/set API."""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, account: str) -> str | None:
        return self.store.get((service, account))

    def set_password(self, service: str, account: str, value: str) -> None:
        self.store[(service, account)] = value


class _BrokenKeyring:
    """Backend whose every call fails (locked keychain / headless session)."""

    def get_password(self, service: str, account: str) -> str | None:
        raise RuntimeError("keychain locked")

    def set_password(self, service: str, account: str, value: str) -> None:
        raise RuntimeError("keychain locked")


@pytest.fixture
def fake_keyring(monkeypatch) -> _FakeKeyring:
    kr = _FakeKeyring()
    monkeypatch.setattr(config, "_keyring_module", lambda: kr)
    return kr


def _fresh_settings(monkeypatch, **kwargs) -> Settings:
    """Construct a Settings instance isolated from this process's env/.env.
    The test suite itself exports DATABASE_URL (see conftest) and provider
    keys, which would otherwise count as 'explicitly provided' and defeat
    the DATA_DIR-derivation under test."""
    for var in ("DATA_DIR", "DATABASE_URL", "MEMORY_ROOT"):
        monkeypatch.delenv(var, raising=False)
    return Settings(_env_file=None, **kwargs)


# ---------- DATA_DIR precedence ----------


def test_data_dir_derives_db_and_memory_paths(monkeypatch, tmp_path):
    s = _fresh_settings(monkeypatch, DATA_DIR=str(tmp_path))
    assert s.database_url == f"sqlite+aiosqlite:///{(tmp_path / 'pmomentum.db').as_posix()}"
    assert s.memory_root == (tmp_path / "memory").as_posix()


def test_explicit_database_url_beats_data_dir(monkeypatch, tmp_path):
    s = _fresh_settings(
        monkeypatch,
        DATA_DIR=str(tmp_path),
        DATABASE_URL="sqlite+aiosqlite:///explicit.db",
    )
    assert s.database_url == "sqlite+aiosqlite:///explicit.db"
    # The non-explicit field is still derived.
    assert s.memory_root == (tmp_path / "memory").as_posix()


def test_explicit_memory_root_beats_data_dir(monkeypatch, tmp_path):
    s = _fresh_settings(monkeypatch, DATA_DIR=str(tmp_path), MEMORY_ROOT="/elsewhere/mem")
    assert s.memory_root == "/elsewhere/mem"
    assert s.database_url.endswith("/pmomentum.db")


def test_no_config_at_all_falls_back_to_cwd_sqlite(monkeypatch):
    s = _fresh_settings(monkeypatch)
    assert s.database_url == "sqlite+aiosqlite:///./pmomentum.db"


def test_data_dir_expands_user_home(monkeypatch):
    s = _fresh_settings(monkeypatch, DATA_DIR="~/pm-data")
    home = os.path.expanduser("~")
    assert s.database_url.startswith(f"sqlite+aiosqlite:///{home}")


# ---------- _load_or_create_vault_key ----------


def test_vault_key_minted_and_reused(tmp_path):
    first = _load_or_create_vault_key(tmp_path)
    # It's a usable Fernet key, persisted with restrictive perms.
    Fernet(first.encode())
    key_path = tmp_path / "vault.key"
    assert key_path.read_text(encoding="utf-8").strip() == first
    assert (key_path.stat().st_mode & 0o777) == 0o600

    # Second call returns the SAME key — rotating would brick the vault.
    assert _load_or_create_vault_key(tmp_path) == first
    # No leftover tmp files from the atomic write.
    assert [p.name for p in tmp_path.iterdir()] == ["vault.key"]


def test_vault_key_empty_file_recovers_with_fresh_key(tmp_path):
    """A zero-byte vault.key (crash / full disk during first launch) must be
    treated as absent, not returned as an empty 'key'."""
    (tmp_path / "vault.key").write_text("", encoding="utf-8")
    key = _load_or_create_vault_key(tmp_path)
    assert key
    Fernet(key.encode())
    assert (tmp_path / "vault.key").read_text(encoding="utf-8").strip() == key


def test_vault_key_whitespace_only_file_recovers(tmp_path):
    (tmp_path / "vault.key").write_text("  \n", encoding="utf-8")
    key = _load_or_create_vault_key(tmp_path)
    Fernet(key.encode())


# ---------- keychain preference order (item 23 / P3) ----------


def test_fresh_key_minted_into_keychain_leaves_no_file(tmp_path, fake_keyring):
    key = _load_or_create_vault_key(tmp_path)
    Fernet(key.encode())
    # Stored under the documented service/account…
    assert fake_keyring.store[("pMomentum", "vault-key")] == key
    # …and crucially NO plaintext key file on disk (the point of P3).
    assert not (tmp_path / "vault.key").exists()
    # Stable across calls.
    assert _load_or_create_vault_key(tmp_path) == key


def test_existing_file_key_migrates_into_keychain_and_keeps_file(
    tmp_path, fake_keyring
):
    file_key = Fernet.generate_key().decode()
    (tmp_path / "vault.key").write_text(file_key, encoding="utf-8")

    assert _load_or_create_vault_key(tmp_path) == file_key
    # Pushed into the keychain (migration)…
    assert fake_keyring.store[("pMomentum", "vault-key")] == file_key
    # …but the file stays for rollback to a pre-keychain build.
    assert (tmp_path / "vault.key").read_text(encoding="utf-8") == file_key


def test_keychain_key_wins_over_file(tmp_path, fake_keyring):
    fake_keyring.store[("pMomentum", "vault-key")] = "keychain-key"
    (tmp_path / "vault.key").write_text("stale-file-key", encoding="utf-8")
    assert _load_or_create_vault_key(tmp_path) == "keychain-key"


def test_broken_keyring_backend_degrades_to_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "_keyring_module", lambda: _BrokenKeyring())
    key = _load_or_create_vault_key(tmp_path)
    Fernet(key.encode())
    # Fell back to the original file path, perms and all.
    key_path = tmp_path / "vault.key"
    assert key_path.read_text(encoding="utf-8").strip() == key
    assert (key_path.stat().st_mode & 0o777) == 0o600
    assert _load_or_create_vault_key(tmp_path) == key


# ---------- bootstrap_data_dir ----------


def test_bootstrap_creates_dir_and_mints_key(monkeypatch, tmp_path):
    root = tmp_path / "appdata" / "pMomentum"  # not yet created
    monkeypatch.setattr(settings, "data_dir", str(root))
    monkeypatch.setattr(settings, "credential_vault_key", None)

    bootstrap_data_dir()

    assert root.is_dir()
    assert settings.credential_vault_key
    assert (root / "vault.key").read_text(encoding="utf-8").strip() == settings.credential_vault_key


def test_bootstrap_respects_explicit_vault_key(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(settings, "credential_vault_key", "explicit-key")

    bootstrap_data_dir()

    assert settings.credential_vault_key == "explicit-key"
    assert not (tmp_path / "vault.key").exists()


def test_bootstrap_noop_without_data_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "data_dir", None)
    monkeypatch.setattr(settings, "credential_vault_key", None)

    bootstrap_data_dir()

    assert settings.credential_vault_key is None
