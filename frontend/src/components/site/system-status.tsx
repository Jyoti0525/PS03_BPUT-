"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Globe, Server, Database, MessageSquareText, FileArchive, RefreshCw, Power, Zap, Loader2 } from "lucide-react";
import { checkStatus, restartAvailable, restartServer, useSystemStatus, wakeServer, type ServerState } from "@/lib/status";
import { useSite } from "@/lib/i18n/site";
import { useSession } from "@/components/providers";
import { useNow } from "@/lib/hooks";
import { toast } from "@/components/ui/toast";
import { cx } from "@/components/ui";

const DOT: Record<ServerState, string> = {
  online: "bg-rout",
  degraded: "bg-amber-400",
  offline: "bg-crit",
  waking: "bg-amber-400",
  checking: "bg-subtle",
  demo: "bg-teal-600",
};

function fmtUptime(s: number) {
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
  return `${Math.floor(s / 86400)}d ${Math.floor((s % 86400) / 3600)}h`;
}

function headline(state: ServerState, c: ReturnType<typeof useSite>["status"]) {
  return { online: c.allOk, degraded: c.degraded, offline: c.offline, waking: c.waking, checking: c.checking, demo: c.demo }[state];
}

/** Compact indicator for the site header. */
export function StatusPill({ className }: { className?: string }) {
  const s = useSystemStatus();
  const c = useSite().status;
  return (
    <Link href="/#status" className={cx("inline-flex h-10 items-center gap-2 rounded-full border border-line bg-white/80 px-3 text-xs font-semibold whitespace-nowrap text-ink-2 backdrop-blur hover:border-coral-200", className)} title={headline(s.state, c)}>
      <span className="relative flex size-2.5">
        {(s.state === "online" || s.state === "waking") && <span className={cx("absolute inline-flex size-full animate-ping rounded-full opacity-60", DOT[s.state])} />}
        <span className={cx("relative inline-flex size-2.5 rounded-full", DOT[s.state])} />
      </span>
      <span className="hidden xl:inline">{s.state === "online" && s.latencyMs != null ? `${c.online} · ${s.latencyMs} ms` : headline(s.state, c)}</span>
    </Link>
  );
}

