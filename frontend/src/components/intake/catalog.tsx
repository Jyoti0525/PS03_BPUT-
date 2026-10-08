import { Thermometer, Wind, HeartCrack, Brain, Droplets, Bandage, BatteryLow, Zap, Waves, RotateCw, Soup, Toilet, Bone, CircleAlert, Sparkles, Frown, Smile, Meh, Annoyed, Angry } from "lucide-react";
import type { ReactNode } from "react";
import type { DictKey } from "@/lib/i18n/dict";
import type { IntakePayload } from "@/lib/types";
import flow from "@/lib/question_flow.json";

/** Icon-first symptom tiles. `en` is the working-language text sent to the rules engine. */
export const SYMPTOMS: { key: DictKey; en: string; icon: ReactNode }[] = [
  { key: "sym.fever", en: "Fever", icon: <Thermometer /> },
  { key: "sym.cough", en: "Cough", icon: <Waves /> },
  { key: "sym.breath", en: "Breathlessness", icon: <Wind /> },
  { key: "sym.chest", en: "Chest pain", icon: <HeartCrack /> },
  { key: "sym.headache", en: "Headache", icon: <Brain /> },
  { key: "sym.stomach", en: "Stomach pain", icon: <Soup /> },
  { key: "sym.vomit", en: "Vomiting", icon: <CircleAlert /> },
  { key: "sym.diarrhoea", en: "Loose motions (diarrhoea)", icon: <Toilet /> },
  { key: "sym.bodyache", en: "Body ache", icon: <Bone /> },
  { key: "sym.injury", en: "Injury or burn", icon: <Bandage /> },
  { key: "sym.bleeding", en: "Bleeding", icon: <Droplets /> },
  { key: "sym.dizzy", en: "Dizziness", icon: <RotateCw /> },
  { key: "sym.swelling", en: "Swelling", icon: <Sparkles /> },
  { key: "sym.rash", en: "Skin rash", icon: <Sparkles /> },
  { key: "sym.tired", en: "Tiredness", icon: <BatteryLow /> },
  { key: "sym.fits", en: "Fits / convulsion", icon: <Zap /> },
];

export const DURATIONS: { key: DictKey; en: string }[] = [
  { key: "dur.today", en: "today" },
  { key: "dur.1_2d", en: "1-2 days" },
  { key: "dur.3_7d", en: "3-7 days" },
  { key: "dur.1_4w", en: "1-4 weeks" },
  { key: "dur.month", en: "more than a month" },
];

export const SEVERITIES: { key: DictKey; value: number; icon: ReactNode; cls: string }[] = [
  { key: "sev.mild", value: 2, icon: <Smile />, cls: "text-rout" },
  { key: "sev.moderate", value: 5, icon: <Meh />, cls: "text-amber-600" },
  { key: "sev.severe", value: 7, icon: <Annoyed />, cls: "text-orange-600" },
  { key: "sev.worst", value: 9, icon: <Angry />, cls: "text-crit" },
];

export const FROWN = <Frown />;

export interface ContextQuestion {
  qid: string;
  question: string;
  options: string[];
}

type Cond = { words?: string[]; age_lt?: number; age_gte?: number; category?: string; not_category?: string; sex?: string; duration_unset_or?: string; any?: Cond[] };
type FlowQuestion = { qid: string; question: string; safety?: boolean; core?: boolean; position?: "first"; when?: Cond; options: { label: string }[] };

/** Questions whose answer can make a case RED (`safety: true`). Always asked, whatever the facility's load. */
const FLOW = flow.questions as FlowQuestion[];
const SAFETY = new Set(FLOW.filter((q) => q.safety).map((q) => q.qid));
/** History every note needs (`core: true`): allergies, regular medicines, long-term illness. */
const CORE = new Set(FLOW.filter((q) => q.core).map((q) => q.qid));

/**
 * Context engine: asks what the reviewer will need that the patient has not yet said.
 * Bounded, closed-ended questions only — answers feed the deterministic rules engine.
 * The questions, their conditions and the findings each answer sets are one versioned file shared with the backend:
 * backend/app/triage/question_flow.yaml, built into lib/question_flow.json (CI fails when the two differ).
 */
/** F2: the question budget follows the facility's patient load. High: safety questions only. Normal: safety, then core history, then
 * others up to 9. Low: all. */
export function contextQuestions(draft: Pick<IntakePayload, "chief_complaint" | "selected_symptoms" | "category" | "symptoms" | "duration"> & { sex?: string }, age: number, load: "low" | "normal" | "high" = "normal"): ContextQuestion[] {
  const all = allQuestions(draft, age);
  if (load === "low") return all;
  if (load === "high") return all.filter((q) => SAFETY.has(q.qid));
  let room = 9 - all.filter((q) => SAFETY.has(q.qid) || CORE.has(q.qid)).length; // every safety and core question, then others while there is room
  return all.filter((q) => SAFETY.has(q.qid) || CORE.has(q.qid) || room-- > 0);
}

function allQuestions(draft: Pick<IntakePayload, "chief_complaint" | "selected_symptoms" | "category" | "symptoms" | "duration"> & { sex?: string }, age: number): ContextQuestion[] {
  const text = [draft.chief_complaint, ...draft.selected_symptoms, ...draft.symptoms.map((s) => s.text)].join(" ").toLowerCase();
  const holds = (c: Cond): boolean =>
    (!c.words || c.words.some((w) => text.includes(w))) &&
    (c.age_lt === undefined || age < c.age_lt) &&
    (c.age_gte === undefined || age >= c.age_gte) &&
    (!c.category || draft.category === c.category) &&
    (!c.not_category || draft.category !== c.not_category) &&
    (!c.sex || draft.sex === c.sex) &&
    (!c.duration_unset_or || !draft.duration || draft.duration === c.duration_unset_or) &&
    (!c.any || c.any.some(holds));
  const qs = FLOW.filter((q) => holds(q.when ?? {})).map((q) =>
    // "Today" was already tapped: narrow it down instead of asking "since when" a second time.
    q.qid === "dur" && draft.duration === "today"
      ? { qid: q.qid, question: "You said today. Did it start in the last few hours?", options: ["In the last few hours", "Earlier today"] }
      : { qid: q.qid, question: q.question, options: q.options.map((o) => o.label) },
  );
  const first = new Set(FLOW.filter((q) => q.position === "first").map((q) => q.qid));
  return [...qs.filter((q) => first.has(q.qid)), ...qs.filter((q) => !first.has(q.qid))];
}
