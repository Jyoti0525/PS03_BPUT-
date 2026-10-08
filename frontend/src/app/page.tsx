"use client";

import { usePrefs } from "@/components/providers";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  ArrowRight, AudioLines, FileScan, ClipboardList, Languages, UserCheck, ShieldCheck, Building2, Hospital, Tent, Factory, GraduationCap, Briefcase,
  Stethoscope, Scale, ListOrdered, History, Trash2, ChevronLeft, ChevronRight, AlertTriangle, Activity, HardHat, Thermometer, Baby, HeartPulse, WifiOff,
  Send, Cpu, Sparkles, Tablet,
} from "lucide-react";
import { SiteFooter, SiteHeader } from "@/components/site/site-chrome";
import { StatusPanel } from "@/components/site/system-status";
import { PatientEntry } from "@/components/site/patient-entry";
import { CountUp, Reveal, useInView } from "@/components/site/motion";
import { useSite, type SiteCopy } from "@/lib/i18n/site";
import { cx } from "@/components/ui";
import { API_MODE } from "@/lib/api";
import { API_BASE } from "@/lib/api/live";

const U_STYLE = {
  red: { pill: "bg-crit-bg text-crit", dot: "bg-crit" },
  yellow: { pill: "bg-semi-bg text-semi", dot: "bg-amber-400" },
  green: { pill: "bg-rout-bg text-rout", dot: "bg-rout" },
} as const;
const RANK = { red: 0, yellow: 1, green: 2 } as const;
const AVATAR = ["bg-coral-50 text-coral-500", "bg-teal-50 text-teal-700"];

type Preview = {
  facility: string;
  waiting: number;
  red: number;
  rules: number;
  items: { name: string; age: number | null; sex: string | null; complaint: string; urgency: "red" | "yellow" | "green"; why: string; wait_minutes: number }[];
};

/** On the demo laptop (server JEEVIA_DEMO_CONTROLS) the real queue of PHC Manikpur, synthetic patients only; elsewhere null. */
function useQueuePreview() {
  const [p, setP] = useState<Preview | null>(null);
  useEffect(() => {
    if (API_MODE !== "live") return;
    let stop = false;
    const load = () =>
      fetch(`${API_BASE}/demo/queue-preview`)
        .then((r) => (r.ok ? r.json() : null))
        .then((j: Preview | null) => {
          if (!stop) setP(j);
        })
        .catch(() => {});
    void load();
    const t = setInterval(load, 15000);
    return () => {
      stop = true;
      clearInterval(t);
    };
  }, []);
  return p;
}

