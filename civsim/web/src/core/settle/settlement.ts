/**
 * Settlements, the land they occupy, and how they spread.
 *
 * Population totals are steered by history; where those people end up living is not. A cell is
 * claimed because it is flat, dry, near water and close to what is already built, so the city
 * grows into the Seoul basin, is held back by the mountains, and crosses the Han only once the
 * administrative anchors open the south bank.
 */
import { Cohorts } from '../pop/population.ts';
import { ERA_PROFILES, Era } from '../era/eras.ts';
import { LandUse, World } from '../world/worldData.ts';
import { newEconomy, type EconomyState } from '../econ/economy.ts';
import { Rng, hash2 } from '../rng.ts';

export interface Settlement {
  id: number;
  name: string;
  /** Centre in local metres. */
  x: number;
  z: number;
  ci: number;
  cj: number;
  cells: number[];
  cohorts: Cohorts;
  econ: EconomyState;
  polityId: number;
  isCapital: boolean;
  /** 0..1 standing. A capital pulls people; an abandoned one slowly stops. */
  prestige: number;
  foundedYear: number;
  foodRatio: number;
  /** 0..1 pull for migrants, from food, size and capital status. */
  attractiveness: number;
  /** Cells that are candidates for the next expansion. */
  frontier: Set<number>;
  walls: number[];
  monuments: number[];
  /** Cells this settlement currently farms; tracked so abandoned fields revert. */
  farm: Set<number>;
  destroyedFraction: number;
}

export interface SettlementTuning {
  /** Metres of decay in the density gradient from a settlement's centre. */
  densityScaleM: number;
  /** How far farmland reaches beyond the built edge. */
  farmRadiusFactor: number;
}

export const DEFAULT_TUNING: SettlementTuning = { densityScaleM: 1800, farmRadiusFactor: 2.2 };

export class SettlementSystem {
  readonly world: World;
  readonly settlements: Settlement[] = [];

  /** People living in each cell. */
  readonly cellPop: Float32Array;
  /** 0..1 how built-up the cell is; drives building height on screen. */
  readonly cellBuild: Float32Array;
  readonly cellUse: Uint8Array;
  readonly cellSettlement: Int16Array;
  /** 0 none, 1 track, 2 street, 3 arterial. */
  readonly cellRoad: Uint8Array;
  readonly cellWall: Uint8Array;
  readonly cellMonument: Uint8Array;
  /** Damage left by war or flood, decays as the city rebuilds. */
  readonly cellDamage: Float32Array;
  /** Earliest year a cell may be built on. Reclamation moves this for the cells it creates. */
  readonly cellOpenYear: Float32Array;
  /** Which bank of the Han a cell is on: +1 north, -1 south, 0 in the channel. */
  readonly cellSide: Int8Array;
  /** The year a settlement on the far bank may first expand into this cell. */
  readonly cellCrossYear: Float32Array;

  /**
   * Mutable copies of the terrain fields reclamation changes. The World stays immutable so two
   * simulations can share one loaded map and still run identically.
   */
  readonly water: Uint8Array;
  readonly buildable: Float32Array;
  readonly height: Float32Array;

  private readonly rng: Rng;
  private readonly tuning: SettlementTuning;

  constructor(world: World, rng: Rng, tuning: SettlementTuning = DEFAULT_TUNING) {
    this.world = world;
    this.rng = rng;
    this.tuning = tuning;
    const n = world.nx * world.nz;
    this.cellPop = new Float32Array(n);
    this.cellBuild = new Float32Array(n);
    this.cellUse = new Uint8Array(n);
    this.cellSettlement = new Int16Array(n).fill(-1);
    this.cellRoad = new Uint8Array(n);
    this.cellWall = new Uint8Array(n);
    this.cellMonument = new Uint8Array(n);
    this.cellDamage = new Float32Array(n);
    this.cellOpenYear = new Float32Array(n);
    this.cellSide = new Int8Array(n);
    this.cellCrossYear = new Float32Array(n);
    this.water = Uint8Array.from(world.water);
    this.buildable = Float32Array.from(world.buildable);
    this.height = Float32Array.from(world.height);
    this.initLandUse();
    this.initOpenYears();
  }

