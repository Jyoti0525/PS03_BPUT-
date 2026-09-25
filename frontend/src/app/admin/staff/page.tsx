"use client";

import { Users, KeyRound } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync, timeAgo } from "@/lib/hooks";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Card, Empty, ErrorNote, Spinner } from "@/components/ui";
import { langByCode } from "@/lib/i18n/languages";

export default function StaffPage() {
  const { data, error, loading, reload } = useAsync(() => api.listUsers(), []);
  return (
    <div className="mx-auto max-w-4xl">
      <PageHeader title="Staff" subtitle="Accounts linked to this facility. New staff register themselves with phone + OTP." />
      {error ? <ErrorNote error={error} onRetry={reload} /> : loading && !data ? <Spinner /> : !data?.length ? <Card><Empty icon={<Users className="size-6" />} title="No staff yet" /></Card> : (
        <Card>
          <ul className="divide-y divide-line">
            {data.map((u) => (
              <li key={u.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <span className="grid size-10 place-items-center rounded-full bg-teal-50 font-bold text-teal-700">{u.name.replace(/^Dr\.\s*/, "").charAt(0)}</span>
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-ink">{u.name}</p>
                  <p className="text-xs text-muted">+91 {u.phone.slice(0, 5)}••••• · {langByCode(u.language).name} · joined {timeAgo(u.created_at)}</p>
                </div>
                {u.registration_no && <Badge>{u.registration_no}</Badge>}
                {u.has_pin && <Badge tone="teal"><KeyRound className="size-3" /> PIN</Badge>}
                <Badge tone="info">{u.role}</Badge>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
