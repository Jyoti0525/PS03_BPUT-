"""API schemas. Mirrors frontend/src/lib/types.ts — keep the two in sync."""

from datetime import date, datetime
from typing import Any, Literal

from pydantic import model_validator, BaseModel, ConfigDict, Field, field_validator

Role = Literal["doctor", "medical_officer", "nurse", "health_worker", "receptionist", "supervisor", "patient", "employer", "kiosk"]
Urgency = Literal["red", "yellow", "green"]
Category = Literal["normal", "maternal", "chronic"]
FileKind = Literal["report", "image", "audio"]
ExportFormat = Literal["pdf", "json", "csv", "fhir", "cda", "print"]

STAFF_ROLES = {"doctor", "medical_officer", "nurse", "health_worker", "receptionist", "supervisor"}
FacilityType = Literal[
    "phc", "chc", "sub_centre", "district_hospital", "hospital", "clinic", "health_camp", "company_clinic", "industrial_unit", "campus"
]
ORG_FACILITY_TYPES = {"company_clinic", "industrial_unit", "campus", "health_camp"}
OrgKind = Literal["company", "industrial", "campus", "ngo", "government_programme"]
FitnessStatus = Literal["fit", "fit_with_restrictions", "temporarily_unfit", "pending_review"]
REVIEWER_ROLES = {"doctor", "medical_officer", "nurse", "health_worker"}
DOCTOR_ROLES = {"doctor", "medical_officer"}  # the medical officer can do everything a doctor can, and receives escalations and alerts
# E2 sign-off limits: the highest urgency each role may confirm. A health worker (ASHA, ANM, MPW…) confirms GREEN only,
# a nurse up to YELLOW; RED needs a doctor or the medical officer.
SIGN_OFF = {"health_worker": "green", "nurse": "yellow", "doctor": "red", "medical_officer": "red"}
ADMIN_ROLES = {"receptionist", "supervisor"}  # front desk + supervisor (tokens, patients, duty)
SUPERVISOR_ROLES = {"supervisor"}
NO_AI_SCOPE = "no_ai"  # consent scope: the patient chose to continue without AI (G1)  # facility setup, kiosk links, devices, staff, audit, retention


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _no_id_numbers(v: str | None) -> str | None:
    """Staff free text: phone, Aadhaar, ABHA and e-mail are replaced before storage (G3). Names stay — staff
    legitimately refer to the patient, whose identity is on the registration record."""
    from .privacy import scrub

    return scrub(v, numbers_only=True)[0]


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


class MedicationReview(BaseModel):
    """Nurse/doctor decision on medicine names read from a strip or prescription (B10)."""
    confirm: list[str] = []  # generic names exactly as listed in medications_pending
    reject: list[str] = []


class ObservationIn(BaseModel):
    vitals: "Vitals | None" = None
    note: str | None = Field(default=None, max_length=1000)
    # Danger-sign check: the signs found present (finding ids). `exam_done` records that the check
    # was performed, so unchecked signs count as absent rather than unknown.
    signs: list[str] | None = None
    exam_done: bool = False

    _scrub = field_validator("note")(_no_id_numbers)


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
    role: Literal["doctor", "medical_officer", "nurse", "health_worker", "receptionist", "supervisor", "employer"]
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
    refer_to: str | None = None  # E4: where this specialty is referred when it is not on site


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
    patient_load: str = "normal"  # F2: low | normal | high
    capabilities: dict[str, bool]
    region: dict | None = None
    region_config: dict | None = None


_MMDD = r"^(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$"


class LocalFestival(BaseModel):
    name: str = Field(min_length=2, max_length=40)
    aliases: list[str] = Field(default_factory=list, max_length=10)
    dates: list[date] = Field(min_length=1, max_length=10)
    faith: str | None = Field(default=None, max_length=40)

    @field_validator("aliases")
    @classmethod
    def _aliases(cls, v: list[str]) -> list[str]:
        v = [a.strip() for a in v if a.strip()]
        if any(len(a) < 2 or len(a) > 40 for a in v):
            raise ValueError("each other name must be 2–40 characters")
        return v


