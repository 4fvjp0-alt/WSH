/** God-view camera: orbit, pan and zoom from satellite altitude down to street level. */
import * as THREE from 'three';
import type { World } from '../core/world/worldData.ts';

export class GodCamera {
  readonly camera: THREE.PerspectiveCamera;
  target = new THREE.Vector3(0, 40, -2000);
  distance = 26000;
  minDistance = 25;
  maxDistance = 70000;
  pitchDeg = 58;
  yawDeg = 0;

  private readonly world: World;
  private dragging: 'orbit' | 'pan' | null = null;
  private lastX = 0;
  private lastY = 0;
  private readonly keys = new Set<string>();
  private velocity = new THREE.Vector3();
  private keyboardAttached = false;

  constructor(world: World, aspect: number) {
    this.world = world;
    this.camera = new THREE.PerspectiveCamera(52, aspect, 1, 200000);
    this.apply();
  }

  /**
   * Bind pointer controls to a canvas. May be called again for a different canvas, such as the one
   * in the always-on-top window; the keyboard is only ever bound once, or WASD would move twice
   * as fast after coming back.
   */
  attach(dom: HTMLElement): void {
    dom.addEventListener('contextmenu', (e) => e.preventDefault());
    dom.addEventListener('pointerdown', (e) => {
      if (e.button === 2 || e.shiftKey) this.dragging = 'orbit';
      else if (e.button === 0 || e.button === 1) this.dragging = 'pan';
      this.lastX = e.clientX;
      this.lastY = e.clientY;
      dom.setPointerCapture(e.pointerId);
    });
    dom.addEventListener('pointerup', (e) => {
      this.dragging = null;
      try { dom.releasePointerCapture(e.pointerId); } catch { /* already released */ }
    });
    dom.addEventListener('pointermove', (e) => {
      if (!this.dragging) return;
      const dx = e.clientX - this.lastX;
      const dy = e.clientY - this.lastY;
      this.lastX = e.clientX;
      this.lastY = e.clientY;
      if (this.dragging === 'orbit') {
        this.yawDeg += dx * 0.28;
        this.pitchDeg = Math.max(6, Math.min(88, this.pitchDeg - dy * 0.24));
      } else {
        const k = this.distance * 0.0016;
        const yaw = (this.yawDeg * Math.PI) / 180;
        const right = new THREE.Vector3(Math.cos(yaw), 0, -Math.sin(yaw));
        const fwd = new THREE.Vector3(Math.sin(yaw), 0, Math.cos(yaw));
        this.target.addScaledVector(right, -dx * k).addScaledVector(fwd, dy * k);
      }
    });
    dom.addEventListener(
      'wheel',
      (e) => {
        e.preventDefault();
        const f = Math.exp(e.deltaY * 0.0013);
        this.distance = Math.max(this.minDistance, Math.min(this.maxDistance, this.distance * f));
      },
      { passive: false },
    );
    if (!this.keyboardAttached) {
      this.keyboardAttached = true;
      window.addEventListener('keydown', (e) => {
        if ((e.target as HTMLElement)?.tagName === 'INPUT') return;
        this.keys.add(e.key.toLowerCase());
      });
      window.addEventListener('keyup', (e) => this.keys.delete(e.key.toLowerCase()));
      // A window that loses focus must not keep a key held down.
      window.addEventListener('blur', () => this.keys.clear());
    }
  }

  /** Move the view to a place, keeping the current angle. */
  flyTo(x: number, z: number, distance?: number): void {
    this.target.x = x;
    this.target.z = z;
    if (distance !== undefined) this.distance = Math.max(this.minDistance, Math.min(this.maxDistance, distance));
  }

  update(dt: number): void {
    const yaw = (this.yawDeg * Math.PI) / 180;
    const right = new THREE.Vector3(Math.cos(yaw), 0, -Math.sin(yaw));
    const fwd = new THREE.Vector3(Math.sin(yaw), 0, Math.cos(yaw));
    const move = new THREE.Vector3();
    if (this.keys.has('w') || this.keys.has('arrowup')) move.add(fwd);
    if (this.keys.has('s') || this.keys.has('arrowdown')) move.sub(fwd);
    if (this.keys.has('d') || this.keys.has('arrowright')) move.add(right);
    if (this.keys.has('a') || this.keys.has('arrowleft')) move.sub(right);
    if (this.keys.has('q')) this.yawDeg -= 45 * dt;
    if (this.keys.has('e')) this.yawDeg += 45 * dt;
    if (move.lengthSq() > 0) move.normalize();
    this.velocity.lerp(move.multiplyScalar(this.distance * 0.9), Math.min(1, dt * 8));
    this.target.addScaledVector(this.velocity, dt);

    const half = { x: (this.world.nx * this.world.cellM) / 2, z: (this.world.nz * this.world.cellM) / 2 };
    this.target.x = Math.max(-half.x * 1.2, Math.min(half.x * 1.2, this.target.x));
    this.target.z = Math.max(-half.z * 1.2, Math.min(half.z * 1.2, this.target.z));
    this.target.y = this.world.heightAt(this.target.x, this.target.z);
    this.apply();
  }

  private apply(): void {
    const pitch = (this.pitchDeg * Math.PI) / 180;
    const yaw = (this.yawDeg * Math.PI) / 180;
    const horizontal = Math.cos(pitch) * this.distance;
    const offset = new THREE.Vector3(
      Math.sin(yaw) * horizontal,
      Math.sin(pitch) * this.distance,
      Math.cos(yaw) * horizontal,
    );
    this.camera.position.copy(this.target).add(offset);
    // Never let the camera drop below the ground it is looking at.
    const ground = this.world.heightAt(this.camera.position.x, this.camera.position.z) + 3;
    if (this.camera.position.y < ground) this.camera.position.y = ground;
    this.camera.lookAt(this.target);
    this.camera.near = Math.max(0.5, this.distance * 0.0025);
    this.camera.far = Math.max(60000, this.distance * 8);
    this.camera.updateProjectionMatrix();
  }

  setAspect(aspect: number): void {
    this.camera.aspect = aspect;
    this.camera.updateProjectionMatrix();
  }
}
