"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { ArrowRight, Menu, X } from "lucide-react";
import { A11yButton, LanguageButton, Logo } from "@/components/layout/chrome";
import { SampleDataSwitch } from "@/components/site/sample-data";
import { StatusPill } from "@/components/site/system-status";
import { HOME_FOR_ROLE } from "@/components/layout/role-gate";
import { useSession } from "@/components/providers";
import { useSite } from "@/lib/i18n/site";
import { cx } from "@/components/ui";

const SECTIONS = ["features", "how", "scenarios", "safety"] as const;

/** Public site header: logo left, section links centred, actions right. Collapses to a menu on small screens. */
export function SiteHeader() {
  const c = useSite();
  const { user } = useSession();
  const path = usePathname();
  const onHome = path === "/";
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (!onHome) return;
    const els = SECTIONS.map((id) => document.getElementById(id)).filter((e): e is HTMLElement => !!e);
    const io = new IntersectionObserver(
      (entries) => {
        const vis = entries.filter((e) => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (vis) setActive(vis.target.id);
      },
      { rootMargin: "-40% 0px -50% 0px", threshold: [0, 0.25, 0.5] },
    );
    els.forEach((e) => io.observe(e));
    return () => io.disconnect();
  }, [onHome]);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  const links = [
    { id: "features", label: c.nav.features },
    { id: "how", label: c.nav.how },
    { id: "scenarios", label: c.nav.scenarios },
    { id: "safety", label: c.nav.safety },
  ];
  const href = (id: string) => (onHome ? `#${id}` : `/#${id}`);
  const cta = user ? { href: HOME_FOR_ROLE[user.role], label: c.nav.openWorkspace } : { href: "/auth?mode=register", label: c.nav.getStarted };

  return (
    <header className={cx("sticky top-0 z-40 transition-all duration-300", scrolled || open ? "border-b border-line/80 bg-white/85 shadow-[0_4px_24px_-12px_rgb(22_24_43/0.15)] backdrop-blur-xl" : "bg-transparent")}>
      <div className="mx-auto grid h-18 max-w-6xl grid-cols-[1fr_auto] items-center lg:grid-cols-[1fr_auto_1fr] gap-4 px-4 sm:px-6">
        <Logo className="justify-self-start" />
        <nav className="hidden justify-center lg:flex" aria-label="Main">
          <ul className="flex items-center gap-1">
            {links.map((l) => (
              <li key={l.id}>
                <a
                  href={href(l.id)}
                  className={cx(
                    "relative rounded-full px-3 py-2 text-[15px] font-medium whitespace-nowrap transition-colors",
                    active === l.id ? "text-ink" : "text-muted hover:text-ink",
                  )}
                >
                  {l.label}
                  <span className={cx("absolute inset-x-3 -bottom-0.5 h-0.5 origin-center rounded-full bg-coral-300 transition-transform duration-300", active === l.id ? "scale-x-100" : "scale-x-0")} />
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <div className="flex items-center justify-end gap-2">
          <SampleDataSwitch className="hidden md:inline-flex" />
          <StatusPill className="hidden xl:inline-flex" />
          <LanguageButton className="hidden sm:block" />
          <LanguageButton compact className="sm:hidden" />
          <A11yButton className="hidden md:inline-flex" />
          {!user && (
            <Link href="/auth" className="hidden h-10 items-center rounded-full border border-line bg-white px-4 text-sm font-semibold whitespace-nowrap text-ink transition-colors hover:border-coral-200 md:inline-flex">
              {c.nav.signIn}
            </Link>
          )}
          <Link href={cta.href} className="bg-brand-gradient hidden h-10 items-center gap-1.5 rounded-full px-5 text-sm font-semibold whitespace-nowrap text-white shadow-[0_8px_20px_-6px_rgb(242_145_145/0.8)] transition-transform hover:-translate-y-0.5 sm:inline-flex">
            {cta.label}
          </Link>
          <button onClick={() => setOpen((o) => !o)} className="inline-flex size-10 items-center justify-center rounded-full border border-line bg-white text-ink lg:hidden" aria-label="Menu" aria-expanded={open}>
            {open ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </div>

      {open && (
        <div className="fade-up border-t border-line bg-white lg:hidden">
          <nav className="mx-auto flex max-w-6xl flex-col px-4 py-3" aria-label="Mobile">
            {links.map((l) => (
              <a key={l.id} href={href(l.id)} onClick={() => setOpen(false)} className="flex items-center justify-between rounded-xl px-3 py-3.5 text-base font-medium text-ink hover:bg-canvas">
                {l.label} <ArrowRight className="size-4 text-subtle" />
              </a>
            ))}
            <div className="mt-3 grid grid-cols-2 gap-2 border-t border-line pt-4">
              {!user && (
                <Link href="/auth" onClick={() => setOpen(false)} className="inline-flex h-12 items-center justify-center rounded-full border border-line font-semibold text-ink">
                  {c.nav.signIn}
                </Link>
              )}
              <Link href={cta.href} onClick={() => setOpen(false)} className={cx("bg-brand-gradient inline-flex h-12 items-center justify-center rounded-full font-semibold text-white", user && "col-span-2")}>
                {cta.label}
              </Link>
            </div>
            <div className="mt-3 flex flex-wrap justify-center gap-2 pb-2">
              <SampleDataSwitch className="inline-flex md:hidden" />
              <A11yButton />
            </div>
          </nav>
        </div>
      )}
    </header>
  );
}

export function SiteFooter() {
  const c = useSite();
  const f = c.footer;
  const cols = [
    {
      title: f.product,
      links: [
        { label: c.nav.features, href: "/#features" },
        { label: c.nav.how, href: "/#how" },
        { label: c.nav.scenarios, href: "/#scenarios" },
        { label: f.kiosk, href: "/kiosk" },
        { label: c.status.eyebrow, href: "/#status" },
        { label: c.nav.signIn, href: "/auth" },
      ],
    },
    {
      title: f.teams,
      links: [
        { label: f.teamLinks[0], href: "/reviewer" },
        { label: f.teamLinks[1], href: "/kiosk" },
        { label: f.teamLinks[2], href: "/admin" },
        { label: f.teamLinks[3], href: "/employer" },
      ],
    },
    {
      title: f.legal,
      links: f.legalLinks.map((label) => ({ label, href: "/#safety" })),
    },
  ];
  return (
    <footer className="bg-ink text-white">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
        <div>
          <Logo light />
          <p className="mt-4 max-w-xs text-sm leading-relaxed text-white/60">{f.blurb}</p>
          <div className="mt-5 flex flex-wrap gap-2">
            <span className="rounded-full bg-coral-100 px-3 py-1 text-xs font-semibold text-coral-700">{f.badges[0]}</span>
            <span className="rounded-full bg-teal-100 px-3 py-1 text-xs font-semibold text-teal-700">{f.badges[1]}</span>
          </div>
        </div>
        {cols.map((col) => (
          <div key={col.title}>
            <p className="text-xs font-bold tracking-[0.14em] text-white uppercase">{col.title}</p>
            <ul className="mt-4 space-y-3">
              {col.links.map((l) => (
                <li key={l.label}>
                  <Link href={l.href} className="text-sm text-white/60 transition-colors hover:text-coral-200">
                    {l.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="border-t border-white/10">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-6 text-xs text-white/45 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p>
            © {new Date().getFullYear()} {f.rights}
          </p>
          <p className="max-w-md sm:text-right">{f.note}</p>
        </div>
      </div>
    </footer>
  );
}
