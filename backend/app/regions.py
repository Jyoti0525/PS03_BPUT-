"""Regional calendar and worker cadres (F5): `regions.yaml` plus each facility's own overrides.

A patient who dates an illness by a festival or season ("since Diwali", "ରଜଠାରୁ", "after the rains") gets the
approximate date or window shown next to their words. The onset stays VAGUE and its `days` stay empty, so the rules
never use it; the note asks staff to confirm the date. Two rules from the plan: never turn a vague reference into a
precise date silently, and always keep the patient's phrase.

The same table names the facility's front-line workers (ASHA, ANM, Mitanin, Sahiya, VHN…), so the app uses the
names staff actually use in that state.
"""

import functools
import re
from datetime import date, timedelta
from pathlib import Path

import yaml

CADRE_KEYS = ("community", "nurse", "nutrition", "male", "cho")
_FILE = Path(__file__).with_name("regions.yaml")


@functools.cache
def table() -> dict:
    return yaml.safe_load(_FILE.read_text(encoding="utf-8"))


def _span(v) -> tuple[date, date]:
    return (v[0], v[1]) if isinstance(v, list) else (v, v)


def _md(year: int, mmdd: str) -> date:
    m, d = map(int, mmdd.split("-"))
    return date(year, m, min(d, 28) if (m, d) == (2, 29) else d)


def fmt(d: date) -> str:
    return f"{d.day} {d:%b %Y}"


def fmt_range(s: date, e: date) -> str:
    if s == e:
        return fmt(s)
    if (s.year, s.month) == (e.year, e.month):
        return f"{s.day}–{e.day} {e:%b %Y}"
    if s.year == e.year:
        return f"{s.day} {s:%b} – {fmt(e)}"
    return f"{fmt(s)} – {fmt(e)}"


def _ago(days: int) -> str:
    if days < 14:
        return f"about {days} day{'s' if days != 1 else ''} ago"
    if days < 60:
        return f"about {round(days / 7)} weeks ago"
    return f"about {round(days / 30.4)} months ago"


def _latin(s: str) -> bool:
    return all(ord(c) < 0x250 for c in s)


def _alt(words) -> str:
    return "|".join(re.escape(w).replace(r"\ ", r"\s+") for w in sorted(set(words), key=len, reverse=True))


