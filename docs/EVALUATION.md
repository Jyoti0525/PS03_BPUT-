# Measured results

Every figure here was produced by a script in this repo on the demo laptop (Dell G15: i5-12500H, 16 GB RAM,
CPU inference, no GPU). Nothing is quoted from a model card. Re-run the scripts to reproduce.

## Speech recognition — Odia

| | CTC decoding (default) | RNNT decoding |
|---|---|---|
| Word error rate (WER) | **21.2 %** | 19.7 % |
| Character error rate (CER) | **5.5 %** | 5.1 % |
| Processing time per second of speech | 0.27 s | 0.54 s |
| A 10-second answer is ready after | ~2.7 s | ~5.4 s |

- **Engine:** IndicConformer-600M multilingual (AI4Bharat, MIT licence), ONNX on CPU, fully offline.
  The table above is the original fp32 model; the app now ships an 8-bit copy (next section).
- **Data:** the first 25 clips (306.6 s of speech, several speakers) of the Odia (`or_in`) dev split of
  Google FLEURS (CC-BY-4.0). Each clip has a human transcript.
- **Scoring:** punctuation removed, then word- and character-level edit distance.
- **Reproduce:** `python backend/scripts/eval_asr.py models/eval/fleurs_or or`. Set `JEEVIA_ASR_DECODING=rnnt` for the RNNT column.

**What the numbers mean**
- Most word errors are spelling or form differences, not wrong meaning. For example:
  - the reference writes "108" in digits, while the model writes the spoken words "ଶହେ ଆଠ";
  - "ଜିରାଫ୍‌" and "ଜିରାଫ" differ only by a final mark.
- That is why CER is about a quarter of WER.
- The per-clip WER median is 18.2 %; the range is 0–66.7 %.

**Limits**
- FLEURS is read speech from Wikipedia-style sentences, recorded fairly cleanly. Patients at a kiosk speak spontaneously, use dialect and medical words, and have background noise. Real-world error will be higher.
- We have no clinician-labelled patient audio. This test shows the engine works on real Odia speech; it does not prove clinical accuracy.

**Safeguards that do not rely on these numbers**
- The patient hears the transcript read back and confirms it, or re-records.
- Recordings that are silent, too short or unreadable are rejected with a message. No transcript is ever invented.

### 8-bit speech model (the default)

The facility PC is assumed to have 16 GB RAM shared with a browser and other software, and the fp32 model
alone took ~3 GB. `backend/scripts/quantize_asr.py` makes an 8-bit copy (ONNX Runtime dynamic quantisation
of the MatMul weights, per channel; activations stay float). Same 25 clips, CTC decoding (5 Oct):

| | fp32 (original) | int8 (default) |
|---|---|---|
| Size on disk | 2.4 GB | 0.9 GB |
| Word error rate | 21.2 % | 21.6 % |
| Character error rate | 5.5 % | 5.6 % |
| Processing time per second of speech | 0.27 s | 0.26 s |
| Process memory with the speech model loaded | 2.93 GB¹ | **1.61 GB** |

- 17 of 25 transcripts are word-for-word identical; of the other 8, WER rose on 3 clips, fell on 2, unchanged on 3.
- ¹ fp32 memory was measured with a standalone load script (same ONNX settings: memory arena off), not by
  `eval_asr.py`; the int8 figure is from `eval_asr.py` (private bytes, before translation loads).
- Reproduce: `JEEVIA_ASR_MODEL=indic-conformer-600m-int8 python backend/scripts/eval_asr.py models/eval/fleurs_or or`.
  Per-clip results: `docs/evaluation/asr_or_fleurs_dev25_ctc_int8.json`.

## Speech recognition — Hindi, Kannada and Odia, with a confidence threshold (7 Oct)

| Language | Clips (speech) | WER | CER | Processing time per second of speech |
|---|---|---|---|---|
| Hindi (`hi_in`) | 25 (262.8 s) | **10.7 %** | 4.6 % | 0.27 s |
| Kannada (`kn_in`) | 25 (277.9 s) | **20.6 %** | 8.0 % | 0.28 s |
| Odia (`or_in`) | 25 (306.6 s) | **21.6 %** | 5.6 % | 0.22 s |

- **Engine:** IndicConformer-600M int8, CTC decoding, the model the app ships. Same scoring as above.
- **Data:** the first 25 rows of each language's FLEURS dev split (`backend/scripts/fetch_fleurs.py`).
- **Reproduce:** `python backend/scripts/eval_asr.py models/eval/fleurs_<hi|kn|or> <hi|kn|or>`. Per clip, with
  confidence: `docs/evaluation/asr_<lang>_fleurs_dev25_ctc_int8_conf.json`.

**Confidence threshold.** The engine's confidence is the mean probability of the chosen letter over the frames that
emit one. Below the language's threshold, the words are kept out of the history and become an `ASR-LOW-CONF` flag
asking the health worker to check with the patient; the rules still read them, so a danger sign is not lost.

| Language | Threshold | Clips flagged | WER of flagged clips | Bad clips (WER ≥ 30 %) missed |
|---|---|---|---|---|
| Odia | 0.92 | 3 of 25 | 40 %, 44 %, 67 % | 4 (38 %, 46 %, 54 %, 30 %) |
| Hindi | 0.85 | 1 of 25 | 40 % | 3 (33 %, 42 %, 30 %) |
| Kannada | 0.92 | 0 of 25 | — | 5 |

- **What it means:** in Odia the threshold catches the worst clips and flags no good one. In Hindi it catches one. In
  Kannada, confidence does not separate good from bad transcripts on this set: the worst clips (42–44 %) score 0.94.
  The threshold is a first filter, not a guarantee. Read-back to the patient and the second engine (B9) stay the main
  checks. Unmeasured languages use 0.92.
- **Limit:** 25 read-speech clips per language. Thresholds should be re-set on recorded clinic speech.

## Speech and translation — every FLEURS language (8 Oct)

The same 8-bit CTC engine on the first 25 FLEURS dev clips of each of the 14 Indian languages FLEURS covers. The
translation is IndicTrans2 indic-en 200M (offline) run on the speech transcript, so its score includes speech errors;
the FLEURS English sentence is the reference.

| Language | WER | CER | Processing time per second of speech | Translation chrF++ | BLEU |
|---|---|---|---|---|---|
| Assamese | 23.1 % | 5.6 % | 0.29 s | 53.0 | 27.1 |
| Bengali | 11.5 % | 3.6 % | 0.27 s | 58.1 | 32.2 |
| Gujarati | 15.9 % | 4.5 % | 0.27 s | 62.2 | 37.5 |
| Hindi | 10.7 % | 4.6 % | 0.27 s | 62.1 | 32.8 |
| Kannada | 20.6 % | 8.0 % | 0.28 s | 63.8 | 39.3 |
| Malayalam | 20.7 % | 3.6 % | 0.23 s | 62.0 | 37.4 |
| Marathi | 21.3 % | 9.1 % | 0.21 s | 60.0 | 31.4 |
| Nepali | 29.1 % | 12.6 % | 0.25 s | 60.1 | 35.0 |
| Odia | 21.6 % | 5.6 % | 0.22 s | 58.4 | 31.7 |
| Punjabi | 14.2 % | 7.5 % | 0.26 s | 61.8 | 36.6 |
| Sindhi | not comparable (script) | — | 0.22 s | 45.3 | 15.5 |
| Tamil | 38.1 % | 16.9 % | 0.25 s | 58.0 | 21.5 |
| Telugu | 31.5 % | 13.6 % | 0.27 s | 57.2 | 29.9 |
| Urdu | 25.2 % | 12.0 % | 0.25 s | 61.3 | 35.3 |

- **Sindhi:** the model writes Sindhi in Devanagari; FLEURS writes it in Arabic script, so the word error rate
  (101.7 %) measures the script, not the recognition. The translation score, which does not depend on script, is
  given instead. The app shows Sindhi as "speech not yet measured".
