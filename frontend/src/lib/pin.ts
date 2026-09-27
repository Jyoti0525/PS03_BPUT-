/** Mirrors backend `security.pin_problem`: reject PINs that are easy to guess. */
const WEAK = new Set(["1234", "12345", "123456", "4321", "54321", "654321", "1212", "121212", "1122", "112233", "2580", "0852", "1111", "0000", "123123", "147258", "159753"]);

export function pinProblem(pin: string): string | null {
  if (!/^\d{4,6}$/.test(pin)) return "PIN must be 4 to 6 digits";
  if (WEAK.has(pin) || new Set(pin).size === 1) return "That PIN is too easy to guess — choose a less obvious one";
  const steps = new Set([...pin].slice(1).map((c, i) => Number(c) - Number(pin[i])));
  if (steps.size === 1 && (steps.has(1) || steps.has(-1))) return "Avoid sequences like 3456 — choose a less obvious PIN";
  return null;
}

export const SAMPLE_PIN = "4826";
