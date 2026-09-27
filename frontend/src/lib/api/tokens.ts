import type { Tokens, User } from "@/lib/types";

const DEVICE_KEY = "jeevia.device_id";

/**
 * Sessions are scoped: a public kiosk tab (/k/CODE) keeps its own kiosk token, so opening a kiosk
 * link never signs a doctor out of another tab — and a doctor's session never leaks into a kiosk.
 */
export function scopeKey(): string {
  if (typeof window === "undefined") return "jeevia.tokens";
  const m = /^\/k\/([^/]+)/.exec(window.location.pathname);
  return m ? `jeevia.tokens.kiosk.${m[1].toUpperCase()}` : "jeevia.tokens";
}

function safeGet(key: string): string | null {
  try {
    return typeof window === "undefined" ? null : window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string | null) {
  try {
    if (value === null) window.localStorage.removeItem(key);
    else window.localStorage.setItem(key, value);
  } catch {
    /* storage blocked — session stays in memory only */
  }
}

const memory = new Map<string, Tokens | null>();

export function getTokens(): Tokens | null {
  const key = scopeKey();
  if (memory.has(key)) return memory.get(key) ?? null;
  const raw = safeGet(key);
  if (!raw) return null;
  try {
    const t = JSON.parse(raw) as Tokens;
    memory.set(key, t);
    return t;
  } catch {
    return null;
  }
}

export function setTokens(tokens: Tokens | null) {
  const key = scopeKey();
  memory.set(key, tokens);
  safeSet(key, tokens ? JSON.stringify(tokens) : null);
  if (!tokens) safeSet(`${key}.user`, null);
}

/** Last known signed-in user for this scope — lets kiosks (and dashboards) open while offline. */
export function getCachedUser(): User | null {
  const raw = safeGet(`${scopeKey()}.user`);
  try {
    return raw ? (JSON.parse(raw) as User) : null;
  } catch {
    return null;
  }
}

export function setCachedUser(user: User | null) {
  safeSet(`${scopeKey()}.user`, user ? JSON.stringify(user) : null);
}

/** Stable per-browser id used for device binding and PIN login. */
export function getDeviceId(): string {
  let id = safeGet(DEVICE_KEY);
  if (!id) {
    id = "dev_" + crypto.randomUUID().replace(/-/g, "").slice(0, 16);
    safeSet(DEVICE_KEY, id);
  }
  return id;
}