class MonsoonDates(BaseModel):
    onset: str = Field(pattern=_MMDD)
    withdrawal: str = Field(pattern=_MMDD)

    @model_validator(mode="after")
    def _real(self):
        for v in (self.onset, self.withdrawal):
            m, d = map(int, v.split("-"))
            date(2024, m, d)  # raises for 02-30, 04-31
        if self.withdrawal <= self.onset:
            raise ValueError("monsoon withdrawal must come after onset in the same year")
        return self


class VisitDays(BaseModel):
    weekdays: list[int] = Field(default_factory=list, max_length=7)  # 0 = Monday
    monthdays: list[int] = Field(default_factory=list, max_length=31)

    @field_validator("weekdays")
    @classmethod
    def _wd(cls, v: list[int]) -> list[int]:
        if any(not 0 <= d <= 6 for d in v):
            raise ValueError("weekdays are 0 (Monday) to 6 (Sunday)")
        return sorted(set(v))

    @field_validator("monthdays")
    @classmethod
    def _md(cls, v: list[int]) -> list[int]:
        if any(not 1 <= d <= 28 for d in v):
            raise ValueError("days of the month are 1 to 28, so every month has them")
        return sorted(set(v))


class VisitCalendar(BaseModel):
    """E5: the days this facility holds each kind of follow-up visit, and the days it is closed."""

    anc_checkup: VisitDays | None = None
    chronic_checkin: VisitDays | None = None
    closed_weekdays: list[int] | None = None
    closed_dates: list[date] | None = Field(default=None, max_length=60)


class RegionConfig(BaseModel):
    """A facility's changes to its state's calendar (F5): local worker names, monsoon dates, local festivals."""

    cadres: dict[Literal["community", "nurse", "nutrition", "male", "cho"], str] = Field(default_factory=dict)
    monsoon: MonsoonDates | None = None
    festivals: list[LocalFestival] = Field(default_factory=list, max_length=20)
    visits: VisitCalendar | None = None

    @field_validator("cadres")
    @classmethod
    def _cadres(cls, v: dict) -> dict:
        v = {k: s.strip() for k, s in v.items() if s and s.strip()}
        if any(len(s) > 60 for s in v.values()):
            raise ValueError("a worker name must be at most 60 characters")
        return v


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
    patient_load: Literal["low", "normal", "high"] | None = None
    capabilities: dict[str, bool] | None = None
    region_config: RegionConfig | None = None


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
    data_origin: str = "SYNTHETIC"  # G8
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
    grievance_contact: str | None = None  # where to complain about data handling; shown on the patient slip


# ── Intake ─────────────────────────────────────────────
class SecondHearing(BaseModel):
    """B9: what the second speech engine heard in the same recording. Only its words are taken from the browser;
    the comparison is redone on the server (app/asr_check.py)."""
    engine: str = Field(max_length=160)
    text: str = Field(max_length=2000)  # in the speaker's language
    translation: str | None = Field(default=None, max_length=2000)  # English, by the server's translator


class SymptomEntry(BaseModel):
    text: str = Field(max_length=2000)
    original_text: str = Field(max_length=2000)
    language: str
    source: Literal["voice", "text", "icon"]
    confirmed_by_readback: bool = False
    engine: str | None = Field(default=None, max_length=160)  # speech/translation engine that produced `text`
    second_hearing: SecondHearing | None = None  # voice only: the other speech engine's transcript (B9)
    confidence: float | None = Field(default=None, ge=0, le=1)  # voice only: the speech engine's own confidence


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

    @model_validator(mode="after")
    def _plausible(self):
        """A8: units are fixed (°F, mmHg); a Celsius temperature is refused, never converted. None = not measured."""
        if self.bp_systolic is not None and self.bp_diastolic is not None and self.bp_systolic <= self.bp_diastolic:
            raise ValueError("BP systolic must be higher than diastolic")
        return self


class Maternal(BaseModel):
    gestation_weeks: int | None = Field(default=None, ge=1, le=42)
    lmp: str | None = None
    anc_visits: int | None = None
    next_checkup: str | None = None
    reminder_channel: Literal["sms", "voice", "none"] | None = "sms"
    # D4: whose phone the reminder goes to. A husband's or family phone gets a message that does not mention pregnancy.
    phone_belongs_to: Literal["self", "husband", "household", "none"] | None = None
    assigned_worker_id: str | None = None  # the ASHA / ANM who follows up a missed visit


Exposure = Literal["silica", "coal_dust", "cotton_dust", "asbestos", "other_dust", "noise", "chemicals", "pesticides", "heat"]
DUST_EXPOSURES = {"silica", "coal_dust", "cotton_dust", "asbestos", "other_dust"}


