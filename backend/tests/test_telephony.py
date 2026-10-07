"""Reminder calls over a real phone line and reminder SMS (Twilio), against a fake Twilio and a fake Sarvam: only the
demo phone is ever dialled or texted, webhooks must be signed, keypad answers go through the same rules, a danger sign
ends the call and texts staff without a name, and the patient's recording is deleted."""

import base64
import hashlib
import hmac

import pytest
from conftest import API
from test_calls import followup

from app import sarvam, telephony
from app.config import get_settings

BASE = "https://jeevia-test.example"
DEMO = "+919999900001"
TOKEN = "test-auth-token"


@pytest.fixture(scope="module")
def hw(client):
    from conftest import login

    return login(client, "9000000006")


@pytest.fixture
def twilio(monkeypatch):
    s = get_settings()
    for k, v in {"twilio_account_sid": "ACtest", "twilio_api_key_sid": "SKtest", "twilio_api_key_secret": "secret", "twilio_auth_token": TOKEN,
                 "twilio_from_number": "+15550001111", "public_base_url": BASE, "telephony_demo_to": DEMO}.items():
        monkeypatch.setattr(s, k, v)
    monkeypatch.setattr(sarvam, "enabled", lambda: True)
    monkeypatch.setattr(sarvam, "speak", lambda text, lang, **kw: b"ID3")
    sent = []

    def post(path, data):
        sent.append((path, data))
        return {"sid": f"SID{len(sent)}"}

    monkeypatch.setattr(telephony, "_post", post)
    return sent


def sign(url: str, params: dict) -> str:
    data = url + "".join(f"{k}{params[k]}" for k in sorted(params))
    return base64.b64encode(hmac.new(TOKEN.encode(), data.encode(), hashlib.sha1).digest()).decode()


def hook(client, cid: str, what: str, **params):
    url = telephony.url(f"calls/{cid}/{what}", cid)
    return client.post(url.removeprefix(BASE), data=params, headers={"X-Twilio-Signature": sign(url, params)})


def phone_call(client, hw, f) -> dict:
    r = client.post(f"{API}/followups/{f['id']}/calls", json={"channel": "phone"}, headers=hw)
    assert r.status_code == 200, r.text
    return r.json()


def test_nothing_is_dialled_until_everything_is_set_up(client, nurse, hw):
    st = client.get(f"{API}/telephony/status", headers=hw).json()
    assert st["calls"] is False and st["sms"] is False and any("DEMO_TO" in m for m in st["missing"])
    f = followup(client, nurse, hw, name="Phone Test Off")
    assert client.post(f"{API}/followups/{f['id']}/calls", json={"channel": "phone"}, headers=hw).status_code == 503
    assert client.post(f"{API}/followups/{f['id']}/sms", headers=hw).status_code == 503


def test_a_phone_call_rings_only_the_demo_phone_and_a_keyed_danger_sign_pages_staff(client, nurse, hw, twilio):
    f = followup(client, nurse, hw, name="Phone Test One")
    call = phone_call(client, hw, f)
    assert call["channel"] == "phone" and call["notes"]["phone"]["to"] == "…0001"
    path, data = twilio[0]
    assert path == "Calls.json" and data["To"] == DEMO and data["To"] != f["phone"] and f["phone"] not in str(data)
    assert data["Url"].startswith(f"{BASE}/api/v1/telephony/calls/{call['id']}/voice?t=")

    # Unsigned, or the wrong token: refused
    assert client.post(f"/api/v1/telephony/calls/{call['id']}/voice?t={telephony.token(call['id'])}", data={}).status_code == 403
    bad = f"{BASE}/api/v1/telephony/calls/{call['id']}/voice?t=nope"
    assert client.post(bad.removeprefix(BASE), data={}, headers={"X-Twilio-Signature": sign(bad, {})}).status_code == 403

    r = hook(client, call["id"], "voice", CallStatus="in-progress")
    assert r.status_code == 200 and "turns/0/audio" in r.text and "<Gather" in r.text and "prompts/en/keypad" in r.text
    r = hook(client, call["id"], "keys", Digits="1")  # yes, it is me
    assert "turns/2/audio" in r.text and "turns/0/audio" not in r.text  # only the new line is played
    hook(client, call["id"], "keys", Digits="1")  # can come
    hook(client, call["id"], "keys", Digits="2")  # no bleeding
    r = hook(client, call["id"], "keys", Digits="1")  # headache: yes
    assert "<Hangup/>" in r.text
    c = client.get(f"{API}/calls/{call['id']}", headers=hw).json()
    assert c["outcome"] == "danger_sign" and c["turns"][-2]["text"] == "Pressed 1" and c["turns"][-2]["text_en"] == "Yes"
    sms = [d for p, d in twilio if p == "Messages.json"]
    assert len(sms) == 1 and sms[0]["To"] == DEMO and f["patient_code"] in sms[0]["Body"]
    assert "Phone Test" not in sms[0]["Body"] and "headache" not in sms[0]["Body"].lower()  # no name, no symptom
    assert c["notes"]["staff_sms"]["sent"] is True


