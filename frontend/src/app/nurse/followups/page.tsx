"use client";

import Link from "next/link";
import { useState } from "react";
import { Baby, Phone, PhoneOff, Home, CheckCircle2, CalendarClock, HeartPulse, Bot, UserRound, Siren, MessageSquare } from "lucide-react";
import { api } from "@/lib/api";
import { fmtDate, useAsync, timeAgo } from "@/lib/hooks";
import { usePrefs, useSession } from "@/components/providers";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Button, Card, Empty, ErrorNote, Segmented, Spinner } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import type { Followup } from "@/lib/types";

const STATUS: Record<Followup["status"], { label: string; tone: "crit" | "semi" | "info" | "neutral" | "rout" }> = {
  flagged: { label: "Danger sign on a call — a person must call back", tone: "crit" },
  call_due: { label: "Reminder call due", tone: "crit" },
  missed: { label: "Missed check-up", tone: "semi" },
  contacted: { label: "Reached — waiting for the visit", tone: "info" },
  scheduled: { label: "Scheduled", tone: "neutral" },
  done: { label: "Came", tone: "rout" },
  cancelled: { label: "Cancelled", tone: "neutral" },
};

const PHONE: Record<string, string> = {
  self: "Own phone",
  husband: "Husband's phone — say nothing about pregnancy",
  household: "Family phone — say nothing about pregnancy",
  none: "No phone — home visit only",
};
// The pregnancy warning is for pregnancy follow-ups; a chronic patient's shared phone only needs naming.
const PHONE_CHRONIC: Record<string, string> = { husband: "Husband's phone", household: "Family phone" };

const WHO: Record<Followup["who_calls"]["who"], { label: string; icon: React.ReactNode; tone: "teal" | "semi" | "neutral" }> = {
  agent: { label: "Agent may call", icon: <Bot className="size-3.5" />, tone: "teal" },
  human: { label: "A person must call", icon: <UserRound className="size-3.5" />, tone: "semi" },
  home_visit: { label: "Home visit", icon: <Home className="size-3.5" />, tone: "neutral" },
};