class Occupational(BaseModel):
    """D2 workplace screening: what the worker is exposed to and how their breathing compares with the last screening."""

    exposures: list[Exposure] = []
    years_exposed: float | None = Field(default=None, ge=0, le=60)
    cough_weeks: float | None = Field(default=None, ge=0, le=520)
    breathless_vs_last: Literal["better", "same", "worse", "unsure", "first"] | None = None
    ppe_issued: bool | None = None
    ppe_used: Literal["always", "sometimes", "never"] | None = None
    fev1_l: float | None = Field(default=None, ge=0.2, le=8)
    fvc_l: float | None = Field(default=None, ge=0.2, le=10)


class Chronic(BaseModel):
    condition: str
    last_checkup: str | None = None
    current_medicines: str | None = None
    feeling_vs_last: Literal["better", "same", "worse", "unsure"] = "unsure"
    # E5/E6: the next check-in. A missed one goes to the assigned health worker, then a reminder call.
    next_checkup: str | None = None
    assigned_worker_id: str | None = None


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
    occupational: Occupational | None = None
    # D3: where the patient sleeps on campus (hostel block). Used only to count fevers per place; never shown by name.
    cluster_key: str | None = Field(default=None, max_length=80)
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
    arrived_at: datetime | None = None  # None: filled in from home, not checked in yet
    data_origin: str = "SYNTHETIC"  # G8: SYNTHETIC or PUBLIC_SAMPLE, never real patient data
    home_advice: str | None = None  # from home only: "emergency" (go now / call 108) or "show_at_desk"; never a tier
    worker: "WorkerInfo | None" = None
    consent: ConsentOut | None = None
    can_confirm: bool = False  # whether this viewer's role may sign off this urgency (E2)
    sign_off: str | None = None  # lowest role that may confirm it


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
    arrived_at: datetime | None = None
    wait_minutes: int  # since arrival
    flag_count: int
    top_flags: list[str] = []  # the first flags in words, critical first, so the row reads without opening the case
    needs_check_count: int
    language: str
    escalation_due_at: datetime | None
    vitals_recorded: bool = False
    observation_count: int = 0
    order_reason: str = ""  # C3: why the case is at this place in the queue, in words
    sign_off: str | None = None  # the lowest role that may confirm this note (green: health worker, yellow: nurse, red: doctor)


class NotePatch(BaseModel):
    summary: str | None = Field(default=None, max_length=5000)
    missing_info: list[str] | None = None
    followup_questions: list[dict[str, Any]] | None = None


class EncounterPatch(BaseModel):
    referral_needed: bool | None = None


class OverrideIn(BaseModel):
    to_urgency: Urgency
    category: str = Field("Clinical judgement — other", min_length=3, max_length=120)
    reason: str = Field("", max_length=2000)  # required (15+ characters) only to lower the urgency

    @field_validator("reason")
    @classmethod
    def _strip(cls, v: str) -> str:
        return _no_id_numbers(v.strip())


class EscalationIn(BaseModel):
    to_role: Literal["senior_mo", "specialist", "doctor"]
    reason: str = Field(min_length=5, max_length=1000)

    _scrub = field_validator("reason")(_no_id_numbers)


class AckIn(BaseModel):
    note: str = ""

    _scrub = field_validator("note")(_no_id_numbers)


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
    due_at: datetime | None = None
    overdue: bool = False
    received_at: datetime | None = None
    received_by: str | None = None
    received_note: str | None = None
    received_via: str | None = None


class ReferralReceivedIn(BaseModel):
    """E4: care received at the destination. `confirmed_by`: who confirmed it (name, role, place)."""
    confirmed_by: str = Field(min_length=3, max_length=200)
    note: str = Field("", max_length=1000)


class ShareReceivedIn(ReferralReceivedIn):
    access_code: str = Field(min_length=6, max_length=6)


class UserPatch(BaseModel):
    role: Literal["doctor", "medical_officer", "nurse", "health_worker", "receptionist", "supervisor"] | None = None
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
    arrived_at: datetime | None = None
    wait_minutes: int  # since arrival; 0 while an intake from home is still expected


class KioskLinkIn(BaseModel):
    label: str = Field(min_length=2, max_length=120)
    for_home: bool = False


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
    for_home: bool = False