/** Hero visual: the real queue when the demo server allows it, else a queue that keeps receiving patients and re-sorts them by urgency. */
function LiveQueue({ c }: { c: SiteCopy }) {
  const { tr } = usePrefs();
  const real = useQueuePreview();
  const pool = c.queue.patients;
  const [ids, setIds] = useState<number[]>([0, 2, 4, 5]);
  const [fresh, setFresh] = useState<number | null>(null);
  const cursor = useRef(0);
  const label = (u: "red" | "yellow" | "green") => (u === "red" ? c.queue.critical : u === "yellow" ? c.queue.semi : c.queue.routine);

  useEffect(() => {
    if (real) return;
    const order = [1, 3, 0, 2, 4, 5];
    const t = setInterval(() => {
      const next = order[cursor.current % order.length];
      cursor.current++;
      setIds((cur) => {
        const without = cur.filter((i) => i !== next);
        const kept = without.length >= 4 ? without.slice(0, 3) : without;
        return [...kept, next].sort((a, b) => RANK[pool[a].u] - RANK[pool[b].u]);
      });
      setFresh(next);
    }, 3400);
    return () => clearInterval(t);
  }, [pool, real]);

  const rows = real
    ? real.items.map((p, k) => ({
        key: `r${k}`,
        name: `${p.name}${p.age != null ? `, ${p.age}${p.sex ?? ""}` : ""}`,
        detail: `${p.complaint} · ${tr("waiting {m} min", { m: p.wait_minutes })}${p.why ? ` · ${p.why}` : ""}`,
        u: p.urgency,
        fresh: false,
      }))
    : ids.map((i) => ({ key: `d${i}`, name: pool[i].name, detail: pool[i].detail, u: pool[i].u, fresh: fresh === i }));
  const critical = real ? real.red : ids.filter((i) => pool[i].u === "red").length;

  return (
    <div className="relative mx-auto w-full max-w-md pt-12 pb-20 lg:max-w-none">
      <div className="float-slower absolute top-0 left-4 z-10 hidden rounded-2xl border border-line bg-white/95 px-4 py-3 shadow-[var(--shadow-pop)] backdrop-blur sm:block lg:-left-6">
        <p className="flex items-center gap-1.5 text-[11px] font-medium text-muted">
          <Cpu className="size-3.5 text-teal-600" /> {c.queue.rules}
        </p>
        <p className="mt-0.5 text-sm font-bold text-ink">{real ? tr("{n} cited rules · ATP · IMCI", { n: real.rules }) : c.queue.rulesBody}</p>
      </div>

      <div className="relative rounded-[28px] border border-white/70 bg-white/90 p-5 shadow-[0_30px_80px_-30px_rgb(22_24_43/0.35)] backdrop-blur sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <div className="min-w-0">
            <p className="flex items-center gap-2 font-bold text-ink">
              <span className="relative inline-flex size-2.5 rounded-full text-crit live-dot">
                <span className="size-2.5 rounded-full bg-crit" />
              </span>
              {c.queue.title}
            </p>
            {real && <p className="mt-0.5 truncate pl-4.5 text-xs text-muted">{tr("Live from {f} · synthetic patients", { f: real.facility })}</p>}
          </div>
          <span className="shrink-0 rounded-full bg-crit-bg px-3 py-1 text-xs font-bold tracking-wide text-crit uppercase transition-all">
            {critical} {c.queue.critical}
          </span>
        </div>
        <ul className="mt-4 divide-y divide-line">
          {rows.length === 0 && <li className="py-6 text-center text-sm text-muted">{tr("No one waiting right now.")}</li>}
          {rows.map((p, k) => (
            <li key={p.key} className={cx("flex items-center gap-3 rounded-xl py-3.5 transition-all duration-500", p.fresh && "row-enter")}>
              <span className={cx("grid size-10 shrink-0 place-items-center rounded-full text-sm font-bold", AVATAR[k % 2])}>{p.name.charAt(0)}</span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-ink">{p.name}</p>
                <p className="truncate text-xs text-muted">{p.detail}</p>
              </div>
              <span className={cx("inline-flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold tracking-wide uppercase", U_STYLE[p.u].pill)}>
                <span className={cx("size-2 rounded-full", U_STYLE[p.u].dot)} />
                <span className="hidden sm:inline">{label(p.u)}</span>
              </span>
            </li>
          ))}
        </ul>
        <div className="mt-2 flex items-center justify-between border-t border-line pt-4 text-xs">
          <span className="flex items-center gap-1.5 text-muted">
            <Sparkles className="size-3.5 text-teal-600" /> {real ? tr("{n} waiting", { n: real.waiting }) : c.queue.footerLeft}
          </span>
          {real ? (
            <Link href="/reviewer" className="flex items-center gap-1 font-semibold text-coral-500 hover:underline">
              {tr("Open the queue")} <ArrowRight className="size-3.5" />
            </Link>
          ) : (
            <span className="flex items-center gap-1 font-semibold text-coral-500">
              {c.queue.footerRight} <ArrowRight className="size-3.5" />
            </span>
          )}
        </div>
      </div>

      <div className="float-slow absolute right-4 bottom-0 z-10 hidden rounded-2xl border border-line bg-white/95 px-4 py-3 shadow-[var(--shadow-pop)] backdrop-blur sm:block lg:-right-6">
        <p className="text-[11px] font-medium text-muted">{c.queue.status}</p>
        <p className="text-lg font-extrabold text-ink tabular-nums">
          {critical} {c.queue.critical}
        </p>
        <p className="flex items-center gap-1 text-[11px] font-semibold text-rout">
          <Activity className="size-3" /> {c.queue.flagged}
        </p>
      </div>
    </div>
  );
}

