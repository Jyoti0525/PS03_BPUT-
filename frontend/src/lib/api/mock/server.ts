/**
 * In-browser mock of the Jeevia API. Persists to IndexedDB so a kiosk intake shows up in the
 * reviewer queue in another tab. Enforces the same role rules as the FastAPI backend:
 *  - patients never receive urgency or the AI note
 *  - facility admins (receptionist/supervisor) cannot read clinical notes
 *  - every read of a patient record writes a VIEW audit event
 */
import { get, set, del } from "idb-keyval";
import type { JeeviaApi } from "../contract";
import { ApiError } from "../contract";
import { getDeviceId, getTokens, setTokens } from "../tokens";
import type {
  AuditAction,
  AuditEvent,
  Consent,
  Device,
  Encounter,
  Escalation,
  Facility,
  FileObject,
  IntakePayload,
  Patient,
  Referral,
  Reminder,
  Role,
  Tokens,
  Urgency,
  User,
  Cohort,
  IntakeChannel,
  KioskLink,
  Alert,
  Capacity,
  OverrideStats,
} from "@/lib/types";
import { ADMIN_ROLES, DOCTOR_ROLES, PIN_ROLES, REVIEWER_ROLES, SIGN_OFF, STAFF_ROLES } from "@/lib/types";
import { SAMPLE_PIN, pinProblem } from "@/lib/pin";
import { evaluate } from "./rules";
import { buildNote, sampleReportImage, type UploadedForNote } from "./note";
import { DEMO_OTP, SEED_COHORTS, SEED_FACILITIES, SEED_HISTORY, SEED_PATIENTS, SEED_TODAY, SEED_USERS } from "./seed";
import { buildExport } from "@/lib/export";

const DB_KEY = "jeevia.mockdb.v4";
const ESCALATE_AFTER_MIN: Record<Urgency, number | null> = { red: 15, yellow: 60, green: null };
const RETENTION_HOURS = { audio: 24, image: 72, report: 168 };

interface StoredFile extends FileObject {
  data_url: string | null;
  sample_key?: string | null;
  boxes?: [number, number, number, number][] | null;
}

interface StoredKioskLink extends Omit<KioskLink, "url" | "intakes_today"> {
  user_id: string;
}

interface DB {
  facilities: Facility[];
  users: (User & { pinHash?: string | null; active?: boolean })[];
  kioskLinks: StoredKioskLink[];
  shares?: { id: string; token: string; code: string; encounter_id: string; purpose: "referral" | "handoff"; created_by: string; created_at: string; expires_at: string; revoked: boolean; views: number; failed: number }[];
  devices: Device[];
  patients: Patient[];
  encounters: Encounter[];
  consents: Consent[];
  escalations: Escalation[];
  referrals: Referral[];
  files: StoredFile[];
  audit: AuditEvent[];
  reminders: Reminder[];
  cohorts: Cohort[];
  otps: Record<string, { phone: string; code: string; exp: number }>;
  registrations: Record<string, { phone: string; exp: number }>;
  seq: number;
}

let db: DB | null = null;
let loading: Promise<DB> | null = null;

const uid = (p: string) => `${p}_${crypto.randomUUID().replace(/-/g, "").slice(0, 12)}`;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const clone = <T>(x: T): T => JSON.parse(JSON.stringify(x));

