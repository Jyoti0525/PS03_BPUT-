"use client";

import { dateLocale, gtr } from "@/lib/i18n/phrases";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";

/** Minimal data hook: runs `fn` on mount / when deps change, exposes reload. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = [], opts: { pollMs?: number; enabled?: boolean } = {}) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  useEffect(() => {
    fnRef.current = fn;
  });
  const enabled = opts.enabled ?? true;

  const reload = useCallback(async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const d = await fnRef.current();
      setData(d);
      setError(null);
    } catch (e) {
      setError(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!enabled) return;
    // Fetch-on-mount: state is set after the awaited request, not synchronously.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    reload();
    if (!opts.pollMs) return;
    const t = setInterval(() => reload(true), opts.pollMs);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, reload, opts.pollMs, ...deps]);

  return { data, error, loading, reload, setData };
}

export function useNow(intervalMs = 30_000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
  return now;
}

function subscribeOnline(cb: () => void) {
  window.addEventListener("online", cb);
  window.addEventListener("offline", cb);
  return () => {
    window.removeEventListener("online", cb);
    window.removeEventListener("offline", cb);
  };
}

export function useOnline() {
  return useSyncExternalStore(subscribeOnline, () => navigator.onLine, () => true);
}

export function timeAgo(iso: string, now = Date.now()) {
  const m = Math.round((now - Date.parse(iso)) / 60000);
  if (m < 1) return gtr("just now");
  if (m < 60) return gtr("{m} min ago", { m });
  const h = Math.floor(m / 60);
  if (h < 24) return gtr("{h}h {m}m ago", { h, m: m % 60 });
  const d = Math.floor(h / 24);
  return d > 1 ? gtr("{d} days ago", { d }) : gtr("1 day ago");
}

export function fmtWait(min: number) {
  if (min < 60) return gtr("{m}m", { m: min });
  return gtr("{h}h {m}m", { h: Math.floor(min / 60), m: min % 60 });
}

/** Date / date-time in the current interface language. */
/* Some browsers ship no Odia calendar data; Intl then silently falls back to English names. */
const OR_MONTHS = ["ଜାନୁଆରୀ", "ଫେବୃଆରୀ", "ମାର୍ଚ୍ଚ", "ଅପ୍ରେଲ", "ମଇ", "ଜୁନ", "ଜୁଲାଇ", "ଅଗଷ୍ଟ", "ସେପ୍ଟେମ୍ବର", "ଅକ୍ଟୋବର", "ନଭେମ୍ବର", "ଡିସେମ୍ବର"];
const OR_DAYS = ["ରବିବାର", "ସୋମବାର", "ମଙ୍ଗଳବାର", "ବୁଧବାର", "ଗୁରୁବାର", "ଶୁକ୍ରବାର", "ଶନିବାର"];
let intlHasOdia: boolean | null = null;

function odiaFallback(): boolean {
  if (dateLocale() !== "or-IN") return false;
  if (intlHasOdia === null) intlHasOdia = new Intl.DateTimeFormat("or-IN", { month: "long" }).format(new Date(2026, 0, 5)) !== "January";
  return !intlHasOdia;
}

function odiaDate(x: Date, opts?: Intl.DateTimeFormatOptions) {
  if (opts?.month === "long") return `${opts.weekday ? `${OR_DAYS[x.getDay()]}, ` : ""}${x.getDate()} ${OR_MONTHS[x.getMonth()]}${opts.year ? ` ${x.getFullYear()}` : ""}`;
  return `${String(x.getDate()).padStart(2, "0")}/${String(x.getMonth() + 1).padStart(2, "0")}/${x.getFullYear()}`;
}

export function fmtDate(d: string | number | Date, opts?: Intl.DateTimeFormatOptions) {
  const x = new Date(d);
  return odiaFallback() ? odiaDate(x, opts) : x.toLocaleDateString(dateLocale(), opts);
}

export function fmtDateTime(d: string | number | Date, opts?: Intl.DateTimeFormatOptions) {
  const x = new Date(d);
  if (!odiaFallback()) return x.toLocaleString(dateLocale(), opts);
  return `${odiaDate(x)}, ${String(x.getHours()).padStart(2, "0")}:${String(x.getMinutes()).padStart(2, "0")}`;
}
