"use client";

import { LayoutDashboard, Building2, TabletSmartphone, Users, ScrollText, Trash2, Tablet } from "lucide-react";
import { RoleGate } from "@/components/layout/role-gate";
import { AppShell } from "@/components/layout/app-shell";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleGate roles={["receptionist", "supervisor"]}>
      <AppShell
        section="Facility admin"
        nav={[
          { href: "/admin", label: "Overview", icon: <LayoutDashboard />, exact: true },
          { href: "/admin/facility", label: "Facility setup", icon: <Building2 /> },
          { href: "/admin/devices", label: "Kiosk devices", icon: <TabletSmartphone /> },
          { href: "/admin/staff", label: "Staff", icon: <Users /> },
          { href: "/admin/audit", label: "Audit log", icon: <ScrollText /> },
          { href: "/admin/retention", label: "Data retention", icon: <Trash2 /> },
          { href: "/kiosk", label: "Open kiosk", icon: <Tablet /> },
        ]}
      >
        {children}
      </AppShell>
    </RoleGate>
  );
}