class KioskInfo(BaseModel):
    code: str
    label: str
    facility_id: str
    facility_name: str
    organisation_name: str | None = None
    district: str
    state: str
    languages: list[str]
    for_home: bool = False


class KioskFinderHit(BaseModel):
    code: str | None = None  # None: in the national directory but not on Jeevia yet (walk in)
    facility_name: str
    facility_type: str
    district: str
    state: str
    pincode: str | None = None
    km: float | None = None
    phone: str | None = None
    lat: float | None = None
    lon: float | None = None


class KioskSessionIn(BaseModel):
    device_id: str = Field(min_length=4, max_length=64)


class KioskIdentifyIn(BaseModel):
    patient_code: str = Field(min_length=4, max_length=20)
    phone: str = Field(pattern=r"^\d{10}$")


class ShareIn(BaseModel):
    hours: int = Field(default=72, ge=1, le=24 * 7)  # a referral hand-off needs days, not weeks
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


class AlertOut(ORM):
    id: str
    facility_id: str
    kind: str
    key: str
    to_role: str
    assigned_to: str | None = None
    title: str
    detail: dict[str, Any]
    status: str
    raised_at: datetime
    updated_at: datetime
    acknowledged_by: str | None = None
    acknowledged_at: datetime | None = None
    ack_note: str | None = None
    resolved_at: datetime | None = None


class CapacityOut(BaseModel):
    open_red: int
    doctors_on_duty: int
    over: bool
    reds: list[dict[str, Any]]  # token, wait, order reason; no names
    alert: AlertOut | None = None


class FollowupOut(BaseModel):
    id: str
    patient_id: str
    patient_code: str
    patient_name: str
    village: str | None
    phone: str | None
    phone_belongs_to: str | None
    kind: str
    due_at: datetime
    status: str
    missed_at: datetime | None
    attempts: list[dict[str, Any]]
    assigned_to: str | None
    assigned_name: str | None
    gestation_weeks: int | None
    call_script: str | None  # what the call would say; None when there is no phone to call
    resolved_at: datetime | None
    programme: str  # maternal | chronic
    condition: str | None = None  # chronic: the long-term condition
    who_calls: dict[str, str]  # {who: agent | human | home_visit, why}


class CallStartIn(BaseModel):
    operator: Literal["agent", "human"] = "agent"  # human: a person phones and reads the same script
    # Defaults to the patient's language when it is one of these (the 11 languages Sarvam's Bulbul voice speaks)
    language: Literal["en", "hi", "or", "bn", "ta", "te", "gu", "kn", "ml", "mr", "pa"] | None = None
    # phone: Twilio rings the demo phone and the patient answers on the keypad (agent calls only)
    channel: Literal["browser", "phone"] = "browser"


class CallAnswerIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)  # what was said (in English when translated)
    original_text: str | None = Field(default=None, max_length=500)  # in the patient's language, when transcribed

    _scrub = field_validator("text", "original_text")(_no_id_numbers)


class CallEndIn(BaseModel):
    outcome: Literal["no_answer", "hung_up"]


class CallOut(BaseModel):
    id: str
    reminder_id: str
    patient_name: str
    patient_code: str
    programme: str
    operator: str
    language: str
    audience: str
    status: str
    outcome: str | None
    turns: list[dict[str, Any]]
    red_flags: list[dict[str, Any]] | None
    notes: dict[str, Any] | None
    expects: str | None  # yes_no | free | None (ended)
    alert_id: str | None
    started_at: datetime
    ended_at: datetime | None
    sources: list[dict[str, str]]
    voice: str = "device"  # sarvam: GET /calls/{id}/turns/{i}/audio speaks each agent line; device: the browser's own voice
    channel: str = "browser"  # phone: a real call through Twilio; the page follows it


class FollowupAttemptIn(BaseModel):
    outcome: Literal["reached", "not_reached", "came"]
    note: str = Field(default="", max_length=500)

    _scrub = field_validator("note")(_no_id_numbers)


class CohortOut(ORM):
    id: str
    name: str
    employer_name: str
    screening_type: str
    workers: list[dict[str, Any]]


EncounterOut.model_rebuild()
ObservationIn.model_rebuild()


class ClaimIn(BaseModel):
    reference: str = Field(min_length=4, max_length=40)
