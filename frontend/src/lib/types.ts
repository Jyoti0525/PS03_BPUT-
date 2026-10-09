/**
 * Jeevia API contract.
 *
 * These types mirror the Pydantic schemas in `backend/app/schemas.py`.
 * Both the in-browser mock adapter and the live FastAPI adapter return these shapes,
 * so every screen can be built against mocks and switched to the live API by env var.
 */

export type Role =
  | "doctor"
  | "medical_officer"
  | "nurse"
  | "health_worker"
  | "receptionist"
  | "supervisor"
  | "employer"
  | "kiosk";

export const STAFF_ROLES: Role[] = ["doctor", "medical_officer", "nurse", "health_worker", "receptionist", "supervisor"];
export const REVIEWER_ROLES: Role[] = ["doctor", "medical_officer", "nurse", "health_worker"];
/** The medical officer can do everything a doctor can, and receives capacity and outbreak alerts. */
export const DOCTOR_ROLES: Role[] = ["doctor", "medical_officer"];
export const CLINICIAN_ROLES: Role[] = ["doctor", "medical_officer", "nurse", "health_worker"];
/** Highest urgency each role may confirm (E2): a health worker GREEN, a nurse up to YELLOW, a doctor or MO any. */
export const SIGN_OFF: Partial<Record<Role, Urgency>> = { health_worker: "green", nurse: "yellow", doctor: "red", medical_officer: "red" };
export const ROLE_LABEL: Record<Role, string> = {
  doctor: "Doctor",
  medical_officer: "Medical officer",
  nurse: "Nurse",
  health_worker: "Health worker (ASHA / ANM / MPW)",
  receptionist: "Front desk",
  supervisor: "Supervisor",
  employer: "Employer",
  kiosk: "Kiosk",
};
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
  | "closed"
  /** Filled in from home; joins the queue when the desk checks the patient in (C3). */
  | "expected"
  /** Filled in from home, never checked in within 36 h. */
  | "lapsed";

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
  /** Verified email (optional second way to receive sign-in codes). */
  email?: string | null;
  /** False when the account was verified by email and the mobile number never received a code. */
  phone_verified?: boolean;
  created_at: string;
}

