"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { getCachedUser, getTokens, setCachedUser, setTokens } from "@/lib/api/tokens";
import type { Tokens, User } from "@/lib/types";
import { translate, type DictKey } from "@/lib/i18n/dict";
import { loadPhrases, makeTr, type Phrases } from "@/lib/i18n/phrases";
import { installOutboxAutoFlush } from "@/lib/offline/outbox";
import { ToastHost } from "@/components/ui/toast";

/* ── Preferences: language + accessibility ─────────────── */

interface Prefs {
  lang: string;
  largeText: boolean;
  iconMode: boolean;
  readAloud: boolean;
}

interface PrefsCtx extends Prefs {
  set: (p: Partial<Prefs>) => void;
  /** Change the language everywhere; a signed-in user's choice is also saved to their account. */
  setLanguage: (lang: string) => void;
  t: (k: DictKey) => string;
  /** Translate an English UI phrase into the current language (falls back to English). */
  tr: (english: string | null | undefined, vars?: Record<string, string | number>) => string;
}

const PREFS_KEY = "jeevia.prefs";
const defaultPrefs: Prefs = { lang: "en", largeText: false, iconMode: false, readAloud: false };
const PrefsContext = createContext<PrefsCtx | null>(null);

export function usePrefs() {
  const c = useContext(PrefsContext);
  if (!c) throw new Error("usePrefs outside provider");
  return c;
}

/* ── Session ────────────────────────────────────────────── */

interface SessionCtx {
  user: User | null;
  loading: boolean;
  signIn: (tokens: Tokens, user: User) => void;
  signOut: () => Promise<void>;
  refresh: () => Promise<void>;
}

const SessionContext = createContext<SessionCtx | null>(null);

export function useSession() {
  const c = useContext(SessionContext);
  if (!c) throw new Error("useSession outside provider");
  return c;
}

function persist(next: Prefs): Prefs {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify(next));
  } catch {
    /* ignore */
  }
  return next;
}

export function Providers({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<Prefs>(defaultPrefs);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [phrases, setPhrases] = useState<Phrases>({});

  useEffect(() => {
    let live = true;
    loadPhrases(prefs.lang).then((p) => live && setPhrases(p), () => live && setPhrases({}));
    return () => {
      live = false;
    };
  }, [prefs.lang]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(PREFS_KEY);
      // Read after mount so server and first client render match (no hydration mismatch).
      // eslint-disable-next-line react-hooks/set-state-in-effect
      if (raw) setPrefs({ ...defaultPrefs, ...JSON.parse(raw) });
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    const root = document.documentElement;
    root.lang = prefs.lang;
    root.dataset.largeText = String(prefs.largeText);
    root.dataset.iconMode = String(prefs.iconMode);
  }, [prefs]);

  const set = useCallback((p: Partial<Prefs>) => {
    setPrefs((cur) => persist({ ...cur, ...p }));
  }, []);

  /** Each signed-in person gets their own saved language on every screen (kiosk sessions keep the kiosk's). */
  const applyUserLanguage = useCallback((u: User) => {
    if (u.role !== "kiosk" && u.language) setPrefs((cur) => (cur.lang === u.language ? cur : persist({ ...cur, lang: u.language })));
  }, []);

  const refresh = useCallback(async () => {
    if (!getTokens()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const u = await api.me();
      setCachedUser(u);
      setUser(u);
      applyUserLanguage(u);
    } catch (e) {
      // Offline (no HTTP status): keep the last known user so offline kiosks keep working.
      setUser((e as { status?: number }).status ? null : getCachedUser());
    } finally {
      setLoading(false);
    }
  }, [applyUserLanguage]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refresh();
  }, [refresh]);

  useEffect(() => {
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") {
      navigator.serviceWorker.register("/sw.js").catch(() => {});
    }
    return installOutboxAutoFlush();
  }, []);

  const session = useMemo<SessionCtx>(
    () => ({
      user,
      loading,
      signIn: (tokens, u) => {
        setTokens(tokens);
        setCachedUser(u);
        setUser(u);
        applyUserLanguage(u);
      },
      signOut: async () => {
        await api.logout();
        setUser(null);
      },
      refresh,
    }),
    [user, loading, refresh, applyUserLanguage],
  );

  const setLanguage = useCallback(
    (lang: string) => {
      set({ lang });
      // A patient choosing a language on a shared kiosk must not change the unlocking staff member's own preference.
      const onKiosk = typeof window !== "undefined" && /^\/(kiosk|k\/)/.test(window.location.pathname);
      if (user && user.role !== "kiosk" && !onKiosk && user.language !== lang) {
        api.updateMe({ language: lang }).then(
          (u) => {
            setCachedUser(u);
            setUser(u);
          },
          () => {},
        );
      }
    },
    [set, user],
  );

  const prefsValue = useMemo<PrefsCtx>(() => ({ ...prefs, set, setLanguage, t: (k) => translate(prefs.lang, k), tr: makeTr(phrases) }), [prefs, set, setLanguage, phrases]);

  return (
    <PrefsContext.Provider value={prefsValue}>
      <SessionContext.Provider value={session}>
        {children}
        <ToastHost />
      </SessionContext.Provider>
    </PrefsContext.Provider>
  );
}
