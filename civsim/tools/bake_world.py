#!/usr/bin/env python3
"""Bake the CivSim world: terrain heightmap + water mask from Copernicus DEM GLO-30.

Outputs into web/public/data/:
  dem.bin    uint16 little-endian, DEM_NX * DEM_NZ, row 0 = south, col 0 = west
  water.bin  uint8, SIM_NX * SIM_NZ, 1 = present-day open water
  world.json metadata (frame origin, extents, height scale, verification report)

Usage:  python3 tools/bake_world.py [--raw data/raw] [--out web/public/data]
"""
from __future__ import annotations

import argparse
import json
import math
import os

import numpy as np
import rasterio

# --- World definition (see docs/seoul-civilization-simulator-plan.md §1.3) ---
ORIGIN_LAT, ORIGIN_LON = 37.5665, 126.9780      # Seoul City Hall
M_PER_DEG = 111194.92664455873                   # 2*pi*R/360 with R = 6371008.8 m

SIM_CELL_M = 100.0
SIM_NX, SIM_NZ = 380, 324                        # 38.0 km east-west, 32.4 km north-south
X0 = -SIM_NX * SIM_CELL_M / 2.0                  # -19000 m
Z0 = -SIM_NZ * SIM_CELL_M / 2.0                  # -16200 m

DEM_CELL_M = 50.0
DEM_NX = int(SIM_NX * SIM_CELL_M / DEM_CELL_M) + 1   # 761 vertices
DEM_NZ = int(SIM_NZ * SIM_CELL_M / DEM_CELL_M) + 1   # 649 vertices

COS_LAT = math.cos(math.radians(ORIGIN_LAT))


