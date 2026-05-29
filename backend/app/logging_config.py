"""Central logging configuration.

One place to decide how the backend logs. Emits one JSON object per log
record so logs are machine-parseable — important once pMomentum ships as a
desktop app and we need to make sense of logs from someone else's machine.

Call `configure_logging()` once at startup (from the app lifespan). Modules
keep using the plain `logging.getLogger(__name__)` pattern; they inherit this
config automatically.
"""

import json
import logging

# Attributes that live on every LogRecord — anything NOT in here is treated
# as caller-supplied context (e.g. logger.info(..., extra={"session_id": ...}))
# and folded into the JSON output.
_STANDARD_ATTRS = set(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__
) | {"message", "asctime", "taskName"}


class JSONFormatter(logging.Formatter):
    """Render each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Fold in any caller-supplied context fields (session_id, user_id, …).
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """Route all logging through a single JSON handler on stdout.

    Idempotent — safe to call more than once. Also re-points uvicorn's
    loggers at the root handler so server logs share the JSON format.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # uvicorn installs its own handlers; clear them and let records propagate
    # to the root handler so everything comes out as JSON.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.handlers.clear()
        lg.propagate = True
