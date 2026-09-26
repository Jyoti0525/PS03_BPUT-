"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { KeyRound, Printer, FileText, Building2, Clock, Send, AlertOctagon, AlertTriangle, Info, Lock, ExternalLink } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Logo, LanguageButton } from "@/components/layout/chrome";
import { Badge, Button, Card, CardHeader, Input, Spinner, cx } from "@/components/ui";
import { UrgencyBadge } from "@/components/triage/note";
import type { SharedSummary } from "@/lib/types";

const SEV = {
  critical: { icon: <AlertOctagon className="size-4 text-crit" />, cls: "border-crit-line bg-crit-bg" },
  warning: { icon: <AlertTriangle className="size-4 text-semi" />, cls: "border-semi-line bg-semi-bg" },
  info: { icon: <Info className="size-4 text-blue-600" />, cls: "border-blue-100 bg-blue-50/60" },
};

/** Opened by scanning a referral QR. Clinician-facing; requires the access code printed beside the QR. */
export default function SharedSummaryPage() {
  const { token } = useParams<{ token: string }>();
  const [meta, setMeta] = useState<{ facility_name: string; expires_at: string } | null>(null);
  const [metaErr, setMetaErr] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [data, setData] = useState<SharedSummary | null>(null);

  useEffect(() => {
    api.shareMeta(token).then(setMeta).catch((e) => setMetaErr(e instanceof Error ? e.message : "Link not valid"));
  }, [token]);

  const open = async () => {
    setErr(null);
    if (!/^\d{6}$/.test(code)) return setErr("Enter the 6-digit access code printed next to the QR");
    setBusy(true);
    try {
      setData(await api.openShare(token, code));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not open");
    } finally {
      setBusy(false);
    }
  };

  const e = data?.encounter;
  const n = data?.note;

  return (
    <div className="min-h-[calc(100vh-28px)] bg-canvas">
      <header className="no-print border-b border-line bg-white">
        <div className="mx-auto flex h-16 max-w-4xl items-center gap-3 px-4">
          <Logo />
          <span className="hidden text-sm text-muted sm:inline">Referral summary</span>
          <div className="ml-auto flex items-center gap-2">
            {data && (
              <Button variant="secondary" size="sm" icon={<Printer className="size-4" />} onClick={() => window.print()}>
                Print
              </Button>
            )}
            <LanguageButton compact />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-4 py-8">
        {metaErr ? (
          <Card className="mx-auto max-w-md p-8 text-center">
            <Lock className="mx-auto size-10 text-subtle" />
            <p className="mt-3 text-xl font-bold text-ink">Summary not available</p>
            <p className="mt-2 text-muted">{metaErr}</p>
          </Card>
        ) : !meta ? (
          <Spinner label="Checking link…" />
        ) : !data ? (
          <Card className="mx-auto max-w-md p-7">
            <span className="grid size-12 place-items-center rounded-2xl bg-coral-50 text-coral-500">
              <KeyRound className="size-6" />
            </span>
            <h1 className="mt-4 text-2xl font-bold text-ink">Enter access code</h1>
            <p className="mt-1 text-muted">
              Patient summary shared by <strong className="text-ink">{meta.facility_name}</strong>. The 6-digit code is printed beside the QR on the referral slip.
            </p>
            <Input
              autoFocus
              inputMode="numeric"
              value={code}
              onChange={(ev) => setCode(ev.target.value.replace(/\D/g, "").slice(0, 6))}
              onKeyDown={(ev) => ev.key === "Enter" && open()}
              className="mt-5 h-14 text-center font-mono text-2xl tracking-[0.4em]"
              aria-label="Access code"
              placeholder="••••••"
            />
            {err && <p className="mt-2 text-sm font-medium text-crit">{err}</p>}
            <Button size="lg" className="mt-4 w-full" loading={busy} onClick={open}>
              Open summary
            </Button>
            <p className="mt-4 flex items-center gap-1.5 text-xs text-subtle">
              <Clock className="size-3.5" /> Link valid until {new Date(meta.expires_at).toLocaleString("en-IN")}. Every opening is logged.
            </p>
          </Card>
        ) : (
          <div className="space-y-4">
            <Card className="overflow-hidden">
              <div className="flex flex-wrap items-start gap-4 p-5">
                <div className="grid size-14 place-items-center rounded-2xl bg-coral-100 text-xl font-bold text-coral-700">{data.patient.name.charAt(0)}</div>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    {e?.token && <span className="rounded-lg bg-coral-50 px-2 py-0.5 font-mono text-sm font-bold text-coral-700">{e.token}</span>}
                    <h1 className="text-2xl font-bold text-ink">{data.patient.name}</h1>
                    <UrgencyBadge u={e?.urgency ?? null} />
                    {e?.urgency_source === "override" && <Badge tone="coral">Clinician override</Badge>}
                  </div>
                  <p className="mt-1 text-sm text-muted">
                    {data.patient.age} y · {data.patient.sex} · <span className="font-mono">{data.patient.code}</span> · language {data.patient.language}
                    {data.patient.phone && ` · +91 ${data.patient.phone}`}
                  </p>
                  <p className="mt-2 font-medium text-ink">{e?.chief_complaint}</p>
                  <p className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted">
                    <span className="flex items-center gap-1">
                      <Building2 className="size-3.5" /> {data.facility.name}, {data.facility.district}
                    </span>
                    <span>Seen {e && new Date(e.created_at).toLocaleString("en-IN")}</span>
                    {e?.reviewed_by && <span>Reviewed by {e.reviewed_by}</span>}
                    {e?.consent?.mode === "proxy" && <span>History from {e.consent.proxy_name} ({e.consent.proxy_relation})</span>}
                  </p>
                </div>
              </div>
            </Card>

            {data.referral && (
              <Card>
                <CardHeader title={`Referred to ${data.referral.destination}`} subtitle={`${data.referral.specialty} · ${data.referral.transport.replace(/_/g, " ")} · by ${data.referral.created_by}`} icon={<Send className="size-4" />} />
                <p className="px-4 py-3 text-sm text-ink">{data.referral.reason}</p>
              </Card>
            )}

            {n && (
              <>
                <Card>
                  <CardHeader title="Summary" subtitle="Organised from patient-provided information — not a diagnosis" />
                  <p className="px-4 py-3 leading-relaxed text-ink">{n.summary}</p>
                </Card>
                {n.flags.length > 0 && (
                  <Card>
                    <CardHeader title="Flags" />
                    <ul className="space-y-1.5 p-4">
                      {n.flags.map((f, i) => (
                        <li key={i} className={cx("flex items-start gap-2 rounded-lg border px-2.5 py-2 text-sm", SEV[f.severity].cls)}>
                          {SEV[f.severity].icon}
                          <span className="font-medium text-ink">{f.label}</span>
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
                          <CardHeader title={g.t} />
                          <ul className="divide-y divide-line">
                            {g.rows.map((v) => (
                              <li key={v.id} className="flex items-center justify-between gap-3 px-4 py-2 text-sm">
                                <span className="text-muted">{v.label}</span>
                                <span className={cx("font-semibold tabular-nums", v.status === "abnormal" ? "text-crit" : v.status === "borderline" ? "text-semi" : "text-ink")}>
                                  {v.value} {v.unit}
                                  {v.needs_check && <Badge tone="semi" className="ml-2">re-check</Badge>}
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
                    <CardHeader title="Not yet available" />
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
              <CardHeader title="Uploaded documents" subtitle={data.documents.length ? "Reports and photos from this visit" : "No documents were uploaded"} icon={<FileText className="size-4" />} />
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
                        <div className="grid h-40 place-items-center bg-canvas text-sm text-muted">Deleted under retention policy</div>
                      )}
                      <div className="flex items-center justify-between gap-2 px-3 py-2 text-xs">
                        <span className="truncate text-ink">{d.filename}</span>
                        {d.url && (
                          <a href={d.url} target="_blank" rel="noreferrer" className="no-print inline-flex shrink-0 items-center gap-1 font-semibold text-teal-700">
                            Open <ExternalLink className="size-3" />
                          </a>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Card>

            <p className="text-center text-xs text-muted">
              Shared by {data.shared_by} · link valid until {new Date(data.expires_at).toLocaleString("en-IN")} · {data.disclaimer}
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
