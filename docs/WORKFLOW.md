# How Jeevia works — roles, dashboards and the patient journey

Written for the Jeevia team and for facility staff learning the system.

## 1. The big picture

```
 PATIENT CHECKS IN                    SYSTEM                              CLINICIANS REVIEW
 ─────────────────                    ──────                              ─────────────────
 Kiosk link /k/CODE  ─┐                                                  Doctor / Nurse
 (tablet or own phone)│   consent → symptoms → reports →   ┌──────────►  /reviewer  queue ordered by
 Staff kiosk /kiosk  ─┼─► follow-up questions → submit ────┤             urgency → case → confirm /
 From home /k/MKHOME ┘             │                       │             override / escalate / refer
                                   ▼                       │
                     Rules engine sets urgency (red /      │             Receptionist / Supervisor
                     yellow / green) from fixed AIIMS      ├──────────►  /admin  tokens board, kiosk
                     ATP + IMCI rules; note is built;      │             links, facility setup, audit
                     daily token T-001… is issued          │
                                   │                       │
                                   └─► every action is written to the audit log
                     From home: an H- reference; joins the queue only when the desk checks the patient in
```

One idea runs through everything: **the system organises and prioritises; a qualified person decides.**

## 2. Who does what

| Role | Signs in at | Main screen | What they do | What they can never see |
|---|---|---|---|---|
| **Supervisor** | `/auth` | `/admin` *(Facility supervisor)* | Picks the facility from the national directory (or adds a missing public one), sets facility type and specialists on duty, creates kiosk links / QR posters, manages staff (role, deactivate, **reset PIN**, on/off duty), staff devices, audit log and data retention | Symptoms, triage notes, reports, patient documents |
| **Receptionist** | `/auth` | `/desk` *(Front desk)* | Today's patients and waiting times, finds and registers patients, corrects registration mistakes, marks doctors and nurses on/off duty, runs the check-in kiosk | Symptoms, urgency, notes, documents; facility setup, kiosk links, devices, audit, staff accounts |
| **Nurse / ANM** | `/auth` | `/nurse` *(Nursing station)* and `/kiosk` | Patients to attend, **records vitals and bedside observations**, works the "Do now" checklist and questions, alerts the doctor, runs assisted intake | Referrals, QR summaries, exports, overrides, sign-off, fitness |
| **Doctor / MO** | `/auth` | `/reviewer` *(Medical officer)* | Works the queue top-down, reviews the note with its sources and the nurses' observations, confirms or edits, overrides urgency with a written reason, acknowledges escalations, sends referrals, exports, shares QR summaries | — |
| **Employer / organisation** | `/auth` | `/employer` | Registers the organisation and its workplaces (company clinic, industrial unit, campus, health camp), keeps the worker roster, sees each worker's fitness outcome (fit / restricted / unfit / pending) | Symptoms, notes, documents — any clinical record |
| **Kiosk link** (no login) | opens `/k/CODE` | intake only | Registers a patient, records consent, takes symptoms and reports, issues a token | Everything else — it cannot read any data |

## 3. Setting up a facility (once)

### 3.1 Government and private health facilities
Jeevia ships with a **directory of India's health facilities** — sub-centres, PHCs, CHCs, district and sub-district hospitals, medical colleges, ESI dispensaries, AYUSH centres, private hospitals and clinics in all 36 states and UTs (from OpenStreetMap, © OpenStreetMap contributors, ODbL). Staff search it by name, district or PIN code when they register.

1. **Supervisor registers** at `/auth → Register`: role *Supervisor* → name → **Workplace**: search the directory and pick the facility. If a public facility is missing, the supervisor adds it (name, type, state, district, PIN code); it is marked *self-registered* until verified → phone → OTP → **create PIN** → accept terms. The facility becomes active on Jeevia the moment its first staff member joins.

### 3.2 Company clinics, industrial units, campuses and health camps
These are **not** in the public list. They appear only after their organisation registers:

1. **Employer registers** at `/auth → Register`: role *Employer / Organisation* → name → organisation (name, type, CIN, state, district) and its **first workplace health centre** → phone → OTP → create PIN → terms.
2. The workplace is now searchable. The organisation's doctors, nurses, receptionists and supervisor register and pick it.
3. In `/employer` the employer adds more workplaces, keeps the **worker roster** (one by one or CSV import: `employee_code, name, age, sex, department, phone`) and edits the organisation profile.
4. When a worker checks in at that workplace, the kiosk asks for the **employee / student ID**; the visit is linked to the roster entry (same name or phone), and the doctor records the fitness outcome on the case.

