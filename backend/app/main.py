import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .config import get_settings
from .db import SessionLocal, engine, init_db
from .observability import RequestContextMiddleware, metrics_endpoint, setup_logging
from .routers import admin, auth, encounters, facilities, files, kiosk, patients

settings = get_settings()
setup_logging(settings.log_level)
log = logging.getLogger("jeevia")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    if settings.seed_demo:
        from .seed import seed

        with SessionLocal() as db:
            seed(db)
    log.info("Jeevia API ready", extra={"path": settings.database_url.split("@")[-1]})
    yield


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
for r in (auth.router, facilities.router, patients.router, encounters.router, files.router, admin.router, kiosk.router):
    app.include_router(r, prefix=API)


@app.exception_handler(PermissionError)
async def _append_only(_: Request, exc: PermissionError):
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(Exception)
async def _unhandled(_: Request, exc: Exception):
    log.exception("unhandled error")
    return JSONResponse({"detail": "Internal error"}, status_code=500)


@app.get("/health", tags=["ops"])
def health():
    with engine.connect() as c:
        c.execute(text("SELECT 1"))
    from . import storage

    s = get_settings()
    return {"status": "ok", "db": engine.dialect.name, "storage": s.storage_backend, "otp": s.otp_provider, "version": app.version}


app.add_api_route("/metrics", metrics_endpoint, methods=["GET"], tags=["ops"], include_in_schema=False)
