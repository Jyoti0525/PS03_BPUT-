# How Jeevia works — roles, dashboards and the patient journey

Written for the Jeevia team and for facility staff learning the system.

## 1. The big picture

```
 PATIENT CHECKS IN                    SYSTEM                              CLINICIANS REVIEW
 ─────────────────                    ──────                              ─────────────────
 Kiosk link /k/CODE  ─┐                                                  Doctor / Nurse
 (tablet or own phone)│   consent → symptoms → reports →   ┌──────────►  /reviewer  queue ordered by
 Staff kiosk /kiosk  ─┼─► follow-up questions → submit ────┤             urgency → case → confirm /
 Patient app /patient ┘            │                       │             override / escalate / refer
                                   ▼                       │
                     Rules engine sets urgency (red /      │             Receptionist / Supervisor
                     yellow / green) from fixed AIIMS      ├──────────►  /admin  tokens board, kiosk
                     ATP + IMCI rules; note is built;      │             links, facility setup, audit
                     daily token T-001… is issued          │
                                   │                       │             Patient
                                   └─► every action is ────┴──────────►  /patient  own visits and
                                       written to the audit log          reminders (no urgency shown)
```

One idea runs through everything: **the system organises and prioritises; a qualified person decides.**

## 2. Who does what

| Role | Signs in at | Main screen | What they do | What they can never see |
|---|---|---|---|---|
| **Supervisor** | `/auth` | `/admin` | Registers the facility, sets facility type and specialists on duty, creates kiosk links / QR posters, watches today's tokens, reviews the audit log and data retention | Symptoms, triage notes, reports |
| **Receptionist** | `/auth` | `/admin` | Watches the token board, calls patients by token, manages kiosk links and staff devices | Symptoms, triage notes, reports |
| **Nurse / ANM** | `/auth` | `/reviewer` (nurse view) and `/kiosk` | Runs assisted intake on the staff kiosk (and adds vitals), works the "Do now" checklist, asks follow-up questions, escalates | Cannot override urgency, confirm notes or send referrals |
| **Doctor / MO** | `/auth` | `/reviewer` | Works the queue top-down, reviews the note with its sources, confirms or edits, overrides urgency with a written reason, acknowledges escalations, sends referrals, exports | — |
| **Patient** | `/auth` | `/patient` | Adds a new problem before arriving, sees own visits, tokens and check-up reminders | Urgency, triage notes, other family members' records |
| **Employer / HR** | `/auth` | `/employer` | Sees fitness status of worker cohorts (fit / restricted / unfit / pending) | Any clinical record |
| **Kiosk link** (no login) | opens `/k/CODE` | intake only | Registers a patient, records consent, takes symptoms and reports, issues a token | Everything else — it cannot read any data |

## 3. Setting up a new facility (once)

1. **Supervisor registers** at `/auth → Register`: role *Supervisor* → name → choose **"+ Register a new facility"** (name, type, district, state) → phone → OTP → accept terms → optional PIN.
2. **Facility setup** (`/admin/facility`): pick the facility type, answer the "what is available here" questions (lab, ECG, X-ray, oxygen…), switch specialists on/off as they arrive or leave, set the default referral hospital and kiosk languages. Referral notes use this automatically.
3. **Kiosk links** (`/admin/kiosk-links`): create one link per place patients check in ("OPD waiting area", "Camp tablet 2"). Each link has a URL like `https://jeevia-triage.vercel.app/k/7QX4MPA2`, a short code and a printable QR poster. Revoking a link stops every device using it immediately.
4. **Staff join**: doctors, nurses and receptionists register themselves at `/auth`, choosing this facility (doctors and nurses give their council registration number). The supervisor sees them under **Staff**.

## 4. A patient's journey, step by step

### 4.1 Check-in — three ways in
| Channel | Where | Who operates it | Notes |
|---|---|---|---|
| **Kiosk link** | `/k/CODE` on a waiting-room tablet, or scanned QR on the patient's own phone | The patient (or family member) | No login. Works in any tab or device. |
| **Staff kiosk** | `/kiosk` on a bound tablet | Nurse / ANM sitting with the patient | Can search existing patients and add vitals. The tablet must be bound to the facility once. |
| **Patient app** | `/patient/new` | The patient, from home | For registered patients; they choose the facility they will visit. |

