/**
 * Phrase translation for every screen. Components call `tr("English text")` (from `usePrefs()`); the English
 * text is the key, so untranslated phrases simply stay in English. Hindi and Odia tables load on demand;
 * Kannada covers the patient screens only.
 * Placeholders: tr("Resend in {s}s", { s: 30 }).
 */
export type Phrases = Record<string, string>;

export const PHRASE_LANGS = ["hi", "or", "kn"] as const;

const cache = new Map<string, Phrases>();

export async function loadPhrases(lang: string): Promise<Phrases> {
  if (!PHRASE_LANGS.includes(lang as (typeof PHRASE_LANGS)[number])) return {};
  const hit = cache.get(lang);
  if (hit) return hit;
  const mod = lang === "hi" ? await import("./hi") : lang === "kn" ? await import("./kn") : await import("./or");
  cache.set(lang, mod.default);
  return mod.default;
}

export function fill(s: string, vars?: Record<string, string | number>) {
  return vars ? s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m)) : s;
}

type Pattern = { re: RegExp; names: string[]; to: string; multi: boolean };

function compile(phrases: Phrases): Pattern[] {
  return Object.keys(phrases)
    // Only templates with a real word in them (or the comma list) are safe to match against free text.
    .filter((k) => /\{\w+\}/.test(k) && (/[A-Za-z]{2,}/.test(k.replace(/\{\w+\}/g, "")) || k === "{a}, {b}" || k === '"{f}": {w}'))
    .sort((a, b) => b.replace(/\{\w+\}/g, "").length - a.replace(/\{\w+\}/g, "").length) // most specific first
    .map((k) => {
      const names: string[] = [];
      const src = k.split(/(\{\w+\})/).map((part) => {
        const m = /^\{(\w+)\}$/.exec(part);
        if (m) {
          names.push(m[1]);
          return "(.+?)";
        }
        return part.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      });
      return { re: new RegExp(`^${src.join("")}$`, "s"), names, to: phrases[k], multi: /[.?!] \S/.test(k) };
    });
}

/**
 * Builds `tr`. Exact phrases first; then templates, so server text built from fixed patterns
 * ("ATP rule {id} matched on intake data", "{m} min ago") translates too, with the captured parts
 * translated in turn; then sentence by sentence for templated paragraphs. Anything unknown stays as is.
 */
export function makeTr(phrases: Phrases) {
  const patterns = compile(phrases);
  const sep = /^\{a\}(.*)\{b\}$/.exec(phrases["{a}, {b}"] ?? "")?.[1];
  const translate = (s: string, depth: number): string => {
    const hit = phrases[s];
    if (hit !== undefined) return hit;
    if (depth > 0 && sep !== undefined && s.includes(", ")) {
      // A captured list ("…until measured: systolic BP, pulse, SpO₂, AVPU…") can be any length: item by item.
      const parts = s.split(", ");
      const out = parts.map((x) => translate(x, depth));
      if (out.some((x, i) => x !== parts[i])) return out.join(sep);
    }
    if (depth > 2 || !patterns.length || !/[A-Za-z]/.test(s)) return s;
    if (depth === 0 && /[.?!] \S/.test(s)) {
      for (const p of patterns) {
        if (!p.multi) continue;
        const m = p.re.exec(s);
        if (m) return p.to.replace(/\{(\w+)\}/g, (x, k) => {
          const i = p.names.indexOf(k);
          return i < 0 ? x : translate(m[i + 1].trim(), depth + 1);
        });
      }
      // A paragraph: translate sentence by sentence.
      const parts = s.split(/(?<=[.?!]) (?=\S)/);
      const out = parts.map((x) => translate(x, 1));
      return out.some((x, i) => x !== parts[i]) ? out.join(" ") : s;
    }
    for (const p of patterns) {
      const m = p.re.exec(s);
      if (m) return p.to.replace(/\{(\w+)\}/g, (x, k) => {
        const i = p.names.indexOf(k);
        return i < 0 ? x : translate(m[i + 1].trim(), depth + 1);
      });
    }
    return s;
  };
  const tr = (s: string | null | undefined, vars?: Record<string, string | number>) => (s == null ? "" : fill(vars ? phrases[s] ?? s : translate(s, 0), vars));
  currentTr = tr;
  return tr;
}

/* Non-component helpers (time formatting, dates) use the translator of the current language. */
let currentTr: (s: string | null | undefined, vars?: Record<string, string | number>) => string = (s, vars) => (s == null ? "" : fill(s, vars));
let currentLang = "en";

export const gtr = (s: string | null | undefined, vars?: Record<string, string | number>) => currentTr(s, vars);

export function setCurrentLang(lang: string) {
  currentLang = lang;
}

/** BCP-47 locale for dates in the current language. */
export function dateLocale() {
  return currentLang === "hi" ? "hi-IN" : currentLang === "or" ? "or-IN" : currentLang === "kn" ? "kn-IN" : "en-IN";
}

type Tr = (s: string | null | undefined, vars?: Record<string, string | number>) => string;

/** Server messages are English; translate the known ones, including "… — try again in about N minutes". */
export function localiseServerMessage(msg: string, tr: Tr): string {
  const m = /^(.*) — try again in about (\d+) (minute|minutes|hour|hours)$/.exec(msg);
  if (!m) return tr(msg);
  const n = Number(m[2]);
  const when = m[3].startsWith("hour") ? tr(n === 1 ? "try again in about 1 hour" : "try again in about {n} hours", { n }) : tr(n === 1 ? "try again in about 1 minute" : "try again in about {n} minutes", { n });
  return `${tr(m[1])} — ${when}`;
}
