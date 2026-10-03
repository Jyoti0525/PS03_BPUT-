/**
 * Mock of the note-generation pipeline (ASR → translation → OCR → bounded summariser).
 * The real pipeline is owned by the ML track; this produces the same TriageNote shape from
 * structured intake so every reviewer screen can be exercised. It never assigns urgency —
 * that comes from rules.ts — and never states a diagnosis.
 */
import type {
  Disagreement,
  Encounter,
  ExtractedValue,
  Flag,
  FollowUpQuestion,
  IntakePayload,
  Patient,
  RuleHit,
  TimelineEvent,
  TrendRow,
  TriageNote,
  ValueStatus,
} from "@/lib/types";
import { SAMPLE_REPORTS } from "@/lib/sample-reports";
export { SAMPLE_REPORTS, sampleReportImage } from "@/lib/sample-reports";

let seq = 0;
const vid = () => `v${Date.now().toString(36)}${(seq++).toString(36)}`;

function vitalStatus(kind: string, n: number): ValueStatus {
  switch (kind) {
    case "sys":
      return n >= 160 || n < 90 ? "abnormal" : n >= 140 ? "borderline" : "normal";
    case "spo2":
      return n < 90 ? "abnormal" : n <= 94 ? "borderline" : "normal";
    case "pulse":
      return n > 120 || n < 50 ? "abnormal" : n > 100 ? "borderline" : "normal";
    case "temp":
      return n >= 103 ? "abnormal" : n >= 100 ? "borderline" : "normal";
    case "rr":
      return n >= 30 ? "abnormal" : n > 20 ? "borderline" : "normal";
    case "glucose":
      return n > 300 || n < 70 ? "abnormal" : n > 140 ? "borderline" : "normal";
    default:
      return "normal";
  }
}

export interface UploadedForNote {
  id: string;
  kind: "report" | "image" | "audio";
  filename: string;
  sample_key?: string | null;
  boxes?: [number, number, number, number][] | null;
}

const FOLLOWUPS: { match: RegExp; q: FollowUpQuestion }[] = [
  { match: /chest/, q: { tag: "Onset", question: "Did the chest discomfort start at rest or during effort?", for_role: "doctor" } },
  { match: /chest/, q: { tag: "ECG", question: "Has a 12-lead ECG been recorded since arrival?", for_role: "nurse" } },
  { match: /fever|बुखार/, q: { tag: "Fever pattern", question: "Is the fever continuous or does it come with chills at a fixed time?", for_role: "health_worker" } },
  { match: /fever|बुखार/, q: { tag: "Rash / bleeding", question: "Any rash, gum bleeding or black stools since the fever began?", for_role: "nurse" } },
  { match: /breath|सांस/, q: { tag: "Speech", question: "Can the patient speak full sentences without pausing for breath?", for_role: "nurse" } },
  { match: /headache|vision|blurred/, q: { tag: "Visual change", question: "Any flashing lights, spots or blurred vision right now?", for_role: "nurse" } },
  { match: /cough/, q: { tag: "Duration", question: "Has the cough lasted more than 2 weeks? Any blood in sputum?", for_role: "health_worker" } },
  { match: /abdominal|stomach|pet/, q: { tag: "Location", question: "Where exactly is the pain — upper, lower, right or left side?", for_role: "doctor" } },
  { match: /burn|injury|fall/, q: { tag: "Mechanism", question: "How and when did the injury happen? Any loss of consciousness?", for_role: "nurse" } },
  { match: /diarr|loose/, q: { tag: "Hydration", question: "How many times has the child passed urine in the last 6 hours?", for_role: "health_worker" } },
];

