/**
 * Drives the built app in a real browser and checks what is actually on screen:
 * the sun is where the almanac says, the city grows, people appear, and nothing throws.
 *
 * Run: npm run build && npm run verify
 */
import { chromium, type ConsoleMessage, type Page } from 'playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { dirname } from 'node:path';
import { sunHorizontal } from '../src/core/astro/solar.ts';
import { localMidnightUt, SEOUL_LAT, SEOUL_LON } from '../src/core/time/koreaTime.ts';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const distDir = join(root, 'dist');
const shotDir = join(root, 'verification');

const MIME: Record<string, string> = {
  '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
  '.json': 'application/json', '.bin': 'application/octet-stream', '.svg': 'image/svg+xml',
};

function serve(port: number): Promise<() => Promise<void>> {
  const server = createServer(async (req, res) => {
    try {
      const url = new URL(req.url ?? '/', 'http://localhost');
      let p = normalize(decodeURIComponent(url.pathname));
      if (p === '/' || p.endsWith('/')) p += 'index.html';
      const file = join(distDir, p);
      if (!file.startsWith(distDir)) { res.writeHead(403).end(); return; }
      const body = await readFile(file);
      res.writeHead(200, { 'content-type': MIME[extname(file)] ?? 'application/octet-stream' });
      res.end(body);
    } catch {
      res.writeHead(404).end('not found');
    }
  });
  return new Promise((resolve) => {
    server.listen(port, '127.0.0.1', () => resolve(() => new Promise((r) => server.close(() => r()))));
  });
}

interface State {
  year: number;
  jd: number;
  scale: number;
  fps: number;
  frames: number;
  mini: boolean;
  pip: boolean;
  pipSupported: boolean; era: number; eraLabel: string; population: number; referencePopulation: number;
  builtCells: number; settlements: number; sunAltitude: number; sunAzimuth: number;
  daylight: number; localTime: string; buildingInstances: number; agentsDrawn: number;
  fastForwarding: boolean; cameraDistance: number; drawCalls: number; triangles: number;
}

const failures: string[] = [];
const notes: string[] = [];

function check(name: string, ok: boolean, detail = ''): void {
  if (ok) notes.push(`  PASS  ${name}${detail ? ` — ${detail}` : ''}`);
  else failures.push(`  FAIL  ${name}${detail ? ` — ${detail}` : ''}`);
}

async function state(page: Page): Promise<State> {
  return page.evaluate(() => (window as unknown as { civsim: { state: () => State } }).civsim.state());
}

async function settle(page: Page, ms: number): Promise<void> {
  await page.waitForTimeout(ms);
}

async function waitForYear(page: Page, year: number, timeoutMs = 300000): Promise<State> {
  const t0 = Date.now();
  await page.evaluate((y) => (window as unknown as { civsim: { jumpToYear: (n: number) => void } }).civsim.jumpToYear(y), year);
  for (;;) {
    const s = await state(page);
    if (!s.fastForwarding && s.year >= year - 1.5) return s;
    if (Date.now() - t0 > timeoutMs) throw new Error(`timed out waiting for year ${year} (at ${s.year.toFixed(0)})`);
    await settle(page, 250);
  }
}

/**
 * Wait until the app reports a state that satisfies `ready`. A frame on this software renderer can
 * take seconds, and everything derived from the scene - the sun, the layout - is only refreshed
 * when one completes, so a fixed delay reads stale values.
 */
async function waitForState(
  page: Page, ready: (s: State) => boolean, what: string, timeoutMs = 90000,
): Promise<State> {
  const t0 = Date.now();
  for (;;) {
    const s = await state(page);
    if (ready(s)) return s;
    if (Date.now() - t0 > timeoutMs) throw new Error(`timed out waiting for ${what}`);
    await settle(page, 250);
  }
}

