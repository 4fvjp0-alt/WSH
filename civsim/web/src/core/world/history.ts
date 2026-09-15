/**
 * The historical record the simulation is measured against and, in "재현" (reproduction) mode, steered by.
 * Coordinates are real; population figures are the conventional estimates for the Seoul area.
 */
import { lonLatToLocal } from '../geo/localFrame.ts';

export interface PopulationAnchor {
  year: number;
  population: number;
  note: string;
}

/**
 * Population of the Seoul area. Pre-modern numbers are estimates from 호구 registers and
 * archaeology; from 1925 they are census figures for the city as then bounded.
 */
export const POPULATION_CURVE: PopulationAnchor[] = [
  { year: 100, population: 12000, note: '한강변 촌락' },
  { year: 250, population: 28000, note: '한성백제 성장' },
  { year: 400, population: 42000, note: '한성백제 전성' },
  { year: 475, population: 30000, note: '고구려의 한성 함락' },
  { year: 600, population: 22000, note: '신라 한산주' },
  { year: 757, population: 25000, note: '한양군' },
  { year: 1000, population: 26000, note: '고려 양주' },
  { year: 1104, population: 35000, note: '남경 궁궐' },
  { year: 1300, population: 40000, note: '남경' },
  { year: 1394, population: 50000, note: '한양 천도' },
  { year: 1428, population: 103000, note: '세종조 한성부 호구' },
  { year: 1550, population: 95000, note: '조선 전기 안정' },
  { year: 1600, population: 70000, note: '임진왜란 직후' },
  { year: 1669, population: 194000, note: '현종조 한성부 호구' },
  { year: 1750, population: 190000, note: '영조조' },
  { year: 1850, population: 200000, note: '조선 후기' },
  { year: 1900, population: 200000, note: '대한제국' },
  { year: 1925, population: 342000, note: '경성부 국세조사' },
  { year: 1936, population: 677000, note: '경성부 확장' },
  { year: 1942, population: 1114000, note: '전시 경성' },
  { year: 1945, population: 900000, note: '광복' },
  { year: 1949, population: 1440000, note: '귀환·월남 인구' },
  { year: 1951, population: 650000, note: '한국전쟁 피난' },
  { year: 1955, population: 1575000, note: '환도 후 복귀' },
  { year: 1960, population: 2445000, note: '전후 도시화' },
  { year: 1966, population: 3805000, note: '이촌향도' },
  { year: 1970, population: 5433000, note: '고도성장' },
  { year: 1975, population: 6890000, note: '강남 개발' },
  { year: 1980, population: 8364000, note: '' },
  { year: 1985, population: 9639000, note: '' },
  { year: 1990, population: 10613000, note: '정점' },
  { year: 1995, population: 10231000, note: '수도권 분산' },
  { year: 2000, population: 9895000, note: '' },
  { year: 2010, population: 9794000, note: '' },
  { year: 2020, population: 9668000, note: '' },
  { year: 2026, population: 9300000, note: '현재' },
];

/** Log-linear interpolation of the reference curve; population grows multiplicatively. */
export function referencePopulation(year: number): number {
  const c = POPULATION_CURVE;
  if (year <= c[0]!.year) return c[0]!.population;
  if (year >= c[c.length - 1]!.year) return c[c.length - 1]!.population;
  for (let i = 1; i < c.length; i++) {
    const b = c[i]!;
    if (year <= b.year) {
      const a = c[i - 1]!;
      const t = (year - a.year) / (b.year - a.year);
      return Math.exp(Math.log(a.population) * (1 - t) + Math.log(b.population) * t);
    }
  }
  return c[c.length - 1]!.population;
}

export type AnchorKind =
  | 'found'      // a settlement is seeded
  | 'capital'    // the capital moves
  | 'wall'       // fortification is built
  | 'palace'     // a monumental complex is built
  | 'war'        // destruction and population loss (statistics only)
  | 'disaster'   // flood, plague, fire
  | 'landfill'   // the river is reshaped
  | 'infra'      // roads, rail, bridges, subway
  | 'boundary'   // the administrative area changes
  | 'era';       // an era label change

export interface AnchorEvent {
  year: number;
  /** Month, for events where the season matters on screen. */
  month?: number;
  kind: AnchorKind;
  title: string;
  detail: string;
  /** Where it happens, in real coordinates. */
  lat?: number;
  lon?: number;
  /** Multiplier applied to population when the event fires (wars, plagues). */
  populationFactor?: number;
  /** Radius in metres over which built-up cells are damaged. */
  destructionRadiusM?: number;
  /** Fraction of buildings destroyed inside the radius. */
  destructionFraction?: number;
  /** Opens new land for settlement (administrative expansion, landfill). */
  opensLand?: boolean;
  /** Name the settlement takes on, for capital moves and renamings. */
  settlementName?: string;
}

