"use client";

import { usePrefs } from "@/components/providers";
import { fmtDateTime } from "@/lib/hooks";
import { AlertOctagon, AlertTriangle, Info, TrendingUp, TrendingDown, Minus, ListChecks, MessageCircleQuestion, Clock3, Scale, FlaskConical, Activity, Languages, Split, Lock } from "lucide-react";
import type { Encounter, ExtractedValue, Flag, TrendRow, Urgency } from "@/lib/types";
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

/** Flags, not confidence percentages. */
export function FlagList({ flags, limit }: { flags: Flag[]; limit?: number }) {
  const { tr } = usePrefs();
  const order = { critical: 0, warning: 1, info: 2 };
  const list = [...flags].sort((a, b) => order[a.severity] - order[b.severity]).slice(0, limit);
  if (!list.length) return <p className="text-sm text-muted">{tr("No flags raised.")}</p>;
  return (
    <ul className="space-y-1.5">
      {list.map((f, i) => (
        <li key={i} className={cx("flex items-start gap-2 rounded-lg border px-2.5 py-2 text-sm", f.severity === "critical" ? "border-crit-line bg-crit-bg" : f.severity === "warning" ? "border-semi-line bg-semi-bg" : "border-blue-100 bg-blue-50/60")}>
          <FlagIcon s={f.severity} />
          <span className="min-w-0 flex-1">
            <span className="font-medium text-ink">{tr(f.label)}</span>
            <span className="block text-xs text-muted">{tr(f.reason)}</span>
          </span>
          <code className="hidden shrink-0 text-[10px] text-subtle sm:block">{f.code}</code>
        </li>
      ))}
    </ul>
  );
}

function statusTone(v: ExtractedValue) {
  return v.status === "abnormal" ? "text-crit" : v.status === "borderline" ? "text-semi" : "text-ink";
}

/** Each value sits beside the evidence that produced it. */
export function ValueTable({ values, compact }: { values: ExtractedValue[]; compact?: boolean }) {
  const { tr } = usePrefs();
  if (!values.length) return <p className="px-4 py-3 text-sm text-muted">{tr("Nothing recorded.")}</p>;
  return (
    <div className="divide-y divide-line">
      {values.map((v) => (
        <div key={v.id} className={cx("grid items-center gap-3 px-4 py-2.5", compact ? "grid-cols-[1fr_auto]" : "grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)] sm:grid-cols-[minmax(0,1fr)_auto_minmax(0,1.2fr)]")}>
          <div className="min-w-0">
            <p className="truncate text-sm text-muted">{tr(v.label)}</p>
            <p className={cx("text-base font-bold tabular-nums", statusTone(v))}>
              {v.value}
              {v.unit && <span className="ml-1 text-xs font-medium text-muted">{v.unit}</span>}
            </p>
          </div>
          <div className={cx("flex flex-col items-start gap-1", compact ? "items-end" : "sm:items-start")}>
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
    </div>
  );
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

/**
 * Role-differentiated rendering (E2): the same note at two densities.
 * Doctor = full case with evidence and rules trace. Nurse = actionable checklist.
 */
export function NoteView({ enc, density }: { enc: Encounter; density: "doctor" | "nurse" }) {
  const { tr } = usePrefs();
  const n = enc.note;
  if (!n) return null;
  const needsCheck = [...n.vitals, ...n.labs].filter((v) => v.needs_check);

  if (density === "nurse") {
    const nurseQs = n.followup_questions.filter((q) => q.for_role !== "doctor");
    return (
      <div className="grid gap-4 lg:grid-cols-2">
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
            {!nurseQs.length && <li className="text-muted">{tr("No nurse questions for this case.")}</li>}
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
        {n.transcript && (
          <details className="border-t border-line px-4 py-2.5 text-sm">
            <summary className="flex cursor-pointer items-center gap-1.5 font-medium text-muted">
              <Languages className="size-4" /> {tr("Original words (")}{tr(langByCode(n.transcript.language).name)})
            </summary>
            <p className="mt-2 rounded-lg bg-canvas p-2.5 text-ink">{n.transcript.original}</p>
            <p className="mt-1.5 text-xs text-muted">{tr("Translated:")} {n.transcript.translated}</p>
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
          {n.triage?.provisional && (
            <div className="border-b border-semi-line bg-semi-bg px-4 py-2.5 text-sm">
              <p className="font-semibold text-semi">{tr("Provisional — unknown is never treated as normal")}</p>
              <p className="text-ink-2">{tr("Measure or check before this case can be routine:")}</p>
              <ul className="mt-1 flex flex-wrap gap-1.5">
                {[...new Set([...n.triage.missing_for_green, ...n.triage.unresolved.flatMap((u) => u.needs.map((x) => (x.startsWith("danger-sign") ? "clinician danger-sign check" : x)))])].map((x) => (
                  <li key={x} className="rounded-md border border-semi-line bg-surface px-2 py-0.5 text-xs text-ink">{tr(x)}</li>
                ))}
              </ul>
            </div>
          )}
          <ul className="divide-y divide-line">
            {n.rules_fired.map((r) => (
              <li key={r.rule_id} className="flex items-start gap-3 px-4 py-2.5">
                <span className={cx("mt-0.5 h-6 w-1 shrink-0 rounded-full", urgencyBar(r.urgency))} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-ink">
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
                      <span className="font-mono text-subtle">{u.rule_id}</span> {tr(u.description)} — {tr("needs")}: {u.needs.join(", ")}
                    </li>
                  ))}
              </ul>
            </details>
          )}
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
        <CardHeader title={tr("Vitals")} subtitle={tr("Each value with the source that produced it")} icon={<Activity className="size-4" />} />
        <ValueTable values={n.vitals} />
      </Card>

      {n.labs.length > 0 && (
        <Card>
          <CardHeader title={tr("Report values")} subtitle={tr("Read from uploaded reports — cropped region shown beside each value")} icon={<FlaskConical className="size-4" />} />
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
