"""Based on InVEST Habitat Quality model v3.19 (Sharp et al., 2024)
"""

import os
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio import features
from rasterio.mask import mask
from scipy.ndimage import label
from shapely.geometry import mapping


lulc_path = "data/prepared/ESA_landcover_all.tif"
stream_path = "data/stream_segments/streams_03_segments_100m.gpkg"
roads_path = "data/prepared/roads_merged.gpkg"

workspace = "data/production/invest_hq_25833"
inputs = os.path.join(workspace, "inputs")

lulc_fixed_path = os.path.join(inputs, "lulc_cur_discrete_esa.tif")
threat_built_path = os.path.join(inputs, "threat_built_cur.tif")
threat_roads_path = os.path.join(inputs, "threat_roads_cur.tif")
threat_ag_path = os.path.join(inputs, "threat_agriculture_cur.tif")
threats_csv = os.path.join(inputs, "threats.csv")
sens_csv = os.path.join(inputs, "sensitivity.csv")
output_path = "data/production/variables/v3_habitat_quality.gpkg"

major_road_classes = {"motorway", "trunk", "primary", "secondary", "tertiary"}
valid_codes = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100], dtype=np.int16)
hq_threshold = 0.6
low_hq_threshold = 0.3


def find_hq_raster() -> str:
    return os.path.join(workspace, "quality_c_esa25833.tif")


def write_threat(arr, path, profile):
    p = profile.copy()
    p.update(dtype=rasterio.float32, nodata=0.0)
    with rasterio.open(path, "w", **p) as dst:
        dst.write(arr.astype(np.float32), 1)


def run_invest_hq() -> str:
    from natcap.invest import habitat_quality

    os.makedirs(inputs, exist_ok=True)

    streams = gpd.read_file(stream_path).to_crs("EPSG:25833")
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
    habitat_quality.execute(args)
    return find_hq_raster()


def stats_in_buffer(src, geom) -> pd.Series:
    out, _ = mask(src, [mapping(geom)], crop=True, filled=False, all_touched=True)
    arr = out[0].filled(np.nan).astype(np.float32)
    vals = arr[np.isfinite(arr)]
    vals = vals[(vals >= 0.0) & (vals <= 1.0)]

    if vals.size == 0:
        return pd.Series(
            {
                "habitat_quality": np.nan,
                "habitat_quality_median": np.nan,
                "habitat_quality_p10": np.nan,
                "habitat_quality_p90": np.nan,
                "habitat_quality_low_fraction": np.nan,
                "habitat_quality_suitable_fraction": np.nan,
                "habitat_quality_largest_patch_fraction": np.nan,
                "habitat_quality_effective_mesh": np.nan,
                "habitat_quality_patch_count": np.nan,
                "habitat_quality_pixel_count": 0,
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
            "habitat_quality": float(np.mean(vals)),
            "habitat_quality_median": float(np.median(vals)),
            "habitat_quality_p10": float(np.percentile(vals, 10)),
            "habitat_quality_p90": float(np.percentile(vals, 90)),
            "habitat_quality_low_fraction": float(np.mean(vals < low_hq_threshold)),
            "habitat_quality_suitable_fraction": float(suitable_count / total_valid),
            "habitat_quality_largest_patch_fraction": largest_patch_share,
            "habitat_quality_effective_mesh": effective_mesh,
            "habitat_quality_patch_count": int(patch_count),
            "habitat_quality_pixel_count": int(vals.size),
        }
    )


def summarize_segments(hq_raster):
    segments = gpd.read_file(stream_path).to_crs("EPSG:25833")
    buffered = segments.copy()
    buffered["geometry"] = buffered.geometry.buffer(100)

    with rasterio.open(hq_raster) as src:
        hq_stats = buffered.geometry.apply(lambda g: stats_in_buffer(src, g))

    out = segments[["segment100_id", "geometry"]].copy()
    out = pd.concat([out.reset_index(drop=True), hq_stats.reset_index(drop=True)], axis=1)

    out.to_file(output_path, driver="GPKG")

def main():
    hq_raster = run_invest_hq()
    summarize_segments(hq_raster)


if __name__ == "__main__":
    main()
