# Jeevia (जीविया)

**Human-in-the-loop multimodal triage assistant for government and institutional health facilities.**
BPUT Hackathon 2026 · Problem Statement 3 (Cognizant).

> **Educational prototype — triage support only.** Jeevia does not diagnose, prescribe or replace a qualified
> professional. It uses synthetic data only. Every health-related output is advisory and reviewer-facing.

**Live demo (frontend, mock API):** https://jeevia-triage.vercel.app — sign in with any demo account below; the OTP is always `123456`.

| Role | Phone | Lands on |
|---|---|---|
| Doctor / Medical Officer | 9000000001 | `/reviewer` — triage queue and case review |
| Nurse / ANM | 9000000002 | `/reviewer` (nurse density) and `/kiosk` |
| Receptionist | 9000000003 | `/admin` |
| Supervisor | 9000000004 | `/admin` — facility setup, audit, retention |
| Patient | 9876543210 | `/patient` — own visits, reminders, add a problem |
| Employer / HR | 9000000005 | `/employer` — fitness cohorts only |

---

## What it does

A staff member unlocks a tablet kiosk. The patient (or a family member, as a recorded proxy) speaks or taps their
symptoms in their own language, hears them read back, answers a few bounded follow-up questions and photographs any
lab slips. A **deterministic YAML rules engine** (AIIMS Triage Protocol for adults, IMCI for under-fives, maternal
red flags) assigns urgency. A structured note is built with **every extracted value sitting beside the image crop or
transcript it came from**. A doctor reviews it in under four minutes, can override urgency only with a written reason,
escalates or refers in one click, and exports PDF / print / JSON / CSV / FHIR. Every view, edit, override and export
lands in a **hash-chained, append-only audit log**. Raw audio and photos expire automatically.

### The golden rules, and where they are enforced

| Rule | Enforcement |
|---|---|
| Non-diagnostic | Summaries only restate patient-provided information and end with a non-diagnostic statement; disclaimer bar on every screen (G6). |
| Urgency only from rules, never the LLM | `backend/app/triage/rules/*.yaml` + `rules.py`; the note pipeline has no access to urgency. Frontend mock mirrors it in `lib/api/mock/rules.ts`. |
| Patients never see triage status | API strips `urgency`, `note`, `override` for the patient role (`services.encounter_out`); patient UI shows workflow status only. |
| Human in the loop | Override requires a doctor and a ≥15-character reason; the original rules output is kept in `rules_urgency`. Escalations require doctor acknowledgement. |
| Flags, not confidence percentages | Notes carry `flags[]` (critical / warning / info) and `needs_check` markers; no model scores are shown. |
| Minimal retention | Upload expiry: audio 24 h, images 72 h, reports 7 days; content served only via 10-minute signed URLs. |
| Admins cannot read clinical notes | Receptionist / supervisor / employer get `403` on encounters and files; they see counts, config and audit only. |

---

## Repository layout

```
Jeevia/
├── frontend/          Next.js 16 + TypeScript + Tailwind v4 PWA (all UIs)
├── backend/           FastAPI + SQLAlchemy 2 (Postgres JSONB / SQLite for dev)
├── prototype/         The original static HTML prototype, kept as design reference
├── docs/ARCHITECTURE.md   Architecture, API contract, spec-item → code map, ownership
├── docker-compose.yml Postgres + API + web
└── .github/workflows/ci.yml   Backend tests + frontend lint / typecheck / build
```

## Run it

### Frontend only (mock API — no backend needed)
```bash
cd frontend
npm install
npm run dev            # http://localhost:3000
```

### Full stack with Docker (Postgres + FastAPI + web)
```bash
docker compose up --build
# web  http://localhost:3000     API docs  http://localhost:8000/docs
```

### Backend on its own
```bash
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn app.main:app --reload          # SQLite at ./data, seeded with synthetic data
.venv/bin/pytest -q                               # 26 tests
```
Point the frontend at it with `NEXT_PUBLIC_API_MODE=live NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev`.

## Team ownership

| Area | Owner | Status |
|---|---|---|
| Entire frontend: app structure, PWA, kiosk, uploads, reviewer dashboard, traceability, role density, escalation, referral/export UI, employer view, accessibility, offline intake | Krutee | Built — see `frontend/` |
| API, auth (OTP / PIN / device binding / JWT), consent, audit log, file storage, exports, facility admin, logging, Docker | Saanvi | Built — see `backend/` |
| ML pipeline (ASR, translation, OCR, summariser), patient identity resolution, retention purge job | Jyoti | Interfaces and stubs in place: `triage/pipeline.py`, `storage.purge_expired`, `services.own_patient` |

Details and the spec-code map (A1, 3D, E1…H9) are in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Clinical safety notice

Jeevia is an assistive triage prototype for research and workflow demonstration. All outputs — summaries, extracted
values, rule-based urgency — exist only to assist qualified, licensed professionals. It provides no diagnosis,
treatment or prescription. Clinical accountability remains with the examining clinician.

License: MIT
