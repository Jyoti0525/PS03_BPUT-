"use client";

import { useState } from "react";
import { Bot, ShieldCheck, Split } from "lucide-react";
import { usePrefs } from "@/components/providers";
import { api } from "@/lib/api";
import { fmtDateTime, useAsync } from "@/lib/hooks";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Card, CardHeader, ErrorNote, Segmented, Spinner, Stat, cx } from "@/components/ui";
import { UrgencyBadge } from "@/components/triage/note";
import type { Urgency } from "@/lib/types";

const TIERS: Urgency[] = ["red", "yellow", "green"];

/** C8: where the model's second opinion on urgency differed from the rules. Nothing here changed any urgency; it is
 *  for reviewing rules (a model that is often more urgent on one kind of case points at a rule worth checking). */
export default function AiOpinionsPage() {
  const { tr } = usePrefs();
  const [days, setDays] = useState<"7" | "28" | "90">("28");
  const { data, error, reload } = useAsync(() => api.aiOpinions(Number(days)), [days]);
  if (error) return <ErrorNote error={error} onRetry={reload} />;
  if (!data) return <Spinner />;
  const compared = data.counts.AGREE + data.counts.DISAGREE;
  const pct = (n: number) => (compared ? `${Math.round((100 * n) / compared)}%` : "—");

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title={tr("AI second opinions")}
        subtitle={tr("The AI model's own urgency for each case, compared with the rules. It never changed any urgency: use this to review rules, not patients.")}
        actions={<Segmented value={days} onChange={setDays} options={[{ value: "7", label: tr("7 days") }, { value: "28", label: tr("28 days") }, { value: "90", label: tr("90 days") }]} />}
      />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={tr("Compared")} value={compared} hint={tr("{n} cases in this period", { n: data.encounters })} />
        <Stat label={tr("Agreed")} value={pct(data.counts.AGREE)} tone="rout" hint={`${data.counts.AGREE} / ${compared}`} />
        <Stat label={tr("AI more urgent")} value={data.higher} tone="semi" hint={tr("flagged for a second look")} />
        <Stat label={tr("AI less urgent")} value={data.lower} tone="teal" hint={tr("shown only; the rules stand")} />
      </div>
      {data.counts.UNAVAILABLE + data.counts.UNREADABLE > 0 && (
        <p className="mt-2 text-xs text-subtle">
          {tr("No opinion for {n} case(s): model not available or answer unreadable.", { n: data.counts.UNAVAILABLE + data.counts.UNREADABLE })}
        </p>
      )}

      <Card className="mt-4 overflow-x-auto">
        <CardHeader title={tr("Rules vs AI model")} subtitle={tr("Rows: the rules' urgency. Columns: the AI model's. The diagonal is agreement.")} icon={<Split className="size-4" />} />
        <table className="w-full min-w-[420px] text-sm">
          <thead>
            <tr className="text-left text-xs text-muted">
              <th className="px-4 py-2 font-medium">{tr("Rules")} ↓ / {tr("AI model")} →</th>
              {TIERS.map((m) => <th key={m} className="px-3 py-2 text-right font-medium"><UrgencyBadge u={m} size="sm" /></th>)}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {TIERS.map((r) => (
              <tr key={r}>
                <td className="px-4 py-2"><UrgencyBadge u={r} size="sm" /></td>
                {TIERS.map((m) => (
                  <td key={m} className={cx("px-3 py-2 text-right tabular-nums", r === m ? "bg-rout-bg font-semibold text-rout" : data.matrix[r][m] ? "font-semibold text-ink" : "text-subtle")}>
                    {data.matrix[r][m]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card className="mt-4">
        <CardHeader title={tr("Cases where they differed")} subtitle={tr("Newest first. Final urgency is what the case ended with, after any doctor's override.")} icon={<Bot className="size-4" />} />
        {data.cases.length ? (
          <ul className="divide-y divide-line">
            {data.cases.map((c) => (
              <li key={c.encounter_id} className="px-4 py-3 text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-xs text-ink">{c.patient_code}</span>
                  <span className="text-xs text-subtle">{fmtDateTime(c.created_at)}</span>
                  <span className="flex items-center gap-1 text-xs text-muted">{tr("Rules")} <UrgencyBadge u={c.rules_urgency} size="sm" /></span>
                  <span className="flex items-center gap-1 text-xs text-muted">{tr("AI model")} <UrgencyBadge u={c.model_urgency} size="sm" /></span>
                  <Badge tone={c.direction === "higher" ? "semi" : "neutral"}>{tr(c.direction === "higher" ? "AI more urgent" : "AI less urgent")}</Badge>
                  <span className="ml-auto flex items-center gap-1 text-xs text-muted">
                    {tr("Final")} <UrgencyBadge u={c.final_urgency} size="sm" />
                    {c.overridden && <Badge tone="crit">{tr("doctor override")}</Badge>}
                  </span>
                </div>
                {c.reason ? (
                  <p className="mt-1.5 text-ink-2">“{c.reason}”</p>
                ) : (
                  <p className="mt-1.5 text-xs text-subtle">{tr(c.reason_withheld ? "Reason hidden: it failed the safety checks" : "No reason given")}</p>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="px-4 py-3 text-sm text-muted">{tr("No disagreements in this period")}</p>
        )}
      </Card>

      <p className="mt-3 flex items-center gap-2 text-xs text-subtle">
        <ShieldCheck className="size-3.5" />
        {tr("Model")}: {data.model?.split(" (")[0] ?? "—"} · {tr("Each opening of this page is written to the audit log.")}
      </p>
    </div>
  );
}
