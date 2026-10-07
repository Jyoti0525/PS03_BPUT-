"use client";

import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { Building2, CloudUpload, Loader2, Ticket, Wifi, WifiOff, ShieldCheck, Languages, Clock } from "lucide-react";
import { api, getDeviceId } from "@/lib/api";
import { useSession, usePrefs } from "@/components/providers";
import { useOnline } from "@/lib/hooks";
import { A11yButton, LanguageButton, Logo } from "@/components/layout/chrome";
import { Badge, Button, Card } from "@/components/ui";
import dynamic from "next/dynamic";
import { subscribeOutbox, type OutboxItem } from "@/lib/offline/outbox";
import { precacheCurrentPage } from "@/lib/offline/precache";
import { loadPhrases } from "@/lib/i18n/phrases";
import type { KioskInfo } from "@/lib/types";

/** The intake wizard loads after the start screen; it is fetched (and cached for offline) as soon as the kiosk activates. */
const loadIntake = () => import("@/components/intake/intake-flow");
const IntakeFlow = dynamic(() => loadIntake().then((m) => m.IntakeFlow), {
  loading: () => (
    <div className="flex items-center justify-center gap-2 py-24 text-muted">
      <Loader2 className="size-5 animate-spin" /> Loading…
    </div>
  ),
});

const infoKey = (code: string) => `jeevia.kiosk.info.${code.toUpperCase()}`;

function cachedInfo(code: string): KioskInfo | null {
  try {
    const raw = localStorage.getItem(infoKey(code));
    return raw ? (JSON.parse(raw) as KioskInfo) : null;
  } catch {
    return null;
  }
}

function saveInfo(code: string, info: KioskInfo | null) {
  try {
    if (info) localStorage.setItem(infoKey(code), JSON.stringify(info));
    else localStorage.removeItem(infoKey(code));
  } catch {
    /* storage blocked */
  }
}

/**
 * Public kiosk: opens on any tab or device from a link the facility shares (or a QR on the wall).
 * No staff login — the link itself grants an intake-only session for that facility.
 * Once opened online, the link keeps working offline: facility info and the kiosk session are kept
 * on the device, intakes queue in the outbox, and the page itself is cached by the service worker.
 */
