"use client";

import { usePrefs } from "@/components/providers";
import Link from "next/link";
import { useState } from "react";
import { Send, Ambulance, Car, Footprints } from "lucide-react";
import { api } from "@/lib/api";
import { useAsync, timeAgo } from "@/lib/hooks";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Card, Empty, ErrorNote, Modal, Spinner } from "@/components/ui";
import type { Referral } from "@/lib/types";

const TRANSPORT = {
  ambulance_108: { label: "108 ambulance", icon: <Ambulance className="size-3" /> },
  facility_vehicle: { label: "Facility vehicle", icon: <Car className="size-3" /> },
  self: { label: "Self / family", icon: <Footprints className="size-3" /> },
};

export default function ReferralsPage() {
  const { tr } = usePrefs();
  const { data, error, loading, reload } = useAsync(() => api.listReferrals(), []);
  const [view, setView] = useState<Referral | null>(null);
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader title={tr("Referrals")} subtitle={tr("Referral notes prepared from triage notes. Destinations follow the facility's specialist configuration.")} />
      {error ? <ErrorNote error={error} onRetry={reload} /> : loading && !data ? <Spinner /> : !data?.length ? (
        <Card><Empty icon={<Send className="size-6" />} title={tr("No referrals yet")} body={tr("Open a case and choose “Referral note” to prepare one.")} /></Card>
      ) : (
        <Card>
          <ul className="divide-y divide-line">
            {data.map((r) => (
              <li key={r.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-ink">
                    <Link href={`/reviewer/case/${r.encounter_id}`} className="hover:underline">{r.patient_name}</Link> <span className="font-normal text-muted">→ {r.destination}</span>
                  </p>
                  <p className="text-sm text-muted">{tr(r.specialty)} · {tr(r.reason)}</p>
                  <p className="text-xs text-subtle">{tr("by")} {r.created_by} · {timeAgo(r.created_at)}</p>
                </div>
                <Badge>{TRANSPORT[r.transport].icon} {tr(TRANSPORT[r.transport].label)}</Badge>
                <Badge tone="teal">{r.status}</Badge>
                <button className="text-sm font-semibold text-teal-700 hover:underline" onClick={() => setView(r)}>{tr("View note")}</button>
              </li>
            ))}
          </ul>
        </Card>
      )}
      <Modal open={!!view} onClose={() => setView(null)} title={tr("Referral — {name}", { name: view?.patient_name ?? "" })} size="lg">
        <pre className="font-mono text-[13px] whitespace-pre-wrap text-ink">{tr(view?.note_text)}</pre>
      </Modal>
    </div>
  );
}
