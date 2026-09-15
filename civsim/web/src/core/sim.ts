/**
 * The simulation orchestrator: one macro step advances demographics, the economy, the land and the
 * historical anchors together.
 *
 * In "재현" (reproduction) mode the total population is steered toward the historical curve, but the
 * steering is applied as migration — which is what actually moved those people — and where they
 * settle is decided by the terrain, not by the script.
 */
import { COHORT_COUNT } from './pop/population.ts';
import { ERA_PROFILES, Era, eraForYear, eraName } from './era/eras.ts';
import { LandUse, World } from './world/worldData.ts';
import { RoadNetwork } from './settle/roads.ts';
import { SettlementSystem, type Settlement } from './settle/settlement.ts';
import { harvestModifier, stepEconomy } from './econ/economy.ts';
import { polityForYear, type Polity } from './polity/polity.ts';
import {
  PLACES, RESOLVED_ANCHORS, referencePopulation, type ResolvedAnchor,
} from './world/history.ts';
import { lonLatToLocal } from './geo/localFrame.ts';
import { Rng } from './rng.ts';
import { DEFAULT_END_JD, DEFAULT_START_JD, SimClock } from './time/simClock.ts';
import { jdToGregorian, gregorianToJd, dayOfYear } from './time/julian.ts';
import { TimeScale, SimLayers } from './time/timeScale.ts';

export type SimMode = 'reproduce' | 'emergent';

export interface LogEntry {
  year: number;
  title: string;
  detail: string;
  kind: string;
  x?: number;
  z?: number;
}

export interface SimStats {
  year: number;
  era: Era;
  eraLabel: string;
  polity: Polity;
  population: number;
  referencePopulation: number;
  settlements: number;
  builtCells: number;
  farmCells: number;
  foodRatio: number;
  births: number;
  deaths: number;
  netMigration: number;
  treasury: number;
  largestSettlement: string;
  largestPopulation: number;
}

export interface SimOptions {
  mode?: SimMode;
  seed?: number;
  startJd?: number;
  endJd?: number;
}

export class Simulation {
  readonly world: World;
  readonly clock: SimClock;
  readonly land: SettlementSystem;
  readonly roads = new RoadNetwork();
  readonly rng: Rng;
  mode: SimMode;

  readonly log: LogEntry[] = [];
  private readonly firedAnchors = new Set<number>();
  private lastRoadYear = -9999;
  private lastStats: SimStats;
  private accBirths = 0;
  private accDeaths = 0;
  private accMigration = 0;

  constructor(world: World, options: SimOptions = {}) {
    this.world = world;
    this.mode = options.mode ?? 'reproduce';
    this.rng = new Rng(options.seed ?? 20260915);
    this.clock = new SimClock(options.startJd ?? DEFAULT_START_JD, TimeScale.Paused, options.endJd ?? DEFAULT_END_JD);
    this.land = new SettlementSystem(world, this.rng.fork(7));
    this.lastStats = this.computeStats(1, 1);
  }

  get year(): number {
    const d = jdToGregorian(this.clock.jdUt);
    return d.year + (dayOfYear(this.clock.jdUt) - 1) / 365.25;
  }

  get era(): Era {
    return eraForYear(this.year);
  }

  get stats(): SimStats {
    return this.lastStats;
  }

  /** Advance the macro layer. Called with whole steps by the clock's debt accounting. */
  stepMacro(stepDays: number, steps: number): void {
    for (let n = 0; n < steps; n++) {
      this.macroStep(stepDays / 365.25);
    }
    this.lastStats = this.computeStats(this.accBirths, this.accDeaths);
  }

