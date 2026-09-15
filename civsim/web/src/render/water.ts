/** The Han and its tributaries: one mesh covering the water cells, rebuilt when reclamation changes them. */
import * as THREE from 'three';
import type { World } from '../core/world/worldData.ts';

export class WaterView {
  readonly mesh: THREE.Mesh;
  private readonly world: World;
  private readonly material: THREE.MeshPhongMaterial;
  private geometry: THREE.BufferGeometry;

  constructor(world: World) {
    this.world = world;
    this.material = new THREE.MeshPhongMaterial({
      color: 0x3a6b87,
      specular: 0x9fc7dd,
      shininess: 90,
      transparent: true,
      opacity: 0.88,
      depthWrite: true,
    });
    this.geometry = new THREE.BufferGeometry();
    this.mesh = new THREE.Mesh(this.geometry, this.material);
    this.mesh.name = 'water';
    this.mesh.renderOrder = 1;
  }

  /** Rebuild from a water mask. The surface sits at a gentle downstream gradient, like the real river. */
  rebuild(water: Uint8Array): void {
    const w = this.world;
    const positions: number[] = [];
    const indices: number[] = [];
    let v = 0;
    const half = w.cellM / 2;
    for (let j = 0; j < w.nz; j++) {
      for (let i = 0; i < w.nx; i++) {
        if (water[w.index(i, j)] !== 1) continue;
        const { x, z } = w.cellCentre(i, j);
        // 2.0 m at the western edge rising to 5.0 m at the eastern edge, plus a little freeboard.
        const surface = 2.6 + (i / (w.nx - 1)) * 3.0;
        positions.push(x - half, surface, z - half);
        positions.push(x + half, surface, z - half);
        positions.push(x - half, surface, z + half);
        positions.push(x + half, surface, z + half);
        indices.push(v, v + 2, v + 1, v + 1, v + 2, v + 3);
        v += 4;
      }
    }
    this.geometry.dispose();
    this.geometry = new THREE.BufferGeometry();
    this.geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    this.geometry.setIndex(indices);
    this.geometry.computeVertexNormals();
    this.geometry.computeBoundingSphere();
    this.mesh.geometry = this.geometry;
  }

  setTime(sunAltitudeDeg: number): void {
    // Water goes from bright daylight blue to near-black at night, with a warm cast at low sun.
    const day = Math.max(0, Math.min(1, (sunAltitudeDeg + 6) / 24));
    const warm = Math.max(0, 1 - Math.abs(sunAltitudeDeg) / 12) * (sunAltitudeDeg > -8 ? 1 : 0);
    this.material.color.setRGB(
      0.06 + day * 0.17 + warm * 0.22,
      0.1 + day * 0.28 + warm * 0.1,
      0.16 + day * 0.37,
    );
    this.material.shininess = 60 + day * 60;
  }

  dispose(): void {
    this.geometry.dispose();
    this.material.dispose();
  }
}
