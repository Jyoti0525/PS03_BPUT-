"""Audit log (G4), retention status, AI second-opinion view, guard test, patient self-service, employer cohorts."""

import csv
import io
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import or_, select

from .. import audit, output_guard, privacy, storage
from ..models import AuditEvent, Encounter, FileObject, User
from ..schemas import ADMIN_ROLES, DOCTOR_ROLES, AuditOut, AuditVerify, RetentionOut
from ..security import DB, require
from ..services import now
from .files import file_out

router = APIRouter(tags=["governance"])
Auditor = Annotated[User, Depends(require("supervisor", *DOCTOR_ROLES))]


@router.get("/audit", response_model=list[AuditOut])
def list_audit(user: Auditor, db: DB, action: str | None = None, q: str | None = None, limit: int = 500):
    stmt = select(AuditEvent).where(or_(AuditEvent.facility_id == user.facility_id, AuditEvent.facility_id.is_(None))).order_by(AuditEvent.id.desc()).limit(min(limit, 2000))
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(AuditEvent.actor_name.ilike(like), AuditEvent.detail.ilike(like), AuditEvent.patient_code.ilike(like)))
    return list(db.scalars(stmt))


@router.get("/audit/verify", response_model=AuditVerify)
def verify_audit(user: Auditor, db: DB):
    ok, n, broken = audit.verify(db)
    return AuditVerify(ok=ok, checked=n, broken_at=broken)