  private macroStep(years: number): void {
    const year = this.year;
    const era = eraForYear(year);

    this.fireAnchors(year);
    if (this.land.settlements.length === 0) return;

    let births = 0;
    let deaths = 0;
    const harvest = harvestModifier(year, this.rng.next(), era);

    for (const s of this.land.settlements) {
      if (s.cohorts.total < 0.5) continue;
      const res = this.land.resourcesOf(s);
      const econ = stepEconomy(s.econ, {
        era,
        isCapital: s.isCapital,
        workers: s.cohorts.workers,
        population: s.cohorts.total,
        farmQuality: res.farmQuality,
        woodland: res.woodland,
        stone: res.stone,
        clay: res.clay,
        harvestModifier: harvest,
        years,
      });
      s.foodRatio = econ.foodRatio;

      const crowding = Math.min(1, s.cohorts.total / Math.max(1, s.cells.length * ERA_PROFILES[era].cellCapacity));
      const d = s.cohorts.step(years, {
        era,
        foodRatio: econ.foodRatio,
        crowding,
        shockDeathRate: 0,
      });
      births += d.births;
      deaths += d.deaths;

      // Standing decays once a place is no longer the capital, which is how 한성 emptied out
      // after 475 and how 한양 took over from every other settlement on the river.
      const targetPrestige = s.isCapital ? 1 : 0.15;
      s.prestige += (targetPrestige - s.prestige) * Math.min(1, years * 0.05);

      // Attractiveness drives where migrants go: food first, then standing, then size.
      // Standing dominates: a capital does not merely outgrow its neighbours, it drains them.
      s.attractiveness =
        Math.max(0.05, Math.min(2, econ.foodRatio)) *
        Math.pow(0.15 + s.prestige, 2) *
        (0.5 + Math.log10(Math.max(10, s.cohorts.total)) * 0.2) *
        (1 - s.destroyedFraction * 0.5);
    }

    const migrated = this.applyMigration(year, years);
    this.accBirths += births;
    this.accDeaths += deaths;
    this.accMigration += migrated;

    for (const s of this.land.settlements) {
      this.land.stepLand(s, year, era);
    }

    this.maybeFoundSatellite(year, era);

    if (year - this.lastRoadYear > (era >= Era.Colonial ? 5 : 40)) {
      this.lastRoadYear = year;
      this.roads.connectSettlements(this.land, era);
      for (const s of this.land.settlements) this.roads.stampGrid(this.land, s, era);
    }
  }

  /**
   * Migration. Between settlements it follows the attractiveness gradient. With the play area as a
   * whole it is the term that carries Seoul from 200,000 people to ten million: in reproduction mode
   * the gap to the historical curve is closed by people arriving from outside, which is what happened.
   */
  private applyMigration(year: number, years: number): number {
    const settlements = this.land.settlements.filter((s) => s.cohorts.total > 1);
    if (settlements.length === 0) return 0;

    // Internal redistribution.
    if (settlements.length > 1) {
      const totalPull = settlements.reduce((a, s) => a + s.attractiveness, 0);
      const movers: Array<{ s: Settlement; amount: number }> = [];
      for (const s of settlements) {
        const share = s.attractiveness / totalPull;
        const expected = this.land.totalPopulation * share;
        const excess = s.cohorts.total - expected;
        if (excess > 0) {
          const rate = Math.min(0.12, 0.05 * years);
          movers.push({ s, amount: excess * rate });
        }
      }
      for (const m of movers) {
        const leaving = m.s.cohorts.removeMigrants(m.amount);
        let sum = 0;
        for (let i = 0; i < leaving.length; i++) sum += leaving[i]!;
        if (sum <= 0) continue;
        const targets = settlements.filter((s) => s !== m.s);
        const pull = targets.reduce((a, s) => a + s.attractiveness, 0) || 1;
        for (const t of targets) {
          const f = t.attractiveness / pull;
          const parcel = new Float64Array(leaving.length);
          for (let i = 0; i < leaving.length; i++) parcel[i] = leaving[i]! * f;
          t.cohorts.addMigrants(parcel);
        }
      }
    }

    if (this.mode !== 'reproduce') return 0;

    // External migration closes the gap to the historical curve.
    const actual = this.land.totalPopulation;
    const target = referencePopulation(year);
    const gap = target - actual;
    if (Math.abs(gap) < 1) return 0;
    // Close a fixed fraction of the gap per year, so the curve is tracked without a jump.
    const rate = 1 - Math.exp(-years / 1.8);
    const move = gap * rate;

    const totalPull = settlements.reduce((a, s) => a + s.attractiveness, 0) || 1;
    if (move > 0) {
      for (const s of settlements) {
        const share = s.attractiveness / totalPull;
        const arriving = new Float64Array(COHORT_COUNT);
        const incoming = move * share;
        // Migrants skew young and working-age.
        const weights = [0.09, 0.08, 0.09, 0.15, 0.17, 0.13, 0.1, 0.07, 0.05, 0.03, 0.02, 0.01, 0.005, 0.003, 0.002, 0.001, 0.0005, 0.0005];
        let wsum = 0;
        for (const w of weights) wsum += w;
        for (let i = 0; i < arriving.length; i++) arriving[i] = (incoming * (weights[i] ?? 0)) / wsum;
        s.cohorts.addMigrants(arriving);
      }
    } else {
      for (const s of settlements) {
        const share = s.cohorts.total / Math.max(1, actual);
        s.cohorts.removeMigrants(-move * share);
      }
    }
    return move;
  }

