"use client";

import { ListOrdered, ScanLine, Siren, Send, Tablet } from "lucide-react";
import { RoleGate } from "@/components/layout/role-gate";
import { AppShell } from "@/components/layout/app-shell";
import { useAsync } from "@/lib/hooks";
import { api } from "@/lib/api";
import { useSession } from "@/components/providers";

function Shell({ children }: { children: React.ReactNode }) {
  const { user } = useSession();
  const { data: open } = useAsync(() => api.listEscalations("open"), [user?.id], { pollMs: 20_000 });
  return (
    <AppShell
      section={user?.role === "nurse" ? "Nurse workspace" : "Medical officer"}
      nav={[
        { href: "/reviewer", label: "Triage queue", icon: <ListOrdered />, exact: true },
        { href: "/reviewer/lookup", label: "Find patient / QR", icon: <ScanLine /> },
        { href: "/reviewer/escalations", label: "Escalations", icon: <Siren />, badge: open?.length },
        { href: "/reviewer/referrals", label: "Referrals", icon: <Send /> },
        { href: "/kiosk", label: "Open kiosk", icon: <Tablet /> },
      ]}
    >
      {children}
    </AppShell>
  );
}

export default function ReviewerLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleGate roles={["doctor", "nurse"]}>
      <Shell>{children}</Shell>
    </RoleGate>
  );
}