- **Tamil and Telugu** are the weakest (agglutinative words: one wrong suffix is a whole wrong word; CER is the
  fairer view). Read-back to the patient matters most there.
- **Speed:** every language runs at 0.21–0.29 s per second of speech on the laptop CPU.
- **RNNT decoding (Odia, same clips):** 19.3 % WER, 5.2 % CER, but 0.64 s per second of speech, so CTC stays the
  default (`JEEVIA_ASR_DECODING=rnnt` switches; per clip: `docs/evaluation/asr_or_fleurs_dev25_rnnt_int8.json`).
- **Reproduce:** `python backend/scripts/eval_fleurs_all.py`; per language
  `docs/evaluation/asr_<lang>_fleurs_dev25_ctc_int8_conf.json`.

## Speech — the eight languages FLEURS lacks (IndicVoices, 8 Oct)

FLEURS has no Bodo, Dogri, Konkani, Kashmiri, Maithili, Manipuri, Sanskrit or Santali. These use the first 25 clips of
each language from **IndicVoices** (AI4Bharat, CC BY 4.0), with the same engine and settings. IndicVoices is natural
(unscripted) speech, not read sentences, so these figures are not directly comparable with the FLEURS table: natural
speech is usually harder. Clips under 1 s were refused by the app, as the kiosk does ("too short"), and are not scored.

| Language | Clips scored | WER | CER | Processing time per second of speech |
|---|---|---|---|---|
| Bodo | 21 | 15.6 % | 5.6 % | 0.47 s |
| Dogri | 25 | 25.4 % | 11.0 % | 0.31 s |
| Konkani | 23 | 33.0 % | 10.9 % | 0.54 s |
| Kashmiri | 23 | 40.4 % | 16.8 % | 0.95 s |
| Maithili | 25 | 28.1 % | 10.1 % | 0.32 s |
| Manipuri | 25 | 14.2 % | 4.5 % | 0.30 s |
| Sanskrit | 23 | 11.4 % | 1.8 % | 0.31 s |
| Santali (Ol Chiki) | 23 | 24.7 % | 7.7 % | 0.31 s |

- With these, every one of the 22 scheduled languages except Sindhi has a measured speech figure, shown in the kiosk's
  language menu.
- **Kashmiri** is the weakest and the slowest; read-back to the patient matters most there.
- 25 clips per language is a small sample; treat a difference of a few points as noise.
- Per clip: `docs/evaluation/asr_<lang>_indicvoices25_ctc_int8.json`. Reproduce:
  `python backend/scripts/eval_asr.py models/eval/iv_<lang> <lang>`.

## Santali (Ol Chiki) end to end (8 Oct)

`backend/scripts/santali_e2e.py` runs the real API in-process (offline, temporary database, no online services).

**Spoken:** six IndicVoices Santali clips (CC BY 4.0) through `/speech/transcribe`. All six were heard in Ol Chiki
(confidence 0.90–0.94) and translated into sensible English ("Then I'd like to have a cake and some fried things").
Speech WER on 23 clips is 24.7 % (table above).

**Typed:** we have no Santali speaker, so eight English complaints were put into Santali by IndicTrans2 and then
entered as a patient would. The English the note got back was mostly nonsense ("chest pain to the left arm" →
"the outbreak of the virus has spread"; "seven months pregnant with bleeding" → "a seven-month-old pig"), and
**5 of the 5 RED complaints came out YELLOW** (3 YELLOW stayed YELLOW). Two machine translations in a row compound
their errors, so this is a pessimistic test, but the rules have no Santali word list to fall back on.

**What changed:** a translated history from any language whose translation is unmeasured (Bodo, Dogri, Konkani,
Kashmiri, Maithili, Manipuri, Sanskrit, Santali) now always carries the MT-CHECK **warning** "translation … has not
been measured and may lose the meaning; ask the complaint again through someone who speaks the language" (test
`test_translation_from_an_unmeasured_language_always_warns`). Santali works end to end, but the complaint must be
confirmed by a person. Per case: `docs/evaluation/santali_e2e.json`.

## Errors by language, sex and age band (G7, 7 Oct)

Reproduce: `python backend/scripts/eval_bias.py` → `docs/evaluation/bias.json`.

**Speech, by speaker sex** (the FLEURS clips above; FLEURS has no speaker age):

| Language | Women: clips, WER | Men: clips, WER |
|---|---|---|
| Hindi | 14, 13.9 % | 11, 7.0 % |
| Kannada | 14, 17.3 % | 11, 24.2 % |
| Odia | 25, 21.6 % | none in this set |

The gaps go in opposite directions in Hindi and Kannada, and 11–14 clips per group from a handful of speakers
cannot separate speaker sex from speaker identity. Odia has women only. This needs recorded clinic speech with
enough speakers of each sex and age before any claim is made.

**Rules, counterfactual check** (the 50 synthetic cases). Only the sex, or only the age, is changed; the urgency
should not move unless a rule is meant to depend on it.

| Change | Runs | Urgency changed |
|---|---|---|
| Sex flipped (non-maternal cases) | 45 | 0 |
| Adult age moved into each other band (18–39, 40–59, 60+) | 86 | 1 |

The one change is by design: "chest tightness on stairs" at 44 → 70 becomes RED through IITT's "pain over 50" rule.

**Second opinion (C8) agreeing with the rules**, by group: women 12 of 24, men 17 of 26; under 12: 3 of 6; 12–17:
0 of 1; 18–39: 9 of 21; 40–59: 11 of 14; 60+: 6 of 8. Agreement is lower for women and for 18–39, but the groups
differ in case mix and are small, so this is a pointer for the next test set, not a finding. The opinion never
changes urgency.

## Offline voice (A7, 7 Oct)

Meta MMS-TTS (VITS) for Odia, Hindi and Kannada, CPU: about 140 MB per language; a 3.5 s Odia sentence took 1.7 s
including the first load. Not scored; listened to by us. Flat, slightly robotic; numbers and English words can be
mispronounced. Licence CC-BY-NC 4.0.

## Clinical rule decisions (7 Oct)

- **Severe hypertension:** IITT's BP line is for pregnancy only and ATP RED needs > 220 / > 110, so 166/102 with a
  headache was GREEN. Added `LOCAL-SEVERE-HTN` (a local facility rule, labelled as such): ≥ 180 / ≥ 110, or ≥ 160 /
  ≥ 100 with headache, visual change, chest pain, breathlessness or one-sided weakness → YELLOW, doctor review.
- **Meningism:** kept as the WHO IITT card states it (any two of altered mental status, stiff neck, fever or
  hypothermia, headache → RED). Fever with headache is over-triaged on purpose; the doctor can override with a reason.

## Rule correctness: every rule tested four ways (8 Oct)

`backend/tests/test_rule_coverage.py` builds the cases from each rule's own YAML condition, so a rule added to the
pack is tested without anyone writing a case for it, and CI (`pytest`) fails if any rule lacks one.

| Case | What it checks | Rules covered |
|---|---|---|
| Firing | an input made from the condition fires the rule | **162 / 162** |
| Non-firing | the nearest input with ordinary values elsewhere gives a definite no | **162 / 162** |
| Boundary | each threshold on the firing path: fires exactly at the published value (≥, ≤) or one step inside it (>, <), not one step past | 52 rules with a numeric threshold, 68 thresholds |
| Unknown input | the measurement or danger sign the rule relied on is removed: the rule says "unknown", never "no" | 76 rules, 84 leaves |

- The other 110 rules have no numeric threshold (findings only). The other 86 rules rely only on items whose absence
  means "not reported" by design: lab values from an uploaded report, workplace answers, symptoms the patient did not
  mention, and blood glucose (`vital_if_measured`, not part of routine triage). They have no unknown-input case.
- **The test catches real slips:** with ≥ / ≤ deliberately changed to > / < in the engine, 21 rules fail the boundary case.
- These cases check that the engine applies the YAML as written. They do not check that the YAML matches the
  protocol; that is the protocol-derived cases in `test_rules.py` and a clinician's reading.

## Missing information on incomplete cases (8 Oct)

