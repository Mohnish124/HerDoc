import React from 'react';
import { useI18n } from '../i18n/I18nContext';

const EMERGENCY_NUMBER = '108';

// Information only: the web portal does not send emergency alerts or dispatch help.
export default function EmergencyNotice() {
  const { t } = useI18n();
  // Word order differs by language, so the number is placed where the translation puts {number}.
  const [before, after = ''] = t('emergency.body').split('{number}');
  return (
    <div className="emergency-notice" role="note">
      <strong>{t('emergency.title')}</strong> {before}
      <a href={`tel:${EMERGENCY_NUMBER}`}>{EMERGENCY_NUMBER}</a>
      {after}
    </div>
  );
}
