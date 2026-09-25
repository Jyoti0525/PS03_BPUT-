/**
 * Mock of the deterministic triage rules engine.
 *
 * The authoritative rules live in `backend/app/triage/rules/*.yaml` (AIIMS Triage Protocol for
 * adults, IMCI for children under 5, maternal red flags). This port exists so the frontend can run
 * with no backend. Urgency is ONLY ever produced here — never by a language model.
 */
import type { IntakePayload, RuleHit, Urgency } from "@/lib/types";

const RANK: Record<Urgency, number> = { green: 0, yellow: 1, red: 2 };

export function maxUrgency(list: Urgency[]): Urgency {
  return list.reduce<Urgency>((a, b) => (RANK[b] > RANK[a] ? b : a), "green");
}

interface Ctx {
  text: string;
  age: number;
  category: IntakePayload["category"];
  v: NonNullable<IntakePayload["vitals"]>;
  severity: number | null;
  duration: string | null;
  weeks: number | null;
}

interface Rule {
  id: string;
  protocol: RuleHit["protocol"];
  description: string;
  urgency: Urgency;
  when: (c: Ctx) => boolean;
}

const has = (c: Ctx, ...words: string[]) => words.some((w) => c.text.includes(w));
const adult = (c: Ctx) => c.age >= 12;
const underFive = (c: Ctx) => c.age < 5;
const pregnant = (c: Ctx) => c.category === "maternal";
const longDuration = (c: Ctx) => !!c.duration && /(3|4|5|6|7).*day|week|month/.test(c.duration);

