"""Fetch India's health facilities from OpenStreetMap into a compressed snapshot.

    python scripts/fetch_directory.py            # all states → directory_data/facilities_in.jsonl.gz
    python scripts/fetch_directory.py --state Odisha

Data © OpenStreetMap contributors, available under the Open Database Licence (ODbL).
Facilities are grouped by district (admin_level 5) so every record carries state + district.
The snapshot is loaded into the database with `python -m app.directory load`.
"""

import gzip
import json
import sys
import time
from pathlib import Path

import httpx

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]
UA = {"User-Agent": "Jeevia-facility-directory/1.0 (+https://github.com/SagarSwain05/Jeevia)"}
OUT = Path(__file__).resolve().parents[1] / "directory_data"
PARTS = OUT / "parts"

STATES_Q = """[out:json][timeout:120];
area["ISO3166-1"="IN"][admin_level=2]->.in;
rel(area.in)[admin_level=4][boundary=administrative];
out tags;"""

STATE_Q = """[out:json][timeout:600];
area(id:{area})->.s;
rel(area.s)[admin_level=5][boundary=administrative]->.dists;
foreach.dists->.d(
  .d out tags;
  .d map_to_area->.a;
  (
    nwr["amenity"~"^(hospital|clinic)$"]["name"](area.a);
    nwr["healthcare"~"^(hospital|clinic|centre)$"]["name"](area.a);
  );
  out center tags;
);"""


def run(query: str, attempts: int = 8) -> dict:
    delay = 20
    for i in range(attempts):
        ep = ENDPOINTS[i % len(ENDPOINTS)]
        try:
            r = httpx.post(ep, data={"data": query}, headers=UA, timeout=700)
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                d = r.json()
                if "remark" in d and "timed out" in d["remark"]:
                    raise RuntimeError(d["remark"][:80])
                return d
            raise RuntimeError(f"HTTP {r.status_code}")
        except Exception as e:  # noqa: BLE001 — retry on anything
            print(f"  attempt {i + 1} via {ep.split('/')[2]} failed: {e}; retry in {delay}s", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 300)
    raise RuntimeError("all attempts failed")


def fetch_state(name: str, rel_id: int) -> list[dict]:
    d = run(STATE_Q.format(area=3600000000 + rel_id))
    rows, district = [], None
    for el in d["elements"]:
        tags = el.get("tags", {})
        if el["type"] == "relation" and tags.get("admin_level") == "5":
            district = tags.get("name:en") or tags.get("name")
            continue
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        rows.append({
            "ref": f"osm:{el['type'][0]}{el['id']}",
            "name": tags.get("name:en") or tags.get("name"),
            "name_local": tags.get("name") if tags.get("name:en") else None,
            "amenity": tags.get("amenity"),
            "healthcare": tags.get("healthcare"),
            "operator": tags.get("operator"),
            "operator_type": tags.get("operator:type"),
            "beds": tags.get("beds"),
            "state": name,
            "district": district,
            "city": tags.get("addr:city") or tags.get("addr:village") or tags.get("addr:town"),
            "pincode": tags.get("addr:postcode"),
            "address": ", ".join(x for x in [tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:suburb")] if x) or None,
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "lat": lat,
            "lon": lon,
        })
    return rows


def main() -> None:
    PARTS.mkdir(parents=True, exist_ok=True)
    only = sys.argv[sys.argv.index("--state") + 1] if "--state" in sys.argv else None
    states = run(STATES_Q)["elements"]
    states = sorted(((s["tags"].get("name:en") or s["tags"]["name"], s["id"]) for s in states), key=lambda x: x[0])
    print(f"{len(states)} states/UTs", flush=True)
    for name, rid in states:
        if only and name != only:
            continue
        part = PARTS / f"{rid}.json"
        if part.exists() and not only:
            continue
        print(f"→ {name}", flush=True)
        rows = fetch_state(name, rid)
        part.write_text(json.dumps(rows, ensure_ascii=False))
        print(f"  {len(rows)} facilities", flush=True)
        time.sleep(5)
    seen, total = set(), 0
    with gzip.open(OUT / "facilities_in.jsonl.gz", "wt", encoding="utf-8") as out:
        for p in sorted(PARTS.glob("*.json")):
            for r in json.loads(p.read_text()):
                if r["ref"] in seen or not r["name"]:
                    continue
                seen.add(r["ref"])
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
                total += 1
    print(f"snapshot written: {total} facilities", flush=True)


if __name__ == "__main__":
    main()