  /** New settlements appear when the core is full and there is good land within reach. */
  private maybeFoundSatellite(year: number, era: Era): void {
    const total = this.land.totalPopulation;
    const wanted = total < 60000 ? 1 : total < 300000 ? 3 : total < 1500000 ? 6 : total < 5000000 ? 10 : 14;
    if (this.land.settlements.length >= wanted) return;

    const names = ['마포나루', '노량진', '뚝섬', '양천', '망우', '수유', '구로', '금천', '상계', '광나루', '신촌', '왕십리', '영등포', '청량리'];
    const known: Record<string, { lat: number; lon: number }> = {
      마포나루: PLACES.mapo, 노량진: PLACES.noryangjin, 뚝섬: PLACES.ttukseom, 양천: PLACES.yangcheon,
    };

    // Look for the best unsettled, open, buildable spot at least 3 km from every existing centre.
    const w = this.world;
    let bestK = -1;
    let bestScore = 0;
    for (let j = 2; j < w.nz - 2; j += 3) {
      for (let i = 2; i < w.nx - 2; i += 3) {
        const k = w.index(i, j);
        if (this.land.cellSettlement[k] !== -1) continue;
        if (this.land.water[k] === 1) continue;
        if (year < this.land.cellOpenYear[k]!) continue;
        const { x, z } = w.cellCentre(i, j);
        let minDist = Infinity;
        for (const s of this.land.settlements) minDist = Math.min(minDist, Math.hypot(x - s.x, z - s.z));
        if (minDist < 3000 || minDist > 16000) continue;
        const score =
          this.land.buildable[k]! * 1.4 +
          w.fertility[k]! +
          Math.exp(-w.distanceToWater[k]! / 2000) * (era >= Era.Industrial ? 0.3 : 1.0) +
          (this.land.cellRoad[k]! > 0 ? 0.5 : 0);
        if (score > bestScore) {
          bestScore = score;
          bestK = k;
        }
      }
    }
    if (bestK < 0 || bestScore < 1.2) return;

    const i = bestK % w.nx;
    const j = (bestK - i) / w.nx;
    const { x, z } = w.cellCentre(i, j);
    // Prefer a real place name when the site is close to one.
    let name = '';
    for (const [n, p] of Object.entries(known)) {
      const local = lonLatToLocal(p.lon, p.lat);
      if (Math.hypot(local.x - x, local.z - z) < 2500 && !this.land.settlements.some((s) => s.name === n)) {
        name = n;
        break;
      }
    }
    if (!name) {
      const unused = names.filter((n) => !this.land.settlements.some((s) => s.name === n));
      name = unused.length > 0 ? this.rng.pick(unused) : this.land.nextName();
    }

    const seed = Math.max(80, this.land.totalPopulation * 0.01);
    const polity = polityForYear(year);
    const s = this.land.found(name, x, z, seed, Math.floor(year), polity.id);
    this.addLog(year, `${name} 취락 형성`, '사람들이 새 자리를 잡는다.', 'found', s.x, s.z);
  }

  private fireAnchors(year: number): void {
    for (let idx = 0; idx < RESOLVED_ANCHORS.length; idx++) {
      const a = RESOLVED_ANCHORS[idx]!;
      if (this.firedAnchors.has(idx)) continue;
      if (year < a.fireYear) continue;
      this.firedAnchors.add(idx);
      this.applyAnchor(a, year);
    }
  }

  private applyAnchor(a: ResolvedAnchor, year: number): void {
    const era = eraForYear(year);
    const polity = polityForYear(year);
    // Log the year the event belongs to, not the year the annual step happened to notice it.
    this.addLog(a.year, a.title, a.detail, a.kind, a.x, a.z);

    switch (a.kind) {
      case 'found': {
        if (!this.land.settlements.some((s) => Math.hypot(s.x - a.x, s.z - a.z) < 2500)) {
          const seed = Math.max(400, referencePopulation(year) * 0.5);
          const s = this.land.found(a.title.replace(/\s.*$/, ''), a.x, a.z, seed, Math.floor(year), polity.id);
          if (this.land.settlements.length === 1) s.isCapital = true;
        }
        break;
      }
      case 'capital': {
        const previous = this.land.settlements.find((s) => s.isCapital) ?? null;
        let target = this.nearestSettlement(a.x, a.z, 4000);
        if (!target) {
          target = this.land.found(
            a.settlementName ?? polity.shortName,
            a.x, a.z,
            Math.max(2000, referencePopulation(year) * 0.2),
            Math.floor(year), polity.id,
          );
        }
        if (a.settlementName) target.name = a.settlementName;
        for (const s of this.land.settlements) s.isCapital = false;
        target.isCapital = true;
        target.prestige = 1;
        target.polityId = polity.id;

        // A court moving is not only a label: the officials, the garrison, the markets and the
        // people who live off them move too.
        if (previous && previous !== target) {
          previous.prestige = 0.2;
          const moving = previous.cohorts.total * 0.55;
          const parcel = previous.cohorts.removeMigrants(moving);
          target.cohorts.addMigrants(parcel);
          this.addLog(a.year, `${previous.name}에서 ${target.name}으로`, '사람과 관청이 새 도읍으로 옮겨간다.', 'capital', target.x, target.z);
        }
        break;
      }
      case 'wall': {
        const s = this.nearestSettlement(a.x, a.z, 6000);
        if (s) {
          // 한양도성 runs about 18.6 km around the inner mountains; earlier earthworks are smaller.
          const radius = era >= Era.JoseonEarly ? 2500 : 700;
          this.land.buildWall(s, radius, era >= Era.JoseonEarly ? 1100 : 300);
        }
        break;
      }
      case 'palace': {
        this.land.placeMonument(a.x, a.z, era >= Era.Industrial ? 160 : 240);
        break;
      }
      case 'war':
      case 'disaster': {
        if (a.destructionRadiusM && a.destructionFraction) {
          this.land.damage(a.x, a.z, a.destructionRadiusM, a.destructionFraction);
        }
        if (a.populationFactor) {
          for (const s of this.land.settlements) {
            const dist = Math.hypot(s.x - a.x, s.z - a.z);
            const reach = (a.destructionRadiusM ?? 4000) * 2.5;
            const f = 1 - (1 - a.populationFactor) * Math.max(0.25, 1 - dist / reach);
            s.cohorts.scaleTo(s.cohorts.total * f);
            s.destroyedFraction = Math.min(1, s.destroyedFraction + (1 - f));
          }
        }
        break;
      }
      case 'landfill': {
        const radius = a.title.includes('여의도') ? 1500 : a.title.includes('잠실') ? 2200 : 1200;
        this.land.reclaim(a.x, a.z, radius, year);
        this.land.openLand(a.x, a.z, radius, year);
        break;
      }
      case 'boundary': {
        const radius = a.year >= 1963 ? 14000 : 7000;
        this.land.openLand(a.x, a.z, radius, year);
        break;
      }
      case 'infra':
      case 'era':
        break;
    }
    for (const s of this.land.settlements) s.destroyedFraction = Math.max(0, s.destroyedFraction - 0.02);
  }