The 50 synthetic cases (`tests/data/llm_eval_cases.yaml`), each first completed (ordinary vital signs for the age,
AVPU alert, danger-sign check recorded, an onset, a severity, gestation for pregnancies), then one item removed at a
time: 493 incomplete cases. Whether an item **matters** is decided without asking the engine: the item is filled
with a low and a high value (pulse 40 / 150, onset "last few hours" / "more than a month", severity 1 / 10, …) and it
matters if the triage colour differs.

| | Result |
|---|---|
| Items that matter, named as missing when removed | **141 / 144 (97.9 %)** |
| Required items (core vital signs, AVPU, danger-sign check) named every time | **344 / 344** |
| Items named although neither value changed the colour (extra questions) | 49 of 349 |
| Came out GREEN with an item that matters missing | **1** |

The three not named:
- **Two onsets were not really missing.** "Weakness … since one hour" and "breathless … worse over the last week"
  state the onset in the patient's own words, and the engine used them.
- **One is a real gap: diastolic BP at age 12–13.** A 12-year-old with a scraped knee and systolic 120 is GREEN without
  a diastolic reading; a diastolic of 125 would make it YELLOW (`LOCAL-SEVERE-HTN`). ATP's diastolic rule starts at
  14, and the local rule treats an unmeasured BP as not tested. A 120/125 reading is implausible, so the rule is
  unchanged until a clinician decides; recorded here instead.

Reproduce: `python backend/scripts/eval_missing.py` → `docs/evaluation/missing_info.json`.

## The 300-patient set: same complaint, any language, sex or age (8 Oct)

50 vignettes written by the team (18 RED, 17 YELLOW, 15 GREEN expected, set before the engine was run), each told in
English, Hindi and Odia by a man and a woman (maternal: two women), ages spread over the vignette's range: 300
patients, 30 of them returning with earlier visits, plus 30 incomplete copies (no vital signs, no danger-sign check).
The engine reads the patient's own words through the offline lexicon (no translation model) with recorded vitals.

| | First run | After the fixes below |
|---|---|---|
| Vignettes with one colour across language and sex | 42 / 50 | **50 / 50** (48 across ages too; the other 2 change only at the child-protocol age gates, 5 and 12) |
| Agreement with the expected colour | 74.7 % | 78.0 % |
| Expected RED that came out GREEN | 4 (Hindi stroke ×2, Hindi burns ×2) | **0** |
| Incomplete copies that came out GREEN | 0 / 30 | 0 / 30 |

| Split | Agreement | Under-triage | Over-triage |
|---|---|---|---|
| English / Hindi / Odia | 78 % / 79 % / 77 % | 16 / 16 / 17 | 6 / 5 / 6 |
| Women / men | 80.0 % / 75.6 % | 25 / 24 | 8 / 9 |
| Under 5 / 5–11 / 12–17 / 18–39 / 40–59 / 60+ | 58 / 67 / 75 / 82 / 79 / 80 % | 8 / 4 / 2 / 13 / 14 / 8 | 0 / 1 / 0 / 7 / 6 / 3 |

**Found and fixed by the set** (lexicon, `findings.py`; each has a test in `tests/test_patients300.py`):
Hindi "बोली लड़खड़ा", "हाथ और पैर कमजोर" (stroke) and Odia "କଥା ଅସ୍ପଷ୍ଟ"; Hindi "जल गए" (burns); Hindi and Odia "worst / sudden
headache" phrasings; Odia "ନିଶ୍ୱାସ ଫୁଲୁଛି" (breathless); Hindi and Odia "cut"; "cannot keep water down". False findings
removed: "kerosene stove" read as poisoning, "burning in the chest" (heartburn) read as a burn, "bleeding stopped" read
as bleeding.

**Where the expected colour and the protocols differ** (the same in all three languages, so not bias; the rulepack
follows its published sources and was not changed): GREEN for presumptive TB (3-week cough, weight loss, night
sweats), BP 172/104 without symptoms, asthma worse with SpO2 93 %, jaundice, child fever with rash, blood in urine;
YELLOW for extensive burns (IITT raises burns to RED only under 2 or over 70) and a child with fever and fast
breathing (IMNCI: pneumonia); RED for fever with headache (IITT: any two of fever, headache, confusion, stiff neck)
and a painful swollen wrist at severity 7. Under 5 has the lowest agreement for the same reasons. These are listed for
a clinician to decide; `docs/evaluation/patients300.json` has every patient.

- **Reproduce:** `python backend/scripts/make_patients300.py` then `python backend/scripts/eval_patients300.py`.

### Where my expected colour and the protocol differed (8 Oct)

We could not keep two answers, so each gap was settled by a published source, not by the software guessing:

| Case | Decision | Source |
|---|---|---|
| Suspected TB (cough 2+ weeks, weight loss, night sweats) | New rule NTEP-PRESUMPTIVE-TB → YELLOW | NTEP |
| Asthma with SpO₂ below 94 % | New rule GINA-ASTHMA-LOW-SPO2 → YELLOW | GINA 2024 |
| Burns of the face, neck, both arms or legs (>15 % of the body) | New rules IITT-A/P-MAJOR-BURN → RED | IITT reference card |
| BP 160/100+ with no symptoms, jaundice, blood in urine | Colour stays; a **follow-up flag** shows on the note (FU-HTN-STAGE2, FU-JAUNDICE, FU-HAEMATURIA) | IHCI; jaundice and haematuria marked as local practice |
| Child fast breathing (IMNCI pneumonia), meningism, pain 7/10, small cut | Protocol kept; the expected colour was ours, not the protocol's | IMNCI, IITT, ATP |

Follow-up flags live in `rules/followup.yaml` and cannot change the colour. After the change, agreement on the 300 set rose from 78.0 % to **84.0 %** (under-triage 49 → 31, over-triage 17). No expected-red case is green. The incomplete copies are still never green. 1,108 backend tests pass.

## Medicine-strip pictures (8 Oct)

40 synthetic blister-strip pictures (generic names from the PMBJP list, no real brand drawn): 8 each clean, phone
photo, photo with glare, blurred, and torn (only half the strip).

| Variant | Labelled a medicine strip | Medicine found | Strength right | Other medicines reported |
|---|---|---|---|---|
| clean / photo / glare / blurred / torn | 8 / 8 / 8 / 8 / 8 | 8 / 8 / 8 / 8 / 8 | 8 / 8 / 8 / 8 / 8 | 0 |

- **Fixed on the way:** on blurred and torn pictures OCR wrote "5oo mg", "IPS0mg"; the strength was read as "0 mg"
  (3 of 40). Letters read for digits right before a unit are now put back, and a strength is never taken from the
  tail of a broken number (`images.py`, tests in `test_images.py`).
- **Limit:** printed generic names in a clear font; real strips have brand names, embossing and curved foil. The live
  test on a real strip (5 Oct) is in the image-understanding section.
- **Reproduce:** `python backend/scripts/eval_strips.py models/eval/strips` → `docs/evaluation/strips.json`.

## Kiosk accessibility (F3, 7 Oct)

axe-core 4.10, WCAG 2.2 AA, every kiosk step from start to the token screen, on an emulated low-end Android phone
(360 × 640, CPU 6× slower, 400 kbit/s, 400 ms latency). Findings fixed: the facility badge's contrast (3.1:1 → about
6.4:1), unnamed QR codes, two controls under 48 px. Left: the "via" of the logo (2.3:1; WCAG exempts logos). Page
load 2.4 s, submit 3.2 s. Not tried on a physical phone.

## Second speech engine (B9)

Sarvam Saaras v3 (online, India-hosted) hears the same recording as the offline IndicConformer. The two transcripts
are compared after bringing them to one written form (`backend/app/asr_check.py`): one spelling (the lexicon's loose
form), punctuation dropped, native digits and Hindi/Odia number words turned into digits ("ଶହେ ଆଠ" = 108,
"ଉଣେଇଶ ହଜାର ପାଞ୍ଚଶହ" = 19500, "ଅଠରଟି" = 18, "ଚାରିଦିନ" = 4 days). A different number, a symptom only one engine
heard, or under 80 % of characters matching is a disagreement.

