/**
 * 서울 문명 시뮬레이터 — entry point.
 *
 * Wires the simulation core to the scene and the interface, then runs one loop: advance the clock,
 * let the macro layers catch up, summon the visible crowd, place the sun, draw.
 */
import * as THREE from 'three';
import { loadWorld, type WorldMeta } from './core/world/worldData.ts';
import { Simulation, DEFAULT_START_JD, DEFAULT_END_JD, type LogEntry } from './core/sim.ts';
import { AgentSystem } from './core/agents/agents.ts';
import { SimLayers, TimeScale, ALL_SCALES } from './core/time/timeScale.ts';
import { gregorianToJd, jdToGregorian, dayOfYear } from './core/time/julian.ts';
import { formatLocalTime, toLocalJd, SEOUL_LAT, SEOUL_LON } from './core/time/koreaTime.ts';
import { dayLengthHours, sunrise, sunset } from './core/astro/sunEvents.ts';
import { LAND_USE_NAMES, LandUse } from './core/world/worldData.ts';
import { ROLE_NAMES, ACTIVITY_NAMES, AgentRole, AgentActivity } from './core/agents/agents.ts';
import { ERA_PROFILES } from './core/era/eras.ts';
import { localToLonLat, formatLonLat } from './core/geo/localFrame.ts';
import { Rng } from './core/rng.ts';
import { TerrainView } from './render/terrain.ts';
import { WaterView } from './render/water.ts';
import { SkyView } from './render/sky.ts';
import { CityView } from './render/city.ts';
import { CrowdView } from './render/crowd.ts';
import { GodCamera } from './render/camera.ts';
import { Hud } from './ui/hud.ts';
import { MiniHud } from './ui/miniHud.ts';

const canvas = document.getElementById('view') as HTMLCanvasElement;

