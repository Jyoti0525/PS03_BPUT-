/**
 * The server's triage rules, run on the device (offline kiosk). A port of backend/app/triage/rules.py and findings.py
 * that reads the same rule pack (rulepack.json, generated from the backend's YAML and word lists), so an offline
 * intake with a danger sign is caught at once instead of after the network returns.
 *
 * Same three-valued logic: a rule is true, false or unknown, and unknown is never read as normal. The server stays
 * the record: it triages every intake again when it arrives. backend/tests/test_device_rules.py runs this file and
 * rules.py on the same patients and fails if any colour or rule differs.
 *
 * Pure: no imports, the pack is passed in, so the parity test can run it in Node.
 * Not ported (they never change a colour on the device): follow-up flags, the translation check's evidence wording,
 * festival-based onset (stays unknown, as on the server).
 */

export type Urgency = "green" | "yellow" | "red";
type Tri = boolean | null;
type Cond = Record<string, unknown>;

export interface RulePack {
  version: string;
  sources: Record<string, string>;
  protocols: { key: string; name: string; applies: Record<string, unknown>; rules: { id: string; description: string; urgency: Urgency; when: Cond; source: string; non_downgradable: boolean; review_by: string }[] }[];
  findings: Record<string, [string, "symptom" | "sign"]>;
  lexicon: Record<string, [string, string][]>;
  tiles: Record<string, string[]>;
  answers: [string, string, Record<string, boolean>][];
  staff_answers: Record<string, Record<string, Record<string, boolean>>>;
  implies: [string, string][];
  negation: { pre: string; post_en: string; post_indic: string[]; clause_split: string };
  loose: { drop: string[]; map: Record<string, string> };
  vitals: string[];
  vital_label: Record<string, string>;
  unit: Record<string, string>;
  exposure_label: Record<string, string>;
  required_adult: string[];
  required_child: string[];
  duration_hours: [string, [number, number]][];
  duration_number: string;
  onset: { explicit: string; relative: [string, number][]; num: Record<string, number>; unit_days: Record<string, number>; not_before: string; not_after: string; digits: Record<string, string> };
}

export interface RuleHit {
  rule_id: string;
  protocol: string;
  description: string;
  urgency: Urgency;
  source: string;
  source_key: string;
  non_downgradable: boolean;
  review_by: string;
  evidence: string[];
}

export interface DeviceTriage {
  urgency: Urgency;
  provisional: boolean;
  hits: RuleHit[];
  unresolved: (Omit<RuleHit, "evidence"> & { needs: string[] })[];
  missing_for_green: string[];
  protocols: { key: string; name: string }[];
  rulepack_version: string;
}

/** The intake fields the rules read (a subset of the kiosk's IntakePayload). */
export interface RuleIntake {
  category?: string | null;
  chief_complaint?: string | null;
  symptoms?: { text?: string | null; original_text?: string | null; language?: string | null; source?: string | null; second_hearing?: { text?: string | null; translation?: string | null; engine?: string | null } | null }[] | null;
  selected_symptoms?: string[] | null;
  answers?: { qid?: string; question?: string | null; answer?: string | null }[] | null;
  staff_answers?: { qid: string; question: string; answer: string; by: string }[] | null;
  duration?: string | null;
  severity?: number | null;
  vitals?: object | null; // numbers by name, plus avpu
  exam?: { done?: boolean; signs?: string[]; by?: string | null } | null;
  maternal?: { gestation_weeks?: number | null } | null;
  lab_values?: Record<string, number | null> | null;
  occupational?: Record<string, unknown> | null;
  age_days?: number | null;
  age_months?: number | null;
}

/* ── Python regex → JavaScript. Python's \w, \b and \d know every script; JavaScript's only know ASCII, so they are
   rewritten to Unicode classes (with the "u" flag). Python letters and digits are what str.isalnum() accepts, which
   leaves out vowel signs, as \p{L}\p{N} does. ── */
