import os

import geopandas as gpd
import numpy as np
import pandas as pd


def merge_by_segment_id(result, path, key, columns):
    gdf = gpd.read_file(path)
    keep = [key] + columns
    return result.merge(gdf[keep], on=key, how="left")


def map_parent_to_100m(result, parent_path, parent_key, parent_cols):
    parent = gpd.read_file(parent_path)
    need = [parent_key, "merged_id", "start_distance", "end_distance"] + parent_cols
    parent = parent[need].copy()

    child_mid = (
        pd.to_numeric(result["start_distance"], errors="coerce")
        + pd.to_numeric(result["end_distance"], errors="coerce")
    ) / 2.0

    for col in parent_cols:
        if col not in parent.columns:
            continue

        out = pd.Series(np.nan, index=result.index, dtype=float)
        for mid_id in result["merged_id"].dropna().unique():
            child_idx = result.index[result["merged_id"] == mid_id]
            p = parent[parent["merged_id"] == mid_id]
            if len(p) == 0:
                continue
            for i in child_idx:
                m = child_mid.loc[i]
                hit = p[(p["start_distance"] <= m) & (m <= p["end_distance"])]
                if len(hit):
                    out.at[i] = pd.to_numeric(hit.iloc[0][col], errors="coerce")

        result[col] = out

    return result


segments_100m = gpd.read_file("data/input/streamall_100m_segments_from_mouth.gpkg")
result = segments_100m.copy()

# 100m variables (direct by segment100_id)
result = merge_by_segment_id(result, "data/production/variables/v2_impervious.gpkg", "segment100_id", ["impervious_density"])
result = merge_by_segment_id(result, "data/production/variables/v2_canopy.gpkg", "segment100_id", ["canopy_ratio"])
result = merge_by_segment_id(result, "data/production/variables/v2_richness.gpkg", "segment100_id", ["richness_150m"])
result = merge_by_segment_id(result, "data/production/variables/v2_shannon.gpkg", "segment100_id", ["shannon_150m"])
result = merge_by_segment_id(result, "data/production/variables/v3_landuse_intensity.gpkg", "segment100_id", ["landuse_intensity"])
result = merge_by_segment_id(result, "data/production/variables/v3_lst.gpkg", "segment100_id", ["lst_mean_100m"])
result = merge_by_segment_id(result, "data/production/variables/v2_riparian_width.gpkg", "segment100_id", ["riparian_width_mean", "riparian_continuity_longest_m"])
result = merge_by_segment_id(result, "data/production/variables/v2_floodplain.gpkg", "segment100_id", ["floodplain_ratio_250m"])
result = merge_by_segment_id(result, "data/production/variables/v3_ndvi.gpkg", "segment100_id", ["ndvi_0.4_ratio"])
result = merge_by_segment_id(result, "data/production/variables/v3_carbon_sequest.gpkg", "segment100_id", ["carbon_sequest"])
result = merge_by_segment_id(result, "data/production/variables/v3_flooding.gpkg", "segment100_id", ["flooding_proxy_v3_clim"])

# 200m variables (map by merged_id + distance)
seg200 = "data/input/streamall_200m_segments_from_mouth.gpkg"
base200 = gpd.read_file(seg200)
base200 = merge_by_segment_id(base200, "data/production/variables/v1_slope.gpkg", "segment200_id", ["longitudinal_slope", "absolute_slope"])
base200 = merge_by_segment_id(base200, "data/input/valleys.gpkg", "segment200_id", ["valley_width", "valley_depth"])
base200 = merge_by_segment_id(base200, "data/production/variables/v2_sinuosity.gpkg", "segment200_id", ["sinuosity"])
base200 = merge_by_segment_id(base200, "data/production/variables/v2_crossings.gpkg", "segment200_id", ["total_crossings"])
base200 = merge_by_segment_id(base200, "data/production/variables/v2_underground_ratio.gpkg", "segment200_id", ["und_ratio"])
base200 = merge_by_segment_id(base200, "data/production/variables/v2_instream_barrier.gpkg", "segment200_id", ["barrier_count"])
base200 = merge_by_segment_id(base200, "data/production/variables/v1_distance_to_source.gpkg", "segment200_id", ["distance_to_source"])
base200 = merge_by_segment_id(base200, "data/production/variables/v1_upstream_area.gpkg", "segment200_id", ["upstream_area_m2", "upstream_area_log"])

path_200_temp = "data/production/variables/_tmp_for_merge_200m.gpkg"
base200.to_file(path_200_temp, driver="GPKG")
result = map_parent_to_100m(
    result,
    path_200_temp,
    "segment200_id",
    [
        "longitudinal_slope",
        "absolute_slope",
        "valley_width",
        "valley_depth",
        "sinuosity",
        "total_crossings",
        "und_ratio",
        "barrier_count",
        "distance_to_source",
        "upstream_area_m2",
        "upstream_area_log",
    ],
)
os.remove(path_200_temp)

# 400m variables (map by merged_id + distance)
seg400 = "data/input/streamall_400m_segments_from_mouth.gpkg"
base400 = gpd.read_file(seg400)
base400 = merge_by_segment_id(base400, "data/production/variables/v2_access_poi.gpkg", "segment400_id", ["POI_count", "poi_access_index"])
base400 = merge_by_segment_id(base400, "data/production/variables/v2_access_transport.gpkg", "segment400_id", ["stop_count", "entrance_count", "transport_access_index"])
base400 = merge_by_segment_id(base400, "data/production/variables/v2_access_slowmob.gpkg", "segment400_id", ["slowMob_length", "slowmob_access_index"])
base400 = merge_by_segment_id(base400, "data/production/variables/v1_pop_density.gpkg", "segment400_id", ["pop_density_1km"])

visibility_path = "data/input/all_streams_isovist_complete.gpkg"
visibility = gpd.read_file(visibility_path)
vis_vals = []
for _, s in base400.iterrows():
    buf = s.geometry.buffer(300)
    match = visibility[visibility["merged_id"] == s["merged_id"]]
    if len(match) == 0:
        vis_vals.append(0.0)
    else:
        inter = buf.intersection(match.iloc[0].geometry)
        vis_vals.append(inter.area / buf.area)
base400["visibility_ratio"] = vis_vals

path_400_temp = "data/production/variables/_tmp_for_merge_400m.gpkg"
base400.to_file(path_400_temp, driver="GPKG")
result = map_parent_to_100m(
    result,
    path_400_temp,
    "segment400_id",
    [
        "POI_count",
        "poi_access_index",
        "stop_count",
        "entrance_count",
        "transport_access_index",
        "slowMob_length",
        "slowmob_access_index",
        "visibility_ratio",
        "pop_density_1km",
    ],
)
os.remove(path_400_temp)

result.to_file("data/production/variables/v_all_variables.gpkg", driver="GPKG")