async function boot(): Promise<void> {
  const hud = new Hud({
    onScale: (s) => setScale(s),
    onScrub: (f) => scrubTo(f),
    onTool: (t) => { tool = t; },
    onView: (v, on) => setView(v, on),
    onMode: (m) => { sim.mode = m; },
  });

  hud.setLoading('지형 데이터를 불러오는 중…', 0.1);
  const base = import.meta.env.BASE_URL ?? './';
  const world = await loadWorld(
    async (name) => {
      const r = await fetch(`${base}data/${name}`);
      if (!r.ok) throw new Error(`${name}: ${r.status}`);
      return r.arrayBuffer();
    },
    async (name) => {
      const r = await fetch(`${base}data/${name}`);
      return (await r.json()) as WorldMeta;
    },
  );

  hud.setLoading('세계를 준비하는 중…', 0.45);
  const sim = new Simulation(world, { mode: 'reproduce', seed: 20260915 });
  const agents = new AgentSystem(new Rng(4242));

  // The view can be drawn into more than one canvas over a session: the page's own, and the one
  // inside the always-on-top window. A renderer belongs to a canvas, so it is made per canvas.
  function createRenderer(target: HTMLCanvasElement): THREE.WebGLRenderer {
    const r = new THREE.WebGLRenderer({ canvas: target, antialias: true, powerPreference: 'high-performance' });
    r.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    r.setClearColor(0x0d1117);
    return r;
  }
  const renderer = createRenderer(canvas);
  let activeRenderer = renderer;
  let activeCanvas: HTMLCanvasElement = canvas;

  const scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0x9fb3c8, 12000, 90000);

  hud.setLoading('지형을 세우는 중…', 0.65);
  const terrain = new TerrainView(world, 1);
  const water = new WaterView(world);
  const city = new CityView(world);
  const crowd = new CrowdView(world);
  const sky = new SkyView(SEOUL_LAT, SEOUL_LON);
  scene.add(terrain.surround, terrain.mesh, water.mesh, city.group, crowd.group, sky.group);

  water.rebuild(sim.land.water);
  terrain.updateColors(sim.land, sim.era);

  const cam = new GodCamera(world, window.innerWidth / window.innerHeight);
  cam.attach(canvas);
  // Open looking north across the Han at the site of the first villages.
  cam.flyTo(6000, -4000, 22000);
  cam.yawDeg = 200;

  hud.setLoading('준비 완료', 1);
  hud.reveal();

  // ----- interaction state -----
  let tool = 'none';
  let running = true;
  let lastFrame = performance.now();
  let lastCityRebuild = 0;
  let lastTerrainPaint = 0;
  let lastSimSignature = '';
  let lastBuildX = Infinity;
  let lastBuildZ = Infinity;
  let lastBuildDistance = 0;
  let fastForward: { targetJd: number } | null = null;
  const raycaster = new THREE.Raycaster();
  const pointer = new THREE.Vector2();
  let showPeople = true;
  let fpsEstimate = 0;
  let frameCount = 0;

  function setScale(s: TimeScale): void {
    sim.clock.scale = s;
    hud.setScale(s);
    miniHud.setScale(s);
    pipHud?.setScale(s);
  }

  // ----- small-window and always-on-top modes -----
  const miniHud = new MiniHud(document, (s) => setScale(s));
  miniHud.root.hidden = true;
  document.body.appendChild(miniHud.root);

  let miniOn = false;
  /** Mini mode follows the window size until the user picks a side themselves. */
  let autoMini = true;
  let pipWindow: Window | null = null;
  let pipRenderer: THREE.WebGLRenderer | null = null;
  let pipHud: MiniHud | null = null;

  function setMini(on: boolean): void {
    if (miniOn === on) return;
    miniOn = on;
    document.body.classList.toggle('mini', on);
    miniHud.root.hidden = !on || pipWindow !== null;
    const btn = document.getElementById('btn-mini');
    if (btn) btn.classList.toggle('active', on);
  }

  interface DocumentPictureInPicture {
    requestWindow(options?: { width?: number; height?: number }): Promise<Window>;
  }

  function pipApi(): DocumentPictureInPicture | null {
    const api = (window as unknown as { documentPictureInPicture?: DocumentPictureInPicture })
      .documentPictureInPicture;
    return api && typeof api.requestWindow === 'function' ? api : null;
  }

  function pipSupported(): boolean {
    return pipApi() !== null;
  }

  /**
   * Move the view into a Document Picture-in-Picture window, which the browser keeps above other
   * windows. A renderer belongs to its canvas, so a fresh one is made for the new canvas and the
   * scene is simply drawn through it instead; nothing about the simulation changes.
   */
  async function enterPip(): Promise<void> {
    const api = pipApi();
    if (!api || pipWindow) return;
    const pip = await api.requestWindow({ width: 560, height: 360 });
    pipWindow = pip;

    for (const sheet of Array.from(document.styleSheets)) {
      try {
        const css = Array.from(sheet.cssRules).map((rule) => rule.cssText).join('\n');
        const style = pip.document.createElement('style');
        style.textContent = css;
        pip.document.head.appendChild(style);
      } catch {
        // A stylesheet from another origin cannot be read; there are none here, but be safe.
      }
    }
    pip.document.documentElement.lang = 'ko';
    pip.document.title = '서울 문명 시뮬레이터';
    pip.document.body.style.margin = '0';
    pip.document.body.style.background = '#0d1117';
    pip.document.body.style.overflow = 'hidden';

    const pipCanvas = pip.document.createElement('canvas');
    pipCanvas.id = 'view';
    pip.document.body.appendChild(pipCanvas);

    pipHud = new MiniHud(pip.document, (s) => setScale(s));
    pipHud.setScale(sim.clock.scale);
    pip.document.body.appendChild(pipHud.root);

    pipRenderer = createRenderer(pipCanvas);
    activeRenderer = pipRenderer;
    activeCanvas = pipCanvas;
    lastWidth = 0;
    lastHeight = 0;
    cam.attach(pipCanvas);

    miniHud.root.hidden = true;
    const handoff = document.getElementById('handoff');
    if (handoff) handoff.hidden = false;
    pip.addEventListener('pagehide', () => exitPip());
  }

  function exitPip(): void {
    if (!pipWindow) return;
    pipHud?.dispose();
    pipHud = null;
    pipRenderer?.dispose();
    pipRenderer = null;
    pipWindow = null;
    activeRenderer = renderer;
    activeCanvas = canvas;
    lastWidth = 0;
    lastHeight = 0;
    miniHud.root.hidden = !miniOn;
    const handoff = document.getElementById('handoff');
    if (handoff) handoff.hidden = true;
  }

  document.getElementById('btn-mini')?.addEventListener('click', () => {
    autoMini = false;
    setMini(!miniOn);
  });
  const pipButton = document.getElementById('btn-pip');
  const windowHint = document.getElementById('window-hint');
  if (pipSupported()) {
    if (pipButton) {
      pipButton.hidden = false;
      pipButton.addEventListener('click', () => {
        if (pipWindow) {
          pipWindow.close();
          exitPip();
        } else {
          void enterPip().catch((e: unknown) => console.warn('always-on-top window refused', e));
        }
      });
    }
    if (windowHint) windowHint.textContent = '"항상 위에"는 다른 창 위에 뜨는 작은 창으로 옮깁니다.';
  } else if (windowHint) {
    windowHint.textContent = '이 브라우저는 항상 위에 띄우기를 지원하지 않습니다. 크롬이나 엣지에서 열거나, PowerToys의 Win+Ctrl+T를 쓰세요.';
  }

  function setView(v: string, on: boolean): void {
    if (v === 'people') { showPeople = on; crowd.setVisible(on); }
    if (v === 'buildings') city.group.visible = on;
    if (v === 'water') water.mesh.visible = on;
  }

  function scrubTo(fraction: number): void {
    const targetJd = DEFAULT_START_JD + (DEFAULT_END_JD - DEFAULT_START_JD) * fraction;
    if (targetJd < sim.clock.jdUt) {
      // The simulation has no rewind, so a jump backwards replays from the beginning.
      window.location.hash = `#${Math.floor(jdToGregorian(targetJd).year)}`;
      window.location.reload();
      return;
    }
    fastForward = { targetJd };
  }

  setScale(TimeScale.Paused);

  // Jump straight to a year given in the URL hash, so a reload keeps your place.
  const hashYear = Number(window.location.hash.replace('#', ''));
  if (Number.isFinite(hashYear) && hashYear > 100 && hashYear < 2027) {
    fastForward = { targetJd: gregorianToJd(Math.floor(hashYear), 1, 1) };
  }

  window.addEventListener('keydown', (e) => {
    if ((e.target as HTMLElement)?.tagName === 'INPUT') return;
    const key = e.key.toLowerCase();
    if (e.code === 'Space') {
      e.preventDefault();
      setScale(sim.clock.scale === TimeScale.Paused ? TimeScale.HourPerSecond : TimeScale.Paused);
    } else if (key === ']') {
      setScale(ALL_SCALES[Math.min(ALL_SCALES.length - 1, sim.clock.scale + 1)]!);
    } else if (key === '[') {
      setScale(ALL_SCALES[Math.max(0, sim.clock.scale - 1)]!);
    } else if (key === 'm') {
      autoMini = false;
      setMini(!miniOn);
    } else if (key === 'f') {
      const capital = sim.land.settlements.find((s) => s.isCapital) ?? sim.land.settlements[0];
      if (capital) cam.flyTo(capital.x, capital.z, 3000);
    }
  });

  // Size is reconciled from whichever canvas is live, which covers both a window resize and the
  // always-on-top window being dragged bigger.
  let lastWidth = 0;
  let lastHeight = 0;

  /** Whether the window is small enough to be worth stripping the interface down. */
  function applyAutoMini(w: number, h: number): void {
    if (autoMini && !pipWindow) setMini(w < 620 || h < 460);
  }

  function syncSize(): void {
    const w = Math.max(1, activeCanvas.clientWidth);
    const h = Math.max(1, activeCanvas.clientHeight);
    if (w === lastWidth && h === lastHeight) return;
    lastWidth = w;
    lastHeight = h;
    activeRenderer.setSize(w, h, false);
    cam.setAspect(w / h);
    applyAutoMini(w, h);
  }

  // The interface must not wait on a render frame: at the fastest speeds one can take seconds,
  // and a window someone just dragged smaller should tidy itself up at once. The renderer catches
  // up on the next frame, which is soon enough for a few stretched pixels.
  window.addEventListener('resize', () => {
    applyAutoMini(window.innerWidth, window.innerHeight);
    lastWidth = 0;
    lastHeight = 0;
    syncSize();
  });

  canvas.addEventListener('click', (e) => {
    pointer.x = (e.clientX / window.innerWidth) * 2 - 1;
    pointer.y = -(e.clientY / window.innerHeight) * 2 + 1;
    raycaster.setFromCamera(pointer, cam.camera);
    const hit = raycaster.intersectObject(terrain.mesh, false)[0];
    if (!hit) return;
    handleClick(hit.point.x, hit.point.z);
  });

  function handleClick(x: number, z: number): void {
    const radius = 900;
    switch (tool) {
      case 'seed': {
        const seedPop = Math.max(150, sim.stats.population * 0.004);
        const s = sim.land.found(sim.land.nextName(), x, z, seedPop, Math.floor(sim.year), 0);
        sim.addLog(sim.year, `${s.name} 개척`, '당신의 뜻으로 사람들이 자리를 잡는다.', 'found', x, z);
        return;
      }
      case 'prosper': {
        for (const s of sim.land.settlements) {
          if (Math.hypot(s.x - x, s.z - z) < radius * 4) s.econ.foodStock += s.cohorts.total * 0.8;
        }
        sim.addLog(sim.year, '풍년', '들에 곡식이 가득하다.', 'disaster', x, z);
        return;
      }
      case 'plague': {
        for (const s of sim.land.settlements) {
          const d = Math.hypot(s.x - x, s.z - z);
          if (d < radius * 5) s.cohorts.scaleTo(s.cohorts.total * (0.72 + 0.2 * (d / (radius * 5))));
        }
        sim.addLog(sim.year, '역병', '거리에 사람이 줄었다.', 'war', x, z);
        return;
      }
      case 'flood': {
        sim.land.damage(x, z, radius * 3, 0.5);
        for (const s of sim.land.settlements) {
          if (Math.hypot(s.x - x, s.z - z) < radius * 3) s.cohorts.scaleTo(s.cohorts.total * 0.94);
        }
        sim.addLog(sim.year, '홍수', '물이 저지대를 덮쳤다.', 'disaster', x, z);
        return;
      }
      default:
        inspect(x, z);
    }
  }

  function inspect(x: number, z: number): void {
    const c = world.cellAt(x, z);
    if (!world.inBounds(c.i, c.j)) return;
    const k = world.index(c.i, c.j);
    const { lat, lon } = localToLonLat(x, z);
    const owner = sim.land.cellSettlement[k]!;
    const settlement = owner >= 0 ? sim.land.settlements[owner] : undefined;

    // Is anyone standing here?
    let nearest = -1;
    let nearestD = 40;
    for (let id = 0; id < agents.count; id++) {
      const d = Math.hypot(agents.x[id]! - x, agents.z[id]! - z);
      if (d < nearestD) { nearestD = d; nearest = id; }
    }

    const rows: Array<[string, string]> = [
      ['좌표', formatLonLat(lon, lat)],
      ['고도', `${world.heightAt(x, z).toFixed(0)} m`],
      ['토지 이용', LAND_USE_NAMES[sim.land.cellUse[k] as LandUse]],
      ['이 칸 인구', `${Math.round(sim.land.cellPop[k]!).toLocaleString('ko-KR')}명`],
      ['농사 적성', `${(world.fertility[k]! * 100).toFixed(0)}%`],
      ['건축 적성', `${(sim.land.buildable[k]! * 100).toFixed(0)}%`],
      ['물까지', `${(world.distanceToWater[k]! / 1000).toFixed(1)} km`],
    ];
    if (settlement) {
      rows.push(['정착지', `${settlement.name}${settlement.isCapital ? ' (도읍)' : ''}`]);
      rows.push(['정착지 인구', `${Math.round(settlement.cohorts.total).toLocaleString('ko-KR')}명`]);
      rows.push(['식량', `${(settlement.foodRatio * 100).toFixed(0)}%`]);
      rows.push(['세운 해', `${settlement.foundedYear}년`]);
    }
    if (nearest >= 0) {
      rows.push(['가까운 사람', ROLE_NAMES[agents.role[nearest] as AgentRole]]);
      rows.push(['지금', ACTIVITY_NAMES[agents.activity[nearest] as AgentActivity]]);
    }
    hud.showInspect(settlement ? settlement.name : '이 자리', rows);
  }

  function onLogClick(entry: LogEntry): void {
    if (entry.x !== undefined && entry.z !== undefined) cam.flyTo(entry.x, entry.z, 4000);
  }

  // ----- the loop -----
  function frame(now: number): void {
    const raw = (now - lastFrame) / 1000;
    lastFrame = now;
    fpsEstimate = raw > 0 ? fpsEstimate * 0.9 + (1 / raw) * 0.1 : fpsEstimate;
    frameCount++;
    // Cap the step so one stalled frame cannot skip a decade, but allow enough that the fastest
    // speeds still make progress on a slow machine.
    const dt = Math.min(0.25, raw);

    if (fastForward) {
      // Run the simulation in slices so the page keeps painting while it catches up.
      const budgetMs = 28;
      const t0 = performance.now();
      while (sim.clock.jdUt < fastForward.targetJd && performance.now() - t0 < budgetMs) {
        sim.clock.advanceSimSeconds(365.25 * 86400);
        sim.stepMacro(365.25, 1);
      }
      if (sim.clock.jdUt >= fastForward.targetJd) {
        fastForward = null;
        // Repaint everything once, now that the catch-up is over.
        lastSimSignature = '';
        lastTerrainPaint = 0;
      }
    } else if (running) {
      sim.update(dt);
    }

    cam.update(dt);
    sky.update(sim.clock.jdUt, cam.camera.position);

    // Fog, the clear colour and the sky's horizon are the same colour, so the edge of the mapped
    // world and the bottom of the sky meet without a seam at any hour.
    const f = scene.fog as THREE.Fog;
    const day = sky.state.daylight;
    f.color.copy(sky.state.horizonColor);
    f.near = 3000 + cam.distance * 0.35;
    f.far = 26000 + cam.distance * 2.4;
    activeRenderer.setClearColor(f.color);
    water.setTime(sky.state.sun.altitudeDeg);
    terrain.setSurroundColor(f.color, day);

    // The crowd only exists when you are close enough to see it and time is slow enough to watch.
    // Paused counts as a micro speed: a frozen street should still have people standing in it.
    const micro = (sim.clock.activeLayers & SimLayers.Micro) !== 0 || sim.clock.scale === TimeScale.Paused;
    const closeEnough = cam.distance < 4200;
    if (showPeople && micro && closeEnough) {
      const budget = cam.distance < 600 ? 5200 : cam.distance < 1200 ? 4500 : cam.distance < 2500 ? 2600 : 1400;
      // Close in, look a little wider than the camera distance so the street ahead is populated too.
      const radius = Math.max(140, Math.min(2200, cam.distance * (cam.distance < 600 ? 1.4 : 0.8)));
      agents.refresh(sim.land, cam.target.x, cam.target.z, radius, sim.era, budget);
      const localJd = toLocalJd(sim.clock.jdUt);
      const hour = ((localJd + 0.5) % 1) * 24;
      const d = jdToGregorian(localJd);
      const jd0 = gregorianToJd(d.year, d.month, d.day);
      const rise = sunrise(jd0, SEOUL_LAT, SEOUL_LON);
      const set = sunset(jd0, SEOUL_LAT, SEOUL_LON);
      const riseHour = rise !== null ? ((toLocalJd(rise) + 0.5) % 1) * 24 : 6;
      const setHour = set !== null ? ((toLocalJd(set) + 0.5) % 1) * 24 : 18;
      const agentDt = sim.clock.scale === TimeScale.Paused ? 0 : dt * Math.max(1, sim.clock.simSecondsPerRealSecond / 60);
      agents.update(agentDt, hour, riseHour, setHour);
      crowd.update(agents, now / 1000, cam.distance);
      crowd.setVisible(true);
    } else {
      crowd.setVisible(false);
      agents.count = 0;
    }

    // Rebuild the built fabric only when the simulation has actually moved.
    // Rebuild when the simulation has moved, and also when the camera has: how much detail each
    // cell gets depends on how far away it is, so panning has to redraw the blocks you moved toward.
    const signature = `${Math.round(sim.stats.year)}|${sim.stats.builtCells}|${sim.stats.era}`;
    const panned =
      Math.hypot(cam.target.x - lastBuildX, cam.target.z - lastBuildZ) > Math.max(250, cam.distance * 0.3) ||
      Math.abs(cam.distance - lastBuildDistance) > lastBuildDistance * 0.3;
    if (!fastForward && (signature !== lastSimSignature || panned) && now - lastCityRebuild > 220) {
      lastSimSignature = signature;
      lastCityRebuild = now;
      lastBuildX = cam.target.x;
      lastBuildZ = cam.target.z;
      lastBuildDistance = cam.distance;
      city.rebuild(sim.land, sim.era, cam.target.x, cam.target.z, Math.max(9000, cam.distance * 1.6), cam.distance);
      if (now - lastTerrainPaint > 600) {
        lastTerrainPaint = now;
        terrain.updateColors(sim.land, sim.era);
        water.rebuild(sim.land.water);
      }
    }

    syncSize();
    activeRenderer.render(scene, cam.camera);
    updateHud();
    requestAnimationFrame(frame);
  }

  let lastHud = 0;
  function updateHud(): void {
    const now = performance.now();
    if (now - lastHud < 100) return;
    lastHud = now;
    const jd = sim.clock.jdUt;
    const local = jdToGregorian(toLocalJd(jd));
    // Sun events are solved from 0h UT of the local civil date, which is what the method expects.
    const jd0 = gregorianToJd(local.year, local.month, local.day);
    const rise = sunrise(jd0, SEOUL_LAT, SEOUL_LON);
    const set = sunset(jd0, SEOUL_LAT, SEOUL_LON);
    hud.updateClock(
      jd,
      rise !== null ? formatLocalTime(rise) : '--:--',
      set !== null ? formatLocalTime(set) : '--:--',
      sky.state.sun.altitudeDeg,
      dayLengthHours(jd0, SEOUL_LAT, SEOUL_LON),
    );
    hud.updateStats(sim.stats, crowd.drawnCount, sim.clock.progress(DEFAULT_START_JD));
    hud.updateLog(sim.log, onLogClick);

    if (miniOn || pipHud) {
      const useLunar = jd < 2299160.5;
      const dateText = useLunar
        ? `${local.year}년 ${local.month}월`
        : `${local.year}.${String(local.month).padStart(2, '0')}.${String(local.day).padStart(2, '0')}`;
      const clockText = formatLocalTime(jd);
      if (miniOn) miniHud.update(sim.stats, clockText, dateText);
      pipHud?.update(sim.stats, clockText, dateText);
    }
  }

  // Expose a small surface for the automated browser checks.
  interface CivSimTestApi {
    sim: Simulation;
    setScale: (s: TimeScale) => void;
    jumpToYear: (y: number) => void;
    flyTo: (x: number, z: number, d: number) => void;
    setCamera: (o: { pitch?: number; yaw?: number; distance?: number }) => void;
    setJd: (jd: number) => void;
    setMini: (on: boolean) => void;
    pipSupported: () => boolean;
    state: () => Record<string, unknown>;
  }
  (window as unknown as { civsim: CivSimTestApi }).civsim = {
    sim,
    setScale,
    jumpToYear: (y: number) => { fastForward = { targetJd: gregorianToJd(Math.floor(y), 6, 21) }; },
    flyTo: (x: number, z: number, d: number) => cam.flyTo(x, z, d),
    setCamera: (o: { pitch?: number; yaw?: number; distance?: number }) => {
      if (o.pitch !== undefined) cam.pitchDeg = o.pitch;
      if (o.yaw !== undefined) cam.yawDeg = o.yaw;
      if (o.distance !== undefined) cam.distance = o.distance;
    },
    setJd: (jd: number) => sim.clock.jumpTo(jd),
    setMini: (on: boolean) => { autoMini = false; setMini(on); },
    pipSupported: () => pipSupported(),
    state: () => ({
      year: sim.stats.year,
      jd: sim.clock.jdUt,
      scale: sim.clock.scale,
      fps: fpsEstimate,
      frames: frameCount,
      era: sim.stats.era,
      eraLabel: sim.stats.eraLabel,
      population: sim.stats.population,
      referencePopulation: sim.stats.referencePopulation,
      builtCells: sim.stats.builtCells,
      settlements: sim.stats.settlements,
      sunAltitude: sky.state.sun.altitudeDeg,
      sunAzimuth: sky.state.sun.azimuthDeg,
      daylight: sky.state.daylight,
      localTime: formatLocalTime(sim.clock.jdUt),
      buildingInstances: city.instanceCount,
      agentsDrawn: crowd.drawnCount,
      fastForwarding: fastForward !== null,
      cameraDistance: cam.distance,
      drawCalls: activeRenderer.info.render.calls,
      triangles: activeRenderer.info.render.triangles,
      mini: miniOn,
      pip: pipWindow !== null,
      pipSupported: pipSupported(),
    }),
  };

  void ERA_PROFILES;
  void dayOfYear;
  requestAnimationFrame(frame);
}

boot().catch((err: unknown) => {
  const text = document.getElementById('loading-text');
  if (text) text.textContent = `오류: ${String(err)}`;
  console.error(err);
});