**FLEURS Odia, the same 25 clips as above (6 Oct)**

| Engine | WER | CER |
|---|---|---|
| IndicConformer-600M int8, CTC (offline) | 21.6 % | 5.6 % |
| Sarvam Saaras v3 (online) | 19.1 % | 4.3 % |

- Agreement between the two engines: median 98.6 %, lowest 85.4 %. None of the 25 clean clips is flagged.
- The first run flagged 4 of 25. All four were the same words written differently (number words vs digits, a counting
  suffix, a thousands separator), so the number reading was extended; none was a real mishearing.
- Reproduce: `python backend/scripts/eval_asr_second.py models/eval/fleurs_or or docs/evaluation/asr_or_fleurs_dev25_ctc_int8.json`
  (needs `SARVAM_API_KEY`; one request per clip). Per clip: `docs/evaluation/asr_or_fleurs_dev25_sarvam.json`.

**Live check through the API (6 Oct):** Sarvam's voice reading four clinical sentences, sent to `/speech/transcribe`
with both engines.

| Said | Result |
|---|---|
| मुझे तीन दिन से बुखार है और सीने में दर्द हो रहा है। | Both engines word for word; no flag |
| मेरा बीपी एक सौ साठ बटा सौ आया था और सिर में बहुत दर्द है। | **Caught:** the offline engine heard सौ as सो, losing the diastolic 100, and its translation said "one hundred and sixty-two". Sarvam heard 160/100. Flagged: "numbers: 160 vs 100, 160" |
| ମୋର ଚାରି ଦିନ ହେଲା ଜ୍ୱର ଓ ଝାଡ଼ା ହେଉଛି। | Flagged at first, wrongly (see below); after the fixes, no flag |
| ପିଲା ଆଜି କମ୍ ହଲୁଛି ଏବଂ ମୁଣ୍ଡ ବିନ୍ଧୁଛି। | Both engines word for word; no flag |

The Odia false flag exposed three faults in the rules and translator, now fixed with regression tests:
- the offline engine writes fever ଜ୍ଵର, with ଵ (U+0B35) for the silent ୱ, and the lexicon did not find fever in it;
- both engines wrote ଝାଡ଼ା (loose stools) as ଝାଡ଼, which the lexicon missed and the translator turned into "cough".
  ଝାଡ଼ before an affirmative "happening" verb is now read as ଝାଡ଼ା; ଝାଡ଼ on its own (a bush) and "ଝାଡ଼ ହେଉନି" are not;
- "ଚାରିଦିନ" (number joined to its unit) was compared as a different number.

**Limits**
- Synthetic voice and read speech. Patients speak spontaneously, with noise; disagreement will be more common, which
  is the point, but how often it flags a correct transcript at a kiosk is not yet measured.
- Number words are read for Hindi and Odia only. In the other languages, number words and digits compare as different
  words and count against agreement only.
- Online: used only when the patient allowed AI help, and the consent screen says the recording may be checked online
  in India. Without the offline model (the hosted link) Sarvam alone transcribes and is named as the engine.

### Offline second engine: IndicWhisper (B9)

When Sarvam cannot be used (no key, no network, a language it does not take, or nothing heard), IndicWhisper hears the
recording instead, so the check still works on a facility machine with no connection.

- **Engine:** AI4Bharat Vistaar IndicWhisper, whisper-medium fine-tuned for Odia (MIT), on CPU with Hugging Face
  Transformers. The linear layers are made 8-bit at load time (PyTorch dynamic quantisation).
- **Data:** the same 25 FLEURS Odia clips (306.6 s of speech), compared with the same IndicConformer transcripts.

| 7 Oct, 25 clips | First run: fp32 | First run: 8-bit | Final: 8-bit (default) |
|---|---|---|---|
| Word error rate | 31.7 % | 35.9 % | **31.7 %** |
| Character error rate | 15.1 % | 15.4 % | **10.3 %** |
| Clips flagged as disagreeing with IndicConformer | 4 | 6 | **3** |
| Seconds per clip (average clip 12.3 s) | 65.9 | 40.8 | **46.9** |

- **What changed after the first run:**
  - *Long clips were cut short.* Whisper has no merges for Odia script, so each letter costs three byte-level tokens,
    about 37 tokens a second of speech. A 30-second window can need more than Whisper's 448-token output, and 5 of 25
    transcripts stopped mid-sentence. Recordings are now cut at the quietest point between 6 and 10 seconds.
  - *Language token.* Whisper has no Odia token. The model's own detection picked Pashto's (`<|ps|>`) on these clips,
    so that token is now given, rather than detected each time, where noise could pick another.
  - *Odia number words with a vowel sign slipped.* Two flags were the checker's fault: IndicWhisper wrote 41 as
    ଏକଚାଳଶ and 70 as ସତୋରୀ, where the number table has ଏକଚାଳିସି and ସତୁରି. A long word whose consonants match a
    number word and which differs by one vowel sign is now read as that number. Checked on all 594 distinct words in
    these transcripts: the three real numbers match, no other word does (two vowel signs, as in ବିସ୍ତାର "expanse"
    against ବାସ୍ତରି 72, is not accepted). The first-run figures above are re-scored with this fix.
- **The 3 flags that remain** are the three clips IndicConformer itself got most wrong (its word error 67 %, 44 % and
  40 %). On one of them, IndicWhisper was nearer the human transcript. No flag is a number or symptom misread by the
  checker.
- **Speed and memory.** About 3.8 seconds per second of speech: too slow to keep the patient waiting, so the check
  runs after the reply and the kiosk adds it when ready. 8-bit is faster than fp32 but saves little memory here:
  peak 4.9 GB while loading; at rest Windows trims it to about 1–2.5 GB.
- **Not used:** CTranslate2 (the faster-whisper engine) ran 3x faster, but the converted Odia model gave out after
  about 220 tokens (6 s of Odia speech), with a word error rate of 58 %.
- Per clip: `docs/evaluation/asr_or_fleurs_dev25_indicwhisper_int8.json` (first runs: `…_int8_first_run.json`,
  `…_fp32_first_run.json`). Reproduce: `python backend/scripts/eval_asr_second.py models/eval/fleurs_or or
  docs/evaluation/asr_or_fleurs_dev25_ctc_int8.json indicwhisper` (`JEEVIA_ASR_SECOND_INT8=false` for fp32).

**Limits**
- Odia only so far; each other language is a separate 1.4–4.3 GB download.
- Its word error rate is higher than both other engines'. It is a check that asks the patient, not a replacement: the
  transcript the patient confirms is still IndicConformer's unless they choose the other.

## Translation — Indic → English

- **Engine:** IndicTrans2 distilled 200M (AI4Bharat, MIT), on CPU. A sentence takes about 1–2 s once the model is warm.
- **Spot checks** (4 Oct; our sentences, not a benchmark):

| Patient said | English produced | |
|---|---|---|
| ମୋର ଚାରି ଦିନ ହେଲା ଜ୍ୱର ହେଉଛି ଓ ମୁଣ୍ଡ ବିନ୍ଧୁଛି | I've had a fever and a headache for four days. | correct |
| ଛାତିରେ ଯନ୍ତ୍ରଣା ବାମ ହାତକୁ ଯାଉଛି | Chest pain goes to the left arm | correct |
| मुझे तीन दिन से सीने में दर्द है और सांस फूल रही है | I have had chest pain and shortness of breath for three days. | correct |
| ପିଲାଟି ଦୁଇ ଦିନ ହେଲା ଖାଉନି ଓ ବହୁତ ଝାଡ଼ା ହେଉଛି | The child has not eaten for two days and is **sweating** a lot. | **wrong**: ଝାଡ଼ା means loose stools |

- Elsewhere, in the speech test set, ଛପନ (56) was rendered as "six".

