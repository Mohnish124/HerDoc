/**
 * Health worker API helpers. Every call goes through apiFetch (in-memory access token,
 * cookie refresh) to existing worker-authorized endpoints; the backend scopes all data
 * to the signed-in worker's own patients.
 */
import { apiFetch } from './client';

// Same display text as the mobile risk engine (mobile/app/services/trend_engine.js ACTION_MAP).
export const RISK_ACTIONS = {
  green: 'Continue routine care',
  yellow: 'Recheck in 1 week',
  red: 'Refer to PHC within 24 hours',
};

// Client-generated UUIDs are the app's ID convention (the mobile app creates them offline too).
export function newId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  const bytes = globalThis.crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((b) => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

async function readJson(res, fallback) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data?.detail;
    if (Array.isArray(detail)) {
      // Validation errors: report field + message only (FastAPI echoes submitted values in "input").
      throw new Error(detail.map((e) => `${(e.loc || []).slice(1).join('.')}: ${e.msg}`).join('; '));
    }
    throw new Error(typeof detail === 'string' ? detail : fallback);
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

export function latestRisk(visit) {
  const flags = visit?.risk_flags || [];
  return flags.length ? flags[flags.length - 1] : null;
}
