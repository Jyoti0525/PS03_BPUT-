"use client";

import { usePrefs } from "@/components/providers";
import { fmtDateTime, refCode } from "@/lib/hooks";
import { langByCode } from "@/lib/i18n/languages";
import { FileText, Building2, Send, AlertOctagon, AlertTriangle, Info, ExternalLink } from "lucide-react";
import { Badge, Card, CardHeader, cx } from "@/components/ui";
import { UrgencyBadge } from "@/components/triage/note";
import type { SharedSummary } from "@/lib/types";

const SEV = {
  critical: { icon: <AlertOctagon className="size-4 text-crit" />, cls: "border-crit-line bg-crit-bg" },
  warning: { icon: <AlertTriangle className="size-4 text-semi" />, cls: "border-semi-line bg-semi-bg" },
  info: { icon: <Info className="size-4 text-blue-600" />, cls: "border-blue-100 bg-blue-50/60" },
};

/** One referred visit as the receiving clinician sees it: opened from the QR slip, or by a doctor signed in at the
 * facility it was referred to. That visit only; no phone number, village or employer. */
export function ReferredVisit({ data, referralAction, viaLink = false }: { data: SharedSummary; referralAction?: React.ReactNode; viaLink?: boolean }) {
  const { tr } = usePrefs();
  const e = data.encounter;
  const n = data.note;
  return (
    <div className="space-y-4">
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-start gap-4 p-5">
          <div className="grid size-14 place-items-center rounded-2xl bg-coral-100 text-xl font-bold text-coral-700">{data.patient.name.charAt(0)}</div>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              {e?.token && <span className="rounded-lg bg-coral-50 px-2 py-0.5 font-mono text-sm font-bold text-coral-700">{e.token}</span>}
              <h1 className="text-2xl font-bold text-ink">{data.patient.name}</h1>
              <UrgencyBadge u={e?.urgency ?? null} />
              {e?.urgency_source === "override" && <Badge tone="coral">{tr("Clinician override")}</Badge>}
            </div>
            <p className="mt-1 text-sm text-muted">
              {data.patient.age} y · {data.patient.sex} · <span className="font-mono">{data.patient.code}</span> · {tr(langByCode(data.patient.language).name)}
            </p>
            <p className="mt-2 font-medium text-ink">{tr(e?.chief_complaint)}</p>
            <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
              <span className="flex items-center gap-1">
                <Building2 className="size-3.5" /> {data.facility.name}, {data.facility.district}
              </span>
              <span>{tr("Seen")} {e && fmtDateTime(e.created_at)}</span>
              {e?.reviewed_by && <span>{tr("Reviewed by")} {e.reviewed_by}</span>}
              {e?.consent?.mode === "proxy" && <span>{tr("History from")} {e.consent.proxy_relation}</span>}
            </p>
          </div>
        </div>
      </Card>

      {data.referral && (
        <Card>
          <CardHeader title={tr("Suggested destination: {d}", { d: data.referral.destination })} subtitle={`${data.referral.id ? `${refCode(data.referral.id)} · ` : ""}${data.referral.specialty} · ${data.referral.transport.replace(/_/g, " ")} · by ${data.referral.created_by}`} icon={<Send className="size-4" />} />
          <p className="border-b border-line bg-teal-50/60 px-4 py-2 text-sm text-teal-900">{tr("Destination is guidance only. The patient may choose any suitable healthcare facility.")}</p>
          <p className="px-4 pt-3 text-sm text-ink">{tr(data.referral.reason)}</p>
          <div className="mx-4 my-3 rounded-xl border border-line bg-canvas/50 p-3">
            <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">{tr("Referral note from the treating clinician")}</p>
            <pre className="whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-ink">{tr(data.referral.note_text)}</pre>
          </div>
          {referralAction}
        </Card>
      )}

      {n && (
        <>
          <Card>
            <CardHeader title={tr("Summary")} subtitle={tr("Organised from patient-provided information — not a diagnosis")} />
            <p className="px-4 py-3 leading-relaxed text-ink">{tr(n.summary)}</p>
          </Card>
          {n.flags.length > 0 && (
            <Card>
              <CardHeader title={tr("Flags")} />
              <ul className="space-y-1.5 p-4">
                {n.flags.map((f, i) => (
                  <li key={i} className={cx("flex items-start gap-2 rounded-lg border px-2.5 py-2 text-sm", SEV[f.severity].cls)}>
                    {SEV[f.severity].icon}
                    <span className="font-medium text-ink">{tr(f.label)}</span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          <div className="grid gap-4 md:grid-cols-2">
            {[
              { t: "Vitals", rows: n.vitals },
              { t: "Report values", rows: n.labs },
            ].map(
              (g) =>
                g.rows.length > 0 && (
                  <Card key={g.t}>
                    <CardHeader title={tr(g.t)} />
                    <ul className="divide-y divide-line">
                      {g.rows.map((v) => (
                        <li key={v.id} className="flex items-center justify-between gap-3 px-4 py-2 text-sm">
                          <span className="text-muted">{tr(v.label)}</span>
                          <span className={cx("font-semibold tabular-nums", v.status === "abnormal" ? "text-crit" : v.status === "borderline" ? "text-semi" : "text-ink")}>
                            {v.value} {v.unit}
                            {v.needs_check && <Badge tone="semi" className="ml-2">{tr("re-check")}</Badge>}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </Card>
                ),
            )}
          </div>
          {n.missing_info.length > 0 && (
            <Card>
              <CardHeader title={tr("Not yet available")} />
              <ul className="list-disc space-y-1 py-3 pr-4 pl-9 text-sm text-ink">
                {n.missing_info.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}

      <Card>
        <CardHeader title={tr("Uploaded documents")} subtitle={data.documents.length ? tr("Reports and photos from this visit") : tr("No documents were uploaded")} icon={<FileText className="size-4" />} />
        {data.documents.length > 0 && (
          <div className="grid gap-4 p-4 sm:grid-cols-2">
            {data.documents.map((d) => (
              <div key={d.id} className="overflow-hidden rounded-xl border border-line bg-white">
                {d.url ? (
                  d.content_type.startsWith("image/") ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={d.url} alt={d.filename} className="max-h-80 w-full bg-canvas object-contain" />
                  ) : (
                    <div className="grid h-40 place-items-center bg-canvas">
                      <FileText className="size-10 text-subtle" />
                    </div>
                  )
                ) : (
                  <div className="grid h-40 place-items-center bg-canvas text-sm text-muted">{tr("Deleted under retention policy")}</div>
                )}
                <div className="flex items-center justify-between gap-2 px-3 py-2 text-xs">
                  <span className="truncate text-ink">{d.filename}</span>
                  {d.url && (
                    <a href={d.url} target="_blank" rel="noreferrer" className="no-print inline-flex shrink-0 items-center gap-1 font-semibold text-teal-700">
                      {tr("Open")} <ExternalLink className="size-3" />
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <p className="text-center text-xs text-muted">
        {tr("Shared by")} {data.shared_by}{viaLink ? <> {tr("· link valid until")} {fmtDateTime(data.expires_at)}</> : null} · {data.disclaimer}
      </p>
    </div>
  );
}
