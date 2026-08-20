import os
import geopandas as gpd
import numpy as np
import pandas as pd


def add_v3_scores(frame):
    specifications = {
        "biodiversity": {
            "habitat_quality": 1,
            "land_cover_diversity": 1,
            "riparian_vegetation_condition": 1,
        },
        "climate_adaptation": {
            "carbon_storage": 1,
            "land_surface_temperature": -1,
            "flood_susceptibility": 1,
        },
        "quality_of_life": {
            "building_accessibility": 1,
            "public_transport_accessibility": 1,
            "programme_accessibility": 1,
            "visibility": 1,
        },
    }

    out = frame.copy()
    domain_columns = []
    for domain, specification in specifications.items():
        components = []
        for name, sign in specification.items():
            values = pd.to_numeric(out[name], errors="coerce") * sign
            lo = values.min(skipna=True)
            hi = values.max(skipna=True)
            components.append((values - lo) / (hi - lo))
        out[f"v3_{domain}"] = pd.concat(components, axis=1).mean(axis=1, skipna=False)
        domain_columns.append(f"v3_{domain}")
    out["v3"] = out[domain_columns].mean(axis=1, skipna=False)
    return out


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


def complete_parent_support(result, parent_path, expected_length):
    """Return whether each 100 m midpoint lies in a complete parent segment."""
    parent = gpd.read_file(parent_path)[
        ["merged_id", "start_distance", "end_distance", "segment_length"]
    ].copy()
    parent = parent[
        np.isclose(
            pd.to_numeric(parent["segment_length"], errors="coerce"),
            expected_length,
            rtol=0,
            atol=1e-6,
        )
    ]
    child_mid = (
        pd.to_numeric(result["start_distance"], errors="coerce")
        + pd.to_numeric(result["end_distance"], errors="coerce")
    ) / 2.0
    supported = pd.Series(False, index=result.index, dtype=bool)

    for merged_id in result["merged_id"].dropna().unique():
        child_idx = result.index[result["merged_id"] == merged_id]
        intervals = parent[parent["merged_id"] == merged_id]
        for i in child_idx:
            midpoint = child_mid.loc[i]
            supported.at[i] = bool(
                (
                    (intervals["start_distance"] <= midpoint)
                    & (midpoint <= intervals["end_distance"])
                ).any()
            )
    return supported


segments_100m = gpd.read_file("data/stream_segments/streams_03_segments_100m.gpkg")
result = segments_100m.copy()
result["has_complete_200m_support"] = complete_parent_support(
    result, "data/stream_segments/streams_03_segments_200m.gpkg", 200.0
)
result["has_complete_400m_support"] = complete_parent_support(
    result, "data/stream_segments/streams_03_segments_400m.gpkg", 400.0
)
result["multiscale_eligible"] = (
    result["has_complete_200m_support"] & result["has_complete_400m_support"]
)
# 100m variables direct by segment100_id
result = merge_by_segment_id(result, "data/production/variables/v2_impervious.gpkg", "segment100_id", ["impervious_cover"])
result = merge_by_segment_id(result, "data/production/variables/v2_canopy.gpkg", "segment100_id", ["canopy_cover"])
result = merge_by_segment_id(result, "data/production/variables/v2_riparian_tree_density.gpkg", "segment100_id", ["riparian_tree_cover"])
result = merge_by_segment_id(result, "data/production/variables/v2_open_space_ratio.gpkg", "segment100_id", ["open_space_cover"])
result = merge_by_segment_id(result, "data/production/variables/v2_land_cover_diversity.gpkg", "segment100_id", ["land_cover_diversity"])
result = merge_by_segment_id(result, "data/production/variables/v2_edge_density.gpkg", "segment100_id", ["edge_density"])
result = merge_by_segment_id(result, "data/production/variables/v3_lst.gpkg", "segment100_id", ["land_surface_temperature"])
result = merge_by_segment_id(result, "data/production/variables/v2_riparian_continuity.gpkg", "segment100_id", ["riparian_continuity"])
result = merge_by_segment_id(result, "data/production/variables/v3_ndvi.gpkg", "segment100_id", ["riparian_vegetation_condition"])
result = merge_by_segment_id(result, "data/production/variables/v3_carbon_storage.gpkg", "segment100_id", ["carbon_storage"])
result = merge_by_segment_id(
    result,
    "data/production/variables/v3_habitat_quality.gpkg",
    "segment100_id",
    [
        "habitat_quality",
        "habitat_quality_median",
        "habitat_quality_p10",
        "habitat_quality_p90",
        "habitat_quality_low_fraction",
        "habitat_quality_suitable_fraction",
        "habitat_quality_largest_patch_fraction",
        "habitat_quality_effective_mesh",
        "habitat_quality_patch_count",
        "habitat_quality_pixel_count",
    ],
)

