"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, AlertTriangle, Info } from "lucide-react";
import clsx from "clsx";

type Kind = "success" | "error" | "info";
interface T {
  id: number;
  kind: Kind;
  msg: string;
}

let n = 0;
const listeners = new Set<(t: T) => void>();

export function toast(msg: string, kind: Kind = "success") {
  const t = { id: ++n, kind, msg };
  listeners.forEach((l) => l(t));
}

export function ToastHost() {
  const [items, setItems] = useState<T[]>([]);
  useEffect(() => {
    const l = (t: T) => {
      setItems((cur) => [...cur, t]);
      setTimeout(() => setItems((cur) => cur.filter((x) => x.id !== t.id)), 3800);
    };
    listeners.add(l);
    return () => {
      listeners.delete(l);
    };
  }, []);
  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-4 z-[60] flex flex-col items-center gap-2 px-4" aria-live="polite">
      {items.map((t) => (
        <div
          key={t.id}
          role="status"
          className={clsx(
            "fade-up pointer-events-auto flex max-w-md items-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-medium shadow-[var(--shadow-pop)]",
            t.kind === "success" && "border-teal-200 bg-white text-teal-800",
            t.kind === "error" && "border-crit-line bg-crit-bg text-crit",
            t.kind === "info" && "border-line bg-ink text-white",
          )}
        >
          {t.kind === "success" ? <CheckCircle2 className="size-4 shrink-0" /> : t.kind === "error" ? <AlertTriangle className="size-4 shrink-0" /> : <Info className="size-4 shrink-0" />}
          {t.msg}
        </div>
      ))}
    </div>
  );
}