def test_no_key_twice_hands_over_and_a_recorded_answer_is_read_then_deleted(client, nurse, hw, twilio, monkeypatch):
    f = followup(client, nurse, hw, name="Phone Test Two")
    call = phone_call(client, hw, f)
    hook(client, call["id"], "voice")
    hook(client, call["id"], "keys", Digits="1")
    hook(client, call["id"], "keys", Digits="1")
    r = hook(client, call["id"], "keys")  # bleeding question, no key pressed
    assert "<Gather" in r.text  # "please say yes or no", asked again
    hook(client, call["id"], "keys")
    assert client.get(f"{API}/calls/{call['id']}", headers=hw).json()["outcome"] == "unclear"

    g = followup(client, nurse, hw, name="Phone Test Three", weeks=14)
    call = phone_call(client, hw, g)
    hook(client, call["id"], "voice")
    for d in "112222":  # identity, can come, then four danger questions (no movement question at 14 weeks)
        r = hook(client, call["id"], "keys", Digits=d)
    assert "<Record" in r.text and "prompts/en/after_beep" in r.text
    deleted = []
    monkeypatch.setattr(telephony, "fetch_recording", lambda url: b"mp3")
    monkeypatch.setattr(telephony, "delete_recording", lambda url: deleted.append(url))
    monkeypatch.setattr(sarvam, "transcribe", lambda audio, lang, name="", translate=False: {"text": "I have had fever since yesterday"})
    r = hook(client, call["id"], "recording", RecordingUrl="https://api.twilio.com/rec/RE1", RecordingDuration="5")
    assert "<Hangup/>" in r.text and deleted == ["https://api.twilio.com/rec/RE1"]
    c = client.get(f"{API}/calls/{call['id']}", headers=hw).json()
    assert c["outcome"] == "danger_sign" and c["red_flags"][0]["finding"] == "fever"


def test_not_answered_and_cut_off(client, nurse, hw, twilio):
    f = followup(client, nurse, hw, name="Phone Test Four")
    call = phone_call(client, hw, f)
    assert hook(client, call["id"], "status", CallStatus="no-answer").status_code == 204
    assert client.get(f"{API}/calls/{call['id']}", headers=hw).json()["outcome"] == "no_answer"
    call = phone_call(client, hw, f)
    hook(client, call["id"], "voice")
    hook(client, call["id"], "status", CallStatus="completed")
    assert client.get(f"{API}/calls/{call['id']}", headers=hw).json()["outcome"] == "hung_up"


def test_reminder_sms_in_the_patients_language_says_nothing_about_health(client, nurse, hw, twilio):
    f = followup(client, nurse, hw, name="Sms Test One", lang="hi")
    r = client.post(f"{API}/followups/{f['id']}/sms", headers=hw)
    assert r.status_code == 200 and r.json()["attempts"][-1]["outcome"] == "sms"
    body = twilio[-1][1]["Body"]
    assert twilio[-1][1]["To"] == DEMO and "नमस्ते Sms" in body and "गर्भ" not in body
    g = followup(client, nurse, hw, name="Sms Test Two", owner="husband")
    client.post(f"{API}/followups/{g['id']}/sms", headers=hw)
    assert twilio[-1][1]["Body"].startswith("Namaste. This is") and "pregnan" not in twilio[-1][1]["Body"].lower()


def test_prompts_and_lines_for_twilio(client, nurse, hw, twilio):
    assert client.get("/api/v1/telephony/prompts/ta/keypad").content == b"ID3"
    assert client.get("/api/v1/telephony/prompts/xx/keypad").status_code == 404
    f = followup(client, nurse, hw, name="Phone Test Five")
    call = phone_call(client, hw, f)
    ok = client.get(f"/api/v1/telephony/calls/{call['id']}/turns/0/audio?t={telephony.token(call['id'])}")
    assert ok.status_code == 200 and ok.headers["content-type"] == "audio/mpeg"
    assert client.get(f"/api/v1/telephony/calls/{call['id']}/turns/0/audio?t=wrong").status_code == 403


# ── Vonage (free trial: calls and texts the account's own number) ──
class _Resp:
    def __init__(self, data):
        self._d = data
        self.content = b"mp3"

    def json(self):
        return self._d


