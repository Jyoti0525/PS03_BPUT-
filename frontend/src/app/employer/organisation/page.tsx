"use client";

import { usePrefs } from "@/components/providers";
import { useState } from "react";
import { BadgeCheck, Landmark } from "lucide-react";
import { PageHeader } from "@/components/layout/app-shell";
import { api, ApiError } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { Badge, Button, Card, CardHeader, ErrorNote, FieldError, Input, Label, Spinner } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import type { Organisation } from "@/lib/types";

const KIND: Record<string, string> = { company: "Company / factory", industrial: "Industrial estate / unit", campus: "College / school campus", ngo: "NGO / health camp organiser", government_programme: "Government programme" };

export default function OrganisationPage() {
  const { data, error, loading, reload } = useAsync(() => api.myOrganisation(), []);
  if (error) return <ErrorNote error={error} onRetry={reload} />;
  if (loading && !data) return <Spinner />;
  return <OrganisationForm key={data!.organisation.id} o={data!.organisation} onSaved={reload} />;
}

function OrganisationForm({ o, onSaved }: { o: Organisation; onSaved: () => void }) {
  const { tr } = usePrefs();
  const [form, setForm] = useState({ name: o.name, registration_no: o.registration_no ?? "", address: o.address ?? "", contact_phone: o.contact_phone ?? "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function save() {
    setErr(null);
    if (form.name.trim().length < 3) return setErr(tr("Organisation name is required"));
    if (form.contact_phone && !/^\d{10}$/.test(form.contact_phone)) return setErr(tr("Contact phone must be 10 digits"));
    setBusy(true);
    try {
      await api.updateOrganisation({ name: form.name.trim(), registration_no: form.registration_no || null, address: form.address || null, contact_phone: form.contact_phone || null });
      toast(tr("Organisation updated"));
      onSaved();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : tr("Could not save"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title={tr("Organisation")} subtitle={tr("Your organisation’s public profile on Jeevia.")} />
      <Card>
        <CardHeader
          title={o.name}
          subtitle={`${KIND[o.kind] ?? o.kind} · ${o.district}, ${o.state}`}
          icon={<Landmark className="size-4" />}
          action={o.verified ? <Badge tone="teal"><BadgeCheck className="size-3" /> {tr("Verified")}</Badge> : <Badge tone="semi">{tr("Self-registered")}</Badge>}
        />
        <div className="grid gap-4 p-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <Label htmlFor="o-name">{tr("Name")}</Label>
            <Input id="o-name" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </div>
          <div>
            <Label htmlFor="o-reg" hint={tr("(CIN / registration)")}>{tr("Registration no.")}</Label>
            <Input id="o-reg" value={form.registration_no} onChange={(e) => setForm({ ...form, registration_no: e.target.value })} />
          </div>
          <div>
            <Label htmlFor="o-phone">{tr("Contact phone")}</Label>
            <Input id="o-phone" inputMode="numeric" value={form.contact_phone} onChange={(e) => setForm({ ...form, contact_phone: e.target.value.replace(/\D/g, "").slice(0, 10) })} />
          </div>
          <div className="sm:col-span-2">
            <Label htmlFor="o-addr">{tr("Address")}</Label>
            <Input id="o-addr" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          </div>
          <div className="sm:col-span-2">
            <FieldError>{err}</FieldError>
            <Button onClick={save} loading={busy}>{tr("Save changes")}</Button>
          </div>
        </div>
      </Card>
    </div>
  );
}
