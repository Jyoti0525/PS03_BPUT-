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
10. **Hand-off** (D7, E4, E7). The case is referred with a QR summary, or exported as PDF, JSON, CSV, FHIR or HL7 CDA.

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
| **Sarvam AI** (optional): Saaras v3 speech-to-text, Bulbul v3 voice, Vision document reading | Second speech engine (B9); the reminder-call voice (E6); reading handwritten prescriptions (B1). Speech and images go only with the patient's AI consent | Cloud, hosted in India |
| fpdf2 | PDF export | API |
| **GitHub Actions** | Tests, lint and build on every push (`ci.yml`); a ping that keeps the free Render server awake (`keepalive.yml`) | GitHub |

### AI models and engines (all offline, on the facility machine)

| Engine | Made by, licence | Used for | Size and speed on the demo laptop |
|---|---|---|---|
| **IndicConformer-600M multilingual**, 8-bit ONNX copy, run with ONNX Runtime | AI4Bharat, MIT | Speech to text in the 22 scheduled languages (A2) | 0.9 GB on disk, 1.6 GB RAM; 0.26 s per second of speech (CPU) |
| **IndicTrans2 distilled 200M**, with IndicTransToolkit | AI4Bharat, MIT | Indian language ↔ English translation (A3) | 1–2 s per sentence (CPU); only Indic → English is loaded at start-up |
| **IndicWhisper** (Vistaar whisper-medium, Odia; Hugging Face Transformers, 8-bit at load time) | AI4Bharat, MIT | Offline second speech engine, when Sarvam cannot be used (B9) | 1.5 GB on disk, ~2.5 GB RAM in use; ~3.8 s per second of Odia speech (CPU), so it runs after the read-back |
| **RapidOCR**: PaddleOCR PP-OCR models on ONNX Runtime | RapidAI / PaddlePaddle, Apache-2.0 | Reading photos of reports, strips and prescriptions (B1) | CPU; 5–9 s per page |
| **docTR** models (db_mobilenet_v3_large + crnn_mobilenet_v3_large) via **OnnxTR** | Mindee / Felix Dittrich, Apache-2.0 | Second OCR engine, compared with RapidOCR test by test (B9) | CPU; adds 3–4 s per page (runs in parallel) |
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
| Indian medicine brands | "A-Z Medicine Dataset of India", Shudhanshu Singh, [Kaggle](https://www.kaggle.com/datasets/shudhanshusingh/az-medicine-dataset-of-india), **CC BY-SA 4.0** (Nov 2022). Cut to 186,094 brands → what each contains, in `backend/app/triage/data/medicine_brands.tsv.gz` (the derived file is CC BY-SA 4.0 too, with this attribution; rebuilt by `backend/scripts/build_brand_list.py`) | Naming the brands on prescriptions (B10) |
| Medicine names | PMBJP list of 2,110 generic medicines, Press Information Bureau (Govt of India), [PDF](https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/feb/doc202626781701.pdf). The [PIB copyright policy](https://www.pib.gov.in/content/102_2_Copyright-Policy.aspx) allows reproduction with acknowledgement. 1,087 unique names, in `backend/app/triage/data/medicines_pmbjp.txt` | Matching names on medicine strips (B10) |
| Health facilities in India | OpenStreetMap contributors, ODbL, in `backend/directory_data/facilities_in.jsonl.gz` | The facility search at sign-up |
| Speech test clips | Google FLEURS, CC-BY-4.0 | Measuring speech accuracy only; never stored in the app |
| Handwritten prescriptions | "100 handwritten medical records", chaithanyakota, Hugging Face, CC BY-ND 4.0 | Measuring handwriting reading only; not copied into the repo or changed |
| Lab report test pages | Generated by `backend/scripts/make_ocr_set.py` (synthetic names, labs and values, fixed seeds) | Measuring OCR only |
| Patients, reports, test cases | Written by us; all synthetic | Demo, tests and evaluation |
| Long patient histories | [Synthea](https://github.com/synthetichealth/synthea) (Apache-2.0), seed 1008: the simulated clinical course (visits, BP, glucose) of 12 adults, re-cast with synthetic Indian names, ages and villages by `backend/scripts/import_synthea.py`, in `backend/app/synthea_histories.json` | Demo patients SYN-001… at PHC Manikpur whose new visit shows a trend (`JEEVIA_SEED_SYNTHEA`) |

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
- **Left:** measuring the other languages; a confidence threshold. (Second engine: Sarvam, see B9.)

**A3 Translation** · Partial
- **Patient slip:** an optional advice box; the advice prints in English and machine-translated (offline IndicTrans2,
  or Bhashini online when configured), marked "read it out to the patient". The slip's labels are in the patient's
  language.
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

**A6 Patient identity and matching** · Working
- **What:** returning patients are found by patient ID and phone. On a shared household phone, the patient picks
  their own name. Each candidate shows why it matched (exact ID, shared household phone, name). A person always
  picks; the pick is logged with the match reason and the number of candidates. Records are never merged.
- **Code:** `backend/app/routers/kiosk.py` (`/kiosk/identify`), `backend/app/routers/patients.py`
  (`POST /patients/{id}/pick`), `backend/app/services.py` (`own_patient`).

**A7 Spoken read-back and prompts** · Working
- **What:** read-back in the patient's language using a voice installed on the device. If the device has no voice
  for that language, nothing is spoken, rather than an English voice mangling Odia.
- **Online voice:** the demo laptop (Windows) has no Hindi or Odia voice. When the device has none and there is a
  connection, the kiosk plays Sarvam Bulbul audio from the server (`POST /language/speak`, kept in memory only). The
  patient's own words are sent only if they chose AI helpers; fixed prompts always may be.
- **Offline voice:** Meta MMS-TTS for Odia, Hindi and Kannada runs on the server and is tried first, so a camp
  with no network still hears Odia. Sarvam is used only for other languages.
- **Uses:** browser `speechSynthesis` (`frontend/src/lib/speech.ts`), MMS-TTS (`backend/app/tts.py`, CC-BY-NC 4.0),
  Sarvam Bulbul v3 (`backend/app/sarvam.py`).

**A8 Vitals entry** · Working
- **What:** nurses record BP, pulse, temperature, SpO₂, breathing rate, glucose, AVPU and the danger-sign
  checklist. New vitals re-run the rules.
- **Units and ranges:** one fixed unit per vital (°F, mmHg, bpm, %, /min, mg/dL). The kiosk and the nurse form share
  the plausible ranges. A temperature typed in Celsius is refused, never converted. Systolic must be higher than
  diastolic (the API checks it too).
- **Not measured:** a blank box says "Not measured" and is never given a default value.
- **Code:** `frontend/src/components/triage/observations.tsx`, `frontend/src/components/intake/intake-flow.tsx`;
  `Vitals` in `backend/app/schemas.py`; `POST /encounters/{id}/observations`.

### B. Reading and understanding

**H0 Text layer before OCR** · Working
- A PDF that already has text is read directly, with no OCR. Scanned pages are turned into images and sent to OCR.
- **Uses:** pypdfium2 (`backend/app/triage/extraction.py`).

**B1 OCR for lab reports** · Working
- **What:** reads printed reports offline, with two engines (B9). A quality check runs first, at one scale (longer
  side 1,600 px), and asks for a retake if the photo is:
  - blurry (variance of the Laplacian below 32, after a median filter so sensor noise does not count as sharpness);
  - too dark (mean brightness below 70);
  - low-contrast or glaring (ink against paper below 60);
  - smaller than 500 px on its shorter side.

  After reading, a mean OCR confidence under 0.75 adds "Text hard to read", and a page neither engine could read
  asks for a retake.
- **Handwriting:** the offline engines cannot read it well. A prescription, or a page they could not make sense of,
  is read online by Sarvam Vision when the patient allowed AI help. What it reads is shown beside the offline
  reading, named, and every lab value from it is marked for checking.
- **Measured** (EVALUATION.md, 303 tests per capture type, held-out synthetic reports): values exactly right 99.3 %
  on scans and phone photos, 98.7 % on photocopies, 99.3 % on thermal slips, 85.5 % on poor photos (72.5 % of which
  are asked to retake). Wrong values not flagged: 3 of 1,515. Handwritten prescriptions (45 test pages): Sarvam reads
  60 % of the medicine names, docTR 26 %, RapidOCR 18 %.
- **Uses:** RapidOCR (PaddleOCR models on ONNX Runtime); docTR via OnnxTR; OpenCV; Sarvam Vision (online, optional).
- **Code:** `backend/app/triage/extraction.py`, `backend/app/sarvam.py`; tests in `backend/tests/test_extraction.py`
  and `backend/tests/test_ocr_checks.py`; measurement in `backend/scripts/make_ocr_set.py`, `eval_ocr.py`,
  `eval_handwriting.py`.
- **Limit:** measured on synthetic print; real reports vary more. Even online, about 4 in 10 medicine names read from
  handwriting are wrong.

**B2 Number checks** · Working
- **What:** every number read from a report is checked before the rules use it. Nothing is corrected: a value that
  fails a check is marked "check this value", with the reason, beside its image crop.
  - **Physiological bounds:** each test has a range the body can have; outside it, the value is a misread.
  - **The lab's own High / Low mark** ("310 H", "(L)", "↑") against the value and the printed range. A mark that
    disagrees means the value, the range or the mark is misread, and the result counts as out of range until someone
    looks. On a report that marks its results, an unmarked result outside its range is also flagged.
  - **Units:** a unit that does not belong to the test (haemoglobin in mg/dL) is flagged. SI units are converted for
    the rules, with their range: a glucose of 17 mmol/L is 306 mg/dL, not 17. Also µmol/L creatinine and bilirubin,
    g/L protein, mmol/L lipids and urea, and HbA1c in mmol/mol. The value is still shown as printed.
    Counts printed in lakhs or thousands become per µL, including when the unit sits at the start of the range cell
    ("4.87 | lakhs/cumm 1.50 – 4.50"). A count with no unit read is always flagged: per µL, thousands and lakhs
    differ 100-fold.
  - **Ranges:** a printed range more than four times off the test's usual range (glucose "3.9 – 5.5" beside a value in
    mg/dL, or "< 2000" for "< 200") is not used for the high/low call.
  - **The report's numbers against each other:** WBC differential adds to 100 %; absolute count = % × total WBC;
    absolute counts add to the WBC; globulin = total protein − albumin; A/G ratio; indirect = total − direct bilirubin;
    MCHC = Hb ÷ PCV, MCV = PCV ÷ RBC, MCH = Hb ÷ RBC; VLDL = TG ÷ 5; a calculated LDL = TC − HDL − VLDL; non-HDL =
    TC − HDL; the cholesterol ratios; urea = 2.14 × BUN. Where nothing is printed to add up to, physiological limits
    between tests: direct bilirubin not above total, HDL + LDL not above total cholesterol, Hb and PCV giving an MCHC
    of 22–40. The allowance for each sum is worked out from how many digits each value is printed with, so rounding
    alone never fails one. A sum that fails marks every value in it, and the note gets a "LAB-SUM" flag. If the second
    OCR engine read one of the values differently and its reading makes the sum work, the check says so.
  - The report date is checked (an old report is flagged) and the name on the report is compared with the patient's.
- **Measured** (EVALUATION.md, "Checking the numbers on a report (B2)"): on 2,000 simulated reports, one misread
  digit that moves a value by 10 % or more is caught 98.6 % of the time (31.9 % by the bounds alone), with no false
  alarm on any correct report. Read through OCR from five kinds of capture (held-out set, 3,425 printed tests): **no
  wrong value went unflagged** (five would have without the sums), and no sum failed on a correctly read report.
- **Code:** `consistency`, `_sums`, `UNIT_OK`, `CONVERT`, `FLAG_RE` in `backend/app/triage/extraction.py`; the note
  flag in `backend/app/triage/pipeline.py`; tests in `backend/tests/test_lab_checks.py`; measurement in
  `backend/scripts/eval_sums.py` and `make_ocr_set.py ... b2`.
- **Limit:** a slip in a value's last digit (12,300 read as 12,308) is inside the rounding every sum must allow; only
  about 1 in 6 slips that move a value by less than 5 % is caught.

**B3 Key-detail extraction** · Working
- **What:** a dictionary of 50 common Indian lab tests, with synonyms and common OCR mistakes, including the full blood
  count (indices, differential and absolute counts), liver and kidney panels and the lipid profile. Tests once read
  as another (VLDL as LDL, "Cholesterol/HDL Ratio" as total cholesterol, "Blood Urea Nitrogen" as urea, "RBC Count" as
  the WBC count, direct bilirubin as total) are now their own tests. For each test it reads the value, unit, printed
  reference range and the lab's High / Low mark from the same row, plus the exact box on the image. The reviewer sees
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

**B9 Two engines disagree → flag** · Working for speech and OCR
- **Speech:** when the patient allowed AI help, Sarvam Saaras v3 (online) hears the same recording as the offline
  IndicConformer, at the same time. With no Sarvam key, no network, a language Sarvam does not take, or nothing
  heard, IndicWhisper (offline) hears it instead. It is slower than real time on the laptop, so it runs after the
  reply: the read-back shows "A second engine is still checking what it heard…", and the result is added when ready,
  to the read-back or to the entry already confirmed (`GET /speech/second/{id}`). The two transcripts are compared after bringing them to one written form (one
  spelling, number words as digits: "ଶହେ ଆଠ" = 108). A different number, a symptom only one engine heard, or under
  80 % of the characters matching is a disagreement.
- **At the kiosk:** the read-back box shows the second engine's words, in English too, and what differs, with "Ask
  the patient which is right" and *Use this one instead*. Whichever is confirmed, the other is kept beside it.
- **In the note:** the server compares the two again (it does not take the browser's word) and adds a *Voice
  transcript: sources disagree* flag with both versions and the differences. A symptom only the second engine heard
  still counts for urgency, labelled "second speech engine only", as with translation (missing a real symptom is
  worse than over-triage). The second transcript is translated on the server and has names removed like the first.
- **Fallback:** where the offline model is not installed (the hosted link), the second engine alone transcribes and is
  named.
- **Measured** (EVALUATION.md): FLEURS Odia, 25 clips: Sarvam 19.1 % WER vs 21.6 % offline; engines agree at median
  98.6 %, none flagged. IndicWhisper (offline, 8-bit) on the same clips: 31.7 % WER, 3 clips flagged, all three the clips IndicConformer got most wrong. Live check: caught the offline engine hearing BP "160/100" as "160 बटा सो".
- **OCR:** docTR (offline) reads every report beside RapidOCR, in parallel. The two readings are compared test by
  test; where they differ, the value is marked "check this value" and the rules use the reading further from
  normal. On the held-out reports this cut silent errors from 10 to 3 of 1,515 tests, at the cost of more correct
  values flagged (11.6 % on phone photos).
- **Code:** `backend/app/asr_check.py`, `backend/app/whisper_asr.py`, `/speech/transcribe` and `/speech/second/{id}`
  in `backend/app/routers/language.py`, `heard_differently` in `backend/app/triage/pipeline.py`; OCR in
  `backend/app/triage/extraction.py`; kiosk `frontend/src/components/intake/intake-flow.tsx`. Tests:
  `test_asr_second.py`, `test_ocr_checks.py`.
- **Left:** IndicWhisper for languages other than Odia is one download each (`models/indicwhisper`); measuring flag
  rates on spontaneous speech.

**B10 Image understanding without diagnosis** · Working
- **What:**
  - **Document type:** lab report, prescription, medicine strip, discharge summary, mother-and-child (MCP) card,
    other document, or not a document. Decided by keyword rules, and the label shows the words that decided it.
  - **Medicine names:** read from strips and prescriptions and matched to the PMBJP generic list or the A-Z list of
    186,094 Indian brands, strength included. Each one shows "awaiting confirmation" until a nurse or doctor taps
    Confirm or "Not this". Both actions are audited, and only confirmed names enter the record.
  - **Brands** are taken only where a medicine's name goes on an order line ("Tab Dolo 650", "Syp Allegra"). A name
    in a weak position needs a strength, a dose pattern (1-0-1) or a form word to confirm it. Between equally close
    names, the brand with more products wins. A brand's strength takes its unit from what the brand contains
    ("Dolo 650" → 650 mg), and generics printed under a brand are folded into it, so one medicine is listed once.
- **Uses:** OCR text from B1; Python `difflib` fuzzy matching (similarity of 0.86 or more for generics, 0.84 for
  brands); the PMBJP list; the A-Z Medicine Dataset of India (CC BY-SA 4.0).
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
- **Measured** (EVALUATION.md, 45 handwritten test pages): with Sarvam's reading, 28.8 % of prescribed medicines are
  named and 59 % of the names given are right. Offline with docTR: 4.4 % named, 64 % right.
- **Limit:** handwritten prescriptions are mostly missed offline, and even online about 4 in 10 names given are
  wrong. Common supplements such as Shelcal and Zincovit are not in the brand list. Every name needs confirmation.

### C. Triage decisions

**C1 Risk-category tagging** · Working
- **What:** 167 rules that set the colour, plus 3 follow-up rules, in YAML files, each citing its published source:

  | Rule file | Rules |
  |---|---|
  | `atp.yaml` | 31 |
  | `iitt_adult.yaml` | 43 |
  | `iitt_paed.yaml` | 46 |
  | `imci.yaml` | 12 |
  | `maternal.yaml` | 14 |
  | `aiims_hrc.yaml` (C5, adults) | 6 |
  | `occupational.yaml` (D2, only when a workplace exposure is recorded) | 5 |
  | `labs.yaml` | 3 |
  | `local.yaml` (marked "local", never passed off as a guideline; also NTEP presumptive TB and GINA asthma with low SpO₂) | 6 |
  | `followup.yaml` (never changes the colour: BP ≥ 160/100, jaundice, blood in urine; shown as "Follow-up: …" info flags) | 3 |

  Protocols are chosen by age, pregnancy and workplace exposure, all applicable sets run, and the highest urgency
  wins.
- **WHO IITT checked against the full tool (8 Oct):** every number on WHO's adult tool and reference card matches the
  rules. Two reference-card items were added: trauma in a patient on blood thinners or with a bleeding disorder (finding
  `anticoagulated`: warfarin, apixaban, "blood thinner", खून पतला करने की दवा, ରକ୍ତ ପତଳା ଔଷଧ …) and inhalation injury as
  a major burn. Not encoded: ECG ischaemia (no ECG input), "known diagnosis needing urgent surgery" and "pregnancy
  referred for complications" (need a referral record), polytrauma.
- **Kiosk questions in one versioned file:** `backend/app/triage/question_flow.yaml` holds every context question, when
  it is asked, whether it is a safety question, and which findings each answer sets. The kiosk reads it as
  `frontend/src/lib/question_flow.json` (built by `scripts/build_question_flow.py`); the rules read the same file. CI
  (`tests/test_question_flow.py`) fails on a finding not in `findings.FINDINGS`, an unknown condition, a duplicate
  question, or a JSON that differs from the YAML.
- **History questions (version 2, 29 questions, 8 Oct):** besides the danger signs, the kiosk now asks what a doctor
  needs before prescribing or referring: medicine allergy, daily medicines (blood thinner named), long-term illness
  (diabetes, high BP, heart disease, TB), medicine-taking for chronic visits, child vaccines (under 5), possible pregnancy
  (women 12–50 with stomach pain, bleeding, fainting or vomiting, outside an antenatal visit), cough for 2 weeks or more
  and blood in the spit / weight loss / night sweats (NTEP screen), blood in the stool, vomiting, fever with chills, and
  burning urine. Each shows only when it fits the complaint. Under normal load the kiosk asks every safety question, then
  allergy, medicines and long-term illness (`core: true`), then others up to 9; under high load safety questions only.
  Hindi, Odia and Kannada text for every new question. New local rule `LOCAL-POSSIBLE-ECTOPIC` (late period or pregnancy
  with stomach pain, bleeding or fainting → YELLOW, pregnancy test and doctor today); a cough for 2 weeks or more now
  meets `NTEP-PRESUMPTIVE-TB` from the answer alone.
- **"Not sure" is not "No" (fixed 8 Oct):** answers matched the option prefix as plain text, so "Not sure" to "Does the
  pain spread to the arm?" was read as "No" and recorded as a negative. Matching is now whole-word; a regression test
  covers it (`tests/test_note_history.py`).
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
- **Order:** urgency, then escalation state, then minutes waiting **since arrival**; offline check-ins keep their
  real capture time. Each row says why it is there, e.g. "RED (ATP-C-SHOCK-INDEX) · 1st of 2 RED · waiting 18 min
  since arrival, longest first", or "provisional until measured" for an undetermined case.
- **Filling in from home (added 7 Oct):** a kiosk link can be marked *for filling in from home* (shared by SMS,
  poster or website; sample `/k/MKHOME`). There is no patient login: the plan rules out a patient portal. The
  intake gets an H- reference and waits on the desk's token board as *Expected*. It joins the queue, with a T-
  token, only when the desk checks the patient in, and waiting time and escalation timers start then. So a form
  sent at 6 a.m. never moves anyone ahead of people already standing in the OPD. Without measured vitals the case
  can only be a provisional YELLOW (or RED) until a nurse measures them, so exaggerating at home buys nothing. If
  a danger sign is reported, the patient is told to go to emergency or call 108 (never a tier), and the case
  enters the doctors' queue at once so someone can call back. Intakes not checked in within 36 h lapse.
- **GREEN long-wait alert (added 7 Oct):** GREEN has no escalation timer, so a GREEN patient waiting more than
  2 h since arrival is reported to the medical officer, who decides: see them, refer them, or give a priority
  token for the next day. The order itself never changes, because moving them above sicker patients would be
  unsafe. The row reads "over the GREEN wait limit, medical officer told".
- **Reads in one glance (added 7 Oct):** each queue row shows its first two flags in words ("Acute chest pain
  (onset within 24 h)", "+2 more") instead of a flag count, and a "Why here" line naming the rule behind the tier
  (the provisional hold is named only when no rule fired at that tier). Long waits read "31 h 47 min". The nurse list
  shows the critical flag on RED rows. In the case view, vitals and report values put out-of-range and to-check values
  first with an "Out of range" / "Borderline" label, and the card header counts them ("2 out of range · 1 to check");
  in a long report the within-range values fold behind "Show N values within range". Code: `top_flags` in
  `routers/encounters.py`, `alerts.why_tier`, `ValueTable` in `components/triage/note.tsx`.
- **Capacity alert:** when open RED cases (not yet confirmed or referred) outnumber the doctors and medical
  officers marked on duty at the front desk, the medical officer gets an alert and every clinical screen shows a
  red banner with the tokens and the longest wait. It closes by itself when the REDs are seen or another doctor
  comes on duty. Checked on every queue read and whenever a case turns RED.
- **Demo:** PHC Manikpur has 2 REDs and 2 doctors on duty; mark Dr. Sharma off duty at the front desk.
- **Code:** `check_capacity`, `check_long_wait`, `order_reasons` in `backend/app/alerts.py`; `check_in`,
  `waiting_since` in `backend/app/services.py`; `POST /encounters/{id}/arrive`; `GET /capacity`;
  `frontend/src/components/alerts/capacity-banner.tsx`; 5 tests in `backend/tests/test_arrival.py`.

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
  *Follow-ups* (`/nurse/followups`), which also lists chronic check-ins (E5).
- **Fever** means the fever finding or a measured temperature of 100.4 °F or more; each patient counts once. The
  place is the hostel block given at intake, or the village.
- **Call script:** on her own phone it mentions the check-up; on a husband's, family or unknown phone it only asks for
  her by first name. With no phone, the call is refused and a home visit is asked for. The reminder shown in the
  patient's record follows the same rule. A new pregnancy visit closes her open reminders.
- **Code:** `backend/app/alerts.py`, `backend/app/routers/alerts.py`.

**Demo scenarios** (`backend/app/scenarios.py`, synthetic): campus fevers (4 from Hostel Block C; one more at kiosk
link `CAMPUS01` raises the alert), Sunita's missed check-up on ASHA Kamla Devi's list, a second RED at PHC Manikpur,
and 17 workers screened at Kalinga Steel Works, the crusher workers also a year earlier. For E6 (`call_scenarios`):
Rina (pregnant, 31 weeks, Odia, her own phone) and Ramprasad (blood pressure and diabetes, Hindi) are due a reminder
call after two failed ASHA attempts; Kusum's last visit was RED, so only a person may call her.
| **D5** Chronic check-in | Working | BP and glucose trends against earlier visits | Check the HbA1c trend |
| **D6** Health camp, offline | Working | Kiosk works with no network and syncs later | — |
| **D7** Referral notes | Working | Referral letter with history, pertinent negatives, allergies, medicines, timed vitals, treatment given before transfer and the referring doctor; QR summary, PDF, print, JSON, CSV, FHIR R4, HL7 CDA R2 | — |

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

**E4 Referral preparation** · Working
- **What:** the referral destination is suggested from the specialists on duty; a specialty not on site is referred
  to its configured place (`refer_to`), then the facility's default referral hospital.
- **Closed only when care is received:** the receiving clinician confirms from the QR summary (with the access code),
  or the referring doctor records who confirmed it. Due in 6 h (RED), 48 h (YELLOW) or 14 days (GREEN); past due
  it is listed first on the Referrals page and raises a "Referral overdue" alert to the medical officer.
- **QR summary:** a time-limited link plus a 6-digit code. It locks after 8 wrong codes, can be revoked, and every
  opening is audited (`backend/app/routers/shares.py`, `/s/<token>`).

**E5 Scheduling and reminders** · Working
- Maternal check-up reminders with due dates and missed-visit detection (D4).
- Chronic check-ins: a chronic visit can set the next check-in date and assign a health worker. A missed one goes
  the same way as a maternal one (health worker, then a reminder call), and the next chronic visit closes it. The
  reminder text never names the condition.
- **Visit calendar** (`backend/app/visits.py`): antenatal days (default weekly VHND on Wednesday and PMSMA on the
  9th), the chronic clinic day (default Tuesday), closed weekdays and holidays. The supervisor sets them on the
  Regional calendar page. A future follow-up date moves to the next clinic day; the kiosk offers the next clinic
  days as buttons (`GET /facilities/{id}/visit-days`).

**E6 Reminder calls (calling agent)** · Working in the browser; real SMS live (Vonage); real phone calls built, blocked by trial accounts
- **For:** maternal and chronic follow-ups, as the fallback after the assigned health worker could not reach the
  patient twice.
- **Two channels, one call.** In the browser, the call screen shows the agent's lines and plays them in Sarvam's
  Bulbul voice (the device's own voice when Sarvam is not set up); the patient's answers are tapped, typed or spoken.
  Over a real phone line (Twilio or Vonage), the phone rings, each line is played in the same voice, and the patient answers on
  the keypad: 1 yes, 2 no, 3 not sure. The keypad needs no speech recognition and works on any phone. The last
  question ("anything else for the nurse?") is recorded, transcribed and translated (Sarvam Saaras, else the offline
  models), read by the same rules, and the recording is deleted from the provider at once. The screen follows the phone
  call live.
- **Only the demo phone is ever dialled or texted** (`JEEVIA_TELEPHONY_DEMO_TO`), never a patient's stored number:
  the demo patients are synthetic and their numbers may belong to real people. Every webhook must carry the call's
  own token, and Twilio's also its signature.
- **What the agent says:** fixed lines, never generated, in the 11 languages Sarvam's voice speaks: English, Hindi,
  Odia, Bengali, Tamil, Telugu, Gujarati, Kannada, Malayalam, Marathi, Punjabi. The eight added on 6 Oct were checked
  by translating each back to English with the offline IndicTrans2 model (`scripts/check_call_lines.py`); six lines
  that drifted were rewritten. All but Hindi still need a native speaker's check. It says it is an automated call,
  checks it is speaking to the patient, gives the logistics (the check-up was due, can you come this week) and asks
  bounded yes / no questions: for pregnancy bleeding or leaking water, headache or blurred vision, swelling of face
  or hands, the baby's movements (from 24 weeks), fever, fits, belly pain, breathing; for long-term conditions
  medicines, chest pain or breathlessness, one-sided weakness or fainting, severe headache, blurred vision or
  confusion; then "anything else for the nurse?".
- **It never answers with advice.** India's Telemedicine Practice Guidelines 2020 do not let an AI platform counsel a
  patient, so the only replies are "thank you, noted" and logistics.
- **Rules read each answer, not a model:** the intake lexicon (English, Hindi, Odia, with negation) looks for danger
  signs anywhere in what was said, in the patient's words and in the English translation; a word list in each of the
  11 languages reads yes, no or not sure ("पता नहीं" is not sure, not no). A hedge ("କମ୍ ହଲୁଛି", moving less; "a
  little"; "sometimes") is always "not sure", so "moving less" can never pass "is the baby moving as usual?". In a
  language the lexicon does not cover, a typed answer is translated first; if it cannot be, only a plain yes or no
  is read, and anything else said freely pages a person.
- **A danger sign ends the call at once** ("a health worker will call you back straight away") and raises a
  *Reminder call* alert to the medical officer and the assigned health worker, with the words that triggered it.
  "Not sure", or an answer that cannot be read twice, on a danger-sign question does the same: unknown is never
  normal. Whoever acknowledges the alert must say what was done. The follow-up moves to the top of the list.
- **The more serious the case, the less AI on the call:** the agent may call only after a routine, fully assessed
  visit. If the last visit was RED, YELLOW or UNDETERMINED, or the patient chose no AI, a person must call; they
  can use the same screen as a script, and danger signs still raise the alert.
- **Privacy:** on a phone that is not the woman's own, or when someone else answers, the agent only asks them to pass
  on the visit date. Nothing about health is said.
- **Weak evidence:** a call where every answer is "no" marks the follow-up as reached but keeps it open until the
  visit; a missed-medicines answer, or "sometimes", is noted for the reviewer.
- **SMS (Vonage, live since 6 Oct; or Twilio):** a danger sign or unclear answer also texts the demo phone, standing in
  for the medical officer and the health worker, in one plain-text SMS: "JEEVIA ALERT: Danger sign on reminder call.
  Patient JVA-P204, PHC Manikpur, 16:18. Call back now and record the action in Jeevia." The patient's code, the
  centre, the time and the action; never a name or a symptom. *Send SMS* on a follow-up
  sends a reminder in the patient's language that never names a pregnancy or a condition (phones are shared and a
  text stays readable); on a phone that is not the patient's own it only asks the reader to pass on the visit. The patient's own reminder is
  signed by the centre. On Vonage's free trial each text ends with "[FREE SMS DEMO, TEST MESSAGE]", added by Vonage.
- **Sources** for the danger signs: WHO PCPNC, ISSHP, RCOG (reduced movements), AIIMS Triage Protocol, AIIMS 2025
  high-risk complaints.
- **Providers:** Vonage is used when its key is set (Voice API with an application's RS256 token and NCCO actions;
  SMS API), else Twilio (TwiML; webhooks signed). Tried on 6 Oct with a Cloudflare tunnel: Vonage SMS reached the demo
  phone; Vonage's trial rejects voice calls to India ("restricted"); a Twilio trial cannot buy a number. A real call
  needs a paid account on either.
- **Code:** `backend/app/calls.py`, `backend/app/calls.yaml`, `backend/app/sarvam.py`, `backend/app/telephony.py`,
  `backend/app/vonage.py`, routes in `backend/app/routers/alerts.py` and `backend/app/routers/telephony.py` (Twilio and
  Vonage webhooks), table `calls` (migration 0009), `frontend/src/app/nurse/followups/[id]/call/page.tsx`. Tests:
  `test_calls.py`, `test_telephony.py` (against a fake Twilio, Vonage and Sarvam).
- **Left:** a live phone call (needs a paid Vonage or Twilio account); native-speaker checks of the call lines.

**E7 Export** · Working
- PDF (fpdf2), print page, JSON, CSV, FHIR R4 bundle, HL7 CDA R2 document. Every export carries the disclaimer.
- **HL7 CDA R2** (8 Oct): a ClinicalDocument coded LOINC 54094-8 (Emergency department triage note) with sections for
  the disclaimer, chief complaint, urgency and override, summary, vital signs (8716-3), report values (30954-2),
  flags, missing information and rules fired. Vitals and report values are also structured observations; a value that
  needs checking is "active", not "completed". The reviewing doctor is the legal authenticator; before review there is
  none. Valid against HL7's CDA R2 schema (`tests/test_cda.py`, when the schema from github.com/HL7/CDA-core-2.0 is in
  `models/reference/cdaxsd`).
- **Code:** `backend/app/exports.py`.

**E8 Patient slip** · Working
- The printed QR slip has the patient, the QR and access code, the referral destination and the next follow-up date,
  and the disclaimer. It never shows an urgency tier; patient screens hide it too.
- **Code:** `frontend/src/components/triage/share-qr.tsx` (`printShareSlip`).

**E9 Overrides with reasons** · Working
- **Raising** the urgency is free: any reviewer (nurse, health worker, doctor), reason optional.
- **Lowering** needs a doctor or medical officer and a written reason of at least 15 characters. Lowering below a
  RED rule is allowed (people decide) but the audit entry names every such rule.
- The rules' own result and every rule that fired stay on the note.
- **Override rate per rule:** the supervisor's "Urgency overrides" page lists, for each rule, how often it fired,
  was lowered and was raised. A rule that doctors often lower is a rule to review.
- **Code:** `POST /encounters/{id}/override`, `GET /override-stats` (`backend/app/routers/admin.py`),
  `frontend/src/app/admin/overrides/page.tsx`.

### F. India context and set-up

**F1 Facility types** · Working
- Sub-centre, PHC, CHC, district hospital, hospital, clinic, health camp, company clinic, industrial unit, campus.
- Staff pick their facility from an all-India directory built from OpenStreetMap. Private workplaces appear only
  after their organisation registers.
- **Code:** `backend/app/directory.py`, `backend/app/routers/organisations.py`, `frontend/src/app/admin/facility`.

**F2 Load, language, specialist and digital-maturity settings** · Working
- **Patient load** (low / normal / high): the kiosk's question budget. High asks only the questions whose answer can
  make a case RED, and says so; normal asks up to 7, safety first; low asks all.
- **Languages:** the facility's own languages head the kiosk's language list.
- **Specialists:** decide the referral destinations (E4).
- **Offline mode:** on, the kiosk queues intakes on the device with no network; off, it refuses and tells staff to
  use the paper form.

**F3 Accessibility** · Working
- **What:** icon mode, large text, read-aloud, 48 px or larger kiosk controls, proxy consent for caregivers. With
  read-aloud on, the consent, the disclaimer and each follow-up question with its choices are spoken.
- **Checked:** axe-core, WCAG 2.2 AA, every kiosk step to the token screen, on an emulated low-end Android phone
  (360 px wide, CPU 6× slower, slow network): no findings apart from the logo, which WCAG exempts. Page load 2.4 s,
  submit 3.2 s on that profile. Not yet tried on a physical phone.

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
- **Flags and checks read in the screen language too (7 Oct):** all 140 rule descriptions, the fixed flag text, the
  provisional "held at YELLOW until measured" list (any length), and the lab reader's own sentences ("MCHC is 33.1
  g/dL, but haemoglobin 9.4 ÷ PCV 42 % = 22.4 — one of the three is misread"), with every number kept exactly as
  printed. Hovering a translated flag shows the English original, so the source wording is always one look away.
  Guideline titles (WHO IMCI, ISSHP, …) stay in English as citations.
- **How the wording was checked:** every Hindi and Odia line added this week was translated back to English by the
  offline IndicTrans2 and read against the original. That found an Odia word for "jaw" that also means "moon", a
  "breathing worse" that could read as "bad breath", and loose terms for diarrhoea, lethargy, sunken eyes and fits;
  all fixed to the words the rest of the Odia screens use. A native speaker's review is still to do.
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

**G6 Disclaimer** · Working
- On every screen and every printed page; in PDF, print, CSV, JSON, FHIR and CDA exports; on the QR slip and the
  referral text. The kiosk reads it aloud as part of the consent text.

**G7 Responsible-AI dossier** · Working
- EVALUATION.md has the measured figures, including speech error rates for Hindi, Kannada and Odia.
- **About the models** (`/about/models`): a card per engine with its job, where it runs, what is sent, licence,
  measured results, known limits and what it never decides; in English, Hindi, Odia and Kannada.
- **Bias table:** speech errors by speaker sex; the rules re-run with only sex or age changed; the second opinion's
  agreement by sex and age band (`backend/scripts/eval_bias.py`).

**G8 Data-origin tagging** · Working
- `data_origin` (SYNTHETIC or PUBLIC_SAMPLE, set by `JEEVIA_DATA_ORIGIN`) on every patient and encounter
  (migration 0011), in `/health` and in every export. Every screen says "Synthetic demo data — no real patients".

**G9 Security hardening** · Working
- **Encryption at rest:** patient name, phone, village and proxy name are stored as Fernet ciphertext; the phone is
  found by a keyed hash. Every uploaded file is encrypted before it reaches disk, S3 or Cloudinary.
- **Rate limits:** per device or address, and per phone number, on public links, kiosk lookups, speech, voice and
  translation, uploads and sign-in checks (429 with Retry-After).
- **Headers:** a strict policy on every API response; a Content Security Policy and HSTS on the web app.
- **Uploads:** typed by their bytes; scripted SVGs refused; files served sandboxed.
- **Production guard:** the server will not start with a default secret, no data key, mock codes or an open CORS list.
- **Scans in CI:** pip-audit, bandit, npm audit, gitleaks.
- **Code:** `backend/app/crypto.py`, `ratelimit.py`, `filetypes.py`; 11 tests in `backend/tests/test_security.py`;
  threats, scan results and DPDP checklist in `SECURITY.md`.
- **DPDP:** under 18, consent must come from a mother, father or guardian (server refuses otherwise; the kiosk sends the helper back to the consent step). The patient slip shows the grievance contact (`JEEVIA_GRIEVANCE_CONTACT`).

### H. Platform

| Feature | Status | What and where |
|---|---|---|
| **H1** Database | Working | `backend/app/models.py`; migrations `backend/migrations/versions/0001`–`0013`, applied at start-up |
| **H2** API | Working | FastAPI under `/api/v1`, routers in `backend/app/routers/`. Interactive docs at `/docs` |
| **H3** Model serving | Working | `JEEVIA_PROFILE`: `stub` (rules only, no models or online engines; the cloud instance), `demo` (models load on first use), `full` (models load at start-up). An explicit setting wins over the profile. The summary model is a separate llama.cpp `llama-server` process |
| **H4** File storage with expiry | Working | `backend/app/storage.py` |
| **H5** Visible fallback when an engine is down | Working | `GET /language/engines` lists what is installed and loaded; a missing engine answers 503 and never a fake result. Every note has `processing_status`: report reading, translation, speech and AI summary, each ok / failed / fallback / unsure. A failed stage raises `STAGE-DEGRADED`; a missing summary model raises `LLM-OFF` |
| **H6** Offline kiosk | Working | `frontend/src/lib/offline/outbox.ts`, `precache.ts`, `public/sw.js`. Check-ins wait in IndexedDB and replay without duplicates (`client_ref`) |
| **H7** Speed targets | Partial | Speech and summary measured. **Left:** the rest |
| **H8** Logging | Working | `backend/app/observability.py`: JSON logs with request IDs and no request bodies; `/metrics`; `/health` |
| **H9** Deployment | Partial | `docker-compose.yml`, `render.yaml`, Vercel. **Left:** update the public link and recheck Compose |
| **H10** CI | Working | `.github/workflows/ci.yml` |

---

## 5. Flags a reviewer can see on a note

The list shows clinical flags (rules and follow-ups about the patient) first. Flags about how the data was captured
(translation, OCR, voice, offline, redaction) follow under **About the data**, and the referral letter leaves them out.

Above the flags, the summary card has a **history block**: what the patient said yes to on questioning, what they denied
(pertinent negatives), allergies ("not asked" is highlighted and listed under missing information), regular medicines
(confirmed from a strip, as told, or "names not given"), and past history. The template summary follows the same order:
who, complaint and duration, other symptoms, on questioning, denies, allergies, medicines, past history, abnormal vitals,
abnormal report values. Every line comes from an answer the patient gave; nothing is inferred.

| Flag | Meaning |
|---|---|
| `ASR-UNCONFIRMED` | The patient skipped the spoken read-back of their transcript |
| `MT-CHECK` | History was machine-translated; check it against the patient's own words shown beside it. A warning (not info) when the translation left out or added a symptom, or was unsure of a number or symptom |
| `DISAGREE` | Two sources disagree, such as today's BP and the BP on a report |
| `DOC-CHECK` | A report looks old, its name does not match, or a value needs checking |
| `LAB-SUM` | The report's own numbers do not add up (a WBC differential not 100 %, globulin not total protein − albumin, …): one of the values in the sum is misread. Each is marked for checking against its image crop |
| `MEDS-UNCONFIRMED` | Medicine names were read from a strip or prescription and await confirmation |
| `PII-REDACTED` | Identifiers were removed from the patient's free text |
| `NO-AI` | The patient chose to continue without AI |
| `STAGE-DEGRADED` | Part of the automatic processing failed (for example a report the OCR could not read). The note's `processing_status` lists every stage and what happened |
| `LLM-OFF` | The AI summary model was not available; the template summary is shown. Urgency always comes from the rules |
| `LLM-FELL-BACK` | The AI summary failed a check; the template summary is shown with the reason |
| `AI-OPINION-HIGHER` | The AI model's own urgency is higher than the rules'. Take a second look; urgency is unchanged |
| `PROXY` | The history was given by a family member or caregiver |
| `OFFLINE` | Captured offline and synced later; waiting time counts from capture |
| `PPE-GAP` | Workplace finding: protective equipment not issued, or worn only sometimes or never. Not part of urgency |
| `SAFE-PROVISIONAL` | UNDETERMINED, held at YELLOW until the listed vitals or checks are recorded |
| `FU-HTN-STAGE2`, `FU-JAUNDICE`, `FU-HAEMATURIA` | "Follow-up: …" info flags from `followup.yaml`: worth a doctor's look at this visit, but the colour is unchanged |
| `MOCK-RULES` | Mock mode only (no backend): the note came from the browser's small rule subset, not the real rules |

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
cd backend && .venv/Scripts/python.exe -m pytest -q     # 1,143 tests (some skip where the speech and translation packages or the CDA schema are not installed)
cd frontend && npx tsc --noEmit && npm run lint
```

| Test file | Tests | Covers |
|---|---|---|
| `test_output_guard.py` | 144 | Red-team set (101 blocked, 40 allowed) plus normalisation; guard test page samples, audit label, scrubbing, supervisor-only |
| `test_rules.py` | 63 | Rules engine, findings, negation, Hindi and Odia phrases, crush-injury fix |
| `test_timeline.py` | 22 | Onset labels and conflicts |
| `test_regions.py` | 28 | Regional calendar: festival and season dates by state, two-meaning words, no guessing, facility overrides, cadre names, every date sourced, every directory state covered |
| `test_referrals.py` | 7 | E4 referral closed only on receipt (QR code or doctor), overdue alert raised and resolved; E5 clinic days, facility's own days and holidays, follow-up moved; F2 patient load; A7 online voice; H3 profiles |
| `test_override.py` | 7 | E9 raise free and lower by a doctor with a reason, override rate per rule; G6/G8 disclaimer and data origin in every export; H5 stage status and fallback flag; A6 logged pick, no merge; A8 Celsius, BP order and range refused |
| `test_api.py` | 20 | Sign-in, roles, consent, offline replay, overrides, escalations, exports, audit |
| `test_wednesday.py` | 27 | AIIMS high-risk floor; occupational rules, FEV1 baseline, PPE gap, employer rates without symptoms; sign-off limits and note density by role; queue reasons and capacity alert; fever cluster and suppressed export; missed visit, neutral call, no-phone refusal; SQLite column patch |
| `test_telephony.py` | 8 | Real calls and SMS against a fake Twilio and Vonage: only the demo phone is dialled, unsigned webhooks refused, keypad answers, a keyed danger sign texts staff without a name, no key twice hands over, a recorded answer is read and deleted, not answered and cut off, SMS says nothing about health; Vonage: keypad danger sign over NCCO, recorded answer read and deleted |
| `test_calls.py` | 51 | Reminder calls: yes / no / not sure in 11 languages, a hedge is never yes or no, every line in every language with the same slots, a call in Tamil, Sarvam speaks only the fixed lines, danger signs with negation, headache pages a person, a sign said freely, baby's movements from 24 weeks, not sure hands over, all-no is weak evidence, someone else hears nothing about health, a serious or unassessed last visit means a person calls, no answer, access |
| `test_zz_scenarios.py` | 2 | Demo scenarios load once and each demo moment works; Synthea histories load once and a new visit shows the BP trend (runs last) |
| `test_note_history.py` | 5 | The note's history block (positives, pertinent negatives, allergies, medicines, past history), allergy not asked goes to missing information, flags split clinical / data, "Not sure" is not "No", possible-ectopic and 2-week-cough rules |
| `test_question_flow.py` | 4 | The kiosk question file: valid against the finding dictionary, JSON matches YAML, a planted unknown finding fails, answers reach the rules |
| `test_cda.py` | 3 | HL7 CDA export valid against the CDA R2 schema (with and without a note, before and after review) |
| `test_privacy.py` | 19 | Name and number removal, Indian digits, cohort small-count suppression |
| `test_orgs.py` | 16 | Organisations, roster, fitness, directory |
| `test_asr_second.py` | 24 | B9: number words and spellings compared as one (incl. Odia number words with a vowel sign slipped), a different number or symptom always flagged, both engines through the API (consent-gated, refused audio, Sarvam-only fallback), the offline IndicWhisper check after the reply (no connection, no key, a failed check says so, only the recorder can read it), the note's flag and second-engine-only symptom, the 6 Oct live-test cases |
| `test_language.py` | 17 | Speech and translation wiring, the two-at-once freeze, and the 5 Oct live-test sentences: spoken spellings, translation cross-check, rewrites, unsure numbers, per-sentence onsets, real-model check |
| `test_images.py` | 12 | Document type, medicine matching (incl. the 5 Oct real strip photo), face and ID blurring |
| `test_llm.py` | 19 | Summary checks and the urgency second opinion with a stand-in model (no GPU needed): never changes urgency, higher-only flag, withheld reasons, no-AI consent, switch, disagreement view roles |
| `test_kiosk.py` | 7 | Kiosk links, tokens, returning patients, the Twilio path |
| `test_extraction.py` | 6 | Test-name matching, MCP card values, old-report and name checks, real OCR on a slip |
| `test_ocr_checks.py` | 19 | Reading report rows from tilted photos, ranges under values, OCR misreads and lakhs; two OCR engines that differ flag the value and the rules use the reading further from normal; the quality gate (a clean white page passes, a page blurred past reading asks for a retake); brand names on order lines, dose and everyday words not named, a brand and its printed contents as one medicine; only unreadable pages go online, only with consent, and what Sarvam reads is marked for checking; the note flag |
| `test_lab_checks.py` | 28 | B2: tests once read as another; a differential printed as a count; a number OCR broke in two ("4-54", "19,9e0"); units as OCR writes them ("x10~3/µL", "µmo1/L"); urine "Albumin: Nil" and microscopy; SI units converted with their range; a unit that does not belong; a range in another unit; the lab's H / L marks (agreeing, contradicting, missing on one result); a correct full report adds up; one misread digit breaks each kind of sum and flags every value in it; physiological limits; a TG misread above 400; a direct LDL; the second engine's reading that makes it add up; rounding never fails a sum; the note's LAB-SUM flag |
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
| **HL7 CDA** | Clinical Document Architecture: the older HL7 standard for a clinical document as XML, still what many hospital systems import |
| **LOINC** | Standard codes for lab tests |
| **PMBJP** | Pradhan Mantri Bhartiya Janaushadhi Pariyojana, the government generic-medicine scheme |
| **ABHA** | Ayushman Bharat Health Account number (14 digits) |
| **Undetermined (provisional YELLOW)** | Held at YELLOW because something needed to rule out danger has not been recorded yet |
| **ASHA / ANM / MPW** | Accredited Social Health Activist (village health worker); Auxiliary Nurse Midwife; Multi-Purpose Worker |
| **FEV1 / FVC** | Air blown out in the first second / in total, measured by spirometry |
| **Template summary** | The plain summary built by code from the facts, used whenever the AI summary is off or fails a check |