  private initLandUse(): void {
    for (let k = 0; k < this.cellUse.length; k++) {
      this.cellUse[k] = this.water[k] === 1 ? LandUse.Water : LandUse.Wild;
    }
  }

  /**
   * Which bank each cell is on, and when a city on the other bank may reach it.
   *
   * This is the constraint that actually shaped Seoul. 한성백제 sat on the south bank and grew
   * there freely. When the capital moved to 한양 in 1394 it was a north-bank city, and it stayed
   * north of the river for five and a half centuries: 영등포 came in with the rail bridge and the
   * 1936 annexation, and everything else south of the Han waited for the great expansion of 1963.
   */
  private initOpenYears(): void {
    const w = this.world;
    const northEdge = new Float32Array(w.nx);
    const southEdge = new Float32Array(w.nx);
    for (let i = 0; i < w.nx; i++) {
      let lo = -1;
      let hi = -1;
      for (let j = 0; j < w.nz; j++) {
        if (this.water[w.index(i, j)] === 1) {
          if (lo < 0) lo = j;
          hi = j;
        }
      }
      southEdge[i] = lo < 0 ? w.nz / 2 : lo;
      northEdge[i] = hi < 0 ? w.nz / 2 : hi;
    }

    for (let j = 0; j < w.nz; j++) {
      for (let i = 0; i < w.nx; i++) {
        const k = w.index(i, j);
        if (this.water[k] === 1) {
          this.cellOpenYear[k] = 9999;
          this.cellSide[k] = 0;
          this.cellCrossYear[k] = 9999;
          continue;
        }
        this.cellOpenYear[k] = 100;
        if (j > northEdge[i]!) {
          this.cellSide[k] = 1;
          this.cellCrossYear[k] = 1900; // the north bank was always reachable from the south
        } else if (j < southEdge[i]!) {
          this.cellSide[k] = -1;
          const { x, z } = w.cellCentre(i, j);
          const nearYeongdeungpo = Math.hypot(x + 3200, z + 5900) < 6000;
          this.cellCrossYear[k] = nearYeongdeungpo ? 1900 : 1963;
        } else {
          this.cellSide[k] = 0;
          this.cellCrossYear[k] = 9999;
        }
      }
    }
  }

  /** The bank a settlement's centre stands on. */
  sideOf(s: Settlement): number {
    return this.cellSide[this.world.index(s.ci, s.cj)]!;
  }

  cellIndexAt(x: number, z: number): number {
    const { i, j } = this.world.cellAt(x, z);
    return this.world.inBounds(i, j) ? this.world.index(i, j) : -1;
  }

  found(name: string, x: number, z: number, population: number, year: number, polityId: number): Settlement {
    const { i, j } = this.world.cellAt(x, z);
    const ci = Math.max(1, Math.min(this.world.nx - 2, i));
    const cj = Math.max(1, Math.min(this.world.nz - 2, j));
    const s: Settlement = {
      id: this.settlements.length,
      name,
      x, z, ci, cj,
      cells: [],
      cohorts: new Cohorts(population),
      econ: newEconomy(population),
      polityId,
      isCapital: false,
      prestige: 0.3,
      foundedYear: year,
      foodRatio: 1,
      attractiveness: 1,
      frontier: new Set(),
      walls: [],
      monuments: [],
      farm: new Set(),
      destroyedFraction: 0,
    };
    this.settlements.push(s);
    this.claimCell(s, this.world.index(ci, cj));
    return s;
  }

  private claimCell(s: Settlement, k: number): void {
    if (this.cellSettlement[k] !== -1) return;
    this.cellSettlement[k] = s.id;
    s.cells.push(k);
    s.frontier.delete(k);
    const i = k % this.world.nx;
    const j = (k - i) / this.world.nx;
    for (let dj = -1; dj <= 1; dj++) {
      for (let di = -1; di <= 1; di++) {
        if (!di && !dj) continue;
        const ni = i + di;
        const nj = j + dj;
        if (!this.world.inBounds(ni, nj)) continue;
        const nk = this.world.index(ni, nj);
        if (this.cellSettlement[nk] === -1) s.frontier.add(nk);
      }
    }
  }

