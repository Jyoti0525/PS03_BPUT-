"use client";

import { useEffect, useRef, useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import { cx } from "@/components/ui";
import { pinProblem } from "@/lib/pin";

export function OtpBoxes({ value, onChange, autoFocus }: { value: string; onChange: (v: string) => void; autoFocus?: boolean }) {
  const refs = useRef<(HTMLInputElement | null)[]>([]);
  useEffect(() => {
    if (autoFocus) refs.current[0]?.focus();
  }, [autoFocus]);
  return (
    <div
      className="flex gap-2"
      onPaste={(e) => {
        const digits = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, 6);
        if (digits) {
          e.preventDefault();
          onChange(digits);
          refs.current[Math.min(digits.length, 5)]?.focus();
        }
      }}
    >
      {Array.from({ length: 6 }).map((_, i) => (
        <input
          key={i}
          ref={(el) => {
            refs.current[i] = el;
          }}
          inputMode="numeric"
          autoComplete={i === 0 ? "one-time-code" : "off"}
          aria-label={`OTP digit ${i + 1}`}
          maxLength={1}
          value={value[i] ?? ""}
          onChange={(e) => {
            const d = e.target.value.replace(/\D/g, "").slice(-1);
            const arr = value.padEnd(6, " ").split("");
            arr[i] = d || " ";
            onChange(arr.join("").trimEnd());
            if (d && i < 5) refs.current[i + 1]?.focus();
          }}
          onKeyDown={(e) => {
            if (e.key === "Backspace" && !value[i] && i > 0) refs.current[i - 1]?.focus();
          }}
          className="h-13 w-11 rounded-xl border border-line bg-white text-center text-xl font-bold text-ink focus:border-teal-600 focus:ring-4 focus:ring-teal-100 focus:outline-none sm:w-12"
        />
      ))}
    </div>
  );
}

/** Masked 4–6 digit PIN entry. */
export function PinInput({ id, value, onChange, autoFocus, label = "PIN", onEnter }: { id: string; value: string; onChange: (v: string) => void; autoFocus?: boolean; label?: string; onEnter?: () => void }) {
  const [show, setShow] = useState(false);
  return (
    <div className="relative">
      <input
        id={id}
        autoFocus={autoFocus}
        type={show ? "text" : "password"}
        inputMode="numeric"
        autoComplete="off"
        aria-label={label}
        maxLength={6}
        value={value}
        onChange={(e) => onChange(e.target.value.replace(/\D/g, "").slice(0, 6))}
        onKeyDown={(e) => e.key === "Enter" && onEnter?.()}
        placeholder="••••"
        className="h-14 w-full rounded-xl border border-line bg-white px-4 pr-12 text-center font-mono text-2xl tracking-[0.5em] text-ink focus:border-teal-600 focus:ring-4 focus:ring-teal-100 focus:outline-none"
      />
      <button type="button" onClick={() => setShow((s) => !s)} className="absolute top-3.5 right-3 text-subtle hover:text-ink" aria-label={show ? "Hide PIN" : "Show PIN"}>
        {show ? <EyeOff className="size-5" /> : <Eye className="size-5" />}
      </button>
    </div>
  );
}

/** New PIN + confirmation with live strength feedback. Returns the PIN when valid, else null. */
export function NewPinFields({ pin, confirm, onPin, onConfirm }: { pin: string; confirm: string; onPin: (v: string) => void; onConfirm: (v: string) => void }) {
  const problem = pin.length >= 4 ? pinProblem(pin) : null;
  const mismatch = confirm.length >= pin.length && confirm.length > 0 && confirm !== pin;
  return (
    <div className="space-y-3">
      <div>
        <label htmlFor="new-pin" className="mb-1.5 block text-sm font-medium text-ink-2">
          Choose a 4–6 digit PIN
        </label>
        <PinInput id="new-pin" value={pin} onChange={onPin} autoFocus label="New PIN" />
        <p className={cx("mt-1.5 text-xs", problem ? "font-medium text-crit" : "text-muted")}>{problem ?? "Avoid birthdays, repeated digits and sequences like 1234."}</p>
      </div>
      <div>
        <label htmlFor="confirm-pin" className="mb-1.5 block text-sm font-medium text-ink-2">
          Enter it again
        </label>
        <PinInput id="confirm-pin" value={confirm} onChange={onConfirm} label="Confirm PIN" />
        {mismatch && <p className="mt-1.5 text-xs font-medium text-crit">PINs don’t match</p>}
      </div>
    </div>
  );
}

export function newPinError(pin: string, confirm: string): string | null {
  return pinProblem(pin) ?? (pin !== confirm ? "PINs don’t match" : null);
}