@pytest.fixture
def vonage_on(monkeypatch):
    from app import vonage

    s = get_settings()
    for k, v in {"vonage_api_key": "k", "vonage_api_secret": "s", "vonage_application_id": "app", "vonage_private_key_path": "x.key",
                 "public_base_url": BASE, "telephony_demo_to": DEMO}.items():
        monkeypatch.setattr(s, k, v)
    monkeypatch.setattr(vonage, "private_key", lambda: b"key")
    monkeypatch.setattr(sarvam, "enabled", lambda: True)
    monkeypatch.setattr(sarvam, "speak", lambda text, lang, **kw: b"ID3")
    sent = []

    def call(method, url, **kw):
        sent.append((method, url, kw.get("json")))
        return _Resp({"uuid": "VON-1"})

    monkeypatch.setattr(vonage, "_call", call)

    class FakeHttpx:
        HTTPError = Exception

        @staticmethod
        def post(url, data=None, timeout=None):
            sent.append(("SMS", url, data))
            return type("R", (), {"status_code": 200, "json": lambda self: {"messages": [{"status": "0", "message-id": "M1"}]}})()

    monkeypatch.setattr(vonage, "httpx", FakeHttpx)
    return sent


def vhook(client, cid, what, method="post", **body):
    from app import vonage

    path = vonage.url(f"calls/{cid}/{what}", cid).removeprefix(BASE)
    return client.get(path) if method == "get" else client.post(path, json=body)


def test_vonage_rings_only_the_demo_phone_and_reads_keys_and_the_recorded_answer(client, nurse, hw, vonage_on, monkeypatch):
    from app import vonage

    assert client.get(f"{API}/telephony/status", headers=hw).json()["provider"] == "vonage"
    f = followup(client, nurse, hw, name="Vonage Test One", weeks=14)
    call = phone_call(client, hw, f)
    method, url, body = vonage_on[0]
    assert method == "POST" and url == vonage.VOICE and body["to"] == [{"type": "phone", "number": DEMO[1:]}]
    assert f["phone"] not in str(body) and body["answer_url"][0].startswith(f"{BASE}/api/v1/telephony/vonage/calls/{call['id']}/answer?t=")
    assert client.get(f"/api/v1/telephony/vonage/calls/{call['id']}/answer?t=wrong").status_code == 403

    ncco = vhook(client, call["id"], "answer", "get").json()
    assert ncco[0]["action"] == "stream" and "turns/0/audio" in ncco[0]["streamUrl"][0]
    assert ncco[-1]["action"] == "input" and ncco[-2]["bargeIn"] is True and "prompts/en/keypad" in ncco[-2]["streamUrl"][0]
    for d in "112222":
        ncco = vhook(client, call["id"], "keys", dtmf={"digits": d, "timed_out": False}).json()
    assert [a["action"] for a in ncco][-3:] == ["stream", "record", "input"]

    deleted = []
    monkeypatch.setattr(vonage, "delete_recording", lambda u: deleted.append(u))
    monkeypatch.setattr(sarvam, "transcribe", lambda audio, lang, name="", translate=False: {"text": "My husband will bring me on Friday"})
    assert vhook(client, call["id"], "recording", recording_url="https://api.nexmo.com/v1/files/R1", size=2048).status_code == 204
    ncco = vhook(client, call["id"], "after_record").json()
    assert deleted == ["https://api.nexmo.com/v1/files/R1"] and "turns/" in ncco[-1]["streamUrl"][0]
    c = client.get(f"{API}/calls/{call['id']}", headers=hw).json()
    assert c["outcome"] == "completed" and c["notes"]["said"].startswith("My husband")


def test_vonage_danger_key_texts_staff_and_unanswered_is_no_answer(client, nurse, hw, vonage_on):
    f = followup(client, nurse, hw, name="Vonage Test Two")
    call = phone_call(client, hw, f)
    vhook(client, call["id"], "answer", "get")
    for d in "111":  # it is me, can come, bleeding: yes
        vhook(client, call["id"], "keys", dtmf={"digits": d})
    c = client.get(f"{API}/calls/{call['id']}", headers=hw).json()
    assert c["outcome"] == "danger_sign" and c["notes"]["staff_sms"]["sent"] is True
    sms = [x for x in vonage_on if x[0] == "SMS"]
    assert sms[0][2]["to"] == DEMO[1:] and f["patient_code"] in sms[0][2]["text"] and "Vonage Test" not in sms[0][2]["text"]
    g = followup(client, nurse, hw, name="Vonage Test Three")  # a flagged follow-up gets a person, not the agent
    call = phone_call(client, hw, g)
    assert vhook(client, call["id"], "event", status="unanswered").status_code == 204
    assert client.get(f"{API}/calls/{call['id']}", headers=hw).json()["outcome"] == "no_answer"