  /** How good a cell is for the next block of the city. */
  private cellScore(s: Settlement, k: number, year: number, era: Era): number {
    const w = this.world;
    if (this.cellSettlement[k] !== -1) return -1;
    if (year < this.cellOpenYear[k]!) return -1;
    if (this.water[k] === 1) return -1;
    // A city may not spread across the Han before the bridges and the annexations.
    const side = this.cellSide[k]!;
    if (side !== 0 && side !== this.sideOf(s) && year < this.cellCrossYear[k]!) return -1;
    const build = this.buildable[k]!;
    if (build <= 0.02) return -1;

    const i = k % w.nx;
    const j = (k - i) / w.nx;
    const { x, z } = w.cellCentre(i, j);
    const d = Math.hypot(x - s.x, z - s.z);
    const scale = this.tuning.densityScaleM * (1 + Math.sqrt(s.cells.length) * 0.18);
    const proximity = Math.exp(-d / scale);

    // Pre-industrial towns cling to water; modern ones care far less.
    const waterWeight = era >= Era.Industrial ? 0.15 : era >= Era.Colonial ? 0.35 : 0.8;
    const waterPull = Math.exp(-w.distanceToWater[k]! / 2500) * waterWeight;
    const fertile = w.fertility[k]! * (era >= Era.Colonial ? 0.15 : 0.6);
    const road = this.cellRoad[k]! > 0 ? 0.35 : 0;
    const flat = 1 - Math.min(1, w.relief[k]! / 35);
    const jitter = 0.85 + hash2(i, j, 97) * 0.3;

    return (build * 1.2 + flat * 0.6 + fertile + waterPull + road) * proximity * jitter;
  }

  /** Grow a settlement so it has room for its people. */
  private expand(s: Settlement, year: number, era: Era): void {
    const p = ERA_PROFILES[era];
    const pop = s.cohorts.total;
    if (pop <= 0) return;
    // Cities build upward before they build outward: the effective density rises with size.
    const sizeFactor = Math.min(1, 0.35 + Math.log10(Math.max(10, pop)) * 0.16);
    const perCell = Math.max(8, p.cellCapacity * sizeFactor);
    const wanted = Math.ceil(pop / perCell);
    let deficit = wanted - s.cells.length;
    if (deficit <= 0) return;
    // Cap growth per step so a city cannot teleport across the basin in one year.
    deficit = Math.min(deficit, Math.max(4, Math.ceil(s.cells.length * 0.35) + 8));

    const candidates: Array<{ k: number; score: number }> = [];
    for (const k of s.frontier) {
      const score = this.cellScore(s, k, year, era);
      if (score > 0) candidates.push({ k, score });
    }
    if (candidates.length === 0) {
      // Boxed in: allow a jump to the best cell in a wider ring (a satellite town forming).
      return;
    }
    candidates.sort((a, b) => b.score - a.score);
    for (let n = 0; n < Math.min(deficit, candidates.length); n++) {
      this.claimCell(s, candidates[n]!.k);
    }
  }

  /**
   * Give up ground. When a city loses its people - a sack, a capital moving away - the outer
   * quarters are abandoned and go back to scrub, rather than staying on the map as a phantom city.
   */
  private contract(s: Settlement, era: Era): void {
    const p = ERA_PROFILES[era];
    const pop = s.cohorts.total;
    const sizeFactor = Math.min(1, 0.35 + Math.log10(Math.max(10, pop)) * 0.16);
    const perCell = Math.max(8, p.cellCapacity * sizeFactor);
    const wanted = Math.max(1, Math.ceil(pop / perCell));
    if (s.cells.length <= wanted * 1.35) return;

    const w = this.world;
    const keep = Math.max(1, Math.ceil(wanted * 1.1));
    const scored = s.cells.map((k) => {
      const i = k % w.nx;
      const j = (k - i) / w.nx;
      const { x, z } = w.cellCentre(i, j);
      const d = Math.hypot(x - s.x, z - s.z);
      // Hold on to the core and to anything monumental or walled.
      const anchor = this.cellMonument[k] || this.cellWall[k] ? 1e9 : 0;
      return { k, value: anchor + this.buildable[k]! * 1000 - d };
    });
    scored.sort((a, b) => b.value - a.value);
    for (let n = keep; n < scored.length; n++) {
      const k = scored[n]!.k;
      this.cellSettlement[k] = -1;
      this.cellPop[k] = 0;
      this.cellBuild[k] = 0;
      this.cellDamage[k] = 0;
      if (this.cellUse[k] !== LandUse.Water && !this.cellMonument[k] && !this.cellWall[k]) {
        this.cellUse[k] = w.fertility[k]! > 0.45 ? LandUse.Farm : LandUse.Wild;
      }
      s.frontier.add(k);
    }
    s.cells = scored.slice(0, keep).map((e) => e.k);
  }