/** Bedside observation recorded by a nurse or doctor (kept on the note). */
export interface Observation {
  by: string;
  role: Role;
  at: string;
  vitals: VitalsInput;
  note: string | null;
  signs?: string[];
  exam_done?: boolean;
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
export const PIN_ROLES: Role[] = ["doctor", "medical_officer", "nurse", "health_worker", "receptionist", "supervisor", "employer"];

export interface RegisterInput {
  registration_token: string;
  /** Required when the registration was verified by email. */
  phone?: string | null;
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
  /** E4: where this specialty is referred when it is not on site. */
  refer_to?: string | null;
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
  /** F2: low | normal | high. On a high-load day the kiosk asks only the safety questions. */
  patient_load?: "low" | "normal" | "high";
  /** Answers to the "what services do you have" setup questions. */
  capabilities: Record<string, boolean>;
  /** F5: worker names and monsoon dates for this facility's state, with its own changes applied. */
  region?: FacilityRegion | null;
  /** F5: this facility's own changes to the state table. */
  region_config?: RegionConfig | null;
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
  /** DPDP s. 13 grievance contact for the patient slip. */
  grievance_contact?: string | null;
}

/* ── Intake ───────────────────────────────────────────── */

export type InputSource = "voice" | "text" | "icon";

export interface SymptomEntry {
  text: string; // working-language text
  original_text: string; // raw text as spoken/typed, kept for audit
  language: string;
  source: InputSource;
  confirmed_by_readback: boolean;
  engine?: string | null; // speech/translation engine that produced `text`
  /** B9, voice only: what the second speech engine heard in the same recording. The server compares the two again. */
  second_hearing?: { engine: string; text: string; translation?: string | null } | null;
  /** Voice only: the speech engine's confidence (0–1). Below the language's threshold the server keeps it out of the history. */
  confidence?: number | null;
}

/** Server speech recognition result (offline IndicConformer, then IndicTrans2 into English). */
export interface Transcription {
  text: string; // in the speaker's language
  language: string;
  engine: string;
  seconds_audio: number | null;
  seconds_taken: number | null;
  translation: { text: string; language: "en"; engine: string } | null;
  translation_error?: string;
  /** The engine's own confidence (0–1) and the language's threshold; below it the words become a question for staff. */
  confidence?: number | null;
  confidence_threshold?: number;
  low_confidence?: boolean;
  /** B9: a second engine on the same audio, when the patient allowed AI help. `error` when it could not run. */
  second_opinion?: SecondOpinion;
  /** The offline engine is not installed here (the hosted link): Sarvam alone transcribed. */
  offline_unavailable?: string;
}

/** Sarvam (online) answers with the transcript; IndicWhisper (offline) answers later: `pending` is the id to ask
 *  `secondCheck` with until the comparison is ready. */
export interface SecondOpinion {
  engine: string;
  text?: string;
  agreement?: number;
  differences?: string[];
  disagree?: boolean;
  translation?: string | null;
  error?: string;
  pending?: string;
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
  /** D4: whose phone reminders go to. On a husband's or family phone nothing about pregnancy is said. */
  phone_belongs_to?: PhoneOwner | null;
  /** The ASHA / ANM who follows up a missed check-up. */
  assigned_worker_id?: string | null;
}

export type PhoneOwner = "self" | "husband" | "household" | "none";

export type Exposure = "silica" | "coal_dust" | "cotton_dust" | "asbestos" | "other_dust" | "noise" | "chemicals" | "pesticides" | "heat";

export const EXPOSURE_LABEL: Record<Exposure, string> = {
  silica: "Silica / stone dust",
  coal_dust: "Coal dust",
  cotton_dust: "Cotton dust",
  asbestos: "Asbestos",
  other_dust: "Other dust",
  noise: "Loud noise",
  chemicals: "Chemicals or fumes",
  pesticides: "Pesticides",
  heat: "Heat",
};

/** D2 workplace screening answers. */
export interface OccupationalIntake {
  exposures: Exposure[];
  years_exposed?: number | null;
  cough_weeks?: number | null;
  breathless_vs_last?: "better" | "same" | "worse" | "unsure" | "first" | null;
  ppe_issued?: boolean | null;
  ppe_used?: "always" | "sometimes" | "never" | null;
  fev1_l?: number | null;
  fvc_l?: number | null;
  /** Filled by the server from the worker's earliest recorded FEV1. */
  fev1_baseline_l?: number | null;
  fev1_baseline_on?: string | null;
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
  avpu?: "A" | "V" | "P" | "U" | null;
}

export type NumericVital = Exclude<keyof VitalsInput, "avpu">;

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
  occupational?: OccupationalIntake | null;
  /** D3: hostel block (campus) — fevers are counted per place, never shown by name. */
  cluster_key?: string | null;
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
  /** Why the value needs checking (misread risk, no printed range…). */
  checks?: string[];
  loinc?: string | null;
  source: SourceRef;
}

export type FlagSeverity = "critical" | "warning" | "info";

/** Reviewers see flags, never model confidence percentages. */
export interface Flag {
  code: string;
  label: string;
  severity: FlagSeverity;
  reason: string;
  /** "clinical": a rule or follow-up about the patient; "data": how the information was captured (translation, OCR, offline). */
  group?: "clinical" | "data";
}

/** What a doctor reads before the complaint details, from the patient's answers only. */
export interface NoteHistory {
  positives: string[];
  /** Pertinent negatives: what the patient said "no" to. */
  negatives: string[];
  allergies: string;
  medicines: string[];
  past: string[];
}

