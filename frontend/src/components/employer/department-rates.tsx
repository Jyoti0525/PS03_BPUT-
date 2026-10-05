"use client";

import { BarChart3 } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { usePrefs } from "@/components/providers";
import { Badge, Card, CardHeader, ErrorNote, Spinner } from "@/components/ui";

/** D2: workplace screening by department — counts and shares only. No symptom, name or note ever reaches the employer,
 * and a department with fewer than 5 screened workers is hidden so nobody can be singled out. */
export function DepartmentRates() {
  const { tr } = usePrefs();
  const { data, error, reload } = useAsync(() => api.departmentRates(365), []);
  if (error) return <ErrorNote error={error} onRetry={reload} />;
  if (!data) return <Spinner />;
  return (
    <Card className="mt-5">
      <CardHeader
        title={tr("Workplace screening by department")}
        subtitle={tr("Last 12 months · departments with fewer than {k} screened workers are hidden", { k: data.k_min })}
        icon={<BarChart3 className="size-4" />}
      />
      {!data.departments.length ? (
        <p className="p-4 text-sm text-muted">{tr("No workplace screenings recorded yet.")}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[520px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs tracking-wide text-muted uppercase">
                <th className="px-4 py-2 font-semibold">{tr("Department")}</th>
                <th className="px-4 py-2 font-semibold">{tr("Screened")}</th>
                <th className="px-4 py-2 font-semibold">{tr("Referred for occupational-health review")}</th>
                <th className="px-4 py-2 font-semibold">{tr("Protective-equipment gap")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {data.departments.map((d) => (
                <tr key={d.department}>
                  <td className="px-4 py-2.5 text-ink">{d.department}</td>
                  {d.suppressed ? (
                    <td colSpan={3} className="px-4 py-2.5 text-muted">{tr("Fewer than {k} screened — hidden", { k: data.k_min })}</td>
                  ) : (
                    <>
                      <td className="px-4 py-2.5 tabular-nums">{d.screened}</td>
                      <td className="px-4 py-2.5 tabular-nums">
                        {d.follow_up_pct} %{" "}
                        {d.above_others && <Badge tone="semi">{tr("2× or more the other departments")}</Badge>}
                      </td>
                      <td className="px-4 py-2.5 tabular-nums">{d.ppe_gap_pct} %</td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="border-t border-line px-4 py-2.5 text-xs text-muted">{tr(data.note)}</p>
    </Card>
  );
}
