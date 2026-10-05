"""Alerts that are not about one patient's note (C3, D3, D4), each decided by a fixed rule over stored data.

* Capacity (C3): open RED cases outnumber the doctors and medical officers on duty → the medical officer is told.
* Fever cluster (D3): 5 or more fevers from one hostel block (or village) in 72 hours, and more than 3 times that
  place's usual rate over the 14 days before → the medical officer is told, with counts only and no names.
* Missed visit (D4): a maternal check-up passes its due date by a day → the assigned health worker is told, and after
  two failed attempts a reminder call is due. On a phone that is not the woman's own, nothing about pregnancy is said.

Checks run when data changes (an intake, new vitals) and lazily when a list is read, like the escalation timer.
One open alert per (facility, kind, key); it is updated while the condition holds and resolved when it stops.
"""

import csv
import io
import threading
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import audit
from .models import Alert, Encounter, Facility, Patient, Reminder, User
from .privacy import K_MIN
from .schemas import DOCTOR_ROLES
from .services import aware, local_day, now

OPEN = ("queued", "in_review", "escalated")
_lock = threading.Lock()


# ── shared ────────────────────────────────────────────
def _open_alert(db: Session, facility_id: str, kind: str, key: str) -> Alert | None:
    return db.scalar(select(Alert).where(Alert.facility_id == facility_id, Alert.kind == kind, Alert.key == key, Alert.status != "resolved"))


def _raise(db: Session, facility_id: str, kind: str, key: str, to_role: str, title: str, detail: dict, assigned_to: str | None = None) -> tuple[Alert, bool]:
    """Open the alert, or refresh the open one. Returns (alert, newly raised)."""
    a = _open_alert(db, facility_id, kind, key)
    if a:
        if a.detail != detail or a.title != title:
            a.title, a.detail, a.updated_at = title, detail, now()
        return a, False
    a = Alert(facility_id=facility_id, kind=kind, key=key, to_role=to_role, assigned_to=assigned_to, title=title, detail=detail)
    db.add(a)
    db.flush()
    audit.record(db, None, "ALERT", "alert", a.id, f"{kind}: {title}", None, facility_id)
    return a, True


def _resolve(db: Session, facility_id: str, kind: str, key: str, why: str) -> None:
    a = _open_alert(db, facility_id, kind, key)
    if a:
        a.status, a.resolved_at, a.updated_at = "resolved", now(), now()
        audit.record(db, None, "ALERT", "alert", a.id, f"{kind} resolved: {why}", None, facility_id)


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


# ── C3: queue order and capacity ──────────────────────
RANK = {"red": 0, "yellow": 1, "green": 2}


def order_reasons(items: list) -> dict[str, str]:
    """Why each queue row is where it is, in words: tier, the rule behind it, place within the tier, wait."""
    tiers = Counter(i["urgency"] for i in items)
    seen: Counter = Counter()
    out = {}
    for i in sorted(items, key=lambda i: (RANK[i["urgency"]], -i["wait"])):
        seen[i["urgency"]] += 1
        u = i["urgency"].upper()
        head = f"{u} ({i['why']})" if i.get("why") else u
        out[i["id"]] = f"{head} · {_ordinal(seen[i['urgency']])} of {tiers[i['urgency']]} {u} · waiting {i['wait']} min, longest first"
    return out


def why_tier(e: Encounter) -> str:
    if e.urgency_source == "override":
        return "doctor's override"
    n = e.note or {}
    if (n.get("triage") or {}).get("provisional") and e.urgency == "yellow":
        return "provisional until measured"
    hit = next((h for h in n.get("rules_fired") or [] if h.get("urgency") == e.urgency), None)
    return hit["rule_id"] if hit else ""


def doctors_on_duty(db: Session, facility_id: str) -> int:
    return len(list(db.scalars(select(User.id).where(User.facility_id == facility_id, User.role.in_(DOCTOR_ROLES), User.is_active, User.on_duty))))