**Because machine translation can be wrong in clinically important ways:**
- The triage rules read the patient's **original-language words** as well as the English. The Odia/Hindi phrase lists still catch ଝାଡ଼ା as diarrhoea. This is covered by a regression test in `backend/tests/test_language.py`.
- Every note with translated history carries an `MT-CHECK` flag. It names the engine and tells the reviewer to check the English against the patient's own words, which are shown alongside it.

**8-bit translation was tried and rejected (5 Oct).** PyTorch dynamic int8 quantisation of IndicTrans2's
linear layers changed "ମୋ ପେଟ ବହୁତ ଯନ୍ତ୍ରଣା କରୁଛି ଓ ବାନ୍ତି ହେଉଛି" from "…and I vomit" (fp32, correct) to "…and I have
**nausea**" — a different symptom — and did not lower memory when applied at load time (2.24 GB vs 1.30 GB for
Indic → English). Translation stays fp32. To save memory, only Indic → English is loaded at start-up;
English → Indic loads when first used.

## Non-diagnostic output guard

Every sentence the summary model writes is checked against a pattern list before it can reach a note
(`backend/app/output_guard.yaml`, `output_guard.py`). The list has three categories: condition names, diagnostic
phrasing, and medicine/dose/treatment advice. Each is covered in English, Hindi (Devanagari and romanised) and Odia.
A phrase is allowed only if the same words are already in the data the model was given. So "Known diabetes" can be
repeated from a chronic check-in, but "likely dengue" cannot be added.

| Set (5 Oct) | Size | Result |
|---|---|---|
| Red-team outputs that must be blocked | 101 | **101 blocked (100 %)** |
| Faithful note sentences that must pass | 40 | **40 passed (0 false blocks)** |

- The red-team set includes evasion attempts:
  - misspellings ("maleria", "dengu", "tyfoid");
  - upper case, full-width letters, zero-width characters and extra spaces;
  - abbreviations ("Dx", "TB", "Koch's", "BD", "SOS").
- It also covers advice that names no drug ("needs antibiotics", "recommend surgery") and claims the source never made.
- Reproduce: `pytest backend/tests/test_output_guard.py` (data: `backend/tests/data/redteam_outputs.yaml`).

**Limits**
- We wrote both sets and the pattern list, so 100 % shows the listed patterns are covered. It does not show that every
  possible phrasing is caught.
- The real test is the model's own output on new cases (next section). Every block is logged with the phrase that
  triggered it, so the list can grow.

## Note summary model (B5)

The rules engine sets urgency and the template note holds every fact. A small local model only rewrites the facts
as a readable paragraph. Its text is used only if it passes two checks; otherwise the reviewer sees the template:
- **Faithfulness:** every number (digits or words), unit and medicine must be in the facts, and every symptom it
  states or denies must agree with the rules engine's findings.
- **The output guard** (above).

- **Engine:** Qwen3-4B-Instruct-2507 (Alibaba Qwen, Apache-2.0), Q4_K_M GGUF quantised by Unsloth (SHA-256
  `3605803b…c67e597`, checked against Hugging Face). Served by llama.cpp b11424 (CUDA 12.4) on the demo laptop's
  RTX 3050 (4 GB), all layers on the GPU (3.1 GB VRAM). Offline.
- **Data:** synthetic intakes we wrote (`backend/tests/data/llm_eval_cases.yaml`), run through the real rules engine
  and note builder. No patient data.

| Set (5 Oct) | Cases | Model text used | Fell back to template | Median time |
|---|---|---|---|---|
| Tuning, first prompt | 30 | 19 (63 %) | 11 | 2.2 s |
| Tuning, final prompt | 30 | **30 (100 %)** | 0 | 0.87 s |
| **Held out**, final prompt | 20 | **18 (90 %)** | 2 | 0.82 s |

**What changed between the first and final prompt (found by reading the rejected texts)**
- The first prompt gave the model the fired rules and the missing list. Rule text names several conditions at once
  ("altered mental status or agitation, fever or hypothermia, headache, or stiff neck"), and the model restated it
  as if the patient had them all. The faithfulness check rejected these correctly. The final fact sheet holds the
  patient's account and the measured values only; rules and missing items have their own sections on the note.
- The model invented "the patient denies chest pain" once, probably copying an example in our own prompt. The check
  rejected it, and the example was removed.
- **A rules-engine bug was found this way:** "works in a stone-crushing unit" fired the *crush injury* trauma rules.
  The lexicon now needs injury wording ("crushed", "crush injury", "trapped under"); regression tests were added.

**Held-out set.** The 20 cases were written after the prompt was revised and before any output on them was seen.
- **First run:** 19 of 20 passed. Reading them showed a problem the checks cannot see: the model called general
  visits "a normal check-up", which understates an acute complaint (a 2-year-old not passing urine). The fact sheet
  now says "General visit for a new problem".
- **After that fix:** 18 of 20. Both fallbacks were the check being strict: "severity 7/10" became "pain 7/10", and
  a dog bite was called "the injury".
- Per-case texts: `docs/evaluation/llm_summary_*.json`.

**Limits**
- Fifty short synthetic cases, all in English (translation happens before the model).
- The checks catch wrong facts, not framing. Framing was checked by us reading the outputs, not by a clinician.
- Re-running the held-out set after a fix makes it less "held out". We report the first run as well.
- Reproduce: start `backend/scripts/start_llm.sh`, then
  `JEEVIA_LLM_URL=http://127.0.0.1:8031 python backend/scripts/eval_llm.py held_out`.

## Second opinion on urgency (C8)

The same model, given the same fact sheet but **not** the rules' result, names the tier it would pick (RED, YELLOW,
GREEN) and lists the facts that decided it. The opinion is shown beside the rules' result on the doctor's note and
never changes urgency. When it is more urgent than the rules, the note gets a "take a second look" flag. When it is less
urgent, it is shown and nothing else happens. Its reason goes through the faithfulness check and the output guard; a
reason that fails is hidden and the tier is still shown.

- **Reference:** the rules' tier, not a clinician's. We have no clinician labels, so this measures agreement, not
  correctness. It tells us where to look, not who is right.
- **Data:** the same 50 synthetic cases as above (tuning 30 + held out 20), run through the real rules engine.

| 5 Oct, final prompt | Result |
|---|---|
| Answers the app could read | 50 of 50 |
| Agrees with the rules | **29 of 50 (58 %)** |
| Model more urgent (flag "take a second look") | 8 |
| Model less urgent (shown only) | 13 |
| … of which the rules held YELLOW only because vitals were not yet measured | 9 |
| … of which the rules said RED | 4 |
| Reason hidden by the checks | 0 |
| Median time | 0.52 s (max 0.99 s) |

Rules (rows) against the model (columns):

| Rules ↓ / model → | RED | YELLOW | GREEN |
|---|---|---|---|
| **RED** | 10 | 3 | 1 |
| **YELLOW** | 8 | 19 | 9 |

**What the disagreements show**
- **The model is less urgent on four RED cases:** fever with headache (two cases), right lower stomach pain with
  vomiting, and a machine cut on the palm (the model said GREEN). These are cases where the rules protect: a small
  model reading the facts would have under-triaged them. This is why the opinion can never lower urgency.
- **The model is more urgent on eight YELLOW cases.** All eight were provisional: the rules were still waiting for a
  full set of vitals or the danger-sign check. Some point at rules worth reviewing with a clinician:
  - BP 182/110 with headache;
  - less baby movement at 36 weeks;
  - not passing urine;
  - hip pain after a fall with the patient unable to stand;
  - BP 170/100 with little urine and leg swelling.

  We have **not** changed the rules on the model's word. They are listed for clinician review, and the view exists to
  surface exactly this.
- **Most "less urgent" answers (9 of 13) are provisional cases**, which the rules hold at YELLOW until vitals are
  measured ("unknown is never normal"). The prompt tells the model not to choose GREEN without vitals; it did so anyway
  on several cases. A further reason the rules decide.

