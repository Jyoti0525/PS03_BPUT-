import type {
  KioskFinderHit,
  Alert,
  Capacity,
  DepartmentRates,
  Call,
  TelephonyStatus,
  Followup,
  FollowupAttempt,
  AuditAction,
  AuditEvent,
  Cohort,
  DeidentifiedCohort,
  GuardTestResult,
  GuardTestSample,
  AiOpinionReport,
  OverrideStats,
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
  RetentionStatus,
  Tokens,
  SecondOpinion,
  Transcription,
  TriageNote,
  Urgency,
  User,
  VitalsInput,
  OnsetReading,
  RegionCalendar,
  VisitCalendar,
  VisitKind,
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
  /** E5: the next days this facility holds this kind of follow-up visit. */
  visitDays(id: string, kind: VisitKind, after?: string): Promise<{ kind: VisitKind; rule: string; days: string[]; calendar: VisitCalendar }>;
  /** F5: how the note would read a phrase such as "since Diwali" at this facility. */
  tryOnset(id: string, text: string): Promise<OnsetReading>;

  facilityTokens(id: string): Promise<TokenBoardItem[]>;

  // Public kiosk links
  listKioskLinks(): Promise<KioskLink[]>;
  createKioskLink(label: string, forHome?: boolean): Promise<KioskLink>;
  /** C3: the desk checks in a patient who filled in from home; they join the queue from now. */
  checkIn(encounterId: string): Promise<Encounter>;
  /** A form filled in "for any centre" (J- reference): it moves to this facility and the patient is checked in. */
  claimForm(reference: string): Promise<Encounter>;
  revokeKioskLink(id: string): Promise<void>;
  kioskInfo(code: string): Promise<KioskInfo>;
  /** Facilities taking forms from home, for a patient without a code. */
  kioskFinder(q: string, lat?: number, lon?: number): Promise<KioskFinderHit[]>;
  /** Starts a kiosk session for this browser tab (role = kiosk, intake-only). */
  kioskSession(code: string, deviceId: string): Promise<{ tokens: Tokens; user: User }>;
  kioskIdentify(patientCode: string, phone: string): Promise<Patient>;

  // QR summary links (referral hand-off)
  createShare(encounterId: string, hours: number, purpose?: ShareLink["purpose"]): Promise<ShareLink>;
  listShares(encounterId: string): Promise<ShareLink[]>;
  revokeShare(id: string): Promise<void>;
  shareMeta(token: string): Promise<{ facility_name: string; purpose: string; expires_at: string }>;
  openShare(token: string, accessCode: string): Promise<SharedSummary>;
  /** E4: the receiving clinician confirms the patient reached care; closes the referral. */
  shareReceived(token: string, accessCode: string, confirmedBy: string, note: string): Promise<{ status: string; received_by: string; received_at: string }>;

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
  /** Record the patient's answer to a follow-up question from the note; the rules run again on it. */
  answerFollowup(encounterId: string, input: { qid: string; answer?: string | null; text?: string | null }): Promise<Encounter>;
  addObservations(encounterId: string, input: { vitals?: VitalsInput | null; note?: string | null; signs?: string[]; exam_done?: boolean }): Promise<Encounter>;

  // Patients
  searchPatients(q: string): Promise<PatientCandidate[]>;
  getPatient(id: string): Promise<Patient>;
  getPatientByCode(code: string): Promise<Patient>;
  /** A6: a person chose this patient from the candidates; logged, never an automatic merge. */
  pickPatient(id: string, matchReason: string, candidates: number): Promise<Patient>;
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

  // Alerts (C3 capacity, D3 fever cluster, D4 missed visit, E6 call escalation), follow-ups and reminder calls
  listAlerts(status?: Alert["status"] | "active"): Promise<Alert[]>;
  acknowledgeAlert(id: string, note: string): Promise<Alert>;
  capacity(): Promise<Capacity>;
  /** Doctor / medical officer: daily counts per place and syndrome, small counts written as "<5". */
  syndromicCsv(days?: number): Promise<ExportResult>;
  listFollowups(scope?: "active" | "all", programme?: "all" | "maternal" | "chronic"): Promise<Followup[]>;
  /** Active health workers at the caller's facility (names only), to assign a maternal follow-up. */
  listHealthWorkers(): Promise<{ id: string; name: string }[]>;
  followupAttempt(id: string, outcome: Exclude<FollowupAttempt["outcome"], "call">, note?: string): Promise<Followup>;
  /** E6 reminder call, simulated in the browser: no phone call is made in this build. */
  startCall(followupId: string, opts?: { operator?: Call["operator"]; language?: Call["language"]; channel?: Call["channel"] }): Promise<Call>;
  /** Real phone calls and SMS through Twilio: set up or not, and the demo phone they go to. */
  telephonyStatus(): Promise<TelephonyStatus>;
  /** A reminder SMS in the patient's language, to the demo phone. Never names a pregnancy or a condition. */
  followupSms(followupId: string): Promise<Followup>;
  /** One answer: what was said (English) and, when transcribed, the patient's own words. Rules read it on the server. */
  callAnswer(callId: string, text: string, originalText?: string): Promise<Call>;
  endCall(callId: string, outcome: "no_answer" | "hung_up"): Promise<Call>;
  getCall(callId: string): Promise<Call>;
  listCalls(followupId: string): Promise<Call[]>;
  /** One agent line spoken by Sarvam's voice (MP3). Rejects with 503 when Sarvam is not set up. */
  callAudio(callId: string, turnIndex: number): Promise<Blob>;
  /** A7: a line read aloud by the online voice when the device has none for the language. */
  /** The server's voice: offline MMS-TTS (Odia, Hindi, Kannada) first, Sarvam online only when allowOnline. */
  speakOnline(text: string, lang: string, allowOnline?: boolean): Promise<Blob>;
  /** English → the patient's language (offline IndicTrans2; Bhashini online when the offline model cannot run). */
  translateText(text: string, source: string, target: string): Promise<{ text: string; engine: string | null }>;

  // Referrals
  createReferral(
    encounterId: string,
    input: Pick<Referral, "destination" | "specialty" | "reason" | "transport" | "note_text">,
  ): Promise<Referral>;
  listReferrals(): Promise<Referral[]>;
  /** E4: the referring doctor records that care was received (e.g. confirmed by phone). */
  referralReceived(id: string, confirmedBy: string, note: string): Promise<Referral>;

  // Files
  /** `sampleKey` marks one of the bundled synthetic reports so OCR crops can be generated. */
  /** `read: false` — the patient chose to continue without AI, so the server does not OCR the report.
   * `online: true` — their AI consent also lets handwriting be read online (Sarvam Vision, India). */
  uploadFile(file: File, kind: FileObject["kind"], encounterId?: string | null, sampleKey?: string | null, read?: boolean, online?: boolean): Promise<FileObject>;
  getFile(id: string): Promise<FileObject>;

  // Speech — offline models on the facility server; the audio itself is not stored by this call
  /** secondOpinion: a second engine also hears the audio (B9); only when the patient allowed AI help. Sarvam (online)
   *  answers at once; IndicWhisper (offline, when Sarvam cannot) answers through `secondCheck`. */
  transcribe(audio: Blob, language: string, opts?: { secondOpinion?: boolean }): Promise<Transcription>;
  secondCheck(id: string): Promise<SecondOpinion>;

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
  overrideStats(days?: number): Promise<OverrideStats>;
  /** C4 demo: run a typed sentence through the output guard. Supervisor only; logged as a test, touches no record. */
  guardTestSamples(): Promise<{ guard_version: number; samples: GuardTestSample[] }>;
  guardTest(text: string, source?: string): Promise<GuardTestResult>;

  // Patient self-service (triage status is stripped server-side for this role)

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
