"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowRight, LocateFixed, MapPin, QrCode, Search } from "lucide-react";
import { usePrefs } from "@/components/providers";
import { api } from "@/lib/api";
import type { KioskFinderHit } from "@/lib/types";

/** Patients have no account: they reach a facility's intake through its kiosk link (/k/CODE), by QR, by typing the
 * code, or, without a code, by finding a nearby facility that takes forms from home. */
export function PatientEntry() {
  const { tr } = usePrefs();
  const router = useRouter();
  const [code, setCode] = useState("");
  const [finding, setFinding] = useState(false);
  const [place, setPlace] = useState("");
  const [hits, setHits] = useState<KioskFinderHit[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const clean = code.trim().toUpperCase().replace(/[^A-Z0-9]/g, "");

  async function find(lat?: number, lon?: number) {
    setBusy(true);
    setErr(null);
    try {
      setHits(await api.kioskFinder(place.trim(), lat, lon));
    } catch {
      setErr(tr("Could not search right now. Please try again."));
    } finally {
      setBusy(false);
    }
  }

  function nearMe() {
    if (!navigator.geolocation) return find();
    setBusy(true);
    navigator.geolocation.getCurrentPosition(
      (p) => find(p.coords.latitude, p.coords.longitude),
      () => find(),
      { timeout: 8000, maximumAge: 600000 },
    );
  }

  return (
    <div id="patient" className="mt-6 max-w-xl scroll-mt-24 rounded-3xl border-2 border-teal-200 bg-white/80 p-5 backdrop-blur">
      <p className="flex items-center gap-2 text-base font-bold text-ink">
        <QrCode className="size-5 text-teal-600" /> {tr("Are you a patient? Start here")}
      </p>
      <p className="mt-1 text-sm text-muted">
        {tr("Scan the QR poster at your health centre, or type the code it gives you. No app, no login, any phone or computer.")}
      </p>
      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (clean) router.push(`/k/${clean}`);
        }}
      >
        <input
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder={tr("Health centre code, e.g. 7QX4MPA2")}
          aria-label={tr("Health centre code")}
          autoCapitalize="characters"
          className="h-12 min-w-0 flex-1 rounded-full border-2 border-line bg-white px-5 text-base font-semibold tracking-wider text-ink uppercase outline-none focus:border-teal-300"
        />
        <button type="submit" disabled={!clean} className="inline-flex h-12 items-center gap-2 rounded-full bg-ink px-5 font-semibold text-white disabled:opacity-40">
          {tr("Start")} <ArrowRight className="size-4" />
        </button>
      </form>

      <Link href="/k/ANYCARE" className="mt-3 flex items-center justify-between gap-3 rounded-2xl bg-teal-50 px-4 py-3 text-sm font-semibold text-teal-800 hover:bg-teal-100">
        <span>
          {tr("Not sure where you will go? Fill in now and take it to any health centre")}
          <span className="block text-xs font-normal text-teal-700">{tr("You get a reference and QR code; any centre on Jeevia opens your details from it.")}</span>
        </span>
        <ArrowRight className="size-4 shrink-0" />
      </Link>
      {!finding ? (
        <button type="button" onClick={() => setFinding(true)} className="mt-3 text-sm font-semibold text-teal-700 underline-offset-4 hover:underline">
          {tr("Don't know the code? Find your nearest health centre")} →
        </button>
      ) : (
        <div className="mt-4 border-t border-line pt-4">
          <form
            className="flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              find();
            }}
          >
            <input
              value={place}
              onChange={(e) => setPlace(e.target.value)}
              placeholder={tr("PIN code, district or centre name")}
              aria-label={tr("PIN code, district or centre name")}
              className="h-11 min-w-0 flex-1 rounded-full border-2 border-line bg-white px-4 text-sm text-ink outline-none focus:border-teal-300"
            />
            <button type="submit" disabled={busy} aria-label={tr("Search")} className="inline-flex h-11 items-center rounded-full border-2 border-line bg-white px-4 text-ink disabled:opacity-40">
              <Search className="size-4" />
            </button>
          </form>
          <button type="button" onClick={nearMe} disabled={busy} className="mt-2 inline-flex items-center gap-1.5 text-sm font-semibold text-teal-700 disabled:opacity-40">
            <LocateFixed className="size-4" /> {tr("Use my location")}
          </button>
          {err && <p className="mt-2 text-sm text-crit">{err}</p>}
          {hits && hits.length === 0 && (
            <p className="mt-3 text-sm text-muted">
              {tr("No health centre found. Try your PIN code or district. In an emergency call 108.")}
            </p>
          )}
          {hits && hits.length > 0 && (
            <ul className="mt-3 divide-y divide-line rounded-2xl border border-line bg-white">
              {hits.map((h, n) => {
                const where = (
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-ink">{h.facility_name}</span>
                    <span className="block truncate text-xs text-muted">
                      {[h.facility_type, h.district, h.pincode].filter(Boolean).join(" · ")}
                      {h.km != null && ` · ${h.km} km`}
                    </span>
                  </span>
                );
                return h.code ? (
                  <li key={h.code}>
                    <Link href={`/k/${h.code}`} className="flex items-center gap-3 px-4 py-3 hover:bg-teal-50/60">
                      <MapPin className="size-4 shrink-0 text-teal-600" />
                      {where}
                      <span className="shrink-0 rounded-full bg-teal-50 px-2.5 py-1 text-xs font-semibold text-teal-700">{tr("Fill in before you go")}</span>
                      <ArrowRight className="size-4 text-muted" />
                    </Link>
                  </li>
                ) : (
                  <li key={`d${n}`} className="flex items-center gap-3 px-4 py-3">
                    <MapPin className="size-4 shrink-0 text-muted" />
                    {where}
                    <span className="flex shrink-0 items-center gap-2 text-xs font-semibold">
                      <span className="text-muted">{tr("Walk in")}</span>
                      {h.phone && <a href={`tel:${h.phone.replace(/[^\d+]/g, "")}`} className="text-teal-700 hover:underline">{tr("Call")}</a>}
                      {h.lat != null && h.lon != null && (
                        <a href={`https://www.google.com/maps/dir/?api=1&destination=${h.lat},${h.lon}`} target="_blank" rel="noreferrer" className="text-teal-700 hover:underline">
                          {tr("Directions")}
                        </a>
                      )}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
          {hits && hits.some((h) => !h.code) && <p className="mt-2 text-xs text-muted">{tr("Centres marked Walk in are not on Jeevia yet: go there directly and staff will see you.")}</p>}
          <p className="mt-3 text-xs text-muted">
            {tr("You fill in your problem before you go. The staff at that centre see you and decide what you need, including referral. In an emergency call 108.")}
          </p>
        </div>
      )}
    </div>
  );
}
