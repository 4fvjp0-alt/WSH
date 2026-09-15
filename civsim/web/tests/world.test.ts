import { beforeAll, describe, expect, it } from 'vitest';
import { LandUse, World } from '../src/core/world/worldData.ts';
import { lonLatToLocal, localToLonLat } from '../src/core/geo/localFrame.ts';
import { loadWorldFromDisk } from './loadWorld.node.ts';

let world: World;
beforeAll(async () => {
  world = await loadWorldFromDisk();
});

describe('local frame', () => {
  it('puts City Hall at the origin', () => {
    const p = lonLatToLocal(126.978, 37.5665);
    expect(Math.abs(p.x)).toBeLessThan(1e-6);
    expect(Math.abs(p.z)).toBeLessThan(1e-6);
  });

  it('round-trips a corner of the play area', () => {
    const p = lonLatToLocal(127.19, 37.71);
    const back = localToLonLat(p.x, p.z);
    expect(back.lon).toBeCloseTo(127.19, 9);
    expect(back.lat).toBeCloseTo(37.71, 9);
    expect(p.x).toBeGreaterThan(18000);
    expect(p.z).toBeGreaterThan(15500);
  });
});

describe('baked terrain', () => {
  it('covers the whole play area at the expected resolution', () => {
    expect(world.nx).toBe(380);
    expect(world.nz).toBe(324);
    expect(world.cellM).toBe(100);
    expect(world.demHeight.length).toBe(761 * 649);
  });

  it('reproduces real Seoul elevations', () => {
    const at = (lat: number, lon: number): number => {
      const p = lonLatToLocal(lon, lat);
      return world.heightAt(p.x, p.z);
    };
    // Bukhansan is the roof of the city; the 50 m grid smooths the granite summit a little.
    expect(at(37.6586, 126.9797)).toBeGreaterThan(700);
    // Namsan stands alone in the middle of the basin.
    expect(at(37.5512, 126.9882)).toBeGreaterThan(200);
    expect(at(37.5512, 126.9882)).toBeLessThan(300);
    // Gwanaksan closes the basin to the south.
    expect(at(37.4452, 126.964)).toBeGreaterThan(500);
    // The old city centre sits low.
    expect(at(37.5665, 126.978)).toBeGreaterThan(15);
    expect(at(37.5665, 126.978)).toBeLessThan(60);
    // The river surface is near sea level.
    expect(at(37.5175, 126.958)).toBeLessThan(25);
  });

  it('places the highest point on Bukhansan', () => {
    let best = -Infinity;
    let bx = 0;
    let bz = 0;
    const d = world.meta.dem;
    for (let j = 0; j < d.nz; j++) {
      for (let i = 0; i < d.nx; i++) {
        const h = world.demHeight[j * d.nx + i]!;
        if (h > best) {
          best = h;
          bx = d.x0 + i * d.cellM;
          bz = d.z0 + j * d.cellM;
        }
      }
    }
    const { lat, lon } = localToLonLat(bx, bz);
    expect(best).toBeGreaterThan(750);
    expect(lat).toBeGreaterThan(37.64);
    expect(lat).toBeLessThan(37.68);
    expect(lon).toBeGreaterThan(126.95);
    expect(lon).toBeLessThan(127.01);
  });
});

describe('the Han river', () => {
  it('crosses the whole map', () => {
    for (let i = 0; i < world.nx; i += 10) {
      let found = false;
      for (let j = 0; j < world.nz; j++) {
        if (world.water[world.index(i, j)] === 1) {
          found = true;
          break;
        }
      }
      expect(found, `column ${i} has no water`).toBe(true);
    }
  });

  it('covers about the right area', () => {
    let n = 0;
    for (let k = 0; k < world.water.length; k++) if (world.water[k] === 1) n++;
    const km2 = (n * world.cellM * world.cellM) / 1e6;
    expect(km2).toBeGreaterThan(30);
    expect(km2).toBeLessThan(60);
  });

  it('runs south of the city centre and reaches the map edges', () => {
    // At City Hall's longitude the Han sits roughly 6 km to the south.
    const i = Math.floor((0 - world.x0) / world.cellM);
    const rows: number[] = [];
    for (let j = 0; j < world.nz; j++) if (world.water[world.index(i, j)] === 1) rows.push(j);
    expect(rows.length).toBeGreaterThan(4);
    const midZ = world.z0 + ((rows[0]! + rows[rows.length - 1]!) / 2) * world.cellM;
    expect(midZ).toBeLessThan(-4000);
    expect(midZ).toBeGreaterThan(-9000);
  });

  it('marks water cells as water land use and gives them no fertility', () => {
    for (let k = 0; k < world.water.length; k++) {
      if (world.water[k] === 1) {
        expect(world.fertility[k]).toBe(0);
        expect(world.buildable[k]).toBe(0);
      }
    }
  });
});

describe('derived cell qualities', () => {
  it('finds the floodplain more fertile than the mountains', () => {
    const plain = lonLatToLocal(127.105, 37.505); // 송파 flats
    const hill = lonLatToLocal(126.9797, 37.6586); // 북한산
    const pc = world.cellAt(plain.x, plain.z);
    const hc = world.cellAt(hill.x, hill.z);
    expect(world.fertility[world.index(pc.i, pc.j)]!).toBeGreaterThan(
      world.fertility[world.index(hc.i, hc.j)]!,
    );
  });

  it('finds the basin more buildable than the ridges', () => {
    const basin = lonLatToLocal(126.99, 37.57);
    const ridge = lonLatToLocal(126.9797, 37.6586);
    const bc = world.cellAt(basin.x, basin.z);
    const rc = world.cellAt(ridge.x, ridge.z);
    expect(world.buildable[world.index(bc.i, bc.j)]!).toBeGreaterThan(0.6);
    expect(world.buildable[world.index(rc.i, rc.j)]!).toBeLessThan(0.4);
  });

  it('measures distance to water as zero in the river and large in the hills', () => {
    const river = lonLatToLocal(126.958, 37.5175);
    const rc = world.cellAt(river.x, river.z);
    expect(world.distanceToWater[world.index(rc.i, rc.j)]!).toBeLessThan(300);
    const hill = lonLatToLocal(126.9797, 37.6586);
    const hc = world.cellAt(hill.x, hill.z);
    expect(world.distanceToWater[world.index(hc.i, hc.j)]!).toBeGreaterThan(5000);
  });

  it('starts with every non-water cell wild', () => {
    expect(LandUse.Wild).toBe(0);
  });
});
