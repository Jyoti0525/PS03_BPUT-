"""API schemas. Mirrors frontend/src/lib/types.ts — keep the two in sync."""

from datetime import datetime
from typing import Any, Literal

from pydantic import model_validator, BaseModel, ConfigDict, Field, field_validator

Role = Literal["doctor", "nurse", "receptionist", "supervisor", "patient", "employer", "kiosk"]
Urgency = Literal["red", "yellow", "green"]
Category = Literal["normal", "maternal", "chronic"]
FileKind = Literal["report", "image", "audio"]
ExportFormat = Literal["pdf", "json", "csv", "fhir", "print"]

STAFF_ROLES = {"doctor", "nurse", "receptionist", "supervisor"}
FacilityType = Literal[
    "phc", "chc", "sub_centre", "district_hospital", "hospital", "clinic", "health_camp", "company_clinic", "industrial_unit", "campus"
]
ORG_FACILITY_TYPES = {"company_clinic", "industrial_unit", "campus", "health_camp"}
OrgKind = Literal["company", "industrial", "campus", "ngo", "government_programme"]
FitnessStatus = Literal["fit", "fit_with_restrictions", "temporarily_unfit", "pending_review"]
REVIEWER_ROLES = {"doctor", "nurse"}
ADMIN_ROLES = {"receptionist", "supervisor"}  # front desk + supervisor (tokens, patients, duty)
SUPERVISOR_ROLES = {"supervisor"}  # facility setup, kiosk links, devices, staff, audit, retention


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
    is_active: bool = True
    organisation_id: str | None = None
    on_duty: bool = True
    duty_changed_at: datetime | None = None
    email: str | None = None
    phone_verified: bool = True
    created_at: datetime


class MePatch(BaseModel):
    language: str | None = Field(default=None, min_length=2, max_length=8)


class DutyIn(BaseModel):
    on_duty: bool


class ObservationIn(BaseModel):
    vitals: "Vitals | None" = None
    note: str | None = Field(default=None, max_length=1000)
    # Danger-sign check: the signs found present (finding ids). `exam_done` records that the check
    # was performed, so unchecked signs count as absent rather than unknown.
    signs: list[str] | None = None
    exam_done: bool = False


class Tokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


EMAIL_RE = r"^[^@\s]{1,64}@[^@\s]+\.[A-Za-z]{2,}$"


class OtpRequest(BaseModel):
    """Exactly one of phone (SMS code) or email (email code)."""

    phone: str | None = Field(default=None, pattern=r"^\d{10}$")
    email: str | None = Field(default=None, max_length=254, pattern=EMAIL_RE)
    purpose: Literal["signin", "register"] = "signin"
    language: str | None = Field(default=None, max_length=8)  # language of the email when the address is new

    @model_validator(mode="after")
    def one_channel(self):
        if bool(self.phone) == bool(self.email):
            raise ValueError("Give either a mobile number or an email address")
        if self.email:
            self.email = self.email.strip().lower()
        return self


class EmailStartIn(BaseModel):
    email: str = Field(max_length=254, pattern=EMAIL_RE)
    language: str | None = Field(default=None, max_length=8)


class EmailConfirmIn(BaseModel):
    challenge_id: str
    code: str = Field(pattern=r"^\d{6}$")


class AuthOptions(BaseModel):
    sms: bool
    email: bool


class OtpChallengeOut(BaseModel):
    challenge_id: str
    expires_in: int
    dev_code: str | None = None


class OtpVerify(BaseModel):
    challenge_id: str
    code: str = Field(pattern=r"^\d{6}$")
    # "register": the number must be new — an existing account is never signed in from the sign-up form.
    purpose: Literal["signin", "register"] = "signin"


class AuthResult(BaseModel):
    tokens: Tokens
    user: UserOut


class OtpVerifyOut(BaseModel):
    status: Literal["authenticated", "new_user", "pin_required", "pin_setup_required"]
    tokens: Tokens | None = None
    user: UserOut | None = None
    registration_token: str | None = None
    pin_token: str | None = None  # for the PIN step (valid a few minutes)
    name: str | None = None
    can_reset_pin: bool | None = None  # supervisors and employers may reset their own PIN after OTP


