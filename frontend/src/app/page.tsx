"use client";

import Link from "next/link";
import { ArrowRight, Mic, FileScan, ListOrdered, ShieldCheck, Stethoscope, Tablet, Building2, HeartPulse, Briefcase, Scale, History, Languages, WifiOff, UserCheck } from "lucide-react";
import { A11yButton, LanguageButton, Logo } from "@/components/layout/chrome";
import { usePrefs, useSession } from "@/components/providers";
import { HOME_FOR_ROLE } from "@/components/layout/role-gate";
import { Button } from "@/components/ui";

const PORTALS = [
  { href: "/kiosk", icon: <Tablet />, title: "Patient intake kiosk", body: "Staff-mediated tablet intake: voice-first, icon mode, reports & photos, works offline.", who: "Nurse / ANM / ASHA" },
  { href: "/reviewer", icon: <Stethoscope />, title: "Reviewer dashboard", body: "Queue ordered by rules-engine urgency, 4-minute case view with source for every value.", who: "Doctor / Nurse" },
  { href: "/admin", icon: <Building2 />, title: "Facility admin", body: "Facility type, specialists on duty, kiosk devices, audit trail and data retention.", who: "Receptionist / Supervisor" },
  { href: "/patient", icon: <HeartPulse />, title: "My health", body: "Add a new problem, upload reports, see visits and check-up reminders.", who: "Patient" },
  { href: "/employer", icon: <Briefcase />, title: "Employer view", body: "Occupational fitness status by cohort. No clinical records, ever.", who: "Industrial / company HR" },
];

const PRINCIPLES = [
  { icon: <Scale />, title: "Non-diagnostic", body: "Organises what the patient said and brought. Never diagnoses, never prescribes." },
  { icon: <ListOrdered />, title: "Deterministic urgency", body: "Red / yellow / green comes only from hard-coded AIIMS ATP and IMCI rules — not a language model." },
  { icon: <UserCheck />, title: "Human in the loop", body: "A qualified reviewer confirms every note. Overrides need a written reason and are logged." },
  { icon: <FileScan />, title: "Source traceability", body: "Each extracted value sits beside the report crop or transcript it came from." },
  { icon: <History />, title: "Append-only audit", body: "Every view, edit, override and export is hash-chained and cannot be altered." },
  { icon: <ShieldCheck />, title: "Minimal retention", body: "Raw audio and photos expire automatically. Patients never see triage status." },
];

