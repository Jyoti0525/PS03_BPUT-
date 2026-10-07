"use client";

import { useState } from "react";
import { Save, Building2, ClipboardCheck, Stethoscope, Route, Plus, Trash2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { useSession, usePrefs } from "@/components/providers";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Button, Card, CardHeader, ErrorNote, Input, Label, Select, Spinner, Toggle, cx } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import type { Facility, FacilityType } from "@/lib/types";
import { LANGUAGES } from "@/lib/i18n/languages";

const TYPES: { v: FacilityType; label: string; hint: string }[] = [
  { v: "phc", label: "Primary Health Centre", hint: "Limited specialists; referral to district hospital is the default." },
  { v: "chc", label: "Community Health Centre", hint: "Some specialists; first referral unit for PHCs." },
  { v: "district_hospital", label: "District / Government Hospital", hint: "Full specialist suite; escalation mostly within the facility." },
  { v: "health_camp", label: "Public Health Camp", hint: "Offline-first, screening-level triage, no beds." },
  { v: "company_clinic", label: "Company Clinic", hint: "Occupational health; employer sees fitness status only." },
  { v: "industrial_unit", label: "Industrial Estate Health Unit", hint: "Trauma, burns and occupational pathways." },
  { v: "campus", label: "Campus Health Centre", hint: "Student population; fever and mental-health pathways." },
];

const QUESTIONS: { key: string; q: string }[] = [
  { key: "lab", q: "Is a basic lab (CBC, sugar, urine) available on site?" },
  { key: "ecg", q: "Can a 12-lead ECG be recorded here?" },
  { key: "xray", q: "Is X-ray available?" },
  { key: "oxygen", q: "Is oxygen available?" },
  { key: "labour_room", q: "Is there a labour room?" },
  { key: "icu", q: "Is there an ICU / HDU bed?" },
  { key: "ambulance", q: "Is an ambulance (108 / own) reachable?" },
  { key: "pharmacy", q: "Is there a pharmacy / dispensary?" },
];

export default function FacilitySetup() {
  const { user } = useSession();
  const fid = user!.facility_id!;
  const { data, error, reload } = useAsync(() => api.getFacility(fid), [fid]);
  if (error) return <ErrorNote error={error} onRetry={reload} />;
  if (!data) return <Spinner />;
  // Re-key on the saved version so the form restarts from server state after each save.
  return <FacilityForm key={JSON.stringify(data)} data={data} onSaved={reload} />;
}