class NewFacility(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    type: FacilityType
    district: str = Field(min_length=2, max_length=100)
    state: str = Field(min_length=2, max_length=100)
    pincode: str | None = Field(default=None, pattern=r"^\d{6}$")
    address: str | None = Field(default=None, max_length=300)
    referral_destination: str | None = None


class NewOrganisation(BaseModel):
    name: str = Field(min_length=3, max_length=200)
    kind: OrgKind
    registration_no: str | None = Field(default=None, max_length=64)
    state: str = Field(min_length=2, max_length=100)
    district: str = Field(min_length=2, max_length=100)
    address: str | None = Field(default=None, max_length=300)
    contact_phone: str | None = Field(default=None, pattern=r"^\d{10}$")
    facility: NewFacility


class RegisterIn(BaseModel):
    registration_token: str
    # Required when the registration token came from an email code (the mobile number is still recorded).
    phone: str | None = Field(default=None, pattern=r"^\d{10}$")
    name: str = Field(min_length=2, max_length=200)
    role: Literal["doctor", "nurse", "receptionist", "supervisor", "patient", "employer"]
    facility_id: str | None = None
    registration_no: str | None = None
    language: str = "en"
    accepted_terms: bool
    device_id: str | None = None
    pin: str | None = Field(default=None, pattern=r"^\d{4,6}$")  # required for staff and employers
    # Where the user works — exactly one of these:
    directory_ref: str | None = None  # a facility from the national directory (activated on first join)
    new_facility: NewFacility | None = None  # supervisor adds a missing public facility
    new_organisation: NewOrganisation | None = None  # employer registers their organisation and first workplace


class PinStepIn(BaseModel):
    pin_token: str
    pin: str = Field(pattern=r"^\d{4,6}$")


class PinForgotIn(BaseModel):
    pin_token: str


class PinChangeIn(BaseModel):
    current_pin: str = Field(pattern=r"^\d{4,6}$")
    new_pin: str = Field(pattern=r"^\d{4,6}$")


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
    source: str = "sample"
    verified: bool = False
    organisation_id: str | None = None
    directory_ref: str | None = None
    pincode: str | None = None
    address: str | None = None
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
    type: FacilityType | None = None
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
    employee_code: str | None = Field(default=None, max_length=40)


class PatientPatch(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    age: int | None = Field(default=None, ge=0, le=120)
    sex: Literal["F", "M", "O"] | None = None
    phone: str | None = Field(default=None, pattern=r"^\d{10}$")
    language: str | None = None
    village: str | None = Field(default=None, max_length=120)


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
    organisation_id: str | None = None
    employee_code: str | None = None
    department: str | None = None
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
    engine: str | None = Field(default=None, max_length=80)  # speech/translation engine that produced `text`


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
    avpu: Literal["A", "V", "P", "U"] | None = None  # Alert / responds to Voice / to Pain / Unresponsive


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
    age_months: int | None = Field(default=None, ge=0, le=59)  # under-5s: exact months for infant rules
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
    token: str | None = None
    channel: str = "staff_kiosk"
    worker: "WorkerInfo | None" = None
    consent: ConsentOut | None = None


class QueueItem(BaseModel):
    encounter_id: str
    token: str | None = None
    channel: str = "staff_kiosk"
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
    vitals_recorded: bool = False
    observation_count: int = 0


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


class UserPatch(BaseModel):
    role: Literal["doctor", "nurse", "receptionist", "supervisor"] | None = None
    is_active: bool | None = None


class DirectoryHit(BaseModel):
    key: str
    name: str
    kind: str
    kind_label: str
    type: str
    ownership: str
    state: str
    district: str | None
    city: str | None
    pincode: str | None
    source: str
    directory_ref: str | None
    facility_id: str | None
    organisation_name: str | None
    verified: bool


class OrganisationOut(ORM):
    id: str
    name: str
    kind: str
    registration_no: str | None
    state: str
    district: str
    address: str | None
    contact_phone: str | None
    verified: bool
    created_at: datetime


class OrganisationPatch(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=200)
    registration_no: str | None = Field(default=None, max_length=64)
    address: str | None = Field(default=None, max_length=300)
    contact_phone: str | None = Field(default=None, pattern=r"^\d{10}$")


class OrganisationHome(BaseModel):
    organisation: OrganisationOut
    facilities: list[FacilityOut]


class WorkerIn(BaseModel):
    employee_code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=2, max_length=200)
    age: int = Field(ge=14, le=100)
    sex: Literal["F", "M", "O"]
    department: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, pattern=r"^\d{10}$")
    language: str = "en"


