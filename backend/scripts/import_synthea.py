"""Longitudinal histories from Synthea, re-cast with Indian demographics (TODO section 9), for PHC Manikpur's demo.

Synthea (Apache-2.0, github.com/synthetichealth/synthea) simulates whole lives: visits, conditions and vital signs
over years. Its disease model is the US one; we keep that clinical course (the spacing of visits, how blood pressure
and glucose drift, when hypertension or diabetes is diagnosed) and replace every US detail with synthetic Indian ones:
names from a fixed list, the age on 8 Oct 2026, a village near the facility, Hindi as the language (PHC Manikpur, Uttar
Pradesh). Names, addresses, SSNs and US places never leave this script.

Kept: living adults with essential hypertension, type 2 diabetes or asthma in Synthea, then others without, up to 12.
For each, the last six outpatient visits that have a blood-pressure reading, shifted so the latest is 30 to 120 days
before 8 Oct 2026; vitals as Synthea recorded them (BP, pulse, respiration, temperature, SpO2, glucose).

Run from backend/ after Synthea has written its CSVs:
    java -jar synthea-with-dependencies.jar -p 60 -s 1008 -cs 1008 --exporter.csv.export=true \
        --exporter.fhir.export=false --exporter.years_of_history=10 --exporter.baseDirectory=./out
    python scripts/import_synthea.py ../models/synthea/out/csv   (writes app/synthea_histories.json)
"""

import csv
import json
import random
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

TODAY = date(2026, 10, 8)
OUT = Path(__file__).resolve().parents[1] / "app" / "synthea_histories.json"
CHRONIC = {"59621000": "high blood pressure", "44054006": "diabetes", "195967001": "asthma"}
VITALS = {"8480-6": "bp_systolic", "8462-4": "bp_diastolic", "8867-4": "pulse", "9279-1": "resp_rate", "8310-5": "temp_c",
          "2708-6": "spo2", "59408-5": "spo2", "2339-0": "glucose"}
MEN = ["Ramesh", "Suresh", "Mahesh", "Rajendra", "Shiv Kumar", "Ram Kishore", "Om Prakash", "Dinesh", "Vijay", "Santosh", "Rakesh", "Ashok"]
WOMEN = ["Sunita", "Geeta", "Kamla", "Savitri", "Pushpa", "Meena", "Rekha", "Asha", "Usha", "Shanti", "Kiran", "Lakshmi"]
SURNAMES = ["Yadav", "Patel", "Kushwaha", "Verma", "Prajapati", "Nishad", "Pal", "Maurya", "Kol", "Tiwari", "Shukla", "Gupta"]
VILLAGES = ["Rampur", "Devipur", "Lalapur", "Kalyanpur", "Bargarh", "Sitapur Khurd", "Nayagaon", "Bhaironpur"]
MAX_PEOPLE, MAX_VISITS = 12, 6


def rows(folder: Path, name: str):
    with open(folder / f"{name}.csv", encoding="utf-8") as f:
        yield from csv.DictReader(f)


def main(folder: str) -> None:
    root, rng = Path(folder), random.Random(1008)
    people = {p["Id"]: p for p in rows(root, "patients") if not p["DEATHDATE"]}
    conds = defaultdict(set)
    for c in rows(root, "conditions"):
        if c["CODE"] in CHRONIC and c["PATIENT"] in people and not c["STOP"]:
            conds[c["PATIENT"]].add(CHRONIC[c["CODE"]])
    visits = {e["Id"]: e for e in rows(root, "encounters") if e["ENCOUNTERCLASS"] in ("ambulatory", "wellness", "outpatient")}
    vitals = defaultdict(dict)
    for o in rows(root, "observations"):
        if o["ENCOUNTER"] in visits and o["CODE"] in VITALS and o["VALUE"]:
            vitals[o["ENCOUNTER"]][VITALS[o["CODE"]]] = round(float(o["VALUE"]), 1)
    for v in vitals.values():  # the app records temperature in Fahrenheit, as Indian thermometers read
        if "temp_c" in v:
            v["temp_f"] = round(v.pop("temp_c") * 9 / 5 + 32, 1)
    by_person = defaultdict(list)
    for eid, v in vitals.items():
        if "bp_systolic" in v:
            by_person[visits[eid]["PATIENT"]].append((visits[eid]["START"][:10], v))

    def age(p):
        b = date.fromisoformat(p["BIRTHDATE"])
        return TODAY.year - b.year - ((TODAY.month, TODAY.day) < (b.month, b.day))

    adults = [pid for pid in people if age(people[pid]) >= 18 and len(by_person[pid]) >= 3]
    chronic = sorted((pid for pid in adults if conds[pid]), key=lambda pid: ("diabetes" not in conds[pid], "asthma" not in conds[pid], pid))
    other = sorted(pid for pid in adults if not conds[pid])
    rng.shuffle(other)
    out, used = [], set()
    for i, pid in enumerate((chronic + other)[:MAX_PEOPLE]):
        p = people[pid]
        sex = "F" if p["GENDER"] == "F" else "M"
        while (name := f"{rng.choice(WOMEN if sex == 'F' else MEN)} {rng.choice(SURNAMES)}") in used:
            pass
        used.add(name)
        hist = sorted(by_person[pid], key=lambda h: h[0])[-MAX_VISITS:]
        shift = TODAY - timedelta(days=rng.randint(30, 120)) - date.fromisoformat(hist[-1][0])
        reason = ", ".join(sorted(conds[pid]))
        out.append({
            "code": f"SYN-{i + 1:03d}", "name": name, "age": age(p), "sex": sex, "language": "hi", "village": rng.choice(VILLAGES),
            "conditions": sorted(conds[pid]),
            "visits": [{"date": (date.fromisoformat(d) + shift).isoformat(), "chief_complaint": f"Follow-up for {reason}" if reason else "Routine check-up",
                        "vitals": v} for d, v in hist],
        })
    meta = {"source": "Synthea (Apache-2.0), seed 1008, population 60; US clinical course, synthetic Indian demographics",
            "people": len(out), "visits": sum(len(x["visits"]) for x in out)}
    OUT.write_text(json.dumps({"meta": meta, "people": out}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(meta), *(f"{x['code']} {x['name']} {x['age']}{x['sex']} {x['conditions']} {len(x['visits'])} visits" for x in out), sep="\n")


if __name__ == "__main__":
    main(sys.argv[1])
