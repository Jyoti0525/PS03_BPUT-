"use client";

import { useEffect, useState } from "react";
import { Building2, CheckCircle2, Search } from "lucide-react";
import { usePrefs } from "@/components/providers";
import { api } from "@/lib/api";
import { Input, cx } from "@/components/ui";
import type { ReferralDestination } from "@/lib/types";

export interface PickedDestination {
  name: string;
  facility_id: string | null;
  directory_ref: string | null;
  on_jeevia: boolean;
}

/** Optional destination recommendation: facilities already on Jeevia first, then national-directory matches.
 * A recommendation never restricts where the patient may seek care; the QR hand-off works at any facility. */
export function DestinationPicker({ value, onChange, quick }: { value: PickedDestination; onChange: (d: PickedDestination) => void; quick: string[] }) {
  const { tr } = usePrefs();
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<ReferralDestination[] | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    const t = setTimeout(() => {
      api.referralDestinations(q.trim())
        .then((r) => live && (setHits(r), setErr(null)))
        .catch((e) => live && setErr(e instanceof Error ? e.message : tr("Could not search")));
    }, q ? 250 : 0);
    return () => {
      live = false;
      clearTimeout(t);
    };
  }, [q, tr]);

  const pick = (h: ReferralDestination) => onChange({ name: h.name, facility_id: h.facility_id, directory_ref: h.facility_id ? null : h.directory_ref, on_jeevia: h.on_jeevia });
  const chosen = (h: ReferralDestination) => (h.facility_id && h.facility_id === value.facility_id) || (!!h.directory_ref && h.directory_ref === value.directory_ref);

  return (
    <div className="space-y-2">
      <div className="rounded-lg border border-teal-200 bg-teal-50/60 px-3 py-2 text-sm">
        <p className="font-semibold text-ink">{value.name || tr("No specific facility — patient choice")}</p>
        <p className="text-xs text-muted">
          {value.facility_id || value.directory_ref
            ? value.on_jeevia ? tr("Recommendation only. The QR hand-off also works at another facility.") : tr("National directory match. Recommendation only; patient may choose another facility.")
            : tr("Patient may attend any suitable facility. The QR summary carries the hand-off.")}
        </p>
      </div>
      <button type="button" onClick={() => onChange({ name: "", facility_id: null, directory_ref: null, on_jeevia: false })}
        className={cx("rounded-full border px-3 py-1.5 text-xs font-semibold", !value.name && !value.facility_id && !value.directory_ref ? "border-teal-600 bg-teal-50 text-teal-800" : "border-line bg-white text-muted hover:border-teal-300")}>
        {tr("No specific destination — patient choice")}
      </button>
      {quick.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {quick.map((name) => (
            <button key={name} type="button" onClick={() => onChange({ name, facility_id: null, directory_ref: null, on_jeevia: false })}
              className={cx("rounded-full border px-2.5 py-1 text-xs", value.name === name && !value.facility_id && !value.directory_ref ? "border-teal-600 bg-teal-50 font-semibold text-teal-800" : "border-line bg-white text-muted hover:border-teal-300")}>
              {name}
            </button>
          ))}
        </div>
      )}
      <div className="relative">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-subtle" />
        <Input value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" placeholder={tr("Search any hospital: name, district or PIN")} aria-label={tr("Search facilities")} />
      </div>
      {err && <p className="text-xs text-crit">{err}</p>}
      {q.trim().length >= 2 && !hits?.some((h) => h.name.toLowerCase() === q.trim().toLowerCase()) && (
        <button type="button" onClick={() => onChange({ name: q.trim(), facility_id: null, directory_ref: null, on_jeevia: false })}
          className="w-full rounded-lg border border-dashed border-teal-300 bg-teal-50/50 px-3 py-2 text-left text-sm text-teal-800 hover:bg-teal-50">
          {tr("Use {name} as a typed recommendation (not linked to Jeevia)", { name: q.trim() })}
        </button>
      )}
      <ul className="max-h-60 divide-y divide-line overflow-y-auto rounded-lg border border-line bg-white">
        {hits === null ? (
          <li className="px-3 py-2 text-xs text-muted">{tr("Loading…")}</li>
        ) : hits.length === 0 ? (
          <li className="px-3 py-2 text-xs text-muted">{q.trim().length < 2 ? tr("Type at least 2 characters to search the national directory by facility, district or PIN.") : tr("No indexed match. You can use the typed destination as an advisory recommendation below.")}</li>
        ) : (
          hits.map((h) => (
            <li key={h.key}>
              <button type="button" onClick={() => pick(h)} className={cx("flex w-full items-start gap-2 px-3 py-2 text-left hover:bg-canvas", chosen(h) && "bg-teal-50")}>
                {chosen(h) ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-teal-700" /> : <Building2 className="mt-0.5 size-4 shrink-0 text-subtle" />}
                <span className="min-w-0">
                  <span className="block text-sm font-medium text-ink">{h.name}</span>
                  <span className="block text-xs text-muted">
                    {tr(h.kind_label)} · {[h.district, h.state].filter(Boolean).join(", ")}
                    {h.on_jeevia && <span className="ml-1.5 font-semibold text-teal-700">· {tr("on Jeevia")}</span>}
                  </span>
                </span>
              </button>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
