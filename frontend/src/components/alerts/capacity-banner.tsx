"use client";

import Link from "next/link";
import { Users } from "lucide-react";
import { api } from "@/lib/api";
import { fmtWait, useAsync } from "@/lib/hooks";
import { usePrefs, useSession } from "@/components/providers";

/** C3: shown on the clinical workspaces when open RED cases outnumber the doctors and medical officers on duty. */
export function CapacityBanner() {
  const { tr } = usePrefs();
  const { user } = useSession();
  const { data } = useAsync(() => api.capacity(), [user?.id], { pollMs: 20_000 });
  if (!data?.over) return null;
  const longest = Math.max(0, ...data.reds.map((r) => r.wait_minutes));
  return (
    <div role="alert" className="mb-4 flex flex-wrap items-center gap-3 rounded-2xl border border-crit-line bg-crit-bg px-4 py-3 text-crit">
      <Users className="size-5 shrink-0" />
      <div className="min-w-0 flex-1 text-sm">
        <p className="font-semibold">
          {tr(data.doctors_on_duty === 1 ? "{r} RED cases waiting, 1 doctor or medical officer on duty" : "{r} RED cases waiting, {d} doctors or medical officers on duty", { r: data.open_red, d: data.doctors_on_duty })}
        </p>
        <p>
          {tr("Tokens")}: {data.reds.map((r) => r.token ?? "—").join(", ")} · {tr("longest wait")} {fmtWait(longest)}.{" "}
          {data.alert?.status === "acknowledged"
            ? tr("Acknowledged by {n}.", { n: data.alert.acknowledged_by ?? "" })
            : tr("The medical officer has been alerted: call in another doctor, or refer the longest-waiting RED case.")}
        </p>
      </div>
      {(user?.role === "medical_officer" || user?.role === "doctor") && (
        <Link href="/reviewer/alerts" className="rounded-lg border border-crit-line bg-white px-3 py-1.5 text-sm font-semibold">
          {tr("Open alerts")}
        </Link>
      )}
    </div>
  );
}
