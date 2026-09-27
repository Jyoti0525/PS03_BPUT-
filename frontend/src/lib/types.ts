/**
 * Jeevia API contract.
 *
 * These types mirror the Pydantic schemas in `backend/app/schemas.py`.
 * Both the in-browser mock adapter and the live FastAPI adapter return these shapes,
 * so every screen can be built against mocks and switched to the live API by env var.
 */

export type Role =
  | "doctor"
  | "nurse"
  | "receptionist"
  | "supervisor"
  | "patient"
  | "employer"
  | "kiosk";

export const STAFF_ROLES: Role[] = ["doctor", "nurse", "receptionist", "supervisor"];
export const REVIEWER_ROLES: Role[] = ["doctor", "nurse"];
export const ADMIN_ROLES: Role[] = ["receptionist", "supervisor"];

/** Urgency is assigned ONLY by the deterministic rules engine (ATP / IMCI), never by the LLM. */
export type Urgency = "red" | "yellow" | "green";
export type PatientCategory = "normal" | "maternal" | "chronic";
export type EncounterStatus =
  | "queued"
  | "in_review"
  | "confirmed"
  | "escalated"
  | "referred"
  | "closed";

export type FacilityType =
  | "phc"
  | "chc"
  | "sub_centre"
  | "district_hospital"
  | "hospital"
  | "clinic"
  | "health_camp"
  | "company_clinic"
  | "industrial_unit"
  | "campus";

/** Workplaces that exist only after their organisation registers them. */
export const ORG_FACILITY_TYPES: FacilityType[] = ["company_clinic", "industrial_unit", "campus", "health_camp"];

export type OrgKind = "company" | "industrial" | "campus" | "ngo" | "government_programme";

export interface User {
  id: string;
  phone: string;
  name: string;
  role: Role;
  facility_id: string | null;
  registration_no?: string | null;
  language: string;
  has_pin: boolean;
  is_active?: boolean;
  organisation_id?: string | null;
  /** Doctors and nurses: on duty right now (front-desk time management). */
  on_duty?: boolean;
  duty_changed_at?: string | null;
  created_at: string;
}

/** Bedside observation recorded by a nurse or doctor (kept on the note). */
export interface Observation {
  by: string;
  role: Role;
  at: string;
  vitals: VitalsInput;
  note: string | null;
}

export interface Tokens {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
}

export interface OtpChallenge {
  challenge_id: string;
  expires_in: number;
  /** Only returned when the backend runs with the mock SMS provider. */
  dev_code?: string | null;
}

export type OtpVerifyResult =
  | { status: "authenticated"; tokens: Tokens; user: User }
  | { status: "new_user"; registration_token: string }
  /** Staff and employers: phone verified, now the account PIN (second factor). */
  | { status: "pin_required" | "pin_setup_required"; pin_token: string; name: string; can_reset_pin: boolean };

/** Roles that sign in with phone OTP + PIN. */
export const PIN_ROLES: Role[] = ["doctor", "nurse", "receptionist", "supervisor", "employer"];

export interface RegisterInput {
  registration_token: string;
  name: string;
  role: Exclude<Role, "kiosk">;
  facility_id: string | null;
  registration_no?: string | null;
  language: string;
  accepted_terms: boolean;
  device_id?: string | null;
  /** Account PIN (second factor) — required for staff and employers. */
  pin?: string | null;
  /** Where the user works — exactly one of facility_id, directory_ref, new_facility (supervisor), new_organisation (employer). */
  directory_ref?: string | null;
  new_facility?: NewFacilityInput | null;
  new_organisation?: NewOrganisationInput | null;
}

export interface NewFacilityInput {
  name: string;
  type: FacilityType;
  district: string;
  state: string;
  pincode?: string | null;
  address?: string | null;
  referral_destination?: string | null;
}

export interface NewOrganisationInput {
  name: string;
  kind: OrgKind;
  registration_no?: string | null;
  state: string;
  district: string;
  address?: string | null;
  contact_phone?: string | null;
  facility: NewFacilityInput;
}

/** One result in the workplace search (national directory or a registered workplace). */
export interface DirectoryHit {
  key: string;
  name: string;
  kind: string;
  kind_label: string;
  type: FacilityType;
  ownership: "public" | "private" | "unknown";
  state: string;
  district: string | null;
  city: string | null;
  pincode: string | null;
  source: "directory" | "organisation" | "user_added" | "sample";
  directory_ref: string | null;
  facility_id: string | null;
  organisation_name: string | null;
  verified: boolean;
}

