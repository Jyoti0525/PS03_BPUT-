"use client";

import { useEffect, useRef, useState } from "react";
import { Building2, Check, Loader2, MapPin, Plus, Search, ShieldCheck, BadgeInfo } from "lucide-react";
import { api } from "@/lib/api";
import { INDIAN_STATES } from "@/lib/india";
import { Badge, Button, Input, Label, Select, cx } from "@/components/ui";
import type { DirectoryHit, FacilityType, NewFacilityInput, Role } from "@/lib/types";

export type Workplace =
  | { kind: "existing"; facility_id: string; hit: DirectoryHit }
  | { kind: "directory"; directory_ref: string; hit: DirectoryHit }
  | { kind: "new"; facility: NewFacilityInput }
  | null;

const PUBLIC_TYPES: { v: FacilityType; label: string }[] = [
  { v: "sub_centre", label: "Sub-centre / Health & Wellness Centre" },
  { v: "phc", label: "Primary Health Centre" },
  { v: "chc", label: "Community Health Centre" },
  { v: "district_hospital", label: "District Hospital" },
  { v: "hospital", label: "Other hospital" },
  { v: "clinic", label: "Clinic / dispensary" },
];

export function workplaceLabel(w: Workplace) {
  if (!w) return "";
  if (w.kind === "new") return `${w.facility.name} (new)`;
  return w.hit.name;
}

