/**
 * The server's triage rules on this device (engine.ts + rulepack.json, built from the backend). Used when there is no
 * server: an offline kiosk checks each queued intake for danger signs, and local demo mode triages with it.
 * The server always triages the intake again when it arrives; the device result is never stored as the record.
 */
import pack from "./rulepack.json";
import { createEngine, type DeviceTriage, type RuleIntake, type RulePack } from "./engine";

let engine: ReturnType<typeof createEngine> | null = null;

export function deviceTriage(intake: RuleIntake, age: number, sex: string | null = null): DeviceTriage {
  engine ??= createEngine(pack as unknown as RulePack);
  return engine.evaluate(intake, age, sex);
}

/** What an offline kiosk tells the patient: only whether a danger sign means "tell the nurse now", never a colour. */
export interface DeviceCheck {
  /** A RED rule fired on what the patient told the kiosk. */
  red: boolean;
  /** The RED rules that fired, for staff (the patient sees only the instruction). */
  rules: { id: string; description: string; evidence: string[] }[];
  rulepack: string;
  at: string;
}

export function offlineCheck(intake: RuleIntake, age: number, sex: string | null): DeviceCheck | null {
  try {
    const r = deviceTriage(intake, age, sex);
    const rules = r.hits.filter((h) => h.urgency === "red").map((h) => ({ id: h.rule_id, description: h.description, evidence: h.evidence }));
    return { red: rules.length > 0, rules, rulepack: r.rulepack_version, at: new Date().toISOString() };
  } catch {
    return null; // never stop an intake from being saved; the server triages it on arrival
  }
}
