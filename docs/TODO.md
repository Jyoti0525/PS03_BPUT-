# PS03 build checklist

Every item from the PS03 Master Plan (Claude Doc, 3 Oct 2026) as a task, with its real state checked in code.
Nothing the problem statement names may be missing, including what it calls "may include", "suggested" or "recommended".

**How to use it**
- `[x]` done and checked in the running app; write the date and commit beside it.
- `[ ]` not done. *Partial:* says what exists and what is left.
- Tick an item only when its **Done when** is true in the app. Code alone, or a slide, does not count.
- Never delete an item. If we drop something, strike it through and write why.

**Deadline:** mid-evaluation **Sat 10 Oct 2026**. The top 5 of 84 teams are chosen on POC and PPT together.
State last checked: **5 Oct 2026, evening** (last commit `bafbe44`; everything marked 5 Oct is uncommitted).

---

## 1. Plan to 10 Oct (day by day)

| Day | Build | Done when | State |
|---|---|---|---|
| Sat 3 Oct | Rules engine v2, real OCR, new repo, free disk space, request Bhashini key | Code on the new repo; 15 GB or more free | Done (`bbf5411`; 99 GB free). Bhashini key still pending |
| Sun 4 Oct | Server speech recognition; translation of free text | An Odia sentence becomes a transcript plus English translation in the note, with the engine named | Done over HTTP (`bafbe44`). **Left:** test with a live voice at the kiosk (§2) |
| Mon 5 Oct | LLM prose with faithfulness check; output guard; anonymisation; "continue without AI" | Red-team phrases blocked and logged; a typed name shows as [NAME] | **Done 5 Oct** (uncommitted): all four, checked live |
| Tue 6 Oct | Image understanding; timeline certainty labels; deck draft starts | A medicine-strip photo becomes a medication list awaiting confirmation; a face is blurred before storage | Image understanding and timeline labels **done early (5 Oct)**. Deck draft not started. **Left:** a live photo of a real strip |
| Wed 7 Oct | Occupational rules, campus cluster alert, maternal missed visit, per-role follow-ups, capacity alert | Each of the seven scenarios has one working demo moment | Not started |
| Thu 8 Oct | Measured figures; hosted deployment; bug fixes; feature freeze at night | Evaluation table with real numbers; the public link works | ASR figures only |
| Fri 9 Oct | Deck final (business proposal, market gap, go-to-market); three rehearsals; backup video | Two full runs in a row inside the slot, with no failure | Not started |

---

## 2. Speech and language accuracy (all languages, not only Odia)

No speech recogniser is 100 % accurate. The goal is that **no recognition error reaches the note unnoticed**, and that every accuracy figure we show is measured.

- [ ] **Live-voice kiosk test, Odia:** 2–3 spoken symptom sentences. *Done when:* transcript, English line, engine name and MT-CHECK flag all appear in the note.
- [ ] **Same live test in Hindi and English.**
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
- [x] **A5 Basic visual inputs** (5 Oct, uncommitted). Report photos and "photo of the problem" are both accepted. Each is redacted before storage and routed to B10, which labels it; a photo of the problem is never interpreted.
- [ ] **A6 Patient identity and matching.** *Partial:* lookup by number. **Check:** match candidates are confirmed by a human, never auto-merged, and every pick is logged.
- [ ] **A7 Spoken read-back and prompts.** *Partial:* browser speech synthesis. Indic Parler-TTS moves after 10 Oct. **Check:** Odia voice quality on the demo laptop.
- [ ] **A8 Vitals entry.** *Partial:* the nurse UI has vitals and AVPU. **Check:** unit lock, plausibility bounds, and a "not measured" option.

