"""Request rate limits: per device (X-Device-Id) or client address, and per phone number.

A sliding one-minute window kept in memory. One API process serves a facility, so this is enough here; several
processes behind a load balancer would share a Redis counter instead. Limits are in config.py (rate_per_min_*).
A 429 carries Retry-After and is logged; the caller's data is never written to the log.
"""

import logging
import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

from .config import get_settings

log = logging.getLogger("jeevia.ratelimit")
_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def reset() -> None:
    with _lock:
        _hits.clear()


def client_key(request: Request) -> str:
    device = request.headers.get("x-device-id", "")[:64]
    host = request.client.host if request.client else "unknown"
    return f"{host}|{device}"


def hit(key: str, limit: int, window_s: int = 60) -> None:
    """Count one request under `key`; refuse with 429 once `limit` requests fall within the window."""
    if not get_settings().rate_limit or limit <= 0:
        return
    now = time.monotonic()
    with _lock:
        q = _hits[key]
        while q and q[0] <= now - window_s:
            q.popleft()
        if len(q) >= limit:
            retry = int(q[0] + window_s - now) + 1
            log.warning("rate limit", extra={"path": key.split(":", 1)[0]})
            raise HTTPException(429, "Too many requests. Please wait a minute and try again.", headers={"Retry-After": str(retry)})
        q.append(now)


def limit(group: str):
    """FastAPI dependency: `dependencies=[Depends(limit("ai"))]`. Groups: public, ai, upload, auth."""

    def dep(request: Request) -> None:
        hit(f"{group}:{client_key(request)}", getattr(get_settings(), f"rate_per_min_{group}"))

    return dep


def per_phone(phone: str | None, group: str = "phone") -> None:
    if phone:
        hit(f"{group}:{phone.strip()[-10:]}", get_settings().rate_per_phone_10min, 600)
