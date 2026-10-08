import React, { useCallback, useEffect, useState } from 'react';
import { adminTokenStore } from '../services/adminTokenStore';
import { THEME_ORDER, isDarkTheme } from './ThemeConstants';
import { ThemeContext } from './ThemeContext';
import type { Theme } from './ThemeConstants';
import { apiClient } from '../services/apiClient';
import { eventBus, Events } from '../lib/componentEventBus';

// বাংলা মন্তব্য: ThemeContext একে অপর ফাইল থেকে ইম্পোর্ট করা হয়েছে, যাতে react-refresh সতর্কতা দূর হয়
// useTheme hook একে অপর ফাইলে সরানো হয়েছে (useTheme.ts)
export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // বাংলা: setThemeState = React-এর raw setter; context-এর setTheme আলাদা
  // (applyTheme-ভিত্তিক) — নাম-সংঘর্ষ এড়াতে রিনেম করা হয়েছে।
  const [theme, setThemeState] = useState<Theme>('dark'); // ডিফল্ট Deep Space (dark)

  useEffect(() => {
    // বাংলা মন্তব্য: Race Condition এড়াতে AbortController ব্যবহার করা হয়েছে
    const controller = new AbortController();
    const token = adminTokenStore.getDecodedToken();
    const storageKey = 'supremeai-theme-storage';
    const stored = localStorage.getItem(storageKey);
    const legacy = localStorage.getItem('supremeai_theme');
    const localTheme = stored ? JSON.parse(stored)?.state?.theme : legacy;
    if (localTheme && THEME_ORDER.includes(localTheme as Theme)) {
      setThemeState(localTheme as Theme);
      localStorage.removeItem('supremeai_theme');
    }

    const loadTheme = async () => {
      if (!token) return;
      try {
        const response = await apiClient.get<{ theme?: string; data?: { theme?: string } }>('/api/preferences/', { signal: controller.signal });
        const remoteTheme = response.data?.theme || response.theme;
        if (remoteTheme && THEME_ORDER.includes(remoteTheme as Theme)) {
          setThemeState(remoteTheme as Theme);
        }
      } catch (err: unknown) {
        const error = err as { name?: string };
        if (error?.name !== 'AbortError' && error?.name !== 'CanceledError') console.error('Theme sync failed:', err);
      }
    };

    loadTheme();

    const unsub = eventBus.subscribe(Events.THEME_CHANGED, (data: unknown) => {
      const payload = data as { theme?: string } | undefined;
      if (payload?.theme && THEME_ORDER.includes(payload.theme as Theme)) setThemeState(payload.theme as Theme);
    });

    return () => {
      controller.abort();
      unsub();
    }; // কম্পোনেন্ট আনমাউন্ট হলে রিকোয়েস্ট বাতিল
  }, []);

  useEffect(() => {
    // বাংলা মন্তব্য: HTML root ও body এলিমেন্টে থিম ক্লাস অ্যাড করা হচ্ছে
    // (#4138): ক্লাস-তালিকা আর হার্ডকোড নয় — THEME_ORDER-ই SSOT (8 থিম)।
    const root = window.document.documentElement;
    const body = window.document.body;
    const classes = THEME_ORDER;
    root.classList.remove(...classes);
    root.classList.add(theme);
    root.setAttribute('data-theme', theme);
    if (body) {
      body.classList.remove(...classes);
      body.classList.add(theme);
      body.setAttribute('data-theme', theme);
    }
  }, [theme]);

  // বাংলা (#4138 Phase 1 follow-up): একটাই applyTheme — toggleTheme ও setTheme
  // দুজনেই এটাই ব্যবহার করে, তাই persist + backend-sync + eventBus emit-এর
  // প্রতিটি পথে একই আচরণ নিশ্চিত (আগে শুধু toggle-পথে ছিল)।
  const applyTheme = useCallback((newTheme: Theme) => {
    // Optimistic UI Update
    setThemeState(newTheme);
    localStorage.setItem('supremeai-theme-storage', JSON.stringify({ state: { theme: newTheme }, version: 0 }));
    localStorage.removeItem('supremeai_theme');

    // ব্যাকএন্ডে async সিঙ্ক করা
    // ERR-H01 FIX: real backend route is POST /api/preferences/ (mounted at
    // prefix /api + router /preferences) — /api/v1/preferences never existed (404).
    // Issue #2475: canonical mounted path carries a trailing slash — call it
    // exactly so the request no longer depends on FastAPI's 307 redirect.
    apiClient.post('/api/preferences/', { theme: newTheme })
      .catch(err => console.error('Failed to sync theme to DB:', err));

    // (#4138): isDark এখন THEME_META থেকে — নতুন থিম যোগ হলে এখানে আর
    // ভুল হার্ডকোড থাকবে না (Config > Hardcoded)।
    eventBus.emit(Events.THEME_CHANGED, {
      theme: newTheme,
      isDark: isDarkTheme(newTheme),
      timestamp: Date.now(),
      source: 'theme_provider',
    });
  }, []);

  const toggleTheme = useCallback(() => {
    // বাংলা মন্তব্য: পরবর্তী থিমে সাইকেল — THEME_ORDER (dark → light → synthwave →
    // cyberpunk → minimal → sunset → matrix → emerald → dark), ৮ থিম।
    const currentIndex = THEME_ORDER.indexOf(theme);
    const nextIndex = (currentIndex + 1) % THEME_ORDER.length;
    applyTheme(THEME_ORDER[nextIndex]);
  }, [theme, applyTheme]);

  const setTheme = useCallback((next: Theme) => {
    // বাংলা: অজানা মান এলে নীরবে উপেক্ষা — fail-safe (THEME_ORDER-ই SSOT)।
    if (!THEME_ORDER.includes(next)) return;
    applyTheme(next);
  }, [applyTheme]);

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};
