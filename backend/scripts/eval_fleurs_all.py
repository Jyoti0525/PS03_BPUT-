"""Speech recognition and translation for every Indian language in FLEURS (Google, CC-BY-4.0), 25 dev clips each.

For each language: fetch the clips, measure WER / CER (eval_asr.py), then score the English translation of what was
heard against FLEURS's own English sentence with the same id (chrF++ and BLEU, sacrebleu). The audio and the
downloaded archive are deleted afterwards (the disk is small); only results.json is kept.

    python backend/scripts/eval_fleurs_all.py as bn gu ml mr ne pa sd ta te ur
"""

import csv
import json
import sys
from pathlib import Path

from huggingface_hub import hf_hub_download, scan_cache_dir
from sacrebleu.metrics import BLEU, CHRF

sys.path.insert(0, str(Path(__file__).resolve().parent))
import eval_asr  # noqa: E402
import fetch_fleurs  # noqa: E402

EVAL = Path(__file__).resolve().parents[2] / "models" / "eval"
CONFIG = {"as": "as_in", "bn": "bn_in", "gu": "gu_in", "hi": "hi_in", "kn": "kn_in", "ml": "ml_in", "mr": "mr_in",
          "ne": "ne_np", "or": "or_in", "pa": "pa_in", "sd": "sd_in", "ta": "ta_in", "te": "te_in", "ur": "ur_pk"}


def english_refs() -> dict[str, str]:
    tsv = Path(hf_hub_download("google/fleurs", "data/en_us/dev.tsv", repo_type="dataset"))
    with open(tsv, encoding="utf-8") as f:
        return {r[0]: r[2] for r in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)}


def translation_score(folder: Path, en: dict[str, str]) -> dict:
    ids = {}
    with open(folder / "dev.tsv", encoding="utf-8") as f:
        for r in csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE):
            ids[r[1]] = r[0]
    res = json.loads((folder / "results.json").read_text(encoding="utf-8"))
    pairs = [(c["english"], en[ids[c["file"]]]) for c in res["clips"] if ids.get(c["file"]) in en and c.get("english")]
    for c in res["clips"]:
        c["english_reference"] = en.get(ids.get(c["file"], ""))
    hyp, ref = [p[0] for p in pairs], [[p[1] for p in pairs]]
    res["summary"]["translation"] = {
        "engine": "IndicTrans2 indic-en 200M (offline), on the speech transcript", "sentences": len(pairs),
        "chrf++": round(CHRF(word_order=2).corpus_score(hyp, ref).score, 1) if pairs else None,
        "bleu": round(BLEU().corpus_score(hyp, ref).score, 1) if pairs else None,
    }
    (folder / "results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res["summary"]


def drop_audio(folder: Path, config: str) -> None:
    for w in folder.glob("*.wav"):
        w.unlink()
    for repo in scan_cache_dir().repos:
        if repo.repo_id == "google/fleurs":
            for rev in repo.revisions:
                for f in rev.files:
                    if f"{config}/audio" in str(f.file_path).replace("\\", "/"):
                        for path in (f.file_path, f.blob_path):  # without symlinks (Windows) both are full copies
                            path.unlink(missing_ok=True)


def main(langs: list[str]) -> None:
    en = english_refs()
    for lang in langs:
        folder = EVAL / f"fleurs_{lang}"
        if not (folder / "results.json").exists():
            fetch_fleurs.main(CONFIG[lang], str(folder), 25)
            eval_asr.main(str(folder), lang)
        s = translation_score(folder, en)
        print(lang, json.dumps({k: s[k] for k in ("wer", "cer", "real_time_factor", "translation")}), flush=True)
        drop_audio(folder, CONFIG[lang])


if __name__ == "__main__":
    main(sys.argv[1:])
