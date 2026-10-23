// Builds the synthetic demo dataset (backend/app/demo/demo_dataset.json) and classifies every visit with the
// real risk model and trend engine (mobile/app/services via web/src/risk/classifyVisit.js) — never by hand.
//   node scripts/build-demo-dataset.mjs          write the dataset
//   node scripts/build-demo-dataset.mjs --check  verify the committed dataset still matches the model (no write)
// All people, phones and readings are fictional. No PINs or credentials are stored in the dataset.
import { build } from 'esbuild';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const webRoot = resolve(fileURLToPath(new URL('..', import.meta.url)));
const datasetPath = resolve(webRoot, '../backend/app/demo/demo_dataset.json');
const checkOnly = process.argv.includes('--check');
const out = mkdtempSync(join(tmpdir(), 'herdoc-demo-'));

const WORKER_PHONES = ['9000000006', '9000000007', '9000000008', '9000000009', '9000000010'];
// Days before the seeding date for the four visits of every patient (oldest first).
const VISIT_DAYS_AGO = [84, 56, 28, 7];
const vitals = (systolic_bp, diastolic_bp, blood_sugar, body_temp_c, heart_rate) => ({ systolic_bp, diastolic_bp, blood_sugar, body_temp_c, heart_rate });

// Three synthetic patterns per worker, varied slightly per worker. Expected outcomes are asserted below
// against the real model; the model's results are what gets stored.
function patterns(w) {
  return [
    {
      kind: 'routine',
      age: 22 + w,
      visits: [vitals(98 + w, 62, 80, 36.6, 70 + w), vitals(98 + w, 66, 88, 36.8, 74), vitals(102, 62 + w, 80, 36.6, 74), vitals(98, 66, 88 - w, 36.8, 70)],
      expect: (rs) => rs.every((r) => r.trend_adjusted_level === 'green'),
      describe: 'all visits green',
    },
    w % 2 === 0
      ? {
          // Steady readings, then blood sugar rises at the latest visit: a "recheck" (yellow) without a trend.
          kind: 'recheck',
          age: 25 + w,
          visits: w === 2
            ? [vitals(98, 62, 80, 36.6, 70), vitals(98, 62, 80, 36.6, 74), vitals(98, 62, 80, 36.6, 82), vitals(98, 62, 104, 36.6, 78)]
            : [vitals(98, 62, 80, 36.6, 82), vitals(98, 62, 80, 36.8, 82), vitals(98, 62, 80, 37.0, 82), vitals(98, 62, 104, 36.6, 70)],
          expect: (rs) => rs.slice(0, 3).every((r) => r.trend_adjusted_level === 'green') && rs[3].trend_adjusted_level === 'yellow' && !rs[3].escalated,
          describe: 'green visits then a yellow latest visit',
        }
      : {
          kind: 'rising-bp',
          age: 24 + w,
          visits: [vitals(104, 68, 88, 36.8, 76), vitals(113, 74, 90, 36.8, 78), vitals(122, 80, 92, 36.9, 80), vitals(131, 86, 94, 36.9, 82)],
          expect: (rs) => rs.some((r) => r.escalated) && rs[3].trend_adjusted_level !== 'green',
          describe: 'trend escalation present',
        },
    {
      kind: 'high-risk',
      age: 27 + w,
      visits: [vitals(138, 90, 120, 37.0, 88), vitals(146, 94, 140, 37.1, 92), vitals(152, 98, 165, 37.2, 96), vitals(158, 102, 180, 37.3, 100)],
      expect: (rs) => rs[3].trend_adjusted_level === 'red',
      describe: 'latest visit red',
    },
  ];
}

try {
  await build({
    entryPoints: [join(webRoot, 'src/risk/classifyVisit.js')], outfile: join(out, 'classify.mjs'),
    bundle: true, format: 'esm', platform: 'node', define: { __DEV__: 'false' }, logLevel: 'error',
  });
  const { classifyVisit } = await import(pathToFileURL(join(out, 'classify.mjs')).href);
  // Fixed reference dates keep the classification deterministic; only the order of visits matters to the trend engine.
  const reference = Date.UTC(2026, 0, 1);

  const dataset = {
    description: 'Synthetic HerDoc demo data. Fictional workers, patients and readings; not real clinical records.',
    generator: 'web/scripts/build-demo-dataset.mjs (risk results from the real HerDoc risk model and trend engine)',
    visit_days_ago: VISIT_DAYS_AGO,
    workers: [],
    patients: [],
  };
  const problems = [];

  WORKER_PHONES.forEach((phone, index) => {
    const w = index + 1;
    dataset.workers.push({ key: `worker-${w}`, name: `Demo Worker ${w}`, phone });
    patterns(w).forEach((pattern, p) => {
      const prior = [];
      const results = pattern.visits.map((reading, i) => {
        const now = new Date(reference - VISIT_DAYS_AGO[i] * 86400000);
        const r = classifyVisit({ patientAge: pattern.age, vitals: reading, priorVisits: prior, now });
        prior.push({ ...reading, visit_date: now.toISOString().slice(0, 10) });
        return r;
      });
      if (!pattern.expect(results)) problems.push(`worker ${w} ${pattern.kind}: expected ${pattern.describe}`);
      dataset.patients.push({
        key: `worker-${w}-patient-${p + 1}`,
        worker_key: `worker-${w}`,
        name: `Demo Patient ${w}-${p + 1}`,
        age: pattern.age,
        village: `Demo Village ${String.fromCharCode(65 + p)}`,
        edd_days_ahead: 60 + 20 * p + 7 * w,
        pattern: pattern.kind,
        visits: pattern.visits.map((reading, i) => ({
          days_ago: VISIT_DAYS_AGO[i],
          ...reading,
          model_risk_level: results[i].model_risk_level,
          trend_adjusted_level: results[i].trend_adjusted_level,
          trend_reason: results[i].trend_reason,
        })),
      });
    });
  });

  if (problems.length) {
    console.error(`Dataset patterns no longer produce the intended demo variety:\n- ${problems.join('\n- ')}`);
    process.exitCode = 1;
  } else {
    const text = `${JSON.stringify(dataset, null, 2)}\n`;
    const levels = {};
    for (const patient of dataset.patients) for (const v of patient.visits) levels[v.trend_adjusted_level] = (levels[v.trend_adjusted_level] || 0) + 1;
    const escalations = dataset.patients.flatMap((pt) => pt.visits).filter((v) => v.model_risk_level !== v.trend_adjusted_level).length;
    const summary = `${dataset.workers.length} workers, ${dataset.patients.length} patients, ${dataset.patients.length * VISIT_DAYS_AGO.length} visits; levels ${JSON.stringify(levels)}; ${escalations} trend escalations`;
    if (checkOnly) {
      const current = readFileSync(datasetPath, 'utf8').replace(/\r\n/g, '\n');
      if (current !== text) {
        console.error('backend/app/demo/demo_dataset.json does not match the current risk model output. Re-run: node scripts/build-demo-dataset.mjs');
        process.exitCode = 1;
      } else {
        console.log(`Demo dataset matches the risk model: ${summary}.`);
      }
    } else {
      writeFileSync(datasetPath, text);
      console.log(`Wrote ${datasetPath}: ${summary}.`);
    }
  }
} finally {
  rmSync(out, { recursive: true, force: true });
}