export interface Organisation {
  id: string;
  name: string;
  kind: OrgKind;
  registration_no: string | null;
  state: string;
  district: string;
  address: string | null;
  contact_phone: string | null;
  verified: boolean;
  created_at: string;
}

export interface Worker {
  employee_code: string;
  name: string;
  department: string | null;
  patient_code: string;
  fitness_status: FitnessStatus;
  restrictions: string | null;
  valid_until: string | null;
  last_assessed_at: string | null;
  assessed_by: string | null;
}

export interface WorkerInput {
  employee_code: string;
  name: string;
  age: number;
  sex: "F" | "M" | "O";
  department?: string | null;
  phone?: string | null;
}

export interface FitnessRecord {
  id: string;
  status: FitnessStatus;
  restrictions: string | null;
  valid_until: string | null;
  assessed_by: string;
  assessed_at: string;
}

export interface WorkerInfo {
  organisation_id: string;
  organisation_name: string;
  employee_code: string | null;
  department: string | null;
  latest: FitnessRecord | null;
}

export interface Specialist {
  key: string;
  label: string;
  available: boolean;
  schedule?: string | null;
}

export interface Facility {
  id: string;
  name: string;
  type: FacilityType;
  district: string;
  state: string;
  languages: string[];
  specialists: Specialist[];
  referral_destination: string;
  beds_total: number;
  beds_occupied: number;
  offline_mode: boolean;
  /** Answers to the "what services do you have" setup questions. */
  capabilities: Record<string, boolean>;
  source?: "sample" | "directory" | "organisation" | "user_added";
  verified?: boolean;
  organisation_id?: string | null;
  directory_ref?: string | null;
  pincode?: string | null;
  address?: string | null;
}

export interface Device {
  id: string;
  label: string;
  facility_id: string;
  bound_by: string;
  bound_at: string;
  last_seen_at: string | null;
  revoked: boolean;
}

export interface Patient {
  id: string;
  code: string; // JVA-xxxx, printed on the token / QR
  name: string;
  age: number;
  sex: "F" | "M" | "O";
  phone: string | null;
  language: string;
  category: PatientCategory;
  village?: string | null;
  employer_id?: string | null;
  organisation_id?: string | null;
  employee_code?: string | null;
  department?: string | null;
  created_at: string;
}

export interface PatientCandidate {
  patient: Patient;
  last_visit_at: string | null;
  match_reason: string;
}

export type ConsentMode = "self" | "proxy";
export type PrivacyContext = "private" | "shared_space" | "assisted";

export interface ConsentInput {
  patient_id: string;
  mode: ConsentMode;
  proxy_name?: string | null;
  proxy_relation?: string | null;
  privacy_context: PrivacyContext;
  language: string;
  scopes: string[];
}

export interface Consent extends ConsentInput {
  id: string;
  captured_by: string;
  captured_at: string;
}

/* ── Intake ───────────────────────────────────────────── */

export type InputSource = "voice" | "text" | "icon";

export interface SymptomEntry {
  text: string; // working-language text
  original_text: string; // raw text as spoken/typed, kept for audit
  language: string;
  source: InputSource;
  confirmed_by_readback: boolean;
}

export interface IntakeAnswer {
  qid: string;
  question: string;
  answer: string;
}

export interface MaternalIntake {
  gestation_weeks: number | null;
  lmp?: string | null;
  anc_visits?: number | null;
  next_checkup?: string | null;
  reminder_channel?: "sms" | "voice" | "none";
}

export interface ChronicIntake {
  condition: string;
  last_checkup?: string | null;
  current_medicines?: string | null;
  feeling_vs_last: "better" | "same" | "worse" | "unsure";
}

export interface VitalsInput {
  bp_systolic?: number | null;
  bp_diastolic?: number | null;
  pulse?: number | null;
  temp_f?: number | null;
  spo2?: number | null;
  resp_rate?: number | null;
  glucose?: number | null;
}

export interface IntakePayload {
  patient_id: string;
  facility_id: string;
  category: PatientCategory;
  language: string;
  chief_complaint: string;
  symptoms: SymptomEntry[];
  selected_symptoms: string[];
  duration: string | null;
  severity: number | null;
  answers: IntakeAnswer[];
  file_ids: string[];
  vitals?: VitalsInput | null;
  maternal?: MaternalIntake | null;
  chronic?: ChronicIntake | null;
  consent_id: string | null;
  /** Client-generated id so offline replays are idempotent. */
  client_ref: string;
  captured_offline?: boolean;
  /** When the intake was actually captured (differs from submit time for offline replays). */
  captured_at?: string | null;
}

