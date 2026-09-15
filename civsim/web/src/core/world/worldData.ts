/** Loading and indexing the baked world: terrain, water and the derived per-cell properties. */
import { hash2 } from '../rng.ts';

export interface WorldMeta {
  origin: { lat: number; lon: number };
  metresPerDegree: number;
  sim: { cellM: number; nx: number; nz: number; x0: number; z0: number };
  dem: {
    cellM: number; nx: number; nz: number; x0: number; z0: number;
    heightMinM: number; heightScaleM: number;
  };
  bbox: { minLon: number; maxLon: number; minLat: number; maxLat: number };
  source: string;
  verification: Record<string, unknown>;
}

export enum LandUse {
  Wild = 0,
  Farm = 1,
  Village = 2,
  Town = 3,
  Urban = 4,
  Dense = 5,
  Industrial = 6,
  Monument = 7,
  Wall = 8,
  Road = 9,
  Water = 10,
  Reclaimed = 11,
}

export const LAND_USE_NAMES: Record<LandUse, string> = {
  [LandUse.Wild]: '자연', [LandUse.Farm]: '농경지', [LandUse.Village]: '촌락',
  [LandUse.Town]: '읍', [LandUse.Urban]: '시가지', [LandUse.Dense]: '고밀 시가지',
  [LandUse.Industrial]: '공업', [LandUse.Monument]: '궁궐·사적', [LandUse.Wall]: '성곽',
  [LandUse.Road]: '도로', [LandUse.Water]: '수역', [LandUse.Reclaimed]: '매립지',
};

export class World {
  readonly meta: WorldMeta;
  readonly nx: number;
  readonly nz: number;
  readonly cellM: number;
  readonly x0: number;
  readonly z0: number;

  /** Terrain height in metres, per simulation cell. */
  readonly height: Float32Array;
  /** Render-resolution heightmap in metres (DEM grid). */
  readonly demHeight: Float32Array;
  /** 1 where present-day open water sits. */
  readonly water: Uint8Array;
  /** Maximum height difference across the cell's neighbours, metres. */
  readonly relief: Float32Array;
  /** 0..1 suitability for farming. */
  readonly fertility: Float32Array;
  /** 0..1 suitability for building. */
  readonly buildable: Float32Array;
  /** Metres to the nearest water cell (capped). */
  readonly distanceToWater: Float32Array;
  /** Mineral and material richness, 0..1. */
  readonly stone: Float32Array;
  readonly clay: Float32Array;
  readonly woodland: Float32Array;

  constructor(meta: WorldMeta, demHeight: Float32Array, simHeight: Float32Array, water: Uint8Array) {
    this.meta = meta;
    this.nx = meta.sim.nx;
    this.nz = meta.sim.nz;
    this.cellM = meta.sim.cellM;
    this.x0 = meta.sim.x0;
    this.z0 = meta.sim.z0;
    this.height = simHeight;
    this.demHeight = demHeight;
    this.water = water;

    const n = this.nx * this.nz;
    this.relief = new Float32Array(n);
    this.fertility = new Float32Array(n);
    this.buildable = new Float32Array(n);
    this.distanceToWater = new Float32Array(n);
    this.stone = new Float32Array(n);
    this.clay = new Float32Array(n);
    this.woodland = new Float32Array(n);
    this.derive();
  }

  index(i: number, j: number): number {
    return j * this.nx + i;
  }

  inBounds(i: number, j: number): boolean {
    return i >= 0 && i < this.nx && j >= 0 && j < this.nz;
  }

  /** Cell centre in local metres. */
  cellCentre(i: number, j: number): { x: number; z: number } {
    return { x: this.x0 + (i + 0.5) * this.cellM, z: this.z0 + (j + 0.5) * this.cellM };
  }

  cellAt(x: number, z: number): { i: number; j: number } {
    return {
      i: Math.floor((x - this.x0) / this.cellM),
      j: Math.floor((z - this.z0) / this.cellM),
    };
  }

  /** Bilinear terrain height at arbitrary local coordinates, from the DEM grid. */
  heightAt(x: number, z: number): number {
    const d = this.meta.dem;
    const fx = Math.max(0, Math.min(d.nx - 1.001, (x - d.x0) / d.cellM));
    const fz = Math.max(0, Math.min(d.nz - 1.001, (z - d.z0) / d.cellM));
    const i0 = Math.floor(fx);
    const j0 = Math.floor(fz);
    const tx = fx - i0;
    const tz = fz - j0;
    const h = this.demHeight;
    const a = h[j0 * d.nx + i0]!;
    const b = h[j0 * d.nx + i0 + 1]!;
    const c = h[(j0 + 1) * d.nx + i0]!;
    const e = h[(j0 + 1) * d.nx + i0 + 1]!;
    return (a * (1 - tx) + b * tx) * (1 - tz) + (c * (1 - tx) + e * tx) * tz;
  }