/** Real coordinates of the places the anchors refer to. */
export const PLACES = {
  pungnap: { lat: 37.5378, lon: 127.1157, name: '풍납토성' },
  mongchon: { lat: 37.5175, lon: 127.1122, name: '몽촌토성' },
  achasan: { lat: 37.5545, lon: 127.1015, name: '아차산' },
  gyeongbok: { lat: 37.5796, lon: 126.977, name: '경복궁' },
  changdeok: { lat: 37.5794, lon: 126.991, name: '창덕궁' },
  jongmyo: { lat: 37.5744, lon: 126.994, name: '종묘' },
  sungnyemun: { lat: 37.5599, lon: 126.9752, name: '숭례문' },
  heunginjimun: { lat: 37.571, lon: 127.0095, name: '흥인지문' },
  namsan: { lat: 37.5512, lon: 126.9882, name: '남산' },
  bukhansan: { lat: 37.6586, lon: 126.9797, name: '북한산' },
  inwangsan: { lat: 37.5817, lon: 126.9583, name: '인왕산' },
  cityHall: { lat: 37.5665, lon: 126.978, name: '서울 도심' },
  seoulStation: { lat: 37.5547, lon: 126.9707, name: '서울역' },
  yeouido: { lat: 37.5216, lon: 126.9241, name: '여의도' },
  jamsil: { lat: 37.5133, lon: 127.1, name: '잠실' },
  gangnam: { lat: 37.4979, lon: 127.0276, name: '강남' },
  mapo: { lat: 37.545, lon: 126.945, name: '마포나루' },
  noryangjin: { lat: 37.5133, lon: 126.9425, name: '노량진' },
  ttukseom: { lat: 37.53, lon: 127.07, name: '뚝섬' },
  yangcheon: { lat: 37.5266, lon: 126.8556, name: '양천' },
} as const;