export interface RuleHit {
  rule_id: string;
  protocol: "ATP" | "IITT" | "IMCI" | "MATERNAL" | "LAB" | "LOCAL" | "SAFETY" | "FACILITY";
  description: string;
  urgency: Urgency;
  source?: string;
  evidence?: string[];
  non_downgradable?: boolean;
  review_by?: "health_worker" | "nurse" | "doctor";
}

export interface Disagreement {
  field: string;
  values: { engine: string; value: string }[];
  action: string;
}

export interface SinceLast {
  encounter_id: string | null;
  date: string;
  days_ago: number;
  complaint: string;
  urgency: Urgency | null;
  decided_by: string | null;
  override_reason: string | null;
  new_symptoms: string[];
  gone_symptoms: string[];
  same_symptoms: string[];
  vitals: { label: string; unit: string; then: string | number; now: string | number; then_status?: string; now_status?: string }[];
  medicines_then: string[];
  medicines_now: string[];
  feeling: string | null;
}

export interface TrendRow {
  parameter: string;
  points: { label: string; value: number }[];
  direction: "worse" | "better" | "stable";
}

export interface TimelineEvent {
  when: string;
  event: string;
  /** How sure the time is (B4). RECORDED = a dated record in this system. */
  certainty?: "RECORDED" | "STATED" | "INFERRED" | "VAGUE" | "UNKNOWN";
  /** The patient's own words (or the tapped answer) the time came from. */
  raw?: string | null;
  /** F5: the festival or season date a vague onset points to, e.g. "Diwali 20 Oct 2025 · Odisha calendar". */
  basis?: string;
}

export interface FollowUpQuestion {
  /** Stable id the answer is recorded against (older notes and the in-browser demo may lack it). */
  id?: string;
  tag: string;
  question: string;
  for_role: "nurse" | "doctor" | "health_worker" | "medical_officer";
  /** Answer buttons; empty means the patient's words are written instead. */
  options?: string[];
}

/** A follow-up question put to the patient at the bedside, and what they said. */
export interface FollowUpAnswer {
  qid: string;
  tag: string;
  question: string;
  answer: string;
  text: string | null;
  by: string;
  role: string;
  at: string;
}

export interface TriageResult {
  /** The rules' tier as computed (older notes may lack it). An override changes the encounter, not this. */
  urgency?: Urgency;
  provisional: boolean;
  protocols: { key: string; name: string }[];
  unresolved: { rule_id: string; urgency: Urgency; description: string; needs: string[] }[];
  missing_for_green: string[];
  findings: Record<string, { label: string; value: boolean | null; evidence: string[] }>;
  rulepack_version: string;
}

