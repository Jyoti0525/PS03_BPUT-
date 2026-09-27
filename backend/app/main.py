import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .config import get_settings
from .db import SessionLocal, engine, init_db
from .observability import RequestContextMiddleware, metrics_endpoint, setup_logging
from .routers import admin, auth, directory as directory_router, encounters, facilities, files, kiosk, organisations, patients, shares

settings = get_settings()
setup_logging(settings.log_level)
log = logging.getLogger("jeevia")


def _housekeeping_loop(stop: threading.Event) -> None:
    """Hourly: purge files past their retention window and old OTP challenges. One server at a time."""
    from datetime import timedelta

    from sqlalchemy import delete

    from . import storage
    from .models import OtpChallenge
    from .services import now

    while not stop.wait(3600):
        try:
            with SessionLocal() as db:
                if engine.dialect.name == "postgresql" and not db.execute(text("SELECT pg_try_advisory_lock(7274424)")).scalar():
                    continue
                try:
                    purged = storage.purge_expired(db)
                    db.execute(delete(OtpChallenge).where(OtpChallenge.expires_at < now() - timedelta(days=2)))
                    db.commit()
                    if purged:
                        log.info("retention purge", extra={"path": str(purged)})
                finally:
                    if engine.dialect.name == "postgresql":
                        db.execute(text("SELECT pg_advisory_unlock(7274424)"))
                        db.commit()
        except Exception:
            log.exception("housekeeping failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if settings.seed_demo:
        from .seed import seed

        with SessionLocal() as db:
            seed(db)
    from . import directory

    if get_settings().directory_autoload:
        directory.load_in_background_if_empty(SessionLocal)
    stop = threading.Event()
    threading.Thread(target=_housekeeping_loop, args=(stop,), name="housekeeping", daemon=True).start()
    log.info("Jeevia API ready", extra={"path": settings.database_url.split("@")[-1]})
    yield
    stop.set()


app = FastAPI(
    title="Jeevia API",
    version="1.0.0",
    description="Human-in-the-loop triage support. Educational prototype — not a diagnostic tool. Synthetic data only.",
    lifespan=lifespan,
)

app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["Authorization", "Content-Type", "X-Device-Id", "X-Request-Id"],
    expose_headers=["Content-Disposition", "X-Request-Id"],
)

API = "/api/v1"
for r in (auth.router, facilities.router, patients.router, encounters.router, files.router, admin.router, kiosk.router, shares.router, directory_router.router, organisations.router):
    app.include_router(r, prefix=API)


@app.exception_handler(PermissionError)
async def _append_only(_: Request, exc: PermissionError):
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(Exception)
async def _unhandled(_: Request, exc: Exception):
    log.exception("unhandled error")
    return JSONResponse({"detail": "Internal error"}, status_code=500)


STARTED = time.time()


@app.get("/health", tags=["ops"])
def health():
    """Public status for the website's status panel. Never includes secrets or data."""
    from . import storage

    s = get_settings()
    t0 = time.perf_counter()
    db_ok = True
    try:
        with engine.connect() as c:
            c.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    db_ms = round((time.perf_counter() - t0) * 1000, 1)
    otp_ready = s.otp_provider != "twilio" or all([s.twilio_account_sid, s.twilio_api_key_sid, s.twilio_api_key_secret, s.twilio_verify_service_sid])
    body = {
        "status": "ok" if db_ok else "degraded",
        "version": app.version,
        "uptime_s": int(time.time() - STARTED),
        "db": {"engine": engine.dialect.name, "ok": db_ok, "latency_ms": db_ms},
        "storage": storage.health(),
        "otp": {"provider": s.otp_provider, "configured": otp_ready},
    }
    return JSONResponse(body, status_code=200 if db_ok else 503, headers={"Cache-Control": "no-store"})


app.add_api_route("/metrics", metrics_endpoint, methods=["GET"], tags=["ops"], include_in_schema=False)