export const RULES: Rule[] = [
  // ── AIIMS Triage Protocol (adults) ──
  {
    id: "ATP-CARD-01",
    protocol: "ATP",
    description: "Chest pain with radiation or sweating",
    urgency: "red",
    when: (c) => adult(c) && has(c, "chest pain", "chest heaviness", "सीने") && has(c, "arm", "jaw", "sweat", "radiat"),
  },
  {
    id: "ATP-CARD-02",
    protocol: "ATP",
    description: "Chest pain reported",
    urgency: "yellow",
    when: (c) => adult(c) && has(c, "chest pain", "chest heaviness", "सीने"),
  },
  {
    id: "ATP-RESP-01",
    protocol: "ATP",
    description: "SpO₂ below 90% on room air",
    urgency: "red",
    when: (c) => c.v.spo2 != null && c.v.spo2 < 90,
  },
  {
    id: "ATP-RESP-02",
    protocol: "ATP",
    description: "SpO₂ 90–93% on room air",
    urgency: "yellow",
    when: (c) => c.v.spo2 != null && c.v.spo2 >= 90 && c.v.spo2 <= 93,
  },
  {
    id: "ATP-RESP-03",
    protocol: "ATP",
    description: "Respiratory rate ≥ 30/min",
    urgency: "red",
    when: (c) => adult(c) && c.v.resp_rate != null && c.v.resp_rate >= 30,
  },
  {
    id: "ATP-RESP-04",
    protocol: "ATP",
    description: "Breathlessness reported",
    urgency: "yellow",
    when: (c) => has(c, "breathless", "short of breath", "difficulty breathing", "सांस"),
  },
  {
    id: "ATP-VITAL-01",
    protocol: "ATP",
    description: "Systolic ≥ 180 or diastolic ≥ 120 mmHg",
    urgency: "red",
    when: (c) => (c.v.bp_systolic ?? 0) >= 180 || (c.v.bp_diastolic ?? 0) >= 120,
  },
  {
    id: "ATP-VITAL-02",
    protocol: "ATP",
    description: "Systolic ≥ 160 or diastolic ≥ 100 mmHg",
    urgency: "yellow",
    when: (c) => (c.v.bp_systolic ?? 0) >= 160 || (c.v.bp_diastolic ?? 0) >= 100,
  },
  {
    id: "ATP-VITAL-03",
    protocol: "ATP",
    description: "Systolic below 90 mmHg",
    urgency: "red",
    when: (c) => c.v.bp_systolic != null && c.v.bp_systolic < 90,
  },
  {
    id: "ATP-VITAL-04",
    protocol: "ATP",
    description: "Pulse above 130 or below 40 bpm",
    urgency: "red",
    when: (c) => c.v.pulse != null && (c.v.pulse > 130 || c.v.pulse < 40),
  },
  {
    id: "ATP-NEURO-01",
    protocol: "ATP",
    description: "Seizure, unconsciousness or one-sided weakness",
    urgency: "red",
    when: (c) => has(c, "seizure", "fits", "unconscious", "fainted", "slurred", "one side", "stroke", "convulsion"),
  },
  {
    id: "ATP-BLEED-01",
    protocol: "ATP",
    description: "Heavy bleeding or vomiting blood",
    urgency: "red",
    when: (c) => has(c, "heavy bleeding", "vomiting blood", "blood in vomit", "coughing blood"),
  },
  {
    id: "ATP-ENDO-01",
    protocol: "ATP",
    description: "Blood glucose below 70 mg/dL",
    urgency: "red",
    when: (c) => c.v.glucose != null && c.v.glucose < 70,
  },
  {
    id: "ATP-ENDO-02",
    protocol: "ATP",
    description: "Blood glucose above 300 mg/dL",
    urgency: "yellow",
    when: (c) => c.v.glucose != null && c.v.glucose > 300,
  },
  {
    id: "ATP-FEVER-01",
    protocol: "ATP",
    description: "Temperature ≥ 103°F",
    urgency: "yellow",
    when: (c) => c.v.temp_f != null && c.v.temp_f >= 103,
  },
  {
    id: "ATP-FEVER-02",
    protocol: "ATP",
    description: "Fever for 3 days or more",
    urgency: "yellow",
    when: (c) => has(c, "fever", "बुखार", "ଜ୍ୱର") && longDuration(c),
  },
  {
    id: "ATP-TRAUMA-01",
    protocol: "ATP",
    description: "Injury, burn or fall",
    urgency: "yellow",
    when: (c) => has(c, "injury", "burn", "fall", "fracture", "cut ", "accident"),
  },
  {
    id: "ATP-ABD-01",
    protocol: "ATP",
    description: "Severe abdominal pain",
    urgency: "yellow",
    when: (c) => has(c, "abdominal pain", "stomach pain", "pet dard") && (c.severity ?? 0) >= 7,
  },
  {
    id: "ATP-PAIN-01",
    protocol: "ATP",
    description: "Self-reported pain score 8 or above",
    urgency: "yellow",
    when: (c) => (c.severity ?? 0) >= 8,
  },
  // ── Maternal red flags ──
  {
    id: "MAT-01",
    protocol: "MATERNAL",
    description: "Pregnant, BP ≥ 140/90 with headache or blurred vision",
    urgency: "red",
    when: (c) =>
      pregnant(c) &&
      ((c.v.bp_systolic ?? 0) >= 140 || (c.v.bp_diastolic ?? 0) >= 90) &&
      has(c, "headache", "blurred", "vision"),
  },
  {
    id: "MAT-02",
    protocol: "MATERNAL",
    description: "Pregnant with vaginal bleeding",
    urgency: "red",
    when: (c) => pregnant(c) && has(c, "bleeding", "spotting"),
  },
  {
    id: "MAT-03",
    protocol: "MATERNAL",
    description: "Pregnant with reduced fetal movement",
    urgency: "red",
    when: (c) => pregnant(c) && has(c, "reduced movement", "baby not moving", "less movement", "fetal movement reduced"),
  },
  {
    id: "MAT-04",
    protocol: "MATERNAL",
    description: "Pregnant with BP ≥ 140/90",
    urgency: "yellow",
    when: (c) => pregnant(c) && ((c.v.bp_systolic ?? 0) >= 140 || (c.v.bp_diastolic ?? 0) >= 90),
  },
  // ── IMCI (children under 5) ──
  {
    id: "IMCI-DANGER-01",
    protocol: "IMCI",
    description: "General danger sign: convulsions, lethargy, unable to drink, vomits everything",
    urgency: "red",
    when: (c) =>
      underFive(c) && has(c, "convulsion", "fits", "lethargic", "unable to drink", "not feeding", "vomits everything"),
  },
  {
    id: "IMCI-RESP-01",
    protocol: "IMCI",
    description: "Fast breathing or chest indrawing",
    urgency: "yellow",
    when: (c) => underFive(c) && ((c.v.resp_rate ?? 0) >= 40 || has(c, "chest indrawing", "fast breathing")),
  },
  {
    id: "IMCI-FEVER-01",
    protocol: "IMCI",
    description: "Fever in a child under 5",
    urgency: "yellow",
    when: (c) => underFive(c) && has(c, "fever", "बुखार", "ଜ୍ୱର"),
  },
  {
    id: "IMCI-DIARR-01",
    protocol: "IMCI",
    description: "Diarrhoea with signs of dehydration",
    urgency: "yellow",
    when: (c) => underFive(c) && has(c, "diarrhoea", "diarrhea", "loose motion") && has(c, "sunken", "dry mouth", "no urine"),
  },
];

export function evaluate(intake: IntakePayload, age: number): { urgency: Urgency; hits: RuleHit[] } {
  const text = [intake.chief_complaint, ...intake.symptoms.map((s) => s.text), ...intake.selected_symptoms, ...intake.answers.map((a) => a.answer)]
    .join(" ")
    .toLowerCase();
  const ctx: Ctx = {
    text,
    age,
    category: intake.category,
    v: intake.vitals ?? {},
    severity: intake.severity,
    duration: intake.duration,
    weeks: intake.maternal?.gestation_weeks ?? null,
  };
  const hits: RuleHit[] = RULES.filter((r) => r.when(ctx)).map((r) => ({
    rule_id: r.id,
    protocol: r.protocol,
    description: r.description,
    urgency: r.urgency,
  }));
  if (hits.length === 0) {
    hits.push({
      rule_id: "ATP-ROUT-00",
      protocol: underFive(ctx) ? "IMCI" : "ATP",
      description: "No red or yellow criteria met — routine queue",
      urgency: "green",
    });
  }
  return { urgency: maxUrgency(hits.map((h) => h.urgency)), hits };
}