# 200m variables mapped by merged_id and distance
seg200 = "data/stream_segments/streams_03_segments_200m.gpkg"
base200 = gpd.read_file(seg200)
base200 = merge_by_segment_id(base200, "data/production/variables/v1_slope.gpkg", "segment200_id", ["longitudinal_slope", "slope"])
base200 = merge_by_segment_id(base200, "data/production/variables/v1_valley_morphology.gpkg", "segment200_id", ["valley_width", "valley_depth"])
base200 = merge_by_segment_id(base200, "data/production/variables/v1_sinuosity.gpkg", "segment200_id", ["sinuosity"])
base200 = merge_by_segment_id(
    base200,
    "data/production/variables/v2_crossings.gpkg",
    "segment200_id",
    ["transport_crossing_density"],
)
base200 = merge_by_segment_id(base200, "data/production/variables/v1_underground_ratio.gpkg", "segment200_id", ["underground_ratio"])
base200 = merge_by_segment_id(base200, "data/production/variables/v1_distance_to_source.gpkg", "segment200_id", ["distance_to_source"])
base200 = merge_by_segment_id(base200, "data/production/variables/v1_upstream_area.gpkg", "segment200_id", ["upstream_area_m2", "upstream_area"])
base200 = merge_by_segment_id(
    base200,
    "data/production/variables/v3_flooding.gpkg",
    "segment200_id",
    [
        "flood_susceptibility",
        "hand_mean",
        "hand_median",
        "hand_p10",
        "hand_p90",
        "hand_1m_cover",
        "hand_2m_cover",
        "hand_3m_cover",
    ],
)

path_200_temp = "data/production/variables/_tmp_for_merge_200m.gpkg"
base200.to_file(path_200_temp, driver="GPKG")
result = map_parent_to_100m(
    result,
    path_200_temp,
    "segment200_id",
    [
        "longitudinal_slope",
        "slope",
        "valley_width",
        "valley_depth",
        "sinuosity",
        "transport_crossing_density",
        "underground_ratio",
        "distance_to_source",
        "upstream_area_m2",
        "upstream_area",
        "flood_susceptibility",
        "hand_mean",
        "hand_median",
        "hand_p10",
        "hand_p90",
        "hand_1m_cover",
        "hand_2m_cover",
        "hand_3m_cover",
    ],
)
os.remove(path_200_temp)

# 400m variables mapped by merged_id and distance
seg400 = "data/stream_segments/streams_03_segments_400m.gpkg"
base400 = gpd.read_file(seg400)
base400 = merge_by_segment_id(base400, "data/production/variables/v2_access_transport.gpkg", "segment400_id", ["public_transport_count", "entrance_count"])
base400 = merge_by_segment_id(base400, "data/production/variables/v2_access_slowmob.gpkg", "segment400_id", ["slowmob_length"])
base400 = merge_by_segment_id(
    base400,
    "data/production/variables/v2_access_poi_programme_amenities.gpkg",
    "segment400_id",
    ["poi_amenities", "programme_count"],
)
base400 = merge_by_segment_id(
    base400,
    "data/production/variables/v3_building_transport_stream_access.gpkg",
    "segment400_id",
    [
        "building_accessibility",
        "building_min_network_distance_m",
        "public_transport_accessibility",
        "transport_min_network_distance_m",
    ],
)
base400 = merge_by_segment_id(
    base400,
    "data/production/variables/v3_stream_use_access.gpkg",
    "segment400_id",
    [
        "programme_accessible_count",
        "programme_accessibility",
    ],
)

visibility_path = "data/production/variables/all_streams_isovist.gpkg"
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
base400["visibility"] = vis_vals

path_400_temp = "data/production/variables/_tmp_for_merge_400m.gpkg"
base400.to_file(path_400_temp, driver="GPKG")
result = map_parent_to_100m(
    result,
    path_400_temp,
    "segment400_id",
    [
        "public_transport_count",
        "entrance_count",
        "slowmob_length",
        "poi_amenities",
        "programme_count",
        "building_accessibility",
        "building_min_network_distance_m",
        "public_transport_accessibility",
        "transport_min_network_distance_m",
        "programme_accessible_count",
        "programme_accessibility",
        "visibility",
    ],
)
os.remove(path_400_temp)

result = add_v3_scores(result)
result.to_file("data/production/variables/v_all_variables.gpkg", driver="GPKG")
