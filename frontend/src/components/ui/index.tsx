"use client";

import clsx from "clsx";
import { Loader2, X } from "lucide-react";
import { usePrefs } from "@/components/providers";
import { forwardRef, useEffect, useRef, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes, type TextareaHTMLAttributes } from "react";

export const cx = clsx;

/** Shared components translate the plain-string text they are given, so every screen follows the chosen language. */
function useT() {
  const { tr } = usePrefs();
  return (n: ReactNode): ReactNode => (typeof n === "string" ? tr(n) : n);
}

/* ── Button ─────────────────────────────────────────────── */

type Variant = "primary" | "secondary" | "ghost" | "danger" | "teal" | "outline";
type Size = "sm" | "md" | "lg" | "xl";

const variants: Record<Variant, string> = {
  primary: "bg-ink text-white hover:bg-ink-2 disabled:bg-subtle",
  teal: "bg-teal-700 text-white hover:bg-teal-800 disabled:bg-subtle",
  secondary: "bg-surface text-ink border border-line hover:bg-canvas",
  outline: "bg-transparent text-ink border border-ink/20 hover:border-ink/40 hover:bg-white",
  ghost: "bg-transparent text-muted hover:bg-ink/5 hover:text-ink",
  danger: "bg-crit text-white hover:bg-red-700 disabled:bg-subtle",
};
const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-sm gap-1.5 rounded-lg",
  md: "h-10 px-4 text-sm gap-2 rounded-xl",
  lg: "h-12 px-5 text-base gap-2 rounded-xl",
  xl: "min-h-16 px-6 text-lg gap-3 rounded-2xl",
};

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { variant = "primary", size = "md", loading, icon, className, children, disabled, ...rest },
  ref,
) {
  return (
    <button
      ref={ref}
      className={cx(
        "inline-flex items-center justify-center font-semibold whitespace-nowrap transition-colors select-none disabled:cursor-not-allowed disabled:opacity-70",
        variants[variant],
        sizes[size],
        className,
      )}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? <Loader2 className="size-4 animate-spin" aria-hidden /> : icon}
      {children}
    </button>
  );
});

/* ── Card ───────────────────────────────────────────────── */

export function Card({ className, children, ...rest }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cx("rounded-[var(--radius-card)] border border-line bg-surface shadow-[var(--shadow-card)]", className)} {...rest}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action, icon }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode; icon?: ReactNode }) {
  const T = useT();
  return (
    <div className="flex items-start justify-between gap-3 border-b border-line px-4 py-3">
      <div className="flex min-w-0 items-start gap-2.5">
        {icon && <span className="mt-0.5 text-muted">{icon}</span>}
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-ink">{T(title)}</h3>
          {subtitle && <p className="text-xs text-muted">{T(subtitle)}</p>}
        </div>
      </div>
      {action}
    </div>
  );
}

/* ── Badge ──────────────────────────────────────────────── */

type Tone = "neutral" | "crit" | "semi" | "rout" | "teal" | "coral" | "info";
const tones: Record<Tone, string> = {
  neutral: "bg-canvas text-muted border-line",
  crit: "bg-crit-bg text-crit border-crit-line",
  semi: "bg-semi-bg text-semi border-semi-line",
  rout: "bg-rout-bg text-rout border-rout-line",
  teal: "bg-teal-50 text-teal-700 border-teal-200",
  coral: "bg-coral-50 text-coral-700 border-coral-200",
  info: "bg-blue-50 text-blue-700 border-blue-200",
};

export function Badge({ tone = "neutral", className, children }: { tone?: Tone; className?: string; children: ReactNode }) {
  const T = useT();
  return <span className={cx("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium whitespace-nowrap", tones[tone], className)}>{T(children)}</span>;
}

/* ── Form fields ───────────────────────────────────────── */

export function Label({ children, htmlFor, hint }: { children: ReactNode; htmlFor?: string; hint?: ReactNode }) {
  const T = useT();
  return (
    <label htmlFor={htmlFor} className="mb-1.5 block text-sm font-medium text-ink-2">
      {T(children)}
      {hint && <span className="ml-1 font-normal text-subtle">{T(hint)}</span>}
    </label>
  );
}

const fieldCls = "w-full rounded-xl border border-line bg-white px-3.5 text-ink placeholder:text-subtle focus:border-teal-600 focus:ring-4 focus:ring-teal-100 focus:outline-none disabled:bg-canvas";

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...rest }, ref) {
  return <input ref={ref} className={cx(fieldCls, "h-11", className)} {...rest} />;
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea({ className, ...rest }, ref) {
  return <textarea ref={ref} className={cx(fieldCls, "py-2.5", className)} {...rest} />;
});

export function Select({ className, children, ...rest }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cx(fieldCls, "h-11 pr-8", className)} {...rest}>
      {children}
    </select>
  );
}

