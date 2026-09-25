"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { Accessibility, Check, ChevronDown, Globe, Plus, Search, ShieldAlert, Type, Volume2, Shapes } from "lucide-react";
import { usePrefs } from "@/components/providers";
import { LANGUAGES, langByCode } from "@/lib/i18n/languages";
import { FULLY_TRANSLATED } from "@/lib/i18n/dict";
import { Modal, Toggle, cx } from "@/components/ui";

export function Logo({ className, light }: { className?: string; light?: boolean }) {
  return (
    <Link href="/" className={cx("group flex items-center gap-2.5 font-extrabold tracking-tight", className)} aria-label="Jeevia home">
      <span className="grid size-9 place-items-center rounded-xl bg-gradient-to-br from-coral-300 to-coral-200 text-white shadow-[0_6px_16px_-4px_rgb(242_145_145/0.7)] transition-transform group-hover:scale-105">
        <span className="grid size-5 place-items-center rounded-full border-2 border-white">
          <Plus className="size-3" strokeWidth={3.5} aria-hidden />
        </span>
      </span>
      <span className={cx("text-xl whitespace-nowrap", light ? "text-white" : "text-ink")}>
        Jee<span className="text-coral-300">via</span>
      </span>
    </Link>
  );
}

/** G6 — non-diagnostic disclaimer, visible on every screen. */
export function DisclaimerBar() {
  const { t } = usePrefs();
  return (
    <div className="no-print flex items-center justify-center gap-2 bg-ink px-4 py-1.5 text-center text-[11px] font-medium text-white/85 sm:text-xs" role="note">
      <ShieldAlert className="size-3.5 shrink-0 text-coral-300" aria-hidden />
      <span>{t("disclaimer.short")}</span>
    </div>
  );
}

/** Language dropdown: the fully translated interfaces first, then every scheduled language for voice/text input. */
export function LanguageButton({ compact, className, align = "right" }: { compact?: boolean; className?: string; align?: "left" | "right" }) {
  const { lang, set } = usePrefs();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef<HTMLDivElement>(null);
  const cur = langByCode(lang);

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

  const { full, voice } = useMemo(() => {
    const s = q.trim().toLowerCase();
    const list = LANGUAGES.filter((l) => !s || l.name.toLowerCase().includes(s) || l.native.includes(q.trim()));
    return { full: list.filter((l) => FULLY_TRANSLATED.includes(l.code)), voice: list.filter((l) => !FULLY_TRANSLATED.includes(l.code)) };
  }, [q]);

  const pick = (code: string) => {
    set({ lang: code });
    setOpen(false);
    setQ("");
  };

  const renderItem = (code: string) => {
    const l = langByCode(code);
    const on = l.code === lang;
    return (
      <li key={code}>
        <button
          type="button"
          role="option"
          aria-selected={on}
          onClick={() => pick(l.code)}
          className={cx("flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left transition-colors", on ? "bg-coral-50" : "hover:bg-canvas")}
        >
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold text-ink">{l.native}</span>
            <span className="block text-xs text-muted">{l.name}</span>
          </span>
          {on && <Check className="size-4 shrink-0 text-coral-500" />}
        </button>
      </li>
    );
  };

  return (
    <div ref={ref} className={cx("relative", className)}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Language: ${cur.name}`}
        className={cx(
          "inline-flex h-10 items-center gap-1.5 rounded-full border bg-white/80 px-3.5 text-sm font-medium whitespace-nowrap text-ink-2 backdrop-blur transition-colors hover:border-coral-200 hover:bg-white",
          open ? "border-coral-300" : "border-line",
        )}
      >
        <Globe className="size-4 text-teal-600" />
        {!compact && <span>{cur.native}</span>}
        <ChevronDown className={cx("size-3.5 text-muted transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <div
          className={cx(
            "fade-up absolute top-12 z-50 w-[min(18rem,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-line bg-white shadow-[var(--shadow-pop)]",
            align === "right" ? "right-0" : "left-0",
          )}
        >
          <div className="border-b border-line p-2">
            <div className="relative">
              <Search className="absolute top-2.5 left-2.5 size-4 text-subtle" />
              <input
                autoFocus
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search language"
                className="h-9 w-full rounded-lg bg-canvas pr-3 pl-8 text-sm text-ink placeholder:text-subtle focus:outline-none"
                aria-label="Search language"
              />
            </div>
          </div>
          <div className="max-h-[min(24rem,60vh)] overflow-y-auto p-1.5" role="listbox">
            {full.length > 0 && (
              <>
                <p className="px-2.5 pt-1.5 pb-1 text-[11px] font-semibold tracking-wider text-coral-500 uppercase">Full interface</p>
                <ul>
                  {full.map((l) => renderItem(l.code))}
                </ul>
              </>
            )}
            {voice.length > 0 && (
              <>
                <p className="mt-1 border-t border-line px-2.5 pt-2.5 pb-1 text-[11px] font-semibold tracking-wider text-teal-700 uppercase">Voice &amp; text input</p>
                <p className="px-2.5 pb-1.5 text-[11px] text-muted">Patients speak in these languages; screens show English.</p>
                <ul>
                  {voice.map((l) => renderItem(l.code))}
                </ul>
              </>
            )}
            {!full.length && !voice.length && <p className="px-3 py-6 text-center text-sm text-muted">No language matches “{q}”</p>}
          </div>
        </div>
      )}
    </div>
  );
}

export function A11yButton({ className }: { className?: string }) {
  const p = usePrefs();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)} className={cx("inline-flex size-10 items-center justify-center rounded-full border border-line bg-white/80 text-ink-2 hover:border-coral-200 hover:bg-white", className)} aria-label="Accessibility settings">
        <Accessibility className="size-4.5" />
      </button>
      <Modal open={open} onClose={() => setOpen(false)} title="Accessibility" subtitle="Settings are remembered on this device." size="sm">
        <div className="space-y-5">
          <div className="flex items-start gap-3">
            <Type className="mt-0.5 size-5 text-muted" />
            <div className="flex-1">
              <Toggle checked={p.largeText} onChange={(v) => p.set({ largeText: v })} label="Large text" description="Increases all text and touch targets." />
            </div>
          </div>
          <div className="flex items-start gap-3">
            <Shapes className="mt-0.5 size-5 text-muted" />
            <div className="flex-1">
              <Toggle checked={p.iconMode} onChange={(v) => p.set({ iconMode: v })} label="Icon mode" description="Big pictures, fewer words — for low-literacy users." />
            </div>
          </div>
          <div className="flex items-start gap-3">
            <Volume2 className="mt-0.5 size-5 text-muted" />
            <div className="flex-1">
              <Toggle checked={p.readAloud} onChange={(v) => p.set({ readAloud: v })} label="Read questions aloud" description="Kiosk speaks each question in the chosen language." />
            </div>
          </div>
        </div>
      </Modal>
    </>
  );
}
