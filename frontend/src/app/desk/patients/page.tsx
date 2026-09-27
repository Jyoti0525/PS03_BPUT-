"use client";

import Link from "next/link";
import { useState } from "react";
import { Pencil, Search, Tablet, UserRound } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { timeAgo } from "@/lib/hooks";
import { usePrefs } from "@/components/providers";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Button, Card, Empty, Input } from "@/components/ui";
import { PatientEditModal } from "@/components/triage/patient-edit";
import { langByCode } from "@/lib/i18n/languages";
import type { Patient, PatientCandidate } from "@/lib/types";

/** Front desk: find a returning patient (phone, patient ID or name), correct their details, or register a new one. */
export default function DeskPatients() {
  const { tr } = usePrefs();
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<PatientCandidate[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [editing, setEditing] = useState<Patient | null>(null);

  async function search() {
    setErr(null);
    const term = q.trim();
    if (term.length < 3) return setErr(tr("Type at least 3 characters"));
    setBusy(true);
    try {
      setRows(/^jva-/i.test(term) ? [{ patient: await api.getPatientByCode(term.toUpperCase()), last_visit_at: null, match_reason: tr("Patient ID") }] : await api.searchPatients(term));
    } catch (e) {
      setRows([]);
      if (!(e instanceof ApiError && e.status === 404)) setErr(e instanceof Error ? e.message : tr("Search failed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title={tr("Find & register patients")}
        subtitle={tr("Search by mobile number, patient ID (JVA-…) or name.")}
        actions={
          <Link href="/kiosk">
            <Button icon={<Tablet className="size-4" />}>{tr("Register new patient")}</Button>
          </Link>
        }
      />
      <Card className="p-4">
        <form
          className="flex gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            search();
          }}
        >
          <div className="relative flex-1">
            <Search className="absolute top-3.5 left-3 size-4 text-subtle" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={tr("98765 43210 · JVA-P012 · Radha")} className="pl-9" aria-label={tr("Search patients")} />
          </div>
          <Button type="submit" loading={busy}>
            {tr("Search")}
          </Button>
        </form>
        {err && <p className="mt-2 text-sm text-crit">{err}</p>}
      </Card>
      {rows && (
        <Card className="mt-4">
          {!rows.length ? (
            <Empty icon={<UserRound className="size-6" />} title={tr("No patient found")} body={tr("Register them through the check-in kiosk.")} />
          ) : (
            <ul className="divide-y divide-line">
              {rows.map(({ patient: p, last_visit_at, match_reason }) => (
                <li key={p.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                  <span className="grid size-10 place-items-center rounded-full bg-coral-50 font-bold text-coral-700">{p.name.charAt(0)}</span>
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-ink">{p.name}</p>
                    <p className="text-xs text-muted">
                      <span className="font-mono">{p.code}</span> · {p.age} · {p.sex} · {langByCode(p.language).name}
                      {p.phone && ` · +91 ${p.phone.slice(0, 5)}•••••`}
                      {last_visit_at && ` · ${tr("last visit")} ${timeAgo(last_visit_at)}`}
                    </p>
                  </div>
                  <Badge>{match_reason}</Badge>
                  <Button size="sm" variant="secondary" icon={<Pencil className="size-4" />} onClick={() => setEditing(p)}>
                    {tr("Edit details")}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </Card>
      )}
      {editing && (
        <PatientEditModal
          patient={editing}
          onClose={() => setEditing(null)}
          onDone={(p) => {
            setEditing(null);
            setRows((r) => r?.map((x) => (x.patient.id === p.id ? { ...x, patient: p } : x)) ?? null);
          }}
        />
      )}
    </div>
  );
}
