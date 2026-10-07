"""Build the Indian medicine brand list used to read prescriptions (B10, handwriting): brand → what it contains.

Prescriptions in India name brands ("Tab Dolo 650", "Montair FX"), not generics, so the PMBJP generic list alone finds
almost nothing on them. Source: "A-Z Medicine Dataset of India" (Shudhanshu Singh, Kaggle, CC BY-SA 4.0; prices and
availability as of Nov 2022), https://www.kaggle.com/datasets/shudhanshusingh/az-medicine-dataset-of-india.
The derived file is therefore CC BY-SA 4.0 too, with this attribution (docs/FEATURES.md, data sources).

Each product name is cut at its first strength or dosage form ("Montair FX Tablet" → "montair fx", "Dolo 650 Tablet"
→ "dolo"). Output: backend/app/triage/data/medicine_brands.tsv.gz, one brand per line:
    brand<TAB>display name<TAB>contains (one composition, or up to three joined by " | " when the brand has several)

    python backend/scripts/build_brand_list.py models/reference/az_medicine/az.zip
"""

import collections
import csv
import gzip
import io
import re
import sys
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "app" / "triage" / "data" / "medicine_brands.tsv.gz"
FORMS = re.compile(
    r"^(tablets?|capsules?|syrup|suspension|injection|infusion|drops?|cream|gel|ointment|lotion|solution|liquid|powder|"
    r"granules|sachet|inhaler|rotacaps?|respules?|transcaps|gargle|mouthwash|spray|shampoo|soap|kit|vial|softgel|lozenges?|"
    r"paediatric|pediatric|oral|nasal|eye|ear|eye/ear|dt|md|sr|er|xr|cr|mr|od|ds|forte|plus|kid|junior|dry|"
    r"strip|pack|bottle|tube|sugar|free|chewable|dispersible|effervescent|redimix|redicaps|penfill|flexpen|cartridge)$", re.I)


def brand(name: str) -> str | None:
    words = []
    for w in re.split(r"[\s\-]+", name.strip()):
        if not w or re.search(r"\d", w) or FORMS.match(w) or "%" in w or "(" in w:
            break
        words.append(w.lower())
    return " ".join(words) if words and len(words[0]) >= 3 else None


def composition(row: dict) -> str:
    parts = [re.sub(r"\s+", " ", row[k]).strip() for k in ("short_composition1", "short_composition2") if row.get(k, "").strip()]
    return " + ".join(parts)


def main(src: Path) -> None:
    z = zipfile.ZipFile(src)
    rows = csv.DictReader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8"))
    comps: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    shown: dict[str, str] = {}
    for r in rows:
        if r.get("type", "allopathy") != "allopathy":
            continue
        b = brand(r["name"])
        c = composition(r)
        if not b or not c:
            continue
        weight = 1 if r.get("Is_discontinued", "").upper() == "TRUE" else 3  # products still sold count more
        for key in {b, b.split()[0]}:  # "montair fx" and "montair"
            comps[key][c] += weight
            if key not in shown or len(r["name"]) < len(shown[key]):
                shown[key] = r["name"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT, "wt", encoding="utf-8") as f:
        f.write("# brand\tshortest product name\tcontains — from the A-Z Medicine Dataset of India (Kaggle, CC BY-SA 4.0)\n")
        for key in sorted(comps):
            top = [c for c, _ in comps[key].most_common(3)]
            f.write("\t".join(re.sub(r"\s+", " ", x).strip() for x in (key, shown[key], " | ".join(top))) + "\n")  # names hold tabs
    print(f"{len(comps)} brands -> {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main(Path(sys.argv[1] if len(sys.argv) > 1 else "models/reference/az_medicine/az.zip"))
