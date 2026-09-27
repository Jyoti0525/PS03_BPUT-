"use client";

import Link from "next/link";
import { useState } from "react";
import { Siren, CheckCircle2, Bot, UserRound } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync, timeAgo } from "@/lib/hooks";
import { useSession, usePrefs } from "@/components/providers";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Button, Card, Empty, ErrorNote, Label, Modal, Segmented, Spinner, Textarea } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { UrgencyBadge } from "@/components/triage/note";
import type { Escalation } from "@/lib/types";

const TO = { senior_mo: "Senior MO", specialist: "Specialist", doctor: "Doctor on duty" };

export default function EscalationsPage() {
  const { tr } = usePrefs();
  const { user } = useSession();
  const [tab, setTab] = useState<"open" | "acknowledged">("open");
  const { data, error, loading, reload } = useAsync(() => api.listEscalations(), [], { pollMs: 15_000 });
  const [ack, setAck] = useState<Escalation | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const list = data?.filter((e) => e.status === tab) ?? [];

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title={tr("Escalations")} subtitle={tr("Raised by staff or automatically when a critical case waits too long. Each must be acknowledged by a doctor.")} />
      <Segmented
        className="mb-4"
        value={tab}
        onChange={setTab}
        options={[
          { value: "open", label: "Awaiting acknowledgement", count: data?.filter((e) => e.status === "open").length },
          { value: "acknowledged", label: "Acknowledged", count: data?.filter((e) => e.status === "acknowledged").length },
        ]}
      />
      {error ? <ErrorNote error={error} onRetry={reload} /> : loading && !data ? <Spinner /> : list.length === 0 ? (
        <Card><Empty icon={<Siren className="size-6" />} title={tab === "open" ? tr("Nothing waiting for acknowledgement") : tr("No acknowledged escalations yet")} /></Card>
      ) : (
        <div className="space-y-3">
          {list.map((e) => (
            <Card key={e.id} className={e.status === "open" ? "border-crit-line" : ""}>
              <div className="flex flex-wrap items-start gap-3 p-4">
                <span className={`grid size-10 place-items-center rounded-xl ${e.status === "open" ? "bg-crit-bg text-crit" : "bg-rout-bg text-rout"}`}>
                  {e.status === "open" ? <Siren className="size-5" /> : <CheckCircle2 className="size-5" />}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <Link href={`/reviewer/case/${e.encounter_id}`} className="font-semibold text-ink hover:underline">{e.patient_name}</Link>
                    <UrgencyBadge u={e.urgency} size="sm" />
                    <Badge tone={e.auto ? "semi" : "neutral"}>{e.auto ? <><Bot className="size-3" /> {tr("Auto (timer)")}</> : <><UserRound className="size-3" /> {e.raised_by}</>}</Badge>
                    <Badge>→ {TO[e.to_role]}</Badge>
                  </div>
                  <p className="mt-1 text-sm text-ink-2">{e.reason}</p>
                  <p className="mt-1 text-xs text-muted">{tr("Raised")} {timeAgo(e.raised_at)}</p>
                  {e.status === "acknowledged" && (
                    <p className="mt-2 rounded-lg bg-rout-bg px-3 py-2 text-sm text-rout">
                      {tr("Acknowledged by")} {e.acknowledged_by} {e.acknowledged_at && timeAgo(e.acknowledged_at)}{e.ack_note ? ` — “${e.ack_note}”` : ""}
                    </p>
                  )}
                </div>
                {e.status === "open" && (
                  <div className="flex gap-2">
                    <Link href={`/reviewer/case/${e.encounter_id}`}><Button variant="secondary">{tr("Open case")}</Button></Link>
                    {user?.role === "doctor" && <Button variant="danger" onClick={() => { setAck(e); setNote(""); }}>{tr("Acknowledge")}</Button>}
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
      <Modal
        open={!!ack}
        onClose={() => setAck(null)}
        title={tr("Acknowledge escalation")}
        subtitle={tr("Confirms you have taken responsibility for this patient. Logged with your name and time.")}
        footer={
          <>
            <Button variant="secondary" onClick={() => setAck(null)}>{tr("Cancel")}</Button>
            <Button
              variant="teal"
              loading={busy}
              onClick={async () => {
                if (!ack) return;
                setBusy(true);
                try {
                  await api.acknowledgeEscalation(ack.id, note);
                  toast(tr("Escalation acknowledged"));
                  setAck(null);
                  reload();
                } catch (err) {
                  toast(err instanceof Error ? err.message : tr("Failed"), "error");
                } finally {
                  setBusy(false);
                }
              }}
            >
              {tr("Acknowledge")}
            </Button>
          </>
        }
      >
        <Label htmlFor="ack-note">{tr("Note (optional)")}</Label>
        <Textarea id="ack-note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder={tr("e.g. Seeing patient now in bay 2")} />
      </Modal>
    </div>
  );
}
