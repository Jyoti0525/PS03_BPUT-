import type {
  Alert,
  Capacity,
  DepartmentRates,
  Followup,
  FollowupAttempt,
  AuditAction,
  AuditEvent,
  Cohort,
  DeidentifiedCohort,
  GuardTestResult,
  GuardTestSample,
  AiOpinionReport,
  Consent,
  ConsentInput,
  Device,
  Encounter,
  Escalation,
  ExportFormat,
  Facility,
  FacilityStats,
  KioskInfo,
  KioskLink,
  ShareLink,
  SharedSummary,
  DirectoryHit,
  Organisation,
  Worker,
  WorkerInput,
  FitnessRecord,
  FitnessStatus,
  NewFacilityInput,
  TokenBoardItem,
  FileObject,
  IntakePayload,
  OtpChallenge,
  OtpVerifyResult,
  Patient,
  PatientCandidate,
  QueueItem,
  Referral,
  RegisterInput,
  Role,
  Reminder,
  RetentionStatus,
  Tokens,
  Transcription,
  TriageNote,
  Urgency,
  User,
  VitalsInput,
  OnsetReading,
  RegionCalendar,
} from "@/lib/types";

export interface ExportResult {
  filename: string;
  mime: string;
  blob: Blob;
}

/**
 * Every call the frontend makes. `live.ts` maps these onto FastAPI routes under /api/v1;
 * `mock/server.ts` implements them in the browser against synthetic data.
 */
export interface JeeviaApi {
  mode: "mock" | "live";

  // Auth — phone + OTP, PIN, device binding, JWT
  /** A phone number (SMS code) or `{ email }` (email code, when the server offers it). */
  requestOtp(target: string | { phone?: string; email?: string; language?: string }, purpose?: "signin" | "register"): Promise<OtpChallenge>;
  authOptions(): Promise<{ sms: boolean; email: boolean }>;
  emailStart(email: string, language?: string): Promise<OtpChallenge>;
  emailConfirm(challengeId: string, code: string): Promise<User>;
  emailRemove(): Promise<User>;
  /** `purpose: "register"` refuses numbers that already have an account (never signs them in). */
  verifyOtp(challengeId: string, code: string, purpose?: "signin" | "register"): Promise<OtpVerifyResult>;
  register(input: RegisterInput): Promise<{ tokens: Tokens; user: User }>;
  /** Second factor after OTP for staff and employers. */
  verifyPin(pinToken: string, pin: string): Promise<{ tokens: Tokens; user: User }>;
  setupPin(pinToken: string, pin: string): Promise<{ tokens: Tokens; user: User }>;
  forgotPin(pinToken: string): Promise<OtpVerifyResult>;
  changePin(currentPin: string, newPin: string): Promise<void>;
  resetStaffPin(userId: string): Promise<void>;
  me(): Promise<User>;
  updateMe(patch: { language?: string }): Promise<User>;
  logout(): Promise<void>;

  // Devices (kiosk binding)
  listDevices(): Promise<Device[]>;
  bindDevice(label: string, deviceId: string): Promise<Device>;
  revokeDevice(id: string): Promise<void>;

  // Facilities
  listFacilities(): Promise<Facility[]>;
  getFacility(id: string): Promise<Facility>;
  updateFacility(id: string, patch: Partial<Facility>): Promise<Facility>;
  facilityStats(id: string): Promise<FacilityStats>;
  /** F5: festivals and seasons this facility dates vague onsets by, and its worker names. Staff only. */
  facilityCalendar(id: string): Promise<RegionCalendar>;
  /** F5: how the note would read a phrase such as "since Diwali" at this facility. */
  tryOnset(id: string, text: string): Promise<OnsetReading>;

  facilityTokens(id: string): Promise<TokenBoardItem[]>;

  // Public kiosk links
  listKioskLinks(): Promise<KioskLink[]>;
  createKioskLink(label: string): Promise<KioskLink>;
  revokeKioskLink(id: string): Promise<void>;
  kioskInfo(code: string): Promise<KioskInfo>;
  /** Starts a kiosk session for this browser tab (role = kiosk, intake-only). */
  kioskSession(code: string, deviceId: string): Promise<{ tokens: Tokens; user: User }>;
  kioskIdentify(patientCode: string, phone: string): Promise<Patient>;

  // QR summary links (referral hand-off)
  createShare(encounterId: string, hours: number, purpose?: ShareLink["purpose"]): Promise<ShareLink>;
  listShares(encounterId: string): Promise<ShareLink[]>;
  revokeShare(id: string): Promise<void>;
  shareMeta(token: string): Promise<{ facility_name: string; purpose: string; expires_at: string }>;
  openShare(token: string, accessCode: string): Promise<SharedSummary>;

  // National facility directory (public, used at sign-up)
  searchDirectory(q: string, state?: string | null): Promise<DirectoryHit[]>;
  directoryStates(): Promise<{ state: string; facilities: number }[]>;

  // Organisations (employer portal)
  myOrganisation(): Promise<{ organisation: Organisation; facilities: Facility[] }>;
  updateOrganisation(patch: Partial<Pick<Organisation, "name" | "registration_no" | "address" | "contact_phone">>): Promise<Organisation>;
  addOrganisationFacility(input: NewFacilityInput): Promise<Facility>;
  listWorkers(): Promise<Worker[]>;
  addWorker(input: WorkerInput): Promise<Worker>;
  importWorkers(csv: string): Promise<{ created: number; updated: number; errors: string[] }>;
  removeWorker(employeeCode: string): Promise<void>;

