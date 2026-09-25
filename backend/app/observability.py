"""Structured JSON logging, request ids and minimal Prometheus-format metrics (H8).

Logs never contain request bodies, so symptoms, names and phone numbers stay out of log files.
"""

import json
import logging
import sys
import threading
import time
import uuid
from collections import defaultdict
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

request_id: ContextVar[str] = ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)) + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id.get(),
        }
        for k in ("method", "path", "status", "duration_ms", "user_role"):
            if hasattr(record, k):
                out[k] = getattr(record, k)
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [h]
    root.setLevel(level)
    logging.getLogger("uvicorn.access").disabled = True  # replaced by our access log


log = logging.getLogger("jeevia.http")


class Metrics:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.requests: dict[tuple[str, str, int], int] = defaultdict(int)
        self.latency_sum: dict[tuple[str, str], float] = defaultdict(float)
        self.latency_count: dict[tuple[str, str], int] = defaultdict(int)
        self.started = time.time()

    def observe(self, method: str, route: str, status: int, seconds: float) -> None:
        with self._lock:
            self.requests[(method, route, status)] += 1
            self.latency_sum[(method, route)] += seconds
            self.latency_count[(method, route)] += 1

    def render(self) -> str:
        lines = [
            "# HELP jeevia_http_requests_total HTTP requests by route and status",
            "# TYPE jeevia_http_requests_total counter",
        ]
        with self._lock:
            for (m, r, s), n in sorted(self.requests.items()):
                lines.append(f'jeevia_http_requests_total{{method="{m}",route="{r}",status="{s}"}} {n}')
            lines += ["# HELP jeevia_http_request_seconds Request latency", "# TYPE jeevia_http_request_seconds summary"]
            for (m, r), total in sorted(self.latency_sum.items()):
                lines.append(f'jeevia_http_request_seconds_sum{{method="{m}",route="{r}"}} {total:.6f}')
                lines.append(f'jeevia_http_request_seconds_count{{method="{m}",route="{r}"}} {self.latency_count[(m, r)]}')
        lines += ["# TYPE jeevia_uptime_seconds gauge", f"jeevia_uptime_seconds {time.time() - self.started:.0f}"]
        return "\n".join(lines) + "\n"


metrics = Metrics()


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("X-Request-Id") or uuid.uuid4().hex[:16]
        token = request_id.set(rid)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-Id"] = rid
            return response
        finally:
            dur = time.perf_counter() - start
            route = request.scope.get("route")
            path = getattr(route, "path", request.url.path)
            metrics.observe(request.method, path, status, dur)
            log.info("request", extra={"method": request.method, "path": path, "status": status, "duration_ms": round(dur * 1000, 1)})
            request_id.reset(token)


def metrics_endpoint() -> PlainTextResponse:
    return PlainTextResponse(metrics.render(), media_type="text/plain; version=0.0.4")
