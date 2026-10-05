"use client";

import { useState } from "react";
import { EyeOff, ShieldCheck, ChartColumn } from "lucide-react";
import { usePrefs } from "@/components/providers";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Card, CardHeader, ErrorNote, Segmented, Spinner, Stat } from "@/components/ui";
import type { CohortCell } from "@/lib/types";

const LABEL: Record<string, string> = {
  F: "Female", M: "Male", O: "Other / not stated",
  normal: "General", maternal: "Maternal", chronic: "Chronic",
  red: "Red", yellow: "Yellow", green: "Green",
};

/** Counts only. `null` = 1–4 cases, shown as "<5" so nobody in a small group can be picked out. */
function Count({ c }: { c: number | null }) {
  return c === null ? <span className="text-subtle" title="1–4 cases, hidden">&lt;5</span> : <span>{c}</span>;
}

function Table({ title, cells }: { title: string; cells: CohortCell[] }) {
  const { tr } = usePrefs();
  return (
    <Card>
      <CardHeader title={tr(title)} />
      <ul className="divide-y divide-line">
        {cells.map((x) => (
          <li key={x.key} className="flex items-center justify-between px-4 py-2 text-sm">
            <span className="text-ink">{tr(LABEL[x.key] ?? x.key)}</span>
            <span className="font-semibold tabular-nums"><Count c={x.count} /></span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

export default function CohortPage() {
  const { tr } = usePrefs();
  const [days, setDays] = useState<"14" | "28" | "90">("28");
  const { data, error, reload } = useAsync(() => api.deidentifiedCohort(Number(days)), [days]);
  if (error) return <ErrorNote error={error} onRetry={reload} />;
  if (!data) return <Spinner />;
  const urg = Object.fromEntries(data.by_urgency.map((x) => [x.key, x.count])) as Record<string, number | null>; // null = 1–4, never shown as 0
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title={tr("De-identified cohort")}
        subtitle={tr("Counts for planning and outbreak watch. Nobody can be identified here: no names, IDs, phone numbers, villages, exact ages, times or free text.")}
        actions={<Segmented value={days} onChange={setDays} options={[{ value: "14", label: tr("14 days") }, { value: "28", label: tr("28 days") }, { value: "90", label: tr("90 days") }]} />}
      />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={tr("Cases")} value={<Count c={data.total} />} />
        <Stat label={tr("Red")} value={<Count c={urg.red} />} tone="crit" />
        <Stat label={tr("Yellow")} value={<Count c={urg.yellow} />} tone="semi" />
        <Stat label={tr("Hidden small counts")} value={data.suppressed_cells} tone="teal" hint={tr("counts of 1–4 show as <5")} />
      </div>

      <div className="mt-5 grid gap-4 md:grid-cols-3">
        <Table title="Age band" cells={data.by_age_band} />
        <Table title="Sex" cells={data.by_sex} />
        <Table title="Visit type" cells={data.by_category} />
      </div>

      <Card className="mt-4 overflow-x-auto">
        <CardHeader title={tr("Urgency by age band")} icon={<ChartColumn className="size-4" />} />
        <table className="w-full min-w-[520px] text-sm">
          <thead>
            <tr className="text-left text-xs text-muted">
              <th className="px-4 py-2 font-medium">{tr("Urgency")}</th>
              {data.by_age_band.map((b) => <th key={b.key} className="px-3 py-2 text-right font-medium">{b.key}</th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {data.urgency_by_age_band.map((r) => (
              <tr key={r.urgency}>
                <td className="px-4 py-2"><Badge tone={r.urgency === "red" ? "crit" : r.urgency === "yellow" ? "semi" : "rout"}>{tr(LABEL[r.urgency])}</Badge></td>
                {r.cells.map((c) => <td key={c.key} className="px-3 py-2 text-right tabular-nums"><Count c={c.count} /></td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <div className="mt-4 grid gap-4 md:grid-cols-2">
        <Table title="Cases per week" cells={data.by_week} />
        <Card>
          <CardHeader title={tr("Most reported findings")} subtitle={tr("From the rules engine's findings, not diagnoses")} />
          {data.findings.length ? (
            <ul className="divide-y divide-line">
              {data.findings.map((f) => (
                <li key={f.key} className="flex items-center justify-between px-4 py-2 text-sm">
                  <span className="text-ink">{tr(f.label)}</span>
                  <span className="font-semibold tabular-nums"><Count c={f.count} /></span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-4 py-3 text-sm text-muted">{tr("No findings in this period")}</p>
          )}
        </Card>
      </div>

      <Card className="mt-4 px-4 py-3 text-sm">
        <p className="flex items-center gap-2 font-medium text-ink"><EyeOff className="size-4" /> {tr("Removed from this view")}</p>
        <p className="mt-1 text-muted">{data.removed_fields.map((f) => tr(f)).join(" · ")}</p>
        <p className="mt-2 flex items-center gap-2 text-xs text-subtle"><ShieldCheck className="size-3.5" /> {tr("Each opening of this page is written to the audit log.")}</p>
      </Card>
    </div>
  );
}
