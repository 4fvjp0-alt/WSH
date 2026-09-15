import { beforeAll, describe, expect, it } from 'vitest';
import { Simulation } from '../src/core/sim.ts';
import { LandUse, World } from '../src/core/world/worldData.ts';
import { POPULATION_CURVE, referencePopulation } from '../src/core/world/history.ts';
import { Era } from '../src/core/era/eras.ts';
import { lonLatToLocal } from '../src/core/geo/localFrame.ts';
import { loadWorldFromDisk } from './loadWorld.node.ts';

let world: World;
beforeAll(async () => {
  world = await loadWorldFromDisk();
});

describe('reference population curve', () => {
  it('passes through every anchor', () => {
    for (const a of POPULATION_CURVE) {
      expect(referencePopulation(a.year)).toBeCloseTo(a.population, -2);
    }
  });

  it('interpolates between anchors monotonically where history does', () => {
    let prev = referencePopulation(1963);
    for (let y = 1964; y <= 1990; y++) {
      const cur = referencePopulation(y);
      expect(cur).toBeGreaterThan(prev);
      prev = cur;
    }
  });

  it('clamps outside the recorded span', () => {
    expect(referencePopulation(50)).toBe(12000);
    expect(referencePopulation(2100)).toBe(9300000);
  });
});

