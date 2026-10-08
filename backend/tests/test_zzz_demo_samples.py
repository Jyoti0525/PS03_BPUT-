"""Sample-data switch (app/routers/demo.py). Runs last: it rebuilds the database."""

from conftest import API, login


def test_switch_is_refused_unless_enabled(client):
    assert client.get(f"{API}/demo/samples").json()["available"] is False
    assert client.post(f"{API}/demo/samples", json={"on": False}).status_code == 403


def test_off_empties_the_queues_and_on_brings_fresh_samples_back(client, monkeypatch):
    from app.config import get_settings

    monkeypatch.setattr(get_settings(), "demo_controls", True)
    r = client.post(f"{API}/demo/samples", json={"on": False})
    assert r.status_code == 200 and r.json() == {"available": True, "on": False}
    doc = login(client, "9000000001")  # staff accounts stay
    assert client.get(f"{API}/queue?facility_id=fac_phc_manikpur", headers=doc).json() == []
    assert client.post(f"{API}/kiosk/ANYCARE/session", json={"device_id": "tab-anycare"}).status_code == 200  # the any-centre link survives

    assert client.post(f"{API}/demo/samples", json={"on": True}).json()["on"] is True
    q = client.get(f"{API}/queue?facility_id=fac_phc_manikpur", headers=login(client, "9000000001")).json()
    assert q and max(i["wait_minutes"] for i in q if i.get("wait_minutes") is not None) < 24 * 60  # timed from now


def test_queue_preview_only_on_the_demo_laptop_and_only_synthetic(client, monkeypatch):
    from app.config import get_settings

    assert client.get(f"{API}/demo/queue-preview").status_code == 404
    monkeypatch.setattr(get_settings(), "demo_controls", True)
    j = client.get(f"{API}/demo/queue-preview").json()
    assert j["facility"] == "PHC Manikpur" and j["rules"] > 100 and len(j["items"]) <= 4
    ranks = [{"red": 0, "yellow": 1, "green": 2}[i["urgency"]] for i in j["items"]]
    assert ranks == sorted(ranks) and j["red"] >= 1
