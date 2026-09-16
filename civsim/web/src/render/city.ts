/**
 * The built fabric: one instance per built cell, sized and coloured by the era's building kit.
 * Rebuilt when the simulation has moved, not every frame.
 */
import * as THREE from 'three';
import { ERA_PROFILES, Era } from '../core/era/eras.ts';
import { LandUse, World } from '../core/world/worldData.ts';
import type { SettlementSystem } from '../core/settle/settlement.ts';
import { hash2 } from '../core/rng.ts';

const MAX_BODIES = 120000;
const MAX_ROOFS = 120000;
const MAX_WALLS = 4000;
const MAX_MONUMENTS = 3000;

export class CityView {
  readonly group = new THREE.Group();
  private readonly bodies: THREE.InstancedMesh;
  private readonly roofs: THREE.InstancedMesh;
  private readonly walls: THREE.InstancedMesh;
  private readonly monuments: THREE.InstancedMesh;
  private readonly monumentRoofs: THREE.InstancedMesh;
  private readonly dummy = new THREE.Object3D();
  private readonly colour = new THREE.Color();

  constructor(private readonly world: World) {
    const boxMat = new THREE.MeshLambertMaterial({ vertexColors: false });
    this.bodies = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), boxMat.clone(), MAX_BODIES);
    this.bodies.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX_BODIES * 3), 3);
    this.bodies.count = 0;
    this.bodies.frustumCulled = false;
    this.bodies.name = 'buildings';

    // A four-sided cone is a hipped roof, which is what reads as a tiled Korean roof at this scale.
    this.roofs = new THREE.InstancedMesh(new THREE.ConeGeometry(0.72, 1, 4), boxMat.clone(), MAX_ROOFS);
    this.roofs.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX_ROOFS * 3), 3);
    this.roofs.count = 0;
    this.roofs.frustumCulled = false;
    this.roofs.name = 'roofs';

    this.walls = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), boxMat.clone(), MAX_WALLS);
    this.walls.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX_WALLS * 3), 3);
    this.walls.count = 0;
    this.walls.frustumCulled = false;
    this.walls.name = 'walls';

    this.monuments = new THREE.InstancedMesh(new THREE.BoxGeometry(1, 1, 1), boxMat.clone(), MAX_MONUMENTS);
    this.monuments.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX_MONUMENTS * 3), 3);
    this.monuments.count = 0;
    this.monuments.frustumCulled = false;

    this.monumentRoofs = new THREE.InstancedMesh(new THREE.ConeGeometry(0.78, 1, 4), boxMat.clone(), MAX_MONUMENTS);
    this.monumentRoofs.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX_MONUMENTS * 3), 3);
    this.monumentRoofs.count = 0;
    this.monumentRoofs.frustumCulled = false;

    this.group.add(this.bodies, this.roofs, this.walls, this.monuments, this.monumentRoofs);
  }

  /**
   * Rebuild the instances. `focusX/Z` and `radius` limit the detailed band so a city of 340 km²
   * does not have to be drawn block by block when the camera is in orbit.
   */
  rebuild(land: SettlementSystem, era: Era, focusX: number, focusZ: number, radiusM: number, cameraDistance = 1000): void {
    const w = this.world;
    const p = ERA_PROFILES[era];
    const traditional = era <= Era.Colonial;
    const [minH, maxH] = p.buildingHeight;

    let nb = 0;
    let nr = 0;
    let nw = 0;
    let nm = 0;

    const { i: ci, j: cj } = w.cellAt(focusX, focusZ);
    const ri = Math.ceil(radiusM / w.cellM);
    const i0 = Math.max(0, ci - ri);
    const i1 = Math.min(w.nx - 1, ci + ri);
    const j0 = Math.max(0, cj - ri);
    const j1 = Math.min(w.nz - 1, cj + ri);

    /** How many buildings a cell would get if there were budget for everything. */
    const fullDetail = (k: number, x: number, z: number): number => {
      const ratio = Math.hypot(x - focusX, z - focusZ) / Math.max(500, cameraDistance);
      const detail = ratio < 2.5 ? 6 : ratio < 5 ? 3 : 1;
      const density = Math.min(1, land.cellBuild[k]!);
      return Math.max(1, Math.min(detail, Math.round(density * detail + 0.35)));
    };

    // Modern Seoul asks for about 180,000 buildings from the default view, well past what one
    // instanced mesh holds. Rather than running out part way through and leaving a straight edge
    // across the city, measure the demand first and thin it out evenly: every built cell keeps at
    // least one building, and what is left of the budget is shared in proportion to demand, so the
    // blocks nearest the camera stay the most detailed.
    let demandCells = 0;
    let demandTotal = 0;
    for (let j = j0; j <= j1; j++) {
      for (let i = i0; i <= i1; i++) {
        const k = w.index(i, j);
        if (land.cellWall[k] === 1 || land.cellMonument[k] === 1) continue;
        if (land.cellBuild[k]! < 0.05) continue;
        const c = w.cellCentre(i, j);
        demandCells++;
        demandTotal += fullDetail(k, c.x, c.z);
      }
    }
    const spare = MAX_BODIES - demandCells;
    const detailScale = demandTotal > MAX_BODIES && demandTotal > demandCells
      ? Math.max(0, spare / (demandTotal - demandCells))
      : 1;

    for (let j = j0; j <= j1; j++) {
      for (let i = i0; i <= i1; i++) {
        const k = w.index(i, j);
        const build = land.cellBuild[k]!;
        const isWall = land.cellWall[k] === 1;
        const isMonument = land.cellMonument[k] === 1;
        if (!isWall && !isMonument && build < 0.05) continue;

        const { x, z } = w.cellCentre(i, j);
        const ground = w.heightAt(x, z);
        const jitter = hash2(i, j, 13);
        const jitter2 = hash2(i, j, 29);

        if (isWall && nw < MAX_WALLS) {
          // A rampart segment following the ridge line.
          const h = era >= Era.JoseonEarly ? 7.5 : 4.5;
          this.dummy.position.set(x, ground + h / 2, z);
          this.dummy.rotation.set(0, 0, 0);
          this.dummy.scale.set(w.cellM * 1.05, h, w.cellM * 0.34);
          this.dummy.rotation.y = this.wallAngle(land, i, j);
          this.dummy.updateMatrix();
          this.walls.setMatrixAt(nw, this.dummy.matrix);
          this.colour.setHex(era >= Era.JoseonEarly ? 0x9a9287 : 0x8c7f68).multiplyScalar(0.9 + jitter * 0.2);
          this.walls.setColorAt(nw, this.colour);
          nw++;
          continue;
        }

        if (isMonument && nm < MAX_MONUMENTS) {
          // A palace precinct is halls set in open ground, so only some cells carry a building.
          if (era < Era.Industrial && jitter > 0.55) continue;
          const h = era >= Era.Industrial ? 26 + jitter * 90 : 7 + jitter * 3.5;
          const width = era >= Era.Industrial ? w.cellM * 0.4 : 26 + jitter2 * 16;
          const depth = era >= Era.Industrial ? width * 0.8 : width * (0.45 + jitter2 * 0.3);
          const angle = era >= Era.Industrial ? 0 : (jitter2 - 0.5) * 0.25;
          this.dummy.position.set(x + (jitter - 0.5) * 30, ground + h / 2, z + (jitter2 - 0.5) * 30);
          this.dummy.rotation.set(0, angle, 0);
          this.dummy.scale.set(width, h, depth);
          this.dummy.updateMatrix();
          this.monuments.setMatrixAt(nm, this.dummy.matrix);
          this.colour.setHex(era >= Era.Industrial ? 0xb9bcc2 : 0xb5794a).multiplyScalar(0.9 + jitter2 * 0.2);
          this.monuments.setColorAt(nm, this.colour);

          const rh = era >= Era.Industrial ? 4 : 5.5;
          this.dummy.position.set(this.dummy.position.x, ground + h + rh / 2, this.dummy.position.z);
          this.dummy.rotation.y = angle + Math.PI / 4;
          this.dummy.scale.set(width * 0.98, rh, depth * 0.98);
          this.dummy.updateMatrix();
          this.monumentRoofs.setMatrixAt(nm, this.dummy.matrix);
          this.colour.setHex(era >= Era.Industrial ? 0x8f949c : 0x4e5a63).multiplyScalar(0.9 + jitter * 0.2);
          this.monumentRoofs.setColorAt(nm, this.colour);
          nm++;
          continue;
        }

        if (nb >= MAX_BODIES) continue;
        const damage = land.cellDamage[k]!;
        const density = Math.min(1, build);

        // A 100 m cell holds dozens of houses. Draw several where the camera can see them, one
        // further out, and thin everything by whatever the budget allows.
        const perCell = Math.max(1, 1 + Math.round((fullDetail(k, x, z) - 1) * detailScale));

        for (let b = 0; b < perCell && nb < MAX_BODIES; b++) {
          const r1 = hash2(i * 7 + b, j * 13 + b, 13);
          const r2 = hash2(i * 11 + b, j * 5 + b, 29);
          const r3 = hash2(i * 3 + b, j * 17 + b, 131);

          const tall = Math.pow(r1, era >= Era.Industrial ? 3.2 : 6);
          const h = Math.max(2, (minH + (maxH - minH) * (density * 0.55 + tall * 0.75)) * (1 - damage * 0.7));
          // Real footprints: a hanok is about 8-14 m across, a modern block 15-45 m.
          const width = era >= Era.Industrial ? 14 + r2 * 30 : 7 + r2 * 8;
          const depth = width * (0.6 + r3 * 0.9);

          // Lay the buildings out on a loose 3 x 2 grid inside the cell with a lot of slop, so a
          // block reads as houses along a lane rather than as a regular pattern.
          const cols = 3;
          const gx = (b % cols) - (cols - 1) / 2;
          const gz = Math.floor(b / cols) - 0.5;
          const spread = w.cellM * 0.3;
          const ox = perCell === 1 ? (r1 - 0.5) * spread * 1.6 : gx * spread + (r1 - 0.5) * spread * 0.55;
          const oz = perCell === 1 ? (r2 - 0.5) * spread * 1.6 : gz * spread + (r2 - 0.5) * spread * 0.55;
          const bx = x + ox;
          const bz = z + oz;
          const bg = w.heightAt(bx, bz);

          this.dummy.position.set(bx, bg + h / 2, bz);
          this.dummy.rotation.set(0, (r3 - 0.5) * (era >= Era.Industrial ? 0.6 : 1.8), 0);
          this.dummy.scale.set(width, h, depth);
          this.dummy.updateMatrix();
          this.bodies.setMatrixAt(nb, this.dummy.matrix);

          this.colour.setHex(p.wallColor);
          const spreadHsl = era >= Era.Industrial ? 1.7 : 1;
          this.colour.offsetHSL((r3 - 0.5) * 0.09 * spreadHsl, (r3 - 0.35) * 0.16 * spreadHsl, (r2 - 0.55) * 0.2 * spreadHsl);
          if (damage > 0.1) this.colour.lerp(new THREE.Color(0x4f463c), Math.min(0.8, damage));
          if (land.cellUse[k] === LandUse.Industrial) this.colour.lerp(new THREE.Color(0x6f6a62), 0.5);
          this.colour.multiplyScalar(0.78 + r2 * 0.3);
          this.bodies.setColorAt(nb, this.colour);
          nb++;

          if (traditional && nr < MAX_ROOFS) {
            // The cone is a hipped roof; its radius is 0.72 of its scale, so this sits it just
            // proud of the walls with an eave rather than swallowing the house.
            const eave = 1.22 / 1.44;
            const rh = Math.min(era >= Era.Colonial ? 4.5 : 2.6, h * 0.62);
            this.dummy.position.set(bx, bg + h + rh / 2, bz);
            this.dummy.rotation.y += Math.PI / 4;
            this.dummy.scale.set(width * eave, rh, depth * eave);
            this.dummy.updateMatrix();
            this.roofs.setMatrixAt(nr, this.dummy.matrix);

            // Most roofs are thatch; tile belongs to the households that could afford it.
            const tileChance = era >= Era.JoseonLate ? 0.42 : era >= Era.JoseonEarly ? 0.3 : 0.12;
            const tiled = r1 < tileChance || land.cellPop[k]! > 220;
            this.colour.setHex(tiled ? 0x565b60 : p.roofColor).multiplyScalar(0.85 + r3 * 0.3);
            if (damage > 0.1) this.colour.lerp(new THREE.Color(0x3a332c), Math.min(0.85, damage));
            this.roofs.setColorAt(nr, this.colour);
            nr++;
          }
        }
      }
    }

    this.bodies.count = nb;
    this.roofs.count = traditional ? nr : 0;
    this.walls.count = nw;
    this.monuments.count = nm;
    this.monumentRoofs.count = nm;
    this.bodies.instanceMatrix.needsUpdate = true;
    this.roofs.instanceMatrix.needsUpdate = true;
    this.walls.instanceMatrix.needsUpdate = true;
    this.monuments.instanceMatrix.needsUpdate = true;
    this.monumentRoofs.instanceMatrix.needsUpdate = true;
    if (this.bodies.instanceColor) this.bodies.instanceColor.needsUpdate = true;
    if (this.roofs.instanceColor) this.roofs.instanceColor.needsUpdate = true;
    if (this.walls.instanceColor) this.walls.instanceColor.needsUpdate = true;
    if (this.monuments.instanceColor) this.monuments.instanceColor.needsUpdate = true;
    if (this.monumentRoofs.instanceColor) this.monumentRoofs.instanceColor.needsUpdate = true;
  }

  /** Orient a rampart segment along its neighbours so the wall reads as a continuous line. */
  private wallAngle(land: SettlementSystem, i: number, j: number): number {
    const w = this.world;
    let dx = 0;
    let dz = 0;
    for (let dj = -1; dj <= 1; dj++) {
      for (let di = -1; di <= 1; di++) {
        if (!di && !dj) continue;
        if (!w.inBounds(i + di, j + dj)) continue;
        if (land.cellWall[w.index(i + di, j + dj)] === 1) {
          dx += di;
          dz += dj;
        }
      }
    }
    if (dx === 0 && dz === 0) return 0;
    return Math.atan2(dz, dx);
  }

  get instanceCount(): number {
    return this.bodies.count + this.roofs.count + this.walls.count + this.monuments.count * 2;
  }

  dispose(): void {
    for (const m of [this.bodies, this.roofs, this.walls, this.monuments, this.monumentRoofs]) {
      m.geometry.dispose();
      (m.material as THREE.Material).dispose();
      m.dispose();
    }
  }
}
