"""Build the generic-medicine name list used to read medicine strips and prescriptions (B10).

Source: "The list of 2110 generic medicines under PMBJP till 31.12.2025", annexure to a Press Information Bureau
release (Release ID 2224371, Feb 2026), Government of India:
https://static.pib.gov.in/WriteReadData/specificdocs/documents/2026/feb/doc202626781701.pdf
PIB copyright policy: material may be reproduced free of charge without prior approval, accurately and with the
source acknowledged (https://www.pib.gov.in/content/102_2_Copyright-Policy.aspx).

Each product row ("Diclofenac Sodium 50mg and Paracetamol 325mg Tablets IP") is reduced to its ingredient names
("diclofenac sodium", "paracetamol"). Output: backend/app/triage/data/medicines_pmbjp.txt, one name per line.

    python backend/scripts/build_medicine_list.py models/reference/pmbjp_2110_generics_2025-12-31.pdf
"""

import re
import sys
from pathlib import Path

import pypdfium2

OUT = Path(__file__).resolve().parents[1] / "app" / "triage" / "data" / "medicines_pmbjp.txt"
# Words that describe the form, standard or release, not the medicine.
FORM = re.compile(
    r"\b(tablets?|tabs?|capsules?|caps?|injections?|inj|infusion|syrup|suspension|oral|drops?|eye|ear|nasal|spray|gel|cream|ointment|lotion|"
    r"solution|powder|granules|sachets?|inhaler|rotacaps?|respules?|dispersible|chewable|effervescent|gastro[- ]?resistant|enteric|coated|film|"
    r"prolonged|extended|sustained|modified|controlled|delayed|release|er|sr|xr|cr|mr|dr|ip|bp|usp|for|with|in|of|per|w/w|w/v|v/v|paediatric|"
    r"pediatric|adult|kit|vial|ampoule|bottle|pre-?filled|syringe|pen|cartridge|mouthwash|gargle|shampoo|soap|dusting|vaginal|pessary|"
    r"suppositor(y|ies)|topical|transdermal|patch|lozenges?|plain|forte|ds|hcl|hydrochloride|plus|combo|combipack|combikit|combi|tablet|"
    r"equivalent|to|as|eq|orally|disintegrating|strips?|intravenouse?|new|improved|sugar[- ]free|flavou?red)\b",
    re.I,
)
ROW = re.compile(r"^\s*(\d+)\s+(\d+)\s+(.*)$")


def ingredients(name: str) -> list[str]:
    name = re.sub(r"\([^)]*\)", " ", name)  # "(Diclofenac Diethylamine)", "(40Mg)"
    out = []
    for part in re.split(r"\s+and\s+|\+|,|/|&| with ", name, flags=re.I):
        part = re.split(r"\d", part, maxsplit=1)[0]  # stop at the first strength
        part = FORM.sub(" ", part)
        part = re.sub(r"[^A-Za-z\- ]", " ", part)
        words = [w for w in part.lower().split() if len(w) > 2]
        if words:
            n = " ".join(words[:3])
            if len(n) >= 4:
                out.append(n)
    return out


def main(pdf: str) -> None:
    doc = pypdfium2.PdfDocument(pdf)
    text = "\n".join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))
    rows, cur = [], None
    for line in text.splitlines():
        if m := ROW.match(line):
            if cur:
                rows.append(cur)
            cur = m.group(3)
        elif cur and line.strip() and not line.startswith(("S. No", "Code", "Generic Name", "This information", "***", "(Release")):
            cur += " " + line.strip()
    if cur:
        rows.append(cur)
    names: set[str] = set()
    for r in rows:
        r = re.sub(r"\s+\d+\s*('s|s|ml|g|gm|kg|l|tablets?|capsules?|no\.?|nos|vials?|pcs?)\s*$", "", r.strip(), flags=re.I)
        if not re.match(r"jan ?aushadhi", r, re.I):  # own-brand consumables and nutraceuticals, not medicines
            names.update(ingredients(r))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    header = (
        "# Generic medicine names from the PMBJP list of 2110 generic medicines (to 31.12.2025),\n"
        "# Press Information Bureau, Government of India, Release ID 2224371. Reproduced under the PIB copyright policy\n"
        "# (free reproduction with source acknowledged). Built by backend/scripts/build_medicine_list.py.\n"
    )
    OUT.write_text(header + "\n".join(sorted(names)) + "\n", encoding="utf-8")
    print(f"{len(rows)} products → {len(names)} names → {OUT}")


if __name__ == "__main__":
    main(sys.argv[1])
