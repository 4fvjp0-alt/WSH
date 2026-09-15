/**
 * Roads. Between settlements they follow least-cost paths over the terrain, so they thread the
 * valleys and pick the narrow crossings rather than climbing straight over the mountains.
 * Inside a dense settlement a coarse grid is stamped so the built fabric reads as blocks.
 */
import { Era } from '../era/eras.ts';
import { World } from '../world/worldData.ts';
import type { Settlement, SettlementSystem } from './settlement.ts';

/** Cost of entering a cell, in abstract units. */
function stepCost(w: World, water: Uint8Array, k: number, era: Era): number {
  const relief = w.relief[k]!;
  const slopeCost = 1 + relief * relief * 0.02;
  if (water[k] === 1) {
    // Bridges are expensive, and nearly impossible before the modern era.
    return era >= Era.Colonial ? 40 : era >= Era.JoseonEarly ? 260 : 900;
  }
  return slopeCost;
}

/** A* over the 8-neighbourhood using a binary heap. Returns cell indices, or null if unreachable. */
export function findPath(w: World, water: Uint8Array, startK: number, goalK: number, era: Era, maxExpansions = 200000): number[] | null {
  const n = w.nx * w.nz;
  const gScore = new Float32Array(n).fill(Infinity);
  const cameFrom = new Int32Array(n).fill(-1);
  const closed = new Uint8Array(n);

  const heapK: number[] = [];
  const heapF: number[] = [];
  const push = (k: number, f: number): void => {
    heapK.push(k);
    heapF.push(f);
    let c = heapK.length - 1;
    while (c > 0) {
      const p = (c - 1) >> 1;
      if (heapF[p]! <= heapF[c]!) break;
      [heapF[p], heapF[c]] = [heapF[c]!, heapF[p]!];
      [heapK[p], heapK[c]] = [heapK[c]!, heapK[p]!];
      c = p;
    }
  };
  const pop = (): number => {
    const top = heapK[0]!;
    const lastK = heapK.pop()!;
    const lastF = heapF.pop()!;
    if (heapK.length > 0) {
      heapK[0] = lastK;
      heapF[0] = lastF;
      let p = 0;
      for (;;) {
        const l = p * 2 + 1;
        const r = l + 1;
        let m = p;
        if (l < heapF.length && heapF[l]! < heapF[m]!) m = l;
        if (r < heapF.length && heapF[r]! < heapF[m]!) m = r;
        if (m === p) break;
        [heapF[p], heapF[m]] = [heapF[m]!, heapF[p]!];
        [heapK[p], heapK[m]] = [heapK[m]!, heapK[p]!];
        p = m;
      }
    }
    return top;
  };

  const gi = goalK % w.nx;
  const gj = (goalK - gi) / w.nx;
  const heuristic = (k: number): number => {
    const i = k % w.nx;
    const j = (k - i) / w.nx;
    return Math.hypot(i - gi, j - gj);
  };

  gScore[startK] = 0;
  push(startK, heuristic(startK));
  let expansions = 0;

  while (heapK.length > 0) {
    const current = pop();
    if (current === goalK) break;
    if (closed[current]) continue;
    closed[current] = 1;
    if (++expansions > maxExpansions) return null;

    const ci = current % w.nx;
    const cj = (current - ci) / w.nx;
    for (let dj = -1; dj <= 1; dj++) {
      for (let di = -1; di <= 1; di++) {
        if (!di && !dj) continue;
        const ni = ci + di;
        const nj = cj + dj;
        if (!w.inBounds(ni, nj)) continue;
        const nk = w.index(ni, nj);
        if (closed[nk]) continue;
        const diag = di !== 0 && dj !== 0 ? 1.41421356 : 1;
        const tentative = gScore[current]! + stepCost(w, water, nk, era) * diag;
        if (tentative < gScore[nk]!) {
          gScore[nk] = tentative;
          cameFrom[nk] = current;
          push(nk, tentative + heuristic(nk));
        }
      }
    }
  }

  if (cameFrom[goalK] === -1 && goalK !== startK) return null;
  const path: number[] = [];
  let k = goalK;
  while (k !== -1) {
    path.push(k);
    if (k === startK) break;
    k = cameFrom[k]!;
  }
  return path.reverse();
}

export class RoadNetwork {
  private readonly linked = new Set<string>();

  /** Connect every settlement to its nearest already-connected neighbour (a growing spanning tree). */
  connectSettlements(sys: SettlementSystem, era: Era): number {
    const { world } = sys;
    const list = sys.settlements.filter((s) => s.cohorts.total > 50);
    if (list.length < 2) return 0;
    let built = 0;

    for (let a = 0; a < list.length; a++) {
      for (let b = a + 1; b < list.length; b++) {
        const sa = list[a]!;
        const sb = list[b]!;
        const key = `${sa.id}-${sb.id}`;
        if (this.linked.has(key)) continue;
        const dist = Math.hypot(sa.x - sb.x, sa.z - sb.z);
        // Only link neighbours; the network fills in as more towns appear.
        const reach = era >= Era.Industrial ? 26000 : era >= Era.Colonial ? 16000 : 9000;
        if (dist > reach) continue;
        const path = findPath(world, sys.water, world.index(sa.ci, sa.cj), world.index(sb.ci, sb.cj), era);
        this.linked.add(key);
        if (!path) continue;
        const cls = era >= Era.Industrial ? 3 : era >= Era.JoseonEarly ? 2 : 1;
        for (const k of path) {
          if (sys.cellRoad[k]! < cls) sys.cellRoad[k] = cls;
        }
        built++;
      }
    }
    return built;
  }

  /** Stamp a street grid over the built-up part of a settlement. */
  stampGrid(sys: SettlementSystem, s: Settlement, era: Era): void {
    if (era < Era.JoseonEarly) return;
    const w = sys.world;
    const spacing = era >= Era.Industrial ? 4 : era >= Era.Colonial ? 5 : 7; // cells between streets
    for (const k of s.cells) {
      const i = k % w.nx;
      const j = (k - i) / w.nx;
      if (sys.cellBuild[k]! < 0.12) continue;
      if (i % spacing === 0 || j % spacing === 0) {
        if (sys.cellRoad[k]! < 2) sys.cellRoad[k] = 2;
      }
    }
  }
}
