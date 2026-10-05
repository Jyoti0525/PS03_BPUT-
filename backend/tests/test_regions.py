"""F5: the regional festival and season calendar dates vague onsets (never silently), and names local worker cadres."""

import gzip
import json
from datetime import date
from pathlib import Path

import pytest
from conftest import API, DEVICE
from test_api import new_intake

from app import regions
from app.regions import Calendar
from app.triage.timeline import onset

ON = date(2026, 10, 5)


def said(text, state="Odisha", on=ON, **cal):
    return onset({"chief_complaint": text}, Calendar(state, **cal), on)


@pytest.mark.parametrize(
    "state, text, raw, start, end",
    [
        ("Odisha", "Cough since Diwali", "since Diwali", "2025-10-20", "2025-10-20"),  # Diwali 2026 (8 Nov) has not come yet
        ("Uttar Pradesh", "दिवाली से खांसी", "दिवाली से", "2025-10-20", "2025-10-20"),
        ("Uttar Pradesh", "holi ke baad se bukhar", "holi ke baad se", "2026-03-04", "2026-03-04"),
        ("Odisha", "ରଜଠାରୁ ଜ୍ୱର ହେଉଛି", "ରଜଠାରୁ", "2026-06-14", "2026-06-16"),
        ("Odisha", "ପୂଜା ପରଠାରୁ ମୁଣ୍ଡବିନ୍ଧା", "ପୂଜା ପରଠାରୁ", "2025-09-29", "2025-10-02"),  # "puja" is Durga Puja in Odisha
        ("West Bengal", "pujo theke jor", "pujo theke", "2025-09-29", "2025-10-02"),
        ("Kerala", "tired since Onam", "since Onam", "2026-08-26", "2026-08-26"),
        ("Assam", "cough since bihu", "since bihu", "2026-04-15", "2026-04-15"),
        ("Odisha", "pain since the rains", "since the rains", "2026-06-13", "2026-10-13"),  # IMD normal onset, Cuttack
        ("Rajasthan", "pain since the rains", "since the rains", "2026-06-29", "2026-09-23"),  # Jaipur: two weeks later
        ("Chhattisgarh", "since winter", "since winter", "2025-12-01", "2026-02-28"),
    ],
)
def test_festival_or_season_gets_an_approximate_date_but_stays_vague(state, text, raw, start, end):
    o = said(text, state)
    assert o["certainty"] == "VAGUE" and o["raw"] == raw and o["days"] is None  # never a precise date, never used by rules
    assert (o["approx"]["start"], o["approx"]["end"]) == (start, end)
    assert "confirm with the patient" in o["check"]


def test_a_word_with_two_meanings_shows_the_latest_and_asks_which():
    o = said("since Eid", "Delhi")
    assert o["approx"]["start"] == "2026-05-28" and "Id-ul-Fitr" in o["check"] and "ask which" in o["check"]
    o = said("since sankranti", "Odisha")  # Raja, Pana or Makar Sankranti
    assert "ask which" in o["check"] and "Pana Sankranti" in o["check"]
    o = said("cough since the rains", "Tamil Nadu", on=date(2026, 11, 25))  # Tamil Nadu has both monsoons
    assert o["approx"]["label"] == "Northeast monsoon" and "Southwest monsoon" in o["check"]


def test_unknown_dates_are_not_guessed():
    o = said("since Diwali", on=date(2028, 12, 1))  # 2028 is not in the table
    assert o["when"] == "Not clear" and not o["approx"]["found"] and "not in the regional calendar" in o["check"]
    o = said("since Nuakhai", on=date(2027, 9, 30))  # Nuakhai 2027 not published: may already have passed
    assert not o["approx"]["found"]
    assert said("since Nuakhai", on=date(2027, 6, 1))["approx"]["start"] == "2026-09-15"  # but before it, last year's is safe
    o = said("since the rains", None)  # no state: monsoon dates unknown
    assert not o["approx"]["found"] and "state is not set" in o["check"]


@pytest.mark.parametrize("text", ["Diwali sweets made me sick", "the raja of the village", "fever since puja"])
def test_a_festival_word_without_a_time_word_is_not_an_onset(text):
    o = said(text, "Gujarat")
    assert "approx" not in o  # "since puja" is still VAGUE, but in Gujarat "puja" names no one festival


def test_rules_never_use_a_calendar_date():
    from app.triage.rules import onset_hours

    assert onset_hours({"chief_complaint": "Chest pain since Diwali"}) is None


def test_facility_changes_override_the_state_table():
    cfg = {"monsoon": {"onset": "06-01", "withdrawal": "09-30"}, "festivals": [{"name": "Sital Sasthi", "aliases": ["ଶୀତଳ ଷଷ୍ଠୀ"], "dates": ["2026-06-20"]}],
           "cadres": {"community": "ASHA didi"}}
    c = Calendar("Odisha", "phc", cfg)
    o = onset({"chief_complaint": "pain since the rains"}, c, ON)
    assert o["approx"]["start"] == "2026-06-01"
    o = onset({"chief_complaint": "ଶୀତଳ ଷଷ୍ଠୀ ପରଠାରୁ ଜ୍ୱର"}, c, ON)
    assert o["approx"]["label"] == "Sital Sasthi" and o["approx"]["start"] == "2026-06-20"
    assert c.cadres["community"]["en"] == "ASHA didi"