export interface TriageNote {
  summary: string;
  /** The presenting complaint alone (age, complaint, duration, severity); history rows carry the rest. */
  hpi?: string;
  /** The presenting complaint as label/value rows (Patient, Complaint, How long, Severity…). */
  presenting?: { label: string; value: string }[];
  /** The patient's previous visit beside this one; null on a first visit. */
  since_last?: SinceLast | null;
  history?: NoteHistory;
  flags: Flag[];
  rules_fired: RuleHit[];
  triage?: TriageResult;
  vitals: ExtractedValue[];
  labs: ExtractedValue[];
  timeline: TimelineEvent[];
  missing_info: string[];
  followup_questions: FollowUpQuestion[];
  followup_answered?: FollowUpAnswer[];
  trend: TrendRow[];
  disagreements: Disagreement[];
  transcript?: { original: string; translated: string; language: string } | null;
  /** A3: every answer not given in English, the patient's words beside the machine translation. */
  original_words?: { original: string; translated: string; language: string; source?: string | null; speech_engine?: string | null; translation_engine?: string | null }[];
  generated_by: string;
  /** Who wrote `summary`: the fixed template, or the local language model after passing the faithfulness check and output guard. */
  renderer?: "TEMPLATE" | "LLM";
  /** H5: what ran on this case; `degraded` when a stage failed, fell back or is unsure. */
  processing_status?: { overall: "ok" | "degraded"; stages: { stage: string; status: "ok" | "failed" | "fallback" | "unsure" | "unconfirmed"; detail: string }[] };
  /** Uploads: what kind of document each is (B10) and what was hidden before storage (G3). */
  documents?: { file_id: string; filename: string; kind: string; read: boolean; doc_type: { type: string; label: string; why: string } | null; redaction: { faces: number; id_numbers: number; engine?: string; skipped?: string } | null }[];
  /** Medicine names read from a strip or prescription — not part of the record until confirmed. */
  medications_pending?: { name: string; strength: string | null; seen: string; confidence: number; file_id: string; filename: string;
    kind?: "generic" | "brand"; contains?: string; read_by?: string }[];
  medications?: { name: string; strength: string | null; source: string; by: string; at: string }[];
  summary_template?: string;
  llm?: { status: "PASS" | "FAIL_FELL_BACK" | "UNAVAILABLE"; model: string; ms?: number; reason?: string; rejected_text?: string; faithfulness?: string[]; guard?: string[] };
  /** C8: the model's own tier for this case, beside the rules' result. It never changes urgency. */
  llm_opinion?: AiOpinion;
  generated_at: string;
  edited_by?: string | null;
  observations?: Observation[];
  edited_at?: string | null;
  /** "summary" for a health worker: summary, flags, missing items, their questions and vital signs only. */
  detail_level?: "summary" | "full";
}

export interface Override {
  from_urgency: Urgency;
  to_urgency: Urgency;
  category: string;
  reason: string;
  by: string;
  by_role?: string;
  at: string;
  /** Raising is open to any reviewer; lowering needs a doctor and a reason (E9). */
  direction?: "up" | "down";
}

/** How often clinicians changed the rules' urgency, per rule (E9). */
export interface OverrideStats {
  days: number;
  encounters: number;
  overrides: number;
  raised: number;
  lowered: number;
  rules: { rule_id: string; urgency: Urgency; description: string; fired: number; lowered: number; raised: number; lowered_rate: number }[];
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
  /** G8: SYNTHETIC or PUBLIC_SAMPLE; never real patient data. */
  data_origin?: "SYNTHETIC" | "PUBLIC_SAMPLE";
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
  /** When the patient reached the facility; null while an intake from home is still expected. */
  arrived_at?: string | null;
  /** From home only: what the patient is told. Never a tier. */
  home_advice?: "emergency" | "show_at_desk" | null;
  /** Present when the patient is on an employer's roster (never sent to patient/kiosk sessions). */
  worker?: WorkerInfo | null;
  consent?: Consent | null;
  /** Whether the signed-in role may confirm this urgency (E2 sign-off limits). */
  can_confirm?: boolean;
  /** Lowest role that may confirm it. */
  sign_off?: "health_worker" | "nurse" | "doctor" | null;
}

export type IntakeChannel = "staff_kiosk" | "kiosk_link" | "home_link" | "patient_app";

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
  /** null: filled in from home, not checked in yet. */
  arrived_at?: string | null;
  /** Since arrival. */
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
  /** Shared for filling in before coming (SMS, poster); its intakes wait until the desk checks the patient in. */
  for_home?: boolean;
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
  patient: { name: string; code: string; age: number; sex: string; language: string };
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
    consent: { mode: ConsentMode; proxy_relation: string | null } | null;
  };
  note: Pick<TriageNote, "summary" | "flags" | "vitals" | "labs" | "timeline" | "missing_info" | "disagreements" | "rules_fired"> | null;
  referral: { id?: string; destination: string; specialty: string; reason: string; transport: string; created_by: string; created_at: string; note_text: string; status?: string; received_by?: string | null; received_at?: string | null } | null;
  documents: { id: string; filename: string; kind: string; content_type: string; uploaded_at: string; url: string | null }[];
  shared_by: string;
  expires_at: string;
  disclaimer: string;
}

