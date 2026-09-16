/** All DOM updates live here, so the render loop stays about the scene. */
import { ALL_SCALES, TimeScale, scaleLabel } from '../core/time/timeScale.ts';
import { formatLocalTime, timeRegimeLabel, toLocalDate, utcOffsetHours } from '../core/time/koreaTime.ts';
import { jdToJulianCalendar, GREGORIAN_START_JD } from '../core/time/julian.ts';
import { lunarDayOfMonth } from '../core/astro/lunar.ts';
import { POPULATION_CURVE, referencePopulation } from '../core/world/history.ts';
import type { LogEntry, SimStats } from '../core/sim.ts';

const $ = (id: string): HTMLElement => {
  const el = document.getElementById(id);
  if (!el) throw new Error(`missing element #${id}`);
  return el;
};

function formatNumber(n: number): string {
  if (n >= 100000000) return `${(n / 100000000).toFixed(2)}억`;
  if (n >= 10000) return `${(n / 10000).toFixed(1)}만`;
  return Math.round(n).toLocaleString('ko-KR');
}

export interface HudCallbacks {
  onScale(scale: TimeScale): void;
  onGoToPeople(): void;
  onScrub(fraction: number): void;
  onTool(tool: string): void;
  onView(view: string, on: boolean): void;
  onMode(mode: 'reproduce' | 'emergent'): void;
}

export class Hud {
  private readonly speedButtons = new Map<TimeScale, HTMLButtonElement>();
  private readonly history: Array<{ year: number; pop: number }> = [];
  private lastLogLength = 0;
  private chart: CanvasRenderingContext2D | null = null;

  constructor(private readonly cb: HudCallbacks) {
    const speeds = $('speeds');
    for (const scale of ALL_SCALES) {
      const b = document.createElement('button');
      b.textContent = scaleLabel(scale);
      b.dataset.scale = String(scale);
      b.addEventListener('click', () => this.cb.onScale(scale));
      speeds.appendChild(b);
      this.speedButtons.set(scale, b);
    }

    const scrub = $('scrub');
    const jump = (e: PointerEvent): void => {
      const r = scrub.getBoundingClientRect();
      this.cb.onScrub(Math.max(0, Math.min(1, (e.clientX - r.left) / r.width)));
    };
    scrub.addEventListener('pointerdown', jump);

    for (const b of document.querySelectorAll<HTMLButtonElement>('button.tool')) {
      b.addEventListener('click', () => {
        for (const o of document.querySelectorAll('button.tool')) o.classList.remove('active');
        b.classList.add('active');
        this.cb.onTool(b.dataset.tool ?? 'none');
        $('tool-hint').textContent = TOOL_HINTS[b.dataset.tool ?? 'none'] ?? '';
      });
    }
    for (const b of document.querySelectorAll<HTMLButtonElement>('button[data-view]')) {
      b.addEventListener('click', () => {
        b.classList.toggle('active');
        this.cb.onView(b.dataset.view!, b.classList.contains('active'));
      });
    }
    for (const b of document.querySelectorAll<HTMLButtonElement>('button[data-mode]')) {
      b.addEventListener('click', () => {
        for (const o of document.querySelectorAll('button[data-mode]')) o.classList.remove('active');
        b.classList.add('active');
        this.cb.onMode(b.dataset.mode as 'reproduce' | 'emergent');
      });
    }

    document.getElementById('btn-people')?.addEventListener('click', () => this.cb.onGoToPeople());

    const canvas = document.getElementById('popchart') as HTMLCanvasElement | null;
    this.chart = canvas?.getContext('2d') ?? null;
  }

  reveal(): void {
    for (const id of ['topbar', 'stats', 'tools', 'timebar']) $(id).hidden = false;
    const loading = $('loading');
    loading.classList.add('done');
    window.setTimeout(() => { loading.style.display = 'none'; }, 450);
  }

  setLoading(text: string, fraction: number): void {
    $('loading-text').textContent = text;
    ($('loading-bar') as HTMLElement).style.width = `${Math.round(fraction * 100)}%`;
  }

  setScale(scale: TimeScale): void {
    for (const [s, b] of this.speedButtons) b.classList.toggle('active', s === scale);
  }

  updateClock(jdUt: number, sunriseText: string, sunsetText: string, sunAltitude: number, dayLength: number): void {
    const d = toLocalDate(jdUt);
    const useLunar = jdUt < GREGORIAN_START_JD;
    let dateText: string;
    if (useLunar) {
      const j = jdToJulianCalendar(jdUt + utcOffsetHours(jdUt) / 24);
      dateText = `서기 ${j.year}년 ${j.month}월 ${j.day}일 · 음력 ${lunarDayOfMonth(jdUt)}일`;
    } else {
      dateText = `${d.year}년 ${d.month}월 ${d.day}일`;
    }
    $('date-label').textContent = dateText;
    $('clock-label').textContent = formatLocalTime(jdUt);
    $('sun-label').textContent = `일출 ${sunriseText} · 일몰 ${sunsetText} · 낮 ${dayLength.toFixed(1)}시간`;
    $('sun-alt').textContent = `태양 고도 ${sunAltitude.toFixed(1)}° · ${timeRegimeLabel(jdUt)}`;
  }

