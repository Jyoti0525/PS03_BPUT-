"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, Baby, BellRing, CheckCircle2, HeartPulse, Paperclip, UserRoundCheck, Users } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAsync, timeAgo } from "@/lib/hooks";
import { usePrefs, useSession } from "@/components/providers";
import { Badge, Button, Card, CardHeader, ErrorNote, FieldError, Label, Modal, Spinner, Textarea, cx } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { NoteView, UrgencyBadge, urgencyBar } from "@/components/triage/note";
import { useFile } from "@/components/triage/source";
import { ObservationForm, ObservationList } from "@/components/triage/observations";
import { langByCode } from "@/lib/i18n/languages";

function FileThumb({ id }: { id: string }) {
  const f = useFile(id);
  if (!f) return <div className="h-20 w-28 animate-pulse rounded-lg bg-canvas" />;
  if (f.url && f.content_type.startsWith("audio"))
    // The patient's own recording: what to listen to when the note says the translation may be wrong.
    return (
      <div className="w-64 rounded-lg border border-line bg-canvas p-2" title={f.filename}>
        <audio controls preload="none" src={f.url} className="h-9 w-full" />
        <p className="mt-1 truncate text-[11px] text-muted">{f.filename}</p>
      </div>
    );
  return (
    <a href={f.url ?? undefined} target="_blank" rel="noreferrer" className="block w-28" title={f.filename}>
      {f.url && f.content_type.startsWith("image") ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={f.url} alt={f.filename} className="h-20 w-28 rounded-lg border border-line object-cover object-top" />
      ) : (
        <div className="grid h-20 w-28 place-items-center rounded-lg border border-line bg-canvas text-xs text-muted">{f.kind}</div>
      )}
      <p className="mt-1 truncate text-[11px] text-muted">{f.filename}</p>
    </a>
  );
}

/** Nurse's or health worker's view of one patient: bedside vitals and observations, checklist, alerting the doctor, and
 * sign-off within the role's limit (E2): a health worker may confirm GREEN, a nurse up to YELLOW. No referrals or exports. */
