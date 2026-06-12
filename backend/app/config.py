import os
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _detect_local_timezone() -> str:
    """Best-effort IANA timezone name for the machine running the app.

    The desktop backend runs on the user's own machine, so the OS timezone
    IS the user's timezone — no config required. We resolve it from the
    `/etc/localtime` symlink (works on macOS and Linux), which points at a
    zoneinfo file like ``.../zoneinfo/America/Los_Angeles``. If we can't
    resolve a valid name (e.g. Windows, or an unusual setup), fall back to a
    fixed default so ``ZoneInfo()`` never fails downstream. An explicit
    USER_TIMEZONE env var always overrides this (see the field below).
    """
    fallback = "America/Los_Angeles"
    localtime = Path("/etc/localtime")
    try:
        if localtime.is_symlink():
            target = os.readlink(localtime)
            if "zoneinfo/" in target:
                name = target.split("zoneinfo/", 1)[1]
                ZoneInfo(name)  # validate; raises if not a real zone
                return name
    except Exception:
        pass
    return fallback


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Per-user writable folder for the desktop build. The desktop launcher
    # (app/desktop.py) sets this to e.g. ~/Library/Application Support/pMomentum
    # before the app imports. When set, the SQLite DB, memory/documents, and the
    # credential vault key all root here. Unset (web dev) → the explicit/relative
    # defaults below apply unchanged. This is config precedence, not a flag.
    data_dir: str | None = Field(None, alias="DATA_DIR")

    # Optional so the app can boot with no config: resolution is explicit env
    # var > derived from DATA_DIR > a self-contained SQLite file in the cwd
    # (matches .env.example). Always a real string after _apply_data_dir runs.
    database_url: str | None = Field(None, alias="DATABASE_URL")

    # Optional at import. Since C8 (the Connections UI), API keys resolve
    # stored-key→env-fallback at call time (app.core.credentials), not at
    # startup — so a fresh desktop user with no key can still boot to the
    # onboarding wizard and enter it there.
    groq_api_key: str | None = Field(None, alias="GROQ_API_KEY")
    groq_model: str = Field(
        "meta-llama/llama-4-scout-17b-16e-instruct", alias="GROQ_MODEL"
    )
    # "Heavy" model used for drafting turns (see app.core.model_router).
    # Name kept as `groq_heavy_model` for compatibility; the value can now
    # be ANY provider's model ID (Groq, Google, ...). Provider is inferred
    # from the model-name prefix by app.core.llm.
    # Sprint 4 sequence: Groq free-tier heavy models all hit per-model TPM
    # ceilings on our ~9k token drafting prompt. Gemini 3 Flash Preview
    # works for single turns but Gemini 3 preview models require a
    # `thought_signature` on tool-call history that the OpenAI-compat
    # endpoint doesn't surface — breaks on the second turn of any
    # tool-using skill workflow. Landed on gemini-2.5-flash: stable (not
    # preview), no thought_signature requirement, still a real quality
    # step up over Scout for drafting.
    # Upgrade path for later:
    # - gemini-2.5-pro (stable, stronger writing, free tier)
    # - gemini-3.x models (would need native Gen AI SDK, ~1 day of work
    #   to replace the OpenAI-compat client — see chunk writeup)
    # Env var alias stays GROQ_HEAVY_MODEL to avoid breaking existing .env
    # files; rename on next sprint if we keep accumulating providers.
    groq_heavy_model: str = Field(
        "gemma-4-31b-it", alias="GROQ_HEAVY_MODEL"
    )
    groq_base_url: str = Field("https://api.groq.com/openai/v1", alias="GROQ_BASE_URL")

    app_env: str = Field("development", alias="APP_ENV")
    frontend_origin: str = Field("http://localhost:3000", alias="FRONTEND_ORIGIN")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    # Optional Sentry crash reporting. OFF unless a DSN is supplied — a
    # privacy-respecting desktop app must not phone home without opt-in.
    sentry_dsn: str | None = Field(None, alias="SENTRY_DSN")

    # Defaults to the machine's own timezone (the desktop backend runs on the
    # user's computer). Set USER_TIMEZONE to override (e.g. server deploys).
    user_timezone: str = Field(default_factory=_detect_local_timezone, alias="USER_TIMEZONE")
    tavily_api_key: str | None = Field(None, alias="TAVILY_API_KEY")
    memory_root: str = Field("pmomentum/data/memory", alias="MEMORY_ROOT")

    # Google Docs integration (Sprint 3 Chunk D). All optional — if any of
    # these are missing, the `/integrations/google/connect` endpoint returns
    # a clear "not configured" error rather than crashing at startup.
    google_client_id: str | None = Field(None, alias="GOOGLE_CLIENT_ID")
    google_client_secret: str | None = Field(None, alias="GOOGLE_CLIENT_SECRET")
    google_redirect_uri: str = Field(
        "http://localhost:8000/api/v1/integrations/google/callback",
        alias="GOOGLE_REDIRECT_URI",
    )

    # Fernet key for encrypting OAuth tokens at rest. Must be a urlsafe
    # base64-encoded 32-byte key (generate with
    # `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
    # Optional at startup — only required when we actually encrypt/decrypt.
    credential_vault_key: str | None = Field(None, alias="CREDENTIAL_VAULT_KEY")

    # Google AI Studio (Gemini / Gemma) API key. Optional at startup — only
    # required if the model router sends a turn to a Google-hosted model.
    google_ai_api_key: str | None = Field(None, alias="GOOGLE_AI_API_KEY")

    # OpenAI API key (paid). Optional — only required if the user picks an
    # OpenAI model (gpt-*) in Settings. Talks to api.openai.com directly.
    openai_api_key: str | None = Field(None, alias="OPENAI_API_KEY")

    # Anthropic API key (paid). Optional — only required if the user picks a
    # Claude model in Settings. Served via the official anthropic SDK.
    anthropic_api_key: str | None = Field(None, alias="ANTHROPIC_API_KEY")

    # OpenRouter API key (pay-as-you-go aggregator). Optional — only required
    # if the user picks an OpenRouter model (vendor/model ids) in Settings.
    openrouter_api_key: str | None = Field(None, alias="OPENROUTER_API_KEY")

    # Mistral API key. Optional — only required if the user picks a Mistral
    # model (mistral-*-latest) in Settings.
    mistral_api_key: str | None = Field(None, alias="MISTRAL_API_KEY")

    # Ollama server base URL for local models (e.g. http://localhost:11434).
    # Deliberately NO default: a non-None value would make every fresh install
    # look "configured" to onboarding even with no Ollama running. Users
    # connect Ollama in Settings (stored like a key) or set this explicitly.
    ollama_base_url: str | None = Field(None, alias="OLLAMA_BASE_URL")

    # Perplexity API key for the WebSearch tool's Perplexity provider option
    # (alternative to Tavily). Optional — only required if the user picks
    # Perplexity as their search provider (see app.core.search).
    perplexity_api_key: str | None = Field(None, alias="PERPLEXITY_API_KEY")

    # Per-launch shared secret for the local API (see app.security). The Tauri
    # shell generates it and passes it to the sidecar via this env var and to
    # the webview over IPC. When set, /api requests must carry it in the
    # X-PMomentum-Token header and WS connects in the `token` query param.
    # Unset (web dev, tests) the token check is skipped.
    auth_token: str | None = Field(None, alias="PMOMENTUM_AUTH_TOKEN")

    @model_validator(mode="after")
    def _resolve_paths(self) -> "Settings":
        """Derive DB/memory paths from DATA_DIR. Pure & side-effect-free.

        Precedence: an explicitly-provided value (env or .env) always wins; else
        a value derived from DATA_DIR (desktop); else a built-in default. We
        detect "explicitly provided" via `model_fields_set` (verified: env- and
        .env-sourced fields appear there; defaults don't). Snapshot it BEFORE we
        assign anything, since assigning also adds the field to that set.

        This runs at construction (before app.dependencies builds the engine),
        but touches no disk and mints no secrets — those happen later in
        bootstrap_data_dir(), called explicitly from the app lifespan.
        """
        explicit = set(self.model_fields_set)
        if self.data_dir:
            root = Path(self.data_dir).expanduser()
            # as_posix() keeps the SQLite URL valid on Windows (C:/...) too.
            if "database_url" not in explicit:
                self.database_url = f"sqlite+aiosqlite:///{(root / 'pmomentum.db').as_posix()}"
            if "memory_root" not in explicit:
                # get_memory_root() picks up an absolute path via its existing
                # `if p.is_absolute()` branch; documents derive from it.
                self.memory_root = (root / "memory").as_posix()
        # Guarantee a usable DB URL even with no DATA_DIR and no DATABASE_URL, so
        # the app boots out of the box (SQLite is the project default).
        if not self.database_url:
            self.database_url = "sqlite+aiosqlite:///./pmomentum.db"
        return self


