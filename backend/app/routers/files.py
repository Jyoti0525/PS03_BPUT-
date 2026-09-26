"""File upload / retrieval with expiry timestamps (A4, H4). Content is served via short-lived signed URLs."""

from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile

from .. import audit, storage
from ..config import get_settings
from ..models import Encounter, FileObject, User
from ..schemas import ADMIN_ROLES, FileKind, FileOut
from ..security import DB, CurrentUser, decode, file_token
from ..services import now, own_patient
from ..triage.reports import SAMPLE_REPORTS, render

router = APIRouter(tags=["files"])


def file_out(f: FileObject, request: Request | None = None, user: User | None = None) -> FileOut:
    url = None
    if request and user and not f.purged_at:
        url = str(request.url_for("file_content", fid=f.id)) + f"?sig={file_token(f.id, user.id)}"
    return FileOut(id=f.id, filename=f.filename, content_type=f.content_type, size=f.size, kind=f.kind, encounter_id=f.encounter_id, uploaded_at=f.uploaded_at, expires_at=f.expires_at, purged_at=f.purged_at, url=url)


@router.post("/files", response_model=FileOut)
async def upload(
    request: Request,
    user: CurrentUser,
    db: DB,
    file: Annotated[UploadFile, File()],
    kind: Annotated[FileKind, Form()],
    encounter_id: Annotated[str | None, Form()] = None,
    sample_key: Annotated[str | None, Form()] = None,
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
    f = FileObject(filename=(file.filename or "upload")[:255], content_type=ctype, size=len(data), kind=kind, encounter_id=encounter_id, uploaded_by=user.id, expires_at=storage.expiry_for(kind), sample_key=sample_key, boxes=boxes)
    db.add(f)
    db.flush()
    try:
        f.storage_key = storage.put(f.id, data, ctype, storage.folder_for(user.facility_id, kind))
    except Exception:
        db.rollback()
        raise HTTPException(502, "File storage is unavailable — please try again")
    audit.record(db, user, "UPLOAD", "file", f.id, f"{kind} uploaded ({f.filename}, {max(1, len(data) // 1024)} KB); expires {f.expires_at:%Y-%m-%d %H:%M} UTC")
    return file_out(f, request, user)


@router.get("/files/{fid}", response_model=FileOut)
def get_file(fid: str, request: Request, user: CurrentUser, db: DB):
    if user.role in ADMIN_ROLES or user.role == "employer":
        raise HTTPException(403, "This role cannot open clinical files")
    f = db.get(FileObject, fid)
    if not f:
        raise HTTPException(404, "File not found")
    enc = db.get(Encounter, f.encounter_id) if f.encounter_id else None
    if f.uploaded_by != user.id:
        if user.role == "kiosk":
            raise HTTPException(403, "Not your file")
        if user.role == "patient":
            mine = own_patient(db, user)
            if not enc or not mine or enc.patient_id != mine.id:
                raise HTTPException(403, "Not your file")
        elif enc and enc.facility_id != user.facility_id:
            raise HTTPException(403, "File belongs to another facility")
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
