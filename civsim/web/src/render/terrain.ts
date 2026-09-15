/** The ground: one indexed mesh built from the baked DEM, recoloured as the land use changes. */
import * as THREE from 'three';
import { LandUse, World } from '../core/world/worldData.ts';
import { Era } from '../core/era/eras.ts';
import type { SettlementSystem } from '../core/settle/settlement.ts';
import { hash2 } from '../core/rng.ts';

const LAND_HAZE = new THREE.Color(0x66714a);

const PALETTE = {
  water: new THREE.Color(0x2c4f63),
  marsh: new THREE.Color(0x5f6f4a),
  grass: new THREE.Color(0x6f7f4a),
  meadow: new THREE.Color(0x7d8a52),
  forest: new THREE.Color(0x3f5a34),
  highForest: new THREE.Color(0x354a2e),
  rock: new THREE.Color(0x6e6558),
  peak: new THREE.Color(0x8a8378),
  farm: new THREE.Color(0x8c9a4e),
  paddy: new THREE.Color(0x77903f),
  village: new THREE.Color(0x7d7154),
  town: new THREE.Color(0x7d7360),
  urban: new THREE.Color(0x7a786f),
  dense: new THREE.Color(0x76777c),
  industrial: new THREE.Color(0x77736c),
  road: new THREE.Color(0x565350),
  wall: new THREE.Color(0x9c958a),
  monument: new THREE.Color(0xa8714d),
  reclaimed: new THREE.Color(0x8a8b7a),
};

export class TerrainView {
  readonly mesh: THREE.Mesh;
  /** Land beyond the mapped area, so the horizon reads as more countryside rather than a void. */
  readonly surround: THREE.Mesh;
  private readonly geometry: THREE.BufferGeometry;
  private readonly colors: Float32Array;
  private readonly world: World;
  private readonly stride: number;
  private readonly vx: number;
  private readonly vz: number;

  constructor(world: World, stride = 1) {
    this.world = world;
    this.stride = stride;
    const d = world.meta.dem;
    this.vx = Math.floor((d.nx - 1) / stride) + 1;
    this.vz = Math.floor((d.nz - 1) / stride) + 1;

    const count = this.vx * this.vz;
    const positions = new Float32Array(count * 3);
    this.colors = new Float32Array(count * 3);

    for (let j = 0; j < this.vz; j++) {
      for (let i = 0; i < this.vx; i++) {
        const si = Math.min(d.nx - 1, i * stride);
        const sj = Math.min(d.nz - 1, j * stride);
        const n = j * this.vx + i;
        positions[n * 3] = d.x0 + si * d.cellM;
        positions[n * 3 + 1] = world.demHeight[sj * d.nx + si]!;
        positions[n * 3 + 2] = d.z0 + sj * d.cellM;
      }
    }

    const quads = (this.vx - 1) * (this.vz - 1);
    const indices = count > 65535 ? new Uint32Array(quads * 6) : new Uint16Array(quads * 6);
    let p = 0;
    for (let j = 0; j < this.vz - 1; j++) {
      for (let i = 0; i < this.vx - 1; i++) {
        const a = j * this.vx + i;
        const b = a + 1;
        const c = a + this.vx;
        const e = c + 1;
        indices[p++] = a; indices[p++] = c; indices[p++] = b;
        indices[p++] = b; indices[p++] = c; indices[p++] = e;
      }
    }

    this.geometry = new THREE.BufferGeometry();
    this.geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    this.geometry.setAttribute('color', new THREE.BufferAttribute(this.colors, 3));
    this.geometry.setIndex(new THREE.BufferAttribute(indices, 1));
    this.geometry.computeVertexNormals();
    this.geometry.computeBoundingSphere();

    const material = new THREE.MeshLambertMaterial({ vertexColors: true });
    this.mesh = new THREE.Mesh(this.geometry, material);
    this.mesh.name = 'terrain';
    this.mesh.receiveShadow = false;

    // A wide, very slightly dished plane under everything. Fog swallows it well before its edge,
    // so the eye reads distant land rather than the underside of the sky dome.
    const surroundGeo = new THREE.CircleGeometry(150000, 72);
    surroundGeo.rotateX(-Math.PI / 2);
    this.surround = new THREE.Mesh(
      surroundGeo,
      new THREE.MeshLambertMaterial({ color: 0x6a7550, fog: true }),
    );
    this.surround.position.y = -6;
    this.surround.name = 'surround';
    this.surround.renderOrder = -1;
  }

