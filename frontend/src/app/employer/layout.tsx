"use client";

import { Briefcase, Building2, Landmark, Users } from "lucide-react";
import { RoleGate } from "@/components/layout/role-gate";
import { AppShell } from "@/components/layout/app-shell";

export default function EmployerLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleGate roles={["employer"]}>
      <AppShell
        section="Employer"
        nav={[
          { href: "/employer", label: "Fitness overview", icon: <Briefcase />, exact: true },
          { href: "/employer/workers", label: "Workers", icon: <Users /> },
          { href: "/employer/workplaces", label: "Workplaces", icon: <Building2 /> },
          { href: "/employer/organisation", label: "Organisation", icon: <Landmark /> },
        ]}
      >
        {children}
      </AppShell>
    </RoleGate>
  );
}
