/**
 * Sky and light, driven by the real solar and lunar positions for Seoul.
 *
 * Nothing here is a time-of-day animation: the sun is placed from the Julian Day, so the day
 * lengthens and shortens through the year, the noon altitude swings between 29° and 76°, and the
 * sunrise point walks along the horizon exactly as it does over the city.
 */
import * as THREE from 'three';
import { horizontalToVector, sunHorizontal, type HorizontalCoords } from '../core/astro/solar.ts';
import { lunarState, moonHorizontal } from '../core/astro/lunar.ts';
import { Rng } from '../core/rng.ts';

const SKY_RADIUS = 90000;

const SKY_VERT = /* glsl */ `
varying vec3 vWorld;
void main() {
  vWorld = normalize(position);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const SKY_FRAG = /* glsl */ `
uniform vec3 uZenith;
uniform vec3 uHorizon;
uniform vec3 uGround;
uniform vec3 uSunDir;
uniform vec3 uSunTint;
uniform float uSunStrength;
uniform float uStarAmount;
varying vec3 vWorld;

// Cheap hash-based starfield, stable in world space.
float hash(vec3 p) {
  p = fract(p * 0.3183099 + vec3(0.71, 0.113, 0.419));
  p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

void main() {
  vec3 dir = normalize(vWorld);
  float h = dir.y;
  vec3 col;
  if (h >= 0.0) {
    col = mix(uHorizon, uZenith, pow(clamp(h, 0.0, 1.0), 0.55));
  } else {
    col = mix(uHorizon, uGround, clamp(-h * 2.5, 0.0, 1.0));
  }

  // Warm glow around the sun's bearing, strongest near the horizon.
  float toSun = max(dot(dir, normalize(uSunDir)), 0.0);
  float glow = pow(toSun, 6.0) * uSunStrength;
  float horizonBand = exp(-abs(h) * 7.0);
  col += uSunTint * (glow * 0.85 + pow(toSun, 2.0) * horizonBand * uSunStrength * 0.5);

  if (uStarAmount > 0.001 && h > -0.02) {
    vec3 cell = floor(dir * 320.0);
    float s = hash(cell);
    float star = smoothstep(0.9975, 0.99995, s);
    float twinkle = 0.75 + 0.25 * hash(cell + 3.7);
    col += vec3(star * uStarAmount * twinkle) * clamp(h * 3.0, 0.0, 1.0);
  }
  gl_FragColor = vec4(col, 1.0);
  // Without these the dome would write linear values straight into an sRGB framebuffer and the sky
  // would sit visibly darker than the fog that is supposed to meet it at the horizon.
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}
`;

export interface SkyState {
  sun: HorizontalCoords;
  moon: HorizontalCoords;
  moonIllumination: number;
  /** 0 at night, 1 in full day. */
  daylight: number;
  /** The colour of the sky right at the horizon; fog and the clear colour copy it exactly. */
  horizonColor: THREE.Color;
}

export class SkyView {
  readonly group = new THREE.Group();
  readonly sunLight: THREE.DirectionalLight;
  readonly moonLight: THREE.DirectionalLight;
  readonly ambient: THREE.HemisphereLight;

  private readonly dome: THREE.Mesh;
  private readonly uniforms: Record<string, THREE.IUniform>;
  private readonly sunDisc: THREE.Mesh;
  private readonly moonDisc: THREE.Mesh;
  private readonly moonMaterial: THREE.MeshBasicMaterial;
  readonly state: SkyState = {
    sun: { altitudeDeg: 0, azimuthDeg: 0 },
    moon: { altitudeDeg: 0, azimuthDeg: 0 },
    moonIllumination: 0,
    daylight: 0,
    horizonColor: new THREE.Color(0x9fb3c8),
  };

  constructor(private readonly latDeg: number, private readonly lonDeg: number) {
    this.uniforms = {
      uZenith: { value: new THREE.Color(0x2b5fa8) },
      uHorizon: { value: new THREE.Color(0xbcd4e8) },
      uGround: { value: new THREE.Color(0x2a2f33) },
      uSunDir: { value: new THREE.Vector3(0, 1, 0) },
      uSunTint: { value: new THREE.Color(0xffd9a0) },
      uSunStrength: { value: 1 },
      uStarAmount: { value: 0 },
    };
    const domeGeo = new THREE.SphereGeometry(SKY_RADIUS, 48, 32);
    const domeMat = new THREE.ShaderMaterial({
      uniforms: this.uniforms,
      vertexShader: SKY_VERT,
      fragmentShader: SKY_FRAG,
      side: THREE.BackSide,
      depthWrite: false,
      fog: false,
    });
    this.dome = new THREE.Mesh(domeGeo, domeMat);
    this.dome.renderOrder = -1000;
    this.dome.frustumCulled = false;
    this.group.add(this.dome);

    this.sunDisc = new THREE.Mesh(
      new THREE.SphereGeometry(SKY_RADIUS * 0.012, 16, 12),
      new THREE.MeshBasicMaterial({ color: 0xfff3d0, fog: false }),
    );
    this.sunDisc.frustumCulled = false;
    this.group.add(this.sunDisc);

    this.moonMaterial = new THREE.MeshBasicMaterial({ color: 0xdfe4ec, fog: false, transparent: true });
    this.moonDisc = new THREE.Mesh(new THREE.SphereGeometry(SKY_RADIUS * 0.011, 16, 12), this.moonMaterial);
    this.moonDisc.frustumCulled = false;
    this.group.add(this.moonDisc);

    this.sunLight = new THREE.DirectionalLight(0xfff0d8, 0);
    this.sunLight.position.set(0, 1, 0);
    this.group.add(this.sunLight);
    this.group.add(this.sunLight.target);

    this.moonLight = new THREE.DirectionalLight(0xaebdd6, 0);
    this.group.add(this.moonLight);
    this.group.add(this.moonLight.target);

    this.ambient = new THREE.HemisphereLight(0x9fb8d8, 0x3a3a30, 0.25);
    this.group.add(this.ambient);

    // Deterministic seed so the starfield is stable between sessions.
    void new Rng(1);
  }

  /** Place everything from the Julian Day. */
  update(jdUt: number, cameraPosition: THREE.Vector3): void {
    const sun = sunHorizontal(jdUt, this.latDeg, this.lonDeg);
    const moon = moonHorizontal(jdUt, this.latDeg, this.lonDeg);
    const lunar = lunarState(jdUt);
    this.state.sun = sun;
    this.state.moon = moon;
    this.state.moonIllumination = lunar.illumination;

    const sv = horizontalToVector(sun);
    const mv = horizontalToVector(moon);
    const sunDir = new THREE.Vector3(sv.x, sv.y, sv.z);
    const moonDir = new THREE.Vector3(mv.x, mv.y, mv.z);

    // The dome and the discs travel with the camera so they never come within reach.
    this.group.position.copy(cameraPosition);
    this.sunDisc.position.copy(sunDir).multiplyScalar(SKY_RADIUS * 0.92);
    this.moonDisc.position.copy(moonDir).multiplyScalar(SKY_RADIUS * 0.9);
    this.moonDisc.visible = moon.altitudeDeg > -2;
    this.moonMaterial.opacity = Math.min(1, 0.25 + lunar.illumination * 0.75);

    const alt = sun.altitudeDeg;
    // Daylight ramps through civil twilight rather than snapping at the horizon.
    const daylight = Math.max(0, Math.min(1, (alt + 6) / 14));
    this.state.daylight = daylight;
    // How red the light is: strongest within a few degrees of the horizon.
    const golden = Math.max(0, 1 - Math.abs(alt) / 10);

    this.sunLight.position.copy(sunDir).multiplyScalar(40000).add(cameraPosition);
    this.sunLight.target.position.copy(cameraPosition);
    this.sunLight.intensity = Math.max(0, Math.min(1, (alt + 2) / 18)) * 2.1;
    this.sunLight.color.setRGB(
      1,
      0.96 - golden * 0.32 - Math.max(0, -alt) * 0.02,
      0.86 - golden * 0.6 - Math.max(0, -alt) * 0.03,
    );
    this.sunLight.visible = alt > -4;

    this.moonLight.position.copy(moonDir).multiplyScalar(40000).add(cameraPosition);
    this.moonLight.target.position.copy(cameraPosition);
    this.moonLight.intensity = moon.altitudeDeg > 0 ? (1 - daylight) * lunar.illumination * 0.22 : 0;

    this.ambient.intensity = 0.1 + daylight * 0.5;
    this.ambient.color.setRGB(0.24 + daylight * 0.4, 0.3 + daylight * 0.42, 0.42 + daylight * 0.43);
    this.ambient.groundColor.setRGB(0.1 + daylight * 0.16, 0.1 + daylight * 0.15, 0.09 + daylight * 0.11);

    const zenith = this.uniforms.uZenith!.value as THREE.Color;
    const horizon = this.uniforms.uHorizon!.value as THREE.Color;
    const ground = this.uniforms.uGround!.value as THREE.Color;
    const tint = this.uniforms.uSunTint!.value as THREE.Color;

    zenith.setRGB(
      0.02 + daylight * 0.14,
      0.03 + daylight * 0.33,
      0.09 + daylight * 0.56,
    );
    horizon.setRGB(
      0.05 + daylight * 0.68 + golden * 0.3,
      0.07 + daylight * 0.75 + golden * 0.1,
      0.14 + daylight * 0.85 - golden * 0.05,
    );
    // Below the horizon the dome is distant haze, a little darker than the sky itself.
    ground.setRGB(0.05 + daylight * 0.42, 0.06 + daylight * 0.45, 0.1 + daylight * 0.46);
    tint.setRGB(1, 0.72 - golden * 0.18, 0.42 - golden * 0.25);

    this.state.horizonColor.copy(horizon);

    (this.uniforms.uSunDir!.value as THREE.Vector3).copy(sunDir);
    this.uniforms.uSunStrength!.value = Math.max(0.05, daylight * 0.8 + golden * 0.9);
    this.uniforms.uStarAmount!.value = Math.max(0, 1 - daylight * 1.6);
    this.sunDisc.visible = alt > -3;
    (this.sunDisc.material as THREE.MeshBasicMaterial).color.setRGB(1, 0.94 - golden * 0.25, 0.8 - golden * 0.5);
  }

  dispose(): void {
    this.dome.geometry.dispose();
    (this.dome.material as THREE.Material).dispose();
    this.sunDisc.geometry.dispose();
    (this.sunDisc.material as THREE.Material).dispose();
    this.moonDisc.geometry.dispose();
    this.moonMaterial.dispose();
  }
}
