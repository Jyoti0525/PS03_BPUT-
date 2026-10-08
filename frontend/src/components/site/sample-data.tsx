"use client";

import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { usePrefs } from "@/components/providers";
import { cx } from "@/components/ui";
import { API_MODE } from "@/lib/api";
import { API_BASE } from "@/lib/api/live";

type State = { available: boolean; on: boolean };

/**
 * Navbar switch, demo laptop only (server JEEVIA_DEMO_CONTROLS): sample patients on (reloaded, timed from now) or off
 * (empty queues; facilities and staff accounts stay). Hidden everywhere else.
 */
export function SampleDataSwitch({ className }: { className?: string }) {
  const { tr } = usePrefs();
  const [s, setS] = useState<State | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (API_MODE !== "live") return;
    fetch(`${API_BASE}/demo/samples`)
      .then((r) => (r.ok ? r.json() : null))
      .then((j: State | null) => j && setS(j))
      .catch(() => {});
  }, []);

  if (!s?.available) return null;

  const set = async (on: boolean) => {
    if (!window.confirm(tr("This rebuilds the demo database: everything entered on this server is cleared. Continue?"))) return;
    setBusy(true);
    try {
      const r = await fetch(`${API_BASE}/demo/samples`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ on }) });
      if (!r.ok) throw new Error();
      setS(await r.json());
    } catch {
      window.alert(tr("Could not change the sample data. Is the server running?"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={cx("h-10 items-center gap-2 rounded-full border border-line bg-white pr-1.5 pl-3", busy && "opacity-60", className)}>
      <span className="text-xs font-semibold whitespace-nowrap text-ink">{tr("Sample patients")}</span>
      <button
        type="button"
        role="switch"
        aria-checked={s.on}
        aria-label={tr("Sample patients")}
        title={tr(s.on ? "Queues filled with sample patients, timed from when they were loaded." : "Queues are empty: staff accounts stay, enter patients live.")}
        disabled={busy}
        onClick={() => void set(!s.on)}
        className={cx("relative h-6 w-11 shrink-0 rounded-full transition-colors", s.on ? "bg-teal-600" : "bg-line")}
      >
        <span className={cx("absolute top-0.5 left-0.5 size-5 rounded-full bg-white shadow transition-transform", s.on && "translate-x-5")} />
      </button>
      {s.on && (
        <button
          type="button"
          disabled={busy}
          onClick={() => void set(true)}
          title={tr("Reload with fresh times")}
          aria-label={tr("Reload with fresh times")}
          className="inline-flex size-7 items-center justify-center rounded-full text-muted hover:bg-canvas hover:text-ink"
        >
          <RefreshCw className={cx("size-4", busy && "animate-spin")} />
        </button>
      )}
    </div>
  );
}
