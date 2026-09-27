"use client";

import { useState } from "react";
import { Building2, MapPin, Plus } from "lucide-react";
import { PageHeader } from "@/components/layout/app-shell";
import { api, ApiError } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { Badge, Button, Card, ErrorNote, FieldError, Input, Label, Modal, Select, Spinner } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import type { FacilityType, NewFacilityInput } from "@/lib/types";
import { INDIAN_STATES } from "@/lib/india";

const TYPES: { v: FacilityType; label: string }[] = [
  { v: "company_clinic", label: "Company clinic / OHC" },
  { v: "industrial_unit", label: "Industrial unit health centre" },
  { v: "campus", label: "Campus health centre" },
  { v: "health_camp", label: "Health camp" },
];
const label = (t: FacilityType) => TYPES.find((x) => x.v === t)?.label ?? t.replace(/_/g, " ");

export default function WorkplacesPage() {
  const { data, error, loading, reload } = useAsync(() => api.myOrganisation(), []);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<NewFacilityInput>({ name: "", type: "company_clinic", district: "", state: "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const start = () => {
    setErr(null);
    setForm({ name: "", type: "company_clinic", district: data?.organisation.district ?? "", state: data?.organisation.state ?? "" });
    setOpen(true);
  };

  async function save() {
    setErr(null);
    if (form.name.trim().length < 3 || form.district.trim().length < 2 || form.state.trim().length < 2) return setErr("Enter the name, district and state");
    setBusy(true);
    try {
      await api.addOrganisationFacility({ ...form, name: form.name.trim(), pincode: form.pincode || null });
      toast(`${form.name} is now listed — staff can select it when they sign up`);
      setOpen(false);
      reload();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not add workplace");
    } finally {
      setBusy(false);
    }
  }

  if (error) return <ErrorNote error={error} onRetry={reload} />;
  if (loading && !data) return <Spinner />;
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="Workplaces"
        subtitle="Health centres run by your organisation. Each one appears in Jeevia’s workplace search so doctors and nurses can join it."
        actions={
          <Button icon={<Plus className="size-4" />} onClick={start}>
            Add workplace
          </Button>
        }
      />
      <div className="grid gap-3 sm:grid-cols-2">
        {data?.facilities.map((f) => (
          <Card key={f.id} className="p-4">
            <div className="flex items-start gap-3">
              <span className="grid size-10 shrink-0 place-items-center rounded-xl bg-coral-50 text-coral-600">
                <Building2 className="size-5" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-ink">{f.name}</p>
                <p className="text-xs text-muted">{label(f.type)}</p>
                <p className="mt-1 flex items-center gap-1 text-xs text-muted">
                  <MapPin className="size-3" /> {f.district}, {f.state}
                  {f.pincode && ` · ${f.pincode}`}
                </p>
              </div>
              <Badge tone="teal">Listed</Badge>
            </div>
          </Card>
        ))}
      </div>
      <p className="mt-4 text-xs text-muted">Doctors, nurses and receptionists join a workplace by searching for it at sign-up. Their supervisor can then create kiosk links for walk-in intake.</p>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="Add a workplace"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={save} loading={busy}>Add workplace</Button>
          </>
        }
      >
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Label htmlFor="wp-name">Name</Label>
            <Input id="wp-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="e.g. Plant 2 First-aid Centre" />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="wp-type">Type</Label>
            <Select id="wp-type" value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value as FacilityType })}>
              {TYPES.map((t) => (
                <option key={t.v} value={t.v}>{t.label}</option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="wp-dist">District</Label>
            <Input id="wp-dist" value={form.district} onChange={(e) => setForm({ ...form, district: e.target.value })} />
          </div>
          <div>
            <Label htmlFor="wp-state">State</Label>
            <Select id="wp-state" value={form.state} onChange={(e) => setForm({ ...form, state: e.target.value })}>
              <option value="">Select</option>
              {INDIAN_STATES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="wp-pin" hint="(optional)">PIN code</Label>
            <Input id="wp-pin" inputMode="numeric" value={form.pincode ?? ""} onChange={(e) => setForm({ ...form, pincode: e.target.value.replace(/\D/g, "").slice(0, 6) })} />
          </div>
          <div>
            <Label htmlFor="wp-addr" hint="(optional)">Address</Label>
            <Input id="wp-addr" value={form.address ?? ""} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          </div>
        </div>
        <FieldError>{err}</FieldError>
      </Modal>
    </div>
  );
}
