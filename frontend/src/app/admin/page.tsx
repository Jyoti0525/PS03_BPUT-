"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { EyeOff, ArrowRight, RefreshCw } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";
import { useSession } from "@/components/providers";
import { PageHeader } from "@/components/layout/app-shell";
import { Button, Card, CardHeader, ErrorNote, Spinner, Stat } from "@/components/ui";
import { TokenBoard } from "@/components/triage/token-board";
import { API_MODE } from "@/lib/api";

export default function AdminHome() {
  const { user, refresh } = useSession();
  const router = useRouter();
  const fid = user!.facility_id!;
  const { data: stats, error, reload } = useAsync(() => api.facilityStats(fid), [fid], { pollMs: 30_000 });
  const { data: facility } = useAsync(() => api.getFacility(fid), [fid]);
  const { data: audit } = useAsync(() => api.listAudit(), []);

  return (
    <>
      <PageHeader
        title={facility?.name ?? "Facility"}
        subtitle="Operational view. Counts only — facility admins cannot open clinical notes."
        actions={<Button variant="secondary" onClick={() => reload()} icon={<RefreshCw className="size-4" />}>Refresh</Button>}
      />
      {error ? <ErrorNote error={error} /> : !stats ? <Spinner /> : (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label="Intakes today" value={stats.today_total} hint={`${stats.offline_synced_today} synced from offline`} />
          <Stat label="Critical" value={stats.by_urgency.red} tone="crit" />
          <Stat label="Semi-urgent" value={stats.by_urgency.yellow} tone="semi" />
          <Stat label="Routine" value={stats.by_urgency.green} tone="rout" />
          <Stat label="Avg. wait (waiting now)" value={`${stats.avg_wait_minutes}m`} />
          <Stat label="Open escalations" value={stats.open_escalations} tone={stats.open_escalations ? "crit" : undefined} />
          <Stat label="Referrals today" value={stats.referrals_today} tone="teal" />
          <Stat label="Beds occupied" value={facility ? `${facility.beds_occupied}/${facility.beds_total}` : "—"} />
        </div>
      )}

      <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_360px]">
        <div className="space-y-4">
        <TokenBoard facilityId={fid} />
        <Card>
          <CardHeader title="Recent activity" subtitle="From the append-only audit log" action={<Link href="/admin/audit" className="text-sm font-semibold text-teal-700">View all</Link>} />
          <ul className="divide-y divide-line">
            {audit?.slice(0, 8).map((a) => (
              <li key={a.id} className="flex items-start gap-3 px-4 py-2.5 text-sm">
                <span className="w-24 shrink-0 rounded-md bg-canvas px-1.5 py-0.5 text-center font-mono text-[11px] text-muted">{a.action}</span>
                <span className="min-w-0 flex-1">
                  <span className="text-ink">{a.detail}</span>
                  <span className="block text-xs text-subtle">{a.actor_name} · {new Date(a.ts).toLocaleString("en-IN")}</span>
                </span>
              </li>
            ))}
          </ul>
        </Card>
        </div>
        <div className="space-y-4">
          <Card className="p-4">
            <p className="font-semibold text-ink">Patient check-in links</p>
            <p className="mt-1 text-sm text-muted">Give each waiting area its own kiosk link or QR poster. Check-ins show up in the tokens list instantly.</p>
            <Link href="/admin/kiosk-links"><Button className="mt-3 w-full" variant="secondary">Manage kiosk links <ArrowRight className="size-4" /></Button></Link>
          </Card>
          <Card className="p-4">
            <div className="flex items-start gap-3">
              <EyeOff className="mt-0.5 size-5 text-coral-600" />
              <div>
                <p className="font-semibold text-ink">Privacy by role</p>
                <p className="mt-1 text-sm text-muted">Your role sees throughput, configuration and the audit trail — never symptoms, notes or reports. Every access by clinical staff is logged here.</p>
              </div>
            </div>
          </Card>
          <Card className="p-4">
            <p className="font-semibold text-ink">Set up this facility</p>
            <p className="mt-1 text-sm text-muted">Facility type and on-site specialists decide referral routing for every triage note.</p>
            <Link href="/admin/facility"><Button className="mt-3 w-full" variant="teal">Facility setup <ArrowRight className="size-4" /></Button></Link>
          </Card>
          {API_MODE === "mock" && (
            <Card className="p-4">
              <p className="font-semibold text-ink">Demo data</p>
              <p className="mt-1 text-sm text-muted">Reset the synthetic database stored in this browser.</p>
              <Button className="mt-3 w-full" variant="secondary" onClick={async () => { const { resetMockData } = await import("@/lib/api/mock/server"); await resetMockData(); await refresh(); router.replace("/auth"); }}>Reset demo data</Button>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
