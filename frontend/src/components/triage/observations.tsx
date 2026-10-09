"use client";

import { useState } from "react";
import { fmtDateTime } from "@/lib/hooks";
import { Activity, ClipboardPen, NotebookPen } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Badge, Button, Card, CardHeader, cx, FieldError, Input, Label, Textarea } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { usePrefs } from "@/components/providers";
import type { Encounter, NumericVital, Observation, VitalsInput } from "@/lib/types";

type Field = { key: NumericVital; label: string; unit: string; min: number; max: number; step?: number };

/** A8: one fixed unit per vital and the plausible range; shared by the kiosk and the nurse's re-measure form. */
export const FIELDS: Field[] = [
  { key: "bp_systolic", label: "BP systolic", unit: "mmHg", min: 50, max: 260 },
  { key: "bp_diastolic", label: "BP diastolic", unit: "mmHg", min: 30, max: 160 },
  { key: "pulse", label: "Pulse", unit: "bpm", min: 20, max: 250 },
  { key: "spo2", label: "SpO₂", unit: "%", min: 50, max: 100 },
  { key: "temp_f", label: "Temperature", unit: "°F", min: 90, max: 110, step: 0.1 },
  { key: "resp_rate", label: "Resp. rate", unit: "/min", min: 4, max: 80 },
  { key: "glucose", label: "Glucose (POC)", unit: "mg/dL", min: 20, max: 600 },
];

const VITAL_LABEL: Record<string, string> = { ...Object.fromEntries(FIELDS.map((f) => [f.key, f.label])), avpu: "AVPU" };

const AVPU: { v: "A" | "V" | "P" | "U"; label: string }[] = [
  { v: "A", label: "Alert" },
  { v: "V", label: "Responds to voice" },
  { v: "P", label: "Responds to pain" },
  { v: "U", label: "Unresponsive" },
];

/** Danger signs from the WHO IITT charts and the AIIMS Triage Protocol that need a trained eye.
 *  Ids match backend findings; until this check is saved they count as unknown, never as absent. */
const SIGNS: { id: string; label: string; child?: boolean }[] = [
  { id: "stridor", label: "Stridor / noisy breathing" },
  { id: "respiratory_distress", label: "Respiratory distress (accessory muscles, flaring, grunting)" },
  { id: "cyanosis", label: "Central cyanosis (blue lips or tongue)" },
  { id: "incomplete_sentences", label: "Cannot speak full sentences" },
  { id: "wheeze", label: "Audible wheeze" },
  { id: "chest_indrawing", label: "Lower chest indrawing", child: true },
  { id: "angioedema_face", label: "Swelling of face, lips or tongue" },
  { id: "swelling_mouth_neck", label: "Swelling or mass of mouth, throat or neck" },
  { id: "cap_refill_gt3", label: "Capillary refill > 3 s" },
  { id: "weak_fast_pulse", label: "Weak and fast pulse" },
  { id: "cold_extremities", label: "Cold hands and feet" },
  { id: "severe_pallor", label: "Severe pallor" },
  { id: "altered_mental_status", label: "Confused or disoriented" },
  { id: "lethargy", label: "Lethargic or abnormally sleepy" },
  { id: "irritable", label: "Restless or continuously irritable", child: true },
  { id: "stiff_neck", label: "Stiff neck" },
  { id: "sunken_eyes", label: "Sunken eyes", child: true },
  { id: "skin_pinch_slow", label: "Skin pinch goes back very slowly", child: true },
  { id: "malnutrition", label: "Visible severe wasting or swelling of both feet", child: true },
];
const SIGN_LABEL: Record<string, string> = Object.fromEntries(SIGNS.map((s) => [s.id, s.label]));

