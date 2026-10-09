"use client";

import { useState } from "react";
import { usePrefs } from "@/components/providers";
import { fmtDate, fmtDateTime } from "@/lib/hooks";
import { AlertOctagon, AlertTriangle, Info, TrendingUp, TrendingDown, Minus, ListChecks, MessageCircleQuestion, Clock3, Scale, FlaskConical, Activity, Languages, Split, Lock, Bot, CalendarDays, History as HistoryIcon, ArrowRight } from "lucide-react";
import type { AiOpinion, Encounter, ExtractedValue, Flag, FollowUpAnswer, FollowUpQuestion, NoteHistory, SinceLast, TrendRow, Urgency } from "@/lib/types";
import { Badge, Button, Card, CardHeader, cx, Input } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { toast } from "@/components/ui/toast";
import { SourceEvidence } from "./source";
import { URGENCY_LABEL } from "@/lib/export";
import { langByCode } from "@/lib/i18n/languages";

export function UrgencyBadge({ u, size = "md" }: { u: Urgency | null; size?: "sm" | "md" | "lg" }) {
  const { tr } = usePrefs();
  if (!u) return null;
  const cls = { red: "bg-crit text-white", yellow: "bg-amber-400 text-ink", green: "bg-rout text-white" }[u];
  const sz = { sm: "px-1.5 py-0.5 text-[10px]", md: "px-2 py-0.5 text-xs", lg: "px-3 py-1 text-sm" }[size];
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-md font-bold tracking-wide uppercase", cls, sz)}>
      <span className="size-1.5 rounded-full bg-current opacity-70" aria-hidden />
      {tr(URGENCY_LABEL[u])}
    </span>
  );
}

export function urgencyBar(u: Urgency | null) {
  return u === "red" ? "bg-crit" : u === "yellow" ? "bg-amber-400" : u === "green" ? "bg-rout" : "bg-line";
}

function FlagIcon({ s }: { s: Flag["severity"] }) {
  if (s === "critical") return <AlertOctagon className="size-4 shrink-0 text-crit" />;
  if (s === "warning") return <AlertTriangle className="size-4 shrink-0 text-semi" />;
  return <Info className="size-4 shrink-0 text-blue-600" />;
}

/** The English original as a hover title when the screen shows a translation, so a clinician can always check the source wording. */
export const english = (tr: (s: string) => string, s: string) => (s && tr(s) !== s ? s : undefined);

/** Flags, not confidence percentages. */
export function FlagList({ flags, limit }: { flags: Flag[]; limit?: number }) {
  const { tr } = usePrefs();
  const order = { critical: 0, warning: 1, info: 2 };
  const list = [...flags].sort((a, b) => order[a.severity] - order[b.severity]).slice(0, limit);
  if (!list.length) return <p className="text-sm text-muted">{tr("No flags raised.")}</p>;
  // Clinical warnings first; how the data was captured (translation, OCR, offline…) after, under its own heading.
  const data = list.filter((f) => f.group === "data");
  if (data.length && data.length < list.length)
    return (
      <div className="space-y-3">
        <FlagRows list={list.filter((f) => f.group !== "data")} />
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">{tr("About the data")}</p>
        <FlagRows list={data} />
      </div>
    );
  return <FlagRows list={list} />;
}

function FlagRows({ list }: { list: Flag[] }) {
  const { tr } = usePrefs();
  return (
    <ul className="space-y-1.5">
      {list.map((f, i) => (
        <li key={i} className={cx("flex items-start gap-2 rounded-lg border px-2.5 py-2 text-sm", f.severity === "critical" ? "border-crit-line bg-crit-bg" : f.severity === "warning" ? "border-semi-line bg-semi-bg" : "border-blue-100 bg-blue-50/60")}>
          <FlagIcon s={f.severity} />
          <span className="min-w-0 flex-1">
            <span className="font-medium text-ink" title={english(tr, f.label)}>{tr(f.label)}</span>
            <span className="block text-xs text-muted" title={english(tr, f.reason)}>{tr(f.reason)}</span>
          </span>
          <code className="hidden shrink-0 text-[10px] text-subtle sm:block">{f.code}</code>
        </li>
      ))}
    </ul>
  );
}

