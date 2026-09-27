"use client";

import Link from "next/link";
import { useState } from "react";
import { Link2, Tablet, UserRound, Ticket, Pencil } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "@/components/ui/toast";
import { PatientEditModal } from "./patient-edit";
import { useAsync, fmtWait } from "@/lib/hooks";
import { Badge, Card, CardHeader, Empty } from "@/components/ui";
import type { EncounterStatus, IntakeChannel, Patient } from "@/lib/types";

const STATUS: Record<EncounterStatus, { label: string; tone: "neutral" | "info" | "rout" | "crit" | "teal" }> = {
  queued: { label: "Waiting", tone: "neutral" },
  in_review: { label: "With doctor", tone: "info" },
  escalated: { label: "Escalated", tone: "crit" },
  confirmed: { label: "Seen", tone: "rout" },
  referred: { label: "Referred", tone: "teal" },
  closed: { label: "Closed", tone: "rout" },
};

const CHANNEL: Record<IntakeChannel, { label: string; icon: React.ReactNode }> = {
  kiosk_link: { label: "Kiosk link", icon: <Link2 className="size-3" /> },
  staff_kiosk: { label: "Staff kiosk", icon: <Tablet className="size-3" /> },
  patient_app: { label: "Patient app", icon: <UserRound className="size-3" /> },
};

/** Today's tokens for the front desk. Names and status only — never symptoms or urgency. */
export function TokenBoard({ facilityId, linkToCase }: { facilityId: string; linkToCase?: boolean }) {
  const { data, reload } = useAsync(() => api.facilityTokens(facilityId), [facilityId], { pollMs: 10_000 });
  const [editing, setEditing] = useState<Patient | null>(null);
  const edit = async (pid: string) => {
    try {
      setEditing(await api.getPatient(pid));
    } catch (e) {
      toast(e instanceof Error ? e.message : "Could not open patient", "error");
    }
  };
  return (
    <Card>
      <CardHeader title="Today's tokens" subtitle="Updates every 10 seconds · includes kiosk-link check-ins" icon={<Ticket className="size-4" />} action={<Badge tone="coral">{data?.length ?? 0} today</Badge>} />
      {!data ? (
        <p className="px-4 py-6 text-sm text-muted">Loading…</p>
      ) : data.length === 0 ? (
        <Empty icon={<Ticket className="size-6" />} title="No tokens yet today" body="Tokens appear here the moment someone checks in." />
      ) : (
        <ul className="max-h-[420px] divide-y divide-line overflow-y-auto">
          {data.map((t) => {
            const row = (
              <div className="flex items-center gap-3 px-4 py-2.5">
                <span className="w-16 shrink-0 rounded-lg bg-coral-50 py-1 text-center font-mono text-sm font-bold text-coral-700">{t.token ?? "—"}</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-ink">{t.patient_name}</p>
                  <p className="flex items-center gap-1 text-xs text-muted">
                    {CHANNEL[t.channel].icon} {CHANNEL[t.channel].label} · <span className="font-mono">{t.patient_code}</span>
                  </p>
                </div>
                <span className="text-xs text-subtle tabular-nums">{fmtWait(t.wait_minutes)}</span>
                <Badge tone={STATUS[t.status].tone}>{STATUS[t.status].label}</Badge>
              </div>
            );
            return (
              <li key={t.encounter_id} className="flex items-center">
                <div className="min-w-0 flex-1">{linkToCase ? <Link href={`/reviewer/case/${t.encounter_id}`} className="block hover:bg-canvas">{row}</Link> : row}</div>
                <button onClick={() => edit(t.patient_id)} className="mr-2 rounded-lg p-2 text-subtle hover:bg-canvas hover:text-ink" aria-label={`Edit details for ${t.patient_name}`} title="Correct patient details">
                  <Pencil className="size-4" />
                </button>
              </li>
            );
          })}
        </ul>
      )}
      {editing && (
        <PatientEditModal
          patient={editing}
          onClose={() => setEditing(null)}
          onDone={() => {
            setEditing(null);
            reload();
          }}
        />
      )}
    </Card>
  );
}
