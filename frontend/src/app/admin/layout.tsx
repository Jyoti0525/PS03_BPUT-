"use client";

import { LayoutDashboard, Building2, TabletSmartphone, Users, ScrollText, Trash2, Tablet, Link2 } from "lucide-react";
import { RoleGate } from "@/components/layout/role-gate";
import { AppShell } from "@/components/layout/app-shell";
import { usePrefs } from "@/components/providers";

/** Supervisor workspace: facility configuration, staff, kiosk links, devices, audit and retention. */
function Shell({ children }: { children: React.ReactNode }) {
  const { tr } = usePrefs();
  return (
    <AppShell
      section={tr("Facility supervisor")}
      accent="coral"
      nav={[
        { href: "/admin", label: tr("Overview"), icon: <LayoutDashboard />, exact: true },
        { href: "/admin/staff", label: tr("Staff & duty"), icon: <Users /> },
        { href: "/admin/facility", label: tr("Facility setup"), icon: <Building2 /> },
        { href: "/admin/kiosk-links", label: tr("Kiosk links"), icon: <Link2 /> },
        { href: "/admin/devices", label: tr("Staff devices"), icon: <TabletSmartphone /> },
        { href: "/admin/audit", label: tr("Audit log"), icon: <ScrollText /> },
        { href: "/admin/retention", label: tr("Data retention"), icon: <Trash2 /> },
        { href: "/kiosk", label: tr("Staff kiosk"), icon: <Tablet /> },
      ]}
    >
      {children}
    </AppShell>
  );
}

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <RoleGate roles={["supervisor"]}>
      <Shell>{children}</Shell>
    </RoleGate>
  );
}