  isWaterAt(x: number, z: number): boolean {
    const { i, j } = this.cellAt(x, z);
    return this.inBounds(i, j) && this.water[this.index(i, j)] === 1;
  }

  private derive(): void {
    const { nx, nz, height, water } = this;

    // Relief: the local height spread, which stands in for slope.
    for (let j = 0; j < nz; j++) {
      for (let i = 0; i < nx; i++) {
        let lo = Infinity;
        let hi = -Infinity;
        for (let dj = -1; dj <= 1; dj++) {
          for (let di = -1; di <= 1; di++) {
            const ni = i + di;
            const nj = j + dj;
            if (!this.inBounds(ni, nj)) continue;
            const h = height[this.index(ni, nj)]!;
            if (h < lo) lo = h;
            if (h > hi) hi = h;
          }
        }
        this.relief[this.index(i, j)] = hi - lo;
      }
    }

    // Distance to water by multi-source BFS over the 8-neighbourhood (chamfer 1 / 1.41).
    const INF = 1e9;
    const dist = this.distanceToWater;
    dist.fill(INF);
    const queue: number[] = [];
    for (let k = 0; k < water.length; k++) {
      if (water[k] === 1) {
        dist[k] = 0;
        queue.push(k);
      }
    }
    // Two-pass chamfer is enough and avoids a priority queue.
    for (let pass = 0; pass < 2; pass++) {
      const forward = pass === 0;
      for (let jj = 0; jj < nz; jj++) {
        const j = forward ? jj : nz - 1 - jj;
        for (let ii = 0; ii < nx; ii++) {
          const i = forward ? ii : nx - 1 - ii;
          const k = this.index(i, j);
          let best = dist[k]!;
          for (let dj = -1; dj <= 1; dj++) {
            for (let di = -1; di <= 1; di++) {
              if (di === 0 && dj === 0) continue;
              if (forward && (dj > 0 || (dj === 0 && di > 0))) continue;
              if (!forward && (dj < 0 || (dj === 0 && di < 0))) continue;
              const ni = i + di;
              const nj = j + dj;
              if (!this.inBounds(ni, nj)) continue;
              const step = di !== 0 && dj !== 0 ? 1.41421356 : 1;
              const cand = dist[this.index(ni, nj)]! + step * this.cellM;
              if (cand < best) best = cand;
            }
          }
          dist[k] = best;
        }
      }
    }
    for (let k = 0; k < dist.length; k++) if (dist[k]! > 20000) dist[k] = 20000;

    // Per-cell qualities.
    for (let j = 0; j < nz; j++) {
      for (let i = 0; i < nx; i++) {
        const k = this.index(i, j);
        const h = height[k]!;
        const rel = this.relief[k]!;
        const dw = dist[k]!;
        const isWater = water[k] === 1;

        // Flat, low, near water, not in the river: prime paddy land.
        const flatness = Math.max(0, 1 - rel / 25);
        const lowland = Math.max(0, 1 - Math.max(0, h - 10) / 90);
        const nearWater = Math.max(0, 1 - dw / 3000);
        const noise = hash2(i, j, 11) * 0.25 + 0.875;
        this.fertility[k] = isWater ? 0 : Math.min(1, flatness * (0.35 + 0.4 * lowland + 0.35 * nearWater) * noise);

        // Buildable: flat enough, above the flood line, not water.
        const dry = Math.max(0, Math.min(1, (h - 6) / 8));
        this.buildable[k] = isWater ? 0 : Math.min(1, Math.max(0, 1 - rel / 40) * dry);

        // Resources. Stone follows relief, clay follows the floodplain, woodland the hillsides.
        this.stone[k] = isWater ? 0 : Math.min(1, (rel / 45) * (0.7 + hash2(i, j, 23) * 0.6));
        this.clay[k] = isWater ? 0 : Math.min(1, nearWater * flatness * (0.6 + hash2(i, j, 31) * 0.8));
        this.woodland[k] = isWater ? 0 : Math.min(1, Math.max(0, Math.min(1, (h - 20) / 120)) * (0.6 + hash2(i, j, 47) * 0.8));
      }
    }
  }
}

export type BinaryLoader = (name: string) => Promise<ArrayBuffer>;

export async function loadWorld(loadBinary: BinaryLoader, loadJson: (name: string) => Promise<WorldMeta>): Promise<World> {
  const meta = await loadJson('world.json');
  const [demBuf, simBuf, waterBuf] = await Promise.all([
    loadBinary('dem.bin'),
    loadBinary('simheight.bin'),
    loadBinary('water.bin'),
  ]);
  const demRaw = new Uint16Array(demBuf);
  const dem = new Float32Array(demRaw.length);
  const { heightMinM, heightScaleM } = meta.dem;
  for (let i = 0; i < demRaw.length; i++) dem[i] = heightMinM + (demRaw[i]! / 65535) * heightScaleM;
  return new World(meta, dem, new Float32Array(simBuf), new Uint8Array(waterBuf));
}