function FacilityForm({ data, onSaved }: { data: Facility; onSaved: () => void }) {
  const { tr } = usePrefs();
  const [f, setF] = useState<Facility>(data);
  const [saving, setSaving] = useState(false);
  const [newSpec, setNewSpec] = useState("");
  const dirty = JSON.stringify(f) !== JSON.stringify(data);

  const save = async () => {
    setSaving(true);
    try {
      await api.updateFacility(f.id, f);
      onSaved();
      toast(tr("Facility configuration saved — referral routing updated"));
    } catch (e) {
      toast(e instanceof Error ? e.message : tr("Save failed"), "error");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl pb-20">
      <PageHeader
        title={tr("Facility setup")}
        subtitle={tr("What kind of facility is this, and who is available today? Referral notes use this configuration.")}
        actions={<Button onClick={save} loading={saving} disabled={!dirty} variant="teal" icon={<Save className="size-4" />}>{tr("Save changes")}</Button>}
      />

      <Card>
        <CardHeader title={tr("1 · What type of facility is it?")} icon={<Building2 className="size-4" />} />
        <div className="grid gap-2 p-4 sm:grid-cols-2 lg:grid-cols-3">
          {TYPES.map((t) => (
            <button key={t.v} onClick={() => setF({ ...f, type: t.v, offline_mode: t.v === "health_camp" ? true : f.offline_mode })} aria-pressed={f.type === t.v} className={cx("rounded-xl border-2 p-3 text-left", f.type === t.v ? "border-teal-600 bg-teal-50" : "border-line hover:bg-canvas")}>
              <p className="font-semibold text-ink">{tr(t.label)}</p>
              <p className="mt-0.5 text-xs text-muted">{tr(t.hint)}</p>
            </button>
          ))}
        </div>
        <div className="grid gap-4 border-t border-line p-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="sm:col-span-2">
            <Label htmlFor="f-name">{tr("Facility name")}</Label>
            <Input id="f-name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
          </div>
          <div>
            <Label htmlFor="f-dist">{tr("District")}</Label>
            <Input id="f-dist" value={f.district} onChange={(e) => setF({ ...f, district: e.target.value })} />
          </div>
          <div>
            <Label htmlFor="f-state">{tr("State")}</Label>
            <Input id="f-state" value={f.state} onChange={(e) => setF({ ...f, state: e.target.value })} />
          </div>
          <div>
            <Label htmlFor="f-beds">{tr("Beds")}</Label>
            <Input id="f-beds" inputMode="numeric" value={f.beds_total} onChange={(e) => setF({ ...f, beds_total: Number(e.target.value.replace(/\D/g, "")) || 0 })} />
          </div>
          <div>
            <Label htmlFor="f-occ">{tr("Occupied")}</Label>
            <Input id="f-occ" inputMode="numeric" value={f.beds_occupied} onChange={(e) => setF({ ...f, beds_occupied: Number(e.target.value.replace(/\D/g, "")) || 0 })} />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="f-load" hint={tr("High: the kiosk asks only the safety questions")}>{tr("Patient load")}</Label>
            <Select id="f-load" value={f.patient_load ?? "normal"} onChange={(e) => setF({ ...f, patient_load: e.target.value as "low" | "normal" | "high" })}>
              <option value="low">{tr("Low — ask every follow-up question")}</option>
              <option value="normal">{tr("Normal — up to 7 questions, safety first")}</option>
              <option value="high">{tr("High — safety questions only")}</option>
            </Select>
          </div>
          <div className="flex items-end sm:col-span-2">
            <div className="w-full rounded-xl border border-line p-3">
              <Toggle checked={f.offline_mode} onChange={(v) => setF({ ...f, offline_mode: v })} label={tr("Offline-first kiosks")} description={tr("Queue intakes locally when the network drops")} />
            </div>
          </div>
        </div>
      </Card>

      <Card className="mt-4">
        <CardHeader title={tr("2 · What is available here?")} subtitle={tr("Used to decide what the reviewer can do on site vs. refer")} icon={<ClipboardCheck className="size-4" />} />
        <div className="grid gap-x-8 gap-y-4 p-4 sm:grid-cols-2">
          {QUESTIONS.map((q) => (
            <Toggle key={q.key} checked={!!f.capabilities[q.key]} onChange={(v) => setF({ ...f, capabilities: { ...f.capabilities, [q.key]: v } })} label={q.q} />
          ))}
        </div>
      </Card>

      <Card className="mt-4">
        <CardHeader title={tr("3 · Specialists on duty")} subtitle={tr("Toggle as staff arrive or leave — takes effect immediately for new referrals")} icon={<Stethoscope className="size-4" />} />
        <ul className="divide-y divide-line">
          {f.specialists.map((s, i) => (
            <li key={s.key} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <span className={cx("size-2.5 rounded-full", s.available ? "bg-rout" : "bg-line")} />
              <span className="min-w-40 flex-1 font-medium text-ink">{tr(s.label)}</span>
              <Input value={s.schedule ?? ""} onChange={(e) => { const sp = [...f.specialists]; sp[i] = { ...s, schedule: e.target.value || null }; setF({ ...f, specialists: sp }); }} placeholder={tr("Schedule e.g. Visiting Thu")} className="h-9 w-48 text-sm" aria-label={`${s.label} schedule`} />
              <Toggle checked={s.available} onChange={(v) => { const sp = [...f.specialists]; sp[i] = { ...s, available: v }; setF({ ...f, specialists: sp }); }} label={<span className="w-20 text-xs text-muted">{s.available ? tr("On site") : tr("Not on site")}</span>} />
              <button onClick={() => setF({ ...f, specialists: f.specialists.filter((_, j) => j !== i) })} className="text-subtle hover:text-crit" aria-label={`Remove ${s.label}`}><Trash2 className="size-4" /></button>
            </li>
          ))}
        </ul>
        <div className="flex gap-2 border-t border-line p-3">
          <Input value={newSpec} onChange={(e) => setNewSpec(e.target.value)} placeholder={tr("Add specialty (e.g. Dermatology)")} className="h-10" />
          <Button variant="secondary" icon={<Plus className="size-4" />} onClick={() => { if (!newSpec.trim()) return; setF({ ...f, specialists: [...f.specialists, { key: newSpec.trim().toLowerCase().replace(/\W+/g, "_"), label: newSpec.trim(), available: true, schedule: null }] }); setNewSpec(""); }}>{tr("Add")}</Button>
        </div>
      </Card>

      <Card className="mt-4">
        <CardHeader title={tr("4 · Referral & languages")} icon={<Route className="size-4" />} />
        <div className="space-y-4 p-4">
          <div>
            <Label htmlFor="f-ref">{tr("Default referral destination")}</Label>
            <Input id="f-ref" value={f.referral_destination} onChange={(e) => setF({ ...f, referral_destination: e.target.value })} />
          </div>
          <div>
            <Label>{tr("Routing preview")}</Label>
            <div className="flex flex-wrap gap-2">
              {f.specialists.map((s) => (
                <Badge key={s.key} tone={s.available ? "rout" : "semi"}>
                  {tr(s.label)} → {s.available ? tr("treat on site") : f.referral_destination.split("(")[0].trim()}
                </Badge>
              ))}
            </div>
          </div>
          <div>
            <Label>{tr("Kiosk languages offered")}</Label>
            <div className="flex flex-wrap gap-1.5">
              {LANGUAGES.map((l) => {
                const on = f.languages.includes(l.code);
                return (
                  <button key={l.code} onClick={() => setF({ ...f, languages: on ? f.languages.filter((x) => x !== l.code) : [...f.languages, l.code] })} aria-pressed={on} className={cx("rounded-full border px-2.5 py-1 text-xs font-medium", on ? "border-teal-600 bg-teal-50 text-teal-800" : "border-line text-muted")}>
                    {l.native}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      </Card>

      {dirty && (
        <div className="fixed inset-x-0 bottom-4 z-30 flex justify-center px-4">
          <div className="flex items-center gap-3 rounded-2xl border border-line bg-ink px-4 py-2.5 text-white shadow-[var(--shadow-pop)]">
            <span className="text-sm">{tr("Unsaved changes")}</span>
            <Button size="sm" variant="secondary" onClick={() => setF(data)}>{tr("Discard")}</Button>
            <Button size="sm" variant="teal" loading={saving} onClick={save}>{tr("Save")}</Button>
          </div>
        </div>
      )}
    </div>
  );
}
