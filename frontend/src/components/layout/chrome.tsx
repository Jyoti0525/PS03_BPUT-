"use client";

import { useState } from "react";
import Link from "next/link";
import { Accessibility, Check, Globe, ShieldAlert, Type, Volume2, Shapes } from "lucide-react";
import { usePrefs } from "@/components/providers";
import { LANGUAGES, langByCode } from "@/lib/i18n/languages";
import { FULLY_TRANSLATED } from "@/lib/i18n/dict";
import { API_MODE } from "@/lib/api";
import { Modal, Toggle, cx } from "@/components/ui";

export function Logo({ className, light }: { className?: string; light?: boolean }) {
  return (
    <Link href="/" className={cx("flex items-center gap-2 font-bold tracking-tight", light ? "text-white" : "text-ink", className)}>
      <span className="grid size-8 place-items-center rounded-xl bg-gradient-to-br from-coral-300 to-teal-300 text-white shadow-sm">
        <svg viewBox="0 0 24 24" className="size-5" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
          <path d="M3 12h4l2-5 4 10 2-5h6" />
        </svg>
      </span>
      <span className="text-lg whitespace-nowrap">
        Jeevia <span className={cx("hidden font-medium sm:inline", light ? "text-white/60" : "text-subtle")}>जीविया</span>
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
      {API_MODE === "mock" && <span className="hidden rounded bg-white/10 px-1.5 py-px text-[10px] tracking-wide text-teal-200 uppercase sm:inline">Demo · mock API</span>}
    </div>
  );
}

export function LanguageButton({ compact, className }: { compact?: boolean; className?: string }) {
  const { lang, set, t } = usePrefs();
  const [open, setOpen] = useState(false);
  const cur = langByCode(lang);
  return (
    <div className={className}>
      <button onClick={() => setOpen(true)} className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-line bg-white px-2.5 text-sm font-medium whitespace-nowrap text-ink-2 hover:bg-canvas" aria-label={`${t("common.language")}: ${cur.name}`}>
        <Globe className="size-4 text-muted" />
        {!compact && <span>{cur.native}</span>}
      </button>
      <Modal open={open} onClose={() => setOpen(false)} title={t("common.language")} subtitle="22 scheduled Indian languages + English. Speech in any of these is captured and translated for the reviewer." size="lg">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
          {LANGUAGES.map((l) => (
            <button
              key={l.code}
              onClick={() => {
                set({ lang: l.code });
                setOpen(false);
              }}
              className={cx("flex items-center justify-between rounded-xl border px-3 py-2.5 text-left transition-colors", l.code === lang ? "border-teal-600 bg-teal-50" : "border-line hover:bg-canvas")}
            >
              <span>
                <span className="block text-base font-semibold text-ink">{l.native}</span>
                <span className="block text-xs text-muted">
                  {l.name}
                  {!FULLY_TRANSLATED.includes(l.code) && " · voice + UI in English"}
                </span>
              </span>
              {l.code === lang && <Check className="size-4 text-teal-700" />}
            </button>
          ))}
        </div>
      </Modal>
    </div>
  );
}

export function A11yButton({ className }: { className?: string }) {
  const p = usePrefs();
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)} className={cx("inline-flex size-9 items-center justify-center rounded-lg border border-line bg-white text-ink-2 hover:bg-canvas", className)} aria-label="Accessibility settings">
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
