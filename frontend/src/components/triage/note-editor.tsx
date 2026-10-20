"use client";

import { useState } from "react";
import { usePrefs } from "@/components/providers";
import { api } from "@/lib/api";
import type { Encounter } from "@/lib/types";
import { Button, Label, Modal, Textarea } from "@/components/ui";
import { toast } from "@/components/ui/toast";

export function NoteEditor({ open, enc, onClose, onDone }: {
  open: boolean;
  enc: Encounter;
  onClose: () => void;
  onDone: (enc: Encounter) => void;
}) {
  const { tr } = usePrefs();
  const [summary, setSummary] = useState(enc.note?.summary ?? "");
  const [missing, setMissing] = useState((enc.note?.missing_info ?? []).join("\n"));
  const [clinicalInput, setClinicalInput] = useState("");
  const [busy, setBusy] = useState(false);

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title={tr("Review and edit the note")}
      subtitle={tr("Patient-reported words remain unchanged. Your bedside clarification is attributed to you and shown separately; when AI summary is enabled, it is included in the guarded summary.")}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>{tr("Cancel")}</Button>
          <Button loading={busy} onClick={async () => {
            setBusy(true);
            try {
              const result = await api.editNote(enc.id, {
                summary,
                missing_info: missing.split("\n").map((line) => line.trim()).filter(Boolean),
                clinician_input: clinicalInput.trim() || undefined,
              });
              onDone(result);
              toast(tr("Note updated"));
            } catch (e) {
              toast(e instanceof Error ? e.message : tr("Failed to update note"), "error");
            } finally {
              setBusy(false);
            }
          }}>{tr("Save changes")}</Button>
        </>
      }
    >
      {!!enc.note?.original_words?.length && (
        <div className="mb-4 rounded-xl border border-line bg-canvas/50 p-3">
          <p className="mb-2 text-xs font-bold uppercase tracking-wide text-muted">{tr("Patient-provided words — source record")}</p>
          <ul className="space-y-3">
            {enc.note.original_words.map((words, i) => (
              <li key={`${words.language}-${i}`} className="grid gap-2 text-sm sm:grid-cols-2">
                <p lang={words.language} className="rounded-lg bg-white p-2.5"><span className="mb-1 block text-[10px] font-semibold uppercase text-muted">{tr("Original")}</span>{words.original}</p>
                <p className="rounded-lg border border-line bg-white p-2.5 text-ink-2"><span className="mb-1 block text-[10px] font-semibold uppercase text-muted">{tr("Translation · verify with patient")}</span>{words.translated}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
      {!!enc.note?.clinician_inputs?.length && (
        <div className="mb-4 rounded-xl border border-teal-100 bg-teal-50/50 p-3">
          <p className="mb-2 text-xs font-bold uppercase tracking-wide text-teal-800">{tr("Earlier clinician clarifications")}</p>
          <ul className="space-y-2 text-sm">
            {enc.note.clinician_inputs.map((item, i) => (
              <li key={`${item.at}-${i}`}><span className="font-semibold">{item.by} · {tr(item.role.replaceAll("_", " "))}</span><span className="block text-ink-2">{item.text}</span></li>
            ))}
          </ul>
        </div>
      )}
      <Label htmlFor="note-summary">{tr("Clinical summary")}</Label>
      <Textarea id="note-summary" rows={5} value={summary} onChange={(e) => setSummary(e.target.value)} />
      <div className="mt-4">
        <Label htmlFor="note-clinician-input" hint={tr("optional")}>{tr("Add your bedside clarification or finding")}</Label>
        <Textarea
          id="note-clinician-input"
          rows={3}
          value={clinicalInput}
          onChange={(e) => setClinicalInput(e.target.value)}
          placeholder={tr("For example: Asked about chest pain; patient denies it. Keep what the patient originally reported visible above.")}
        />
        <p className="mt-1 text-xs text-muted">{tr("This does not erase the patient's words or silently change the rules-based urgency. Your clarification is shown with your name and role.")}</p>
      </div>
      <div className="mt-4">
        <Label htmlFor="note-missing" hint={tr("one item per line")}>{tr("Still missing or to check")}</Label>
        <Textarea id="note-missing" rows={3} value={missing} onChange={(e) => setMissing(e.target.value)} />
      </div>
    </Modal>
  );
}
