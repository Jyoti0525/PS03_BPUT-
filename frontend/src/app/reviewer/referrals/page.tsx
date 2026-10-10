"use client";

import { usePrefs, useSession } from "@/components/providers";
import Link from "next/link";
import { useState } from "react";
import { Send, Ambulance, Car, Footprints, Inbox, Search, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync, timeAgo, refCode } from "@/lib/hooks";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Button, Card, Empty, ErrorNote, FieldError, Input, Label, Modal, Segmented, Spinner } from "@/components/ui";
import { UrgencyBadge } from "@/components/triage/note";
import { ReferredVisit } from "@/components/triage/referred-visit";
import { toast } from "@/components/ui/toast";
import type { Referral, SharedSummary } from "@/lib/types";

const TRANSPORT = {
  ambulance_108: { label: "108 ambulance", icon: <Ambulance className="size-3" /> },
  facility_vehicle: { label: "Facility vehicle", icon: <Car className="size-3" /> },
  self: { label: "Self / family", icon: <Footprints className="size-3" /> },
};

export default function ReferralsPage() {
  const { tr } = usePrefs();
  const incoming = useAsync(() => api.incomingReferrals(), []);
  const waiting = incoming.data?.filter((r) => r.status !== "received").length ?? 0;
  const [tab, setTab] = useState<"sent" | "incoming">("sent");
  const [open, setOpen] = useState<Referral | null>(null);
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title={tr("Referrals")} subtitle={tr("Referrals this facility sent, and referrals other facilities sent here. Find any of them by its ID.")} />
      <FindReferral onFound={setOpen} />
      <Segmented
        className="mb-4"
        value={tab}
        onChange={setTab}
        options={[
          { value: "sent", label: tr("Sent") },
          { value: "incoming", label: tr("Incoming"), count: waiting || undefined },
        ]}
      />
      {tab === "sent" ? <SentReferrals onOpen={setOpen} /> : <IncomingReferrals state={incoming} onOpen={setOpen} />}
      {open && <VisitModal r={open} onClose={() => setOpen(null)} onChanged={() => { incoming.reload(); }} />}
    </div>
  );
}