export default function NursePatient() {
  const { id } = useParams<{ id: string }>();
  const { tr } = usePrefs();
  const { user } = useSession();
  const [confirming, setConfirming] = useState(false);
  const { data: enc, error, reload, setData } = useAsync(() => api.getEncounter(id), [id]);
  const [alertOpen, setAlertOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (error) return <ErrorNote error={error} onRetry={reload} />;
  if (!enc) return <Spinner />;
  const p = enc.patient;

  async function alertDoctor() {
    setErr(null);
    if (reason.trim().length < 5) return setErr(tr("Add a short reason"));
    setBusy(true);
    try {
      await api.escalate(enc!.id, "doctor", reason.trim());
      toast(tr("Doctor alerted — they must acknowledge it"));
      setAlertOpen(false);
      setReason("");
      reload();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : tr("Could not alert the doctor"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-6xl">
      <Link href="/nurse" className="mb-3 inline-flex items-center gap-1 text-sm font-medium text-muted hover:text-ink">
        <ArrowLeft className="size-4" /> {tr("Patients to attend")}
      </Link>
      <Card className="overflow-hidden">
        <div className="flex">
          <span className={cx("w-2 shrink-0", urgencyBar(enc.urgency))} />
          <div className="flex flex-1 flex-wrap items-start gap-4 p-4 sm:p-5">
            <div className="grid size-14 shrink-0 place-items-center rounded-2xl bg-teal-50 text-xl font-bold text-teal-700">{p.name.charAt(0)}</div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                {enc.token && <span className="rounded-lg bg-teal-50 px-2 py-0.5 font-mono text-sm font-bold text-teal-800">{enc.token}</span>}
                <h1 className="text-xl font-bold text-ink sm:text-2xl">{p.name}</h1>
                <UrgencyBadge u={enc.urgency} size="lg" />
              </div>
              <p className="mt-0.5 text-sm text-muted">
                {p.age} · {tr(p.sex === "F" ? "Female" : p.sex === "M" ? "Male" : "Other")} · <span className="font-mono">{p.code}</span> · {tr(langByCode(p.language).name)} · {tr("arrived {t}", { t: timeAgo(enc.created_at) })}
              </p>
              <p className="mt-2 text-[15px] font-medium text-ink">{tr(enc.chief_complaint)}</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {enc.category === "maternal" && (
                  <Badge tone="coral">
                    <Baby className="size-3" /> {tr("Maternal")} · {enc.intake?.maternal?.gestation_weeks ?? "?"} {tr("weeks")}
                  </Badge>
                )}
                {enc.category === "chronic" && (
                  <Badge tone="teal">
                    <HeartPulse className="size-3" /> {tr("Chronic")} · {tr(enc.intake?.chronic?.condition)}
                  </Badge>
                )}
                {enc.consent && (
                  <Badge tone={enc.consent.mode === "proxy" ? "info" : "neutral"}>
                    {enc.consent.mode === "proxy" ? <Users className="size-3" /> : <UserRoundCheck className="size-3" />}
                    {enc.consent.mode === "proxy" ? tr("With {name}", { name: enc.consent.proxy_name ?? "" }) : tr("Self consent")}
                  </Badge>
                )}
              </div>
            </div>
            <div className="flex flex-col items-end gap-2">
              <Button variant="danger" icon={<BellRing className="size-4" />} onClick={() => setAlertOpen(true)}>
                {tr("Alert doctor")}
              </Button>
              {enc.status === "confirmed" ? (
                <Badge tone="rout"><CheckCircle2 className="size-3" /> {tr("Confirmed by {n}", { n: enc.reviewed_by ?? "" })}</Badge>
              ) : enc.can_confirm ? (
                <Button
                  variant="teal"
                  loading={confirming}
                  icon={<CheckCircle2 className="size-4" />}
                  onClick={async () => {
                    setConfirming(true);
                    try {
                      setData(await api.confirmEncounter(enc.id));
                      toast(tr("Note confirmed and signed"));
                    } catch (e) {
                      toast(e instanceof Error ? e.message : tr("Failed"), "error");
                    } finally {
                      setConfirming(false);
                    }
                  }}
                >
                  {tr("Confirm note")}
                </Button>
              ) : (
                <p className="max-w-56 text-right text-xs text-muted">
                  {enc.sign_off === "doctor" ? tr("A RED note is confirmed by a doctor or medical officer.") : tr("A YELLOW note is confirmed by a nurse, doctor or medical officer.")}
                </p>
              )}
            </div>
          </div>
        </div>
      </Card>

      <div className="mt-4 grid gap-4 lg:grid-cols-[420px_1fr]">
        <div className="space-y-4">
          <ObservationForm enc={enc} onSaved={setData} compact />
          <ObservationList items={enc.note?.observations} />
        </div>
        <div className="space-y-4">
          {enc.note ? <NoteView enc={enc} density={user?.role === "health_worker" ? "health_worker" : "nurse"} /> : null}
          {!!enc.intake?.file_ids.length && (
            <Card>
              <CardHeader title={tr("Reports and photos")} icon={<Paperclip className="size-4" />} />
              <div className="flex flex-wrap gap-3 p-4">
                {enc.intake.file_ids.map((f) => (
                  <FileThumb key={f} id={f} />
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>

      <Modal
        open={alertOpen}
        onClose={() => setAlertOpen(false)}
        title={tr("Alert the doctor on duty")}
        subtitle={tr("Use this when the patient needs a doctor now. The doctor must acknowledge it.")}
        footer={
          <>
            <Button variant="secondary" onClick={() => setAlertOpen(false)}>
              {tr("Cancel")}
            </Button>
            <Button variant="danger" loading={busy} onClick={alertDoctor}>
              {tr("Alert doctor")}
            </Button>
          </>
        }
      >
        <Label htmlFor="alert-reason">{tr("What have you noticed?")}</Label>
        <Textarea id="alert-reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder={tr("e.g. SpO₂ dropped to 88% on repeat, breathless at rest")} />
        <FieldError>{err}</FieldError>
      </Modal>
    </div>
  );
}
