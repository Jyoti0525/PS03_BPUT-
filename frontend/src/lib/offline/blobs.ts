/**
 * Photos and reports taken while offline. Each file is kept in IndexedDB under its own key (not inside the outbox
 * list, which is rewritten on every change) and deleted as soon as the server has it: until then it sits on a shared
 * tablet unredacted, because faces and ID numbers are blurred on the server (routers/files.py).
 */
import { del, get, keys, set } from "idb-keyval";
import { api } from "@/lib/api";
import type { FileObject } from "@/lib/types";

const PREFIX = "jeevia.blob.";
/** A file nobody queued (the intake was abandoned) is removed after this long. */
const ORPHAN_MS = 6 * 60 * 60 * 1000;

export interface QueuedFile {
  key: string;
  kind: "report" | "image";
  filename: string;
  content_type: string;
  size: number;
  sample_key?: string | null;
  /** Set once uploaded, so a retry after a dropped connection does not upload it twice. */
  uploaded_id?: string | null;
  /** The server refused it (type, size): the intake is sent without it and staff see why. */
  failed?: string | null;
}

/** Keeps a file on this device; returns its record, and a FileObject the intake screen can preview. */
export async function keepFile(file: File, kind: QueuedFile["kind"], sampleKey?: string | null): Promise<{ queued: QueuedFile; preview: FileObject }> {
  const key = `${PREFIX}${Date.now()}.${Math.random().toString(36).slice(2, 10)}`;
  await set(key, file);
  askToKeepStorage();
  const queued: QueuedFile = { key, kind, filename: file.name, content_type: file.type || "application/octet-stream", size: file.size, sample_key: sampleKey ?? null };
  const now = new Date().toISOString();
  return {
    queued,
    preview: {
      id: key, filename: file.name, content_type: queued.content_type, size: file.size, kind, encounter_id: null,
      uploaded_at: now, expires_at: now, purged_at: null, url: URL.createObjectURL(file), read_quality: null,
    },
  };
}

export const isLocalFile = (id: string) => id.startsWith(PREFIX);

export async function dropFile(key: string) {
  await del(key).catch(() => undefined);
}

/** Uploads one kept file. Returns the server's id, or null when the file is no longer on the device. Network errors throw. */
export async function sendFile(q: QueuedFile, aiAssist: boolean): Promise<string | null> {
  if (q.uploaded_id) return q.uploaded_id;
  const blob = (await get(q.key)) as Blob | undefined;
  if (!blob) return null;
  const up = await api.uploadFile(new File([blob], q.filename, { type: q.content_type }), q.kind, null, q.sample_key ?? null, aiAssist, aiAssist && !q.sample_key);
  return up.id;
}

/** Removes kept files that no queued intake refers to and that are older than ORPHAN_MS (an abandoned intake). */
export async function sweepFiles(referenced: Set<string>) {
  const now = Date.now();
  for (const k of await keys()) {
    if (typeof k !== "string" || !k.startsWith(PREFIX) || referenced.has(k)) continue;
    const at = Number(k.slice(PREFIX.length).split(".")[0]);
    if (!at || now - at > ORPHAN_MS) await dropFile(k);
  }
}

let asked = false;
/** Asks the browser not to clear our storage when the device runs low on space (granted silently for installed apps). */
export function askToKeepStorage() {
  if (asked) return;
  asked = true;
  navigator.storage?.persist?.().catch(() => undefined);
}
