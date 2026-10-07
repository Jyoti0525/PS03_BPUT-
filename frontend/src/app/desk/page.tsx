"use client";

import { CLINICIAN_ROLES, DOCTOR_ROLES } from "@/lib/types";

import Link from "next/link";
import { EyeOff, RefreshCw, Tablet, UserPlus } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync, fmtWait } from "@/lib/hooks";
import { usePrefs, useSession } from "@/components/providers";
import { PageHeader } from "@/components/layout/app-shell";
import { Button, Card, Stat } from "@/components/ui";
import { TokenBoard } from "@/components/triage/token-board";
import { DutyList } from "@/components/staff/duty";

/** Receptionist home: who is waiting, for how long, and which doctors and nurses are on duty. Never urgency or symptoms. */
export default function DeskHome() {
  const { user } = useSession();
  const { tr } = usePrefs();
  const fid = user!.facility_id!;
  const { data: tokens, reload: reloadTokens } = useAsync(() => api.facilityTokens(fid), [fid], { pollMs: 15_000 });
  const { data: staff, reload: reloadStaff } = useAsync(() => api.listUsers(), [fid]);
  const { data: facility } = useAsync(() => api.getFacility(fid), [fid]);

  const waiting = tokens?.filter((t) => t.status === "queued" || t.status === "escalated") ?? [];
  const expected = tokens?.filter((t) => t.status === "expected").length ?? 0;
  const withDoctor =tokens?.filter((t) => t.status === "in_review").length ?? 0;
  const seen = tokens?.filter((t) => ["confirmed", "referred", "closed"].includes(t.status)).length ?? 0;
  const avg = waiting.length ? Math.round(waiting.reduce((s, t) => s + t.wait_minutes, 0) / waiting.length) : 0;
  const longest = waiting.reduce((m, t) => Math.max(m, t.wait_minutes), 0);
  const onDuty = staff?.filter((u) => CLINICIAN_ROLES.includes(u.role) && u.on_duty !== false && u.is_active !== false) ?? [];
  const doctorsOn = onDuty.filter((u) => DOCTOR_ROLES.includes(u.role)).length;

  return (
    <>
      <PageHeader
        title={tr("Front desk")}
        subtitle={facility ? tr("{name} · check-ins, waiting times and staff on duty", { name: facility.name }) : undefined}
        actions={
          <Button
            variant="secondary"
            icon={<RefreshCw className="size-4" />}
            onClick={() => {
              reloadTokens();
              reloadStaff();
            }}
          >
            {tr("Refresh")}
          </Button>
        }
      />
      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat
          label={tr("Waiting now")}
          value={waiting.length}
          tone={waiting.length > 10 ? "semi" : undefined}
          hint={expected ? tr("{n} expected from home", { n: expected }) : undefined}
        />
        <Stat label={tr("With doctor")} value={withDoctor} />
        <Stat label={tr("Seen today")} value={seen} tone="rout" />
        <Stat label={tr("Average wait")} value={fmtWait(avg)} hint={tr("Longest: {w}", { w: fmtWait(longest) })} tone={avg > 45 ? "crit" : undefined} />
        <Stat label={tr("Doctors on duty")} value={doctorsOn} tone={doctorsOn ? "teal" : "crit"} hint={tr("{n} clinicians in total", { n: onDuty.length })} />
      </div>
      {doctorsOn === 0 && staff && (
        <div className="mb-4 rounded-xl border border-crit/30 bg-crit-bg px-4 py-3 text-sm font-medium text-crit">{tr("No doctor is marked on duty. Update the duty list so patients are not kept waiting.")}</div>
      )}
      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <TokenBoard facilityId={fid} onChange={reloadTokens} />
        <div className="space-y-4">
          <DutyList staff={staff ?? null} onChange={reloadStaff} compact />
          <Card className="p-4">
            <p className="font-semibold text-ink">{tr("Check in a patient")}</p>
            <p className="mt-1 text-sm text-muted">{tr("Find a returning patient or register a new one, then take them through the check-in kiosk for a token.")}</p>
            <div className="mt-3 grid gap-2">
              <Link href="/desk/patients">
                <Button className="w-full" icon={<UserPlus className="size-4" />}>{tr("Find or register a patient")}</Button>
              </Link>
              <Link href="/kiosk">
                <Button className="w-full" variant="secondary" icon={<Tablet className="size-4" />}>{tr("Open check-in kiosk")}</Button>
              </Link>
            </div>
          </Card>
          <Card className="p-4">
            <div className="flex items-start gap-3">
              <EyeOff className="mt-0.5 size-5 text-coral-600" />
              <p className="text-sm text-muted">{tr("The front desk sees names, tokens, waiting time and status only — never symptoms, urgency, notes or documents.")}</p>
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}
