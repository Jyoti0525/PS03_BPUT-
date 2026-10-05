"use client";

import { useState } from "react";
import { Baby, Phone, PhoneOff, Home, CheckCircle2, CalendarClock } from "lucide-react";
import { api } from "@/lib/api";
import { fmtDate, useAsync, timeAgo } from "@/lib/hooks";
import { usePrefs, useSession } from "@/components/providers";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Button, Card, Empty, ErrorNote, Segmented, Spinner } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import type { Followup } from "@/lib/types";

const STATUS: Record<Followup["status"], { label: string; tone: "crit" | "semi" | "info" | "neutral" | "rout" }> = {
  call_due: { label: "Reminder call due", tone: "crit" },
  missed: { label: "Missed check-up", tone: "semi" },
  contacted: { label: "Reached — waiting for her visit", tone: "info" },
  scheduled: { label: "Scheduled", tone: "neutral" },
  done: { label: "Came", tone: "rout" },
  cancelled: { label: "Cancelled", tone: "neutral" },
};

const PHONE: Record<string, string> = {
  self: "Her own phone",
  husband: "Husband's phone — say nothing about pregnancy",
  household: "Family phone — say nothing about pregnancy",
  none: "No phone — home visit only",
};

/** D4: the health worker's list of women whose maternal check-up was missed. */
export default function FollowupsPage() {
  const { tr } = usePrefs();
  const { user } = useSession();
  const [scope, setScope] = useState<"active" | "all">("active");
  const { data, error, loading, reload, setData } = useAsync(() => api.listFollowups(scope), [scope], { pollMs: 30_000 });
  const [busy, setBusy] = useState<string | null>(null);

  async function act(f: Followup, what: "reached" | "not_reached" | "came" | "call") {
    setBusy(`${f.id}:${what}`);
    try {
      const r = what === "call" ? await api.followupCall(f.id) : await api.followupAttempt(f.id, what);
      setData((data ?? []).map((x) => (x.id === r.id ? r : x)));
      toast(what === "call" ? tr("Call recorded (simulated — no call is made in this build)") : tr("Attempt recorded"));
      if (what === "came") reload();
    } catch (err) {
      toast(err instanceof Error ? err.message : tr("Failed"), "error");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title={tr("Maternal follow-ups")}
        subtitle={
          user?.role === "health_worker"
            ? tr("Women assigned to you whose check-up is due or was missed. Visit or phone; after 2 failed attempts a reminder call is due.")
            : tr("Every maternal check-up at this facility. A check-up becomes missed one day after its due date.")
        }
      />
      <Segmented className="mb-4" value={scope} onChange={setScope} options={[{ value: "active", label: "Open" }, { value: "all", label: "All, including closed" }]} />
      {error ? <ErrorNote error={error} onRetry={reload} /> : loading && !data ? <Spinner /> : !data?.length ? (
        <Card><Empty icon={<Baby className="size-6" />} title={tr("No follow-ups due")} body={tr("Check-ups appear here when a pregnancy visit sets the next check-up date.")} /></Card>
      ) : (
        <div className="space-y-3">
          {data.map((f) => (
            <Card key={f.id} className={f.status === "call_due" ? "border-crit-line" : ""}>
              <div className="p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-ink">{f.patient_name}</span>
                  <span className="font-mono text-xs text-subtle">{f.patient_code}</span>
                  {f.village && <span className="text-sm text-muted">{f.village}</span>}
                  {f.gestation_weeks && <Badge tone="coral">{tr("{w} weeks at last visit", { w: f.gestation_weeks })}</Badge>}
                  <Badge tone={STATUS[f.status].tone}>{tr(STATUS[f.status].label)}</Badge>
                </div>
                <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-2">
                  <span className="inline-flex items-center gap-1"><CalendarClock className="size-4" /> {tr("Due")} {fmtDate(f.due_at)}</span>
                  <span className="inline-flex items-center gap-1">
                    {f.phone_belongs_to === "none" || !f.phone ? <PhoneOff className="size-4" /> : <Phone className="size-4" />}
                    {f.phone ?? tr("no phone")} · {tr(PHONE[f.phone_belongs_to ?? "household"] ?? PHONE.household)}
                  </span>
                  {f.assigned_name && <span className="text-muted">{tr("Assigned to")} {f.assigned_name}</span>}
                </p>
                {f.call_script && ["missed", "call_due", "contacted"].includes(f.status) && (
                  <p className="mt-2 rounded-lg bg-canvas px-3 py-2 text-sm text-ink-2">
                    <span className="font-semibold">{tr("Call script")} ({tr("English only in this build")}):</span> “{f.call_script}”
                  </p>
                )}
                {f.attempts.length > 0 && (
                  <ul className="mt-2 space-y-0.5 text-xs text-muted">
                    {f.attempts.map((a, i) => (
                      <li key={i}>
                        {timeAgo(a.at)} · {a.by} · {tr(a.outcome.replace("_", " "))}{a.note ? ` — ${a.note}` : ""}
                      </li>
                    ))}
                  </ul>
                )}
                {["missed", "call_due", "contacted", "scheduled"].includes(f.status) && (
                  <div className="mt-3 flex flex-wrap gap-2">
                    <Button size="sm" variant="teal" icon={<CheckCircle2 className="size-4" />} loading={busy === `${f.id}:came`} onClick={() => act(f, "came")}>{tr("She came")}</Button>
                    {f.status !== "scheduled" && (
                      <>
                        <Button size="sm" variant="secondary" icon={<Home className="size-4" />} loading={busy === `${f.id}:reached`} onClick={() => act(f, "reached")}>{tr("Reached her")}</Button>
                        <Button size="sm" variant="secondary" icon={<PhoneOff className="size-4" />} loading={busy === `${f.id}:not_reached`} onClick={() => act(f, "not_reached")}>{tr("Could not reach")}</Button>
                        {f.call_script && (
                          <Button size="sm" variant={f.status === "call_due" ? "danger" : "outline"} icon={<Phone className="size-4" />} loading={busy === `${f.id}:call`} onClick={() => act(f, "call")}>
                            {tr("Place reminder call")}
                          </Button>
                        )}
                      </>
                    )}
                  </div>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