/** Search by the full ID or the short code on the slip (REF-3F9A2C). Only referrals sent to or from this facility. */
function FindReferral({ onFound }: { onFound: (r: Referral) => void }) {
  const { tr } = usePrefs();
  const [q, setQ] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const find = async () => {
    if (q.trim().length < 6) return setErr(tr("Enter the referral ID, e.g. REF-3F9A2C"));
    setBusy(true);
    setErr(null);
    try {
      onFound(await api.findReferral(q));
    } catch (e) {
      setErr(e instanceof Error ? e.message : tr("Not found"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card className="mb-4 p-4">
      <Label htmlFor="rf-find">{tr("Find a referral by ID")}</Label>
      <div className="flex gap-2">
        <Input id="rf-find" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === "Enter" && find()} placeholder="REF-3F9A2C" className="font-mono uppercase" />
        <Button variant="teal" loading={busy} onClick={find} icon={<Search className="size-4" />}>{tr("Find")}</Button>
      </div>
      <FieldError>{err}</FieldError>
    </Card>
  );
}

/** Referrals other facilities sent here: open the visit, then record the arrival. */
function IncomingReferrals({ state, onOpen }: { state: ReturnType<typeof useAsync<Referral[]>>; onOpen: (r: Referral) => void }) {
  const { tr } = usePrefs();
  const { data, error, loading, reload } = state;
  if (error) return <ErrorNote error={error} onRetry={reload} />;
  if (loading && !data) return <Spinner />;
  if (!data?.length) return <Card><Empty icon={<Inbox className="size-6" />} title={tr("No incoming referrals")} body={tr("When another facility refers a patient here, it appears in this list.")} /></Card>;
  const rows = [...data].sort((a, b) => Number(a.status === "received") - Number(b.status === "received"));
  return (
    <Card>
      <ul className="divide-y divide-line">
        {rows.map((r) => (
          <li key={r.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
            <div className="min-w-0 flex-1">
              <p className="flex flex-wrap items-center gap-2 font-semibold text-ink">
                <UrgencyBadge u={r.urgency ?? null} size="sm" /> {r.patient_name}
                <span className="rounded bg-teal-50 px-1.5 py-0.5 font-mono text-xs font-medium text-teal-800">{refCode(r.id)}</span>
              </p>
              <p className="text-sm text-muted">{tr("From")} {r.from_facility_name} · {tr(r.specialty)} · {tr(r.reason)}</p>
              <p className="text-xs text-subtle">{tr("by")} {r.created_by} · {timeAgo(r.created_at)}</p>
              {r.status === "received" && <p className="text-xs text-subtle">{tr("Arrived — recorded by {who}", { who: r.received_by ?? "" })}</p>}
            </div>
            <Badge>{TRANSPORT[r.transport].icon} {tr(TRANSPORT[r.transport].label)}</Badge>
            <Badge tone={r.status === "received" ? "teal" : "coral"}>{tr(r.status === "received" ? "Arrived" : "Expected")}</Badge>
            <Button size="sm" variant="secondary" onClick={() => onOpen(r)}>{tr("Open visit")}</Button>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** The referred visit only. The receiving facility records the arrival here; the sender sees the same view. */
function VisitModal({ r, onClose, onChanged }: { r: Referral; onClose: () => void; onChanged: () => void }) {
  const { tr } = usePrefs();
  const { user } = useSession();
  const visit = useAsync<SharedSummary>(() => api.referralVisit(r.id), [r.id]);
  const [cur, setCur] = useState(r);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const receiving = !!user?.facility_id && cur.to_facility_id === user.facility_id;
  const arrived = async () => {
    setBusy(true);
    try {
      setCur(await api.referralArrived(cur.id, note));
      toast(tr("Arrival recorded — the referring facility sees it now"));
      onChanged();
    } catch (e) {
      toast(e instanceof Error ? e.message : tr("Failed"), "error");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      open
      onClose={onClose}
      size="xl"
      title={`${refCode(cur.id)} · ${cur.patient_name}`}
      subtitle={`${cur.from_facility_name || ""} · ${tr("Suggested destination:")} ${cur.to_facility_name ?? cur.destination}`}
      footer={receiving && cur.status !== "received" ? (
        <>
          <Input value={note} onChange={(e) => setNote(e.target.value)} placeholder={tr("Note (optional), e.g. seen in casualty")} className="max-w-xs" aria-label={tr("Note (optional)")} />
          <Button variant="teal" loading={busy} onClick={arrived} icon={<CheckCircle2 className="size-4" />}>{tr("Patient arrived")}</Button>
        </>
      ) : undefined}
    >
      {cur.status === "received" && (
        <p className="mb-3 rounded-lg bg-rout-bg px-3 py-2 text-sm font-medium text-rout">{tr("Arrived — recorded by {who}", { who: cur.received_by ?? "" })}{cur.received_at ? ` · ${timeAgo(cur.received_at)}` : ""}</p>
      )}
      {visit.error ? <ErrorNote error={visit.error} onRetry={visit.reload} /> : !visit.data ? <Spinner /> : <ReferredVisit data={visit.data} />}
      <p className="mt-3 text-xs text-muted">{tr("This visit only, not the patient's other visits. Every opening is logged at both facilities.")}</p>
    </Modal>
  );
}

function SentReferrals({ onOpen }: { onOpen: (r: Referral) => void }) {
  const { tr } = usePrefs();
  const { data, error, loading, reload } = useAsync(() => api.listReferrals(), []);
  const [view, setView] = useState<Referral | null>(null);
  const [confirm, setConfirm] = useState<Referral | null>(null);
  const overdue = data?.filter((r) => r.overdue).length ?? 0;
  // E4: overdue first, then open, then received.
  const rows = [...(data ?? [])].sort((a, b) => Number(!!b.overdue) - Number(!!a.overdue) || Number(a.status === "received") - Number(b.status === "received"));
  return (
    <>
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
                    <Link href={`/reviewer/case/${r.encounter_id}`} className="hover:underline">{r.patient_name}</Link> <span className="font-normal text-muted">· {tr("Suggested:")} {r.to_facility_name ?? r.destination}</span> <span className="ml-1 rounded bg-teal-50 px-1.5 py-0.5 font-mono text-xs font-medium text-teal-800">{refCode(r.id)}</span>
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
                {r.to_facility_id && <Badge tone="teal">{tr("Also routed to their Incoming")}</Badge>}
                <button className="text-sm font-semibold text-teal-700 hover:underline" onClick={() => setView(r)}>{tr("View note")}</button>
                <button className="text-sm font-semibold text-teal-700 hover:underline" onClick={() => onOpen(r)}>{tr("Open visit")}</button>
              </li>
            ))}
          </ul>
        </Card>
      )}
      {confirm && <ReceivedModal r={confirm} onClose={() => setConfirm(null)} onDone={() => { setConfirm(null); reload(); }} />}
      <Modal open={!!view} onClose={() => setView(null)} title={tr("Referral — {name}", { name: view?.patient_name ?? "" })} size="lg">
        <pre className="font-mono text-[13px] whitespace-pre-wrap text-ink">{tr(view?.note_text)}</pre>
      </Modal>
    </>
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
      subtitle={tr("Close the referral only after care is confirmed. The receiving clinician can confirm from the QR summary at any facility the patient chooses.")}
      footer={<><Button variant="secondary" onClick={onClose}>{tr("Cancel")}</Button><Button variant="teal" loading={busy} onClick={submit}>{tr("Close referral")}</Button></>}
    >
      <p className="text-sm text-muted">{refCode(r.id)} · {r.patient_name} → {r.destination}</p>
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
