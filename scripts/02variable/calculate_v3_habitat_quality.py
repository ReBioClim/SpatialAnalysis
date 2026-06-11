
# Based on the model Sharp et al. (2024), InVEST Habitat Quality model v3.19.


import argparse
import json
import os

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio import features
from rasterio.mask import mask
from scipy.ndimage import label
from shapely.geometry import mapping


lulc_path = "data/input/ESA_landcover_all.tif"
stream_path = "data/input/streamall_100m_segments_from_mouth.gpkg"
roads_path = "data/input/roads_merged.gpkg"

workspace = "output/invest_hq_25833"
inputs = os.path.join(workspace, "inputs")

lulc_fixed_path = os.path.join(inputs, "lulc_cur_discrete_esa.tif")
threat_built_path = os.path.join(inputs, "threat_built_cur.tif")
threat_roads_path = os.path.join(inputs, "threat_roads_cur.tif")
threat_ag_path = os.path.join(inputs, "threat_agriculture_cur.tif")
threats_csv = os.path.join(inputs, "threats.csv")
sens_csv = os.path.join(inputs, "sensitivity.csv")
args_json = os.path.join(inputs, "habitat_quality_args.json")

output_path = "data/production/variables/v3_habitat_quality.gpkg"

major_road_classes = {"motorway", "trunk", "primary", "secondary", "tertiary"}
valid_codes = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100], dtype=np.int16)
hq_threshold = 0.6
low_hq_threshold = 0.3


def find_hq_raster() -> str:
    hq_raster = os.path.join(workspace, "quality_c_esa25833.tif")
    if not os.path.exists(hq_raster):
        raise RuntimeError(f"Expected habitat-quality raster not found: {hq_raster}")
    return hq_raster


def write_threat(arr, path, profile):
    p = profile.copy()
    p.update(dtype=rasterio.float32, nodata=0.0)
    with rasterio.open(path, "w", **p) as dst:
        dst.write(arr.astype(np.float32), 1)


def run_invest_hq() -> str:
    from natcap.invest import habitat_quality

    os.makedirs(inputs, exist_ok=True)

    streams = gpd.read_file(stream_path).to_crs("EPSG:25833")
    stream_buffer = streams.buffer(100).union_all()
    aoi = streams.buffer(1000).union_all()

    # 1) clip ESA LULC to AOI and snap to discrete class codes
    with rasterio.open(lulc_path) as src:
        lulc, transform = mask(src, [aoi], crop=True, filled=True, nodata=0)
        lulc = lulc[0]
        profile = src.profile.copy()

    valid_lulc = (lulc > 0) & (lulc <= 100)
    lulc_fixed = np.zeros(lulc.shape, dtype=np.int16)
    if np.any(valid_lulc):
        vals = lulc[valid_lulc].astype(np.int16)
        lulc_fixed[valid_lulc] = valid_codes[
            np.abs(vals[:, None] - valid_codes).argmin(axis=1)
        ]

    profile.update(
        dtype=rasterio.int16,
        count=1,
        nodata=0,
        compress="lzw",
        height=lulc_fixed.shape[0],
        width=lulc_fixed.shape[1],
        transform=transform,
    )
    with rasterio.open(lulc_fixed_path, "w", **profile) as dst:
        dst.write(lulc_fixed, 1)

    # 2) threat rasters on the LULC grid
    write_threat((lulc_fixed == 50).astype(np.float32), threat_built_path, profile)
    write_threat((lulc_fixed == 40).astype(np.float32), threat_ag_path, profile)

    roads = gpd.read_file(roads_path).to_crs("EPSG:25833")
    roads = roads[roads["fclass"].isin(major_road_classes)]
    roads = roads[roads.intersects(aoi)]
    print(f"Major roads inside AOI: {len(roads)}")

    if len(roads) > 0:
        shapes = ((geom, 1) for geom in roads.geometry)
        threat_roads = features.rasterize(
            shapes,
            out_shape=lulc_fixed.shape,
            transform=transform,
            fill=0,
            dtype="float32",
            all_touched=True,
        )
    else:
        threat_roads = np.zeros_like(lulc_fixed, dtype=np.float32)
    write_threat(threat_roads, threat_roads_path, profile)

    # 3) threats table
    pd.DataFrame(
        [
            {"threat": "built_up",    "max_dist": 1.0, "weight": 1.0, "decay": "exponential", "cur_path": os.path.basename(threat_built_path)},
            {"threat": "roads",       "max_dist": 0.5, "weight": 0.7, "decay": "exponential", "cur_path": os.path.basename(threat_roads_path)},
            {"threat": "agriculture", "max_dist": 0.8, "weight": 0.5, "decay": "linear",      "cur_path": os.path.basename(threat_ag_path)},
        ]
    ).to_csv(threats_csv, index=False)

    # 4) sensitivity table
    sens_rows = [
        # lucode  habitat  built_up  roads  agriculture
        (10,      1.00,    0.9,      0.8,   0.7),
        (20,      0.80,    0.8,      0.7,   0.6),
        (30,      0.70,    0.7,      0.6,   0.5),
        (40,      0.40,    0.5,      0.4,   0.0),
        (50,      0.00,    0.0,      0.0,   0.0),
        (60,      0.20,    0.3,      0.2,   0.2),
        (70,      0.10,    0.1,      0.1,   0.1),
        (80,      0.90,    0.4,      0.4,   0.5),
        (90,      0.80,    0.6,      0.5,   0.6),
        (95,      0.90,    0.6,      0.6,   0.6),
        (100,     0.30,    0.2,      0.2,   0.2),
    ]
    pd.DataFrame(
        sens_rows, columns=["lucode", "habitat", "built_up", "roads", "agriculture"]
    ).to_csv(sens_csv, index=False)

    # 5) run InVEST
    args = {
        "workspace_dir": workspace,
        "results_suffix": "esa25833",
        "lulc_cur_path": lulc_fixed_path,
        "threats_table_path": threats_csv,
        "sensitivity_table_path": sens_csv,
        "half_saturation_constant": 0.5,
    }
    with open(args_json, "w", encoding="utf-8") as f:
        json.dump(args, f, indent=2)

    habitat_quality.execute(args)

    hq_file = find_hq_raster()
    write_workspace_summary(hq_file, stream_buffer)
    return hq_file


