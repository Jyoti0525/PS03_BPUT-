"""API schemas. Mirrors frontend/src/lib/types.ts — keep the two in sync."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Role = Literal["doctor", "nurse", "receptionist", "supervisor", "patient", "employer", "kiosk"]
Urgency = Literal["red", "yellow", "green"]
Category = Literal["normal", "maternal", "chronic"]
FileKind = Literal["report", "image", "audio"]
ExportFormat = Literal["pdf", "json", "csv", "fhir", "print"]

STAFF_ROLES = {"doctor", "nurse", "receptionist", "supervisor"}
REVIEWER_ROLES = {"doctor", "nurse"}
ADMIN_ROLES = {"receptionist", "supervisor"}


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Auth ────────────────────────────────────────────────
class UserOut(ORM):
    id: str
    phone: str
    name: str
    role: Role
    facility_id: str | None
    registration_no: str | None = None
    language: str
    has_pin: bool = False
    created_at: datetime


class Tokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class OtpRequest(BaseModel):
    phone: str = Field(pattern=r"^\d{10}$")


class OtpChallengeOut(BaseModel):
    challenge_id: str
    expires_in: int
    dev_code: str | None = None


class OtpVerify(BaseModel):
    challenge_id: str
    code: str = Field(pattern=r"^\d{6}$")


class AuthResult(BaseModel):
    tokens: Tokens
    user: UserOut


class OtpVerifyOut(BaseModel):
    status: Literal["authenticated", "new_user"]
    tokens: Tokens | None = None
    user: UserOut | None = None
    registration_token: str | None = None


class RegisterIn(BaseModel):
    registration_token: str
    name: str = Field(min_length=2, max_length=200)
    role: Literal["doctor", "nurse", "receptionist", "supervisor", "patient", "employer"]
    facility_id: str | None = None
    registration_no: str | None = None
    language: str = "en"
    accepted_terms: bool
    device_id: str | None = None


class PinSet(BaseModel):
    pin: str = Field(pattern=r"^\d{4,6}$")
    device_id: str = Field(min_length=4, max_length=64)


class PinLogin(BaseModel):
    phone: str = Field(pattern=r"^\d{10}$")
    pin: str = Field(pattern=r"^\d{4,6}$")
    device_id: str


class RefreshIn(BaseModel):
    refresh_token: str


# ── Facility / devices ─────────────────────────────────
class Specialist(BaseModel):
    key: str
    label: str
    available: bool
    schedule: str | None = None


class FacilityOut(ORM):
    id: str
    name: str
    type: str
    district: str
    state: str
    languages: list[str]
    specialists: list[Specialist]
    referral_destination: str
    beds_total: int
    beds_occupied: int
    offline_mode: bool
    capabilities: dict[str, bool]


class FacilityPatch(BaseModel):
    name: str | None = None
    type: Literal["phc", "chc", "district_hospital", "health_camp", "company_clinic", "industrial_unit", "campus"] | None = None
    district: str | None = None
    state: str | None = None
    languages: list[str] | None = None
    specialists: list[Specialist] | None = None
    referral_destination: str | None = None
    beds_total: int | None = Field(default=None, ge=0)
    beds_occupied: int | None = Field(default=None, ge=0)
    offline_mode: bool | None = None
    capabilities: dict[str, bool] | None = None


class FacilityStats(BaseModel):
    facility_id: str
    today_total: int
    by_urgency: dict[str, int]
    avg_wait_minutes: int
    open_escalations: int
    referrals_today: int
    offline_synced_today: int


class DeviceIn(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    device_id: str = Field(min_length=4, max_length=64)


class DeviceOut(ORM):
    id: str
    label: str
    facility_id: str
    bound_by: str
    bound_at: datetime
    last_seen_at: datetime | None
    revoked: bool


# ── Patients / consent ─────────────────────────────────
class PatientIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    age: int = Field(ge=0, le=120)
    sex: Literal["F", "M", "O"]
    phone: str | None = Field(default=None, pattern=r"^\d{10}$")
    language: str = "en"
    category: Category = "normal"
    village: str | None = None
    employer_id: str | None = None


class PatientOut(ORM):
    id: str
    code: str
    name: str
    age: int
    sex: str
    phone: str | None
    language: str
    category: Category
    village: str | None = None
    employer_id: str | None = None
    created_at: datetime


class PatientCandidate(BaseModel):
    patient: PatientOut
    last_visit_at: datetime | None
    match_reason: str


class ConsentIn(BaseModel):
    patient_id: str
    mode: Literal["self", "proxy"]
    proxy_name: str | None = None
    proxy_relation: str | None = None
    privacy_context: Literal["private", "shared_space", "assisted"]
    language: str
    scopes: list[str]


class ConsentOut(ORM):
    id: str
    patient_id: str
    mode: str
    proxy_name: str | None
    proxy_relation: str | None
    privacy_context: str
    language: str
    scopes: list[str]
    captured_by: str
    captured_at: datetime


# ── Intake ─────────────────────────────────────────────
class SymptomEntry(BaseModel):
    text: str = Field(max_length=2000)
    original_text: str = Field(max_length=2000)
    language: str
    source: Literal["voice", "text", "icon"]
    confirmed_by_readback: bool = False


class IntakeAnswer(BaseModel):
    qid: str
    question: str
    answer: str


class Vitals(BaseModel):
    bp_systolic: float | None = Field(default=None, ge=40, le=300)
    bp_diastolic: float | None = Field(default=None, ge=20, le=200)
    pulse: float | None = Field(default=None, ge=20, le=250)
    temp_f: float | None = Field(default=None, ge=90, le=110)
    spo2: float | None = Field(default=None, ge=50, le=100)
    resp_rate: float | None = Field(default=None, ge=4, le=80)
    glucose: float | None = Field(default=None, ge=10, le=1000)


class Maternal(BaseModel):
    gestation_weeks: int | None = Field(default=None, ge=1, le=42)
    lmp: str | None = None
    anc_visits: int | None = None
    next_checkup: str | None = None
    reminder_channel: Literal["sms", "voice", "none"] | None = "sms"


class Chronic(BaseModel):
    condition: str
    last_checkup: str | None = None
    current_medicines: str | None = None
    feeling_vs_last: Literal["better", "same", "worse", "unsure"] = "unsure"


class IntakeIn(BaseModel):
    patient_id: str
    facility_id: str
    category: Category
    language: str
    chief_complaint: str = Field(min_length=1, max_length=500)
    symptoms: list[SymptomEntry] = []
    selected_symptoms: list[str] = []
    duration: str | None = None
    severity: int | None = Field(default=None, ge=0, le=10)
    answers: list[IntakeAnswer] = []
    file_ids: list[str] = []
    vitals: Vitals | None = None
    maternal: Maternal | None = None
    chronic: Chronic | None = None
    consent_id: str | None = None
    client_ref: str = Field(min_length=4, max_length=80)
    captured_offline: bool = False
    captured_at: datetime | None = None


# ── Encounters ─────────────────────────────────────────
class EncounterOut(BaseModel):
    id: str
    patient: PatientOut
    facility_id: str
    category: Category
    status: str
    chief_complaint: str
    created_at: datetime
    urgency: Urgency | None
    urgency_source: str
    note: dict[str, Any] | None
    intake: dict[str, Any] | None
    override: dict[str, Any] | None = None
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    referral_needed: bool | None = None
    specialist_required: str | None = None
    escalation_due_at: datetime | None = None
    consent: ConsentOut | None = None


class QueueItem(BaseModel):
    encounter_id: str
    patient_code: str
    patient_name: str
    age: int
    sex: str
    category: Category
    chief_complaint: str
    urgency: Urgency
    status: str
    created_at: datetime
    wait_minutes: int
    flag_count: int
    needs_check_count: int
    language: str
    escalation_due_at: datetime | None


class NotePatch(BaseModel):
    summary: str | None = Field(default=None, max_length=5000)
    missing_info: list[str] | None = None
    followup_questions: list[dict[str, Any]] | None = None


class EncounterPatch(BaseModel):
    referral_needed: bool | None = None


class OverrideIn(BaseModel):
    to_urgency: Urgency
    category: str = Field(min_length=3, max_length=120)
    reason: str = Field(min_length=15, max_length=2000)

    @field_validator("reason")
    @classmethod
    def _strip(cls, v: str) -> str:
        if len(v.strip()) < 15:
            raise ValueError("A written reason of at least 15 characters is required")
        return v.strip()


class EscalationIn(BaseModel):
    to_role: Literal["senior_mo", "specialist", "doctor"]
    reason: str = Field(min_length=5, max_length=1000)


class AckIn(BaseModel):
    note: str = ""


class EscalationOut(BaseModel):
    id: str
    encounter_id: str
    patient_name: str
    urgency: Urgency
    raised_by: str
    raised_at: datetime
    to_role: str
    reason: str
    auto: bool
    status: str
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    ack_note: str | None = None


class ReferralIn(BaseModel):
    destination: str = Field(min_length=2, max_length=300)
    specialty: str = Field(min_length=2, max_length=120)
    reason: str = Field(min_length=2, max_length=1000)
    transport: Literal["self", "ambulance_108", "facility_vehicle"]
    note_text: str = Field(min_length=10, max_length=20000)


class ReferralOut(BaseModel):
    id: str
    encounter_id: str
    patient_name: str
    destination: str
    specialty: str
    reason: str
    note_text: str
    transport: str
    created_by: str
    created_at: datetime
    status: str


class FileOut(BaseModel):
    id: str
    filename: str
    content_type: str
    size: int
    kind: FileKind
    encounter_id: str | None
    uploaded_at: datetime
    expires_at: datetime
    purged_at: datetime | None
    url: str | None = None


class AuditOut(ORM):
    id: int
    ts: datetime
    actor_id: str | None
    actor_name: str
    actor_role: str
    action: str
    resource_type: str
    resource_id: str | None
    patient_code: str | None
    detail: str
    prev_hash: str
    hash: str


class AuditVerify(BaseModel):
    ok: bool
    checked: int
    broken_at: int | None


class RetentionOut(BaseModel):
    policy_hours: dict[str, int]
    active: int
    pending_purge: int
    purged_last_7d: int
    files: list[FileOut]


class ReminderOut(ORM):
    id: str
    patient_id: str
    kind: str
    due_at: datetime
    channel: str
    status: str
    message: str


class MyRecord(BaseModel):
    patient: PatientOut
    encounters: list[EncounterOut]
    reminders: list[ReminderOut]


class CohortOut(ORM):
    id: str
    name: str
    employer_name: str
    screening_type: str
    workers: list[dict[str, Any]]
