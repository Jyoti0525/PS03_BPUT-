import type {
  AuditAction,
  AuditEvent,
  Cohort,
  Consent,
  ConsentInput,
  Device,
  Encounter,
  Escalation,
  ExportFormat,
  Facility,
  FacilityStats,
  FileObject,
  IntakePayload,
  OtpChallenge,
  OtpVerifyResult,
  Patient,
  PatientCandidate,
  QueueItem,
  Referral,
  RegisterInput,
  Reminder,
  RetentionStatus,
  Tokens,
  TriageNote,
  Urgency,
  User,
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
  requestOtp(phone: string): Promise<OtpChallenge>;
  verifyOtp(challengeId: string, code: string): Promise<OtpVerifyResult>;
  register(input: RegisterInput): Promise<{ tokens: Tokens; user: User }>;
  loginWithPin(phone: string, pin: string, deviceId: string): Promise<{ tokens: Tokens; user: User }>;
  setPin(pin: string, deviceId: string): Promise<void>;
  me(): Promise<User>;
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

  // Users
  listUsers(): Promise<User[]>;

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

  // Referrals
  createReferral(
    encounterId: string,
    input: Pick<Referral, "destination" | "specialty" | "reason" | "transport" | "note_text">,
  ): Promise<Referral>;
  listReferrals(): Promise<Referral[]>;

  // Files
  /** `sampleKey` marks one of the bundled synthetic reports so OCR crops can be generated. */
  uploadFile(file: File, kind: FileObject["kind"], encounterId?: string | null, sampleKey?: string | null): Promise<FileObject>;
  getFile(id: string): Promise<FileObject>;

  // Audit
  listAudit(filter?: { action?: AuditAction | ""; q?: string }): Promise<AuditEvent[]>;
  verifyAudit(): Promise<{ ok: boolean; checked: number; broken_at: number | null }>;
  exportAuditCsv(): Promise<ExportResult>;

  // Privacy / retention (purge job itself is owned by the ML/data track)
  retentionStatus(): Promise<RetentionStatus>;

  // Patient self-service (triage status is stripped server-side for this role)
  myRecord(): Promise<{ patient: Patient; encounters: Encounter[]; reminders: Reminder[] }>;

  // Employer — fitness status and cohort only, never records
  listCohorts(): Promise<Cohort[]>;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
