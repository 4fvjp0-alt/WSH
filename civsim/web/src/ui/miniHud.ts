/**
 * The compact readout used when the simulator is watched from a corner of the screen: in the
 * always-on-top window, or in the main window's mini mode. Everything it needs fits in one strip.
 */
import { ALL_SCALES, TimeScale, scaleShortLabel, scaleLabel } from '../core/time/timeScale.ts';
import type { SimStats } from '../core/sim.ts';

const MINI_CSS = `
.mini-root {
  position: fixed; left: 0; right: 0; bottom: 0;
  display: flex; align-items: center; gap: 8px;
  padding: 5px 8px calc(5px + env(safe-area-inset-bottom, 0px));
  background: rgba(13, 17, 23, 0.82);
  border-top: 1px solid rgba(150, 175, 205, 0.18);
  backdrop-filter: blur(8px);
  font-family: 'Pretendard', 'Apple SD Gothic Neo', 'Noto Sans KR', 'Malgun Gothic', system-ui, sans-serif;
  color: #dce3ec; font-size: 11px;
  z-index: 20;
}
.mini-when { display: flex; flex-direction: column; line-height: 1.25; min-width: 86px; }
.mini-era { color: #d8a657; font-weight: 700; font-size: 11px; }
.mini-date { font-variant-numeric: tabular-nums; white-space: nowrap; }
.mini-pop { margin-left: auto; text-align: right; line-height: 1.25; font-variant-numeric: tabular-nums; }
.mini-pop b { display: block; font-size: 13px; font-weight: 600; }
.mini-pop span { color: #8b97a8; font-size: 10px; }
.mini-speeds { display: flex; gap: 3px; flex-wrap: nowrap; }
.mini-speeds button {
  font: inherit; font-size: 10px; min-width: 26px; padding: 3px 5px;
  border-radius: 5px; border: 1px solid rgba(150, 175, 205, 0.2);
  background: rgba(255, 255, 255, 0.05); color: #dce3ec; cursor: pointer;
}
.mini-speeds button:hover { background: rgba(255, 255, 255, 0.12); }
.mini-speeds button.active { background: #7a6336; border-color: #d8a657; color: #fff; }
@media (max-width: 430px) {
  .mini-when { min-width: 72px; }
  .mini-pop span { display: none; }
}
`;

function formatPopulation(n: number): string {
  if (n >= 100000000) return `${(n / 100000000).toFixed(2)}억`;
  if (n >= 10000) return `${(n / 10000).toFixed(1)}만`;
  return Math.round(n).toLocaleString('ko-KR');
}

export class MiniHud {
  readonly root: HTMLElement;
  private readonly era: HTMLElement;
  private readonly date: HTMLElement;
  private readonly pop: HTMLElement;
  private readonly ref: HTMLElement;
  private readonly buttons = new Map<TimeScale, HTMLButtonElement>();

  constructor(doc: Document, onScale: (s: TimeScale) => void) {
    const style = doc.createElement('style');
    style.textContent = MINI_CSS;
    doc.head.appendChild(style);

    this.root = doc.createElement('div');
    this.root.className = 'mini-root';

    const when = doc.createElement('div');
    when.className = 'mini-when';
    this.era = doc.createElement('span');
    this.era.className = 'mini-era';
    this.date = doc.createElement('span');
    this.date.className = 'mini-date';
    when.append(this.era, this.date);

    const speeds = doc.createElement('div');
    speeds.className = 'mini-speeds';
    for (const s of ALL_SCALES) {
      const b = doc.createElement('button');
      b.textContent = scaleShortLabel(s);
      b.title = scaleLabel(s);
      b.addEventListener('click', () => onScale(s));
      speeds.appendChild(b);
      this.buttons.set(s, b);
    }

    const popWrap = doc.createElement('div');
    popWrap.className = 'mini-pop';
    this.pop = doc.createElement('b');
    this.ref = doc.createElement('span');
    popWrap.append(this.pop, this.ref);

    this.root.append(when, speeds, popWrap);
  }

  setScale(scale: TimeScale): void {
    for (const [s, b] of this.buttons) b.classList.toggle('active', s === scale);
  }

  update(stats: SimStats, clockText: string, dateText: string): void {
    this.era.textContent = stats.eraLabel;
    this.date.textContent = `${dateText} ${clockText}`;
    this.pop.textContent = formatPopulation(stats.population);
    const ratio = stats.referencePopulation > 0 ? (stats.population / stats.referencePopulation) * 100 : 100;
    this.ref.textContent = `역사 대비 ${ratio.toFixed(0)}%`;
  }

  dispose(): void {
    this.root.remove();
  }
}