### 3.3 Then, for every facility
2. **Facility setup** (`/admin/facility`): pick the facility type, answer the "what is available here" questions (lab, ECG, X-ray, oxygen…), switch specialists on/off as they arrive or leave, set the default referral hospital and kiosk languages. Referral notes use this automatically.
3. **Kiosk links** (`/admin/kiosk-links`): create one link per place patients check in ("OPD waiting area", "Camp tablet 2"). Each link has a URL like `https://ps-03-bput.vercel.app/k/7QX4MPA2`, a short code and a printable QR poster. Revoking a link stops every device using it immediately.
4. **Staff join**: doctors, nurses and receptionists register themselves at `/auth`, searching for this facility (doctors and nurses give their council registration number) and creating their PIN. The supervisor sees them under **Staff**, where they can change a role, deactivate or reactivate an account, and reset a forgotten PIN.

## 4. A patient's journey, step by step

### 4.1 Check-in — three ways in
| Channel | Where | Who operates it | Notes |
|---|---|---|---|
| **Kiosk link** | `/k/CODE` on a waiting-room tablet, or scanned QR on the patient's own phone | The patient (or family member) | No login. Works in any tab or device. |
| **Any-centre form** | `/k/ANYCARE` (landing: *Not sure where you will go?*) | The patient, before choosing a centre | No login. Gives a **J-** reference and QR. At any centre the desk or nurse types it or scans the QR (*Patient has a form reference?*): the intake moves there and the patient is checked in with a T- token. A danger sign: go to the nearest emergency or call 108 and show the reference. |
| **Staff kiosk** | `/kiosk` on a bound tablet | Nurse / ANM sitting with the patient | Can search existing patients and add vitals. The tablet must be bound to the facility once. |
| **From-home link** | `/k/CODE` of a link marked *for filling in from home* (SMS, poster, website); sample `/k/MKHOME` | The patient, before coming | No login, no patient account (the plan has no patient portal). The intake gets an **H-** reference and waits on the desk's token board as *Expected*. When the patient arrives the desk presses **Checked in**: a T- token is issued and waiting time and escalation timers start then, so filling in early never puts anyone ahead of people already waiting. If a danger sign was reported, the patient is told to go to emergency or call 108 (never a tier), and the case goes straight to the doctors' queue. |

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

### 4.4 Front desk (receptionist)
`/desk` → **Today's patients**: waiting now, with doctor, seen today, average and longest wait, doctors on duty. **Today's tokens** updates every 10 seconds: token, name, patient ID, how they checked in, waiting time and status (*Waiting → With doctor → Seen / Referred / Escalated*). Staff call patients by token. The pencil on each row corrects a registration mistake (name, age, sex, phone, language, village); the audit log records which fields changed.
- **Find & register** (`/desk/patients`): search by phone, patient ID or name; edit details; register new patients through the check-in kiosk.
- **Doctors & nurses** (`/desk/staff`): switch each doctor or nurse on/off duty as they arrive or leave (time management). A warning shows when no doctor is on duty.
- The front desk never sees symptoms, urgency or documents, and has no facility setup, kiosk-link, device, audit or staff-account tools — those are the supervisor's (`/admin`), and the API refuses them to receptionists.

### 4.5 Nurse (`/nurse`)
- **Patients to attend** lists everyone waiting, with *Vitals needed* first, urgency colour and waiting time.
- Opening a patient (`/nurse/patient/…`) shows **Record vitals & observations** (BP, pulse, SpO₂, temperature, respiratory rate, glucose and a free-text nursing observation), the nurse checklist (*Do now*, questions to ask, still missing), the visit's reports and photos, and **Alert doctor**.
- Saved observations go on the patient's record with the nurse's name. The fixed rules run again on the new vitals, so a low SpO₂ raises urgency automatically; the doctor sees every observation on the case.
- Nurses have no referral, QR summary, export, override, sign-off or fitness tools — the API enforces this too.

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
   - **Edit details** — correct the patient's registration details.
   - **Record fitness** — for workers on an organisation's roster: fit / fit with restrictions / temporarily unfit / pending, restrictions and a validity date. The employer sees only this outcome.
4. **Safety nets** — unreviewed *Critical* cases auto-escalate after 15 minutes (*Semi-urgent* after 60).

### 4.7 Referral hand-off with a QR summary
1. On the case, the doctor presses **Share QR** (or keeps **Attach QR summary** ticked when sending a referral).
2. Jeevia creates a link valid for 24 hours to 30 days and shows a **QR code** plus a **6-digit access code** (shown once). **Print slip** gives a one-page slip with both.
3. The receiving clinician scans the QR (`/s/…`), enters the code and sees: patient details, token, urgency and any override, the reviewed summary, flags, vitals and report values, the referral, and the **uploaded documents** (prescriptions, lab slips, photos) to view or print.
4. Eight wrong codes lock the link; the doctor can revoke it any time from the same dialog; every opening is in the audit log.

