import logging
import sys


def setup_logging(level: str = "INFO", fmt: str | None = None) -> None:
    """Configure root logger. Call once at application startup."""
    log_format = fmt or "%(asctime)s %(name)-30s %(levelname)-8s %(message)s"
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        stream=sys.stderr,
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. Modules can also use logging.getLogger(__name__) directly."""
    return logging.getLogger(name)
