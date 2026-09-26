# Jeevia API

FastAPI + SQLAlchemy 2 on PostgreSQL (Neon in production; JSONB notes, append-only audit trigger); SQLite for quick tests. Files in Cloudinary, SMS codes via Twilio Verify. See the root README for configuration and ../docs/OPERATIONS.md for running it.

```bash
python3.12 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload     # http://localhost:8000/docs
.venv/bin/pytest -q
python -m app.seed --reset                  # rebuild the synthetic demo database
```

Configuration is via `JEEVIA_*` environment variables — see `.env.example` and `app/config.py`.
Important ones: `JEEVIA_DATABASE_URL`, `JEEVIA_JWT_SECRET`, `JEEVIA_OTP_PROVIDER` (`mock` returns the code in the
response for demos — set anything else in production and wire an SMS gateway in `routers/auth.py`),
`JEEVIA_REQUIRE_BOUND_DEVICE`, `JEEVIA_CORS_ORIGINS`.

Rules live in `app/triage/rules/*.yaml`; each rule is `{id, description, urgency, when}` where `when` combines
`all` / `any`, `text_any`, `age_gte` / `age_lt`, `category`, `vital_lt` / `vital_gte` / `vital_between`,
`severity_gte` and `duration_long`. Unknown condition keys fail loudly.

Endpoint list, role matrix and module map: [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md).
