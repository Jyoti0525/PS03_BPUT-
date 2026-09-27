# Jeevia — operations runbook

For whoever keeps Jeevia running: deploys, status, keys, database and data.

## Services at a glance

| Service | Where | Identifier |
|---|---|---|
| Web app | Vercel | project `jeevia-triage` → https://jeevia-triage.vercel.app |
| API | Render (Singapore, free plan) | web service `jeevia-api` (`srv-daruvjp7lnhs73euubf0`) → https://jeevia-api.onrender.com |
| Database | Neon (`aws-ap-southeast-1`, PostgreSQL 18) | project `jeevia` (`empty-dream-42914552`), database `jeevia`, role `jeevia` |
| SMS codes | Twilio Verify | service "Jeevia" (`VA074dc…`) |
| Files | Cloudinary | folder `jeevia/<facility>/<yyyy-mm>/<kind>/`, authenticated delivery |
| CI and keep-alive | GitHub Actions | `ci.yml`, `keepalive.yml` in both repositories |

## Is it up?

- Open https://jeevia-triage.vercel.app/#status — API, database, SMS and storage, refreshed every 20 s.
- Or `curl https://jeevia-api.onrender.com/health` — `status`, `db.latency_ms`, `storage.backend`, `otp.configured`, `uptime_s`.
- `/metrics` exposes Prometheus counters and latency per route.

**Server asleep.** Press **Wake server** on the status panel (any visitor can); it pings until the API answers,
usually 30–60 s. The keep-alive workflow pings every 10 minutes so this should be rare. GitHub pauses scheduled
workflows after 60 days without commits — re-enable it from the Actions tab if that happens.

**Server stuck.** Sign in as a supervisor and press **Restart server** on the status panel. The request goes through
the web app's server route (`frontend/src/app/api/ops/restart/route.ts`), which checks the supervisor's session and
calls Render; the Render key never reaches a browser. One restart per minute.

## Deploying

| What | How |
|---|---|
| API | Push to `main` of `SagarSwain05/Jeevia`; Render auto-deploys `backend/`. Watch it in the Render dashboard or `GET /v1/services/<id>/deploys`. |
| Web app | `cd frontend && vercel deploy --prod`. Environment changes need a redeploy. |
| Both repositories | The same tree is pushed to `SagarSwain05/Jeevia` (author SagarSwain05) and `saanvi-sahoo/Jeevia` (author saanvi-sahoo). |

Before pushing: `cd backend && .venv/bin/pytest -q` and `cd frontend && npm run lint && npx tsc --noEmit && npm run build`.

## Secrets and where they live

| Secret | Stored in | Rotate by |
|---|---|---|
| `JEEVIA_DATABASE_URL` | Render env | Neon console → Roles → reset password, then update Render |
| `JEEVIA_JWT_SECRET` | Render env **and** Vercel env (same value) | Set a new random value in both, redeploy both. All users sign in again. |
| Twilio `ACCOUNT_SID`, `API_KEY_SID`, `API_KEY_SECRET`, `VERIFY_SERVICE_SID` | Render env | Twilio console → API keys → create new, update Render, delete the old key |
| Cloudinary `CLOUD_NAME`, `API_KEY`, `API_SECRET` | Render env | Cloudinary console → API keys → generate, update Render, revoke the old key |
| `RENDER_API_KEY`, `RENDER_SERVICE_ID` | Vercel env (server-only) | Render → Account settings → API keys |

Nothing secret is committed. Local development uses `backend/.env` (git-ignored).

## Database (Neon)

- **Connection**: the API uses Neon's direct endpoint with `sslmode=require`; connections are health-checked and recycled every 4 minutes because Neon suspends idle compute (first query after a pause takes well under a second).
- **Schema**: managed by **Alembic** (`backend/migrations/`). On start-up the API runs `alembic upgrade head` under a Postgres advisory lock (only one instance migrates), then re-applies the trigger that makes `audit_events` append-only. A database created before Alembic is stamped at `0001` first.
  - New migration: change `app/models.py`, then `cd backend && JEEVIA_DATABASE_URL=<local pg> .venv/bin/alembic revision --autogenerate -m "…"`, review it, and check with `alembic check`.
  - Rehearse risky migrations on a Neon branch: `neonctl branches create --project-id empty-dream-42914552 --name mig-test`, run `alembic upgrade head` against the branch URL, inspect, then delete the branch.
