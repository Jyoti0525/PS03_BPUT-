"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import {
  ArrowLeft, CheckCircle2, Pencil, ShieldAlert, Siren, Send, Printer, FileJson, FileSpreadsheet, FileText, Stethoscope, Baby, HeartPulse,
  UserRoundCheck, Users, Timer, Paperclip, Copy, Ambulance, ChevronDown, Eye, QrCode,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAsync, useNow, timeAgo, fmtDate } from "@/lib/hooks";
import { useSession, usePrefs } from "@/components/providers";
import { Badge, Button, Card, CardHeader, ErrorNote, FieldError, Label, Modal, Segmented, Select, Spinner, Textarea, cx } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { NoteView, UrgencyBadge, urgencyBar } from "@/components/triage/note";
import { DocumentLabels, MedicationsPanel } from "@/components/triage/medications";
import { useFile } from "@/components/triage/source";
import { DOCTOR_ROLES, type Encounter, type ExportFormat, type Facility, type ShareLink, type Urgency } from "@/lib/types";
import { ShareQrModal } from "@/components/triage/share-qr";
import { PatientEditModal } from "@/components/triage/patient-edit";
import { WorkerPanel } from "@/components/triage/worker-panel";
import { ObservationList } from "@/components/triage/observations";
import { URGENCY_LABEL, downloadBlob, referralText } from "@/lib/export";
import { langByCode } from "@/lib/i18n/languages";

const OVERRIDE_CATEGORIES = [
  "Examination findings differ from intake",
  "Vitals re-measured",
  "Known chronic baseline for this patient",
  "Rule triggered on ambiguous wording",
  "Clinical judgement — other",
];

function FileThumb({ id }: { id: string }) {
  const { tr } = usePrefs();
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
        <div className="grid h-20 w-28 place-items-center rounded-lg border border-line bg-canvas text-xs text-muted">{f.purged_at ? tr("Purged") : f.kind}</div>
      )}
      <p className="mt-1 truncate text-[11px] text-muted">{f.filename}</p>
      <p className="text-[10px] text-subtle">{tr("expires")} {fmtDate(f.expires_at)}</p>
    </a>
  );
}

function ReviewClock({ start }: { start: number }) {
  const { tr } = usePrefs();
  const now = useNow(1000);
  const s = Math.floor((now - start) / 1000);
  const over = s > 240;
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold tabular-nums", over ? "bg-semi-bg text-semi" : "bg-canvas text-muted")} title={tr("Target: review within 4 minutes")}>
      <Timer className="size-3.5" /> {Math.floor(s / 60)}:{String(s % 60).padStart(2, "0")} / 4:00
    </span>
  );
}