export default function PublicKiosk() {
  const { code } = useParams<{ code: string }>();
  const { user, loading, signIn } = useSession();
  const { tr, t } = usePrefs();
  const online = useOnline();
  const [info, setInfo] = useState<KioskInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [started, setStarted] = useState(false);
  const [round, setRound] = useState(0);
  const [outbox, setOutbox] = useState<OutboxItem[]>([]);

  useEffect(() => subscribeOutbox(setOutbox), []);

  useEffect(() => {
    if (loading) return;
    let live = true;
    (async () => {
      try {
        let i: KioskInfo;
        let reachable = true;
        try {
          i = await api.kioskInfo(code);
          saveInfo(code, i);
        } catch (e) {
          const status = (e as { status?: number }).status;
          const cached = cachedInfo(code);
          if (status || !cached) {
            if (status === 404) saveInfo(code, null);
            throw e;
          }
          i = cached; // offline: reuse what this device saw last time
          reachable = false;
        }
        if (!live) return;
        setInfo(i);
        const valid = user && user.role === "kiosk" && user.facility_id === i.facility_id;
        if (!valid) {
          if (!reachable) throw new Error("This kiosk needs an internet connection once to activate on this device. Connect and reload.");
          const r = await api.kioskSession(code, getDeviceId());
          if (live) signIn(r.tokens, r.user);
        }
        // Fetch the intake wizard and the Hindi/Odia screens now, so they are cached for offline use too.
        if (reachable) Promise.allSettled([loadIntake(), loadPhrases("hi"), loadPhrases("or")]).then(() => precacheCurrentPage());
      } catch (e) {
        if (live) setError(e instanceof Error ? e.message : tr("This kiosk link could not be opened."));
      }
    })();
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, loading]);

  const ready = info && user?.role === "kiosk";

  return (
    <div className="min-h-[calc(100vh-28px)] bg-[radial-gradient(60%_40%_at_100%_0%,var(--color-coral-50),transparent),radial-gradient(60%_40%_at_0%_100%,var(--color-teal-50),transparent)]">
      <header className="no-print sticky top-0 z-30 border-b border-line bg-white/85 backdrop-blur-xl">
        <div className="mx-auto flex h-16 max-w-5xl items-center gap-3 px-4">
          <Logo />
          {info && (
            <span className="hidden min-w-0 items-center gap-1.5 truncate text-sm text-muted md:flex">
              <Building2 className="size-4 shrink-0" /> <span className="truncate font-semibold text-ink">{info.facility_name}</span> {!info.for_home && <> · {tr(info.label)}</>}
            </span>
          )}
          <div className="ml-auto flex items-center gap-2">
            {online ? (
              <Badge tone="rout">
                <Wifi className="size-3" /> <span className="hidden sm:inline">{tr("Online")}</span>
              </Badge>
            ) : (
              <Badge tone="semi">
                <WifiOff className="size-3" /> {tr("Offline")}
              </Badge>
            )}
            {outbox.length > 0 && (
              <Badge tone="info">
                <CloudUpload className="size-3" /> {outbox.length}
              </Badge>
            )}
            <LanguageButton compact className="sm:hidden" />
            <LanguageButton className="hidden sm:block" />
            <A11yButton />
          </div>
        </div>
      </header>

      <main className="px-4 py-8">
        {error ? (
          <Card className="mx-auto max-w-md p-8 text-center">
            <p className="text-xl font-bold text-ink">{tr("Link not active")}</p>
            <p className="mt-2 text-muted">{error}</p>
          </Card>
        ) : !ready ? (
          <div className="flex items-center justify-center gap-2 py-24 text-muted">
            <Loader2 className="size-5 animate-spin" /> {tr("Opening kiosk…")}
          </div>
        ) : !started ? (
          <div className="fade-up mx-auto max-w-2xl text-center">
            <span className="inline-flex items-center gap-2 rounded-full border border-coral-200 bg-white px-4 py-1.5 text-xs font-bold tracking-wider text-coral-500 uppercase">
              <Building2 className="size-3.5" /> {info.facility_name}
            </span>
            <h1 className="mt-6 text-4xl leading-tight font-extrabold tracking-tight text-ink sm:text-5xl">
              {info.for_home ? (
                <>
                  {tr("Fill in")} <span className="text-gradient">{tr("before you come")}</span>
                </>
              ) : (
                <>
                  {tr("Get your")} <span className="text-gradient">{tr("token")}</span>
                </>
              )}
            </h1>
            <p className="mx-auto mt-4 max-w-lg text-lg text-muted">
              {info.for_home ? tr("You get a reference number. Show it at the desk when you arrive; your place in the queue starts then.") : t("kiosk.welcome")}
            </p>
            {info.for_home && <p className="mx-auto mt-4 max-w-lg rounded-xl border border-crit-line bg-crit-bg px-4 py-2.5 text-sm font-medium text-crit">{t("kiosk.home.danger")}</p>}
            <button
              onClick={() => setStarted(true)}
              className="bg-brand-gradient mx-auto mt-10 flex h-20 w-full max-w-sm items-center justify-center gap-3 rounded-full text-2xl font-bold text-white shadow-[0_18px_40px_-12px_rgb(242_145_145/0.9)] transition-transform hover:-translate-y-0.5 active:scale-[0.98]"
            >
              <Ticket className="size-7" /> {tr("Start")}
            </button>
            <div className="mx-auto mt-12 grid max-w-xl gap-3 text-left sm:grid-cols-3">
              {[
                { i: <Languages className="size-5" />, t: "Speak in your language" },
                { i: <Clock className="size-5" />, t: "Takes about 3 minutes" },
                { i: <ShieldCheck className="size-5" />, t: "Shared only with your care team" },
              ].map((x) => (
                <div key={x.t} className="flex items-center gap-3 rounded-2xl border border-line bg-white/80 p-3 text-sm font-medium text-ink-2">
                  <span className="grid size-9 shrink-0 place-items-center rounded-xl bg-teal-50 text-teal-700">{x.i}</span>
                  {tr(x.t)}
                </div>
              ))}
            </div>
          </div>
        ) : (
          <IntakeFlow
            key={round}
            mode="link"
            facilityId={info.facility_id}
            organisationName={info.organisation_name}
            offline={!online}
            onReset={() => {
              setRound((n) => n + 1);
              setStarted(false);
            }}
          />
        )}
        {ready && started && (
          <div className="no-print mx-auto mt-6 max-w-3xl text-center">
            <Button variant="ghost" size="sm" onClick={() => { setRound((n) => n + 1); setStarted(false); }}>
              {tr("Cancel and start over")}
            </Button>
          </div>
        )}
      </main>
    </div>
  );
}
