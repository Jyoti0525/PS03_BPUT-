"use client";

import { TabletSmartphone, ShieldOff, ShieldCheck } from "lucide-react";
import { api, getDeviceId } from "@/lib/api";
import { useAsync, timeAgo } from "@/lib/hooks";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Button, Card, Empty, ErrorNote, Spinner } from "@/components/ui";
import { toast } from "@/components/ui/toast";

export default function DevicesPage() {
  const { data, error, loading, reload } = useAsync(() => api.listDevices(), []);
  const me = typeof window === "undefined" ? "" : getDeviceId();
  const thisBound = data?.some((d) => d.id === me && !d.revoked);
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader
        title="Kiosk devices"
        subtitle="Only bound devices can run patient intake. Revoking a lost tablet stops it immediately."
        actions={
          !thisBound && (
            <Button variant="teal" icon={<ShieldCheck className="size-4" />} onClick={async () => { await api.bindDevice("Admin desk", me); toast("This device is now bound"); reload(); }}>
              Bind this device
            </Button>
          )
        }
      />
      {error ? <ErrorNote error={error} onRetry={reload} /> : loading && !data ? <Spinner /> : !data?.length ? (
        <Card><Empty icon={<TabletSmartphone className="size-6" />} title="No devices bound yet" /></Card>
      ) : (
        <Card>
          <ul className="divide-y divide-line">
            {data.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <TabletSmartphone className="size-5 text-muted" />
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-ink">{d.label} {d.id === me && <Badge tone="teal">this device</Badge>}</p>
                  <p className="font-mono text-xs text-subtle">{d.id}</p>
                  <p className="text-xs text-muted">Bound by {d.bound_by} {timeAgo(d.bound_at)}{d.last_seen_at && ` · last seen ${timeAgo(d.last_seen_at)}`}</p>
                </div>
                {d.revoked ? <Badge tone="crit">Revoked</Badge> : (
                  <Button size="sm" variant="secondary" icon={<ShieldOff className="size-4" />} onClick={async () => {
                    try {
                      await api.revokeDevice(d.id);
                      toast("Device revoked");
                      reload();
                    } catch (e) {
                      toast(e instanceof Error ? e.message : "Failed", "error");
                    }
                  }}>
                    Revoke
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
