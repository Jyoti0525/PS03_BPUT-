"use client";

import { usePrefs } from "@/components/providers";
import { Mic, FileImage, FileText, Clock, CheckCircle2, Hourglass } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync, useNow, fmtDateTime } from "@/lib/hooks";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Card, CardHeader, ErrorNote, Spinner, Stat } from "@/components/ui";

const KIND_ICON = { audio: <Mic className="size-4" />, image: <FileImage className="size-4" />, report: <FileText className="size-4" /> };

export default function RetentionPage() {
  const { tr } = usePrefs();
  const { data, error, reload } = useAsync(() => api.retentionStatus(), [], { pollMs: 60_000 });
  const now = useNow(60_000);
  if (error) return <ErrorNote error={error} onRetry={reload} />;
  if (!data) return <Spinner />;
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title={tr("Data retention")} subtitle={tr("Minimal retention: raw audio and images expire automatically. Structured notes are kept; the raw inputs are not.")} />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label={tr("Raw audio kept for")} value={`${data.policy_hours.audio}h`} hint={tr("deleted after transcript confirmation")} />
        <Stat label={tr("Photos kept for")} value={`${data.policy_hours.image / 24}d`} />
        <Stat label={tr("Reports kept for")} value={`${data.policy_hours.report / 24}d`} />
        <Stat label={tr("Purged (7 days)")} value={data.purged_last_7d} tone="teal" hint={tr("{n} awaiting purge job", { n: data.pending_purge })} />
      </div>
      <Card className="mt-5">
        <CardHeader title={tr("Stored files")} subtitle={tr("Admins see metadata only — never the file contents")} icon={<Clock className="size-4" />} />
        <ul className="divide-y divide-line">
          {data.files.map((f) => {
            const expired = Date.parse(f.expires_at) <= now;
            return (
              <li key={f.id} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm">
                <span className="text-muted">{KIND_ICON[f.kind]}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium text-ink">{f.filename}</span>
                  <span className="text-xs text-subtle">{Math.round(f.size / 1024)} {tr("KB · uploaded")} {fmtDateTime(f.uploaded_at)}</span>
                </span>
                <span className="text-xs text-muted tabular-nums">{tr("expires")} {fmtDateTime(f.expires_at, { dateStyle: "short", timeStyle: "short" })}</span>
                {f.purged_at ? (
                  <Badge tone="rout"><CheckCircle2 className="size-3" /> {tr("Purged")}</Badge>
                ) : expired ? (
                  <Badge tone="semi"><Hourglass className="size-3" /> {tr("Pending purge")}</Badge>
                ) : (
                  <Badge>{tr("Active")}</Badge>
                )}
              </li>
            );
          })}
        </ul>
      </Card>
      <p className="mt-3 text-xs text-muted">{tr("The purge job runs server-side on a schedule and writes a PURGE entry to the audit log for every deleted file.")}</p>
    </div>
  );
}
