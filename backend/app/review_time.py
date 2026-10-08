"""Review time per case (§5 target: under 4 minutes), measured from the audit trail, not from a stopwatch.

For each case a clinician confirmed: the time from that clinician's first view of the triage note to their
confirmation. Views by others (a nurse, a second doctor) do not start the clock. A case confirmed without a recorded
view (through the API directly) is left out, and so is one over 2 hours (the note was left open; not review time).
"""

import statistics

from sqlalchemy import select

from app.models import AuditEvent

TARGET_S, IDLE_S = 240, 7200


def review_times(db, facility_id: str | None = None) -> dict:
    q = select(AuditEvent).where(AuditEvent.resource_type == "encounter", AuditEvent.action.in_(("VIEW", "CONFIRM"))).order_by(AuditEvent.id)
    if facility_id:
        q = q.where(AuditEvent.facility_id == facility_id)
    first_view: dict[tuple, object] = {}
    cases, idle, unseen = [], 0, 0
    for ev in db.scalars(q):
        key = (ev.resource_id, ev.actor_id)
        if ev.action == "VIEW":
            first_view.setdefault(key, ev.ts)
        elif key in first_view:
            s = (ev.ts - first_view.pop(key)).total_seconds()
            if s > IDLE_S:
                idle += 1
            else:
                cases.append({"encounter_id": ev.resource_id, "by_role": ev.actor_role, "seconds": round(s, 1)})
        else:
            unseen += 1
    xs = sorted(c["seconds"] for c in cases)
    return {"cases": len(xs), "median_s": statistics.median(xs) if xs else None, "p90_s": xs[min(len(xs) - 1, int(0.9 * len(xs)))] if xs else None,
            "under_target": sum(x < TARGET_S for x in xs), "target_s": TARGET_S, "left_open_over_2h": idle, "confirmed_without_view": unseen, "per_case": cases}
