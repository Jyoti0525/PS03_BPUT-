"""File upload / retrieval with expiry timestamps (A4, H4). Content is served via short-lived signed URLs."""

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from starlette.concurrency import run_in_threadpool

from .. import audit, sarvam, storage
from ..config import get_settings
from ..models import Encounter, FileObject, User
from ..schemas import ADMIN_ROLES, REVIEWER_ROLES, FileKind, FileOut
from ..security import DB, CurrentUser, decode, file_token
from ..services import now
from ..triage.extraction import add_online_reading, extract_document, wants_online_reading
from ..triage.images import redact
from ..triage.reports import SAMPLE_REPORTS, render

router = APIRouter(tags=["files"])


def file_out(f: FileObject, request: Request | None = None, user: User | None = None) -> FileOut:
    url = None
    if request and user and not f.purged_at:
        url = str(request.url_for("file_content", fid=f.id)) + f"?sig={file_token(f.id, user.id)}"
    ex = f.extraction
    rq = {"engine": ex["engine"], "ok": ex["quality"].get("ok", True), "issues": ex["quality"].get("issues", []), "values_found": len(ex["rows"])} if ex and f.kind == "report" else None
    return FileOut(id=f.id, filename=f.filename, content_type=f.content_type, size=f.size, kind=f.kind, encounter_id=f.encounter_id, uploaded_at=f.uploaded_at, expires_at=f.expires_at, purged_at=f.purged_at, url=url, read_quality=rq)


@router.post("/files", response_model=FileOut)
async def upload(
    request: Request,
    user: CurrentUser,
    db: DB,
    file: Annotated[UploadFile, File()],
    kind: Annotated[FileKind, Form()],
    encounter_id: Annotated[str | None, Form()] = None,
    sample_key: Annotated[str | None, Form()] = None,
    read: Annotated[bool, Form()] = True,  # False: the patient chose to continue without AI — no OCR runs
    online: Annotated[bool, Form()] = False,  # the patient's AI consent covers the online reader (consent text)
):
    if user.role in ADMIN_ROLES or user.role == "employer":
        raise HTTPException(403, "This role cannot upload clinical files")
    s = get_settings()
    ctype = file.content_type or "application/octet-stream"
    if not ctype.startswith(storage.ALLOWED_TYPES[kind]):
        raise HTTPException(415, f"{ctype} is not allowed for {kind}")
    data = await file.read(s.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"File too large (max {s.max_upload_mb} MB)")
    boxes = None
    if sample_key:
        if sample_key not in SAMPLE_REPORTS:
            raise HTTPException(422, "Unknown sample report")
        boxes = render(sample_key, "")[1]
    extraction = None
    if kind == "report" and read:
        # Read the document now (offline OCR / text layer) so the reviewer sees values with their source crops.
        # Two offline OCR engines read it at once and are compared test by test (B9).
        extraction = await run_in_threadpool(lambda: extract_document(data, ctype, second=True))
        # Handwriting the offline engines cannot read: Sarvam Vision (online, India), only with the patient's consent.
        if online and ctype.startswith("image/") and ctype != "image/svg+xml" and sarvam.enabled() and wants_online_reading(extraction):
            extraction = await run_in_threadpool(add_online_reading, extraction, data, file.filename or "page.jpg")
    elif kind == "image" and read and ctype.startswith("image/"):
        # A photo of the problem is never interpreted; it is only scanned for ID numbers to black out.
        ex = await run_in_threadpool(extract_document, data, ctype)
        extraction = {"engine": "none", "quality": {"ok": True, "issues": []}, "rows": [], "meta": {}, "warnings": [], "text": [],
                      "doc_type": {"type": "non_document", "label": "Photo — not interpreted", "why": "photo of the problem"}, "medicines": [], "_lines": ex["text"]}
    # Privacy before storage (G3): faces blurred, ID-number lines blacked out, photo metadata dropped.
    lines = (extraction or {}).pop("_lines", None) or (extraction or {}).get("text")
    data, redaction = await run_in_threadpool(redact, data, ctype, lines)
    if kind == "image" and extraction is None:
        extraction = {"engine": "none", "quality": {"ok": True, "issues": []}, "rows": [], "meta": {}, "warnings": [], "text": [],
                      "doc_type": {"type": "non_document", "label": "Photo — not interpreted", "why": "photo of the problem"}, "medicines": []}
    if extraction is not None:
        extraction["redaction"] = redaction
    f = FileObject(filename=(file.filename or "upload")[:255], content_type=ctype, size=len(data), kind=kind, encounter_id=encounter_id, uploaded_by=user.id, expires_at=storage.expiry_for(kind), sample_key=sample_key, boxes=boxes, extraction=extraction)
    db.add(f)
    db.flush()
    try:
        f.storage_key = storage.put(f.id, data, ctype, storage.folder_for(user.facility_id, kind))
    except Exception:
        db.rollback()
        raise HTTPException(502, "File storage is unavailable — please try again")
    audit.record(db, user, "UPLOAD", "file", f.id, f"{kind} uploaded ({f.filename}, {max(1, len(data) // 1024)} KB); expires {f.expires_at:%Y-%m-%d %H:%M} UTC"
                 + (f"; read by {f.extraction['engine']}, {len(f.extraction['rows'])} lab value(s)" if f.extraction else "")
                 + (f"; also read online by {f.extraction['online_reading']['engine']} (patient's AI consent)" if f.extraction and f.extraction.get("online_reading") else "")
                 + ("; not read (patient continued without AI)" if kind == "report" and not read else "")
                 + (f"; redacted before storage: {redaction['faces']} face(s), {redaction['id_numbers']} ID-number line(s)" if redaction.get("faces") or redaction.get("id_numbers") else ""))
    return file_out(f, request, user)


@router.get("/files/{fid}", response_model=FileOut)
def get_file(fid: str, request: Request, user: CurrentUser, db: DB):
    if user.role in ADMIN_ROLES or user.role == "employer":
        raise HTTPException(403, "This role cannot open clinical files")
    f = db.get(FileObject, fid)
    if not f:
        raise HTTPException(404, "File not found")
    enc = db.get(Encounter, f.encounter_id) if f.encounter_id else None
    # Patient documents are for the treating team only: doctors and nurses at the facility where
    # the patient was seen, and whoever uploaded the file before submission.
    # Front desk, supervisors, employers and kiosks never open them. (QR summaries use their own links.)
    if f.uploaded_by != user.id:
        if user.role not in REVIEWER_ROLES or not enc or enc.facility_id != user.facility_id:
            raise HTTPException(403, "Only the doctors and nurses treating this patient can open their documents")
    if enc and user.role in REVIEWER_ROLES:
        audit.record(db, user, "VIEW", "file", f.id, f"Document opened: {f.kind} {f.filename}", enc.patient.code, enc.facility_id)
    return file_out(f, request, user)


@router.get("/files/{fid}/content", name="file_content")
def file_content(fid: str, sig: str, db: DB):
    claims = decode(sig, "file")
    if claims.get("fid") != fid:
        raise HTTPException(403, "Signature does not match file")
    f = db.get(FileObject, fid)
    if not f or f.purged_at or not f.storage_key or f.expires_at < now():
        raise HTTPException(410, "File expired or purged under the retention policy")
    data = storage.get(f.storage_key)
    if data is None:
        raise HTTPException(410, "File no longer stored")
    return Response(data, media_type=f.content_type, headers={"Cache-Control": "private, max-age=300", "X-Content-Type-Options": "nosniff"})
