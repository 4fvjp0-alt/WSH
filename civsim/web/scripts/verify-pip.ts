/**
 * Exercises the always-on-top path without a real Document Picture-in-Picture window.
 *
 * The browser's own PiP window is not available in a headless run, so the API is stubbed with an
 * ordinary same-origin popup. Everything downstream of requestWindow is the real code: the
 * stylesheet copy, the second canvas, the second WebGL renderer, the compact readout, and the
 * teardown that hands the view back.
 */
import { chromium } from 'playwright';
import { createServer } from 'node:http';
import { readFile, mkdir } from 'node:fs/promises';
import { extname, join, normalize, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const distDir = join(root, 'dist');
const MIME: Record<string, string> = {
  '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.bin': 'application/octet-stream', '.svg': 'image/svg+xml',
};

const server = createServer(async (req, res) => {
  try {
    const url = new URL(req.url ?? '/', 'http://localhost');
    let p = normalize(decodeURIComponent(url.pathname));
    if (p === '/' || p.endsWith('/')) p += 'index.html';
    const body = await readFile(join(distDir, p));
    res.writeHead(200, { 'content-type': MIME[extname(p)] ?? 'application/octet-stream' });
    res.end(body);
  } catch {
    res.writeHead(404).end('nf');
  }
});
await new Promise<void>((r) => server.listen(4183, '127.0.0.1', () => r()));

const failures: string[] = [];
const notes: string[] = [];
function check(name: string, ok: boolean, detail = ''): void {
  (ok ? notes : failures).push(`  ${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ` — ${detail}` : ''}`);
}

const browser = await chromium.launch({
  executablePath: process.env.CIVSIM_CHROME ?? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome',
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--no-sandbox'],
});
const context = await browser.newContext({ viewport: { width: 1200, height: 760 } });

// Stand in for the browser's always-on-top window with a same-origin popup.
await context.addInitScript(() => {
  (window as unknown as { documentPictureInPicture: unknown }).documentPictureInPicture = {
    requestWindow: async (opts?: { width?: number; height?: number }) => {
      const w = window.open('about:blank', 'civsim-pip',
        `popup=yes,width=${opts?.width ?? 560},height=${opts?.height ?? 360}`);
      if (!w) throw new Error('popup blocked');
      (window as unknown as { __pip: Window }).__pip = w;
      return w;
    },
  };
});

const page = await context.newPage();
const errors: string[] = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));
page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)); });

interface State { triangles: number; pip: boolean; pipSupported: boolean; mini: boolean; year: number }
const state = (): Promise<State> =>
  page.evaluate(() => (window as unknown as { civsim: { state: () => State } }).civsim.state());

await page.goto('http://127.0.0.1:4183/', { waitUntil: 'domcontentloaded' });
await page.waitForFunction(() => (window as unknown as { civsim?: unknown }).civsim !== undefined, null, { timeout: 90000 });
await page.waitForTimeout(2500);

const before = await state();
check('the always-on-top button is offered when the browser supports it', before.pipSupported);
check('the button is visible in the panel', await page.isVisible('#btn-pip'));
check('the view renders in the page to begin with', before.triangles > 100000, `${before.triangles.toLocaleString()} triangles`);

const popupPromise = context.waitForEvent('page');
await page.click('#btn-pip');
const popup = await popupPromise;
await popup.waitForLoadState('domcontentloaded').catch(() => undefined);
await page.waitForTimeout(4000);

const during = await state();
check('the view moves to the second window', during.pip, `pip=${during.pip}`);
check('a second renderer draws the same world', during.triangles > 100000, `${during.triangles.toLocaleString()} triangles`);

const popupCanvas = await popup.evaluate(() => {
  const c = document.getElementById('view') as HTMLCanvasElement | null;
  return c ? { w: c.width, h: c.height, cw: c.clientWidth, ch: c.clientHeight } : null;
});
check('the second window has a sized canvas', !!popupCanvas && popupCanvas.w > 100 && popupCanvas.h > 100,
  popupCanvas ? `${popupCanvas.w}x${popupCanvas.h} (css ${popupCanvas.cw}x${popupCanvas.ch})` : 'no canvas');

const popupStrip = await popup.evaluate(() => {
  const el = document.querySelector('.mini-root');
  if (!el) return null;
  return { buttons: el.querySelectorAll('button').length, text: (el.textContent ?? '').slice(0, 60) };
});
check('the compact readout travels with it', !!popupStrip && popupStrip.buttons === 8,
  popupStrip ? `${popupStrip.buttons} buttons, "${popupStrip.text.trim()}"` : 'no strip');

check('the page shows that the view moved', await page.isVisible('#handoff'));

// The speed buttons in the second window must drive the same clock.
const yearBefore = (await state()).year;
await popup.evaluate(() => {
  const buttons = Array.from(document.querySelectorAll('.mini-root button')) as HTMLButtonElement[];
  buttons[7]?.click(); // 10년/초
});
await page.waitForTimeout(3500);
const yearAfter = (await state()).year;
check('its speed buttons drive the simulation', yearAfter > yearBefore + 1,
  `${yearBefore.toFixed(1)} → ${yearAfter.toFixed(1)}`);

await mkdir(join(root, 'verification'), { recursive: true });
await popup.screenshot({ path: join(root, 'verification', '13-always-on-top.png') });

await popup.close();
await page.waitForTimeout(3000);
const after = await state();
check('closing it hands the view back to the page', !after.pip);
check('the page renders again afterwards', after.triangles > 100000, `${after.triangles.toLocaleString()} triangles`);
check('the handoff notice is cleared', !(await page.isVisible('#handoff')));

check('no uncaught errors', errors.length === 0, errors.slice(0, 3).join(' | '));

await browser.close();
server.close();

const report = ['항상 위에 띄우기 — 검증', '='.repeat(40), ...notes, ...failures, '',
  `${notes.length} passed, ${failures.length} failed`].join('\n');
console.log(report);
if (failures.length > 0) process.exitCode = 1;
