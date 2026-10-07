"""B10: image understanding without diagnosis, and G3 redaction before storage."""

import io

import pytest
from conftest import API, DEVICE
from test_api import new_intake

from app.triage import images

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")


def strip_png(lines: list[str]) -> bytes:
    """A synthetic medicine strip: dark print on foil-grey, as a phone photo would be after cropping."""
    img = np.full((90 + 70 * len(lines), 1100, 3), 225, np.uint8)
    for i, t in enumerate(lines):
        cv2.putText(img, t, (40, 80 + 70 * i), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (30, 30, 30), 3, cv2.LINE_AA)
    return cv2.imencode(".png", img)[1].tobytes()


STRIP = ["PARACETAMOL TABLETS IP", "Paracetamol 500 mg", "Batch No. SYN2401", "Mfg. 01/2026  Exp. 12/2027", "MRP Rs. 20.00 for 10 tablets"]


def lines(*texts):
    return [{"text": t, "conf": 0.95, "bbox": [0.1, 0.1 * i, 0.5, 0.05]} for i, t in enumerate(texts)]


def test_medicine_names_are_matched_to_the_generic_list_with_strength():
    meds = images.medicines(lines("AMOXYCILLIN CAPSULES IP", "Amoxycillin 500 mg", "Batch AB12"))
    meds += images.medicines(lines("Metformn Hydrochloride Tablets 500 mg"))  # OCR dropped a letter
    names = {m["name"].split()[0]: m for m in meds}
    assert "metformin" in names and names["metformin"]["strength"] == "500 mg"
    assert all(m["status"] == "awaiting_confirmation" for m in meds)


def test_real_strip_photo_reads_each_medicine_once_with_its_strength_column():
    """OCR lines (text, box) from a phone photo of a paracetamol + phenylephrine + chlorpheniramine strip, 5 Oct.
    The strength column is a separate box on the same row; the torn lower half left "heniramine", which used to
    fuzzy-match pheniramine, a different medicine."""
    read = [("gcnuncoated tablelcontains", [0.143, 0.243, 0.306, 0.028]), ("500", [0.554, 0.254, 0.069, 0.017]),
            ("patacetamolIP", [0.147, 0.259, 0.149, 0.021]), ("10mg", [0.562, 0.264, 0.064, 0.016]),
            ("Phenylephrine Hydrochloride Ip", [0.147, 0.266, 0.289, 0.023]), ("2m9", [0.576, 0.274, 0.053, 0.016]),
            ("ChlorpheniramineMaleate IP", [0.149, 0.278, 0.269, 0.021]), ("Paracetamol+", [0.182, 0.49, 0.351, 0.045]),
            ("Phenylephrine", [0.185, 0.518, 0.354, 0.048]), ("Chlorpheniramine", [0.192, 0.57, 0.433, 0.055]),
            ("acetamolIP", [0.244, 0.703, 0.121, 0.031]), ("ylephrine Hy", [0.264, 0.712, 0.126, 0.033]), ("heniramine", [0.286, 0.726, 0.1, 0.027])]
    meds = {m["name"]: m["strength"] for m in images.medicines([{"text": t, "conf": 0.95, "bbox": b} for t, b in read])}
    assert meds == {"paracetamol": "500 (unit not read)", "phenylephrine": "10 mg", "chlorpheniramine": "2 mg"}


@pytest.mark.parametrize(
    "text, expected",
    [
        (["PARACETAMOL TABLETS IP 500 mg", "Batch No. SYN2401", "Mfg. 01/2026 Exp. 12/2027", "MRP Rs 20"], "medicine_strip"),
        (["Dr. A. Sahoo MBBS Reg. No. 12345", "Rx", "Tab Paracetamol 500 mg 1-0-1 after food", "Follow up after 5 days"], "prescription"),
        (["DISCHARGE SUMMARY", "Date of admission 01/09/2026", "Date of discharge 05/09/2026", "Course in hospital: uneventful"], "discharge_summary"),
        (["Haemoglobin 9.4 g/dL", "Reference range 12-15", "Pathology laboratory", "Result"], "lab_report"),
        (["a"], "non_document"),
        (["Village panchayat notice", "Meeting on Sunday at the school", "All are invited to attend"], "other_document"),
    ],
)
def test_document_type(text, expected):
    assert images.doc_type(lines(*text))["type"] == expected