### B. Reading and understanding
- [x] **H0 Text-layer check before OCR** (pypdfium2, `bbf5411`).
- [x] **B1 OCR for lab reports** (PS: OCR). RapidOCR with PaddleOCR models, offline (`bbf5411`).
- [ ] **B2 Numeric validation.** *Partial:* lab parser, stale-date and name-mismatch checks. **Left:** flag-versus-range consistency, unit plausibility, physiological bounds, arithmetic checks (WBC differential near 100 %, absolute count = % × total, globulin = total protein − albumin).
- [x] **B3 Key-detail extraction**: test, value, unit, range, traced to the image.
- [x] **B4 Timeline summary with certainty labels** (5 Oct, uncommitted).
  - `app/triage/timeline.py` labels each onset STATED, INFERRED, VAGUE or UNKNOWN (plus RECORDED for dated records), with the patient's raw words. Works in English, Hindi (both scripts) and Odia.
  - Ignores "3 times a day", "32 weeks pregnant" and "2 years old".
  - A said-vs-tapped conflict ("3 days" said, "1–4 weeks" tapped) becomes a missing-info question.
  - The rules engine now uses a STATED onset when nothing was tapped, with a wide window. 22 tests.
  - **Left:** the regional festival calendar (F5) for "since Diwali" hints.
