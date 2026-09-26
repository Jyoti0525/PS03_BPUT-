# Jeevia — architecture and implementation map

Written for the team (frontend, backend, ML/data) and reviewers who want to see where each requirement lives.

## 1. System overview

```
 Kiosk / tablet (PWA)        Reviewer dashboard         Facility admin        Patient app      Employer view
 staff-unlocked, offline     doctor + nurse density     config · audit        own visits       fitness only
            │                         │                        │                  │                 │
            └──────────── Next.js 16 frontend  (lib/api: one contract, mock or live adapter) ───────┘
                                                     │  HTTPS + JWT, X-Device-Id
                                                     ▼
                                     FastAPI  /api/v1   (backend/app)
      auth · devices · facilities · patients · consents · encounters · escalations · referrals · files · audit
                     │                     │                          │
         Rules engine (YAML)      Note pipeline (stub →        Local object storage
         ATP · IMCI · maternal    ML track: ASR, IndicTrans2,   (expiry timestamps,
         → urgency, rules trace   PaddleOCR + parrotlet, LLM)   signed URLs)
                     │                     │
                     └──────────► PostgreSQL on Neon: relational identity, facilities, users, audit_events
                                  (append-only trigger + hash chain); JSONB for intake and triage notes
 Hosting: web on Vercel · API on Render (Singapore) · DB on Neon (Singapore) · files on Cloudinary (private)
          · SMS codes via Twilio Verify · CI + keep-alive on GitHub Actions
```

### Request lifecycle for one intake
1. A nurse signs in (phone + OTP, later device PIN) and opens `/kiosk`. The tablet must be **bound** to her facility
   (`POST /devices`); staff intake submissions without a bound `X-Device-Id` are rejected.
2. Consent is captured first (`POST /consents`: self or proxy + relationship, privacy context, scopes).
3. Voice: Web Speech API gives a live transcript; the kiosk **reads it back aloud** (TTS) and the patient confirms.
   Raw audio is uploaded as `kind=audio` (24 h retention). Unconfirmed transcripts are flagged `ASR-UNCONFIRMED`.
4. Bounded follow-up questions (`components/intake/catalog.tsx → contextQuestions`) fill gaps; answers feed the rules.
5. `POST /encounters` → `rules.evaluate()` sets urgency and returns every fired rule → `pipeline.build_note()` builds
   the note (values with `source`, flags, disagreements, missing info, follow-ups, timeline, trend).
6. Offline: the whole payload goes to an IndexedDB outbox with a `client_ref`; it replays when the connection returns.
   `client_ref` makes replays idempotent, and `captured_at` keeps the true waiting time.
7. Reviewer queue orders by urgency then wait. Unreviewed red cases auto-escalate after 15 min (yellow 60 min).

## 2. Frontend (`frontend/`)

| Path | Purpose |
|---|---|
| `src/lib/types.ts` | The API contract (mirrors `backend/app/schemas.py`). |
| `src/lib/api/contract.ts` | `JeeviaApi` interface — every call the UI makes. |
| `src/lib/api/live.ts` | FastAPI adapter (JWT refresh, device header, file downloads). |
| `src/lib/api/mock/*` | In-browser mock backend (IndexedDB) with the same RBAC, rules, audit hash chain and seed data. Default mode, used for the Vercel demo. |
| `src/lib/offline/outbox.ts` | Offline intake queue + replay; `public/sw.js` caches the kiosk shell and wakes the page on Background Sync. |
| `src/components/intake/*` | Kiosk / patient intake flow: consent → identity (household phone disambiguation) → visit type → voice / icons / text → duration & severity (+ maternal / chronic branches) → uploads → follow-ups → staff vitals → review → token + QR. |
| `src/components/triage/*` | Urgency badge, flag list, value table with **source evidence** (image crop / transcript / device), sparkline trends, `NoteView` at doctor or nurse density. |
| `src/app/reviewer/*` | Queue, case view (confirm / edit / override / escalate / referral / export), lookup by ID · QR · phone, escalations with acknowledgement, referrals. |
| `src/app/admin/*` | Overview (counts only), facility setup wizard, kiosk devices, staff, audit log (verify chain, CSV), data retention. |
| `src/app/patient/*`, `src/app/employer/*` | Patient self-service (no urgency), employer cohorts (no records). |
| `src/app/k/[code]` | Public kiosk link: intake-only session per facility, token on completion, auto-reset for shared tablets. Kiosk tabs keep their own session (`lib/api/tokens.ts` scopes by path). |
| `src/app/s/[token]` | QR summary page for receiving clinicians (access code → patient, note, referral, documents). |
| `src/app/admin/kiosk-links`, `components/triage/token-board.tsx` | Kiosk link management with QR posters; today's tokens for the front desk. |
| `components/triage/share-qr.tsx` | Create/revoke QR summaries and print hand-off slips. |
| `lib/status.ts`, `components/site/system-status.tsx` | Shared live status store (polls `/health`), status panel, header dot, wake and restart. |
| `src/app/api/ops/restart/route.ts` | Server-only route: verifies a supervisor JWT and asks Render to restart the API. |
| `lib/image.ts` | In-browser photo compression before upload. |
| `src/lib/i18n/*` | 22 scheduled languages + English in the picker; full UI strings for English, Hindi, Odia. |

