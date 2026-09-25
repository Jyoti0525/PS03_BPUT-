"use client";

import { Briefcase, ShieldCheck, EyeOff } from "lucide-react";
import { RoleGate } from "@/components/layout/role-gate";
import { AppShell, PageHeader } from "@/components/layout/app-shell";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { Badge, Card, CardHeader, ErrorNote, Spinner, Stat } from "@/components/ui";
import type { FitnessStatus } from "@/lib/types";

const STATUS: Record<FitnessStatus, { label: string; tone: "rout" | "semi" | "crit" | "neutral" }> = {
  fit: { label: "Fit", tone: "rout" },
  fit_with_restrictions: { label: "Fit with restrictions", tone: "semi" },
  temporarily_unfit: { label: "Temporarily unfit", tone: "crit" },
  pending_review: { label: "Pending review", tone: "neutral" },
};

function EmployerView() {
  const { data, error, reload } = useAsync(() => api.listCohorts(), []);
  if (error) return <ErrorNote error={error} onRetry={reload} />;
  if (!data) return <Spinner />;
  const all = data.flatMap((c) => c.workers);
  const count = (s: FitnessStatus) => all.filter((w) => w.fitness_status === s).length;
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title="Occupational fitness" subtitle="Fitness status by cohort. This view never contains symptoms, diagnoses, notes or reports." />
      <div className="mb-5 flex items-start gap-3 rounded-xl border border-teal-200 bg-teal-50 px-4 py-3 text-sm text-teal-800">
        <EyeOff className="mt-0.5 size-4 shrink-0" />
        Workers are identified by employee code only. Clinical details stay between the worker and the health unit; the employer receives the fitness outcome decided by the medical officer.
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Fit" value={count("fit")} tone="rout" />
        <Stat label="With restrictions" value={count("fit_with_restrictions")} tone="semi" />
        <Stat label="Temporarily unfit" value={count("temporarily_unfit")} tone="crit" />
        <Stat label="Pending review" value={count("pending_review")} />
      </div>
      {data.map((c) => (
        <Card key={c.id} className="mt-5">
          <CardHeader title={c.name} subtitle={`${c.employer_name} · ${c.screening_type}`} icon={<Briefcase className="size-4" />} />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs tracking-wide text-muted uppercase">
                  <th className="px-4 py-2 font-semibold">Worker</th>
                  <th className="px-4 py-2 font-semibold">Department</th>
                  <th className="px-4 py-2 font-semibold">Status</th>
                  <th className="px-4 py-2 font-semibold">Last screened</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {c.workers.map((w) => (
                  <tr key={w.worker_code}>
                    <td className="px-4 py-2.5 font-mono text-ink">{w.worker_code}</td>
                    <td className="px-4 py-2.5 text-muted">{w.department}</td>
                    <td className="px-4 py-2.5"><Badge tone={STATUS[w.fitness_status].tone}>{STATUS[w.fitness_status].label}</Badge></td>
                    <td className="px-4 py-2.5 text-muted">{w.last_screened_at ? new Date(w.last_screened_at).toLocaleDateString("en-IN") : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ))}
      <p className="mt-4 flex items-center gap-1.5 text-xs text-muted"><ShieldCheck className="size-3.5" /> Every employer view is recorded in the facility audit log.</p>
    </div>
  );
}

export default function EmployerPage() {
  return (
    <RoleGate roles={["employer"]}>
      <AppShell section="Employer" nav={[{ href: "/employer", label: "Fitness cohorts", icon: <Briefcase />, exact: true }]}>
        <EmployerView />
      </AppShell>
    </RoleGate>
  );
}