- [x] **B5 Structured note** (PS: structured triage note; lightweight LLM summarisation). Done 5 Oct, uncommitted; checked live. An Odia chest-pain case was summarised in 1.8 s, the checks passed, and the model badge shows on the note:
  - [x] `app/llm.py`: fact sheet → Qwen3-4B-Instruct-2507 Q4_K_M via llama.cpp llama-server (`JEEVIA_LLM_URL`) → faithfulness check (numbers incl. number words, units, medicines, and every stated or denied symptom against the rules engine's findings) → output guard → else template + FAIL_FELL_BACK.
  - [x] Runs in the background after intake and after new vitals; never overwrites a clinician's edit; skipped for "continue without AI".
  - [x] The note shows who wrote the summary (model badge or "Template summary"), the template beside it, and any rejected text with reasons.
  - [x] 10 tests with a stand-in model (`tests/test_llm.py`).
  - [x] llama.cpp b11424 (CUDA 12.4) and the GGUF (SHA-256 checked) run on the laptop GPU (3.1 GB VRAM). `scripts/start_llm.sh` starts it; the backend needs `JEEVIA_LLM_URL=http://127.0.0.1:8031`.
  - [x] Measured (`docs/EVALUATION.md`): tuning set 30/30 after fixes (first prompt 19/30); held-out set 18/20 (first run 19/20, then a framing fix); median 0.8 s.
  - [x] Found and fixed through this work: "normal check-up" framing; an invented "denies chest pain" (from our own prompt example); the rules bug "stone-crushing unit" → crush injury.
- [x] **B6 Missing information** (PS: identify missing information). The note lists what blocks GREEN (`bbf5411`).
- [ ] **B7 Follow-up questions by role** (PS: for health worker, nurse, doctor, medical officer). *Partial:* health worker, nurse and doctor questions exist. **Left:** medical-officer questions, and the per-role view (needs the E2 roles).
- [x] **B8 Test-name normalisation (LOINC)**: a LOINC code on parsed tests.
- [ ] **B9 Cross-engine disagreement flag.** Speech: local model vs Bhashini. OCR: second engine (docTR moves after 10 Oct).
- [ ] **B10 Image understanding without diagnosis** (PS: basic visual inputs; Multimodal 15 %). *Nearly done (5 Oct, uncommitted):*
  - [x] Document-type label: lab report, prescription, medicine strip, discharge summary, MCP card, other, or non-document. Deterministic, with the deciding words shown.
  - [x] Medicine names matched to the **PMBJP list of 2,110 generic medicines** (PIB, Govt of India, free to reproduce with acknowledgement; 1,087 names, `scripts/build_medicine_list.py`). Strength is read too. Each name awaits confirmation; nurse/doctor Confirm or "Not this", audited. Checked live in the browser.
  - [x] Faces pixelated (YuNet, MIT, vendored; checked on a public-domain portrait) and phone/Aadhaar/ABHA lines blacked out **before storage**. Photos are always re-encoded, which drops EXIF/GPS.
  - [x] A photo of the problem gets zero interpretation. 11 tests (`tests/test_images.py`).
  - [ ] Live test with a phone photo of a real medicine strip and a real prescription. Handwritten prescriptions will mostly fail OCR; say so.

### C. Triage intelligence
- [x] **C1 Risk-category tagging** (PS: risk-category tagging; rules-based flags). About 150 cited rules: ATP, IITT adult and paediatric, IMCI, maternal, labs, local (`bbf5411`).
- [x] **C2 Urgency signal highlighting**: each tier shows its rule, the value and the source.
- [ ] **C3 Queue prioritisation** (PS: queue prioritisation; patient load varies). *Partial:* urgency, then waiting time. **Left:** capacity alert to the medical officer when unacknowledged REDs outnumber reviewers on shift; ordering reason printed on each row.
- [ ] **C4 Non-diagnostic output guard** (PS: explicitly non-diagnostic). *Nearly done (5 Oct, uncommitted):*
  - [x] Pattern list (`app/output_guard.yaml`): condition names, diagnostic phrasing, medicine/dose/treatment advice in English, Hindi (Devanagari + romanised), Odia. A phrase passes only if the source data already says it.
  - [x] Red-team set: 101 of 101 blocked, 40 of 40 safe sentences passed (`tests/data/redteam_outputs.yaml`; written in `docs/EVALUATION.md` with its limits).
  - [x] Blocked outputs logged (audit GUARD_BLOCK, with the rejected text) and shown on the note ("Rejected AI text and why").
  - [x] Runs on every real model output (B5 live). The model has produced no blockable phrasing on 50 cases.
  - [ ] **Demo step 5 needs a visible block.** Plan: a supervisor "guard test" button that runs a red-team sentence through the same guard and logs GUARD_BLOCK. It must be labelled as a test, never passed off as a real model output.
- [ ] **C5 AIIMS 2025 high-risk complaints.** **Check:** the six complaints (shortness of breath, altered mental status, haematemesis, fall from height, one-sided weakness, chest pain) raise urgency. Only `findings.py` mentions haematemesis today.
- [x] **C6 Children 5–13 and trauma rules**: IITT paediatric and adult; trauma is never GREEN (`bbf5411`).
- [x] **C7 Unknown is never normal**: no GREEN until vitals, AVPU and the danger-sign check are recorded (`bbf5411`). **Check:** whether an explicit UNDETERMINED tier is shown (the plan's wording).
- [ ] **C8 Rule-vs-LLM disagreement view**: an optional LLM urgency opinion shown beside the rule result, never replacing it.

### D. The seven scenarios (all suggested in the PS)
- [x] **D1 Outpatient queue triage**
- [ ] **D2 Occupational screening, industrial estates.** *Partial:* employer portal, roster, fitness status. **Left:** exposure and PPE questions; occupational rules (respiratory symptoms with dust, TB signs with silica → RED, PPE gap); spirometry or year-on-year breathlessness; department rates; a check that the employer never sees a symptom.
- [ ] **D3 Campus fever triage.** *Partial:* campus facility type. **Left:** hostel-block cluster alert (5 or more fevers in 72 h and more than 3× the 14-day average), sent de-identified to the campus medical officer, plus a syndromic count export.
- [ ] **D4 Maternal follow-up reminders.** *Partial:* maternal branch and reminders. **Left:** missed-visit detection, routed to the assigned ASHA first and then a reminder call; `phone_belongs_to` rule (nothing reproductive is spoken on a shared phone).
- [x] **D5 Chronic disease check-in**: trend against earlier visits. **Check:** HbA1c trend and the "what changed" flow.
- [x] **D6 Public health camp, offline**: offline kiosk with sync.
- [x] **D7 Referral notes for higher facilities**: referral, QR summary, PDF, print, JSON, CSV, FHIR R4.

### E. Human review and workflow
- [x] **E1 Reviewer dashboard** (PS: reviewer dashboard)
- [ ] **E2 Four reviewer roles** (PS: health worker, nurse, doctor, medical officer). *Partial:* the roles are doctor, nurse, receptionist, supervisor and employer. **Left:** health worker (ASHA, ANM, MPW) and medical officer roles, each with its own note density and sign-off limit. A health worker cannot confirm RED or YELLOW.
- [x] **E3 Escalation and handoff**: auto-escalation timers. **Check:** escalation climbs to the next role and the timer restarts.
- [ ] **E4 Referral preparation** (PS: referral preparation). *Partial:* referral packet and exports. **Left:** close a referral only when care is received (status today is `sent`); surface open referrals past their due date; use the facility's specialist list.
- [ ] **E5 Scheduling and reminders.** *Partial:* reminders table. **Left:** visit calendar from facility config, due dates, missed-visit detection (with D4).
- [ ] **E6 Calling agent (simulated in the browser).** Logistics and bounded questions only; a red flag ends the call and pages a human.
- [x] **E7 Note export**: PDF, print, JSON, CSV, FHIR. HL7 CDA moves after 10 Oct.
- [ ] **E8 Patient slip.** **Check:** printed slip with follow-up date, referral and QR, and never an urgency tier. The patient screens already hide urgency.
- [ ] **E9 Override path with reasons.** **Check:** upgrades are free; a downgrade needs the right role and a reason; locked flags stay on record; override rate per rule is tracked.

### F. India context and configuration
- [x] **F1 Facility configuration**: PHC, CHC, sub-centre, district hospital, hospital, clinic, camp, company clinic, industrial unit, campus. **Check:** a live facility switch in under 30 s.
- [ ] **F2 Four variance axes in config**: patient load, languages, specialists, digital maturity. *Partial:* facility types exist. **Left:** each axis visibly changes behaviour (question budget or capacity alert, languages offered, referral path, offline mode).
- [ ] **F3 Accessibility.** **Check:** low-literacy icons, a complete voice path for blind users (spoken consent and disclaimer), a complete tap path for non-speaking users, caregiver proxy, large type and contrast, 48 px touch targets, low-end Android.
- [x] **F4 Longitudinal records**: BP and glucose trends.
- [ ] **F5 Regional calendar and cadres**: festival and season table per region (feeds B4); local cadre names.

### G. Privacy, safety and responsible AI (PS mandatory: consent, minimal retention, anonymisation, auditability, handoff)
- [x] **G1 Consent** (5 Oct, uncommitted). Self or proxy consent, plus **"Continue without AI"** on the kiosk consent step (scope `no_ai`). With it: the mic is hidden, voice entries are refused by the server, nothing is translated, uploaded reports are not OCR-read (staff are told to view the image), and the note carries the NO-AI flag with renderer TEMPLATE. Checked live in the kiosk, plus 4 tests. **When B5 lands:** the LLM must also skip these notes (test to add then).
- [x] **G2 Minimal retention**: purge job and retention page.
- [x] **G3 Anonymisation** (PS mandatory). Done 5 Oct, uncommitted:
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

- [ ] Problem in India: patient load, languages, specialist gaps, digital maturity (sourced figures only)
- [ ] What we built in one sentence, plus the non-diagnostic boundary
- [ ] Architecture diagram
- [ ] Safety architecture: rules decide, the LLM writes, humans confirm, with the LLM-triage meta-analysis figure (re-open the source first)
- [ ] Protocols: ATP, IMCI, IITT, maternal and occupational sources
- [ ] PS compliance matrix (one slide, every phrase ticked)
- [ ] Multimodal: four channels and image understanding without diagnosis
- [ ] India-wide: facility types, live switch, languages measured
- [ ] Privacy and responsible AI mapped to DPDP Rules 2025 and ICMR 2023
- [ ] Evaluation results with targets and misses
- [ ] **Business proposal / business model:** who pays (state NHM programmes, employers' statutory health examinations, campus health budgets, CSR) and a **researched cost per facility**
- [ ] **Market gap:** symptom checkers diagnose, eSanjeevani teleconsults, and nothing produces safe multilingual triage notes for public facilities
- [ ] **Go-to-market and expansion:** pilot PHCs, then district, then state; ABDM integration; industrial-estate partnerships
- [ ] Impact metrics we would track in a pilot
- [ ] Limitations and what is not validated
- [ ] Team and roadmap

---

## 8. To verify or ask

**Re-open before any slide cites it**
- [ ] LLM-triage meta-analysis (BMC Emerg Med 2026)
- [ ] AIIMS 2025 presenting-complaints study
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
