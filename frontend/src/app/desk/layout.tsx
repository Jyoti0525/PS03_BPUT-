"use client";

import { ConciergeBell, Search, Stethoscope, Tablet } from "lucide-react";
import { RoleGate } from "@/components/layout/role-gate";
import { AppShell } from "@/components/layout/app-shell";
import { usePrefs } from "@/components/providers";

/** Receptionist workspace: patients, doctors & nurses on duty, and waiting-time management. */
function Shell({ children }: { children: React.ReactNode }) {
  const { tr } = usePrefs();
  return (
    <AppShell
      section={tr("Front desk")}
      accent="info"
      nav={[
        { href: "/desk", label: tr("Today's patients"), icon: <ConciergeBell />, exact: true },
        { href: "/desk/patients", label: tr("Find & register"), icon: <Search /> },
        { href: "/desk/staff", label: tr("Doctors & nurses"), icon: <Stethoscope /> },
        { href: "/kiosk", label: tr("Check-in kiosk"), icon: <Tablet /> },
      ]}
    >
      {children}
    </AppShell>
  );
}

export default function DeskLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleGate roles={["receptionist"]}>
      <Shell>{children}</Shell>
    </RoleGate>
  );
}
