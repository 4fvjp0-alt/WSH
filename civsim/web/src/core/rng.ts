/**
 * Deterministic RNG. Same seed and same inputs always produce the same history,
 * which is what makes saves, replays and regression tests possible.
 * SplitMix64-derived 32-bit variant (mulberry32): fast, well-distributed, no dependencies.
 */
export class Rng {
  private state: number;

  constructor(seed: number) {
    this.state = seed >>> 0;
  }

  /** Uniform in [0, 1). */
  next(): number {
    this.state = (this.state + 0x6d2b79f5) >>> 0;
    let t = this.state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  }

  /** Uniform in [min, max). */
  range(min: number, max: number): number {
    return min + this.next() * (max - min);
  }

  /** Integer in [0, n). */
  int(n: number): number {
    return Math.floor(this.next() * n);
  }

  bool(probability = 0.5): boolean {
    return this.next() < probability;
  }

  pick<T>(items: readonly T[]): T {
    return items[this.int(items.length)]!;
  }

  /** Standard normal via Box-Muller. */
  normal(mean = 0, stdDev = 1): number {
    const u = Math.max(this.next(), 1e-12);
    const v = this.next();
    return mean + stdDev * Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v);
  }

  /** Derive an independent stream, so adding a system does not shift another's numbers. */
  fork(salt: number): Rng {
    return new Rng((Math.imul(this.state ^ salt, 0x9e3779b1) ^ (salt << 16)) >>> 0);
  }

  get seed(): number {
    return this.state;
  }

  set seed(v: number) {
    this.state = v >>> 0;
  }
}

/** Stable hash of two integers to a [0,1) value — for per-cell noise that needs no storage. */
export function hash2(x: number, y: number, salt = 0): number {
  let h = Math.imul(x, 0x27d4eb2d) ^ Math.imul(y, 0x165667b1) ^ Math.imul(salt, 0x9e3779b1);
  h = Math.imul(h ^ (h >>> 15), 0x85ebca6b);
  h = Math.imul(h ^ (h >>> 13), 0xc2b2ae35);
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
}