  /**
   * @param crowdHint why nobody is on screen, when nobody is. Without it an empty city looks
   * broken rather than simply too far away.
   */
  updateStats(stats: SimStats, visibleAgents: number, progress: number, crowdHint = ''): void {
    $('era-label').textContent = stats.eraLabel;
    $('polity-label').textContent = stats.polity.name;
    $('stat-pop').textContent = `${formatNumber(stats.population)}명`;
    const ratio = stats.referencePopulation > 0 ? stats.population / stats.referencePopulation : 1;
    $('stat-ref').textContent = `${formatNumber(stats.referencePopulation)}명 (${(ratio * 100).toFixed(0)}%)`;
    $('stat-settlements').textContent = `${stats.settlements}곳`;
    $('stat-built').textContent = `${((stats.builtCells * 1e4) / 1e6).toFixed(1)} km²`;
    $('stat-farm').textContent = `${((stats.farmCells * 1e4) / 1e6).toFixed(1)} km²`;
    $('stat-food').textContent = `${(stats.foodRatio * 100).toFixed(0)}%`;
    $('stat-largest').textContent = `${stats.largestSettlement} ${formatNumber(stats.largestPopulation)}`;
    const agentsEl = $('stat-agents');
    agentsEl.textContent = `${visibleAgents.toLocaleString('ko-KR')}명`;
    if (crowdHint) {
      const why = document.createElement('span');
      why.className = 'why';
      why.textContent = crowdHint;
      agentsEl.appendChild(why);
    }

    ($('scrub-fill') as HTMLElement).style.width = `${progress * 100}%`;
    ($('scrub-knob') as HTMLElement).style.left = `${progress * 100}%`;

    const last = this.history[this.history.length - 1];
    if (!last || stats.year - last.year > 4) {
      this.history.push({ year: stats.year, pop: stats.population });
      if (this.history.length > 1200) this.history.shift();
      this.drawChart();
    }
  }

  private drawChart(): void {
    const ctx = this.chart;
    if (!ctx) return;
    const w = ctx.canvas.width;
    const h = ctx.canvas.height;
    ctx.clearRect(0, 0, w, h);

    const y0 = 100;
    const y1 = 2026;
    const logMin = Math.log10(8000);
    const logMax = Math.log10(12000000);
    const px = (year: number): number => ((year - y0) / (y1 - y0)) * w;
    const py = (pop: number): number => h - ((Math.log10(Math.max(1000, pop)) - logMin) / (logMax - logMin)) * h;

    ctx.lineWidth = 1;
    ctx.strokeStyle = 'rgba(216, 166, 87, 0.85)';
    ctx.beginPath();
    for (let n = 0; n < POPULATION_CURVE.length; n++) {
      const a = POPULATION_CURVE[n]!;
      const x = px(a.year);
      const y = py(referencePopulation(a.year));
      if (n === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();

    ctx.strokeStyle = 'rgba(127, 179, 213, 0.95)';
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    for (let n = 0; n < this.history.length; n++) {
      const p = this.history[n]!;
      const x = px(p.year);
      const y = py(p.pop);
      if (n === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();

    // Era grid lines at the big turning points.
    ctx.strokeStyle = 'rgba(255,255,255,0.07)';
    ctx.lineWidth = 1;
    for (const year of [475, 918, 1394, 1592, 1910, 1950, 1963]) {
      ctx.beginPath();
      ctx.moveTo(px(year), 0);
      ctx.lineTo(px(year), h);
      ctx.stroke();
    }
  }

  updateLog(log: LogEntry[], onClick: (entry: LogEntry) => void): void {
    if (log.length === this.lastLogLength) return;
    this.lastLogLength = log.length;
    const ul = $('log');
    ul.textContent = '';
    for (const e of log.slice(-24).reverse()) {
      const li = document.createElement('li');
      li.className = e.kind;
      const y = document.createElement('span');
      y.className = 'y';
      y.textContent = `${Math.floor(e.year)}`;
      const t = document.createElement('span');
      t.textContent = e.title;
      const d = document.createElement('span');
      d.className = 'd';
      d.textContent = e.detail;
      li.append(y, t, d);
      if (e.x !== undefined) {
        li.style.cursor = 'pointer';
        li.addEventListener('click', () => onClick(e));
      }
      ul.appendChild(li);
    }
  }

  showInspect(title: string, rows: Array<[string, string]>): void {
    const el = $('inspect');
    el.textContent = '';
    const h = document.createElement('h3');
    h.textContent = title;
    el.appendChild(h);
    for (const [k, v] of rows) {
      const row = document.createElement('div');
      row.className = 'row';
      const a = document.createElement('span');
      a.textContent = k;
      const b = document.createElement('span');
      b.textContent = v;
      row.append(a, b);
      el.appendChild(row);
    }
    const close = document.createElement('button');
    close.className = 'close';
    close.textContent = '닫기';
    close.addEventListener('click', () => { el.hidden = true; $('tools').hidden = false; });
    el.appendChild(close);
    el.hidden = false;
    $('tools').hidden = true;
  }
}

const TOOL_HINTS: Record<string, string> = {
  none: '지도를 클릭하면 그 자리의 정보를 봅니다.',
  seed: '클릭한 자리에 새 정착지를 세웁니다.',
  prosper: '클릭한 둘레에 풍년이 듭니다.',
  plague: '클릭한 둘레에 역병이 돕니다.',
  flood: '클릭한 둘레가 물에 잠깁니다.',
};
