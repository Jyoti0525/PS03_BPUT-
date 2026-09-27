/**
 * Phrase translation for every screen. Components call `tr("English text")` (from `usePrefs()`); the English
 * text is the key, so untranslated phrases simply stay in English. Hindi and Odia tables load on demand.
 * Placeholders: tr("Resend in {s}s", { s: 30 }).
 */
export type Phrases = Record<string, string>;

export const PHRASE_LANGS = ["hi", "or"] as const;

const cache = new Map<string, Phrases>();

export async function loadPhrases(lang: string): Promise<Phrases> {
  if (!PHRASE_LANGS.includes(lang as (typeof PHRASE_LANGS)[number])) return {};
  const hit = cache.get(lang);
  if (hit) return hit;
  const mod = lang === "hi" ? await import("./hi") : await import("./or");
  cache.set(lang, mod.default);
  return mod.default;
}

export function fill(s: string, vars?: Record<string, string | number>) {
  return vars ? s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m)) : s;
}

export function makeTr(phrases: Phrases) {
  return (s: string | null | undefined, vars?: Record<string, string | number>) => (s == null ? "" : fill(phrases[s] ?? s, vars));
}