Switch adapters with `NEXT_PUBLIC_API_MODE=mock|live` and `NEXT_PUBLIC_API_URL`.

## 3. Backend (`backend/app`)

| Module | Purpose |
|---|---|
| `models.py` | SQLAlchemy models. `UTCDateTime` keeps every timestamp timezone-aware. `JSONType` = JSONB on Postgres. |
| `security.py` | JWT (access 60 min, rotating single-use refresh 7 days, revocation on logout), PBKDF2 hashing for OTP and PIN (PIN salted with user + device id), role dependencies. |
| `audit.py` | Append-only hash chain. Each event is written in its own short transaction, serialised by a process lock and a Postgres advisory lock. ORM hook + DB trigger block UPDATE / DELETE. `GET /audit/verify` re-computes the chain. |
| `triage/rules/*.yaml`, `triage/rules.py` | Deterministic rules engine (ATP, IMCI, maternal). |
| `triage/pipeline.py` | Note-generation interface + deterministic stub — **replace internals here** with the ML pipeline. |
| `triage/reports.py` | Synthetic lab slips rendered to SVG with per-row bounding boxes (drives the traceability crops). |
| `services.py` | Encounter creation, role-aware serialisation, patient ownership, lazy auto-escalation. |
| `storage.py` | Pluggable object storage — local disk, Cloudinary (authenticated assets, signed downloads) or S3/R2 — with expiry and `purge_expired()`. |
| `otp.py` | OTP delivery: mock (dev) or Twilio Verify; sample accounts keep a fixed code. |
| `routers/kiosk.py` | Kiosk links (create/revoke), public kiosk session and returning-patient identify, token board. |
| `routers/shares.py` | QR summary links: create/list/revoke, public meta, open with access code (lockout, expiry, audit). |
| `exports.py` | PDF (fpdf2), print HTML, JSON, CSV, FHIR R4 document bundle. |
| `observability.py` | JSON logs with request id (no request bodies → no PHI in logs), `/metrics` in Prometheus text format, `/health`. |
| `seed.py` | Synthetic facilities, staff, patients and encounters (same scenarios as the frontend mock). |

