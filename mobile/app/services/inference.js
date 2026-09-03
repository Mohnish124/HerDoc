/**
 * HerDoc On-Device ML Inference Service
 * Executes decision tree ensemble inference locally on-device.
 * 100% offline - 0 network calls required.
 */

import modelBundle from '../ml/maternal_risk_model_bundle.json';

const CLASS_MAPPING = {
  0: 'green',
  1: 'yellow',
  2: 'red',
};

const ACTION_MAPPING = {
  green: 'Continue routine care',
  yellow: 'Recheck in 1 week',
  red: 'Refer to PHC within 24 hours',
};

/**
 * Normalizes input vitals to match the dataset training distributions:
 * - Age: years
 * - SystolicBP: mmHg
 * - DiastolicBP: mmHg
 * - Blood Sugar: converted to mmol/L if provided in mg/dL (> 30)
 * - Body Temperature: converted to °F if provided in °C (< 50)
 * - Heart Rate: bpm
 */
function normalizeFeatures({ age, systolic_bp, diastolic_bp, blood_sugar, body_temp, heart_rate }) {
  const parsedAge = Number(age) || 25;
  const parsedSys = Number(systolic_bp) || 120;
  const parsedDia = Number(diastolic_bp) || 80;

  // Convert blood sugar from mg/dL to mmol/L if >= 30 (e.g. 90 mg/dL -> 5.0 mmol/L)
  const rawBs = Number(blood_sugar) || 6.8;
  const parsedBs = rawBs > 30 ? rawBs / 18.0182 : rawBs;

  // Convert temperature from Celsius to Fahrenheit if < 50 (e.g. 37.0 C -> 98.6 F)
  const rawTemp = Number(body_temp) || 37.0;
  const parsedTemp = rawTemp < 50 ? (rawTemp * 9) / 5 + 32 : rawTemp;

  const parsedHr = Number(heart_rate) || 75;

  return [parsedAge, parsedSys, parsedDia, parsedBs, parsedTemp, parsedHr];
}

/**
 * Scales raw features using the training pipeline's StandardScaler parameters.
 */
function scaleFeatures(rawFeatures, scaler) {
  const { mean, scale } = scaler;
  return rawFeatures.map((val, idx) => {
    const m = mean[idx] ?? 0;
    const s = scale[idx] ?? 1;
    return (val - m) / (s || 1);
  });
}

/**
 * Evaluates a single decision tree recursively.
 */
function evaluateTree(treeNode, scaledFeatures) {
  let curr = treeNode;
  while (curr.l === 0) {
    const featIdx = curr.f;
    const threshold = curr.t;
    if (scaledFeatures[featIdx] <= threshold) {
      curr = curr.lc;
    } else {
      curr = curr.rc;
    }
  }
  return curr.v; // Array of normalized class probabilities [p_green, p_yellow, p_red]
}

/**
 * Runs on-device machine learning inference for a maternal visit.
 *
 * @param {Object} vitals
 * @param {number} vitals.age
 * @param {number} vitals.systolic_bp
 * @param {number} vitals.diastolic_bp
 * @param {number} vitals.blood_sugar
 * @param {number} vitals.body_temp
 * @param {number} vitals.heart_rate
 * @returns {Object} { risk_level: 'green' | 'yellow' | 'red', action: string }
 */
export function predictMaternalRisk(vitals) {
  try {
    if (!modelBundle || !modelBundle.trees || !modelBundle.trees.length) {
      throw new Error('Model bundle is unavailable on device.');
    }

    const rawFeatures = normalizeFeatures(vitals);
    const scaledFeatures = scaleFeatures(rawFeatures, modelBundle.scaler);

    // Sum probabilities across all 150 decision trees
    const totalProbabilities = [0.0, 0.0, 0.0];
    const nTrees = modelBundle.trees.length;

    for (let i = 0; i < nTrees; i++) {
      const treeProbs = evaluateTree(modelBundle.trees[i], scaledFeatures);
      totalProbabilities[0] += treeProbs[0] || 0;
      totalProbabilities[1] += treeProbs[1] || 0;
      totalProbabilities[2] += treeProbs[2] || 0;
    }

    // Average probabilities
    const avgProbabilities = totalProbabilities.map((p) => p / nTrees);

    // Argmax prediction
    let maxIdx = 0;
    let maxProb = avgProbabilities[0];
    for (let i = 1; i < 3; i++) {
      if (avgProbabilities[i] > maxProb) {
        maxProb = avgProbabilities[i];
        maxIdx = i;
      }
    }

    const riskLevel = CLASS_MAPPING[maxIdx] || 'yellow';
    const action = ACTION_MAPPING[riskLevel] || ACTION_MAPPING.yellow;

    return {
      risk_level: riskLevel,
      action,
    };
  } catch (error) {
    if (__DEV__) {
      console.warn('[HerDoc Inference Error]:', error);
    }
    // Safe clinical fallback: flag as yellow (recheck) on unforeseen inference failure
    return {
      risk_level: 'yellow',
      action: ACTION_MAPPING.yellow,
    };
  }
}
