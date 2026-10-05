# PS03 build checklist

Every item from the PS03 Master Plan (Claude Doc, 3 Oct 2026) as a task, with its real state checked in code.
Nothing the problem statement names may be missing, including what it calls "may include", "suggested" or "recommended".

**How to use it**
- `[x]` done and checked in the running app; write the date and commit beside it.
- `[ ]` not done. *Partial:* says what exists and what is left.
- Tick an item only when its **Done when** is true in the app. Code alone, or a slide, does not count.
- Never delete an item. If we drop something, strike it through and write why.

**Deadline:** mid-evaluation **Sat 10 Oct 2026**. The top 5 of 84 teams are chosen on POC and PPT together.
State last checked: **5 Oct 2026, evening** (last commit `ca889e7`).

---

## 1. Plan to 10 Oct (day by day)

| Day | Build | Done when | State |
|---|---|---|---|
| Sat 3 Oct | Rules engine v2, real OCR, new repo, free disk space, request Bhashini key | Code on the new repo; 15 GB or more free | Done (`bbf5411`; 99 GB free). Bhashini key still pending |
| Sun 4 Oct | Server speech recognition; translation of free text | An Odia sentence becomes a transcript plus English translation in the note, with the engine named | Done over HTTP (`bafbe44`). Live voice test in Odia and Hindi done 5 Oct; fixes in §2 |
| Mon 5 Oct | LLM prose with faithfulness check; output guard; anonymisation; "continue without AI" | Red-team phrases blocked and logged; a typed name shows as [NAME] | **Done 5 Oct** (`ca889e7`): all four, checked live |
| Tue 6 Oct | Image understanding; timeline certainty labels; deck draft starts | A medicine-strip photo becomes a medication list awaiting confirmation; a face is blurred before storage | Image understanding and timeline labels **done early (5 Oct)**. Deck draft **done 6 Oct**: 22 slides ([Slides artifact](https://claude.ai/artifact/FsYj1k2qTsaTUZUa44HSRk), private until shared). Live strip photo done 5 Oct; two matcher fixes |
| Wed 7 Oct | Occupational rules, campus cluster alert, maternal missed visit, per-role follow-ups, capacity alert | Each of the seven scenarios has one working demo moment | **Done early (6 Oct)**, `8a7c3ee`: D2, D3, D4, B7/E2, C3, plus C5 and the C7 label; each demo moment checked on the live server (`backend/app/scenarios.py`). 406 tests |
| Thu 8 Oct | Measured figures; hosted deployment; bug fixes; feature freeze at night | Evaluation table with real numbers; the public link works | ASR figures only |
| Fri 9 Oct | Deck final (business proposal, market gap, go-to-market); three rehearsals; backup video | Two full runs in a row inside the slot, with no failure | Not started |

---

## 2. Speech and language accuracy (all languages, not only Odia)

No speech recogniser is 100 % accurate. The goal is that **no recognition error reaches the note unnoticed**, and that every accuracy figure we show is measured.

- [x] **Live-voice kiosk test, Odia:** done 5 Oct by Jyoti, 3 sentences on the laptop microphone. Transcript, English line, engine name and MT-CHECK flag all appeared. Found: translation dropped fever (ଜର), turned ଝାଡ଼ା into "sweating", 56 into "sixty-six"; the word list missed spoken spellings; the timeline put "2 days" against the wrong complaint. All fixed the same evening (0dc032a), see the next items.
- [x] **Same live test in Hindi** (5 Oct, 2 sentences): transcripts word-perfect, translations right.
- [ ] **Same live test in English.**
- [x] Symptom word list matches spoken Hindi/Odia spellings (nukta, long/short vowels, ଶ/ଷ/ସ, silent ୱ) and allows up to two words in between ("ଛାତି ବି ଦରଦ") (5 Oct, 0dc032a).
- [x] Translation cross-check: symptoms in the patient's words vs in the English; a difference makes MT-CHECK a warning naming the sentence, and translation-only evidence is labelled (5 Oct, 0dc032a).
- [x] Translator gets standard words and digits (ଜର → ଜ୍ୱର, ଝାଡ଼ା → ଅତିସାର, ଛପନ ବର୍ଷ → 56 ବର୍ଷ); the record keeps the patient's words; rewrites listed on the note (5 Oct, 0dc032a).
- [x] Near-equal translation candidates compared for numbers and symptoms, all languages, no word list ("number unclear: 66 or 56") (5 Oct, 0dc032a).
- [ ] A native Odia speaker checks the Odia number list (1–100) and spoken-spelling list in `backend/app/mt_checks.py` and `findings.py`.
- [ ] Measure the 8-bit model with RNNT decoding. Figures to beat: 19.7 % WER for fp32 RNNT, 21.6 % for int8 CTC. Make RNNT the default if it is accurate enough and fast enough.
- [ ] **Measure every Indian language in FLEURS** (25 clips each, same script): as, bn, gu, hi, kn, ml, mr, ne, or ✅, pa, sd, ta, te, ur. Add per-language WER and CER to `docs/EVALUATION.md`.
- [ ] For the languages FLEURS does not cover (brx, doi, kok, ks, mai, mni, sa, sat), find an openly licensed public test set and check its licence first. Until one is measured, label that language "unmeasured" in the app.
- [ ] Measure translation on the same clips (reference English is in FLEURS); report the score per language.
- [ ] Team-recorded symptom sentences (synthetic scripts, written consent from each speaker) in Odia, Hindi, English, Kannada and code-mixed speech. Measure WER on medical words.
- [ ] Per-language confidence threshold. A low-confidence answer does not enter the record; it becomes a question for the health worker.
- [ ] Bhashini (or Sarvam) online engine as a second opinion. Any disagreement between the two engines is flagged for review (B9).
- [ ] The kiosk shows which languages are measured and which are "unmeasured".
- [ ] Screen languages: only English, Hindi and Odia today. Add **Kannada** (needed for the campus demo instance), then the other scheduled languages.
- [x] Read-back of the transcript plus patient confirmation or re-record (browser speech synthesis).
- [x] Rules also read the patient's original words, so a mistranslation cannot hide a finding (ଝାଡ଼ା test, `bafbe44`).
- [x] Every note with translated history carries an MT-CHECK flag naming the engine (`bafbe44`).
- [x] Silent, short or unreadable recordings are rejected with a message; no transcript is ever invented (`bafbe44`).
- [x] The 8-bit speech model halves memory. 8-bit translation was rejected because it turned vomiting into nausea (`bafbe44`).

---

## 3. Feature inventory (62 features)

Codes match the plan. **PS** shows the problem-statement phrase each feature answers. The percentages are judging weights: safety 20 %, extraction 20 %, multimodal 15 %, India-wide 15 %, human review 15 %, privacy 10 %, demo 5 %.

### A. Getting information in
- [x] **A1 Guided text intake** (PS: collect symptoms through text; Multimodal). Kiosk and nurse intake, consent, tokens. *Note:* the question flow lives in code, not YAML (YAML is in the roadmap).
- [ ] **A2 Voice intake** (PS: voice; speech-to-text). *Partial:* offline IndicConformer is done. **Left:** everything in §2, plus Bhashini online.
- [ ] **A3 Translation English / Hindi / regional** (PS: translation). *Partial:* offline IndicTrans2, original words kept, MT-CHECK flag. **Left:** Bhashini online; check that the note shows the original beside the translation, marked "machine translated"; English → Indic for advice and slips.
- [x] **A4 Report upload**: PDF and images, multiple files.
- [x] **A5 Basic visual inputs** (5 Oct, `ca889e7`). Report photos and "photo of the problem" are both accepted. Each is redacted before storage and routed to B10, which labels it; a photo of the problem is never interpreted.
- [ ] **A6 Patient identity and matching.** *Partial:* lookup by number. **Check:** match candidates are confirmed by a human, never auto-merged, and every pick is logged.
- [ ] **A7 Spoken read-back and prompts.** *Partial:* browser speech synthesis. Indic Parler-TTS moves after 10 Oct. **Check:** Odia voice quality on the demo laptop.
- [ ] **A8 Vitals entry.** *Partial:* the nurse UI has vitals and AVPU. **Check:** unit lock, plausibility bounds, and a "not measured" option.

### B. Reading and understanding
- [x] **H0 Text-layer check before OCR** (pypdfium2, `bbf5411`).
- [x] **B1 OCR for lab reports** (PS: OCR). RapidOCR with PaddleOCR models, offline (`bbf5411`).
- [ ] **B2 Numeric validation.** *Partial:* lab parser, stale-date and name-mismatch checks. **Left:** flag-versus-range consistency, unit plausibility, physiological bounds, arithmetic checks (WBC differential near 100 %, absolute count = % × total, globulin = total protein − albumin).
- [x] **B3 Key-detail extraction**: test, value, unit, range, traced to the image.
- [x] **B4 Timeline summary with certainty labels** (5 Oct, `ca889e7`).
  - `app/triage/timeline.py` labels each onset STATED, INFERRED, VAGUE or UNKNOWN (plus RECORDED for dated records), with the patient's raw words. Works in English, Hindi (both scripts) and Odia.
  - Ignores "3 times a day", "32 weeks pregnant" and "2 years old".
  - A said-vs-tapped conflict ("3 days" said, "1–4 weeks" tapped) becomes a missing-info question.
  - The rules engine now uses a STATED onset when nothing was tapped, with a wide window. 22 tests.
  - [x] Festival and season onsets are dated by the regional calendar (F5, 5 Oct): the date shows beside the patient's words, the onset stays VAGUE, and the rules never use it.
- [x] **B5 Structured note** (PS: structured triage note; lightweight LLM summarisation). Done 5 Oct (`ca889e7`); checked live. An Odia chest-pain case was summarised in 1.8 s, the checks passed, and the model badge shows on the note:
  - [x] `app/llm.py`: fact sheet → Qwen3-4B-Instruct-2507 Q4_K_M via llama.cpp llama-server (`JEEVIA_LLM_URL`) → faithfulness check (numbers incl. number words, units, medicines, and every stated or denied symptom against the rules engine's findings) → output guard → else template + FAIL_FELL_BACK.
  - [x] Runs in the background after intake and after new vitals; never overwrites a clinician's edit; skipped for "continue without AI".
  - [x] The note shows who wrote the summary (model badge or "Template summary"), the template beside it, and any rejected text with reasons.
  - [x] 10 tests with a stand-in model (`tests/test_llm.py`).
  - [x] llama.cpp b11424 (CUDA 12.4) and the GGUF (SHA-256 checked) run on the laptop GPU (3.1 GB VRAM). `scripts/start_llm.sh` starts it; the backend needs `JEEVIA_LLM_URL=http://127.0.0.1:8031`.
  - [x] Measured (`docs/EVALUATION.md`): tuning set 30/30 after fixes (first prompt 19/30); held-out set 18/20 (first run 19/20, then a framing fix); median 0.8 s.
  - [x] Found and fixed through this work: "normal check-up" framing; an invented "denies chest pain" (from our own prompt example); the rules bug "stone-crushing unit" → crush injury.
- [x] **B6 Missing information** (PS: identify missing information). The note lists what blocks GREEN (`bbf5411`).
- [x] **B7 Follow-up questions by role** (PS: for health worker, nurse, doctor, medical officer): **done 6 Oct** (`8a7c3ee`). Medical-officer questions (transfer for RED, obstetrician at the FRU, worker exposure and Factories Act s.89 notification); up to 3 per role; the server sends each role only its own (health worker → own; nurse → health worker + nurse; doctor and MO → all).
- [x] **B8 Test-name normalisation (LOINC)**: a LOINC code on parsed tests.
- [ ] **B9 Cross-engine disagreement flag.** Speech: local model vs Bhashini. OCR: second engine (docTR moves after 10 Oct).
- [ ] **B10 Image understanding without diagnosis** (PS: basic visual inputs; Multimodal 15 %). *Nearly done (5 Oct, `ca889e7`):*
  - [x] Document-type label: lab report, prescription, medicine strip, discharge summary, MCP card, other, or non-document. Deterministic, with the deciding words shown.
  - [x] Medicine names matched to the **PMBJP list of 2,110 generic medicines** (PIB, Govt of India, free to reproduce with acknowledgement; 1,087 names, `scripts/build_medicine_list.py`). Strength is read too. Each name awaits confirmation; nurse/doctor Confirm or "Not this", audited. Checked live in the browser.
  - [x] Faces pixelated (YuNet, MIT, vendored; checked on a public-domain portrait) and phone/Aadhaar/ABHA lines blacked out **before storage**. Photos are always re-encoded, which drops EXIF/GPS.
  - [x] A photo of the problem gets zero interpretation. 11 tests (`tests/test_images.py`).
  - [x] Live test with a phone photo of a real medicine strip (5 Oct, Jyoti): labelled correctly, all three medicines found. Fixed the same evening (0dc032a): a torn fragment matched a different medicine (pheniramine); strengths in a column on the same row are now read.
  - [ ] Live test with a real printed prescription (blank out the patient's name first). Handwritten prescriptions will mostly fail OCR; say so.

### C. Triage intelligence
- [x] **C1 Risk-category tagging** (PS: risk-category tagging; rules-based flags). About 150 cited rules: ATP, IITT adult and paediatric, IMCI, maternal, labs, local (`bbf5411`).
- [x] **C2 Urgency signal highlighting**: each tier shows its rule, the value and the source.
- [x] **C3 Queue prioritisation** (PS: queue prioritisation; patient load varies): **done 6 Oct** (`8a7c3ee`). Each row prints why it is there; open REDs above the doctors and MOs on duty raise a capacity alert to the MO and a banner on clinical screens, closed automatically when resolved. Demo: mark Dr. Sharma off duty at the desk.
- [x] **C4 Non-diagnostic output guard** (PS: explicitly non-diagnostic). Done 5 Oct (`ca889e7`, demo page 5 Oct, `8a7c3ee`):
  - [x] Pattern list (`app/output_guard.yaml`): condition names, diagnostic phrasing, medicine/dose/treatment advice in English, Hindi (Devanagari + romanised), Odia. A phrase passes only if the source data already says it.
  - [x] Red-team set: 101 of 101 blocked, 40 of 40 safe sentences passed (`tests/data/redteam_outputs.yaml`; written in `docs/EVALUATION.md` with its limits).
  - [x] Blocked outputs logged (audit GUARD_BLOCK, with the rejected text) and shown on the note ("Rejected AI text and why").
  - [x] Runs on every real model output (B5 live). The model has produced no blockable phrasing on 50 cases.
  - [x] **Demo step 5 visible block** (5 Oct, `8a7c3ee`): supervisor page *Output guard test* (`/admin/guard-test`, `POST /guard-test`). A typed or picked red-team sentence goes through the same `output_guard.check`; the page shows each matched phrase and why. Labelled "Test only … not written by the AI model" on the page and in the audit entry (GUARD_BLOCK, resource `guard_test`, no patient). Typed text is scrubbed of names/phone numbers before logging. Checked live in the browser (Odia sentence blocked).
- [x] **C5 AIIMS 2025 high-risk complaints**: **done 6 Oct** (`8a7c3ee`). The check found breathlessness and chest pain (English, Hindi, Odia) GREEN with normal vitals. Fixed with `aiims_hrc.yaml`, a YELLOW floor for all six from age 16, cited to Rauniyar et al., J Emerg Trauma Shock 2025;18(2):62–68 (PMID 40666389).
- [x] **C6 Children 5–13 and trauma rules**: IITT paediatric and adult; trauma is never GREEN (`bbf5411`).
- [x] **C7 Unknown is never normal**: no GREEN until vitals, AVPU and the danger-sign check are recorded (`bbf5411`). Check done 6 Oct: it said "Provisional"; now shown as **UNDETERMINED, held at YELLOW** with what to measure (`8a7c3ee`).
- [x] **C8 Rule-vs-LLM disagreement view**: an optional LLM urgency opinion shown beside the rule result, never replacing it. Done 5 Oct (`8a7c3ee`):
  - [x] The same local model (Qwen3-4B), given the fact sheet but not the rules' result, names a tier and the facts that decided it (`llm.urgency_opinion`). Runs in the background after the summary; skipped when the patient chose no AI (G1) or `JEEVIA_LLM_URGENCY_OPINION=false`.
  - [x] Never changes urgency. More urgent than the rules → warning flag "take a second look"; less urgent → shown only. Its reason goes through faithfulness + output guard; a failed reason is hidden, the tier still shown. Unreadable answers are never guessed. Disagreements are audited.
  - [x] Doctor's note: "AI second opinion" under the rules trace (rules tier vs model tier). Supervisor page *AI second opinions* (`/admin/ai-opinions`, `GET /ai-opinions`): agreement, rules × model table, every disagreement with the final urgency and any override.
  - [x] Measured on the 50 synthetic cases: 58 % agreement; model less urgent on 4 rules-RED cases (why it never decides), more urgent on 8 provisional YELLOWs (5 listed for clinician rule review). `docs/EVALUATION.md`. 9 tests. Checked live: the real model on 7 local demo cases agreed on 6 and was more urgent on one (glucose 318); the flag, the note panel and the supervisor page showed it.

### D. The seven scenarios (all suggested in the PS)
- [x] **D1 Outpatient queue triage**
- [x] **D2 Occupational screening, industrial estates**: **done 6 Oct** (`8a7c3ee`). Exposure and PPE questions; `occupational.yaml` (silica + presumptive TB symptom → RED per NTEP/WHO 2021; dust + cough or breathlessness > 8 weeks, silica 5+ years, breathing worse than last time, FEV1 down 15 % from own baseline per ATS 2014 → YELLOW); PPE-GAP flag (not urgency); employer department rates with k ≥ 5; a test that no symptom word reaches the employer. Rules are adapted (no Indian occupational triage protocol) and need an occupational physician's review.
- [x] **D3 Campus fever triage**: **done 6 Oct** (`8a7c3ee`). Hostel block asked at campus clinics; cluster alert (5+ fevers in 72 h and more than 3× the 14 days before) to the campus MO with counts only; syndromic CSV per day and place with counts under 5 written as "<5". Demo: one more Block C fever at kiosk link CAMPUS01.
- [x] **D4 Maternal follow-up reminders**: **done 6 Oct** (`8a7c3ee`). Missed check-up (a day past due) alerts the assigned ASHA; attempts recorded; after 2 failed attempts a reminder call is due. `phone_belongs_to`: only her own phone hears about the check-up; husband's, family or unknown phone gets a neutral message; no phone → home visit. The call is simulated and English only.
- [x] **D5 Chronic disease check-in**: trend against earlier visits. **Check:** HbA1c trend and the "what changed" flow.
- [x] **D6 Public health camp, offline**: offline kiosk with sync.
- [x] **D7 Referral notes for higher facilities**: referral, QR summary, PDF, print, JSON, CSV, FHIR R4.

### E. Human review and workflow
- [x] **E1 Reviewer dashboard** (PS: reviewer dashboard)
- [x] **E2 Four reviewer roles** (PS: health worker, nurse, doctor, medical officer): **done 6 Oct** (`8a7c3ee`). Health worker and medical officer roles; sign-off limits (health worker GREEN, nurse up to YELLOW, doctor and MO any), enforced by the server; short note for the health worker; the MO can do all a doctor can and receives alerts. Sample accounts 9000000006 (ASHA) and 9000000007 (MO).
- [x] **E3 Escalation and handoff**: auto-escalation timers. **Check:** escalation climbs to the next role and the timer restarts.
- [ ] **E4 Referral preparation** (PS: referral preparation). *Partial:* referral packet and exports. **Left:** close a referral only when care is received (status today is `sent`); surface open referrals past their due date; use the facility's specialist list.
- [ ] **E5 Scheduling and reminders.** *Partial:* reminders table; due dates and missed-visit detection done with D4 (6 Oct). **Left:** visit calendar from facility config; chronic check-in reminders.
- [ ] **E6 Calling agent (simulated in the browser).** Logistics and bounded questions only; a red flag ends the call and pages a human.
- [x] **E7 Note export**: PDF, print, JSON, CSV, FHIR. HL7 CDA moves after 10 Oct.
- [ ] **E8 Patient slip.** **Check:** printed slip with follow-up date, referral and QR, and never an urgency tier. The patient screens already hide urgency.
- [ ] **E9 Override path with reasons.** **Check:** upgrades are free; a downgrade needs the right role and a reason; locked flags stay on record; override rate per rule is tracked.

### F. India context and configuration
- [x] **F1 Facility configuration**: PHC, CHC, sub-centre, district hospital, hospital, clinic, camp, company clinic, industrial unit, campus. **Check:** a live facility switch in under 30 s.
- [ ] **F2 Four variance axes in config**: patient load, languages, specialists, digital maturity. *Partial:* facility types exist. **Left:** each axis visibly changes behaviour (question budget or capacity alert, languages offered, referral path, offline mode).
- [ ] **F3 Accessibility.** **Check:** low-literacy icons, a complete voice path for blind users (spoken consent and disclaimer), a complete tap path for non-speaking users, caregiver proxy, large type and contrast, 48 px touch targets, low-end Android.
- [x] **F4 Longitudinal records**: BP and glucose trends.
- [x] **F5 Regional calendar and cadres**: festival and season table per region (feeds B4); local cadre names. Done 5 Oct (`8a7c3ee`).
  - [x] `backend/app/regions.yaml` is facility configuration, not code. It covers every state and UT in the facility directory (36 entries).
    - Festivals: 42 multi-faith festivals with names in English, Hindi, Odia and other scripts. The 2025–2027 dates come from the DoPT gazetted and restricted holiday lists, and Raja, Nuakhai and Pana Sankranti from the Odisha GAD list. A year that could not be checked is left out.
    - Monsoon: IMD's normal onset and withdrawal dates (CRS Report 3/2020) at a station in each state, plus the northeast monsoon for the southern states.
    - Seasons and the farming cycle: from IMD and NCERT.
  - [x] `app/regions.py` reads "since Diwali", "दिवाली से", "ରଜଠାରୁ", "holi ke baad se" and "pujo theke".
    - A word only counts as a date when a time word goes with it, so "Diwali sweets" is not an onset.
    - It returns the most recent date or window. A word with two meanings ("Eid", Odia "sankranti", "the rains" in Tamil Nadu) shows the latest one and asks which.
    - If the table doesn't have the date, the note says so and doesn't guess.
  - [x] Facility overrides: a supervisor can set local worker names, local monsoon dates and the facility's own festivals (`Facility.region_config`, migration 0007, validated).
  - [x] Cadre names: ASHA, Mitanin (Chhattisgarh), Sahiya (Jharkhand), ASHA Sahyogini (Rajasthan), VHN (Tamil Nadu), JPHN/JHI (Kerala), FHW/MPHW (Gujarat), Arogya Sevika/Sevak (Maharashtra), and first-aider or OH nurse at workplaces. They appear in the staff role label, the staff page and the kiosk helper list.
  - [x] The supervisor page `/admin/calendar` has a "Try a phrase" box, the festivals and seasons with their sources, and the overrides.
  - [x] 28 tests (`tests/test_regions.py`).

### G. Privacy, safety and responsible AI (PS mandatory: consent, minimal retention, anonymisation, auditability, handoff)
- [x] **G1 Consent** (5 Oct, `ca889e7`). Self or proxy consent, plus **"Continue without AI"** on the kiosk consent step (scope `no_ai`). With it: the mic is hidden, voice entries are refused by the server, nothing is translated, uploaded reports are not OCR-read (staff are told to view the image), and the note carries the NO-AI flag with renderer TEMPLATE. Checked live in the kiosk, plus 4 tests. **When B5 lands:** the LLM must also skip these notes (test to add then).
- [x] **G2 Minimal retention**: purge job and retention page.
- [x] **G3 Anonymisation** (PS mandatory). Done 5 Oct (`ca889e7`):
  - [x] Names (registered patient and proxy, plus "my name is …" in English, Hindi, Odia, Kannada), phone, Aadhaar, ABHA and e-mail scrubbed from the patient's free text **before storage and before translation** (`app/privacy.py`). Checked live: an Odia intake shows `[NAME]` and `[PHONE]` in both the Odia and the English line.
  - [x] A word the triage lexicon reads as a symptom is never removed as a name (ସୀତା ଜ୍ୱର keeps ଜ୍ୱର).
  - [x] Staff free text (observation note, override, escalation and acknowledgement reasons): ID numbers scrubbed, names kept.
  - [x] Reviewer sees the PII-REDACTED flag; the audit log records a REDACT event with counts only.
  - [x] De-identified cohort view (`/admin/cohort`, API `/cohort`): counts only, cells of 1–4 shown as "<5", every view audited.
  - [x] Image redaction of faces and ID numbers before storage (with B10).
  - *Limits to state:* names said without an introduction and not on the registration are not found; numbers spoken as words are not recognised.
- [x] **G4 Auditability**: hash-chained audit log. **Check:** VIEW events are logged.
- [x] **G5 Role-based access**: OTP and PIN, device binding, employer limits.
- [ ] **G6 Disclaimer.** *Partial:* on screens and exports. **Check:** it appears on every note and export and on the patient slip, and is spoken where needed.
- [ ] **G7 Responsible-AI dossier.** *Partial:* `docs/EVALUATION.md`. **Left:** model cards (known limits per language), a bias table (errors by language, sex and age band), override statistics, and an in-app "about the models" page.
- [ ] **G8 Data-origin tagging.** *Partial:* the FHIR export is tagged synthetic. **Left:** `data_origin` (SYNTHETIC or PUBLIC_SAMPLE) on every record, and a banner on every screen.

### H. Platform
- [x] **H1 Database schema**
- [x] **H2 API layer (FastAPI)**
- [ ] **H3 Model serving.** *Partial:* models load in-process on first use or at start-up. **Left:** `stub` / `demo` / `full` profiles; the LLM via llama.cpp.
- [x] **H4 File storage with retention clock**
- [ ] **H5 Visible degradation.** *Partial:* engine status endpoint, 503 when a model is missing. **Left:** `processing_status` on the note and a reviewer flag whenever a stage degraded.
- [x] **H6 Offline intake PWA and sync**
- [ ] **H7 Performance targets**: text to note under 3 s, voice to transcript under 2 s, report to findings under 15 s, queue under 1 s. *Partial:* speech measured at 2.0 s for 8.9 s of audio.
- [x] **H8 Observability** (`observability.py`)
- [ ] **H9 Deployment.** *Partial:* `docker-compose.yml` and `render.yaml` exist. **Left:** a public link that works (Vercel + Render, rules and OCR only), the demo profile on the laptop, and a check that Compose still builds.
- [x] **H10 CI** (`.github/workflows/ci.yml`): passing on `bafbe44` (5 Oct).

### I. Data and proof
- [ ] **I1 Synthetic dataset.** *Partial:* demo seed and synthetic lab slips. **Left:** red-flag vignettes per rule, incomplete cases, occupational cohort over two cycles, campus cluster set, voice clips, image set (strips, prescriptions, blurred and glare photos).
- [ ] **I2 Evaluation with real numbers.** *Partial:* Odia ASR. **Left:** see §5.
- [ ] **I3 Demo design and rehearsal.** See §6.

---

## 4. PS compliance index

Every PS phrase and the feature that answers it. A phrase is covered only when all of its features are ticked above.

| PS phrase | Features |
|---|---|
| Human-in-the-loop | E1, E3 |
| Government hospitals, PHCs, camps, company clinics, industrial units, campus centres | F1 |
| Patient-provided symptoms, through text or voice | A1, A2 |
| Uploaded reports; extract key details from sample reports | A4, H0, B1, B2, B3, B8 |
| Basic visual inputs | A5, B10 |
| Structured triage note for qualified review | B5 |
| Summarise timelines | B4 |
| Identify missing information | B6 |
| Follow-up questions for health worker, nurse, doctor, medical officer | B7, E2 |
| Patient load / language / specialist / digital-maturity variance | C3, F2, A3, E4, H6 |
| OCR for lab reports | B1 |
| Translation English / Hindi / regional | A3 |
| Risk-category tagging; rules-based risk flags | C1 |
| Queue prioritisation | C3 |
| Referral preparation | E4, D7 |
| Reviewer dashboard | E1 |
| Explicitly non-diagnostic; must not prescribe or replace a professional | C4 |
| Highlight urgency signals | C2 |
| Support faster review | H7, four-minute review timing |
| Seven suggested scenarios | D1–D7 |
| Synthetic or public sample data only | I1, G8 |
| Clear disclaimer | G6 |
| OCR libraries, speech-to-text, lightweight LLM summarisation | B1, A2, B5 |
| Secure role-based access mockups | G5 |
| Consent, minimal retention, anonymisation, auditability, handoff to qualified staff | G1, G2, G3, G4, E3, E4 |
| Outputs advisory and reviewer-facing | Patient screens show status only |

---

## 5. Measured numbers (due Thu 8 Oct)

Targets are the bar we set for ourselves, not results. Report each actual figure beside its target, misses included.

- [x] ASR, Odia: WER 21.6 % and CER 5.6 % (int8, CTC), 25 FLEURS clips (`docs/EVALUATION.md`)
- [ ] ASR for every other language (§2)
- [ ] Translation quality per language
- [ ] Rule correctness: each rule has a firing, a non-firing, a boundary and an unknown-input test. Report the count; CI fails on a gap.
- [ ] OCR field accuracy on synthetic slips (test, value, unit, range exact match), per capture type
- [ ] Validation catch rate: injected digit swaps, unit errors and decimal shifts
- [x] Output guard: 101 red-team outputs, 100 % blocked; 40 safe, 0 false blocks (5 Oct)
- [x] Note faithfulness: held-out 18/20 used, 2 fell back; tuning 30/30; median 0.8 s (5 Oct)
- [ ] Missing-information recall on deliberately incomplete cases
- [ ] Latency for each H7 target
- [ ] Review time per case (target under 4 minutes)
- [ ] Fairness split by language, sex and age band, or say plainly that it moves after 10 Oct
- No "0 missed REDs" claim: we have no clinician mentor, so we claim protocol-derived tests only.

---

## 6. Demo (about 9 minutes; confirm the slot length)

- [ ] 1. Consent and disclaimer: proxy consent by a daughter-in-law, spoken in Odia; disclaimer read aloud
- [ ] 2. Intake: voice in Odia, read back and confirmed; one answer by tap
- [ ] 3. Report: blurred photo rejected and retaken; one value fails validation and is flagged (deliberate failure 1)
- [ ] 4. Note: RED with rule, value and citation; missing temperature blocks; follow-ups differ for the ASHA and the doctor
- [ ] 5. Review: the ASHA cannot confirm the RED; auto-escalation; the doctor corrects and confirms; the blocked LLM phrase is shown in the log (deliberate failure 2)
- [ ] 6. Referral: district hospital packet, FHIR export, patient slip without a tier
- [ ] 7. Facility switch to an industrial unit in under 30 s
- [ ] 8. Occupational: spirometry decline flagged; the employer sees fitness and department rates only
- [ ] 9. Maternal: missed visit goes to the ASHA, then the simulated call; "headache" on the call pages a human
- [ ] 10. Camp offline: Wi-Fi off, three patients queued, sync on reconnect
- [ ] 11. Proof: audit trail, purge log, evaluation numbers
- [ ] Demo laptop: quit Docker Desktop; preload models; check free RAM
- [ ] Three rehearsals, two full runs in a row with no failure
- [ ] Backup video on the laptop and a USB stick

---

## 7. Deck (PPT): every item before every sitting

Draft of 6 Oct: 22 slides in the [Slides artifact](https://claude.ai/artifact/FsYj1k2qTsaTUZUa44HSRk) (downloads as .pptx or PDF; private until shared from its Share menu). Every figure on it was opened at its source on 6 Oct; the sources are in each slide's footer. Re-check every slide against the build on 9 Oct.

- [x] Problem in India: patient load, languages, specialist gaps, digital maturity (sourced figures only). Slides 2–3 (6 Oct): 79.9 % specialist shortfall at rural CHCs (HDI 2022-23), 1,81,873 AAMs with 494.71 crore footfall (MoHFW Achievements 2025), 22 scheduled languages
- [x] What we built in one sentence, plus the non-diagnostic boundary. Slide 4 (6 Oct)
- [x] Architecture diagram. Slides 5–6 (6 Oct): five-step flow and component diagram
- [x] Safety architecture: rules decide, the LLM writes, humans confirm, with the LLM-triage meta-analysis figure (re-open the source first). Slide 7 (6 Oct): 61 % pooled sensitivity, re-read on PubMed (PMID 42298434), plus our C8 result
- [x] Protocols: ATP, IMCI, IITT, maternal and occupational sources. Slide 8 (6 Oct, version 10 of the deck): 161 rules, adding the AIIMS 2025 high-risk floor and the adapted occupational pack with its sources
- [ ] PS compliance matrix (one slide, every phrase ticked). *Partial:* slide 15 maps every criterion with its honest state, updated 6 Oct after the Wednesday build (four roles, capacity alert, all seven scenarios). **Left:** final state on 9 Oct
- [x] Multimodal: four channels and image understanding without diagnosis. Slide 9 (6 Oct)
- [x] India-wide: facility types, live switch, languages measured. Slide 12 (6 Oct); add the FLEURS languages after Thursday's measurement
- [x] Privacy and responsible AI mapped to DPDP Rules 2025 and ICMR 2023. Slide 13 (6 Oct)
- [x] Evaluation results with targets and misses. Slide 14 (6 Oct): voice-to-transcript target missed (2.7 s vs 2 s); missed REDs vs a clinician still open
- [x] **Business proposal / business model:** who pays (state NHM programmes, employers' statutory health examinations, campus health budgets, CSR) and a **researched cost per facility**. Slides 17–18 (6 Oct): four payers sized from HDI 2022-23, ASI 2024-25 (2.67 lakh factories), AISHE 2021-22 and the OSH Code; hosting ≈ ₹5,000 per PHC a year from Render and Neon prices. **Prices (₹12,000 / ₹60,000 / ₹36,000 / ₹5,000) are proposals for Jyoti to confirm**
- [x] **Market gap:** symptom checkers diagnose, eSanjeevani teleconsults, and nothing produces safe multilingual triage notes for public facilities. Slide 16 (6 Oct)
- [x] **Go-to-market and expansion:** pilot PHCs, then district, then state; ABDM integration; industrial-estate partnerships. Slide 19 (6 Oct), with a gate per phase
- [x] Impact metrics we would track in a pilot. Slide 20 (6 Oct)
- [x] Limitations and what is not validated. Slide 21 (6 Oct)
- [ ] Team and roadmap. *Partial:* slide 22 (6 Oct) has the roadmap. **Left:** team name, members and roles (placeholders on slides 1 and 22)

---

## 8. To verify or ask

**Re-open before any slide cites it**
- [x] LLM-triage meta-analysis (BMC Emerg Med 2026): re-read 6 Oct on PubMed (PMID 42298434, Cui et al.): 11 studies, 3,088 cases, sensitivity 61 % (48–73 %), specificity 97 %
- [x] AIIMS 2025 presenting-complaints study: re-read 6 Oct on PubMed (PMID 40666389, Rauniyar et al., J Emerg Trauma Shock 2025;18(2):62–68): 1,225 adults, 6 of 34 complaints high risk; ORs in `sources.yaml`
- [x] Occupational sources: re-read 6 Oct on PubMed: ATS 2014 workplace spirometry (PMID 24735032, 15 % FEV1 decline plus ageing), ERS 2020 chronic cough > 8 weeks (PMID 31515408)
- [ ] IITT adult "any two of fever, headache, altered mental status, stiff neck" → RED (IITT-A-MENINGISM): makes every febrile headache RED. Check against the full WHO tool (found 6 Oct while building the campus fever demo)
- [ ] Indian clinical ASR paper (arXiv 2512.10967)
- [ ] CDSCO medical-device software guidance, current status
- [ ] ATP adoption sites named in the 16 Sep plan
- [ ] IITT thresholds against the full WHO tool, not only the reference card
- [ ] Finale judging criteria on the official listing

**For the organisers**
- [ ] Demo slot length; live or recorded demo; projector or machine provided; is a hosted link required?
- [ ] Is a public, PII-redacted benchmark (EkaCare, MIT) allowed for offline evaluation?
- [ ] Finale: is pre-built code allowed, and what must be built on site?
- [ ] Must every team member present?

**For us**
- [x] Drug-name list: PMBJP 2,110 generics via PIB (copyright policy allows reproduction with acknowledgement), 5 Oct
- [ ] Bhashini API key (applied 3 Oct); Sarvam as the interim online engine

---

## 9. After 10 Oct (roadmap to the finale; not named in the PS)

- [ ] docTR second OCR engine and OCR disagreement flag
- [ ] PP-StructureV3 table extraction
- [ ] HL7 CDA export
- [ ] Synthea longitudinal histories with Indian demographics
- [ ] Santali (Ol Chiki) end to end
- [ ] Live telephony for the calling agent
- [ ] Qwen3-VL-4B document-type label
- [ ] 300-patient synthetic set and full fairness split
- [ ] Indic Parler-TTS pre-generated prompt audio
- [ ] Question flow moved to versioned YAML with a shared field dictionary; CI fails on undefined fields
- [ ] Finale rubric pass: innovation, technical complexity, real-world impact, UI/UX, presentation

---

## 10. Housekeeping

- [x] Fixed a hang (5 Oct): two translations at the same moment (two kiosks, or start-up warm-up during the first intake) froze the backend, because IndicTrans2's text processor shares one queue. Translations now run one at a time per direction; regression test in `test_language.py`.
- [x] The local frontend was running in **mock mode** (started without `NEXT_PUBLIC_API_MODE=live`). `frontend/.env.local` (not committed) now sets live mode and port 8030 for the demo laptop.
- [ ] Demo-day check: the header must say "All systems operational", not "Local demo mode — no server".
- [x] Demo start order written down (5 Oct): `docs/FEATURES.md` §6, linked from the README.
- [x] Rules bug fixed (5 Oct): "stone-crushing unit" (an occupation) fired the crush-injury trauma rules; regression tests added.

- [ ] Update the old mock-mode rules in the frontend (`frontend/src/lib/api/mock/`) or label them; live mode is the demo path
- [ ] Revoke the Hugging Face read token after the hackathon
- [ ] Keep `docs/EVALUATION.md`, `docs/FEATURES.md` and this file current at every commit
