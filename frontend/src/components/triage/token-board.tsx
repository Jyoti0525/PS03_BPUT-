"use client";

import { usePrefs } from "@/components/providers";
import Link from "next/link";
import { useState } from "react";
import { Link2, Tablet, UserRound, Ticket, Pencil, House, CheckCircle2, Search } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "@/components/ui/toast";
import { PatientEditModal } from "./patient-edit";
import { useAsync, fmtWait, timeAgo } from "@/lib/hooks";
import { Badge, Button, Card, CardHeader, Empty, Input } from "@/components/ui";
import type { EncounterStatus, IntakeChannel, Patient, TokenBoardItem } from "@/lib/types";

const STATUS: Record<EncounterStatus, { label: string; tone: "neutral" | "info" | "rout" | "crit" | "teal" }> = {
  queued: { label: "Waiting", tone: "neutral" },
  in_review: { label: "With doctor", tone: "info" },
  escalated: { label: "Escalated", tone: "crit" },
  confirmed: { label: "Seen", tone: "rout" },
  referred: { label: "Referred", tone: "teal" },
  closed: { label: "Closed", tone: "rout" },
  expected: { label: "Expected", tone: "info" },
  lapsed: { label: "Did not come", tone: "neutral" },
};

const CHANNEL: Record<IntakeChannel, { label: string; icon: React.ReactNode }> = {
  kiosk_link: { label: "Kiosk link", icon: <Link2 className="size-3" /> },
  staff_kiosk: { label: "Staff kiosk", icon: <Tablet className="size-3" /> },
  home_link: { label: "From home", icon: <House className="size-3" /> },
  patient_app: { label: "Patient app", icon: <UserRound className="size-3" /> },
};

/** Today's tokens for the front desk. Names and status only — never symptoms or urgency. */
export function TokenBoard({ facilityId, linkToCase, onChange }: { facilityId: string; linkToCase?: boolean; onChange?: () => void }) {
  const { tr } = usePrefs();
  const { data, reload } = useAsync(() => api.facilityTokens(facilityId), [facilityId], { pollMs: 10_000 });
  const [editing, setEditing] = useState<Patient | null>(null);
  const [find, setFind] = useState("");
  const [arriving, setArriving] = useState<string | null>(null);
  const expected = (data ?? []).filter((t) => t.status === "expected");
  const today = (data ?? []).filter((t) => t.status !== "expected" && t.status !== "lapsed");
  const q = find.trim().toLowerCase();
  const shown = q ? expected.filter((t) => [t.token, t.patient_name, t.patient_code].some((x) => x?.toLowerCase().includes(q))) : expected;
  const checkIn = async (t: TokenBoardItem) => {
    setArriving(t.encounter_id);
    try {
      const e = await api.checkIn(t.encounter_id);
      toast(tr("{name} checked in — token {token}", { name: t.patient_name, token: e.token ?? "" }));
      setFind("");
      reload();
      onChange?.();
    } catch (err) {
      toast(err instanceof Error ? err.message : tr("Failed"), "error");
    } finally {
      setArriving(null);
    }
  };
  const edit = async (pid: string) => {
    try {
      setEditing(await api.getPatient(pid));
    } catch (e) {
      toast(e instanceof Error ? e.message : tr("Could not open patient"), "error");
    }
  };
  return (
    <div className="min-w-0">
    {expected.length > 0 && (
      <Card className="mb-4">
        <CardHeader
          title={tr("Expected — filled in from home")}
          subtitle={tr("Check them in when they reach the desk. Their place in the queue starts then, so filling in early never puts anyone ahead of people already waiting.")}
          icon={<House className="size-4" />}
          action={<Badge tone="info">{expected.length}</Badge>}
        />
        {expected.length > 4 && (
          <div className="relative px-4 pb-2">
            <Search className="pointer-events-none absolute top-1/2 left-7 size-4 -translate-y-1/2 text-subtle" />
            <Input value={find} onChange={(e) => setFind(e.target.value)} placeholder={tr("H- number, name or patient ID")} className="pl-9" aria-label={tr("Find an expected patient")} />
          </div>
        )}
        <ul className="max-h-[300px] divide-y divide-line overflow-y-auto">
          {shown.map((t) => (
            <li key={t.encounter_id} className="flex items-center gap-3 px-4 py-2.5">
              <span className="w-16 shrink-0 rounded-lg bg-canvas py-1 text-center font-mono text-sm font-bold text-ink-2">{t.token ?? "—"}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-ink">{t.patient_name}</p>
                <p className="text-xs text-muted">
                  <span className="font-mono">{t.patient_code}</span> · {tr("sent {t}", { t: timeAgo(t.created_at) })}
                </p>
              </div>
              <Button size="sm" variant="teal" loading={arriving === t.encounter_id} icon={<CheckCircle2 className="size-4" />} onClick={() => checkIn(t)}>
                {tr("Checked in")}
              </Button>
            </li>
          ))}
          {shown.length === 0 && <li className="px-4 py-3 text-sm text-muted">{tr("No match")}</li>}
        </ul>
      </Card>
    )}
    <Card>
      <CardHeader title={tr("Today's tokens")} subtitle={tr("Updates every 10 seconds · includes kiosk-link check-ins")} icon={<Ticket className="size-4" />} action={<Badge tone="coral">{today.length} {tr("today")}</Badge>} />
      {!data ? (
        <p className="px-4 py-6 text-sm text-muted">{tr("Loading…")}</p>
      ) : today.length === 0 ? (
        <Empty icon={<Ticket className="size-6" />} title={tr("No tokens yet today")} body={tr("Tokens appear here the moment someone checks in.")} />
      ) : (
        <ul className="max-h-[420px] divide-y divide-line overflow-y-auto">
          {today.map((t) => {
            const row = (
              <div className="flex items-center gap-3 px-4 py-2.5">
                <span className="w-16 shrink-0 rounded-lg bg-coral-50 py-1 text-center font-mono text-sm font-bold text-coral-700">{t.token ?? "—"}</span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-ink">{t.patient_name}</p>
                  <p className="flex items-center gap-1 text-xs text-muted">
                    {CHANNEL[t.channel].icon} {tr(CHANNEL[t.channel].label)} · <span className="font-mono">{t.patient_code}</span>
                  </p>
                </div>
                <span className="text-xs text-subtle tabular-nums">{fmtWait(t.wait_minutes)}</span>
                <Badge tone={STATUS[t.status].tone}>{tr(STATUS[t.status].label)}</Badge>
              </div>
            );
            return (
              <li key={t.encounter_id} className="flex items-center">
                <div className="min-w-0 flex-1">{linkToCase ? <Link href={`/reviewer/case/${t.encounter_id}`} className="block hover:bg-canvas">{row}</Link> : row}</div>
                <button onClick={() => edit(t.patient_id)} className="mr-2 rounded-lg p-2 text-subtle hover:bg-canvas hover:text-ink" aria-label={`Edit details for ${t.patient_name}`} title={tr("Correct patient details")}>
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
    </div>
  );
}
