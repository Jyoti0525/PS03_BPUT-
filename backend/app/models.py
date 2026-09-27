"""Relational tables for identity, facilities and audit; JSONB for flexible triage notes."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, event, true as sa_true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base, JSONType, UTCDateTime


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Organisation(Base):
    """An employer or institution (company, industrial estate, campus, NGO / camp organiser).
    Its clinics, units, campus centres and camps appear in the workplace list only after it registers."""

    __tablename__ = "organisations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("org"))
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(24))  # company | industrial | campus | ngo | government_programme
    registration_no: Mapped[str | None] = mapped_column(String(64), nullable=True)  # GSTIN / CIN / AISHE / NGO reg.
    state: Mapped[str] = mapped_column(String(100))
    district: Mapped[str] = mapped_column(String(100))
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(15), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class DirectoryFacility(Base):
    """Reference list of India's health facilities (OpenStreetMap import). Read-only for the app;
    a row becomes an operational Facility when the first staff member joins it."""

    __tablename__ = "facility_directory"
    __table_args__ = (Index("ix_facility_directory_state_district", "state", "district"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ref: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    name_local: Mapped[str | None] = mapped_column(String(300), nullable=True)
    kind: Mapped[str] = mapped_column(String(24), index=True)
    ownership: Mapped[str] = mapped_column(String(10), default="unknown")  # public | private | unknown
    state: Mapped[str] = mapped_column(String(100))
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(120), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    beds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(16), default="osm")


class Facility(Base):
    __tablename__ = "facilities"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(32))
    district: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(100))
    languages: Mapped[list] = mapped_column(JSONType, default=list)
    specialists: Mapped[list] = mapped_column(JSONType, default=list)
    referral_destination: Mapped[str] = mapped_column(String(300), default="")
    beds_total: Mapped[int] = mapped_column(Integer, default=0)
    beds_occupied: Mapped[int] = mapped_column(Integer, default=0)
    offline_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    capabilities: Mapped[dict] = mapped_column(JSONType, default=dict)
    # Provenance: sample | directory (national list) | organisation (registered by an employer) | user_added
    source: Mapped[str] = mapped_column(String(16), default="sample", server_default="sample")
    directory_ref: Mapped[str | None] = mapped_column(String(40), nullable=True, unique=True)
    organisation_id: Mapped[str | None] = mapped_column(ForeignKey("organisations.id"), nullable=True, index=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True, default=utcnow)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("usr"))
    phone: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    facility_id: Mapped[str | None] = mapped_column(ForeignKey("facilities.id"), nullable=True)
    registration_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    organisation_id: Mapped[str | None] = mapped_column(ForeignKey("organisations.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    # Second sign-in factor for staff and employers (after phone OTP). Hash is salted per user.
    pin_hash: Mapped[str | None] = mapped_column(String(200), nullable=True)
    pin_set_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    pin_failed_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    pin_locked_until: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    # Front-desk time management: whether a doctor / nurse is on duty right now.
    on_duty: Mapped[bool] = mapped_column(Boolean, default=True, server_default=sa_true())
    duty_changed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class OtpChallenge(Base):
    __tablename__ = "otp_challenges"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("otp"))
    phone: Mapped[str] = mapped_column(String(15), index=True)
    code_hash: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True, default=utcnow, index=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    consumed: Mapped[bool] = mapped_column(Boolean, default=False)


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"
    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    revoked_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Device(Base):
    __tablename__ = "devices"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    label: Mapped[str] = mapped_column(String(120))
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id"))
    bound_by: Mapped[str] = mapped_column(String(200))
    bound_by_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bound_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (UniqueConstraint("organisation_id", "employee_code", name="uq_patient_employee_code"),)
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("pat"))
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    age: Mapped[int] = mapped_column(Integer)
    sex: Mapped[str] = mapped_column(String(1))
    phone: Mapped[str | None] = mapped_column(String(15), index=True, nullable=True)
    language: Mapped[str] = mapped_column(String(8), default="en")
    category: Mapped[str] = mapped_column(String(16), default="normal")
    village: Mapped[str | None] = mapped_column(String(120), nullable=True)
    employer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # legacy, superseded by organisation_id
    # Workers: linked to their employer's roster
    organisation_id: Mapped[str | None] = mapped_column(ForeignKey("organisations.id"), nullable=True, index=True)
    employee_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class FitnessAssessment(Base):
    """Occupational fitness outcome recorded by a doctor. The employer sees only this, never the visit."""

    __tablename__ = "fitness_assessments"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("fit"))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    organisation_id: Mapped[str] = mapped_column(ForeignKey("organisations.id"), index=True)
    encounter_id: Mapped[str | None] = mapped_column(ForeignKey("encounters.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(24))  # fit | fit_with_restrictions | temporarily_unfit | pending_review
    restrictions: Mapped[str | None] = mapped_column(String(300), nullable=True)
    valid_until: Mapped[str | None] = mapped_column(String(10), nullable=True)
    assessed_by: Mapped[str] = mapped_column(String(200))
    assessed_by_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Consent(Base):
    __tablename__ = "consents"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("con"))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    mode: Mapped[str] = mapped_column(String(8))
    proxy_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    proxy_relation: Mapped[str | None] = mapped_column(String(64), nullable=True)
    privacy_context: Mapped[str] = mapped_column(String(20))
    language: Mapped[str] = mapped_column(String(8))
    scopes: Mapped[list] = mapped_column(JSONType, default=list)
    captured_by: Mapped[str] = mapped_column(String(200))
    captured_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)


class Encounter(Base):
    __tablename__ = "encounters"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("enc"))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id"), index=True)
    category: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    chief_complaint: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    urgency: Mapped[str] = mapped_column(String(8))
    rules_urgency: Mapped[str] = mapped_column(String(8))  # original rules output, never overwritten
    urgency_source: Mapped[str] = mapped_column(String(10), default="rules")
    note: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    intake: Mapped[dict] = mapped_column(JSONType)
    override: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    referral_needed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    specialist_required: Mapped[str | None] = mapped_column(String(32), nullable=True)
    escalation_due_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    consent_id: Mapped[str | None] = mapped_column(ForeignKey("consents.id"), nullable=True)
    client_ref: Mapped[str] = mapped_column(String(80), unique=True)
    # Queue token printed for the patient, e.g. T-014; restarts daily per facility.
    token: Mapped[str | None] = mapped_column(String(12), nullable=True)
    token_date: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    channel: Mapped[str] = mapped_column(String(16), default="staff_kiosk")  # staff_kiosk | kiosk_link | patient_app
    patient: Mapped[Patient] = relationship(lazy="joined")
    consent: Mapped[Consent | None] = relationship(lazy="joined")


class KioskLink(Base):
    """A public intake link for one facility. Opening it starts a kiosk session (role=kiosk) that can
    only register patients, capture consent, upload files and submit intakes."""

    __tablename__ = "kiosk_links"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("kl"))
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120))
    facility_id: Mapped[str] = mapped_column(ForeignKey("facilities.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    last_used_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    sessions: Mapped[int] = mapped_column(Integer, default=0)


class ShareLink(Base):
    """Time-limited summary link behind a QR code (for referral hand-off). Opening it needs the
    6-digit access code printed beside the QR; every opening is audited."""

    __tablename__ = "share_links"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("shr"))
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    code_hash: Mapped[str] = mapped_column(String(200))
    encounter_id: Mapped[str] = mapped_column(ForeignKey("encounters.id"), index=True)
    purpose: Mapped[str] = mapped_column(String(20), default="referral")
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    views: Mapped[int] = mapped_column(Integer, default=0)
    failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    encounter: Mapped["Encounter"] = relationship(lazy="joined")


class Escalation(Base):
    __tablename__ = "escalations"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("esc"))
    encounter_id: Mapped[str] = mapped_column(ForeignKey("encounters.id"), index=True)
    raised_by: Mapped[str] = mapped_column(String(200))
    raised_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    to_role: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(Text)
    auto: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="open")
    acknowledged_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    ack_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    encounter: Mapped[Encounter] = relationship(lazy="joined")


class Referral(Base):
    __tablename__ = "referrals"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("ref"))
    encounter_id: Mapped[str] = mapped_column(ForeignKey("encounters.id"), index=True)
    destination: Mapped[str] = mapped_column(String(300))
    specialty: Mapped[str] = mapped_column(String(120))
    reason: Mapped[str] = mapped_column(Text)
    note_text: Mapped[str] = mapped_column(Text)
    transport: Mapped[str] = mapped_column(String(20))
    created_by: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    status: Mapped[str] = mapped_column(String(16), default="sent")
    encounter: Mapped[Encounter] = relationship(lazy="joined")


class FileObject(Base):
    __tablename__ = "files"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("file"))
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))
    encounter_id: Mapped[str | None] = mapped_column(ForeignKey("encounters.id"), nullable=True, index=True)
    storage_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    purged_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    sample_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    boxes: Mapped[list | None] = mapped_column(JSONType, nullable=True)


class AuditEvent(Base):
    """Append-only, hash-chained. Updates/deletes are blocked by the ORM hook below
    and, on Postgres, by a database trigger (see db.APPEND_ONLY_SQL)."""

    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, index=True)
    actor_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(200))
    actor_role: Mapped[str] = mapped_column(String(20))
    facility_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(20), index=True)
    resource_type: Mapped[str] = mapped_column(String(32))
    resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    patient_code: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    detail: Mapped[str] = mapped_column(Text)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)


@event.listens_for(AuditEvent, "before_update")
@event.listens_for(AuditEvent, "before_delete")
def _audit_immutable(*_):
    raise PermissionError("audit_events is append-only")


class Reminder(Base):
    __tablename__ = "reminders"
    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=lambda: new_id("rem"))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    due_at: Mapped[datetime] = mapped_column(UTCDateTime)
    channel: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(12), default="scheduled")
    message: Mapped[str] = mapped_column(Text)
