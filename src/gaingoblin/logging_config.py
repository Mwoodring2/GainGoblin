"""Safe local logging configuration for Gain Goblin."""

from __future__ import annotations

import logging
import re
from collections.abc import Iterable
from logging.handlers import RotatingFileHandler
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SENSITIVE_PARAM_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "api-key",
        "token",
        "secret",
        "password",
        "access_token",
        "auth",
        "authorization",
    }
)

_SENSITIVE_ASSIGNMENT = re.compile(
    r"(?i)\b("
    + "|".join(re.escape(name) for name in sorted(SENSITIVE_PARAM_NAMES))
    + r")\b\s*[:=]\s*([^\s,;]+)"
)


def redact_text(text: str) -> str:
    """Redact credential-like values from free-form log text."""
    if not text:
        return text
    redacted = _SENSITIVE_ASSIGNMENT.sub(r"\1=[REDACTED]", text)
    if "://" in redacted and ("?" in redacted or "&" in redacted):
        redacted = redact_url(redacted)
    return redacted


def redact_url(url: str) -> str:
    """Strip credential query parameters from a URL before logging."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "[REDACTED_URL]"
    if not parts.query:
        return url
    safe_pairs: list[tuple[str, str]] = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() in SENSITIVE_PARAM_NAMES:
            safe_pairs.append((key, "[REDACTED]"))
        else:
            safe_pairs.append((key, value))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(safe_pairs), parts.fragment))


class RedactingFilter(logging.Filter):
    """Ensure credentials never appear in rendered log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True
        redacted = redact_text(message)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def configure_logging(
    log_dir: Path | None = None,
    *,
    level: int = logging.INFO,
    logger_names: Iterable[str] | None = None,
) -> Path:
    """Configure rotating file logging under ``logs/`` and return the log path."""
    directory = Path(log_dir) if log_dir is not None else Path("logs")
    directory.mkdir(parents=True, exist_ok=True)
    log_path = directory / "gaingoblin.log"

    root = logging.getLogger()
    root.setLevel(level)

    redactor = RedactingFilter()
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    already_configured = any(
        isinstance(handler, RotatingFileHandler)
        and Path(getattr(handler, "baseFilename", "")) == log_path.resolve()
        for handler in root.handlers
    )
    if not already_configured:
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(redactor)
        root.addHandler(file_handler)

    for name in logger_names or ("gaingoblin",):
        logging.getLogger(name).setLevel(level)

    logging.getLogger("gaingoblin").info("Logging configured path=%s", log_path)
    return log_path
