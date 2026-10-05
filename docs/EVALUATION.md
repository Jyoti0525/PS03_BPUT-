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