function SectionTitle({ eyebrow, title, body, light }: { eyebrow: string; title: [string, string]; body?: string; light?: boolean }) {
  return (
    <Reveal className="mx-auto max-w-4xl text-center">
      <p className="text-xs font-bold tracking-[0.18em] text-coral-500 uppercase">{eyebrow}</p>
      <h2 className={cx("mt-3 text-3xl leading-tight font-extrabold tracking-tight sm:text-4xl lg:text-5xl", light ? "text-white" : "text-ink")}>
        {title[0]} <br className="hidden sm:block" />
        <span className="text-gradient">{title[1]}</span>
      </h2>
      {body && <p className="mx-auto mt-4 max-w-2xl text-base leading-relaxed text-muted sm:text-lg">{body}</p>}
    </Reveal>
  );
}

const FEATURE_ICONS = [AudioLines, FileScan, ClipboardList, Languages, UserCheck, ShieldCheck];
const FACILITY_ICONS = [Hospital, Building2, Tent, Factory, GraduationCap, Briefcase];
const SCENARIO_ICONS = [ListOrdered, HardHat, Thermometer, Baby, HeartPulse, WifiOff, Send];
const SAFETY_ICONS = [Scale, ListOrdered, UserCheck, FileScan, History, Trash2];

function Process({ c }: { c: SiteCopy }) {
  const { ref, inView } = useInView<HTMLDivElement>(0.3);
  const icons = [Tablet, Cpu, Stethoscope];
  return (
    <div ref={ref} className="relative mt-14 grid gap-10 md:grid-cols-3 md:gap-8">
      <div className="absolute top-10 right-[16%] left-[16%] hidden h-0.5 overflow-hidden rounded-full bg-line md:block" aria-hidden>
        <div className={cx("h-full origin-left bg-gradient-to-r from-coral-300 via-coral-200 to-teal-300 transition-transform duration-[1600ms] ease-out", inView ? "scale-x-100" : "scale-x-0")} />
      </div>
      {c.how.steps.map((s, i) => {
        const Icon = icons[i];
        return (
          <Reveal key={s.title} delay={i * 180} className="relative text-center">
            <div
              className={cx(
                "relative mx-auto grid size-20 place-items-center rounded-full text-white shadow-[0_14px_30px_-10px_rgb(242_145_145/0.7)] ring-8 ring-white",
                i === 0 && "bg-gradient-to-br from-coral-300 to-coral-200",
                i === 1 && "bg-gradient-to-br from-teal-200 to-teal-100 text-teal-800",
                i === 2 && "bg-gradient-to-br from-coral-200 to-teal-200",
              )}
            >
              <Icon className="size-8" />
              <span className="absolute -top-1 -right-1 grid size-7 place-items-center rounded-full bg-ink text-xs font-bold text-white">{i + 1}</span>
            </div>
            <h3 className="mt-6 text-xl font-bold text-ink">{s.title}</h3>
            <p className="mx-auto mt-2 max-w-xs text-[15px] leading-relaxed text-muted">{s.body}</p>
          </Reveal>
        );
      })}
    </div>
  );
}