def check_capacity(db: Session, facility_id: str) -> dict:
    """Open REDs (not yet confirmed or referred) against the doctors and medical officers on duty."""
    with _lock:
        reds = list(db.scalars(select(Encounter).where(Encounter.facility_id == facility_id, Encounter.status.in_(OPEN), Encounter.urgency == "red")
                               .order_by(Encounter.created_at)))
        docs = doctors_on_duty(db, facility_id)
        t = now()
        rows = [{"token": e.token, "wait_minutes": max(0, round((t - aware(e.created_at)).total_seconds() / 60)), "status": e.status} for e in reds]
        over = len(reds) > docs
        alert = None
        if over:
            title = f"{len(reds)} RED case{'s' if len(reds) != 1 else ''} waiting, {docs} doctor{'s' if docs != 1 else ''} or medical officer{'s' if docs != 1 else ''} on duty"
            alert, _ = _raise(db, facility_id, "capacity", "red", "medical_officer", title,
                              {"open_red": len(reds), "doctors_on_duty": docs, "tokens": [r["token"] for r in rows],
                               "longest_wait_min": max((r["wait_minutes"] for r in rows), default=0),
                               "action": "Call in another doctor, or refer the longest-waiting RED case"})
        else:
            _resolve(db, facility_id, "capacity", "red", f"{len(reds)} open RED, {docs} on duty")
        db.commit()
        return {"open_red": len(reds), "doctors_on_duty": docs, "over": over, "reds": rows, "alert": alert}


# ── D3: fever clusters and syndromic counts ───────────
CLUSTER_MIN = 5  # cases in the window
WINDOW_H = 72
BASELINE_DAYS = 14
RATIO = 3.0
SYNDROMES = {"fever": ("fever",), "respiratory": ("cough", "breathless"), "gastro": ("diarrhoea", "vomiting"), "rash": ("rash",)}


def _found(e: Encounter, fid: str) -> bool:
    return (((e.note or {}).get("triage") or {}).get("findings") or {}).get(fid, {}).get("value") is True


def is_fever(e: Encounter) -> bool:
    t = ((e.intake or {}).get("vitals") or {}).get("temp_f")
    return _found(e, "fever") or (t is not None and t >= 100.4)


def cluster_of(e: Encounter) -> str | None:
    k = ((e.intake or {}).get("cluster_key") or "").strip() or (e.patient.village or "").strip()
    return k or None


def _recent(db: Session, facility_id: str, since: datetime) -> list[Encounter]:
    return list(db.scalars(select(Encounter).where(Encounter.facility_id == facility_id, Encounter.created_at >= since)))


def check_fever_cluster(db: Session, facility_id: str, key: str | None) -> Alert | None:
    """Fevers from one place in the last 72 h against that place's own 14 days before. One count per patient."""
    if not key:
        return None
    t = now()
    start = t - timedelta(hours=WINDOW_H)
    rows = [e for e in _recent(db, facility_id, start - timedelta(days=BASELINE_DAYS)) if cluster_of(e) == key and is_fever(e)]
    cases = {e.patient_id for e in rows if aware(e.created_at) >= start}
    before = {e.patient_id for e in rows if aware(e.created_at) < start}
    expected = len(before) / BASELINE_DAYS * (WINDOW_H / 24)  # the 14-day rate scaled to 72 hours
    n = len(cases)
    if n >= CLUSTER_MIN and n > RATIO * expected:
        detail = {"cluster": key, "cases_72h": n, "baseline_14d": len(before), "expected_72h": round(expected, 1),
                  "ratio": round(n / expected, 1) if expected else None, "window_hours": WINDOW_H,
                  "rule": f"{CLUSTER_MIN} or more fevers in {WINDOW_H} h and more than {RATIO:g}× the rate of the {BASELINE_DAYS} days before",
                  "action": "Check water, food and mosquito breeding at the site; consider IDSP reporting (form S, syndromic)"}
        a, new = _raise(db, facility_id, "fever_cluster", key, "medical_officer", f"Fever cluster: {key} — {n} cases in {WINDOW_H} h", detail)
        return a
    _resolve(db, facility_id, "fever_cluster", key, f"{n} fevers in {WINDOW_H} h")
    return None


def syndromic_csv(db: Session, facility_id: str, days: int = 14) -> str:
    """Daily counts per place and syndrome. A count of 1–4 is written as "<5" so nobody can be singled out."""
    since = now() - timedelta(days=days)
    counts: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for e in _recent(db, facility_id, since):
        k = (local_day(aware(e.created_at)), cluster_of(e) or "not recorded")
        counts[k]["visits"] += 1
        for s, fids in SYNDROMES.items():
            if (s == "fever" and is_fever(e)) or (s != "fever" and any(_found(e, f) for f in fids)):
                counts[k][s] += 1
    buf = io.StringIO()
    w = csv.writer(buf)
    cols = ["visits", *SYNDROMES]
    w.writerow(["date", "place", *cols])
    for (day, place), c in sorted(counts.items()):
        w.writerow([day, place, *("<5" if 0 < c[x] < K_MIN else c[x] for x in cols)])
    return buf.getvalue()