export interface KioskFinderHit {
  /** null: in the national directory but not on Jeevia yet (walk in). */
  code: string | null;
  facility_name: string;
  facility_type: string;
  district: string;
  state: string;
  pincode?: string | null;
  km?: number | null;
  phone?: string | null;
  lat?: number | null;
  lon?: number | null;
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
  for_home?: boolean;
}

export interface QueueItem {
  encounter_id: string;
  token?: string | null;
  channel?: IntakeChannel;
  /** When the patient reached the facility; waiting time counts from here. */
  arrived_at?: string | null;
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
  /** The first flags in words, critical first. */
  top_flags?: string[];
  needs_check_count: number;
  language: string;
  escalation_due_at: string | null;
  vitals_recorded?: boolean;
  observation_count?: number;
  /** C3: why this row is here, e.g. "RED (ATP-B-SPO2) · 1st of 3 RED · waiting 12 min, longest first". */
  order_reason?: string;
  sign_off?: "health_worker" | "nurse" | "doctor" | null;
}

export type AlertKind = "capacity" | "fever_cluster" | "missed_visit" | "call_escalation" | "referral_overdue";

export interface Alert {
  id: string;
  facility_id: string;
  kind: AlertKind;
  key: string;
  to_role: "medical_officer" | "health_worker";
  assigned_to: string | null;
  title: string;
  detail: Record<string, unknown>;
  status: "open" | "acknowledged" | "resolved";
  raised_at: string;
  updated_at: string;
  acknowledged_by?: string | null;
  acknowledged_at?: string | null;
  ack_note?: string | null;
  resolved_at?: string | null;
}

export interface Capacity {
  open_red: number;
  doctors_on_duty: number;
  over: boolean;
  reds: { token: string | null; wait_minutes: number; status: string }[];
  alert: Alert | null;
}

export interface FollowupAttempt {
  at: string;
  by: string;
  outcome: "reached" | "not_reached" | "came" | "call" | "sms";
  note: string | null;
  call_outcome?: CallOutcome;
  call_id?: string;
}

/** E6: who may phone this patient. The more serious the case, the less AI on the call. */
export interface WhoCalls {
  who: "agent" | "human" | "home_visit";
  why: string;
}

/** The 11 languages Sarvam's Bulbul voice speaks: a reminder call can be in any of them. */
export type CallLanguage = "en" | "hi" | "or" | "bn" | "ta" | "te" | "gu" | "kn" | "ml" | "mr" | "pa";

export type CallOutcome = "completed" | "danger_sign" | "unclear" | "message_left" | "no_answer" | "hung_up";

export interface CallTurn {
  who: "agent" | "patient";
  key: string;
  /** In the call's language. */
  text: string;
  /** Agent: the English line. Patient: the English translation, when it differs. */
  text_en: string | null;
  heard?: "yes" | "no" | "unsure" | null;
  findings?: string[];
  /** Typed in a language the danger-sign word lists do not cover, and no translation was available. */
  unread?: string;
  at: string;
}

export interface RedFlag {
  finding: string | null;
  label: string;
  evidence: string;
}

/** E6: one reminder call, simulated in the browser. */
export interface Call {
  id: string;
  reminder_id: string;
  patient_name: string;
  patient_code: string;
  programme: "maternal" | "chronic";
  operator: "agent" | "human";
  language: CallLanguage;
  audience: "patient" | "other";
  status: "active" | "ended";
  outcome: CallOutcome | null;
  turns: CallTurn[];
  red_flags: RedFlag[] | null;
  notes: {
    can_come?: boolean | null;
    flags?: string[];
    said?: string;
    message_passed_on?: string | null;
    /** A real phone call: the demo phone (last four digits) and whether it was picked up. */
    phone?: { to: string; answered?: boolean; status?: string; error?: string };
    /** A danger sign or unclear answer also texted the demo phone (standing in for the MO and the ASHA). */
    staff_sms?: { sent: boolean; to?: string; error?: string };
  } | null;
  expects: "yes_no" | "free" | null;
  alert_id: string | null;
  started_at: string;
  ended_at: string | null;
  sources: { id: string; short: string }[];
  /** sarvam: each agent line is spoken by Sarvam's Bulbul voice (callAudio); device: the browser's own voice. */
  voice: "sarvam" | "device";
  /** phone: a real call through Twilio to the demo phone; the page follows it. */
  channel: "browser" | "phone";
}

