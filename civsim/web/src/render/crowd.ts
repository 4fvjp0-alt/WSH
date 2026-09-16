/** The visible crowd: one instance per summoned person, updated every frame. */
import * as THREE from 'three';
import { AgentRole, AgentSystem, MAX_AGENTS } from '../core/agents/agents.ts';
import type { World } from '../core/world/worldData.ts';

const ROLE_COLORS: Record<AgentRole, number> = {
  [AgentRole.Farmer]: 0xd8cfae,
  [AgentRole.Townsfolk]: 0xb8c2d8,
  [AgentRole.Official]: 0x6f7fb8,
  [AgentRole.Labourer]: 0xc1a184,
  [AgentRole.Child]: 0xe0d0c0,
};

export class CrowdView {
  readonly group = new THREE.Group();
  private readonly bodies: THREE.InstancedMesh;
  private readonly heads: THREE.InstancedMesh;
  private readonly dummy = new THREE.Object3D();
  private readonly colour = new THREE.Color();

  constructor(private readonly world: World) {
    const mat = new THREE.MeshLambertMaterial();
    // A person is a 1.7 m capsule; at this scale that is all the silhouette anyone needs.
    this.bodies = new THREE.InstancedMesh(new THREE.CapsuleGeometry(0.28, 0.95, 3, 6), mat.clone(), MAX_AGENTS);
    this.bodies.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX_AGENTS * 3), 3);
    this.bodies.count = 0;
    this.bodies.frustumCulled = false;
    this.bodies.name = 'crowd';

    this.heads = new THREE.InstancedMesh(new THREE.SphereGeometry(0.21, 6, 5), mat.clone(), MAX_AGENTS);
    this.heads.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(MAX_AGENTS * 3), 3);
    this.heads.count = 0;
    this.heads.frustumCulled = false;

    this.group.add(this.bodies, this.heads);
  }

  /**
   * @param cameraDistance used to hold people at a readable size from a little way off. A 1.7 m
   * person is under a pixel from 800 m up, so the marker grows gently with distance and stops at
   * 3.2x, which keeps a crowd legible without turning anyone into a giant.
   */
  update(agents: AgentSystem, time: number, cameraDistance = 0): void {
    const distanceScale = Math.max(1, Math.min(3.2, cameraDistance / 300));
    let n = 0;
    for (let id = 0; id < agents.count; id++) {
      if (!agents.isVisible(id)) continue;
      const x = agents.x[id]!;
      const z = agents.z[id]!;
      const ground = this.world.heightAt(x, z);
      // A small bob so a walking crowd does not look like it is sliding.
      const moving = Math.hypot(agents.targetX[id]! - x, agents.targetZ[id]! - z) > 1.5;
      const bob = moving ? Math.abs(Math.sin(time * 4.5 + (agents.seed[id]! % 100) * 0.3)) * 0.07 : 0;

      this.dummy.position.set(x, ground + 0.85 * distanceScale + bob, z);
      this.dummy.rotation.set(0, agents.heading[id]!, 0);
      const scale = (agents.role[id] === AgentRole.Child ? 0.72 : 1) * distanceScale;
      this.dummy.scale.set(scale, scale, scale);
      this.dummy.updateMatrix();
      this.bodies.setMatrixAt(n, this.dummy.matrix);

      this.dummy.position.y = ground + 1.55 * scale + bob;
      this.dummy.updateMatrix();
      this.heads.setMatrixAt(n, this.dummy.matrix);

      this.colour.setHex(ROLE_COLORS[agents.role[id] as AgentRole]);
      this.bodies.setColorAt(n, this.colour);
      this.heads.setColorAt(n, this.colour.clone().multiplyScalar(0.92));
      n++;
    }
    this.bodies.count = n;
    this.heads.count = n;
    this.bodies.instanceMatrix.needsUpdate = true;
    this.heads.instanceMatrix.needsUpdate = true;
    if (this.bodies.instanceColor) this.bodies.instanceColor.needsUpdate = true;
    if (this.heads.instanceColor) this.heads.instanceColor.needsUpdate = true;
  }

  setVisible(v: boolean): void {
    this.group.visible = v;
  }

  get drawnCount(): number {
    return this.bodies.count;
  }

  dispose(): void {
    for (const m of [this.bodies, this.heads]) {
      m.geometry.dispose();
      (m.material as THREE.Material).dispose();
      m.dispose();
    }
  }
}
