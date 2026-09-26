"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import {
  ArrowLeft, CheckCircle2, Pencil, ShieldAlert, Siren, Send, Download, Printer, FileJson, FileSpreadsheet, FileText, Stethoscope, Baby, HeartPulse,
  UserRoundCheck, Users, Timer, Paperclip, Copy, Ambulance, ChevronDown, Eye,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { useAsync, useNow, timeAgo } from "@/lib/hooks";
import { useSession } from "@/components/providers";
import { Badge, Button, Card, CardHeader, ErrorNote, FieldError, Label, Modal, Segmented, Select, Spinner, Textarea, cx } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { NoteView, UrgencyBadge, urgencyBar } from "@/components/triage/note";
import { useFile } from "@/components/triage/source";
import type { Encounter, ExportFormat, Facility, Urgency } from "@/lib/types";
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
  const f = useFile(id);
  if (!f) return <div className="h-20 w-28 animate-pulse rounded-lg bg-canvas" />;
  return (
    <a href={f.url ?? undefined} target="_blank" rel="noreferrer" className="block w-28" title={f.filename}>
      {f.url && f.content_type.startsWith("image") ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={f.url} alt={f.filename} className="h-20 w-28 rounded-lg border border-line object-cover object-top" />
      ) : (
        <div className="grid h-20 w-28 place-items-center rounded-lg border border-line bg-canvas text-xs text-muted">{f.purged_at ? "Purged" : f.kind}</div>
      )}
      <p className="mt-1 truncate text-[11px] text-muted">{f.filename}</p>
      <p className="text-[10px] text-subtle">expires {new Date(f.expires_at).toLocaleDateString("en-IN")}</p>
    </a>
  );
}

function ReviewClock({ start }: { start: number }) {
  const now = useNow(1000);
  const s = Math.floor((now - start) / 1000);
  const over = s > 240;
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-semibold tabular-nums", over ? "bg-semi-bg text-semi" : "bg-canvas text-muted")} title="Target: review within 4 minutes">
      <Timer className="size-3.5" /> {Math.floor(s / 60)}:{String(s % 60).padStart(2, "0")} / 4:00
    </span>
  );
}