/** Full status panel with wake / restart controls. */
export function StatusPanel() {
  const s = useSystemStatus();
  const c = useSite().status;
  const { user } = useSession();
  const now = useNow(1000);
  const [canRestart, setCanRestart] = useState(false);
  const [restarting, setRestarting] = useState(false);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    if (user?.role !== "supervisor") return;
    let live = true;
    restartAvailable().then((v) => live && setCanRestart(v));
    return () => {
      live = false;
    };
  }, [user?.role]);

  const h = s.health;
  const up = s.state === "online" || s.state === "degraded";
  const rows = [
    { icon: <Globe className="size-5" />, label: c.website, ok: true, value: c.online, detail: "Vercel" },
    { icon: <Server className="size-5" />, label: c.api, ok: up, value: up ? c.online : s.state === "waking" ? c.waking : s.state === "demo" ? "—" : c.asleep, detail: h ? `${s.latencyMs} ms · ${c.uptime} ${fmtUptime(h.uptime_s)} · v${h.version}` : "Render" },
    { icon: <Database className="size-5" />, label: c.database, ok: !!h?.db.ok, value: h ? (h.db.ok ? c.online : "Error") : "—", detail: h ? `${h.db.engine} · ${h.db.latency_ms} ms` : "PostgreSQL" },
    { icon: <MessageSquareText className="size-5" />, label: c.sms, ok: !!h?.otp.configured, value: h ? (h.otp.configured ? c.ready : c.notReady) : "—", detail: h ? h.otp.provider : "Twilio Verify" },
    { icon: <FileArchive className="size-5" />, label: c.storage, ok: !!h?.storage.ok && !!h?.storage.persistent, value: h ? (h.storage.ok ? c.ready : "Error") : "—", detail: h ? h.storage.backend : "Cloudinary" },
  ];

  return (
    <div className="overflow-hidden rounded-3xl border border-line bg-white shadow-[var(--shadow-card)]">
      <div className={cx("flex flex-wrap items-center gap-3 px-5 py-4 sm:px-6", s.state === "online" ? "bg-rout-bg" : s.state === "offline" ? "bg-crit-bg" : s.state === "demo" ? "bg-teal-50" : "bg-semi-bg")}>
        <span className="relative flex size-3">
          {(s.state === "online" || s.state === "waking") && <span className={cx("absolute inline-flex size-full animate-ping rounded-full opacity-60", DOT[s.state])} />}
          <span className={cx("relative inline-flex size-3 rounded-full", DOT[s.state])} />
        </span>
        <p className="flex-1 font-bold text-ink">{headline(s.state, c)}</p>
        {s.checkedAt && (
          <span className="text-xs text-muted tabular-nums">
            {c.checked} {Math.max(0, Math.round((now - s.checkedAt) / 1000))}s
          </span>
        )}
        <div className="flex flex-wrap gap-2">
          {s.state !== "demo" && (
            <button
              onClick={async () => {
                setChecking(true);
                await checkStatus();
                setChecking(false);
              }}
              className="inline-flex h-9 items-center gap-1.5 rounded-full border border-line bg-white px-3.5 text-sm font-semibold text-ink hover:border-coral-200"
            >
              <RefreshCw className={cx("size-4", checking && "animate-spin")} /> {c.checkNow}
            </button>
          )}
          {(s.state === "offline" || s.state === "waking") && (
            <button onClick={wakeServer} disabled={s.state === "waking"} className="bg-brand-gradient inline-flex h-9 items-center gap-1.5 rounded-full px-4 text-sm font-semibold text-white disabled:opacity-80">
              {s.state === "waking" ? <Loader2 className="size-4 animate-spin" /> : <Zap className="size-4" />} {c.wake}
            </button>
          )}
          {canRestart && s.state !== "demo" && (
            <button
              disabled={restarting}
              onClick={async () => {
                if (!confirm("Restart the API server? Anyone using Jeevia right now will wait about a minute.")) return;
                setRestarting(true);
                const r = await restartServer();
                toast(r.message, r.ok ? "info" : "error");
                setRestarting(false);
                if (r.ok) setTimeout(wakeServer, 8000);
              }}
              className="inline-flex h-9 items-center gap-1.5 rounded-full border border-crit-line bg-white px-3.5 text-sm font-semibold text-crit hover:bg-crit-bg"
            >
              <Power className="size-4" /> {c.restart}
            </button>
          )}
        </div>
      </div>
      {s.state === "waking" && (
        <div className="h-1 bg-semi-bg">
          <div className="h-full bg-amber-400 transition-[width] duration-1000" style={{ width: `${Math.round(s.wakeProgress * 100)}%` }} />
        </div>
      )}
      <ul className="divide-y divide-line">
        {rows.map((r) => (
          <li key={r.label} className="flex items-center gap-4 px-5 py-3.5 sm:px-6">
            <span className={cx("grid size-10 shrink-0 place-items-center rounded-xl", r.ok ? "bg-teal-50 text-teal-700" : "bg-canvas text-subtle")}>{r.icon}</span>
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-ink">{r.label}</p>
              <p className="truncate text-xs text-muted">{r.detail}</p>
            </div>
            <span className={cx("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-bold", r.ok ? "bg-rout-bg text-rout" : s.state === "checking" ? "bg-canvas text-muted" : "bg-semi-bg text-semi")}>
              <span className={cx("size-1.5 rounded-full", r.ok ? "bg-rout" : "bg-amber-500")} />
              {r.value}
            </span>
          </li>
        ))}
      </ul>
      {(s.state === "offline" || s.state === "waking") && <p className="border-t border-line px-6 py-3 text-xs text-muted">{c.sleepHint}</p>}
    </div>
  );
}
