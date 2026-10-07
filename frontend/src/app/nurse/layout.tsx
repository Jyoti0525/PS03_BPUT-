"use client";

import { CalendarClock, HeartHandshake, ScanLine, Tablet } from "lucide-react";
import { RoleGate } from "@/components/layout/role-gate";
import { AppShell } from "@/components/layout/app-shell";
import { usePrefs, useSession } from "@/components/providers";
import { CapacityBanner } from "@/components/alerts/capacity-banner";
import { api } from "@/lib/api";
import { useAsync } from "@/lib/hooks";

/** Nursing station and health-worker desk: patients to attend, vitals and observations, assisted intake, maternal and chronic follow-ups and reminder calls. */
function Shell({ children }: { children: React.ReactNode }) {
  const { tr } = usePrefs();
  const { user } = useSession();
  const { data: due } = useAsync(() => api.listFollowups("active"), [user?.id], { pollMs: 60_000 });
  const waiting = due?.filter((f) => f.status === "missed" || f.status === "call_due" || f.status === "flagged").length;
  return (
    <AppShell
      section={user?.role === "health_worker" ? tr("Health worker") : tr("Nursing station")}
      accent="teal"
      nav={[
        { href: "/nurse", label: tr("Patients to attend"), icon: <HeartHandshake />, exact: true },
        { href: "/nurse/lookup", label: tr("Find patient"), icon: <ScanLine /> },
        { href: "/nurse/followups", label: tr("Follow-ups"), icon: <CalendarClock />, badge: waiting || undefined },
        { href: "/kiosk", label: tr("Assisted intake (kiosk)"), icon: <Tablet /> },
      ]}
    >
      {user?.role === "nurse" && <CapacityBanner />}
      {children}
    </AppShell>
  );
}

export default function NurseLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleGate roles={["nurse", "health_worker"]}>
      <Shell>{children}</Shell>
    </RoleGate>
  );
}