export default function CasePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { user } = useSession();
  const isDoctor = user?.role === "doctor";
  const { data: enc, error, loading, reload, setData } = useAsync(() => api.getEncounter(id), [id]);
  const { data: facility } = useAsync<Facility | null>(() => (enc ? api.getFacility(enc.facility_id) : Promise.resolve(null)), [enc?.facility_id]);
  const [density, setDensity] = useState<"doctor" | "nurse">(isDoctor ? "doctor" : "nurse");
  const [start] = useState(() => Date.now());
  const now = useNow(1000);
  const [modal, setModal] = useState<null | "override" | "escalate" | "referral" | "edit">(null);
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
      toast(e instanceof ApiError ? e.message : "Action failed", "error");
      return false;
    } finally {
      setBusy(false);
    }
  };

  if (error) return <ErrorNote error={error} onRetry={reload} />;
  if (loading || !enc) return <Spinner label="Opening case…" />;
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
      toast(e instanceof Error ? e.message : "Export failed", "error");
    }
  };

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-3 flex items-center justify-between gap-2">
        <Link href="/reviewer" className="inline-flex items-center gap-1 text-sm font-medium text-muted hover:text-ink">
          <ArrowLeft className="size-4" /> Queue
        </Link>
        <ReviewClock start={start} />
      </div>

      {/* Patient card */}
      <Card className="overflow-hidden">
        <div className="flex">
          <span className={cx("w-2 shrink-0", urgencyBar(enc.urgency))} />
          <div className="flex-1 p-4 sm:p-5">
            <div className="flex flex-wrap items-start gap-4">
              <div className="grid size-14 shrink-0 place-items-center rounded-2xl bg-coral-100 text-xl font-bold text-coral-700">{p.name.charAt(0)}</div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  {enc.token && <span className="rounded-lg bg-coral-50 px-2 py-0.5 font-mono text-sm font-bold text-coral-700">{enc.token}</span>}
                  <h1 className="text-xl font-bold text-ink sm:text-2xl">{p.name}</h1>
                  <UrgencyBadge u={enc.urgency} size="lg" />
                  {enc.urgency_source === "override" && <Badge tone="coral">Overridden</Badge>}
                </div>
                <p className="mt-0.5 text-sm text-muted">
                  {p.age} y · {p.sex === "F" ? "Female" : p.sex === "M" ? "Male" : "Other"} · <span className="font-mono">{p.code}</span> · {langByCode(p.language).name} · intake {timeAgo(enc.created_at, now)}
                </p>
                <p className="mt-2 text-[15px] font-medium text-ink">{enc.chief_complaint}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {enc.category === "maternal" && <Badge tone="coral"><Baby className="size-3" /> Maternal · {enc.intake?.maternal?.gestation_weeks ?? "?"} weeks</Badge>}
                  {enc.category === "chronic" && <Badge tone="teal"><HeartPulse className="size-3" /> Chronic · {enc.intake?.chronic?.condition}</Badge>}
                  {enc.consent && (
                    <Badge tone={enc.consent.mode === "proxy" ? "info" : "neutral"}>
                      {enc.consent.mode === "proxy" ? <Users className="size-3" /> : <UserRoundCheck className="size-3" />}
                      {enc.consent.mode === "proxy" ? `Proxy: ${enc.consent.proxy_name} (${enc.consent.proxy_relation})` : "Self consent"}
                    </Badge>
                  )}
                  {enc.intake?.captured_offline && <Badge>Captured offline</Badge>}
                  <Badge tone="neutral">Status: {enc.status.replace("_", " ")}</Badge>
                  {dueMs != null && !done && enc.status !== "escalated" && (
                    <Badge tone={dueMs < 300000 ? "crit" : "neutral"}>
                      <Timer className="size-3" />
                      {dueMs > 0 ? `Auto-escalates in ${Math.floor(dueMs / 60000)}:${String(Math.floor((dueMs % 60000) / 1000)).padStart(2, "0")}` : "Escalation due"}
                    </Badge>
                  )}
                </div>
              </div>

              {/* Referral yes / no + triage status (from system design) */}
              <div className="w-full rounded-xl border border-line bg-canvas p-3 sm:w-auto sm:min-w-56">
                <p className="text-xs font-semibold tracking-wide text-muted uppercase">Referral needed?</p>
                <div className="mt-2 flex gap-1.5">
                  {[true, false].map((v) => (
                    <button
                      key={String(v)}
                      disabled={busy}
                      onClick={() => act(() => api.setReferralNeeded(enc.id, v), `Referral marked ${v ? "needed" : "not needed"}`)}
                      className={cx("flex-1 rounded-lg border px-3 py-1.5 text-sm font-semibold", enc.referral_needed === v ? (v ? "border-coral-500 bg-coral-500 text-white" : "border-ink bg-ink text-white") : "border-line bg-white text-muted")}
                    >
                      {v ? "Yes" : "No"}
                    </button>
                  ))}
                </div>
                {enc.specialist_required && facility && (
                  <p className="mt-2 text-xs text-muted">
                    {(() => {
                      const s = facility.specialists.find((x) => x.key === enc.specialist_required);
                      return s ? (s.available ? `${s.label}: on site` : `${s.label}: not on site → ${facility.referral_destination}`) : `No ${enc.specialist_required} service here → ${facility.referral_destination}`;
                    })()}
                  </p>
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Action bar */}
        <div className="no-print flex flex-wrap items-center gap-2 border-t border-line bg-canvas/60 px-4 py-3">
          {isDoctor && (
            <Button variant="teal" disabled={done} loading={busy} onClick={() => act(() => api.confirmEncounter(enc.id), "Note confirmed and signed")} icon={<CheckCircle2 className="size-4" />}>
              {done ? `Reviewed by ${enc.reviewed_by}` : "Confirm note"}
            </Button>
          )}
          <Button variant="secondary" onClick={() => setModal("edit")} icon={<Pencil className="size-4" />}>
            Edit
          </Button>
          {isDoctor && (
            <Button variant="secondary" onClick={() => setModal("override")} icon={<ShieldAlert className="size-4" />}>
              Override urgency
            </Button>
          )}
          <Button variant="secondary" onClick={() => setModal("escalate")} icon={<Siren className="size-4" />}>
            Escalate
          </Button>
          {isDoctor && (
            <Button variant="secondary" onClick={() => setModal("referral")} icon={<Send className="size-4" />}>
              Referral note
            </Button>
          )}
          <div className="relative">
            <Button variant="secondary" onClick={() => setExportOpen((o) => !o)} icon={<Download className="size-4" />}>
              Export <ChevronDown className="size-3.5" />
            </Button>
            {exportOpen && (
              <div className="absolute top-11 left-0 z-20 w-44 rounded-xl border border-line bg-white p-1 shadow-[var(--shadow-pop)]">
                {(
                  [
                    ["pdf", "PDF", <FileText key="p" className="size-4" />],
                    ["print", "Print", <Printer key="pr" className="size-4" />],
                    ["json", "JSON", <FileJson key="j" className="size-4" />],
                    ["csv", "CSV", <FileSpreadsheet key="c" className="size-4" />],
                    ["fhir", "FHIR R4 bundle", <FileJson key="f" className="size-4" />],
                  ] as const
                ).map(([f, label, icon]) => (
                  <button key={f} onClick={() => doExport(f)} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm text-ink hover:bg-canvas">
                    {icon} {label}
                  </button>
                ))}
              </div>
            )}
          </div>
          <div className="ml-auto">
            <Segmented
              value={density}
              onChange={setDensity}
              options={[
                { value: "doctor", label: <span className="inline-flex items-center gap-1"><Stethoscope className="size-3.5" /> Doctor view</span> },
                { value: "nurse", label: <span className="inline-flex items-center gap-1"><Eye className="size-3.5" /> Nurse view</span> },
              ]}
            />
          </div>
        </div>
      </Card>

      {/* Scenario panels */}
      {enc.category === "maternal" && enc.intake?.maternal && (
        <Card className="mt-4">
          <CardHeader title="Maternal details" icon={<Baby className="size-4" />} />
          <dl className="grid grid-cols-2 gap-4 p-4 text-sm sm:grid-cols-4">
            <div><dt className="text-muted">Gestation</dt><dd className="font-semibold">{enc.intake.maternal.gestation_weeks ?? "—"} weeks</dd></div>
            <div><dt className="text-muted">ANC visits</dt><dd className="font-semibold">{enc.intake.maternal.anc_visits ?? "—"}</dd></div>
            <div><dt className="text-muted">Next check-up</dt><dd className="font-semibold">{enc.intake.maternal.next_checkup ?? "Not scheduled"}</dd></div>
            <div><dt className="text-muted">Reminder channel</dt><dd className="font-semibold uppercase">{enc.intake.maternal.reminder_channel ?? "—"}</dd></div>
          </dl>
        </Card>
      )}
      {enc.category === "chronic" && enc.intake?.chronic && (
        <Card className="mt-4">
          <CardHeader title="Chronic follow-up" subtitle="Compare with the last check-up before deciding" icon={<HeartPulse className="size-4" />} />
          <dl className="grid grid-cols-2 gap-4 p-4 text-sm sm:grid-cols-4">
            <div><dt className="text-muted">Condition</dt><dd className="font-semibold">{enc.intake.chronic.condition}</dd></div>
            <div><dt className="text-muted">Last check-up</dt><dd className="font-semibold">{enc.intake.chronic.last_checkup ?? "—"}</dd></div>
            <div><dt className="text-muted">Patient feels</dt><dd className={cx("font-semibold capitalize", enc.intake.chronic.feeling_vs_last === "worse" && "text-crit")}>{enc.intake.chronic.feeling_vs_last} than last time</dd></div>
            <div className="col-span-2 sm:col-span-1"><dt className="text-muted">Medicines</dt><dd className="font-semibold">{enc.intake.chronic.current_medicines ?? "—"}</dd></div>
          </dl>
        </Card>
      )}

      <div className="mt-4">{n ? <NoteView enc={enc} density={density} /> : <p className="text-sm text-muted">No note generated.</p>}</div>

      {!!enc.intake?.file_ids.length && (
        <Card className="mt-4">
          <CardHeader title="Uploaded files" subtitle="Raw files expire automatically under the retention policy" icon={<Paperclip className="size-4" />} />
          <div className="flex flex-wrap gap-3 p-4">
            {enc.intake.file_ids.map((f) => (
              <FileThumb key={f} id={f} />
            ))}
          </div>
        </Card>
      )}

      {/* Mounted only while open, so each opening starts from fresh state. */}
      {modal === "override" && <OverrideModal open enc={enc} onClose={() => setModal(null)} onDone={(e) => { setData(e); setModal(null); }} />}
      {modal === "escalate" && <EscalateModal open enc={enc} onClose={() => setModal(null)} onDone={() => { setModal(null); reload(); }} />}
      {modal === "edit" && <EditModal open enc={enc} onClose={() => setModal(null)} onDone={(e) => { setData(e); setModal(null); }} />}
      {modal === "referral" && <ReferralModal open enc={enc} facility={facility ?? null} onClose={() => setModal(null)} onDone={() => { setModal(null); router.push("/reviewer/referrals"); }} />}
    </div>
  );
}