/* ── Triage note ──────────────────────────────────────── */

export type SourceKind = "image_crop" | "transcript" | "sensor" | "manual";

export interface SourceRef {
  kind: SourceKind;
  engine: string;
  file_id?: string | null;
  /** Normalised crop box [x, y, w, h] in 0..1 of the source image. */
  bbox?: [number, number, number, number] | null;
  /** Text around the value as it appeared in the report, for the crop preview. */
  crop_text?: string | null;
  transcript_excerpt?: string | null;
  original_excerpt?: string | null;
  timestamp?: string | null;
}

export type ValueStatus = "normal" | "borderline" | "abnormal";

export interface ExtractedValue {
  id: string;
  label: string;
  value: string;
  unit?: string | null;
  reference?: string | null;
  status: ValueStatus;
  needs_check: boolean;
  source: SourceRef;
}

export type FlagSeverity = "critical" | "warning" | "info";

/** Reviewers see flags, never model confidence percentages. */
export interface Flag {
  code: string;
  label: string;
  severity: FlagSeverity;
  reason: string;
}

export interface RuleHit {
  rule_id: string;
  protocol: "ATP" | "IMCI" | "MATERNAL" | "FACILITY";
  description: string;
  urgency: Urgency;
}

export interface Disagreement {
  field: string;
  values: { engine: string; value: string }[];
  action: string;
}

export interface TrendRow {
  parameter: string;
  points: { label: string; value: number }[];
  direction: "worse" | "better" | "stable";
}

export interface TimelineEvent {
  when: string;
  event: string;
}

export interface FollowUpQuestion {
  tag: string;
  question: string;
  for_role: "nurse" | "doctor" | "health_worker";
}

export interface TriageNote {
  summary: string;
  flags: Flag[];
  rules_fired: RuleHit[];
  vitals: ExtractedValue[];
  labs: ExtractedValue[];
  timeline: TimelineEvent[];
  missing_info: string[];
  followup_questions: FollowUpQuestion[];
  trend: TrendRow[];
  disagreements: Disagreement[];
  transcript?: { original: string; translated: string; language: string } | null;
  generated_by: string;
  generated_at: string;
  edited_by?: string | null;
  observations?: Observation[];
  edited_at?: string | null;
}

export interface Override {
  from_urgency: Urgency;
  to_urgency: Urgency;
  category: string;
  reason: string;
  by: string;
  at: string;
}

export interface Encounter {
  id: string;
  patient: Patient;
  facility_id: string;
  category: PatientCategory;
  status: EncounterStatus;
  chief_complaint: string;
  created_at: string;
  /** null in any response delivered to a patient-role session. */
  urgency: Urgency | null;
  urgency_source: "rules" | "override";
  note: TriageNote | null;
  intake: IntakePayload | null;
  override?: Override | null;
  reviewed_by?: string | null;
  reviewed_at?: string | null;
  referral_needed?: boolean | null;
  specialist_required?: string | null;
  escalation_due_at?: string | null;
  /** Daily queue token shown to the patient, e.g. T-014. */
  token?: string | null;
  channel?: IntakeChannel;
  /** Present when the patient is on an employer's roster (never sent to patient/kiosk sessions). */
  worker?: WorkerInfo | null;
  consent?: Consent | null;
}

export type IntakeChannel = "staff_kiosk" | "kiosk_link" | "patient_app";

/** Front-desk view of today's tokens — no clinical content. */
export interface TokenBoardItem {
  encounter_id: string;
  token: string | null;
  patient_id: string;
  patient_name: string;
  patient_code: string;
  status: EncounterStatus;
  channel: IntakeChannel;
  created_at: string;
  wait_minutes: number;
}

export interface KioskLink {
  id: string;
  code: string;
  label: string;
  facility_id: string;
  url: string;
  created_by: string;
  created_at: string;
  revoked: boolean;
  last_used_at: string | null;
  sessions: number;
  intakes_today: number;
}

export interface ShareLink {
  id: string;
  url: string;
  /** Only present right after creation — print it next to the QR. */
  access_code: string | null;
  purpose: "referral" | "handoff";
  created_by: string;
  created_at: string;
  expires_at: string;
  revoked: boolean;
  views: number;
}