@router.get("/audit/export")
def export_audit(user: Auditor, db: DB):
    audit.record(db, user, "EXPORT", "audit", None, "Audit log exported as CSV")
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_ALL)
    w.writerow(["id", "ts", "actor", "role", "action", "resource", "patient", "detail", "prev_hash", "hash"])
    for a in db.scalars(select(AuditEvent).where(or_(AuditEvent.facility_id == user.facility_id, AuditEvent.facility_id.is_(None))).order_by(AuditEvent.id)):
        w.writerow([a.id, a.ts.isoformat(), a.actor_name, a.actor_role, a.action, f"{a.resource_type}:{a.resource_id or ''}", a.patient_code or "", a.detail, a.prev_hash, a.hash])
    return Response(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="jeevia-audit-log.csv"'})


@router.get("/cohort")
def deidentified_cohort(user: Auditor, db: DB, days: int = 28):
    """De-identified view of this facility's recent cases (G3): counts only, small cells suppressed."""
    days = max(7, min(days, 180))
    since = now() - timedelta(days=days)
    rows = []
    for e in db.scalars(select(Encounter).where(Encounter.facility_id == user.facility_id, Encounter.created_at >= since)):
        found = ((e.note or {}).get("triage") or {}).get("findings") or {}
        y, w, _ = e.created_at.isocalendar()
        rows.append({"week": f"{y}-W{w:02d}", "age": e.patient.age, "sex": e.patient.sex if e.patient.sex in ("F", "M") else "O",
                     "category": e.category, "urgency": e.urgency, "findings": [f for f, v in found.items() if (v or {}).get("value") is True]})
    audit.record(db, user, "VIEW", "cohort", None, f"De-identified cohort viewed ({days} days, {len(rows)} cases)", None, user.facility_id)
    return privacy.cohort(rows, days)


@router.get("/ai-opinions")
def ai_opinions(user: Auditor, db: DB, days: int = 28):
    """Where the model's second opinion on urgency differed from the rules (C8), for rule review.

    The opinion never changed any urgency; this shows how often it differed, in which direction, and what the
    clinician finally decided."""
    days = max(1, min(days, 180))
    since = now() - timedelta(days=days)
    counts = {"AGREE": 0, "DISAGREE": 0, "UNAVAILABLE": 0, "UNREADABLE": 0}
    matrix = {r: {m: 0 for m in ("red", "yellow", "green")} for r in ("red", "yellow", "green")}
    cases, model, total = [], None, 0
    stmt = select(Encounter).where(Encounter.facility_id == user.facility_id, Encounter.created_at >= since).order_by(Encounter.created_at.desc())
    for e in db.scalars(stmt):
        total += 1
        op = (e.note or {}).get("llm_opinion")
        if not op or op.get("status") not in counts:
            continue
        counts[op["status"]] += 1
        model = model or op.get("model")
        if op["status"] not in ("AGREE", "DISAGREE"):
            continue
        matrix[op["rules_urgency"]][op["model_urgency"]] += 1
        if op["status"] == "DISAGREE":
            cases.append({
                "encounter_id": e.id, "patient_code": e.patient.code, "created_at": e.created_at, "category": e.category,
                "rules_urgency": op["rules_urgency"], "model_urgency": op["model_urgency"], "direction": op["direction"],
                "reason": op.get("reason"), "reason_withheld": bool(op.get("reason_withheld")),
                "final_urgency": e.urgency, "overridden": bool(e.override), "status": e.status,
            })
    audit.record(db, user, "VIEW", "ai_opinions", None, f"AI second-opinion disagreements viewed ({days} days, {len(cases)} cases)", None, user.facility_id)
    return {"days": days, "model": model, "encounters": total, "counts": counts, "matrix": matrix,
            "higher": sum(c["direction"] == "higher" for c in cases), "lower": sum(c["direction"] == "lower" for c in cases),
            "cases": cases[:200]}


@router.get("/override-stats")
def override_stats(user: Auditor, db: DB, days: int = 28):
    """How often clinicians changed the rules' urgency, per rule (E9). A rule overruled often is a rule to review.

    For each rule that fired: cases, cases lowered below it by a doctor, cases raised. Only the rules' own output is
    counted (`rules_fired`); the override never rewrites it."""
    days = max(1, min(days, 180))
    since = now() - timedelta(days=days)
    rank = {"green": 0, "yellow": 1, "red": 2}
    per: dict[str, dict] = {}
    total = up = down = 0
    for e in db.scalars(select(Encounter).where(Encounter.facility_id == user.facility_id, Encounter.created_at >= since)):
        total += 1
        o = e.override or {}
        to = o.get("to_urgency")
        up += bool(o) and rank.get(to, 0) > rank.get(o.get("from_urgency"), 0)
        down += bool(o) and rank.get(to, 0) < rank.get(o.get("from_urgency"), 0)
        for h in (e.note or {}).get("rules_fired") or []:
            r = per.setdefault(h["rule_id"], {"rule_id": h["rule_id"], "urgency": h.get("urgency"), "description": h.get("description"), "fired": 0, "lowered": 0, "raised": 0})
            r["fired"] += 1
            if o and rank.get(to, 0) < rank.get(h.get("urgency"), 0):
                r["lowered"] += 1
            elif o and rank.get(to, 0) > rank.get(o.get("from_urgency"), 0):
                r["raised"] += 1
    rules = sorted(per.values(), key=lambda r: (-r["lowered"] / r["fired"], -r["fired"]))
    for r in rules:
        r["lowered_rate"] = round(r["lowered"] / r["fired"], 3)
    audit.record(db, user, "VIEW", "override_stats", None, f"Override rates per rule viewed ({days} days)", None, user.facility_id)
    return {"days": days, "encounters": total, "overrides": up + down, "raised": up, "lowered": down, "rules": rules}


class GuardTestIn(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    source: str = Field("", max_length=2000)


Supervisor = Annotated[User, Depends(require("supervisor"))]


@router.get("/guard-test/samples")
def guard_test_samples(user: Supervisor):
    return {"guard_version": output_guard.version(), "samples": output_guard.TEST_SAMPLES}


@router.post("/guard-test")
def guard_test(body: GuardTestIn, user: Supervisor, db: DB):
    """Run a typed sentence through the same output guard every model summary passes (C4, demo step 5).

    This is a test of the guard, never a model output: it touches no patient record and the audit entry says so.
    Identifiers in the typed text are scrubbed before it is logged."""
    verdict = output_guard.check(body.text, body.source)
    hits = [{"category": h.category, "label": h.label, "phrase": h.phrase} for h in verdict.hits]
    logged, _ = privacy.scrub(body.text)
    if verdict.ok:
        audit.record(db, user, "VIEW", "guard_test", None, f'Guard test by {user.role} (typed, not a model output): passed. Text: "{logged[:600]}"', None, user.facility_id)
    else:
        why = "; ".join(verdict.reasons())
        audit.record(db, user, "GUARD_BLOCK", "guard_test", None, f'Guard test by {user.role} (typed, not a model output): blocked ({why}). Text: "{logged[:600]}"', None, user.facility_id)
    return {"ok": verdict.ok, "hits": hits, "guard_version": output_guard.version(), "test": True}


@router.get("/retention", response_model=RetentionOut)
def retention(user: Supervisor, db: DB):
    t = now()
    files = list(db.scalars(select(FileObject).order_by(FileObject.expires_at)))
    return RetentionOut(
        policy_hours={k: storage.retention_hours(k) for k in ("audio", "image", "report")},
        active=sum(1 for f in files if not f.purged_at and f.expires_at > t),
        pending_purge=sum(1 for f in files if not f.purged_at and f.expires_at <= t),
        purged_last_7d=sum(1 for f in files if f.purged_at and t - f.purged_at < timedelta(days=7)),
        files=[file_out(f) for f in files],  # metadata only: no URL for admins
    )