def test_faces_are_pixelated_and_id_lines_blacked_out(monkeypatch):
    img = np.full((400, 600, 3), 200, np.uint8)
    img[100:200, 100:200] = np.random.default_rng(0).integers(0, 255, (100, 100, 3), dtype=np.uint8)  # "face" texture
    data = cv2.imencode(".png", img)[1].tobytes()
    monkeypatch.setattr(images, "_faces", lambda im: [(100, 100, 100, 100)])
    out, rep = images.redact(data, "image/png", [{"text": "Aadhaar 2345 6789 0123", "bbox": [0.5, 0.8, 0.3, 0.05]}, {"text": "Hb 9.4 g/dL", "bbox": [0.1, 0.9, 0.2, 0.05]}])
    assert rep["faces"] == 1 and rep["id_numbers"] == 1
    red = cv2.imdecode(np.frombuffer(out, np.uint8), cv2.IMREAD_COLOR)
    face = red[110:190, 110:190].astype(int)
    assert np.abs(np.diff(face, axis=1)).mean() < np.abs(np.diff(img[110:190, 110:190].astype(int), axis=1)).mean() / 3  # detail destroyed
    assert red[int(0.82 * 400), int(0.6 * 600)].max() < 20  # ID line is black


def test_photo_without_faces_is_still_reencoded_without_metadata():
    data = cv2.imencode(".jpg", np.full((200, 200, 3), 180, np.uint8))[1].tobytes()
    out, rep = images.redact(data, "image/jpeg", [])
    assert rep["faces"] == 0 and out != data


def test_strip_photo_becomes_medicines_awaiting_confirmation(client, nurse, doctor):
    pytest.importorskip("rapidocr_onnxruntime")
    up = client.post(f"{API}/files", files={"file": ("strip.png", io.BytesIO(strip_png(STRIP)), "image/png")}, data={"kind": "report"}, headers=nurse).json()
    _, body = new_intake(client, nurse, file_ids=[up["id"]])
    enc = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()
    doc = enc["note"]["documents"][0]
    assert doc["doc_type"]["type"] == "medicine_strip"
    pending = enc["note"]["medications_pending"]
    assert [m["name"] for m in pending] == ["paracetamol"] and pending[0]["strength"] == "500 mg"
    assert enc["note"]["medications"] == [] and any(f["code"] == "MEDS-UNCONFIRMED" for f in enc["note"]["flags"])
    assert not enc["note"]["labs"]  # strengths on a strip are not lab values
    done = client.post(f"{API}/encounters/{enc['id']}/medications", json={"confirm": ["paracetamol"]}, headers=doctor).json()
    assert done["note"]["medications"][0]["name"] == "paracetamol" and not done["note"]["medications_pending"]
    assert not any(f["code"] == "MEDS-UNCONFIRMED" for f in done["note"]["flags"])
    assert client.post(f"{API}/encounters/{enc['id']}/medications", json={"confirm": ["insulin"]}, headers=doctor).status_code == 422


def test_photo_of_the_problem_is_not_interpreted(client, nurse):
    data = cv2.imencode(".png", np.full((300, 300, 3), 150, np.uint8))[1].tobytes()
    up = client.post(f"{API}/files", files={"file": ("rash.png", io.BytesIO(data), "image/png")}, data={"kind": "image"}, headers=nurse).json()
    _, body = new_intake(client, nurse, file_ids=[up["id"]])
    enc = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()
    doc = enc["note"]["documents"][0]
    assert doc["doc_type"]["type"] == "non_document" and doc["read"] is False and not enc["note"]["medications_pending"]


@pytest.mark.parametrize("text,want", [
    ("Azithromycin IP5oo mg", "500 mg"), ("LosartanIPS0mg", "50 mg"), ("Ciprofloxacin Ip 5o0 mg", "500 mg"), ("Losartan IPSomg", "50 mg"),
])
def test_strength_with_letters_read_for_digits_is_read_whole(text, want):
    """A strip photo's OCR writes o for 0 and S for 5; the strength must not become the tail of the number ("0 mg")."""
    meds = images.medicines([{"text": text, "conf": 0.9, "bbox": [0.1, 0.1, 0.5, 0.05]}])
    assert meds and meds[0]["strength"] == want
