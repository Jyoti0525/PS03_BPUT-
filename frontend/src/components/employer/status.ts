import type { FitnessStatus } from "@/lib/types";

export const FITNESS: Record<FitnessStatus, { label: string; tone: "rout" | "semi" | "crit" | "neutral" }> = {
  fit: { label: "Fit", tone: "rout" },
  fit_with_restrictions: { label: "Fit with restrictions", tone: "semi" },
  temporarily_unfit: { label: "Temporarily unfit", tone: "crit" },
  pending_review: { label: "Pending review", tone: "neutral" },
};
