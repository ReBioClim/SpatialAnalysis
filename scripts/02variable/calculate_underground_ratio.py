import geopandas as gpd
import numpy as np


segments = gpd.read_file("data/input/streamall_200m_segments_from_mouth.gpkg")
merged_stream = gpd.read_file("data/input/streamall_merged_final.gpkg")
allblue = gpd.read_file("data/input/allblue.gpkg")


allblue = allblue[allblue.geometry.notna() & (~allblue.geometry.is_empty)]
allblue = allblue[allblue.geometry.geom_type.isin(["LineString", "MultiLineString"])]
allblue = allblue.explode(index_parts=False)
allblue = allblue[allblue.geometry.geom_type == "LineString"]

allblue["covering"] = allblue["covering"].astype(str).str.lower().str.strip()
raw_candidates = allblue[allblue["covering"].isin(["piped", "covered"])][["geometry"]]


# assign to merged stream
merged_stream = merged_stream[["merged_id", "geometry"]]
raw_on_stream = gpd.overlay(
    raw_candidates,
    merged_stream.rename(columns={"merged_id": "source_merged_id"}),
    how="intersection",
)

raw_on_stream = raw_on_stream[raw_on_stream.geometry.geom_type == "LineString"]


# intersect with segments
segments = segments[["segment200_id", "merged_id", "geometry"]]

und_in_seg = gpd.overlay(
    raw_on_stream,
    segments.rename(columns={"merged_id": "segment_merged_id"}),
    how="intersection",
)

und_in_seg = und_in_seg[und_in_seg.geometry.geom_type == "LineString"]
und_in_seg = und_in_seg[und_in_seg["source_merged_id"] == und_in_seg["segment_merged_id"]]


# length filter
und_in_seg["und_len"] = und_in_seg.geometry.length
und_in_seg = und_in_seg[und_in_seg["und_len"] >= 5]


# sum by segment
und_by_seg = und_in_seg.dissolve(by="segment200_id")
und_by_seg["und_len"] = und_by_seg.geometry.length
und_by_seg = und_by_seg.reset_index()[["segment200_id", "und_len"]]


# ratio
result = segments.copy()
result["seg_len"] = result.geometry.length
result = result.merge(und_by_seg, on="segment200_id", how="left")
result["und_len"] = result["und_len"].fillna(0)

result["und_ratio"] = (result["und_len"] / result["seg_len"]).clip(0, 1).fillna(0)


result[["segment200_id", "geometry", "und_ratio"]].to_file(
    "data/production/variables/v2_underground_ratio.gpkg",
    driver="GPKG"
)