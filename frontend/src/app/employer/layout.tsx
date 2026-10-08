"use client";

import { Briefcase, Building2, Landmark, Users } from "lucide-react";
import { RoleGate } from "@/components/layout/role-gate";
import { AppShell } from "@/components/layout/app-shell";
import { usePrefs } from "@/components/providers";

export default function EmployerLayout({ children }: { children: React.ReactNode }) {
  const { tr } = usePrefs();
  return (
    <RoleGate roles={["employer"]}>
      <AppShell
        section={tr("Employer")}
        nav={[
          { href: "/employer", label: tr("Fitness overview"), icon: <Briefcase />, exact: true },
          { href: "/employer/workers", label: tr("Workers"), icon: <Users /> },
          { href: "/employer/workplaces", label: tr("Workplaces"), icon: <Building2 /> },
          { href: "/employer/organisation", label: tr("Organisation"), icon: <Landmark /> },
        ]}
      >
        {children}
      </AppShell>
    </RoleGate>
  );
}
