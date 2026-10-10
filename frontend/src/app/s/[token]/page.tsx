"use client";

import { usePrefs } from "@/components/providers";
import { fmtDateTime } from "@/lib/hooks";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { KeyRound, Printer, Clock, Lock } from "lucide-react";
import { api, ApiError } from "@/lib/api";
import { Logo, LanguageButton } from "@/components/layout/chrome";
import { Button, Card, FieldError, Input, Label, Spinner } from "@/components/ui";
import { ReferredVisit } from "@/components/triage/referred-visit";
import type { SharedSummary } from "@/lib/types";

/** Opened by scanning a referral QR. Clinician-facing; requires the access code printed beside the QR. */
export default function SharedSummaryPage() {
  const { tr } = usePrefs();
  const { token } = useParams<{ token: string }>();
  const [meta, setMeta] = useState<{ facility_name: string; expires_at: string } | null>(null);
  const [metaErr, setMetaErr] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [data, setData] = useState<SharedSummary | null>(null);

  useEffect(() => {
    api.shareMeta(token).then(setMeta).catch((e) => setMetaErr(e instanceof Error ? e.message : "Link not valid"));
  }, [token]);

  const open = async () => {
    setErr(null);
    if (!/^\d{6}$/.test(code)) return setErr(tr("Enter the 6-digit access code printed next to the QR"));
    setBusy(true);
    try {
      setData(await api.openShare(token, code));
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : tr("Could not open"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-[calc(100vh-28px)] bg-canvas">
      <header className="no-print border-b border-line bg-white">
        <div className="mx-auto flex h-16 max-w-4xl items-center gap-3 px-4">
          <Logo />
          <span className="hidden text-sm text-muted sm:inline">{tr("Referral summary")}</span>
          <div className="ml-auto flex items-center gap-2">
            {data && (
              <Button variant="secondary" size="sm" icon={<Printer className="size-4" />} onClick={() => window.print()}>
                {tr("Print")}
              </Button>
            )}
            <LanguageButton compact />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-4 py-8">
        {metaErr ? (
          <Card className="mx-auto max-w-md p-8 text-center">
            <Lock className="mx-auto size-10 text-subtle" />
            <p className="mt-3 text-xl font-bold text-ink">{tr("Summary not available")}</p>
            <p className="mt-2 text-muted">{metaErr}</p>
          </Card>
        ) : !meta ? (
          <Spinner label={tr("Checking link…")} />
        ) : !data ? (
          <Card className="mx-auto max-w-md p-7">
            <span className="grid size-12 place-items-center rounded-2xl bg-coral-50 text-coral-500">
              <KeyRound className="size-6" />
            </span>
            <h1 className="mt-4 text-2xl font-bold text-ink">{tr("Enter access code")}</h1>
            <p className="mt-1 text-muted">
              {tr("Patient summary shared by")} <strong className="text-ink">{meta.facility_name}</strong>{tr(". The 6-digit code is printed beside the QR on the referral slip.")}
            </p>
            <Input
              autoFocus
              inputMode="numeric"
              value={code}
              onChange={(ev) => setCode(ev.target.value.replace(/\D/g, "").slice(0, 6))}
              onKeyDown={(ev) => ev.key === "Enter" && open()}
              className="mt-5 h-14 text-center font-mono text-2xl tracking-[0.4em]"
              aria-label={tr("Access code")}
              placeholder="••••••"
            />
            {err && <p className="mt-2 text-sm font-medium text-crit">{err}</p>}
            <Button size="lg" className="mt-4 w-full" loading={busy} onClick={open}>
              {tr("Open summary")}
            </Button>
            <p className="mt-4 flex items-center gap-1.5 text-xs text-subtle">
              <Clock className="size-3.5" /> {tr("Link valid until")} {fmtDateTime(meta.expires_at)}{tr(". Every opening is logged.")}
            </p>
          </Card>
        ) : (
          <ReferredVisit data={data} viaLink referralAction={data.referral ? <ReceivedForm token={token} code={code} referral={data.referral} /> : null} />
        )}
      </main>
    </div>
  );
}

/** E4: the receiving clinician confirms the patient reached care; this closes the referral at the sending facility. */
function ReceivedForm({ token, code, referral }: { token: string; code: string; referral: NonNullable<SharedSummary["referral"]> }) {
  const { tr } = usePrefs();
  const [who, setWho] = useState("");
  const [done, setDone] = useState<string | null>(referral.status === "received" ? referral.received_by ?? "" : null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  if (done !== null) return <p className="border-t border-line px-4 py-3 text-sm font-semibold text-teal-700">{tr("Care received — confirmed by {who}", { who: done })}</p>;
  return (
    <div className="no-print flex flex-wrap items-end gap-2 border-t border-line px-4 py-3">
      <div className="min-w-[220px] flex-1">
        <Label htmlFor="rcv-who">{tr("Patient seen here? Your name and role")}</Label>
        <Input id="rcv-who" value={who} onChange={(e) => setWho(e.target.value)} placeholder={tr("e.g. Dr Rao, casualty")} />
      </div>
      <Button
        variant="teal"
        loading={busy}
        onClick={async () => {
          setErr(null);
          if (who.trim().length < 3) return setErr(tr("Enter your name and role"));
          setBusy(true);
          try {
            const r = await api.shareReceived(token, code, who, "");
            setDone(r.received_by);
          } catch (e) {
            setErr(e instanceof Error ? e.message : tr("Failed"));
          } finally {
            setBusy(false);
          }
        }}
      >
        {tr("Confirm care received")}
      </Button>
      <FieldError>{err}</FieldError>
    </div>
  );
}
