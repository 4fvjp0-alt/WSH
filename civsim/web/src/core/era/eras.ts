/** Technological/cultural eras. Each one changes what gets built, how people live, and how fast things grow. */

export enum Era {
  ThreeKingdoms = 0, // 삼국시대 (한성백제)
  UnifiedSilla = 1,  // 통일신라
  Goryeo = 2,        // 고려 남경
  JoseonEarly = 3,   // 조선 전기 (한양 천도 이후)
  JoseonLate = 4,    // 조선 후기
  Colonial = 5,      // 대한제국·일제강점기 (경성)
  PostWar = 6,       // 해방·한국전쟁 이후 복구
  Industrial = 7,    // 산업화·강남 개발
  Modern = 8,        // 현대
}

export const ALL_ERAS: Era[] = [
  Era.ThreeKingdoms, Era.UnifiedSilla, Era.Goryeo, Era.JoseonEarly,
  Era.JoseonLate, Era.Colonial, Era.PostWar, Era.Industrial, Era.Modern,
];

export interface EraProfile {
  era: Era;
  name: string;
  /** Gregorian year this era begins. */
  startYear: number;
  /** Food produced per worker per year, in person-years of subsistence. Above 1 means a surplus. */
  farmYield: number;
  /** Fraction of the population that can live off non-farm work. */
  urbanShare: number;
  /** Baseline crude birth rate per 1000 per year. */
  birthRate: number;
  /** Baseline crude death rate per 1000 per year, before food and disease effects. */
  deathRate: number;
  /** People housed per 100 m cell (one hectare) at full build-out. Present-day Seoul averages ~250. */
  cellCapacity: number;
  /** Typical building height in metres for the render kit. */
  buildingHeight: [number, number];
  /** Palette hint for the era's built fabric. */
  roofColor: number;
  wallColor: number;
  /** Road width in metres. */
  roadWidth: number;
  /** How far a person will routinely walk to work, metres. */
  commuteRange: number;
}

export const ERA_PROFILES: Record<Era, EraProfile> = {
  [Era.ThreeKingdoms]: {
    era: Era.ThreeKingdoms, name: '삼국시대', startYear: -18,
    farmYield: 1.15, urbanShare: 0.06, birthRate: 44, deathRate: 40,
    cellCapacity: 40, buildingHeight: [2.2, 3.2], roofColor: 0x9c8a63, wallColor: 0xa89878,
    roadWidth: 3, commuteRange: 900,
  },
  [Era.UnifiedSilla]: {
    era: Era.UnifiedSilla, name: '통일신라', startYear: 676,
    farmYield: 1.25, urbanShare: 0.09, birthRate: 43, deathRate: 38,
    cellCapacity: 50, buildingHeight: [2.6, 4.2], roofColor: 0x9a8760, wallColor: 0xb0a184,
    roadWidth: 4, commuteRange: 1100,
  },
  [Era.Goryeo]: {
    era: Era.Goryeo, name: '고려', startYear: 918,
    farmYield: 1.35, urbanShare: 0.12, birthRate: 43, deathRate: 37,
    cellCapacity: 60, buildingHeight: [2.8, 5.0], roofColor: 0x96835c, wallColor: 0xb6a68a,
    roadWidth: 5, commuteRange: 1300,
  },
  [Era.JoseonEarly]: {
    era: Era.JoseonEarly, name: '조선 전기', startYear: 1392,
    farmYield: 1.45, urbanShare: 0.16, birthRate: 42, deathRate: 36,
    cellCapacity: 80, buildingHeight: [3.0, 6.0], roofColor: 0x9c8a63, wallColor: 0xc8b89a,
    roadWidth: 6, commuteRange: 1600,
  },
  [Era.JoseonLate]: {
    era: Era.JoseonLate, name: '조선 후기', startYear: 1637,
    farmYield: 1.6, urbanShare: 0.2, birthRate: 41, deathRate: 34,
    cellCapacity: 115, buildingHeight: [3.0, 6.5], roofColor: 0x9a8760, wallColor: 0xccbc9e,
    roadWidth: 7, commuteRange: 1900,
  },
  [Era.Colonial]: {
    era: Era.Colonial, name: '개항·경성', startYear: 1896,
    farmYield: 2.2, urbanShare: 0.42, birthRate: 40, deathRate: 29,
    cellCapacity: 190, buildingHeight: [4.0, 16.0], roofColor: 0x6b4f43, wallColor: 0xb9a893,
    roadWidth: 10, commuteRange: 3500,
  },
  [Era.PostWar]: {
    era: Era.PostWar, name: '해방·전후 복구', startYear: 1945,
    farmYield: 3.0, urbanShare: 0.62, birthRate: 42, deathRate: 20,
    cellCapacity: 230, buildingHeight: [3.5, 14.0], roofColor: 0x7a6a5c, wallColor: 0xc2b6a6,
    roadWidth: 12, commuteRange: 5000,
  },
  [Era.Industrial]: {
    era: Era.Industrial, name: '산업화', startYear: 1963,
    farmYield: 6.0, urbanShare: 0.86, birthRate: 30, deathRate: 9,
    cellCapacity: 290, buildingHeight: [8.0, 45.0], roofColor: 0x8d8a86, wallColor: 0xd2cdc4,
    roadWidth: 20, commuteRange: 12000,
  },
  [Era.Modern]: {
    era: Era.Modern, name: '현대', startYear: 1988,
    farmYield: 20.0, urbanShare: 0.97, birthRate: 8, deathRate: 6,
    cellCapacity: 285, buildingHeight: [12.0, 120.0], roofColor: 0x9aa0a6, wallColor: 0xdfe3e8,
    roadWidth: 28, commuteRange: 20000,
  },
};

export function eraForYear(year: number): Era {
  let result = Era.ThreeKingdoms;
  for (const era of ALL_ERAS) {
    if (year >= ERA_PROFILES[era].startYear) result = era;
  }
  return result;
}

export function eraName(era: Era): string {
  return ERA_PROFILES[era].name;
}

/** Smooth 0..1 blend between an era and the next, so visuals do not pop on the transition year. */
export function eraBlend(year: number): { era: Era; next: Era; t: number } {
  const era = eraForYear(year);
  const idx = ALL_ERAS.indexOf(era);
  const next = ALL_ERAS[Math.min(idx + 1, ALL_ERAS.length - 1)]!;
  if (next === era) return { era, next, t: 0 };
  const span = ERA_PROFILES[next].startYear - ERA_PROFILES[era].startYear;
  const into = year - ERA_PROFILES[era].startYear;
  // Blend over the last quarter of the era.
  const t = Math.max(0, Math.min(1, (into / span - 0.75) * 4));
  return { era, next, t };
}
