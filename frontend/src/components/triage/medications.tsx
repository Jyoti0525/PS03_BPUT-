"use client";

import { useState } from "react";
import { Check, Pill, X, EyeOff, FileSearch, ExternalLink } from "lucide-react";
import { usePrefs } from "@/components/providers";
import { api } from "@/lib/api";
import { Badge, Button, Card, CardHeader } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { useFile } from "@/components/triage/source";
import type { Encounter } from "@/lib/types";

function PrescriptionSource({ id, filename }: { id?: string; filename?: string }) {
  const { tr } = usePrefs();
  const file = useFile(id);
  if (!id) return null;
  if (!file?.url) return <span className="text-xs text-muted">{filename ?? tr("Source image unavailable")}</span>;
  return file.content_type.startsWith("image/") ? (
    <a href={file.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 rounded-lg border border-line bg-white p-1.5 text-xs text-ink-2 hover:border-teal">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img src={file.url} alt={tr("Uploaded prescription source")} className="h-14 w-14 rounded object-cover object-top" />
      <span>{tr("Open original prescription")} <ExternalLink className="inline size-3" /></span>
    </a>
  ) : <a className="inline-flex items-center gap-1 text-xs text-teal-ink underline" href={file.url} target="_blank" rel="noreferrer">{tr("Open original document")} <ExternalLink className="size-3" /></a>;
}

/** Medicines read from a strip or prescription photo (B10). Nothing enters the record until a nurse or doctor
 * confirms each name; rejected names are dropped for good. */
export function MedicationsPanel({ enc, canReview, onDone }: { enc: Encounter; canReview: boolean; onDone: (e: Encounter) => void }) {
  const { tr } = usePrefs();
  const [busy, setBusy] = useState<string | null>(null);
  const n = enc.note;
  const pending = n?.medications_pending ?? [];
  const confirmed = n?.medications ?? [];
  if (!pending.length && !confirmed.length) return null;

  const review = async (name: string, ok: boolean) => {
    setBusy(name);
    try {
      onDone(await api.reviewMedications(enc.id, ok ? [name] : [], ok ? [] : [name]));
      toast(ok ? tr("Added to the record") : tr("Removed"));
    } catch (e) {
      toast(e instanceof Error ? e.message : tr("Could not save"), "error");
    } finally {
      setBusy(null);
    }
  };

  return (
    <Card className="mt-4">
      <CardHeader title={tr("Current medicines")} subtitle={tr("OCR candidates from a strip or prescription. Verify every name and direction against the original before confirming.")} icon={<Pill className="size-4" />} />
      {!canReview && pending.length > 0 && <p className="border-b border-line bg-semi-bg px-4 py-2 text-xs font-medium text-ink-2">{tr("Doctor review required before these OCR candidates enter the confirmed medication history.")}</p>}
      <ul className="divide-y divide-line">
        {pending.map((m) => (
          <li key={m.name} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm">
            <span className="min-w-0 flex-1">
              <span className="font-semibold capitalize text-ink">{m.name}</span>
              {m.strength && <span className="ml-1.5 text-ink-2">{m.strength}</span>}
              {m.contains && <span className="block text-xs text-ink-2">{tr("Contains")}: {m.contains}</span>}
              {m.prescription_details && Object.values(m.prescription_details).some(Boolean) && (
                <span className="mt-1 block text-xs text-ink-2">
                  {tr("Possible directions (read from this line; verify against the original)")}: {[m.prescription_details.dose, m.prescription_details.frequency,
                    m.prescription_details.duration, m.prescription_details.route, m.prescription_details.timing].filter(Boolean).join(" · ")}
                </span>
              )}
              <span className="block text-xs text-muted">
                {tr("Seen as")} “{m.seen}” · {m.filename} · {tr(m.read_by?.startsWith("Sarvam Vision 1.5") ? "OCR confidence" : "match")} {Math.round(m.confidence * 100)}%
                {m.kind === "unverified" && ` · ${tr("Not matched to the medicine list; verify the name from the original")}`}
                {m.read_by === "both" ? ` · ${tr("Read by both offline and online engines")}` : m.read_by?.startsWith("Sarvam") ? ` · ${tr("Read online from handwriting by Sarvam Vision")}` : ""}
              </span>
              <span className="mt-2 block"><PrescriptionSource id={m.file_id} filename={m.filename} /></span>
            </span>
            <Badge tone="semi">{tr("Awaiting confirmation")}</Badge>
            {canReview && (
              <span className="flex gap-1.5">
                <Button size="sm" variant="teal" disabled={!!busy} onClick={() => review(m.name, true)} icon={<Check className="size-4" />}>{tr("Confirm")}</Button>
                <Button size="sm" variant="secondary" disabled={!!busy} onClick={() => review(m.name, false)} icon={<X className="size-4" />}>{tr("Not this")}</Button>
              </span>
            )}
          </li>
        ))}
        {confirmed.map((m) => (
          <li key={m.name} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm">
            <span className="min-w-0 flex-1">
              <span className="font-semibold capitalize text-ink">{m.name}</span>
              {m.strength && <span className="ml-1.5 text-ink-2">{m.strength}</span>}
              {m.prescription_details && Object.values(m.prescription_details).some(Boolean) && (
                <span className="mt-1 block text-xs text-ink-2">{tr("Doctor-verified directions")} · {[m.prescription_details.dose, m.prescription_details.frequency,
                  m.prescription_details.duration, m.prescription_details.route, m.prescription_details.timing].filter(Boolean).join(" · ")}</span>
              )}
              <span className="block text-xs text-muted">{tr(m.source)} · {tr("confirmed by")} {m.confirmed_by ?? m.by} ({tr(m.confirmed_by_role ?? "doctor")})</span>
              <span className="mt-2 block"><PrescriptionSource id={m.file_id ?? undefined} filename={m.source} /></span>
            </span>
            <Badge tone="rout">{tr("Confirmed")}</Badge>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/** What each upload is and what was hidden before it was stored. Photos of the problem are never interpreted. */
export function DocumentLabels({ enc }: { enc: Encounter }) {
  const { tr } = usePrefs();
  const docs = enc.note?.documents ?? [];
  if (!docs.length) return null;
  return (
    <ul className="divide-y divide-line border-t border-line">
      {docs.map((d) => (
        <li key={d.file_id} className="flex flex-wrap items-center gap-2 px-4 py-2 text-sm">
          <FileSearch className="size-4 text-muted" />
          <span className="min-w-0 flex-1 truncate text-ink">{d.filename}</span>
          {d.doc_type && <Badge tone={d.doc_type.type === "non_document" ? "neutral" : "info"}>{tr(d.doc_type.label)}</Badge>}
          {d.doc_type && d.doc_type.type !== "non_document" && <span className="text-xs text-muted">{tr("because")}: {d.doc_type.why}</span>}
          {!!d.readings?.length && (
            <details className="basis-full rounded-lg border border-line bg-canvas px-3 py-2 text-xs">
              <summary className="cursor-pointer font-semibold text-ink-2">{tr("OCR reading — compare with the original")}</summary>
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                {d.readings.map((r) => (
                  <section key={r.engine} className="rounded-md bg-white p-2">
                    <p className="font-semibold">{r.engine} · {tr("confidence")} {Math.round(r.confidence * 100)}%</p>
                    <p className="mt-1 whitespace-pre-wrap text-ink-2">{r.lines.join("\n")}</p>
                  </section>
                ))}
              </div>
              <p className="mt-2 text-muted">{tr("Handwriting may be misread. Verify every medicine, dose and instruction with the original prescription or patient.")}</p>
            </details>
          )}
          {d.redaction && (d.redaction.faces > 0 || d.redaction.id_numbers > 0) && (
            <Badge tone="teal">
              <EyeOff className="size-3" /> {tr("{f} face(s), {i} ID number(s) hidden before storage", { f: d.redaction.faces, i: d.redaction.id_numbers })}
            </Badge>
          )}
        </li>
      ))}
    </ul>
  );
}
