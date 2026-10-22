// Checks that the web portal classifies visits exactly like the mobile app.
// Bundles (a) web/src/risk/classifyVisit.js and (b) a reference that calls the mobile modules the
// way mobile/app/screens/NewVisitScreen.jsx does, then compares their outputs on fixed cases.
// Run: npm run check:risk
import { build } from 'esbuild';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const webRoot = resolve(fileURLToPath(new URL('..', import.meta.url)));
const mobileServices = resolve(webRoot, '../mobile/app/services');
const out = mkdtempSync(join(tmpdir(), 'herdoc-risk-'));

const reference = `
import { predictMaternalRisk } from ${JSON.stringify(join(mobileServices, 'inference.js'))};
import { calculateTrendAdjustment } from ${JSON.stringify(join(mobileServices, 'trend_engine.js'))};
// Mirrors NewVisitScreen.handleSubmit steps 1-5.
export function mobileClassify({ patientAge, vitals, priorVisits, now }) {
  const currentVisitData = {
    id: 'v', patient_id: 'p', worker_id: 'w',
    visit_date: now.toISOString().split('T')[0],
    systolic_bp: Number(vitals.systolic_bp),
    diastolic_bp: Number(vitals.diastolic_bp),
    blood_sugar: Number(vitals.blood_sugar),
    body_temp_c: Number(vitals.body_temp_c),
    heart_rate: Number(vitals.heart_rate),
    created_locally_at: now.toISOString(),
    created_at: now.toISOString(),
  };
  const raw = predictMaternalRisk({
    age: patientAge || 25,
    systolic_bp: Number(vitals.systolic_bp),
    diastolic_bp: Number(vitals.diastolic_bp),
    blood_sugar: Number(vitals.blood_sugar),
    body_temp: Number(vitals.body_temp_c),
    heart_rate: Number(vitals.heart_rate),
  });
  return calculateTrendAdjustment(currentVisitData, priorVisits, raw.risk_level);
}`;
writeFileSync(join(out, 'reference.js'), reference);

const common = { bundle: true, format: 'esm', platform: 'node', define: { __DEV__: 'false' }, logLevel: 'error' };
try {
  await build({ ...common, entryPoints: [join(webRoot, 'src/risk/classifyVisit.js')], outfile: join(out, 'web.mjs') });
  await build({ ...common, entryPoints: [join(out, 'reference.js')], outfile: join(out, 'ref.mjs') });
  const { classifyVisit } = await import(pathToFileURL(join(out, 'web.mjs')).href);
  const { mobileClassify } = await import(pathToFileURL(join(out, 'ref.mjs')).href);

  const now = new Date('2026-10-23T09:30:00Z');
  const visit = (date, sys, dia, extra = {}) => ({ visit_date: date, systolic_bp: sys, diastolic_bp: dia, blood_sugar: 95, body_temp_c: 37, heart_rate: 80, ...extra });
  const v = (systolic_bp, diastolic_bp, blood_sugar, body_temp_c, heart_rate) => ({ systolic_bp, diastolic_bp, blood_sugar, body_temp_c, heart_rate });
  const cases = [
    { name: 'normal vitals', patientAge: 24, vitals: v(110, 72, 90, 36.8, 76), priorVisits: [] },
    { name: 'severe hypertension + high sugar', patientAge: 38, vitals: v(170, 112, 300, 38.5, 118), priorVisits: [] },
    { name: 'borderline', patientAge: 30, vitals: v(135, 88, 140, 37.2, 92), priorVisits: [] },
    { name: 'missing age uses mobile default', patientAge: undefined, vitals: v(120, 80, 100, 37, 80), priorVisits: [] },
    { name: 'mmol/L-range sugar input', patientAge: 27, vitals: v(118, 76, 25, 36.9, 78), priorVisits: [] },
    {
      name: 'steady BP rise over 3 visits (trend escalation)', patientAge: 26, vitals: v(138, 90, 95, 37, 80),
      priorVisits: [visit('2026-10-02', 112, 72), visit('2026-10-12', 125, 81)],
    },
    {
      name: 'prior visits out of order', patientAge: 26, vitals: v(138, 90, 95, 37, 80),
      priorVisits: [visit('2026-10-12', 125, 81), visit('2026-10-02', 112, 72), visit('2026-09-20', 108, 70)],
    },
    { name: 'only one prior visit (no trend)', patientAge: 26, vitals: v(138, 90, 95, 37, 80), priorVisits: [visit('2026-10-12', 125, 81)] },
    {
      name: 'normal reading but systolic +9, +9 (green escalated)', patientAge: 24, vitals: v(118, 76, 90, 36.8, 76),
      priorVisits: [visit('2026-10-02', 100, 64, { blood_sugar: 90 }), visit('2026-10-12', 109, 70, { blood_sugar: 90 })],
    },
  ];

  let failures = 0;
  let escalations = 0;
  const levels = new Set();
  for (const c of cases) {
    const web = classifyVisit({ ...c, now });
    const mobile = mobileClassify({ ...c, now });
    const same = JSON.stringify(web) === JSON.stringify(mobile);
    levels.add(web.model_risk_level);
    if (web.escalated) escalations += 1;
    if (!same) failures += 1;
    console.log(`${same ? 'MATCH' : 'DIFF '}  ${c.name}: model=${web.model_risk_level} adjusted=${web.trend_adjusted_level}${web.escalated ? ' (escalated)' : ''}`);
    if (!same) console.log('   web:', web, '\n   mobile:', mobile);
  }
  // The mobile engine falls back to "yellow" on any inference error; seeing other levels proves the model ran.
  if (!(levels.has('green') && levels.has('red'))) {
    failures += 1;
    console.log(`FAIL  model produced only ${[...levels].join(', ')}: inference may be failing`);
  }
  if (!escalations) {
    failures += 1;
    console.log('FAIL  no case exercised a trend escalation');
  }
  console.log(failures ? `\n${failures} check(s) failed` : `\nAll ${cases.length} cases match the mobile implementation.`);
  process.exitCode = failures ? 1 : 0;
} finally {
  rmSync(out, { recursive: true, force: true });
}