  /** Spread a settlement's people over its cells and derive land use. */
  private distribute(s: Settlement, era: Era): void {
    const w = this.world;
    const p = ERA_PROFILES[era];
    const pop = s.cohorts.total;
    const scale = this.tuning.densityScaleM * (1 + Math.sqrt(s.cells.length) * 0.18);

    let weightSum = 0;
    const weights = new Float64Array(s.cells.length);
    for (let n = 0; n < s.cells.length; n++) {
      const k = s.cells[n]!;
      const i = k % w.nx;
      const j = (k - i) / w.nx;
      const { x, z } = w.cellCentre(i, j);
      const d = Math.hypot(x - s.x, z - s.z);
      const decay = Math.exp(-d / scale);
      const damage = 1 - this.cellDamage[k]!;
      const wgt = Math.max(0.001, this.buildable[k]! * decay * damage * (1 + this.cellRoad[k]! * 0.15));
      weights[n] = wgt;
      weightSum += wgt;
    }
    if (weightSum <= 0) return;

    const capacity = p.cellCapacity;
    for (let n = 0; n < s.cells.length; n++) {
      const k = s.cells[n]!;
      const cp = (pop * weights[n]!) / weightSum;
      this.cellPop[k] = cp;
      this.cellBuild[k] = Math.min(1, Math.pow(cp / capacity, 0.55));
      this.cellUse[k] = this.classify(k, cp, era);
    }
  }

  private classify(k: number, cellPop: number, era: Era): LandUse {
    if (this.cellMonument[k]) return LandUse.Monument;
    if (this.cellWall[k]) return LandUse.Wall;
    if (this.water[k] === 1) return LandUse.Water;
    if (this.cellRoad[k]! >= 2 && cellPop < 30) return LandUse.Road;
    if (cellPop < 2) return this.world.fertility[k]! > 0.45 ? LandUse.Farm : LandUse.Wild;
    if (cellPop < 40) return LandUse.Village;
    if (cellPop < 220) return LandUse.Town;
    if (cellPop < 1200) return LandUse.Urban;
    if (era >= Era.Industrial && this.world.distanceToWater[k]! < 1200 && hash2(k, 3, 7) < 0.22) {
      return LandUse.Industrial;
    }
    return LandUse.Dense;
  }

  /**
   * Farmland follows the settled area outward, on whatever ground will take a crop, and is given
   * up again when the city paves over it or when the era stops feeding itself locally.
   */
  private updateFarmland(s: Settlement, era: Era): void {
    const w = this.world;
    // How much land this settlement needs to feed itself; the modern city imports nearly everything.
    const selfSufficiency = era >= Era.Modern ? 0.02 : era >= Era.Industrial ? 0.12 : era >= Era.Colonial ? 0.5 : 1;
    const radius = Math.sqrt((s.cells.length * w.cellM * w.cellM) / Math.PI) *
      this.tuning.farmRadiusFactor * selfSufficiency;

    const keep = new Set<number>();
    const ri = Math.ceil(radius / w.cellM);
    for (let dj = -ri; dj <= ri; dj++) {
      const j = s.cj + dj;
      if (j < 0 || j >= w.nz) continue;
      for (let di = -ri; di <= ri; di++) {
        const i = s.ci + di;
        if (i < 0 || i >= w.nx) continue;
        if (di * di + dj * dj > ri * ri) continue;
        const k = w.index(i, j);
        if (this.cellSettlement[k] !== -1) continue;
        if (this.water[k] === 1) continue;
        if (this.cellUse[k] !== LandUse.Wild && this.cellUse[k] !== LandUse.Farm) continue;
        if (w.fertility[k]! <= 0.42) continue;
        this.cellUse[k] = LandUse.Farm;
        keep.add(k);
      }
    }
    for (const k of s.farm) {
      if (!keep.has(k) && this.cellUse[k] === LandUse.Farm) this.cellUse[k] = LandUse.Wild;
    }
    s.farm = keep;
  }

