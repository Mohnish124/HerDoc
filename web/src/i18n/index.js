/**
 * Lightweight i18n for the health worker interface (no external library, no network calls).
 *
 * Adding a language: create locales/<code>.js with the same keys as en.js, then add one entry
 * to LANGUAGES. `npm run check:i18n` reports missing or extra keys.
 *
 * Only presentation is translated. API fields, stored records, risk codes (green/yellow/red)
 * and review status codes stay as the backend sends them.
 */
import en from './locales/en';
import hi from './locales/hi';
import mr from './locales/mr';

export const LANGUAGES = [
  { code: 'en', label: 'English', dictionary: en },
  { code: 'mr', label: 'मराठी', dictionary: mr },
  { code: 'hi', label: 'हिन्दी', dictionary: hi },
];

export const DEFAULT_LANGUAGE = 'en';
// Only the language code is stored on the device; never patient data.
export const LANGUAGE_STORAGE_KEY = 'herdoc.workerLanguage';

const BY_CODE = Object.fromEntries(LANGUAGES.map((language) => [language.code, language]));

export function isSupportedLanguage(code) {
  return Boolean(BY_CODE[code]);
}

/**
 * Translate `key` into `lang`, falling back to English and finally the key itself.
 * `{name}` placeholders are replaced from `params`. `onMissing(lang, key)` is called when a
 * language lacks a key (used by the checks).
 */
export function translate(lang, key, params, onMissing) {
  const dictionary = BY_CODE[lang]?.dictionary || en;
  let text = dictionary[key];
  if (text === undefined) {
    onMissing?.(lang, key);
    text = en[key] ?? key;
  }
  if (params) {
    text = text.replace(/\{(\w+)\}/g, (match, name) => (params[name] === undefined || params[name] === null ? match : String(params[name])));
  }
  return text;
}

// Exact English trend messages produced by mobile/app/services/trend_engine.js and stored with
// each risk flag. Known messages are shown translated; anything else is shown as stored.
export const TREND_REASON_KEYS = {
  'Blood pressure and blood sugar have risen steadily over your last 3 visits.': 'risk.trend.bpAndSugar',
  'Blood pressure has risen steadily over your last 3 visits.': 'risk.trend.bp',
  'Blood sugar has risen steadily over your last 3 visits.': 'risk.trend.sugar',
};

export const RISK_LEVELS = ['green', 'yellow', 'red'];
export const REVIEW_STATUSES = ['pending', 'approved', 'rejected', 'reviewed', 'referred'];
