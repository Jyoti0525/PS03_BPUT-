"use client";

import { useState } from "react";
import { Check, Pill, X, EyeOff, FileSearch } from "lucide-react";
import { usePrefs } from "@/components/providers";
import { api } from "@/lib/api";
import { Badge, Button, Card, CardHeader } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import type { Encounter } from "@/lib/types";

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
      <CardHeader title={tr("Current medicines")} subtitle={tr("Read from a photo and matched to the Jan Aushadhi generic list or a list of Indian brands — confirm each one against the strip or prescription")} icon={<Pill className="size-4" />} />
      <ul className="divide-y divide-line">
        {pending.map((m) => (
          <li key={m.name} className="flex flex-wrap items-center gap-3 px-4 py-2.5 text-sm">
            <span className="min-w-0 flex-1">
              <span className="font-semibold capitalize text-ink">{m.name}</span>
              {m.strength && <span className="ml-1.5 text-ink-2">{m.strength}</span>}
              {m.contains && <span className="block text-xs text-ink-2">{tr("Contains")}: {m.contains}</span>}
              <span className="block text-xs text-muted">
                {tr("Seen as")} “{m.seen}” · {m.filename} · {tr("match")} {Math.round(m.confidence * 100)}%
                {m.read_by === "both" ? ` · ${tr("Read by both offline and online engines")}` : m.read_by?.startsWith("Sarvam") ? ` · ${tr("Read online from handwriting by Sarvam Vision")}` : ""}
              </span>
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
              <span className="block text-xs text-muted">{tr(m.source)} · {tr("confirmed by")} {m.by}</span>
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