export interface SharedSummary {
  facility: { name?: string; district?: string; state?: string; type?: string };
  patient: { name: string; code: string; age: number; sex: string; language: string; phone: string | null };
  encounter: {
    token: string | null;
    created_at: string;
    category: PatientCategory;
    chief_complaint: string;
    status: EncounterStatus;
    urgency: Urgency | null;
    urgency_source: string;
    override: Override | null;
    reviewed_by: string | null;
    reviewed_at: string | null;
    maternal: MaternalIntake | null;
    chronic: ChronicIntake | null;
    consent: { mode: ConsentMode; proxy_name: string | null; proxy_relation: string | null } | null;
  };
  note: Pick<TriageNote, "summary" | "flags" | "vitals" | "labs" | "timeline" | "missing_info" | "disagreements" | "rules_fired"> | null;
  referral: { destination: string; specialty: string; reason: string; transport: string; created_by: string; created_at: string; note_text: string } | null;
  documents: { id: string; filename: string; kind: string; content_type: string; uploaded_at: string; url: string | null }[];
  shared_by: string;
  expires_at: string;
  disclaimer: string;
}

export interface KioskInfo {
  code: string;
  label: string;
  facility_id: string;
  facility_name: string;
  organisation_name?: string | null;
  district: string;
  state: string;
  languages: string[];
}

export interface QueueItem {
  encounter_id: string;
  token?: string | null;
  channel?: IntakeChannel;
  patient_code: string;
  patient_name: string;
  age: number;
  sex: string;
  category: PatientCategory;
  chief_complaint: string;
  urgency: Urgency;
  status: EncounterStatus;
  created_at: string;
  wait_minutes: number;
  flag_count: number;
  needs_check_count: number;
  language: string;
  escalation_due_at: string | null;
  vitals_recorded?: boolean;
  observation_count?: number;
}

export interface Escalation {
  id: string;
  encounter_id: string;
  patient_name: string;
  urgency: Urgency;
  raised_by: string;
  raised_at: string;
  to_role: "senior_mo" | "specialist" | "doctor";
  reason: string;
  auto: boolean;
  status: "open" | "acknowledged";
  acknowledged_by?: string | null;
  acknowledged_at?: string | null;
  ack_note?: string | null;
}

export interface Referral {
  id: string;
  encounter_id: string;
  patient_name: string;
  destination: string;
  specialty: string;
  reason: string;
  note_text: string;
  transport: "self" | "ambulance_108" | "facility_vehicle";
  created_by: string;
  created_at: string;
  status: "draft" | "sent" | "received";
}

export type AuditAction =
  | "VIEW"
  | "CREATE"
  | "UPDATE"
  | "CONFIRM"
  | "OVERRIDE"
  | "ESCALATE"
  | "ACKNOWLEDGE"
  | "REFERRAL"
  | "EXPORT"
  | "LOGIN"
  | "CONSENT"
  | "UPLOAD"
  | "DEVICE"
  | "CONFIG"
  | "DISAGREEMENT"
  | "PURGE";

export interface AuditEvent {
  id: number;
  ts: string;
  actor_id: string | null;
  actor_name: string;
  actor_role: string;
  action: AuditAction;
  resource_type: string;
  resource_id: string | null;
  patient_code: string | null;
  detail: string;
  prev_hash: string;
  hash: string;
}

export interface FileObject {
  id: string;
  filename: string;
  content_type: string;
  size: number;
  kind: "report" | "image" | "audio";
  encounter_id: string | null;
  uploaded_at: string;
  expires_at: string;
  purged_at: string | null;
  /** Object URL / data URL for previews (mock) or signed path (live). */
  url?: string | null;
}

export interface RetentionStatus {
  policy_hours: { audio: number; image: number; report: number };
  active: number;
  pending_purge: number;
  purged_last_7d: number;
  files: FileObject[];
}

export interface FacilityStats {
  facility_id: string;
  today_total: number;
  by_urgency: Record<Urgency, number>;
  avg_wait_minutes: number;
  open_escalations: number;
  referrals_today: number;
  offline_synced_today: number;
}

export type FitnessStatus = "fit" | "fit_with_restrictions" | "temporarily_unfit" | "pending_review";

export interface CohortWorker {
  worker_code: string;
  department: string;
  fitness_status: FitnessStatus;
  last_screened_at: string | null;
}

export interface Cohort {
  id: string;
  name: string;
  employer_name: string;
  screening_type: string;
  workers: CohortWorker[];
}

export interface Reminder {
  id: string;
  patient_id: string;
  kind: "anc_checkup" | "chronic_checkin" | "followup";
  due_at: string;
  channel: "sms" | "voice";
  status: "scheduled" | "sent" | "done";
  message: string;
}

export type ExportFormat = "pdf" | "json" | "csv" | "fhir" | "print";