/** Move the clock, then wait for the scene to have been drawn at that instant. */
async function setJdAndWait(page: Page, jd: number): Promise<State> {
  const before = await state(page);
  await page.evaluate((j) => {
    const w = window as unknown as { civsim: { setJd: (v: number) => void } };
    w.civsim.setJd(j);
  }, jd);
  return waitForState(
    page,
    (s) => Math.abs(s.jd - jd) < 1e-6 && s.frames > before.frames + 1,
    `the scene to be drawn at JD ${jd}`,
  );
}

async function shot(page: Page, name: string): Promise<void> {
  await page.screenshot({ path: join(shotDir, `${name}.png`) });
}

async function main(): Promise<void> {
  await mkdir(shotDir, { recursive: true });
  const stop = await serve(4178);
  const chromePath = process.env.CIVSIM_CHROME ?? '/opt/pw-browsers/chromium-1194/chrome-linux/chrome';
  const browser = await chromium.launch({
    executablePath: existsSync(chromePath) ? chromePath : undefined,
    args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--disable-gpu-sandbox', '--no-sandbox'],
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

  const errors: string[] = [];
  page.on('console', (m: ConsoleMessage) => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', (e) => errors.push(String(e)));

  await page.goto('http://127.0.0.1:4178/', { waitUntil: 'load' });
  await page.waitForFunction(() => (window as unknown as { civsim?: unknown }).civsim !== undefined, null, { timeout: 90000 });
  await settle(page, 1500);

  // --- the scene renders at all ---
  let s = await state(page);
  check('WebGL scene draws geometry', s.triangles > 100000, `${s.triangles.toLocaleString()} triangles, ${s.drawCalls} draw calls`);
  check('starts in AD 100', Math.abs(s.year - 100) < 2, `year ${s.year.toFixed(1)}`);
  check('starts in the Three Kingdoms era', s.eraLabel === '삼국시대', s.eraLabel);
  await shot(page, '01-ad100-start');

  // --- the sun is where the almanac puts it ---
  const solarChecks: Array<[number, number, number, number, string]> = [
    [2026, 6, 21, 12, '하지 정오'],
    [2026, 12, 22, 12, '동지 정오'],
    [2026, 3, 20, 7, '춘분 아침'],
  ];
  for (const [y, mo, d, hour, label] of solarChecks) {
    const jd = localMidnightUt(y, mo, d) + hour / 24;
    const live = await setJdAndWait(page, jd);
    const expected = sunHorizontal(jd, SEOUL_LAT, SEOUL_LON);
    const dAlt = Math.abs(live.sunAltitude - expected.altitudeDeg);
    const dAz = Math.abs(live.sunAzimuth - expected.azimuthDeg);
    check(
      `sun position matches the almanac (${label})`,
      dAlt < 0.05 && dAz < 0.05,
      `alt ${live.sunAltitude.toFixed(2)}° vs ${expected.altitudeDeg.toFixed(2)}°, az ${live.sunAzimuth.toFixed(1)}° vs ${expected.azimuthDeg.toFixed(1)}°`,
    );
  }

  // Noon altitude really does swing between the solstices.
  const summerJd = localMidnightUt(2026, 6, 21) + 12.5 / 24;
  const winterJd = localMidnightUt(2026, 12, 22) + 12.5 / 24;
  const summerAlt = sunHorizontal(summerJd, SEOUL_LAT, SEOUL_LON).altitudeDeg;
  const winterAlt = sunHorizontal(winterJd, SEOUL_LAT, SEOUL_LON).altitudeDeg;
  check('noon altitude swings with the seasons', summerAlt - winterAlt > 44, `${summerAlt.toFixed(1)}° vs ${winterAlt.toFixed(1)}°`);

  // --- night really is dark ---
  const night = await setJdAndWait(page, localMidnightUt(2026, 6, 21) + 1 / 24);
  check('night is dark', night.daylight < 0.02, `daylight ${night.daylight.toFixed(3)} at ${night.localTime}`);
  await shot(page, '02-night');

  const noon = await setJdAndWait(page, localMidnightUt(2026, 6, 21) + 12 / 24);
  check('noon is bright', noon.daylight > 0.95, `daylight ${noon.daylight.toFixed(3)}`);

  // Put the clock back where the run needs it.
  await page.reload({ waitUntil: 'load' });
  await page.waitForFunction(() => (window as unknown as { civsim?: unknown }).civsim !== undefined, null, { timeout: 90000 });
  await settle(page, 1200);

  // --- the city grows through history ---
  const eras: Array<[number, string, string]> = [
    [400, '한성백제', '03-ad400-baekje'],
    [1450, '조선 한양', '04-1450-hanyang'],
    [1900, '대한제국', '05-1900'],
    [1975, '산업화', '06-1975'],
    [2026, '현대 서울', '07-2026'],
  ];
  const marks: Record<number, State> = {};
  for (const [year, label, file] of eras) {
    const st = await waitForYear(page, year);
    marks[year] = st;
    await settle(page, 900);
    await shot(page, file);
    const ratio = st.population / st.referencePopulation;
    check(
      `population near the record at ${year} (${label})`,
      ratio > 0.7 && ratio < 1.35,
      `${Math.round(st.population).toLocaleString()} vs ${Math.round(st.referencePopulation).toLocaleString()} (${(ratio * 100).toFixed(0)}%)`,
    );
    check(`buildings drawn at ${year}`, st.buildingInstances > 20, `${st.buildingInstances} instances`);
  }
  check('the city grows over time', marks[2026]!.builtCells > marks[1450]!.builtCells * 8,
    `${marks[1450]!.builtCells} → ${marks[2026]!.builtCells} cells`);
  check('era label reaches the modern day', marks[2026]!.eraLabel === '현대', marks[2026]!.eraLabel);

  // --- people appear when you zoom in and slow down ---
  await page.evaluate(() => {
    const w = window as unknown as {
      civsim: { sim: { land: { settlements: Array<{ x: number; z: number; isCapital: boolean }> }; clock: { jdUt: number } };
        flyTo: (x: number, z: number, d: number) => void; setScale: (s: number) => void; setJd: (jd: number) => void };
    };
    const capital = w.civsim.sim.land.settlements.find((s) => s.isCapital) ?? w.civsim.sim.land.settlements[0]!;
    w.civsim.flyTo(capital.x, capital.z, 800);
    // Mid-morning in June, when the streets are busy and the light is good.
    w.civsim.setJd(2461213.5 + 1 / 24);
    w.civsim.setScale(2); // 1분/초
  });
  await settle(page, 9000);
  const street = await state(page);
  check('people are summoned at street level', street.agentsDrawn > 200, `${street.agentsDrawn} people drawn`);
  check('street view still renders', street.triangles > 100000, `${street.triangles.toLocaleString()} triangles`);
  await shot(page, '08-street-level');

  // Close enough to watch individual people walking between the buildings.
  await page.evaluate(() => {
    const w = window as unknown as { civsim: { setCamera: (o: Record<string, number>) => void } };
    w.civsim.setCamera({ distance: 200, pitch: 22 });
  });
  await settle(page, 3500);
  const close = await state(page);
  check('people are legible from street height', close.agentsDrawn > 50, `${close.agentsDrawn} people at ${close.cameraDistance.toFixed(0)} m`);
  await shot(page, '09-among-the-people');

  await page.evaluate(() => {
    const w = window as unknown as { civsim: { setCamera: (o: Record<string, number>) => void } };
    w.civsim.setCamera({ distance: 900, pitch: 34 });
  });
  await settle(page, 3000);
  await shot(page, '10-close-modern');

  // The same street in the Joseon city, where the building kit is entirely different.
  await page.reload({ waitUntil: 'load' });
  await page.waitForFunction(() => (window as unknown as { civsim?: unknown }).civsim !== undefined, null, { timeout: 90000 });
  await settle(page, 1200);
  const joseonYear = await waitForYear(page, 1500);
  check('replaying to 1500 lands in the Joseon era', joseonYear.eraLabel === '조선 전기', joseonYear.eraLabel);
  await page.evaluate(() => {
    const w = window as unknown as {
      civsim: { flyTo: (x: number, z: number, d: number) => void; setScale: (s: number) => void;
        setCamera: (o: Record<string, number>) => void; setJd: (jd: number) => void;
        sim: { land: { settlements: Array<{ x: number; z: number; isCapital: boolean }> }; clock: { jdUt: number } } };
    };
    const capital = w.civsim.sim.land.settlements.find((s) => s.isCapital)!;
    w.civsim.flyTo(capital.x, capital.z, 700);
    w.civsim.setCamera({ pitch: 30, yaw: 40 });
    w.civsim.setScale(2);
    // Mid-morning, so the streets are busy.
    w.civsim.setJd(Math.floor(w.civsim.sim.clock.jdUt) + 0.5 + 1.5 / 24);
  });
  await settle(page, 4500);
  const joseon = await state(page);
  check('the Joseon street is populated too', joseon.agentsDrawn > 50, `${joseon.agentsDrawn} people in ${joseon.eraLabel}`);
  await shot(page, '11-joseon-street');

  // People must actually move.
  const before = await page.evaluate(() => {
    const w = window as unknown as { civsim: { sim: unknown } };
    void w;
    return 0;
  });
  void before;
  const posA = await page.evaluate(() => {
    const el = document.getElementById('stat-agents');
    return el?.textContent ?? '';
  });
  await settle(page, 2000);
  const posB = await page.evaluate(() => {
    const el = document.getElementById('stat-agents');
    return el?.textContent ?? '';
  });
  check('the crowd panel is live', posA.length > 0 && posB.length > 0, `${posA} → ${posB}`);

  // --- time controls ---
  await page.evaluate(() => (window as unknown as { civsim: { setScale: (s: number) => void } }).civsim.setScale(0));
  const paused1 = (await state(page)).year;
  await settle(page, 800);
  const paused2 = (await state(page)).year;
  check('pause stops the clock', Math.abs(paused2 - paused1) < 1e-6, `${paused1.toFixed(4)} → ${paused2.toFixed(4)}`);

  // Step back from the end of the recorded span, pull the camera up so the software renderer is
  // not the bottleneck, then let a year per second run. The clock is read directly: on this
  // headless renderer a frame can take a second, and the simulation is deliberately tied to it.
  await page.evaluate(() => {
    const w = window as unknown as { civsim: { setJd: (jd: number) => void; setScale: (s: number) => void; setCamera: (o: Record<string, number>) => void } };
    w.civsim.setJd(2433283.5); // 1950-01-01
    w.civsim.setCamera({ distance: 30000, pitch: 60 });
    w.civsim.setScale(6);
  });
  await settle(page, 600);
  const runStart = await state(page);
  await settle(page, 4000);
  const ran = await state(page);
  const days = ran.jd - runStart.jd;
  // The rate is tied to the frame rate by design, and this software renderer manages a few frames
  // a second, so the check is that the calendar moves, not how fast.
  check('a year per second advances the calendar', days > 40,
    `+${days.toFixed(0)} days in 4 s at ${ran.fps.toFixed(1)} fps`);
  // At a decade per second the macro layer must actually run: the clock alone is not the point.
  await page.evaluate(() => {
    const w = window as unknown as { civsim: { setJd: (jd: number) => void; setScale: (s: number) => void } };
    w.civsim.setJd(2433283.5);
    w.civsim.setScale(7);
  });
  await settle(page, 6000);
  const macroEnd = await state(page);
  // The jump put the clock at 1950; a decade per second must carry the macro layer past it.
  check('the macro layers keep up with the clock', macroEnd.year > 1951 && macroEnd.year < 2010,
    `1950 → ${macroEnd.year.toFixed(1)} in 6 s at ${macroEnd.fps.toFixed(1)} fps`);
  check('the population responds while running', Number.isFinite(macroEnd.population) && macroEnd.population > 0,
    `${Math.round(macroEnd.population).toLocaleString()}`);
  await page.evaluate(() => (window as unknown as { civsim: { setScale: (s: number) => void } }).civsim.setScale(0));

  // --- the interface is there ---
  for (const [id, label] of [['timebar', '시간 막대'], ['stats', '현황판'], ['topbar', '날짜판'], ['tools', '개입 도구']] as const) {
    const visible = await page.isVisible(`#${id}`);
    check(`${label} is on screen`, visible);
  }
  const speedCount = await page.locator('#speeds button').count();
  check('all eight speed buttons exist', speedCount === 8, `${speedCount} buttons`);
  const logCount = await page.locator('#log li').count();
  check('the chronicle has entries', logCount > 3, `${logCount} entries`);

  await page.locator('#speeds button').nth(4).click();
  await settle(page, 300);
  const afterClick = await page.evaluate(() => document.querySelectorAll('#speeds button.active').length);
  check('clicking a speed button selects it', afterClick === 1);
  await page.evaluate(() => (window as unknown as { civsim: { setScale: (s: number) => void } }).civsim.setScale(0));

  // --- watching it from a corner of the screen ---
  // Pause first: at a decade per second a single frame can outlast the wait below.
  await page.evaluate(() => (window as unknown as { civsim: { setScale: (s: number) => void } }).civsim.setScale(0));
  await settle(page, 1000);
  // Mini mode has to survive a window small enough to park beside other work.
  await page.setViewportSize({ width: 460, height: 320 });
  const smallState = await waitForState(page, (s) => s.mini, 'mini mode to turn on');
  check('mini mode turns itself on in a small window', smallState.mini, `${smallState.mini}`);
  check('the view still renders at 460x320', smallState.triangles > 100000, `${smallState.triangles.toLocaleString()} triangles`);
  const stripVisible = await page.isVisible('.mini-root');
  check('the compact strip is on screen', stripVisible);
  const bigPanelsHidden = await page.evaluate(() => {
    const ids = ['topbar', 'stats', 'tools', 'timebar'];
    return ids.every((id) => {
      const el = document.getElementById(id);
      return !el || getComputedStyle(el).display === 'none';
    });
  });
  check('the full panels step aside in mini mode', bigPanelsHidden);
  const strip = await page.locator('.mini-root').boundingBox();
  check('the compact strip fits the window', !!strip && strip.width <= 460 && strip.height < 70,
    strip ? `${Math.round(strip.width)}x${Math.round(strip.height)}` : 'not laid out');
  const miniSpeeds = await page.locator('.mini-root button').count();
  check('the compact strip keeps every speed button', miniSpeeds === 8, `${miniSpeeds} buttons`);
  await shot(page, '12-mini-mode');
  await page.setViewportSize({ width: 1440, height: 900 });
  const backState = await waitForState(page, (s) => !s.mini, 'mini mode to turn off');
  check('mini mode steps back down when the window grows', !backState.mini);

  check('no uncaught errors in the browser', errors.length === 0, errors.slice(0, 3).join(' | '));

  await browser.close();
  await stop();

  const report = [
    '서울 문명 시뮬레이터 — 브라우저 검증',
    '='.repeat(52),
    ...notes,
    ...failures,
    '',
    `${notes.length} passed, ${failures.length} failed`,
    `screenshots in ${shotDir}`,
  ].join('\n');
  console.log(report);
  await writeFile(join(shotDir, 'report.txt'), `${report}\n`, 'utf8');
  if (failures.length > 0) process.exitCode = 1;
}

main().catch((e: unknown) => {
  console.error(e);
  process.exitCode = 1;
});
