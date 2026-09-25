import type { Tokens } from "@/lib/types";

const KEY = "jeevia.tokens";
const DEVICE_KEY = "jeevia.device_id";

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

let memoryTokens: Tokens | null = null;

export function getTokens(): Tokens | null {
  if (memoryTokens) return memoryTokens;
  const raw = safeGet(KEY);
  if (!raw) return null;
  try {
    memoryTokens = JSON.parse(raw) as Tokens;
    return memoryTokens;
  } catch {
    return null;
  }
}

export function setTokens(tokens: Tokens | null) {
  memoryTokens = tokens;
  safeSet(KEY, tokens ? JSON.stringify(tokens) : null);
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
