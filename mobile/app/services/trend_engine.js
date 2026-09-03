/**
 * HerDoc Trend-Based Risk Escalation Engine
 * Evaluates physiological trends across consecutive visits to detect
 * insidious, gradual maternal deterioration that single-snapshot models miss.
 *
 * 100% pure JavaScript - deterministic, offline-first.
 */

/**
 * ESCALATION THRESHOLDS (Documented Clinical Justification):
 *
 * 1. SYSTOLIC BLOOD PRESSURE:
 *    - Threshold: >= 8 mmHg rise across consecutive visits (e.g. V1 -> V2 >= +8 mmHg AND V2 -> V3 >= +8 mmHg).
 *    - Total trajectory: >= 16 mmHg climb across 3 visits.
 *    - Clinical rationale: In pregnancy, a steady progressive increase of >= 15-20 mmHg above baseline
 *      is a primary hallmark of developing preeclampsia, even if absolute values have not yet breached 140 mmHg.
 *
 * 2. DIASTOLIC BLOOD PRESSURE:
 *    - Threshold: >= 6 mmHg rise across consecutive visits.
 *    - Total trajectory: >= 12 mmHg climb across 3 visits.
 *    - Clinical rationale: Progressive diastolic rise reflects systemic peripheral vasoconstriction.
 *
 * 3. BLOOD SUGAR:
 *    - Threshold: >= 15 mg/dL (or >= 0.85 mmol/L) rise across consecutive visits.
 *    - Total trajectory: >= 30 mg/dL climb across 3 visits.
 *    - Clinical rationale: Insidious onset of gestational diabetes mellitus (GDM).
 */
export const TREND_THRESHOLDS = {
  SYSTOLIC_CONSECUTIVE_RISE_MMHG: 8,
  DIASTOLIC_CONSECUTIVE_RISE_MMHG: 6,
  BLOOD_SUGAR_CONSECUTIVE_RISE_MGDL: 15,
  BLOOD_SUGAR_CONSECUTIVE_RISE_MMOL: 0.85,
  MIN_REQUIRED_PRIOR_VISITS: 2,
};

const ESCALATION_MAP = {
  green: 'yellow',
  yellow: 'red',
  red: 'red',
};

const ACTION_MAP = {
  green: 'Continue routine care',
  yellow: 'Recheck in 1 week',
  red: 'Refer to PHC within 24 hours',
};

/**
 * Calculates trend adjustment based on a patient's historical vitals.
 *
 * @param {Object} currentVisit - The newly submitted visit object.
 * @param {Array<Object>} previousVisits - Historical visits from SQLite (sorted newest to oldest or vice-versa).
 * @param {string} rawModelRisk - The baseline ML risk prediction ('green' | 'yellow' | 'red').
 * @returns {Object} {
 *   model_risk_level: string,
 *   trend_adjusted_level: string,
 *   trend_reason: string | null,
 *   action: string,
 *   escalated: boolean,
 * }
 */
