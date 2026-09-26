import type { JeeviaApi, ExportResult } from "./contract";
import { ApiError } from "./contract";
import { getDeviceId, getTokens, setTokens } from "./tokens";
import type { Tokens } from "@/lib/types";

export const API_ORIGIN = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");
const BASE = API_ORIGIN + "/api/v1";

async function refresh(): Promise<boolean> {
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

  requestOtp: (phone) => post("/auth/otp/request", { phone }),
  verifyOtp: (challenge_id, code) => post("/auth/otp/verify", { challenge_id, code }),
  register: (input) => post("/auth/register", input),
  loginWithPin: (phone, pin, device_id) => post("/auth/pin/login", { phone, pin, device_id }),
  setPin: (pin, device_id) => post("/auth/pin", { pin, device_id }),
  me: () => json("/auth/me"),
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
  facilityStats: (id) => json(`/facilities/${id}/stats`),

  facilityTokens: (id) => json(`/facilities/${id}/tokens`),

  listKioskLinks: () => json("/kiosk-links"),
  createKioskLink: (label) => post("/kiosk-links", { label }),
  revokeKioskLink: (id) => json(`/kiosk-links/${id}`, { method: "DELETE" }),
  kioskInfo: (code) => json(`/kiosk/${encodeURIComponent(code)}`),
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

  listUsers: () => json("/users"),

  searchPatients: (q) => json(`/patients?q=${encodeURIComponent(q)}`),
  getPatient: (id) => json(`/patients/${id}`),
  getPatientByCode: (code) => json(`/patients/by-code/${encodeURIComponent(code)}`),
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

  createReferral: (encounterId, input) => post(`/encounters/${encounterId}/referrals`, input),
  listReferrals: () => json("/referrals"),

  uploadFile: (file, kind, encounterId, sampleKey) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("kind", kind);
    if (encounterId) fd.append("encounter_id", encounterId);
    if (sampleKey) fd.append("sample_key", sampleKey);
    return json("/files", { method: "POST", body: fd });
  },
  getFile: (id) => json(`/files/${id}`),

  listAudit: (f) => {
    const qs = new URLSearchParams();
    if (f?.action) qs.set("action", f.action);
    if (f?.q) qs.set("q", f.q);
    return json(`/audit?${qs}`);
  },
  verifyAudit: () => json("/audit/verify"),
  exportAuditCsv: () => download("/audit/export", "audit-log.csv"),

  retentionStatus: () => json("/retention"),

  myRecord: () => json("/me/record"),

  listCohorts: () => json("/employer/cohorts"),
};

export const API_BASE = BASE;
