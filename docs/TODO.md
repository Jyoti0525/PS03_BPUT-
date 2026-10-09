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
- [x] Flags, rule descriptions and lab-check sentences translated into Hindi and Odia, numbers kept as printed; English original on hover; lists of any length translate — 7 Oct (commit 25a75a0).
- [x] Back-translation check (offline IndicTrans2) of every Hindi and Odia line added this week; 21 Odia lines corrected — 7 Oct (commit 25a75a0).
- [ ] A native Odia speaker (and a Hindi-speaking clinician) reads the flag and rule wording; the list to read is everything added to `or.ts` / `hi.ts` since commit ebe00c4.
- [x] Measure the 8-bit model with RNNT decoding. Figures to beat: 19.7 % WER for fp32 RNNT, 21.6 % for int8 CTC. Make RNNT the default if it is accurate enough and fast enough. **Done 8 Oct (2da0140):** Odia, same 25 clips: **19.3 % WER**, 5.2 % CER (best so far) but real-time factor **0.64** against 0.22 for CTC, so a 9 s answer takes about 5.7 s against the 2 s target. CTC stays the default; RNNT is a setting (`JEEVIA_ASR_DECODING=rnnt`).
- [x] **Measure every Indian language in FLEURS** (25 clips each, same script): as, bn, gu, hi, kn, ml, mr, ne, or ✅, pa, sd, ta, te, ur. Add per-language WER and CER to `docs/EVALUATION.md`. **Done 8 Oct (2da0140):** all 14; WER from 10.7 % (Hindi) to 38.1 % (Tamil); Sindhi not comparable (model writes Devanagari, FLEURS Arabic script), shown as unmeasured.
- [x] For the languages FLEURS does not cover (brx, doi, kok, ks, mai, mni, sa, sat), find an openly licensed public test set and check its licence first. Until one is measured, label that language "unmeasured" in the app. **Done 8 Oct (774ea33):** IndicVoices (CC BY 4.0), 25 clips each, WER 11.4 % (Sanskrit) to 40.4 % (Kashmiri); shown in the kiosk language menu; natural speech, not comparable with FLEURS (EVALUATION.md).
- [x] Measure translation on the same clips (reference English is in FLEURS); report the score per language. **Done 8 Oct (2da0140):** IndicTrans2 on the speech transcript, chrF++ 45.3 (Sindhi) to 63.8 (Kannada), table in EVALUATION.md.
- [ ] Team-recorded symptom sentences (synthetic scripts, written consent from each speaker). **Kit ready 8 Oct (2da0140):** `docs/recording_kit.md`, consent text, 12 sentences in Odia and Hindi with the medical words in bold, English and Kannada and code-mixed instructions, folder layout for `eval_asr.py`. **Left:** the team records in Odia, Hindi, English, Kannada and code-mixed speech. Measure WER on medical words.
- [x] Per-language confidence threshold. A low-confidence answer does not enter the record; it becomes a question for the health worker. **Done 7 Oct (0a36c36):** CTC confidence from IndicConformer; thresholds calibrated on FLEURS (Odia 0.92, Hindi 0.85, Kannada 0.92, others 0.92); below it the kiosk tells the patient a health worker will ask, the history leaves it out and an `ASR-LOW-CONF` flag carries the words; the rules still read them. Confidence separates well in Odia only (EVALUATION.md).
- [x] Online engine as a second opinion: Sarvam AI (Bhashini access unlikely, 6 Oct), plus IndicWhisper offline so the check works with no network. Any disagreement between the two engines is flagged for review (B9). **Done 6–7 Oct (commit 25a75a0):** see B9.
- [x] The kiosk shows which languages are measured and which are "unmeasured". **Done 7 Oct (0a36c36):** the language menu shows "speech measured: N % word errors" (Hindi 10.7, Kannada 20.6, Odia 21.6, FLEURS) or "speech not yet measured". 8 Oct (2da0140): all 13 comparable FLEURS languages listed.
- [ ] Screen languages: only English, Hindi and Odia today. Add **Kannada** (needed for the campus demo instance), then the other scheduled languages. **Kannada done 7 Oct (0a36c36)** for the patient screens (kiosk, pre-arrival, intake: 342 phrases plus the dictionary); staff screens stay English. **Native review sheet ready 7 Oct (0a36c36):** `docs/translation_review_kn.csv`, 392 lines with the machine read-back into English; the 58 whose read-back shares little with the English come first. **Left:** a Kannada speaker fills it in (we apply the corrections); the other languages.
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
- [ ] **A2 Voice intake** (PS: voice; speech-to-text). *Partial:* offline IndicConformer is done. **Left:** everything in §2. Bhashini adapter added 7 Oct (0a36c36), used for translation when the offline model cannot run; not tested live (no key).
- [x] **A3 Translation English / Hindi / regional** (PS: translation). *Partial:* offline IndicTrans2, original words kept, MT-CHECK flag. **Done 7 Oct (0a36c36):** Bhashini online as the fallback translator (`app/bhashini.py`, keys `BHASHINI_USER_ID` / `BHASHINI_API_KEY`; untested live, no key); English → Indic on the patient slip: an optional advice box, printed in English with the machine translation marked "read it out to the patient", and the slip's labels in the patient's language. **Done 8 Oct (2da0140):** the note lists every answer not given in English, the patient's words beside the English, each marked "Machine translated (engine) — check against the patient's own words", shown open (was folded, first voice answer only); test `test_note_keeps_every_answer_in_the_patients_words_beside_the_translation`. **Not possible without a key:** a live Bhashini test (built, untested live).
- [x] **A4 Report upload**: PDF and images, multiple files.
- [x] **A5 Basic visual inputs** (5 Oct, `ca889e7`). Report photos and "photo of the problem" are both accepted. Each is redacted before storage and routed to B10, which labels it; a photo of the problem is never interpreted.
- [x] **A6 Patient identity and matching.** Done 7 Oct (0a36c36): candidates show why they matched (exact ID, shared household phone, name); a person picks one; the pick is logged with the match reason and the number of candidates (`POST /patients/{id}/pick`); records are never merged.
- [x] **A7 Spoken read-back and prompts.** *Partial:* browser speech synthesis. **Checked 7 Oct on the demo laptop:** Windows has English voices only (UK, US, India English), no Hindi or Odia, so Chrome speaks nothing in Odia. **Added 7 Oct (0a36c36):** when the device has no voice for the language and there is a connection, the kiosk plays Sarvam Bulbul audio (`POST /language/speak`, kept in memory only); the patient's own words go online only if they chose AI helpers. **Offline voice done 7 Oct (0a36c36):** Meta MMS-TTS for Odia, Hindi and Kannada on the server (`app/tts.py`, `models/mms-tts-{ory,hin,kan}`, about 140 MB each, CPU, about 0.5 s per second of speech). `/language/speak` tries it first; Sarvam only for other languages, and the patient's own words never go online without AI consent (`allow_online`). Checked in the browser: Odia Listen is served by the offline voice. Licence CC-BY-NC 4.0: fine for this POC, a commercial deployment needs another voice. **Left:** listen to the Bulbul Odia lines.
- [x] **A8 Vitals entry.** Done 7 Oct (0a36c36): one fixed unit per vital (°F, mmHg …); the kiosk and the nurse form share the plausible ranges; a Celsius temperature is refused, never converted; systolic must exceed diastolic (also checked by the API); a blank box is "Not measured" and never gets a default.

