"use client";

import { LayoutDashboard, Building2, CalendarDays, TabletSmartphone, Users, ScrollText, Trash2, Tablet, Link2, ChartColumn, FlaskConical, Bot, ShieldAlert, Info } from "lucide-react";
import { RoleGate } from "@/components/layout/role-gate";
import { AppShell } from "@/components/layout/app-shell";
import { usePrefs } from "@/components/providers";

/** Supervisor workspace: facility configuration, regional calendar and worker names, staff, kiosk links, devices, audit, retention, de-identified cohort, AI second opinions and the output guard test. */
function Shell({ children }: { children: React.ReactNode }) {
  const { tr } = usePrefs();
  return (
    <AppShell
      section={tr("Facility supervisor")}
      accent="coral"
      nav={[
        { href: "/admin", label: tr("Overview"), icon: <LayoutDashboard />, exact: true },
        { href: "/admin/staff", label: tr("Staff & duty"), icon: <Users />, group: tr("Facility") },
        { href: "/admin/facility", label: tr("Facility setup"), icon: <Building2 />, group: tr("Facility") },
        { href: "/admin/calendar", label: tr("Regional calendar"), icon: <CalendarDays />, group: tr("Facility") },
        { href: "/admin/kiosk-links", label: tr("Kiosk links"), icon: <Link2 />, group: tr("Facility") },
        { href: "/admin/devices", label: tr("Staff devices"), icon: <TabletSmartphone />, group: tr("Facility") },
        { href: "/admin/overrides", label: tr("Urgency overrides"), icon: <ShieldAlert />, group: tr("Safety & records") },
        { href: "/admin/ai-opinions", label: tr("AI second opinions"), icon: <Bot />, group: tr("Safety & records") },
        { href: "/admin/audit", label: tr("Audit log"), icon: <ScrollText />, group: tr("Safety & records") },
        { href: "/admin/retention", label: tr("Data retention"), icon: <Trash2 />, group: tr("Safety & records") },
        { href: "/admin/cohort", label: tr("De-identified cohort"), icon: <ChartColumn />, group: tr("Safety & records") },
        { href: "/kiosk", label: tr("Open the kiosk"), icon: <Tablet />, group: tr("Tools") },
        { href: "/admin/guard-test", label: tr("Output guard test"), icon: <FlaskConical />, group: tr("Tools") },
        { href: "/about/models", label: tr("About the models"), icon: <Info />, group: tr("Tools") },
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
