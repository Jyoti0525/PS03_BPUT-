"use client";

import { ListOrdered, ScanLine, Siren, Send } from "lucide-react";
import { RoleGate } from "@/components/layout/role-gate";
import { AppShell } from "@/components/layout/app-shell";
import { useAsync } from "@/lib/hooks";
import { api } from "@/lib/api";
import { usePrefs, useSession } from "@/components/providers";

/** Medical officer workspace: triage decisions, escalations and referrals. */
function Shell({ children }: { children: React.ReactNode }) {
  const { user } = useSession();
  const { tr } = usePrefs();
  const { data: open } = useAsync(() => api.listEscalations("open"), [user?.id], { pollMs: 20_000 });
  return (
    <AppShell
      section={tr("Medical officer")}
      accent="ink"
      nav={[
        { href: "/reviewer", label: tr("Triage queue"), icon: <ListOrdered />, exact: true },
        { href: "/reviewer/lookup", label: tr("Find patient / QR"), icon: <ScanLine /> },
        { href: "/reviewer/escalations", label: tr("Escalations"), icon: <Siren />, badge: open?.length },
        { href: "/reviewer/referrals", label: tr("Referrals"), icon: <Send /> },
      ]}
    >
      {children}
    </AppShell>
  );
}

export default function ReviewerLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleGate roles={["doctor"]}>
      <Shell>{children}</Shell>
    </RoleGate>
  );
}
