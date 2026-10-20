"use client";

import { useState } from "react";
import { ArrowUpRight } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Button, FieldError, Label, Modal, Textarea } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { usePrefs } from "@/components/providers";
import { UrgencyBadge } from "@/components/triage/note";
import type { Encounter, Urgency } from "@/lib/types";

const nextUrgency: Partial<Record<Urgency, Urgency>> = { green: "yellow", yellow: "red" };

/** First-review staff may raise priority after bedside reassessment; they cannot downgrade a rules red flag. */
export function PriorityAdjuster({ enc, onSaved }: { enc: Encounter; onSaved: (enc: Encounter) => void }) {
  const { tr } = usePrefs();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const target = enc.urgency ? nextUrgency[enc.urgency] : undefined;

  async function save() {
    setError(null);
    if (!target) return;
    if (reason.trim().length < 5) return setError(tr("Add a short reason (at least 5 characters)"));
    setBusy(true);
    try {
      const updated = await api.overrideUrgency(enc.id, target, "Bedside reassessment", reason.trim());
      onSaved(updated);
      setOpen(false);
      setReason("");
      toast(tr("Triage priority raised; the updated case returns to the queue"));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : tr("Could not update triage priority"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      {target && <Button variant="secondary" icon={<ArrowUpRight className="size-4" />} onClick={() => setOpen(true)}>
        {tr("Raise triage priority")}
      </Button>}
      <Modal open={open} onClose={() => setOpen(false)} title={tr("Raise triage priority")} subtitle={tr("For the first bedside review. The rules result stays on record; raising moves this case up in the clinician queue.")}
        footer={<><Button variant="secondary" onClick={() => setOpen(false)}>{tr("Cancel")}</Button><Button variant="danger" loading={busy} disabled={!target} onClick={save}>{tr("Raise priority")}</Button></>}>
        <p className="text-sm text-muted">{tr("Current priority:")} <UrgencyBadge u={enc.urgency} size="sm" /> <span className="px-1">→</span> {target && <UrgencyBadge u={target} size="sm" />}</p>
        <div className="mt-4">
          <Label htmlFor="priority-reason">{tr("What changed at the bedside? (required)")}</Label>
          <Textarea id="priority-reason" rows={3} value={reason} onChange={(e) => setReason(e.target.value)} placeholder={tr("e.g. Repeat SpO₂ is falling; patient now breathless at rest")}/>
        </div>
        <FieldError>{error}</FieldError>
      </Modal>
    </>
  );
}