# ── D4: maternal missed visits ────────────────────────
GRACE = timedelta(days=1)
CALL_AFTER = 2  # failed home-visit or phone attempts before a reminder call is due
ACTIVE = ("scheduled", "missed", "contacted", "call_due")


def first_name(p: Patient) -> str:
    return (p.name or "").split()[0] if p.name else "the patient"


def reminder_message(p: Patient, facility: str, due: datetime, phone_belongs_to: str | None) -> str:
    """What the SMS or call says. Only on the woman's own phone does it mention a pregnancy check-up; on a husband's,
    family or unknown phone it asks for her by first name and says nothing reproductive."""
    when = aware(due).strftime("%d %b")
    if phone_belongs_to == "self":
        return f"Namaste {first_name(p)}. Your pregnancy check-up at {facility} is due on {when}. Please bring your MCP card."
    return f"Namaste. This is {facility}. Please ask {first_name(p)} to visit {facility} on {when}."


def call_script(r: Reminder, p: Patient, facility: str) -> str | None:
    if r.phone_belongs_to == "none" or not p.phone:
        return None
    if r.phone_belongs_to == "self":
        return (f"Namaste {first_name(p)}. This is {facility}. Your pregnancy check-up was due on {aware(r.due_at).strftime('%d %b')}. "
                f"Please come this week and bring your MCP card. If you cannot come, your ASHA will visit you.")
    return f"Namaste. This is {facility}. Please ask {first_name(p)} to visit {facility} this week. Thank you."


def check_missed_visits(db: Session, facility_id: str) -> int:
    """Scheduled check-ups more than a day overdue become missed, and the assigned health worker is alerted."""
    t = now()
    n = 0
    for r in db.scalars(select(Reminder).where(Reminder.facility_id == facility_id, Reminder.status == "scheduled")):
        if aware(r.due_at) + GRACE > t:
            continue
        r.status, r.missed_at = "missed", t
        p = db.get(Patient, r.patient_id)
        _raise(db, facility_id, "missed_visit", r.id, "health_worker", f"Missed check-up: {p.name} ({p.village or 'village not recorded'})",
               {"reminder_id": r.id, "patient_code": p.code, "due": aware(r.due_at).date().isoformat(), "kind": r.kind,
                "action": "Visit or phone her; record each attempt. After 2 failed attempts a reminder call is due."}, assigned_to=r.assigned_to)
        audit.record(db, None, "ALERT", "reminder", r.id, f"Check-up due {aware(r.due_at).date().isoformat()} missed", p.code, facility_id)
        n += 1
    if n:
        db.commit()
    return n


def record_attempt(db: Session, r: Reminder, user: User, outcome: str, note: str) -> None:
    attempts = list(r.attempts or [])
    attempts.append({"at": now().isoformat(), "by": f"{user.name} ({user.role})", "outcome": outcome, "note": note or None})
    r.attempts = attempts
    a = _open_alert(db, r.facility_id, "missed_visit", r.id)
    if outcome == "came":
        r.status, r.resolved_at = "done", now()
        _resolve(db, r.facility_id, "missed_visit", r.id, "she came for the check-up")
    elif outcome == "reached":
        r.status = "contacted"
        if a and a.status == "open":
            a.status, a.acknowledged_by, a.acknowledged_at, a.updated_at = "acknowledged", user.name, now(), now()
    elif sum(1 for x in attempts if x["outcome"] == "not_reached") >= CALL_AFTER:
        r.status = "call_due"
        if a:
            a.title = a.title.replace("Missed check-up", "Reminder call due")
            a.detail = {**a.detail, "call_due": True}
            a.updated_at = now()


def close_on_visit(db: Session, patient_id: str, user: User | None) -> int:
    """A new pregnancy visit closes her open check-up reminders and their alerts."""
    n = 0
    for r in db.scalars(select(Reminder).where(Reminder.patient_id == patient_id, Reminder.kind == "anc_checkup", Reminder.status.in_(ACTIVE))):
        attempts = list(r.attempts or [])
        attempts.append({"at": now().isoformat(), "by": f"{user.name} ({user.role})" if user else "intake", "outcome": "came", "note": "pregnancy visit recorded"})
        r.attempts, r.status, r.resolved_at = attempts, "done", now()
        if r.facility_id:
            _resolve(db, r.facility_id, "missed_visit", r.id, "she came for a visit")
        n += 1
    return n


def facility_name(db: Session, facility_id: str | None) -> str:
    f = db.get(Facility, facility_id) if facility_id else None
    return f.name if f else "the health centre"
