import type { CadreKey, FacilityRegion } from "@/lib/types";

const NATIONAL: Record<CadreKey, string> = { community: "ASHA", nurse: "ANM", nutrition: "Anganwadi worker", male: "MPW", cho: "CHO" };

/** F5: the title staff use in this facility's state for a front-line worker (ASHA, Mitanin, Sahiya, VHN…), in the
 *  screen language when the table has it. Falls back to the national name when the facility is not loaded yet. */
export function cadreName(region: FacilityRegion | null | undefined, key: CadreKey, lang = "en"): string {
  const c = region?.cadres?.[key];
  if (!c) return NATIONAL[key];
  return (c as unknown as Record<string, string | undefined>)[lang] ?? c.en;
}

/** True when the facility uses the national name, so the existing translated label can be shown as it is. */
export function isNational(region: FacilityRegion | null | undefined, key: CadreKey): boolean {
  return !region?.cadres?.[key] || region.cadres[key].en === NATIONAL[key];
}

/** "Health worker / ASHA", or the state's title for the community worker ("Health worker / Mitanin" in Chhattisgarh). */
export function healthWorkerLabel(region: FacilityRegion | null | undefined, tr: (s: string) => string, lang = "en"): string {
  return isNational(region, "community") ? tr("Health worker / ASHA") : `${tr("Health worker")} / ${cadreName(region, "community", lang)}`;
}

/** "Nurse / ANM", or the state's title for the same post: "Nurse / VHN" in Tamil Nadu, "Nurse / Arogya Sevika" in Maharashtra. */
export function nurseLabel(region: FacilityRegion | null | undefined, tr: (s: string) => string, lang = "en"): string {
  return isNational(region, "nurse") ? tr("Nurse / ANM") : `${tr("Nurse")} / ${cadreName(region, "nurse", lang)}`;
}
