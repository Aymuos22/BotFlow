"""
Structured JSON logging configuration.

Sets up a consistent log format across the entire application.
Log level is driven by the ``LOG_LEVEL`` environment variable.
"""
import logging
import sys
from typing import Any


class JSONFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON strings.

    Fields emitted per record:
        timestamp, level, logger, message, [extra fields]
    """

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, timezone

        log_data: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include any extra fields attached via logger.info("...", extra={...})
        _RESERVED = {
            "args", "asctime", "created", "exc_info", "exc_text",
            "filename", "funcName", "id", "levelname", "levelno",
            "lineno", "module", "msecs", "message", "msg", "name",
            "pathname", "process", "processName", "relativeCreated",
            "stack_info", "thread", "threadName", "taskName",
            # JSONFormatter-added fields (avoid double-emission)
            "timestamp", "level", "logger",
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                log_data[key] = value

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)


def setup_logging(log_level: str = "INFO") -> None:
    """
    Configure root logger with a JSON formatter writing to stdout.

    Call once at application start-up (inside ``create_app()``).
    """
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    handler.setLevel(numeric_level)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove existing handlers to avoid duplicate output
    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Quieten noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger (convenience wrapper)."""
    return logging.getLogger(name)
