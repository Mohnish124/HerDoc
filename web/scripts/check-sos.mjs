// Checks the web SOS request logic (src/api/worker.js sendEmergencyAlert) with a mocked network.
// No real request is made and nothing is sent to Telegram. Run: npm run check:sos
import { build } from 'esbuild';
import { mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const webRoot = resolve(fileURLToPath(new URL('..', import.meta.url)));
const out = mkdtempSync(join(tmpdir(), 'herdoc-sos-'));
const src = (rel) => JSON.stringify(join(webRoot, 'src', rel).replace(/\\/g, '/'));
writeFileSync(join(out, 'entry.js'), `
export { sendEmergencyAlert, WEB_SOS_NOTE, SOS_TIMEOUT_MS } from ${src('api/worker.js')};
export { setAccessToken } from ${src('api/client.js')};
`);

const results = [];
const check = (name, ok, detail = '') => results.push(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? `  (${detail})` : ''}`);
const json = (status, body) => ({ status, ok: status >= 200 && status < 300, json: async () => body });
const never = (signal) => new Promise((_, reject) => signal?.addEventListener('abort', () => reject(Object.assign(new Error('aborted'), { name: 'AbortError' }))));

try {
  await build({
    entryPoints: [join(out, 'entry.js')], outfile: join(out, 'bundle.mjs'), bundle: true, format: 'esm', platform: 'node',
    define: { 'import.meta.env.DEV': 'false', 'import.meta.env.VITE_API_BASE_URL': '""' }, logLevel: 'error',
  });
  const m = await import(pathToFileURL(join(out, 'bundle.mjs')).href);
  m.setAccessToken('test-access-token');

  // Mocked network: `routes` decides each reply; every call is recorded.
  let calls = [];
  let routes = {};
  globalThis.fetch = async (url, options = {}) => {
    calls.push({ url, options });
    const handler = routes[url];
    if (!handler) throw new Error(`unexpected request to ${url}`);
    return handler(options, calls.filter((c) => c.url === url).length);
  };
  const run = async (name, setup, expectKind, extra) => {
    calls = [];
    routes = setup;
    const result = await m.sendEmergencyAlert({ timeoutMs: 200 });
    const posts = calls.filter((c) => c.url === '/api/emergency').length;
    const ok = result.kind === expectKind && (!extra || extra(posts));
    check(name, ok, `kind=${result.kind}, emergency requests=${posts}`);
    m.setAccessToken('test-access-token');
  };

  // Request contract
  calls = [];
  routes = { '/api/emergency': async () => json(200, { status: 'sent', location_included: false }) };
  const sent = await m.sendEmergencyAlert({ timeoutMs: 200 });
  const req = calls[0];
  const body = JSON.parse(req.options.body);
  check('confirmed "sent" is the only success', sent.kind === 'sent');
  check('uses the existing endpoint: same-origin POST /api/emergency', req.url === '/api/emergency' && req.options.method === 'POST');
  check('sends the session cookie and the in-memory access token', req.options.credentials === 'include' && req.options.headers.Authorization === 'Bearer test-access-token');
  check('body is only the web note (no location, no patient data)', JSON.stringify(Object.keys(body)) === '["message"]' && body.message === m.WEB_SOS_NOTE);
  check('the note fits the endpoint limit (300 chars)', m.WEB_SOS_NOTE.length <= 300);
  check('default limit is 30 seconds', m.SOS_TIMEOUT_MS === 30000);

  await run('200 without confirmation -> unconfirmed', { '/api/emergency': async () => json(200, { status: 'queued' }) }, 'unconfirmed');
  await run('200 with unreadable body -> unconfirmed', { '/api/emergency': async () => ({ status: 200, ok: true, json: async () => { throw new Error('bad json'); } }) }, 'unconfirmed');
  await run('503 not configured -> notConfigured', { '/api/emergency': async () => json(503, { detail: 'Emergency alerts are not configured on the server' }) }, 'notConfigured');
  await run('502 delivery failure -> failed', { '/api/emergency': async () => json(502, { detail: 'Could not deliver the emergency alert.' }) }, 'failed');
  await run('403 -> forbidden', { '/api/emergency': async () => json(403, { detail: 'Forbidden' }) }, 'forbidden');
  await run('422 -> unconfirmed', { '/api/emergency': async () => json(422, { detail: [] }) }, 'unconfirmed');
  await run('500 -> unconfirmed', { '/api/emergency': async () => json(500, {}) }, 'unconfirmed');
  await run('offline (network error) -> offline', { '/api/emergency': async () => { throw new TypeError('Failed to fetch'); } }, 'offline');
  await run('401 and refresh fails -> sessionExpired, one request', {
    '/api/emergency': async () => json(401, {}),
    '/api/auth/refresh': async () => json(401, {}),
  }, 'sessionExpired', (posts) => posts === 1);
  await run('401, refresh succeeds, one retry -> sent (no duplicate after success)', {
    '/api/emergency': async (_o, n) => (n === 1 ? json(401, {}) : json(200, { status: 'sent' })),
    '/api/auth/refresh': async () => json(200, { access_token: 'new-token', user: { role: 'worker' } }),
  }, 'sent', (posts) => posts === 2);
  await run('server never answers -> unconfirmed after the limit (request aborted)', { '/api/emergency': async (o) => never(o.signal) }, 'unconfirmed');
  await run('token refresh never answers -> still bounded, unconfirmed', {
    '/api/emergency': async () => json(401, {}),
    '/api/auth/refresh': async () => new Promise(() => {}),
  }, 'unconfirmed');

  // Duplicate submissions
  calls = [];
  let release;
  routes = { '/api/emergency': () => new Promise((r) => { release = () => r(json(200, { status: 'sent' })); }) };
  const first = m.sendEmergencyAlert({ timeoutMs: 1000 });
  const second = m.sendEmergencyAlert({ timeoutMs: 1000 });
  const third = m.sendEmergencyAlert({ timeoutMs: 1000 });
  await new Promise((r) => setTimeout(r, 10));
  release();
  const outcomes = await Promise.all([first, second, third]);
  check('repeated calls while pending share one request', first === second && second === third && calls.length === 1 && outcomes.every((o) => o.kind === 'sent'), `requests=${calls.length}`);
  calls = [];
  routes = { '/api/emergency': async () => json(200, { status: 'sent' }) };
  await m.sendEmergencyAlert({ timeoutMs: 200 });
  check('a new alert can be sent after the previous one finished', calls.length === 1);

  console.log(results.join('\n'));
  const failed = results.filter((r) => r.startsWith('FAIL')).length;
  console.log(failed ? `\n${failed} SOS check(s) failed` : `\nAll ${results.length} SOS checks passed.`);
  process.exitCode = failed ? 1 : 0;
} finally {
  rmSync(out, { recursive: true, force: true });
}
