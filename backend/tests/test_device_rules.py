"""The offline kiosk runs the server's rules (frontend/src/lib/triage/engine.ts reading rulepack.json). Both engines get
the same patients here and must give the same colour, the same rules fired and the same rules left undecided.

Cases: the 300-patient set as recorded, the same 300 as an offline kiosk captures them (no vitals, no nurse check),
every kiosk answer and symptom tile, and the word matcher alone on every sentence written in these tests (English,
Hindi and Odia, with denials). Needs Node and the frontend's node_modules; skipped without them."""

import ast
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from app.triage import device_pack, findings, question_flow
from app.triage.rules import evaluate_full

ROOT = Path(__file__).resolve().parents[2]
RUNNER = ROOT / "frontend" / "scripts" / "rules-parity.mjs"
NODE = shutil.which("node")
BASE = {"symptoms": [], "selected_symptoms": [], "answers": [], "file_ids": []}
SEX = {"M": "M", "F": "F", "male": "M", "female": "F"}

# Skipped on a machine without Node; never in CI, where a skip would hide a difference between the two engines.
needs_node = pytest.mark.skipif(not os.environ.get("CI") and (not NODE or not (ROOT / "frontend" / "node_modules" / "typescript").exists()),
                                reason="Node and frontend/node_modules are needed")


def test_device_pack_is_current():
    built = json.loads(device_pack.JSON_PATH.read_text(encoding="utf-8"))
    assert built == json.loads(json.dumps(device_pack.build())), "run: python backend/scripts/build_rulepack.py"


