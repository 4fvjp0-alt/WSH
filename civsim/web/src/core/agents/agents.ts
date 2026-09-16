/**
 * The people you can actually watch.
 *
 * Only the ones near the camera exist as individuals. They are summoned from the settlement's
 * statistics when you come close and dissolved back into them when you leave, so the cost is
 * bounded by what is on screen rather than by the population of the city.
 */
import { Era, ERA_PROFILES } from '../era/eras.ts';
import { LandUse } from '../world/worldData.ts';
import type { SettlementSystem } from '../settle/settlement.ts';
import { Rng, hash2 } from '../rng.ts';

export enum AgentRole {
  Farmer = 0,
  Townsfolk = 1,
  Official = 2,
  Labourer = 3,
  Child = 4,
}

export const ROLE_NAMES: Record<AgentRole, string> = {
  [AgentRole.Farmer]: '농민',
  [AgentRole.Townsfolk]: '장사치',
  [AgentRole.Official]: '관원',
  [AgentRole.Labourer]: '역부',
  [AgentRole.Child]: '아이',
};

export enum AgentActivity {
  Asleep = 0,
  Commuting = 1,
  Working = 2,
  Returning = 3,
  Idle = 4,
}

export const ACTIVITY_NAMES: Record<AgentActivity, string> = {
  [AgentActivity.Asleep]: '잠',
  [AgentActivity.Commuting]: '출근길',
  [AgentActivity.Working]: '일하는 중',
  [AgentActivity.Returning]: '귀가길',
  [AgentActivity.Idle]: '쉬는 중',
};

export const MAX_AGENTS = 6000;

/** Share of people still out after everyone else has gone in, as a percentage. */
const NIGHT_AWAKE_PERCENT = 7;

export class AgentSystem {
  /** Live agent count; the arrays below are valid for [0, count). */
  count = 0;

  readonly x = new Float32Array(MAX_AGENTS);
  readonly z = new Float32Array(MAX_AGENTS);
  readonly homeX = new Float32Array(MAX_AGENTS);
  readonly homeZ = new Float32Array(MAX_AGENTS);
  readonly workX = new Float32Array(MAX_AGENTS);
  readonly workZ = new Float32Array(MAX_AGENTS);
  readonly targetX = new Float32Array(MAX_AGENTS);
  readonly targetZ = new Float32Array(MAX_AGENTS);
  readonly speed = new Float32Array(MAX_AGENTS);
  readonly heading = new Float32Array(MAX_AGENTS);
  readonly role = new Uint8Array(MAX_AGENTS);
  readonly activity = new Uint8Array(MAX_AGENTS);
  /** Personal offsets so a crowd does not move in lockstep. */
  readonly wakeOffset = new Float32Array(MAX_AGENTS);
  readonly seed = new Uint32Array(MAX_AGENTS);

  private readonly rng: Rng;
  private lastCentreX = Infinity;
  private lastCentreZ = Infinity;
  private lastEra: Era | null = null;
  private lastRadius = 0;
  private lastBudget = 0;

  constructor(rng: Rng) {
    this.rng = rng;
  }