/** Pertinent positives and negatives, allergies, medicines, past history: the lines a doctor looks for first. */
function HistoryList({ h }: { h: NoteHistory }) {
  const { tr } = usePrefs();
  const rows: [string, string][] = [
    [tr("On questioning"), h.positives.join("; ")],
    [tr("Denies"), h.negatives.join("; ")],
    [tr("Allergies"), tr(h.allergies)],
    [tr("Regular medicines"), h.medicines.join("; ") || tr("none reported")],
    [tr("Past history"), h.past.join("; ") || tr("none reported")],
  ];
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 border-t border-line px-4 py-3 text-sm">
      {rows.filter(([, v]) => v).map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="font-medium text-muted">{k}</dt>
          <dd className={k === tr("Allergies") && h.allergies === "not asked" ? "text-semi" : "text-ink"}>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function PresentingRows({ rows }: { rows: { label: string; value: string }[] }) {
  const { tr } = usePrefs();
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 px-4 pt-2 text-[15px] sm:px-5">
      {rows.map((r) => (
        <div key={r.label} className="contents">
          <dt className="text-sm font-medium text-muted">{tr(r.label)}</dt>
          <dd className={cx("text-ink", r.label === "Complaint" && "font-semibold")}>{tr(r.value)}</dd>
        </div>
      ))}
    </dl>
  );
}

/** The last visit beside this one: what changed in between, so a follow-up is read as a change, not from scratch. */
function SinceLastVisit({ s }: { s: SinceLast }) {
  const { tr } = usePrefs();
  const chips = (xs: string[], tone: "crit" | "semi" | "rout") => xs.map((x) => <Badge key={x} tone={tone}>{tr(x)}</Badge>);
  const medsChanged = s.medicines_then.join("|") !== s.medicines_now.join("|");
  const num = (v: string | number) => (typeof v === "number" ? v : parseFloat(String(v)));
  return (
    <div className="space-y-3 px-4 pt-2 text-sm sm:px-5">
      <p className="flex flex-wrap items-center gap-2 text-ink">
        <span className="font-semibold">{fmtDate(s.date)}</span>
        <span className="text-muted">({s.days_ago === 0 ? tr("earlier today") : tr("{n} days ago", { n: s.days_ago })})</span>
        {s.urgency && <UrgencyBadge u={s.urgency} size="sm" />}
        {s.decided_by && <span className="text-muted">· {tr("seen by")} {s.decided_by}</span>}
      </p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5">
        <dt className="font-medium text-muted">{tr("Came with")}</dt>
        <dd className="text-ink">{tr(s.complaint)}</dd>
        {s.override_reason && (
          <>
            <dt className="font-medium text-muted">{tr("Doctor's note")}</dt>
            <dd className="text-ink-2">“{tr(s.override_reason)}”</dd>
          </>
        )}
        {s.feeling && (
          <>
            <dt className="font-medium text-muted">{tr("Patient feels")}</dt>
            <dd className="text-ink">{tr(s.feeling)}</dd>
          </>
        )}
        {s.new_symptoms.length > 0 && (
          <>
            <dt className="font-medium text-muted">{tr("New since then")}</dt>
            <dd className="flex flex-wrap gap-1">{chips(s.new_symptoms, "crit")}</dd>
          </>
        )}
        {s.same_symptoms.length > 0 && (
          <>
            <dt className="font-medium text-muted">{tr("Still there")}</dt>
            <dd className="flex flex-wrap gap-1">{chips(s.same_symptoms, "semi")}</dd>
          </>
        )}
        {s.gone_symptoms.length > 0 && (
          <>
            <dt className="font-medium text-muted">{tr("Gone")}</dt>
            <dd className="flex flex-wrap gap-1">{chips(s.gone_symptoms, "rout")}</dd>
          </>
        )}
        {medsChanged && (
          <>
            <dt className="font-medium text-muted">{tr("Medicines")}</dt>
            <dd className="text-ink">
              {s.medicines_then.join("; ") || tr("none reported")} <ArrowRight className="inline size-3.5 text-muted" /> {s.medicines_now.join("; ") || tr("none reported")}
            </dd>
          </>
        )}
      </dl>
      {s.vitals.length > 0 && (
        <table className="w-full max-w-md text-sm">
          <thead>
            <tr className="border-b border-line text-left text-[11px] font-semibold tracking-wide text-subtle uppercase">
              <th className="py-1.5 pr-2 font-semibold">{tr("Vital")}</th>
              <th className="px-2 py-1.5 text-right font-semibold">{tr("Then")}</th>
              <th className="px-2 py-1.5 text-right font-semibold">{tr("Now")}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {s.vitals.map((v) => {
              const d = num(v.now) - num(v.then);
              return (
                <tr key={v.label}>
                  <td className="py-1.5 pr-2 text-ink">{tr(v.label)}</td>
                  <td className={cx("px-2 py-1.5 text-right tabular-nums", v.then_status === "abnormal" ? "text-crit" : "text-muted")}>{v.then}</td>
                  <td className={cx("px-2 py-1.5 text-right font-semibold tabular-nums", v.now_status === "abnormal" ? "text-crit" : "text-ink")}>
                    {v.now} {v.unit && <span className="text-xs font-normal text-muted">{v.unit}</span>}
                    {!Number.isNaN(d) && d !== 0 && <span className="ml-1 text-xs font-normal text-muted">({d > 0 ? "+" : ""}{Math.round(d * 10) / 10})</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

function statusTone(v: ExtractedValue) {
  return v.status === "abnormal" ? "text-crit" : v.status === "borderline" ? "text-semi" : "text-ink";
}

const attention = (v: ExtractedValue) => (v.status === "abnormal" ? 0 : v.needs_check ? 1 : v.status === "borderline" ? 2 : 3);

/** A lab-style table: test, result, normal range, status. What to check sits under the result; the report crop the value
 * was read from opens on demand. Out-of-range and to-check values come first; in a long list the within-range values fold
 * away so the reviewer reads what matters first (4-minute budget). */
export function ValueTable({ values, compact }: { values: ExtractedValue[]; compact?: boolean }) {
  const { tr } = usePrefs();
  const [open, setOpen] = useState(false);
  const [src, setSrc] = useState<string | null>(null);
  if (!values.length) return <p className="px-4 py-3 text-sm text-muted">{tr("Nothing recorded.")}</p>;
  const sorted = [...values].sort((a, b) => attention(a) - attention(b));
  const ok = sorted.filter((v) => attention(v) === 3);
  const fold = !compact && values.length >= 6 && ok.length >= 3 && ok.length < values.length;
  const shown = fold && !open ? sorted.filter((v) => attention(v) < 3) : sorted;
  const hasSource = !compact && values.some((v) => v.source.kind === "image_crop" || v.source.kind === "transcript");
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-[11px] font-semibold tracking-wide text-subtle uppercase">
            <th className="px-4 py-2 font-semibold">{tr("Test")}</th>
            <th className="px-2 py-2 text-right font-semibold">{tr("Result")}</th>
            {!compact && <th className="hidden px-3 py-2 font-semibold sm:table-cell">{tr("Normal range")}</th>}
            <th className="px-2 py-2 font-semibold">{tr("Status")}</th>
            {hasSource && <th className="px-4 py-2 text-right font-semibold">{tr("Source")}</th>}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {shown.map((v) => (
            <ValueRow key={v.id} v={v} compact={compact} hasSource={hasSource} open={src === v.id} onSource={() => setSrc(src === v.id ? null : v.id)} />
          ))}
        </tbody>
      </table>
      {fold && (
        <button type="button" onClick={() => setOpen((o) => !o)} className="w-full border-t border-line px-4 py-2.5 text-left text-sm font-medium text-teal-700 hover:bg-canvas">
          {open ? tr("Hide the values within range") : tr("Show {n} values within range", { n: ok.length })}
        </button>
      )}
    </div>
  );
}

function ValueRow({ v, compact, hasSource, open, onSource }: { v: ExtractedValue; compact?: boolean; hasSource: boolean; open: boolean; onSource: () => void }) {
  const { tr } = usePrefs();
  const cols = 3 + (compact ? 0 : 1) + (hasSource ? 1 : 0);
  return (
    <>
      <tr className={cx("align-top", v.status === "abnormal" && "bg-crit-bg/40")}>
        <td className="px-4 py-2.5">
          <p className="font-medium text-ink">{tr(v.label)}</p>
          {!compact && v.reference && <p className="text-[11px] text-subtle sm:hidden">{tr("Normal")}: {v.reference}</p>}
          {v.needs_check && !compact && (v.checks?.length ?? 0) > 0 && (
            <p className="mt-0.5 flex items-start gap-1 text-[11px] text-semi">
              <AlertTriangle className="mt-px size-3 shrink-0" /> {v.checks!.map((c) => tr(c)).join(" · ")}
            </p>
          )}
        </td>
        <td className={cx("px-2 py-2.5 text-right whitespace-nowrap tabular-nums", statusTone(v))}>
          <span className="text-base font-bold">{v.value}</span>
          {v.unit && <span className="ml-1 text-xs font-medium text-muted">{v.unit}</span>}
        </td>
        {!compact && <td className="hidden px-3 py-2.5 text-muted tabular-nums sm:table-cell">{v.reference ?? "—"}</td>}
        <td className="px-2 py-2.5">
          <span className="flex flex-wrap gap-1">
            {v.status === "abnormal" ? <Badge tone="crit">{tr("Out of range")}</Badge> : v.status === "borderline" ? <Badge tone="semi">{tr("Borderline")}</Badge> : <Badge tone="rout">{tr("Normal")}</Badge>}
            {v.needs_check && <Badge tone="semi">{tr("Check")}</Badge>}
          </span>
        </td>
        {hasSource && (
          <td className="px-4 py-2.5 text-right">
            {v.source.kind === "image_crop" || v.source.kind === "transcript" ? (
              <button type="button" onClick={onSource} aria-expanded={open} className="text-xs font-semibold text-teal-700 hover:underline">
                {open ? tr("Hide") : v.source.kind === "image_crop" ? tr("See in report") : tr("See words")}
              </button>
            ) : (
              <span className="text-[11px] text-subtle">{tr(v.source.kind === "sensor" ? "Device" : "Typed")}</span>
            )}
          </td>
        )}
      </tr>
      {open && (
        <tr>
          <td colSpan={cols} className="bg-canvas px-4 py-3">
            <div className="max-w-xl">
              <SourceEvidence v={v} />
              <p className="mt-1 text-[11px] text-muted">{tr("Read by")} {tr(v.source.engine)}</p>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

/** "2 out of range · 1 to check" for a card header, or null when everything is within range. */
export function valueSummary(values: ExtractedValue[], tr: (s: string, v?: Record<string, string | number>) => string): string | null {
  const out = values.filter((v) => v.status === "abnormal").length;
  const check = values.filter((v) => v.needs_check).length;
  const parts = [out && tr("{n} out of range", { n: out }), check && tr("{n} to check", { n: check })].filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}

export function Sparkline({ row }: { row: TrendRow }) {
  const { tr } = usePrefs();
  const vals = row.points.map((p) => p.value);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const W = 140;
  const H = 36;
  const pts = row.points.map((p, i) => [(i / Math.max(1, row.points.length - 1)) * (W - 8) + 4, H - 6 - ((p.value - min) / span) * (H - 12)] as const);
  const color = row.direction === "worse" ? "var(--color-crit)" : row.direction === "better" ? "var(--color-rout)" : "var(--color-muted)";
  return (
    <div className="flex items-center gap-3">
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} aria-hidden>
        <polyline points={pts.map((p) => p.join(",")).join(" ")} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
        {pts.map(([x, y], i) => (
          <circle key={i} cx={x} cy={y} r={i === pts.length - 1 ? 3.5 : 2.5} fill={i === pts.length - 1 ? color : "white"} stroke={color} strokeWidth="1.5" />
        ))}
      </svg>
      <div className="text-xs">
        <p className="font-medium text-ink">{row.parameter}</p>
        <p className="text-muted tabular-nums">{row.points.map((p) => p.value).join(" → ")}</p>
      </div>
      <span className={cx("ml-auto inline-flex items-center gap-1 text-xs font-semibold", row.direction === "worse" ? "text-crit" : row.direction === "better" ? "text-rout" : "text-muted")}>
        {row.direction === "worse" ? <TrendingUp className="size-3.5" /> : row.direction === "better" ? <TrendingDown className="size-3.5" /> : <Minus className="size-3.5" />}
        {row.direction === "worse" ? tr("Worse") : row.direction === "better" ? tr("Better") : tr("Stable")}
      </span>
    </div>
  );
}

/** C8: the model's own tier beside the rules' tier. Informational only: it never changes urgency. */
export function SecondOpinion({ op }: { op: AiOpinion }) {
  const { tr } = usePrefs();
  const compared = op.status === "AGREE" || op.status === "DISAGREE";
  return (
    <div className="border-t border-line px-4 py-3 text-sm">
      <p className="flex flex-wrap items-center gap-1.5 font-semibold text-ink">
        <Bot className="size-4 text-teal-700" /> {tr("AI second opinion")}
        <span className="text-xs font-normal text-subtle">· {tr("does not change urgency")}</span>
      </p>
      {compared ? (
        <>
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1.5">
            <span className="flex items-center gap-1.5 text-xs text-muted">{tr("Rules")} <UrgencyBadge u={op.rules_urgency} size="sm" /></span>
            <span className="flex items-center gap-1.5 text-xs text-muted">{tr("AI model")} <UrgencyBadge u={op.model_urgency ?? null} size="sm" /></span>
            {op.status === "AGREE" ? (
              <Badge tone="rout">{tr("Agrees with the rules")}</Badge>
            ) : op.direction === "higher" ? (
              <Badge tone="semi">{tr("More urgent than the rules — take a second look")}</Badge>
            ) : (
              <Badge>{tr("Less urgent than the rules — the rules stand")}</Badge>
            )}
          </div>
          {op.reason && <p className="mt-2 rounded-lg bg-canvas px-3 py-2 text-ink-2">“{op.reason}”</p>}
          {op.reason_withheld && (
            <details className="mt-2 text-xs">
              <summary className="cursor-pointer text-muted">{tr("Reason hidden: it failed the safety checks")}</summary>
              <ul className="mt-1 list-disc pl-5 text-crit">{op.reason_withheld.map((r) => <li key={r}>{r}</li>)}</ul>
            </details>
          )}
        </>
      ) : (
        <p className="mt-1 text-muted">
          {op.status === "UNAVAILABLE" ? tr("AI model not available, so there is no second opinion.") : tr("The model's answer could not be read, so no opinion is shown.")}
        </p>
      )}
      <p className="mt-2 text-xs text-subtle">
        {tr("Urgency comes only from the rules. Only a doctor can change it, with a written reason.")} · {op.model.split(" (")[0]}
        {op.ms ? ` · ${(op.ms / 1000).toFixed(1)} s` : ""}
      </p>
    </div>
  );
}

/**
 * Role-differentiated rendering (E2): the same note at two densities.
 * Doctor = full case with evidence and rules trace. Nurse = actionable checklist.
 */
/** C7: a case the rules cannot yet rule out is shown as UNDETERMINED, held at YELLOW, never as routine. */
export function Undetermined({ note, compact }: { note: NonNullable<Encounter["note"]>; compact?: boolean }) {
  const { tr } = usePrefs();
  const t = note.triage;
  if (!t?.provisional) return null;
  const needs = [...new Set([...(t.missing_for_green ?? []), ...(t.unresolved ?? []).flatMap((u) => u.needs.map((x) => (x.startsWith("danger-sign") ? "clinician danger-sign check" : x)))])];
  return (
    <div className={cx("border-semi-line bg-semi-bg px-4 py-2.5 text-sm", compact ? "rounded-xl border" : "border-b")}>
      <p className="font-semibold text-semi">{tr("UNDETERMINED — held at YELLOW until measured")}</p>
      <p className="text-ink-2">{tr("Unknown is never treated as normal. Measure or check before this case can be routine:")}</p>
      <ul className="mt-1 flex flex-wrap gap-1.5">
        {needs.map((x) => (
          <li key={x} className="rounded-md border border-semi-line bg-surface px-2 py-0.5 text-xs text-ink">{tr(x)}</li>
        ))}
      </ul>
    </div>
  );
}

/** Note density by role (E2): the doctor and medical officer see everything; the nurse a working view; the health worker
 * a short form (summary, flags, what is missing, their own questions, vital signs). */
export function NoteView({ enc, density, onUpdated }: { enc: Encounter; density: "doctor" | "nurse" | "health_worker"; onUpdated?: (e: Encounter) => void }) {
  if (!enc.note) return null;
  return density === "doctor" ? <ClinicalNote enc={enc} onUpdated={onUpdated} /> : <BedsideNote enc={enc} density={density} onUpdated={onUpdated} />;
}

const YES_NO = ["Yes", "No", "Not sure"];

/** One follow-up question the patient can answer at the bedside: answer buttons (or their words), saved to the record.
 * The rules run again on the answer, so a "yes" to a danger question raises urgency. Read-only without onUpdated. */
function AskQuestion({ enc, q, n, onUpdated }: { enc: Encounter; q: FollowUpQuestion; n: number; onUpdated?: (e: Encounter) => void }) {
  const { tr } = usePrefs();
  const options = q.options ?? YES_NO;
  const [pick, setPick] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const ready = options.length ? !!pick : !!text.trim();
  const save = async () => {
    setBusy(true);
    setErr(null);
    try {
      const before = enc.urgency;
      const e = await api.answerFollowup(enc.id, { qid: q.id ?? q.tag, answer: pick, text: text.trim() || null });
      toast(e.urgency !== before ? tr("Answer saved — the rules raised the urgency; the doctor has been alerted in the queue") : tr("Answer saved to the patient's history"), e.urgency !== before ? "info" : "success");
      onUpdated!(e);
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : tr("Could not save"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <li className="px-4 py-3">
      <div className="flex gap-2 text-sm">
        <span className="font-semibold text-teal-700 tabular-nums">{n}.</span>
        <div className="min-w-0 flex-1">
          <p className="text-ink">
            {tr(q.question)} <span className="ml-1 text-[11px] font-medium text-subtle uppercase">{tr(q.tag)}</span>
          </p>
          {onUpdated && (
            <div className="mt-2 space-y-2">
              {options.length > 0 && (
                <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label={tr(q.question)}>
                  {options.map((o) => (
                    <button key={o} type="button" role="radio" aria-checked={pick === o} onClick={() => setPick(pick === o ? null : o)}
                      className={cx("rounded-lg border px-3 py-1 text-sm font-medium transition-colors", pick === o ? "border-teal-700 bg-teal-700 text-white" : "border-line bg-surface text-ink hover:bg-canvas")}>
                      {tr(o)}
                    </button>
                  ))}
                </div>
              )}
              <div className="flex gap-2">
                <Input value={text} onChange={(e) => setText(e.target.value)} maxLength={300} className="h-9 flex-1 text-sm"
                  placeholder={options.length ? tr("Patient's words (optional)") : tr("What the patient said")} aria-label={tr("Patient's words")} />
                <Button size="sm" variant="teal" className="h-9" disabled={!ready} loading={busy} onClick={save}>{tr("Save")}</Button>
              </div>
              {err && <p className="text-xs text-crit">{err}</p>}
            </div>
          )}
        </div>
      </div>
    </li>
  );
}

/** Questions put to the patient at the bedside and their answers, with who asked and when. */
function AnsweredList({ answers }: { answers: FollowUpAnswer[] }) {
  const { tr } = usePrefs();
  if (!answers.length) return null;
  return (
    <div className="border-t border-line px-4 py-3">
      <p className="text-xs font-semibold text-muted uppercase">{tr("Asked at the bedside")}</p>
      <ul className="mt-1.5 space-y-2 text-sm">
        {answers.map((a) => (
          <li key={a.qid}>
            <p className="text-ink-2">{tr(a.question)}</p>
            <p className="text-ink">
              <span className="font-semibold">{tr(a.answer === "Told" ? "Answer" : a.answer)}</span>
              {a.text && <span> — “{a.text}”</span>}
            </p>
            <p className="text-[11px] text-subtle">{a.by} · {fmtDateTime(a.at)}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** A numbered section of the clinical note. */
function Section({ n, title, aside, icon, children, tone }: { n: number; title: string; aside?: React.ReactNode; icon: React.ReactNode; children: React.ReactNode; tone?: "crit" | "semi" }) {
  return (
    <section className={cx("border-t border-line", tone === "crit" && "bg-crit-bg/30", tone === "semi" && "bg-semi-bg/30")}>
      <div className="flex flex-wrap items-baseline justify-between gap-2 px-4 pt-3 sm:px-5">
        <h3 className="flex items-center gap-2 text-sm font-bold tracking-wide text-ink uppercase">
          <span className="grid size-5 place-items-center rounded-full bg-ink text-[11px] text-white">{n}</span>
          <span className="text-muted [&>svg]:size-4">{icon}</span>
          {title}
        </h3>
        {aside && <span className="text-xs text-muted">{aside}</span>}
      </div>
      <div className="pb-3">{children}</div>
    </section>
  );
}

/** Vitals as tiles: value, unit and a word status; "not measured" is shown, never left blank. */
function VitalsGrid({ values }: { values: ExtractedValue[] }) {
  const { tr } = usePrefs();
  const KEYS: [string, string][] = [
    ["BP", "BP"], ["Pulse", "Pulse"], ["SpO", "SpO₂"], ["Resp", "Resp. rate"], ["Temp", "Temperature"], ["Glucose", "Glucose"], ["AVPU", "AVPU"],
  ];
  const tiles = KEYS.map(([k, label]) => {
    const vs = values.filter((v) => v.label.toLowerCase().includes(k.toLowerCase()));
    return { label, vs };
  });
  const others = values.filter((v) => !KEYS.some(([k]) => v.label.toLowerCase().includes(k.toLowerCase())));
  return (
    <div className="grid grid-cols-2 gap-2 px-4 pt-2 sm:grid-cols-4 sm:px-5 lg:grid-cols-7">
      {tiles.map(({ label, vs }) => {
        const worst = vs.find((v) => v.status === "abnormal") ?? vs.find((v) => v.status === "borderline") ?? vs[0];
        const value = label === "BP" && vs.length === 2 ? `${vs.find((v) => /systolic/i.test(v.label))?.value ?? "?"}/${vs.find((v) => /diastolic/i.test(v.label))?.value ?? "?"}` : vs.map((v) => v.value).join(" / ");
        return (
          <div key={label} className={cx("rounded-xl border px-3 py-2", !worst ? "border-dashed border-line" : worst.status === "abnormal" ? "border-crit-line bg-crit-bg" : worst.status === "borderline" ? "border-semi-line bg-semi-bg" : "border-line bg-surface")}>
            <p className="text-[11px] font-semibold tracking-wide text-muted uppercase">{tr(label)}</p>
            {worst ? (
              <p className={cx("text-lg font-bold tabular-nums", statusTone(worst))}>
                {value}
                {worst.unit && <span className="ml-1 text-[11px] font-medium text-muted">{worst.unit}</span>}
                {vs.some((v) => v.needs_check) && <AlertTriangle className="ml-1 inline size-3.5 text-semi" aria-label={tr("Check")} />}
              </p>
            ) : (
              <p className="text-sm text-subtle">{tr("Not measured")}</p>
            )}
          </div>
        );
      })}
      {others.map((v) => (
        <div key={v.id} className={cx("rounded-xl border px-3 py-2", v.status === "abnormal" ? "border-crit-line bg-crit-bg" : "border-line")}>
          <p className="truncate text-[11px] font-semibold tracking-wide text-muted uppercase">{tr(v.label)}</p>
          <p className={cx("text-lg font-bold tabular-nums", statusTone(v))}>
            {v.value}
            {v.unit && <span className="ml-1 text-[11px] font-medium text-muted">{v.unit}</span>}
          </p>
        </div>
      ))}
    </div>
  );
}

/** The doctor's note, read top to bottom in the order a clinician decides: why this urgency, what the patient says,
 * history, vitals, investigations, what to do next. How the note was produced (rule IDs, engines, timeline, AI checks)
 * is kept at the end, folded, for audit. */
/** "Blurred vision — answer to \"…\" (asked by X): Yes — WHO … age ≥12" → "Blurred vision — answered Yes at the bedside".
 * The full reason stays in the tooltip; the protocol source is already on the rule line. */
function shortReason(reason: string) {
  const parts = reason.split(" — ");
  if (parts.length < 2) return reason;
  const what = parts[0];
  const how = parts[1];
  const m = how.match(/^answer to ".*" \(asked by .*\): (.+)$/);
  if (m) return `${what} — answered ${m[1]} at the bedside`;
  return what;
}

function ClinicalNote({ enc, onUpdated }: { enc: Encounter; onUpdated?: (e: Encounter) => void }) {
  const { tr } = usePrefs();
  const n = enc.note!;
  const answered = n.followup_answered ?? [];
  const t = n.triage;
  const tier = enc.urgency;
  const decisive = n.rules_fired.filter((r) => r.rule_id !== "SAFE-PROVISIONAL" && r.urgency === (t?.urgency ?? tier));
  const supporting = n.rules_fired.filter((r) => r.rule_id !== "SAFE-PROVISIONAL" && !decisive.includes(r));
  const measure = [...new Set([...(t?.missing_for_green ?? []), ...(t?.unresolved ?? []).flatMap((u) => u.needs.map((x) => (x.startsWith("danger-sign") ? "clinician danger-sign check" : x)))])];
  // A rule already listed under "Because" is not repeated as a flag below it.
  const clinicalFlags = n.flags.filter((f) => f.group !== "data" && f.code !== "SAFE-PROVISIONAL" && !decisive.some((r) => r.rule_id === f.code));
  const dataFlags = n.flags.filter((f) => f.group === "data");
  const words = n.original_words?.length ? n.original_words : n.transcript ? [n.transcript] : [];
  const otherMissing = n.missing_info.filter((m) => !/needed before the case can be routine|^Ask \/ measure:/.test(m));
  const byRole = (["doctor", "medical_officer", "nurse", "health_worker"] as const)
    .map((r) => ({ r, qs: n.followup_questions.filter((q) => q.for_role === r) }))
    .filter((x) => x.qs.length);
  const redOpen = t?.unresolved.filter((u) => u.urgency === "red") ?? [];
  let s = 0;

  return (
    <div className="space-y-4">
      <Card className="overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 sm:px-5">
          <div>
            <h2 className="text-lg font-bold text-ink">{tr("Triage note")}</h2>
            <p className="text-xs text-muted">
              {tr("Organised from patient-provided information")} · {fmtDateTime(n.generated_at)}
              {n.edited_by ? ` · ${tr("edited by {name}", { name: n.edited_by })}` : ""}
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            {n.renderer === "LLM" && !n.edited_by ? <Badge tone="teal">{tr("Written by {model} · checked against the record", { model: n.llm?.model.split(" (")[0] ?? "AI" })}</Badge> : <Badge>{tr("Template summary")}</Badge>}
            {n.llm?.status === "FAIL_FELL_BACK" && <Badge tone="semi">{tr("AI summary rejected by the checks")}</Badge>}
          </div>
        </div>

        {/* 1. Assessment: why this urgency */}
        <Section n={++s} title={tr("Assessment")} icon={<Scale />} tone={tier === "red" ? "crit" : t?.provisional ? "semi" : undefined} aside={t ? `${t.protocols.map((p) => p.key).join(" + ")} · ${tr("rulepack")} ${t.rulepack_version}` : undefined}>
          <div className="space-y-2 px-4 pt-2 sm:px-5">
            <p className="flex flex-wrap items-center gap-2 text-[15px] text-ink">
              <UrgencyBadge u={tier} size="lg" />
              <span className="font-semibold">
                {t?.provisional && !decisive.length ? tr("Held at YELLOW: not yet safe to call routine") : decisive.length ? tr("Because:") : tr("No urgent rule matched")}
              </span>
            </p>
            {decisive.length > 0 && (
              <ul className="space-y-1.5">
                {decisive.map((r) => (
                  <li key={r.rule_id} className="flex items-start gap-2 text-sm">
                    <span className={cx("mt-1 h-4 w-1 shrink-0 rounded-full", urgencyBar(r.urgency))} />
                    <span className="min-w-0">
                      <span className="font-medium text-ink" title={english(tr, r.description)}>{tr(r.description)}</span>
                      {r.non_downgradable && r.urgency === "red" && (
                        <span title={tr("Non-downgradable: only a doctor can lower it, with a written reason that is audited")} className="ml-1.5 inline-flex items-center gap-0.5 rounded bg-crit-bg px-1.5 text-[10px] font-semibold text-crit uppercase">
                          <Lock className="size-3" /> {tr("locked")}
                        </span>
                      )}
                      {(r.evidence?.length ?? 0) > 0 && <span className="block text-xs text-ink-2" title={r.evidence!.join(" | ")}>{tr("Found")}: {r.evidence!.map((e) => tr(e.split(" — ")[0])).join(", ")}</span>}
                      <span className="block font-mono text-[10px] text-subtle">{r.rule_id} · {r.source ?? r.protocol}</span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {measure.length > 0 && (
              <div className="text-sm">
                <p className="text-ink-2">{tr("To rule out a more urgent tier, measure:")}</p>
                <ul className="mt-1 flex flex-wrap gap-1.5">
                  {measure.map((x) => (
                    <li key={x} className="rounded-md border border-semi-line bg-surface px-2 py-0.5 text-xs font-medium text-ink">{tr(x)}</li>
                  ))}
                </ul>
              </div>
            )}
            {clinicalFlags.length > 0 && (
              <ul className="space-y-1 pt-1">
                {clinicalFlags.map((f, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm">
                    <FlagIcon s={f.severity} />
                    <span>
                      <span className="font-medium text-ink">{tr(f.label)}</span> <span className="text-muted" title={f.reason}>— {tr(shortReason(f.reason))}</span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
            {enc.override && (
              <div className="rounded-lg border border-coral-200 bg-coral-50 px-3 py-2 text-sm">
                <p className="font-semibold text-coral-700">
                  {tr("Clinician override:")} {tr(URGENCY_LABEL[enc.override.from_urgency])} → {tr(URGENCY_LABEL[enc.override.to_urgency])}
                </p>
                <p className="text-ink-2">“{tr(enc.override.reason)}”</p>
                <p className="text-xs text-muted">{enc.override.by} · {fmtDateTime(enc.override.at)} · {tr(enc.override.category)}</p>
              </div>
            )}
          </div>
        </Section>

        {/* 2. Presenting complaint */}
        <Section n={++s} title={tr("Presenting complaint")} icon={<MessageCircleQuestion />}>
          {n.presenting?.length ? <PresentingRows rows={n.presenting} /> : <p className="px-4 pt-2 text-[15px] leading-relaxed text-ink sm:px-5">{n.renderer === "LLM" ? n.summary : tr(n.hpi ?? n.summary)}</p>}
          {words.length > 0 && (
            <div className="space-y-2 px-4 pt-3 sm:px-5">
              {words.map((w, i) => (
                <div key={i} className="grid gap-2 text-sm sm:grid-cols-2">
                  <p lang={w.language} className="rounded-lg bg-canvas p-2.5 text-ink">
                    <span className="mb-0.5 block text-[11px] font-semibold text-muted uppercase">{tr("Patient's words")} · {tr(langByCode(w.language).name)}</span>
                    {w.original}
                  </p>
                  <p className="rounded-lg border border-line p-2.5 text-ink-2">
                    <span className="mb-0.5 block text-[11px] font-semibold text-muted uppercase">{tr("Machine translation: check against the patient's words")}</span>
                    {w.translated}
                  </p>
                </div>
              ))}
            </div>
          )}
        </Section>

        {/* Follow-up visit: what changed since the last one */}
        {n.since_last && (
          <Section n={++s} title={tr("Since the last visit")} icon={<HistoryIcon />}>
            <SinceLastVisit s={n.since_last} />
          </Section>
        )}

        {/* 3. History */}
        {(n.history || answered.length > 0) && (
          <Section n={++s} title={tr("History")} icon={<ListChecks />}>
            {n.history && <HistoryList h={n.history} />}
            <AnsweredList answers={answered} />
          </Section>
        )}

        {/* 4. Vitals */}
        <Section n={++s} title={tr("Vitals")} icon={<Activity />} aside={valueSummary(n.vitals, tr) ?? undefined}>
          <VitalsGrid values={n.vitals} />
        </Section>

        {/* 5. Investigations */}
        {n.labs.length > 0 && (
          <Section n={++s} title={tr("Investigations")} icon={<FlaskConical />} aside={valueSummary(n.labs, tr) ?? tr("Read from uploaded reports")}>
            <div className="pt-1">
              <ValueTable values={n.labs} />
            </div>
          </Section>
        )}

        {/* 6. Trend */}
        {n.trend.length > 0 && (
          <Section n={++s} title={enc.category === "maternal" ? tr("Across antenatal visits") : tr("Compared with previous visits")} icon={<TrendingUp />}>
            <div className="space-y-3 px-4 pt-2 sm:px-5">
              {n.trend.map((r) => (
                <Sparkline key={r.parameter} row={r} />
              ))}
            </div>
          </Section>
        )}

        {/* 7. Plan */}
        {(byRole.length > 0 || otherMissing.length > 0) && (
          <Section n={++s} title={tr("Still to ask or do")} icon={<Clock3 />}>
            {byRole.length > 0 && onUpdated && <p className="px-4 pt-1 text-xs text-muted sm:px-5">{tr("Ask the patient and save the answer: it joins the history and the rules re-check the urgency.")}</p>}
            <div className="grid gap-4 px-4 pt-2 sm:px-5">
              {byRole.map(({ r, qs }) => (
                <div key={r}>
                  <p className="text-xs font-semibold text-teal-700 uppercase">{tr("For the {r}", { r: tr(r.replace("_", " ")) })}</p>
                  <ol className="-mx-4 mt-1 divide-y divide-line">
                    {qs.map((q, i) => (
                      <AskQuestion key={q.id ?? q.tag} enc={enc} q={q} n={i + 1} onUpdated={onUpdated} />
                    ))}
                  </ol>
                </div>
              ))}
              {otherMissing.length > 0 && (
                <div>
                  <p className="text-xs font-semibold text-coral-700 uppercase">{tr("Missing information")}</p>
                  <ul className="mt-1 list-disc space-y-1 pl-5 text-sm text-ink">
                    {otherMissing.map((m) => (
                      <li key={m}>{tr(m)}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </Section>
        )}
      </Card>

      {n.disagreements.length > 0 && (
        <Card className="border-semi-line">
          <CardHeader title={tr("Sources disagree")} subtitle={tr("Values captured from different sources do not match")} icon={<Split className="size-4 text-semi" />} />
          <ul className="divide-y divide-line">
            {n.disagreements.map((d, i) => (
              <li key={i} className="px-4 py-3 text-sm">
                <p className="font-semibold text-ink">{tr(d.field)}</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  {d.values.map((v) => (
                    <span key={v.engine} className="rounded-lg border border-line bg-canvas px-2 py-1">
                      <span className="text-xs text-muted">{tr(v.engine)}:</span> <span className="font-semibold tabular-nums">{v.value}</span>
                    </span>
                  ))}
                </div>
                <p className="mt-1.5 text-xs font-medium text-semi">{tr(d.action)}</p>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {n.llm_opinion && (
        <Card>
          <SecondOpinion op={n.llm_opinion} />
        </Card>
      )}

      {/* Audit: how the note was produced */}
      <details className="group rounded-[var(--radius-card)] border border-line bg-surface">
        <summary className="flex cursor-pointer items-center justify-between gap-2 px-4 py-3 text-sm font-semibold text-ink sm:px-5">
          <span className="flex items-center gap-2"><Bot className="size-4 text-muted" /> {tr("How this note was made")}</span>
          <span className="text-xs font-normal text-muted">{tr("Full rule trace, timeline, capture checks")} · {n.generated_by}</span>
        </summary>
        <div className="grid gap-4 border-t border-line p-4 sm:p-5 xl:grid-cols-2">
          <div>
            <p className="mb-2 text-xs font-semibold tracking-wide text-muted uppercase">{tr("Rules engine trace")}</p>
            <ul className="divide-y divide-line rounded-xl border border-line">
              {[...decisive, ...supporting, ...n.rules_fired.filter((r) => r.rule_id === "SAFE-PROVISIONAL")].map((r) => (
                <li key={r.rule_id} className="flex items-start gap-2 px-3 py-2 text-sm">
                  <span className={cx("mt-1 h-4 w-1 shrink-0 rounded-full", urgencyBar(r.urgency))} />
                  <span className="min-w-0 flex-1">
                    <span className="text-ink">{tr(r.description)}</span>
                    <span className="block font-mono text-[10px] text-subtle">{r.rule_id} · {r.source ?? r.protocol}</span>
                  </span>
                  <UrgencyBadge u={r.urgency} size="sm" />
                </li>
              ))}
            </ul>
            {redOpen.length > 0 && (
              <>
                <p className="mt-3 mb-1 text-xs font-semibold tracking-wide text-muted uppercase">{tr("RED rules not yet ruled out")} ({redOpen.length})</p>
                <ul className="space-y-1 text-xs text-ink-2">
                  {redOpen.map((u) => (
                    <li key={u.rule_id}>
                      <span className="font-mono text-subtle">{u.rule_id}</span> {tr(u.description)} — {tr("needs")}: {u.needs.map((x) => tr(x)).join(", ")}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </div>
          <div className="space-y-4">
            {n.timeline.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-semibold tracking-wide text-muted uppercase">{tr("Timeline")}</p>
                <ol className="space-y-1.5 text-sm">
                  {n.timeline.map((e, i) => (
                    <li key={i} className="flex gap-2">
                      <span className="w-28 shrink-0 text-xs text-subtle">{tr(e.when)}</span>
                      <span className="text-ink">
                        {tr(e.event)}
                        {e.certainty && e.certainty !== "RECORDED" && <span className="ml-1 text-[10px] text-muted uppercase">({tr(e.certainty)})</span>}
                        {e.basis && <span className="block text-xs text-subtle"><CalendarDays className="mr-1 inline size-3" />{e.basis}</span>}
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
            )}
            {dataFlags.length > 0 && (
              <div>
                <p className="mb-2 text-xs font-semibold tracking-wide text-muted uppercase">{tr("Capture checks")}</p>
                <FlagRows list={dataFlags} />
              </div>
            )}
            {n.renderer === "LLM" && n.summary_template && (
              <div>
                <p className="mb-1 text-xs font-semibold tracking-wide text-muted uppercase">{tr("Template summary (facts as recorded)")}</p>
                <p className="text-sm text-ink-2">{tr(n.summary_template)}</p>
              </div>
            )}
            {n.llm?.status === "FAIL_FELL_BACK" && n.llm.rejected_text && (
              <div>
                <p className="mb-1 text-xs font-semibold tracking-wide text-muted uppercase">{tr("Rejected AI text and why")}</p>
                <p className="rounded-lg bg-canvas p-2.5 text-sm text-ink-2 line-through decoration-crit/60">{n.llm.rejected_text}</p>
                <ul className="mt-1.5 list-disc pl-5 text-xs text-crit">
                  {[...(n.llm.guard ?? []), ...(n.llm.faithfulness ?? [])].map((r) => <li key={r}>{r}</li>)}
                </ul>
              </div>
            )}
          </div>
        </div>
      </details>
    </div>
  );
}

/** What a nurse or health worker needs at the bedside, in order: what the patient said, what to do now, what to measure
 * before the case can be routine, and what to ask. Rule IDs, engines and the full trace stay in the doctor's view. */
function BedsideNote({ enc, density, onUpdated }: { enc: Encounter; density: "nurse" | "health_worker"; onUpdated?: (e: Encounter) => void }) {
  const { tr } = usePrefs();
  const n = enc.note!;
  const answered = n.followup_answered ?? [];
  const sees = density === "health_worker" ? ["health_worker"] : ["health_worker", "nurse"];
  const questions = n.followup_questions.filter((q) => sees.includes(q.for_role));
  const clinical = n.flags.filter((f) => f.group !== "data" && f.code !== "SAFE-PROVISIONAL" && f.severity !== "info");
  const dataFlags = n.flags.filter((f) => f.group === "data");
  const t = n.triage;
  // One list of what to measure or check, instead of the same items in a flag, a rule list and a "still missing" card.
  const measure = [
    ...new Set([
      ...(t?.missing_for_green ?? []),
      ...(t?.unresolved ?? []).flatMap((u) => u.needs.map((x) => (x.startsWith("danger-sign") ? "clinician danger-sign check" : x))),
    ]),
  ];
  const otherMissing = n.missing_info.filter((m) => !/needed before the case can be routine|^Ask \/ measure:/.test(m));
  const words = n.original_words?.length ? n.original_words : n.transcript ? [n.transcript] : [];
  const recorded = n.vitals.filter((v) => v.value !== null && v.value !== undefined && v.value !== "");
  const abnormalLabs = (n.labs ?? []).filter((v) => v.status === "abnormal" || v.status === "borderline" || v.needs_check);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title={tr("What the patient told us")} icon={<Languages className="size-4" />} />
        <div className="space-y-3 px-4 py-3 text-[15px]">
          {words.map((w, i) => (
            <div key={i} className="grid gap-2 sm:grid-cols-2">
              <p lang={w.language} className="rounded-lg bg-canvas p-2.5 text-ink">
                <span className="mb-0.5 block text-xs text-muted">{tr(langByCode(w.language).name)}</span>
                {w.original}
              </p>
              <p className="rounded-lg border border-line p-2.5 text-ink-2">
                <span className="mb-0.5 block text-xs text-muted">{tr("Machine translation: check with the patient")}</span>
                {w.translated}
              </p>
            </div>
          ))}
          {n.presenting?.length ? <PresentingRows rows={n.presenting} /> : <p className="leading-relaxed text-ink">{n.renderer === "LLM" ? n.summary : tr(n.hpi ?? n.summary)}</p>}
        </div>
        {n.history && <HistoryList h={n.history} />}
        <AnsweredList answers={answered} />
        {abnormalLabs.length > 0 && (
          <div className="border-t border-line">
            <p className="flex items-center gap-1.5 px-4 pt-3 text-sm font-semibold text-ink">
              <FlaskConical className="size-4" /> {tr("From the uploaded reports")}
            </p>
            <ValueTable values={abnormalLabs} compact />
          </div>
        )}
      </Card>

      {clinical.length > 0 && (
        <Card className="border-crit-line">
          <CardHeader title={tr("Act on this now")} icon={<AlertOctagon className="size-4 text-crit" />} />
          <ul className="space-y-2 p-4 text-sm">
            {clinical.map((f, i) => (
              <li key={i} className="flex gap-2">
                <FlagIcon s={f.severity} />
                <span>
                  <span className="font-semibold text-ink">{tr(f.label)}</span>
                  <span className="block text-muted">{tr(f.reason)}</span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}

      {(measure.length > 0 || otherMissing.length > 0) && (
        <Card className="border-semi-line">
          <CardHeader
            title={tr("Measure before this can be routine")}
            subtitle={t?.provisional ? tr("Held at YELLOW until these are recorded: unknown is never treated as normal.") : undefined}
            icon={<ListChecks className="size-4 text-semi" />}
          />
          <ul className="flex flex-wrap gap-2 p-4">
            {measure.map((x) => (
              <li key={x} className="rounded-lg border border-semi-line bg-semi-bg px-2.5 py-1 text-sm font-medium text-ink">
                {tr(x)}
              </li>
            ))}
          </ul>
          {otherMissing.length > 0 && (
            <ul className="space-y-1 border-t border-line px-4 py-3 text-sm text-ink-2">
              {otherMissing.map((m) => (
                <li key={m}>• {tr(m)}</li>
              ))}
            </ul>
          )}
          <p className="border-t border-line px-4 py-2.5 text-xs text-muted">{tr("Use the form on the left; the urgency is re-checked as soon as you save.")}</p>
        </Card>
      )}

      {questions.length > 0 && (
        <Card>
          <CardHeader title={tr("Ask the patient")} subtitle={onUpdated ? tr("Save each answer: it joins the history and the rules re-check the urgency.") : undefined} icon={<MessageCircleQuestion className="size-4" />} />
          <ol className="divide-y divide-line">
            {questions.map((q, i) => (
              <AskQuestion key={q.id ?? q.tag} enc={enc} q={q} n={i + 1} onUpdated={onUpdated} />
            ))}
          </ol>
        </Card>
      )}

      {recorded.length > 0 && (
        <Card>
          <CardHeader title={tr("Vitals recorded")} icon={<Activity className="size-4" />} />
          <ValueTable values={n.vitals} compact />
        </Card>
      )}

      {dataFlags.length > 0 && (
        <details className="rounded-2xl border border-line bg-surface px-4 py-3 text-sm">
          <summary className="cursor-pointer font-medium text-muted">{tr("How this was captured")} ({dataFlags.length})</summary>
          <ul className="mt-2 space-y-1.5">
            {dataFlags.map((f, i) => (
              <li key={i}>
                <span className="font-medium text-ink">{tr(f.label)}</span>
                <span className="block text-xs text-muted">{tr(f.reason)}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