function OverrideModal({ open, enc, onClose, onDone }: { open: boolean; enc: Encounter; onClose: () => void; onDone: (e: Encounter) => void }) {
  const [to, setTo] = useState<Urgency | "">("");
  const [category, setCategory] = useState(OVERRIDE_CATEGORIES[0]);
  const [reason, setReason] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const options = (["red", "yellow", "green"] as Urgency[]).filter((u) => u !== enc.urgency);
  const submit = async () => {
    setErr(null);
    if (!to) return setErr("Choose the new urgency");
    if (reason.trim().length < 15) return setErr("Write a reason of at least 15 characters");
    setBusy(true);
    try {
      onDone(await api.overrideUrgency(enc.id, to, category, reason));
      toast("Override recorded in audit log");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  };
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Override rules-engine urgency"
      subtitle="The original rules output is kept. Your reason is permanently written to the audit log."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button variant="danger" onClick={submit} loading={busy}>Record override</Button>
        </>
      }
    >
      <p className="text-sm text-muted">Current: <UrgencyBadge u={enc.urgency} size="sm" /> from rules {enc.note?.rules_fired.map((r) => r.rule_id).join(", ")}</p>
      <div className="mt-4 grid grid-cols-2 gap-2">
        {options.map((u) => (
          <button key={u} onClick={() => setTo(u)} className={cx("rounded-xl border p-3 text-left", to === u ? "border-ink bg-canvas" : "border-line")}>
            <UrgencyBadge u={u} />
            <p className="mt-1 text-xs text-muted">{u === "red" ? "Immediate" : u === "yellow" ? "Within 30–60 min" : "Standard OPD order"}</p>
          </button>
        ))}
      </div>
      <div className="mt-4">
        <Label htmlFor="ov-cat">Category</Label>
        <Select id="ov-cat" value={category} onChange={(e) => setCategory(e.target.value)}>
          {OVERRIDE_CATEGORIES.map((c) => <option key={c}>{c}</option>)}
        </Select>
      </div>
      <div className="mt-4">
        <Label htmlFor="ov-reason" hint={`${reason.trim().length}/15 min`}>Written reason (required)</Label>
        <Textarea id="ov-reason" rows={4} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Repeat BP 132/84 after rest; chest wall tenderness reproduces pain; ECG normal." />
      </div>
      <FieldError>{err}</FieldError>
    </Modal>
  );
}

