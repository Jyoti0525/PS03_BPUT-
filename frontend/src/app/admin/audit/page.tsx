"use client";

import { useState } from "react";
import { Download, ShieldCheck, ShieldX, Search, Link2 } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Button, Card, ErrorNote, Input, Select, Spinner } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import { downloadBlob } from "@/lib/export";
import type { AuditAction } from "@/lib/types";

const ACTIONS: AuditAction[] = ["VIEW", "CREATE", "UPDATE", "CONFIRM", "OVERRIDE", "ESCALATE", "ACKNOWLEDGE", "REFERRAL", "EXPORT", "LOGIN", "CONSENT", "UPLOAD", "DEVICE", "CONFIG", "DISAGREEMENT", "PURGE"];
const TONE: Partial<Record<AuditAction, "crit" | "semi" | "teal" | "coral" | "info" | "neutral">> = {
  OVERRIDE: "coral",
  ESCALATE: "crit",
  DISAGREEMENT: "semi",
  PURGE: "neutral",
  VIEW: "info",
  EXPORT: "teal",
  REFERRAL: "teal",
};

export default function AuditPage() {
  const [action, setAction] = useState<AuditAction | "">("");
  const [q, setQ] = useState("");
  const [verify, setVerify] = useState<{ ok: boolean; checked: number; broken_at: number | null } | null>(null);
  const { data, error, loading, reload } = useAsync(() => api.listAudit({ action, q }), [action, q]);

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        title="Audit log"
        subtitle="Append-only and hash-chained. Records who viewed, changed, overrode or exported what — including every VIEW."
        actions={
          <>
            <Button
              variant="secondary"
              icon={<ShieldCheck className="size-4" />}
              onClick={async () => {
                const r = await api.verifyAudit();
                setVerify(r);
                toast(r.ok ? `Chain intact — ${r.checked} entries verified` : `Chain broken at entry ${r.broken_at}`, r.ok ? "success" : "error");
              }}
            >
              Verify chain
            </Button>
            <Button
              variant="secondary"
              icon={<Download className="size-4" />}
              onClick={async () => {
                const r = await api.exportAuditCsv();
                downloadBlob(r.filename, r.blob);
                reload();
              }}
            >
              Export CSV
            </Button>
          </>
        }
      />
      {verify && (
        <div className={`mb-4 flex items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium ${verify.ok ? "border-rout-line bg-rout-bg text-rout" : "border-crit-line bg-crit-bg text-crit"}`}>
          {verify.ok ? <ShieldCheck className="size-4" /> : <ShieldX className="size-4" />}
          {verify.ok ? `All ${verify.checked} entries verified: each hash matches its content and the previous entry.` : `Tampering detected at entry #${verify.broken_at}.`}
        </div>
      )}
      <Card>
        <div className="flex flex-wrap gap-2 border-b border-line p-3">
          <div className="relative min-w-56 flex-1">
            <Search className="absolute top-3 left-3 size-4 text-subtle" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search actor, patient ID or detail" className="h-10 pl-9" />
          </div>
          <Select value={action} onChange={(e) => setAction(e.target.value as AuditAction | "")} className="h-10 w-48" aria-label="Filter by action">
            <option value="">All actions</option>
            {ACTIONS.map((a) => <option key={a}>{a}</option>)}
          </Select>
        </div>
        {error ? <div className="p-4"><ErrorNote error={error} /></div> : loading && !data ? <Spinner /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs tracking-wide text-muted uppercase">
                  <th className="px-4 py-2 font-semibold">#</th>
                  <th className="px-4 py-2 font-semibold">Time</th>
                  <th className="px-4 py-2 font-semibold">Actor</th>
                  <th className="px-4 py-2 font-semibold">Action</th>
                  <th className="px-4 py-2 font-semibold">Patient</th>
                  <th className="px-4 py-2 font-semibold">Detail</th>
                  <th className="px-4 py-2 font-semibold">Hash</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {data?.map((a) => (
                  <tr key={a.id} className="align-top hover:bg-canvas/60">
                    <td className="px-4 py-2.5 text-subtle tabular-nums">{a.id}</td>
                    <td className="px-4 py-2.5 whitespace-nowrap text-muted tabular-nums">{new Date(a.ts).toLocaleString("en-IN", { dateStyle: "short", timeStyle: "medium" })}</td>
                    <td className="px-4 py-2.5">
                      <p className="font-medium text-ink">{a.actor_name}</p>
                      <p className="text-xs text-subtle">{a.actor_role}</p>
                    </td>
                    <td className="px-4 py-2.5"><Badge tone={TONE[a.action] ?? "neutral"}>{a.action}</Badge></td>
                    <td className="px-4 py-2.5 font-mono text-xs text-muted">{a.patient_code ?? "—"}</td>
                    <td className="max-w-md px-4 py-2.5 text-ink-2">{a.detail}</td>
                    <td className="px-4 py-2.5 font-mono text-[11px] text-subtle" title={`prev ${a.prev_hash}\nthis ${a.hash}`}>
                      <Link2 className="mr-1 inline size-3" />
                      {a.hash.slice(0, 10)}…
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {data?.length === 0 && <p className="p-6 text-center text-sm text-muted">No matching entries.</p>}
          </div>
        )}
      </Card>
    </div>
  );
}
