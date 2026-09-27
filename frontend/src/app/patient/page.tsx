"use client";

import Link from "next/link";
import { QRCodeSVG } from "qrcode.react";
import { PlusCircle, CalendarClock, MessageSquareText, PhoneCall, CheckCircle2, Hourglass, Send, FileText, Info } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync, timeAgo } from "@/lib/hooks";
import { usePrefs } from "@/components/providers";
import { Badge, Button, Card, CardHeader, Empty, ErrorNote, Spinner } from "@/components/ui";
import type { Encounter } from "@/lib/types";

function StatusBadge({ e }: { e: Encounter }) {
  const { tr, t } = usePrefs();
  // Patients see workflow status only — never urgency or the AI note.
  if (e.status === "referred") return <Badge tone="info"><Send className="size-3" /> {tr("Referred")}</Badge>;
  if (["confirmed", "closed"].includes(e.status)) return <Badge tone="rout"><CheckCircle2 className="size-3" /> {t("patient.reviewed")}</Badge>;
  return <Badge tone="neutral"><Hourglass className="size-3" /> {t("patient.waiting")}</Badge>;
}

export default function PatientHome() {
  const { tr, t } = usePrefs();
  const { data, error, loading, reload } = useAsync(() => api.myRecord(), []);
  if (error) return <ErrorNote error={error} onRetry={reload} />;
  if (loading || !data) return <Spinner />;
  const { patient, encounters, reminders } = data;
  const upcoming = reminders.filter((r) => r.status === "scheduled").sort((a, b) => a.due_at.localeCompare(b.due_at));

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center gap-5 bg-gradient-to-r from-teal-50 to-coral-50 p-5">
          <div className="flex-1">
            <p className="text-sm text-muted">{t("patient.home")}</p>
            <h1 className="text-2xl font-bold text-ink">{patient.name}</h1>
            <p className="text-sm text-muted">{patient.age} y · {patient.code} · {patient.category === "maternal" ? tr("Pregnancy care") : patient.category === "chronic" ? tr("Long-term care") : tr("General")}</p>
            <Link href="/patient/new">
              <Button size="xl" variant="teal" className="mt-4" icon={<PlusCircle className="size-6" />}>{t("patient.newProblem")}</Button>
            </Link>
          </div>
          <div className="rounded-2xl bg-white p-3 text-center shadow-sm">
            <QRCodeSVG value={`jeevia:${patient.code}`} size={112} />
            <p className="mt-1 text-[11px] text-muted">{tr("Show at the counter")}</p>
          </div>
        </div>
        <p className="flex items-start gap-2 border-t border-line px-5 py-3 text-sm text-muted">
          <Info className="mt-0.5 size-4 shrink-0 text-teal-700" /> {t("patient.note")}
        </p>
      </Card>

      {upcoming.length > 0 && (
        <Card>
          <CardHeader title={t("patient.reminders")} subtitle={tr("Sent automatically by SMS or a voice call in your language")} icon={<CalendarClock className="size-4" />} />
          <ul className="divide-y divide-line">
            {upcoming.map((r) => (
              <li key={r.id} className="flex items-center gap-3 px-4 py-3">
                <span className="grid size-10 place-items-center rounded-xl bg-coral-50 text-coral-700">{r.channel === "sms" ? <MessageSquareText className="size-5" /> : <PhoneCall className="size-5" />}</span>
                <div className="flex-1">
                  <p className="font-medium text-ink">{r.message}</p>
                  <p className="text-sm text-muted">{new Date(r.due_at).toLocaleDateString("en-IN", { weekday: "long", day: "numeric", month: "long" })} · {r.channel.toUpperCase()}</p>
                </div>
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card>
        <CardHeader title={t("patient.visits")} icon={<FileText className="size-4" />} />
        {encounters.length === 0 ? (
          <Empty title={tr("No visits yet")} body={tr("Use “Add a new problem” to tell the health centre what is wrong before you arrive.")} />
        ) : (
          <ul className="divide-y divide-line">
            {encounters.map((e) => (
              <li key={e.id} className="px-4 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="flex-1 font-medium text-ink">{e.chief_complaint}</p>
                  <StatusBadge e={e} />
                </div>
                <p className="mt-0.5 text-sm text-muted">
                  {new Date(e.created_at).toLocaleDateString("en-IN")} · {timeAgo(e.created_at)}
                  {e.reviewed_by && ` · seen by ${e.reviewed_by}`}
                  {!!e.intake?.file_ids.length && ` · ${e.intake.file_ids.length} file(s) shared`}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
