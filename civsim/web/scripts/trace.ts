/** Prints the simulated trajectory beside the historical record. */
import { Simulation } from '../src/core/sim.ts';
import { referencePopulation } from '../src/core/world/history.ts';
import { loadWorldFromDisk } from '../tests/loadWorld.node.ts';

const world = await loadWorldFromDisk();
const sim = new Simulation(world, { mode: 'reproduce', seed: 12345 });

function southShare(): number {
  const w = sim.world;
  let north = 0;
  let south = 0;
  for (let i = 0; i < w.nx; i++) {
    let riverJ = -1;
    for (let j = 0; j < w.nz; j++) if (sim.land.water[w.index(i, j)] === 1) riverJ = Math.max(riverJ, j);
    if (riverJ < 0) continue;
    for (let j = 0; j < w.nz; j++) {
      const k = w.index(i, j);
      if (sim.land.cellBuild[k]! < 0.05) continue;
      if (j > riverJ) north++; else south++;
    }
  }
  return north + south > 0 ? south / (north + south) : 0;
}

const t0 = Date.now();
console.log('  year     sim pop     ref pop   ratio  settl  built km²  farm  food  south%  largest');
for (const y of [200, 400, 475, 600, 800, 1100, 1400, 1450, 1600, 1700, 1800, 1900, 1930, 1945, 1955, 1965, 1975, 1985, 1995, 2010, 2026]) {
  const s = sim.runTo(y);
  const ratio = s.population / referencePopulation(y);
  console.log(
    String(y).padStart(6),
    Math.round(s.population).toLocaleString().padStart(12),
    Math.round(referencePopulation(y)).toLocaleString().padStart(12),
    ratio.toFixed(2).padStart(6),
    String(s.settlements).padStart(6),
    ((s.builtCells * 1e4) / 1e6).toFixed(0).padStart(9),
    String(s.farmCells).padStart(6),
    s.foodRatio.toFixed(2).padStart(6),
    (southShare() * 100).toFixed(0).padStart(7),
    ' ' + s.largestSettlement,
  );
}
console.log(`\nelapsed ${(Date.now() - t0) / 1000}s, log entries ${sim.log.length}`);