export function FieldError({ children }: { children?: ReactNode }) {
  if (!children) return null;
  return (
    <p role="alert" className="mt-1.5 text-sm font-medium text-crit">
      {children}
    </p>
  );
}

export function Toggle({ checked, onChange, label, description, disabled }: { checked: boolean; onChange: (v: boolean) => void; label: ReactNode; description?: ReactNode; disabled?: boolean }) {
  const T = useT();
  return (
    <label className={cx("flex cursor-pointer items-center justify-between gap-4", disabled && "cursor-not-allowed opacity-60")}>
      <span className="min-w-0">
        <span className="block text-sm font-medium text-ink">{T(label)}</span>
        {description && <span className="block text-xs text-muted">{T(description)}</span>}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={cx("relative inline-flex h-6 w-11 shrink-0 rounded-full transition-colors", checked ? "bg-teal-600" : "bg-line")}
      >
        <span className={cx("absolute top-0.5 size-5 rounded-full bg-white shadow transition-transform", checked ? "translate-x-5.5" : "translate-x-0.5")} />
      </button>
    </label>
  );
}

/* ── Modal ──────────────────────────────────────────────── */

export function Modal({
  open,
  onClose,
  title,
  subtitle,
  children,
  footer,
  size = "md",
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
}) {
  const T = useT();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    ref.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);
  if (!open) return null;
  const w = { sm: "max-w-md", md: "max-w-lg", lg: "max-w-2xl", xl: "max-w-4xl" }[size];
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink/40 p-0 backdrop-blur-[2px] sm:items-center sm:p-4" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} tabIndex={-1} role="dialog" aria-modal="true" className={cx("fade-up flex max-h-[92vh] w-full flex-col rounded-t-2xl bg-surface shadow-[var(--shadow-pop)] outline-none sm:rounded-2xl", w)}>
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div>
            <h2 className="text-lg font-semibold text-ink">{T(title)}</h2>
            {subtitle && <p className="mt-0.5 text-sm text-muted">{T(subtitle)}</p>}
          </div>
          <button onClick={onClose} className="rounded-lg p-1.5 text-muted hover:bg-canvas hover:text-ink" aria-label="Close">
            <X className="size-5" />
          </button>
        </div>
        <div className="overflow-y-auto px-5 py-4">{children}</div>
        {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
      </div>
    </div>
  );
}

/* ── Misc ───────────────────────────────────────────────── */

export function Spinner({ label = "Loading…" }: { label?: string }) {
  const T = useT();
  return (
    <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted" role="status">
      <Loader2 className="size-4 animate-spin" /> {T(label)}
    </div>
  );
}

export function Empty({ icon, title, body, action }: { icon?: ReactNode; title: string; body?: ReactNode; action?: ReactNode }) {
  const T = useT();
  return (
    <div className="flex flex-col items-center justify-center px-6 py-12 text-center">
      {icon && <div className="mb-3 rounded-2xl bg-canvas p-3 text-subtle">{icon}</div>}
      <p className="font-semibold text-ink">{T(title)}</p>
      {body && <p className="mt-1 max-w-sm text-sm text-muted">{T(body)}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorNote({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const T = useT();
  const msg = error instanceof Error ? error.message : String(error);
  return (
    <div role="alert" className="flex items-center justify-between gap-3 rounded-xl border border-crit-line bg-crit-bg px-4 py-3 text-sm text-crit">
      <span>{T(msg)}</span>
      {onRetry && (
        <Button size="sm" variant="secondary" onClick={onRetry}>
          {T("Retry")}
        </Button>
      )}
    </div>
  );
}

export function Segmented<T extends string>({ value, onChange, options, className }: { value: T; onChange: (v: T) => void; options: { value: T; label: ReactNode; count?: number }[]; className?: string }) {
  const T = useT();
  return (
    <div role="tablist" className={cx("inline-flex flex-wrap gap-1 rounded-xl bg-canvas p-1", className)}>
      {options.map((o) => (
        <button
          key={o.value}
          role="tab"
          aria-selected={value === o.value}
          onClick={() => onChange(o.value)}
          className={cx("rounded-lg px-3 py-1.5 text-sm font-medium transition-colors", value === o.value ? "bg-white text-ink shadow-sm" : "text-muted hover:text-ink")}
        >
          {T(o.label)}
          {o.count != null && <span className="ml-1.5 text-xs text-subtle">{o.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: ReactNode; tone?: "crit" | "semi" | "rout" | "teal" }) {
  const T = useT();
  const color = tone ? { crit: "text-crit", semi: "text-semi", rout: "text-rout", teal: "text-teal-700" }[tone] : "text-ink";
  return (
    <Card className="px-4 py-3">
      <p className="text-xs font-medium tracking-wide text-muted uppercase">{T(label)}</p>
      <p className={cx("mt-1 text-2xl font-bold tabular-nums", color)}>{value}</p>
      {hint && <p className="mt-0.5 text-xs text-subtle">{T(hint)}</p>}
    </Card>
  );
}