const W = "\\p{L}\\p{N}_";
function py(src: string, flags = ""): RegExp {
  let out = "";
  let inClass = false;
  for (let i = 0; i < src.length; i++) {
    const ch = src[i];
    if (ch === "\\") {
      const n = src[++i];
      if (n === "w") out += inClass ? W : `[${W}]`;
      else if (n === "W") {
        if (inClass) throw new Error(`\\W inside a class is not supported: ${src}`);
        out += `[^${W}]`;
      } else if (n === "d") out += "\\p{Nd}";
      else if (n === "b" && !inClass) out += `(?:(?<=[${W}])(?![${W}])|(?<![${W}])(?=[${W}]))`;
      else if (/[A-Za-z0-9]/.test(n) || "^$\\.*+?()[]{}|/-".includes(n)) out += "\\" + n;
      else out += n; // Python's identity escapes (\', \ , \#) are plain characters
      continue;
    }
    if (ch === "[" && !inClass) inClass = true;
    else if (ch === "]" && inClass) inClass = false;
    out += ch;
  }
  return new RegExp(out, flags + "u");
}

function fmt(v: number): string {
  // Python's format(v, "g"): six significant digits, no trailing zeros.
  return String(Number(v.toPrecision(6)));
}

const RANK: Record<Urgency, number> = { green: 0, yellow: 1, red: 2 };
type Op = "lt" | "lte" | "gt" | "gte" | "eq";
const OPS: Record<Op, (a: number, b: number) => boolean> = { lt: (a, b) => a < b, lte: (a, b) => a <= b, gt: (a, b) => a > b, gte: (a, b) => a >= b, eq: (a, b) => a === b };

interface Finding {
  value: Tri;
  evidence: string[];
}