  /** Summed cell qualities the economy needs. */
  resourcesOf(s: Settlement): { farmQuality: number; woodland: number; stone: number; clay: number } {
    const w = this.world;
    let farm = 0;
    for (const k of s.farm) farm += w.fertility[k]!;

    let wood = 0;
    let stone = 0;
    let clay = 0;
    const radius = Math.sqrt((s.cells.length * w.cellM * w.cellM) / Math.PI) * this.tuning.farmRadiusFactor;
    const ri = Math.ceil(radius / w.cellM);
    for (let dj = -ri; dj <= ri; dj += 2) {
      const j = s.cj + dj;
      if (j < 0 || j >= w.nz) continue;
      for (let di = -ri; di <= ri; di += 2) {
        const i = s.ci + di;
        if (i < 0 || i >= w.nx) continue;
        if (di * di + dj * dj > ri * ri) continue;
        const k = w.index(i, j);
        wood += w.woodland[k]!;
        stone += w.stone[k]!;
        clay += w.clay[k]!;
      }
    }
    return { farmQuality: farm, woodland: wood / 60, stone: stone / 60, clay: clay / 60 };
  }

  stepLand(s: Settlement, year: number, era: Era): void {
    this.contract(s, era);
    this.expand(s, year, era);
    this.updateFarmland(s, era);
    this.distribute(s, era);
    // Damage heals as the city rebuilds.
    for (const k of s.cells) {
      if (this.cellDamage[k]! > 0) this.cellDamage[k] = Math.max(0, this.cellDamage[k]! - 0.04);
    }
  }

  /** Destroy built fabric around a point. Used by war and flood anchors. */
  damage(x: number, z: number, radiusM: number, fraction: number): number {
    const w = this.world;
    const { i: ci, j: cj } = w.cellAt(x, z);
    const ri = Math.ceil(radiusM / w.cellM);
    let affected = 0;
    for (let dj = -ri; dj <= ri; dj++) {
      const j = cj + dj;
      if (j < 0 || j >= w.nz) continue;
      for (let di = -ri; di <= ri; di++) {
        const i = ci + di;
        if (i < 0 || i >= w.nx) continue;
        const dist = Math.hypot(di, dj) * w.cellM;
        if (dist > radiusM) continue;
        const k = w.index(i, j);
        if (this.cellSettlement[k] === -1 && this.cellMonument[k] === 0) continue;
        const falloff = 1 - dist / radiusM;
        const hit = fraction * falloff;
        this.cellDamage[k] = Math.min(1, this.cellDamage[k]! + hit);
        this.cellBuild[k] = Math.max(0, this.cellBuild[k]! * (1 - hit));
        if (this.cellMonument[k] && hit > 0.5) this.cellMonument[k] = 0;
        affected++;
      }
    }
    return affected;
  }

  /**
   * Raise a fortification ring around a settlement. The line is pulled onto the surrounding
   * ridges, which is how 한양도성 actually runs: 북악산, 낙산, 남산, 인왕산.
   */
  buildWall(s: Settlement, radiusM: number, ridgeSeek = 900): number[] {
    const w = this.world;
    const steps = 180;
    const ring: Array<{ i: number; j: number }> = [];
    for (let a = 0; a < steps; a++) {
      const ang = (a / steps) * Math.PI * 2;
      let bestR = radiusM;
      let bestH = -Infinity;
      for (let r = radiusM - ridgeSeek; r <= radiusM + ridgeSeek; r += w.cellM) {
        if (r <= 0) continue;
        const x = s.x + Math.cos(ang) * r;
        const z = s.z + Math.sin(ang) * r;
        const { i, j } = w.cellAt(x, z);
        if (!w.inBounds(i, j)) continue;
        if (this.water[w.index(i, j)] === 1) continue;
        // Prefer high ground, but do not wander too far from the intended radius.
        const h = this.height[w.index(i, j)]! - Math.abs(r - radiusM) * 0.02;
        if (h > bestH) {
          bestH = h;
          bestR = r;
        }
      }
      const x = s.x + Math.cos(ang) * bestR;
      const z = s.z + Math.sin(ang) * bestR;
      const { i, j } = w.cellAt(x, z);
      if (w.inBounds(i, j)) ring.push({ i, j });
    }

    const cells: number[] = [];
    for (let a = 0; a < ring.length; a++) {
      const p = ring[a]!;
      const q = ring[(a + 1) % ring.length]!;
      const n = Math.max(Math.abs(q.i - p.i), Math.abs(q.j - p.j));
      for (let t = 0; t <= n; t++) {
        const i = Math.round(p.i + ((q.i - p.i) * t) / Math.max(1, n));
        const j = Math.round(p.j + ((q.j - p.j) * t) / Math.max(1, n));
        if (!w.inBounds(i, j)) continue;
        const k = w.index(i, j);
        if (this.cellWall[k]) continue;
        this.cellWall[k] = 1;
        this.cellUse[k] = LandUse.Wall;
        cells.push(k);
      }
    }
    s.walls.push(...cells);
    return cells;
  }

