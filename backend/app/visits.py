"""Visit calendar (E5): which days a facility holds each kind of follow-up visit.

A follow-up date (the next antenatal check-up, the next chronic check-in) is moved to the next day the facility
actually runs that clinic, never earlier than the date asked for, and never on a day it is closed. The defaults follow
how public facilities usually work: antenatal care on the weekly Village Health and Nutrition Day and on the 9th of
each month (PMSMA), a weekly NCD clinic, closed on Sunday. A facility sets its own days in `region_config["visits"]`.
"""

from datetime import date, timedelta

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
KINDS = {"anc_checkup": "Antenatal check-up", "chronic_checkin": "Chronic check-in"}
PUBLIC = {"phc", "chc", "sub_centre", "district_hospital"}


def defaults(facility_type: str | None) -> dict:
    if facility_type in PUBLIC:
        return {"anc_checkup": {"weekdays": [2], "monthdays": [9]},  # Wednesday VHND, PMSMA on the 9th
                "chronic_checkin": {"weekdays": [1]},  # Tuesday NCD clinic
                "closed_weekdays": [6], "closed_dates": []}
    # Company, campus and private clinics: any working day.
    return {"anc_checkup": {"weekdays": [0, 1, 2, 3, 4, 5]}, "chronic_checkin": {"weekdays": [0, 1, 2, 3, 4, 5]},
            "closed_weekdays": [6], "closed_dates": []}


def rules(facility) -> dict:
    out = defaults(getattr(facility, "type", None))
    own = ((getattr(facility, "region_config", None) or {}).get("visits")) or {}
    for k, v in own.items():
        if v is not None:
            out[k] = v
    return out


def is_visit_day(r: dict, kind: str, d: date) -> bool:
    if d.weekday() in (r.get("closed_weekdays") or []) or d.isoformat() in (r.get("closed_dates") or []):
        return False
    k = r.get(kind) or {}
    return d.weekday() in (k.get("weekdays") or []) or d.day in (k.get("monthdays") or [])


def snap(facility, kind: str, wanted: date) -> tuple[date, str | None]:
    """The first visit day on or after `wanted`, and why it moved (None when it did not)."""
    r = rules(facility)
    d = wanted
    for _ in range(62):
        if is_visit_day(r, kind, d):
            return d, (None if d == wanted else f"moved from {wanted:%a %d %b} to the next {KINDS.get(kind, 'clinic').lower()} day")
        d += timedelta(days=1)
    return wanted, None  # no clinic day configured in two months: keep what was asked


def upcoming(facility, kind: str, start: date, n: int = 5) -> list[date]:
    r = rules(facility)
    out, d = [], start
    while len(out) < n and d < start + timedelta(days=120):
        if is_visit_day(r, kind, d):
            out.append(d)
        d += timedelta(days=1)
    return out


def describe(facility, kind: str) -> str:
    r = rules(facility)
    k = r.get(kind) or {}
    parts = []
    if k.get("weekdays"):
        parts.append("every " + ", ".join(WEEKDAYS[i] for i in k["weekdays"]))
    if k.get("monthdays"):
        parts.append("the " + ", ".join(f"{m}{'th' if 10 <= m % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(m % 10, 'th')}" for m in k["monthdays"]) + " of each month")
    closed = [WEEKDAYS[i] for i in r.get("closed_weekdays") or []]
    s = f"{KINDS.get(kind, kind)}: " + (" and ".join(parts) or "no days set")
    if closed:
        s += f"; closed {', '.join(closed)}"
    if r.get("closed_dates"):
        s += f" and on {len(r['closed_dates'])} holiday(s)"
    return s