export function createEngine(pack: RulePack) {
  const looseMap = pack.loose.map;
  const norm = (s: string | null | undefined) => (s || "").normalize("NFC").toLowerCase();
  const loose = (s: string) => {
    let t = norm(s);
    for (const d of pack.loose.drop) t = t.split(d).join("");
    let out = "";
    for (const ch of t) out += ch in looseMap ? looseMap[ch] : ch;
    return out;
  };
  const NEG_PRE = py(pack.negation.pre);
  const NEG_POST_EN = py(pack.negation.post_en);
  const CLAUSE_SPLIT = py(pack.negation.clause_split, "g");
  const lex = Object.entries(pack.lexicon).map(([fid, pats]) => [fid, pats.map(([lang, p]) => [lang, lang === "en" ? py(`(?<![\\w])${p}(?![\\w])`, "g") : py(p, "g")] as const)] as const);
  const durationHours = pack.duration_hours.map(([p, r]) => [py(p), r] as const);
  const durationNumber = py(pack.duration_number);
  const EXPLICIT = py(pack.onset.explicit, "gi");
  const RELATIVE = pack.onset.relative.map(([p, d]) => [py(p, "i"), d] as const);
  const NOT_BEFORE = py(pack.onset.not_before);
  const NOT_AFTER = py(`^(?:${pack.onset.not_after})`);

  /* ── findings.py ── */
  function negated(clause: string, start: number, end: number): boolean {
    const before = clause.slice(0, start);
    const after = clause.slice(end);
    if (NEG_PRE.test(before) || NEG_POST_EN.test(after)) return true;
    const tail = after.slice(0, 24);
    return pack.negation.post_indic.some((n) => tail.includes(n));
  }

  function scanText(text: string | null | undefined, source: string): Record<string, Finding> {
    const found: Record<string, Finding> = {};
    const clauses = norm(text).split(CLAUSE_SPLIT).filter((c) => c && c.trim());
    for (const [fid, pats] of lex) {
      for (const clause of clauses) {
        const lc = loose(clause);
        const snippet = [...clause.trim()].slice(0, 80).join("");
        for (const [lang, rx] of pats) {
          const target = lang === "en" ? clause : lc;
          for (const m of target.matchAll(rx)) {
            const s = m.index!;
            const neg = negated(target, s, s + m[0].length);
            const cur = found[fid];
            if (!neg) {
              if (!cur || cur.value !== true) found[fid] = { value: true, evidence: [`${source}: "${snippet}"`] };
            } else if (!cur) found[fid] = { value: false, evidence: [`${source} (denied): "${snippet}"`] };
          }
        }
      }
    }
    return found;
  }

  function merge(into: Record<string, Finding>, fid: string, value: boolean, evidence: string) {
    const cur = into[fid];
    if (!cur || cur.value === null) into[fid] = { value, evidence: [evidence] };
    else if (value === true && cur.value !== true) into[fid] = { value: true, evidence: [evidence] };
    else if (value === cur.value && !cur.evidence.includes(evidence)) cur.evidence.push(evidence);
  }

  function extract(intake: RuleIntake, category: string | null | undefined): Record<string, Finding> {
    const out: Record<string, Finding> = {};
    for (const tile of intake.selected_symptoms ?? []) for (const fid of pack.tiles[norm(tile).trim()] ?? []) merge(out, fid, true, `symptom tile "${tile}"`);

    for (const a of intake.answers ?? []) {
      const qid = a.qid ?? "";
      const ans = (a.answer ?? "").trim();
      for (const [q, prefix, values] of pack.answers) {
        if (q === qid && ans.toLowerCase().startsWith(prefix.toLowerCase()) && !/^\p{L}/u.test(ans.slice(prefix.length, prefix.length + 1))) {
          for (const [fid, val] of Object.entries(values)) merge(out, fid, val, `answer to "${a.question || qid}": ${ans}`);
        }
      }
    }

    const cc = intake.chief_complaint ?? "";
    const texts: [string, string][] = [["chief complaint", cc]];
    for (const s of intake.symptoms ?? []) {
      texts.push([`${s.source ?? "text"} intake`, s.text ?? ""]);
      if (s.original_text && s.original_text !== s.text) texts.push([`${s.source ?? "text"} intake (original ${s.language ?? ""})`, s.original_text]);
    }
    for (const s of intake.symptoms ?? []) {
      const h = s.source === "voice" ? s.second_hearing : null;
      if (!h || typeof h !== "object") continue;
      const heard = new Set<string>();
      for (const first of [s.original_text, s.text]) for (const [f, x] of Object.entries(scanText(first ?? "", ""))) if (x.value === true) heard.add(f);
      const src = `voice intake (second speech engine only, ${h.engine || "online"} — not in the confirmed transcript)`;
      for (const second of [h.text, h.translation])
        for (const [fid, f] of Object.entries(scanText(second ?? "", src))) if (f.value === true && !heard.has(fid)) merge(out, fid, true, f.evidence[0]);
    }
    for (const [src, t] of texts) for (const [fid, f] of Object.entries(scanText(t, src))) for (const e of f.evidence) merge(out, fid, f.value as boolean, e);

    for (const a of intake.staff_answers ?? [])
      for (const [fid, val] of Object.entries(pack.staff_answers[a.qid]?.[a.answer] ?? {})) merge(out, fid, val, `answer to "${a.question}" (asked by ${a.by}): ${a.answer}`);

    const exam = intake.exam ?? {};
    for (const fid of exam.signs ?? []) if (fid in pack.findings) merge(out, fid, true, `danger-sign check by ${exam.by || "clinician"}`);
    if (exam.done)
      for (const [fid, [, kind]] of Object.entries(pack.findings))
        if (kind === "sign" && !(fid in out)) out[fid] = { value: false, evidence: [`danger-sign check by ${exam.by || "clinician"}: not present`] };

    if (category === "maternal") merge(out, "pregnant", true, "visit category: pregnancy");
    if (out.vaginal_bleeding?.value !== true && category === "maternal" && out.bleeding?.value === true) merge(out, "vaginal_bleeding", true, "bleeding reported during a pregnancy visit");
    for (const [child, parent] of pack.implies) {
      const c = out[child];
      if (c && c.value === true) merge(out, parent, true, c.evidence[0]);
    }
    return out;
  }

  function resolve(found: Record<string, Finding>, fid: string): Finding {
    if (!(fid in pack.findings)) throw new Error(`Unknown finding: ${fid}`);
    if (fid in found) return found[fid];
    return pack.findings[fid][1] === "sign" ? { value: null, evidence: [] } : { value: false, evidence: ["not reported"] };
  }

  /* ── timeline.py: an onset the patient stated in their own words ── */
  function statedOnsetDays(intake: RuleIntake): number | null {
    const digits = (t: string) => [...t].map((c) => pack.onset.digits[c] ?? c).join("");
    const texts = [intake.chief_complaint ?? ""];
    for (const s of intake.symptoms ?? []) texts.push(s.original_text ?? "", s.text ?? "");
    for (const a of intake.answers ?? []) if (a.qid !== "dur") texts.push(a.answer ?? "");
    for (const raw of texts) {
      if (!raw) continue;
      const t = digits(raw);
      for (const m of t.matchAll(EXPLICIT)) {
        const before = [...t.slice(0, m.index!).toLowerCase()].slice(-12).join("");
        const after = [...t.slice(m.index! + m[0].length).toLowerCase()].slice(0, 14).join("");
        if (NOT_BEFORE.test(before) || NOT_AFTER.test(after)) continue;
        const n = /^\d+(\.\d+)?$/.test(m[1]) ? Number(m[1]) : pack.onset.num[m[1].toLowerCase()];
        const unit = /^[\x00-\x7f]*$/.test(m[2]) ? m[2].toLowerCase() : m[2];
        return n * pack.onset.unit_days[unit];
      }
      for (const [rx, d] of RELATIVE) if (rx.test(t)) return d;
    }
    return null;
  }

  function onsetHours(intake: RuleIntake): [number, number] | null {
    const texts = [...(intake.answers ?? []).filter((a) => a.qid === "dur").map((a) => a.answer ?? ""), intake.duration ?? ""];
    for (let t of texts) {
      t = t.trim().toLowerCase().replace(/[–—]/g, "-");
      if (!t) continue;
      for (const [rx, rng] of durationHours) if (rx.test(t)) return rng;
      const m = durationNumber.exec(t);
      if (m) {
        const lo = Number(m[1]);
        const hi = Number(m[2] ?? m[1]);
        const per = ({ hour: 1, hr: 1, h: 1, day: 24, week: 168, month: 720 } as Record<string, number>)[m[3]];
        return per > 1 ? [Math.max(0, (lo - 0.5) * per), (hi + 0.5) * per] : [lo, hi];
      }
    }
    const days = statedOnsetDays(intake);
    if (days === null) return null;
    const h = days * 24;
    if (h < 1e-9) return [0, 24];
    const margin = h < 24 ? h * 0.25 : Math.max(12, h * 0.25);
    return [Math.max(0, h - margin), h + margin];
  }

  /* ── rules.py ── */
  interface Ctx {
    findings: Record<string, Finding>;
    vitals: Record<string, number>;
    avpu: string | null;
    age: number;
    ageDays: [number, number];
    sex: string | null;
    severity: number | null;
    onsetH: [number, number] | null;
    gestation: number | null;
    labs: Record<string, number>;
    occ: Record<string, unknown>;
    unknown: Set<string>;
    evidence: string[];
  }

  const compare = (lo: number, hi: number, op: Op, value: number): Tri => {
    const a = OPS[op](lo, value);
    return a === OPS[op](hi, value) ? a : null;
  };
  const and = (v: Tri[]): Tri => (v.some((x) => x === false) ? false : v.every((x) => x === true) ? true : null);
  const or = (v: Tri[]): Tri => (v.some((x) => x === true) ? true : v.every((x) => x === false) ? false : null);
  const round2 = (x: number) => Number(x.toFixed(2));

  function vital(c: Ctx, name: string): number | null {
    if (name === "temp_c") return c.vitals.temp_f !== undefined ? round2(((c.vitals.temp_f - 32) * 5) / 9) : null;
    if (name === "shock_index") {
      const p = c.vitals.pulse;
      const s = c.vitals.bp_systolic;
      return p !== undefined && s ? round2(p / s) : null;
    }
    return c.vitals[name] ?? null;
  }

  function ev(c: Ctx, cond: Cond): Tri {
    const [[key, arg]] = Object.entries(cond) as [string, any][]; // eslint-disable-line @typescript-eslint/no-explicit-any
    switch (key) {
      case "all":
        return and((arg as Cond[]).map((x) => ev(c, x)));
      case "any":
        return or((arg as Cond[]).map((x) => ev(c, x)));
      case "not": {
        const v = ev(c, arg);
        return v === null ? null : !v;
      }
      case "at_least": {
        const vals = (arg.of as Cond[]).map((x) => ev(c, x));
        const yes = vals.filter((v) => v === true).length;
        const maybe = vals.filter((v) => v === null).length;
        return yes >= arg.n ? true : yes + maybe < arg.n ? false : null;
      }
      case "finding": {
        const f = resolve(c.findings, arg);
        if (f.value === null) c.unknown.add(`danger-sign check: ${pack.findings[arg][0].toLowerCase()}`);
        else if (f.value) c.evidence.push(`${pack.findings[arg][0]} — ${f.evidence[0]}`);
        return f.value;
      }
      case "vital":
      case "vital_if_measured": {
        const [name, op, value] = arg as [string, Op, number];
        const v = vital(c, name);
        if (v === null) {
          if (key === "vital_if_measured") return false;
          c.unknown.add(pack.vital_label[name]);
          return null;
        }
        const ok = OPS[op](v, value);
        if (ok) {
          const lab = pack.vital_label[name];
          c.evidence.push(`${lab[0].toUpperCase()}${lab.slice(1)} ${fmt(v)}${pack.unit[name] ? " " + pack.unit[name] : ""}`);
        }
        return ok;
      }
      case "avpu_in":
        if (c.avpu === null) {
          c.unknown.add(pack.vital_label.avpu);
          return null;
        }
        if ((arg as string[]).includes(c.avpu)) {
          c.evidence.push(`AVPU: ${c.avpu}`);
          return true;
        }
        return false;
      case "age_years":
        return OPS[arg[0] as Op](c.age, arg[1]);
      case "age_days": {
        const v = compare(c.ageDays[0], c.ageDays[1], arg[0], arg[1]);
        if (v === null) c.unknown.add("exact age in days or months (infant)");
        return v;
      }
      case "sex":
        return c.sex === null ? null : c.sex === arg;
      case "severity": {
        if (c.severity === null) {
          c.unknown.add("pain / symptom severity");
          return null;
        }
        const ok = OPS[arg[0] as Op](c.severity, arg[1]);
        if (ok) c.evidence.push(`Self-rated severity ${c.severity}/10`);
        return ok;
      }
      case "onset_hours": {
        if (c.onsetH === null) {
          c.unknown.add("time of onset");
          return null;
        }
        const v = compare(c.onsetH[0], c.onsetH[1], arg[0], arg[1]);
        if (v === null) c.unknown.add(`exact time of onset (within ${arg[1]} h?)`);
        else if (v) c.evidence.push(`Onset within ${arg[1]} h`);
        return v;
      }
      case "gestation_weeks":
        if (c.gestation === null) {
          c.unknown.add("gestational age");
          return null;
        }
        return OPS[arg[0] as Op](c.gestation, arg[1]);
      case "lab": {
        const [name, op, value] = arg as [string, Op, number];
        const v = c.labs[name];
        if (v === undefined) return false;
        const ok = OPS[op](v, value);
        if (ok) c.evidence.push(`Report: ${name} ${fmt(v)}`);
        return ok;
      }
      case "exposure": {
        const hit = ((c.occ.exposures as string[] | undefined) ?? []).filter((x) => (arg as string[]).includes(x));
        if (hit.length) c.evidence.push("Works with " + hit.map((x) => pack.exposure_label[x]).join(", "));
        return hit.length > 0;
      }
      case "exposure_years":
      case "cough_weeks": {
        const v = c.occ[key === "exposure_years" ? "years_exposed" : key] as number | null | undefined;
        if (v === null || v === undefined) return false;
        const ok = OPS[arg[0] as Op](Number(v), arg[1]);
        if (ok) c.evidence.push(key === "exposure_years" ? `${fmt(v)} years of exposure` : `Cough for ${fmt(v)} weeks`);
        return ok;
      }
      case "breathless_vs_last": {
        const ok = c.occ.breathless_vs_last === arg;
        if (ok) c.evidence.push(`Breathing ${arg} than at the last screening (worker's answer)`);
        return ok;
      }
      case "fev1_decline_pct": {
        const now = c.occ.fev1_l as number | undefined;
        const base = c.occ.fev1_baseline_l as number | undefined;
        if (!now || !base) return false;
        const pct = Number((((base - now) / base) * 100).toFixed(1));
        const ok = OPS[arg[0] as Op](pct, arg[1]);
        if (ok) c.evidence.push(`FEV1 ${fmt(now)} L, down ${fmt(pct)} % from ${fmt(base)} L on ${c.occ.fev1_baseline_on || "an earlier screening"}`);
        return ok;
      }
    }
    throw new Error(`Unknown rule condition: ${key}`);
  }

  function applies(a: Record<string, unknown>, c: Ctx): boolean {
    if ("age_min" in a && c.age < (a.age_min as number)) return false;
    if ("age_max_exclusive" in a && c.age >= (a.age_max_exclusive as number)) return false;
    if (a.pregnant && resolve(c.findings, "pregnant").value !== true) return false;
    if (a.occupational && !((c.occ.exposures as unknown[] | undefined) ?? []).length) return false;
    return true;
  }

  function ageDays(intake: RuleIntake, age: number): [number, number] {
    if (intake.age_days != null) return [Number(intake.age_days), Number(intake.age_days)];
    if (intake.age_months != null) {
      const m = Number(intake.age_months);
      return [m * 30.4, (m + 1) * 30.4 - 1];
    }
    return [age * 365.25, (age + 1) * 365.25 - 1];
  }

  function evaluate(intake: RuleIntake, age: number, sex: string | null = null): DeviceTriage {
    const raw = (intake.vitals ?? {}) as Record<string, unknown>;
    const vit: Record<string, number> = {};
    for (const [k, v] of Object.entries(raw)) if (v !== null && v !== undefined && v !== "" && pack.vitals.includes(k)) vit[k] = Number(v);
    const avpu = String(raw.avpu ?? "").toUpperCase().slice(0, 1) || null;
    const category = intake.category ?? "normal";
    const c: Ctx = {
      findings: extract(intake, category),
      vitals: vit,
      avpu: avpu && "AVPU".includes(avpu) ? avpu : null,
      age,
      ageDays: ageDays(intake, age),
      sex,
      severity: intake.severity ?? null,
      onsetH: onsetHours(intake),
      gestation: intake.maternal?.gestation_weeks ?? null,
      labs: Object.fromEntries(Object.entries(intake.lab_values ?? {}).filter(([, v]) => v !== null && v !== undefined).map(([k, v]) => [k.toLowerCase(), Number(v)])),
      occ: { ...(intake.occupational ?? {}) },
      unknown: new Set(),
      evidence: [],
    };

    const applied: DeviceTriage["protocols"] = [];
    const hits: RuleHit[] = [];
    const unresolved: DeviceTriage["unresolved"] = [];
    for (const p of pack.protocols) {
      if (!applies(p.applies, c)) continue;
      applied.push({ key: p.key, name: p.name });
      for (const r of p.rules) {
        c.unknown = new Set();
        c.evidence = [];
        const v = ev(c, r.when);
        const base = { rule_id: r.id, protocol: p.key, description: r.description, urgency: r.urgency, source: pack.sources[r.source], source_key: r.source, non_downgradable: r.non_downgradable, review_by: r.review_by };
        if (v === true) hits.push({ ...base, evidence: [...new Set(c.evidence)] });
        else if (v === null) unresolved.push({ ...base, needs: [...c.unknown].sort() });
      }
    }

    const required = age >= 12 ? pack.required_adult : pack.required_child;
    const missing = required.filter((k) => !(k in vit)).map((k) => pack.vital_label[k]);
    if (c.avpu === null) missing.push(pack.vital_label.avpu);
    if (!intake.exam?.done) missing.push("clinician danger-sign check");

    let top: Urgency = hits.reduce<Urgency>((a, h) => (RANK[h.urgency] > RANK[a] ? h.urgency : a), "green");
    const provisional = top !== "red" && (missing.length > 0 || unresolved.length > 0);
    const couldBeRed = [...new Set(unresolved.filter((u) => u.urgency === "red").map((u) => u.rule_id))].sort();
    if (provisional && top === "green") top = "yellow";
    if (provisional) {
      const needs = [...new Set([...unresolved.flatMap((u) => u.needs.map((n) => (n.startsWith("danger-sign") ? "clinician danger-sign check" : n))), ...missing])].sort();
      hits.push({
        rule_id: "SAFE-PROVISIONAL", protocol: "SAFETY", urgency: "yellow",
        description: "UNDETERMINED, held at YELLOW — cannot be routine until measured: " + needs.join(", "),
        source: pack.sources.safety, source_key: "safety", non_downgradable: true, review_by: "nurse",
        evidence: couldBeRed.length ? [`${couldBeRed.length} RED rule(s) could not be ruled out: ${couldBeRed.join(", ")}`] : [],
      });
    } else if (!hits.length) {
      hits.push({
        rule_id: "TRIAGE-GREEN", protocol: "SAFETY", urgency: "green",
        description: "No red or yellow criteria; vital signs measured and within limits; danger-sign check recorded",
        source: pack.sources.safety, source_key: "safety", non_downgradable: false, review_by: "nurse", evidence: [],
      });
    }
    return { urgency: top, provisional, hits, unresolved, missing_for_green: missing, protocols: applied, rulepack_version: pack.version };
  }

  return { evaluate, scanText };
}