export default function CasePage() {
  const { tr } = usePrefs();
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useSession();
  const isDoctor = !!user && DOCTOR_ROLES.includes(user.role);
  const { data: enc, error, loading, reload, setData } = useAsync(() => api.getEncounter(id), [id]);
  const { data: facility } = useAsync<Facility | null>(() => (enc ? api.getFacility(enc.facility_id) : Promise.resolve(null)), [enc?.facility_id]);
  const [density, setDensity] = useState<"doctor" | "nurse" | "health_worker">(isDoctor ? "doctor" : "nurse");
  const [start] = useState(() => Date.now());
  const now = useNow(1000);
  const [modal, setModal] = useState<null | "override" | "escalate" | "referral" | "edit" | "share" | "patient">(null);
  const [freshShare, setFreshShare] = useState<ShareLink | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const act = async (fn: () => Promise<Encounter | void>, msg: string) => {
    setBusy(true);
    try {
      const r = await fn();
      if (r) setData(r);
      toast(msg);
      return true;
    } catch (e) {
      toast(e instanceof ApiError ? e.message : tr("Action failed"), "error");
      return false;
    } finally {
      setBusy(false);
    }
  };

  if (error) return <ErrorNote error={error} onRetry={reload} />;
  if (loading || !enc) return <Spinner label={tr("Opening case…")} />;
  const p = enc.patient;
  const n = enc.note;
  const done = ["confirmed", "referred", "closed"].includes(enc.status);
  const dueMs = enc.escalation_due_at ? Date.parse(enc.escalation_due_at) - now : null;

  const doExport = async (f: ExportFormat) => {
    setExportOpen(false);
    try {
      const r = await api.exportEncounter(enc.id, f);
      if (f === "print") {
        const w = window.open(URL.createObjectURL(r.blob), "_blank");
        if (!w) downloadBlob(r.filename, r.blob);
      } else downloadBlob(r.filename, r.blob);
      toast(`Exported ${f.toUpperCase()} — logged to audit`);
    } catch (e) {
      toast(e instanceof Error ? e.message : tr("Export failed"), "error");
    }
  };

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-3 flex items-center justify-between gap-2">
        <Link href="/reviewer" className="inline-flex items-center gap-1 text-sm font-medium text-muted hover:text-ink">
          <ArrowLeft className="size-4" /> {tr("Queue")}
        </Link>
        <ReviewClock start={start} />
      </div>

      {/* Patient card */}
      <Card>
        <div className="flex">
          <span className={cx("w-2 shrink-0 rounded-tl-[var(--radius-card)]", urgencyBar(enc.urgency))} />
          <div className="flex-1 p-4 sm:p-5">
            <div className="flex flex-wrap items-start gap-4">
              <div className="grid size-14 shrink-0 place-items-center rounded-2xl bg-coral-100 text-xl font-bold text-coral-700">{p.name.charAt(0)}</div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  {enc.token && <span className="rounded-lg bg-coral-50 px-2 py-0.5 font-mono text-sm font-bold text-coral-700">{enc.token}</span>}
                  <h1 className="text-xl font-bold text-ink sm:text-2xl">{p.name}</h1>
                  <UrgencyBadge u={enc.urgency} size="lg" />
                  {enc.urgency_source === "override" && <Badge tone="coral">{tr("Overridden")}</Badge>}
                  <button onClick={() => setModal("patient")} className="inline-flex items-center gap-1 rounded-lg px-1.5 py-0.5 text-xs font-medium text-muted hover:bg-canvas hover:text-ink" title={tr("Correct name, age, phone…")}>
                    <Pencil className="size-3.5" /> {tr("Edit details")}
                  </button>
                </div>
                <p className="mt-0.5 text-sm text-muted">
                  {p.age} y · {p.sex === "F" ? tr("Female") : p.sex === "M" ? tr("Male") : tr("Other")} · <span className="font-mono">{p.code}</span> · {tr(langByCode(p.language).name)} {tr("· intake")} {timeAgo(enc.created_at, now)}
                </p>
                <p className="mt-2 text-[15px] font-medium text-ink">{tr(enc.chief_complaint)}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {enc.category === "maternal" && <Badge tone="coral"><Baby className="size-3" /> {tr("Maternal ·")} {enc.intake?.maternal?.gestation_weeks ?? "?"} {tr("weeks")}</Badge>}
                  {enc.category === "chronic" && <Badge tone="teal"><HeartPulse className="size-3" /> {tr("Chronic ·")} {tr(enc.intake?.chronic?.condition)}</Badge>}
                  {enc.consent && (
                    <Badge tone={enc.consent.mode === "proxy" ? "info" : "neutral"}>
                      {enc.consent.mode === "proxy" ? <Users className="size-3" /> : <UserRoundCheck className="size-3" />}
                      {enc.consent.mode === "proxy" ? tr("Proxy: {n} ({r})", { n: enc.consent.proxy_name ?? "", r: tr(enc.consent.proxy_relation ?? "") }) : tr("Self consent")}
                    </Badge>
                  )}
                  {enc.intake?.captured_offline && <Badge>{tr("Captured offline")}</Badge>}
                  <Badge tone="neutral">{tr("Status:")} {tr(enc.status.replace("_", " "))}</Badge>
                  {dueMs != null && !done && enc.status !== "escalated" && (
                    <Badge tone={dueMs < 300000 ? "crit" : "neutral"}>
                      <Timer className="size-3" />
                      {dueMs > 0 ? tr("Auto-escalates in {t}", { t: `${Math.floor(dueMs / 60000)}:${String(Math.floor((dueMs % 60000) / 1000)).padStart(2, "0")}` }) : tr("Escalation due")}
                    </Badge>
                  )}
                </div>
              </div>

              {/* Referral yes / no + triage status (from system design) */}
              <div className="w-full rounded-xl border border-line bg-canvas p-3 sm:w-auto sm:min-w-56">
                <p className="text-xs font-semibold tracking-wide text-muted uppercase">{tr("Referral needed?")}</p>
                <div className="mt-2 flex gap-1.5">
                  {[true, false].map((v) => (
                    <button
                      key={String(v)}
                      disabled={busy}
                      onClick={() => act(() => api.setReferralNeeded(enc.id, v), `Referral marked ${v ? "needed" : "not needed"}`)}
                      className={cx("flex-1 rounded-lg border px-3 py-1.5 text-sm font-semibold", enc.referral_needed === v ? (v ? "border-coral-500 bg-coral-500 text-white" : "border-ink bg-ink text-white") : "border-line bg-white text-muted")}
                    >
                      {v ? tr("Yes") : tr("No")}
                    </button>
                  ))}
                </div>
                {enc.specialist_required && facility && (
                  <p className="mt-2 text-xs text-muted">
                    {(() => {
                      const s = facility.specialists.find((x) => x.key === enc.specialist_required);
                      return s ? (s.available ? tr("{s}: on site", { s: tr(s.label) }) : tr("{s}: not on site → {d}", { s: tr(s.label), d: facility.referral_destination })) : tr("No {s} service here → {d}", { s: enc.specialist_required ?? "", d: facility.referral_destination });
                    })()}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Action bar */}
        <div className="no-print flex flex-wrap items-center gap-2 rounded-b-[var(--radius-card)] border-t border-line bg-canvas/60 px-4 py-3">
          {isDoctor && (
            <Button variant="teal" disabled={done} loading={busy} onClick={() => act(() => api.confirmEncounter(enc.id), "Note confirmed and signed")} icon={<CheckCircle2 className="size-4" />}>
              {done ? `Reviewed by ${enc.reviewed_by}` : tr("Confirm note")}
            </Button>
          )}
          {done && (
            <Link href="/reviewer" className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-ink px-4 text-sm font-semibold text-white hover:opacity-90">
              {tr("Next patient")} <ArrowLeft className="size-4 rotate-180" />
            </Link>
          )}
          {/* E9: anyone reviewing may raise the urgency; only a doctor may lower it. */}
          <Button variant="secondary" onClick={() => setModal("override")} icon={<ShieldAlert className="size-4" />}>
            {tr(isDoctor ? "Override urgency" : "Raise urgency")}
          </Button>
          <Button variant="secondary" onClick={() => setModal("escalate")} icon={<Siren className="size-4" />}>
            {tr("Escalate")}
          </Button>
          {isDoctor && (
            <Button variant="secondary" onClick={() => setModal("referral")} icon={<Send className="size-4" />}>
              {tr("Referral note")}
            </Button>
          )}
          <div className="relative">
            <Button variant="secondary" onClick={() => setExportOpen((o) => !o)} aria-haspopup="menu" aria-expanded={exportOpen}>
              {tr("More")} <ChevronDown className="size-3.5" />
            </Button>
            {exportOpen && (
              <div role="menu" className="absolute top-11 left-0 z-20 w-52 rounded-xl border border-line bg-white p-1 shadow-[var(--shadow-pop)]">
                <button role="menuitem" onClick={() => { setExportOpen(false); setModal("edit"); }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-semibold text-ink hover:bg-canvas">
                  <Pencil className="size-4" /> {tr("Edit note")}
                </button>
                <button role="menuitem" onClick={() => { setExportOpen(false); setFreshShare(null); setModal("share"); }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-semibold text-ink hover:bg-canvas">
                  <QrCode className="size-4" /> {tr("Share QR")}
                </button>
                <p className="mt-1 border-t border-line px-3 pt-2 pb-1 text-[11px] font-bold tracking-wide text-subtle uppercase">{tr("Download")}</p>
                {(
                  [
                    ["pdf", "PDF", <FileText key="p" className="size-4" />],
                    ["print", "Print", <Printer key="pr" className="size-4" />],
                    ["json", "JSON", <FileJson key="j" className="size-4" />],
                    ["csv", "CSV", <FileSpreadsheet key="c" className="size-4" />],
                    ["fhir", "FHIR R4 bundle", <FileJson key="f" className="size-4" />],
                    ["cda", "HL7 CDA document", <FileJson key="cda" className="size-4" />],
                  ] as const
                ).map(([f, label, icon]) => (
                  <button role="menuitem" key={f} onClick={() => { setExportOpen(false); doExport(f); }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-ink hover:bg-canvas">
                    {icon} {tr(label)}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </Card>

      {/* Scenario panels */}
      {enc.category === "maternal" && enc.intake?.maternal && (
        <Card className="mt-4">
          <CardHeader title={tr("Maternal details")} icon={<Baby className="size-4" />} />
          <dl className="grid grid-cols-2 gap-4 p-4 text-sm sm:grid-cols-4">
            <div><dt className="text-muted">{tr("Gestation")}</dt><dd className="font-semibold">{enc.intake.maternal.gestation_weeks ?? "—"} {tr("weeks")}</dd></div>
            <div><dt className="text-muted">{tr("ANC visits")}</dt><dd className="font-semibold">{enc.intake.maternal.anc_visits ?? "—"}</dd></div>
            <div><dt className="text-muted">{tr("Next check-up")}</dt><dd className="font-semibold">{enc.intake.maternal.next_checkup ?? tr("Not scheduled")}</dd></div>
            <div><dt className="text-muted">{tr("Reminder channel")}</dt><dd className="font-semibold uppercase">{enc.intake.maternal.reminder_channel ?? "—"}</dd></div>
          </dl>
        </Card>
      )}
      {enc.category === "chronic" && enc.intake?.chronic && (
        <Card className="mt-4">
          <CardHeader title={tr("Chronic follow-up")} subtitle={tr("Compare with the last check-up before deciding")} icon={<HeartPulse className="size-4" />} />
          <dl className="grid grid-cols-2 gap-4 p-4 text-sm sm:grid-cols-4">
            <div><dt className="text-muted">{tr("Condition")}</dt><dd className="font-semibold">{tr(enc.intake.chronic.condition)}</dd></div>
            <div><dt className="text-muted">{tr("Last check-up")}</dt><dd className="font-semibold">{enc.intake.chronic.last_checkup ?? "—"}</dd></div>
            <div><dt className="text-muted">{tr("Patient feels")}</dt><dd className={cx("font-semibold capitalize", enc.intake.chronic.feeling_vs_last === "worse" && "text-crit")}>{enc.intake.chronic.feeling_vs_last} {tr("than last time")}</dd></div>
            <div className="col-span-2 sm:col-span-1"><dt className="text-muted">{tr("Medicines")}</dt><dd className="font-semibold">{enc.intake.chronic.current_medicines ?? "—"}</dd></div>
          </dl>
        </Card>
      )}

      {!!enc.note?.observations?.length && (
        <div className="mt-4">
          <ObservationList items={enc.note.observations} />
        </div>
      )}

      {enc.worker && <WorkerPanel encounterId={enc.id} worker={enc.worker} canRecord={isDoctor} onRecorded={reload} />}

      <MedicationsPanel enc={enc} canReview onDone={setData} />

          {isDoctor && (
          <div className="no-print mt-4 flex justify-end">
            <Segmented
              value={density}
              onChange={setDensity}
              options={[
                { value: "doctor", label: <span className="inline-flex items-center gap-1"><Stethoscope className="size-3.5" /> {tr("Doctor view")}</span> },
                { value: "nurse", label: <span className="inline-flex items-center gap-1"><Eye className="size-3.5" /> {tr("Nurse view")}</span> },
                { value: "health_worker", label: <span className="inline-flex items-center gap-1"><Eye className="size-3.5" /> {tr("Health-worker view")}</span> },
              ]}
            />
          </div>
          )}
      <div className="mt-4">{n ? <NoteView enc={enc} density={density} onUpdated={setData} /> : <p className="text-sm text-muted">{tr("No note generated.")}</p>}</div>

      {!!enc.intake?.file_ids.length && (
        <Card className="mt-4">
          <CardHeader title={tr("Uploaded files")} subtitle={tr("Raw files expire automatically under the retention policy")} icon={<Paperclip className="size-4" />} />
          <div className="flex flex-wrap gap-3 p-4">
            {enc.intake.file_ids.map((f) => (
              <FileThumb key={f} id={f} />
            ))}
          </div>
          <DocumentLabels enc={enc} />
        </Card>
      )}

      {/* Mounted only while open, so each opening starts from fresh state. */}
      {modal === "override" && <OverrideModal open enc={enc} onClose={() => setModal(null)} onDone={(e) => { setData(e); setModal(null); }} />}
      {modal === "escalate" && <EscalateModal open enc={enc} onClose={() => setModal(null)} onDone={() => { setModal(null); reload(); }} />}
      {modal === "edit" && <EditModal open enc={enc} onClose={() => setModal(null)} onDone={(e) => { setData(e); setModal(null); }} />}
      {modal === "referral" && (
        <ReferralModal
          open
          enc={enc}
          facility={facility ?? null}
          onClose={() => setModal(null)}
          onDone={(share) => {
            reload();
            if (share) {
              setFreshShare(share);
              setModal("share");
            } else {
              setModal(null);
              router.push("/reviewer/referrals");
            }
          }}
        />
      )}
      {modal === "patient" && <PatientEditModal patient={p} onClose={() => setModal(null)} onDone={() => { setModal(null); reload(); }} />}
      {modal === "share" && <ShareQrModal enc={enc} facilityName={facility?.name} initial={freshShare} onClose={() => setModal(null)} />}
    </div>
  );
}

function OverrideModal({ open, enc, onClose, onDone }: { open: boolean; enc: Encounter; onClose: () => void; onDone: (e: Encounter) => void }) {
  const { tr } = usePrefs();
  const [to, setTo] = useState<Urgency | "">("");
  const [category, setCategory] = useState(OVERRIDE_CATEGORIES[0]);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const { user } = useSession();
  const isDoctor = !!user && DOCTOR_ROLES.includes(user.role);
  const rank: Record<Urgency, number> = { green: 0, yellow: 1, red: 2 };
  const cur = enc.urgency ?? "green";
  // E9: raising is free for every reviewer; lowering is a doctor's decision with a written reason.
  const options = (["red", "yellow", "green"] as Urgency[]).filter((u) => u !== cur && (isDoctor || rank[u] > rank[cur]));
  const down = !!to && rank[to] < rank[cur];
  const submit = async () => {
    setErr(null);
    if (!to) return setErr(tr("Choose the new urgency"));
    if (down && reason.trim().length < 15) return setErr(tr("Write a reason of at least 15 characters"));
    setBusy(true);
    try {
      onDone(await api.overrideUrgency(enc.id, to, category, reason));
      toast(tr("Override recorded in audit log"));
    } catch (e) {
      setErr(e instanceof Error ? e.message : tr("Failed"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={tr("Override rules-engine urgency")}
      subtitle={tr(isDoctor ? "The original rules output is kept. Your reason is permanently written to the audit log." : "You can raise the urgency at any time; only a doctor can lower it. The original rules output is kept.")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{tr("Cancel")}</Button>
          <Button variant="danger" onClick={submit} loading={busy}>{tr("Record override")}</Button>
        </>
      }
    >
      {!options.length && <p className="mb-2 text-sm text-muted">{tr("This case is already RED. Only a doctor can lower it; use Escalate to call one.")}</p>}
      <p className="text-sm text-muted">{tr("Current:")} <UrgencyBadge u={enc.urgency} size="sm" /> {tr("from rules")} {enc.note?.rules_fired.map((r) => r.rule_id).join(", ")}</p>
      <div className="mt-4 grid grid-cols-2 gap-2">
        {options.map((u) => (
          <button key={u} onClick={() => setTo(u)} className={cx("rounded-xl border p-3 text-left", to === u ? "border-ink bg-canvas" : "border-line")}>
            <UrgencyBadge u={u} />
            <p className="mt-1 text-xs text-muted">{u === "red" ? tr("Immediate") : u === "yellow" ? tr("Within 30–60 min") : tr("Standard OPD order")}</p>
          </button>
        ))}
      </div>
      <div className="mt-4">
        <Label htmlFor="ov-cat">{tr("Category")}</Label>
        <Select id="ov-cat" value={category} onChange={(e) => setCategory(e.target.value)}>
          {OVERRIDE_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
        </Select>
      </div>
      <div className="mt-4">
        <Label htmlFor="ov-reason" hint={down ? tr("{n}/15 characters minimum", { n: reason.trim().length }) : undefined}>{tr(down ? "Written reason (required)" : "Reason (optional)")}</Label>
        <Textarea id="ov-reason" rows={4} value={reason} onChange={(e) => setReason(e.target.value)} placeholder={tr("e.g. Repeat BP 132/84 after rest; chest wall tenderness reproduces pain; ECG normal.")} />
      </div>
      <FieldError>{err}</FieldError>
    </Modal>
  );
}

function EscalateModal({ open, enc, onClose, onDone }: { open: boolean; enc: Encounter; onClose: () => void; onDone: () => void }) {
  const { tr } = usePrefs();
  const [to, setTo] = useState<"senior_mo" | "specialist" | "doctor">("senior_mo");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={tr("Escalate this case")}
      subtitle={tr("The receiving clinician must acknowledge. Unacknowledged escalations stay on their dashboard.")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{tr("Cancel")}</Button>
          <Button
            variant="danger"
            loading={busy}
            onClick={async () => {
              setErr(null);
              if (reason.trim().length < 5) return setErr(tr("Add a short reason"));
              setBusy(true);
              try {
                await api.escalate(enc.id, to, reason);
                toast(tr("Escalated — awaiting acknowledgement"));
                onDone();
              } catch (e) {
                setErr(e instanceof Error ? e.message : tr("Failed"));
              } finally {
                setBusy(false);
              }
            }}
          >
            {tr("Escalate")}
          </Button>
        </>
      }
    >
      <Label htmlFor="esc-to">{tr("Escalate to")}</Label>
      <Select id="esc-to" value={to} onChange={(e) => setTo(e.target.value as typeof to)}>
        <option value="senior_mo">{tr("Senior Medical Officer")}</option>
        <option value="specialist">{tr("Specialist on call")}</option>
        <option value="doctor">{tr("Doctor on duty")}</option>
      </Select>
      <div className="mt-4">
        <Label htmlFor="esc-reason">{tr("Reason")}</Label>
        <Textarea id="esc-reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder={tr("e.g. SpO₂ dropping on repeat, needs senior review now")} />
      </div>
      <FieldError>{err}</FieldError>
    </Modal>
  );
}

function EditModal({ open, enc, onClose, onDone }: { open: boolean; enc: Encounter; onClose: () => void; onDone: (e: Encounter) => void }) {
  const { tr } = usePrefs();
  const [summary, setSummary] = useState(enc.note?.summary ?? "");
  const [missing, setMissing] = useState((enc.note?.missing_info ?? []).join("\n"));
  const [busy, setBusy] = useState(false);
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title={tr("Edit triage note")}
      subtitle={tr("Edits are attributed to you and logged. Urgency cannot be changed here — use Override.")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{tr("Cancel")}</Button>
          <Button
            loading={busy}
            onClick={async () => {
              setBusy(true);
              try {
                onDone(await api.editNote(enc.id, { summary, missing_info: missing.split("\n").map((s) => s.trim()).filter(Boolean) }));
                toast(tr("Note updated"));
              } catch (e) {
                toast(e instanceof Error ? e.message : tr("Failed"), "error");
              } finally {
                setBusy(false);
              }
            }}
          >
            {tr("Save changes")}
          </Button>
        </>
      }
    >
      <Label htmlFor="ed-sum">{tr("Summary")}</Label>
      <Textarea id="ed-sum" rows={6} value={summary} onChange={(e) => setSummary(e.target.value)} />
      <div className="mt-4">
        <Label htmlFor="ed-miss" hint={tr("(one per line)")}>{tr("Missing information")}</Label>
        <Textarea id="ed-miss" rows={4} value={missing} onChange={(e) => setMissing(e.target.value)} />
      </div>
    </Modal>
  );
}

function ReferralModal({ open, enc, facility, onClose, onDone }: { open: boolean; enc: Encounter; facility: Facility | null; onClose: () => void; onDone: (share: ShareLink | null) => void }) {
  const { tr } = usePrefs();
  const spec = facility?.specialists.find((s) => s.key === enc.specialist_required);
  const defaultDest = spec?.available ? `${facility?.name} — ${spec.label} (in-house)` : spec?.refer_to || (facility?.referral_destination ?? "");
  const [destination, setDestination] = useState(defaultDest);
  const [specialty, setSpecialty] = useState(spec?.label ?? "General Medicine");
  const [reason, setReason] = useState("");
  const [given, setGiven] = useState("");
  const { user } = useSession();
  const [transport, setTransport] = useState<"self" | "ambulance_108" | "facility_vehicle">(enc.urgency === "red" ? "ambulance_108" : "self");
  const [edited, setEdited] = useState<string | null>(null);
  const [withQr, setWithQr] = useState(true);
  const [busy, setBusy] = useState(false);

  const generated = useMemo(() => referralText(enc, facility, destination, specialty, reason || enc.chief_complaint, { given, referrer: user ? { name: user.name, role: user.role, phone: user.phone } : null }),
    [enc, facility, destination, specialty, reason, given, user],
  );
  // Show the generated text until the doctor edits it by hand.
  const text = edited ?? generated;
  const setText = setEdited;

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="xl"
      title={tr("Referral note")}
      subtitle={tr("Prepared from the triage note and this facility's specialist configuration. Review before sending.")}
      footer={
        <>
          <Button variant="secondary" icon={<Copy className="size-4" />} onClick={() => { navigator.clipboard?.writeText(text); toast(tr("Copied")); }}>{tr("Copy")}</Button>
          <Button
            variant="secondary"
            icon={<Printer className="size-4" />}
            onClick={() => {
              const w = window.open("", "_blank");
              if (w) {
                w.document.write(`<pre style="font:14px/1.5 system-ui;white-space:pre-wrap;max-width:760px;margin:24px auto">${text.replace(/</g, "&lt;")}</pre>`);
                w.document.close();
                w.print();
              }
            }}
          >
            {tr("Print")}
          </Button>
          <Button
            variant="teal"
            loading={busy}
            icon={transport === "ambulance_108" ? <Ambulance className="size-4" /> : <Send className="size-4" />}
            onClick={async () => {
              setBusy(true);
              try {
                const share = withQr ? await api.createShare(enc.id, 168, "referral") : null;
                const note = share
                  ? `${text}\n\nPatient summary and documents (scan QR or open): ${share.url}\nAccess code: ${share.access_code} · valid until ${new Date(share.expires_at).toLocaleString("en-IN")}`
                  : text;
                await api.createReferral(enc.id, { destination, specialty, reason: reason || enc.chief_complaint, transport, note_text: note });
                toast(share ? tr("Referral sent — print the QR slip for the patient") : tr("Referral sent and logged"));
                onDone(share);
              } catch (e) {
                toast(e instanceof Error ? e.message : tr("Failed"), "error");
              } finally {
                setBusy(false);
              }
            }}
          >
            {tr("Send referral")}
          </Button>
        </>
      }
    >
      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <div className="space-y-3">
          <div>
            <Label htmlFor="rf-dest">{tr("Destination")}</Label>
            <Select id="rf-dest" value={destination} onChange={(e) => setDestination(e.target.value)}>
              {spec?.available && <option value={`${facility?.name} — ${spec.label} (in-house)`}>{`${facility?.name} — ${tr(spec.label)} (${tr("in-house")})`}</option>}
              {/* E4: each specialty's referral place from the facility's configuration, then the default referral hospital */}
              {[...new Set([spec?.refer_to, ...(facility?.specialists ?? []).filter((s) => !s.available).map((s) => s.refer_to)].filter((x): x is string => !!x))].map((d) => <option key={d}>{d}</option>)}
              {facility && <option>{facility.referral_destination}</option>}
              <option>{tr("Tele-consultation (eSanjeevani hub)")}</option>
            </Select>
            {spec && !spec.available && <p className="mt-1 text-xs text-muted">{tr(spec.label)} {tr("is not on site today")}{spec.schedule ? ` (${spec.schedule})` : ""}.</p>}
          </div>
          <div>
            <Label htmlFor="rf-spec">{tr("Specialty")}</Label>
            <Select id="rf-spec" value={specialty} onChange={(e) => setSpecialty(e.target.value)}>
              {[...new Set([specialty, ...(facility?.specialists.map((s) => s.label) ?? []), "Emergency Medicine"])].map((s) => <option key={s}>{s}</option>)}
            </Select>
          </div>
          <div>
            <Label htmlFor="rf-reason">{tr("Reason")}</Label>
            <Textarea id="rf-reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder={tr(enc.chief_complaint)} />
          </div>
          <div>
            <Label htmlFor="rf-given">{tr("Treatment given here")}</Label>
            <Textarea id="rf-given" rows={3} value={given} onChange={(e) => setGiven(e.target.value)} placeholder={tr("e.g. Aspirin 300 mg chewed at 10:40; oxygen 4 L/min")} />
          </div>
          <label className="flex cursor-pointer items-start gap-2.5 rounded-xl border border-teal-200 bg-teal-50/60 p-3 text-sm">
            <input type="checkbox" checked={withQr} onChange={(e) => setWithQr(e.target.checked)} className="mt-0.5 size-4 accent-teal-700" />
            <span>
              <span className="font-semibold text-ink">{tr("Attach QR summary")}</span>
              <span className="block text-xs text-muted">{tr("Receiving team scans it for details and uploaded documents (valid 7 days, needs access code).")}</span>
            </span>
          </label>
          <div>
            <Label htmlFor="rf-tr">{tr("Transport")}</Label>
            <Select id="rf-tr" value={transport} onChange={(e) => setTransport(e.target.value as typeof transport)}>
              <option value="ambulance_108">{tr("108 ambulance")}</option>
              <option value="facility_vehicle">{tr("Facility vehicle")}</option>
              <option value="self">{tr("Self / family")}</option>
            </Select>
          </div>
        </div>
        <div>
          <Label htmlFor="rf-text">{tr("Note text (editable)")}</Label>
          <Textarea id="rf-text" rows={20} value={text} onChange={(e) => setText(e.target.value)} className="font-mono text-[13px]" />
        </div>
      </div>
      <p className="mt-2 text-xs text-muted">{tr("Triage category:")} {enc.urgency && URGENCY_LABEL[enc.urgency]}{tr(". Export as PDF/FHIR from the case Share & export menu.")}</p>
    </Modal>
  );
}