  private nearestSettlement(x: number, z: number, maxDist: number): Settlement | null {
    let best: Settlement | null = null;
    let bestD = maxDist;
    for (const s of this.land.settlements) {
      const d = Math.hypot(s.x - x, s.z - z);
      if (d < bestD) {
        bestD = d;
        best = s;
      }
    }
    return best;
  }

  addLog(year: number, title: string, detail: string, kind: string, x?: number, z?: number): void {
    this.log.push({ year, title, detail, kind, x, z });
    if (this.log.length > 400) this.log.shift();
  }

  private computeStats(births: number, deaths: number): SimStats {
    const year = this.year;
    const era = eraForYear(year);
    let farm = 0;
    for (let k = 0; k < this.land.cellUse.length; k++) if (this.land.cellUse[k] === LandUse.Farm) farm++;
    let largest: Settlement | null = null;
    for (const s of this.land.settlements) {
      if (!largest || s.cohorts.total > largest.cohorts.total) largest = s;
    }
    let foodRatio = 1;
    if (this.land.settlements.length > 0) {
      let sum = 0;
      let w = 0;
      for (const s of this.land.settlements) {
        sum += s.foodRatio * s.cohorts.total;
        w += s.cohorts.total;
      }
      foodRatio = w > 0 ? sum / w : 1;
    }
    return {
      year,
      era,
      eraLabel: eraName(era),
      polity: polityForYear(year),
      population: this.land.totalPopulation,
      referencePopulation: referencePopulation(year),
      settlements: this.land.settlements.length,
      builtCells: this.land.builtCellCount,
      farmCells: farm,
      foodRatio,
      births,
      deaths,
      netMigration: this.accMigration,
      treasury: this.land.settlements.reduce((a, s) => a + s.econ.treasury, 0),
      largestSettlement: largest?.name ?? '-',
      largestPopulation: largest?.cohorts.total ?? 0,
    };
  }

  /** Advance the clock by real time and run whatever layers that speed enables. */
  update(realDeltaSeconds: number): void {
    this.clock.advance(realDeltaSeconds);
    const { steps, stepDays } = this.clock.takeMacroSteps();
    if (steps > 0 && this.clock.activeLayers & (SimLayers.Macro | SimLayers.Meso)) {
      this.stepMacro(stepDays, steps);
    } else if (steps > 0) {
      // At micro speeds the macro layer still needs to tick, just rarely.
      this.stepMacro(stepDays, steps);
    }
  }

  /** Run headless from the start to a given year. Used by tests and by the fast-forward button. */
  runTo(targetYear: number, stepDays = 365.25): SimStats {
    const targetJd = gregorianToJd(Math.floor(targetYear), 1, 1);
    let guard = 0;
    while (this.clock.jdUt < targetJd && guard++ < 40000) {
      this.clock.advanceSimSeconds(stepDays * 86400);
      this.stepMacro(stepDays, 1);
    }
    return this.stats;
  }
}

export { DEFAULT_START_JD, DEFAULT_END_JD };