export function calculateTrendAdjustment(currentVisit, previousVisits = [], rawModelRisk = 'green') {
  const normalizedRaw = String(rawModelRisk || 'green').toLowerCase();

  // If there are fewer than 2 prior visits, we cannot establish a 3-point trend
  if (!previousVisits || previousVisits.length < TREND_THRESHOLDS.MIN_REQUIRED_PRIOR_VISITS) {
    return {
      model_risk_level: normalizedRaw,
      trend_adjusted_level: normalizedRaw,
      trend_reason: null,
      action: ACTION_MAP[normalizedRaw] || ACTION_MAP.green,
      escalated: false,
    };
  }

  // Sort prior visits chronologically (oldest -> newest)
  const sortedPriors = [...previousVisits].sort((a, b) => {
    const timeA = new Date(a.visit_date || a.created_locally_at || 0).getTime();
    const timeB = new Date(b.visit_date || b.created_locally_at || 0).getTime();
    return timeA - timeB;
  });

  // Pick the most recent 2 prior visits to form a 3-visit sequence with currentVisit
  const recentTwo = sortedPriors.slice(-2);
  const v1 = recentTwo[0]; // Oldest of the three
  const v2 = recentTwo[1]; // Middle visit
  const v3 = currentVisit; // Current newest visit

  // 1. Evaluate Systolic Blood Pressure Trend
  const sys1 = Number(v1.systolic_bp);
  const sys2 = Number(v2.systolic_bp);
  const sys3 = Number(v3.systolic_bp);
  const hasValidSys = Number.isFinite(sys1) && Number.isFinite(sys2) && Number.isFinite(sys3);

  const deltaSys12 = sys2 - sys1;
  const deltaSys23 = sys3 - sys2;
  const sustainedSystolicRise =
    hasValidSys &&
    deltaSys12 >= TREND_THRESHOLDS.SYSTOLIC_CONSECUTIVE_RISE_MMHG &&
    deltaSys23 >= TREND_THRESHOLDS.SYSTOLIC_CONSECUTIVE_RISE_MMHG;

  // 2. Evaluate Diastolic Blood Pressure Trend
  const dia1 = Number(v1.diastolic_bp);
  const dia2 = Number(v2.diastolic_bp);
  const dia3 = Number(v3.diastolic_bp);
  const hasValidDia = Number.isFinite(dia1) && Number.isFinite(dia2) && Number.isFinite(dia3);

  const deltaDia12 = dia2 - dia1;
  const deltaDia23 = dia3 - dia2;
  const sustainedDiastolicRise =
    hasValidDia &&
    deltaDia12 >= TREND_THRESHOLDS.DIASTOLIC_CONSECUTIVE_RISE_MMHG &&
    deltaDia23 >= TREND_THRESHOLDS.DIASTOLIC_CONSECUTIVE_RISE_MMHG;

  // 3. Evaluate Blood Sugar Trend (handle both mg/dL and mmol/L)
  const bs1 = Number(v1.blood_sugar);
  const bs2 = Number(v2.blood_sugar);
  const bs3 = Number(v3.blood_sugar);
  const hasValidBs = Number.isFinite(bs1) && Number.isFinite(bs2) && Number.isFinite(bs3);

  const deltaBs12 = bs2 - bs1;
  const deltaBs23 = bs3 - bs2;
  const bsThreshold =
    bs1 > 30 || bs3 > 30
      ? TREND_THRESHOLDS.BLOOD_SUGAR_CONSECUTIVE_RISE_MGDL
      : TREND_THRESHOLDS.BLOOD_SUGAR_CONSECUTIVE_RISE_MMOL;

  const sustainedBsRise =
    hasValidBs &&
    deltaBs12 >= bsThreshold &&
    deltaBs23 >= bsThreshold;

  const bpWorsening = sustainedSystolicRise || sustainedDiastolicRise;
  const shouldEscalate = bpWorsening || sustainedBsRise;

  if (!shouldEscalate) {
    return {
      model_risk_level: normalizedRaw,
      trend_adjusted_level: normalizedRaw,
      trend_reason: null,
      action: ACTION_MAP[normalizedRaw] || ACTION_MAP.green,
      escalated: false,
    };
  }

  // Generate plain-language clinical reason
  let trendReason = '';
  if (bpWorsening && sustainedBsRise) {
    trendReason = 'Blood pressure and blood sugar have risen steadily over your last 3 visits.';
  } else if (bpWorsening) {
    trendReason = 'Blood pressure has risen steadily over your last 3 visits.';
  } else if (sustainedBsRise) {
    trendReason = 'Blood sugar has risen steadily over your last 3 visits.';
  }

  const finalAdjustedLevel = ESCALATION_MAP[normalizedRaw] || 'yellow';
  const escalated = finalAdjustedLevel !== normalizedRaw;

  return {
    model_risk_level: normalizedRaw,
    trend_adjusted_level: finalAdjustedLevel,
    trend_reason: trendReason,
    action: ACTION_MAP[finalAdjustedLevel] || ACTION_MAP.yellow,
    escalated,
  };
}