/** Search India's health facilities (national directory) and registered workplaces. */
export function WorkplacePicker({ role, value, onChange }: { role: Role; value: Workplace; onChange: (w: Workplace) => void }) {
  const [q, setQ] = useState("");
  const [state, setState] = useState("");
  const [hits, setHits] = useState<DirectoryHit[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [adding, setAdding] = useState(value?.kind === "new");
  const [nf, setNf] = useState<NewFacilityInput>(value?.kind === "new" ? value.facility : { name: "", type: "phc", district: "", state: "", pincode: "" });
  const seq = useRef(0);

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) return;
    const my = ++seq.current;
    const t = setTimeout(async () => {
      setBusy(true);
      try {
        const r = await api.searchDirectory(term, state || null);
        if (my === seq.current) setHits(r);
      } catch {
        if (my === seq.current) setHits([]);
      } finally {
        if (my === seq.current) setBusy(false);
      }
    }, 280);
    return () => clearTimeout(t);
  }, [q, state]);

  const pick = (h: DirectoryHit) => onChange(h.facility_id ? { kind: "existing", facility_id: h.facility_id, hit: h } : { kind: "directory", directory_ref: h.directory_ref!, hit: h });
  const selectedKey = value && value.kind !== "new" ? value.hit.key : null;

  if (adding) {
    const update = (p: Partial<NewFacilityInput>) => {
      const next = { ...nf, ...p };
      setNf(next);
      onChange({ kind: "new", facility: next });
    };
    return (
      <div className="space-y-3 rounded-xl border border-coral-200 bg-coral-50/40 p-3">
        <p className="text-sm font-semibold text-ink">Add a public facility that is not listed</p>
        <div>
          <Label htmlFor="nf-name">Facility name</Label>
          <Input id="nf-name" value={nf.name} onChange={(e) => update({ name: e.target.value })} placeholder="e.g. PHC Balipatna" />
        </div>
        <div>
          <Label htmlFor="nf-type">Type</Label>
          <Select id="nf-type" value={nf.type} onChange={(e) => update({ type: e.target.value as FacilityType })}>
            {PUBLIC_TYPES.map((t) => (
              <option key={t.v} value={t.v}>
                {t.label}
              </option>
            ))}
          </Select>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <Label htmlFor="nf-state">State</Label>
            <Select id="nf-state" value={nf.state} onChange={(e) => update({ state: e.target.value })}>
              <option value="">Select</option>
              {INDIAN_STATES.map((s) => (
                <option key={s}>{s}</option>
              ))}
            </Select>
          </div>
          <div>
            <Label htmlFor="nf-dist">District</Label>
            <Input id="nf-dist" value={nf.district} onChange={(e) => update({ district: e.target.value })} />
          </div>
        </div>
        <div>
          <Label htmlFor="nf-pin" hint="(optional)">PIN code</Label>
          <Input id="nf-pin" inputMode="numeric" value={nf.pincode ?? ""} onChange={(e) => update({ pincode: e.target.value.replace(/\D/g, "").slice(0, 6) })} />
        </div>
        <p className="text-xs text-muted">It will be marked “self-registered” until verified.</p>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setAdding(false);
            onChange(null);
          }}
        >
          Back to search
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <div className="grid gap-2 sm:grid-cols-[1fr_150px]">
        <div className="relative">
          <Search className="absolute top-3.5 left-3 size-4 text-subtle" />
          <Input
            autoFocus
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              if (e.target.value.trim().length < 2) setHits(null);
            }}
            placeholder="Facility name, district or PIN code"
            className="pl-9"
            aria-label="Search your workplace"
          />
          {busy && <Loader2 className="absolute top-3.5 right-3 size-4 animate-spin text-subtle" />}
        </div>
        <Select value={state} onChange={(e) => setState(e.target.value)} aria-label="State">
          <option value="">All states</option>
          {INDIAN_STATES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </Select>
      </div>

      {value && value.kind !== "new" && (
        <div className="flex items-start gap-2 rounded-xl border-2 border-teal-600 bg-teal-50 p-3">
          <Check className="mt-0.5 size-4 shrink-0 text-teal-700" />
          <div className="min-w-0 text-sm">
            <p className="font-semibold text-ink">{value.hit.name}</p>
            <p className="text-xs text-muted">
              {value.hit.kind_label} · {[value.hit.district, value.hit.state].filter(Boolean).join(", ")}
              {value.hit.organisation_name && ` · ${value.hit.organisation_name}`}
            </p>
          </div>
        </div>
      )}

      {hits && (
        <ul className="max-h-72 space-y-1.5 overflow-y-auto pr-1" role="listbox" aria-label="Workplaces">
          {hits.length === 0 && !busy && <li className="rounded-xl bg-canvas px-3 py-4 text-center text-sm text-muted">No match. Try the district or PIN code.</li>}
          {hits.map((h) => (
            <li key={h.key}>
              <button
                type="button"
                role="option"
                aria-selected={selectedKey === h.key}
                onClick={() => pick(h)}
                className={cx("flex w-full items-start gap-3 rounded-xl border px-3 py-2.5 text-left transition-colors", selectedKey === h.key ? "border-teal-600 bg-teal-50" : "border-line hover:bg-canvas")}
              >
                <span className={cx("mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg", h.ownership === "public" ? "bg-teal-50 text-teal-700" : "bg-coral-50 text-coral-600")}>
                  <Building2 className="size-4" />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-semibold text-ink">{h.name}</span>
                  <span className="flex flex-wrap items-center gap-x-2 text-xs text-muted">
                    <span>{h.kind_label}</span>
                    <span className="inline-flex items-center gap-0.5">
                      <MapPin className="size-3" />
                      {[h.city, h.district, h.state].filter(Boolean).join(", ")}
                      {h.pincode && ` · ${h.pincode}`}
                    </span>
                  </span>
                  {h.organisation_name && <span className="block text-xs text-coral-600">{h.organisation_name}</span>}
                </span>
                {h.facility_id ? <Badge tone="teal">On Jeevia</Badge> : h.verified ? <Badge><ShieldCheck className="size-3" /> Listed</Badge> : null}
              </button>
            </li>
          ))}
        </ul>
      )}

      <div className="flex items-start gap-2 rounded-xl bg-canvas p-3 text-xs text-muted">
        <BadgeInfo className="mt-0.5 size-4 shrink-0" />
        <span>
          Government and private health facilities across India are listed (© OpenStreetMap contributors, ODbL). Company clinics, industrial units, campus health centres and health camps appear once their organisation registers on Jeevia.
          {role === "supervisor" ? " Can’t find a public facility? Add it below." : " Can’t find your workplace? Ask your supervisor to add it."}
        </span>
      </div>
      {role === "supervisor" && (
        <Button
          variant="secondary"
          size="sm"
          icon={<Plus className="size-4" />}
          onClick={() => {
            setAdding(true);
            onChange({ kind: "new", facility: nf });
          }}
        >
          Add a missing public facility
        </Button>
      )}
    </div>
  );
}
