import numpy as np
import pandas as pd
import geopandas as gpd


segments_path = "data/input/streamall_100m_segments_from_mouth.gpkg"
riparian_path = "data/production/variables/v2_riparian_width.gpkg"
floodplain_path = "data/production/variables/v2_floodplain.gpkg"
slope_path = "data/production/variables/v1_slope.gpkg"
upstream_path = "data/production/variables/v1_upstream_area.gpkg"

output_path = "data/production/variables/v3_flooding.gpkg"


def zscore(s):
    arr = pd.to_numeric(s, errors="coerce").astype(float)
    return (arr - np.nanmean(arr)) / np.nanstd(arr)


def map_200m(segments, vars200, col):
    out = pd.Series(np.nan, index=segments.index)

    seg_mid = (
        pd.to_numeric(segments["start_distance"], errors="coerce")
        + pd.to_numeric(segments["end_distance"], errors="coerce")
    ) / 2

    for mid_id in segments["merged_id"].dropna().unique():
        seg_idx = segments.index[segments["merged_id"] == mid_id]
        subset = vars200[vars200["merged_id"] == mid_id]

        for i in seg_idx:
            m = seg_mid.loc[i]
            match = subset[(subset["start_distance"] <= m) & (m <= subset["end_distance"])]

            if len(match):
                out.at[i] = match.iloc[0][col]

    return out


def qclass(s):
    labels = ["very_low", "low", "moderate", "high", "very_high"]
    v = pd.to_numeric(s, errors="coerce").dropna()
    cls = pd.qcut(v, q=5, labels=labels, duplicates="drop")
    out = pd.Series(np.nan, index=s.index)
    out.loc[v.index] = cls.astype(str)
    return out


segments = gpd.read_file(segments_path).to_crs("EPSG:25833")

result = segments[["segment100_id", "merged_id", "start_distance", "end_distance", "geometry"]].copy()


riparian = gpd.read_file(riparian_path).to_crs("EPSG:25833")
col = "riparian_width_mean" if "riparian_width_mean" in riparian else "riparian_width_median"
result = result.merge(
    riparian[["segment100_id", col]].rename(columns={col: "riparian_width_m"}),
    on="segment100_id",
    how="left",
)


floodplain = gpd.read_file(floodplain_path).to_crs("EPSG:25833")
result = result.merge(
    floodplain[["segment100_id", "floodplain_ratio_250m"]],
    on="segment100_id",
    how="left",
)

result["floodplain_width_m"] = (
    pd.to_numeric(result["floodplain_ratio_250m"], errors="coerce") * 500
).clip(0, 500)


slope = gpd.read_file(slope_path).to_crs("EPSG:25833")
upstream = gpd.read_file(upstream_path).to_crs("EPSG:25833")

result["slope"] = map_200m(result, slope, "longitudinal_slope")
result["area"] = map_200m(result, upstream, "upstream_area_m2")
result["area_log"] = np.log1p(pd.to_numeric(result["area"], errors="coerce"))


z1 = zscore(result["floodplain_width_m"])
z2 = zscore(result["riparian_width_m"])
z3 = -zscore(result["slope"])
z4 = zscore(result["area_log"])


comp = pd.concat([z1, z2, z3, z4], axis=1)
result["flooding_proxy_v3_clim"] = comp.mean(axis=1)
result.loc[comp.notna().sum(axis=1) < 3, "flooding_proxy_v3_clim"] = np.nan


result.to_file(output_path, driver="GPKG")