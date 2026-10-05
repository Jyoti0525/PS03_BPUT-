"""G3 anonymisation: identifiers are scrubbed from free text before storage; clinical content is never touched."""

import pytest
from conftest import API, DEVICE
from test_api import new_intake

from app.privacy import cohort, scrub


@pytest.mark.parametrize(
    "text, names, expected",
    [
        ("My name is Sita Devi and I have fever, call 98765 43210.", ["Sita Devi"], "My name is [NAME] and I have fever, call [PHONE]."),
        ("मेरा नाम सीता है, मुझे बुखार है। फोन ९८७६५४३२१०", [], "मेरा नाम [NAME] है, मुझे बुखार है। फोन [PHONE]"),
        ("ମୋ ନାମ ସୀତା ମୋତେ ଜ୍ୱର ହେଉଛି ଫୋନ୍ ୯୮୭୬୫୪୩୨୧୦", [], "ମୋ ନାମ [NAME] ମୋତେ ଜ୍ୱର ହେଉଛି ଫୋନ୍ [PHONE]"),
        ("ನನ್ನ ಹೆಸರು ರಮೇಶ್ ನನಗೆ ತಲೆನೋವು", [], "ನನ್ನ ಹೆಸರು [NAME] ನನಗೆ ತಲೆನೋವು"),
        ("Aadhaar 2345 6789 0123, ABHA 91-2345-6789-0123, sita.devi@abdm, a@b.com", [], "Aadhaar [AADHAAR], ABHA [ABHA], [ABHA], [EMAIL]"),
        ("+91 98765 43210 or 0674-2345678 or 09876543210", [], "[PHONE] or [PHONE] or [PHONE]"),
        ("Patient Asha Kumari was seen by the ASHA", ["Asha Kumari"], "Patient [NAME] was seen by the ASHA"),
    ],
)
def test_identifiers_are_replaced(text, names, expected):
    assert scrub(text, names)[0] == expected


@pytest.mark.parametrize(
    "text",
    [
        "BP 150 95, pulse 98 97 96, sugar 250, Hb 9.8, since 2024-10-01, called 108",
        "ମୋର ଚାରି ଦିନ ହେଲା ଜ୍ୱର ହେଉଛି ଓ ମୁଣ୍ଡ ବିନ୍ଧୁଛି",
        "चोट लगी, 3 दिन से 102 बुखार",
    ],
)
def test_clinical_content_is_untouched(text):
    assert scrub(text, ["Ramesh Sahoo"]) == (text, {})


def test_a_symptom_word_after_the_name_is_never_removed():
    # Speech often has no punctuation: the fever word right after the name must survive.
    out, _ = scrub("ମୋ ନାମ ସୀତା ଜ୍ୱର ହେଉଛି", [])
    assert "ଜ୍ୱର" in out and "ସୀତା" not in out


def test_untranslated_symptom_is_counted_once():
    from app.privacy import anonymise_intake

    t = "ମୋ ନାମ ସୀତା, ଫୋନ୍ ୯୮୭୬୫୪୩୨୧୦"
    out, n = anonymise_intake({"symptoms": [{"text": t, "original_text": t, "language": "or"}]}, [])
    assert n == {"name": 1, "phone": 1} and out["symptoms"][0]["text"] == out["symptoms"][0]["original_text"]


def test_staff_text_keeps_names_but_not_numbers():
    assert scrub("Spoke to Sita's son on 9876543210", ["Sita"], numbers_only=True)[0] == "Spoke to Sita's son on [PHONE]"


