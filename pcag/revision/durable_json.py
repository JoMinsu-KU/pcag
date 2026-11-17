"""Publish one fsynced JSON candidate, retrying only Windows rename metadata.

The retry budget is three seconds after serialization/write/flush/fsync. It is
not a bound on SDK execution, fsync duration, or an OS call that blocks. A
transient sharing error never reserializes the receipt, rewrites its candidate,
repeats fsync, or re-enters the caller's command. Exhaustion preserves both the
previous committed receipt and the new candidate for diagnosis.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import time
import uuid
from typing import Callable

logger = logging.getLogger(__name__)
_WINDOWS_SHARING_ERRORS = {5, 32, 33}
_RETRY_BUDGET_S = 3.0


def publish_durable_json(path: Path | str, value, *, ensure_ascii: bool = False,
                         clock: Callable[[], float] | None = None,
                         sleep: Callable[[float], None] | None = None) -> None:
    """Write once and atomically replace; callers serialize writes to this path.

    ``clock`` and ``sleep`` may be injected for deterministic tests. Only native
    Windows errors 5/32/33 raised by ``os.replace`` are retryable. Other I/O or
    JSON errors propagate immediately, retaining the fail-closed caller logic.
    """
    path = Path(path)
    encoded = json.dumps(value, ensure_ascii=ensure_ascii, allow_nan=False).encode("utf-8")
    # A later UNKNOWN publication must not overwrite an exhausted candidate.
    candidate = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with candidate.open("xb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())

    now = clock or time.monotonic
    pause = sleep or time.sleep
    started = now()
    deadline = started + _RETRY_BUDGET_S
    delay = .010
    retries = 0
    while True:
        try:
            os.replace(candidate, path)
            if retries:
                logger.warning("JSON metadata publication retried %d times over %.3fs; destination=%s; no command was replayed",
                               retries, now() - started, path)
            return
        except OSError as exc:
            if getattr(exc, "winerror", None) not in _WINDOWS_SHARING_ERRORS:
                raise
            remaining = deadline - now()
            if remaining <= 0:
                raise
            pause(min(delay, remaining))
            # Do not start another replacement attempt after the budget ends.
            if now() >= deadline:
                raise
            retries += 1
            delay = min(delay * 2, .200)
