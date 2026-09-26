"use client";

import { useSyncExternalStore } from "react";
import { API_MODE } from "@/lib/api";
import { API_ORIGIN } from "@/lib/api/live";
import { getTokens } from "@/lib/api/tokens";

export interface Health {
  status: "ok" | "degraded";
  version: string;
  uptime_s: number;
  db: { engine: string; ok: boolean; latency_ms: number };
  storage: { backend: string; ok: boolean; persistent: boolean };
  otp: { provider: string; configured: boolean };
}

export type ServerState = "demo" | "checking" | "online" | "degraded" | "offline" | "waking";

export interface StatusSnapshot {
  state: ServerState;
  health: Health | null;
  latencyMs: number | null;
  checkedAt: number | null;
  wakeProgress: number;
}

const POLL_MS = 20_000;
const WAKE_TIMEOUT_MS = 120_000;

let snap: StatusSnapshot = { state: API_MODE === "mock" ? "demo" : "checking", health: null, latencyMs: null, checkedAt: null, wakeProgress: 0 };
const listeners = new Set<() => void>();
let timer: ReturnType<typeof setInterval> | null = null;
let waking = false;

function set(p: Partial<StatusSnapshot>) {
  snap = { ...snap, ...p };
  listeners.forEach((l) => l());
}

async function probe(timeoutMs: number) {
  const t0 = performance.now();
  const ctl = new AbortController();
  const id = setTimeout(() => ctl.abort(), timeoutMs);
  try {
    const r = await fetch(`${API_ORIGIN}/health`, { cache: "no-store", signal: ctl.signal });
    return { health: (await r.json()) as Health, ms: Math.round(performance.now() - t0), ok: r.ok };
  } catch {
    return { health: null, ms: 0, ok: false };
  } finally {
    clearTimeout(id);
  }
}

function apply(res: Awaited<ReturnType<typeof probe>>) {
  set({
    checkedAt: Date.now(),
    latencyMs: res.health ? res.ms : null,
    health: res.health,
    state: res.health ? (res.ok && res.health.status === "ok" ? "online" : "degraded") : waking ? "waking" : "offline",
  });
}

/** Re-check now. */
export async function checkStatus() {
  if (API_MODE === "mock" || waking) return;
  apply(await probe(8000));
}

/** Render's free tier sleeps after 15 idle minutes; any request wakes it. Keep pinging until it answers. */
export function wakeServer() {
  if (API_MODE === "mock" || waking) return;
  waking = true;
  set({ state: "waking", wakeProgress: 0.02 });
  const start = Date.now();
  const loop = async () => {
    const res = await probe(15000);
    const elapsed = Date.now() - start;
    if (res.health || elapsed > WAKE_TIMEOUT_MS) {
      waking = false;
      set({ wakeProgress: res.health ? 1 : 0 });
      apply(res);
      return;
    }
    set({ wakeProgress: Math.min(0.95, elapsed / 60000) });
    setTimeout(loop, 3000);
  };
  loop();
}

function subscribe(l: () => void) {
  listeners.add(l);
  if (listeners.size === 1 && API_MODE !== "mock") {
    checkStatus();
    timer = setInterval(() => document.visibilityState === "visible" && checkStatus(), POLL_MS);
  }
  return () => {
    listeners.delete(l);
    if (!listeners.size && timer) {
      clearInterval(timer);
      timer = null;
    }
  };
}

const serverSnap: StatusSnapshot = { state: API_MODE === "mock" ? "demo" : "checking", health: null, latencyMs: null, checkedAt: null, wakeProgress: 0 };

/** Live status of the API server and its dependencies, shared by every component on the page. */
export function useSystemStatus(): StatusSnapshot {
  return useSyncExternalStore(subscribe, () => snap, () => serverSnap);
}

/** Supervisor-only restart through the web app's server route (holds the Render API key). */
export async function restartServer(): Promise<{ ok: boolean; message: string }> {
  const t = getTokens();
  const r = await fetch("/api/ops/restart", { method: "POST", headers: { Authorization: `Bearer ${t?.access_token ?? ""}` } });
  const body = (await r.json().catch(() => ({}))) as { message?: string };
  return { ok: r.ok, message: body.message ?? (r.ok ? "Restart requested" : "Restart failed") };
}

export async function restartAvailable(): Promise<boolean> {
  try {
    const r = await fetch("/api/ops/restart", { cache: "no-store" });
    return ((await r.json()) as { configured?: boolean }).configured === true;
  } catch {
    return false;
  }
}