async function sha256(s: string) {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return Array.from(new Uint8Array(buf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function persist() {
  if (db) await set(DB_KEY, db);
}

async function load(): Promise<DB> {
  if (db) return db;
  if (!loading)
    loading = (async () => {
      const stored = (await get(DB_KEY)) as DB | undefined;
      db = stored ?? (await seed());
      if (!stored) await persist();
      return db;
    })();
  return loading;
}

export async function resetMockData() {
  await del(DB_KEY);
  db = null;
  loading = null;
  setTokens(null);
}

/* ── Audit (append-only, hash-chained) ─────────────────── */

async function audit(
  d: DB,
  actor: User | null,
  action: AuditAction,
  resource_type: string,
  resource_id: string | null,
  detail: string,
  patient_code: string | null = null,
  ts = new Date().toISOString(),
) {
  const prev = d.audit[d.audit.length - 1]?.hash ?? "GENESIS";
  const id = (d.audit[d.audit.length - 1]?.id ?? 0) + 1;
  const body = { id, ts, actor_id: actor?.id ?? null, actor_name: actor?.name ?? "System", actor_role: actor?.role ?? "system", action, resource_type, resource_id, patient_code, detail };
  const hash = await sha256(prev + JSON.stringify(body));
  d.audit.push({ ...body, prev_hash: prev, hash });
}

/* ── Seeding ──────────────────────────────────────────── */

async function seed(): Promise<DB> {
  const d: DB = {
    facilities: clone(SEED_FACILITIES),
    users: clone(SEED_USERS),
    kioskLinks: [],
    devices: [
      { id: "dev_kiosk_manikpur_1", label: "OPD entrance tablet", facility_id: "fac_phc_manikpur", bound_by: "Meera Nair", bound_at: new Date(Date.now() - 20 * 86400000).toISOString(), last_seen_at: new Date().toISOString(), revoked: false },
    ],
    patients: clone(SEED_PATIENTS),
    encounters: [],
    consents: [],
    escalations: [],
    referrals: [],
    files: [],
    audit: [],
    reminders: [],
    cohorts: clone(SEED_COHORTS),
    otps: {},
    registrations: {},
    seq: 3,
  };
  const system = null;
  await audit(d, system, "CONFIG", "system", null, "Demo database seeded with synthetic data", null, new Date(Date.now() - 86400000).toISOString());

  const all = [...SEED_HISTORY, ...SEED_TODAY];
  for (const s of all) {
    const patient = d.patients.find((p) => p.id === s.patient_id)!;
    const created = new Date(Date.now() - s.minutes_ago * 60000).toISOString();
    const file_ids: string[] = [];
    for (const key of s.sample_reports ?? []) {
      const img = sampleReportImage(key, patient.name);
      const f: StoredFile = {
        id: uid("file"),
        filename: `${key}_report_${patient.code}.svg`,
        content_type: "image/svg+xml",
        size: img.dataUrl.length,
        kind: "report",
        encounter_id: null,
        uploaded_at: created,
        expires_at: new Date(Date.parse(created) + RETENTION_HOURS.report * 3600000).toISOString(),
        purged_at: null,
        data_url: img.dataUrl,
        sample_key: key,
        boxes: img.boxes,
      };
      d.files.push(f);
      file_ids.push(f.id);
    }
    let consentId: string | null = null;
    const consent: Consent = {
      id: uid("con"),
      patient_id: patient.id,
      mode: s.proxy ? "proxy" : "self",
      proxy_name: s.proxy?.name ?? null,
      proxy_relation: s.proxy?.relation ?? null,
      privacy_context: "private",
      language: s.language,
      scopes: ["triage", "share_with_treating_team"],
      captured_by: "Sunita Yadav (ANM)",
      captured_at: created,
    };
    d.consents.push(consent);
    consentId = consent.id;
    const payload: IntakePayload = {
      patient_id: patient.id,
      facility_id: s.facility_id ?? "fac_phc_manikpur",
      category: s.category,
      language: s.language,
      chief_complaint: s.chief_complaint,
      symptoms: s.symptoms,
      selected_symptoms: s.selected_symptoms,
      duration: s.duration,
      severity: s.severity,
      answers: s.answers,
      file_ids,
      vitals: s.vitals,
      maternal: s.maternal ?? null,
      chronic: s.chronic ?? null,
      consent_id: consentId,
      client_ref: uid("ref"),
    };
    const enc = buildEncounter(d, payload, patient, created);
    if (s.status === "closed") {
      enc.status = "closed";
      enc.reviewed_by = "Dr. Deepa Sharma";
      enc.reviewed_at = created;
    } else {
      assignToken(d, enc, "staff_kiosk");
    }
    d.encounters.push(enc);
    for (const id of file_ids) d.files.find((f) => f.id === id)!.encounter_id = enc.id;
    await audit(d, null, "CREATE", "encounter", enc.id, `Intake captured (${s.category}); rules engine: ${enc.urgency}`, patient.code, created);
    if (enc.note?.disagreements.length)
      await audit(d, null, "DISAGREEMENT", "encounter", enc.id, enc.note.disagreements.map((x) => `${x.field}: ${x.values.map((v) => v.value).join(" vs ")}`).join("; "), patient.code, created);
  }

  // Maternal and chronic reminders (auto-fired via SMS / voice agent by the backend scheduler)
  const inDays = (n: number) => new Date(Date.now() + n * 86400000).toISOString();
  d.reminders.push({ id: uid("rem"), patient_id: "pat_003", kind: "anc_checkup", due_at: inDays(14), channel: "sms", status: "scheduled", message: "ANC check-up at PHC Manikpur (30 weeks). Bring your MCP card." });

  await audit(d, null, "DEVICE", "device", "dev_kiosk_manikpur_1", "Kiosk device 'OPD entrance tablet' bound by Meera Nair", null, new Date(Date.now() - 20 * 86400000).toISOString());
  makeKioskLink(d, "fac_phc_manikpur", "OPD waiting area", "Meera Nair", "MANIKPUR");
  makeKioskLink(d, "fac_phc_manikpur", "Fill in before you come (SMS / poster)", "Meera Nair", "MKHOME", true);
  // Keep audit strictly chronological for the chain display
  return d;
}

function buildEncounter(d: DB, payload: IntakePayload, patient: Patient, created = new Date().toISOString()): Encounter {
  const history = d.encounters
    .filter((e) => e.patient.id === patient.id)
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
  const files: UploadedForNote[] = payload.file_ids
    .map((id) => d.files.find((f) => f.id === id))
    .filter((f): f is StoredFile => !!f)
    .map((f) => ({ id: f.id, kind: f.kind, filename: f.filename, sample_key: f.sample_key, boxes: f.boxes }));
  const { urgency, hits } = evaluate(payload, patient.age);
  const consent = d.consents.find((c) => c.id === payload.consent_id) ?? null;
  const note = buildNote({ intake: payload, patient, hits, files, history, proxy: consent?.mode === "proxy" });
  const specialist = inferSpecialist(payload, patient);
  const facility = d.facilities.find((f) => f.id === payload.facility_id);
  const onSite = facility?.specialists.find((s) => s.key === specialist)?.available ?? false;
  const esc = ESCALATE_AFTER_MIN[urgency];
  return {
    id: uid("enc"),
    patient: clone(patient),
    facility_id: payload.facility_id,
    category: payload.category,
    status: "queued",
    chief_complaint: payload.chief_complaint,
    created_at: created,
    urgency,
    urgency_source: "rules",
    note,
    intake: payload,
    override: null,
    reviewed_by: null,
    reviewed_at: null,
    referral_needed: urgency === "red" && !onSite ? true : null,
    specialist_required: specialist,
    escalation_due_at: esc ? new Date(Date.parse(created) + esc * 60000).toISOString() : null,
    consent,
  };
}

function dayKey(iso = new Date().toISOString()) {
  return new Date(iso).toLocaleDateString("en-CA", { timeZone: "Asia/Kolkata" });
}

/** Daily running token per facility: T-001, T-002 … An intake from home gets an H- reference until it is checked in. */
function assignToken(d: DB, enc: Encounter & { token_date?: string }, channel: IntakeChannel, prefix: "T" | "H" = "T") {
  const day = dayKey();
  const n = d.encounters.filter((e) => e.facility_id === enc.facility_id && (e as Encounter & { token_date?: string }).token_date === day && e.token?.startsWith(`${prefix}-`)).length;
  enc.token_date = day;
  enc.token = `${prefix}-${String(n + 1).padStart(3, "0")}`;
  enc.channel = channel;
}

/** Waiting counts from arrival, not from when the form was sent (C3). */
function waitMin(e: Encounter): number {
  return Math.max(0, Math.round((Date.now() - Date.parse(e.arrived_at ?? e.created_at)) / 60000));
}

const CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";

function makeKioskLink(d: DB, facility_id: string, label: string, createdBy: string, code?: string, for_home = false): StoredKioskLink {
  const c = code ?? Array.from(crypto.getRandomValues(new Uint8Array(8)), (b) => CODE_ALPHABET[b % CODE_ALPHABET.length]).join("");
  const user = { id: uid("usr"), phone: `kiosk-${c}`, name: `Kiosk · ${label}`, role: "kiosk" as const, facility_id, registration_no: null, language: "en", has_pin: false, created_at: new Date().toISOString(), active: true };
  d.users.push(user);
  const link: StoredKioskLink = { id: uid("kl"), code: c, label, facility_id, user_id: user.id, created_by: createdBy, created_at: new Date().toISOString(), revoked: false, last_used_at: null, sessions: 0, for_home };
  d.kioskLinks.push(link);
  return link;
}

function linkOut(d: DB, k: StoredKioskLink): KioskLink {
  const day = dayKey();
  const { user_id: _u, ...rest } = k;
  void _u;
  return {
    ...rest,
    url: `${window.location.origin}/k/${k.code}`,
    intakes_today: d.encounters.filter((e) => e.facility_id === k.facility_id && (e.channel === "kiosk_link" || e.channel === "home_link") && (e as Encounter & { token_date?: string }).token_date === day).length,
  };
}

function inferSpecialist(p: IntakePayload, patient: Patient): string {
  const t = [p.chief_complaint, ...p.symptoms.map((s) => s.text)].join(" ").toLowerCase();
  if (patient.age < 12) return "paeds";
  if (p.category === "maternal") return "obgyn";
  if (/chest/.test(t)) return "cardio";
  if (/breath|copd|asthma/.test(t)) return "pulmo";
  if (/diabet|sugar|thirst/.test(t)) return "endo";
  if (/burn/.test(t)) return "burns";
  if (/fracture|fall/.test(t)) return "ortho";
  return "genmed";
}

/* ── Session helpers ──────────────────────────────────── */

function issueTokens(user: User): Tokens {
  const exp = Date.now() + 8 * 3600000;
  const tok = `mock.${btoa(JSON.stringify({ sub: user.id, role: user.role, exp }))}`;
  return { access_token: tok, refresh_token: tok + ".r", token_type: "bearer", expires_in: 8 * 3600 };
}

function publicUser(u: DB["users"][number]): User {
  const { pinHash, active: _a, ...rest } = u;
  void _a;
  return { ...rest, has_pin: !!pinHash || (pinHash === undefined && DEMO_PHONES.includes(u.phone) && PIN_ROLES.includes(u.role)) };
}

async function current(d: DB): Promise<User> {
  const t = getTokens();
  if (!t) throw new ApiError(401, "Not signed in");
  try {
    const payload = JSON.parse(atob(t.access_token.split(".")[1])) as { sub: string; exp: number };
    if (payload.exp < Date.now()) throw new Error("expired");
    const u = d.users.find((x) => x.id === payload.sub);
    if (!u || u.active === false) throw new Error("gone");
    return publicUser(u);
  } catch {
    setTokens(null);
    throw new ApiError(401, "Session expired — please sign in again");
  }
}

/** A patient account is linked to exactly one patient record (phone + name), even on a shared household phone. */
function requireRole(u: User, roles: Role[]) {
  if (!roles.includes(u.role)) throw new ApiError(403, `This action is not available to the ${u.role} role`);
}

const RANK: Record<Urgency, number> = { green: 0, yellow: 1, red: 2 };
const ROLE_SEES: Partial<Record<Role, string[]>> = { health_worker: ["health_worker"], nurse: ["health_worker", "nurse"] };

function canConfirm(role: Role, u: Urgency | null): boolean {
  const limit = SIGN_OFF[role];
  return !!limit && !!u && RANK[u] <= RANK[limit];
}

function forRole(e: Encounter, u: User): Encounter {
  if (u.role === "kiosk") {
    // Health outputs stay reviewer-facing: strip urgency, note and override.
    const home_advice = e.channel === "home_link" ? (e.urgency === "red" ? "emergency" : "show_at_desk") : null;
    return { ...clone(e), urgency: null, note: null, override: null, escalation_due_at: null, specialist_required: null, referral_needed: null, home_advice };
  }
  const out = clone(e);
  out.can_confirm = canConfirm(u.role, out.urgency);
  out.sign_off = out.urgency === "green" ? "health_worker" : out.urgency === "yellow" ? "nurse" : "doctor";
  if (out.note) {
    const sees = ROLE_SEES[u.role];
    out.note.followup_questions = out.note.followup_questions.filter((q) => !sees || sees.includes(q.for_role));
    out.note.detail_level = u.role === "health_worker" ? "summary" : "full";
    if (u.role === "health_worker") {
      out.note = { ...out.note, rules_fired: [], labs: [], timeline: [], trend: [], disagreements: [], documents: [], medications_pending: [] };
    }
  }
  return out;
}

function mockCapacity(d: DB, me: User): Capacity {
  const reds = d.encounters.filter((e) => e.facility_id === me.facility_id && e.urgency === "red" && ["queued", "in_review", "escalated"].includes(e.status));
  const docs = d.users.filter((u) => u.facility_id === me.facility_id && DOCTOR_ROLES.includes(u.role) && (u as { on_duty?: boolean }).on_duty !== false).length;
  const now = Date.now();
  const rows = reds.map((e) => ({ token: e.token ?? null, wait_minutes: Math.max(0, Math.round((now - Date.parse(e.created_at)) / 60000)), status: e.status }));
  const over = reds.length > docs;
  const iso = new Date().toISOString();
  const alert: Alert | null = over
    ? { id: "alr_capacity", facility_id: me.facility_id ?? "", kind: "capacity", key: "red", to_role: "medical_officer", assigned_to: null,
        title: `${reds.length} RED cases waiting, ${docs} doctors or medical officers on duty`, detail: { open_red: reds.length, doctors_on_duty: docs }, status: "open", raised_at: iso, updated_at: iso }
    : null;
  return { open_red: reds.length, doctors_on_duty: docs, over, reds: rows, alert };
}

async function autoEscalate(d: DB) {
  const now = Date.now();
  let changed = false;
  for (const e of d.encounters) {
    if (e.status !== "queued" || !e.escalation_due_at || !e.urgency) continue;
    if (Date.parse(e.escalation_due_at) > now) continue;
    if (d.escalations.some((x) => x.encounter_id === e.id)) continue;
    const esc: Escalation = {
      id: uid("esc"),
      encounter_id: e.id,
      patient_name: e.patient.name,
      urgency: e.urgency,
      raised_by: "Escalation timer",
      raised_at: e.escalation_due_at,
      to_role: "senior_mo",
      reason: `Unreviewed ${e.urgency === "red" ? "critical" : "semi-urgent"} case past ${ESCALATE_AFTER_MIN[e.urgency]} min`,
      auto: true,
      status: "open",
    };
    d.escalations.push(esc);
    e.status = "escalated";
    await audit(d, null, "ESCALATE", "encounter", e.id, esc.reason, e.patient.code);
    changed = true;
  }
  if (changed) await persist();
}

function sanitizeFile(f: StoredFile): FileObject {
  const { data_url, ...rest } = f;
  delete (rest as Partial<StoredFile>).sample_key;
  delete (rest as Partial<StoredFile>).boxes;
  return { ...rest, url: f.purged_at ? null : data_url };
}

const LAT = 180;
const DEMO_PHONES = ["9000000001", "9000000002", "9000000003", "9000000004", "9000000005", "9000000006", "9000000007"];

function pinStepUser(token: string) {
  return token.startsWith("pinstep.") ? token.slice(8) : "";
}

async function pinMatches(u: { id: string; phone: string; pinHash?: string | null }, pin: string) {
  if (u.pinHash) return u.pinHash === (await sha256(pin + u.id));
  return u.pinHash === undefined && DEMO_PHONES.includes(u.phone) && pin === SAMPLE_PIN;
}

const MOCK_ORG = { id: "org_kalinganagar", name: "Kalinga Steel Works (sample)", kind: "industrial" as const, registration_no: null, state: "Odisha", district: "Jajpur", address: null, contact_phone: null, verified: false, created_at: new Date(0).toISOString() };

async function withDb<T>(fn: (d: DB) => Promise<T>): Promise<T> {
  const d = await load();
  await sleep(LAT);
  const out = await fn(d);
  await persist();
  return out;
}

/* ── API implementation ──────────────────────────────── */

export const mockApi: JeeviaApi = {
  mode: "mock",

  authOptions: async () => ({ sms: true, email: false }),
  emailStart: async () => {
    throw new ApiError(503, "Email codes are not enabled on this server");
  },
  emailConfirm: async () => {
    throw new ApiError(503, "Email codes are not enabled on this server");
  },
  emailRemove: async () => {
    throw new ApiError(503, "Email codes are not enabled on this server");
  },

  requestOtp: (target) =>
    withDb(async (d) => {
      if (typeof target !== "string") throw new ApiError(503, "Email codes are not enabled on this server");
      const phone = target;
      if (!/^\d{10}$/.test(phone)) throw new ApiError(422, "Enter a valid 10-digit mobile number");
      const id = uid("otp");
      d.otps[id] = { phone, code: DEMO_OTP, exp: Date.now() + 5 * 60000 };
      return { challenge_id: id, expires_in: 300, dev_code: DEMO_OTP };
    }),

  verifyOtp: (challengeId, code, purpose = "signin") =>
    withDb(async (d) => {
      const c = d.otps[challengeId];
      if (!c || c.exp < Date.now()) throw new ApiError(400, "OTP expired — request a new one");
      if (c.code !== code) throw new ApiError(400, "Incorrect OTP");
      delete d.otps[challengeId];
      const u = d.users.find((x) => x.phone === c.phone);
      if (u && purpose === "register") throw new ApiError(409, "This mobile number is already registered. Each number can hold only one account — sign in instead, or register with your own number.");
      if (!u) {
        const token = uid("reg");
        d.registrations[token] = { phone: c.phone, exp: Date.now() + 15 * 60000 };
        return { status: "new_user" as const, registration_token: token };
      }
      if (PIN_ROLES.includes(u.role)) {
        const has = u.pinHash !== null && (u.pinHash !== undefined || DEMO_PHONES.includes(u.phone));
        return { status: has ? ("pin_required" as const) : ("pin_setup_required" as const), pin_token: `pinstep.${u.id}`, name: u.name, can_reset_pin: ["supervisor", "employer"].includes(u.role) };
      }
      const tokens = issueTokens(publicUser(u));
      setTokens(tokens);
      await audit(d, publicUser(u), "LOGIN", "user", u.id, "Signed in with phone + OTP");
      return { status: "authenticated" as const, tokens, user: publicUser(u) };
    }),

  register: (input) =>
    withDb(async (d) => {
      const r = d.registrations[input.registration_token];
      if (!r || r.exp < Date.now()) throw new ApiError(400, "Registration session expired — verify your phone again");
      if (!input.accepted_terms) throw new ApiError(422, "Terms must be accepted");
      let facilityId = input.facility_id;
      if (input.role === "supervisor" && input.new_facility && !facilityId) {
        const nf = input.new_facility;
        const f: Facility = {
          id: uid("fac"), name: nf.name.trim(), type: nf.type, district: nf.district.trim(), state: nf.state.trim(),
          languages: input.language === "en" ? ["en", "hi"] : [input.language, "en"],
          specialists: [{ key: "genmed", label: "General Medicine", available: true, schedule: null }],
          referral_destination: nf.referral_destination ?? "", beds_total: 0, beds_occupied: 0, offline_mode: nf.type === "health_camp", capabilities: {},
        };
        d.facilities.push(f);
        facilityId = f.id;
      }
      const user: User = {
        id: uid("usr"),
        phone: r.phone,
        name: input.name,
        role: input.role,
        facility_id: facilityId,
        registration_no: input.registration_no ?? null,
        language: input.language,
        has_pin: false,
        created_at: new Date().toISOString(),
      };
      if (PIN_ROLES.includes(input.role)) {
        const problem = pinProblem(input.pin ?? "");
        if (problem) throw new ApiError(422, problem);
      }
      d.users.push({ ...user, pinHash: input.pin ? await sha256(input.pin + user.id) : undefined });
      delete d.registrations[input.registration_token];
      await audit(d, user, "CREATE", "user", user.id, `Registered as ${input.role}; terms accepted`);
      const tokens = issueTokens(user);
      setTokens(tokens);
      return { tokens, user };
    }),

  verifyPin: (pinToken, pin) =>
    withDb(async (d) => {
      const u = d.users.find((x) => x.id === pinStepUser(pinToken));
      if (!u) throw new ApiError(401, "Sign in again");
      if (!(await pinMatches(u, pin))) throw new ApiError(400, "Incorrect PIN");
      const user = publicUser(u);
      const tokens = issueTokens(user);
      setTokens(tokens);
      await audit(d, user, "LOGIN", "user", u.id, "Signed in with phone OTP + PIN");
      return { tokens, user };
    }),

  setupPin: (pinToken, pin) =>
    withDb(async (d) => {
      const u = d.users.find((x) => x.id === pinStepUser(pinToken));
      if (!u) throw new ApiError(401, "Sign in again");
      const problem = pinProblem(pin);
      if (problem) throw new ApiError(422, problem);
      u.pinHash = await sha256(pin + u.id);
      const user = publicUser(u);
      const tokens = issueTokens(user);
      setTokens(tokens);
      return { tokens, user };
    }),

  forgotPin: (pinToken) =>
    withDb(async (d) => {
      const u = d.users.find((x) => x.id === pinStepUser(pinToken));
      if (!u) throw new ApiError(401, "Sign in again");
      if (!["supervisor", "employer"].includes(u.role)) throw new ApiError(403, "Ask your facility supervisor to reset your PIN");
      u.pinHash = null;
      return { status: "pin_setup_required" as const, pin_token: pinToken, name: u.name, can_reset_pin: true };
    }),

  changePin: (currentPin, newPin) =>
    withDb(async (d) => {
      const me = await current(d);
      const u = d.users.find((x) => x.id === me.id)!;
      if (!(await pinMatches(u, currentPin))) throw new ApiError(400, "Current PIN is incorrect");
      const problem = pinProblem(newPin);
      if (problem) throw new ApiError(422, problem);
      u.pinHash = await sha256(newPin + u.id);
    }),

  resetStaffPin: (id) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, ["supervisor"]);
      const u = d.users.find((x) => x.id === id && x.facility_id === me.facility_id);
      if (!u) throw new ApiError(404, "Staff member not found");
      u.pinHash = null;
    }),

  me: () => withDb(async (d) => current(d)),
  updateMe: (patch) =>
    withDb(async (d) => {
      const me = await current(d);
      const u = d.users.find((x) => x.id === me.id)!;
      if (patch.language) u.language = patch.language;
      return publicUser(u);
    }),

  logout: async () => {
    setTokens(null);
  },

  listDevices: () =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, STAFF_ROLES);
      return d.devices.filter((x) => x.facility_id === me.facility_id);
    }),

  bindDevice: (label, deviceId) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, STAFF_ROLES);
      const existing = d.devices.find((x) => x.id === deviceId);
      if (existing) {
        existing.revoked = false;
        existing.label = label;
        existing.last_seen_at = new Date().toISOString();
        await audit(d, me, "DEVICE", "device", deviceId, `Kiosk device '${label}' re-bound`);
        return existing;
      }
      const dev: Device = { id: deviceId, label, facility_id: me.facility_id!, bound_by: me.name, bound_at: new Date().toISOString(), last_seen_at: new Date().toISOString(), revoked: false };
      d.devices.push(dev);
      await audit(d, me, "DEVICE", "device", deviceId, `Kiosk device '${label}' bound to facility`);
      return dev;
    }),

  revokeDevice: (id) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, ADMIN_ROLES);
      const dev = d.devices.find((x) => x.id === id);
      if (!dev) throw new ApiError(404, "Device not found");
      dev.revoked = true;
      await audit(d, me, "DEVICE", "device", id, `Kiosk device '${dev.label}' revoked`);
    }),

  listFacilities: () => withDb(async (d) => clone(d.facilities)),

  getFacility: (id) =>
    withDb(async (d) => {
      const f = d.facilities.find((x) => x.id === id);
      if (!f) throw new ApiError(404, "Facility not found");
      return clone(f);
    }),

  updateFacility: (id, patch) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, ADMIN_ROLES);
      const f = d.facilities.find((x) => x.id === id);
      if (!f) throw new ApiError(404, "Facility not found");
      const changed = Object.keys(patch).filter((k) => JSON.stringify((f as never)[k]) !== JSON.stringify((patch as never)[k]));
      Object.assign(f, patch, { id });
      await audit(d, me, "CONFIG", "facility", id, `Facility configuration updated: ${changed.join(", ") || "no changes"}`);
      return clone(f);
    }),

  facilityStats: (id) =>
    withDb(async (d) => {
      await current(d);
      await autoEscalate(d);
      const today = new Date().toDateString();
      const list = d.encounters.filter((e) => e.facility_id === id && new Date(e.created_at).toDateString() === today);
      const waiting = list.filter((e) => ["queued", "escalated"].includes(e.status));
      return {
        facility_id: id,
        today_total: list.length,
        by_urgency: {
          red: list.filter((e) => e.urgency === "red").length,
          yellow: list.filter((e) => e.urgency === "yellow").length,
          green: list.filter((e) => e.urgency === "green").length,
        },
        avg_wait_minutes: waiting.length ? Math.round(waiting.reduce((s, e) => s + (Date.now() - Date.parse(e.created_at)) / 60000, 0) / waiting.length) : 0,
        open_escalations: d.escalations.filter((x) => x.status === "open" && list.some((e) => e.id === x.encounter_id)).length,
        referrals_today: d.referrals.filter((r) => list.some((e) => e.id === r.encounter_id)).length,
        offline_synced_today: list.filter((e) => e.intake?.captured_offline).length,
      };
    }),

  facilityTokens: (id) =>
    withDb(async (d) => {
      const me = await current(d);
      if (!STAFF_ROLES.includes(me.role) || me.facility_id !== id) throw new ApiError(403, "Not allowed");
      const day = dayKey();
      for (const e of d.encounters) if (e.status === "expected" && Date.now() - Date.parse(e.created_at) > 36 * 3600_000) e.status = "lapsed";
      return d.encounters
        .filter((e) => e.facility_id === id && ((e as Encounter & { token_date?: string }).token_date === day || e.status === "expected"))
        .sort((a, b) => b.created_at.localeCompare(a.created_at))
        .map((e) => ({ encounter_id: e.id, token: e.token ?? null, patient_id: e.patient.id, patient_name: e.patient.name, patient_code: e.patient.code, status: e.status, channel: e.channel ?? "staff_kiosk", created_at: e.created_at, arrived_at: e.arrived_at ?? null, wait_minutes: e.status === "expected" ? 0 : waitMin(e) }));
    }),

  checkIn: (id) =>
    withDb(async (d) => {
      const me = await current(d);
      if (!STAFF_ROLES.includes(me.role)) throw new ApiError(403, "Not allowed");
      const e = d.encounters.find((x) => x.id === id && x.facility_id === me.facility_id);
      if (!e) throw new ApiError(404, "Not found");
      if (e.status !== "expected") throw new ApiError(409, e.arrived_at ? "Already checked in" : `This intake is ${e.status}`);
      e.arrived_at = new Date().toISOString();
      e.status = "queued";
      assignToken(d, e, e.channel ?? "home_link");
      const mins = e.urgency === "red" ? 15 : e.urgency === "yellow" ? 60 : null;
      e.escalation_due_at = mins ? new Date(Date.now() + mins * 60000).toISOString() : null;
      await audit(d, me, "ARRIVE", "encounter", e.id, `Checked in at the desk (filled in from home); token ${e.token}`, e.patient.code);
      return forRole(e, me);
    }),

  listKioskLinks: () =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, ADMIN_ROLES);
      return d.kioskLinks.filter((k) => k.facility_id === me.facility_id).map((k) => linkOut(d, k)).reverse();
    }),

  createKioskLink: (label, forHome = false) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, ADMIN_ROLES);
      const k = makeKioskLink(d, me.facility_id!, label.trim(), me.name, undefined, forHome);
      await audit(d, me, "DEVICE", "kiosk_link", k.id, `Kiosk link '${k.label}' created (${k.code})${forHome ? " for filling in from home" : ""}`);
      return linkOut(d, k);
    }),

  revokeKioskLink: (id) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, ADMIN_ROLES);
      const k = d.kioskLinks.find((x) => x.id === id && x.facility_id === me.facility_id);
      if (!k) throw new ApiError(404, "Kiosk link not found");
      k.revoked = true;
      const u = d.users.find((x) => x.id === k.user_id);
      if (u) u.active = false;
      await audit(d, me, "DEVICE", "kiosk_link", k.id, `Kiosk link '${k.label}' revoked`);
    }),

  kioskInfo: (code) =>
    withDb(async (d) => {
      const k = d.kioskLinks.find((x) => x.code === code.toUpperCase() && !x.revoked);
      if (!k) throw new ApiError(404, "This kiosk link is not active. Ask the facility for a new one.");
      const f = d.facilities.find((x) => x.id === k.facility_id)!;
      return { code: k.code, label: k.label, facility_id: f.id, facility_name: f.name, district: f.district, state: f.state, languages: f.languages, for_home: !!k.for_home };
    }),

  kioskSession: (code, deviceId) =>
    withDb(async (d) => {
      const k = d.kioskLinks.find((x) => x.code === code.toUpperCase() && !x.revoked);
      const u = k && d.users.find((x) => x.id === k.user_id && x.active !== false);
      if (!k || !u) throw new ApiError(404, "This kiosk link is not active.");
      k.sessions++;
      k.last_used_at = new Date().toISOString();
      const user = publicUser(u);
      const tokens = issueTokens(user);
      setTokens(tokens);
      await audit(d, user, "LOGIN", "kiosk_link", k.id, `Kiosk session opened on device ${deviceId.slice(0, 12)}`);
      return { tokens, user };
    }),

  kioskIdentify: (patientCode, phone) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, ["kiosk"]);
      const p = d.patients.find((x) => x.code.toLowerCase() === patientCode.trim().toLowerCase() && x.phone === phone);
      if (!p) throw new ApiError(404, "No match — check the ID and phone, or register as new");
      await audit(d, me, "VIEW", "patient", p.id, "Returning patient identified at kiosk (ID + phone)", p.code);
      return clone(p);
    }),

  createShare: (encounterId, hours, purpose = "referral") =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, REVIEWER_ROLES);
      const e = d.encounters.find((x) => x.id === encounterId);
      if (!e) throw new ApiError(404, "Encounter not found");
      d.shares ??= [];
      const code = String(crypto.getRandomValues(new Uint32Array(1))[0] % 1_000_000).padStart(6, "0");
      const s = { id: uid("shr"), token: crypto.randomUUID().replace(/-/g, ""), code, encounter_id: e.id, purpose, created_by: me.name, created_at: new Date().toISOString(), expires_at: new Date(Date.now() + hours * 3600000).toISOString(), revoked: false, views: 0, failed: 0 };
      d.shares.push(s);
      await audit(d, me, "EXPORT", "share", s.id, `QR summary link created (${purpose}, valid ${hours}h)`, e.patient.code);
      return { id: s.id, url: `${window.location.origin}/s/${s.token}`, access_code: code, purpose, created_by: s.created_by, created_at: s.created_at, expires_at: s.expires_at, revoked: false, views: 0 };
    }),

  listShares: (encounterId) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, REVIEWER_ROLES);
      return (d.shares ?? []).filter((s) => s.encounter_id === encounterId).reverse().map((s) => ({ id: s.id, url: `${window.location.origin}/s/${s.token}`, access_code: null, purpose: s.purpose, created_by: s.created_by, created_at: s.created_at, expires_at: s.expires_at, revoked: s.revoked, views: s.views }));
    }),

  revokeShare: (id) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, REVIEWER_ROLES);
      const s = (d.shares ?? []).find((x) => x.id === id);
      if (!s) throw new ApiError(404, "Share link not found");
      s.revoked = true;
    }),

  shareMeta: (token) =>
    withDb(async (d) => {
      const s = (d.shares ?? []).find((x) => x.token === token && !x.revoked);
      if (!s) throw new ApiError(404, "This summary link is not valid.");
      if (Date.parse(s.expires_at) < Date.now()) throw new ApiError(410, "This summary link has expired.");
      const e = d.encounters.find((x) => x.id === s.encounter_id)!;
      return { facility_name: d.facilities.find((f) => f.id === e.facility_id)?.name ?? "", purpose: s.purpose, expires_at: s.expires_at };
    }),

  openShare: (token, accessCode) =>
    withDb(async (d) => {
      const s = (d.shares ?? []).find((x) => x.token === token && !x.revoked);
      if (!s) throw new ApiError(404, "This summary link is not valid.");
      if (s.failed >= 8) throw new ApiError(423, "Locked after too many wrong codes.");
      if (s.code !== accessCode) {
        s.failed++;
        throw new ApiError(403, `Wrong access code. ${8 - s.failed} attempts left.`);
      }
      s.views++;
      const e = d.encounters.find((x) => x.id === s.encounter_id)!;
      const f = d.facilities.find((x) => x.id === e.facility_id);
      const ref = d.referrals.filter((r) => r.encounter_id === e.id).pop() ?? null;
      const docs = (e.intake?.file_ids ?? []).map((id) => d.files.find((x) => x.id === id)).filter((x): x is StoredFile => !!x && x.kind !== "audio");
      await audit(d, null, "VIEW", "share", s.id, `QR summary opened (view ${s.views})`, e.patient.code);
      const n = e.note;
      return {
        facility: { name: f?.name, district: f?.district, state: f?.state, type: f?.type },
        patient: { name: e.patient.name, code: e.patient.code, age: e.patient.age, sex: e.patient.sex, language: e.patient.language, phone: e.patient.phone },
        encounter: { token: e.token ?? null, created_at: e.created_at, category: e.category, chief_complaint: e.chief_complaint, status: e.status, urgency: e.urgency, urgency_source: e.urgency_source, override: e.override ?? null, reviewed_by: e.reviewed_by ?? null, reviewed_at: e.reviewed_at ?? null, maternal: e.intake?.maternal ?? null, chronic: e.intake?.chronic ?? null, consent: e.consent ? { mode: e.consent.mode, proxy_name: e.consent.proxy_name ?? null, proxy_relation: e.consent.proxy_relation ?? null } : null },
        note: n ? { summary: n.summary, flags: n.flags, vitals: n.vitals, labs: n.labs, timeline: n.timeline, missing_info: n.missing_info, disagreements: n.disagreements, rules_fired: n.rules_fired } : null,
        referral: ref ? { destination: ref.destination, specialty: ref.specialty, reason: ref.reason, transport: ref.transport, created_by: ref.created_by, created_at: ref.created_at, note_text: ref.note_text, status: ref.status, received_by: ref.received_by ?? null, received_at: ref.received_at ?? null } : null,
        documents: docs.map((x) => ({ id: x.id, filename: x.filename, kind: x.kind, content_type: x.content_type, uploaded_at: x.uploaded_at, url: x.purged_at ? null : x.data_url })),
        shared_by: s.created_by,
        expires_at: s.expires_at,
        disclaimer: "Triage support only. Not a diagnosis.",
      };
    }),

  shareReceived: (token, accessCode, confirmedBy, note) =>
    withDb(async (d) => {
      const s = (d.shares ?? []).find((x) => x.token === token && !x.revoked);
      if (!s) throw new ApiError(404, "This summary link is not valid.");
      if (s.code !== accessCode) {
        s.failed++;
        throw new ApiError(403, "Wrong access code.");
      }
      const ref = d.referrals.filter((r) => r.encounter_id === s.encounter_id).pop();
      if (!ref) throw new ApiError(404, "No referral on this summary.");
      if (ref.status === "received") throw new ApiError(409, `Already confirmed received by ${ref.received_by}`);
      Object.assign(ref, { status: "received", received_at: new Date().toISOString(), received_by: confirmedBy.trim(), received_note: note.trim() || null, received_via: "qr" });
      await audit(d, null, "REFERRAL", "referral", ref.id, `Care received at ${ref.destination}; confirmed by ${confirmedBy.trim()}, recorded by the receiving clinician (QR summary)`);
      return { status: "received", received_by: ref.received_by!, received_at: ref.received_at! };
    }),

  searchDirectory: (q, state) =>
    withDb(async (d) => {
      const s = q.trim().toLowerCase();
      return d.facilities
        .filter((f) => (!state || f.state === state) && (`${f.name} ${f.district}`.toLowerCase().includes(s) || f.pincode === s))
        .map((f) => ({
          key: `fac:${f.id}`, name: f.name, kind: f.type, kind_label: f.type.replace(/_/g, " "), type: f.type, ownership: f.organisation_id ? "private" : "public",
          state: f.state, district: f.district, city: null, pincode: f.pincode ?? null, source: f.source ?? "sample", directory_ref: null, facility_id: f.id,
          organisation_name: f.organisation_id ? "Kalinga Steel Works (sample)" : null, verified: false,
        }));
    }),

  directoryStates: () => withDb(async (d) => [...new Set(d.facilities.map((f) => f.state))].sort().map((state) => ({ state, facilities: d.facilities.filter((f) => f.state === state).length }))),

  myOrganisation: () =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, ["employer"]);
      return { organisation: MOCK_ORG, facilities: clone(d.facilities.filter((f) => f.id === me.facility_id)) };
    }),

  updateOrganisation: async () => {
    throw new ApiError(501, "Editing the organisation needs the live API");
  },
  addOrganisationFacility: async () => {
    throw new ApiError(501, "Adding workplaces needs the live API");
  },

  listWorkers: () =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, ["employer"]);
      return d.cohorts.flatMap((c) =>
        c.workers.map((w) => ({ employee_code: w.worker_code, name: `Worker ${w.worker_code} (sample)`, department: w.department, patient_code: `JVA-${w.worker_code}`, fitness_status: w.fitness_status, restrictions: null, valid_until: null, last_assessed_at: w.last_screened_at, assessed_by: w.last_screened_at ? "Occupational Health Physician (sample)" : null })),
      );
    }),

  addWorker: async () => {
    throw new ApiError(501, "Managing the roster needs the live API");
  },
  importWorkers: async () => {
    throw new ApiError(501, "Managing the roster needs the live API");
  },
  removeWorker: async () => {
    throw new ApiError(501, "Managing the roster needs the live API");
  },
  recordFitness: async () => {
    throw new ApiError(501, "Recording fitness needs the live API");
  },

  updateUser: (id, patch) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, ["supervisor"]);
      const u = d.users.find((x) => x.id === id && x.facility_id === me.facility_id);
      if (!u) throw new ApiError(404, "Staff member not found");
      if (u.id === me.id) throw new ApiError(422, "You cannot change your own role or access");
      if (patch.role) u.role = patch.role;
      if (patch.is_active !== undefined) u.active = patch.is_active;
      await audit(d, me, "UPDATE", "user", u.id, `Staff ${u.name} updated`);
      return { ...publicUser(u), is_active: u.active !== false };
    }),

  correctPatient: (id, patch) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, STAFF_ROLES);
      const p = d.patients.find((x) => x.id === id);
      if (!p) throw new ApiError(404, "Patient not found");
      Object.assign(p, Object.fromEntries(Object.entries(patch).filter(([, v]) => v !== undefined && v !== null)));
      for (const e of d.encounters) if (e.patient.id === id) e.patient = clone(p);
      await audit(d, me, "UPDATE", "patient", id, `Patient details corrected: ${Object.keys(patch).join(", ")}`, p.code);
      return clone(p);
    }),

  listUsers: () =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, ADMIN_ROLES);
      return d.users
        .filter((u) => u.facility_id === me.facility_id && u.role !== "kiosk" && (me.role === "supervisor" || u.role === "doctor" || u.role === "nurse"))
        .map((u) => ({ ...publicUser(u), is_active: u.active !== false }));
    }),

  setDuty: (id, onDuty) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, ADMIN_ROLES);
      const u = d.users.find((x) => x.id === id && x.facility_id === me.facility_id && (x.role === "doctor" || x.role === "nurse"));
      if (!u) throw new ApiError(404, "Doctor or nurse not found");
      u.on_duty = onDuty;
      u.duty_changed_at = new Date().toISOString();
      await audit(d, me, "UPDATE", "user", u.id, `${u.name} marked ${onDuty ? "on" : "off"} duty`);
      return publicUser(u);
    }),

  reviewMedications: (eid) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, ["doctor", "nurse"]);
      const enc = d.encounters.find((e) => e.id === eid);
      if (!enc) throw new ApiError(404, "Encounter not found");
      return clone(enc); // the in-browser demo never reads medicine strips (no OCR), so there is nothing to confirm
    }),

  addObservations: (eid, input) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, ["doctor", "nurse"]);
      const e = d.encounters.find((x) => x.id === eid);
      if (!e || !e.note) throw new ApiError(404, "Encounter not found");
      const vitals = Object.fromEntries(Object.entries(input.vitals ?? {}).filter(([, v]) => v != null));
      if (!Object.keys(vitals).length && !input.note?.trim()) throw new ApiError(422, "Enter at least one vital sign or an observation");
      e.note.observations = [...(e.note.observations ?? []), { by: me.name, role: me.role, at: new Date().toISOString(), vitals, note: input.note?.trim() || null }];
      await audit(d, me, "UPDATE", "encounter", e.id, `Observations recorded by ${me.role}`);
      return e as unknown as Encounter;
    }),

  searchPatients: (q) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, STAFF_ROLES);
      const s = q.trim().toLowerCase().replace(/\s|\+91/g, "");
      if (!s) return [];
      const hits = d.patients.filter((p) => p.code.toLowerCase() === s || p.code.toLowerCase().includes(s) || (p.phone ?? "").includes(s) || p.name.toLowerCase().includes(s));
      await audit(d, me, "VIEW", "patient_search", null, `Searched patients: "${q}" (${hits.length} candidates)`);
      return hits.map((p) => {
        const last = d.encounters.filter((e) => e.patient.id === p.id).sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
        const reason = p.code.toLowerCase() === s ? "Exact patient ID" : (p.phone ?? "").includes(s) ? "Shared household phone" : "Name match";
        return { patient: clone(p), last_visit_at: last?.created_at ?? null, match_reason: reason };
      });
    }),

  getPatient: (id) =>
    withDb(async (d) => {
      const me = await current(d);
      const p = d.patients.find((x) => x.id === id);
      if (!p) throw new ApiError(404, "Patient not found");
      await audit(d, me, "VIEW", "patient", id, "Patient identity viewed", p.code);
      return clone(p);
    }),

  pickPatient: (id, matchReason, candidates) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, STAFF_ROLES);
      const p = d.patients.find((x) => x.id === id);
      if (!p) throw new ApiError(404, "Patient not found");
      await audit(d, me, "VIEW", "patient", p.id, `Patient picked by staff from ${candidates} candidate(s); match: ${matchReason || "not given"}`, p.code);
      return clone(p);
    }),

  getPatientByCode: (code) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, STAFF_ROLES);
      const p = d.patients.find((x) => x.code.toLowerCase() === code.trim().toLowerCase());
      if (!p) throw new ApiError(404, `No patient with ID ${code}`);
      await audit(d, me, "VIEW", "patient", p.id, "Patient opened by ID / QR scan", p.code);
      return clone(p);
    }),

  createPatient: (input) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, [...STAFF_ROLES, "kiosk"]);
      const p: Patient = { ...input, id: uid("pat"), code: `JVA-P${String(++d.seq).padStart(3, "0")}`, created_at: new Date().toISOString() };
      d.patients.push(p);
      await audit(d, me, "CREATE", "patient", p.id, "Patient registered at intake", p.code);
      return clone(p);
    }),

  patientEncounters: (patientId) =>
    withDb(async (d) => {
      const me = await current(d);
      if (ADMIN_ROLES.includes(me.role)) throw new ApiError(403, "Facility admins cannot read clinical records");
      const p = d.patients.find((x) => x.id === patientId);
      const list = d.encounters.filter((e) => e.patient.id === patientId).sort((a, b) => b.created_at.localeCompare(a.created_at));
      await audit(d, me, "VIEW", "patient", patientId, `Encounter history viewed (${list.length})`, p?.code ?? null);
      return list.map((e) => forRole(e, me));
    }),

  captureConsent: (input) =>
    withDb(async (d) => {
      const me = await current(d);
      if (input.mode === "proxy" && (!input.proxy_name || !input.proxy_relation)) throw new ApiError(422, "Proxy name and relationship are required");
      const c: Consent = { ...input, id: uid("con"), captured_by: me.name, captured_at: new Date().toISOString() };
      d.consents.push(c);
      const p = d.patients.find((x) => x.id === input.patient_id);
      await audit(d, me, "CONSENT", "consent", c.id, `${input.mode === "proxy" ? `Proxy consent by ${input.proxy_name} (${input.proxy_relation})` : "Self consent"}; privacy: ${input.privacy_context}; scopes: ${input.scopes.join(", ")}`, p?.code ?? null);
      return c;
    }),

  submitIntake: (payload) =>
    withDb(async (d) => {
      const me = await current(d);
      if (!["nurse", "doctor", "receptionist", "supervisor", "kiosk"].includes(me.role)) throw new ApiError(403, "Not allowed");
      const dup = d.encounters.find((e) => e.intake?.client_ref === payload.client_ref);
      if (dup) return forRole(dup, me); // idempotent offline replay
      const p = d.patients.find((x) => x.id === payload.patient_id);
      if (!p) throw new ApiError(404, "Patient not found");
      if (payload.facility_id !== me.facility_id) throw new ApiError(403, "Intakes can only be submitted for your own facility");
      if (me.role !== "kiosk") {
        const dev = d.devices.find((x) => x.id === getDeviceId());
        if (!dev || dev.revoked || dev.facility_id !== me.facility_id) throw new ApiError(403, "This device is not bound to your facility — bind it from the kiosk screen");
        dev.last_seen_at = new Date().toISOString();
      }
      if (!payload.consent_id) throw new ApiError(422, "Consent must be captured before intake");
      const captured = payload.captured_at && Date.parse(payload.captured_at) < Date.now() ? payload.captured_at : undefined;
      const enc = buildEncounter(d, payload, p, captured);
      const link = me.role === "kiosk" ? d.kioskLinks.find((k) => k.user_id === me.id) : undefined;
      const channel: IntakeChannel = !link ? "staff_kiosk" : link.for_home ? "home_link" : "kiosk_link";
      // From home: not in the queue until the desk checks the patient in; a RED goes to the doctors now (C3)
      const expected = channel === "home_link" && enc.urgency !== "red";
      assignToken(d, enc, channel, expected ? "H" : "T");
      enc.arrived_at = channel === "home_link" ? null : enc.created_at;
      if (expected) {
        enc.status = "expected";
        enc.escalation_due_at = null;
      }
      d.encounters.push(enc);
      for (const id of payload.file_ids) {
        const f = d.files.find((x) => x.id === id);
        if (f) f.encounter_id = enc.id;
      }
      if (payload.maternal?.next_checkup && payload.maternal.reminder_channel !== "none")
        d.reminders.push({ id: uid("rem"), patient_id: p.id, kind: "anc_checkup", due_at: new Date(payload.maternal.next_checkup).toISOString(), channel: payload.maternal.reminder_channel ?? "sms", status: "scheduled", message: `ANC check-up reminder for ${p.name}` });
      await audit(d, me, "CREATE", "encounter", enc.id, `Intake submitted${payload.captured_offline ? " (offline, synced)" : ""}; rules engine: ${enc.urgency}`, p.code);
      if (enc.note?.disagreements.length)
        await audit(d, null, "DISAGREEMENT", "encounter", enc.id, enc.note.disagreements.map((x) => `${x.field}: ${x.values.map((v) => v.value).join(" vs ")}`).join("; "), p.code);
      return forRole(enc, me);
    }),

  queue: (facilityId) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, REVIEWER_ROLES);
      await autoEscalate(d);
      const rank: Record<Urgency, number> = { red: 0, yellow: 1, green: 2 };
      const rows = d.encounters
        .filter((e) => e.facility_id === facilityId && ["queued", "in_review", "escalated"].includes(e.status))
        .map((e) => {
          const raised = (e.note?.flags ?? []).filter((f) => f.severity !== "info").sort((a, b) => Number(a.severity !== "critical") - Number(b.severity !== "critical"));
          return {
          encounter_id: e.id,
          patient_code: e.patient.code,
          patient_name: e.patient.name,
          age: e.patient.age,
          sex: e.patient.sex,
          category: e.category,
          chief_complaint: e.chief_complaint,
          urgency: e.urgency!,
          status: e.status,
          created_at: e.created_at,
          arrived_at: e.arrived_at ?? null,
          wait_minutes: waitMin(e),
          flag_count: raised.length,
          top_flags: raised.slice(0, 2).map((f) => f.label),
          needs_check_count: [...(e.note?.vitals ?? []), ...(e.note?.labs ?? [])].filter((v) => v.needs_check).length,
          language: e.patient.language,
          escalation_due_at: e.escalation_due_at ?? null,
          token: e.token ?? null,
          channel: e.channel,
          vitals_recorded: !!e.note?.vitals.length,
          observation_count: e.note?.observations?.length ?? 0,
          why: e.note?.rules_fired.find((h) => h.urgency === e.urgency && h.rule_id !== "SAFE-PROVISIONAL")?.rule_id ?? (e.note?.triage?.provisional && e.urgency === "yellow" ? "provisional until measured" : ""),
          };
        })
        .sort((a, b) => rank[a.urgency] - rank[b.urgency] || Number(b.status === "escalated") - Number(a.status === "escalated") || b.wait_minutes - a.wait_minutes);
      // same words as the backend's alerts.order_reasons
      const total: Record<string, number> = {};
      rows.forEach((r) => (total[r.urgency] = (total[r.urgency] ?? 0) + 1));
      const seen: Record<string, number> = {};
      const mins = (m: number) => (m < 60 ? `${m} min` : m % 60 ? `${Math.floor(m / 60)} h ${m % 60} min` : `${m / 60} h`);
      const nth = (n: number) => `${n}${n % 100 >= 11 && n % 100 <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] ?? "th"}`;
      return rows.map(({ why, ...r }) => {
        seen[r.urgency] = (seen[r.urgency] ?? 0) + 1;
        const u = r.urgency.toUpperCase();
        const place = r.status === "escalated" ? `escalated, ahead of unescalated ${u}` : "longest first";
        let line = `${why ? `${u} (${why})` : u} · ${nth(seen[r.urgency])} of ${total[r.urgency]} ${u} · waiting ${mins(r.wait_minutes)} since arrival, ${place}`;
        if (r.channel === "home_link") line += " · filled in from home";
        return { ...r, order_reason: line };
      });
    }),

  getEncounter: (id) =>
    withDb(async (d) => {
      const me = await current(d);
      if (ADMIN_ROLES.includes(me.role) || me.role === "employer" || me.role === "kiosk") throw new ApiError(403, "This role cannot read clinical notes");
      const e = d.encounters.find((x) => x.id === id);
      if (!e) throw new ApiError(404, "Encounter not found");
      if (e.status === "queued" && REVIEWER_ROLES.includes(me.role)) e.status = "in_review";
      await audit(d, me, "VIEW", "encounter", id, "Triage note viewed", e.patient.code);
      return forRole(e, me);
    }),

  confirmEncounter: (id) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, REVIEWER_ROLES);
      const e = d.encounters.find((x) => x.id === id);
      if (!e) throw new ApiError(404, "Encounter not found");
      if (!canConfirm(me.role, e.urgency))
        throw new ApiError(403, `A ${me.role.replace("_", " ")} cannot confirm a ${(e.urgency ?? "").toUpperCase()} note — it needs ${e.urgency === "red" ? "a doctor or medical officer" : "a nurse, doctor or medical officer"}`);
      e.status = "confirmed";
      e.reviewed_by = me.name;
      e.reviewed_at = new Date().toISOString();
      await audit(d, me, "CONFIRM", "encounter", id, "Triage note reviewed and confirmed", e.patient.code);
      return clone(e);
    }),

  editNote: (id, patch) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, REVIEWER_ROLES);
      const e = d.encounters.find((x) => x.id === id);
      if (!e?.note) throw new ApiError(404, "Encounter not found");
      Object.assign(e.note, patch, { edited_by: me.name, edited_at: new Date().toISOString() });
      await audit(d, me, "UPDATE", "encounter", id, `Note edited: ${Object.keys(patch).join(", ")}`, e.patient.code);
      return clone(e);
    }),

  overrideUrgency: (id, to, category, reason) =>
    withDb(async (d) => {
      const me = await current(d);
      const e = d.encounters.find((x) => x.id === id);
      if (!e || !e.urgency) throw new ApiError(404, "Encounter not found");
      if (to === e.urgency) throw new ApiError(400, `The urgency is already ${e.urgency.toUpperCase()}`);
      // E9: raising is open to any reviewer; lowering needs a doctor and a written reason.
      const down = RANK[to] < RANK[e.urgency];
      if (down && !DOCTOR_ROLES.includes(me.role)) throw new ApiError(403, "Only a doctor or medical officer can lower the urgency; you can raise it or escalate");
      if (down && reason.trim().length < 15) throw new ApiError(422, "A written reason of at least 15 characters is required to lower the urgency");
      e.override = { from_urgency: e.urgency, to_urgency: to, category, reason: reason.trim(), by: me.name, by_role: me.role, at: new Date().toISOString(), direction: down ? "down" : "up" };
      e.urgency = to;
      e.urgency_source = "override";
      const esc = ESCALATE_AFTER_MIN[to];
      e.escalation_due_at = esc ? new Date(Date.parse(e.created_at) + esc * 60000).toISOString() : null;
      await audit(d, me, "OVERRIDE", "encounter", id, `Urgency ${e.override.from_urgency} → ${to} (${category}). Reason: "${reason.trim()}". Rules-engine output retained for audit.`, e.patient.code);
      return clone(e);
    }),

  setReferralNeeded: (id, needed) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, REVIEWER_ROLES);
      const e = d.encounters.find((x) => x.id === id);
      if (!e) throw new ApiError(404, "Encounter not found");
      e.referral_needed = needed;
      await audit(d, me, "UPDATE", "encounter", id, `Referral needed: ${needed ? "yes" : "no"}`, e.patient.code);
      return clone(e);
    }),

  exportEncounter: (id, format) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, REVIEWER_ROLES);
      const e = d.encounters.find((x) => x.id === id);
      if (!e) throw new ApiError(404, "Encounter not found");
      await audit(d, me, "EXPORT", "encounter", id, `Triage note exported as ${format.toUpperCase()}`, e.patient.code);
      return buildExport(e, format, d.facilities.find((f) => f.id === e.facility_id));
    }),

  escalate: (encounterId, toRole, reason) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, REVIEWER_ROLES);
      const e = d.encounters.find((x) => x.id === encounterId);
      if (!e) throw new ApiError(404, "Encounter not found");
      if (reason.trim().length < 5) throw new ApiError(422, "Give a short reason for escalation");
      const esc: Escalation = { id: uid("esc"), encounter_id: e.id, patient_name: e.patient.name, urgency: e.urgency!, raised_by: me.name, raised_at: new Date().toISOString(), to_role: toRole, reason: reason.trim(), auto: false, status: "open" };
      d.escalations.push(esc);
      e.status = "escalated";
      await audit(d, me, "ESCALATE", "encounter", e.id, `Escalated to ${toRole}: ${reason.trim()}`, e.patient.code);
      return esc;
    }),

  listEscalations: (status) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, REVIEWER_ROLES);
      await autoEscalate(d);
      const facilityEnc = new Set(d.encounters.filter((e) => e.facility_id === me.facility_id).map((e) => e.id));
      return clone(d.escalations.filter((x) => facilityEnc.has(x.encounter_id) && (!status || x.status === status)).sort((a, b) => b.raised_at.localeCompare(a.raised_at)));
    }),

  acknowledgeEscalation: (id, note) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, DOCTOR_ROLES);
      const esc = d.escalations.find((x) => x.id === id);
      if (!esc) throw new ApiError(404, "Escalation not found");
      esc.status = "acknowledged";
      esc.acknowledged_by = me.name;
      esc.acknowledged_at = new Date().toISOString();
      esc.ack_note = note;
      const e = d.encounters.find((x) => x.id === esc.encounter_id);
      if (e && e.status === "escalated") e.status = "in_review";
      await audit(d, me, "ACKNOWLEDGE", "escalation", id, `Escalation acknowledged${note ? `: ${note}` : ""}`, e?.patient.code ?? null);
      return clone(esc);
    }),

  createReferral: (encounterId, input) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, DOCTOR_ROLES);
      const e = d.encounters.find((x) => x.id === encounterId);
      if (!e) throw new ApiError(404, "Encounter not found");
      const dueH = e.urgency === "red" ? 6 : e.urgency === "yellow" ? 48 : 336;
      const r: Referral = { ...input, id: uid("ref"), encounter_id: e.id, patient_name: e.patient.name, created_by: me.name, created_at: new Date().toISOString(), status: "sent", due_at: new Date(Date.now() + dueH * 3600000).toISOString() };
      d.referrals.push(r);
      e.status = "referred";
      e.referral_needed = true;
      e.reviewed_by ??= me.name;
      e.reviewed_at ??= r.created_at;
      await audit(d, me, "REFERRAL", "encounter", e.id, `Referral to ${input.destination} (${input.specialty}); transport: ${input.transport}`, e.patient.code);
      return r;
    }),

  referralReceived: (id, confirmedBy, note) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, DOCTOR_ROLES);
      const r = d.referrals.find((x) => x.id === id);
      if (!r) throw new ApiError(404, "Referral not found");
      if (r.status === "received") throw new ApiError(409, `Already confirmed received by ${r.received_by}`);
      Object.assign(r, { status: "received", received_at: new Date().toISOString(), received_by: confirmedBy.trim(), received_note: note.trim() || null, received_via: "phone" });
      await audit(d, me, "REFERRAL", "referral", r.id, `Care received at ${r.destination}; confirmed by ${confirmedBy.trim()}, recorded by the referring doctor`);
      return clone(r);
    }),

  listReferrals: () =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, REVIEWER_ROLES);
      const t = Date.now();
      return clone(d.referrals)
        .map((r) => ({ ...r, overdue: r.status !== "received" && !!r.due_at && Date.parse(r.due_at) < t }))
        .sort((a, b) => b.created_at.localeCompare(a.created_at));
    }),

  uploadFile: (file, kind, encounterId, sampleKey) =>
    withDb(async (d) => {
      const me = await current(d);
      if (file.size > 8 * 1024 * 1024) throw new ApiError(413, "File too large (max 8 MB)");
      const sample = sampleKey ?? null;
      const boxes = sample ? sampleReportImage(sample, "").boxes : null;
      const dataUrl: string = await new Promise((res, rej) => {
        const fr = new FileReader();
        fr.onload = () => res(fr.result as string);
        fr.onerror = () => rej(fr.error);
        fr.readAsDataURL(file);
      });
      const now = new Date();
      const f: StoredFile = {
        id: uid("file"),
        filename: file.name,
        content_type: file.type || "application/octet-stream",
        size: file.size,
        kind,
        encounter_id: encounterId ?? null,
        uploaded_at: now.toISOString(),
        expires_at: new Date(now.getTime() + RETENTION_HOURS[kind] * 3600000).toISOString(),
        purged_at: null,
        data_url: dataUrl,
        sample_key: sample,
        boxes,
      };
      d.files.push(f);
      await audit(d, me, "UPLOAD", "file", f.id, `${kind} uploaded (${file.name}, ${Math.round(file.size / 1024)} KB); expires ${f.expires_at.slice(0, 16).replace("T", " ")}`);
      return sanitizeFile(f);
    }),

  getFile: (id) =>
    withDb(async (d) => {
      const me = await current(d);
      if (ADMIN_ROLES.includes(me.role) || me.role === "employer") throw new ApiError(403, "This role cannot open clinical files");
      const f = d.files.find((x) => x.id === id);
      if (!f) throw new ApiError(404, "File not found");
      return sanitizeFile(f);
    }),

  // The browser-only demo has no speech models; the kiosk falls back to on-device recognition or typing.
  transcribe: async () => {
    throw new ApiError(503, "Server speech recognition runs only with the live API");
  },
  secondCheck: async () => {
    throw new ApiError(404, "No such check");
  },

  listAudit: (filter) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, [...ADMIN_ROLES, ...DOCTOR_ROLES]);
      const q = filter?.q?.toLowerCase() ?? "";
      return clone(d.audit)
        .filter((a) => (!filter?.action || a.action === filter.action) && (!q || `${a.actor_name} ${a.detail} ${a.patient_code ?? ""}`.toLowerCase().includes(q)))
        .reverse();
    }),

  verifyAudit: () =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, [...ADMIN_ROLES, ...DOCTOR_ROLES]);
      let prev = "GENESIS";
      for (const a of d.audit) {
        const { prev_hash, hash, ...body } = a;
        if (prev_hash !== prev || hash !== (await sha256(prev + JSON.stringify(body)))) return { ok: false, checked: a.id, broken_at: a.id };
        prev = hash;
      }
      return { ok: true, checked: d.audit.length, broken_at: null };
    }),

  exportAuditCsv: () =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, [...ADMIN_ROLES, ...DOCTOR_ROLES]);
      await audit(d, me, "EXPORT", "audit", null, "Audit log exported as CSV");
      const rows = [["id", "ts", "actor", "role", "action", "resource", "patient", "detail", "hash"], ...d.audit.map((a) => [a.id, a.ts, a.actor_name, a.actor_role, a.action, `${a.resource_type}:${a.resource_id ?? ""}`, a.patient_code ?? "", a.detail, a.hash].map(String))];
      const csv = rows.map((r) => r.map((c) => `"${c.replace(/"/g, '""')}"`).join(",")).join("\n");
      return { filename: "jeevia-audit-log.csv", mime: "text/csv", blob: new Blob([csv], { type: "text/csv" }) };
    }),

  retentionStatus: () =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, ADMIN_ROLES);
      const now = Date.now();
      return {
        policy_hours: RETENTION_HOURS,
        active: d.files.filter((f) => !f.purged_at && Date.parse(f.expires_at) > now).length,
        pending_purge: d.files.filter((f) => !f.purged_at && Date.parse(f.expires_at) <= now).length,
        purged_last_7d: d.files.filter((f) => f.purged_at && now - Date.parse(f.purged_at) < 7 * 86400000).length,
        files: d.files.map(sanitizeFile).map((f) => ({ ...f, url: null })).sort((a, b) => a.expires_at.localeCompare(b.expires_at)),
      };
    }),

  // The regional calendar (F5) lives on the server with its sources; the browser-only demo does not copy it.
  speakOnline: async () => {
    throw new ApiError(501, "The online voice needs the live API");
  },
  visitDays: async () => {
    throw new ApiError(501, "The visit calendar needs the live API");
  },
  facilityCalendar: async () => {
    throw new ApiError(501, "The regional calendar needs the live API");
  },
  tryOnset: async () => {
    throw new ApiError(501, "The regional calendar needs the live API");
  },

  // No language model runs in the browser-only demo, so there are no second opinions to compare.
  overrideStats: (days = 28) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, ["supervisor", ...DOCTOR_ROLES]);
      const since = Date.now() - days * 86400000;
      const rows = d.encounters.filter((e) => e.facility_id === me.facility_id && Date.parse(e.created_at) >= since);
      const per = new Map<string, OverrideStats["rules"][number]>();
      let raised = 0;
      let lowered = 0;
      for (const e of rows) {
        const o = e.override;
        if (o && RANK[o.to_urgency] > RANK[o.from_urgency]) raised++;
        else if (o) lowered++;
        for (const h of e.note?.rules_fired ?? []) {
          const r = per.get(h.rule_id) ?? { rule_id: h.rule_id, urgency: h.urgency, description: h.description, fired: 0, lowered: 0, raised: 0, lowered_rate: 0 };
          r.fired++;
          if (o && RANK[o.to_urgency] < RANK[h.urgency]) r.lowered++;
          else if (o && RANK[o.to_urgency] > RANK[o.from_urgency]) r.raised++;
          r.lowered_rate = Math.round((1000 * r.lowered) / r.fired) / 1000;
          per.set(h.rule_id, r);
        }
      }
      await audit(d, me, "VIEW", "override_stats", null, `Override rates per rule viewed (${days} days)`);
      return { days, encounters: rows.length, overrides: raised + lowered, raised, lowered, rules: [...per.values()].sort((a, b) => b.lowered_rate - a.lowered_rate || b.fired - a.fired) };
    }),

  aiOpinions: async () => {
    throw new ApiError(501, "AI second opinions need the live API and the local model");
  },

  // The guard's pattern list lives on the server; the browser-only demo does not copy it.
  guardTestSamples: async () => {
    throw new ApiError(501, "The output guard test needs the live API");
  },
  guardTest: async () => {
    throw new ApiError(501, "The output guard test needs the live API");
  },

  deidentifiedCohort: (days = 28) =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, ["supervisor", ...DOCTOR_ROLES]);
      const since = Date.now() - days * 86400000;
      const rows = d.encounters.filter((e) => e.facility_id === me.facility_id && Date.parse(e.created_at) >= since);
      await audit(d, me, "VIEW", "cohort", null, `De-identified cohort viewed (${days} days, ${rows.length} cases)`);
      const K = 5;
      let suppressed = 0;
      const table = (vals: string[], keys: string[]) =>
        keys.map((key) => {
          const n = vals.filter((v) => v === key).length;
          const hide = n > 0 && n < K;
          if (hide) suppressed++;
          return { key, count: hide ? null : n };
        });
      const bands: [number, number, string][] = [[0, 4, "0–4"], [5, 13, "5–13"], [14, 17, "14–17"], [18, 39, "18–39"], [40, 59, "40–59"], [60, 200, "60+"]];
      const band = (a: number) => bands.find(([lo, hi]) => lo <= a && a <= hi)![2];
      const week = (iso: string) => {
        const t = new Date(iso);
        const d0 = new Date(Date.UTC(t.getUTCFullYear(), t.getUTCMonth(), t.getUTCDate()));
        d0.setUTCDate(d0.getUTCDate() + 4 - (d0.getUTCDay() || 7)); // ISO week: the Thursday decides the year
        const w = Math.ceil(((d0.getTime() - Date.UTC(d0.getUTCFullYear(), 0, 1)) / 86400000 + 1) / 7);
        return `${d0.getUTCFullYear()}-W${String(w).padStart(2, "0")}`;
      };
      const weeks = rows.map((e) => week(e.created_at));
      const urg = rows.map((e) => e.urgency ?? "green");
      const ages = rows.map((e) => band(e.patient.age));
      return {
        days,
        k_min: K,
        total: rows.length >= K || rows.length === 0 ? rows.length : null,
        by_week: table(weeks, [...new Set(weeks)].sort()),
        by_age_band: table(ages, bands.map((b) => b[2])),
        by_sex: table(rows.map((e) => (e.patient.sex === "F" || e.patient.sex === "M" ? e.patient.sex : "O")), ["F", "M", "O"]),
        by_category: table(rows.map((e) => e.category), ["normal", "maternal", "chronic"]),
        by_urgency: table(urg, ["red", "yellow", "green"]),
        urgency_by_age_band: (["red", "yellow", "green"] as const).map((u) => ({ urgency: u, cells: table(rows.filter((e) => (e.urgency ?? "green") === u).map((e) => band(e.patient.age)), bands.map((b) => b[2])) })),
        findings: [],
        suppressed_cells: suppressed,
        removed_fields: ["name", "patient ID", "phone", "village", "exact age", "exact date and time", "free text", "token"],
      };
    }),

  // Alerts in the local demo: the capacity check only; fever clusters and missed visits need the server.
  listAlerts: () =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, REVIEWER_ROLES);
      const cap = mockCapacity(d, me);
      return cap.alert ? [cap.alert] : [];
    }),

  acknowledgeAlert: () => Promise.reject(new ApiError(501, "Alerts need the Jeevia server (local demo mode)")),

  capacity: () =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, REVIEWER_ROLES);
      return mockCapacity(d, me);
    }),

  syndromicCsv: async (days = 14) => ({ filename: `syndromic_${days}d.csv`, mime: "text/csv", blob: new Blob(["date,place,visits,fever,respiratory,gastro,rash\n"], { type: "text/csv" }) }),

  listFollowups: async () => [],
  listHealthWorkers: () =>
    withDb(async (d) => {
      const me = await current(d);
      return d.users.filter((u) => u.facility_id === me.facility_id && u.role === "health_worker").map((u) => ({ id: u.id, name: u.name }));
    }),
  followupAttempt: () => Promise.reject(new ApiError(501, "Follow-ups need the Jeevia server (local demo mode)")),
  startCall: () => Promise.reject(new ApiError(501, "Reminder calls need the Jeevia server (local demo mode)")),
  telephonyStatus: async () => ({ calls: false, sms: false, demo_to: null, missing: ["the Jeevia server"] }),
  followupSms: () => Promise.reject(new ApiError(501, "SMS needs the Jeevia server (local demo mode)")),
  callAnswer: () => Promise.reject(new ApiError(501, "Reminder calls need the Jeevia server (local demo mode)")),
  endCall: () => Promise.reject(new ApiError(501, "Reminder calls need the Jeevia server (local demo mode)")),
  getCall: () => Promise.reject(new ApiError(501, "Reminder calls need the Jeevia server (local demo mode)")),
  listCalls: async () => [],
  callAudio: () => Promise.reject(new ApiError(501, "Reminder calls need the Jeevia server (local demo mode)")),

  departmentRates: async (days = 365) => ({ days, k_min: 5, departments: [], note: "Department rates need the Jeevia server (local demo mode)." }),

  listCohorts: () =>
    withDb(async (d) => {
      const me = await current(d);
      requireRole(me, ["employer"]);
      await audit(d, me, "VIEW", "cohort", null, "Employer viewed fitness cohorts (no clinical records)");
      return clone(d.cohorts);
    }),
};
