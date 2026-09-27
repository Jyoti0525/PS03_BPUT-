"use client";

import { HeartHandshake, ScanLine, Tablet } from "lucide-react";
import { RoleGate } from "@/components/layout/role-gate";
import { AppShell } from "@/components/layout/app-shell";
import { usePrefs } from "@/components/providers";

/** Nursing station: patients to attend, vitals and observations, assisted kiosk intake. */
function Shell({ children }: { children: React.ReactNode }) {
  const { tr } = usePrefs();
  return (
    <AppShell
      section={tr("Nursing station")}
      accent="teal"
      nav={[
        { href: "/nurse", label: tr("Patients to attend"), icon: <HeartHandshake />, exact: true },
        { href: "/nurse/lookup", label: tr("Find patient"), icon: <ScanLine /> },
        { href: "/kiosk", label: tr("Assisted intake (kiosk)"), icon: <Tablet /> },
      ]}
    >
      {children}
    </AppShell>
  );
}

export default function NurseLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleGate roles={["nurse"]}>
      <Shell>{children}</Shell>
    </RoleGate>
  );
}
