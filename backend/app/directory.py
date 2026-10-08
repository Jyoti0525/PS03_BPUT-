"""National facility directory: classification, loading and search.

    python -m app.directory load [path]   # load/refresh the snapshot into the database
    python -m app.directory stats         # counts by state and kind

Source: OpenStreetMap (© OpenStreetMap contributors, ODbL), fetched by scripts/fetch_directory.py.
Rows are reference data. A directory row becomes an operational Facility the first time a staff
member joins it (see `activate`). Private workplaces — company clinics, industrial units, campus
health centres, health camps — are not taken from the directory: their organisation registers them.
"""

import gzip
import json
import logging
import re
import sys
import threading
import uuid
from pathlib import Path

from sqlalchemy import func, or_, select, text
from sqlalchemy.orm import Session

from .models import DirectoryFacility, Facility, Organisation

log = logging.getLogger("jeevia.directory")
SNAPSHOT = Path(__file__).resolve().parents[1] / "directory_data" / "facilities_in.jsonl.gz"

KIND_LABEL = {
    "sub_centre": "Sub-centre / Health & Wellness Centre",
    "phc": "Primary Health Centre",
    "chc": "Community Health Centre",
    "district_hospital": "District Hospital",
    "sub_district_hospital": "Sub-district / Taluk Hospital",
    "medical_college": "Medical College Hospital",
    "esi": "ESI Hospital / Dispensary",
    "dispensary": "Dispensary",
    "ayush": "AYUSH Centre",
    "hospital": "Hospital",
    "clinic": "Clinic",
    "health_centre": "Health Centre",
}

# Operational facility type used by the app for each directory kind.
KIND_TO_TYPE = {
    "sub_centre": "sub_centre",
    "phc": "phc",
    "chc": "chc",
    "district_hospital": "district_hospital",
    "sub_district_hospital": "hospital",
    "medical_college": "hospital",
    "esi": "hospital",
    "hospital": "hospital",
    "dispensary": "clinic",
    "ayush": "clinic",
    "clinic": "clinic",
    "health_centre": "clinic",
}

_RULES = [
    ("sub_centre", r"sub[\s-]*(health[\s-]*)?cent(re|er)|\bhsc\b|health\s*(and|&)\s*wellness|\bhwc\b|ayushman\s+arogya\s+mandir|\baam\b"),
    ("phc", r"primary\s+health|\bu?p\.?\s?h\.?\s?c\b|urban\s+health\s+cent|\bphc\b|additional\s+primary"),
    ("chc", r"community\s+health|\bc\.?\s?h\.?\s?c\b|\bchc\b"),
    ("district_hospital", r"district\s+(head\s*quarters?\s+)?hospital|\bd\.?h\.?h\b|district\s+hq|zilla\s+hospital|civil\s+hospital"),
    ("sub_district_hospital", r"sub[\s-]*divisional\s+hospital|\bsdh\b|area\s+hospital|taluk[a]?\s+hospital|block\s+hospital|rural\s+hospital|general\s+hospital"),
    ("medical_college", r"medical\s+college|\baiims\b|institute\s+of\s+medical\s+sciences|\bpgimer\b|\bjipmer\b"),
    ("esi", r"\besic?\b|employees'?\s+state\s+insurance"),
    ("dispensary", r"dispensar"),
    ("ayush", r"\bayush\b|ayurved|homo?eo|unani|siddha|naturopath"),
]
_PUBLIC = re.compile(
    r"\bgovt\b|government|sarkari|railway|municipal|corporation|civil\s+hospital|\baiims\b|\bcghs\b|police|army|military|\bechs\b|\besic?\b|district|primary\s+health|community\s+health|\bphc\b|\bchc\b|sub[\s-]*cent|wellness|\bnhm\b|\bpgimer\b|\bjipmer\b",
    re.I,
)


def classify(name: str, amenity: str | None, healthcare: str | None) -> str:
    n = name.lower()
    for kind, pat in _RULES:
        if re.search(pat, n):
            return kind
    if amenity == "hospital" or healthcare == "hospital":
        return "hospital"
    if healthcare == "centre":
        return "health_centre"
    return "clinic"


def ownership(name: str, kind: str, operator_type: str | None) -> str:
    ot = (operator_type or "").lower()
    if ot in ("government", "public", "state", "central"):
        return "public"
    if ot in ("private", "private_non_profit", "ngo", "charitable", "religious", "community"):
        return "private"
    if kind in ("sub_centre", "phc", "chc", "district_hospital", "esi") or _PUBLIC.search(name):
        return "public"
    return "unknown"