**Prompt change found by reading the reasons.** The first prompt asked for "one short sentence". The model then
interpreted the facts ("which indicates a possible acute neurological event requiring immediate evaluation"). In
the first 17 cases, 2 reasons were hidden by the checks ("hypertensive"; "injury" for a snake bite). The final prompt
asks only for the deciding facts, copied as written ("temperature 102.4 °F, breathing 52 /min"). All 50 reasons then
passed the checks.

**Limits**
- Agreement with our own rules, on cases we wrote, in English. Not a measure of clinical accuracy.
- The opinion runs only when the patient allowed AI (G1) and the local model is running. Otherwise the note says
  there is no second opinion.
- Per-case answers: `docs/evaluation/llm_opinion_all.json`. Reproduce:
  `JEEVIA_LLM_URL=http://127.0.0.1:8031 python backend/scripts/eval_llm.py opinion all`.

## Reading lab reports (B1, B9)

A photographed or scanned lab report is read by OCR, then parsed into rows (test, value, unit, reference range,
high/low). The rules use those rows, so a misread value can change urgency. The measure that matters most is the
**silent error**: a wrong value that the reviewer is *not* told to check.

- **Engines (offline):**
  - RapidOCR (PaddleOCR PP-OCR models on ONNX Runtime) reads every page.
  - docTR (db_mobilenet_v3_large + crnn_mobilenet_v3_large, via OnnxTR, Apache-2.0) reads the same page in parallel.
    The two readings are compared test by test. Where they differ, the reviewer is asked to check, and the rules use
    the reading further from normal.
- **Quality gate:** before reading, sharpness (variance of the Laplacian) and contrast are measured. After reading, a
  mean OCR confidence under 0.75 adds "Text hard to read", and no text from either engine asks for a retake.
- **Data:** synthetic Indian lab reports (`backend/scripts/make_ocr_set.py`). No real person's report is used.
  - Each report is a printed table in the usual layout, with a header (lab, patient, age/sex, dates), saved five ways:
    flat scan; phone photo (tilt, perspective, uneven light, blur, noise, JPEG); poor photo (all of that, worse);
    photocopy (black and white, speckle); thermal slip (narrow, monospaced, faded).
  - Development set: 40 reports per capture type, seed 20261006. Used to find and fix faults.
  - Held-out set: 40 reports per capture type, 303 tests each, seed 777. Generated once and never looked at while
    tuning. **The figures below are from this set.**

**Held-out set, 6 Oct: one engine against two**

| Capture | Values exactly right | Wrong and not flagged | Correct values flagged for checking | Retake asked | Seconds per page |
|---|---|---|---|---|---|
| | 1 engine → 2 | 1 engine → 2 | 1 engine → 2 | | 1 engine → 2 |
| Scan | 99.3 % → 99.3 % | 2 → **1** | 0.3 % → 4.3 % | 0 % | 8.7 → 13.0 |
| Phone photo | 99.3 % → 99.3 % | 2 → **1** | 0.0 % → 11.6 % | 0 % | 8.5 → 11.2 |
| Poor photo | 77.9 % → **85.5 %** | 3 → **1** | 11.9 % → 34.4 % | 72.5 % | 7.7 → 10.5 |
| Photocopy | 95.4 % → **98.7 %** | 2 → **0** | 2.8 % → 10.0 % | 0 % | 7.2 → 10.5 |
| Thermal slip | 98.7 % → 99.3 % | 1 → **0** | 0.7 % → 1.3 % | 0 % | 5.4 → 8.6 |

- **Silent errors fall from 10 to 3** of 1,515 printed tests. The second engine also finds tests the first missed:
  on poor photos, 84.8 % → 95.7 % of tests found, which is why more values are right.
- **The cost** is more correct values flagged: 11.6 % on phone photos and 34.4 % on poor photos. Each flag is a
  "check this value" for the reviewer; none changes a value on its own.
- No test was invented on any page (a row for a test not on the report) with one engine or two.
- Report date read: 100 % except poor photos (90 %) and thermal (97.5 %). Patient name: 87.5–100 %.
- The retake request comes on 72.5 % of poor photos and on none of the readable captures.
- The B2 checks were added on 7 Oct and this set was run again; see "Checking the numbers on a report (B2)" below.
  `ocr_heldout_two_engines.json` now holds that rerun.
- Per page: `docs/evaluation/ocr_heldout_rapidocr.json` and `ocr_heldout_two_engines.json`. Reproduce:
  `python backend/scripts/make_ocr_set.py models/eval/ocr_heldout 40 777`, then
  `python backend/scripts/eval_ocr.py models/eval/ocr_heldout docs/evaluation/ocr_heldout_two_engines.json all second`.

**Development set.** The first run, before any fix, read 96.7 % of values exactly on scans but 70.5 % on phone photos and
28.6 % on poor photos, and asked for a retake on a quarter of clean scans. It is kept as
`docs/evaluation/ocr_synth_rapidocr_first_run.json`. With the final code and one engine (7 Oct): scans 99.7 %, phone
photos 99.4 %, poor photos 84.6 %, photocopies 96.0 %, thermal slips 98.8 %; 10 wrong values not flagged; no retake
asked on any readable capture (`docs/evaluation/ocr_synth_rapidocr.json`). The held-out figures are close to these
(within 7 points on poor photos, 1 point elsewhere), so the fixes were not fitted to the development pages alone.

**Limits**
- Synthetic print in Windows fonts, with simulated capture faults. Real reports vary more in layout, logos, stamps,
  handwriting on the page and folds. Real-world error will be higher.
- Printed reports only. Handwriting is measured separately below.
- Every value read from a photo is shown as read from a photo, beside the image, for the reviewer to confirm.

## Second document-type label: the image model (B10, 8 Oct)

The text-based label (`images.doc_type`, words found by OCR) is checked by **Qwen3-VL-4B** (Q4_K_M, llama.cpp, offline
on the laptop CPU), which looks at the picture itself. When the two disagree, the reviewer sees "The image model sees
this as …, the text reading as … — check the picture". The image model never replaces the text label.

| Pictures | Count | Text label right | Image model right | Disagreed | Disagreed where the text label was wrong |
|---|---|---|---|---|---|
| Synthetic lab reports (6 each: photo, poor photo, thermal) | 18 | 17 | 18 | 1 | 1 |
| Synthetic medicine strips (clean, blurred, glare, photo, torn) | 14 | 14 | 14 | 0 | 0 |
| Public handwritten prescriptions (rx_hand, read only) | 15 | 3 | 11 | 8 | 8 |
| **All** | **47** | **34 (72 %)** | **43 (91 %)** | **9** | **9** |

- Every disagreement was a case where the text label was wrong, so no warning was a false alarm on these 47.
- Handwriting is where it helps: OCR finds few printed words on a handwritten prescription, so the text label says
  "other document" for 12 of 15; the image model recognises 11 of 15.
- Both were wrong together on 4 prescriptions ("other document"). Those get no warning; the reviewer still sees the
  picture.
- **Speed:** median 11.2 s per picture (1.6–57 s) on the laptop CPU, run after the upload reply. Off unless
  `JEEVIA_VLM_URL` is set (`backend/scripts/start_vlm.sh`).
- Per picture: `docs/evaluation/vlm_doctype.json`. Reproduce: `python backend/scripts/eval_vlm_doctype.py`.

## Table reader as a third reading: tried and left off (PP-StructureV3, 8 Oct)

PaddleOCR's table models were tried as a third reading of report rows (`app/triage/tables.py`).
- **Full PP-StructureV3** (layout model plus two RT-DETR-L cell detectors): over 15 minutes of CPU for **one page** on
  the demo laptop; stopped.
- **Light set** (no layout step, end-to-end table models, mobile OCR): 8.6 s per page, but on 40 held-out synthetic
  reports (8 per capture type) it read only **31 of 340 values exactly**; 280 were not found and 29 were wrong. Our
  reports are printed without cell borders, and the table model merges several tests into one cell
  ("Test Name Result 12.9 48.3 3,900"). Of 9 values the two OCR engines got wrong, it would have flagged 1.
