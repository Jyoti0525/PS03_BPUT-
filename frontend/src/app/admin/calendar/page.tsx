"use client";

import { useState } from "react";
import { CalendarDays, CloudRain, Plus, Save, Search, Trash2, UserRound } from "lucide-react";
import { api } from "@/lib/api";
import { ApiError } from "@/lib/api/contract";
import { useAsync } from "@/lib/hooks";
import { useSession, usePrefs } from "@/components/providers";
import { PageHeader } from "@/components/layout/app-shell";
import { Badge, Button, Card, CardHeader, Empty, ErrorNote, Input, Label, Spinner, cx } from "@/components/ui";
import { toast } from "@/components/ui/toast";
import type { CadreKey, LocalFestival, OnsetReading, RegionCalendar, RegionConfig, VisitCalendar, VisitKind } from "@/lib/types";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const day = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number);
  return `${d} ${MONTHS[m - 1]} ${y}`;
};
const span = (a: string | null, b: string | null) => (!a ? "—" : !b || a === b ? day(a) : `${day(a)} – ${day(b)}`);
const mmdd = (v: string) => {
  const [m, d] = v.split("-").map(Number);
  return `${d} ${MONTHS[m - 1]}`;
};

const CADRES: { key: CadreKey; what: string }[] = [
  { key: "community", what: "Village health activist" },
  { key: "nurse", what: "Auxiliary nurse midwife" },
  { key: "nutrition", what: "Anganwadi (nutrition and child care)" },
  { key: "male", what: "Male multipurpose health worker" },
  { key: "cho", what: "Community Health Officer" },
];

/** F5: the festival and season table this facility's notes use to date "since Diwali" or "after the rains", and the
 *  names of its front-line workers. Shipped per state (regions.yaml, every date sourced); a supervisor can change it. */
export default function RegionalCalendarPage() {
  const { user } = useSession();
  const { tr } = usePrefs();
  const fid = user!.facility_id!;
  const { data, error, reload } = useAsync(() => api.facilityCalendar(fid), [fid]);
  // 501: the browser-only demo has no calendar (it lives on the server with its sources). Not a fault, so no retry.
  if (error instanceof ApiError && error.status === 501)
    return (
      <>
        <PageHeader title={tr("Regional calendar")} />
        <Card><Empty icon={<CalendarDays className="size-6" />} title={tr("The regional calendar needs the live API")} body={tr("Festivals, seasons and worker names for this state come from the Jeevia server. Start the server to view or edit them.")} /></Card>
      </>
    );
  if (error) return <ErrorNote error={error} onRetry={reload} />;
  if (!data) return <Spinner />;
  return <CalendarView key={JSON.stringify(data.region_config)} data={data} fid={fid} canEdit={user!.role === "supervisor"} onSaved={reload} />;
}

