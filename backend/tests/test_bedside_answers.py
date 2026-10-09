"""Follow-up questions answered at the bedside: the answer joins the history, the question leaves the list, and where
the answer settles a finding the rules run again on it."""

from conftest import API
from test_wednesday import NORMAL, hw, intake  # noqa: F401  (hw is a fixture)


def _q(note: dict, tag: str) -> dict:
    return next(q for q in note["followup_questions"] if q["tag"] == tag)


def test_answer_moves_into_history_and_feeds_the_rules(client, nurse):
    _, e = intake(client, nurse, chief_complaint="Headache since morning", vitals=NORMAL, severity=3, duration="today", exam={"done": True})
    q = _q(e["note"], "Visual change")
    assert q["id"] == "headache:visual_change" and q["options"] == ["Yes", "No", "Not sure"]
    r = client.post(f"{API}/encounters/{e['id']}/answers", json={"qid": q["id"], "answer": "Yes", "text": "sees flashing lights"}, headers=nurse)
    assert r.status_code == 200, r.text
    n = r.json()["note"]
    assert all(x["id"] != q["id"] for x in n["followup_questions"])
    a = n["followup_answered"][0]
    assert a["answer"] == "Yes" and a["text"] == "sees flashing lights" and "nurse" in a["by"]
    f = n["triage"]["findings"]["visual_disturbance"]
    assert f["value"] is True and "asked by" in f["evidence"][0]
    assert "blurred vision or seeing spots" in n["history"]["positives"]


def test_one_sided_weakness_raises_urgency(client, nurse):
    _, e = intake(client, nurse, chief_complaint="Sudden weakness since morning", vitals=NORMAL, severity=3, duration="today", exam={"done": True})
    q = _q(e["note"], "Weakness")
    r = client.post(f"{API}/encounters/{e['id']}/answers", json={"qid": q["id"], "answer": "One arm, leg or side of the face"}, headers=nurse).json()
    assert r["note"]["triage"]["findings"]["one_sided_weakness"]["value"] is True
    assert r["urgency"] == "red" and r["urgency"] != e["urgency"]


def test_not_sure_sets_nothing_and_answers_are_checked(client, nurse, hw):  # noqa: F811
    _, e = intake(client, nurse, chief_complaint="Headache since morning", vitals=NORMAL, severity=3, duration="today", exam={"done": True})
    url = f"{API}/encounters/{e['id']}/answers"
    assert client.post(url, json={"qid": "headache:visual_change", "answer": "Maybe"}, headers=nurse).status_code == 422
    assert client.post(url, json={"qid": "no_such_question", "answer": "Yes"}, headers=nurse).status_code == 422
    assert client.post(url, json={"qid": "headache:visual_change", "answer": "Yes"}, headers=hw).status_code == 422  # a nurse's question
    n = client.post(url, json={"qid": "headache:visual_change", "answer": "Not sure"}, headers=nurse).json()["note"]
    assert "visual_disturbance" not in n["triage"]["findings"] or "asked by" not in str(n["triage"]["findings"]["visual_disturbance"])
    ctx = _q(n, "Context")
    assert ctx["options"] == []
    assert client.post(url, json={"qid": "context"}, headers=nurse).status_code == 422  # free-text question needs the words
    n = client.post(url, json={"qid": "context", "text": "started a new job in a stone quarry"}, headers=nurse).json()["note"]
    assert [a["qid"] for a in n["followup_answered"]] == ["headache:visual_change", "context"]
