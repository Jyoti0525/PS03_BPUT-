"use client";

import { usePrefs } from "@/components/providers";
import Link from "next/link";
import { Briefcase, ShieldCheck, EyeOff, Users } from "lucide-react";
import { PageHeader } from "@/components/layout/app-shell";
import { api } from "@/lib/api";
import { useAsync, fmtDate } from "@/lib/hooks";
import { Badge, Button, Card, CardHeader, Empty, ErrorNote, Spinner, Stat } from "@/components/ui";
import { FITNESS } from "@/components/employer/status";
import type { FitnessStatus } from "@/lib/types";

export default function EmployerOverview() {
  const { tr } = usePrefs();
  const { data, error, reload } = useAsync(() => api.listCohorts(), []);
  if (error) return <ErrorNote error={error} onRetry={reload} />;
  if (!data) return <Spinner />;
  const all = data.flatMap((c) => c.workers);
  const count = (s: FitnessStatus) => all.filter((w) => w.fitness_status === s).length;
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title={tr("Occupational fitness")} subtitle={tr("Fitness status by department. This view never contains symptoms, diagnoses, notes or reports.")} />
      <div className="mb-5 flex items-start gap-3 rounded-xl border border-teal-200 bg-teal-50 px-4 py-3 text-sm text-teal-800">
        <EyeOff className="mt-0.5 size-4 shrink-0" />
        {tr("Workers are identified by employee code only. Clinical details stay between the worker and the health unit; you receive the fitness outcome decided by the medical officer.")}
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={tr("Fit")} value={count("fit")} tone="rout" />
        <Stat label={tr("With restrictions")} value={count("fit_with_restrictions")} tone="semi" />
        <Stat label={tr("Temporarily unfit")} value={count("temporarily_unfit")} tone="crit" />
        <Stat label={tr("Pending review")} value={count("pending_review")} />
      </div>
      {!data.length && (
        <Card className="mt-5">
          <Empty
            icon={<Users className="size-6" />}
            title={tr("No workers on your roster yet")}
            body={tr("Add workers (or import a CSV) so the health unit can link their visits and record fitness outcomes.")}
            action={
              <Link href="/employer/workers">
                <Button>{tr("Add workers")}</Button>
              </Link>
            }
          />
        </Card>
      )}
      {data.map((c) => (
        <Card key={c.id} className="mt-5">
          <CardHeader title={c.name} subtitle={tr(c.workers.length === 1 ? "{org} · 1 worker" : "{org} · {n} workers", { org: c.employer_name, n: c.workers.length })} icon={<Briefcase className="size-4" />} />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs tracking-wide text-muted uppercase">
                  <th className="px-4 py-2 font-semibold">{tr("Worker")}</th>
                  <th className="px-4 py-2 font-semibold">{tr("Department")}</th>
                  <th className="px-4 py-2 font-semibold">{tr("Status")}</th>
                  <th className="px-4 py-2 font-semibold">{tr("Last assessed")}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {c.workers.map((w) => (
                  <tr key={w.worker_code}>
                    <td className="px-4 py-2.5 font-mono text-ink">{w.worker_code}</td>
                    <td className="px-4 py-2.5 text-muted">{w.department}</td>
                    <td className="px-4 py-2.5">
                      <Badge tone={FITNESS[w.fitness_status].tone}>{tr(FITNESS[w.fitness_status].label)}</Badge>
                    </td>
                    <td className="px-4 py-2.5 text-muted">{w.last_screened_at ? fmtDate(w.last_screened_at) : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ))}
      <p className="mt-4 flex items-center gap-1.5 text-xs text-muted">
        <ShieldCheck className="size-3.5" /> {tr("Every employer view is recorded in the audit log.")}
      </p>
    </div>
  );
}
