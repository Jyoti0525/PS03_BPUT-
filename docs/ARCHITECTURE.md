# Jeevia — architecture and implementation map

Written for the team (frontend, backend, ML/data) and reviewers who want to see where each requirement lives.
For each feature with the tools, models and data it uses, see [FEATURES.md](FEATURES.md).

## 1. System overview

```
 Kiosk / tablet (PWA)        Reviewer dashboard         Facility admin        From-home link   Employer view
 staff-unlocked, offline     doctor + nurse density     config · audit        joins on arrival fitness only
            │                         │                        │                  │                 │
            └──────────── Next.js 16 frontend  (lib/api: one contract, mock or live adapter) ───────┘
                                                     │  HTTPS + JWT, X-Device-Id
                                                     ▼
                                     FastAPI  /api/v1   (backend/app)
      auth · devices · facilities · patients · consents · encounters · escalations · referrals · files · audit
                     │                     │                          │
         Rules engine (YAML)      Note pipeline: OCR, ASR,      Object storage
         ATP · IITT · IMCI ·      IndicTrans2, privacy scrub,   (expiry timestamps,
         maternal → urgency       checked LLM summary           signed URLs)
                     │                     │
                     └──────────► PostgreSQL on Neon: relational identity, facilities, users, audit_events
                                  (append-only trigger + hash chain); JSONB for intake and triage notes
 Hosting: web on Vercel · API on Render (Singapore) · DB on Neon (Singapore) · files on Cloudinary (private)
          · SMS codes via Twilio Verify · CI + keep-alive on GitHub Actions
```

### Request lifecycle for one intake
1. A nurse signs in (phone OTP + account PIN — two factors) and opens `/kiosk`. The tablet must be **bound** to her facility
   (`POST /devices`); staff intake submissions without a bound `X-Device-Id` are rejected.
