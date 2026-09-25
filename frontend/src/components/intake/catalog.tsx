import { Thermometer, Wind, HeartCrack, Brain, Droplets, Bandage, BatteryLow, Zap, Waves, RotateCw, Soup, Toilet, Bone, CircleAlert, Sparkles, Frown, Smile, Meh, Annoyed, Angry } from "lucide-react";
import type { ReactNode } from "react";
import type { DictKey } from "@/lib/i18n/dict";
import type { IntakePayload } from "@/lib/types";

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

/**
 * Context engine: asks what the reviewer will need that the patient has not yet said.
 * Bounded, closed-ended questions only — answers feed the deterministic rules engine.
 */
export function contextQuestions(draft: Pick<IntakePayload, "chief_complaint" | "selected_symptoms" | "category" | "symptoms" | "duration">, age: number): ContextQuestion[] {
  const text = [draft.chief_complaint, ...draft.selected_symptoms, ...draft.symptoms.map((s) => s.text)].join(" ").toLowerCase();
  const qs: ContextQuestion[] = [];
  const has = (...w: string[]) => w.some((x) => text.includes(x));
  if (has("chest")) {
    qs.push({ qid: "chest_radiation", question: "Does the pain spread to the arm, jaw or back?", options: ["Yes — spreads to arm / jaw", "No", "Not sure"] });
    qs.push({ qid: "chest_sweat", question: "Is there sweating or feeling faint with the pain?", options: ["Yes — sweating", "No"] });
  }
  if (has("breath")) qs.push({ qid: "breath_speech", question: "Can the patient speak a full sentence without stopping for breath?", options: ["Yes", "No — difficulty breathing while talking"] });
  if (has("fever") && age < 5) qs.push({ qid: "child_danger", question: "Is the child able to drink or breastfeed?", options: ["Yes", "No — unable to drink", "Vomits everything"] });
  if (has("fever")) qs.push({ qid: "fever_bleed", question: "Any rash, bleeding gums or black stools?", options: ["No", "Rash", "Bleeding"] });
  if (has("headache") && draft.category === "maternal") qs.push({ qid: "mat_vision", question: "Any blurred vision or seeing spots?", options: ["Yes — blurred vision", "No"] });
  if (draft.category === "maternal") {
    qs.push({ qid: "mat_movement", question: "Is the baby moving as usual today?", options: ["Yes", "Less than usual — reduced movement", "Not yet felt (early pregnancy)"] });
    qs.push({ qid: "mat_bleed", question: "Any bleeding or fluid leaking?", options: ["No", "Yes — bleeding", "Fluid leaking"] });
  }
  if (has("diarr", "loose")) qs.push({ qid: "dehyd", question: "Dry mouth, sunken eyes or passing very little urine?", options: ["No", "Yes — sunken eyes / dry mouth"] });
  if (has("injury", "burn")) qs.push({ qid: "inj_loc", question: "Did the person faint or hit their head?", options: ["No", "Yes — fainted / head injury"] });
  if (has("stomach")) qs.push({ qid: "abd_where", question: "Where is the pain?", options: ["Upper", "Lower right", "Lower left", "All over"] });
  if (!draft.duration) qs.push({ qid: "dur", question: "Since when do you have this problem?", options: ["Today", "1–2 days", "3–7 days", "More than a week"] });
  if (draft.category === "chronic") qs.push({ qid: "chr_meds", question: "Are you taking your medicines every day?", options: ["Yes, every day", "Sometimes miss", "Stopped taking"] });
  return qs.slice(0, 5);
}
