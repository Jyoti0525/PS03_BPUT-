"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { RefreshCw, Search, Baby, HeartPulse, Timer, AlertTriangle, WifiOff, Inbox } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync, useNow, fmtWait } from "@/lib/hooks";
import { useSession } from "@/components/providers";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Button, Card, Empty, ErrorNote, Input, Segmented, Spinner, Stat, cx } from "@/components/ui";
import { UrgencyBadge, urgencyBar } from "@/components/triage/note";
import type { QueueItem, Urgency } from "@/lib/types";
import { langByCode } from "@/lib/i18n/languages";

function Countdown({ due, now }: { due: string | null; now: number }) {
  if (!due) return null;
  const ms = Date.parse(due) - now;
  if (ms <= 0) return <Badge tone="crit"><AlertTriangle className="size-3" /> Escalated</Badge>;
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return (
    <Badge tone={m < 5 ? "crit" : "neutral"}>
      <Timer className="size-3" /> {m}:{String(s).padStart(2, "0")}
    </Badge>
  );
}

export default function QueuePage() {
  const { user } = useSession();
  const fid = user!.facility_id!;
  const { data, error, loading, reload } = useAsync(() => api.queue(fid), [fid], { pollMs: 15_000 });
  const now = useNow(1000);
  const [filter, setFilter] = useState<"all" | Urgency>("all");
  const [q, setQ] = useState("");

  const items = useMemo(() => {
    const s = q.trim().toLowerCase();
    return (data ?? []).filter((i) => (filter === "all" || i.urgency === filter) && (!s || `${i.patient_name} ${i.patient_code} ${i.chief_complaint}`.toLowerCase().includes(s)));
  }, [data, filter, q]);

  const count = (u: Urgency) => data?.filter((i) => i.urgency === u).length ?? 0;
  const avgWait = data?.length ? Math.round(data.reduce((s, i) => s + i.wait_minutes, 0) / data.length) : 0;

  return (
    <>
      <PageHeader
        title="Triage queue"
        subtitle="Ordered by rules-engine urgency, then waiting time. Critical cases auto-escalate after 15 minutes."
        actions={
          <Button variant="secondary" onClick={() => reload()} icon={<RefreshCw className="size-4" />}>
            Refresh
          </Button>
        }
      />

      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Critical" value={count("red")} tone="crit" hint="Immediate" />
        <Stat label="Semi-urgent" value={count("yellow")} tone="semi" hint="Within 30–60 min" />
        <Stat label="Routine" value={count("green")} tone="rout" hint="Standard OPD order" />
        <Stat label="Avg. wait" value={fmtWait(avgWait)} hint={`${data?.length ?? 0} waiting`} />
      </div>

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-line p-3">
          <Segmented
            value={filter}
            onChange={setFilter}
            options={[
              { value: "all", label: "All", count: data?.length },
              { value: "red", label: "Critical", count: count("red") },
              { value: "yellow", label: "Semi-urgent", count: count("yellow") },
              { value: "green", label: "Routine", count: count("green") },
            ]}
          />
          <div className="relative ml-auto w-full sm:w-64">
            <Search className="absolute top-3 left-3 size-4 text-subtle" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Name, ID or complaint" className="h-10 pl-9" aria-label="Filter queue" />
          </div>
        </div>

        {error ? (
          <div className="p-4">
            <ErrorNote error={error} onRetry={reload} />
          </div>
        ) : loading && !data ? (
          <Spinner label="Loading queue…" />
        ) : items.length === 0 ? (
          <Empty icon={<Inbox className="size-6" />} title="No patients waiting" body="New intakes from the kiosk appear here automatically." />
        ) : (
          <ul className="divide-y divide-line">
            {items.map((i: QueueItem, idx) => (
              <li key={i.encounter_id}>
                <Link href={`/reviewer/case/${i.encounter_id}`} className="flex items-stretch gap-3 px-3 py-3 transition-colors hover:bg-canvas sm:px-4">
                  <span className={cx("w-1.5 shrink-0 rounded-full", urgencyBar(i.urgency))} />
                  <span className="hidden w-6 pt-0.5 text-sm font-semibold text-subtle tabular-nums sm:block">{idx + 1}</span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-ink">{i.patient_name}</span>
                      <span className="text-sm text-muted">
                        {i.age}
                        {i.sex}
                      </span>
                      <span className="font-mono text-xs text-subtle">{i.patient_code}</span>
                      {i.category === "maternal" && <Badge tone="coral"><Baby className="size-3" /> Maternal</Badge>}
                      {i.category === "chronic" && <Badge tone="teal"><HeartPulse className="size-3" /> Chronic</Badge>}
                      {i.status === "in_review" && <Badge tone="info">In review</Badge>}
                    </div>
                    <p className="mt-0.5 truncate text-sm text-ink-2">{i.chief_complaint}</p>
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                      {i.flag_count > 0 && <Badge tone={i.urgency === "red" ? "crit" : "semi"}>{i.flag_count} flag{i.flag_count > 1 && "s"}</Badge>}
                      {i.needs_check_count > 0 && <Badge tone="semi">{i.needs_check_count} needs checking</Badge>}
                      <Badge>{langByCode(i.language).name}</Badge>
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-col items-end justify-between gap-1.5">
                    <UrgencyBadge u={i.urgency} size="sm" />
                    <span className="text-sm font-semibold text-ink tabular-nums">{fmtWait(Math.max(i.wait_minutes, Math.round((now - Date.parse(i.created_at)) / 60000)))}</span>
                    {i.status !== "escalated" ? <Countdown due={i.escalation_due_at} now={now} /> : <Badge tone="crit">Escalated</Badge>}
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <p className="mt-3 flex items-center gap-1.5 text-xs text-subtle">
        <WifiOff className="size-3.5" /> Intakes captured offline keep their original capture time, so waiting time is never understated.
      </p>
    </>
  );
}
