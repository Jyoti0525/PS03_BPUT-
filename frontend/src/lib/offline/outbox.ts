/**
 * Offline intake outbox. When the kiosk is offline (rural camps), completed intakes are queued in
 * IndexedDB and replayed when the connection returns. `client_ref` makes replays idempotent.
 */
import { get, keys, set } from "idb-keyval";
import type { IntakePayload, ConsentInput, Patient } from "@/lib/types";
import { api } from "@/lib/api";
import { scopeKey } from "@/lib/api/tokens";
import type { DeviceCheck } from "@/lib/triage/device";
import { dropFile, sendFile, sweepFiles, type QueuedFile } from "./blobs";

/** One outbox per session scope, so a kiosk link's queue is replayed with that kiosk's own session. */
function outboxKey(): string {
  const scope = scopeKey();
  return scope === "jeevia.tokens" ? "jeevia.outbox.v1" : `jeevia.outbox.v1.${scope.slice("jeevia.tokens.".length)}`;
}

export interface OutboxItem {
  client_ref: string;
  queued_at: string;
  /** Present when the patient was registered offline and must be created first. */
  new_patient?: Omit<Patient, "id" | "code" | "created_at"> | null;
  consent: Omit<ConsentInput, "patient_id">;
  intake: Omit<IntakePayload, "consent_id" | "patient_id"> & { patient_id: string | null };
  attempts: number;
  last_error?: string | null;
  /** The device's own run of the rules at capture, with the words that fired them; stays on this device. */
  device_check?: DeviceCheck | null;
  /** Photos and reports taken offline (lib/offline/blobs.ts): uploaded first, then sent as the intake's file_ids. */
  files?: QueuedFile[];
}

type Listener = (items: OutboxItem[]) => void;
const listeners = new Set<Listener>();

export async function readOutbox(): Promise<OutboxItem[]> {
  return ((await get(outboxKey())) as OutboxItem[] | undefined) ?? [];
}

async function write(items: OutboxItem[]) {
  await set(outboxKey(), items);
  listeners.forEach((l) => l(items));
}

export function subscribeOutbox(l: Listener) {
  listeners.add(l);
  readOutbox().then(l);
  return () => {
    listeners.delete(l);
  };
}

export async function enqueue(item: Omit<OutboxItem, "attempts" | "queued_at">) {
  const items = await readOutbox();
  items.push({ ...item, attempts: 0, queued_at: new Date().toISOString() });
  await write(items);
  if ("serviceWorker" in navigator) {
    // Not awaited: `ready` never settles when no service worker is registered (dev server, a failed registration),
    // which left the kiosk's Submit spinning after the intake was already saved.
    navigator.serviceWorker.ready
      .then((reg) => (reg as ServiceWorkerRegistration & { sync?: { register(tag: string): Promise<void> } }).sync?.register("jeevia-outbox"))
      .catch(() => undefined); // Background Sync unsupported — the online listener below flushes instead
  }
}

const SIM_KEY = "jeevia.simulate_offline";

/** Demo switch for rural-camp mode: behaves as offline even when the network is up. */
export function isSimulatedOffline(): boolean {
  try {
    return sessionStorage.getItem(SIM_KEY) === "1";
  } catch {
    return false;
  }
}

export function setSimulatedOffline(on: boolean) {
  try {
    if (on) sessionStorage.setItem(SIM_KEY, "1");
    else sessionStorage.removeItem(SIM_KEY);
  } catch {
    /* ignore */
  }
}

let flushing = false;

/** Replays queued intakes in order. Stops at the first network failure. */
export async function flushOutbox(): Promise<{ sent: number; remaining: number }> {
  if (flushing || isSimulatedOffline()) return { sent: 0, remaining: (await readOutbox()).length };
  flushing = true;
  let sent = 0;
  try {
    const items = await readOutbox();
    const rest: OutboxItem[] = [];
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      try {
        let patientId = it.intake.patient_id;
        if (!patientId && it.new_patient) patientId = (await api.createPatient(it.new_patient)).id;
        const consent = await api.captureConsent({ ...it.consent, patient_id: patientId! });
        if (!it.intake.patient_id) it.intake.patient_id = patientId; // a retry must not register the patient twice
        await sendFiles(it);
        const dc = it.device_check;
        await api.submitIntake({
          ...it.intake, patient_id: patientId!, consent_id: consent.id, captured_offline: true,
          file_ids: [...it.intake.file_ids, ...(it.files ?? []).flatMap((f) => (f.uploaded_id ? [f.uploaded_id] : []))],
          files_not_sent: (it.files ?? []).flatMap((f) => (f.failed ? [{ kind: f.kind, reason: f.failed }] : [])),
          device_check: dc ? { red: dc.red, rules: dc.rules.map(({ id, description }) => ({ id, description })), rulepack: dc.rulepack, at: dc.at } : null,
        });
        // The server has the files (redacted there): nothing unredacted stays on the tablet.
        await Promise.all((it.files ?? []).map((f) => dropFile(f.key)));
        sent++;
      } catch (e) {
        const err = e as { status?: number; message?: string };
        if (!err.status) {
          // Network still down: keep this and everything after it (with any files already uploaded marked as such).
          rest.push({ ...it, attempts: it.attempts + 1, last_error: "offline" }, ...items.slice(i + 1));
          break;
        }
        rest.push({ ...it, attempts: it.attempts + 1, last_error: err.message ?? "error" });
      }
    }
    await write(rest);
    await sweepFiles(await queuedFileKeys()).catch(() => undefined);
    return { sent, remaining: rest.length };
  } finally {
    flushing = false;
  }
}

/** Uploads an item's offline files, marking each as it goes. A network error throws (the item stays queued);
 *  a file the server refuses, or one no longer on the device, is reported with the intake instead of blocking it. */
async function sendFiles(it: OutboxItem) {
  const ai = it.consent.scopes.includes("ai_assist");
  for (const f of it.files ?? []) {
    if (f.uploaded_id || f.failed) continue;
    try {
      const id = await sendFile(f, ai);
      if (id) f.uploaded_id = id;
      else f.failed = "no longer on this device (browser storage was cleared)";
    } catch (e) {
      const err = e as { status?: number; message?: string };
      if (!err.status) throw e;
      f.failed = `refused by the server: ${(err.message ?? "error").slice(0, 150)}`;
    }
  }
}

/** Every file key referred to by any kiosk's outbox on this device. */
async function queuedFileKeys(): Promise<Set<string>> {
  const out = new Set<string>();
  for (const k of await keys()) {
    if (typeof k !== "string" || !k.startsWith("jeevia.outbox.v1")) continue;
    for (const it of ((await get(k)) as OutboxItem[] | undefined) ?? []) for (const f of it.files ?? []) out.add(f.key);
  }
  return out;
}

export function installOutboxAutoFlush() {
  const run = () => navigator.onLine && flushOutbox();
  window.addEventListener("online", run);
  navigator.serviceWorker?.addEventListener("message", (e) => {
    if (e.data?.type === "flush-outbox") run();
  });
  run();
  return () => window.removeEventListener("online", run);
}
