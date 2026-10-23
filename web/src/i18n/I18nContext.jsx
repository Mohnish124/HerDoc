import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { DEFAULT_LANGUAGE, LANGUAGE_STORAGE_KEY, TREND_REASON_KEYS, isSupportedLanguage, translate } from './index';

const I18nContext = createContext(null);

// Missing keys fall back to English (see translate); in development they are also reported.
const warnMissingInDev = import.meta.env.DEV
  ? (lang, key) => console.warn(`[i18n] missing "${key}" for "${lang}"; showing English`)
  : undefined;

function readStoredLanguage() {
  try {
    const stored = window.localStorage.getItem(LANGUAGE_STORAGE_KEY);
    return isSupportedLanguage(stored) ? stored : DEFAULT_LANGUAGE;
  } catch {
    return DEFAULT_LANGUAGE; // storage blocked (private mode, SSR): use the default
  }
}

export function I18nProvider({ children, initialLanguage, onMissing = warnMissingInDev }) {
  const [lang, setLangState] = useState(() =>
    isSupportedLanguage(initialLanguage) ? initialLanguage : readStoredLanguage(),
  );

  const setLang = useCallback((next) => {
    if (!isSupportedLanguage(next)) return;
    setLangState(next);
    try {
      window.localStorage.setItem(LANGUAGE_STORAGE_KEY, next);
    } catch {
      // Not persisted when storage is unavailable; the choice still applies for this visit.
    }
  }, []);

  const value = useMemo(() => {
    const t = (key, params) => translate(lang, key, params, onMissing);
    return {
      lang,
      setLang,
      t,
      // Stored trend messages are English; show a translation only for the known engine messages.
      trendReason: (reason) => (reason && TREND_REASON_KEYS[reason] ? t(TREND_REASON_KEYS[reason]) : reason),
    };
  }, [lang, setLang, onMissing]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n() {
  const context = useContext(I18nContext);
  if (!context) {
    throw new Error('useI18n must be used within an I18nProvider');
  }
  return context;
}