settings = Settings()


# --- credential vault key storage (item 23, finding P3) ----------------------
# Preference order: OS keychain (macOS Keychain via `keyring`) > vault.key
# file. The file was a plaintext Fernet key sitting next to the very DB it
# encrypts; the keychain keeps it behind the user's login session instead.
# `keyring` ships only with the desktop extra — when it's absent (Linux CI,
# web dev) or its backend fails (headless session, locked keychain), every
# helper degrades silently to the file path, which is byte-for-byte the old
# behavior.
_KEYRING_SERVICE = "pMomentum"
_KEYRING_ACCOUNT = "vault-key"


def _keyring_module():
    """The `keyring` module, or None when not installed. Separate function so
    tests can monkeypatch a fake backend in."""
    try:
        import keyring
    except ImportError:
        return None
    return keyring


def _keychain_get_key() -> str | None:
    kr = _keyring_module()
    if kr is None:
        return None
    try:
        return kr.get_password(_KEYRING_SERVICE, _KEYRING_ACCOUNT) or None
    except Exception:  # noqa: BLE001 — any backend failure means "no keychain"
        return None


def _keychain_store_key(key: str) -> bool:
    kr = _keyring_module()
    if kr is None:
        return False
    try:
        kr.set_password(_KEYRING_SERVICE, _KEYRING_ACCOUNT, key)
    except Exception:  # noqa: BLE001 — best-effort; file remains the fallback
        return False
    return True