  /**
   * Keep the land beyond the map continuous with the haze on the horizon. Taking the colour from
   * the fog and pulling it a little toward green means the edge of the mapped area stops reading
   * as an edge at all, at any time of day.
   */
  setSurroundColor(fogColor: THREE.Color, daylight: number): void {
    const m = this.surround.material as THREE.MeshLambertMaterial;
    m.color.copy(fogColor).lerp(LAND_HAZE, 0.34 + daylight * 0.12);
    // Lambert shading would darken a flat plane under a low sun; compensate so it stays level
    // with the fog it is supposed to disappear into.
    m.color.multiplyScalar(1 / Math.max(0.35, 0.28 + daylight * 0.85));
  }

  /** Recolour from the current land use. Called when the simulation has moved, not every frame. */
  updateColors(land: SettlementSystem | null, era: Era): void {
    const w = this.world;
    const d = w.meta.dem;
    const c = new THREE.Color();
    const winter = new THREE.Color(0xc8ccd0);

    for (let j = 0; j < this.vz; j++) {
      const sj = Math.min(d.nz - 1, j * this.stride);
      const z = d.z0 + sj * d.cellM;
      for (let i = 0; i < this.vx; i++) {
        const si = Math.min(d.nx - 1, i * this.stride);
        const x = d.x0 + si * d.cellM;
        const h = w.demHeight[sj * d.nx + si]!;
        const cell = w.cellAt(x, z);
        const k = w.inBounds(cell.i, cell.j) ? w.index(cell.i, cell.j) : -1;

        c.copy(this.naturalColor(h, k));
        if (k >= 0 && land) {
          const use = land.cellUse[k]! as LandUse;
          const build = land.cellBuild[k]!;
          const built = this.builtColor(use, era);
          if (built) c.lerp(built, Math.min(1, 0.35 + build * 0.65));
          if (land.cellRoad[k]! >= 2 && build < 0.5) c.lerp(PALETTE.road, 0.4);
          if (land.cellDamage[k]! > 0.15) c.lerp(new THREE.Color(0x4a4038), Math.min(0.75, land.cellDamage[k]!));
        }
        // A little per-vertex grain so large flat areas do not read as plastic.
        const n = 0.94 + hash2(si, sj, 3) * 0.12;
        c.multiplyScalar(n);
        void winter;

        const idx = (j * this.vx + i) * 3;
        this.colors[idx] = c.r;
        this.colors[idx + 1] = c.g;
        this.colors[idx + 2] = c.b;
      }
    }
    (this.geometry.getAttribute('color') as THREE.BufferAttribute).needsUpdate = true;
  }

  private naturalColor(h: number, k: number): THREE.Color {
    const w = this.world;
    if (k >= 0 && w.water[k] === 1) return PALETTE.water;
    const out = new THREE.Color();
    if (h < 8) return out.copy(PALETTE.marsh);
    if (h < 40) return out.copy(PALETTE.grass).lerp(PALETTE.meadow, (h - 8) / 32);
    if (h < 140) return out.copy(PALETTE.meadow).lerp(PALETTE.forest, (h - 40) / 100);
    if (h < 320) return out.copy(PALETTE.forest).lerp(PALETTE.highForest, (h - 140) / 180);
    if (h < 560) return out.copy(PALETTE.highForest).lerp(PALETTE.rock, (h - 320) / 240);
    return out.copy(PALETTE.rock).lerp(PALETTE.peak, Math.min(1, (h - 560) / 260));
  }

  private builtColor(use: LandUse, era: Era): THREE.Color | null {
    switch (use) {
      case LandUse.Farm: return era >= Era.Colonial ? PALETTE.farm : PALETTE.paddy;
      case LandUse.Village: return PALETTE.village;
      case LandUse.Town: return PALETTE.town;
      case LandUse.Urban: return PALETTE.urban;
      case LandUse.Dense: return PALETTE.dense;
      case LandUse.Industrial: return PALETTE.industrial;
      case LandUse.Road: return PALETTE.road;
      case LandUse.Wall: return PALETTE.wall;
      case LandUse.Monument: return PALETTE.monument;
      case LandUse.Reclaimed: return PALETTE.reclaimed;
      default: return null;
    }
  }

  dispose(): void {
    this.geometry.dispose();
    (this.mesh.material as THREE.Material).dispose();
    this.surround.geometry.dispose();
    (this.surround.material as THREE.Material).dispose();
  }
}
