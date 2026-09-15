#!/usr/bin/env python3
"""Bake a Seoul heightmap for the Unity terrain from Copernicus DEM GLO-30 tiles.

Output: a 16-bit little-endian RAW (.r16, Unity Terrain import format) plus a PNG preview and a
JSON sidecar with the local-frame origin, extent and vertical scale.

Usage
-----
  # 1. download the two 1°×1° tiles covering Seoul (public AWS bucket, no login):
  python3 tools/bake_dem.py --download data/raw
  # 2. bake at 30 m per sample:
  python3 tools/bake_dem.py --tiles data/raw --out data/baked/seoul --res 30
  # or, without any data, generate a synthetic Han-river valley to unblock engine work:
  python3 tools/bake_dem.py --synthetic --out data/baked/seoul_synthetic --res 30

Requires numpy + pillow. GeoTIFF tiles are read with rasterio when installed, otherwise via pillow
(works for the AWS COG tiles).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import urllib.request

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

# Play area (plan §1.3) and local frame origin (Seoul City Hall)
MIN_LON, MAX_LON, MIN_LAT, MAX_LAT = 126.76, 127.19, 37.42, 37.71
ORIGIN_LAT, ORIGIN_LON = 37.5665, 126.9780
EARTH_R = 6371008.8

TILE_URL = ("https://copernicus-dem-30m.s3.amazonaws.com/"
            "Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM/"
            "Copernicus_DSM_COG_10_N{lat:02d}_00_E{lon:03d}_00_DEM.tif")


def tiles_needed():
    lats = range(math.floor(MIN_LAT), math.ceil(MAX_LAT))
    lons = range(math.floor(MIN_LON), math.ceil(MAX_LON))
    return [(la, lo) for la in lats for lo in lons]


def download(dst: str):
    os.makedirs(dst, exist_ok=True)
    for la, lo in tiles_needed():
        url = TILE_URL.format(lat=la, lon=lo)
        path = os.path.join(dst, os.path.basename(url))
        if os.path.exists(path):
            print("exists", path)
            continue
        print("downloading", url)
        urllib.request.urlretrieve(url, path)
    print("done")


def read_tile(path: str) -> tuple[np.ndarray, float, float, float, float]:
    """Return (array[rows, cols], top_lat, left_lon, dlat, dlon) with dlat negative (north-up)."""
    try:
        import rasterio  # type: ignore
        with rasterio.open(path) as ds:
            arr = ds.read(1).astype(np.float32)
            t = ds.transform
            return arr, t.f, t.c, t.e, t.a
    except ImportError:
        pass
    img = Image.open(path)
    arr = np.asarray(img, dtype=np.float32)
    name = os.path.basename(path)
    # Copernicus naming: ..._N37_00_E126_00_DEM.tif  → tile spans lat 37..38, lon 126..127
    la = int(name.split("_N")[1][:2])
    lo = int(name.split("_E")[1][:3])
    rows, cols = arr.shape
    # GLO-30 pixel-is-point grid: the tile's first row is at lat+1, last row at lat exactly.
    dlat = -1.0 / (rows - 1) if rows > 1 else -1.0
    dlon = 1.0 / (cols - 1) if cols > 1 else 1.0
    return arr, la + 1.0, float(lo), dlat, dlon


def local_grid(res_m: float):
    k = EARTH_R * math.pi / 180.0
    cos_lat = math.cos(math.radians(ORIGIN_LAT))
    x0 = (MIN_LON - ORIGIN_LON) * k * cos_lat
    x1 = (MAX_LON - ORIGIN_LON) * k * cos_lat
    z0 = (MIN_LAT - ORIGIN_LAT) * k
    z1 = (MAX_LAT - ORIGIN_LAT) * k
    nx = int(math.ceil((x1 - x0) / res_m)) + 1
    nz = int(math.ceil((z1 - z0) / res_m)) + 1
    xs = x0 + np.arange(nx) * res_m
    zs = z0 + np.arange(nz) * res_m
    lons = ORIGIN_LON + xs / (k * cos_lat)
    lats = ORIGIN_LAT + zs / k
    return xs, zs, lons, lats


def sample_bilinear(arr, top_lat, left_lon, dlat, dlon, lats, lons):
    rows, cols = arr.shape
    r = (lats[:, None] - top_lat) / dlat          # [nz, 1]
    c = (lons[None, :] - left_lon) / dlon          # [1, nx]
    r = np.broadcast_to(r, (len(lats), len(lons)))
    c = np.broadcast_to(c, (len(lats), len(lons)))
    inside = (r >= 0) & (r <= rows - 1) & (c >= 0) & (c <= cols - 1)
    r0 = np.clip(np.floor(r).astype(int), 0, rows - 2)
    c0 = np.clip(np.floor(c).astype(int), 0, cols - 2)
    fr = np.clip(r - r0, 0, 1)
    fc = np.clip(c - c0, 0, 1)
    v = (arr[r0, c0] * (1 - fr) * (1 - fc) + arr[r0 + 1, c0] * fr * (1 - fc)
         + arr[r0, c0 + 1] * (1 - fr) * fc + arr[r0 + 1, c0 + 1] * fr * fc)
    return np.where(inside, v, np.nan)


def bake_from_tiles(tile_dir: str, res_m: float) -> np.ndarray:
    xs, zs, lons, lats = local_grid(res_m)
    out = np.full((len(zs), len(xs)), np.nan, dtype=np.float32)
    files = [os.path.join(tile_dir, f) for f in os.listdir(tile_dir) if f.lower().endswith(".tif")]
    if not files:
        sys.exit(f"no .tif tiles in {tile_dir}; run --download first")
    for f in files:
        arr, top, left, dlat, dlon = read_tile(f)
        v = sample_bilinear(arr, top, left, dlat, dlon, lats, lons)
        out = np.where(np.isnan(out), v, out)
    if np.isnan(out).any():
        print(f"warning: {int(np.isnan(out).sum())} samples not covered by tiles, filled with 0", file=sys.stderr)
        out = np.nan_to_num(out, nan=0.0)
    return out  # row 0 = south edge (z0); Unity RAW wants row 0 at the bottom, handled at write time


def synthetic(res_m: float) -> np.ndarray:
    """A plausible stand-in: Han river S-curve, Bukhansan (N), Namsan (centre), Gwanaksan (S)."""
    xs, zs, _, _ = local_grid(res_m)
    X, Z = np.meshgrid(xs, zs)
    h = 25 + 0.0006 * np.abs(Z) + 8 * np.sin(X / 1300) * np.cos(Z / 1700)
    river_z = -3500 + 1800 * np.sin(X / 6000) + 600 * np.sin(X / 2100)
    d = np.abs(Z - river_z)
    h = np.where(d < 500, 5 + 3 * (d / 500), h)
    for cx, cz, height, radius in [(-3500, 10500, 830, 3500), (0, 500, 270, 900), (-4000, -14000, 630, 3000),
                                   (9000, 7000, 480, 2000), (-11000, -6000, 330, 1800), (7000, -9000, 400, 1600)]:
        r2 = ((X - cx) ** 2 + (Z - cz) ** 2) / radius ** 2
        h = h + height * np.exp(-r2 * 1.5)
    rng = np.random.default_rng(7)
    h += rng.normal(0, 1.5, h.shape)
    return h.astype(np.float32)


def write_outputs(h: np.ndarray, out_prefix: str, res_m: float):
    os.makedirs(os.path.dirname(out_prefix) or ".", exist_ok=True)
    hmin, hmax = float(np.floor(h.min())), float(np.ceil(h.max()))
    scale = max(hmax - hmin, 1.0)
    q = np.clip((h - hmin) / scale, 0, 1)
    u16 = (q * 65535.0 + 0.5).astype("<u2")
    # Unity RAW import: bottom-to-top rows are expected when "Flip Vertically" is off; our row 0 is south. Keep as is.
    u16.tofile(out_prefix + ".r16")
    Image.fromarray(np.flipud(u16)).save(out_prefix + ".png")
    xs, zs, _, _ = local_grid(res_m)
    meta = {
        "origin": {"lat": ORIGIN_LAT, "lon": ORIGIN_LON, "frame": "east=x, north=z, metres"},
        "bbox": {"minLon": MIN_LON, "maxLon": MAX_LON, "minLat": MIN_LAT, "maxLat": MAX_LAT},
        "resolutionM": res_m,
        "width": int(h.shape[1]), "height": int(h.shape[0]),
        "localMinX": float(xs[0]), "localMinZ": float(zs[0]),
        "extentX": float(xs[-1] - xs[0]), "extentZ": float(zs[-1] - zs[0]),
        "heightMinM": hmin, "heightMaxM": hmax, "heightScaleM": scale,
        "rawFormat": "uint16 little-endian, row 0 = south edge, column 0 = west edge",
        "source": "Copernicus DEM GLO-30 (© DLR e.V. 2010-2014 and © Airbus Defence and Space GmbH 2014-2018, ESA licence)",
    }
    with open(out_prefix + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    print(f"wrote {out_prefix}.r16/.png/.json  {h.shape[1]}x{h.shape[0]} @ {res_m} m, heights {hmin}..{hmax} m")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--download", metavar="DIR", help="download the Copernicus tiles into DIR and exit")
    p.add_argument("--tiles", metavar="DIR", help="directory with the downloaded .tif tiles")
    p.add_argument("--synthetic", action="store_true", help="generate a synthetic Seoul-like terrain instead")
    p.add_argument("--out", default="data/baked/seoul", help="output prefix (no extension)")
    p.add_argument("--res", type=float, default=30.0, help="metres per sample")
    a = p.parse_args()
    if a.download:
        download(a.download)
        return
    if a.synthetic:
        h = synthetic(a.res)
    elif a.tiles:
        h = bake_from_tiles(a.tiles, a.res)
    else:
        p.error("one of --download, --tiles or --synthetic is required")
    write_outputs(h, a.out, a.res)


if __name__ == "__main__":
    main()
