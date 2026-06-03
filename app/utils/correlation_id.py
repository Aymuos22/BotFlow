"""
Request correlation ID utilities.

Every HTTP request gets a unique correlation ID:
  - Read from ``X-Correlation-ID`` request header if present.
  - Otherwise generated as a UUID4.

The ID is stored in a ``contextvars.ContextVar`` so it is accessible
from service/repository code without being passed explicitly through
every function.  The ``JSONFormatter`` in ``logging_config.py`` reads
it automatically for every log line.
"""
import contextvars
import uuid

_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)

HEADER_NAME = "X-Correlation-ID"


def get_correlation_id() -> str:
    """Return the current request's correlation ID (empty string if not set)."""
    return _correlation_id.get()


def set_correlation_id(cid: str) -> None:
    """Store a correlation ID for the current async task."""
    _correlation_id.set(cid)


def new_correlation_id() -> str:
    """Generate a fresh UUID4 correlation ID string."""
    return str(uuid.uuid4())
