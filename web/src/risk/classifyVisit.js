/**
 * Risk classification for the worker web portal.
 *
 * Reuses the mobile app's on-device model and trend engine unchanged (single source of truth),
 * and builds their inputs exactly as mobile/app/screens/NewVisitScreen.jsx does. This module pulls in
 * the ~750 KB model bundle, so pages load it with a dynamic import() only when a visit is recorded.
 */
import { predictMaternalRisk } from '../../../mobile/app/services/inference.js';
import { calculateTrendAdjustment } from '../../../mobile/app/services/trend_engine.js';

/**
 * @param {Object} args
 * @param {number|undefined} args.patientAge
 * @param {{systolic_bp:number, diastolic_bp:number, blood_sugar:number, body_temp_c:number, heart_rate:number}} args.vitals
 * @param {Array<Object>} args.priorVisits  Visits already saved for the patient (API shape).
 * @param {Date} args.now
 * @returns {{model_risk_level:string, trend_adjusted_level:string, trend_reason:string|null, action:string, escalated:boolean}}
 */
export function classifyVisit({ patientAge, vitals, priorVisits, now }) {
  const currentVisitData = {
    visit_date: now.toISOString().split('T')[0],
    systolic_bp: Number(vitals.systolic_bp),
    diastolic_bp: Number(vitals.diastolic_bp),
    blood_sugar: Number(vitals.blood_sugar),
    body_temp_c: Number(vitals.body_temp_c),
    heart_rate: Number(vitals.heart_rate),
    created_locally_at: now.toISOString(),
  };

  const rawPrediction = predictMaternalRisk({
    age: patientAge || 25,
    systolic_bp: currentVisitData.systolic_bp,
    diastolic_bp: currentVisitData.diastolic_bp,
    blood_sugar: currentVisitData.blood_sugar,
    body_temp: currentVisitData.body_temp_c,
    heart_rate: currentVisitData.heart_rate,
  });

  return calculateTrendAdjustment(currentVisitData, priorVisits || [], rawPrediction.risk_level);
}

// Same field limits as the mobile visit form (NewVisitScreen validate()).
// Returns a translation key (see src/i18n/locales) or '' when valid.
export function validateVitals(form) {
  const sys = Number(form.systolic_bp);
  if (!Number.isFinite(sys) || sys < 50 || sys > 260) return 'vitals.errors.systolic';
  const dia = Number(form.diastolic_bp);
  if (!Number.isFinite(dia) || dia < 30 || dia > 180) return 'vitals.errors.diastolic';
  if (dia >= sys) return 'vitals.errors.diastolicBelowSystolic';
  const bs = Number(form.blood_sugar);
  if (!Number.isFinite(bs) || bs < 20 || bs > 500) return 'vitals.errors.sugar';
  const temp = Number(form.body_temp_c);
  if (!Number.isFinite(temp) || temp < 30.0 || temp > 45.0) return 'vitals.errors.temp';
  const hr = Number(form.heart_rate);
  if (!Number.isFinite(hr) || hr < 30 || hr > 220) return 'vitals.errors.heartRate';
  return '';
}
