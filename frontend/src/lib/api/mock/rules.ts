/**
 * Triage for local demo mode (no backend): the device engine (lib/triage), which runs the backend's own rule pack
 * (backend/app/triage/rules/*.yaml, built into rulepack.json). Until 23 Oct this was a small hand-written subset whose
 * colours could differ from the server's; backend/tests/test_device_rules.py now checks both give the same result.
 * Urgency is ONLY ever produced by these rules — never by a language model.
 */
import type { IntakePayload, RuleHit, Urgency } from "@/lib/types";
import type { RuleIntake } from "@/lib/triage/engine";
import { deviceTriage } from "@/lib/triage/device";

const RANK: Record<Urgency, number> = { green: 0, yellow: 1, red: 2 };

export function maxUrgency(list: Urgency[]): Urgency {
  return list.reduce<Urgency>((a, b) => (RANK[b] > RANK[a] ? b : a), "green");
}

export function evaluate(intake: IntakePayload, age: number, sex: string | null = null): { urgency: Urgency; hits: RuleHit[]; rulepack: string } {
  const r = deviceTriage(intake as unknown as RuleIntake, age, sex);
  return { urgency: r.urgency, hits: r.hits as RuleHit[], rulepack: r.rulepack_version };
}
