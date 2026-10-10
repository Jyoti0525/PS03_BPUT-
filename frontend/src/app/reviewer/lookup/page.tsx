"use client";

import Link from "next/link";
import { useState } from "react";
import { ScanLine, Search, Phone, ArrowRight } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Button, Card, CardHeader, Empty, ErrorNote, Input, Spinner } from "@/components/ui";
import type { Encounter, Patient, PatientCandidate } from "@/lib/types";
import { UrgencyBadge } from "@/components/triage/note";
import { QrScanner } from "@/components/triage/qr-scanner";
import { timeAgo, fmtDate } from "@/lib/hooks";
import { langByCode } from "@/lib/i18n/languages";
import { useSession, usePrefs } from "@/components/providers";

export default function LookupPage() {
  const { tr } = usePrefs();
  const { user } = useSession();
  const caseBase = user?.role === "nurse" ? "/nurse/patient" : "/reviewer/case";
  const [q, setQ] = useState("");
  const [scan, setScan] = useState(false);
  const [candidates, setCandidates] = useState<PatientCandidate[] | null>(null);
  const [patient, setPatient] = useState<Patient | null>(null);
  const [history, setHistory] = useState<Encounter[] | null>(null);
  const [err, setErr] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  const open = async (p: Patient) => {
    setPatient(p);
    setHistory(null);
    try {
      setHistory(await api.patientEncounters(p.id));
    } catch (e) {
      setErr(e);
    }
  };

  const search = async (value = q) => {
    const v = value.trim();
    if (!v) return;
    setErr(null);
    setPatient(null);
    setBusy(true);
    try {
      let code = v;
      try {
        const url = new URL(code);
        code = url.searchParams.get("claim") ?? url.searchParams.get("patient") ?? code;
      } catch { /* QR payloads can be plain IDs, not URLs */ }
      code = code.replace(/^jeevia:/i, "").trim();
      if (/^jva-/i.test(code)) {
        await open(await api.getPatientByCode(code));
        setCandidates(null);
      } else if (/^j-/i.test(code)) {
        await open(await api.getPatientByReference(code));
        setCandidates(null);
      } else {
        const c = await api.searchPatients(v);
        setCandidates(c);
        if (c.length === 1) await open(c[0].patient);
      }
    } catch (e) {
      setErr(e instanceof ApiError && e.status === 404 ? new Error(`No patient found for “${v}”`) : e);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title={tr("Find patient")} subtitle={tr("By patient ID, QR or J- form reference, or phone. Every lookup is written to the audit log.")} />
      <Card className="p-4">
        <form className="flex flex-col gap-2 sm:flex-row" onSubmit={(e) => { e.preventDefault(); search(); }}>
          <div className="relative flex-1">
            <Search className="absolute top-3.5 left-3 size-4 text-subtle" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={tr("JVA-P001, J-2XJFND, phone, or name")} className="h-12 pl-9 text-base" aria-label={tr("Patient ID, phone or name")} />
          </div>
          <Button type="submit" size="lg" loading={busy}>{tr("Search")}</Button>
          <Button type="button" size="lg" variant="secondary" onClick={() => setScan(true)} icon={<ScanLine className="size-5" />}>{tr("Scan QR")}</Button>
        </form>
        <div className="mt-3 flex flex-wrap gap-2 text-xs">
          <span className="text-muted">{tr("Try:")}</span>
          {["JVA-P003", "9876543210", "Lakshmi"].map((s) => (
            <button key={s} className="rounded-full bg-canvas px-2.5 py-1 font-medium text-ink-2 hover:bg-line" onClick={() => { setQ(s); search(s); }}>{s}</button>
          ))}
        </div>
      </Card>

      {scan && (
        <div className="mt-4">
          <QrScanner onClose={() => setScan(false)} onCode={(c) => { setScan(false); setQ(c); search(c); }} />
        </div>
      )}

      {!!err && <div className="mt-4"><ErrorNote error={err} /></div>}

      {candidates && candidates.length > 1 && !patient && (
        <Card className="mt-4">
          <CardHeader title={tr("{n} people match", { n: candidates.length })} subtitle={tr("Phones are often shared within a household — confirm identity before opening a record.")} icon={<Phone className="size-4" />} />
          <ul className="divide-y divide-line">
            {candidates.map((c) => (
              <li key={c.patient.id}>
                <button onClick={() => open(c.patient)} className="flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-canvas">
                  <span className="grid size-10 place-items-center rounded-xl bg-coral-100 font-bold text-coral-700">{c.patient.name.charAt(0)}</span>
                  <span className="min-w-0 flex-1">
                    <span className="block font-semibold text-ink">{c.patient.name} <span className="font-normal text-muted">· {c.patient.age}{c.patient.sex}</span></span>
                    <span className="block text-xs text-muted">{c.patient.code} · {c.patient.village ?? "—"} {tr("· last visit")} {c.last_visit_at ? timeAgo(c.last_visit_at) : tr("never")}</span>
                  </span>
                  <Badge tone={c.match_reason.startsWith("Shared") ? "semi" : "neutral"}>{c.match_reason}</Badge>
                </button>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {candidates && candidates.length === 0 && <Card className="mt-4"><Empty title={tr("No matching patients")} body={tr("Register them at the kiosk to start an intake.")} /></Card>}

      {patient && (
        <Card className="mt-4">
          <div className="flex flex-wrap items-center gap-4 p-4">
            <span className="grid size-14 place-items-center rounded-2xl bg-coral-100 text-xl font-bold text-coral-700">{patient.name.charAt(0)}</span>
            <div className="flex-1">
              <p className="text-lg font-bold text-ink">{patient.name}</p>
              <p className="text-sm text-muted">{patient.age} y · {patient.sex} · <span className="font-mono">{patient.code}</span> · {tr(langByCode(patient.language).name)} · {tr(patient.category)}</p>
            </div>
          </div>
          <div className="border-t border-line">
            <p className="px-4 pt-3 text-xs font-semibold tracking-wide text-muted uppercase">{tr("Encounters")}</p>
            {!history ? <Spinner /> : history.length === 0 ? <p className="px-4 py-3 text-sm text-muted">{tr("No encounters yet.")}</p> : (
              <ul className="divide-y divide-line">
                {history.map((e) => (
                  <li key={e.id}>
                    <Link href={`${caseBase}/${e.id}`} className="flex items-center gap-3 px-4 py-3 hover:bg-canvas">
                      <span className="w-28 shrink-0 text-xs text-muted">{fmtDate(e.created_at)}</span>
                      <span className="min-w-0 flex-1 truncate text-sm text-ink">{tr(e.chief_complaint)}</span>
                      <UrgencyBadge u={e.urgency} size="sm" />
                      <Badge>{e.status}</Badge>
                      <ArrowRight className="size-4 text-subtle" />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </Card>
      )}
    </div>
  );
}