  // Occupational fitness (doctor)
  recordFitness(encounterId: string, input: { status: FitnessStatus; restrictions?: string | null; valid_until?: string | null }): Promise<FitnessRecord>;

  // Staff and identity management
  updateUser(id: string, patch: { role?: Role; is_active?: boolean }): Promise<User>;
  correctPatient(id: string, patch: Partial<Pick<Patient, "name" | "age" | "sex" | "phone" | "language" | "village">>): Promise<Patient>;

  // Users
  listUsers(): Promise<User[]>;
  setDuty(userId: string, onDuty: boolean): Promise<User>;
  /** Confirm or reject medicine names read from a photo (B10). */
  reviewMedications(encounterId: string, confirm: string[], reject: string[]): Promise<Encounter>;
  addObservations(encounterId: string, input: { vitals?: VitalsInput | null; note?: string | null; signs?: string[]; exam_done?: boolean }): Promise<Encounter>;

  // Patients
  searchPatients(q: string): Promise<PatientCandidate[]>;
  getPatient(id: string): Promise<Patient>;
  getPatientByCode(code: string): Promise<Patient>;
  createPatient(input: Omit<Patient, "id" | "code" | "created_at">): Promise<Patient>;
  patientEncounters(patientId: string): Promise<Encounter[]>;

  // Consent
  captureConsent(input: ConsentInput): Promise<Consent>;

  // Encounters + triage review
  submitIntake(payload: IntakePayload): Promise<Encounter>;
  queue(facilityId: string): Promise<QueueItem[]>;
  getEncounter(id: string): Promise<Encounter>;
  confirmEncounter(id: string): Promise<Encounter>;
  editNote(id: string, note: Partial<TriageNote>): Promise<Encounter>;
  overrideUrgency(id: string, to: Urgency, category: string, reason: string): Promise<Encounter>;
  setReferralNeeded(id: string, needed: boolean): Promise<Encounter>;
  exportEncounter(id: string, format: ExportFormat): Promise<ExportResult>;

  // Escalations
  escalate(encounterId: string, toRole: Escalation["to_role"], reason: string): Promise<Escalation>;
  listEscalations(status?: Escalation["status"]): Promise<Escalation[]>;
  acknowledgeEscalation(id: string, note: string): Promise<Escalation>;

  // Alerts (C3 capacity, D3 fever cluster, D4 missed visit) and maternal follow-ups
  listAlerts(status?: Alert["status"] | "active"): Promise<Alert[]>;
  acknowledgeAlert(id: string, note: string): Promise<Alert>;
  capacity(): Promise<Capacity>;
  /** Doctor / medical officer: daily counts per place and syndrome, small counts written as "<5". */
  syndromicCsv(days?: number): Promise<ExportResult>;
  listFollowups(scope?: "active" | "all"): Promise<Followup[]>;
  /** Active health workers at the caller's facility (names only), to assign a maternal follow-up. */
  listHealthWorkers(): Promise<{ id: string; name: string }[]>;
  followupAttempt(id: string, outcome: Exclude<FollowupAttempt["outcome"], "call_placed">, note?: string): Promise<Followup>;
  /** Simulated in this build: the script is recorded, no call is made. */
  followupCall(id: string): Promise<Followup>;

  // Referrals
  createReferral(
    encounterId: string,
    input: Pick<Referral, "destination" | "specialty" | "reason" | "transport" | "note_text">,
  ): Promise<Referral>;
  listReferrals(): Promise<Referral[]>;

  // Files
  /** `sampleKey` marks one of the bundled synthetic reports so OCR crops can be generated. */
  /** `read: false` — the patient chose to continue without AI, so the server does not OCR the report. */
  uploadFile(file: File, kind: FileObject["kind"], encounterId?: string | null, sampleKey?: string | null, read?: boolean): Promise<FileObject>;
  getFile(id: string): Promise<FileObject>;

  // Speech — offline models on the facility server; the audio itself is not stored by this call
  transcribe(audio: Blob, language: string): Promise<Transcription>;

  // Audit
  listAudit(filter?: { action?: AuditAction | ""; q?: string }): Promise<AuditEvent[]>;
  verifyAudit(): Promise<{ ok: boolean; checked: number; broken_at: number | null }>;
  exportAuditCsv(): Promise<ExportResult>;

  // Privacy / retention (purge job itself is owned by the ML/data track)
  retentionStatus(): Promise<RetentionStatus>;
  /** Counts only, small cells suppressed (anonymisation, G3). Supervisor and doctor. */
  deidentifiedCohort(days?: number): Promise<DeidentifiedCohort>;
  /** C8: where the AI model's urgency differed from the rules. Supervisor and doctor. */
  aiOpinions(days?: number): Promise<AiOpinionReport>;
  /** C4 demo: run a typed sentence through the output guard. Supervisor only; logged as a test, touches no record. */
  guardTestSamples(): Promise<{ guard_version: number; samples: GuardTestSample[] }>;
  guardTest(text: string, source?: string): Promise<GuardTestResult>;

  // Patient self-service (triage status is stripped server-side for this role)
  myRecord(): Promise<{ patient: Patient; encounters: Encounter[]; reminders: Reminder[] }>;

  // Employer — fitness status and cohort only, never records
  listCohorts(): Promise<Cohort[]>;
  /** D2: per department, screened / referred-for-review / PPE-gap shares; no symptoms, departments under 5 hidden. */
  departmentRates(days?: number): Promise<DepartmentRates>;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
