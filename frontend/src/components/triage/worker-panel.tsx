"use client";

import { useState } from "react";
import { Briefcase, ClipboardCheck, EyeOff } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Badge, Button, Card, CardHeader, FieldError, Input, Label, Textarea, cx } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { FITNESS } from "@/components/employer/status";
import type { FitnessStatus, WorkerInfo } from "@/lib/types";

const CHOICES: FitnessStatus[] = ["fit", "fit_with_restrictions", "temporarily_unfit", "pending_review"];

/** Shown on a case when the patient is on an employer's roster. Only the fitness outcome is shared with the employer. */
export function WorkerPanel({ encounterId, worker, canRecord, onRecorded }: { encounterId: string; worker: WorkerInfo; canRecord: boolean; onRecorded: () => void }) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState<FitnessStatus>(worker.latest?.status ?? "fit");
  const [restrictions, setRestrictions] = useState("");
  const [validUntil, setValidUntil] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const l = worker.latest;

  async function save() {
    setErr(null);
    if (status === "fit_with_restrictions" && restrictions.trim().length < 3) return setErr("Describe the restrictions (e.g. no work at height)");
    setBusy(true);
    try {
      await api.recordFitness(encounterId, { status, restrictions: restrictions.trim() || null, valid_until: validUntil || null });
      toast(`Fitness recorded: ${FITNESS[status].label}`);
      setOpen(false);
      onRecorded();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not record fitness");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="mt-4">
      <CardHeader
        title="Occupational health"
        subtitle={`${worker.organisation_name}${worker.employee_code ? ` · ${worker.employee_code}` : ""}${worker.department ? ` · ${worker.department}` : ""}`}
        icon={<Briefcase className="size-4" />}
        action={
          canRecord && !open ? (
            <Button size="sm" icon={<ClipboardCheck className="size-4" />} onClick={() => setOpen(true)}>
              Record fitness
            </Button>
          ) : undefined
        }
      />
      <div className="space-y-3 p-4 text-sm">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-muted">Current status:</span>
          <Badge tone={FITNESS[l?.status ?? "pending_review"].tone}>{FITNESS[l?.status ?? "pending_review"].label}</Badge>
          {l && (
            <span className="text-xs text-muted">
              by {l.assessed_by} · {new Date(l.assessed_at).toLocaleDateString("en-IN")}
              {l.valid_until && ` · valid until ${new Date(l.valid_until).toLocaleDateString("en-IN")}`}
            </span>
          )}
        </div>
        {l?.restrictions && <p className="text-ink-2">Restrictions: {l.restrictions}</p>}
        {open && (
          <div className="space-y-3 rounded-xl border border-line bg-canvas p-3">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {CHOICES.map((c) => (
                <button key={c} onClick={() => setStatus(c)} aria-pressed={status === c} className={cx("rounded-xl border px-2 py-2 text-xs font-semibold", status === c ? "border-teal-600 bg-teal-50 text-teal-800" : "border-line bg-white text-muted")}>
                  {FITNESS[c].label}
                </button>
              ))}
            </div>
            {status !== "pending_review" && (
              <div className="grid gap-3 sm:grid-cols-[1fr_180px]">
                <div>
                  <Label htmlFor="fit-r" hint={status === "fit_with_restrictions" ? undefined : "(optional)"}>Work restrictions</Label>
                  <Textarea id="fit-r" rows={2} value={restrictions} onChange={(e) => setRestrictions(e.target.value)} placeholder="e.g. No work at height for 2 weeks" />
                </div>
                <div>
                  <Label htmlFor="fit-v" hint="(optional)">Valid until</Label>
                  <Input id="fit-v" type="date" value={validUntil} onChange={(e) => setValidUntil(e.target.value)} />
                </div>
              </div>
            )}
            <p className="flex items-start gap-1.5 text-xs text-muted">
              <EyeOff className="mt-0.5 size-3.5 shrink-0" /> The employer sees only this outcome, restrictions and validity — never symptoms, notes or documents.
            </p>
            <FieldError>{err}</FieldError>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>Cancel</Button>
              <Button size="sm" onClick={save} loading={busy}>Save outcome</Button>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
