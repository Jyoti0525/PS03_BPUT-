"use client";

import { useState } from "react";
import { ShieldAlert, ShieldCheck } from "lucide-react";
import { usePrefs } from "@/components/providers";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { PageHeader } from "@/components/layout/app-shell";
import { Card, CardHeader, ErrorNote, Segmented, Spinner, Stat, cx } from "@/components/ui";
import { UrgencyBadge } from "@/components/triage/note";

/** E9: how often clinicians changed the rules' urgency, per rule. A rule that doctors often lower is a rule to review;
 *  the rules' own output is never rewritten by an override. */
export default function OverridesPage() {
  const { tr } = usePrefs();
  const [days, setDays] = useState<"7" | "28" | "90">("28");
  const { data, error, reload } = useAsync(() => api.overrideStats(Number(days)), [days]);
  if (error) return <ErrorNote error={error} onRetry={reload} />;
  if (!data) return <Spinner />;
  const pct = (x: number) => `${Math.round(100 * x)}%`;

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        title={tr("Urgency overrides")}
        subtitle={tr("Any reviewer can raise a case's urgency; only a doctor can lower it, with a written reason. The rules' own output is kept on every case.")}
        actions={<Segmented value={days} onChange={setDays} options={[{ value: "7", label: tr("7 days") }, { value: "28", label: tr("28 days") }, { value: "90", label: tr("90 days") }]} />}
      />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={tr("Cases")} value={data.encounters} hint={tr("{n} days", { n: data.days })} />
        <Stat label={tr("Overrides")} value={data.overrides} hint={data.encounters ? pct(data.overrides / data.encounters) : "—"} />
        <Stat label={tr("Raised")} value={data.raised} tone="semi" hint={tr("any reviewer")} />
        <Stat label={tr("Lowered")} value={data.lowered} tone="teal" hint={tr("doctor, with a reason")} />
      </div>

      <Card className="mt-4 overflow-x-auto">
        <CardHeader title={tr("Override rate per rule")} subtitle={tr("Most often lowered first. A high rate points at a rule worth reviewing.")} icon={<ShieldAlert className="size-4" />} />
        {data.rules.length ? (
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th className="px-4 py-2 font-medium">{tr("Rule")}</th>
                <th className="px-3 py-2 text-right font-medium">{tr("Fired")}</th>
                <th className="px-3 py-2 text-right font-medium">{tr("Lowered")}</th>
                <th className="px-3 py-2 text-right font-medium">{tr("Raised")}</th>
                <th className="px-3 py-2 text-right font-medium">{tr("Lowered rate")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.rules.map((r) => (
                <tr key={r.rule_id}>
                  <td className="px-4 py-2">
                    <div className="flex items-center gap-2">
                      <UrgencyBadge u={r.urgency} size="sm" />
                      <span className="font-mono text-xs text-ink">{r.rule_id}</span>
                    </div>
                    <p className="mt-0.5 text-xs text-muted">{tr(r.description)}</p>
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{r.fired}</td>
                  <td className={cx("px-3 py-2 text-right tabular-nums", r.lowered ? "font-semibold text-ink" : "text-subtle")}>{r.lowered}</td>
                  <td className={cx("px-3 py-2 text-right tabular-nums", r.raised ? "font-semibold text-ink" : "text-subtle")}>{r.raised}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{pct(r.lowered_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="px-4 py-3 text-sm text-muted">{tr("No rules fired in this period")}</p>
        )}
      </Card>

      <p className="mt-3 flex items-center gap-2 text-xs text-subtle">
        <ShieldCheck className="size-3.5" />
        {tr("Each opening of this page is written to the audit log.")}
      </p>
    </div>
  );
}