export default function Landing() {
  const { t } = usePrefs();
  const { user } = useSession();

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-20 border-b border-line bg-surface/90 backdrop-blur">
        <div className="mx-auto flex h-16 max-w-6xl items-center gap-3 px-4">
          <Logo />
          <div className="ml-auto flex items-center gap-2">
            <LanguageButton className="hidden sm:block" />
            <LanguageButton compact className="sm:hidden" />
            <A11yButton />
            {user ? (
              <Link href={HOME_FOR_ROLE[user.role]}>
                <Button size="md">Open workspace</Button>
              </Link>
            ) : (
              <Link href="/auth">
                <Button size="md">{t("auth.signin")}</Button>
              </Link>
            )}
          </div>
        </div>
      </header>

      <section className="relative overflow-hidden">
        <div className="absolute inset-0 -z-10 bg-[radial-gradient(60%_60%_at_85%_0%,var(--color-teal-100),transparent),radial-gradient(50%_50%_at_0%_30%,var(--color-coral-50),transparent)]" />
        <div className="mx-auto grid max-w-6xl gap-10 px-4 py-14 lg:grid-cols-[1.15fr_1fr] lg:py-20">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full border border-teal-200 bg-white px-3 py-1 text-xs font-semibold text-teal-700">
              BPUT Hackathon 2026 · Problem Statement 3
            </p>
            <h1 className="mt-4 text-4xl leading-tight font-extrabold tracking-tight text-ink sm:text-5xl">
              Faster, safer triage review for every kind of Indian health facility.
            </h1>
            <p className="mt-4 max-w-xl text-lg text-muted">
              Jeevia turns what a patient says, the reports they carry and simple photos into a structured, prioritised triage note — for a qualified professional to review in under four minutes.
            </p>
            <div className="mt-7 flex flex-wrap gap-3">
              <Link href="/kiosk">
                <Button size="lg" variant="teal" icon={<Tablet className="size-5" />}>
                  Start patient intake
                </Button>
              </Link>
              <Link href="/auth">
                <Button size="lg" variant="secondary">
                  Staff sign in <ArrowRight className="size-4" />
                </Button>
              </Link>
            </div>
            <div className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-muted">
              <span className="flex items-center gap-1.5"><Mic className="size-4 text-teal-700" /> Voice in 22 languages</span>
              <span className="flex items-center gap-1.5"><FileScan className="size-4 text-teal-700" /> OCR for lab slips</span>
              <span className="flex items-center gap-1.5"><WifiOff className="size-4 text-teal-700" /> Offline camp mode</span>
              <span className="flex items-center gap-1.5"><Languages className="size-4 text-teal-700" /> Hindi · Odia · + 20</span>
            </div>
          </div>

          <div className="rounded-3xl border border-line bg-white p-4 shadow-[var(--shadow-pop)]">
            <div className="mb-3 flex items-center justify-between">
              <p className="text-sm font-semibold text-ink">Triage queue · PHC Manikpur</p>
              <span className="text-xs text-subtle">ordered by rules engine</span>
            </div>
            {[
              { u: "crit", n: "Radha K., 42F", c: "Chest pain → left arm, sweating", f: "ATP-CARD-01", w: "8m" },
              { u: "crit", n: "Aarav S., 3M", c: "High fever, one convulsion", f: "IMCI-DANGER-01", w: "11m" },
              { u: "semi", n: "Lakshmi D., 55F", c: "Thirst, blurred vision (diabetic)", f: "Report: FBS 310", w: "38m" },
              { u: "rout", n: "Priya S., 24F", c: "Routine ANC, 28 weeks", f: "No red flags", w: "62m" },
            ].map((r) => (
              <div key={r.n} className="mb-2 flex items-center gap-3 rounded-2xl border border-line px-3 py-2.5 last:mb-0">
                <span className={`h-9 w-1.5 rounded-full ${r.u === "crit" ? "bg-crit" : r.u === "semi" ? "bg-amber-500" : "bg-rout"}`} />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold text-ink">{r.n}</p>
                  <p className="truncate text-xs text-muted">{r.c}</p>
                </div>
                <span className="hidden rounded-md bg-canvas px-2 py-0.5 font-mono text-[11px] text-muted sm:inline">{r.f}</span>
                <span className="text-xs text-subtle tabular-nums">{r.w}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-4 py-12">
        <h2 className="text-2xl font-bold text-ink">One system, five workspaces</h2>
        <p className="mt-1 text-muted">Each role sees only what it needs. Health outputs stay reviewer-facing.</p>
        <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {PORTALS.map((p) => (
            <Link key={p.href} href={p.href} className="group rounded-2xl border border-line bg-white p-5 transition-shadow hover:shadow-[var(--shadow-pop)]">
              <span className="grid size-11 place-items-center rounded-xl bg-teal-50 text-teal-700 [&>svg]:size-5.5">{p.icon}</span>
              <h3 className="mt-4 font-semibold text-ink">{p.title}</h3>
              <p className="mt-1 text-sm text-muted">{p.body}</p>
              <p className="mt-3 flex items-center justify-between text-xs font-medium text-subtle">
                {p.who} <ArrowRight className="size-4 text-teal-700 transition-transform group-hover:translate-x-1" />
              </p>
            </Link>
          ))}
        </div>
      </section>

      <section className="border-y border-line bg-white">
        <div className="mx-auto max-w-6xl px-4 py-12">
          <h2 className="text-2xl font-bold text-ink">Safety rules the system is built around</h2>
          <div className="mt-6 grid gap-x-8 gap-y-6 sm:grid-cols-2 lg:grid-cols-3">
            {PRINCIPLES.map((p) => (
              <div key={p.title} className="flex gap-3">
                <span className="mt-0.5 text-coral-600 [&>svg]:size-5">{p.icon}</span>
                <div>
                  <h3 className="font-semibold text-ink">{p.title}</h3>
                  <p className="mt-0.5 text-sm text-muted">{p.body}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <footer className="mx-auto max-w-6xl px-4 py-8 text-sm text-muted">
        <p className="font-medium text-ink-2">Clinical safety notice</p>
        <p className="mt-1 max-w-3xl">
          Jeevia is an educational prototype for triage support. It uses synthetic data only, does not diagnose or recommend treatment, and every output must be reviewed by a qualified medical professional.
        </p>
      </footer>
    </div>
  );
}
