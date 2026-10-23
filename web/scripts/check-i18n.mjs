// Checks the worker-interface translations. Run: npm run check:i18n
//  1. Every language has exactly the English keys, no empty values, and the same {placeholders}.
//  2. Every translation key used by the worker screens exists (including runtime-built keys).
//  3. English risk actions / trend messages match the mobile engine, so stored text maps correctly.
//  4. Each language renders the worker login, dashboard, registration and visit screens with no
//     missing keys, no leftover {placeholders}, the right lang attribute, and no stray English.
import { build } from 'esbuild';
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const webRoot = resolve(fileURLToPath(new URL('..', import.meta.url)));
const src = join(webRoot, 'src');
const out = mkdtempSync(join(tmpdir(), 'herdoc-i18n-'));
const failures = [];
const fail = (message) => failures.push(message);

// Values allowed to equal English (codes/abbreviations kept on purpose).
const SAME_AS_ENGLISH_OK = new Set(['login.pin', 'home.edd']);
// Worker-facing source files whose t('...') calls must resolve.
const WORKER_SOURCES = [
  'pages/LoginPage.jsx',
  'pages/WorkerHomePage.jsx',
  'pages/WorkerPatientPage.jsx',
  'components/Navbar.jsx',
  'components/EmergencyNotice.jsx',
  'components/LanguageSelect.jsx',
  'components/worker/WorkerViews.jsx',
  'components/worker/SosButton.jsx',
  'risk/classifyVisit.js',
  'i18n/errors.js',
  'i18n/I18nContext.jsx',
];

const p = (rel) => JSON.stringify(join(src, rel).replace(/\\/g, '/'));
const entry = `
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { MemoryRouter } from 'react-router-dom';
import { LANGUAGES, TREND_REASON_KEYS, RISK_LEVELS, REVIEW_STATUSES, translate } from ${p('i18n/index.js')};
import { I18nProvider } from ${p('i18n/I18nContext.jsx')};
import { AuthContext } from ${p('context/AuthContext.jsx')};
import LoginPage from ${p('pages/LoginPage.jsx')};
import WorkerHomePage from ${p('pages/WorkerHomePage.jsx')};
import WorkerPatientPage from ${p('pages/WorkerPatientPage.jsx')};
import * as V from ${p('components/worker/WorkerViews.jsx')};
export { LANGUAGES, TREND_REASON_KEYS, RISK_LEVELS, REVIEW_STATUSES, translate };

const noop = async () => ({});
const worker = { id: 'w-1', name: 'Asha Patil', role: 'worker' };
const visit = (id, date, sys, dia, level, reason = null) => ({
  id, visit_date: date, systolic_bp: sys, diastolic_bp: dia, blood_sugar: 96, body_temp_c: 37.1, heart_rate: 84,
  risk_flags: level ? [{ id: id + '-f', model_risk_level: level, trend_adjusted_level: level, trend_reason: reason }] : [],
});
const reasons = Object.keys(TREND_REASON_KEYS);
const patient = (id, name) => ({ id, name, age: 26, village: 'Rampur', edd: '2026-12-20', phone: '9876543210' });
const rows = [
  { patient: patient('p1', 'Sunita'), latestVisit: visit('v1', '2026-10-20', 152, 98, 'red', reasons[1]), review: { status: 'referred', reviewed_at: '2026-10-21T08:00:00Z', notes: 'Refer today' } },
  { patient: patient('p2', 'Meena'), latestVisit: visit('v2', '2026-10-19', 132, 86, 'yellow'), review: { status: 'reviewed', reviewed_at: '2026-10-20T08:00:00Z', notes: '' } },
  { patient: patient('p3', 'Kavita'), latestVisit: visit('v3', '2026-10-18', 110, 72, 'green'), review: null },
  { patient: patient('p4', 'Rekha'), latestVisit: null, review: { status: 'pending' } },
];
const history = [visit('v9', '2026-10-20', 138, 90, 'yellow', reasons[0]), visit('v8', '2026-10-10', 125, 81, 'green', reasons[2]), visit('v7', '2026-10-01', 112, 72, 'green')];
const result = { model_risk_level: 'green', trend_adjusted_level: 'yellow', trend_reason: reasons[1], escalated: true };
const form = { name: 'Sunita', age: '26', village: 'Rampur', edd: '2026-12-20', phone: '' };
const vitals = { systolic_bp: '138', diastolic_bp: '90', blood_sugar: '96', body_temp_c: '37.1', heart_rate: '84' };

function Shell({ lang, onMissing, user, path = '/worker', children }) {
  const auth = { user, isAuthenticated: Boolean(user), isLoading: false, login: noop, loginWorker: noop, logout: noop };
  return (
    <MemoryRouter initialEntries={[path]}>
      <I18nProvider initialLanguage={lang} onMissing={onMissing}>
        <AuthContext.Provider value={auth}>{children}</AuthContext.Provider>
      </I18nProvider>
    </MemoryRouter>
  );
}

export function renderScreens(lang, onMissing) {
  const r = (node, opts = {}) => renderToStaticMarkup(<Shell lang={lang} onMissing={onMissing} user={worker} {...opts}>{node}</Shell>);
  return {
    login: r(<LoginPage />, { user: null, path: '/login?as=worker' }),
    homePage: r(<WorkerHomePage />),
    dashboard: r(<div lang={lang}><V.WorkerMetrics rows={rows} /><V.WorkerPatientList rows={rows} /></div>),
    registration: r(<div lang={lang}><V.PatientRegistrationForm form={form} onChange={() => {}} onSubmit={() => {}} error="" isSaving={false} /></div>),
    visitPage: r(<WorkerPatientPage />, { path: '/worker/patients/p1' }),
    visitRecording: r(
      <div lang={lang}>
        <V.PatientHeader patient={rows[0].patient} currentLevel="yellow" review={rows[0].review} />
        <V.ReviewPanel review={rows[0].review} />
        <V.VisitHistory visits={history} />
        <V.VisitForm vitals={vitals} onChange={() => {}} onSubmit={() => {}} error="" isSaving={false} result={result} />
      </div>,
    ),
  };
}
`;
writeFileSync(join(out, 'entry.jsx'), entry);

