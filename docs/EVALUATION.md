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