/** Whether real phone calls and SMS (Twilio) are set up. Everything goes to one demo phone, never a patient's number. */
export interface TelephonyStatus {
  calls: boolean;
  sms: boolean;
  demo_to: string | null;
  provider?: "twilio" | "vonage";
  missing: string[];
}

export interface Followup {
  id: string;
  patient_id: string;
  patient_code: string;
  patient_name: string;
  village: string | null;
  phone: string | null;
  phone_belongs_to: PhoneOwner | null;
  kind: string;
  programme: "maternal" | "chronic";
  /** Chronic: the long-term condition. */
  condition: string | null;
  who_calls: WhoCalls;
  due_at: string;
  status: "scheduled" | "missed" | "contacted" | "call_due" | "flagged" | "done" | "cancelled";
  missed_at: string | null;
  attempts: FollowupAttempt[];
  assigned_to: string | null;
  assigned_name: string | null;
  gestation_weeks: number | null;
  /** What the reminder call would say; null when there is no phone to call. */
  call_script: string | null;
  resolved_at: string | null;
}

export interface DepartmentRate {
  department: string;
  screened: number | null;
  follow_up_pct: number | null;
  ppe_gap_pct: number | null;
  above_others: boolean;
  suppressed: boolean;
}

export interface DepartmentRates {
  days: number;
  k_min: number;
  departments: DepartmentRate[];
  note: string;
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
  /** E4: open until the receiving side confirms care; past this time it is overdue. */
  due_at?: string | null;
  overdue?: boolean;
  received_at?: string | null;
  received_by?: string | null;
  received_note?: string | null;
  received_via?: "qr" | "phone" | null;
}

export type AuditAction =
  | "ARRIVE"
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
  | "PURGE"
  | "REDACT"
  | "GUARD_BLOCK"
  | "ALERT";

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
  /** Capture feedback from the server's document reader: image quality and how many values it found. */
  read_quality?: { engine: string; ok: boolean; issues: string[]; values_found: number } | null;
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

/** One count in the de-identified view: `null` means 1–4 cases, suppressed so a small group cannot be singled out. */
export interface CohortCell {
  key: string;
  count: number | null;
}

/** C8: the language model's second opinion on urgency. Shown beside the rules; the rules' tier always stands. */
export interface AiOpinion {
  status: "AGREE" | "DISAGREE" | "UNAVAILABLE" | "UNREADABLE";
  model: string;
  ms?: number;
  rules_urgency: Urgency;
  model_urgency?: Urgency;
  direction?: "higher" | "lower" | null;
  /** Present only when it passed the faithfulness check and the output guard. */
  reason?: string;
  /** Why the reason was hidden (it failed the checks); the tier is still shown. */
  reason_withheld?: string[];
}

export type CadreKey = "community" | "nurse" | "nutrition" | "male" | "cho";

/** A front-line worker title as used in the facility's state (ASHA, Mitanin, VHN…). */
export interface CadreName {
  en: string;
  hi?: string;
  or?: string;
  full: string;
  source?: string;
}

export interface MonsoonDates {
  onset: string; // MM-DD
  withdrawal: string; // MM-DD
  station?: string;
}

export interface FacilityRegion {
  state: string | null;
  cadres: Record<CadreKey, CadreName>;
  monsoon: MonsoonDates | null;
  northeast: boolean;
}

