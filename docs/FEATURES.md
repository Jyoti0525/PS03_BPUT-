# Jeevia: every feature, what it uses, and where it lives

This guide is for anyone on the team who needs to know what has been built, how each part works, which tools,
models and data it uses, and where to find the code. Use it to answer a judge's question, to change a feature, or
to get up to speed after time away.

- **State as of 5 Oct 2026.** [TODO.md](TODO.md) is the live checklist: if the two disagree, TODO.md wins.
- **Measured figures** (speech accuracy, model pass rates) are in [EVALUATION.md](EVALUATION.md), with how to
  reproduce each one.
- **Screens, role by role:** [WORKFLOW.md](WORKFLOW.md). **API endpoints and role matrix:** [ARCHITECTURE.md](ARCHITECTURE.md).

**Status words used below**
- **Working**: built and checked in the running app.
- **Partial**: some of it works; the "Left" line says what is missing.
- **Not built**: planned only.

---

## Contents

1. [The one rule behind every feature](#1-the-one-rule-behind-every-feature)
2. [One check-in, start to finish](#2-one-check-in-start-to-finish)
3. [Everything we use](#3-everything-we-use)
4. [Features](#4-features)
   - [A. Getting information in](#a-getting-information-in)
   - [B. Reading and understanding](#b-reading-and-understanding)
   - [C. Triage decisions](#c-triage-decisions)
   - [D. The seven scenarios](#d-the-seven-scenarios)
   - [E. Human review and hand-off](#e-human-review-and-hand-off)
   - [F. India context and set-up](#f-india-context-and-set-up)
   - [G. Privacy, safety and responsible AI](#g-privacy-safety-and-responsible-ai)
   - [H. Platform](#h-platform)
5. [Flags a reviewer can see on a note](#5-flags-a-reviewer-can-see-on-a-note)
6. [Running the full demo on the laptop](#6-running-the-full-demo-on-the-laptop)
7. [Tests](#7-tests)
8. [Words used in this guide](#8-words-used-in-this-guide)

---

## 1. The one rule behind every feature

**Rules decide, the model writes, humans confirm.**

- **Urgency** (RED, YELLOW, GREEN) comes only from fixed rules taken from published triage protocols. No AI model
  can set, raise or lower it.
- **AI models** turn speech into text, translate, read printed reports and write a readable summary. Each output
  names the engine that made it. Each one is checked, and anything doubtful is marked for a human.
- **Clinicians** confirm, edit or override, and every action is written to a tamper-evident audit log.
- **Jeevia never diagnoses or prescribes.** A guard blocks disease names and medicine advice that are not already
  in the patient's own data.

---

## 2. One check-in, start to finish

Each step names the feature code (see section 4) and the main file.

1. **Consent** (G1). The patient or a family member agrees, and chooses "Use AI helpers" or "Continue without AI".
   `frontend/src/components/intake/intake-flow.tsx`
2. **Symptoms** (A1, A2). The patient speaks, taps pictures or types, in their own language. Speech is turned into
   text on the facility machine, read back aloud and confirmed. `backend/app/language.py`
3. **Identifiers removed** (G3). Names, phone, Aadhaar and ABHA numbers in the free text become `[NAME]`,
   `[PHONE]` and so on, before anything is stored or translated. `backend/app/privacy.py`
4. **Translation** (A3). Indian-language text is translated to English, and the original words are kept beside
   it. `backend/app/language.py`
5. **Reports and photos** (A4, A5, B1, B10). Each upload is read (OCR), labelled (lab report, medicine strip and so
   on) and redacted (faces blurred, ID numbers blacked out) before it is stored.
   `backend/app/triage/extraction.py`, `backend/app/triage/images.py`
6. **Findings and urgency** (C1). The rules engine turns everything into findings (present, absent or unknown) and
   sets urgency from 161 cited rules. `backend/app/triage/findings.py`, `backend/app/triage/rules.py`
7. **Note** (B4, B5, B6). The note builder lists values with their sources, the onset timeline, missing information
   and flags. A small local model then writes a summary paragraph, which is used only if it passes every check.
   `backend/app/triage/pipeline.py`, `backend/app/llm.py`
8. **Token and queue** (C3). The patient gets a token (T-001…). The case enters the doctor's queue, ordered by
   urgency and then waiting time, and each row says why it is there. If open RED cases outnumber the doctors and
   medical officers on duty, the medical officer gets a capacity alert.
9. **Review** (E1, E3). The nurse adds vitals, which re-runs the rules. The doctor confirms, edits, overrides with
   a reason, or escalates. Unreviewed RED cases escalate on their own after 15 minutes.
10. **Hand-off** (D7, E4, E7). The case is referred with a QR summary, or exported as PDF, JSON, CSV or FHIR.

Every view and change along the way is written to the audit log (G4).

---

## 3. Everything we use

### Software and services

| What | Used for | Where it runs |
|---|---|---|
| **Next.js 16**, React 19, TypeScript, Tailwind CSS v4 | Every screen: website, kiosk, dashboards, share pages. Installable app (PWA) with a service worker for offline use | Browser; hosted on Vercel |
| SWR, idb-keyval, qrcode.react, lucide-react | Data fetching, offline queue in IndexedDB, QR codes, icons | Browser |
| **FastAPI** (Python 3.12), SQLAlchemy 2, Pydantic 2, Alembic | The API, database models, input checks, database migrations | Facility machine, or Render |
| **PostgreSQL** (Neon, Singapore) / SQLite | Database. JSONB holds intake and notes. SQLite is used for local runs and tests | Neon / local |
| PyJWT, PBKDF2-SHA256 (Python standard library) | Sign-in sessions; PIN and code hashing | API |
| **Twilio Verify** | SMS sign-in codes | Cloud |
| **Brevo** (optional) | Email sign-in codes | Cloud |
| **Cloudinary** (private), or S3 / R2, or local disk | Storing reports and photos with an expiry date | Cloud / local |
| fpdf2 | PDF export | API |
| **GitHub Actions** | Tests, lint and build on every push (`ci.yml`); a ping that keeps the free Render server awake (`keepalive.yml`) | GitHub |

### AI models and engines (all offline, on the facility machine)

| Engine | Made by, licence | Used for | Size and speed on the demo laptop |
|---|---|---|---|
| **IndicConformer-600M multilingual**, 8-bit ONNX copy, run with ONNX Runtime | AI4Bharat, MIT | Speech to text in the 22 scheduled languages (A2) | 0.9 GB on disk, 1.6 GB RAM; 0.26 s per second of speech (CPU) |
| **IndicTrans2 distilled 200M**, with IndicTransToolkit | AI4Bharat, MIT | Indian language ↔ English translation (A3) | 1–2 s per sentence (CPU); only Indic → English is loaded at start-up |
| **RapidOCR**: PaddleOCR PP-OCR models on ONNX Runtime | RapidAI / PaddlePaddle, Apache-2.0 | Reading photos of reports, strips and prescriptions (B1) | CPU |
| **pypdfium2** | Apache-2.0 / BSD | Text from PDFs; page images from scanned PDFs (H0) | CPU |
| **OpenCV** | Apache-2.0 | Photo quality check (blur, darkness, glare); face blurring | CPU |
| **YuNet** face detector (`face_detection_yunet_2023mar.onnx`, 230 KB, kept in the repo) | Shiqi Yu / OpenCV Zoo, MIT | Finding faces to blur before a photo is stored (G3) | CPU; falls back to OpenCV's Haar detector |
| **Qwen3-4B-Instruct-2507**, 4-bit GGUF (Q4_K_M, quantised by Unsloth) | Alibaba Qwen, Apache-2.0 | Writing the summary paragraph of a note (B5) | 3.1 GB of GPU memory (RTX 3050); median 0.8 s per note |
| **llama.cpp** `llama-server`, build b11424, CUDA 12.4 | ggml-org, MIT | Serving Qwen3 on the laptop GPU at `127.0.0.1:8031` | — |

The hosted API on Render installs only `backend/requirements.txt`, without these engines. On the public link,
speech, translation, OCR and the summary model therefore report "unavailable" and the rest still works. The full
AI stack runs on the demo laptop (`backend/requirements-ml.txt`, models in `models/`, fetched by
`backend/scripts/fetch_models.py`).

### Data

| Data | Source and licence | Used for |
|---|---|---|
| Triage protocols | AIIMS Triage Protocol (ATP); WHO/ICRC/MSF Interagency Integrated Triage Tool (IITT); WHO IMCI 2014; WHO PCPNC; ISSHP 2021; RCOG GTG 57; ADA; WHO Pocket Book; WHO haemoglobin thresholds. Full citations in `backend/app/triage/rules/sources.yaml` | The rules (C1) |
| Medicine names | PMBJP list of 2,110 generic medicines, Press Information Bureau (Govt of India), [PDF](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/feb/doc202626781701.pdf). The [PIB copyright policy](https://www.pib.gov.in/content/102_2_Copyright-Policy.aspx) allows reproduction with acknowledgement. 1,087 unique names, in `backend/app/triage/data/medicines_pmbjp.txt` | Matching names on medicine strips (B10) |
| Health facilities in India | OpenStreetMap contributors, ODbL, in `backend/directory_data/facilities_in.jsonl.gz` | The facility search at sign-up |
| Speech test clips | Google FLEURS, CC-BY-4.0 | Measuring speech accuracy only; never stored in the app |
| Patients, reports, test cases | Written by us; all synthetic | Demo, tests and evaluation |

**No real patient data is used anywhere.**

---

## 4. Features

Feature codes match [TODO.md](TODO.md). Paths are from the repo root.

### A. Getting information in

**A1 Guided text intake** · Working
- **What:** a step-by-step check-in: consent → who (new or returning) → visit type → symptoms → since when and how
  bad → pregnancy or long-term-condition questions → reports and photos → follow-up questions → nurse vitals →
  review → token.
- **Uses:** React; the question list in code.
- **Code:** `frontend/src/components/intake/intake-flow.tsx`, `catalog.tsx`; `backend/app/routers/encounters.py`.
- **Limit:** the question flow is in code, not in a config file.

**A2 Voice intake** · Partial
- **What:**
  - The kiosk records the patient and sends the audio to the facility server, which returns a transcript and an
    English translation, each naming its engine.
  - The transcript is read back aloud; the patient confirms or records again.
  - Silent, too-short or unreadable recordings are refused with a message. No transcript is ever made up.
  - If the server is unreachable, the browser's own speech recognition is used where available, and labelled as
    such.
- **Uses:** IndicConformer-600M (8-bit, CTC decoding) on ONNX Runtime; MediaRecorder in the browser; browser speech
  synthesis for the read-back.
- **Code:** `backend/app/language.py`, `backend/app/routers/language.py` (`POST /speech/transcribe`);
  `frontend/src/lib/speech.ts`.
- **Measured:** Odia, 25 FLEURS clips: 21.6 % word error, 5.6 % character error (details in EVALUATION.md).
- **Live test (5 Oct, laptop microphone, 3 Odia + 2 Hindi sentences):** Hindi transcripts were word-perfect. Odia was
  close but written as spoken: ଜର for ଜ୍ୱର, ଦରଦ for ଦରଜ, ଦିଇ for ଦୁଇ. The symptom word list now matches spoken
  spellings (see A3).
- **Left:** measuring the other languages; a confidence threshold; Bhashini as a second engine.

**A3 Translation** · Partial
- **What:**
  - Indian-language text is translated to English on submission, by the server, from the patient's own words (English
    sent by the browser is not trusted). The original words stay beside the translation, unchanged.
  - The rules read both, so a wrong translation cannot hide a symptom.
  - **What the live test found (5 Oct):** the translator dropped "fever" when it was spoken as ଜର, turned ଝାଡ଼ା
    (loose stools) into "sweating" every time, and turned ଛପନ (56) into "sixty-six". Three fixes:
    1. **Standard words for the translator only** (`prepare` in `backend/app/mt_checks.py`): ଜର → ଜ୍ୱର, ଝାଡ଼ା as loose
       stools → ଅତିସାର, ଝାଡ଼ାରେ → ମଳରେ, negated ଝାଡ଼ା → "ମଳ ବାହାରୁ ନାହିଁ", and number words before a time unit or age
       → digits (Hindi and Odia, 1–100). Each rewrite was tested on the model; ଡାଇରିଆ was rejected because the
       model read it as "diary". The note lists every rewrite.
    2. **Cross-check against the patient's words** (`translation_check` in `backend/app/triage/findings.py`): the
       symptoms found in the Hindi/Odia are compared with those found in the English. A symptom the translation
       left out, or one it added, turns MT-CHECK into a warning that names the sentence. A symptom found only in the
       translation still counts for urgency (missing a real symptom is worse) but its evidence says "machine
       translation only".
    3. **Near-equal candidates** (`unsure` in `mt_checks.py`, all 22 languages, no word list needed): the beam
       search's other top translations are compared with the best one. If they disagree on a number ("66 or 56")
       or a symptom, the note says so. Digits in the patient's words that are missing from the English are flagged
       too.
  - Every translated note carries the MT-CHECK flag; it is a warning when any check above finds a problem.
- **Uses:** IndicTrans2 distilled 200M, full precision. An 8-bit copy was tried and rejected because it turned
  "vomiting" into "nausea".
- **Code:** `backend/app/language.py` (`translate_patient`), `backend/app/mt_checks.py`. Translations run one at a
  time per direction: two at once froze the server (fixed 5 Oct, regression test in `backend/tests/test_language.py`).
- **Measured:** with the fixes, the three Odia sentences from the live test translate correctly (fever kept,
  diarrhoea not sweating, 56 not 66), checked by a test that runs the real model.
- **Needs a native speaker:** the Odia number list and spoken-spelling list in `mt_checks.py` and `findings.py`.
- **Left:** Bhashini online; English → Indian language for patient slips.

**A4 Report upload** · Working
- **What:** PDFs and photos, several per visit. Photos are compressed in the browser before upload.
- **Uses:** `frontend/src/lib/image.ts`; `backend/app/routers/files.py`; `backend/app/storage.py`.
- **Storage:** Cloudinary private assets, S3 or local disk. Files are served only through the API, to people
  allowed to see them, with signed links that expire after 10 minutes.

**A5 Basic visual inputs** · Working
- **What:** besides reports, a patient can add a "photo of the problem". It is redacted before storage, attached for
  the clinician, and **never interpreted**.
- **Code:** `backend/app/routers/files.py`, `backend/app/triage/images.py`.

**A6 Patient identity and matching** · Partial
- **What:** returning patients are found by patient ID and phone. On a shared household phone, the patient picks
  their own name.
- **Code:** `backend/app/routers/kiosk.py` (`/kiosk/identify`), `backend/app/services.py` (`own_patient`).
- **Left:** confirm that matches are always picked by a human and logged.

**A7 Spoken read-back and prompts** · Partial
- **What:** read-back in the patient's language using a voice installed on the device. If the device has no voice
  for that language, nothing is spoken, rather than an English voice mangling Odia.
- **Uses:** browser `speechSynthesis` (`frontend/src/lib/speech.ts`).
- **Left:** check Odia voice quality on the demo laptop.

**A8 Vitals entry** · Partial
- **What:** nurses record BP, pulse, temperature, SpO₂, breathing rate, glucose, AVPU and the danger-sign
  checklist. New vitals re-run the rules.
- **Code:** `frontend/src/components/triage/observations.tsx`; `POST /encounters/{id}/observations`.
- **Left:** unit lock, plausibility bounds, and a "not measured" option.

### B. Reading and understanding

**H0 Text layer before OCR** · Working
- A PDF that already has text is read directly, with no OCR. Scanned pages are turned into images and sent to OCR.
- **Uses:** pypdfium2 (`backend/app/triage/extraction.py`).

**B1 OCR for lab reports** · Working
- **What:** reads printed reports offline. A quality check runs first and asks for a retake if the photo is:
  - blurry (Laplacian variance below 60);
  - too dark (mean brightness below 70);
  - low-contrast or glaring;
  - smaller than 500 px on its shorter side.
- **Uses:** RapidOCR (PaddleOCR models on ONNX Runtime); OpenCV.
- **Code:** `backend/app/triage/extraction.py`; tests in `backend/tests/test_extraction.py`.
- **Limit:** handwriting is mostly not readable.

**B2 Number checks** · Partial
- **What:** each test has a plausible range; an impossible value is treated as a misread, not a finding. The report
  date is checked (an old report is flagged) and the name on the report is compared with the patient's.
- **Left:** consistency checks (flag against range, unit sense, WBC differential near 100 %, globulin = total
  protein − albumin).

**B3 Key-detail extraction** · Working
- **What:** a dictionary of 25 common Indian lab tests, with synonyms and common OCR mistakes. For each test it reads
  the value, unit and printed reference range from the same row, plus the exact box on the image. The reviewer sees
  the image crop beside each value.
- **Code:** `TESTS` in `backend/app/triage/extraction.py`; `frontend/src/components/triage/source.tsx`.

**B4 Onset timeline with certainty labels** · Working
- **What:** every onset shows a label, with the patient's own words beside it:
  - **STATED**: "3 days", "since yesterday", ଚାରି ଦିନ ହେଲା;
  - **VAGUE**: "few days", "since Diwali", कई दिन से. A festival or season is looked up in the facility's regional
    calendar (F5); the date it points to is shown beside the patient's words, for example "Around 20 Oct 2025
    (Diwali) · Odisha calendar". The onset stays VAGUE and the rules never use it.
  - **UNKNOWN**: nothing said;
  - **RECORDED**: a dated record.

  It ignores phrases that are not onsets ("3 times a day", "32 weeks pregnant", "2 years old"). If the patient says
  "3 days" but taps "1–4 weeks", the note asks staff to check. A stated onset also feeds the rules when nothing was
  tapped.

  Each sentence the patient said gets its own onset row, from its own words. (The live test showed "2 days" from
  the fever sentence printed against the headache "for a long time"; fixed 5 Oct.)
- **Uses:** phrase lists in English, Hindi (Devanagari and romanised) and Odia. No model.
- **Code:** `backend/app/triage/timeline.py`; 22 tests in `backend/tests/test_timeline.py`.

**B5 Structured note with an AI-written summary** · Working
- **What:** the note holds the summary, flags, rules that fired, vitals and report values with their sources,
  timeline, trends, missing information and follow-up questions. A small local model rewrites the facts as a
  2–4 sentence summary.
- **How the summary is checked:**
  1. The model gets a "fact sheet" of the patient's account and measured values only (`fact_sheet()`).
  2. **Faithfulness check:** every number (including number words), unit and medicine in its text must be in the
     fact sheet. Every symptom it states or denies must agree with the rules engine's findings.
  3. **Output guard (C4):** no disease names, diagnostic wording or medicine advice.
  4. If any check fails, the note keeps the plain template summary. The rejected text and the reason stay visible
     to the reviewer (flag LLM-FELL-BACK).
- **When it runs:** in the background after intake and after new vitals. It never overwrites a clinician's edit,
  and it is skipped for patients who chose "continue without AI".
- **Uses:** Qwen3-4B-Instruct-2507 (4-bit GGUF) on llama.cpp `llama-server`, at temperature 0, on the laptop GPU.
- **Code:** `backend/app/llm.py`; `summarise_later()` in `backend/app/services.py`; `backend/scripts/start_llm.sh`;
  `backend/scripts/eval_llm.py`.
- **Measured:** 30 of 30 tuning cases passed; 18 of 20 held-out cases passed (the other 2 fell back safely);
  0.8 s median.
- **Limit:** the checks catch wrong facts, not tone. We read every output ourselves; no clinician has reviewed them.

**B6 Missing information** · Working
- The note lists what is missing, for example temperature not measured or onset not given. A case stays at
  provisional YELLOW until it is filled in. Built in `backend/app/triage/rules.py` and `pipeline.py`.

**B7 Follow-up questions by role** · Working
- **What:** questions are picked from the findings and the rules that fired, at most 3 per role. The medical officer
  gets system-level questions: transfer (vehicle and receiving bed confirmed for a RED case), the obstetrician at the
  first referral unit for a pregnant woman, and for a workplace case whether to keep the worker away from the
  exposure and that silicosis is notifiable (Factories Act 1948, s.89).
- **Who sees what:** a health worker sees health-worker questions; a nurse sees health-worker and nurse questions; a
  doctor or medical officer sees all. The server filters them, so a role never receives the others' questions.
- **Code:** `FOLLOWUPS`, `questions_for` in `backend/app/triage/pipeline.py`; `note_for` in `backend/app/services.py`.

**B8 Test names to LOINC codes** · Working
- 16 of the 25 tests carry a LOINC code (`TESTS` in `extraction.py`), used in the FHIR export.

**B9 Two engines disagree → flag** · Not built
- Needs Bhashini (speech) or a second OCR engine.

**B10 Image understanding without diagnosis** · Working
- **What:**
  - **Document type:** lab report, prescription, medicine strip, discharge summary, mother-and-child (MCP) card,
    other document, or not a document. Decided by keyword rules, and the label shows the words that decided it.
  - **Medicine names:** read from strips and prescriptions and matched to the PMBJP list, strength included. Each
    one shows "awaiting confirmation" until a nurse or doctor taps Confirm or "Not this". Both actions are audited,
    and only confirmed names enter the record.
- **Uses:** OCR text from B1; Python `difflib` fuzzy matching (similarity of 0.86 or more); the PMBJP list.
- **Live test (5 Oct, phone photo of a paracetamol + phenylephrine + chlorpheniramine strip):** labelled "Medicine
  strip or pack"; all three medicines found. Two fixes followed:
  - a torn piece of a name ("heniramine" from Chlorpheniramine) had matched a different medicine, pheniramine. A
    word that sits inside a longer medicine name read on the same photo is now ignored;
  - strengths printed in a column ("Paracetamol IP …… 500 mg") are now read from the same printed row, including
    OCR's "2m9" for 2 mg. A number with no readable unit shows as "500 (unit not read)".
  The manufacturer's customer-care phone number was blacked out by the privacy step, as designed.
- **Code:** `backend/app/triage/images.py`; `POST /encounters/{id}/medications`;
  `frontend/src/components/triage/medications.tsx`; `backend/scripts/build_medicine_list.py` rebuilds the list;
  12 tests in `backend/tests/test_images.py`.
- **Limit:** handwritten prescriptions will mostly fail.

### C. Triage decisions

**C1 Risk-category tagging** · Working
- **What:** 161 rules in YAML files, each citing its published source:

  | Rule file | Rules |
  |---|---|
  | `atp.yaml` | 31 |
  | `iitt_adult.yaml` | 42 |
  | `iitt_paed.yaml` | 45 |
  | `imci.yaml` | 12 |
  | `maternal.yaml` | 14 |
  | `aiims_hrc.yaml` (C5, adults) | 6 |
  | `occupational.yaml` (D2, only when a workplace exposure is recorded) | 5 |
  | `labs.yaml` | 3 |
  | `local.yaml` (marked "local", never passed off as a guideline) | 3 |

  Protocols are chosen by age, pregnancy and workplace exposure, all applicable sets run, and the highest urgency
  wins.
- **Three-valued logic:** each condition is true, false or unknown. Unknown never counts as normal.
- **Findings** come from staff-recorded signs, then answers, then tapped tiles, then free text in English, Hindi
  and Odia. Negation is understood ("no chest pain", सीने में दर्द नहीं).
- **Uses:** PyYAML and plain Python. No model; the same input always gives the same result.
- **Code:** `backend/app/triage/rules.py`, `backend/app/triage/findings.py`, `backend/app/triage/rules/*.yaml`;
  63 tests in `backend/tests/test_rules.py`.

**C2 Urgency signals highlighted** · Working
- Each fired rule shows the rule, the value that triggered it, where the value came from and the protocol it is
  from.

**C3 Queue order** · Working
- **Order:** urgency, then waiting time; offline check-ins keep their real capture time. Each row says why it is
  there, e.g. "RED (ATP-C-SHOCK-INDEX) · 1st of 2 RED · waiting 18 min, longest first", or "provisional until
  measured" for an undetermined case.
- **Capacity alert:** when open RED cases (not yet confirmed or referred) outnumber the doctors and medical
  officers marked on duty at the front desk, the medical officer gets an alert and every clinical screen shows a
  red banner with the tokens and the longest wait. It closes by itself when the REDs are seen or another doctor
  comes on duty. Checked on every queue read and whenever a case turns RED.
- **Demo:** PHC Manikpur has 2 REDs and 2 doctors on duty; mark Dr. Sharma off duty at the front desk.
- **Code:** `check_capacity`, `order_reasons` in `backend/app/alerts.py`; `GET /capacity`;
  `frontend/src/components/alerts/capacity-banner.tsx`.

**C4 Non-diagnostic output guard** · Working
- **What:** every sentence the model writes is checked against a pattern list in three categories:
  - disease or condition names;
  - diagnostic wording ("likely", "suggests", "consistent with");
  - medicine, dose or treatment advice.

  Each category is covered in English, Hindi (both scripts) and Odia. A phrase passes only if the same words are
  already in the patient's data: "known diabetes" can be repeated, "likely dengue" cannot be added. Common
  misspellings and abbreviations are in the list, and odd letters and hidden characters are normalised first.
- **When it blocks:** the summary falls back to the template, and the audit log records a GUARD_BLOCK event with
  the rejected text.
- **Code:** `backend/app/output_guard.py`, `backend/app/output_guard.yaml`; red-team set in
  `backend/tests/data/redteam_outputs.yaml`.
- **Measured:** 101 of 101 bad sentences blocked; 40 of 40 good sentences passed. We wrote both sets, so this shows
  coverage of the listed patterns, not of every possible phrasing.
- **Guard test page (demo):** Supervisor → *Output guard test* (`/admin/guard-test`). Type a sentence, or pick one
  of 11 from the red-team set (English, Hindi in both scripts, Odia; 8 that should block, 3 that should pass), and
  optionally the data the model was given. The same guard runs and the page shows each matched phrase and its
  category. The page and the audit entry both say it is a test typed by a person, not a model output; it touches no
  patient record. Names and phone numbers in the typed text are removed before it is logged. Endpoints:
  `GET /guard-test/samples`, `POST /guard-test` (supervisor only).

**C5 AIIMS high-risk complaints** · Working
- **Found on 6 Oct:** with normal vital signs, "shortness of breath" and "chest pain" (and the Hindi and Odia
  equivalents) came out GREEN.
- **Fix:** a YELLOW floor for the six chief complaints that a prospective AIIMS New Delhi study found to predict
  death or ICU admission within 72 hours: Rauniyar N, Sahu AK, Gopinath B, et al., *J Emerg Trauma Shock*
  2025;18(2):62–68 (PMID 40666389), 1,225 adults. Odds ratios: shortness of breath 43.7, altered mental status 6.2,
  vomiting blood 3.88, fall from height 3.88, one-sided weakness 3.16, chest pain 1.78. ATP and IITT still decide RED.
- **Applies from age 16** (the study enrolled patients older than 16).
- **Code:** `backend/app/triage/rules/aiims_hrc.yaml`; tests in `backend/tests/test_wednesday.py`.

**C6 Children and trauma** · Working
- IITT child rules with age-banded breathing and heart-rate limits; trauma is never GREEN.

**C7 Unknown is never normal** · Working
- No case is GREEN until vitals, AVPU and the danger-sign check are recorded. Until then it is shown as
  **UNDETERMINED, held at YELLOW**, with the list of what to measure (rule `SAFE-PROVISIONAL`; the label was
  "Provisional" before 6 Oct).

**C8 Rule vs model disagreement view** · Working
- **What:** the note-summary model (Qwen3-4B, offline) is also asked for its own urgency, given the same facts but
  **not** the rules' result. It answers with a tier and the facts that decided it. The rules' tier always stands.
  - **More urgent than the rules:** a warning flag on the note, "AI second opinion is more urgent than the rules —
    take a second look".
  - **Less urgent:** shown only. A model must never be able to talk a case down.
  - **The reason** goes through the faithfulness check and the output guard. A reason that fails is hidden and the
    tier is still shown. An answer the app cannot read is never guessed.
- **Where:** doctor's note → *AI second opinion*, under the rules trace (rules tier beside the model's tier).
  Supervisor → *AI second opinions* (`/admin/ai-opinions`): agreement rate, a rules × model table, and every
  disagreement with the final urgency and any doctor's override. Doctors can call the same endpoint.
- **When it runs:** in the background after the summary. It is skipped if the patient chose "continue without AI"
  (G1), if the model is not running, or if `JEEVIA_LLM_URGENCY_OPINION=false`. Disagreements are written to the
  audit log.
- **Code:** `backend/app/llm.py` (`urgency_opinion`, `OPINION_SYSTEM`), `backend/app/routers/admin.py`
  (`GET /ai-opinions`), `frontend/src/components/triage/note.tsx` (`SecondOpinion`),
  `frontend/src/app/admin/ai-opinions/page.tsx`.
- **Measured (50 synthetic cases, 5 Oct):** agrees with the rules on 29 (58 %). The model was less urgent on 4 RED
  cases and more urgent on 8 provisional YELLOWs; 5 of those 8 are listed for clinician rule review. Median 0.52 s.
  Details: [EVALUATION.md](EVALUATION.md#second-opinion-on-urgency-c8).

### D. The seven scenarios

| Scenario | Status | What exists | Left |
|---|---|---|---|
| **D1** Outpatient queue | Working | Kiosk → rules → queue → review | — |
| **D2** Occupational screening | Working | Employer portal, roster, fitness status; exposure and PPE questions at workplace clinics; 5 occupational rules; FEV1 against the worker's own earliest value; PPE-gap flag; department rates for the employer (no symptoms, departments under 5 hidden) | Rules need review by an occupational physician |
| **D3** Campus fever | Working | Hostel block asked at campus clinics; cluster alert to the campus MO (5+ fevers in 72 h and more than 3× the 14 days before), counts only; syndromic CSV export with counts under 5 written as "<5" | Counts per day and block are small, so most cells are "<5" at demo scale |
| **D4** Maternal follow-up | Working | Whose phone it is and the assigned ASHA asked at a pregnancy visit; missed check-up detected a day after its due date and sent to that ASHA; after 2 failed attempts a reminder call is due; nothing about pregnancy on a husband's or family phone | The call is simulated and in English only |

**D2 Occupational screening, in detail**
- **Questions** (workplace clinics and roster workers): exposures (silica, coal, cotton, asbestos, other dust,
  noise, chemicals, pesticides, heat), years exposed, weeks of cough, breathing compared with the last screening,
  PPE issued and how often worn; FEV1 and FVC when staff measure them.
- **Rules** (`occupational.yaml`, no published Indian occupational triage protocol exists, so they are adapted and
  say so):
  - RED: silica exposure with a presumptive TB symptom (cough 2 weeks or more, coughing blood, weight loss, night
    sweats, fever for 2 weeks), NTEP and WHO TB screening 2021; RED here means same-day doctor review and a sputum
    test.
  - YELLOW: dust with cough or breathlessness for more than 8 weeks (ERS 2020 chronic cough); cough or
    breathlessness after 5+ years of silica; breathing worse than at the last screening; FEV1 down 15 % or more from
    the worker's own earliest value (ATS 2014, without the ageing allowance, so slightly earlier than the standard).
  - A detail not asked counts as not reported, so a screening is never held up; the note lists what is missing.
- **PPE-GAP** is a workplace finding about the employer, not a symptom and not part of urgency.
- **Employer view:** *Workplace screening by department*: screened, % referred for occupational-health review, %
  PPE gap, and a mark when a department is twice the others. A test checks that no symptom word reaches the employer.
- **Code:** `backend/app/triage/rules/occupational.yaml`, `with_fev1_baseline` in `services.py`,
  `GET /employer/department-rates` in `backend/app/routers/alerts.py`, `frontend/src/components/employer/department-rates.tsx`.

**D3 and D4, in detail**
- **Alerts** are a table of their own (migration 0008): one open alert per facility, kind and key, raised by a fixed
  rule and closed by itself when the condition stops; acknowledged by a doctor or MO (cluster, capacity) or the
  assigned health worker (missed visit). Medical officer → *Alerts* (`/reviewer/alerts`); health worker →
  *Maternal follow-ups* (`/nurse/followups`).
- **Fever** means the fever finding or a measured temperature of 100.4 °F or more; each patient counts once. The
  place is the hostel block given at intake, or the village.
- **Call script:** on her own phone it mentions the check-up; on a husband's, family or unknown phone it only asks for
  her by first name. With no phone, the call is refused and a home visit is asked for. The reminder shown in the
  patient's record follows the same rule. A new pregnancy visit closes her open reminders.
- **Code:** `backend/app/alerts.py`, `backend/app/routers/alerts.py`.

**Demo scenarios** (`backend/app/scenarios.py`, synthetic): campus fevers (4 from Hostel Block C; one more at kiosk
link `CAMPUS01` raises the alert), Sunita's missed check-up on ASHA Kamla Devi's list, a second RED at PHC Manikpur,
and 17 workers screened at Kalinga Steel Works, the crusher workers also a year earlier.
| **D5** Chronic check-in | Working | BP and glucose trends against earlier visits | Check the HbA1c trend |
| **D6** Health camp, offline | Working | Kiosk works with no network and syncs later | — |
| **D7** Referral notes | Working | Referral, QR summary, PDF, print, JSON, CSV, FHIR R4 | — |

### E. Human review and hand-off

**E1 Reviewer dashboard** · Working
- Queue, case view, nurse and doctor views of the same note, and lookup by ID, QR or phone.
- **Code:** `frontend/src/app/reviewer/*`, `frontend/src/components/triage/note.tsx`.
- The note shows who wrote the summary ("AI summary, checked" or "Template summary"), the template beside any AI
  text, and any rejected AI text with its reasons.

**E2 Four reviewer roles** · Working
- **Roles:** health worker (ASHA, ANM, MPW; the title follows the state, e.g. Mitanin), nurse, doctor and medical
  officer, beside receptionist, supervisor, employer and patient.
- **Sign-off limits:** a health worker may confirm a GREEN note, a nurse up to YELLOW, a doctor or medical officer
  any. The server refuses anything above the limit and says who must confirm.
- **Note density:** the health worker gets a short form (summary, flags, what is missing, their questions, vital
  signs); the rules trace, labs and documents stay with the nurse and doctors. Doctors can switch to the nurse or
  health-worker view to see what each receives.
- **The medical officer** can do everything a doctor can (override, referral, export, fitness, escalations) and
  receives the capacity and fever-cluster alerts.
- **Medicines read from photos** are confirmed only by a nurse, doctor or MO.
- **Code:** `SIGN_OFF`, `DOCTOR_ROLES` in `backend/app/schemas.py`; `can_confirm`, `note_for` in `services.py`.

**E3 Escalation** · Working
- Manual escalation, plus automatic escalation of unreviewed RED cases after 15 minutes and YELLOW after 60.
  Escalations must be acknowledged.

**E4 Referral preparation** · Partial
- **What:** the referral destination is suggested from the specialists on duty.
- **QR summary:** a time-limited link plus a 6-digit code. It locks after 8 wrong codes, can be revoked, and every
  opening is audited (`backend/app/routers/shares.py`, `/s/<token>`).
- **Left:** close a referral only when care is received; flag overdue referrals.

**E5 Scheduling and reminders** · Partial
- Maternal check-up reminders with due dates and missed-visit detection (D4). **Left:** a visit calendar from the
  facility's configuration, and reminders for chronic check-ins.

**E6 Calling agent** · Not built

**E7 Export** · Working
- PDF (fpdf2), print page, JSON, CSV, FHIR R4 bundle. Every export carries the disclaimer.
- **Code:** `backend/app/exports.py`.

**E8 Patient slip** · Partial
- Patient screens already hide urgency. A printed slip still has to be checked.

**E9 Overrides with reasons** · Partial
- **What:** only doctors override, with a written reason of at least 15 characters; the original rules result is
  kept.
- **Left:** free upgrades, role rules for downgrades, and override rate per rule.

### F. India context and set-up

**F1 Facility types** · Working
- Sub-centre, PHC, CHC, district hospital, hospital, clinic, health camp, company clinic, industrial unit, campus.
- Staff pick their facility from an all-India directory built from OpenStreetMap. Private workplaces appear only
  after their organisation registers.
- **Code:** `backend/app/directory.py`, `backend/app/routers/organisations.py`, `frontend/src/app/admin/facility`.

**F2 Load, language, specialist and digital-maturity settings** · Partial
- Facility types exist. **Left:** each setting visibly changing behaviour.

**F3 Accessibility** · Partial
- **What:** icon mode, large text, read-aloud, 56–64 px kiosk buttons, proxy consent for caregivers.
- **Left:** a full voice path for blind users; low-end Android checks.

**F4 Long-term records** · Working
- BP and glucose trends across visits.

**F5 Regional calendar and worker names** · Working
- **What:** patients date illness by festival and season, and the festival differs by region and faith. Each
  facility's notes use its state's table:
  - Festivals: 42 multi-faith festivals.
  - Monsoon: IMD normal onset and withdrawal dates, plus the northeast monsoon in the south.
  - Seasons and the farming cycle: winter, summer, paddy and wheat harvest, and transplanting.
- **How a phrase is read:**
  - "since Diwali", "दिवाली से", "ରଜଠାରୁ", "holi ke baad se", "pujo theke" and "after the rains" all become an
    approximate date or window.
  - The plan's two rules hold: a vague reference is never silently made precise (the onset stays VAGUE, `days`
    stays empty, staff are asked to confirm), and the patient's phrase is always kept.
  - A word with two meanings ("Eid", "sankranti" in Odisha, "the rains" in Tamil Nadu) shows the latest one and
    asks which.
  - A year missing from the table is reported, not guessed.
- **Worker names:** the state's own title for front-line workers is shown in the staff role label, the staff page
  and the kiosk helper list. Examples: Mitanin in Chhattisgarh, Sahiya in Jharkhand, VHN in Tamil Nadu, JPHN in
  Kerala, Arogya Sevika in Maharashtra; first-aider at workplaces.
- **Facility overrides:** a supervisor can set worker names, local monsoon dates and the facility's own festivals,
  and can try any phrase on `/admin/calendar`.
- **Uses:** public data only, cited in the table:
  - DoPT central holiday lists 2025–2027;
  - Odisha GAD holiday lists;
  - IMD CRS Report 3/2020 (new normal monsoon dates);
  - NCERT crop seasons;
  - NHM cadres.

  No model.
- **Code:** `backend/app/regions.yaml`, `backend/app/regions.py`, `backend/app/triage/timeline.py`,
  `backend/app/routers/facilities.py` (`/facilities/{id}/calendar`, `/facilities/{id}/onset`),
  `frontend/src/app/admin/calendar`, `frontend/src/lib/cadres.ts`. 28 tests in `backend/tests/test_regions.py`.
- **Limits:**
  - Lunar and Islamic dates can differ by a day locally.
  - Festival dates beyond 2027 must be added each year from the new DoPT list.
  - A monsoon date is a 1961–2019 normal, not that year's actual onset.
  - The Odia and Hindi festival spellings need a native speaker's check.

**Screen languages:** the language picker lists English and the 22 scheduled languages. Every screen is fully
translated into English, Hindi and Odia; for other languages, untranslated text shows in English.
- **Code:** `frontend/src/lib/i18n/*`.
- **Left:** Kannada next.

### G. Privacy, safety and responsible AI

**G1 Consent, including "Continue without AI"** · Working
- **What:** no intake is accepted without a consent record (self or proxy, with relationship). On the consent step
  the patient can choose **Continue without AI** (scope `no_ai`). With it:
  - the microphone is hidden, and the server refuses voice entries;
  - nothing is translated;
  - uploaded reports are not read by OCR, and staff view the image instead;
  - no summary model runs;
  - the note carries the NO-AI flag.
- **Code:** `submit_intake` in `backend/app/routers/encounters.py`; `NO_AI_SCOPE` in `backend/app/schemas.py`.

**G2 Minimal retention** · Working
- Voice recordings are kept 24 hours, photos 3 days and reports 30 days. An hourly job deletes expired files (the
  record that a file existed stays) and writes a PURGE audit event.
- **Code:** `purge_expired()` in `backend/app/storage.py`; `/admin/retention`.

**G3 Anonymisation** · Working
- **Text:** names, phone, Aadhaar and ABHA numbers and email addresses are replaced in the patient's free text
  before storage and before translation, so they never reach the translator, the summary model or exports.
  - Names are found two ways: the registered patient and proxy names, and whatever follows "my name is" in English,
    Hindi, Odia or Kannada.
  - Indian-script digits (୯୮୭…, ९८७…) are caught too. Clinical numbers like "BP 150 95" are left alone.
  - A word the triage rules read as a symptom is never removed as a name.
  - In staff notes, ID numbers are removed but names are kept.
- **Images:** faces are blurred (YuNet) and lines with phone, Aadhaar or ABHA numbers are blacked out before
  storage. Every photo is re-encoded, which removes location (GPS) and camera data.
- **Cohort view:** `/admin/cohort` shows case counts only, by week, age band, sex, visit type and urgency. Any count from
  1 to 4 shows as "<5" so a small group cannot be singled out, and every view is audited.
- **Reviewer and audit:** the reviewer sees the PII-REDACTED flag; the audit log records how many items of each kind
  were removed, never the values.
- **Code:** `backend/app/privacy.py`, `backend/app/triage/images.py`, `GET /cohort` in
  `backend/app/routers/admin.py`, `frontend/src/app/admin/cohort/page.tsx`; 19 tests in
  `backend/tests/test_privacy.py`.
- **Limits:** a name said without an introduction and not on the registration is not found; numbers spoken as
  words are not recognised.

**G4 Audit log** · Working
- **What:** every view, edit, override, export, share opening, redaction, guard block and purge is logged.
- **Tamper evidence:** each event's SHA-256 hash includes the previous event's hash, so editing an old event breaks
  the chain. A database trigger refuses updates and deletes.
- **Use:** the supervisor and doctor can verify the chain and export it as CSV.
- **Code:** `backend/app/audit.py`, `/admin/audit`.

**G5 Role-based access** · Working
- **What:** staff sign in with an SMS (or email) code **and** a personal PIN. Weak PINs are refused, and the account
  locks for 15 minutes after 5 wrong tries.
- **Sessions:** last 60 minutes; refresh tokens rotate and can be revoked.
- **Devices:** staff kiosks must be bound devices.
- **Limits by role:** front desk sees names and tokens only; employers see fitness status only; patients never see
  urgency.
- **Code:** `backend/app/security.py`, `backend/app/routers/auth.py`, `backend/app/otp.py`, `backend/app/mailer.py`.

**G6 Disclaimer** · Partial
- On every screen and export. **Left:** the patient slip, and spoken at the kiosk.

**G7 Responsible-AI dossier** · Partial
- EVALUATION.md has the measured figures. **Left:** model cards, error rates by language, sex and age, and an "about
  the models" page.

**G8 Data-origin tagging** · Partial
- The FHIR export is tagged synthetic. **Left:** a tag on every record and a banner on every screen.

### H. Platform

| Feature | Status | What and where |
|---|---|---|
| **H1** Database | Working | `backend/app/models.py`; migrations `backend/migrations/versions/0001`–`0006`, applied at start-up |
| **H2** API | Working | FastAPI under `/api/v1`, routers in `backend/app/routers/`. Interactive docs at `/docs` |
| **H3** Model serving | Partial | Speech, translation and OCR load inside the API (`JEEVIA_PRELOAD_LANGUAGE_MODELS=true` loads them at start-up). The summary model is a separate `llama-server` process. **Left:** switchable profiles |
| **H4** File storage with expiry | Working | `backend/app/storage.py` |
| **H5** Visible fallback when an engine is down | Partial | `GET /language/engines` lists what is installed and loaded; a missing engine answers 503 and never a fake result; the note says when the summary model was unavailable. **Left:** a per-stage status on every note |
| **H6** Offline kiosk | Working | `frontend/src/lib/offline/outbox.ts`, `precache.ts`, `public/sw.js`. Check-ins wait in IndexedDB and replay without duplicates (`client_ref`) |
| **H7** Speed targets | Partial | Speech and summary measured. **Left:** the rest |
| **H8** Logging | Working | `backend/app/observability.py`: JSON logs with request IDs and no request bodies; `/metrics`; `/health` |
| **H9** Deployment | Partial | `docker-compose.yml`, `render.yaml`, Vercel. **Left:** update the public link and recheck Compose |
| **H10** CI | Working | `.github/workflows/ci.yml` |

---

## 5. Flags a reviewer can see on a note

| Flag | Meaning |
|---|---|
| `ASR-UNCONFIRMED` | The patient skipped the spoken read-back of their transcript |
| `MT-CHECK` | History was machine-translated; check it against the patient's own words shown beside it. A warning (not info) when the translation left out or added a symptom, or was unsure of a number or symptom |
| `DISAGREE` | Two sources disagree, such as today's BP and the BP on a report |
| `DOC-CHECK` | A report looks old, its name does not match, or a value needs checking |
| `MEDS-UNCONFIRMED` | Medicine names were read from a strip or prescription and await confirmation |
| `PII-REDACTED` | Identifiers were removed from the patient's free text |
| `NO-AI` | The patient chose to continue without AI |
| `LLM-FELL-BACK` | The AI summary failed a check; the template summary is shown with the reason |
| `AI-OPINION-HIGHER` | The AI model's own urgency is higher than the rules'. Take a second look; urgency is unchanged |
| `PROXY` | The history was given by a family member or caregiver |
| `OFFLINE` | Captured offline and synced later; waiting time counts from capture |
| `PPE-GAP` | Workplace finding: protective equipment not issued, or worn only sometimes or never. Not part of urgency |
| `SAFE-PROVISIONAL` | UNDETERMINED, held at YELLOW until the listed vitals or checks are recorded |

---

## 6. Running the full demo on the laptop

Ports: API **8030**, web app **3010**, summary model **8031**. Ports 8000, 8009 and 8010 belong to other projects
on the laptop.

1. **Summary model** (needs the NVIDIA GPU; downloads llama.cpp on first run):
   ```bash
   bash backend/scripts/start_llm.sh
   ```
2. **API** with the AI engines (Python packages from `backend/requirements-ml.txt`, models fetched once by
   `python backend/scripts/fetch_models.py`):
   ```bash
   cd backend
   JEEVIA_PRELOAD_LANGUAGE_MODELS=true JEEVIA_LLM_URL=http://127.0.0.1:8031 \
   JEEVIA_CORS_ORIGINS=http://localhost:3010 JEEVIA_WEB_BASE_URL=http://localhost:3010 \
   .venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8030
   ```
3. **Web app.** Create `frontend/.env.local` (not committed) with:
   ```
   NEXT_PUBLIC_API_MODE=live
   NEXT_PUBLIC_API_URL=http://127.0.0.1:8030
   ```
   then run `cd frontend && npx next dev -p 3010`.
4. **Check before demoing:** the header must say **"All systems operational"**. "Local demo mode — no server" means
   the web app is running its built-in sample backend instead of ours.

Memory is tight on a 16 GB laptop: quit Docker Desktop before a demo. With every engine loaded the API uses about
2.5 GB of RAM, and the summary model uses 3.1 GB of GPU memory.

---

## 7. Tests

```bash
cd backend && .venv/Scripts/python.exe -m pytest -q     # 406 tests
cd frontend && npx tsc --noEmit && npm run lint
```

| Test file | Tests | Covers |
|---|---|---|
| `test_output_guard.py` | 144 | Red-team set (101 blocked, 40 allowed) plus normalisation; guard test page samples, audit label, scrubbing, supervisor-only |
| `test_rules.py` | 63 | Rules engine, findings, negation, Hindi and Odia phrases, crush-injury fix |
| `test_timeline.py` | 22 | Onset labels and conflicts |
| `test_regions.py` | 28 | Regional calendar: festival and season dates by state, two-meaning words, no guessing, facility overrides, cadre names, every date sourced, every directory state covered |
| `test_api.py` | 20 | Sign-in, roles, consent, offline replay, overrides, escalations, exports, audit |
| `test_wednesday.py` | 27 | AIIMS high-risk floor; occupational rules, FEV1 baseline, PPE gap, employer rates without symptoms; sign-off limits and note density by role; queue reasons and capacity alert; fever cluster and suppressed export; missed visit, neutral call script, no-phone refusal; SQLite column patch |
| `test_zz_scenarios.py` | 1 | Demo scenarios load once and each demo moment works (runs last) |
| `test_privacy.py` | 19 | Name and number removal, Indian digits, cohort small-count suppression |
| `test_orgs.py` | 16 | Organisations, roster, fitness, directory |
| `test_language.py` | 17 | Speech and translation wiring, the two-at-once freeze, and the 5 Oct live-test sentences: spoken spellings, translation cross-check, rewrites, unsure numbers, per-sentence onsets, real-model check |
| `test_images.py` | 12 | Document type, medicine matching (incl. the 5 Oct real strip photo), face and ID blurring |
| `test_llm.py` | 19 | Summary checks and the urgency second opinion with a stand-in model (no GPU needed): never changes urgency, higher-only flag, withheld reasons, no-AI consent, switch, disagreement view roles |
| `test_kiosk.py` | 7 | Kiosk links, tokens, returning patients, the Twilio path |
| `test_extraction.py` | 6 | Test-name matching, MCP card values, old-report and name checks, real OCR on a slip |
| `test_shares.py` | 5 | QR summaries: codes, lockout, expiry |

---

## 8. Words used in this guide

| Word | Meaning |
|---|---|
| **ASR** | Automatic speech recognition: speech to text |
| **OCR** | Optical character recognition: reading text from an image |
| **WER / CER** | Word / character error rate: the share of words or letters the speech engine got wrong (lower is better) |
| **ATP** | AIIMS Triage Protocol, from AIIMS New Delhi |
| **IITT** | Interagency Integrated Triage Tool, from WHO, ICRC and MSF |
| **IMCI** | WHO Integrated Management of Childhood Illness |
| **AVPU** | Alert / Voice / Pain / Unresponsive: a quick check of consciousness |
| **GGUF, Q4_K_M** | The file format llama.cpp uses; Q4_K_M is a 4-bit compression that makes a 4-billion-parameter model fit in 3 GB |
| **ONNX** | A model file format that runs fast on CPU through ONNX Runtime |
| **FHIR R4** | The international standard format for exchanging health records |
| **LOINC** | Standard codes for lab tests |
| **PMBJP** | Pradhan Mantri Bhartiya Janaushadhi Pariyojana, the government generic-medicine scheme |
| **ABHA** | Ayushman Bharat Health Account number (14 digits) |
| **Undetermined (provisional YELLOW)** | Held at YELLOW because something needed to rule out danger has not been recorded yet |
| **ASHA / ANM / MPW** | Accredited Social Health Activist (village health worker); Auxiliary Nurse Midwife; Multi-Purpose Worker |
| **FEV1 / FVC** | Air blown out in the first second / in total, measured by spirometry |
| **Template summary** | The plain summary built by code from the facts, used whenever the AI summary is off or fails a check |
