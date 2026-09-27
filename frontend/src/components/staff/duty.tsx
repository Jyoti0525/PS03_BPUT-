"use client";

import { Stethoscope, Syringe } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { usePrefs } from "@/components/providers";
import { Badge, Card, CardHeader, Empty, Toggle, cx } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { timeAgo } from "@/lib/hooks";
import type { User } from "@/lib/types";

/** Doctors and nurses with an on-duty switch — the front desk's time-management view. */
export function DutyList({ staff, onChange, compact }: { staff: User[] | null; onChange: () => void; compact?: boolean }) {
  const { tr } = usePrefs();
  const clinicians = (staff ?? []).filter((u) => (u.role === "doctor" || u.role === "nurse") && u.is_active !== false);
  const on = clinicians.filter((u) => u.on_duty !== false);

  async function toggle(u: User, v: boolean) {
    try {
      await api.setDuty(u.id, v);
      toast(tr(v ? "{name} is on duty" : "{name} is off duty", { name: u.name }));
      onChange();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : tr("Could not update"), "error");
    }
  }

  return (
    <Card>
      <CardHeader
        title={tr("Doctors & nurses on duty")}
        subtitle={tr("{on} of {all} on duty now", { on: on.length, all: clinicians.length })}
        icon={<Stethoscope className="size-4" />}
      />
      {!clinicians.length ? (
        <Empty icon={<Stethoscope className="size-6" />} title={tr("No doctors or nurses yet")} body={tr("They appear here once they register at this facility.")} />
      ) : (
        <ul className="divide-y divide-line">
          {clinicians.map((u) => {
            const onDuty = u.on_duty !== false;
            return (
              <li key={u.id} className={cx("flex items-center gap-3 px-4", compact ? "py-2" : "py-3")}>
                <span className={cx("grid size-9 shrink-0 place-items-center rounded-full", onDuty ? "bg-teal-50 text-teal-700" : "bg-canvas text-subtle")}>
                  {u.role === "doctor" ? <Stethoscope className="size-4" /> : <Syringe className="size-4" />}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-ink">{u.name}</p>
                  <p className="text-xs text-muted">
                    {tr(u.role === "doctor" ? "Doctor" : "Nurse")}
                    {u.duty_changed_at && ` · ${tr(onDuty ? "on since" : "off since")} ${timeAgo(u.duty_changed_at)}`}
                  </p>
                </div>
                {!compact && <Badge tone={onDuty ? "rout" : "neutral"}>{tr(onDuty ? "On duty" : "Off duty")}</Badge>}
                <div className="shrink-0">
                  <Toggle checked={onDuty} onChange={(v) => toggle(u, v)} label={<span className="sr-only">{tr("On duty")}</span>} />
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}
