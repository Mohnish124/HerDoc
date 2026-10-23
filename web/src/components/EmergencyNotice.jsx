import React from 'react';
import { useI18n } from '../i18n/I18nContext';
import SosButton, { EMERGENCY_NUMBER } from './worker/SosButton';

// Calling 108 comes first; the SOS button only alerts the HerDoc emergency contact group (no dispatch).
export default function EmergencyNotice() {
  const { t } = useI18n();
  // Word order differs by language, so the number is placed where the translation puts {number}.
  const [before, after = ''] = t('emergency.body').split('{number}');
  return (
    <div className="emergency-notice" role="note">
      <p className="emergency-notice-text">
        <strong>{t('emergency.title')}</strong> {before}
        <a href={`tel:${EMERGENCY_NUMBER}`}>{EMERGENCY_NUMBER}</a>
        {after}
      </p>
      <SosButton />
    </div>
  );
}
