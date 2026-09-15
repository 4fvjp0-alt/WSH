/** Polities. Wars are represented statistically: territory, population and buildings change, armies do not appear. */

export interface Polity {
  id: number;
  name: string;
  shortName: string;
  fromYear: number;
  toYear: number;
  color: number;
  /** Where its capital sits, if it is in the play area. */
  capitalPlace?: 'pungnap' | 'cityHall' | 'mongchon';
}

export const POLITY_TIMELINE: Polity[] = [
  { id: 0, name: '한성백제', shortName: '백제', fromYear: -18, toYear: 475, color: 0x3f7f5f, capitalPlace: 'pungnap' },
  { id: 1, name: '고구려 남부', shortName: '고구려', fromYear: 475, toYear: 553, color: 0x7a4b3a, capitalPlace: 'mongchon' },
  { id: 2, name: '신라 신주', shortName: '신라', fromYear: 553, toYear: 676, color: 0x6b5ea8 },
  { id: 3, name: '통일신라 한양군', shortName: '통일신라', fromYear: 676, toYear: 918, color: 0x5a6fa8, capitalPlace: 'cityHall' },
  { id: 4, name: '고려 남경', shortName: '고려', fromYear: 918, toYear: 1392, color: 0x2f6f8f, capitalPlace: 'cityHall' },
  { id: 5, name: '조선 한성부', shortName: '조선', fromYear: 1392, toYear: 1897, color: 0x8a1f2d, capitalPlace: 'cityHall' },
  { id: 6, name: '대한제국 한성부', shortName: '대한제국', fromYear: 1897, toYear: 1910, color: 0x9a3b2a, capitalPlace: 'cityHall' },
  { id: 7, name: '경성부', shortName: '경성부', fromYear: 1910, toYear: 1945, color: 0x6a6a6a, capitalPlace: 'cityHall' },
  { id: 8, name: '대한민국 서울특별시', shortName: '서울', fromYear: 1945, toYear: 9999, color: 0x1f5fa8, capitalPlace: 'cityHall' },
];

export function polityForYear(year: number): Polity {
  let found = POLITY_TIMELINE[0]!;
  for (const p of POLITY_TIMELINE) {
    if (year >= p.fromYear) found = p;
  }
  return found;
}