class Calendar:
    """The calendar for one facility: its state's table entry with the facility's overrides on top."""

    def __init__(self, state: str | None = None, facility_type: str | None = None, config: dict | None = None):
        t = table()
        self.state = state if state in t["regions"] else None
        reg = t["regions"].get(state) or t["default"]
        cfg = config or {}
        monsoon = {**(reg.get("monsoon") or {}), **{k: v for k, v in (cfg.get("monsoon") or {}).items() if v}}
        if (cfg.get("monsoon") or {}).get("onset"):
            monsoon["station"] = "set by this facility"
        self.monsoon = monsoon if monsoon.get("onset") else None
        self.northeast = bool(reg.get("northeast"))
        self.local = list(reg.get("local") or [])

        self.festivals: dict[str, dict] = dict(t["festivals"])
        for i, f in enumerate(cfg.get("festivals") or []):
            key = f"custom_{i}"
            dates = {}
            for d in f.get("dates") or []:
                d = date.fromisoformat(str(d))
                dates[d.year] = d
            self.festivals[key] = {"label": f["name"], "faith": f.get("faith") or "", "names": [f["name"], *(f.get("aliases") or [])],
                                   "dates": dates, "source": "facility", "custom": True}
            self.local.insert(0, key)
        self.seasons: dict[str, dict] = dict(t["seasons"])

        # word (lower-case) → festival or season keys. Later entries win: national names, then shared ambiguous words,
        # then what this region means by a word, then the facility's own festivals.
        self.words: dict[str, tuple[str, list[str]]] = {}
        for key, f in self.festivals.items():
            for n in f["names"]:
                self.words[n.lower()] = ("festival", [key])
        for key, s in self.seasons.items():
            for n in s["names"]:
                self.words[n.lower()] = ("season", [key])
        for w, keys in {**(t.get("ambiguous") or {}), **(reg.get("ambiguous") or {})}.items():
            self.words[w.lower()] = ("festival", list(keys))
        for w, key in (reg.get("aliases") or {}).items():
            self.words[w.lower()] = ("festival", [key])
        for i, f in enumerate(cfg.get("festivals") or []):
            for n in [f["name"], *(f.get("aliases") or [])]:
                self.words[n.lower()] = ("festival", [f"custom_{i}"])

        latin = [w for w in self.words if _latin(w)]
        indic = [w for w in self.words if not _latin(w)]
        before, after = t["before"], t["after"]
        after_latin = [a for a in after if _latin(a)]
        after_indic = [a for a in after if not _latin(a)]
        self._rx = [
            re.compile(rf"\b(?:{_alt(before)})\s+(?:the\s+|last\s+|this\s+|last\s+year'?s?\s+)?({_alt(latin)})\b", re.I),
            re.compile(rf"\b({_alt(latin)})\s+(?:{_alt(after_latin)})\b", re.I),
            re.compile(rf"({_alt(indic)})\s*(?:{_alt(after_indic)})"),
        ]

        self.cadres = {k: {**v, "source": "National Health Mission"} for k, v in t["cadres"].items()}
        for k, v in (reg.get("cadres") or {}).items():
            self.cadres[k] = {**v, "source": f"{state} state programme"}
        for k, v in ((t.get("facility_type_cadres") or {}).get(facility_type) or {}).items():
            self.cadres[k] = {**v, "source": "workplace or campus facility"}
        for k, v in (cfg.get("cadres") or {}).items():
            if v:
                self.cadres[k] = {"en": v, "full": v, "source": "set by this facility"}

    # ── matching ───────────────────────────────────────
    def match(self, text: str) -> tuple[str, str, list[str]] | None:
        """(the patient's phrase, 'festival' | 'season', keys) for the first festival or season used as a time."""
        hits = [(m.start(), m) for rx in self._rx if (m := rx.search(text))]
        if not hits:
            return None
        m = min(hits, key=lambda h: h[0])[1]
        kind, keys = self.words[re.sub(r"\s+", " ", m.group(1).lower())]
        return m.group(0).strip(), kind, keys

    # ── dates ──────────────────────────────────────────
    def _festival(self, key: str, on: date) -> tuple[date, date] | None:
        dates = self.festivals[key]["dates"]
        if on.year in dates:
            s, e = _span(dates[on.year])
            if s <= on:
                return s, e
        elif on.year - 1 in dates:
            # This year's date is not in the table, so it may already have passed. Last year's is safe only while we
            # are clearly before this year's (lunar dates move by up to about three weeks).
            s, _ = _span(dates[on.year - 1])
            if on >= _md(on.year, f"{s.month:02d}-{s.day:02d}") - timedelta(days=21):
                return None
        if on.year - 1 in dates:
            return _span(dates[on.year - 1])
        return None

    def _window(self, key: str, on: date) -> tuple[date, date] | None:
        s = self.seasons[key]
        if key == "monsoon":
            if not self.monsoon:
                return None
            a, b = self.monsoon["onset"], self.monsoon["withdrawal"]
        else:
            a, b = s["window"]
        for y in (on.year, on.year - 1):
            start = _md(y, a)
            end = _md(y + 1 if b < a else y, b)
            if start <= on:
                return start, end
        return None

    def _one(self, kind: str, key: str, on: date) -> dict | None:
        spec = (self.festivals if kind == "festival" else self.seasons)[key]
        got = self._festival(key, on) if kind == "festival" else self._window(key, on)
        if not got:
            return None
        start, end = got
        return {"kind": kind, "key": key, "label": spec["label"], "start": start.isoformat(), "end": end.isoformat(),
                "days_ago": (on - start).days, "ongoing": start <= on <= end and start != end, "source": spec.get("source", ""),
                "regional": kind == "season" and key in ("monsoon", "northeast_monsoon")}

    def resolve(self, kind: str, keys: list[str], on: date) -> dict:
        """The most recent occurrence on or before `on`. {'found': False, 'reason'} when the calendar cannot say."""
        if kind == "season" and len(keys) == 1 and (either := self.seasons[keys[0]].get("either")):
            keys = list(either)
        if kind == "season" and keys == ["monsoon"] and self.northeast:
            keys = ["monsoon", "northeast_monsoon"]  # "the rains" in Tamil Nadu or Kerala: either monsoon
        found = [r for k in keys if (r := self._one(kind, k, on))]
        if not found:
            spec = (self.festivals if kind == "festival" else self.seasons)[keys[0]]
            if kind == "season" and keys[0] == "monsoon" and not self.monsoon:
                reason = "the facility's state is not set, so monsoon dates are unknown"
            else:
                reason = f"the {on.year} date of {spec['label']} is not in the regional calendar yet"
            return {"found": False, "label": spec["label"], "reason": reason}
        found.sort(key=lambda r: r["start"], reverse=True)
        best = {**found[0], "found": True, "region": self.state}
        # Other readings worth asking about: within about seven months of the most recent one.
        near = [r for r in found[1:] if (date.fromisoformat(best["start"]) - date.fromisoformat(r["start"])).days <= 200]
        if near:
            best["others"] = [{"label": r["label"], "start": r["start"], "end": r["end"]} for r in near]
        return best

    def describe(self, raw: str, r: dict) -> tuple[str, str]:
        """(when, check) for the note."""
        if not r["found"]:
            return "Not clear", f'Onset given only as "{raw}" — {r["reason"]}; ask for an approximate date'
        s, e = date.fromisoformat(r["start"]), date.fromisoformat(r["end"])
        where = f" in {r['region']}" if r.get("region") and r.get("regional") else ""
        if s == e:
            when = f"Around {fmt(s)} ({r['label']})"
            said = f"{r['label']} was on {fmt(s)}, {_ago(r['days_ago'])}"
        else:
            when = f"{r['label']}{where}: {fmt_range(s, e)}"
            said = f"{r['label']}{where} {'began ' + fmt(s) if r['ongoing'] else 'was ' + fmt_range(s, e)}, {_ago(r['days_ago'])}"
        check = f'Onset given only as "{raw}" — {said}'
        if r.get("others"):
            check += "; or " + ", ".join(f"{o['label']} ({fmt_range(date.fromisoformat(o['start']), date.fromisoformat(o['end']))})" for o in r["others"]) + " — ask which"
        return when, check + "; confirm with the patient"

    # ── views ──────────────────────────────────────────
    def cadre(self, key: str, lang: str = "en") -> str:
        c = self.cadres[key]
        return c.get(lang) or c["en"]

    def summary(self) -> dict:
        return {"state": self.state, "cadres": self.cadres, "monsoon": self.monsoon, "northeast": self.northeast}

    def view(self, on: date) -> dict:
        """Festivals from about a year before `on` to four months after, and the latest window of each season."""
        lo, hi = on - timedelta(days=400), on + timedelta(days=120)
        rows = []
        for key, f in self.festivals.items():
            for y, v in f["dates"].items():
                s, e = _span(v)
                if lo <= s <= hi:
                    rows.append({"key": key, "label": f["label"], "faith": f.get("faith", ""), "start": s.isoformat(), "end": e.isoformat(),
                                 "source": f.get("source", ""), "local": key in self.local, "custom": bool(f.get("custom")), "past": s <= on})
        rows.sort(key=lambda r: r["start"])
        seasons = []
        for key, s in self.seasons.items():
            if s.get("either") or (key == "northeast_monsoon" and not self.northeast):
                continue
            w = self._one("season", key, on)
            seasons.append({"key": key, "label": w["label"] if w else s["label"], "start": w and w["start"], "end": w and w["end"],
                            "source": w["source"] if w else s.get("source", ""), "names": s["names"][:8],
                            "station": (self.monsoon or {}).get("station") if key == "monsoon" else None})
        t = table()
        return {"state": self.state, "as_of": on.isoformat(), "version": t["version"], "festivals": rows, "seasons": seasons,
                "cadres": self.cadres, "monsoon": self.monsoon, "northeast": self.northeast, "sources": t["sources"]}


@functools.lru_cache(maxsize=256)
def _cached(state: str | None, ftype: str | None, cfg_key: str) -> Calendar:
    import json

    return Calendar(state, ftype, json.loads(cfg_key) if cfg_key else None)


def for_facility(f) -> Calendar:
    """The calendar for a Facility row (or anything with state, type and region_config)."""
    import json

    if f is None:
        return _cached(None, None, "")
    cfg = getattr(f, "region_config", None)
    return _cached(f.state, f.type, json.dumps(cfg, sort_keys=True, default=str) if cfg else "")