def _device(cases: list[dict]) -> list:
    out = subprocess.run([NODE, str(RUNNER)], input=json.dumps({"cases": cases}, ensure_ascii=False), capture_output=True,
                         text=True, encoding="utf-8", cwd=ROOT / "frontend", timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    return json.loads(out.stdout)


def _summary(r: dict) -> dict:
    return {"urgency": r["urgency"], "provisional": r["provisional"],
            "hits": sorted((h["rule_id"], tuple(h["evidence"])) for h in r["hits"]),
            "hit_text": sorted(h["description"] for h in r["hits"]),
            "unresolved": sorted((u["rule_id"], tuple(u["needs"])) for u in r["unresolved"]),
            "missing_for_green": r["missing_for_green"], "protocols": [p["key"] for p in r["protocols"]]}


def _patients() -> list[dict]:
    data = yaml.safe_load((Path(__file__).parent / "data/patients300.yaml").read_text(encoding="utf-8"))["patients"]
    cases = [{"id": p["id"], "intake": {**BASE, **p["intake"]}, "age": p["age"], "sex": SEX[p["sex"]]} for p in data]
    # The offline kiosk: the patient's own words, tiles and answers, nothing measured yet.
    for p in data:
        bare = {k: v for k, v in p["intake"].items() if k not in ("vitals", "exam")}
        cases.append({"id": p["id"] + "-kiosk", "intake": {**BASE, **bare}, "age": p["age"], "sex": SEX[p["sex"]]})
    return cases


def _kiosk_inputs() -> list[dict]:
    cases = []
    for q in question_flow.load()["questions"]:
        for o in q.get("options") or []:
            for age in (1, 30):
                cases.append({"id": f"{q['qid']}:{o['label']}:{age}", "age": age, "sex": "F",
                              "intake": {**BASE, "chief_complaint": "Not feeling well", "answers": [{"qid": q["qid"], "question": q.get("text", q["qid"]), "answer": o["label"]}]}})
    for tile in findings.TILES:
        for dur in ("Today", "In the last few hours", "1-2 days", "3–7 days", "More than a month", "2 hours", None):
            cases.append({"id": f"tile:{tile}:{dur}", "age": 45, "sex": "M", "intake": {**BASE, "chief_complaint": tile, "selected_symptoms": [tile], "duration": dur, "severity": 8}})
    cases.append({"id": "infant", "age": 0, "sex": "F", "intake": {**BASE, "age_days": 20, "chief_complaint": "fever and not feeding", "vitals": {"temp_f": 100.8, "resp_rate": 66}}})
    cases.append({"id": "maternal", "age": 24, "sex": "F", "intake": {**BASE, "category": "maternal", "chief_complaint": "bleeding and headache", "maternal": {"gestation_weeks": 34},
                                                                       "vitals": {"bp_systolic": 162, "bp_diastolic": 112}}})
    cases.append({"id": "labs", "age": 50, "sex": "M", "intake": {**BASE, "chief_complaint": "tired", "lab_values": {"Hb": 6.1, "potassium": 6.8}}})
    cases.append({"id": "occupational", "age": 40, "sex": "M", "intake": {**BASE, "chief_complaint": "screening", "occupational": {"exposures": ["silica"], "years_exposed": 12, "cough_weeks": 3,
                                                                          "breathless_vs_last": "worse", "fev1_l": 2.1, "fev1_baseline_l": 2.8}}})
    cases.append({"id": "second-hearing", "age": 60, "sex": "M", "intake": {**BASE, "chief_complaint": "headache", "symptoms": [
        {"text": "headache", "original_text": "सिर दर्द", "language": "hi", "source": "voice", "second_hearing": {"text": "सिर दर्द और सीने में दर्द", "engine": "test"}}]}})
    cases.append({"id": "spoken-onset", "age": 58, "sex": "M", "intake": {**BASE, "chief_complaint": "ଦୁଇ ଘଣ୍ଟା ହେଲା ଛାତି ଦରଦ ଓ ଝାଳ", "symptoms": [
        {"text": "chest pain and sweating for 2 hours", "original_text": "ଦୁଇ ଘଣ୍ଟା ହେଲା ଛାତି ଦରଦ ଓ ଝାଳ", "language": "or", "source": "voice"}]}})
    cases.append({"id": "exam", "age": 8, "sex": "M", "intake": {**BASE, "chief_complaint": "cough", "exam": {"done": True, "signs": ["chest_indrawing"], "by": "Nurse"},
                                                                 "vitals": {"pulse": 120, "resp_rate": 44, "spo2": 91, "temp_f": 101, "avpu": "A"}}})
    return cases


def _sentences() -> list[str]:
    """Every string in the backend tests that reads like a sentence a patient might say."""
    out = set()
    for f in Path(__file__).parent.glob("test_*.py"):
        for node in ast.walk(ast.parse(f.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) and 6 <= len(node.value) <= 300 and " " in node.value:
                out.add(node.value)
    for p in yaml.safe_load((Path(__file__).parent / "data/vignettes300.yaml").read_text(encoding="utf-8"))["vignettes"]:
        out.update((p.get("text") or {}).values())
    sentences = sorted(out)
    # Denials both ways round: "no chest pain", "chest pain nahi", "ଛାତି ଦରଦ ନାହିଁ".
    return sentences + [f"no {s}" for s in sentences[:400]] + [f"{s} नहीं" for s in sentences[:400]]


@needs_node
def test_device_and_server_give_the_same_triage():
    cases = _patients() + _kiosk_inputs()
    device = _device([{k: c[k] for k in ("intake", "age", "sex")} for c in cases])
    diffs = []
    for c, d in zip(cases, device):
        s = _summary(evaluate_full(json.loads(json.dumps(c["intake"])), c["age"], c["sex"]))
        if s != _summary(d):
            diffs.append(f"{c['id']}: server {s} | device {_summary(d)}")
    assert not diffs, f"{len(diffs)} of {len(cases)} differ:\n" + "\n".join(diffs[:5])
    # The offline kiosk catches danger signs from words alone: the red vignettes that need no measurement stay red.
    reds = [d for c, d in zip(cases, device) if c["id"].endswith("-kiosk") and d["urgency"] == "red"]
    assert len(reds) >= 100  # 102 of the 112 RED patients (23 Oct); the other 10 need BP, SpO2 or the nurse's check


@needs_node
def test_device_and_server_read_the_same_words():
    sentences = _sentences()
    device = _device([{"scan": s} for s in sentences])
    diffs = [f"{s!r}: server {want} | device {got}" for s, got in zip(sentences, device)
             if (want := {k: f.value for k, f in findings.scan_text(s, "").items()}) != got]
    assert len(sentences) > 500
    assert not diffs, f"{len(diffs)} of {len(sentences)} differ:\n" + "\n".join(diffs[:8])


def test_offline_red_reaches_the_note():
    """An intake the offline kiosk flagged keeps the flag when it syncs: the note tells staff the patient was sent to a
    nurse, and names any rule the server no longer fires."""
    from app.triage import pipeline
    from types import SimpleNamespace

    vitals = {"bp_systolic": 120, "bp_diastolic": 80, "pulse": 80, "spo2": 98, "temp_f": 98.6, "resp_rate": 16, "avpu": "A"}
    intake = {"chief_complaint": "chest pain and sweating", "category": "normal", "duration": "In the last few hours", "symptoms": [], "vitals": vitals,
              "captured_offline": True, "device_check": {"red": True, "rules": [{"id": "LOCAL-ACS-FEATURES", "description": "x"}, {"id": "OLD-RULE", "description": "y"}],
                                                          "rulepack": "abc", "at": "2026-10-23T10:00:00Z"}}
    t = evaluate_full(intake, 55, "M")
    flags = {f["code"]: f for f in pipeline.build_note(intake=intake, patient=SimpleNamespace(name="T", age=55, sex="M"), triage=t, files=[], history=[], proxy=False)["flags"]}
    assert flags["DEVICE-RED"]["severity"] == "critical" and flags["DEVICE-RED"]["group"] == "clinical"
    assert "did not fire OLD-RULE:" in flags["DEVICE-RED"]["reason"]

    # The API accepts the field and keeps it with the intake (rule ids only).
    from app.schemas import IntakeIn
    body = IntakeIn(patient_id="p", facility_id="f", category="normal", language="en", chief_complaint="x", client_ref="cr_test1", device_check=intake["device_check"])
    assert body.device_check.red and [r.id for r in body.device_check.rules] == ["LOCAL-ACS-FEATURES", "OLD-RULE"]


def test_offline_photos_arrive_with_the_intake(client, nurse):
    """Photos taken on the offline kiosk are uploaded when it syncs and attached to the intake; one that never arrived
    (browser storage cleared, or refused) is named on the note so staff ask for it again."""
    import io

    from conftest import API, DEVICE
    from test_api import new_intake

    png = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                        "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")
    up = client.post(f"{API}/files", files={"file": ("rash.png", io.BytesIO(png), "image/png")}, data={"kind": "image", "read": "false"}, headers=nurse)
    assert up.status_code == 200, up.text
    lost = [{"kind": "report", "reason": "no longer on this device (browser storage was cleared)"}]
    _, body = new_intake(client, nurse, file_ids=[up.json()["id"]], captured_offline=True, files_not_sent=lost)
    enc = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()
    assert [d["filename"] for d in enc["note"]["documents"]] == ["rash.png"]
    flag = next(f for f in enc["note"]["flags"] if f["code"] == "OFFLINE-FILES")
    assert flag["severity"] == "warning" and flag["group"] == "data" and "report: no longer on this device" in flag["reason"]

    _, body = new_intake(client, nurse, files_not_sent=[{"kind": "report", "reason": "x" * 201}])
    assert client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).status_code == 422