/** D4 + E5 + E6: the health worker's list of maternal and chronic check-ups that are due or were missed. */
export default function FollowupsPage() {
  const { tr } = usePrefs();
  const { user } = useSession();
  const [scope, setScope] = useState<"active" | "all">("active");
  const [programme, setProgramme] = useState<"all" | "maternal" | "chronic">("all");
  const { data, error, loading, reload, setData } = useAsync(() => api.listFollowups(scope, programme), [scope, programme], { pollMs: 30_000 });
  const [busy, setBusy] = useState<string | null>(null);
  const tel = useAsync(() => api.telephonyStatus(), []);

  async function sms(f: Followup) {
    setBusy(`${f.id}:sms`);
    try {
      const r = await api.followupSms(f.id);
      setData((data ?? []).map((x) => (x.id === r.id ? r : x)));
      toast(tr("Reminder SMS sent to the demo phone {n}", { n: tel.data?.demo_to ?? "" }));
    } catch (err) {
      toast(err instanceof Error ? err.message : tr("Failed"), "error");
    } finally {
      setBusy(null);
    }
  }

  async function act(f: Followup, what: "reached" | "not_reached" | "came") {
    setBusy(`${f.id}:${what}`);
    try {
      const r = await api.followupAttempt(f.id, what);
      setData((data ?? []).map((x) => (x.id === r.id ? r : x)));
      toast(tr("Attempt recorded"));
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
        title={tr("Follow-ups")}
        subtitle={
          user?.role === "health_worker"
            ? tr("Pregnancy and long-term-condition check-ups assigned to you that are due or were missed. Visit or phone; after 2 failed attempts a reminder call is due.")
            : tr("Every maternal and chronic check-up at this facility. A check-up becomes missed one day after its due date.")
        }
      />
      <div className="mb-4 flex flex-wrap gap-2">
        <Segmented value={programme} onChange={setProgramme} options={[{ value: "all", label: tr("All") }, { value: "maternal", label: tr("Pregnancy") }, { value: "chronic", label: tr("Long-term conditions") }]} />
        <Segmented value={scope} onChange={setScope} options={[{ value: "active", label: tr("Open") }, { value: "all", label: tr("All, including closed") }]} />
      </div>
      {error ? <ErrorNote error={error} onRetry={reload} /> : loading && !data ? <Spinner /> : !data?.length ? (
        <Card><Empty icon={<CalendarClock className="size-6" />} title={tr("No follow-ups due")} body={tr("Check-ups appear here when a pregnancy or chronic visit sets the next check-up date.")} /></Card>
      ) : (
        <div className="space-y-3">
          {data.map((f) => {
            const open = ["missed", "call_due", "contacted", "flagged"].includes(f.status);
            const who = WHO[f.who_calls.who];
            return (
              <Card key={f.id} className={f.status === "flagged" || f.status === "call_due" ? "border-crit-line" : ""}>
                <div className="p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    {f.programme === "maternal" ? <Baby className="size-4 text-coral-700" /> : <HeartPulse className="size-4 text-teal-700" />}
                    <span className="font-semibold text-ink">{f.patient_name}</span>
                    <span className="font-mono text-xs text-subtle">{f.patient_code}</span>
                    {f.village && <span className="text-sm text-muted">{f.village}</span>}
                    {f.gestation_weeks && <Badge tone="coral">{tr("{w} weeks at last visit", { w: f.gestation_weeks })}</Badge>}
                    {f.condition && <Badge tone="teal">{f.condition}</Badge>}
                    <Badge tone={STATUS[f.status].tone}>{tr(STATUS[f.status].label)}</Badge>
                  </div>
                  <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-2">
                    <span className="inline-flex items-center gap-1"><CalendarClock className="size-4" /> {tr("Due")} {fmtDate(f.due_at)}</span>
                    <span className="inline-flex items-center gap-1">
                      {f.phone_belongs_to === "none" || !f.phone ? <PhoneOff className="size-4" /> : <Phone className="size-4" />}
                      {f.phone ?? tr("no phone")} · {tr((f.programme === "chronic" && PHONE_CHRONIC[f.phone_belongs_to ?? "household"]) || PHONE[f.phone_belongs_to ?? "household"] || PHONE.household)}
                    </span>
                    {f.assigned_name && <span className="text-muted">{tr("Assigned to")} {f.assigned_name}</span>}
                  </p>
                  {open && (
                    <p className="mt-2 flex flex-wrap items-center gap-2 text-sm text-ink-2">
                      <Badge tone={who.tone}>{who.icon} {tr(who.label)}</Badge>
                      <span className="text-muted">{tr(f.who_calls.why)}</span>
                    </p>
                  )}
                  {f.attempts.length > 0 && (
                    <ul className="mt-2 space-y-0.5 text-xs text-muted">
                      {f.attempts.map((a, i) => (
                        <li key={i} className={a.call_outcome === "danger_sign" ? "font-semibold text-crit" : ""}>
                          {timeAgo(a.at)} · {a.by} · {a.outcome === "call" ? tr("call") : a.outcome === "sms" ? tr("SMS") : tr(a.outcome.replace("_", " "))}{a.note ? ` — ${a.note}` : ""}
                        </li>
                      ))}
                    </ul>
                  )}
                  {(open || f.status === "scheduled") && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Button size="sm" variant="teal" icon={<CheckCircle2 className="size-4" />} loading={busy === `${f.id}:came`} onClick={() => act(f, "came")}>{tr("Came for the check-up")}</Button>
                      {open && (
                        <>
                          <Button size="sm" variant="secondary" icon={<Home className="size-4" />} loading={busy === `${f.id}:reached`} onClick={() => act(f, "reached")}>{tr("Reached")}</Button>
                          <Button size="sm" variant="secondary" icon={<PhoneOff className="size-4" />} loading={busy === `${f.id}:not_reached`} onClick={() => act(f, "not_reached")}>{tr("Could not reach")}</Button>
                          {tel.data?.sms && f.who_calls.who !== "home_visit" && (
                            <Button size="sm" variant="secondary" icon={<MessageSquare className="size-4" />} loading={busy === `${f.id}:sms`} onClick={() => sms(f)}>{tr("Send SMS")}</Button>
                          )}
                          {f.who_calls.who !== "home_visit" && (
                            <Link href={`/nurse/followups/${f.id}/call`}>
                              <Button size="sm" variant={f.status === "call_due" ? "danger" : "outline"} icon={f.status === "flagged" ? <Siren className="size-4" /> : <Phone className="size-4" />}>
                                {f.status === "flagged" ? tr("See the call") : f.who_calls.who === "agent" ? tr("Reminder call") : tr("Call with the script")}
                              </Button>
                            </Link>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