@pytest.mark.parametrize(
    "state, ftype, key, name",
    [
        ("Odisha", "phc", "community", "ASHA"),
        ("Chhattisgarh", "phc", "community", "Mitanin"),
        ("Jharkhand", "phc", "community", "Sahiya"),
        ("Tamil Nadu", "phc", "nurse", "VHN"),
        ("Kerala", "phc", "nurse", "JPHN"),
        ("Maharashtra", "phc", "nurse", "Arogya Sevika"),
        ("Chhattisgarh", "industrial_unit", "community", "First-aider"),  # a workplace keeps its own first line
    ],
)
def test_cadre_names_follow_state_and_facility_type(state, ftype, key, name):
    assert Calendar(state, ftype).cadres[key]["en"] == name


def test_table_is_complete_and_every_date_is_real():
    t = regions.table()
    for key, f in t["festivals"].items():
        assert f["source"] in t["sources"], key
        for y, v in f["dates"].items():
            s, e = regions._span(v)
            assert s.year == y and s <= e and (e - s).days < 31, key
    for key, s in t["seasons"].items():
        assert s["source"] in t["sources"], key
    states = {json.loads(line)["state"] for line in gzip.open(Path(__file__).parents[1] / "directory_data" / "facilities_in.jsonl.gz", "rt", encoding="utf-8")}
    assert states - set(t["regions"]) == set()  # every state and UT in the facility directory has an entry
    for name, r in t["regions"].items():
        on, off = r["monsoon"]["onset"], r["monsoon"]["withdrawal"]
        assert "05-15" <= on <= "07-10" and "09-01" <= off <= "10-31", name
        assert all(k in t["festivals"] for k in r.get("local") or []), name
        assert all(v in t["festivals"] for v in (r.get("aliases") or {}).values()), name


def test_note_timeline_shows_the_calendar_date_and_asks_staff(client, nurse):
    _, body = new_intake(client, nurse, chief_complaint="Cough since Diwali")  # PHC Manikpur, Uttar Pradesh
    enc = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()
    t = next(x for x in enc["note"]["timeline"] if x["event"].startswith("Onset"))
    assert t["certainty"] == "VAGUE" and t["raw"] == "since Diwali" and t["when"].startswith("Around")
    assert "Diwali" in t["basis"] and "Uttar Pradesh calendar" in t["basis"]
    assert any("Diwali was on" in m and "confirm with the patient" in m for m in enc["note"]["missing_info"])


def test_calendar_view_try_box_and_supervisor_config(client, nurse, supervisor):
    fid = "fac_phc_manikpur"  # Uttar Pradesh
    v = client.get(f"{API}/facilities/{fid}/calendar?on=2026-10-05", headers=nurse).json()
    assert v["state"] == "Uttar Pradesh" and v["monsoon"]["station"] == "Kanpur"
    assert any(f["key"] == "diwali" and f["start"] == "2026-11-08" and not f["past"] for f in v["festivals"])
    assert client.get(f"{API}/facilities/{fid}/calendar").status_code == 401

    r = client.get(f"{API}/facilities/{fid}/onset", params={"text": "होली के बाद से बुखार", "on": "2026-10-05"}, headers=nurse).json()
    assert r["certainty"] == "VAGUE" and r["approx"]["start"] == "2026-03-04"

    assert client.get(f"{API}/facilities/{fid}", headers=nurse).json()["region"]["cadres"]["nurse"]["en"] == "ANM"
    bad = {"region_config": {"monsoon": {"onset": "02-30", "withdrawal": "09-30"}}}
    assert client.patch(f"{API}/facilities/{fid}", json=bad, headers=supervisor).status_code == 422
    cfg = {"region_config": {"cadres": {"nurse": "ANM didi"}, "festivals": [{"name": "Ram Barat", "dates": ["2026-09-25"]}]}}
    assert client.patch(f"{API}/facilities/{fid}", json=cfg, headers=nurse).status_code == 403
    try:
        f = client.patch(f"{API}/facilities/{fid}", json=cfg, headers=supervisor).json()
        assert f["region"]["cadres"]["nurse"]["en"] == "ANM didi"
        r = client.get(f"{API}/facilities/{fid}/onset", params={"text": "since Ram Barat", "on": "2026-10-05"}, headers=nurse).json()
        assert r["approx"]["start"] == "2026-09-25" and r["approx"]["source"] == "facility"
    finally:
        client.patch(f"{API}/facilities/{fid}", json={"region_config": None}, headers=supervisor)
    assert client.get(f"{API}/facilities/{fid}", headers=nurse).json()["region"]["cadres"]["nurse"]["en"] == "ANM"