### API (all under `/api/v1`)

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/otp/request`, `POST /auth/otp/verify`, `POST /auth/register`, `POST /auth/pin`, `POST /auth/pin/login`, `POST /auth/refresh`, `GET /auth/me`, `POST /auth/logout` |
| Devices | `GET/POST /devices`, `DELETE /devices/{id}` |
| Facilities / users | `GET /facilities`, `GET/PATCH /facilities/{id}`, `GET /facilities/{id}/stats`, `GET /users` |
| Patients / consent | `GET /patients?q=`, `POST /patients`, `GET /patients/{id}`, `GET /patients/by-code/{code}`, `GET /patients/{id}/encounters`, `POST /consents` |
| Encounters | `POST /encounters`, `GET /queue?facility_id=`, `GET/PATCH /encounters/{id}`, `POST /encounters/{id}/confirm`, `PATCH /encounters/{id}/note`, `POST /encounters/{id}/override`, `GET /encounters/{id}/export?format=pdf|print|json|csv|fhir` |
| Escalation / referral | `POST /encounters/{id}/escalations`, `GET /escalations`, `POST /escalations/{id}/acknowledge`, `POST /encounters/{id}/referrals`, `GET /referrals` |
| Files | `POST /files` (multipart, `kind`, optional `sample_key`), `GET /files/{id}`, `GET /files/{id}/content?sig=` |
| Governance | `GET /audit`, `GET /audit/verify`, `GET /audit/export`, `GET /retention`, `GET /me/record`, `GET /employer/cohorts` |
| Kiosk links and tokens | `GET/POST /kiosk-links`, `DELETE /kiosk-links/{id}`, `GET /kiosk/{code}`, `POST /kiosk/{code}/session`, `POST /kiosk/identify`, `GET /facilities/{id}/tokens` |
| QR summaries | `POST/GET /encounters/{id}/shares`, `DELETE /shares/{id}`, `GET /share/{token}`, `POST /share/{token}/open` |
| Ops | `GET /health`, `GET /metrics` |

### Role matrix

| | doctor | nurse | receptionist / supervisor | patient | employer |
|---|---|---|---|---|---|
| Queue, case notes, files | ✔ | ✔ | ✘ (counts only) | own visits, no urgency / note | ✘ |
| Confirm, override, referral, acknowledge | ✔ | ✘ | ✘ | ✘ | ✘ |
| Edit note, escalate, export | ✔ | ✔ | ✘ | ✘ | ✘ |
| Facility config, device revoke, staff, retention | ✘ | ✘ | ✔ | ✘ | ✘ |
| Audit log | ✔ | ✘ | ✔ | ✘ | ✘ |
| Fitness cohorts | ✘ | ✘ | ✘ | ✘ | ✔ |

## 4. Spec item → implementation

### Frontend (Krutee)

| Spec | Item | Where |
|---|---|---|
| 3N | Next.js structure, routing, PWA | `src/app/*`, `src/app/manifest.ts`, `public/sw.js`, icons |
| A1, 3D | Kiosk intake question flow | `components/intake/intake-flow.tsx`, `catalog.tsx`, `app/kiosk/page.tsx` |
| A4 | Report & image upload | intake "Reports or photos" step; sample synthetic reports |
| G6 | Visible non-diagnostic disclaimer | `DisclaimerBar` on every page, landing, auth terms, exports |
| E1, 3E | Reviewer dashboard: queue, case view, confirm & edit | `app/reviewer/page.tsx`, `app/reviewer/case/[id]/page.tsx` |
| 3E | Source traceability — crop beside each value | `components/triage/source.tsx` (`Crop`, `SourceEvidence`) |
| E2, 3E | Role-differentiated rendering | `NoteView density="doctor|nurse"`; nurse toggle on case view |
| E3, 3E | Escalation UI + acknowledgement | Escalate modal, `app/reviewer/escalations`, auto-escalation timers |
| D7, E4, E7 | Referral UI and export triggers | Referral modal (facility-aware destination), Export menu |
| 3F, 3N | Employer view — fitness and cohort only | `app/employer/page.tsx` |
| F3, 3J | Accessibility — TTS read-back, icon mode, large targets | `lib/speech.ts`, A11y menu (large text, icon mode, read aloud), 56–64 px kiosk targets |
| 3N | Offline intake PWA | `lib/offline/outbox.ts`, `public/sw.js`, simulate-offline switch on the kiosk |

### Backend (Saanvi)

| Spec | Item | Where |
|---|---|---|
| H2 | CRUD for Patient, Encounter, Facility, User | `routers/patients.py`, `routers/encounters.py`, `routers/facilities.py` |
| 3N | Phone + OTP, PIN, device binding, JWT | `routers/auth.py`, `security.py`, `routers/facilities.py` (devices) |
| G1 | Consent capture — self, proxy, privacy context | `POST /consents`; intake refuses without `consent_id` |
| G4 | Append-only audit writes incl. VIEW | `audit.py`, DB trigger in `db.py`, VIEW on every clinical read |
| A4, H4 | File storage — upload, retrieve, expiry | `routers/files.py`, `storage.py` |
| E7 | Export — PDF, print, JSON, CSV, FHIR | `exports.py`, `GET /encounters/{id}/export` |
| F1 | Facility admin screens | `PATCH /facilities/{id}` + `frontend/src/app/admin/*` |
| H8 | Logging and observability | `observability.py`, `/metrics`, `/health` |
| H9 | Docker Compose | `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile` |

### Hand-off points for the ML / data track (Jyoti)

| Item | Hook |
|---|---|
| ASR / translation / OCR / summariser | Replace the body of `backend/app/triage/pipeline.py::build_note` — keep the returned shape (`TriageNote` in `frontend/src/lib/types.ts`). Values must carry `source` (bbox for OCR) and `needs_check` when engines disagree. |
| Patient identity resolution | `services.own_patient` (patient-account linking) and `GET /patients?q=` candidate ranking. |
| Retention purge | Call `storage.purge_expired(db)` on a schedule; it deletes bytes, keeps metadata and writes `PURGE` audit events. |

## 5. Verification done

* Backend: 38 pytest tests (rules, auth incl. OTP lockout / PIN device binding / refresh rotation / logout revocation,
  bound-device intake, idempotent replay, override rules, escalation acknowledgement, exports, RBAC for every role,
  patient isolation on a shared household phone, audit VIEW logging, chain verification, append-only guard, signed file
  URLs, concurrency) — passing on SQLite and on PostgreSQL 16.
* Browser end-to-end (Playwright, Chrome) in mock mode, live mode against FastAPI + SQLite, and the Docker Compose
  stack on Postgres: kiosk intake → critical in queue → OCR crops → override → referral → PDF export → audit verify →
  patient and employer isolation; plus offline capture → queue → sync → reviewed.
