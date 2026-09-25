"use client";

import { HeartPulse, PlusCircle } from "lucide-react";
import { RoleGate } from "@/components/layout/role-gate";
import { AppShell } from "@/components/layout/app-shell";
import { usePrefs } from "@/components/providers";

function Shell({ children }: { children: React.ReactNode }) {
  const { t } = usePrefs();
  return (
    <AppShell
      section={t("patient.home")}
      nav={[
        { href: "/patient", label: t("patient.home"), icon: <HeartPulse />, exact: true },
        { href: "/patient/new", label: t("patient.newProblem"), icon: <PlusCircle /> },
      ]}
    >
      {children}
    </AppShell>
  );
}

export default function PatientLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleGate roles={["patient"]}>
      <Shell>{children}</Shell>
    </RoleGate>
  );
}
