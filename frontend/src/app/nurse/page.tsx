"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { Activity, Baby, CheckCircle2, HeartPulse, Inbox, RefreshCw, Search } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync, useNow, fmtWait } from "@/lib/hooks";
import { usePrefs, useSession } from "@/components/providers";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Button, Card, Empty, ErrorNote, Input, Segmented, Spinner, Stat, cx } from "@/components/ui";
import { UrgencyBadge, urgencyBar } from "@/components/triage/note";

/** Nursing station: every waiting patient, with what still needs doing at the bedside (vitals, observations). */
export default function NurseHome() {
  const { user } = useSession();
  const { tr } = usePrefs();
  const fid = user!.facility_id!;
  const { data, error, loading, reload } = useAsync(() => api.queue(fid), [fid], { pollMs: 15_000 });
  const now = useNow(30_000);
  const [filter, setFilter] = useState<"todo" | "all">("todo");
  const [q, setQ] = useState("");

  const needVitals = (data ?? []).filter((i) => !i.vitals_recorded && !i.observation_count);
  const items = useMemo(() => {
    const s = q.trim().toLowerCase();
    const base = filter === "todo" ? needVitals : data ?? [];
    return base.filter((i) => !s || `${i.patient_name} ${i.patient_code} ${i.token ?? ""}`.toLowerCase().includes(s));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, filter, q]);

  return (
    <>
      <PageHeader
        title={tr("Patients to attend")}
        subtitle={tr("Record vitals and bedside observations. The doctor sees them in the case straight away.")}
        actions={
          <Button variant="secondary" onClick={() => reload()} icon={<RefreshCw className="size-4" />}>
            {tr("Refresh")}
          </Button>
        }
      />
      <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label={tr("Waiting")} value={data?.length ?? 0} />
        <Stat label={tr("Vitals still needed")} value={needVitals.length} tone={needVitals.length ? "semi" : "rout"} />
        <Stat label={tr("Critical")} value={data?.filter((i) => i.urgency === "red").length ?? 0} tone="crit" hint={tr("Attend first")} />
        <Stat label={tr("Observed")} value={(data ?? []).filter((i) => (i.observation_count ?? 0) > 0).length} tone="teal" />
      </div>
      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-line p-3">
          <Segmented
            value={filter}
            onChange={setFilter}
            options={[
              { value: "todo", label: tr("Vitals needed"), count: needVitals.length },
              { value: "all", label: tr("All waiting"), count: data?.length },
            ]}
          />
          <div className="relative ml-auto w-full sm:w-64">
            <Search className="absolute top-3 left-3 size-4 text-subtle" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder={tr("Name, ID or token")} className="h-10 pl-9" aria-label={tr("Filter patients")} />
          </div>
        </div>
        {error ? (
          <div className="p-4">
            <ErrorNote error={error} onRetry={reload} />
          </div>
        ) : loading && !data ? (
          <Spinner />
        ) : !items.length ? (
          <Empty icon={filter === "todo" ? <CheckCircle2 className="size-6" /> : <Inbox className="size-6" />} title={tr(filter === "todo" ? "Everyone waiting has vitals recorded" : "No patients waiting")} />
        ) : (
          <ul className="divide-y divide-line">
            {items.map((i) => (
              <li key={i.encounter_id} className="flex items-stretch gap-3 px-3 py-3 sm:px-4">
                <span className={cx("w-1.5 shrink-0 rounded-full", urgencyBar(i.urgency))} />
                <span className="w-14 shrink-0 pt-0.5">
                  <span className="block rounded-md bg-teal-50 py-0.5 text-center font-mono text-xs font-bold text-teal-800">{i.token ?? "—"}</span>
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold text-ink">{i.patient_name}</span>
                    <span className="text-sm text-muted">
                      {i.age}
                      {i.sex}
                    </span>
                    {i.category === "maternal" && (
                      <Badge tone="coral">
                        <Baby className="size-3" /> {tr("Maternal")}
                      </Badge>
                    )}
                    {i.category === "chronic" && (
                      <Badge tone="teal">
                        <HeartPulse className="size-3" /> {tr("Chronic")}
                      </Badge>
                    )}
                  </div>
                  <p className="mt-0.5 truncate text-sm text-ink-2">{i.chief_complaint}</p>
                  <div className="mt-1.5 flex flex-wrap gap-1.5">
                    {i.vitals_recorded ? <Badge tone="rout">{tr("Vitals recorded")}</Badge> : <Badge tone="semi">{tr("Vitals needed")}</Badge>}
                    {!!i.observation_count && <Badge tone="teal">{tr("{n} observations", { n: i.observation_count })}</Badge>}
                    <span className="text-xs text-subtle">{tr("waiting {w}", { w: fmtWait(Math.max(i.wait_minutes, Math.round((now - Date.parse(i.created_at)) / 60000))) })}</span>
                  </div>
                </div>
                <div className="flex shrink-0 flex-col items-end justify-between gap-2">
                  <UrgencyBadge u={i.urgency} size="sm" />
                  <Link href={`/nurse/patient/${i.encounter_id}`}>
                    <Button size="sm" icon={<Activity className="size-4" />}>
                      {tr(i.vitals_recorded ? "Open" : "Record vitals")}
                    </Button>
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </>
  );
}