  placeMonument(x: number, z: number, radiusM: number): number[] {
    const w = this.world;
    const { i: ci, j: cj } = w.cellAt(x, z);
    const ri = Math.max(1, Math.round(radiusM / w.cellM));
    const cells: number[] = [];
    for (let dj = -ri; dj <= ri; dj++) {
      for (let di = -ri; di <= ri; di++) {
        if (di * di + dj * dj > ri * ri) continue;
        const i = ci + di;
        const j = cj + dj;
        if (!w.inBounds(i, j)) continue;
        const k = w.index(i, j);
        if (this.water[k] === 1) continue;
        this.cellMonument[k] = 1;
        this.cellUse[k] = LandUse.Monument;
        cells.push(k);
      }
    }
    return cells;
  }

  /** Turn river cells into buildable ground: 여의도 윤중제, 잠실 매립. */
  reclaim(x: number, z: number, radiusM: number, year: number): number {
    const w = this.world;
    const { i: ci, j: cj } = w.cellAt(x, z);
    const ri = Math.ceil(radiusM / w.cellM);
    let n = 0;
    for (let dj = -ri; dj <= ri; dj++) {
      for (let di = -ri; di <= ri; di++) {
        const dist = Math.hypot(di, dj) * w.cellM;
        if (dist > radiusM) continue;
        const i = ci + di;
        const j = cj + dj;
        if (!w.inBounds(i, j)) continue;
        const k = w.index(i, j);
        if (this.water[k] !== 1) continue;
        // Keep a navigable channel: only reclaim the shallower margins of the reach.
        if (hash2(i, j, 5) < 0.42) continue;
        this.water[k] = 0;
        this.buildable[k] = 0.85;
        this.height[k] = Math.max(this.height[k]!, 11);
        this.cellUse[k] = LandUse.Reclaimed;
        this.cellOpenYear[k] = year;
        n++;
      }
    }
    return n;
  }

  /** Open land that administrative expansion brings inside the city. */
  openLand(x: number, z: number, radiusM: number, year: number): number {
    const w = this.world;
    const { i: ci, j: cj } = w.cellAt(x, z);
    const ri = Math.ceil(radiusM / w.cellM);
    let n = 0;
    for (let dj = -ri; dj <= ri; dj++) {
      for (let di = -ri; di <= ri; di++) {
        if (Math.hypot(di, dj) * w.cellM > radiusM) continue;
        const i = ci + di;
        const j = cj + dj;
        if (!w.inBounds(i, j)) continue;
        const k = w.index(i, j);
        if (this.water[k] === 1) continue;
        if (this.cellOpenYear[k]! > year) {
          this.cellOpenYear[k] = year;
          n++;
        }
      }
    }
    return n;
  }

  get totalPopulation(): number {
    let t = 0;
    for (const s of this.settlements) t += s.cohorts.total;
    return t;
  }

  get builtCellCount(): number {
    let n = 0;
    for (let k = 0; k < this.cellBuild.length; k++) if (this.cellBuild[k]! > 0.02) n++;
    return n;
  }

  /** Deterministic-but-varied name for an emergent settlement. */
  nextName(): string {
    const stems = ['한', '양', '노', '마', '뚝', '광', '수', '송', '왕', '고', '구', '금', '망', '안'];
    const tails = ['촌', '리', '나루', '골', '말', '뜰', '터'];
    return `${this.rng.pick(stems)}${this.rng.pick(tails)}`;
  }
}
