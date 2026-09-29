"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";
import { LogOut, Building2, KeyRound, Mail } from "lucide-react";
import { usePrefs, useSession } from "@/components/providers";
import { A11yButton, LanguageButton, Logo } from "./chrome";
import { cx } from "@/components/ui";
import { useAsync } from "@/lib/hooks";
import { api } from "@/lib/api";
import { PIN_ROLES } from "@/lib/types";
import { ChangePinModal } from "@/components/auth/change-pin";
import { EmailModal } from "@/components/auth/email-settings";

export interface NavItem {
  href: string;
  label: string;
  icon: ReactNode;
  badge?: number | null;
  exact?: boolean;
}

const ROLE_LABEL: Record<string, string> = {
  doctor: "Medical Officer",
  nurse: "Nurse / ANM",
  receptionist: "Receptionist",
  supervisor: "Facility Supervisor",
  patient: "Patient",
  employer: "Employer",
};

type Accent = "ink" | "teal" | "coral" | "info";

/** Each workspace has its own colour so doctors, nurses, front desk and supervisors never confuse them. */
const ACCENT: Record<Accent, { strip: string; active: string; chip: string }> = {
  ink: { strip: "bg-ink", active: "bg-ink text-white", chip: "bg-ink text-white" },
  teal: { strip: "bg-teal-600", active: "bg-teal-600 text-white", chip: "bg-teal-600 text-white" },
  coral: { strip: "bg-coral-500", active: "bg-coral-500 text-white", chip: "bg-coral-500 text-white" },
  info: { strip: "bg-[#3b6fd8]", active: "bg-[#3b6fd8] text-white", chip: "bg-[#3b6fd8] text-white" },
};

export function AppShell({ nav, children, section, accent = "teal" }: { nav: NavItem[]; children: ReactNode; section: string; accent?: Accent }) {
  const path = usePathname();
  const router = useRouter();
  const { user, signOut } = useSession();
  const { tr } = usePrefs();
  const a = ACCENT[accent];
  const { data: facility } = useAsync(() => (user?.facility_id ? api.getFacility(user.facility_id) : Promise.resolve(null)), [user?.facility_id]);
  const [pinOpen, setPinOpen] = useState(false);
  const [emailOpen, setEmailOpen] = useState(false);
  const { data: authOpts } = useAsync(() => api.authOptions(), []);
  const active = (n: NavItem) => (n.exact ? path === n.href : path === n.href || path.startsWith(n.href + "/"));

  return (
    <div className="flex min-h-[calc(100vh-28px)] flex-col lg:flex-row">
      <aside className="no-print hidden w-60 shrink-0 flex-col border-r border-line bg-surface lg:flex">
        <span className={cx("h-1 w-full", a.strip)} />
        <div className="px-5 py-4">
          <Logo />
        </div>
        <p className={cx("mx-4 mt-1 mb-2 rounded-lg px-3 py-1.5 text-xs font-bold tracking-wide uppercase", a.chip)}>{section}</p>
        <nav className="flex flex-1 flex-col gap-0.5 px-3">
          {nav.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className={cx(
                "flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition-colors",
                active(n) ? a.active : "text-muted hover:bg-canvas hover:text-ink",
              )}
            >
              <span className="[&>svg]:size-4.5">{n.icon}</span>
              <span className="flex-1">{tr(n.label)}</span>
              {!!n.badge && <span className="rounded-full bg-crit px-1.5 text-[11px] font-bold text-white">{n.badge}</span>}
            </Link>
          ))}
        </nav>
        {facility && (
          <div className="m-3 rounded-xl border border-line bg-canvas p-3">
            <div className="flex items-center gap-2 text-xs font-semibold text-ink">
              <Building2 className="size-3.5 text-muted" /> {facility.name}
            </div>
            <p className="mt-0.5 text-[11px] text-muted">
              {facility.district}, {facility.state}
            </p>
          </div>
        )}
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="no-print sticky top-0 z-30 border-b border-line bg-surface/95 backdrop-blur">
          <div className="flex h-14 items-center gap-3 px-4 lg:px-6">
            <Logo className="lg:hidden" />
            <span className={cx("rounded-md px-2 py-0.5 text-[11px] font-bold uppercase lg:hidden", a.chip)}>{section}</span>
            <div className="hidden min-w-0 flex-1 lg:block">
              {facility && (
                <p className="truncate text-sm text-muted">
                  <span className="font-semibold text-ink">{facility.name}</span> · {tr(facility.type.replace(/_/g, " ")).toUpperCase()}
                </p>
              )}
            </div>
            <div className="ml-auto flex items-center gap-2">
              <LanguageButton compact className="sm:hidden" />
              <LanguageButton className="hidden sm:block" />
              <A11yButton />
              {user && (
                <div className="hidden items-center gap-2 border-l border-line pl-3 sm:flex">
                  <span className="grid size-8 place-items-center rounded-full bg-coral-100 text-sm font-bold text-coral-700">{user.name.replace(/^Dr\.\s*/, "").charAt(0)}</span>
                  <div className="leading-tight">
                    <p className="text-sm font-semibold text-ink">{user.name}</p>
                    <p className="text-[11px] text-muted">{tr(ROLE_LABEL[user.role] ?? user.role)}</p>
                  </div>
                </div>
              )}
              {user && authOpts?.email && (
                <button
                  onClick={() => setEmailOpen(true)}
                  className="inline-flex size-9 items-center justify-center rounded-lg text-muted hover:bg-canvas hover:text-ink"
                  aria-label={tr("Email for sign-in codes")}
                  title={tr("Email for sign-in codes")}
                >
                  <Mail className="size-4.5" />
                </button>
              )}
              {user && PIN_ROLES.includes(user.role) && (
                <button
                  onClick={() => setPinOpen(true)}
                  className="inline-flex size-9 items-center justify-center rounded-lg text-muted hover:bg-canvas hover:text-ink"
                  aria-label={tr("Change PIN")}
                  title={tr("Change PIN")}
                >
                  <KeyRound className="size-4.5" />
                </button>
              )}
              <button
                onClick={async () => {
                  await signOut();
                  router.replace("/auth");
                }}
                className="inline-flex size-9 items-center justify-center rounded-lg text-muted hover:bg-canvas hover:text-ink"
                aria-label={tr("Sign out")}
                title={tr("Sign out")}
              >
                <LogOut className="size-4.5" />
              </button>
            </div>
          </div>
          <nav className="flex gap-1 overflow-x-auto px-3 pb-2 lg:hidden" aria-label={section}>
            {nav.map((n) => (
              <Link
                key={n.href}
                href={n.href}
                className={cx(
                  "flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium",
                  active(n) ? a.active : "bg-canvas text-muted",
                )}
              >
                <span className="[&>svg]:size-4">{n.icon}</span>
                {tr(n.label)}
                {!!n.badge && <span className="rounded-full bg-crit px-1.5 text-[10px] font-bold text-white">{n.badge}</span>}
              </Link>
            ))}
          </nav>
        </header>
        <main className="min-w-0 flex-1 p-4 lg:p-6">{children}</main>
        <ChangePinModal open={pinOpen} onClose={() => setPinOpen(false)} />
        <EmailModal open={emailOpen} onClose={() => setEmailOpen(false)} />
      </div>
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: ReactNode; subtitle?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-bold text-ink sm:text-2xl">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}
