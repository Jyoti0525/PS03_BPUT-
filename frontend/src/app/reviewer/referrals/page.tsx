"use client";

import { usePrefs } from "@/components/providers";
import Link from "next/link";
import { useState } from "react";
import { Send, Ambulance, Car, Footprints } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync, timeAgo } from "@/lib/hooks";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Button, Card, Empty, ErrorNote, FieldError, Input, Label, Modal, Spinner } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import type { Referral } from "@/lib/types";

const TRANSPORT = {
  ambulance_108: { label: "108 ambulance", icon: <Ambulance className="size-3" /> },
  facility_vehicle: { label: "Facility vehicle", icon: <Car className="size-3" /> },
  self: { label: "Self / family", icon: <Footprints className="size-3" /> },
};

export default function ReferralsPage() {
  const { tr } = usePrefs();
  const { data, error, loading, reload } = useAsync(() => api.listReferrals(), []);
  const [view, setView] = useState<Referral | null>(null);
  const [confirm, setConfirm] = useState<Referral | null>(null);
  const overdue = data?.filter((r) => r.overdue).length ?? 0;
  // E4: overdue first, then open, then received.
  const rows = [...(data ?? [])].sort((a, b) => Number(!!b.overdue) - Number(!!a.overdue) || Number(a.status === "received") - Number(b.status === "received"));
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title={tr("Referrals")} subtitle={tr("Referral notes prepared from triage notes. Destinations follow the facility's specialist configuration.")} />
      {error ? <ErrorNote error={error} onRetry={reload} /> : loading && !data ? <Spinner /> : !data?.length ? (
        <Card><Empty icon={<Send className="size-6" />} title={tr("No referrals yet")} body={tr("Open a case and choose “Referral note” to prepare one.")} /></Card>
      ) : (
        <Card>
          {overdue > 0 && (
            <p className="border-b border-line bg-crit-bg px-4 py-2.5 text-sm font-semibold text-crit">
              {tr("{n} referral(s) past due and not confirmed received — check that the patient reached care.", { n: overdue })}
            </p>
          )}
          <ul className="divide-y divide-line">
            {rows.map((r) => (
              <li key={r.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-ink">
                    <Link href={`/reviewer/case/${r.encounter_id}`} className="hover:underline">{r.patient_name}</Link> <span className="font-normal text-muted">→ {r.destination}</span>
                  </p>
                  <p className="text-sm text-muted">{tr(r.specialty)} · {tr(r.reason)}</p>
                  <p className="text-xs text-subtle">{tr("by")} {r.created_by} · {timeAgo(r.created_at)}</p>
                  {r.status === "received" ? (
                    <p className="text-xs text-subtle">{tr("Care received — confirmed by {who}", { who: r.received_by ?? "" })} · {r.received_at ? timeAgo(r.received_at) : ""}</p>
                  ) : r.due_at ? (
                    <p className="text-xs text-subtle">{tr(r.overdue ? "Was due {when}" : "Confirm by {when}", { when: timeAgo(r.due_at) })}</p>
                  ) : null}
                </div>
                <Badge>{TRANSPORT[r.transport].icon} {tr(TRANSPORT[r.transport].label)}</Badge>
                <Badge tone={r.status === "received" ? "teal" : r.overdue ? "crit" : "neutral"}>{tr(r.status === "received" ? "Care received" : r.overdue ? "Overdue" : "Open")}</Badge>
                {r.status !== "received" && <button className="text-sm font-semibold text-teal-700 hover:underline" onClick={() => setConfirm(r)}>{tr("Confirm received")}</button>}
                <button className="text-sm font-semibold text-teal-700 hover:underline" onClick={() => setView(r)}>{tr("View note")}</button>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {confirm && <ReceivedModal r={confirm} onClose={() => setConfirm(null)} onDone={() => { setConfirm(null); reload(); }} />}
      <Modal open={!!view} onClose={() => setView(null)} title={tr("Referral — {name}", { name: view?.patient_name ?? "" })} size="lg">
        <pre className="font-mono text-[13px] whitespace-pre-wrap text-ink">{tr(view?.note_text)}</pre>
      </Modal>
    </div>
  );
}

/** E4: the referring doctor records that care was received, for example after phoning the destination. */
function ReceivedModal({ r, onClose, onDone }: { r: Referral; onClose: () => void; onDone: () => void }) {
  const { tr } = usePrefs();
  const [who, setWho] = useState("");
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    if (who.trim().length < 3) return setErr(tr("Who confirmed it? (name, role, place)"));
    setBusy(true);
    try {
      await api.referralReceived(r.id, who, note);
      toast(tr("Referral closed — care received"));
      onDone();
    } catch (e) {
      setErr(e instanceof Error ? e.message : tr("Failed"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      open
      onClose={onClose}
      title={tr("Confirm care received")}
      subtitle={tr("Close the referral only when the destination confirms the patient was seen. The receiving clinician can also confirm from the QR summary.")}
      footer={<><Button variant="secondary" onClick={onClose}>{tr("Cancel")}</Button><Button variant="teal" loading={busy} onClick={submit}>{tr("Close referral")}</Button></>}
    >
      <p className="text-sm text-muted">{r.patient_name} → {r.destination}</p>
      <div className="mt-3">
        <Label htmlFor="rc-who">{tr("Confirmed by")}</Label>
        <Input id="rc-who" value={who} onChange={(e) => setWho(e.target.value)} placeholder={tr("e.g. Dr Rao, casualty, District Hospital (phone)")} />
      </div>
      <div className="mt-3">
        <Label htmlFor="rc-note">{tr("Note (optional)")}</Label>
        <Input id="rc-note" value={note} onChange={(e) => setNote(e.target.value)} />
      </div>
      <FieldError>{err}</FieldError>
    </Modal>
  );
}
