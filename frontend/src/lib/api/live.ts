import type { JeeviaApi, ExportResult } from "./contract";
import { ApiError } from "./contract";
import { getDeviceId, getTokens, setTokens } from "./tokens";
import type { Tokens } from "@/lib/types";

export const API_ORIGIN = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const BASE = API_ORIGIN + "/api/v1";

// Several screens poll at once, so an expired access token can trigger parallel refreshes. Refresh tokens work once,
// so they share a single request: a second one would be refused and sign the user out.
let refreshing: Promise<boolean> | null = null;

function refresh(): Promise<boolean> {
  refreshing ??= doRefresh().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

async function doRefresh(): Promise<boolean> {
  const t = getTokens();
  if (!t?.refresh_token) return false;
  const res = await fetch(`${BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: t.refresh_token }),
  });
  if (!res.ok) {
    setTokens(null);
    return false;
  }
  setTokens((await res.json()) as Tokens);
  return true;
}

async function raw(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  const t = getTokens();
  if (t) headers.set("Authorization", `Bearer ${t.access_token}`);
  headers.set("X-Device-Id", getDeviceId());
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(0, "Network unavailable");
  }
  if (res.status === 401 && retry && (await refresh())) return raw(path, init, false);
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* non-JSON error */
    }
    throw new ApiError(res.status, msg);
  }
  return res;
}

async function json<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await raw(path, init);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const post = <T>(path: string, body?: unknown) =>
  json<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const patch = <T>(path: string, body: unknown) => json<T>(path, { method: "PATCH", body: JSON.stringify(body) });

async function download(path: string, fallbackName: string): Promise<ExportResult> {
  const res = await raw(path);
  const cd = res.headers.get("Content-Disposition") || "";
  const name = /filename="?([^"]+)"?/.exec(cd)?.[1] ?? fallbackName;
  const blob = await res.blob();
  return { filename: name, mime: blob.type, blob };
}

export const liveApi: JeeviaApi = {
  mode: "live",

  requestOtp: (target, purpose = "signin") => post("/auth/otp/request", { ...(typeof target === "string" ? { phone: target } : target), purpose }),
  authOptions: () => json("/auth/options"),
  emailStart: (email, language) => post("/auth/email/start", { email, language }),
  emailConfirm: (challenge_id, code) => post("/auth/email/confirm", { challenge_id, code }),
  emailRemove: () => json("/auth/email", { method: "DELETE" }),
  verifyOtp: (challenge_id, code, purpose = "signin") => post("/auth/otp/verify", { challenge_id, code, purpose }),
  register: (input) => post("/auth/register", input),
  verifyPin: (pin_token, pin) => post("/auth/pin/verify", { pin_token, pin }),
  setupPin: (pin_token, pin) => post("/auth/pin/setup", { pin_token, pin }),
  forgotPin: (pin_token) => post("/auth/pin/forgot", { pin_token }),
  changePin: (current_pin, new_pin) => post("/auth/pin/change", { current_pin, new_pin }),
  resetStaffPin: (id) => post(`/users/${id}/reset-pin`),
  me: () => json("/auth/me"),
  updateMe: (p) => patch("/auth/me", p),
  logout: async () => {
    try {
      await post("/auth/logout");
    } finally {
      setTokens(null);
    }
  },

  listDevices: () => json("/devices"),
  bindDevice: (label, device_id) => post("/devices", { label, device_id }),
  revokeDevice: (id) => json(`/devices/${id}`, { method: "DELETE" }),

  listFacilities: () => json("/facilities"),
  getFacility: (id) => json(`/facilities/${id}`),
  updateFacility: (id, p) => patch(`/facilities/${id}`, p),
  facilityCalendar: (id) => json(`/facilities/${id}/calendar`),
  visitDays: (id, kind, after) => json(`/facilities/${id}/visit-days?kind=${kind}${after ? `&after=${after}` : ""}`),
  tryOnset: (id, text) => json(`/facilities/${id}/onset?text=${encodeURIComponent(text)}`),
  facilityStats: (id) => json(`/facilities/${id}/stats`),

  facilityTokens: (id) => json(`/facilities/${id}/tokens`),

  listKioskLinks: () => json("/kiosk-links"),
  createKioskLink: (label, forHome = false) => post("/kiosk-links", { label, for_home: forHome }),
  checkIn: (id) => post(`/encounters/${id}/arrive`, {}),
  claimForm: (reference) => post("/encounters/claim", { reference }),
  revokeKioskLink: (id) => json(`/kiosk-links/${id}`, { method: "DELETE" }),
  kioskInfo: (code) => json(`/kiosk/${encodeURIComponent(code)}`),
  kioskFinder: (q, lat, lon) => {
    const p = new URLSearchParams({ q });
    if (lat != null && lon != null) p.set("lat", String(lat)), p.set("lon", String(lon));
    return json(`/kiosk-finder?${p}`);
  },
  kioskSession: async (code, device_id) => {
    const r = await post<{ tokens: Tokens; user: import("@/lib/types").User }>(`/kiosk/${encodeURIComponent(code)}/session`, { device_id });
    setTokens(r.tokens);
    return r;
  },
  kioskIdentify: (patient_code, phone) => post("/kiosk/identify", { patient_code, phone }),

  createShare: (id, hours, purpose = "referral") => post(`/encounters/${id}/shares`, { hours, purpose }),
  listShares: (id) => json(`/encounters/${id}/shares`),
  revokeShare: (id) => json(`/shares/${id}`, { method: "DELETE" }),
  shareMeta: (token) => json(`/share/${encodeURIComponent(token)}`),
  openShare: (token, access_code) => post(`/share/${encodeURIComponent(token)}/open`, { access_code }),
  shareReceived: (token, access_code, confirmed_by, note) => post(`/share/${encodeURIComponent(token)}/received`, { access_code, confirmed_by, note }),

  searchDirectory: (q, state) => json(`/directory/search?q=${encodeURIComponent(q)}${state ? `&state=${encodeURIComponent(state)}` : ""}`),
  directoryStates: () => json("/directory/states"),

  myOrganisation: () => json("/organisations/me"),
  updateOrganisation: (p) => patch("/organisations/me", p),
  addOrganisationFacility: (input) => post("/organisations/me/facilities", input),
  listWorkers: () => json("/organisations/me/workers"),
  addWorker: (input) => post("/organisations/me/workers", input),
  importWorkers: (csv) => post("/organisations/me/workers/import", { csv }),
  removeWorker: async (code) => {
    await patch(`/organisations/me/workers/${encodeURIComponent(code)}`, { active: false });
  },

  recordFitness: (id, input) => post(`/encounters/${id}/fitness`, input),

  updateUser: (id, p) => patch(`/users/${id}`, p),
  correctPatient: (id, p) => patch(`/patients/${id}`, p),

  listUsers: () => json("/users"),
  setDuty: (id, on_duty) => patch(`/users/${id}/duty`, { on_duty }),
  reviewMedications: (eid, confirm, reject) => post(`/encounters/${eid}/medications`, { confirm, reject }),
  addObservations: (eid, input) => post(`/encounters/${eid}/observations`, input),

  searchPatients: (q) => json(`/patients?q=${encodeURIComponent(q)}`),
  getPatient: (id) => json(`/patients/${id}`),
  getPatientByCode: (code) => json(`/patients/by-code/${encodeURIComponent(code)}`),
  pickPatient: (id, match_reason, candidates) => post(`/patients/${id}/pick`, { match_reason, candidates }),
  createPatient: (input) => post("/patients", input),
  patientEncounters: (id) => json(`/patients/${id}/encounters`),

  captureConsent: (input) => post("/consents", input),

  submitIntake: (payload) => post("/encounters", payload),
  queue: (facilityId) => json(`/queue?facility_id=${encodeURIComponent(facilityId)}`),
  getEncounter: (id) => json(`/encounters/${id}`),
  confirmEncounter: (id) => post(`/encounters/${id}/confirm`),
  editNote: (id, note) => patch(`/encounters/${id}/note`, note),
  overrideUrgency: (id, to_urgency, category, reason) =>
    post(`/encounters/${id}/override`, { to_urgency, category, reason }),
  setReferralNeeded: (id, needed) => patch(`/encounters/${id}`, { referral_needed: needed }),
  exportEncounter: (id, format) => download(`/encounters/${id}/export?format=${format}`, `triage-note.${format}`),

  escalate: (encounterId, to_role, reason) => post(`/encounters/${encounterId}/escalations`, { to_role, reason }),
  listEscalations: (status) => json(`/escalations${status ? `?status=${status}` : ""}`),
  acknowledgeEscalation: (id, note) => post(`/escalations/${id}/acknowledge`, { note }),
  listAlerts: (status) => json(`/alerts${status ? `?status=${status}` : ""}`),
  acknowledgeAlert: (id, note) => post(`/alerts/${id}/acknowledge`, { note }),
  capacity: () => json("/capacity"),
  syndromicCsv: (days = 14) => download(`/surveillance/syndromic.csv?days=${days}`, `syndromic_${days}d.csv`),
  listFollowups: (scope = "active", programme = "all") => json(`/followups?scope=${scope}&programme=${programme}`),
  listHealthWorkers: () => json("/health-workers"),
  followupAttempt: (id, outcome, note = "") => post(`/followups/${id}/attempt`, { outcome, note }),
  startCall: (id, opts = {}) => post(`/followups/${id}/calls`, opts),
  telephonyStatus: () => json("/telephony/status"),
  followupSms: (id) => post(`/followups/${id}/sms`),
  callAnswer: (cid, text, originalText) => post(`/calls/${cid}/answer`, { text, original_text: originalText ?? null }),
  endCall: (cid, outcome) => post(`/calls/${cid}/end`, { outcome }),
  getCall: (cid) => json(`/calls/${cid}`),
  callAudio: async (cid, i) => (await raw(`/calls/${cid}/turns/${i}/audio`)).blob(),
  translateText: (text, source, target) => post("/translate", { text, source, target }),
  speakOnline: async (text, language, allowOnline = true) =>
    (await raw("/language/speak", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text, language, allow_online: allowOnline }) })).blob(),
  listCalls: (id) => json(`/followups/${id}/calls`),

  createReferral: (encounterId, input) => post(`/encounters/${encounterId}/referrals`, input),
  listReferrals: () => json("/referrals"),
  referralReceived: (id, confirmed_by, note) => post(`/referrals/${id}/received`, { confirmed_by, note }),

  uploadFile: (file, kind, encounterId, sampleKey, read = true, online = false) => {
    const fd = new FormData();
    if (!read) fd.append("read", "false");
    if (online) fd.append("online", "true");
    fd.append("file", file);
    fd.append("kind", kind);
    if (encounterId) fd.append("encounter_id", encounterId);
    if (sampleKey) fd.append("sample_key", sampleKey);
    return json("/files", { method: "POST", body: fd });
  },
  getFile: (id) => json(`/files/${id}`),

  transcribe: (audio, language, opts) => {
    const fd = new FormData();
    fd.append("audio", new File([audio], "speech.webm", { type: audio.type || "audio/webm" }));
    fd.append("language", language);
    if (opts?.secondOpinion) fd.append("second_opinion", "true");
    return json("/speech/transcribe", { method: "POST", body: fd });
  },
  secondCheck: (id) => json(`/speech/second/${encodeURIComponent(id)}`),

  listAudit: (f) => {
    const qs = new URLSearchParams();
    if (f?.action) qs.set("action", f.action);
    if (f?.q) qs.set("q", f.q);
    return json(`/audit?${qs}`);
  },
  verifyAudit: () => json("/audit/verify"),
  exportAuditCsv: () => download("/audit/export", "audit-log.csv"),

  retentionStatus: () => json("/retention"),
  deidentifiedCohort: (days = 28) => json(`/cohort?days=${days}`),
  aiOpinions: (days = 28) => json(`/ai-opinions?days=${days}`),
  overrideStats: (days = 28) => json(`/override-stats?days=${days}`),
  guardTestSamples: () => json("/guard-test/samples"),
  guardTest: (text, source = "") => post("/guard-test", { text, source }),


  listCohorts: () => json("/employer/cohorts"),
  departmentRates: (days = 365) => json(`/employer/department-rates?days=${days}`),
};

export const API_BASE = BASE;
