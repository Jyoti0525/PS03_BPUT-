"use client";

import { useState } from "react";
import { BellRing, CheckCircle2, Download, Thermometer, Users, Baby } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync, timeAgo } from "@/lib/hooks";
import { usePrefs } from "@/components/providers";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Button, Card, Empty, ErrorNote, Label, Modal, Segmented, Spinner, Textarea } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { downloadBlob } from "@/lib/export";
import type { Alert, AlertKind } from "@/lib/types";

const KIND: Record<AlertKind, { label: string; icon: React.ReactNode }> = {
  capacity: { label: "Capacity", icon: <Users className="size-5" /> },
  fever_cluster: { label: "Fever cluster", icon: <Thermometer className="size-5" /> },
  missed_visit: { label: "Missed check-up", icon: <Baby className="size-5" /> },
};

/** What the alert's numbers mean, in words. Cluster alerts carry counts only — never names. */
function Detail({ a }: { a: Alert }) {
  const { tr } = usePrefs();
  const d = a.detail as Record<string, string | number | boolean | null | string[]>;
  if (a.kind === "fever_cluster")
    return (
      <p className="mt-1 text-sm text-ink-2">
        {tr("{n} fevers from {p} in the last {h} hours; the {b} days before averaged {e} per {h} hours ({c} cases).", {
          n: String(d.cases_72h), p: String(d.cluster), h: String(d.window_hours), b: "14", e: String(d.expected_72h), c: String(d.baseline_14d),
        })}{" "}
        <span className="text-muted">{tr("Rule")}: {String(d.rule)}.</span>
      </p>
    );
  if (a.kind === "capacity")
    return (
      <p className="mt-1 text-sm text-ink-2">
        {tr("Tokens")}: {(d.tokens as string[] | undefined)?.join(", ") || "—"} · {tr("longest wait {m} min", { m: String(d.longest_wait_min ?? 0) })}
      </p>
    );
  return <p className="mt-1 text-sm text-ink-2">{tr("Due")} {String(d.due)} · {String(d.patient_code)}</p>;
}

export default function AlertsPage() {
  const { tr } = usePrefs();
  const [tab, setTab] = useState<"active" | "resolved">("active");
  const { data, error, loading, reload } = useAsync(() => api.listAlerts(), [], { pollMs: 20_000 });
  const [ack, setAck] = useState<Alert | null>(null);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const list = (data ?? []).filter((a) => (tab === "active" ? a.status !== "resolved" : a.status === "resolved"));

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title={tr("Alerts")}
        subtitle={tr("Raised by fixed rules, not by a model: too many RED cases for the doctors on duty, a fever cluster from one place, or a missed maternal check-up.")}
        actions={
          <Button
            variant="secondary"
            icon={<Download className="size-4" />}
            onClick={async () => {
              try {
                const r = await api.syndromicCsv(14);
                downloadBlob(r.filename, r.blob);
              } catch (err) {
                toast(err instanceof Error ? err.message : tr("Failed"), "error");
              }
            }}
          >
            {tr("Syndromic counts (14 days, CSV)")}
          </Button>
        }
      />
      <Segmented
        className="mb-4"
        value={tab}
        onChange={setTab}
        options={[
          { value: "active", label: "Active", count: data?.filter((a) => a.status !== "resolved").length },
          { value: "resolved", label: "Resolved", count: data?.filter((a) => a.status === "resolved").length },
        ]}
      />
      {error ? <ErrorNote error={error} onRetry={reload} /> : loading && !data ? <Spinner /> : list.length === 0 ? (
        <Card><Empty icon={<BellRing className="size-6" />} title={tab === "active" ? tr("No active alerts") : tr("No resolved alerts yet")} /></Card>
      ) : (
        <div className="space-y-3">
          {list.map((a) => (
            <Card key={a.id} className={a.status === "open" ? "border-crit-line" : ""}>
              <div className="flex flex-wrap items-start gap-3 p-4">
                <span className={`grid size-10 place-items-center rounded-xl ${a.status === "resolved" ? "bg-rout-bg text-rout" : a.status === "open" ? "bg-crit-bg text-crit" : "bg-semi-bg text-semi"}`}>
                  {a.status === "resolved" ? <CheckCircle2 className="size-5" /> : KIND[a.kind].icon}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-ink">{a.title}</span>
                    <Badge tone={a.kind === "capacity" ? "crit" : a.kind === "fever_cluster" ? "semi" : "coral"}>{tr(KIND[a.kind].label)}</Badge>
                    <Badge>→ {a.to_role === "medical_officer" ? tr("Medical officer") : tr("Health worker")}</Badge>
                  </div>
                  <Detail a={a} />
                  {typeof a.detail.action === "string" && <p className="mt-1 text-sm font-medium text-ink">{tr(a.detail.action)}</p>}
                  <p className="mt-1 text-xs text-muted">
                    {tr("Raised")} {timeAgo(a.raised_at)}
                    {a.updated_at !== a.raised_at && ` · ${tr("updated")} ${timeAgo(a.updated_at)}`}
                    {a.resolved_at && ` · ${tr("resolved")} ${timeAgo(a.resolved_at)}`}
                  </p>
                  {a.acknowledged_by && (
                    <p className="mt-2 rounded-lg bg-rout-bg px-3 py-2 text-sm text-rout">
                      {tr("Acknowledged by")} {a.acknowledged_by} {a.acknowledged_at && timeAgo(a.acknowledged_at)}{a.ack_note ? ` — “${a.ack_note}”` : ""}
                    </p>
                  )}
                </div>
                {a.status === "open" && <Button variant="danger" onClick={() => { setAck(a); setNote(""); }}>{tr("Acknowledge")}</Button>}
              </div>
            </Card>
          ))}
        </div>
      )}
      <p className="mt-4 text-xs text-subtle">
        {tr("Fever cluster: 5 or more fevers from one hostel block or village in 72 hours and more than 3 times that place's rate over the 14 days before. The export writes counts of 1–4 as “<5”.")}
      </p>
      <Modal
        open={!!ack}
        onClose={() => setAck(null)}
        title={tr("Acknowledge alert")}
        subtitle={tr("Logged with your name and time. The alert closes by itself when its condition no longer holds.")}
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
                  await api.acknowledgeAlert(ack.id, note);
                  toast(tr("Alert acknowledged"));
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
        <Label htmlFor="alert-note">{tr("What you are doing (optional)")}</Label>
        <Textarea id="alert-note" rows={3} value={note} onChange={(e) => setNote(e.target.value)} placeholder={tr("e.g. Called in Dr. Gupta; hostel water tank being checked")} />
      </Modal>
    </div>
  );
}
