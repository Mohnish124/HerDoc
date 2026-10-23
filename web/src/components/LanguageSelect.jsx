import React from 'react';
import { LANGUAGES } from '../i18n';
import { useI18n } from '../i18n/I18nContext';

// Language names are shown in their own script so a worker can find theirs whatever is selected.
export default function LanguageSelect({ className = '' }) {
  const { lang, setLang, t } = useI18n();
  return (
    <label className={`language-select ${className}`}>
      <span className="language-select-label">🌐 {t('language.label')}</span>
      <select value={lang} onChange={(e) => setLang(e.target.value)} aria-label={`${t('language.label')} / Language`}>
        {LANGUAGES.map((language) => (
          <option key={language.code} value={language.code} lang={language.code}>
            {language.label}
          </option>
        ))}
      </select>
    </label>
  );
}
