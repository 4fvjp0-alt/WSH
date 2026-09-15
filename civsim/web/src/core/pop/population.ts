/**
 * Cohort demographics. Five-year age bands, no sex split (it buys little at this scale and
 * doubles the state). Rates come from the era profile and are modulated by food, crowding and war.
 */
import { ERA_PROFILES, type Era } from '../era/eras.ts';

export const COHORT_COUNT = 18; // 0-4, 5-9, ... 85+
export const COHORT_YEARS = 5;

export interface DemographicInputs {
  era: Era;
  /** Food available per person, 1.0 = subsistence. */
  foodRatio: number;
  /** 0..1, how tightly packed the settlement is relative to what the era can support. */
  crowding: number;
  /** Extra deaths per 1000 from an ongoing event. */
  shockDeathRate: number;
}

export class Cohorts {
  /** People in each five-year band. */
  readonly bands: Float64Array;

  constructor(total = 0) {
    this.bands = new Float64Array(COHORT_COUNT);
    if (total > 0) this.seedStable(total);
  }

  get total(): number {
    let s = 0;
    for (let i = 0; i < COHORT_COUNT; i++) s += this.bands[i]!;
    return s;
  }

  /** Working-age population, 15-64. */
  get workers(): number {
    let s = 0;
    for (let i = 3; i < 13; i++) s += this.bands[i]!;
    return s;
  }

  get children(): number {
    return this.bands[0]! + this.bands[1]! + this.bands[2]!;
  }

  get elders(): number {
    let s = 0;
    for (let i = 13; i < COHORT_COUNT; i++) s += this.bands[i]!;
    return s;
  }

  /** A pre-industrial pyramid: wide base, steep decline. */
  seedStable(total: number): void {
    let sum = 0;
    const w = new Float64Array(COHORT_COUNT);
    for (let i = 0; i < COHORT_COUNT; i++) {
      w[i] = Math.exp(-i * 0.28);
      sum += w[i]!;
    }
    for (let i = 0; i < COHORT_COUNT; i++) this.bands[i] = (total * w[i]!) / sum;
  }

  scaleTo(total: number): void {
    const cur = this.total;
    if (cur <= 0) {
      this.seedStable(total);
      return;
    }
    const f = total / cur;
    for (let i = 0; i < COHORT_COUNT; i++) this.bands[i]! *= f;
  }

  /**
   * Advance by `years`. Returns births and deaths so callers can report them.
   * Ageing is fractional: a `years/5` share of each band moves up, which keeps the pyramid
   * smooth at any step length instead of only working for whole five-year jumps.
   */
  step(years: number, input: DemographicInputs): { births: number; deaths: number } {
    const p = ERA_PROFILES[input.era];
    const food = Math.max(0.2, Math.min(2.5, input.foodRatio));

    // Hunger raises mortality sharply below subsistence and lowers fertility.
    const hungerDeath = food < 1 ? (1 - food) * 60 : 0;
    const crowdDeath = input.crowding * (p.deathRate > 20 ? 8 : 2);
    const deathRate = (p.deathRate + hungerDeath + crowdDeath + input.shockDeathRate) / 1000;
    const birthRate = (p.birthRate * Math.min(1, 0.45 + 0.55 * food)) / 1000;

    const total = this.total;
    const births = total * birthRate * years;
    let deaths = 0;

    // Age-specific mortality multipliers: infants and elders die first.
    const ageMult = [3.2, 0.7, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.3, 1.6, 2.1, 2.9, 4.2, 6.4, 10, 16, 26];
    const flow = Math.min(1, years / COHORT_YEARS);

    for (let i = COHORT_COUNT - 1; i >= 0; i--) {
      const band = this.bands[i]!;
      if (band <= 0) continue;
      const d = Math.min(band, band * deathRate * ageMult[i]! * years);
      deaths += d;
      this.bands[i] = band - d;
    }
    // Ageing, from the top down so nobody skips a band.
    for (let i = COHORT_COUNT - 1; i > 0; i--) {
      const moving = this.bands[i - 1]! * flow;
      this.bands[i]! += moving;
      this.bands[i - 1]! -= moving;
    }
    this.bands[0]! += births;

    for (let i = 0; i < COHORT_COUNT; i++) if (this.bands[i]! < 0) this.bands[i] = 0;
    return { births, deaths };
  }

  /** Move `count` people out, taken proportionally but weighted toward working age. */
  removeMigrants(count: number): Float64Array {
    const taken = new Float64Array(COHORT_COUNT);
    const weights = new Float64Array(COHORT_COUNT);
    let wsum = 0;
    for (let i = 0; i < COHORT_COUNT; i++) {
      weights[i] = this.bands[i]! * (i >= 3 && i <= 10 ? 1.8 : 0.6);
      wsum += weights[i]!;
    }
    if (wsum <= 0) return taken;
    const f = Math.min(1, count / wsum);
    for (let i = 0; i < COHORT_COUNT; i++) {
      const t = Math.min(this.bands[i]!, weights[i]! * f);
      taken[i] = t;
      this.bands[i]! -= t;
    }
    return taken;
  }

  addMigrants(migrants: Float64Array): void {
    for (let i = 0; i < COHORT_COUNT; i++) this.bands[i]! += migrants[i]!;
  }

  static cohortLabel(i: number): string {
    return i === COHORT_COUNT - 1 ? '85+' : `${i * 5}-${i * 5 + 4}`;
  }
}
