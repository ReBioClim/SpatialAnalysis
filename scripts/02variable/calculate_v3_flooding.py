"""Calculate a HAND-based flood susceptibility proxy.

Reference: Nobre et al. (2016).
"""

from pathlib import Path

import geopandas as gpd
import numpy as np
import numba
import pandas as pd
import rasterio
from rasterio.features import geometry_mask, rasterize
from rasterio.windows import from_bounds


# pysheds ships cached numba functions that fail in some python environments
_njit = numba.njit


def _uncached_njit(*args, **kwargs):
    kwargs["cache"] = False
    return _njit(*args, **kwargs)


numba.njit = _uncached_njit
from pysheds.grid import Grid


dem_path = "data/prepared/DTM_30m.tif"
segments_path = "data/stream_segments/streams_03_segments_200m.gpkg"
network_path = "data/stream_geometry/streams_02_network.gpkg"
output_path = "data/production/variables/v3_flooding.gpkg"
buffer_m = 100.0
dem_pad_m = 10000.0


@numba.njit
def route_to_stream(flow_dir, stream_mask, elevation, valid, codes):
    """route each cell to its first stream cell and return routed hand."""
    rows, cols = flow_dir.shape
    hand = np.full((rows, cols), np.nan, dtype=np.float32)
    state = np.zeros((rows, cols), dtype=np.uint8)
    dr = np.array([0, 0, 1, 1, 1, 0, -1, -1, -1])
    dc = np.array([0, 1, 1, 0, -1, -1, -1, 0, 1])
    for r in range(rows):
        for c in range(cols):
            if not valid[r, c]:
                continue
            if stream_mask[r, c]:
                hand[r, c] = 0.0
                state[r, c] = 2
                continue
            if state[r, c] == 2:
                continue
            path_r = np.empty(rows + cols, dtype=np.int64)
            path_c = np.empty(rows + cols, dtype=np.int64)
            length = 0
            cr, cc = r, c
            base = np.nan
            while True:
                if not valid[cr, cc]:
                    break
                if state[cr, cc] == 2:
                    base = elevation[cr, cc] + hand[cr, cc]
                    break
                if stream_mask[cr, cc]:
                    base = elevation[cr, cc]
                    break
                if state[cr, cc] == 1 or length >= path_r.size:
                    break
                state[cr, cc] = 1
                path_r[length] = cr
                path_c[length] = cc
                length += 1
                code = int(flow_dir[cr, cc])
                direction = -1
                for k in range(1, 9):
                    if codes[k - 1] == code:
                        direction = k
                        break
                if direction < 0:
                    break
                nr, nc = cr + dr[direction], cc + dc[direction]
                if nr < 0 or nr >= rows or nc < 0 or nc >= cols:
                    break
                cr, cc = nr, nc
            if np.isfinite(base):
                for k in range(length):
                    pr, pc = path_r[k], path_c[k]
                    hand[pr, pc] = elevation[pr, pc] - base
                    state[pr, pc] = 2
            else:
                for k in range(length):
                    state[path_r[k], path_c[k]] = 0
    return hand


def city_surface(city, segments, network, dem_src):
    city_segments = segments[segments["city"] == city].copy()
    city_network = network[network["city"] == city]
    bounds = city_segments.total_bounds
    padded = (bounds[0] - dem_pad_m, bounds[1] - dem_pad_m,
              bounds[2] + dem_pad_m, bounds[3] + dem_pad_m)
    window = from_bounds(*padded, dem_src.transform).round_offsets().round_lengths()
    dem_raw = dem_src.read(1, window=window).astype("float64")
    transform = dem_src.window_transform(window)
    valid = np.isfinite(dem_raw)
    if not valid.any():
        raise ValueError(f"no valid dem cells for {city}")

    profile = dem_src.profile.copy()
    profile.update(height=dem_raw.shape[0], width=dem_raw.shape[1], transform=transform,
                   nodata=-9999)
    temp = Path("data/production/variables") / f"_hand_{city.lower()}.tif"
    with rasterio.open(temp, "w", **profile) as dst:
        dst.write(np.where(valid, dem_raw, -9999).astype("float32"), 1)
    grid = Grid.from_raster(str(temp), data_name="dem")
    dem = grid.read_raster(str(temp))
    dem = grid.fill_depressions(dem)
    dem = grid.resolve_flats(dem)
    flow_dir = np.asarray(grid.flowdir(dem))
    stream_mask = rasterize(
        [(geom, 1) for geom in city_network.geometry],
        out_shape=dem_raw.shape, transform=transform, fill=0, dtype="uint8"
    ).astype(bool)
    hand = route_to_stream(
        flow_dir, stream_mask, dem_raw, valid,
        np.array([1, 2, 4, 8, 16, 32, 64, 128], dtype=np.int64),
    )
    temp.unlink(missing_ok=True)

    valid_hand = valid & np.isfinite(hand) & (hand >= 0)
    out = city_segments[["segment200_id", "geometry"]].copy()
    for name in ["hand_mean", "hand_median", "hand_p10", "hand_p90",
                 "hand_1m_cover", "hand_2m_cover", "hand_3m_cover"]:
        out[name] = np.nan
    for idx, geom in out.geometry.items():
        mask = geometry_mask([geom.buffer(buffer_m)], out_shape=hand.shape,
                             transform=transform, invert=True)
        values = hand[mask & valid_hand]
        if values.size:
            out.at[idx, "hand_mean"] = float(np.mean(values))
            out.at[idx, "hand_median"] = float(np.median(values))
            out.at[idx, "hand_p10"] = float(np.percentile(values, 10))
            out.at[idx, "hand_p90"] = float(np.percentile(values, 90))
            for threshold in [1, 2, 3]:
                out.at[idx, f"hand_{threshold}m_cover"] = float(np.mean(values <= threshold))
    out["flood_susceptibility"] = out["hand_2m_cover"]
    return out


def main():
    segments = gpd.read_file(segments_path)
    network = gpd.read_file(network_path)
    with rasterio.open(dem_path) as dem_src:
        pieces = [city_surface(city, segments, network, dem_src)
                  for city in ["Dresden", "Poznan", "Jablonec", "Senica"]]
    result = gpd.GeoDataFrame(pd.concat(pieces, ignore_index=True), crs=segments.crs)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    result.to_file(output_path, layer="v3_flooding", driver="GPKG")


if __name__ == "__main__":
    main()