def write_workspace_summary(hq_file, stream_buffer):
    with rasterio.open(hq_file) as src:
        out, _ = mask(src, [stream_buffer], crop=False, filled=False)
        v = out[0].compressed().astype(np.float32)
        v = v[(v >= 0.0) & (v <= 1.0)]

    summary = pd.DataFrame(
        {
            "metric": ["pixel_count", "hq_mean", "hq_median", "hq_std", "hq_p10", "hq_p90", "hq_low_share_lt_0p3"],
            "value": [
                int(v.size),
                float(np.mean(v)),
                float(np.median(v)),
                float(np.std(v)),
                float(np.percentile(v, 10)),
                float(np.percentile(v, 90)),
                float(np.mean(v < 0.3)),
            ],
        }
    )
    out_csv = os.path.join(workspace, "riparian_hq_stats_100m.csv")
    summary.to_csv(out_csv, index=False)

    print(f"HQ raster: {hq_file}")
    print(f"Riparian summary: {out_csv}")
    print(summary.to_string(index=False))


def stats_in_buffer(src, geom) -> pd.Series:
    out, _ = mask(src, [mapping(geom)], crop=True, filled=False, all_touched=True)
    arr = out[0].filled(np.nan).astype(np.float32)
    vals = arr[np.isfinite(arr)]
    vals = vals[(vals >= 0.0) & (vals <= 1.0)]

    if vals.size == 0:
        return pd.Series(
            {
                "hq_mean": np.nan,
                "hq_median": np.nan,
                "hq_p10": np.nan,
                "hq_p90": np.nan,
                "hq_low_share_lt0p3": np.nan,
                "hq_suitable_share_ge0p6": np.nan,
                "hq_largest_patch_share_ge0p6": np.nan,
                "hq_effective_mesh_ge0p6": np.nan,
                "hq_patch_count_ge0p6": np.nan,
                "hq_px_count": 0,
            }
        )

    valid = np.isfinite(arr) & (arr >= 0.0) & (arr <= 1.0)
    suitable = valid & (arr >= hq_threshold)
    total_valid = int(valid.sum())
    suitable_count = int(suitable.sum())

    largest_patch_share = 0.0
    effective_mesh = 0.0
    patch_count = 0
    if suitable_count > 0:
        structure = np.ones((3, 3), dtype=np.int8)
        labeled, patch_count = label(suitable, structure=structure)
        patch_sizes = np.bincount(labeled.ravel())[1:]
        largest_patch_share = float(patch_sizes.max() / suitable_count)
        effective_mesh = float(np.sum((patch_sizes / total_valid) ** 2))

    return pd.Series(
        {
            "hq_mean": float(np.mean(vals)),
            "hq_median": float(np.median(vals)),
            "hq_p10": float(np.percentile(vals, 10)),
            "hq_p90": float(np.percentile(vals, 90)),
            "hq_low_share_lt0p3": float(np.mean(vals < low_hq_threshold)),
            "hq_suitable_share_ge0p6": float(suitable_count / total_valid),
            "hq_largest_patch_share_ge0p6": largest_patch_share,
            "hq_effective_mesh_ge0p6": effective_mesh,
            "hq_patch_count_ge0p6": int(patch_count),
            "hq_px_count": int(vals.size),
        }
    )


def summarize_segments(hq_raster):
    segments = gpd.read_file(stream_path).to_crs("EPSG:25833")
    buffered = segments.copy()
    buffered["geometry"] = buffered.geometry.buffer(100)

    print(f"Using HQ raster: {hq_raster}")

    with rasterio.open(hq_raster) as src:
        hq_stats = buffered.geometry.apply(lambda g: stats_in_buffer(src, g))

    out = segments[["segment100_id", "geometry"]].copy()
    out = pd.concat([out.reset_index(drop=True), hq_stats.reset_index(drop=True)], axis=1)

    if os.path.exists(output_path):
        os.remove(output_path)
    out.to_file(output_path, driver="GPKG")

    print(f"Wrote {len(out)} segments -> {output_path}")
    print(out["hq_mean"].describe().to_string())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-invest",
        action="store_true",
        help="Use the existing HQ raster and only update per-segment summaries.",
    )
    args = parser.parse_args()

    hq_raster = find_hq_raster() if args.skip_invest else run_invest_hq()
    summarize_segments(hq_raster)


if __name__ == "__main__":
    main()
