"use client";

import { BellRing, ListOrdered, ScanLine, Siren, Send } from "lucide-react";
import { RoleGate } from "@/components/layout/role-gate";
import { AppShell } from "@/components/layout/app-shell";
import { useAsync } from "@/lib/hooks";
import { api } from "@/lib/api";
import { usePrefs, useSession } from "@/components/providers";
import { CapacityBanner } from "@/components/alerts/capacity-banner";
import { DOCTOR_ROLES } from "@/lib/types";

/** Doctor and medical officer workspace: triage decisions, escalations, referrals and alerts. */
function Shell({ children }: { children: React.ReactNode }) {
  const { user } = useSession();
  const { tr } = usePrefs();
  const { data: open } = useAsync(() => api.listEscalations("open"), [user?.id], { pollMs: 20_000 });
  const { data: alerts } = useAsync(() => api.listAlerts("open"), [user?.id], { pollMs: 20_000 });
  return (
    <AppShell
      section={user?.role === "medical_officer" ? tr("Medical officer") : tr("Doctor")}
      accent="ink"
      nav={[
        { href: "/reviewer", label: tr("Triage queue"), icon: <ListOrdered />, exact: true },
        { href: "/reviewer/lookup", label: tr("Find patient / QR"), icon: <ScanLine /> },
        { href: "/reviewer/escalations", label: tr("Escalations"), icon: <Siren />, badge: open?.length },
        { href: "/reviewer/referrals", label: tr("Referrals"), icon: <Send /> },
        { href: "/reviewer/alerts", label: tr("Alerts"), icon: <BellRing />, badge: alerts?.length },
      ]}
    >
      <CapacityBanner />
      {children}
    </AppShell>
  );
}

export default function ReviewerLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleGate roles={DOCTOR_ROLES}>
      <Shell>{children}</Shell>
    </RoleGate>
  );
}
