"""Loguru-based logging (adapted from the project's logging template).

One stderr sink (Docker captures stdout/stderr — no log files in the image),
plus an InterceptHandler so all stdlib logging (uvicorn, httpx, openai,
sqlalchemy, alembic) flows through loguru with a single format. Noisy
per-request loggers (httpx/openai) are pinned to WARNING so a provider error
shows once, at the right level — not buried in INFO request lines.

Call setup_logging() once at startup (the app lifespan does this).
"""

from __future__ import annotations

import logging
import os
import sys

from loguru import logger

logger.remove()

_LEVEL_ABBR = {
    "TRACE": "TRC", "DEBUG": "DBG", "INFO": "INF", "SUCCESS": "SUC",
    "WARNING": "WRN", "ERROR": "ERR", "CRITICAL": "CRT",
}

_is_prod = os.getenv("ENVIRONMENT", "dev") == "prod"


def _console_format(record: dict) -> str:
    abbr = _LEVEL_ABBR.get(record["level"].name, record["level"].name[:3])
    return (
        "<green>{time:HH:mm:ss.SSS}</green>  "
        f"<level>{abbr}</level>  "
        "<level>{message}</level>\n"
        "{exception}"
    )


logger.add(
    sink=sys.stderr,
    format=_console_format,
    colorize=not _is_prod,
    level="INFO" if _is_prod else "DEBUG",
    backtrace=True,
    diagnose=not _is_prod,
)


class InterceptHandler(logging.Handler):
    """Redirect Python stdlib logging into loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


# Per-request loggers that would otherwise spam INFO (incl. the line that made a
# 400 look like an INFO event). Pinned to WARNING.
_NOISY = ("httpx", "httpcore", "openai", "urllib3", "sqlalchemy.engine")


def setup_logging() -> None:
    """Route all stdlib logging through loguru. Idempotent; call once at startup."""
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    # Re-point every existing logger (uvicorn.*, etc.) at the root interceptor.
    for name in list(logging.root.manager.loggerDict):
        lg = logging.getLogger(name)
        lg.handlers = []
        lg.propagate = True
    for noisy in _NOISY:
        logging.getLogger(noisy).setLevel(logging.WARNING)


__all__ = ["logger", "setup_logging", "InterceptHandler"]