export const ANCHOR_EVENTS: AnchorEvent[] = [
  { year: 100, kind: 'found', title: '한강변 촌락', detail: '강변 충적지에 마을이 자리잡는다.', ...PLACES.pungnap },
  { year: 132, kind: 'found', title: '위례 취락 확대', detail: '남한산 기슭으로 취락이 퍼진다.', ...PLACES.mongchon },
  { year: 250, kind: 'wall', title: '풍납토성 축조', detail: '판축 기법의 토성이 강변을 둘러싼다.', ...PLACES.pungnap },
  { year: 286, kind: 'wall', title: '몽촌토성 축조', detail: '배후 방어 토성이 세워진다.', ...PLACES.mongchon },
  { year: 371, kind: 'capital', title: '한성 도읍', detail: '백제가 한성을 도읍으로 삼는다.', settlementName: '한성', ...PLACES.pungnap },
  {
    year: 475, month: 9, kind: 'war', title: '고구려의 한성 함락',
    detail: '개로왕이 전사하고 백제는 웅진으로 천도한다.',
    populationFactor: 0.62, destructionRadiusM: 3000, destructionFraction: 0.65, ...PLACES.pungnap,
  },
  { year: 481, kind: 'wall', title: '아차산 보루', detail: '고구려가 능선에 보루를 쌓는다.', ...PLACES.achasan },
  { year: 553, kind: 'capital', title: '신라의 한강 유역 장악', detail: '신주가 설치된다.', settlementName: '한산주', ...PLACES.mongchon },
  { year: 757, kind: 'capital', title: '한양군', detail: '통일신라의 지방 행정 중심이 된다.', settlementName: '한양', ...PLACES.cityHall },
  { year: 1067, kind: 'capital', title: '고려 남경', detail: '양주가 남경으로 승격된다.', settlementName: '남경', ...PLACES.cityHall },
  { year: 1104, kind: 'palace', title: '남경 궁궐', detail: '숙종이 남경에 궁궐을 짓는다.', ...PLACES.gyeongbok },
  {
    year: 1231, kind: 'war', title: '몽골 침입', detail: '전란으로 인구가 흩어진다.',
    populationFactor: 0.82, destructionRadiusM: 2500, destructionFraction: 0.3, ...PLACES.cityHall,
  },
  { year: 1394, month: 10, kind: 'capital', title: '한양 천도', detail: '조선이 한양을 도읍으로 정한다.', settlementName: '한양', ...PLACES.cityHall },
  { year: 1395, month: 9, kind: 'palace', title: '경복궁 창건', detail: '법궁이 북악 아래 들어선다.', ...PLACES.gyeongbok },
  { year: 1395, month: 9, kind: 'palace', title: '종묘 창건', detail: '왕실의 사당이 세워진다.', ...PLACES.jongmyo },
  { year: 1396, month: 1, kind: 'wall', title: '한양도성 축조', detail: '내사산 능선을 따라 성곽이 이어진다.', ...PLACES.cityHall },
  { year: 1398, kind: 'palace', title: '숭례문 준공', detail: '도성의 남문이 완성된다.', ...PLACES.sungnyemun },
  { year: 1405, kind: 'palace', title: '창덕궁 창건', detail: '이궁이 들어선다.', ...PLACES.changdeok },
  { year: 1412, kind: 'infra', title: '청계천 개천 공사', detail: '도심 하천을 준설하고 다리를 놓는다.', ...PLACES.cityHall },
  {
    year: 1592, month: 5, kind: 'war', title: '임진왜란', detail: '경복궁과 도성 대부분이 불탄다.',
    populationFactor: 0.45, destructionRadiusM: 4000, destructionFraction: 0.75, ...PLACES.cityHall,
  },
  {
    year: 1636, month: 12, kind: 'war', title: '병자호란', detail: '다시 전란이 도성을 스친다.',
    populationFactor: 0.82, destructionRadiusM: 3000, destructionFraction: 0.25, ...PLACES.cityHall,
  },
  { year: 1760, kind: 'infra', title: '청계천 준설', detail: '영조가 개천을 대대적으로 친다.', ...PLACES.cityHall },
  { year: 1876, kind: 'era', title: '개항', detail: '조선이 문을 연다.', ...PLACES.cityHall },
  { year: 1896, month: 1, kind: 'era', title: '양력 채택', detail: '달력이 태양력으로 바뀐다.', ...PLACES.cityHall },
  { year: 1899, kind: 'infra', title: '전차 개통', detail: '서대문에서 청량리까지 전차가 다닌다.', ...PLACES.cityHall },
  { year: 1900, kind: 'infra', title: '한강철교', detail: '한강을 건너는 첫 철교가 놓인다.', ...PLACES.noryangjin },
  { year: 1910, kind: 'boundary', title: '경성부', detail: '한성부가 경성부로 바뀐다.', ...PLACES.cityHall, opensLand: true },
  {
    year: 1925, month: 7, kind: 'disaster', title: '을축년 대홍수', detail: '한강이 넘쳐 저지대가 잠긴다.',
    populationFactor: 0.97, destructionRadiusM: 6000, destructionFraction: 0.2, ...PLACES.ttukseom,
  },
  { year: 1936, kind: 'boundary', title: '경성부 확장', detail: '영등포가 편입된다.', ...PLACES.noryangjin, opensLand: true },
  { year: 1945, month: 8, kind: 'capital', title: '광복', detail: '해방과 함께 귀환 인구가 몰리고, 도시는 서울이라는 이름을 얻는다.', settlementName: '서울', ...PLACES.cityHall },
  {
    year: 1950, month: 6, kind: 'war', title: '한국전쟁', detail: '서울이 네 차례 주인이 바뀐다.',
    populationFactor: 0.42, destructionRadiusM: 7000, destructionFraction: 0.55, ...PLACES.cityHall,
  },
  { year: 1953, month: 7, kind: 'era', title: '환도', detail: '피난민이 돌아오고 복구가 시작된다.', ...PLACES.cityHall },
  { year: 1963, month: 1, kind: 'boundary', title: '행정구역 대확장', detail: '강남 일대가 서울에 편입된다.', ...PLACES.gangnam, opensLand: true },
  { year: 1968, kind: 'landfill', title: '여의도 개발', detail: '밤섬을 폭파하고 윤중제를 쌓는다.', ...PLACES.yeouido, opensLand: true },
  { year: 1970, kind: 'infra', title: '경부고속도로', detail: '남쪽으로 고속도로가 열린다.', ...PLACES.gangnam },
  { year: 1971, kind: 'landfill', title: '잠실 매립', detail: '잠실섬과 북쪽 물길을 메운다.', ...PLACES.jamsil, opensLand: true },
  { year: 1974, month: 8, kind: 'infra', title: '지하철 1호선', detail: '서울역에서 청량리까지 지하철이 달린다.', ...PLACES.seoulStation },
  { year: 1982, kind: 'landfill', title: '한강종합개발', detail: '강을 직강화하고 둔치를 만든다.', ...PLACES.yeouido },
  { year: 1988, month: 9, kind: 'era', title: '서울올림픽', detail: '잠실에서 올림픽이 열린다.', ...PLACES.jamsil },
  { year: 1997, month: 12, kind: 'disaster', title: '외환위기', detail: '건설이 멈추고 인구가 빠진다.', populationFactor: 0.99, ...PLACES.cityHall },
  { year: 2005, month: 10, kind: 'infra', title: '청계천 복원', detail: '복개 도로를 걷어내고 물길을 되살린다.', ...PLACES.cityHall },
  { year: 2017, month: 4, kind: 'palace', title: '롯데월드타워', detail: '555 m 초고층이 잠실에 선다.', ...PLACES.jamsil },
];

export interface ResolvedAnchor extends AnchorEvent {
  /** Local frame position, metres. */
  x: number;
  z: number;
  /** Decimal year the event fires. */
  fireYear: number;
}

export const RESOLVED_ANCHORS: ResolvedAnchor[] = ANCHOR_EVENTS.map((e) => {
  const p = e.lat !== undefined && e.lon !== undefined ? lonLatToLocal(e.lon, e.lat) : { x: 0, z: 0 };
  return { ...e, x: p.x, z: p.z, fireYear: e.year + ((e.month ?? 1) - 0.5) / 12 };
}).sort((a, b) => a.fireYear - b.fireYear);