function Scenarios({ c }: { c: SiteCopy }) {
  const track = useRef<HTMLDivElement>(null);
  const [idx, setIdx] = useState(0);
  const n = c.scenarios.items.length;

  const scrollTo = (i: number) => {
    const el = track.current;
    if (!el) return;
    const card = el.children[Math.max(0, Math.min(n - 1, i))] as HTMLElement | undefined;
    if (card) el.scrollTo({ left: card.offsetLeft - el.offsetLeft, behavior: "smooth" });
  };

  useEffect(() => {
    const el = track.current;
    if (!el) return;
    const onScroll = () => {
      const first = el.children[0] as HTMLElement | undefined;
      if (!first) return;
      const w = first.offsetWidth + 20;
      setIdx(Math.round(el.scrollLeft / w));
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="mt-12">
      <div ref={track} className="no-scrollbar -mx-4 flex snap-x snap-mandatory gap-5 overflow-x-auto scroll-smooth px-4 pt-2 pb-6 sm:-mx-6 sm:px-6">
        {c.scenarios.items.map((s, i) => {
          const Icon = SCENARIO_ICONS[i];
          return (
            <article
              key={s.title}
              className="group w-[82%] shrink-0 snap-start rounded-3xl border border-line bg-white p-6 transition-all duration-300 hover:-translate-y-1.5 hover:border-teal-200 hover:shadow-[0_24px_50px_-24px_rgb(22_24_43/0.35)] sm:w-[46%] lg:w-[calc((100%-60px)/4)]"
            >
              <span className={cx("grid size-12 place-items-center rounded-2xl transition-transform group-hover:scale-110", i % 2 ? "bg-teal-50 text-teal-700" : "bg-coral-50 text-coral-500")}>
                <Icon className="size-6" />
              </span>
              <p className="mt-6 text-[11px] font-bold tracking-[0.16em] text-coral-500 uppercase">{s.tag}</p>
              <h3 className="mt-1.5 text-lg font-bold text-ink">{s.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{s.body}</p>
            </article>
          );
        })}
      </div>
      <div className="mt-2 flex items-center justify-center gap-4">
        <button onClick={() => scrollTo(idx - 1)} disabled={idx <= 0} className="grid size-11 place-items-center rounded-full border border-line bg-white text-ink transition-colors hover:border-coral-200 disabled:opacity-40" aria-label="Previous">
          <ChevronLeft className="size-5" />
        </button>
        <div className="flex gap-1.5">
          {c.scenarios.items.map((s, i) => (
            <button key={s.title} onClick={() => scrollTo(i)} aria-label={s.title} className={cx("h-2 rounded-full transition-all", i === idx ? "w-7 bg-coral-300" : "w-2 bg-line hover:bg-coral-100")} />
          ))}
        </div>
        <button onClick={() => scrollTo(idx + 1)} disabled={idx >= n - 1} className="grid size-11 place-items-center rounded-full border border-line bg-white text-ink transition-colors hover:border-coral-200 disabled:opacity-40" aria-label="Next">
          <ChevronRight className="size-5" />
        </button>
      </div>
    </div>
  );
}

export default function Landing() {
  const c = useSite();
  const { tr } = usePrefs();

  return (
    <div className="min-h-screen bg-[#fbfbfe]">
      <div className="relative overflow-hidden">
        {/* soft brand background */}
        <div className="pointer-events-none absolute inset-0 -z-0" aria-hidden>
          <div className="blob absolute -top-40 -right-32 size-[520px] rounded-full bg-coral-100/80 blur-3xl" />
          <div className="blob absolute top-40 -left-40 size-[460px] rounded-full bg-teal-100/70 blur-3xl [animation-delay:-6s]" />
          <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-b from-transparent to-[#fbfbfe]" />
        </div>

        <div className="relative z-10">
          <SiteHeader />

          {/* Hero */}
          <section className="mx-auto grid max-w-6xl items-center gap-14 px-4 pt-10 pb-20 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:gap-10 lg:pt-16 lg:pb-28">
            <div>
              <Reveal>
                <span className="inline-flex items-center gap-2 rounded-full border border-coral-200 bg-white/70 px-4 py-1.5 text-xs font-bold tracking-wider text-coral-500 uppercase backdrop-blur">
                  <span className="size-1.5 rounded-full bg-coral-300" />
                  {c.hero.badge}
                </span>
              </Reveal>
              <Reveal delay={80}>
                <h1 className="mt-6 text-[2.6rem] leading-[1.05] font-extrabold tracking-tight text-ink sm:text-6xl lg:text-[4.2rem]">
                  {c.hero.title[0]}
                  <br />
                  <span className="text-gradient">{c.hero.title[1]}</span>
                  <br />
                  {c.hero.title[2]}
                </h1>
              </Reveal>
              <Reveal delay={160}>
                <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted">{c.hero.body}</p>
              </Reveal>
              <Reveal delay={240} className="mt-8 flex flex-col gap-3 sm:flex-row">
                <Link href="/auth?mode=register" className="bg-brand-gradient group inline-flex h-14 items-center justify-center gap-2 rounded-full px-8 text-base font-semibold text-white shadow-[0_14px_30px_-10px_rgb(242_145_145/0.9)] transition-transform hover:-translate-y-0.5">
                  {c.hero.primary} <ArrowRight className="size-5 transition-transform group-hover:translate-x-1" />
                </Link>
                <a href="#how" className="inline-flex h-14 items-center justify-center rounded-full border-2 border-line bg-white/70 px-8 text-base font-semibold text-ink backdrop-blur transition-colors hover:border-coral-200 hover:bg-white">
                  {c.hero.secondary}
                </a>
              </Reveal>
              <Reveal delay={280}>
                <PatientEntry />
              </Reveal>
              <Reveal delay={320} className="mt-10 grid max-w-md grid-cols-3 gap-4 border-t border-line pt-7">
                {[
                  { n: 22, s: "" },
                  { n: 4, s: " min" },
                  { n: 100, s: "%" },
                ].map((x, i) => (
                  <div key={i}>
                    <p className="text-2xl font-extrabold text-ink sm:text-3xl">
                      <CountUp to={x.n} suffix={x.s} />
                    </p>
                    <p className="mt-1 text-xs text-muted sm:text-sm">{c.hero.stats[i]}</p>
                  </div>
                ))}
              </Reveal>
            </div>
            <Reveal delay={200}>
              <LiveQueue c={c} />
            </Reveal>
          </section>
        </div>
      </div>

      {/* Facility types */}
      <section className="border-y border-line bg-white py-6" aria-label="Facility types">
        <div className="marquee overflow-hidden [mask-image:linear-gradient(90deg,transparent,black_8%,black_92%,transparent)]">
          <div className="marquee-track flex w-max gap-4">
            {[...c.facilities, ...c.facilities].map((f, i) => {
              const Icon = FACILITY_ICONS[i % FACILITY_ICONS.length];
              return (
                <span key={i} className="flex shrink-0 items-center gap-3 rounded-full border border-line bg-canvas/60 py-2 pr-5 pl-2 text-sm font-semibold text-ink-2">
                  <span className={cx("grid size-9 place-items-center rounded-full", i % 2 ? "bg-teal-100 text-teal-700" : "bg-coral-100 text-coral-600")}>
                    <Icon className="size-4.5" />
                  </span>
                  {f}
                </span>
              );
            })}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" className="scroll-mt-20 py-20 sm:py-28">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <SectionTitle eyebrow={c.features.eyebrow} title={c.features.title} body={c.features.body} />
          <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
            {c.features.items.map((f, i) => {
              const Icon = FEATURE_ICONS[i];
              return (
                <Reveal key={f.title} delay={(i % 3) * 100}>
                  <article className="group relative h-full overflow-hidden rounded-3xl border border-line bg-white p-7 transition-all duration-300 hover:-translate-y-1.5 hover:shadow-[0_28px_60px_-28px_rgb(22_24_43/0.35)]">
                    <div className="absolute inset-0 bg-gradient-to-br from-coral-50 via-transparent to-teal-50 opacity-0 transition-opacity duration-300 group-hover:opacity-100" aria-hidden />
                    <div className="relative">
                      <span className={cx("grid size-14 place-items-center rounded-2xl transition-transform duration-300 group-hover:scale-110 group-hover:-rotate-3", i % 2 ? "bg-teal-100 text-teal-700" : "bg-coral-100 text-coral-600")}>
                        <Icon className="size-7" />
                      </span>
                      <h3 className="mt-6 text-xl font-bold text-ink">{f.title}</h3>
                      <p className="mt-2.5 leading-relaxed text-muted">{f.body}</p>
                    </div>
                  </article>
                </Reveal>
              );
            })}
          </div>
        </div>
      </section>

      {/* How it works */}
      <section id="how" className="scroll-mt-20 bg-gradient-to-b from-white to-teal-50/70 py-20 sm:py-28">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <SectionTitle eyebrow={c.how.eyebrow} title={c.how.title} body={c.how.body} />
          <Process c={c} />
        </div>
      </section>

      {/* Scenarios */}
      <section id="scenarios" className="scroll-mt-20 py-20 sm:py-28">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <SectionTitle eyebrow={c.scenarios.eyebrow} title={c.scenarios.title} />
          <Scenarios c={c} />
        </div>
      </section>

      {/* Safety */}
      <section id="safety" className="scroll-mt-20 bg-white py-20 sm:py-28">
        <div className="mx-auto max-w-6xl px-4 sm:px-6">
          <SectionTitle eyebrow={c.safety.eyebrow} title={c.safety.title} />
          <div className="mt-14 grid gap-x-10 gap-y-8 sm:grid-cols-2 lg:grid-cols-3">
            {c.safety.items.map((s, i) => {
              const Icon = SAFETY_ICONS[i];
              return (
                <Reveal key={s.title} delay={(i % 3) * 90} className="flex gap-4">
                  <span className={cx("grid size-11 shrink-0 place-items-center rounded-xl", i % 2 ? "bg-teal-50 text-teal-700" : "bg-coral-50 text-coral-500")}>
                    <Icon className="size-5" />
                  </span>
                  <div>
                    <h3 className="font-bold text-ink">{s.title}</h3>
                    <p className="mt-1 text-[15px] leading-relaxed text-muted">{s.body}</p>
                  </div>
                </Reveal>
              );
            })}
          </div>
          <p className="mt-10 text-center">
            <Link href="/about/models" className="font-semibold text-teal-700 underline-offset-4 hover:underline">{tr("About the models: what each one does, and what it never decides")} →</Link>
          </p>
        </div>
      </section>

      <section className="border-t-4 border-amber-400 bg-gradient-to-r from-amber-50 via-coral-50 to-coral-50">
        <Reveal className="mx-auto flex max-w-6xl gap-4 px-4 py-10 sm:px-6">
          <AlertTriangle className="mt-1 size-7 shrink-0 text-amber-500" />
          <div>
            <h3 className="text-lg font-bold text-amber-800">{c.safety.noticeTitle}</h3>
            <p className="mt-2 leading-relaxed text-amber-900/90">
              <strong>{c.safety.noticeLead}</strong> {c.safety.notice}
            </p>
          </div>
        </Reveal>
      </section>

      {/* Live status */}
      <section id="status" className="scroll-mt-20 bg-gradient-to-b from-white to-teal-50/60 py-20 sm:py-24">
        <div className="mx-auto max-w-3xl px-4 sm:px-6">
          <SectionTitle eyebrow={c.status.eyebrow} title={c.status.title} body={c.status.body} />
          <Reveal className="mt-10">
            <StatusPanel />
          </Reveal>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20">
        <Reveal className="mx-auto max-w-6xl px-4 sm:px-6">
          <div className="relative overflow-hidden rounded-[32px] bg-gradient-to-br from-coral-300 via-coral-200 to-teal-200 px-6 py-14 text-center sm:px-12">
            <div className="blob absolute -top-20 -left-10 size-72 rounded-full bg-white/25 blur-2xl" aria-hidden />
            <div className="blob absolute -right-10 -bottom-24 size-80 rounded-full bg-teal-100/50 blur-2xl [animation-delay:-8s]" aria-hidden />
            <div className="relative">
              <h2 className="text-3xl font-extrabold tracking-tight text-ink sm:text-4xl">{c.cta.title}</h2>
              <p className="mx-auto mt-3 max-w-xl text-lg text-ink/75">{c.cta.body}</p>
              <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
                <Link href="/auth?mode=register" className="inline-flex h-13 items-center justify-center gap-2 rounded-full bg-ink px-7 font-semibold text-white transition-transform hover:-translate-y-0.5">
                  {c.cta.primary} <ArrowRight className="size-4" />
                </Link>
                <Link href="#patient" className="inline-flex h-13 items-center justify-center gap-2 rounded-full bg-white/80 px-7 font-semibold text-ink backdrop-blur transition-colors hover:bg-white">
                  <Tablet className="size-4" /> {c.cta.secondary}
                </Link>
              </div>
            </div>
          </div>
        </Reveal>
      </section>

      <SiteFooter />
    </div>
  );
}
