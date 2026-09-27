/**
 * Offline intake outbox. When the kiosk is offline (rural camps), completed intakes are queued in
 * IndexedDB and replayed when the connection returns. `client_ref` makes replays idempotent.
 */
import { get, set } from "idb-keyval";
import type { IntakePayload, ConsentInput, Patient } from "@/lib/types";
import { api } from "@/lib/api";
import { scopeKey } from "@/lib/api/tokens";

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
    try {
      const reg = await navigator.serviceWorker.ready;
      (reg as ServiceWorkerRegistration & { sync?: { register(tag: string): Promise<void> } }).sync?.register("jeevia-outbox");
    } catch {
      /* Background Sync unsupported — the online listener below flushes instead */
    }
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
        await api.submitIntake({ ...it.intake, patient_id: patientId!, consent_id: consent.id, captured_offline: true });
        sent++;
      } catch (e) {
        const err = e as { status?: number; message?: string };
        if (!err.status) {
          // Network still down: keep this and everything after it.
          rest.push({ ...it, attempts: it.attempts + 1, last_error: "offline" }, ...items.slice(i + 1));
          break;
        }
        rest.push({ ...it, attempts: it.attempts + 1, last_error: err.message ?? "error" });
      }
    }
    await write(rest);
    return { sent, remaining: rest.length };
  } finally {
    flushing = false;
  }
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
