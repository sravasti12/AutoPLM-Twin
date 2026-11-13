"""Secret-free startup stage logging through the existing security logger."""

import logging
from contextlib import contextmanager
from typing import Iterator

logger = logging.getLogger("autoplm.security")


@contextmanager
def startup_stage(stage: str) -> Iterator[None]:
    # Callers supply constant labels, never configuration or provider values.
    try:
        yield
    except Exception as exc:
        exception_class = type(exc).__name__
        logger.error(
            "security_event=startup_failed stage=%s exception_class=%s",
            stage, exception_class,
            extra={"security_event": "startup_failed", "stage": stage, "exception_class": exception_class},
        )
        raise