### B. Reading and understanding
- [x] **H0 Text-layer check before OCR** (pypdfium2, `bbf5411`).
- [x] **B1 OCR for lab reports** (PS: OCR). RapidOCR with PaddleOCR models, offline (`bbf5411`). **6–7 Oct (commit 25a75a0):** measured on synthetic reports (5 capture types; development seed 20261006, held-out seed 777 never tuned on); quality gate reworked (one scale, blur after a median filter, ink-vs-paper contrast, "Text hard to read", retake when nothing is read); handwriting read online by Sarvam Vision with the patient's AI consent, measured on 85 real prescriptions (CC BY-ND set). Held-out: values exactly right 99.3 % scans and phone photos, 98.7 % photocopies, 99.3 % thermal, 85.5 % poor photos (72.5 % asked to retake), 3 of 1,515 wrong and not flagged. Handwriting (45 test pages): Sarvam reads 60 % of medicine names, docTR 26 %, RapidOCR 18 %.
- [x] **B2 Numeric validation.** — 7 Oct (commit 25a75a0). Physiological bounds, the lab's H/L mark against the value and range, unit plausibility and SI conversion, range sanity, and the report's numbers against each other (differential, absolute counts, proteins, bilirubin, red-cell indices, lipids, urea/BUN). Measured on a simulation (2,000 reports) and on OCR of new full-panel reports, development and held-out, five capture types, two engines: 0 silent errors on the held-out set, 0 sum false alarms. Found and fixed on the way: OCR-mangled units, and a lakh unit printed in the range cell that turned a high platelet count into a critically low one. EVALUATION.md "Checking the numbers on a report (B2)".
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
- [x] **B9 Cross-engine disagreement flag.** *Speech done 6 Oct (0a36c36):* Sarvam Saaras v3 (online, only with the patient's AI consent) hears the same recording as IndicConformer; `asr_check.py` compares numbers, symptoms and overall agreement; kiosk shows both with *Use this one instead*; note flag *Voice transcript: sources disagree*, recomputed on the server; a second-engine-only symptom counts, labelled. FLEURS Odia: Sarvam 19.1 % WER vs 21.6 %, 0/25 flagged. Live check caught BP 160/100 heard as "160 बटा सो", and found three Odia faults (ଵ for ୱ, ଝାଡ଼ without ା read as "cough", ଚାରିଦିନ), fixed. 18 tests. **7 Oct (commit 25a75a0):** OCR second engine (docTR via OnnxTR, in parallel; values compared test by test, the rules use the reading further from normal): silent errors 10 → 3 of 1,515 held-out tests. IndicWhisper (Vistaar, Odia) as the offline second speech engine when Sarvam cannot be used, run after the reply and picked up by the kiosk (`GET /speech/second/{id}`): 31.7 % WER, 3 of 25 FLEURS clips flagged (all three the clips IndicConformer got most wrong); Odia number words with a slipped vowel sign now read as numbers. 24 tests in `test_asr_second.py`, 19 in `test_ocr_checks.py`. **Left:** IndicWhisper downloads for languages other than Odia.
- [ ] **B10 Image understanding without diagnosis** (PS: basic visual inputs; Multimodal 15 %). *Nearly done (5 Oct, `ca889e7`):*
  - [x] Document-type label: lab report, prescription, medicine strip, discharge summary, MCP card, other, or non-document. Deterministic, with the deciding words shown.
  - [x] Medicine names matched to the **PMBJP list of 2,110 generic medicines** (PIB, Govt of India, free to reproduce with acknowledgement; 1,087 names, `scripts/build_medicine_list.py`). Strength is read too. Each name awaits confirmation; nurse/doctor Confirm or "Not this", audited. Checked live in the browser.
  - [x] Faces pixelated (YuNet, MIT, vendored; checked on a public-domain portrait) and phone/Aadhaar/ABHA lines blacked out **before storage**. Photos are always re-encoded, which drops EXIF/GPS.
  - [x] A photo of the problem gets zero interpretation. 11 tests (`tests/test_images.py`).
  - [x] Live test with a phone photo of a real medicine strip (5 Oct, Jyoti): labelled correctly, all three medicines found. Fixed the same evening (0dc032a): a torn fragment matched a different medicine (pheniramine); strengths in a column on the same row are now read.
  - [x] Brand names (7 Oct, 2da0140): the A-Z Medicine Dataset of India (186,094 brands, CC BY-SA 4.0, attributed in FEATURES.md), taken only where a medicine's name goes on an order line; generics printed under a brand folded into it. Handwritten test pages, docTR: wrong names 11 → 4.
  - [ ] Live test with a real printed prescription (blank out the patient's name first). Handwriting is measured (EVALUATION.md): offline mostly misses it, Sarvam names 29 % of prescribed medicines; say so.

### C. Triage intelligence
- [x] **C1 Risk-category tagging** (PS: risk-category tagging; rules-based flags). About 150 cited rules: ATP, IITT adult and paediatric, IMCI, maternal, labs, local (`bbf5411`).
- [x] **C2 Urgency signal highlighting**: each tier shows its rule, the value and the source.
- [x] **C3 Queue prioritisation** (PS: queue prioritisation; patient load varies): **done 6 Oct** (`8a7c3ee`). Each row prints why it is there; open REDs above the doctors and MOs on duty raise a capacity alert to the MO and a banner on clinical screens, closed automatically when resolved. Demo: mark Dr. Sharma off duty at the desk.
  - [x] **C3 follow-ups — 7 Oct (commit 25a75a0):** filling in from home (H- reference, joins the queue at desk check-in, lapses after 36 h; danger signs go straight to the queue with a "go to emergency / call 108" screen), GREEN long-wait alert to the MO, no patient portal. UX pass: flags in words and a "Why here" line on queue rows, out-of-range values first with word labels, desk token-board layout fix, desk stats refresh on check-in, untranslated review-step labels fixed. Checked in the browser end to end (Hindi).
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
- [x] **E4 Referral preparation** (PS: referral preparation). Done 7 Oct (0a36c36): a referral stays open until care is received, confirmed by the receiving clinician from the QR summary (with the access code) or recorded by the referring doctor with who confirmed it; due in 6 h (RED), 48 h (YELLOW) or 14 days (GREEN); past due it is listed first on the Referrals page and raises a "Referral overdue" alert to the medical officer, resolved on receipt; destinations come from each specialty's `refer_to` in the facility's specialist list (migration 0012).
- [x] **E5 Scheduling and reminders.** *Partial:* reminders table; due dates and missed-visit detection done with D4 (6 Oct); chronic check-in reminders done with E6 (6 Oct, 2da0140): a chronic visit can set the next check-in and assign a health worker, a missed one follows the D4 path, and the next chronic visit closes it. **Done 7 Oct (0a36c36):** visit calendar from facility config (`app/visits.py`): antenatal days (default weekly VHND Wednesday and PMSMA on the 9th), chronic clinic day (default Tuesday), closed weekdays and holidays, set by the supervisor on the Regional calendar page; a future follow-up date moves to the next clinic day; the kiosk offers the next clinic days as buttons.
- [x] **E6 Calling agent (simulated in the browser)**: **done 6 Oct** (0a36c36). Maternal and chronic follow-ups (the plan's scope). Fixed lines in 11 languages (`backend/app/calls.yaml`; English, Hindi and Odia first, the other eight added later the same day and checked by back-translation; all but Hindi need a native check); answers read by rules: the intake lexicon finds danger signs anywhere in an answer, a word list reads yes / no / not sure. A danger sign, or "not sure" / two unreadable answers on a danger question, ends the call and raises a `call_escalation` alert to the MO and the assigned ASHA; acknowledging it needs a note. Never advice (Telemedicine Practice Guidelines 2020). Inverted escalation: the agent may call only after a routine, fully assessed visit; a RED, YELLOW or UNDETERMINED last visit, or no-AI consent, means a person calls with the same script. Someone else on the line, or a phone that is not hers, hears nothing about health. An all-"no" call is weak evidence and keeps the follow-up open. Call screen `/nurse/followups/<id>/call`: browser voice reads the lines where the device has one; answers by tap, typing or speech (server ASR + translation). Table `calls` (migration 0009). Demo: Rina (Odia, 31 weeks) and Ramprasad (chronic, Hindi) are due a call; Kusum's last visit was RED, so only a person may call. 51 tests in `test_calls.py`. **Later on 6 Oct (0a36c36):** Sarvam Bulbul voice for the lines; a hedge ("କମ୍ ହଲୁଛି", moving less) is always "not sure" (it had read as yes); typed answers in languages without a lexicon are translated or only read as plain yes / no; real phone calls and SMS through Twilio or Vonage (see §9: live telephony); real SMS reached the demo phone through Vonage's trial.
- [x] **E7 Note export**: PDF, print, JSON, CSV, FHIR. HL7 CDA: §9, before 10 Oct.
- [x] **E8 Patient slip.** Done 7 Oct (0a36c36): the printed QR slip adds the referral destination and the next follow-up date; it never shows an urgency tier; disclaimer at the foot.
- [x] **E9 Override path with reasons.** Done 7 Oct (0a36c36): any reviewer can raise the urgency, reason optional; lowering needs a doctor or medical officer and a 15-character reason; the rules' output and the RED rules stay on the note; override rate per rule on the supervisor's "Urgency overrides" page (`GET /override-stats`).

### F. India context and configuration
- [x] **F1 Facility configuration**: PHC, CHC, sub-centre, district hospital, hospital, clinic, camp, company clinic, industrial unit, campus. **Check:** a live facility switch in under 30 s.
- [x] **F2 Four variance axes in config**: patient load, languages, specialists, digital maturity. Done 7 Oct (0a36c36): **load** (low / normal / high, migration 0013) sets the kiosk's question budget, and high asks only the safety questions, never dropping one that can make a case RED; **languages** offered by the facility head the kiosk's language list; **specialists** set the referral destinations (E4); **offline mode** off means the kiosk refuses to queue intakes with no network and tells staff to use the paper form.
- [x] **F3 Accessibility.** **Done 7 Oct (0a36c36):** axe-core (WCAG 2.2 AA) on the public kiosk's start, consent and patient-details steps: one finding fixed (step indicator role); controls under 48 px enlarged (language and accessibility buttons, Listen, Cancel); with read-aloud on, the disclaimer and each follow-up question with its choices are now spoken. **Closed 7 Oct (0a36c36):** the facility badge text is now coral-700 (about 6.4:1); every kiosk step to the token screen audited with axe on an emulated low-end Android phone (360 × 640, CPU 6× slower, 400 kbit/s, 400 ms): no findings except the "via" of the logo, which WCAG exempts; QR codes given names; "I have visited before" and the sample-report buttons enlarged to 48 px; no sideways scrolling; page loads in 2.4 s and submit takes 3.2 s on that profile. Not tried on a physical phone. **Check:** low-literacy icons, a complete voice path for blind users (spoken consent and disclaimer), a complete tap path for non-speaking users, caregiver proxy, large type and contrast, 48 px touch targets, low-end Android.
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
- [x] **G6 Disclaimer.** Done 7 Oct (0a36c36): bar on every screen and on every printed page; in PDF, print, CSV, JSON and FHIR exports, on the QR slip and the referral text; spoken at the kiosk as part of the consent text.
- [x] **G7 Responsible-AI dossier.** *Partial:* `docs/EVALUATION.md`. **Done 7 Oct (0a36c36):** model cards and an in-app "About the models" page (`/about/models`, public, linked from the home page and admin): job, where it runs, what is sent, licence, measured, known limits and what it never decides, for all eight engines; error rates by language (above); override statistics (E9). **Bias table done 7 Oct (0a36c36):** `backend/scripts/eval_bias.py` → `docs/evaluation/bias.json`; speech errors by speaker sex, the rules re-run with only sex or only age changed, and the second opinion's agreement by sex and age band (EVALUATION.md). Every card's text is translated into Hindi, Odia and Kannada; an MMS-TTS card was added.
- [x] **G8 Data-origin tagging.** Done 7 Oct (0a36c36): `data_origin` on every patient and encounter (migration 0011, set by `JEEVIA_DATA_ORIGIN`), in `/health` and every export; "Synthetic demo data — no real patients" on every screen.

- [x] **G9 Security hardening.** Done 8 Oct (0a36c36), see `SECURITY.md`:
  - [x] Encryption at rest: patient name, phone, village and proxy name (Fernet, `JEEVIA_DATA_KEY`); phone found by keyed hash; every stored file encrypted; old rows encrypted at start-up (migration 0014).
  - [x] Rate limits per device/address and per phone (`app/ratelimit.py`) on public links, kiosk lookup, speech/voice/translation, uploads and sign-in checks.
  - [x] Security headers: API (`default-src 'none'`, no-store, HSTS on HTTPS; docs off in production); web app CSP and HSTS. Production refuses to start with dev settings.
  - [x] Uploads typed by their bytes (`app/filetypes.py`); scripted SVGs refused; SVG parsed with defusedxml; files served sandboxed.
  - [x] Share links: a week at most; summary leaves out phone, village and proxy's name.
  - [x] CI `security` job: pip-audit, bandit, npm audit (shipped code), gitleaks. All clean on 8 Oct.
  - [x] Require proxy (guardian) consent for patients under 18, server and kiosk (DPDP s. 9). 8 Oct (0a36c36)
  - [x] Grievance contact on the patient slip (DPDP s. 13). 8 Oct (0a36c36)
  - [x] CI runs the backend tests on PostgreSQL 16 too (schema built by the migrations); upgrade of a database holding unencrypted rows checked by hand. 8 Oct (0a36c36)
  - [x] Real SMS sign-in codes: Twilio Verify service created, server switched from mock. 8 Oct (0a36c36)
  - [x] Real SMS code received on a verified Indian number (Twilio trial). 8 Oct (0a36c36)
  - [~] Live reminder calls: built and tested, but the Vonage trial rejects calls to the demo number ("restricted") and Twilio has no calling number. Left as is by decision, 8 Oct; demo shows the call flow on screen only.
  - [ ] Verify any other live-demo phone in the Twilio console (trial texts verified numbers only); optional Brevo for email codes.

### H. Platform
- [x] **H1 Database schema**
- [x] **H2 API layer (FastAPI)**
- [x] **H3 Model serving.** Done 7 Oct (0a36c36): `JEEVIA_PROFILE` = `stub` (rules only: no speech, translation, OCR, summary model or online engines; Render uses it) / `demo` (laptop default, models load on first use) / `full` (models load at start-up); an explicit setting always wins; `/health` and `/language/engines` report the profile. The summary model runs on llama.cpp `llama-server` (`JEEVIA_LLM_URL`; command in `.env.example`).
- [x] **H4 File storage with retention clock**
- [x] **H5 Visible degradation.** Done 7 Oct (0a36c36): `processing_status` on every note lists report reading, translation, speech and AI summary with ok / failed / fallback / unsure; a failed stage raises STAGE-DEGRADED, a missing model raises LLM-OFF.
- [x] **H6 Offline intake PWA and sync**
- [x] **H7 Performance targets**: text to note under 3 s, voice to transcript under 2 s, report to findings under 15 s, queue under 1 s. All four measured 8 Oct (f832c9a): text and queue met, reports borderline, voice missed for 13 s clips (EVALUATION, Speed).
- [x] **H8 Observability** (`observability.py`)
- [x] **H9 Deployment.** **Live 8 Oct (uncommitted):** https://ps-03-bput.vercel.app (Vercel) + https://jeevia-api-5n8u.onrender.com (Render, stub profile, Neon PostgreSQL 18, Cloudinary files); health green, browser origin allowed, sample facilities seeded. Earlier: `docker-compose.yml` and `render.yaml` exist. **Left:** a public link that works (Vercel + Render, rules and OCR only), the demo profile on the laptop, and a check that Compose still builds.
- [x] **H10 CI** (`.github/workflows/ci.yml`): passing on `bafbe44` (5 Oct).

### I. Data and proof
- [x] **I1 Synthetic dataset.** Demo seed, synthetic lab slips in five capture types (scan, photo, poor photo, photocopy, thermal), generated firing / non-firing / boundary / unknown cases for all 162 rules (`test_rule_coverage.py`), 493 incomplete cases (`eval_missing.py`), occupational cohort over two cycles and the campus fever cluster (`app/scenarios.py`), public voice clips (FLEURS, IndicVoices). **Done 8 Oct (2da0140):** the 300-patient set (`make_patients300.py`: names and villages by region, 30 returning patients, 30 incomplete copies) and 40 medicine-strip pictures in five conditions (`eval_strips.py`: 40/40 labelled and found, strengths 40/40 after a fix).
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
- [x] ASR for every other language (§2): 13 FLEURS languages (8 Oct, 2da0140) and the 8 others on IndicVoices (8 Oct, 774ea33); Sindhi not comparable (script)
- [x] Translation quality per language: chrF++ 45.3–63.8 on all 14 FLEURS languages (8 Oct, 2da0140). The 8 others have no English reference; Santali tested end to end below, and their translations always carry a warning (8 Oct, 774ea33)
- [x] Rule correctness: each rule has a firing, a non-firing, a boundary and an unknown-input test. Report the count; CI fails on a gap. **Done 8 Oct (2da0140):** `tests/test_rule_coverage.py` generates the cases from each rule's YAML; 162/162 fire and do not fire, 68 thresholds in 52 rules exact, 84 unknown-input leaves in 76 rules; the other 86 rules use only items where absence means not reported. A planted ≥→> slip fails 21 rules (`docs/EVALUATION.md`)
- [x] OCR field accuracy on synthetic slips (test, value, unit, range exact match), per capture type: held-out 99.3 / 99.3 / 85.5 / 98.7 / 99.3 % values exact (scan / photo / poor photo / photocopy / thermal, two engines), 3 silent errors in 1,515 (7 Oct, `docs/EVALUATION.md`)
- [x] Validation catch rate: injected digit swaps, unit errors and decimal shifts. Digit and decimal slips: 79.5 % caught, decimal point lost 100 % (B2, 7 Oct). **Unit errors 8 Oct (2da0140):** `scripts/eval_units.py`, 500 reports: wrong unit 97.9 % caught, SI value read as mg/dL 98.5 %, 59 silent of 11,950, no false alarm (`docs/EVALUATION.md`)
- [x] Output guard: 101 red-team outputs, 100 % blocked; 40 safe, 0 false blocks (5 Oct)
- [x] Note faithfulness: held-out 18/20 used, 2 fell back; tuning 30/30; median 0.8 s (5 Oct)
- [x] Missing-information recall on deliberately incomplete cases. **Done 8 Oct (2da0140):** `scripts/eval_missing.py`, 493 one-item-removed versions of the 50 cases; 141/144 items that change the colour are named (97.9 %), required items 344/344; one real gap (diastolic BP at age 12–13) recorded, not changed without a clinician
- [x] Latency for each H7 target, 8 Oct (f832c9a)
- [ ] Review time per case (target under 4 minutes)
- [x] Fairness split by language, sex and age band (§9: the 300-patient set). **First version 7 Oct (0a36c36)** on public speech and the 50 synthetic cases (G7). **Done 8 Oct (2da0140):** 300 patients (50 vignettes × en/hi/or × M/F); first run split 8 vignettes by language (Hindi stroke and burns came out GREEN), lexicon fixed, now 50/50 consistent across language and sex, agreement en 78 / hi 79 / or 77 %, no expected-RED GREEN; protocol-versus-expectation gaps listed for a clinician (EVALUATION.md).
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
- [ ] 9. Maternal: missed visit goes to the ASHA, then the simulated call; "headache" on the call pages a human. *Built 6 Oct* (Rina Majhi at PHC Manikpur, checked live in Odia); rehearse
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
- [x] PS compliance matrix (one slide, every phrase ticked). Slide 15 maps every criterion with its honest state. **Final state 8 Oct (deck version 13):** every criterion built, with measured figures; open items said plainly (Bhashini key, review time, paid telephony, native review); table reader tried and left off. Re-check on 9 Oct only if something changes
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
- [x] **Closed 7 Oct (0a36c36):** new local rule `LOCAL-SEVERE-HTN` (labelled "Local facility rule", not a guideline): ≥ 180 / ≥ 110 mmHg, or ≥ 160 / ≥ 100 with headache, visual change, chest pain, breathlessness or one-sided weakness → YELLOW with a doctor's review. 166/102 with headache is now YELLOW (`tests/test_clinical_decisions.py`). Was: non-pregnant adult with BP 166/102 and headache comes out GREEN (ATP RED needs > 220 / > 110; IITT's BP line is pregnancy only). Check whether IITT or another Indian source gives a YELLOW for severe hypertension with symptoms (found 6 Oct while building the E6 demo)
- [x] **Closed 7 Oct, kept as published:** the WHO IITT age ≥ 12 card says exactly this ("any two of altered mental status, stiff neck, hypothermia or fever, headache" → RED), so loosening it would weaken a published RED criterion. Over-triage of febrile headache is accepted; the doctor can override with a reason (E9). Test pins it. Was: IITT adult "any two of fever, headache, altered mental status, stiff neck" → RED (IITT-A-MENINGISM): makes every febrile headache RED. Check against the full WHO tool (found 6 Oct while building the campus fever demo)
- [x] Indian clinical ASR paper (arXiv 2512.10967). **Read 8 Oct (a917f49):** Kumar et al., "ASR Under the Stethoscope" (30 Nov 2025, CC BY 4.0): IndicWhisper, Whisper, Sarvam, Google, Gemma3n, Omnilingual, Vaani and Gemini on clinical conversations in Kannada, Hindi and Indian English; wide spread across models, failures on code-mixed and vernacular speech, and gaps by speaker role (patient vs clinician) and gender. Supports what we built: a second engine (B9), per-language confidence, read-back, and the team recordings (§2) to measure patient-style speech. Their data is not public, so we cannot score on it.
- [x] CDSCO medical-device software guidance, current status. **Checked 8 Oct (a917f49):** CDSCO issued a *draft* Guidance Document on Medical Device Software under MDR 2017 on 21 Oct 2025 (risk class A–D by medical purpose, significance of the information, and seriousness of the condition; AI change protocol). Secondary sources disagree on whether a final version came out in 2026; the CDSCO site was not readable here, so we say "draft, Oct 2025" on slides. Human review does not by itself take software out of scope; our position is an educational prototype, not a device, and a field pilot would need classification first.
- [x] ATP adoption sites named in the 16 Sep plan. **Checked 8 Oct (a917f49):** ATP in use at AIIMS New Delhi since 2010 (about 1.5 lakh ED patients a year); adopted and modified at AIIMS Bhubaneswar, CMC Vellore and GTB Delhi; Kerala DHS uses a similar protocol in medical colleges, district hospitals and CHCs (J Emerg Trauma Shock 2020;13(2), PMID 36353399 validation). AIIMS Bhubaneswar is the Odisha example for the slides.
- [x] IITT thresholds against the full WHO tool, not only the reference card. **Checked 8 Oct (a917f49)** against WHO's adult tool and reference card PDFs (who.int/tools/triage): every number matches (Red HR < 50 / > 150; high-risk HR < 60 / > 130, RR < 10 / > 30, temp < 36 / > 39, SpO₂ < 92, AVPU; pregnancy SBP ≥ 160 / DBP ≥ 110; burns > 15 %, age < 2 or > 70). Two card items were missing and are now rules: trauma in a patient on blood thinners or with a bleeding disorder (new finding `anticoagulated`), and inhalation injury as a major burn. Not encoded, with reason: "ECG with acute ischaemia" (no ECG input), "known diagnosis requiring urgent surgery" and "pregnancy referred for complications" (need a referral record), polytrauma (not reliably said in a complaint).
- [ ] Finale judging criteria on the official listing. **Tried 8 Oct:** hackathon.bput.ac.in renders with JavaScript and shows nothing to a fetch; a search summary gives innovation 30 / technical 25 / UX 20 / impact 15 / presentation 10 and a 10-minute pitch with 5-minute Q&A, but that could not be traced to an official page, so it is not used. **Left:** read it in a browser or ask the organisers (below).

**For the organisers**
- [ ] Demo slot length; live or recorded demo; projector or machine provided; is a hosted link required?
- [ ] Is a public, PII-redacted benchmark (EkaCare, MIT) allowed for offline evaluation?
- [ ] Finale: is pre-built code allowed, and what must be built on site?
- [ ] Must every team member present?

**For us**
- [x] Drug-name list: PMBJP 2,110 generics via PIB (copyright policy allows reproduction with acknowledgement), 5 Oct
- [x] Bhashini API key (applied 3 Oct): access looks unlikely (6 Oct). Instead: Sarvam AI as the online engine (key in `backend/.env` since 6 Oct; Bulbul voice for E6 in use, Saaras speech-to-text for B9 next), and AI4Bharat IndicWhisper (Vistaar, MIT, offline) as the second speech engine for B9
- [ ] Twilio for real calls and SMS: `JEEVIA_TWILIO_ACCOUNT_SID`, `JEEVIA_TWILIO_AUTH_TOKEN`, `JEEVIA_TWILIO_FROM_NUMBER` (a Twilio number with voice and SMS), `JEEVIA_TELEPHONY_DEMO_TO` (a phone verified in the Twilio console), India on in the voice and SMS geo permissions

---

## 9. Moved before 10 Oct (was "after 10 Oct")

The user's rule (6 Oct): nothing waits until after the mid-evaluation; every item here is built before 10 Oct.

- [x] docTR second OCR engine and OCR disagreement flag (7 Oct, f832c9a; see B9)
- [x] PP-StructureV3 table extraction. Built 8 Oct (a917f49); **measured and left off 8 Oct (774ea33):** the full pipeline took over 15 min per page on the laptop; a light set takes 8.6 s but read 31/340 values exactly on borderless reports, so it would only add false warnings. Two-engine OCR stays (EVALUATION.md)
- [x] HL7 CDA export. **Done 8 Oct (a917f49):** `exports.to_cda`, CDA R2 ClinicalDocument (LOINC 54094-8) with narrative sections and structured vitals and report values; valid against HL7's CDA R2 schema in three cases (`tests/test_cda.py`); "HL7 CDA document" in the case export menu (live and mock).
- [x] Synthea longitudinal histories with Indian demographics. **Done 8 Oct (a917f49):** Synthea (Apache-2.0, seed 1008, 60 people) run locally; `scripts/import_synthea.py` keeps 12 adults with hypertension or asthma (Synthea's US disease model), 71 earlier visits with their BP, pulse, respiration and glucose, and gives them synthetic Indian names, ages and villages near PHC Manikpur. Seeded as SYN-001… (`JEEVIA_SEED_SYNTHEA`); a new visit shows the BP trend (test). No Indian prevalence model exists for Synthea, so the disease mix is not Indian; said in FEATURES.md.
- [x] Santali (Ol Chiki) end to end. **Done 8 Oct (774ea33):** `scripts/santali_e2e.py` through the real API. Speech heard and translated sensibly (6 IndicVoices clips); typed Santali made by machine translation came back as nonsense and 5 of 5 RED complaints came out YELLOW, so a translation from any of the 8 unmeasured languages now always carries an MT-CHECK warning to ask again (test added; EVALUATION.md)
- [ ] Live telephony for the calling agent. *Built 6 Oct (0a36c36)*: Twilio calls with Sarvam's voice and keypad answers, the free answer recorded, transcribed and deleted, reminder SMS and staff SMS on a danger sign; only the demo phone is ever dialled; 6 tests against a fake Twilio. Vonage added the same day (Voice API with NCCO, SMS API; 2 more tests); `cloudflared` installed for the tunnel. Tried live: Vonage SMS works (staff alert and reminders, one segment each); Vonage's trial rejects voice calls to India ("restricted"); a Twilio trial cannot buy a number. **Left:** a live call needs a paid Vonage or Twilio account; a phone-simulator page for the demo was proposed and set aside by the user (6 Oct), to revisit later
- [x] Qwen3-VL-4B document-type label. Built 8 Oct (a917f49); **measured 8 Oct (774ea33):** 43/47 right vs 34/47 for the text label, prescriptions 11/15 vs 3/15, every disagreement was a text-label error, median 11.2 s (EVALUATION.md)
- [x] 300-patient synthetic set and full fairness split. **Done 8 Oct (2da0140):** see §5 fairness and EVALUATION.md.
- [x] Settle cases where the expected colour and the protocol differ. **Done 8 Oct (2da0140):** cited rules NTEP-PRESUMPTIVE-TB, GINA-ASTHMA-LOW-SPO2, IITT-A/P-MAJOR-BURN; follow-up flags (rules/followup.yaml) for BP 160/100+, jaundice, blood in urine that never change the colour; 300-set agreement 78.0 → 84.0 %.
- [ ] Indic Parler-TTS pre-generated prompt audio. *Instead, 6 Oct:* Sarvam Bulbul v3 speaks the call lines (online, 11 languages)
- [x] Question flow moved to versioned YAML with a shared field dictionary; CI fails on undefined fields. **Done 8 Oct (a917f49):** `backend/app/triage/question_flow.yaml` (version 1, 18 questions) is read by the rules and, as `frontend/src/lib/question_flow.json`, by the kiosk; the dictionary is `findings.FINDINGS`. Same 39 answer-to-finding entries as before, and the kiosk picks the same questions in the same order for 2,430 sample intakes.
- [x] Note and referral a doctor can act on without opening anything else. **Done 8 Oct (a917f49):** history block
  (on questioning, denies, allergies, medicines, past history) on the note and in the summary; flags split clinical /
  about the data; referral letter adds pertinent negatives, allergies, medicines, timed vitals, treatment given before
  transfer and the referring doctor, and leaves out data notices.
- [x] Better kiosk questions. **Done 8 Oct (a917f49):** question flow version 2 (29 questions): allergy, daily
  medicines, long-term illness, adherence, child vaccines, possible pregnancy, NTEP cough screen, blood in stool,
  vomiting, chills, burning urine; hi/or/kn text; rule `LOCAL-POSSIBLE-ECTOPIC`; "Not sure" no longer read as "No".
- [x] Strict pass against the official PS03 document (8 Oct, f832c9a): visible disclaimer now says "Educational
  prototype" (exports, case screen, QR slips, hi/or/kn); photos of the problem are described for the reviewer (basic
  visual input; tested live 8 Oct: 3 of 3 described plainly after a prompt fix, median 11 s); HbA1c trend across visits (D5); D4 row corrected (real calls to the demo number, 11 languages).
- [x] Patient-to-referral walk-through in the browser (8 Oct, e0d7334): kiosk check-in gives token, patient ID and QR;
  doctor finds the patient by ID, sends a referral, QR slip opens for the receiving clinician with the access code. Fixed on the
  way: sample reports failed to attach (security policy blocked fetching data: URLs); referrals now carry a short ID
  (REF-XXXXXX) on the referrals list and the receiving summary; patient ID labelled under the token QR; 19 newer kiosk
  safety questions translated into Hindi, Odia and Kannada; share page shows the language name, not its code.
- [x] Fewer choices for busy staff (8 Oct, 774ea33): the reminder call starts with one button (agent, or a person when the rules require it); language, the demo phone and the other caller sit under More options; the agent's rules fold away. The case page keeps Confirm, Override, Escalate and Referral; Edit note, Share QR and downloads are under More; a Next patient button appears once the case is done. The queue's "Why here" line fits on one line on phones. The patient's token can be read aloud. No sideways scroll on phones in the staff header.
- [x] A sample of every facility type the PS names (8 Oct, 7a2ecad): besides PHC Manikpur, the campus and the industrial unit, a district hospital (Puri: doctor, MO, nurse, registration), a private clinic (Bhubaneswar: doctor, front desk) and an NGO health camp (Kandhamal: ASHA, ANM, camp tablet), each with patients waiting (`scenarios.facility_kinds`, phones 9000000011–18, test). Sign-in shows "Other facilities" buttons when connected to the server.
- [x] Sample-data switch in the landing-page navbar (8 Oct, f5c396d; top disclaimer shortened to "Educational prototype · triage support only · not a diagnosis" at the user's request): with `JEEVIA_DEMO_CONTROLS=true` on a local SQLite server, *Sample patients* on/off plus *Reload with fresh times* (no more "60 h" waits); off keeps facilities and staff, empties the queues (`routers/demo.py`, 2 tests, checked in the browser; OPERATIONS.md). The 8 new sample phones added to `demo_phones`.
- [x] Landing-page hero shows the real queue on the demo laptop (8 Oct, f5c396d): `GET /demo/queue-preview` (only with `JEEVIA_DEMO_CONTROLS`, synthetic patients only; elsewhere the illustration stays), top four by urgency with rule and live wait, refreshed every 15 s; the sample switch now stays off across restarts (test).
- [x] Last English on patient and sign-in screens (8 Oct, 1adec2e): sign-in role cards (ASHA / MPW, Medical Officer and others) in Hindi, Odia and Kannada; the default grievance contact on the kiosk slip shown in the patient's language (a facility's own text stays as typed).
- [x] Follow-ups, call screen, regional calendar and doctor lookup checked in the browser (8 Oct, 76d03fc): local demo mode now has three sample follow-ups (missed pregnancy check, chronic review due today, reminder call due after two failed visits) and records visit attempts; a chronic patient's shared phone no longer carries the "say nothing about pregnancy" warning; follow-up labels and the server's who-calls reasons in Hindi, Odia and Kannada; the regional calendar shows a calm notice instead of a red error in local demo mode. With the live API, the calendar ("since Raja" → Raja Parba 14–16 Jun, with source) and the shared-phone lookup work.
- [x] UI clean-up, second pass (8 Oct, 520c8a3): nursing station count cards are the filter (vitals needed, waiting, critical, observed), replacing the tab switch; employer menu translated.
- [x] UI clean-up for first-time users (8 Oct, f832c9a): one account menu instead of three header icons; supervisor
  menu grouped (Facility, Safety & records, Tools); queue count cards are the filter; Share QR and exports in one menu;
  self-refreshing lists lose their Refresh buttons; kiosk's offline simulator moved behind a staff settings button.
- [ ] Finale rubric pass: innovation, technical complexity, real-world impact, UI/UX, presentation

---

## 10. Housekeeping

- [x] Fixed a hang (5 Oct): two translations at the same moment (two kiosks, or start-up warm-up during the first intake) froze the backend, because IndicTrans2's text processor shares one queue. Translations now run one at a time per direction; regression test in `test_language.py`.
- [x] The local frontend was running in **mock mode** (started without `NEXT_PUBLIC_API_MODE=live`). `frontend/.env.local` (not committed) now sets live mode and port 8030 for the demo laptop.
- [ ] Demo-day check: the header must say "All systems operational", not "Local demo mode — no server".
- [x] Demo start order written down (5 Oct): `docs/FEATURES.md` §6, linked from the README.
- [x] Rules bug fixed (5 Oct): "stone-crushing unit" (an occupation) fired the crush-injury trauma rules; regression tests added.

- [x] Update the old mock-mode rules in the frontend (`frontend/src/lib/api/mock/`) or label them; live mode is the demo path. **Labelled 8 Oct (a917f49):** the file says it is an unsynced subset, and every mock note carries a `MOCK-RULES` info flag ("Local demo mode: simplified rules").
- [x] Landing page: patient entry under the hero (scan QR or type the health-centre code → /k/CODE, no login); the bottom "Open the kiosk" button, which led patients to the staff-locked /kiosk, now reads "I'm a patient" and scrolls to it. English, Hindi, Odia. Plus "Don't know the code? Find your nearest health centre" (`GET /kiosk-finder`: all 115k directory facilities nearby, Jeevia ones with their from-home link, others as walk-in with call and directions; nearest first with location, exact district/town first by name; test in `tests/test_arrival.py`). **9 Oct (a867ff3)**
- [x] Any-centre form: `/k/ANYCARE` gives a J- reference and QR; desk or nurse claims it (`POST /encounters/claim`), it joins that centre's queue with the note ready. English, Hindi, Odia; 1,154 backend tests pass. **9 Oct (a867ff3)**
- [x] Intake fixes: the emergency screen for a J- form shows the QR too; review shows the patient's own words and translated answers (Odia/Hindi), not English; after tapping "Today" the follow-up narrows it ("in the last few hours?") instead of asking "since when" again. **9 Oct (b3f8ee0)**
- [x] Lost J- reference: the desk claim box also takes the mobile number the patient gave (latest open any-centre form within 36 h); the patient's screen says so. Test in `tests/test_arrival.py`; 1,155 backend tests pass. **9 Oct (dfcc09d)**
- [x] Sample-data switch no longer removes the any-centre facility and its ANYCARE link (a rebuild recreates them; asserted in `tests/test_zzz_demo_samples.py`). **9 Oct (dfcc09d)**
- [x] Any-centre form needs a mobile number (form asks for it; server refuses without one; test in `tests/test_arrival.py`). 1,156 backend tests pass. **9 Oct (dfcc09d)**
- [x] Nurse/health-worker note rewritten as a bedside checklist: patient's own words beside the translation, history and out-of-range report values; "Act on this now"; one "Measure before this can be routine" list (replaces the rule-ID dump and the duplicate "Still missing"); questions; capture details folded away. Rule trace stays in the doctor view. English, Hindi, Odia. **9 Oct, commit fc41b06**
- [x] Vitals form catches a swapped BP (systolic ≤ diastolic) before saving; server validation errors show as a sentence app-wide, never raw JSON. **9 Oct, commit fc41b06**
- [x] Doctor note rebuilt as one numbered clinical note: 1 Assessment (tier, the rules that decided it with evidence, what to measure, flags, override), 2 Presenting complaint (summary + patient's own words beside the translation), 3 History, 4 Vitals as tiles ("not measured" shown), 5 Investigations, 6 Trend, 7 Still to ask or do (by role). Rule trace, timeline, capture checks and AI text folded into "How this note was made". Report values are a lab table (test, result, normal range, status, "see in report" opens the crop). English, Hindi, Odia. **9 Oct, commit fc41b06**
- [x] Follow-up questions answerable in the note: the nurse or doctor asks the patient, taps Yes / No / Not sure (or a choice such as "At rest / During effort") and can add the patient's words. The answer joins History ("Asked at the bedside", who and when) and leaves the list; where it settles a finding (`backend/app/triage/followups.py` ANSWER_FINDINGS, e.g. one-sided weakness, can't speak full sentences, visual change) the rules re-run and can raise urgency, audited. `POST /encounters/{id}/answers`; tests in `test_bedside_answers.py`. English, Hindi, Odia. **9 Oct, commit fc41b06**
- [ ] Revoke the Hugging Face read token after the hackathon
- [ ] Keep `docs/EVALUATION.md`, `docs/FEATURES.md` and this file current at every commit