export interface LocalFestival {
  name: string;
  aliases?: string[];
  dates: string[]; // YYYY-MM-DD
  faith?: string | null;
}

/** E5: the days a facility holds each kind of follow-up visit (weekday 0 = Monday). */
export interface VisitDays {
  weekdays: number[];
  monthdays?: number[];
}
export interface VisitCalendar {
  anc_checkup?: VisitDays | null;
  chronic_checkin?: VisitDays | null;
  closed_weekdays?: number[] | null;
  closed_dates?: string[] | null;
}
export type VisitKind = "anc_checkup" | "chronic_checkin";

export interface RegionConfig {
  cadres?: Partial<Record<CadreKey, string>>;
  monsoon?: { onset: string; withdrawal: string } | null;
  festivals?: LocalFestival[];
  visits?: VisitCalendar | null;
}

/** F5: the festival and season table a facility's notes use to date "since Diwali" onsets. */
export interface RegionCalendar {
  facility_id: string;
  state: string | null;
  as_of: string;
  version: string;
  festivals: { key: string; label: string; faith: string; start: string; end: string; source: string; local: boolean; custom: boolean; past: boolean }[];
  seasons: { key: string; label: string; start: string | null; end: string | null; source: string; names: string[]; station: string | null }[];
  cadres: Record<CadreKey, CadreName>;
  monsoon: MonsoonDates | null;
  northeast: boolean;
  sources: Record<string, string>;
  region_config: RegionConfig;
}

/** How the note would read a phrase: onset with its certainty and, for a festival or season, the date it points to. */
export interface OnsetReading {
  on: string;
  when: string;
  certainty: "STATED" | "INFERRED" | "VAGUE" | "UNKNOWN";
  raw: string | null;
  days: number | null;
  check: string | null;
  approx?: { found: boolean; label: string; start?: string; end?: string; source?: string; region?: string | null; reason?: string; others?: { label: string; start: string; end: string }[] };
}

/** Supervisor/doctor view of where the model's opinion differed from the rules (C8). */
export interface AiOpinionReport {
  days: number;
  model: string | null;
  encounters: number;
  counts: Record<AiOpinion["status"], number>;
  /** rules tier → model tier → cases */
  matrix: Record<Urgency, Record<Urgency, number>>;
  higher: number;
  lower: number;
  cases: {
    encounter_id: string;
    patient_code: string;
    created_at: string;
    category: string;
    rules_urgency: Urgency;
    model_urgency: Urgency;
    direction: "higher" | "lower";
    reason: string | null;
    reason_withheld: boolean;
    final_urgency: Urgency;
    overridden: boolean;
    status: string;
  }[];
}

/** One phrase the output guard (C4) matched. */
export interface GuardHit {
  category: "condition" | "diagnostic_phrasing" | "drug_advice" | string;
  label: string;
  phrase: string;
}

/** Result of the supervisor's guard test: a typed sentence, never a model output. */
export interface GuardTestResult {
  ok: boolean;
  hits: GuardHit[];
  guard_version: number;
  test: true;
}

export interface GuardTestSample {
  text: string;
  source?: string;
  language: string;
  expect: "block" | "allow";
}

/** Facility cases as counts only (G3): no name, ID, phone, village, exact age, time or free text. */
export interface DeidentifiedCohort {
  days: number;
  k_min: number;
  total: number | null;
  by_week: CohortCell[];
  by_age_band: CohortCell[];
  by_sex: CohortCell[];
  by_category: CohortCell[];
  by_urgency: CohortCell[];
  urgency_by_age_band: { urgency: Urgency; cells: CohortCell[] }[];
  findings: (CohortCell & { label: string })[];
  suppressed_cells: number;
  removed_fields: string[];
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
  status: "scheduled" | "sent" | "done" | "missed" | "contacted" | "call_due" | "cancelled";
  message: string;
}

export type ExportFormat = "pdf" | "json" | "csv" | "fhir" | "cda" | "print";
