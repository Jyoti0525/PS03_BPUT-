"use client";

import { useState } from "react";
import { api, ApiError } from "@/lib/api";
import { Button, FieldError, Input, Label, Modal, Select } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { LANGUAGES } from "@/lib/i18n/languages";
import type { Patient } from "@/lib/types";

type Editable = Pick<Patient, "name" | "age" | "sex" | "phone" | "language" | "village">;

/** Correct a patient's registration details (typos at intake). The audit log records which fields changed. */
export function PatientEditModal({ patient, onClose, onDone }: { patient: Editable & { id: string }; onClose: () => void; onDone: (p: Patient) => void }) {
  const [f, setF] = useState<Editable>({ name: patient.name, age: patient.age, sex: patient.sex, phone: patient.phone ?? "", language: patient.language, village: patient.village ?? "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    setErr(null);
    if (f.name.trim().length < 2) return setErr("Enter the patient’s name");
    if (!(f.age >= 0 && f.age <= 120)) return setErr("Age must be between 0 and 120");
    if (f.phone && !/^\d{10}$/.test(f.phone)) return setErr("Phone must be 10 digits");
    const patch: Partial<Editable> = {};
    (Object.keys(f) as (keyof Editable)[]).forEach((k) => {
      const v = k === "phone" || k === "village" ? f[k] || null : k === "name" ? f.name.trim() : f[k];
      if (v !== ((patient[k] as unknown) ?? (k === "phone" || k === "village" ? null : undefined))) (patch as Record<string, unknown>)[k] = v;
    });
    if (!Object.keys(patch).length) return onClose();
    setBusy(true);
    try {
      const p = await api.correctPatient(patient.id, patch);
      toast("Patient details corrected — change recorded in the audit log");
      onDone(p);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not save");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title="Edit patient details"
      subtitle="Fix registration mistakes. Clinical notes are not changed here."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={save} loading={busy}>Save correction</Button>
        </>
      }
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <Label htmlFor="pe-name">Name</Label>
          <Input id="pe-name" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
        </div>
        <div>
          <Label htmlFor="pe-age">Age</Label>
          <Input id="pe-age" type="number" min={0} max={120} value={f.age} onChange={(e) => setF({ ...f, age: Number(e.target.value) })} />
        </div>
        <div>
          <Label htmlFor="pe-sex">Sex</Label>
          <Select id="pe-sex" value={f.sex} onChange={(e) => setF({ ...f, sex: e.target.value as Patient["sex"] })}>
            <option value="F">Female</option>
            <option value="M">Male</option>
            <option value="O">Other</option>
          </Select>
        </div>
        <div>
          <Label htmlFor="pe-phone" hint="(optional)">Mobile</Label>
          <Input id="pe-phone" inputMode="numeric" value={f.phone ?? ""} onChange={(e) => setF({ ...f, phone: e.target.value.replace(/\D/g, "").slice(0, 10) })} />
        </div>
        <div>
          <Label htmlFor="pe-lang">Language</Label>
          <Select id="pe-lang" value={f.language} onChange={(e) => setF({ ...f, language: e.target.value })}>
            {LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>{l.name}</option>
            ))}
          </Select>
        </div>
        <div className="sm:col-span-2">
          <Label htmlFor="pe-village" hint="(optional)">Village / locality</Label>
          <Input id="pe-village" value={f.village ?? ""} onChange={(e) => setF({ ...f, village: e.target.value })} />
        </div>
      </div>
      <FieldError>{err}</FieldError>
    </Modal>
  );
}