/** Record vitals and bedside observations. Rules run again on the server, so urgency can rise. */
export function ObservationForm({ enc, onSaved, compact }: { enc: Encounter; onSaved: (e: Encounter) => void; compact?: boolean }) {
  const { tr } = usePrefs();
  const [v, setV] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [avpu, setAvpu] = useState<VitalsInput["avpu"]>(null);
  const [signs, setSigns] = useState<string[]>([]);
  const [examDone, setExamDone] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const child = enc.patient.age < 12;
  const priorExam = !!(enc.intake as { exam?: { done?: boolean } } | null)?.exam?.done;
  const [busy, setBusy] = useState(false);

  async function save() {
    setErr(null);
    const vitals: VitalsInput = {};
    for (const f of FIELDS) {
      const raw = v[f.key]?.trim();
      if (!raw) continue;
      const n = Number(raw);
      if (!Number.isFinite(n) || n < f.min || n > f.max) return setErr(`${tr(f.label)}: ${f.min}–${f.max} ${f.unit}`);
      vitals[f.key] = n;
    }
    if (!!vitals.bp_systolic !== !!vitals.bp_diastolic) return setErr(tr("Enter both BP values"));
    if (vitals.bp_systolic && vitals.bp_diastolic && vitals.bp_systolic <= vitals.bp_diastolic) return setErr(tr("BP systolic (top number) must be higher than diastolic (bottom number). Check they are not swapped."));
    if (avpu) vitals.avpu = avpu;
    if (!Object.keys(vitals).length && !note.trim() && !signs.length && !examDone) return setErr(tr("Enter at least one vital sign, danger sign or observation"));
    setBusy(true);
    try {
      const before = enc.urgency;
      const e = await api.addObservations(enc.id, { vitals, note: note.trim() || null, signs, exam_done: examDone });
      setV({});
      setNote("");
      setAvpu(null);
      setSigns([]);
      setExamDone(false);
      toast(e.urgency !== before ? tr("Saved — the rules raised the urgency; the doctor has been alerted in the queue") : tr("Observations saved to the patient record"), e.urgency !== before ? "info" : "success");
      onSaved(e);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : tr("Could not save"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardHeader title={tr("Record vitals & observations")} subtitle={tr("Saved to the patient record with your name. Urgency is re-checked by the fixed rules.")} icon={<ClipboardPen className="size-4" />} />
      <div className="space-y-4 p-4">
        <div className={compact ? "grid grid-cols-2 gap-3" : "grid grid-cols-2 gap-3 sm:grid-cols-4"}>
          {FIELDS.map((f) => (
            <div key={f.key}>
              <Label htmlFor={`ob-${f.key}`} hint={f.unit}>
                {tr(f.label)}
              </Label>
              <Input id={`ob-${f.key}`} inputMode="decimal" type="number" step={f.step ?? 1} min={f.min} max={f.max} value={v[f.key] ?? ""} onChange={(e) => setV({ ...v, [f.key]: e.target.value })} />
            </div>
          ))}
        </div>
        <fieldset>
          <legend className="mb-1.5 text-sm font-medium text-ink">{tr("Level of consciousness (AVPU)")}</legend>
          <div className="flex flex-wrap gap-2">
            {AVPU.map((a) => (
              <button
                key={a.v}
                type="button"
                aria-pressed={avpu === a.v}
                onClick={() => setAvpu(avpu === a.v ? null : a.v)}
                className={cx("min-h-10 rounded-lg border-2 px-3 text-sm", avpu === a.v ? (a.v === "A" ? "border-teal-600 bg-teal-50 text-teal-800" : "border-crit bg-crit-bg text-crit") : "border-line text-ink-2")}
              >
                <strong>{a.v}</strong> · {tr(a.label)}
              </button>
            ))}
          </div>
        </fieldset>
        <fieldset className="rounded-xl border border-line p-3">
          <legend className="px-1 text-sm font-medium text-ink">{tr("Danger-sign check")}</legend>
          <p className="mb-2 text-xs text-muted">{tr("Tick every sign present. Until the check is saved, these count as unknown — the case cannot be routine.")}</p>
          <div className={compact ? "grid gap-1.5" : "grid gap-1.5 sm:grid-cols-2"}>
            {SIGNS.filter((s) => child || !s.child).map((s) => (
              <label key={s.id} className="flex items-start gap-2 text-sm text-ink-2">
                <input type="checkbox" className="mt-0.5 size-4 accent-current" checked={signs.includes(s.id)} onChange={(e) => setSigns(e.target.checked ? [...signs, s.id] : signs.filter((x) => x !== s.id))} />
                {tr(s.label)}
              </label>
            ))}
          </div>
          <label className="mt-3 flex items-center gap-2 border-t border-line pt-2.5 text-sm font-medium text-ink">
            <input type="checkbox" className="size-4" checked={examDone} onChange={(e) => setExamDone(e.target.checked)} />
            {priorExam ? tr("Danger-sign check repeated (already recorded once)") : tr("I have checked for all the signs above")}
          </label>
        </fieldset>
        <div>
          <Label htmlFor="ob-note" hint={tr("(optional)")}>
            {tr("Nursing observation")}
          </Label>
          <Textarea id="ob-note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder={tr("e.g. Breathless on walking, pale, pain 6/10, vomited once")} />
        </div>
        <FieldError>{err}</FieldError>
        <Button onClick={save} loading={busy} icon={<Activity className="size-4" />}>
          {tr("Save observations")}
        </Button>
      </div>
    </Card>
  );
}

export function ObservationList({ items }: { items: Observation[] | undefined }) {
  const { tr } = usePrefs();
  if (!items?.length) return null;
  return (
    <Card>
      <CardHeader title={tr("Bedside observations")} subtitle={tr("Recorded by nurses and doctors during this visit")} icon={<NotebookPen className="size-4" />} />
      <ul className="divide-y divide-line">
        {[...items].reverse().map((o, i) => (
          <li key={i} className="px-4 py-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-ink">{o.by}</span>
              <Badge tone={o.role === "nurse" ? "teal" : "info"}>{tr(o.role === "nurse" ? "Nurse" : "Doctor")}</Badge>
              <span className="text-xs text-subtle">{fmtDateTime(o.at)}</span>
            </div>
            {Object.keys(o.vitals ?? {}).length > 0 && (
              <p className="mt-1 flex flex-wrap gap-1.5">
                {Object.entries(o.vitals).map(([k, val]) => (
                  <span key={k} className="rounded-md bg-canvas px-2 py-0.5 text-xs text-ink-2">
                    {tr(VITAL_LABEL[k] ?? k)}: <strong>{String(val)}</strong>
                  </span>
                ))}
              </p>
            )}
            {(o.signs?.length ?? 0) > 0 && (
              <p className="mt-1 flex flex-wrap gap-1.5">
                {o.signs!.map((s) => (
                  <span key={s} className="rounded-md bg-crit-bg px-2 py-0.5 text-xs font-medium text-crit">
                    {tr(SIGN_LABEL[s] ?? s)}
                  </span>
                ))}
              </p>
            )}
            {o.exam_done && <p className="mt-1 text-xs text-muted">{tr("Danger-sign check completed")}</p>}
            {o.note && <p className="mt-1 text-ink-2">{o.note}</p>}
          </li>
        ))}
      </ul>
    </Card>
  );
}