- **Decision:** it stays off (`JEEVIA_TABLE_PYTHON` unset). Turned on, its 29 wrong values would put false "check the
  crop" warnings on reports the two OCR engines already read at 99.3 % (scan and photo). The two-engine reading with
  row joining by position remains the method.
- Per value: `docs/evaluation/tables_heldout.json`. Reproduce: `python backend/scripts/eval_tables.py 8`.

## Checking the numbers on a report (B2)

A value read from a report reaches the rules only after three checks. None of them changes a value; a value that
fails is marked **needs checking** with the reason, and the flag shows on the case.

- **Bounds:** every test has a possible range (haemoglobin 2–25 g/dL, platelets 1,000–2,000,000 /µL, …). A value
  outside it is a misread, not a result.
- **Units:** the printed unit is matched to the test and converted (g/L → g/dL, mmol/L → mg/dL, lakhs/cumm → /µL).
  A unit that is not used for that test is flagged. Where no unit is read, the usual one is assumed and said so; for
  counts (platelets, WBC, RBC), where per µL, thousands and lakhs differ 100-fold, a missing unit always flags.
- **Sums:** values that must agree on a correct report are checked against each other: WBC differential = 100 %,
  absolute count = % × total WBC, the absolute counts add up to the total, globulin = total protein − albumin, A/G
  ratio, indirect bilirubin = total − direct, MCHC = Hb ÷ PCV, MCV = PCV ÷ RBC, MCH = Hb ÷ RBC, VLDL = TG ÷ 5, the
  cholesterol fractions, non-HDL, the TC/HDL and LDL/HDL ratios, and urea = BUN × 2.14. The tolerance is what
  rounding of each printed digit can explain. A sum cannot say which value is wrong, so every value in a failed sum
  is flagged; where the second OCR engine's reading of one of them makes it add up, the flag says so.

**How much the sums can catch (simulation).** 2,000 synthetic reports (seed 4242), each value slipped the ways OCR
slips: a decimal point lost, a digit dropped, a look-alike digit (1/7, 3/8, 5/6, 6/8, 0/8, 4/9, 2/7, 1/4) in the first, middle or last
place. 110,801 slips; 15,454 relations on the correct reports, with **no false alarm**.

| Slip | Caught by bounds alone | Caught by bounds or sums |
|---|---|---|
| Decimal point lost | 81.2 % | **100 %** |
| Look-alike, first digit | 22.3 % | **99.9 %** |
| Look-alike, middle digit | 0.1 % | 84.8 % |
| Digit dropped | 23.9 % | 78.5 % |
| Look-alike, last digit | 0 % | 44.1 % |
| **All** | 22.6 % | **79.5 %** |

By size: a slip that moves the value by 10 % or more is caught 98.6 % of the time; 5–10 %, 81.7 %; under 5 %,
17.7 %. The slips the sums miss are mostly last-digit changes that rounding can explain, which rarely change a
high/low call. `docs/evaluation/b2_sums_simulation.json`; reproduce with
`python backend/scripts/eval_sums.py 2000 4242 docs/evaluation/b2_sums_simulation.json`.

**On read reports.** A second generator mode (`b2`) prints full panels where the sums apply: CBC with differential
and absolute counts, liver function with bilirubin fractions and proteins, lipid profile with ratios, kidney function
with BUN; and units the way Indian labs print them (lakhs/cumm, thousand/µL, mmol/L). Both engines, five capture types.

*Held-out set (seed 779, 40 reports and 685 tests per capture, never looked at while tuning):*

| Capture | Values exactly right | Units right | Wrong values | Wrong and not flagged | … without the sums | Sum false alarms | Correct values flagged | Retake asked |
|---|---|---|---|---|---|---|---|---|
| Scan | 100 % | 99.9 % | 0 | **0** | 0 | 0 | 3.1 % | 0 % |
| Phone photo | 99.6 % | 99.1 % | 3 | **0** | 0 | 0 | 15.0 % | 0 % |
| Poor photo | 82.0 % | 84.8 % | 97 | **0** | 4 | 0 | 53.4 % | 47.5 % |
| Photocopy | 98.5 % | 97.7 % | 9 | **0** | 0 | 0 | 12.3 % | 0 % |
| Thermal slip | 97.7 % | 96.1 % | 16 | **0** | 1 | 0 | 12.4 % | 0 % |

- **No silent error in 3,425 printed tests.** Without the sums there would have been five; the sums caught them.
- No sum failed on a correctly read report (0 false alarms in 1,445 relations checked).
- The cost is on poor photos: half of the correct values there carry a "check" (47.0 % without the sums). Those are
  the photos where a retake is asked for anyway.

*Development set (seed 20261007, same sizes):* values exactly right 99.8 / 99.1 / 84.1 / 98.5 / 97.5 % (scan, photo,
poor photo, photocopy, thermal); 0 silent errors on every capture (6 without the sums); 0 sum false alarms; no
invented rows. `docs/evaluation/ocr_b2_dev_two_engines.json`.

**Faults found and fixed on these sets**
- *Units misread in ways that have only one reading* ("X10~3/µL" for x10^3/µL, "mmo1/L" for mmol/L): mended before
  the unit is matched. Units right on the development set: scan 97.5 → 100 %, photo 97.4 → 99.7 %, poor photo
  87.0 → 88.1 %, photocopy 98.3 → 98.8 %, thermal 90.7 → 95.5 %. Values unchanged.
- *A unit printed in the range column:* "Platelets | 4.87 | lakhs/cumm 1.50 – 4.50". The unit was not seen with the
  value, so 4.87 was taken as thousands: 4,870 /µL, critically low, against a true 487,000, which is high, and
  it was not flagged. Found on the old held-out set (scan r003). Now the unit is taken from the range cell when it
  leads it, and a count with no unit read always flags. Both are covered by tests (`test_lab_checks.py`).
- *Tried and reverted:* straightening tilted photos before reading. It lowered exact values on phone photos from
  99.1 % to 97.4 %, so it was taken out.

**Old held-out set, rerun with the B2 checks (7 Oct).** Values exactly right: scan 99.7 %, photo 99.7 %, poor
photo 85.8 %, photocopy 98.7 %, thermal 99.3 %. One silent error remains, on a poor photo: an LDL of 73 read as 130
by **both** engines, in a lipid panel without VLDL or ratios, so no sum covers it. The sums report 4–5 failures per
capture on this set that are not misreads: the older generator printed haemoglobin and PCV pairs that no blood can
have (an MCHC outside 22–40). The `b2` generator fixed that, and the false alarms go to 0 there.
`docs/evaluation/ocr_heldout_two_engines.json`.

**Limits**
- Synthetic reports and simulated capture faults; real reports have more layouts, stamps and handwriting.
- The sums only cover panels that print related values. A single glucose or a lone LDL is checked only by bounds,
  the unit, the lab's own High/Low mark and the second engine.
- A misread both engines agree on, inside the possible range and outside any sum, is not caught (the LDL above). The
  value is still shown beside the image crop it came from, for the reviewer to confirm.

Reproduce: `python backend/scripts/make_ocr_set.py models/eval/ocr_b2_heldout 40 779 b2`, then
`python backend/scripts/eval_ocr.py models/eval/ocr_b2_heldout docs/evaluation/ocr_b2_heldout_two_engines.json all second`
(development set: `models/eval/ocr_b2 40 20261007 b2`).
### Unit errors (8 Oct)

The digit and decimal slips above leave the unit alone. `backend/scripts/eval_units.py` breaks the unit instead, one
printed row at a time, on 500 synthetic B2 reports (seed 5151), and parses the report again. *Caught* means the row
is now marked for checking; *silent* means the value the rules see moved by more than 5 % and nothing marked it.