function EscalateModal({ open, enc, onClose, onDone }: { open: boolean; enc: Encounter; onClose: () => void; onDone: () => void }) {
  const [to, setTo] = useState<"senior_mo" | "specialist" | "doctor">("senior_mo");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Escalate this case"
      subtitle="The receiving clinician must acknowledge. Unacknowledged escalations stay on their dashboard."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            variant="danger"
            loading={busy}
            onClick={async () => {
              setErr(null);
              if (reason.trim().length < 5) return setErr("Add a short reason");
              setBusy(true);
              try {
                await api.escalate(enc.id, to, reason);
                toast("Escalated — awaiting acknowledgement");
                onDone();
              } catch (e) {
                setErr(e instanceof Error ? e.message : "Failed");
              } finally {
                setBusy(false);
              }
            }}
          >
            Escalate
          </Button>
        </>
      }
    >
      <Label htmlFor="esc-to">Escalate to</Label>
      <Select id="esc-to" value={to} onChange={(e) => setTo(e.target.value as typeof to)}>
        <option value="senior_mo">Senior Medical Officer</option>
        <option value="specialist">Specialist on call</option>
        <option value="doctor">Doctor on duty</option>
      </Select>
      <div className="mt-4">
        <Label htmlFor="esc-reason">Reason</Label>
        <Textarea id="esc-reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. SpO₂ dropping on repeat, needs senior review now" />
      </div>
      <FieldError>{err}</FieldError>
    </Modal>
  );
}

function EditModal({ open, enc, onClose, onDone }: { open: boolean; enc: Encounter; onClose: () => void; onDone: (e: Encounter) => void }) {
  const [summary, setSummary] = useState(enc.note?.summary ?? "");
  const [missing, setMissing] = useState((enc.note?.missing_info ?? []).join("\n"));
  const [busy, setBusy] = useState(false);
  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title="Edit triage note"
      subtitle="Edits are attributed to you and logged. Urgency cannot be changed here — use Override."
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>Cancel</Button>
          <Button
            loading={busy}
            onClick={async () => {
              setBusy(true);
              try {
                onDone(await api.editNote(enc.id, { summary, missing_info: missing.split("\n").map((s) => s.trim()).filter(Boolean) }));
                toast("Note updated");
              } catch (e) {
                toast(e instanceof Error ? e.message : "Failed", "error");
              } finally {
                setBusy(false);
              }
            }}
          >
            Save changes
          </Button>
        </>
      }
    >
      <Label htmlFor="ed-sum">Summary</Label>
      <Textarea id="ed-sum" rows={6} value={summary} onChange={(e) => setSummary(e.target.value)} />
      <div className="mt-4">
        <Label htmlFor="ed-miss" hint="(one per line)">Missing information</Label>
        <Textarea id="ed-miss" rows={4} value={missing} onChange={(e) => setMissing(e.target.value)} />
      </div>
    </Modal>
  );
}

