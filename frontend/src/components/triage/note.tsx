"use client";

import { useState } from "react";
import { usePrefs } from "@/components/providers";
import { fmtDateTime } from "@/lib/hooks";
import { AlertOctagon, AlertTriangle, Info, TrendingUp, TrendingDown, Minus, ListChecks, MessageCircleQuestion, Clock3, Scale, FlaskConical, Activity, Languages, Split, Lock, Bot, CalendarDays } from "lucide-react";
import type { AiOpinion, Encounter, ExtractedValue, Flag, NoteHistory, TrendRow, Urgency } from "@/lib/types";
import { Badge, Card, CardHeader, cx } from "@/components/ui";
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

function statusTone(v: ExtractedValue) {
  return v.status === "abnormal" ? "text-crit" : v.status === "borderline" ? "text-semi" : "text-ink";
}

const attention = (v: ExtractedValue) => (v.status === "abnormal" ? 0 : v.needs_check ? 1 : v.status === "borderline" ? 2 : 3);

/** Each value sits beside the evidence that produced it. Out-of-range and to-check values come first, with a word label;
 * in a long list the within-range values fold away so the reviewer reads what matters first (4-minute budget). */
export function ValueTable({ values, compact }: { values: ExtractedValue[]; compact?: boolean }) {
  const { tr } = usePrefs();
  const [open, setOpen] = useState(false);
  if (!values.length) return <p className="px-4 py-3 text-sm text-muted">{tr("Nothing recorded.")}</p>;
  const sorted = [...values].sort((a, b) => attention(a) - attention(b));
  const ok = sorted.filter((v) => attention(v) === 3);
  const fold = !compact && values.length >= 6 && ok.length >= 3 && ok.length < values.length;
  const shown = fold && !open ? sorted.filter((v) => attention(v) < 3) : sorted;
  return (
    <div className="divide-y divide-line">
      {shown.map((v) => (
        <div key={v.id} className={cx("grid items-center gap-3 px-4 py-2.5", compact ? "grid-cols-[1fr_auto]" : "grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1.2fr)]")}>
          <div className="min-w-0">
            <p className="truncate text-sm text-muted">{tr(v.label)}</p>
            <p className={cx("text-base font-bold tabular-nums", statusTone(v))}>
              {v.value}
              {v.unit && <span className="ml-1 text-xs font-medium text-muted">{v.unit}</span>}
            </p>
          </div>
          <div className={cx("flex flex-col items-start gap-1", compact ? "items-end" : "sm:items-start")}>
            {v.status === "abnormal" && <Badge tone="crit">{tr("Out of range")}</Badge>}
            {v.status === "borderline" && <Badge tone="semi">{tr("Borderline")}</Badge>}
            {v.needs_check && <Badge tone="semi">{tr("Needs checking")}</Badge>}
            {v.reference && !compact && <span className="text-[11px] text-subtle">{tr("ref")} {v.reference}</span>}
            {!compact && v.checks?.map((c) => (
              <span key={c} className="text-[11px] text-semi">{tr(c)}</span>
            ))}
          </div>
          {!compact && (
            <div className="col-span-2 min-w-0 sm:col-span-1">
              <SourceEvidence v={v} />
            </div>
          )}
        </div>
      ))}
      {fold && (
        <button type="button" onClick={() => setOpen((o) => !o)} className="w-full px-4 py-2.5 text-left text-sm font-medium text-teal-700 hover:bg-canvas">
          {open ? tr("Hide the values within range") : tr("Show {n} values within range", { n: ok.length })}
        </button>
      )}
    </div>
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
export function NoteView({ enc, density }: { enc: Encounter; density: "doctor" | "nurse" | "health_worker" }) {
  const { tr } = usePrefs();
  const n = enc.note;
  if (!n) return null;
  const needsCheck = [...n.vitals, ...(n.labs ?? [])].filter((v) => v.needs_check);

  if (density !== "doctor") {
    const sees = density === "health_worker" ? ["health_worker"] : ["health_worker", "nurse"];
    const nurseQs = n.followup_questions.filter((q) => sees.includes(q.for_role));
    return (
      <div className="grid gap-4 2xl:grid-cols-2">
        {density === "health_worker" && (
          <Card className="2xl:col-span-2">
            <CardHeader title={tr("Summary")} subtitle={tr("Short form for the health worker; the full note is with the nurse and doctor")} icon={<Scale className="size-4" />} />
            <p className="px-4 py-3 text-[15px] leading-relaxed text-ink">{n.renderer === "LLM" ? n.summary : tr(n.summary)}</p>
          </Card>
        )}
        <Card>
          <CardHeader title={tr("Do now")} subtitle={tr("Flags from the rules engine and source checks")} icon={<ListChecks className="size-4" />} />
          <div className="p-4">
            <FlagList flags={n.flags} />
          </div>
        </Card>
        <Card>
          <CardHeader title={tr("Vitals")} subtitle={needsCheck.length ? `${needsCheck.length} value(s) need re-measuring` : tr("As captured at intake")} icon={<Activity className="size-4" />} />
          <ValueTable values={n.vitals} compact />
        </Card>
        <Card>
          <CardHeader title={tr("Ask the patient")} icon={<MessageCircleQuestion className="size-4" />} />
          <ol className="space-y-2 p-4 text-sm">
            {nurseQs.map((q, i) => (
              <li key={i} className="flex gap-2">
                <span className="font-semibold text-teal-700">{i + 1}.</span>
                <span>
                  {tr(q.question)} <span className="text-xs text-subtle">({tr(q.tag)})</span>
                </span>
              </li>
            ))}
            {!nurseQs.length && <li className="text-muted">{density === "health_worker" ? tr("No health-worker questions for this case.") : tr("No nurse questions for this case.")}</li>}
          </ol>
        </Card>
        <Card>
          <CardHeader title={tr("Still missing")} icon={<Clock3 className="size-4" />} />
          <ul className="space-y-1.5 p-4 text-sm">
            {n.missing_info.map((m) => (
              <li key={m} className="flex gap-2">
                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-coral-500" />
                {tr(m)}
              </li>
            ))}
            {!n.missing_info.length && <li className="text-muted">{tr("Nothing missing.")}</li>}
          </ul>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title={tr("Summary")}
          subtitle={`${tr("Organised from patient-provided information")} · ${n.generated_by}${n.edited_by ? ` · ${tr("edited by {name}", { name: n.edited_by })}` : ""}`}
          icon={<Scale className="size-4" />}
        />
        <div className="flex flex-wrap items-center gap-2 px-4 pt-3 text-xs">
          {n.renderer === "LLM" && !n.edited_by ? (
            <Badge tone="teal">{tr("Written by {model} · checked against the record", { model: n.llm?.model.split(" (")[0] ?? "AI" })}</Badge>
          ) : (
            <Badge>{tr("Template summary")}</Badge>
          )}
          {n.llm?.status === "FAIL_FELL_BACK" && <Badge tone="semi">{tr("AI summary rejected by the checks")}</Badge>}
          {n.llm?.status === "UNAVAILABLE" && <Badge>{tr("AI summary unavailable")}</Badge>}
        </div>
        <p className="px-4 py-3 text-[15px] leading-relaxed text-ink">{n.renderer === "LLM" ? n.summary : tr(n.summary)}</p>
        {n.history && <HistoryList h={n.history} />}
        {n.renderer === "LLM" && n.summary_template && (
          <details className="border-t border-line px-4 py-2.5 text-sm">
            <summary className="cursor-pointer font-medium text-muted">{tr("Template summary (facts as recorded)")}</summary>
            <p className="mt-2 text-ink-2">{tr(n.summary_template)}</p>
          </details>
        )}
        {n.llm?.status === "FAIL_FELL_BACK" && n.llm.rejected_text && (
          <details className="border-t border-line px-4 py-2.5 text-sm">
            <summary className="cursor-pointer font-medium text-muted">{tr("Rejected AI text and why")}</summary>
            <p className="mt-2 rounded-lg bg-canvas p-2.5 text-ink-2 line-through decoration-crit/60">{n.llm.rejected_text}</p>
            <ul className="mt-1.5 list-disc pl-5 text-xs text-crit">
              {[...(n.llm.guard ?? []), ...(n.llm.faithfulness ?? [])].map((r) => <li key={r}>{r}</li>)}
            </ul>
          </details>
        )}
        {(n.original_words?.length ? n.original_words : n.transcript ? [n.transcript] : []).length > 0 && (
          <details open className="border-t border-line px-4 py-2.5 text-sm">
            <summary className="flex cursor-pointer items-center gap-1.5 font-medium text-muted">
              <Languages className="size-4" /> {tr("Original words (")}{tr(langByCode((n.original_words?.[0] ?? n.transcript)!.language).name)})
            </summary>
            {(n.original_words?.length ? n.original_words : [n.transcript!]).map((w, i) => (
              <div key={i} className="mt-2 grid gap-2 sm:grid-cols-2">
                <p lang={w.language} className="rounded-lg bg-canvas p-2.5 text-ink">{w.original}</p>
                <div>
                  <p className="rounded-lg border border-line p-2.5 text-ink-2">{w.translated}</p>
                  <p className="mt-1 text-xs text-muted">
                    {tr("Machine translated")}
                    {"translation_engine" in w && w.translation_engine ? ` (${w.translation_engine})` : ""}
                    {tr(" — check against the patient's own words")}
                  </p>
                </div>
              </div>
            ))}
          </details>
        )}
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader title={tr("Flags")} subtitle={tr("Shown instead of model confidence scores")} icon={<AlertTriangle className="size-4" />} />
          <div className="p-4">
            <FlagList flags={n.flags} />
          </div>
        </Card>
        <Card>
          <CardHeader
            title={tr("Rules engine trace")}
            subtitle={`${tr("Urgency comes only from these deterministic rules")}${n.triage ? ` · ${n.triage.protocols.map((p) => p.key).join(" + ")} · rulepack ${n.triage.rulepack_version}` : ""}`}
            icon={<ListChecks className="size-4" />}
          />
          <Undetermined note={n} />
          <ul className="divide-y divide-line">
            {n.rules_fired.map((r) => (
              <li key={r.rule_id} className="flex items-start gap-3 px-4 py-2.5">
                <span className={cx("mt-0.5 h-6 w-1 shrink-0 rounded-full", urgencyBar(r.urgency))} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-ink" title={english(tr, r.description)}>
                    {tr(r.description)}
                    {r.non_downgradable && r.urgency === "red" && (
                      <span title={tr("Non-downgradable: only a doctor can lower it, with a written reason that is audited")} className="ml-1.5 inline-flex items-center gap-0.5 rounded bg-crit-bg px-1.5 text-[10px] font-semibold uppercase text-crit">
                        <Lock className="size-3" /> {tr("locked")}
                      </span>
                    )}
                  </p>
                  {(r.evidence?.length ?? 0) > 0 && (
                    <ul className="mt-0.5 space-y-0.5">
                      {r.evidence!.map((ev, i) => (
                        <li key={i} className="text-xs text-ink-2">→ {ev}</li>
                      ))}
                    </ul>
                  )}
                  <p className="font-mono text-[11px] text-subtle">
                    {r.rule_id} · {r.source ?? r.protocol}
                  </p>
                </div>
                <UrgencyBadge u={r.urgency} size="sm" />
              </li>
            ))}
          </ul>
          {(n.triage?.unresolved.filter((u) => u.urgency === "red").length ?? 0) > 0 && (
            <details className="border-t border-line px-4 py-2.5 text-sm">
              <summary className="cursor-pointer font-medium text-muted">
                {tr("RED rules not yet ruled out")} ({n.triage!.unresolved.filter((u) => u.urgency === "red").length})
              </summary>
              <ul className="mt-1.5 space-y-1">
                {n.triage!.unresolved
                  .filter((u) => u.urgency === "red")
                  .map((u) => (
                    <li key={u.rule_id} className="text-xs text-ink-2">
                      <span className="font-mono text-subtle">{u.rule_id}</span> <span title={english(tr, u.description)}>{tr(u.description)}</span> — {tr("needs")}: {u.needs.map((x) => tr(x)).join(", ")}
                    </li>
                  ))}
              </ul>
            </details>
          )}
          {n.llm_opinion && <SecondOpinion op={n.llm_opinion} />}
          {enc.override && (
            <div className="border-t border-line bg-coral-50 px-4 py-2.5 text-sm">
              <p className="font-semibold text-coral-700">
                {tr("Clinician override:")} {tr(URGENCY_LABEL[enc.override.from_urgency])} → {tr(URGENCY_LABEL[enc.override.to_urgency])}
              </p>
              <p className="text-ink-2">“{tr(enc.override.reason)}”</p>
              <p className="text-xs text-muted">
                {enc.override.by} · {fmtDateTime(enc.override.at)} · {tr(enc.override.category)}
              </p>
            </div>
          )}
        </Card>
      </div>

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

      <Card>
        <CardHeader title={tr("Vitals")} subtitle={valueSummary(n.vitals, tr) ?? tr("Each value with the source that produced it")} icon={<Activity className="size-4" />} />
        <ValueTable values={n.vitals} />
      </Card>

      {n.labs.length > 0 && (
        <Card>
          <CardHeader title={tr("Report values")} subtitle={valueSummary(n.labs, tr) ?? tr("Read from uploaded reports — cropped region shown beside each value")} icon={<FlaskConical className="size-4" />} />
          <ValueTable values={n.labs} />
        </Card>
      )}

      {n.trend.length > 0 && (
        <Card>
          <CardHeader title={enc.category === "maternal" ? tr("Across antenatal visits") : tr("Compared with previous visits")} subtitle={tr("Longitudinal values from this patient's earlier encounters")} icon={<TrendingUp className="size-4" />} />
          <div className="space-y-3 p-4">
            {n.trend.map((r) => (
              <Sparkline key={r.parameter} row={r} />
            ))}
          </div>
        </Card>
      )}

      <div className="grid gap-4 xl:grid-cols-3">
        <Card>
          <CardHeader title={tr("Timeline")} icon={<Clock3 className="size-4" />} />
          <ol className="relative space-y-3 p-4 pl-6 text-sm before:absolute before:top-5 before:bottom-5 before:left-[18px] before:w-px before:bg-line">
            {n.timeline.map((t, i) => (
              <li key={i} className="relative">
                <span className="absolute top-1.5 -left-[11px] size-2 rounded-full bg-teal-600 ring-2 ring-white" />
                <p className="flex flex-wrap items-center gap-1.5 text-xs text-subtle">
                  {tr(t.when)}
                  {t.certainty && t.certainty !== "RECORDED" && (
                    <Badge tone={t.certainty === "STATED" ? "teal" : t.certainty === "INFERRED" ? "info" : "semi"}>{tr(t.certainty)}</Badge>
                  )}
                </p>
                <p className="text-ink">{tr(t.event)}</p>
                {t.raw && <p className="text-xs text-muted">“{t.raw}”</p>}
                {t.basis && (
                  <p className="mt-0.5 flex items-center gap-1 text-xs text-subtle" title={tr("Approximate: from the regional calendar. Confirm the date with the patient.")}>
                    <CalendarDays className="size-3 shrink-0" /> {t.basis}
                  </p>
                )}
              </li>
            ))}
          </ol>
        </Card>
        <Card>
          <CardHeader title={tr("Missing information")} icon={<ListChecks className="size-4" />} />
          <ul className="space-y-1.5 p-4 text-sm">
            {n.missing_info.map((m) => (
              <li key={m} className="flex gap-2">
                <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-coral-500" /> {tr(m)}
              </li>
            ))}
            {!n.missing_info.length && <li className="text-muted">{tr("Nothing flagged as missing.")}</li>}
          </ul>
        </Card>
        <Card>
          <CardHeader title={tr("Follow-up questions")} icon={<MessageCircleQuestion className="size-4" />} />
          <ul className="space-y-2.5 p-4 text-sm">
            {n.followup_questions.map((q, i) => (
              <li key={i}>
                <span className="text-xs font-semibold text-teal-700">
                  {tr(q.tag)} {tr("· for")} {tr(q.for_role.replace("_", " "))}
                </span>
                <p className="text-ink">{tr(q.question)}</p>
              </li>
            ))}
          </ul>
        </Card>
      </div>
    </div>
  );
}