def test_intake_is_stored_without_identifiers_and_flagged(client, nurse, supervisor):
    pat, body = new_intake(client, nurse, chief_complaint="I am Test Person, chest pain since morning, call 9123456780",
                           answers=[{"qid": "x", "question": "Anything else?", "answer": "my name is Test Person, Aadhaar 2345 6789 0123"}])
    enc = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()
    assert enc["chief_complaint"] == "I am [NAME], chest pain since morning, call [PHONE]"
    assert enc["intake"]["answers"][0]["answer"] == "my name is [NAME], Aadhaar [AADHAAR]"
    assert enc["intake"]["redactions"] == {"name": 2, "phone": 1, "aadhaar": 1}
    assert any(f["code"] == "PII-REDACTED" for f in enc["note"]["flags"])
    assert enc["note"]["triage"]["findings"]["chest_pain"]["value"] is True  # still read from the scrubbed text
    log = client.get(f"{API}/audit", params={"action": "REDACT"}, headers=supervisor).json()
    assert any(a["resource_id"] == enc["id"] and "9123456780" not in a["detail"] for a in log)


def test_cohort_view_counts_only_and_suppresses_small_cells(client, supervisor):
    view = client.get(f"{API}/cohort", headers=supervisor).json()
    assert "name" in view["removed_fields"]
    flat = str(view)
    assert "Test Person" not in flat and "pat_" not in flat
    rows = [{"week": "2026-W40", "age": 30, "sex": "F", "category": "normal", "urgency": "red", "findings": ["fever"]} for _ in range(6)]
    rows += [{"week": "2026-W40", "age": 70, "sex": "M", "category": "chronic", "urgency": "green", "findings": []} for _ in range(2)]
    c = cohort(rows, 28)
    sex = {x["key"]: x["count"] for x in c["by_sex"]}
    assert sex == {"F": 6, "M": None, "O": 0}  # 2 men → suppressed, never shown as 2
    assert c["suppressed_cells"] > 0


# ── G1: continue without AI ─────────────────────────────
def _no_ai_intake(client, nurse, **kw):
    pat, body = new_intake(client, nurse, **kw)
    con = client.post(f"{API}/consents", json={"patient_id": pat["id"], "mode": "self", "privacy_context": "private", "language": "or",
                                              "scopes": ["triage", "no_ai"]}, headers=nurse).json()
    return {**body, "consent_id": con["id"], "language": "or"}


def test_no_ai_intake_runs_no_model_and_says_so(client, nurse, monkeypatch):
    from app import language

    def boom(*a, **k):
        raise AssertionError("translation must not run without AI consent")

    monkeypatch.setattr(language, "translate", boom)
    t = "ମୋର ଚାରି ଦିନ ହେଲା ଜ୍ୱର ହେଉଛି"
    body = _no_ai_intake(client, nurse, symptoms=[{"text": t, "original_text": t, "language": "or", "source": "text"}])
    enc = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE}).json()
    assert enc["intake"]["ai_assist"] is False and enc["note"]["ai_assist"] is False
    assert enc["note"]["renderer"] == "TEMPLATE"
    assert any(f["code"] == "NO-AI" for f in enc["note"]["flags"])
    assert not any(f["code"] == "MT-CHECK" for f in enc["note"]["flags"])
    assert enc["note"]["triage"]["findings"]["fever"]["value"] is True  # rules still read the Odia words


def test_no_ai_rejects_voice_entries(client, nurse):
    body = _no_ai_intake(client, nurse, symptoms=[{"text": "fever", "original_text": "fever", "language": "en", "source": "voice"}])
    r = client.post(f"{API}/encounters", json=body, headers={**nurse, "X-Device-Id": DEVICE})
    assert r.status_code == 422 and "declined" in r.json()["detail"]


def test_no_ai_upload_is_not_read(client, nurse):
    import io

    r = client.post(f"{API}/files", files={"file": ("slip.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 64), "image/png")},
                    data={"kind": "report", "read": "false"}, headers=nurse)
    assert r.status_code == 200 and r.json()["read_quality"] is None


def test_consent_must_belong_to_the_patient(client, nurse):
    _, body = new_intake(client, nurse)
    other, _ = new_intake(client, nurse)
    con = client.post(f"{API}/consents", json={"patient_id": other["id"], "mode": "self", "privacy_context": "private", "language": "en", "scopes": ["triage"]}, headers=nurse).json()
    assert client.post(f"{API}/encounters", json={**body, "consent_id": con["id"]}, headers={**nurse, "X-Device-Id": DEVICE}).status_code == 422