class WorkerPatch(BaseModel):
    department: str | None = Field(default=None, max_length=120)
    name: str | None = Field(default=None, min_length=2, max_length=200)
    phone: str | None = Field(default=None, pattern=r"^\d{10}$")
    active: bool | None = None  # false removes the worker from the roster (the health record stays)


class WorkerOut(BaseModel):
    employee_code: str
    name: str
    department: str | None
    patient_code: str
    fitness_status: str
    restrictions: str | None
    valid_until: str | None
    last_assessed_at: datetime | None
    assessed_by: str | None


class WorkerImportIn(BaseModel):
    csv: str = Field(max_length=500_000)


class WorkerImportOut(BaseModel):
    created: int
    updated: int
    errors: list[str]


class FitnessIn(BaseModel):
    status: FitnessStatus
    restrictions: str | None = Field(default=None, max_length=300)
    valid_until: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class FitnessOut(ORM):
    id: str
    status: str
    restrictions: str | None
    valid_until: str | None
    assessed_by: str
    assessed_at: datetime


class WorkerInfo(BaseModel):
    organisation_id: str
    organisation_name: str
    employee_code: str | None
    department: str | None
    latest: FitnessOut | None


class TokenBoardItem(BaseModel):
    """Operational view of today's tokens — no clinical content, safe for front-desk staff."""

    encounter_id: str
    token: str | None
    patient_id: str
    patient_name: str
    patient_code: str
    status: str
    channel: str
    created_at: datetime
    wait_minutes: int


class KioskLinkIn(BaseModel):
    label: str = Field(min_length=2, max_length=120)


class KioskLinkOut(BaseModel):
    id: str
    code: str
    label: str
    facility_id: str
    url: str
    created_by: str
    created_at: datetime
    revoked: bool
    last_used_at: datetime | None
    sessions: int
    intakes_today: int


class KioskInfo(BaseModel):
    code: str
    label: str
    facility_id: str
    facility_name: str
    organisation_name: str | None = None
    district: str
    state: str
    languages: list[str]


class KioskSessionIn(BaseModel):
    device_id: str = Field(min_length=4, max_length=64)


class KioskIdentifyIn(BaseModel):
    patient_code: str = Field(min_length=4, max_length=20)
    phone: str = Field(pattern=r"^\d{10}$")


class ShareIn(BaseModel):
    hours: int = Field(default=72, ge=1, le=24 * 30)
    purpose: Literal["referral", "handoff"] = "referral"


class ShareOut(BaseModel):
    id: str
    url: str
    access_code: str | None = None  # returned only once, at creation
    purpose: str
    created_by: str
    created_at: datetime
    expires_at: datetime
    revoked: bool
    views: int


class ShareOpenIn(BaseModel):
    access_code: str = Field(pattern=r"^\d{6}$")


class SharedDocument(BaseModel):
    id: str
    filename: str
    kind: str
    content_type: str
    uploaded_at: datetime
    url: str | None


class SharedSummary(BaseModel):
    """What a receiving clinician sees after scanning the QR. Clinician-facing by design."""

    facility: dict[str, Any]
    patient: dict[str, Any]
    encounter: dict[str, Any]
    note: dict[str, Any] | None
    referral: dict[str, Any] | None
    documents: list[SharedDocument]
    shared_by: str
    expires_at: datetime
    disclaimer: str


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
    # Capture feedback only (engine, image quality, how many values were read) — never the values
    # or their interpretation, which stay reviewer-facing.
    read_quality: dict | None = None


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


EncounterOut.model_rebuild()
ObservationIn.model_rebuild()
