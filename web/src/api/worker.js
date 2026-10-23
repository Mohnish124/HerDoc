/**
 * Health worker API helpers. Every call goes through apiFetch (in-memory access token,
 * cookie refresh) to existing worker-authorized endpoints; the backend scopes all data
 * to the signed-in worker's own patients.
 */
import { apiFetch } from './client';

// Client-generated UUIDs are the app's ID convention (the mobile app creates them offline too).
export function newId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((b) => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

// Errors keep the server's message separate so the UI can show it in the worker's language
// (see src/i18n/errors.js).
async function readJson(res, fallback) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data?.detail;
    const error = new Error(typeof detail === 'string' ? detail : fallback);
    if (Array.isArray(detail)) {
      // Validation errors: report field + message only (FastAPI echoes submitted values in "input").
      error.validation = detail.map((e) => `${(e.loc || []).slice(1).join('.')}: ${e.msg}`).join('; ');
    } else if (typeof detail === 'string') {
      error.detail = detail;
    }
    throw error;
  }
  return data;
}

export async function listMyPatients() {
  return readJson(await apiFetch('/api/patients'), 'Could not load your patients.');
}

export async function getPatient(patientId) {
  return readJson(await apiFetch(`/api/patients/${patientId}`), 'Could not load this patient.');
}

export async function listVisits(patientId) {
  return readJson(await apiFetch(`/api/patients/${patientId}/visits`), 'Could not load visits.');
}

export async function registerPatient({ name, age, village, edd, phone }) {
  const body = { id: newId(), name, age: Number(age), village, edd, phone: phone || null };
  return readJson(await apiFetch('/api/patients', { method: 'POST', body: JSON.stringify(body) }), 'Could not register the patient.');
}

/**
 * Save a visit with its risk flag. `ids` must stay the same across retries of one submission:
 * the visit endpoint is idempotent by id, so a retry after a dropped response cannot duplicate it.
 */
export async function recordVisit({ patientId, workerId, vitals, classification, ids, now }) {
  const body = {
    id: ids.visitId,
    patient_id: patientId,
    worker_id: workerId,
    visit_date: now.toISOString(),
    systolic_bp: Number(vitals.systolic_bp),
    diastolic_bp: Number(vitals.diastolic_bp),
    blood_sugar: Number(vitals.blood_sugar),
    body_temp_c: Number(vitals.body_temp_c),
    heart_rate: Number(vitals.heart_rate),
    created_locally_at: now.toISOString(),
    risk_flags: [
      {
        id: ids.flagId,
        model_risk_level: classification.model_risk_level,
        trend_adjusted_level: classification.trend_adjusted_level,
        trend_reason: classification.trend_reason,
      },
    ],
  };
  return readJson(
    await apiFetch(`/api/patients/${patientId}/visits`, { method: 'POST', body: JSON.stringify(body) }),
    'Could not save the visit.',
  );
}

/** Latest doctor review per patient, via the existing worker sync endpoint with an empty batch (no writes). */
export async function fetchLatestReviews() {
  const res = await apiFetch('/api/sync', {
    method: 'POST',
    body: JSON.stringify({ patients: [], visits: [], risk_flags: [], last_synced_at: null }),
  });
  const data = await readJson(res, 'Could not load doctor reviews.');
  const latest = {};
  for (const review of data.reviews || []) {
    const current = latest[review.patient_id];
    if (!current || String(review.reviewed_at) > String(current.reviewed_at)) latest[review.patient_id] = review;
  }
  return latest;
}

// ---------------------------------------------------------------- Emergency SOS

export const SOS_TIMEOUT_MS = 30000;
// The web portal does not collect location; the existing endpoint's optional note says so to the recipients.
export const WEB_SOS_NOTE = 'Sent from the HerDoc web portal. Location not included.';
let sosInFlight = null;

/**
 * Ask the existing POST /api/emergency endpoint to relay an alert (backend Telegram service).
 * Resolves to { kind } where kind is one of:
 *   sent            server confirmed delivery ({status: "sent"}) — the ONLY success
 *   notConfigured   503: alerts not set up on the server, nothing sent
 *   failed          502: the server could not deliver it
 *   unconfirmed     timed out, or any other/unexpected reply: delivery unknown
 *   offline         the server could not be reached
 *   sessionExpired  401 / refresh failed: not sent
 *   forbidden       403: not sent
 * A second call while one is pending returns the same promise, so repeated clicks send one request.
 */
export function sendEmergencyAlert({ timeoutMs = SOS_TIMEOUT_MS } = {}) {
  if (!sosInFlight) {
    sosInFlight = requestEmergencyAlert(timeoutMs).finally(() => {
      sosInFlight = null;
    });
  }
  return sosInFlight;
}

async function requestEmergencyAlert(timeoutMs) {
  const controller = new AbortController();
  let timer;
  // Bounds the whole attempt, including any token refresh inside apiFetch.
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => {
      controller.abort();
      reject(Object.assign(new Error('timeout'), { sosTimeout: true }));
    }, timeoutMs);
  });
  try {
    const res = await Promise.race([
      apiFetch('/api/emergency', { method: 'POST', body: JSON.stringify({ message: WEB_SOS_NOTE }), signal: controller.signal }),
      timeout,
    ]);
    const data = await Promise.race([res.json().catch(() => ({})), timeout]);
    if (res.ok && data?.status === 'sent') return { kind: 'sent' };
    if (res.status === 503) return { kind: 'notConfigured' };
    if (res.status === 502) return { kind: 'failed' };
    if (res.status === 401) return { kind: 'sessionExpired' };
    if (res.status === 403) return { kind: 'forbidden' };
    return { kind: 'unconfirmed' };
  } catch (error) {
    if (error?.sosTimeout || error?.name === 'AbortError') return { kind: 'unconfirmed' }; // may still have been processed
    if (/session expired/i.test(error?.message || '')) return { kind: 'sessionExpired' };
    return { kind: 'offline' };
  } finally {
    clearTimeout(timer);
  }
}

export function latestRisk(visit) {
  const flags = visit?.risk_flags || [];
  return flags.length ? flags[flags.length - 1] : null;
}