try {
  await build({
    entryPoints: [join(out, 'entry.jsx')],
    outfile: join(out, 'bundle.mjs'),
    bundle: true,
    format: 'esm',
    platform: 'node',
    jsx: 'automatic',
    nodePaths: [join(webRoot, 'node_modules')],
    // react-dom/server is CommonJS and requires Node built-ins at runtime.
    banner: { js: "import { createRequire as __createRequire } from 'node:module'; const require = __createRequire(import.meta.url);" },
    define: { 'import.meta.env.DEV': 'false', 'import.meta.env.VITE_API_BASE_URL': '""', __DEV__: 'false' },
    logLevel: 'error',
  });
  const m = await import(pathToFileURL(join(out, 'bundle.mjs')).href);
  const en = m.LANGUAGES.find((l) => l.code === 'en').dictionary;
  const enKeys = Object.keys(en);
  const placeholders = (text) => [...String(text).matchAll(/\{(\w+)\}/g)].map((x) => x[1]).sort().join(',');

  // 1. Dictionary completeness
  for (const { code, dictionary } of m.LANGUAGES) {
    const keys = Object.keys(dictionary);
    for (const key of enKeys) {
      if (!(key in dictionary)) fail(`[${code}] missing key ${key}`);
      else if (!String(dictionary[key]).trim()) fail(`[${code}] empty value for ${key}`);
      else if (placeholders(dictionary[key]) !== placeholders(en[key])) fail(`[${code}] placeholders differ for ${key}`);
      else if (code !== 'en' && dictionary[key] === en[key] && !SAME_AS_ENGLISH_OK.has(key)) fail(`[${code}] untranslated (same as English): ${key}`);
    }
    for (const key of keys) if (!(key in en)) fail(`[${code}] extra key not in English: ${key}`);
  }

  // 2. Keys used in worker source files exist
  const used = new Set();
  for (const rel of WORKER_SOURCES) {
    const text = readFileSync(join(src, rel), 'utf8');
    for (const match of text.matchAll(/\bt\(\s*'([\w.]+)'/g)) used.add(match[1]);
    for (const match of text.matchAll(/'((?:vitals|register)\.errors\.\w+|vitals\.\w+|errors\.\w+|login\.\w+|risk\.\w+(?:\.\w+)?|visitForm\.\w+|home\.\w+|patient\.\w+|visits\.\w+|sos\.\w+|emergency\.\w+)'/g)) used.add(match[1]);
  }
  for (const level of m.RISK_LEVELS) used.add(`risk.level.${level}`).add(`risk.action.${level}`);
  for (const status of m.REVIEW_STATUSES) used.add(`review.statusValue.${status}`);
  for (const key of Object.values(m.TREND_REASON_KEYS)) used.add(key);
  for (const key of used) if (!(key in en)) fail(`key used in code but missing from en.js: ${key}`);
  const unused = enKeys.filter((key) => !used.has(key));

  // 3. Display text matches the mobile engine
  const engine = readFileSync(resolve(webRoot, '../mobile/app/services/trend_engine.js'), 'utf8');
  const actionMap = engine.match(/const ACTION_MAP = \{([\s\S]*?)\};/)[1];
  for (const level of m.RISK_LEVELS) {
    const mobileText = actionMap.match(new RegExp(`${level}:\\s*'([^']+)'`))[1];
    if (en[`risk.action.${level}`] !== mobileText) fail(`risk.action.${level} differs from mobile ACTION_MAP ("${mobileText}")`);
  }
  const engineReasons = [...engine.matchAll(/trendReason = '([^']+)'/g)].map((x) => x[1]).sort();
  const mappedReasons = Object.keys(m.TREND_REASON_KEYS).sort();
  if (JSON.stringify(engineReasons) !== JSON.stringify(mappedReasons)) fail('TREND_REASON_KEYS do not match the trend messages in trend_engine.js');
  for (const [reason, key] of Object.entries(m.TREND_REASON_KEYS)) if (en[key] !== reason) fail(`${key} English text differs from the engine message`);

  // 4. Render every screen in every language
  const ENGLISH_ONLY = ['Register a patient', 'Record a visit', 'Systolic BP', 'Visit history', 'My Patients', 'Awaiting doctor review', 'Refer to PHC within 24 hours', 'Sign In as Health Worker', 'Blood pressure has risen'];
  const stripTags = (html) => html.replace(/<style[\s\S]*?<\/style>/g, '').replace(/<[^>]+>/g, ' ');
  const expectations = {
    login: ['login.submitWorker', 'login.phone', 'login.tabWorker'],
    homePage: ['home.title', 'nav.myPatients', 'nav.signOut', 'emergency.title', 'sos.button'],
    dashboard: ['home.metricRed', 'risk.action.red', 'review.statusValue.referred', 'risk.level.yellow', 'risk.none', 'review.awaiting'],
    registration: ['register.title', 'register.edd', 'register.submit'],
    visitPage: ['patient.loading'],
    visitRecording: ['visitForm.title', 'vitals.systolic', 'vitals.heartRate', 'visits.title', 'risk.trend.bp', 'visitForm.saved', 'review.notesLabel'],
  };
  const summary = [];
  // React warns that router links use useLayoutEffect during server rendering; expected here, so silence only that.
  const consoleError = console.error;
  console.error = (first, ...rest) => {
    if (typeof first === 'string' && first.includes('useLayoutEffect does nothing on the server')) return;
    consoleError(first, ...rest);
  };
  for (const { code } of m.LANGUAGES) {
    const missing = [];
    const screens = m.renderScreens(code, (lang, key) => missing.push(`${lang}:${key}`));
    for (const [screen, html] of Object.entries(screens)) {
      const text = stripTags(html);
      if (missing.length) fail(`[${code}] ${screen}: missing translations ${[...new Set(missing)].join(', ')}`);
      const leftover = text.match(/\{\w+\}/);
      if (leftover) fail(`[${code}] ${screen}: unreplaced placeholder ${leftover[0]}`);
      if (!html.includes(`lang="${code}"`)) fail(`[${code}] ${screen}: no lang="${code}" attribute`);
      for (const key of expectations[screen]) {
        const expected = m.translate(code, key).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#x27;' })[c]);
        if (!html.includes(expected)) fail(`[${code}] ${screen}: expected text for ${key} not rendered`);
      }
      if (code !== 'en') {
        for (const english of ENGLISH_ONLY) if (text.includes(english)) fail(`[${code}] ${screen}: English text "${english}" still shown`);
      }
    }
    summary.push(`${code}: ${Object.keys(screens).length} screens rendered`);
  }

  const review = [];
  for (const { code } of m.LANGUAGES.filter((l) => l.code !== 'en')) {
    const file = readFileSync(join(src, `i18n/locales/${code}.js`), 'utf8');
    for (const match of file.matchAll(/'([\w.]+)':[^\n]*\/\/ REVIEW/g)) review.push(`${code}:${match[1]}`);
  }

  console.log(`Languages: ${m.LANGUAGES.map((l) => `${l.code} (${l.label})`).join(', ')}; ${enKeys.length} keys each.`);
  console.log(summary.join('\n'));
  if (unused.length) console.log(`Note: ${unused.length} key(s) not found by the static scan: ${unused.join(', ')}`);
  console.log(`Clinical wording flagged for native-speaker review: ${review.length} (${review.join(', ')})`);
  if (failures.length) {
    console.log(`\n${failures.length} problem(s):\n- ${failures.join('\n- ')}`);
    process.exitCode = 1;
  } else {
    console.log('\nAll translation checks passed.');
  }
} finally {
  rmSync(out, { recursive: true, force: true });
}