### 4.2 Intake (all channels)
1. **Consent** — "I am the patient" or "I am helping" (proxy name + relationship), and where it is being filled (private / shared space / assisted). Nothing is saved without consent.
2. **Who** — new patient (name, age, sex, phone) or returning. At a kiosk link, returning patients type the ID on their old token **and** their phone; there is no search, so nobody can browse other patients.
3. **Visit type** — unwell / pregnancy check-up / long-term illness. Pregnancy and long-term illness add their own questions (weeks pregnant, reminder channel; condition, medicines, better/same/worse).
4. **Symptoms** — tap the mic and speak in their language (the kiosk reads it back and asks "Is this what you said?"), tap picture tiles, or type.
5. **Since when / how bad** — big buttons.
6. **Reports or photos** — photograph a lab slip or the affected area.
7. **A few more questions** — bounded questions the reviewer will need (e.g. "Does the pain spread to the arm?").
8. **Vitals** — staff kiosk only.
9. **Submit → token**. The patient sees a large token (e.g. **T-014**) and a QR with their patient ID. They never see urgency. Shared tablets return to the start screen after a minute.

If the network is down, the intake is saved on the device and sent automatically when the connection returns; the token then shows as `OFF-xxxx` and the real wait time is kept.

### 4.3 What the system does on submit
1. **Rules engine** assigns urgency from fixed rules — e.g. chest pain spreading to the arm → *Critical* (ATP-CARD-01); child under 5 with a convulsion → *Critical* (IMCI-DANGER-01); fever ≥ 3 days → *Semi-urgent*. No AI model can set or lower urgency.
2. **Triage note** is built: summary, flags, vitals and report values (each shown beside the cropped image or transcript it came from), disagreements between sources ("needs checking"), timeline, missing information, follow-up questions, and trends against earlier visits.
3. **Token** — the facility's next number for the day (T-001, T-002 …, restarting at midnight).
4. **Routing** — if the needed specialist is not on duty, the case is pre-marked "Referral needed".
5. **Audit** — the intake, consent and any source disagreement are written to the audit log.

### 4.4 Front desk (receptionist / supervisor)
`/admin` → **Today's tokens** updates every 10 seconds: token, name, patient ID, how they checked in, waiting time and status (*Waiting → With doctor → Seen / Referred / Escalated*). Staff call patients by token. The front desk never sees symptoms or urgency.

### 4.5 Nurse
`/reviewer` shows the same queue. Opening a case gives the **nurse view**: *Do now* (flags), vitals to re-measure, questions to ask, missing information. A nurse can edit the note and **escalate** ("SpO₂ dropping — needs senior review now").

### 4.6 Doctor
1. **Queue** (`/reviewer`) — ordered by urgency, then waiting time; each row shows the token, flags, "needs checking" counts and an auto-escalation timer.
2. **Case** — patient card (token, consent, proxy), referral yes/no, summary, flags, rules trace, source disagreements, vitals and report values with their image crops, trends, timeline, missing info, follow-ups. A timer shows the 4-minute review target.
3. **Decide**
   - **Confirm note** — marks it reviewed and signed.
   - **Edit** — change the summary or missing-information list (attributed to them).
   - **Override urgency** — choose the new level, a category and a written reason (≥ 15 characters). The original rules output is kept for audit.
   - **Escalate** to a senior MO / specialist; the receiver must **acknowledge** it in *Escalations*.
   - **Referral note** — destination is suggested from the facility's specialist settings; choose transport (108 / facility vehicle / self), edit, send, print.
   - **Export** — PDF, print, JSON, CSV or FHIR R4.
4. **Safety nets** — unreviewed *Critical* cases auto-escalate after 15 minutes (*Semi-urgent* after 60).

### 4.7 After the visit
- The patient sees the visit as *Reviewed by a doctor* or *Referred* in `/patient`, plus any check-up reminders (SMS or voice).
- Raw voice recordings are deleted after 24 hours, photos after 3 days and reports after 7 days (`/admin/retention`); the structured note stays.
- Every view, edit, override, referral and export is in the hash-chained audit log (`/admin/audit` → *Verify chain*).

## 5. Signing in

- **First time:** phone → one-time code by SMS (Twilio Verify) → register → optional PIN.
- **Next time:** phone + code, or phone + PIN on the same device (a PIN only works on the device where it was created).
- **Sample walkthrough accounts** (code `123456`): doctor 9000000001, nurse 9000000002, receptionist 9000000003, supervisor 9000000004, employer 9000000005, patient 9876543210. They belong to the sample facility *PHC Manikpur*, whose kiosk link is `/k/MANIKPUR`.

## 6. Where things run

| Part | Where |
|---|---|
| Website, dashboards, kiosk | Vercel — `https://jeevia-triage.vercel.app` |
| API | Render web service `jeevia-api` |
| Database | Render PostgreSQL `jeevia-db` (locally: Homebrew Postgres 15, database `jeevia`) |
| SMS one-time codes | Twilio Verify |
| Uploaded reports and photos | Cloudflare R2 bucket (S3-compatible) |
