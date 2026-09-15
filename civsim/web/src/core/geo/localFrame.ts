/**
 * Flat metric frame centred on Seoul City Hall: +X east, +Z north, metres.
 * Equirectangular approximation; across the 38 x 32 km play area the error stays under a few metres,
 * far below the 100 m simulation cell.
 */
export const ORIGIN_LAT = 37.5665;
export const ORIGIN_LON = 126.978;
export const M_PER_DEG = 111194.92664455873; // 2*pi*R/360, R = 6371008.8 m

const COS_LAT = Math.cos((ORIGIN_LAT * Math.PI) / 180);

export function lonLatToLocal(lon: number, lat: number): { x: number; z: number } {
  return { x: (lon - ORIGIN_LON) * M_PER_DEG * COS_LAT, z: (lat - ORIGIN_LAT) * M_PER_DEG };
}

export function localToLonLat(x: number, z: number): { lon: number; lat: number } {
  return { lon: ORIGIN_LON + x / (M_PER_DEG * COS_LAT), lat: ORIGIN_LAT + z / M_PER_DEG };
}

export function formatLonLat(lon: number, lat: number): string {
  const ns = lat >= 0 ? 'N' : 'S';
  const ew = lon >= 0 ? 'E' : 'W';
  return `${Math.abs(lat).toFixed(4)}°${ns} ${Math.abs(lon).toFixed(4)}°${ew}`;
}