  /**
   * Re-populate the visible crowd around a point.
   *
   * `budget` is how many individuals the renderer can afford; the rest of the population stays
   * as statistics. Agents are placed on inhabited cells in proportion to how many people live there.
   */
  refresh(land: SettlementSystem, centreX: number, centreZ: number, radiusM: number, era: Era, budget: number): void {
    const moved = Math.hypot(centreX - this.lastCentreX, centreZ - this.lastCentreZ);
    const zoomed = Math.abs(radiusM - this.lastRadius) > this.lastRadius * 0.25;
    const rebudgeted = Math.abs(budget - this.lastBudget) > this.lastBudget * 0.25;
    if (moved < radiusM * 0.25 && !zoomed && !rebudgeted && this.lastEra === era && this.count > 0) return;
    this.lastCentreX = centreX;
    this.lastCentreZ = centreZ;
    this.lastEra = era;
    this.lastRadius = radiusM;
    this.lastBudget = budget;

    const w = land.world;
    const { i: ci, j: cj } = w.cellAt(centreX, centreZ);
    const ri = Math.ceil(radiusM / w.cellM);

    // Collect inhabited cells in range with their populations.
    const cells: number[] = [];
    const weights: number[] = [];
    let totalPeople = 0;
    for (let dj = -ri; dj <= ri; dj++) {
      const j = cj + dj;
      if (j < 0 || j >= w.nz) continue;
      for (let di = -ri; di <= ri; di++) {
        const i = ci + di;
        if (i < 0 || i >= w.nx) continue;
        if (di * di + dj * dj > ri * ri) continue;
        const k = w.index(i, j);
        const p = land.cellPop[k]!;
        if (p < 0.5) continue;
        cells.push(k);
        weights.push(p);
        totalPeople += p;
      }
    }

    this.count = 0;
    if (cells.length === 0 || totalPeople <= 0) return;

    const target = Math.min(budget, MAX_AGENTS);
    // One agent stands for this many real people.
    for (let n = 0; n < cells.length && this.count < target; n++) {
      const k = cells[n]!;
      const share = weights[n]! / totalPeople;
      let here = Math.round(share * target);
      if (here < 1 && this.rng.next() < share * target) here = 1;
      for (let q = 0; q < here && this.count < target; q++) {
        this.spawn(land, k, era);
      }
    }
  }

  private spawn(land: SettlementSystem, cellK: number, era: Era): void {
    const w = land.world;
    const id = this.count++;
    const i = cellK % w.nx;
    const j = (cellK - i) / w.nx;
    const centre = w.cellCentre(i, j);
    const jitterX = (this.rng.next() - 0.5) * w.cellM * 0.85;
    const jitterZ = (this.rng.next() - 0.5) * w.cellM * 0.85;

    this.homeX[id] = centre.x + jitterX;
    this.homeZ[id] = centre.z + jitterZ;
    this.x[id] = this.homeX[id]!;
    this.z[id] = this.homeZ[id]!;
    this.seed[id] = (hash2(i, j, id) * 4294967295) >>> 0;
    this.wakeOffset[id] = (this.rng.next() - 0.5) * 1.4;

    // What this person does depends on the era and on what is around them.
    const use = land.cellUse[cellK]!;
    let role: AgentRole;
    const r = this.rng.next();
    if (r < 0.14) role = AgentRole.Child;
    else if (land.cellMonument[cellK] === 1 && r < 0.4) role = AgentRole.Official;
    else if (era <= Era.JoseonLate && (use === LandUse.Village || use === LandUse.Farm) && r < 0.75) role = AgentRole.Farmer;
    else if (era >= Era.Industrial && r < 0.55) role = AgentRole.Townsfolk;
    else if (r < 0.62) role = AgentRole.Labourer;
    else role = AgentRole.Townsfolk;
    this.role[id] = role;

    const p = ERA_PROFILES[era];
    // A modern commute is twenty kilometres, which for someone you are watching means walking off
    // the screen and never coming back. The people on screen work close to where they live; the
    // long commute is a fact about the city, not about what a crowd should look like.
    const reach = Math.min(role === AgentRole.Farmer ? 320 : 420, p.commuteRange);
    const work = this.findWorkplace(land, i, j, reach, role);
    this.workX[id] = work.x;
    this.workZ[id] = work.z;

    const base = role === AgentRole.Child ? 1.0 : role === AgentRole.Official ? 1.15 : 1.35;
    this.speed[id] = base * (0.85 + this.rng.next() * 0.35);
    this.activity[id] = AgentActivity.Asleep;
    this.targetX[id] = this.homeX[id]!;
    this.targetZ[id] = this.homeZ[id]!;
    this.heading[id] = this.rng.next() * Math.PI * 2;
  }