describe('a full run from AD 100 to the present', () => {
  let sim: Simulation;
  const marks = new Map<number, ReturnType<Simulation['runTo']>>();
  const southShare: Array<{ year: number; share: number }> = [];

  beforeAll(() => {
    sim = new Simulation(world, { mode: 'reproduce', seed: 12345 });
    for (const year of [300, 500, 800, 1100, 1400, 1600, 1750, 1900, 1940, 1960, 1975, 1990, 2010, 2026]) {
      marks.set(year, { ...sim.runTo(year) });
      southShare.push({ year, share: southOfHanShare(sim) });
    }
  }, 300000);

  function southOfHanShare(s: Simulation): number {
    // Share of built-up cells that sit south of the Han, by comparing to the river's own rows.
    const w = s.world;
    let north = 0;
    let south = 0;
    for (let i = 0; i < w.nx; i++) {
      let riverJ = -1;
      for (let j = 0; j < w.nz; j++) if (w.water[w.index(i, j)] === 1) riverJ = Math.max(riverJ, j);
      if (riverJ < 0) continue;
      for (let j = 0; j < w.nz; j++) {
        const k = w.index(i, j);
        if (s.land.cellBuild[k]! < 0.05) continue;
        if (j > riverJ) north++;
        else south++;
      }
    }
    const total = north + south;
    return total > 0 ? south / total : 0;
  }

  it('tracks the historical population within a factor of two', () => {
    for (const [year, stat] of marks) {
      const ref = referencePopulation(year);
      expect(stat.population, `year ${year}`).toBeGreaterThan(ref * 0.5);
      expect(stat.population, `year ${year}`).toBeLessThan(ref * 2);
    }
  });

  it('stays within 25 percent of the historical curve at every mark', () => {
    for (const [year, stat] of marks) {
      const ratio = stat.population / referencePopulation(year);
      expect(ratio, `year ${year} ratio ${ratio.toFixed(2)}`).toBeGreaterThan(0.75);
      expect(ratio, `year ${year} ratio ${ratio.toFixed(2)}`).toBeLessThan(1.25);
    }
  });

  it('keeps people fed without either famine or absurd surplus', () => {
    for (const [year, stat] of marks) {
      expect(stat.foodRatio, `year ${year}`).toBeGreaterThan(0.6);
      expect(stat.foodRatio, `year ${year}`).toBeLessThan(2.0);
    }
  });

  it('reaches roughly the right size at the key dates', () => {
    expect(marks.get(1400)!.population).toBeGreaterThan(30000);
    expect(marks.get(1400)!.population).toBeLessThan(160000);
    expect(marks.get(1900)!.population).toBeGreaterThan(120000);
    expect(marks.get(1900)!.population).toBeLessThan(400000);
    expect(marks.get(1975)!.population).toBeGreaterThan(4000000);
    expect(marks.get(2026)!.population).toBeGreaterThan(7000000);
    expect(marks.get(2026)!.population).toBeLessThan(13000000);
  });

  it('moves through the eras in order', () => {
    expect(marks.get(300)!.era).toBe(Era.ThreeKingdoms);
    expect(marks.get(800)!.era).toBe(Era.UnifiedSilla);
    expect(marks.get(1100)!.era).toBe(Era.Goryeo);
    expect(marks.get(1400)!.era).toBe(Era.JoseonEarly);
    expect(marks.get(1750)!.era).toBe(Era.JoseonLate);
    expect(marks.get(1940)!.era).toBe(Era.Colonial);
    expect(marks.get(1960)!.era).toBe(Era.PostWar);
    expect(marks.get(1975)!.era).toBe(Era.Industrial);
    expect(marks.get(2026)!.era).toBe(Era.Modern);
  });

  it('names the right polity for each era', () => {
    expect(marks.get(300)!.polity.shortName).toBe('백제');
    expect(marks.get(500)!.polity.shortName).toBe('고구려');
    expect(marks.get(800)!.polity.shortName).toBe('통일신라');
    expect(marks.get(1100)!.polity.shortName).toBe('고려');
    expect(marks.get(1600)!.polity.shortName).toBe('조선');
    expect(marks.get(1940)!.polity.shortName).toBe('경성부');
    expect(marks.get(2010)!.polity.shortName).toBe('서울');
  });

  it('follows the river the way the city actually did', () => {
    // 한성백제 sat on the south bank at 풍납토성.
    for (const year of [300, 500]) {
      expect(southShare.find((s) => s.year === year)!.share, `year ${year}`).toBeGreaterThan(0.75);
    }
    // Once the capital moved north in 1394 the city stayed north of the Han for five centuries.
    for (const year of [1400, 1600, 1750, 1900, 1940]) {
      expect(southShare.find((s) => s.year === year)!.share, `year ${year}`).toBeLessThan(0.35);
    }
    // 강남 only opens up after the 1963 expansion, and then it takes a large share.
    expect(southShare.find((s) => s.year === 1960)!.share).toBeLessThan(0.3);
    expect(southShare.find((s) => s.year === 2026)!.share).toBeGreaterThan(0.3);
  });

  it('renames the capital as the polities change', () => {
    const titles = sim.log.map((l) => l.title);
    expect(titles).toContain('한양 천도');
    expect(titles).toContain('광복');
    const capital = sim.land.settlements.find((s) => s.isCapital);
    expect(capital!.name).toBe('서울');
  });

  it('puts the capital in the historic centre after the 1394 move', () => {
    const capital = sim.land.settlements.find((s) => s.isCapital);
    expect(capital).toBeDefined();
    const target = lonLatToLocal(126.978, 37.5665);
    expect(Math.hypot(capital!.x - target.x, capital!.z - target.z)).toBeLessThan(6000);
  });

  it('builds a city wall that climbs onto the ridges', () => {
    const wallCells: number[] = [];
    for (let k = 0; k < sim.land.cellWall.length; k++) if (sim.land.cellWall[k] === 1) wallCells.push(k);
    expect(wallCells.length).toBeGreaterThan(80);
    let sum = 0;
    for (const k of wallCells) sum += world.height[k]!;
    const wallMean = sum / wallCells.length;
    // The average height along the wall must clear the basin floor it encloses.
    expect(wallMean).toBeGreaterThan(50);
  });

  it('grows a built-up area of a plausible size', () => {
    const cells = marks.get(2026)!.builtCells;
    const km2 = (cells * 100 * 100) / 1e6;
    // Seoul's built-up area is on the order of 350 km²; the play area is larger than the city.
    expect(km2).toBeGreaterThan(220);
    expect(km2).toBeLessThan(700);
  });

  it('turns farmland into city as the eras pass', () => {
    expect(marks.get(1750)!.farmCells).toBeGreaterThan(marks.get(2026)!.farmCells * 3);
  });

  it('matches the recorded density of Joseon Hanyang', () => {
    // 한성부 held on the order of 190,000 people in about 16 km² inside and around the walls.
    const m = marks.get(1750)!;
    const km2 = (m.builtCells * 100 * 100) / 1e6;
    const perKm2 = m.population / km2;
    expect(perKm2).toBeGreaterThan(5000);
    expect(perKm2).toBeLessThan(25000);
  });

  it('records the historical anchors in order', () => {
    const titles = sim.log.map((l) => l.title);
    const wanted = ['풍납토성 축조', '고구려의 한성 함락', '한양 천도', '경복궁 창건', '임진왜란', '한국전쟁', '행정구역 대확장', '여의도 개발'];
    let last = -1;
    for (const t of wanted) {
      const idx = titles.indexOf(t);
      expect(idx, `missing anchor: ${t}`).toBeGreaterThanOrEqual(0);
      expect(idx).toBeGreaterThan(last);
      last = idx;
    }
  });

  it('loses people to the wars', () => {
    const war = sim.log.find((l) => l.title === '임진왜란');
    expect(war).toBeDefined();
  });

  it('reclaims land at Yeouido and Jamsil', () => {
    for (const [name, lat, lon] of [['여의도', 37.5216, 126.9241], ['잠실', 37.5133, 127.1]] as [string, number, number][]) {
      const p = lonLatToLocal(lon, lat);
      const c = world.cellAt(p.x, p.z);
      let reclaimed = 0;
      for (let dj = -12; dj <= 12; dj++) {
        for (let di = -12; di <= 12; di++) {
          if (!world.inBounds(c.i + di, c.j + dj)) continue;
          const k = world.index(c.i + di, c.j + dj);
          if (sim.land.cellUse[k] === LandUse.Reclaimed || (world.water[k] === 0 && sim.land.cellBuild[k]! > 0.05)) reclaimed++;
        }
      }
      expect(reclaimed, `${name} reclamation`).toBeGreaterThan(20);
    }
  });

  it('is deterministic', () => {
    const a = new Simulation(world, { mode: 'reproduce', seed: 999 }).runTo(1500);
    const worldB = world;
    const b = new Simulation(worldB, { mode: 'reproduce', seed: 999 }).runTo(1500);
    expect(Math.round(b.population)).toBe(Math.round(a.population));
  });
});