def _load_or_create_vault_key(root: Path) -> str:
    """Return the credential vault key, minting one if absent.

    Resolution order:
      1. OS keychain entry (service "pMomentum" / account "vault-key").
      2. `vault.key` file under `root` — the pre-keychain location. Its key
         is pushed INTO the keychain (migration) but the file is kept so the
         user can roll back to an older build that only reads the file.
      3. Mint a fresh key: stored in the keychain when available, else
         written to the file (atomically, 0600) exactly as before.

    Treats an empty/truncated file as absent (a half-written key from a
    crash or full disk must not brick the vault)."""
    keychain_key = _keychain_get_key()
    if keychain_key:
        return keychain_key

    key_path = root / "vault.key"
    if key_path.exists():
        existing = key_path.read_text(encoding="utf-8").strip()
        if existing:
            # Migrate into the keychain; keep the file for rollback.
            _keychain_store_key(existing)
            return existing
        # else: empty/truncated → fall through and mint a fresh key

    from cryptography.fernet import Fernet

    new_key = Fernet.generate_key().decode("utf-8")
    if _keychain_store_key(new_key):
        return new_key  # keychain-only — no plaintext key on disk

    tmp = root / f"vault.key.{os.getpid()}.tmp"
    tmp.write_text(new_key, encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except OSError:
        pass  # best-effort; some filesystems/platforms lack POSIX perms
    os.replace(tmp, key_path)  # atomic publish
    return new_key


def bootstrap_data_dir() -> None:
    """Prepare the per-user data dir: create it and ensure a credential vault
    key exists. Explicit (called once from the app lifespan), NOT an import
    side effect — so importing app.config never touches disk or mints secrets.
    No-op unless DATA_DIR is set (web dev). Idempotent; an explicit
    CREDENTIAL_VAULT_KEY always wins."""
    if not settings.data_dir:
        return
    root = Path(settings.data_dir).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    if not settings.credential_vault_key:
        settings.credential_vault_key = _load_or_create_vault_key(root)
