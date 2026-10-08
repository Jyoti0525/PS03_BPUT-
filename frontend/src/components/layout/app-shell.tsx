"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { LogOut, Building2, ChevronDown, KeyRound, Mail } from "lucide-react";
import { usePrefs, useSession } from "@/components/providers";
import { A11yButton, LanguageButton, Logo } from "./chrome";
import { cx } from "@/components/ui";
import { useAsync } from "@/lib/hooks";
import { api } from "@/lib/api";
import { PIN_ROLES } from "@/lib/types";
import { healthWorkerLabel, nurseLabel } from "@/lib/cadres";
import { ChangePinModal } from "@/components/auth/change-pin";
import { EmailModal } from "@/components/auth/email-settings";

export interface NavItem {
  href: string;
  label: string;
  icon: ReactNode;
  badge?: number | null;
  exact?: boolean;
  /** Heading the item sits under in the side menu; items without one come first. */
  group?: string;
}

const ROLE_LABEL: Record<string, string> = {
  doctor: "Doctor",
  medical_officer: "Medical Officer",
  nurse: "Nurse / ANM",
  health_worker: "Health worker / ASHA",
  receptionist: "Receptionist",
  supervisor: "Facility Supervisor",
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
  const { tr, lang } = usePrefs();
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
          {nav.map((n, i) => (
            <Fragment key={n.href}>
            {n.group && n.group !== nav[i - 1]?.group && <p className="mt-4 mb-1 px-3 text-[11px] font-bold tracking-wide text-subtle uppercase">{n.group}</p>}
            <Link
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
            </Fragment>
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
                <AccountMenu
                  name={user.name}
                  role={user.role === "nurse" ? nurseLabel(facility?.region, tr, lang) : user.role === "health_worker" ? healthWorkerLabel(facility?.region, tr, lang) : tr(ROLE_LABEL[user.role] ?? user.role)}
                  onEmail={authOpts?.email ? () => setEmailOpen(true) : undefined}
                  onPin={PIN_ROLES.includes(user.role) ? () => setPinOpen(true) : undefined}
                  onSignOut={async () => {
                    await signOut();
                    router.replace("/auth");
                  }}
                />
              )}
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

/** Name and role in the header; account settings and sign-out live in one menu behind it. */
function AccountMenu({ name, role, onEmail, onPin, onSignOut }: { name: string; role: string; onEmail?: () => void; onPin?: () => void; onSignOut: () => void }) {
  const { tr } = usePrefs();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);
  const item = "flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm font-medium text-ink-2 hover:bg-canvas";
  const pick = (fn: () => void) => () => {
    setOpen(false);
    fn();
  };
  return (
    <div ref={ref} className="relative sm:border-l sm:border-line sm:pl-3">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-haspopup="menu" aria-expanded={open} className="flex items-center gap-2 rounded-xl p-1 pr-2 hover:bg-canvas">
        <span className="grid size-8 place-items-center rounded-full bg-coral-100 text-sm font-bold text-coral-700">{name.replace(/^Dr\.\s*/, "").charAt(0)}</span>
        <span className="hidden text-left leading-tight sm:block">
          <span className="block text-sm font-semibold text-ink">{name}</span>
          <span className="block text-[11px] text-muted">{role}</span>
        </span>
        <ChevronDown className="size-4 text-muted" aria-hidden />
      </button>
      {open && (
        <div role="menu" className="absolute right-0 z-50 mt-2 w-56 rounded-xl border border-line bg-surface p-1.5 shadow-[var(--shadow-pop)]">
          <p className="px-3 pt-1.5 pb-2 text-xs text-muted sm:hidden">
            <span className="block font-semibold text-ink">{name}</span>
            {role}
          </p>
          {onEmail && (
            <button role="menuitem" className={item} onClick={pick(onEmail)}>
              <Mail className="size-4 text-muted" /> {tr("Email for sign-in codes")}
            </button>
          )}
          {onPin && (
            <button role="menuitem" className={item} onClick={pick(onPin)}>
              <KeyRound className="size-4 text-muted" /> {tr("Change PIN")}
            </button>
          )}
          <button role="menuitem" className={cx(item, "text-crit")} onClick={pick(onSignOut)}>
            <LogOut className="size-4" /> {tr("Sign out")}
          </button>
        </div>
      )}
    </div>
  );
}

/** Shown where a list refreshes itself, instead of a Refresh button. */
export function AutoUpdates() {
  const { tr } = usePrefs();
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted">
      <span className="size-2 rounded-full bg-rout" aria-hidden /> {tr("Updates automatically")}
    </span>
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