- **Backups**: Neon keeps point-in-time history (restore window per plan). For an extra copy:
  ```bash
  pg_dump "$NEON_URL" --no-owner --no-privileges -f jeevia-$(date +%F).sql
  ```
  Use a `pg_dump` at least as new as the server (currently 18).
- **Restore / move**: `psql "$TARGET_URL" -v ON_ERROR_STOP=1 -f jeevia-YYYY-MM-DD.sql`, then point `JEEVIA_DATABASE_URL` at it and redeploy. After any move, check `GET /api/v1/audit/verify` returns `ok: true`.
- **Branches**: Neon branches are instant copies — use one to test a risky change against real data.

History: the database moved from Render PostgreSQL to Neon on 27 Sep 2026 (row counts and the audit chain verified
identical after the move). The old Render database `jeevia-db` is no longer used and can be deleted.

## Facility directory (all of India)

- Source: OpenStreetMap health facilities (`amenity=hospital|clinic|doctors`, `healthcare=*`), © OpenStreetMap contributors, ODbL. Credit is shown in the sign-up workplace search.
- Refresh (a few hours, polite to the public Overpass servers):
  ```bash
  cd backend && .venv/bin/python scripts/fetch_directory.py      # writes directory_data/facilities_in.jsonl.gz
  .venv/bin/python -m app.directory load                         # upsert into the database (idempotent)
  .venv/bin/python -m app.directory stats
  ```
  Commit the new snapshot; on an empty `facility_directory` table the API loads it in the background at start-up.
- OSM coverage of small sub-centres varies by state. Supervisors can add a missing public facility at sign-up (marked *self-registered*, `verified=false`); company clinics, industrial units, campuses and camps come only from organisations that register.

## Security settings

| Setting (env) | Default | Meaning |
|---|---|---|
| `JEEVIA_OTP_PER_PHONE_10MIN` / `JEEVIA_OTP_PER_PHONE_DAY` | 3 / 10 | OTP requests per phone (sample phones exempt) |
| `JEEVIA_OTP_PER_IP_HOUR` | 30 | OTP requests per client address |
| `JEEVIA_PIN_MAX_ATTEMPTS` / `JEEVIA_PIN_LOCK_MINUTES` | 5 / 15 | Wrong PINs before a temporary lock |
| `JEEVIA_DEMO_PIN` | 4826 | PIN of the sample staff/employer accounts |

A forgotten staff PIN is reset by the facility supervisor (Admin → Staff → Reset PIN); supervisors and employers reset their own after the phone OTP.

## Sample data

`JEEVIA_SEED_DEMO=true` seeds an **empty** database with two facilities, six sample staff/patient accounts (OTP `123456`,
staff PIN `4826`), three fictional patients, the sample organisation *Kalinga Steel Works* with three roster workers,
and the kiosk link `MANIKPUR`. It never touches a database that already has facilities.

To reset production to the sample state (destructive — removes all real records):
1. Take a `pg_dump` first.
2. Drop all tables (`Base.metadata.drop_all`) against the production URL.
3. Restart the API; it runs the migrations, seeds, and reloads the facility directory in the background.
4. Delete orphaned files under `jeevia/` in Cloudinary (the API only deletes files through the retention purge).

## Twilio trial

The Twilio account is on a trial. Until it is upgraded, SMS codes are only delivered to numbers verified in the Twilio
console (Phone Numbers → Verified Caller IDs); other numbers get "the recipient must be a verified tester". The six
sample accounts use the fixed code `123456` and never send SMS.

## Data retention

Uploads carry an expiry at creation: voice 24 h, photos 72 h, reports 720 h (30 days, so they travel with referrals).
Expired files stop being served immediately. The API runs `storage.purge_expired(db)` every hour (one instance at a
time via an advisory lock): it deletes the bytes, keeps the metadata and writes a `PURGE` audit event. The same loop
deletes OTP challenges older than a day.

Documents and photos are only served to the doctors and nurses of the facility that holds the visit, the patient
themself, or through a QR summary link with its access code. Every opening is audited.