export function buildNote(args: {
  intake: IntakePayload;
  patient: Patient;
  hits: RuleHit[];
  files: UploadedForNote[];
  history: Encounter[];
  proxy: boolean;
}): TriageNote {
  const { intake, patient, hits, files, history } = args;
  const v = intake.vitals ?? {};
  const flags: Flag[] = [];
  const vitals: ExtractedValue[] = [];
  const labs: ExtractedValue[] = [];
  const disagreements: Disagreement[] = [];
  const missing: string[] = [];
  const voice = intake.symptoms.find((s) => s.source === "voice");

  const vitalSource = (label: string) =>
    voice && voice.text.toLowerCase().includes(label)
      ? { kind: "transcript" as const, engine: voice.engine ?? "Browser speech recognition", transcript_excerpt: voice.text, original_excerpt: voice.original_text }
      : { kind: "manual" as const, engine: "Nurse entry at kiosk" };

  if (v.bp_systolic && v.bp_diastolic)
    vitals.push({
      id: vid(),
      label: "Blood pressure",
      value: `${v.bp_systolic}/${v.bp_diastolic}`,
      unit: "mmHg",
      status: vitalStatus("sys", v.bp_systolic),
      needs_check: false,
      source: vitalSource("bp"),
    });
  if (v.pulse) vitals.push({ id: vid(), label: "Pulse", value: String(v.pulse), unit: "bpm", status: vitalStatus("pulse", v.pulse), needs_check: false, source: { kind: "sensor", engine: "Pulse oximeter" } });
  if (v.spo2) vitals.push({ id: vid(), label: "SpO₂", value: String(v.spo2), unit: "%", status: vitalStatus("spo2", v.spo2), needs_check: v.spo2 < 90, source: { kind: "sensor", engine: "Pulse oximeter" } });
  if (v.temp_f) vitals.push({ id: vid(), label: "Temperature", value: String(v.temp_f), unit: "°F", status: vitalStatus("temp", v.temp_f), needs_check: false, source: { kind: "sensor", engine: "IR thermometer" } });
  if (v.resp_rate) vitals.push({ id: vid(), label: "Resp. rate", value: String(v.resp_rate), unit: "/min", status: vitalStatus("rr", v.resp_rate), needs_check: false, source: { kind: "manual", engine: "Nurse count" } });
  if (v.glucose) vitals.push({ id: vid(), label: "Glucose (POC)", value: String(v.glucose), unit: "mg/dL", status: vitalStatus("glucose", v.glucose), needs_check: false, source: { kind: "sensor", engine: "Glucometer" } });

  for (const f of files) {
    if (f.kind !== "report") continue;
    const sample = SAMPLE_REPORTS.find((s) => s.key === f.sample_key);
    if (!sample) {
      missing.push(`Uploaded report "${f.filename}" is awaiting OCR — review the image directly`);
      continue;
    }
    sample.rows.forEach((row, i) => {
      const ev: ExtractedValue = {
        id: vid(),
        label: row.test,
        value: row.value,
        unit: row.unit || null,
        reference: row.ref,
        status: row.status,
        needs_check: false,
        source: {
          kind: "image_crop",
          engine: "Synthetic sample report — values pre-extracted for the demo (not OCR)",
          file_id: f.id,
          bbox: f.boxes?.[i] ?? null,
          crop_text: `${row.test}  ${row.value} ${row.unit}`,
        },
      };
      // Cross-source disagreement: report value vs value captured at the kiosk.
      if (row.field === "bp" && v.bp_systolic && v.bp_diastolic) {
        const kiosk = `${v.bp_systolic}/${v.bp_diastolic}`;
        if (kiosk !== row.value) {
          ev.needs_check = true;
          const bpVital = vitals.find((x) => x.label === "Blood pressure");
          if (bpVital) bpVital.needs_check = true;
          disagreements.push({
            field: "Blood pressure",
            values: [
              { engine: "Kiosk reading", value: `${kiosk} mmHg` },
              { engine: "OCR from card", value: `${row.value} mmHg` },
            ],
            action: "Needs checking — re-measure during examination",
          });
        }
      }
      if (row.field === "glucose" && v.glucose && Math.abs(v.glucose - Number(row.value)) > 40) {
        ev.needs_check = true;
        disagreements.push({
          field: "Blood glucose",
          values: [
            { engine: "Glucometer today", value: `${v.glucose} mg/dL` },
            { engine: "OCR from slip", value: `${row.value} mg/dL` },
          ],
          action: "Needs checking — confirm date of the lab slip",
        });
      }
      labs.push(ev);
    });
  }

  for (const h of hits) {
    if (h.urgency === "green") continue;
    flags.push({
      code: h.rule_id,
      label: h.description,
      severity: h.urgency === "red" ? "critical" : "warning",
      reason: `${h.protocol} rule ${h.rule_id} matched on intake data`,
    });
  }
  for (const d of disagreements)
    flags.push({ code: "DISAGREE", label: `${d.field}: sources disagree`, severity: "warning", reason: d.action });
  if (voice && !voice.confirmed_by_readback)
    flags.push({ code: "ASR-UNCONFIRMED", label: "Voice transcript not confirmed by read-back", severity: "warning", reason: "Patient skipped the spoken confirmation step" });
  if (args.proxy) flags.push({ code: "PROXY", label: "History given by a proxy", severity: "info", reason: "Consent and history captured from a family member or caregiver" });
  if (intake.captured_offline) flags.push({ code: "OFFLINE", label: "Captured offline, synced later", severity: "info", reason: "Wait time is counted from the original capture time" });

  if (!v.bp_systolic) missing.push("Blood pressure not recorded");
  if (!v.pulse && !v.spo2) missing.push("Pulse / SpO₂ not recorded");
  if (!intake.duration) missing.push("Duration of complaint not stated");
  if (intake.category === "maternal" && !intake.maternal?.gestation_weeks) missing.push("Gestational age not recorded");
  if (intake.category === "chronic" && !intake.chronic?.current_medicines) missing.push("Current medicines and adherence not recorded");
  if (intake.category === "chronic" && !files.some((f) => f.kind === "report")) missing.push("No recent lab report for chronic follow-up");

  const text = [intake.chief_complaint, ...intake.symptoms.map((s) => s.text), ...intake.selected_symptoms].join(" ").toLowerCase();
  const followup: FollowUpQuestion[] = [];
  for (const f of FOLLOWUPS) if (f.match.test(text) && followup.length < 5) followup.push(f.q);
  if (followup.length === 0)
    followup.push({ tag: "Context", question: "Anything else that changed recently — food, work, travel or medicines?", for_role: "health_worker" });

  const timeline: TimelineEvent[] = [];
  const prior = history.filter((e) => e.intake).slice(0, 3);
  for (const e of prior) timeline.push({ when: new Date(e.created_at).toLocaleDateString("en-IN"), event: `Previous visit: ${e.chief_complaint}` });
  if (intake.chronic?.last_checkup) timeline.push({ when: intake.chronic.last_checkup, event: `Last ${intake.chronic.condition} check-up` });
  if (intake.duration) timeline.push({ when: `${intake.duration} ago`, event: `Onset: ${intake.chief_complaint}` });
  timeline.push({ when: "Today", event: `Intake at kiosk (${intake.language.toUpperCase()}, ${intake.symptoms[0]?.source ?? "text"})` });

  const trend: TrendRow[] = [];
  const bpHist = [...history]
    .reverse()
    .map((e) => e.intake?.vitals)
    .filter((x): x is NonNullable<typeof x> => !!x?.bp_systolic);
  if (v.bp_systolic && bpHist.length) {
    const pts = [...bpHist.map((x, i) => ({ label: `Visit ${i + 1}`, value: x.bp_systolic! })), { label: "Today", value: v.bp_systolic }];
    const d = pts[pts.length - 1].value - pts[0].value;
    trend.push({ parameter: "Systolic BP (mmHg)", points: pts, direction: d > 8 ? "worse" : d < -8 ? "better" : "stable" });
  }
  const gHist = [...history].reverse().map((e) => e.intake?.vitals?.glucose).filter((x): x is number => !!x);
  if (v.glucose && gHist.length) {
    const pts = [...gHist.map((g, i) => ({ label: `Visit ${i + 1}`, value: g })), { label: "Today", value: v.glucose }];
    const d = pts[pts.length - 1].value - pts[0].value;
    trend.push({ parameter: "Glucose (mg/dL)", points: pts, direction: d > 20 ? "worse" : d < -20 ? "better" : "stable" });
  }

  const sexWord = patient.sex === "F" ? "female" : patient.sex === "M" ? "male" : "patient";
  const parts = [
    `${patient.age}-year-old ${sexWord}, ${intake.category === "normal" ? "general" : intake.category} visit.`,
    `Chief complaint: ${intake.chief_complaint}${intake.duration ? ` for ${intake.duration}` : ""}.`,
  ];
  if (intake.selected_symptoms.length) parts.push(`Also reports: ${intake.selected_symptoms.join(", ")}.`);
  if (intake.severity != null) parts.push(`Self-rated severity ${intake.severity}/10.`);
  if (intake.maternal?.gestation_weeks) parts.push(`Pregnant, ${intake.maternal.gestation_weeks} weeks by history.`);
  if (intake.chronic) parts.push(`Known ${intake.chronic.condition}; patient feels ${intake.chronic.feeling_vs_last} compared with last visit.`);
  if (labs.some((l) => l.status === "abnormal")) parts.push(`Uploaded report shows ${labs.filter((l) => l.status === "abnormal").map((l) => `${l.label} ${l.value}${l.unit ? " " + l.unit : ""}`).join(", ")} outside reference range.`);
  parts.push("Summary organises patient-provided information only; it is not a diagnosis.");

  return {
    summary: parts.join(" "),
    flags,
    rules_fired: hits,
    vitals,
    labs,
    timeline,
    missing_info: missing,
    followup_questions: followup,
    trend,
    disagreements,
    transcript: voice ? { original: voice.original_text, translated: voice.text, language: voice.language } : null,
    generated_by: "mock-pipeline (rules v1 + template summariser)",
    generated_at: new Date().toISOString(),
  };
}
