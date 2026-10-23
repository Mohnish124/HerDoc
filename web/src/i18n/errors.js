// Map known backend/network error messages (English, from the API) to translation keys.
// Unknown server messages are shown after a translated summary so nothing is hidden.
const KNOWN_ERRORS = [
  [/^invalid (credentials|phone number or pin)/i, 'errors.invalidCredentials'],
  [/^account (is )?locked/i, 'errors.locked'],
  [/^too many login attempts/i, 'errors.tooManyAttempts'],
  [/deactivated/i, 'errors.deactivated'],
  [/unreachable|failed to fetch|networkerror|load failed/i, 'errors.network'],
  [/session expired/i, 'errors.sessionExpired'],
  [/belongs to another worker/i, 'errors.notYourPatient'],
  [/^patient not found/i, 'errors.patientNotFound'],
];

/**
 * @param {Function} t translate function
 * @param {Error & {detail?: string, validation?: string}} error
 * @param {string} fallbackKey translation key describing what failed
 */
export function errorText(t, error, fallbackKey) {
  if (error?.validation) return t('errors.validation', { detail: error.validation });
  const message = String(error?.detail || error?.message || '');
  for (const [pattern, key] of KNOWN_ERRORS) {
    if (pattern.test(message)) return t(key);
  }
  return error?.detail ? `${t(fallbackKey)} (${error.detail})` : t(fallbackKey);
}
