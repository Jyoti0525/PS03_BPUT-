"use client";

import { useEffect, useState } from "react";
import { QrCode } from "lucide-react";
import { api } from "@/lib/api";
import { usePrefs } from "@/components/providers";
import { Button, Card, Input } from "@/components/ui";

/** A patient brings a reference (J-XXXXXX) or QR from a form filled in "for any centre": claim it for this facility.
 * Scanning the QR with any phone camera opens /desk?claim=J-XXXXXX, which fills the box in. */
export function ClaimForm({ onClaimed }: { onClaimed?: () => void }) {
  const { tr } = usePrefs();
  const [ref, setRef] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);

  useEffect(() => {
    const c = new URLSearchParams(window.location.search).get("claim");
    if (c) setRef(c.toUpperCase());
  }, []);

  const claim = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const e = await api.claimForm(ref.trim());
      setMsg({ ok: true, text: tr("Checked in. Token {t}. The details are in the queue.", { t: e.token ?? "" }) });
      setRef("");
      onClaimed?.();
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : tr("Could not find this form") });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card className="p-4">
      <p className="flex items-center gap-2 font-semibold text-ink">
        <QrCode className="size-4 text-teal-600" /> {tr("Patient has a form reference?")}
      </p>
      <p className="mt-1 text-sm text-muted">{tr("Forms filled in for any centre start with J-. Type it, scan the patient's QR with a phone camera, or enter the mobile number they gave if they lost it.")}</p>
      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (ref.trim()) claim();
        }}
      >
        <Input value={ref} onChange={(e) => setRef(e.target.value.toUpperCase().slice(0, 40))} placeholder={tr("J-7QX4MP or mobile number")} aria-label={tr("Form reference")} className="font-mono" />
        <Button type="submit" variant="teal" loading={busy} disabled={!ref.trim()}>
          {tr("Check in")}
        </Button>
      </form>
      {msg && <p className={msg.ok ? "mt-2 text-sm font-medium text-rout" : "mt-2 text-sm font-medium text-crit"}>{msg.text}</p>}
    </Card>
  );
}
