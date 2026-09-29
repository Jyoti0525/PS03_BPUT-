"use client";

import { useState } from "react";
import { fmtDateTime } from "@/lib/hooks";
import { Activity, ClipboardPen, NotebookPen } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Badge, Button, Card, CardHeader, FieldError, Input, Label, Textarea } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { usePrefs } from "@/components/providers";
import type { Encounter, Observation, VitalsInput } from "@/lib/types";

type Field = { key: keyof VitalsInput; label: string; unit: string; min: number; max: number; step?: number };

const FIELDS: Field[] = [
  { key: "bp_systolic", label: "BP systolic", unit: "mmHg", min: 50, max: 260 },
  { key: "bp_diastolic", label: "BP diastolic", unit: "mmHg", min: 30, max: 160 },
  { key: "pulse", label: "Pulse", unit: "bpm", min: 20, max: 250 },
  { key: "spo2", label: "SpO₂", unit: "%", min: 50, max: 100 },
  { key: "temp_f", label: "Temperature", unit: "°F", min: 90, max: 110, step: 0.1 },
  { key: "resp_rate", label: "Resp. rate", unit: "/min", min: 4, max: 80 },
  { key: "glucose", label: "Glucose (POC)", unit: "mg/dL", min: 20, max: 600 },
];

const VITAL_LABEL: Record<string, string> = Object.fromEntries(FIELDS.map((f) => [f.key, f.label]));

/** Record vitals and bedside observations. Rules run again on the server, so urgency can rise. */
export function ObservationForm({ enc, onSaved, compact }: { enc: Encounter; onSaved: (e: Encounter) => void; compact?: boolean }) {
  const { tr } = usePrefs();
  const [v, setV] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
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
    if (!Object.keys(vitals).length && !note.trim()) return setErr(tr("Enter at least one vital sign or an observation"));
    setBusy(true);
    try {
      const before = enc.urgency;
      const e = await api.addObservations(enc.id, { vitals, note: note.trim() || null });
      setV({});
      setNote("");
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
            {o.note && <p className="mt-1 text-ink-2">{o.note}</p>}
          </li>
        ))}
      </ul>
    </Card>
  );
}