| Break | Rows | Caught | Silent |
|---|---|---|---|
| Wrong unit read (another test's unit: g/dL for mg/dL, U/L for %, …) | 8,140 | **97.9 %** | 0 % |
| Value printed in SI (mmol/L, µmol/L), unit read as mg/dL | 3,728 | **98.5 %** | 1.5 % (57) |
| Value in mg/dL, unit read as SI | 82 | **97.6 %** | 2.4 % (2) |
| Unit lost | 8,140 | 19.3 % | 0 % |

- **No false alarm:** none of the 8,740 correct rows was marked.
- **Unit lost:** in the other 80.7 % the unit assumed was the right one, so the value is unchanged; a note still says
  "No unit read — mg/dL assumed". Counts without a unit (a 100-fold question) are always marked.
- **Wrong unit, not caught:** 61 rows kept the right value (a unit the test also uses) and 111 were read as the
  absolute count instead of the percentage (a count unit beside a differential); the differential sum then fails.
- **Silent:** the 59 are SI values whose number happens to sit inside the mg/dL range and whose printed range was not
  read as SI. The bounds and the range check cannot see these; the reviewer still sees the image crop.

Reproduce: `python backend/scripts/eval_units.py 500 5151 docs/evaluation/unit_errors.json`.

## Handwritten prescriptions (B1, B10)

The patient photographs a doctor's prescription. The app names the medicines on it, each matched to the Jan Aushadhi
generic list or the A-Z Medicine Dataset of India (186,094 brands, CC BY-SA 4.0). Every name is shown for the nurse to
confirm against the paper.

- **Data:** "100 handwritten medical records" (chaithanyakota, Hugging Face, CC BY-ND 4.0): photographed Indian
  outpatient prescriptions, each listing the medicines written on it. 85 pages list medicines.
  - Development: rx000–rx049 (40 pages, 169 medicines). Used to tune the matcher.
  - Test: rx050–rx099 (45 pages, 160 medicines). Not looked at while tuning. **Headline figures are from these.**
  - Used for measurement only. The images are not copied into the repo or changed.
- **Measures, per prescribed medicine:**
  - *read:* its name is in the engine's text, allowing small slips;
  - *named:* the app's medicine list for the page contains it.
- **Measures, per name the app gives:**
  - *right:* it was prescribed, or it is a generic that a prescribed brand contains;
  - *precision:* right names as a share of all names given.

**Test pages, 6 Oct**

| Engine | Medicines read | Medicines named | Names given | Wrong | Precision | Seconds per page |
|---|---|---|---|---|---|---|
| RapidOCR (offline) | 17.5 % | 0.6 % | 4 | 3 | 25 % | 12.7 |
| docTR (offline) | 25.6 % | 4.4 % | 11 | 4 | 64 % | 2.9 |
| Sarvam Vision (online) | **60.0 %** | **28.8 %** | 80 | 33 | 59 % | 6.7 |

Development pages: RapidOCR named 5.9 % (precision 70 %), docTR 11.8 % (65 %), Sarvam 34.3 % (63 %).

- **The offline engines cannot read handwriting** well enough to rely on: docTR finds about a quarter of the names.
  Online reading (Sarvam Vision) is offered only when the patient allowed AI help. It read every page (0 failures,
  about ₹0.50 a page).
- **Matcher changes made on the development pages:** brands are taken only where a medicine's name goes on an order
  line; a brand must be confirmed by a strength, a dose pattern or a form word; between equally close names, the brand
  with more products wins; and generics printed under a brand are folded into it.
  - Scored the old way (no credit for a generic inside a prescribed brand), docTR on the test pages went from 18 names
    given (11 wrong, precision 39 %) to 11 (4 wrong, 64 %). So the gain is from the matcher, not the scoring.
- **Why a name is missed:**
  - the engine did not read it, which is most misses;
  - the brand is not in the A-Z list. Common supplements are absent: Shelcal, Zincovit, Pegura, Enterogermina,
    Supracal, Bevon, Threptin, Fefol.
- **Why a wrong name is given:**
  - a real generic printed on the page but not in the record's medicine list (terbutaline, menthol, budesonide);
  - a close but wrong brand (Montana, Protocid, Telinam).
  - One is a safety example: "Lorazep" (most likely Lonazep, clonazepam) was matched to Lorazepam. This is why every
    list is labelled "Read from a photo and matched to the Jan Aushadhi generic list or a list of Indian brands —
    confirm each one against the strip or prescription".
- Per page: `docs/evaluation/handwriting_rx100.json`. Reproduce:
  `python backend/scripts/eval_handwriting.py models/eval/rx_hand rapidocr,doctr,sarvam` (Sarvam readings are cached in
  the set folder, so a re-run costs nothing).

**Limits**
- 85 pages from one public set, from a limited number of clinics. Precision near 60 % means about 4 in 10 names
  given are wrong. The names are suggestions for the nurse to check against the paper.

## Speed (H7, 8 Oct)

Measured through the app itself (FastAPI test client, every check and the database included) on the demo laptop: Dell
G15, i5-12500H, 16 GB RAM. Speech and report reading run on the CPU; the summary model (Qwen3-4B) runs on the laptop GPU.
Odia voice: 10 public FLEURS dev clips (CC-BY). Reports: 16 synthetic report images (scans and phone photos).

| Step | Median | Slowest 10 % | Target | Under target |
|---|---|---|---|---|
| Typed complaint → triage note and urgency, English | 0.08 s | 0.11 s | 3 s | 12 of 12 |
| Typed complaint → triage note and urgency, Odia | 0.08 s | 0.09 s | 3 s | 12 of 12 |
| Intake → model-written summary on the note (background) | 1.8 s | 15.5 s | 15 s (ours) | 7 of 8 |
| Odia voice → Odia text (clips of 10–18 s, median 13 s) | 3.4 s | 4.1 s | 2 s | 0 of 10 |
| Odia voice → Odia text and English | 9.7 s | 13.3 s | 2 s | 0 of 10 |
| Report photo → findings | 14.8 s | 18.0 s | 15 s | 9 of 16 |
| Queue screen | 0.05 s | 1.09 s | 1 s | 9 of 10 |

- **Met:**
  - Text to note: the rules note and urgency are ready in well under a second.
  - The queue: one load of 10 took 1.09 s, while the summary model was still busy.
  - The model summary arrives later and replaces the template text only if it passes the checks. One of the 8 failed
    the faithfulness check and kept the template note.
- **Not met:**
  - **Voice:** speech is about a quarter of real time. A typical kiosk answer of 5–8 s is transcribed in about 1.5–2 s,
    but these 13 s clips take 3.4 s. Adding English roughly triples that, because translation runs after recognition.
  - **Reports:** the median is just under 15 s, but phone photos (de-skewing and a second reading pass) run to 18–20 s.
- Results: `docs/evaluation/latency.json`. Reproduce: `JEEVIA_LLM_URL=http://127.0.0.1:8031 python
  backend/scripts/eval_latency.py <odia clips> models/eval/ocr_synth docs/evaluation/latency.json`. The script reads no
  `.env`, so it never calls Sarvam, Twilio or Vonage.

## Photo of the problem, described live (8 Oct)

The local image model (Qwen3-VL-4B, CPU) describes a photo the patient adds (a rash, a cut, a swelling) for the
reviewer. The description never reaches the rules and never changes urgency. Tested on 3 synthetic drawings.

- **First run:** 2 of 3 were blocked by the guard, both for "likely" (the model guessing). The one kept said "appearing
  to be … a lesion", a hedge the guard had missed.
- **Fixes:**
  - The prompt now tells the model to say plainly what it sees, without likely, probably, appears or seems.
  - The guard also catches "appearing to be" and "seems". A test covers both.
- **After the fixes:** 3 of 3 kept, 0 blocked, median 11 s. Example: "A red, circular patch is visible on a light brown
  skin surface. The patch is roughly the size of a small coin and has a slightly raised, defined edge."
- **One stall:** one request hung in the image server for 5 minutes and returned nothing. The app treats that as "no
  description" and the intake is not held up. A rerun took 11 s.
- **Limits:** these are drawings, not real photos, so they show that the wording is safe, not that the descriptions are
  accurate.
- Results: `docs/evaluation/vlm_photo.json`. Reproduce: `python backend/scripts/eval_vlm_photo.py <folder of photos>`.
