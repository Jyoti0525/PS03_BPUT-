# Jeevia frontend

Next.js 16 (App Router, Turbopack) + TypeScript + Tailwind CSS v4, installable as a PWA.

```bash
npm install
npm run dev          # http://localhost:3000 — mock API, no backend needed
npm run lint && npx tsc --noEmit && npm run build
```

## API modes

| Variable | Values | Effect |
|---|---|---|
| `NEXT_PUBLIC_API_MODE` | `mock` (default) / `live` | `mock` runs the in-browser backend in `src/lib/api/mock` (IndexedDB, synthetic data). `live` calls FastAPI. |
| `NEXT_PUBLIC_API_URL` | e.g. `http://localhost:8000` | Base URL for live mode. |

Mock mode enforces the same role rules, rules engine and audit chain as the backend, so every screen can be built and
demoed without the API. Reset the mock database from **Admin → Overview → Reset demo data**.

## Routes

| Route | Who |
|---|---|
| `/` | Landing |
| `/auth` | Sign in (OTP or device PIN) and registration (role → personal info → phone → OTP → terms → PIN) |
| `/kiosk` | Staff-unlocked intake kiosk (device binding, offline mode) |
| `/reviewer`, `/reviewer/case/[id]`, `/reviewer/lookup`, `/reviewer/escalations`, `/reviewer/referrals` | Doctor, nurse |
| `/admin`, `/admin/facility`, `/admin/devices`, `/admin/staff`, `/admin/audit`, `/admin/retention` | Receptionist, supervisor |
| `/patient`, `/patient/new` | Patient |
| `/employer` | Employer |

See [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) for the component map.

> This project uses Next.js 16 — read `node_modules/next/dist/docs/` before changing framework-level code (see `AGENTS.md`).