  private findWorkplace(
    land: SettlementSystem, i: number, j: number, reachM: number, role: AgentRole,
  ): { x: number; z: number } {
    const w = land.world;
    const ri = Math.max(1, Math.round(reachM / w.cellM));
    let bestK = w.index(i, j);
    let bestScore = -1;
    for (let attempt = 0; attempt < 14; attempt++) {
      const di = Math.round((this.rng.next() * 2 - 1) * ri);
      const dj = Math.round((this.rng.next() * 2 - 1) * ri);
      const ni = i + di;
      const nj = j + dj;
      if (!w.inBounds(ni, nj)) continue;
      const k = w.index(ni, nj);
      if (land.water[k] === 1) continue;
      const use = land.cellUse[k]!;
      let score = 0;
      switch (role) {
        case AgentRole.Farmer: score = use === LandUse.Farm ? 3 : use === LandUse.Wild ? 0.6 : 0.2; break;
        case AgentRole.Official: score = land.cellMonument[k] === 1 ? 4 : use === LandUse.Dense ? 1 : 0.3; break;
        case AgentRole.Labourer: score = land.cellWall[k] === 1 ? 3 : use === LandUse.Industrial ? 2.5 : 0.6; break;
        case AgentRole.Child: score = 0.5 + land.cellPop[k]! / 400; break;
        default: score = land.cellPop[k]! / 200 + (use === LandUse.Road ? 0.8 : 0); break;
      }
      score *= 0.6 + this.rng.next() * 0.8;
      if (score > bestScore) {
        bestScore = score;
        bestK = k;
      }
    }
    const bi = bestK % w.nx;
    const bj = (bestK - bi) / w.nx;
    const c = w.cellCentre(bi, bj);
    return { x: c.x + (this.rng.next() - 0.5) * w.cellM * 0.7, z: c.z + (this.rng.next() - 0.5) * w.cellM * 0.7 };
  }

  /**
   * Move everyone. `hourOfDay` is local solar-ish time, `dt` is elapsed simulated seconds capped
   * by the caller so people never teleport.
   */
  update(dtSeconds: number, hourOfDay: number, sunriseHour: number, sunsetHour: number): void {
    const dt = Math.min(dtSeconds, 4);

    for (let id = 0; id < this.count; id++) {
      const wake = sunriseHour - 0.6 + this.wakeOffset[id]!;
      const sleep = sunsetHour + 1.2 + this.wakeOffset[id]!;
      const role = this.role[id]! as AgentRole;

      let activity: AgentActivity;
      if (hourOfDay < wake || hourOfDay > sleep) {
        // A city is never entirely indoors. A few people are out at any hour: the watch, porters,
        // travellers arriving late. Without them a night view looks like an empty stage set.
        activity = this.seed[id]! % 100 < NIGHT_AWAKE_PERCENT ? AgentActivity.Idle : AgentActivity.Asleep;
      } else if (hourOfDay < wake + 1.1) {
        activity = AgentActivity.Commuting;
      } else if (hourOfDay > sleep - 1.6) {
        activity = AgentActivity.Returning;
      } else {
        activity = role === AgentRole.Child && hourOfDay > 14 ? AgentActivity.Idle : AgentActivity.Working;
      }
      this.activity[id] = activity;

      let tx: number;
      let tz: number;
      if (activity === AgentActivity.Asleep || activity === AgentActivity.Returning) {
        tx = this.homeX[id]!;
        tz = this.homeZ[id]!;
      } else if (activity === AgentActivity.Idle) {
        // Wander a little around home.
        const t = hourOfDay * 0.7 + (this.seed[id]! % 1000) * 0.01;
        tx = this.homeX[id]! + Math.cos(t) * 35;
        tz = this.homeZ[id]! + Math.sin(t * 1.3) * 35;
      } else {
        tx = this.workX[id]!;
        tz = this.workZ[id]!;
      }
      this.targetX[id] = tx;
      this.targetZ[id] = tz;

      const dx = tx - this.x[id]!;
      const dz = tz - this.z[id]!;
      const dist = Math.hypot(dx, dz);
      if (dist < 1.2) {
        if (activity !== AgentActivity.Asleep) {
          // Shuffle on the spot so a working crowd still reads as alive.
          const t = hourOfDay * 3 + (this.seed[id]! % 997) * 0.1;
          this.x[id]! += Math.cos(t) * 0.12 * dt;
          this.z[id]! += Math.sin(t * 1.7) * 0.12 * dt;
        }
        continue;
      }
      const step = Math.min(dist, this.speed[id]! * dt);
      this.x[id]! += (dx / dist) * step;
      this.z[id]! += (dz / dist) * step;
      this.heading[id] = Math.atan2(dx, dz);
    }
  }

  /** True when this person should be drawn: asleep people are indoors. */
  isVisible(id: number): boolean {
    return this.activity[id] !== AgentActivity.Asleep;
  }
}
