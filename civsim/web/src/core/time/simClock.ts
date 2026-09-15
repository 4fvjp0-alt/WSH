/**
 * The one clock every system reads. Time is a Julian Day in UT; the speed is a TimeScale.
 * The clock accumulates macro-step debt so callers can run whole days/months/years at once,
 * independently of frame rate.
 */
import { SECONDS_PER_DAY, gregorianToJd, type CalendarDate } from './julian.ts';
import { formatLocalTime, toLocalDate } from './koreaTime.ts';
import { TimeScale, activeLayers, macroStepDays, simSecondsPerRealSecond } from './timeScale.ts';

/** AD 100, spring equinox: a small riverside village era on the Han. */
export const DEFAULT_START_JD = gregorianToJd(100, 3, 21) + 0.25; // 06:00 UT

/** The simulation stops here; the present day. */
export const DEFAULT_END_JD = gregorianToJd(2026, 12, 31);

export class SimClock {
  jdUt: number;
  scale: TimeScale;
  endJd: number;
  totalFrames = 0;
  private macroDebtDays = 0;
  private lastMacroJd: number;
  /** Set when the clock reaches endJd. */
  finished = false;

  constructor(startJd: number = DEFAULT_START_JD, scale: TimeScale = TimeScale.Paused, endJd = DEFAULT_END_JD) {
    this.jdUt = startJd;
    this.scale = scale;
    this.endJd = endJd;
    this.lastMacroJd = startJd;
  }

  get simSecondsPerRealSecond(): number {
    return simSecondsPerRealSecond(this.scale);
  }

  get activeLayers(): number {
    return activeLayers(this.scale);
  }

  get macroStepDays(): number {
    return macroStepDays(this.scale);
  }

  /** Called once per rendered frame with the real elapsed seconds. */
  advance(realDeltaSeconds: number): void {
    if (realDeltaSeconds <= 0) return;
    this.advanceSimSeconds(realDeltaSeconds * this.simSecondsPerRealSecond);
    this.totalFrames++;
  }

  advanceSimSeconds(simSeconds: number): void {
    if (simSeconds === 0) return;
    this.jdUt += simSeconds / SECONDS_PER_DAY;
    if (this.jdUt >= this.endJd) {
      this.jdUt = this.endJd;
      this.finished = true;
      this.scale = TimeScale.Paused;
    }
  }

  /** Jump to an absolute date. Macro debt is discarded; callers re-seed derived state. */
  jumpTo(jdUt: number): void {
    this.jdUt = jdUt;
    this.lastMacroJd = jdUt;
    this.macroDebtDays = 0;
    this.finished = false;
  }

  /**
   * How many macro steps of `macroStepDays` are owed since the last call, so the macro layer
   * can catch up in whole steps. Capped so a single stalled frame cannot freeze the app.
   */
  takeMacroSteps(maxSteps = 512): { steps: number; stepDays: number } {
    const stepDays = this.macroStepDays;
    this.macroDebtDays += this.jdUt - this.lastMacroJd;
    this.lastMacroJd = this.jdUt;
    if (this.macroDebtDays < stepDays) return { steps: 0, stepDays };
    let steps = Math.floor(this.macroDebtDays / stepDays);
    if (steps > maxSteps) {
      steps = maxSteps;
      this.macroDebtDays = 0; // drop the backlog rather than spiralling
      return { steps, stepDays };
    }
    this.macroDebtDays -= steps * stepDays;
    return { steps, stepDays };
  }

  get localDate(): CalendarDate {
    return toLocalDate(this.jdUt);
  }

  get localTimeText(): string {
    return formatLocalTime(this.jdUt);
  }

  /** Progress through the whole simulated span, 0..1. */
  progress(startJd = DEFAULT_START_JD): number {
    return Math.max(0, Math.min(1, (this.jdUt - startJd) / (this.endJd - startJd)));
  }
}