function CalendarView({ data, fid, canEdit, onSaved }: { data: RegionCalendar; fid: string; canEdit: boolean; onSaved: () => void }) {
  const { tr } = usePrefs();
  const [cfg, setCfg] = useState<RegionConfig>(data.region_config ?? {});
  const [saving, setSaving] = useState(false);
  const dirty = JSON.stringify(cfg) !== JSON.stringify(data.region_config ?? {});

  const save = async () => {
    const m = cfg.monsoon;
    if (m && (!/^\d{2}-\d{2}$/.test(m.onset) || !/^\d{2}-\d{2}$/.test(m.withdrawal))) {
      toast(tr("Give both monsoon dates as MM-DD, or clear both"), "error");
      return;
    }
    setSaving(true);
    try {
      const clean: RegionConfig = { ...cfg, monsoon: m ?? null, cadres: Object.fromEntries(Object.entries(cfg.cadres ?? {}).filter(([, v]) => v?.trim())) };
      await api.updateFacility(fid, { region_config: clean });
      toast(tr("Regional calendar saved — new notes use it"));
      onSaved();
    } catch (e) {
      toast(e instanceof Error ? e.message : tr("Save failed"), "error");
    } finally {
      setSaving(false);
    }
  };

  const past = data.festivals.filter((f) => f.past).reverse();
  const coming = data.festivals.filter((f) => !f.past);

  return (
    <div className="mx-auto max-w-5xl pb-20">
      <PageHeader
        title={tr("Regional calendar")}
        subtitle={tr("Patients often date an illness by a festival or season. The note shows the date it points to beside their words, marked VAGUE; staff confirm it, and the rules never use it.")}
        actions={canEdit ? <Button onClick={save} loading={saving} disabled={!dirty} variant="teal" icon={<Save className="size-4" />}>{tr("Save changes")}</Button> : undefined}
      />

      {!data.state && (
        <p className="mb-4 rounded-xl border border-semi/30 bg-semi-bg px-4 py-3 text-sm text-ink">
          {tr("This facility's state is not in the regional table, so national festivals are used and monsoon dates are unknown. Set the state in Facility setup.")}
        </p>
      )}

      <TryPhrase fid={fid} sources={data.sources} />

      <Card className="mt-4">
        <CardHeader title={tr("Worker names")} subtitle={tr("The titles staff use here. They appear on screens, staff roles and the helper list at the kiosk.")} icon={<UserRound className="size-4" />} />
        <ul className="divide-y divide-line">
          {CADRES.map(({ key, what }) => {
            const c = data.cadres[key];
            return (
              <li key={key} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <div className="min-w-48 flex-1">
                  <p className="font-semibold text-ink">{c.en}{c.or && <span className="ml-2 font-normal text-muted">{c.or}</span>}{c.hi && <span className="ml-2 font-normal text-muted">{c.hi}</span>}</p>
                  <p className="text-xs text-muted">{tr(what)} · {c.full}</p>
                  {c.source && <p className="text-[11px] text-subtle">{tr("Source")}: {tr(c.source)}</p>}
                </div>
                {canEdit && (
                  <Input
                    aria-label={`${tr("Local name for")} ${tr(what)}`}
                    value={cfg.cadres?.[key] ?? ""}
                    onChange={(e) => setCfg({ ...cfg, cadres: { ...cfg.cadres, [key]: e.target.value } })}
                    placeholder={tr("Local name (optional)")}
                    maxLength={60}
                    className="h-9 w-56 text-sm"
                  />
                )}
              </li>
            );
          })}
        </ul>
      </Card>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader title={tr("Monsoon")} subtitle={data.monsoon?.station ? `${tr("IMD normal dates")} · ${data.monsoon.station}` : tr("No dates for this state")} icon={<CloudRain className="size-4" />} />
          <div className="space-y-3 p-4 text-sm">
            {data.monsoon && (
              <p className="text-ink">
                {tr("Rains begin")} <b>{mmdd(data.monsoon.onset)}</b> · {tr("withdraw")} <b>{mmdd(data.monsoon.withdrawal)}</b>
              </p>
            )}
            {data.northeast && <p className="text-xs text-muted">{tr("This state also gets the northeast monsoon (20 Oct – 31 Dec). “The rains” shows both and asks which.")}</p>}
            {canEdit && (
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <Label htmlFor="m-on">{tr("Local onset (MM-DD)")}</Label>
                  <Input id="m-on" value={cfg.monsoon?.onset ?? ""} placeholder={data.monsoon?.onset ?? "06-15"} maxLength={5}
                    onChange={(e) => setCfg({ ...cfg, monsoon: e.target.value || cfg.monsoon?.withdrawal ? { onset: e.target.value, withdrawal: cfg.monsoon?.withdrawal ?? "" } : null })} />
                </div>
                <div>
                  <Label htmlFor="m-off">{tr("Local withdrawal (MM-DD)")}</Label>
                  <Input id="m-off" value={cfg.monsoon?.withdrawal ?? ""} placeholder={data.monsoon?.withdrawal ?? "10-01"} maxLength={5}
                    onChange={(e) => setCfg({ ...cfg, monsoon: e.target.value || cfg.monsoon?.onset ? { onset: cfg.monsoon?.onset ?? "", withdrawal: e.target.value } : null })} />
                </div>
              </div>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title={tr("Seasons")} subtitle={tr("The most recent window of each, as of today")} icon={<CalendarDays className="size-4" />} />
          <ul className="divide-y divide-line text-sm">
            {data.seasons.map((s) => (
              <li key={s.key} className="px-4 py-2.5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-medium text-ink">{tr(s.label)}</span>
                  <span className="text-xs tabular-nums text-muted">{span(s.start, s.end)}</span>
                </div>
                <p className="mt-0.5 truncate text-xs text-subtle" title={s.names.join(", ")}>“{s.names.slice(0, 6).join("”, “")}”</p>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader title={tr("Festivals")} subtitle={tr("About a year back and four months ahead. Festivals of local importance are in bold; every date has a source.")} icon={<CalendarDays className="size-4" />} />
        <div className="grid gap-0 md:grid-cols-2 md:divide-x md:divide-line">
          <FestivalList title={tr("Coming up")} rows={coming} />
          <FestivalList title={tr("Past year")} rows={past} />
        </div>
      </Card>

      <LocalFestivals cfg={cfg} setCfg={setCfg} canEdit={canEdit} />

      <VisitDaysCard fid={fid} cfg={cfg} setCfg={setCfg} canEdit={canEdit} />

      <Card className="mt-4">
        <CardHeader title={tr("Sources")} subtitle={`${tr("Table version")} ${data.version}`} />
        <dl className="space-y-2 p-4 text-xs">
          {Object.entries(data.sources).map(([k, v]) => (
            <div key={k}>
              <dt className="font-mono text-subtle">{k}</dt>
              <dd className="text-muted">{v}</dd>
            </div>
          ))}
        </dl>
      </Card>

      {dirty && canEdit && (
        <div className="fixed inset-x-0 bottom-4 z-30 flex justify-center px-4">
          <div className="flex items-center gap-3 rounded-2xl border border-line bg-ink px-4 py-2.5 text-white shadow-[var(--shadow-pop)]">
            <span className="text-sm">{tr("Unsaved changes")}</span>
            <Button size="sm" variant="secondary" onClick={() => setCfg(data.region_config ?? {})}>{tr("Discard")}</Button>
            <Button size="sm" variant="teal" loading={saving} onClick={save}>{tr("Save")}</Button>
          </div>
        </div>
      )}
    </div>
  );
}

function FestivalList({ title, rows }: { title: string; rows: RegionCalendar["festivals"] }) {
  const { tr } = usePrefs();
  const [all, setAll] = useState(false);
  const shown = all ? rows : rows.slice(0, 12);
  return (
    <div>
      <p className="px-4 pt-3 text-xs font-semibold tracking-wide text-subtle uppercase">{title}</p>
      <ul className="divide-y divide-line text-sm">
        {shown.map((f) => (
          <li key={`${f.key}-${f.start}`} className="flex flex-wrap items-center gap-2 px-4 py-2">
            <span className={cx("text-ink", f.local && "font-semibold")}>{tr(f.label)}</span>
            {f.local && <Badge tone="teal">{tr(f.custom ? "this facility" : "local")}</Badge>}
            <span className="ml-auto text-xs tabular-nums text-muted">{span(f.start, f.end)}</span>
          </li>
        ))}
        {!rows.length && <li className="px-4 py-2 text-muted">—</li>}
      </ul>
      {rows.length > shown.length && (
        <button onClick={() => setAll(true)} className="px-4 py-2 text-xs font-medium text-teal-700 hover:underline">
          {tr("Show all")} ({rows.length})
        </button>
      )}
    </div>
  );
}

function LocalFestivals({ cfg, setCfg, canEdit }: { cfg: RegionConfig; setCfg: (c: RegionConfig) => void; canEdit: boolean }) {
  const { tr } = usePrefs();
  const [name, setName] = useState("");
  const [aliases, setAliases] = useState("");
  const [dates, setDates] = useState("");
  const list = cfg.festivals ?? [];
  const parsed = dates.split(/[,\s]+/).filter(Boolean);
  const ok = name.trim().length >= 2 && parsed.length > 0 && parsed.every((d) => /^\d{4}-\d{2}-\d{2}$/.test(d) && !Number.isNaN(Date.parse(d)));

  const add = () => {
    const f: LocalFestival = { name: name.trim(), aliases: aliases.split(",").map((a) => a.trim()).filter(Boolean), dates: parsed };
    setCfg({ ...cfg, festivals: [...list, f] });
    setName("");
    setAliases("");
    setDates("");
  };

  if (!canEdit && !list.length) return null;
  return (
    <Card className="mt-4">
      <CardHeader title={tr("This facility's own festivals")} subtitle={tr("A village fair or local deity's day that the state table does not have. Add its date for each year.")} icon={<Plus className="size-4" />} />
      {list.length > 0 && (
        <ul className="divide-y divide-line text-sm">
          {list.map((f, i) => (
            <li key={`${f.name}-${i}`} className="flex flex-wrap items-center gap-2 px-4 py-2.5">
              <span className="font-medium text-ink">{f.name}</span>
              {!!f.aliases?.length && <span className="text-xs text-muted">({f.aliases.join(", ")})</span>}
              <span className="ml-auto text-xs tabular-nums text-muted">{f.dates.map(day).join(" · ")}</span>
              {canEdit && (
                <button onClick={() => setCfg({ ...cfg, festivals: list.filter((_, j) => j !== i) })} className="text-subtle hover:text-crit" aria-label={`${tr("Remove")} ${f.name}`}>
                  <Trash2 className="size-4" />
                </button>
              )}
            </li>
          ))}
        </ul>
      )}
      {canEdit && (
        <div className="grid gap-3 border-t border-line p-4 sm:grid-cols-[1fr_1fr_1fr_auto] sm:items-end">
          <div>
            <Label htmlFor="lf-name">{tr("Name")}</Label>
            <Input id="lf-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Sital Sasthi" maxLength={40} />
          </div>
          <div>
            <Label htmlFor="lf-alias">{tr("Other names (comma-separated)")}</Label>
            <Input id="lf-alias" value={aliases} onChange={(e) => setAliases(e.target.value)} placeholder="ଶୀତଳ ଷଷ୍ଠୀ" />
          </div>
          <div>
            <Label htmlFor="lf-dates">{tr("Dates (YYYY-MM-DD)")}</Label>
            <Input id="lf-dates" value={dates} onChange={(e) => setDates(e.target.value)} placeholder="2026-06-20, 2027-06-09" />
          </div>
          <Button variant="secondary" icon={<Plus className="size-4" />} disabled={!ok} onClick={add}>{tr("Add")}</Button>
        </div>
      )}
    </Card>
  );
}

function TryPhrase({ fid, sources }: { fid: string; sources: Record<string, string> }) {
  const { tr } = usePrefs();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [r, setR] = useState<OnsetReading | null>(null);
  const samples = ["Cough since Diwali", "ରଜଠାରୁ ଜ୍ୱର", "होली के बाद से बुखार", "pain since the rains", "since Eid"];

  const run = async (t: string) => {
    setText(t);
    if (t.trim().length < 2) return;
    setBusy(true);
    try {
      setR(await api.tryOnset(fid, t.trim()));
    } catch (e) {
      toast(e instanceof Error ? e.message : tr("Failed"), "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card>
      <CardHeader title={tr("Try a phrase")} subtitle={tr("How a note at this facility would read it today. Nothing is saved.")} icon={<Search className="size-4" />} />
      <div className="space-y-3 p-4">
        <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); run(text); }}>
          <Input value={text} onChange={(e) => setText(e.target.value)} placeholder={tr("e.g. fever since the puja")} maxLength={300} aria-label={tr("Phrase to try")} />
          <Button type="submit" variant="teal" loading={busy} disabled={text.trim().length < 2}>{tr("Read")}</Button>
        </form>
        <div className="flex flex-wrap gap-1.5">
          {samples.map((s) => (
            <button key={s} onClick={() => run(s)} className="rounded-full border border-line px-2.5 py-1 text-xs text-muted hover:bg-canvas">{s}</button>
          ))}
        </div>
        {r && (
          <div className="rounded-xl border border-line bg-canvas p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={r.certainty === "STATED" ? "teal" : r.certainty === "VAGUE" ? "semi" : "neutral"}>{tr(r.certainty)}</Badge>
              <span className="font-semibold text-ink">{tr(r.when)}</span>
              {r.raw && <span className="text-xs text-muted">“{r.raw}”</span>}
            </div>
            {r.check && <p className="mt-1.5 text-ink-2">{r.check}</p>}
            {r.approx?.found && r.approx.source && <p className="mt-1 text-xs text-subtle">{tr("Source")}: {r.approx.source === "facility" ? tr("set by this facility") : sources[r.approx.source] ?? r.approx.source}</p>}
            {r.certainty === "VAGUE" && <p className="mt-1 text-xs text-subtle">{tr("Stays VAGUE: the rules never use this date.")}</p>}
          </div>
        )}
      </div>
    </Card>
  );
}

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const VISIT_KINDS: [VisitKind, string][] = [["anc_checkup", "Antenatal check-up"], ["chronic_checkin", "Chronic check-in"]];

/** E5: the days this facility holds each kind of follow-up visit. Follow-up dates move to the next such day. */
function VisitDaysCard({ fid, cfg, setCfg, canEdit }: { fid: string; cfg: RegionConfig; setCfg: (c: RegionConfig) => void; canEdit: boolean }) {
  const { tr } = usePrefs();
  const { data } = useAsync(() => api.visitDays(fid, "anc_checkup"), [fid, JSON.stringify(cfg.visits ?? null)]);
  if (!data) return null;
  const cal: VisitCalendar = { ...data.calendar, ...(cfg.visits ?? {}) };
  const set = (v: VisitCalendar) => setCfg({ ...cfg, visits: { ...cal, ...v } });
  const toggle = (list: number[] | null | undefined, d: number) => (list ?? []).includes(d) ? (list ?? []).filter((x) => x !== d) : [...(list ?? []), d].sort();
  return (
    <Card className="mt-4">
      <CardHeader title={tr("Visit days")} subtitle={tr("Which days this facility holds follow-up visits. A follow-up date is moved to the next such day, never earlier and never on a closed day.")} icon={<CalendarDays className="size-4" />} />
      <div className="space-y-4 p-4">
        {VISIT_KINDS.map(([k, label]) => (
          <div key={k}>
            <p className="text-sm font-semibold text-ink">{tr(label)}</p>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              {WEEKDAYS.map((w, i) => (
                <button key={w} type="button" disabled={!canEdit} aria-pressed={(cal[k]?.weekdays ?? []).includes(i)} onClick={() => set({ [k]: { ...cal[k], weekdays: toggle(cal[k]?.weekdays, i) } })}
                  className={cx("rounded-lg border px-2.5 py-1 text-xs font-semibold", (cal[k]?.weekdays ?? []).includes(i) ? "border-teal-600 bg-teal-50 text-teal-800" : "border-line text-ink-2")}>
                  {tr(w)}
                </button>
              ))}
              <label htmlFor={`vd-${k}`} className="ml-2 text-xs text-muted">{tr("and days of the month")}</label>
              <Input id={`vd-${k}`} disabled={!canEdit} className="h-8 w-28 text-sm" defaultValue={(cal[k]?.monthdays ?? []).join(", ")} placeholder="9"
                onBlur={(e) => set({ [k]: { ...cal[k], weekdays: cal[k]?.weekdays ?? [], monthdays: e.target.value.split(/[ ,]+/).map(Number).filter((n) => n >= 1 && n <= 28) } })} />
            </div>
          </div>
        ))}
        <div>
          <p className="text-sm font-semibold text-ink">{tr("Closed")}</p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {WEEKDAYS.map((w, i) => (
              <button key={w} type="button" disabled={!canEdit} aria-pressed={(cal.closed_weekdays ?? []).includes(i)} onClick={() => set({ closed_weekdays: toggle(cal.closed_weekdays, i) })}
                className={cx("rounded-lg border px-2.5 py-1 text-xs font-semibold", (cal.closed_weekdays ?? []).includes(i) ? "border-ink bg-canvas text-ink" : "border-line text-ink-2")}>
                {tr(w)}
              </button>
            ))}
          </div>
          <label htmlFor="vd-hol" className="mt-2 block text-xs text-muted">{tr("Holidays (YYYY-MM-DD, comma separated)")}</label>
          <Input id="vd-hol" disabled={!canEdit} className="h-9 text-sm" defaultValue={(cal.closed_dates ?? []).join(", ")}
            onBlur={(e) => set({ closed_dates: e.target.value.split(/[ ,]+/).filter((x) => /^\d{4}-\d{2}-\d{2}$/.test(x)) })} />
        </div>
        <p className="text-xs text-muted">{tr(data.rule)} · {tr("Next")}: {data.days.join(", ")}</p>
      </div>
    </Card>
  );
}
