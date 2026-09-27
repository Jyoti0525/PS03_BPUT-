/**
 * Synthetic lab slips for training at the sample facility. Never offered at real facilities, so fake
 * values can't end up in a real record. Crops are generated so source traceability can be practised.
 */
import type { ValueStatus } from "@/lib/types";
import { renderLabReport } from "@/lib/api/mock/report";

/** The sample training facility, the only place sample reports are offered outside local mock mode. */
export const SAMPLE_FACILITY_ID = "fac_phc_manikpur";

export interface SampleReport {
  key: string;
  title: string;
  lab: string;
  rows: { test: string; value: string; unit: string; ref: string; status: ValueStatus; field?: "glucose" | "bp" | "hb" }[];
  handwritten?: boolean;
}

export const SAMPLE_REPORTS: SampleReport[] = [
  {
    key: "glucose",
    title: "Blood sugar & HbA1c slip",
    lab: "Sunrise Diagnostics (Synthetic)",
    rows: [
      { test: "Fasting Blood Sugar", value: "310", unit: "mg/dL", ref: "70–110", status: "abnormal", field: "glucose" },
      { test: "HbA1c", value: "9.8", unit: "%", ref: "< 7.0", status: "abnormal" },
      { test: "Serum Creatinine", value: "1.38", unit: "mg/dL", ref: "0.6–1.2", status: "borderline" },
      { test: "eGFR", value: "54", unit: "mL/min", ref: "> 60", status: "borderline" },
    ],
  },
  {
    key: "cbc",
    title: "Complete blood count",
    lab: "District Lab Services (Synthetic)",
    rows: [
      { test: "Haemoglobin", value: "9.4", unit: "g/dL", ref: "12.0–15.0", status: "abnormal", field: "hb" },
      { test: "Total WBC", value: "11,800", unit: "/µL", ref: "4,000–11,000", status: "borderline" },
      { test: "Platelets", value: "96,000", unit: "/µL", ref: "1.5–4.5 lakh", status: "abnormal" },
      { test: "PCV", value: "31", unit: "%", ref: "36–46", status: "abnormal" },
    ],
  },
  {
    key: "anc",
    title: "Mother & child protection card",
    lab: "MCP Card — Sub-Centre Entry (Synthetic)",
    handwritten: true,
    rows: [
      { test: "Blood Pressure", value: "150/98", unit: "mmHg", ref: "< 140/90", status: "abnormal", field: "bp" },
      { test: "Urine Albumin", value: "2+", unit: "", ref: "Nil", status: "abnormal" },
      { test: "Haemoglobin", value: "9.6", unit: "g/dL", ref: "≥ 11.0", status: "abnormal", field: "hb" },
      { test: "Fundal Height", value: "31", unit: "cm", ref: "~ weeks", status: "normal" },
    ],
  },
  {
    key: "lipid",
    title: "Lipid profile",
    lab: "CityCare Pathology (Synthetic)",
    rows: [
      { test: "Total Cholesterol", value: "238", unit: "mg/dL", ref: "< 200", status: "abnormal" },
      { test: "LDL", value: "162", unit: "mg/dL", ref: "< 100", status: "abnormal" },
      { test: "HDL", value: "38", unit: "mg/dL", ref: "> 40", status: "borderline" },
      { test: "Triglycerides", value: "180", unit: "mg/dL", ref: "< 150", status: "borderline" },
    ],
  },
];

export function sampleReportImage(key: string, patientName: string) {
  const s = SAMPLE_REPORTS.find((r) => r.key === key)!;
  return renderLabReport({
    lab: s.lab,
    patient: patientName,
    date: new Date().toLocaleDateString("en-IN"),
    rows: s.rows,
    handwritten: s.handwritten,
  });
}