2. Consent is captured first (`POST /consents`: self or proxy + relationship, privacy context, scopes).
3. Voice: the recording goes to `POST /speech/transcribe` (offline IndicConformer + IndicTrans2; the browser's Web Speech API only as a labelled fallback); the kiosk **reads it back aloud** (TTS) and the patient confirms.
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
| `src/lib/offline/outbox.ts` | Offline intake queue + replay, one queue per session scope (a kiosk link's queue replays with that link's session); `public/sw.js` caches pages and build assets and wakes the page on Background Sync. |
| `src/lib/offline/precache.ts` | After a kiosk opens online, sends the service worker the page URL and every loaded `/_next/static` asset so the kiosk reloads with no network. |
| `src/components/intake/*` | Kiosk / patient intake flow: consent → identity (household phone disambiguation) → visit type → voice / icons / text → duration & severity (+ maternal / chronic branches) → uploads → follow-ups → staff vitals → review → token + QR. |
| `src/components/triage/*` | Urgency badge, flag list, value table with **source evidence** (image crop / transcript / device), sparkline trends, `NoteView` at doctor or nurse density. |
| `src/app/reviewer/*` | **Doctor only.** Queue, case view (confirm / edit / override / escalate / referral / export / QR, nurses' observations), lookup by ID · QR · phone, escalations with acknowledgement, referrals. |
| `src/app/nurse/*` | **Nursing station.** Patients to attend (vitals needed first), patient view with vitals & observations form, nurse checklist, reports, alert doctor; lookup. |
| `src/app/desk/*` | **Front desk (receptionist).** Today's patients and waiting times, token board with corrections, find & register patients, doctors & nurses on/off duty. |
| `src/app/admin/*` | **Supervisor only.** Overview (counts only), staff & duty, facility setup wizard, kiosk links, devices, audit log (verify chain, CSV), data retention. |
| `components/layout/app-shell.tsx` | Shared shell; each workspace has its own colour and label (doctor ink, nurse teal, front desk blue, supervisor coral). |
| `components/triage/observations.tsx`, `components/staff/duty.tsx` | Vitals & observations form/list; on-duty list with switches. |
| `src/app/employer/*` | Employer portal: fitness overview by department, worker roster (add / CSV import / remove), workplaces, organisation profile. Never any clinical record. |
| `src/app/auth/page.tsx`, `components/auth/*` | Sign-in (OTP → PIN step, forgot PIN), registration with the national workplace search, organisation registration for employers, PIN creation; Change PIN modal in the dashboard header. |
| `components/triage/worker-panel.tsx`, `patient-edit.tsx` | Occupational-health panel with *Record fitness* on a case; correcting a patient's registration details (case header and token board). |
| `src/app/k/[code]` | Public kiosk link: intake-only session per facility, token on completion, auto-reset for shared tablets. Kiosk tabs keep their own session (`lib/api/tokens.ts` scopes by path). Works offline after one online visit (kiosk info, session and last user cached per scope). The intake wizard is loaded after the start screen. Live builds never download the mock backend (`lib/api/index.ts` loads it lazily). |
| `src/app/s/[token]` | QR summary page for receiving clinicians (access code → patient, note, referral, documents). |
| `src/app/admin/kiosk-links`, `components/triage/token-board.tsx` | Kiosk link management with QR posters; today's tokens for the front desk. |
| `components/triage/share-qr.tsx` | Create/revoke QR summaries and print hand-off slips. |
| `lib/status.ts`, `components/site/system-status.tsx` | Shared live status store (polls `/health`), status panel, header dot, wake and restart. |
| `src/app/api/ops/restart/route.ts` | Server-only route: verifies a supervisor JWT and asks Render to restart the API. |
| `lib/image.ts` | In-browser photo compression before upload. |
| `src/lib/i18n/*` | 22 scheduled languages + English in the picker. Every screen is translated into Hindi and Odia: components call `tr("English text")` from `usePrefs()`, and `i18n/phrases/{hi,or}.ts` (loaded on demand, cached for offline kiosks) map the English text to the translation; missing phrases fall back to English. Kiosk step keys use `i18n/dict.ts`. The signed-in user's saved language is applied at sign-in; changing it from the header saves it (`PATCH /auth/me`). |
| `src/lib/speech.ts` | Speech recognition and read-aloud in the chosen language; picks an installed voice for that language and reports when none exists. |

Switch adapters with `NEXT_PUBLIC_API_MODE=mock|live` and `NEXT_PUBLIC_API_URL`.

## 3. Backend (`backend/app`)

| Module | Purpose |
|---|---|
| `models.py` | SQLAlchemy models. `UTCDateTime` keeps every timestamp timezone-aware. `JSONType` = JSONB on Postgres. Includes `Organisation`, `DirectoryFacility`, `FitnessAssessment`. |
| `migrations/` (Alembic) | `0001` baseline, `0002` organisations + national directory + fitness (converts old JSON cohorts into real rows), `0003` account PIN … `0008` alerts and follow-ups, `0009` reminder calls. `init_db()` runs `alembic upgrade head` under a Postgres advisory lock at start-up (stamping `0001` on databases created before Alembic); SQLite tests use `create_all`. |
| `directory.py`, `scripts/fetch_directory.py` | National facility directory: classification (sub-centre, PHC, CHC, district / sub-district hospital, medical college, ESI, AYUSH, hospital, clinic), public/private ownership, batched upsert loader, trigram search. The fetch script pulls OpenStreetMap health facilities state by state via Overpass into `directory_data/facilities_in.jsonl.gz`; the API loads it in the background when the table is empty. |
| `security.py` | JWT (access 60 min, rotating single-use refresh 7 days, revocation on logout; 5-minute `pin` step tokens between OTP and PIN), PBKDF2 hashing for OTP and PIN, weak-PIN rules, role dependencies. |
| `audit.py` | Append-only hash chain. Each event is written in its own short transaction, serialised by a process lock and a Postgres advisory lock. ORM hook + DB trigger block UPDATE / DELETE. `GET /audit/verify` re-computes the chain. |
| `triage/rules/*.yaml`, `triage/rules.py` | Deterministic rules engine (ATP, IMCI, maternal). |
| `triage/pipeline.py` | Builds the note: values with sources, flags, timeline, missing info, trends, documents, medicines. |
| `triage/findings.py`, `triage/timeline.py` | Intake → present / absent / unknown findings (English, Hindi, Odia); onset with a certainty label. |
| `triage/extraction.py`, `triage/images.py` | OCR and lab parsing (RapidOCR and docTR in parallel, compared test by test; quality gate); B2 number checks (the lab's H/L marks, units and SI conversion, ranges that fit, the report's own sums: `consistency`); document type, medicine names (PMBJP generics and the A-Z brand list, `triage/data/medicine_brands.tsv.gz`), face and ID redaction. |
| `language.py`, `privacy.py`, `llm.py`, `output_guard.py` | Speech and translation; identifier removal and cohort counts; checked summary model; non-diagnostic guard. |
| `asr_check.py` | B9: compares the two transcripts of one recording (numbers, symptoms, overall agreement). |
| `whisper_asr.py` | B9: IndicWhisper, the offline second speech engine when Sarvam cannot be used. Slower than real time, so `/speech/transcribe` returns first and the check runs on one background worker; the kiosk asks `GET /speech/second/{id}` (kept 10 minutes in memory, only for the user who recorded it). |
| `triage/reports.py` | Synthetic lab slips rendered to SVG with per-row bounding boxes (drives the traceability crops). |
| `services.py` | Encounter creation, role-aware serialisation, patient ownership, lazy auto-escalation. |
| `alerts.py`, `calls.py` + `calls.yaml` | Rule-raised alerts (capacity, fever cluster, missed check-up, call escalation); E6 reminder calls for maternal and chronic follow-ups: fixed lines in 11 languages, answers read by the findings lexicon and a yes / no / not-sure word list (a hedge is never yes or no), a danger sign ends the call and raises an alert, a serious or unassessed last visit means a person calls. |
| `sarvam.py` | Sarvam AI over REST: Bulbul v3 speaks the fixed call lines (11 languages, kept in memory only), Saaras v3 speech-to-text, Vision reads handwritten pages (Digitise job; HTML tables and Markdown turned into plain lines). Unset key = the device's voice. |
| `crypto.py`, `ratelimit.py`, `filetypes.py` | Encryption at rest (Fernet fields and files, keyed phone hash); per-device and per-phone rate limits; upload type from the bytes. See `SECURITY.md`. |
| `tts.py` | Offline voice: Meta MMS-TTS (VITS) for Odia, Hindi and Kannada on CPU, returns WAV. `/language/speak` tries it before Sarvam. CC-BY-NC 4.0. |
| `bhashini.py` | Bhashini (MeitY) ULCA pipeline: online translation used only when IndicTrans2 cannot run here. Keys `BHASHINI_USER_ID` / `BHASHINI_API_KEY`. |
| `telephony.py` + `vonage.py` + `routers/telephony.py` | Twilio or Vonage over REST: the same call over a real phone line (Sarvam's voice, keypad answers, the free answer recorded, transcribed and deleted), reminder SMS and staff SMS on a danger sign. Only the demo phone is ever dialled; webhooks need a per-call token (and Twilio's signature). Vonage when its key is set: JWT (RS256) voice calls driven by NCCO, SMS API. |
| `storage.py` | Pluggable object storage — local disk, Cloudinary (authenticated assets, signed downloads) or S3/R2 — with expiry and `purge_expired()`. |
| `otp.py` | OTP delivery: mock (dev) or Twilio Verify; sample accounts keep a fixed code. |
| `routers/organisations.py` | Organisation profile, workplaces, worker roster (CSV import), department fitness view for employers. |
| `routers/directory.py` | Public workplace search and state list. |
| `routers/kiosk.py` | Kiosk links (create/revoke), public kiosk session and returning-patient identify, token board. |
| `routers/shares.py` | QR summary links: create/list/revoke, public meta, open with access code (lockout, expiry, audit). |
| `exports.py` | PDF (fpdf2), print HTML, JSON, CSV, FHIR R4 document bundle, HL7 CDA R2 document (LOINC 54094-8, schema-tested). |
| `triage/question_flow.yaml` + `question_flow.py` | The kiosk's context questions, their conditions and the findings each answer sets; one versioned file read by the rules and (as `frontend/src/lib/question_flow.json`) by the kiosk. CI checks it against `findings.FINDINGS`. |
| `triage/vlm.py` | Optional second document-type label from Qwen3-VL-4B on a local llama-server; a disagreement adds a warning, never changes the label. |
| `triage/tables.py` | Optional PP-StructureV3 table reading of report photos in a separate Python (subprocess); a different value marks the row for checking. |
| `scenarios.synthea_histories` | Seeds 12 patients with earlier visits from Synthea (`synthea_histories.json`, built by `scripts/import_synthea.py`). |
| `observability.py` | JSON logs with request id (no request bodies → no PHI in logs), `/metrics` in Prometheus text format, `/health`. |
| `seed.py` | Synthetic facilities, staff, patients and encounters (same scenarios as the frontend mock). |

### API (all under `/api/v1`)

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/otp/request`, `POST /auth/otp/verify` (patients: tokens; staff/employers: `pin_required` or `pin_setup_required` + `pin_token`; `purpose: "register"` refuses numbers that already have an account), `PATCH /auth/me` (language), `GET /auth/options`, `POST /auth/otp/request` with `{email}` (Brevo email code), `POST /auth/email/start`, `POST /auth/email/confirm`, `DELETE /auth/email`, `POST /auth/pin/verify`, `POST /auth/pin/setup`, `POST /auth/pin/forgot` (supervisor/employer), `POST /auth/pin/change`, `POST /auth/register`, `POST /auth/refresh`, `GET /auth/me`, `POST /auth/logout` |
| Directory / organisations | `GET /directory/search?q=&state=`, `GET /directory/states`, `GET/PATCH /organisations/me`, `POST /organisations/me/facilities`, `GET/POST /organisations/me/workers`, `POST /organisations/me/workers/import`, `PATCH /organisations/me/workers/{code}`, `GET /employer/cohorts`, `POST /encounters/{id}/fitness` |
| Devices | `GET/POST /devices`, `DELETE /devices/{id}` |
| Facilities / users | `GET /facilities`, `GET/PATCH /facilities/{id}` (PATCH: supervisor), `GET /facilities/{id}/stats`, `GET /users` (supervisor: all staff; receptionist: doctors & nurses), `PATCH /users/{id}` (role, active), `POST /users/{id}/reset-pin`, `PATCH /users/{id}/duty` (receptionist / supervisor) |
| Patients / consent | `GET /patients?q=`, `POST /patients` (optional `employee_code` at organisation workplaces), `GET /patients/{id}`, `PATCH /patients/{id}` (correction), `GET /patients/by-code/{code}`, `GET /patients/{id}/encounters`, `POST /consents` |
| Encounters | `POST /encounters`, `GET /queue?facility_id=`, `GET/PATCH /encounters/{id}`, `POST /encounters/{id}/confirm`, `PATCH /encounters/{id}/note`, `POST /encounters/{id}/observations` (nurse/doctor: vitals + note, rules re-run), `POST /encounters/{id}/override`, `GET /encounters/{id}/export?format=pdf|print|json|csv|fhir` |
| Escalation / referral | `POST /encounters/{id}/escalations`, `GET /escalations`, `POST /escalations/{id}/acknowledge`, `POST /encounters/{id}/referrals`, `GET /referrals` |
| Files | `POST /files` (multipart, `kind`, optional `sample_key`), `GET /files/{id}`, `GET /files/{id}/content?sig=` |
| Governance | `GET /audit`, `GET /audit/verify`, `GET /audit/export`, `GET /retention`, `GET /me/record`, `GET /employer/cohorts` |
| Kiosk links and tokens | `GET/POST /kiosk-links`, `DELETE /kiosk-links/{id}`, `GET /kiosk/{code}`, `POST /kiosk/{code}/session`, `POST /kiosk/identify`, `GET /facilities/{id}/tokens` |
| QR summaries | `POST/GET /encounters/{id}/shares`, `DELETE /shares/{id}`, `GET /share/{token}`, `POST /share/{token}/open` |
| Alerts, follow-ups, calls | `GET /alerts`, `POST /alerts/{id}/acknowledge`, `GET /capacity`, `GET /surveillance/syndromic.csv`, `GET /followups?scope=&programme=`, `POST /followups/{id}/attempt`, `POST /followups/{id}/calls`, `GET /followups/{id}/calls`, `GET /calls/{id}`, `GET /calls/{id}/turns/{i}/audio`, `POST /calls/{id}/answer`, `POST /calls/{id}/end`, `POST /followups/{id}/sms`, `GET /telephony/status`, Twilio webhooks under `/telephony/calls/{id}/…`, Vonage webhooks under `/telephony/vonage/calls/{id}/…`, `GET /health-workers`, `GET /employer/department-rates` |
| Ops | `GET /health`, `GET /metrics` |

### Role matrix

| | doctor | nurse | receptionist | supervisor | employer |
|---|---|---|---|---|---|
| Workspace | `/reviewer` | `/nurse` | `/desk` | `/admin` | `/employer` |
| Queue, case notes | ✔ | ✔ | ✘ (names, tokens, waits only) | ✘ (counts only) | ✘ |
| Vitals & bedside observations | ✔ | ✔ | ✘ | ✘ | ✘ |
| Patient documents and photos | ✔ at the treating facility | ✔ at the treating facility | ✘ | ✘ | ✘ |
| Find / correct patient details | ✔ | ✔ | ✔ | ✔ | ✘ |
| Doctors & nurses on/off duty | ✘ | ✘ | ✔ | ✔ | ✘ |
| Check in a patient who filled in from home (C3) | ✔ | ✔ | ✔ | ✔ | ✘ |
| Edit note, escalate (alert doctor) | ✔ | ✔ | ✘ | ✘ | ✘ |
| Confirm, override, referral, export, QR summary, acknowledge, fitness | ✔ | ✘ | ✘ | ✘ | ✘ |
| Facility config, kiosk links, devices, retention | ✘ | ✘ | ✘ | ✔ | ✘ |
| Staff role / deactivate / reset PIN | ✘ | ✘ | ✘ | ✔ | ✘ |
| Audit log | ✔ | ✘ | ✘ | ✔ | ✘ |
| Fitness outcomes, roster, workplaces | ✘ | ✘ | ✘ | ✘ | ✔ (own organisation) |
| Sign-in factors | OTP + PIN | OTP + PIN | OTP + PIN | OTP + PIN | OTP + PIN |

Patients have no login and no portal (plan: staff-only surfaces). They use a kiosk link, on a waiting-room tablet or, for a link marked *for filling in from home*, their own phone before coming; either way they never see an urgency tier.

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
| 3F, 3N | Employer view — fitness and cohort only | `app/employer/*` (overview, workers, workplaces, organisation) |
| F3, 3J | Accessibility — TTS read-back, icon mode, large targets | `lib/speech.ts`, A11y menu (large text, icon mode, read aloud), 56–64 px kiosk targets |
| 3N | Offline intake PWA | `lib/offline/outbox.ts`, `lib/offline/precache.ts`, `public/sw.js`, simulate-offline switch on the kiosk; `/k/CODE` reloads offline |

### Backend (Saanvi)

| Spec | Item | Where |
|---|---|---|
| H2 | CRUD for Patient, Encounter, Facility, User | `routers/patients.py`, `routers/encounters.py`, `routers/facilities.py` |
| 3N | Phone OTP + account PIN (two-factor), device binding, JWT, OTP rate limits | `routers/auth.py`, `security.py`, `routers/facilities.py` (devices, staff) |
| H2 | Organisations, national facility directory, fitness | `routers/organisations.py`, `routers/directory.py`, `directory.py`, `migrations/` |
| G1 | Consent capture — self, proxy, privacy context | `POST /consents`; intake refuses without `consent_id` |
| G4 | Append-only audit writes incl. VIEW | `audit.py`, DB trigger in `db.py`, VIEW on every clinical read |
| A4, H4 | File storage — upload, retrieve, expiry; documents open only for the treating doctors / nurses, the patient, or a QR summary holder | `routers/files.py`, `storage.py` |
| E7 | Export — PDF, print, JSON, CSV, FHIR, HL7 CDA | `exports.py`, `GET /encounters/{id}/export` |
| F1 | Facility admin screens | `PATCH /facilities/{id}` + `frontend/src/app/admin/*` |
| H8 | Logging and observability | `observability.py`, `/metrics`, `/health` |
| H9 | Docker Compose | `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile` |

### Hand-off points for the ML / data track (Jyoti)

| Item | Hook |
|---|---|
| ASR / translation / OCR / summariser | Built (see [FEATURES.md](FEATURES.md)). New engines must keep the note shape (`TriageNote` in `frontend/src/lib/types.ts`); values carry `source` (bbox for OCR) and `needs_check` when engines disagree. |
| Patient identity resolution | `services.own_patient` (patient-account linking) and `GET /patients?q=` candidate ranking. |
| Retention purge | Runs hourly in the API (`main._housekeeping_loop`, one instance via advisory lock); `storage.purge_expired(db)` deletes bytes, keeps metadata and writes `PURGE` audit events. Old OTP challenges are deleted too. |

## 5. Verification done

* Backend: 483 pytest tests as of 6 Oct (see FEATURES.md §7); the list below is the original platform set: 54 tests (incl. front desk vs supervisor, nurse observations vs doctor-only actions, sign-up number reuse, language preference) — rules; auth (OTP lockout and rate limits, two-factor PIN: setup, verify, lockout, forgot,
  change, supervisor reset; refresh rotation; logout revocation); bound-device intake; idempotent replay; overrides;
  escalation acknowledgement; exports; RBAC for every role; patient isolation on a shared household phone; document
  access (treating clinicians only); directory search; organisation onboarding; roster and CSV import; fitness →
  employer view; staff management; patient correction; audit VIEW logging, chain verification, append-only guard;
  signed file URLs; concurrency. Passing on SQLite and PostgreSQL.
* Migrations: `0002`/`0003` rehearsed on a Neon branch copy of production before release; `alembic check` clean.
* Browser end-to-end (Playwright, Chrome) in live mode: full staff journey with OTP + PIN; employer registers an
  organisation → roster + CSV → doctor and supervisor join its workplace by search → PIN change / wrong PIN / supervisor
  reset → worker checks in at a kiosk link with an employee ID → doctor records fitness and corrects details → employer
  sees the outcome only; kiosk links on tablet and phone; QR summaries; and a true-offline test (network cut, `/k/CODE`
  reloaded, intake queued, synced on reconnect with the kiosk's own session).
