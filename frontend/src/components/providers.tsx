"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { getTokens, setTokens } from "@/lib/api/tokens";
import type { Tokens, User } from "@/lib/types";
import { translate, type DictKey } from "@/lib/i18n/dict";
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
  t: (k: DictKey) => string;
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

export function Providers({ children }: { children: ReactNode }) {
  const [prefs, setPrefs] = useState<Prefs>(defaultPrefs);
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

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
    setPrefs((cur) => {
      const next = { ...cur, ...p };
      try {
        localStorage.setItem(PREFS_KEY, JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);

  const refresh = useCallback(async () => {
    if (!getTokens()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      setUser(await api.me());
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

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
        setUser(u);
      },
      signOut: async () => {
        await api.logout();
        setUser(null);
      },
      refresh,
    }),
    [user, loading, refresh],
  );

  const prefsValue = useMemo<PrefsCtx>(() => ({ ...prefs, set, t: (k) => translate(prefs.lang, k) }), [prefs, set]);

  return (
    <PrefsContext.Provider value={prefsValue}>
      <SessionContext.Provider value={session}>
        {children}
        <ToastHost />
      </SessionContext.Provider>
    </PrefsContext.Provider>
  );
}