def _row(r: dict) -> dict:
    name = (r["name"] or "").strip()[:300]
    kind = classify(name, r.get("amenity"), r.get("healthcare"))
    beds = r.get("beds")
    try:
        beds = int(beds) if beds not in (None, "") else None
    except ValueError:
        beds = None
    pin = (r.get("pincode") or "").strip()
    return {
        "ref": r["ref"][:40],
        "name": name,
        "name_local": (r.get("name_local") or None) and r["name_local"][:300],
        "kind": kind,
        "ownership": ownership(name, kind, r.get("operator_type")),
        "state": (r.get("state") or "")[:100],
        "district": (r.get("district") or None) and r["district"][:100],
        "city": (r.get("city") or None) and r["city"][:120],
        "pincode": pin[:10] if re.fullmatch(r"\d{6}", pin) else None,
        "address": (r.get("address") or None) and r["address"][:300],
        "phone": (r.get("phone") or None) and r["phone"][:40],
        "beds": beds,
        "lat": r.get("lat"),
        "lon": r.get("lon"),
        "source": "osm",
    }


def load(db: Session, path: Path = SNAPSHOT, batch: int = 2000) -> int:
    """Upsert the snapshot. Safe to re-run; existing rows are refreshed by `ref`."""
    if not path.exists():
        log.warning("directory snapshot not found")
        return 0
    n = 0
    buf: list[dict] = []
    dialect = db.get_bind().dialect.name

    def flush():
        nonlocal buf
        if not buf:
            return
        if dialect == "postgresql":
            from sqlalchemy.dialects.postgresql import insert

            stmt = insert(DirectoryFacility).values(buf)
            cols = {c: getattr(stmt.excluded, c) for c in buf[0] if c != "ref"}
            db.execute(stmt.on_conflict_do_update(index_elements=["ref"], set_=cols))
        else:
            from sqlalchemy.dialects.sqlite import insert

            stmt = insert(DirectoryFacility).values(buf)
            cols = {c: getattr(stmt.excluded, c) for c in buf[0] if c != "ref"}
            db.execute(stmt.on_conflict_do_update(index_elements=["ref"], set_=cols))
        db.commit()
        buf = []

    with gzip.open(path, "rt", encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            if not r.get("name") or not r.get("state"):
                continue
            buf.append(_row(r))
            n += 1
            if len(buf) >= batch:
                flush()
    flush()
    return n


def load_in_background_if_empty(session_factory) -> None:
    """Called at start-up: fill an empty directory without delaying the server."""

    def run():
        try:
            with session_factory() as db:
                if db.scalar(select(DirectoryFacility.id).limit(1)) is not None:
                    return
                if db.get_bind().dialect.name == "postgresql":
                    got = db.execute(text("SELECT pg_try_advisory_lock(7274423)")).scalar()
                    if not got:
                        return
                try:
                    n = load(db)
                    log.info("facility directory loaded: %s facilities", n)
                finally:
                    if db.get_bind().dialect.name == "postgresql":
                        db.execute(text("SELECT pg_advisory_unlock(7274423)"))
                        db.commit()
        except Exception:
            log.exception("facility directory load failed")

    threading.Thread(target=run, name="directory-load", daemon=True).start()


def search(db: Session, q: str, state: str | None = None, limit: int = 20) -> list[dict]:
    """Directory facilities plus registered workplaces (organisation / user-added / sample), best match first."""
    q = " ".join(q.lower().split())[:80]
    if len(q) < 2:
        return []
    pg = db.get_bind().dialect.name == "postgresql"
    tokens = [t for t in re.split(r"[\s,]+", q) if t][:5]

    out: list[dict] = []
    # 1) Workplaces already operating in Jeevia that did not come from the directory
    fq = select(Facility, Organisation.name).outerjoin(Organisation, Facility.organisation_id == Organisation.id).where(Facility.directory_ref.is_(None), Facility.source.notin_(("sample", "system")))  # sample facilities are walkthrough-only
    for t in tokens:
        like = f"%{t}%"
        fq = fq.where(or_(func.lower(Facility.name).like(like), func.lower(Facility.district).like(like), Facility.pincode == t, func.lower(func.coalesce(Organisation.name, "")).like(like)))
    if state:
        fq = fq.where(Facility.state == state)
    for f, org_name in db.execute(fq.limit(limit)).all():
        out.append(_fac_out(f, org_name))

    # 2) National directory
    pin = next((t for t in tokens if re.fullmatch(r"\d{6}", t)), None)
    words = [t for t in tokens if t != pin]

    def directory_query(required: list[str]):
        dq = select(DirectoryFacility)
        if pin:
            dq = dq.where(DirectoryFacility.pincode == pin)
        for t in required:
            like = f"%{t}%"
            dq = dq.where(or_(func.lower(DirectoryFacility.name).like(like), func.lower(func.coalesce(DirectoryFacility.district, "")).like(like), func.lower(func.coalesce(DirectoryFacility.city, "")).like(like)))
        if state:
            dq = dq.where(DirectoryFacility.state == state)
        if pg and words:
            return dq.order_by(func.similarity(func.lower(DirectoryFacility.name), " ".join(words)).desc())
        return dq.order_by(func.length(DirectoryFacility.name))

    rows = list(db.scalars(directory_query(words).limit(limit)))
    if not rows and len(words) > 1:
        # Every word must match normally; if that finds nothing, keep the first word and rank by similarity.
        rows = list(db.scalars(directory_query(words[:1]).limit(limit)))
    active = {f.directory_ref: f.id for f in db.scalars(select(Facility).where(Facility.directory_ref.in_([r.ref for r in rows])))} if rows else {}
    for r in rows:
        out.append({
            "key": f"dir:{r.ref}", "name": r.name, "kind": r.kind, "kind_label": KIND_LABEL.get(r.kind, r.kind), "type": KIND_TO_TYPE.get(r.kind, "clinic"),
            "ownership": r.ownership, "state": r.state, "district": r.district, "city": r.city, "pincode": r.pincode,
            "source": "directory", "directory_ref": r.ref, "facility_id": active.get(r.ref), "organisation_name": None, "verified": True,
        })
    return out[:limit]


def _fac_out(f: Facility, org_name: str | None) -> dict:
    labels = {"company_clinic": "Company clinic", "industrial_unit": "Industrial estate health unit", "campus": "Campus health centre", "health_camp": "Public health camp"}
    return {
        "key": f"fac:{f.id}", "name": f.name, "kind": f.type, "kind_label": labels.get(f.type, KIND_LABEL.get(f.type, f.type.replace("_", " ").title())), "type": f.type,
        "ownership": "private" if f.organisation_id else "public", "state": f.state, "district": f.district, "city": None, "pincode": f.pincode,
        "source": f.source, "directory_ref": f.directory_ref, "facility_id": f.id, "organisation_name": org_name, "verified": f.verified,
    }


_states_cache: tuple[float, list] | None = None


def states(db: Session) -> list[dict]:
    import time

    global _states_cache
    if _states_cache and time.time() - _states_cache[0] < 3600:
        return _states_cache[1]
    rows = db.execute(select(DirectoryFacility.state, func.count()).group_by(DirectoryFacility.state).order_by(DirectoryFacility.state)).all()
    out = [{"state": s, "facilities": n} for s, n in rows if s]
    _states_cache = (time.time(), out)
    return out


def activate(db: Session, ref: str, created_by: str | None) -> Facility:
    """Turn a directory entry into an operational facility (idempotent)."""
    f = db.scalar(select(Facility).where(Facility.directory_ref == ref))
    if f:
        return f
    r = db.scalar(select(DirectoryFacility).where(DirectoryFacility.ref == ref))
    if not r:
        raise LookupError("Facility not found in the national directory")
    slug = re.sub(r"[^a-z0-9]+", "", r.name.lower())[:20] or "facility"
    f = Facility(
        id=f"fac_{slug}_{uuid.uuid4().hex[:6]}", name=r.name, type=KIND_TO_TYPE.get(r.kind, "clinic"), district=r.district or r.city or "", state=r.state,
        languages=["hi", "en"], specialists=[{"key": "genmed", "label": "General Medicine", "available": True, "schedule": None}],
        referral_destination="", beds_total=r.beds or 0, beds_occupied=0, offline_mode=r.kind in ("sub_centre", "phc"), capabilities={},
        source="directory", directory_ref=r.ref, verified=True, pincode=r.pincode, address=r.address, lat=r.lat, lon=r.lon, created_by=created_by,
    )
    db.add(f)
    db.flush()
    return f


if __name__ == "__main__":
    from .db import SessionLocal, init_db

    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    init_db()
    with SessionLocal() as db:
        if cmd == "load":
            p = Path(sys.argv[2]) if len(sys.argv) > 2 else SNAPSHOT
            print(f"loaded {load(db, p)} facilities")
        else:
            total = db.scalar(select(func.count()).select_from(DirectoryFacility))
            print(f"{total} facilities")
            for k, n in db.execute(select(DirectoryFacility.kind, func.count()).group_by(DirectoryFacility.kind).order_by(func.count().desc())).all():
                print(f"  {KIND_LABEL.get(k, k):40} {n}")