### 4.8 Who can open a patient's documents and photos
Reports, prescriptions and photos a patient uploads open only for:
- the **doctors and nurses at the facility treating that visit**,
- the **patient** (their own files),
- whoever holds a **QR summary link and its access code** (§4.7).

Receptionists, supervisors, employers and staff at other facilities get *"Only the doctors and nurses treating this patient can open their documents"*. Every opening is written to the audit log.

### 4.9 After the visit
- The patient gets the clinician-issued slip (follow-up date, referral, QR for staff; never an urgency tier) and any check-up reminders (SMS or voice). There is no patient portal.
- Raw voice recordings are deleted after 24 hours, photos after 3 days and reports after 30 days (`/admin/retention`); the structured note stays.
- Every view, edit, override, referral and export is in the hash-chained audit log (`/admin/audit` → *Verify chain*).

## 5. System status

The landing page shows live status (checked every 20 seconds) for the website, API server, database, SMS codes and document storage, and the header shows a coloured dot. On the free Render plan the API sleeps after 15 idle minutes; **Wake server** brings it back in 30–60 seconds, and a scheduled GitHub workflow pings it every 10 minutes to keep it awake. Signed-in supervisors also get **Restart server** once a Render API key is configured.

## 6. Signing in (two-factor for staff and employers)

- **Patients:** phone → one-time code by SMS. That is all.
- **Email instead of SMS (optional):** when the server has email codes on, the sign-in and registration screens offer *Mobile (SMS)* or *Email*. Registering by email still records the mobile number. Anyone signed in can add or change a verified email from the envelope icon in the header.
- **Doctors, nurses, receptionists, supervisors and employers:** two factors every time —
  1. phone → one-time code (proves the phone), then
  2. their **account PIN** (4–6 digits, chosen at registration; proves the person).
- **PIN rules:** easy PINs (1234, 0000, 1111, 2580, birthdays-style repeats, straight sequences) are refused. Five wrong PINs lock the account for 15 minutes.
- **Change PIN:** the key icon in the dashboard header (needs the current PIN).
- **Forgot PIN:** supervisors and employers reset it themselves after the OTP (*Forgot PIN?*). Doctors, nurses and receptionists ask their supervisor (**Admin → Staff → Reset PIN**); they then create a new PIN after their next OTP.
- **Rate limits:** 3 codes per phone per 10 minutes, 10 per day, 30 per network address per hour; the message says how long to wait. Sample numbers are exempt (they never send an SMS).
- **Sample walkthrough accounts** (code `123456`, staff PIN `4826`): doctor 9000000001, nurse 9000000002, receptionist 9000000003, supervisor 9000000004, employer 9000000005. Patients have no login; the from-home kiosk link is `/k/MKHOME`. They belong to the sample facility *PHC Manikpur* (kiosk link `/k/MANIKPUR`) and the sample organisation *Kalinga Steel Works*.
- **New accounts start empty:** a number that already has an account cannot be used to register again (sign in instead), the sample numbers are reserved, and the sample facility cannot be joined — so a newly registered doctor, nurse or employer always gets their own fresh dashboard.

## 7. Language

- The language picker (globe) in every header switches **every screen** — website, sign-in, all dashboards and both kiosks — between English, हिन्दी and ଓଡ଼ିଆ at any time.
- Each person's choice is saved to their account: when they sign in on any device, their dashboard opens in their language. (The sample nurse, receptionist and patient prefer Hindi.)
- On a kiosk the patient picks their own language; it applies to every question and answer, the microphone listens in that language, and questions are read aloud in it. Changing language on a shared kiosk never changes the unlocking staff member's own preference.
- Read-aloud needs a voice for that language on the device (Android: Settings → Text-to-speech → install Odia/Hindi). If it is missing the kiosk says so instead of reading Odia text with an English voice.
- Clinical notes stay in the working language (English) for the reviewing clinician; the patient's original words are kept beside them.

## 8. Kiosk links offline

Open a kiosk link once with internet and it keeps working without it: the page, the facility details and the kiosk session stay on the device. Intakes made offline get an `OFF-xxxx` slip, wait in that link's own queue on the device, and are sent automatically — with that kiosk's session — as soon as the connection returns.

## 9. Where things run

| Part | Where |
|---|---|
| Website, dashboards, kiosk | Vercel — `https://ps-03-bput.vercel.app` |
| API | Render web service `jeevia-api` |
| Database | Neon serverless PostgreSQL, project `jeevia`, Singapore (locally: Homebrew Postgres 15, database `jeevia`) |
| SMS one-time codes | Twilio Verify |
| Uploaded reports and photos | Cloudinary (private, `jeevia/<facility>/<yyyy-mm>/<kind>/`), served only through the API with signed downloads |