function ReferralModal({ open, enc, facility, onClose, onDone }: { open: boolean; enc: Encounter; facility: Facility | null; onClose: () => void; onDone: () => void }) {
  const spec = facility?.specialists.find((s) => s.key === enc.specialist_required);
  const defaultDest = spec?.available ? `${facility?.name} — ${spec.label} (in-house)` : facility?.referral_destination ?? "";
  const [destination, setDestination] = useState(defaultDest);
  const [specialty, setSpecialty] = useState(spec?.label ?? "General Medicine");
  const [reason, setReason] = useState("");
  const [transport, setTransport] = useState<"self" | "ambulance_108" | "facility_vehicle">(enc.urgency === "red" ? "ambulance_108" : "self");
  const [edited, setEdited] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const generated = useMemo(() => referralText(enc, facility, destination, specialty, reason || enc.chief_complaint), [enc, facility, destination, specialty, reason]);
  // Show the generated text until the doctor edits it by hand.
  const text = edited ?? generated;
  const setText = setEdited;

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="xl"
      title="Referral note"
      subtitle="Prepared from the triage note and this facility's specialist configuration. Review before sending."
      footer={
        <>
          <Button variant="secondary" icon={<Copy className="size-4" />} onClick={() => { navigator.clipboard?.writeText(text); toast("Copied"); }}>Copy</Button>
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
            Print
          </Button>
          <Button
            variant="teal"
            loading={busy}
            icon={transport === "ambulance_108" ? <Ambulance className="size-4" /> : <Send className="size-4" />}
            onClick={async () => {
              setBusy(true);
              try {
                await api.createReferral(enc.id, { destination, specialty, reason: reason || enc.chief_complaint, transport, note_text: text });
                toast("Referral sent and logged");
                onDone();
              } catch (e) {
                toast(e instanceof Error ? e.message : "Failed", "error");
              } finally {
                setBusy(false);
              }
            }}
          >
            Send referral
          </Button>
        </>
      }
    >
      <div className="grid gap-4 lg:grid-cols-[280px_1fr]">
        <div className="space-y-3">
          <div>
            <Label htmlFor="rf-dest">Destination</Label>
            <Select id="rf-dest" value={destination} onChange={(e) => setDestination(e.target.value)}>
              {spec?.available && <option>{`${facility?.name} — ${spec.label} (in-house)`}</option>}
              {facility && <option>{facility.referral_destination}</option>}
              <option>Tele-consultation (eSanjeevani hub)</option>
            </Select>
            {spec && !spec.available && <p className="mt-1 text-xs text-muted">{spec.label} is not on site today{spec.schedule ? ` (${spec.schedule})` : ""}.</p>}
          </div>
          <div>
            <Label htmlFor="rf-spec">Specialty</Label>
            <Select id="rf-spec" value={specialty} onChange={(e) => setSpecialty(e.target.value)}>
              {[...new Set([specialty, ...(facility?.specialists.map((s) => s.label) ?? []), "Emergency Medicine"])].map((s) => <option key={s}>{s}</option>)}
            </Select>
          </div>
          <div>
            <Label htmlFor="rf-reason">Reason</Label>
            <Textarea id="rf-reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder={enc.chief_complaint} />
          </div>
          <div>
            <Label htmlFor="rf-tr">Transport</Label>
            <Select id="rf-tr" value={transport} onChange={(e) => setTransport(e.target.value as typeof transport)}>
              <option value="ambulance_108">108 ambulance</option>
              <option value="facility_vehicle">Facility vehicle</option>
              <option value="self">Self / family</option>
            </Select>
          </div>
        </div>
        <div>
          <Label htmlFor="rf-text">Note text (editable)</Label>
          <Textarea id="rf-text" rows={20} value={text} onChange={(e) => setText(e.target.value)} className="font-mono text-[13px]" />
        </div>
      </div>
      <p className="mt-2 text-xs text-muted">Triage category: {enc.urgency && URGENCY_LABEL[enc.urgency]}. Export as PDF/FHIR from the case Export menu.</p>
    </Modal>
  );
}