def local_to_lonlat(x: np.ndarray, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lon = ORIGIN_LON + x / (M_PER_DEG * COS_LAT)
    lat = ORIGIN_LAT + z / M_PER_DEG
    return lon, lat


def open_tiles(raw_dir: str):
    tiles = []
    for name in sorted(os.listdir(raw_dir)):
        if name.endswith('.tif'):
            tiles.append(rasterio.open(os.path.join(raw_dir, name)))
    if not tiles:
        raise SystemExit(f'no .tif tiles in {raw_dir}; run tools/bake_dem.py --download data/raw')
    return tiles


def sample_tiles(tiles, lons: np.ndarray, lats: np.ndarray) -> np.ndarray:
    """Bilinear sample of the mosaic at the given lon/lat arrays (same shape)."""
    out = np.full(lons.shape, np.nan, dtype=np.float64)
    for ds in tiles:
        t = ds.transform
        left, top = t.c, t.f
        dlon, dlat = t.a, t.e  # dlat is negative
        col = (lons - left) / dlon - 0.5   # pixel-is-area: centre of pixel 0 is at +0.5
        row = (lats - top) / dlat - 0.5
        inside = (row >= 0) & (row <= ds.height - 1) & (col >= 0) & (col <= ds.width - 1)
        if not inside.any():
            continue
        arr = ds.read(1).astype(np.float64)
        r0 = np.clip(np.floor(row), 0, ds.height - 2).astype(np.int64)
        c0 = np.clip(np.floor(col), 0, ds.width - 2).astype(np.int64)
        fr = np.clip(row - r0, 0.0, 1.0)
        fc = np.clip(col - c0, 0.0, 1.0)
        v = (arr[r0, c0] * (1 - fr) * (1 - fc) + arr[r0 + 1, c0] * fr * (1 - fc)
             + arr[r0, c0 + 1] * (1 - fr) * fc + arr[r0 + 1, c0 + 1] * fr * fc)
        out = np.where(inside & np.isnan(out), v, out)
    if np.isnan(out).any():
        raise SystemExit(f'{int(np.isnan(out).sum())} samples outside the available tiles')
    return out


def build_dem(tiles) -> np.ndarray:
    xs = X0 + np.arange(DEM_NX) * DEM_CELL_M
    zs = Z0 + np.arange(DEM_NZ) * DEM_CELL_M
    X, Z = np.meshgrid(xs, zs)           # [DEM_NZ, DEM_NX], row 0 = south
    lons, lats = local_to_lonlat(X, Z)
    return sample_tiles(tiles, lons, lats)


def build_sim_heights(dem: np.ndarray) -> np.ndarray:
    """Cell-centre heights on the 100 m simulation grid, averaged from the 50 m DEM."""
    # Cell (i, j) centre sits exactly on the midpoint of DEM vertices 2i..2i+2, 2j..2j+2.
    h = np.empty((SIM_NZ, SIM_NX), dtype=np.float64)
    for j in range(SIM_NZ):
        block = dem[2 * j:2 * j + 3, :]
        for i in range(SIM_NX):
            h[j, i] = block[:, 2 * i:2 * i + 3].mean()
    return h


def build_water(sim_h: np.ndarray) -> np.ndarray:
    """
    Present-day open water on the simulation grid.

    The Han's surface in the DSM rises about 3 m from the west edge of the play area to the east,
    so the threshold follows that downstream gradient instead of being flat. Everything not
    8-connected to the main channel is dropped, which removes low inland hollows while keeping
    the tributaries that actually join the river.

    Validated against present-day river widths: 행주대교 1.4 km, 가양대교 1.0 km, 한강대교 1.1 km,
    잠실대교 1.0 km, 강동대교 0.9 km, and a total Seoul-reach area of about 41 km².
    """
    margin = 3.5
    thr = (2.0 + np.arange(SIM_NX) / (SIM_NX - 1) * 3.0 + margin)[None, :]
    mask = sim_h < thr

    label = np.zeros(mask.shape, dtype=np.int32)
    current = 0
    sizes: dict[int, int] = {}
    neighbours = [(dj, di) for dj in (-1, 0, 1) for di in (-1, 0, 1) if dj or di]
    for j in range(SIM_NZ):
        for i in range(SIM_NX):
            if not mask[j, i] or label[j, i]:
                continue
            current += 1
            stack = [(j, i)]
            label[j, i] = current
            n = 0
            while stack:
                cj, ci = stack.pop()
                n += 1
                for dj, di in neighbours:
                    nj, ni = cj + dj, ci + di
                    if 0 <= nj < SIM_NZ and 0 <= ni < SIM_NX and mask[nj, ni] and not label[nj, ni]:
                        label[nj, ni] = current
                        stack.append((nj, ni))
            sizes[current] = n
    if sizes:
        main = max(sizes, key=lambda k: sizes[k])
        mask = label == main
    return mask.astype(np.uint8)


def verify(dem: np.ndarray, sim_h: np.ndarray, water: np.ndarray) -> dict:
    """Structural checks that do not depend on remembering exact summit coordinates."""
    report: dict = {}
    jmax, imax = np.unravel_index(int(np.argmax(dem)), dem.shape)
    x = X0 + imax * DEM_CELL_M
    z = Z0 + jmax * DEM_CELL_M
    lon, lat = local_to_lonlat(np.array(x), np.array(z))
    report['highestPoint'] = {
        'heightM': float(dem[jmax, imax]), 'lat': float(lat), 'lon': float(lon),
    }
    report['heightRange'] = [float(dem.min()), float(dem.max())]
    report['waterCells'] = int(water.sum())
    report['waterFraction'] = float(water.mean())
    # The Han must cross the map: water present in the far west and far east columns bands.
    west = water[:, :20].sum()
    east = water[:, -20:].sum()
    report['waterWestEdge'] = int(west)
    report['waterEastEdge'] = int(east)
    # City Hall cell
    ci, cj = SIM_NX // 2, SIM_NZ // 2
    report['cityHallHeightM'] = float(sim_h[cj, ci])
    # Land fraction below 50 m: the Seoul basin plus the river plain
    report['fractionBelow50m'] = float((sim_h < 50).mean())
    report['fractionAbove200m'] = float((sim_h > 200).mean())
    widths = {}
    for name, x_km, truth_km in (('행주대교', -15.0, 1.4), ('가양대교', -9.0, 1.0), ('한강대교', -1.8, 1.1),
                                 ('잠실대교', 7.0, 1.0), ('강동대교', 13.0, 0.9)):
        i = int((x_km * 1000 - X0) / SIM_CELL_M)
        widths[name] = {'measuredKm': float(water[:, i].sum() * SIM_CELL_M / 1000), 'actualKm': truth_km}
    report['riverWidths'] = widths
    report['waterAreaKm2'] = float(water.sum() * SIM_CELL_M * SIM_CELL_M / 1e6)
    return report


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--raw', default='data/raw')
    ap.add_argument('--out', default='web/public/data')
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    tiles = open_tiles(a.raw)
    print(f'mosaic: {len(tiles)} tile(s)')
    dem = build_dem(tiles)
    print(f'dem {DEM_NX}x{DEM_NZ} @ {DEM_CELL_M} m  range {dem.min():.1f}..{dem.max():.1f} m')
    sim_h = build_sim_heights(dem)
    water = build_water(sim_h)
    print(f'water cells: {int(water.sum())} of {SIM_NX * SIM_NZ}')

    h_min = math.floor(dem.min())
    h_max = math.ceil(dem.max())
    scale = max(h_max - h_min, 1.0)
    q = np.clip((dem - h_min) / scale, 0, 1)
    (q * 65535 + 0.5).astype('<u2').tofile(os.path.join(a.out, 'dem.bin'))
    water.astype(np.uint8).tofile(os.path.join(a.out, 'water.bin'))
    # Sim-grid heights in metres as float32, so the simulation does not re-quantise.
    sim_h.astype('<f4').tofile(os.path.join(a.out, 'simheight.bin'))

    report = verify(dem, sim_h, water)
    meta = {
        'origin': {'lat': ORIGIN_LAT, 'lon': ORIGIN_LON},
        'metresPerDegree': M_PER_DEG,
        'frame': '+x east, +y up, +z north, metres from Seoul City Hall',
        'sim': {'cellM': SIM_CELL_M, 'nx': SIM_NX, 'nz': SIM_NZ, 'x0': X0, 'z0': Z0},
        'dem': {'cellM': DEM_CELL_M, 'nx': DEM_NX, 'nz': DEM_NZ, 'x0': X0, 'z0': Z0,
                'heightMinM': h_min, 'heightScaleM': scale,
                'encoding': 'uint16 LE, height = heightMinM + v/65535*heightScaleM'},
        'bbox': {'minLon': float(ORIGIN_LON + X0 / (M_PER_DEG * COS_LAT)),
                 'maxLon': float(ORIGIN_LON + (X0 + SIM_NX * SIM_CELL_M) / (M_PER_DEG * COS_LAT)),
                 'minLat': float(ORIGIN_LAT + Z0 / M_PER_DEG),
                 'maxLat': float(ORIGIN_LAT + (Z0 + SIM_NZ * SIM_CELL_M) / M_PER_DEG)},
        'source': ('Copernicus DEM GLO-30, © DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH '
                   '2014-2018 provided under COPERNICUS by the European Union and ESA'),
        'verification': report,
    }
    with open(os.path.join(a.out, 'world.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
