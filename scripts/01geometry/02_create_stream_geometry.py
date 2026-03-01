import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.ops import linemerge, unary_union

allblue = gpd.read_file("data/stream_geometry/allblue.gpkg")
stream_only = allblue[allblue["waterway"] == "stream"].copy()
stream_lines = stream_only[stream_only.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()


# remove exact duplicates by geometry
stream_lines["geometry_wkb"] = stream_lines.geometry.apply(lambda x: x.wkb)
stream_lines = stream_lines.drop_duplicates(subset=["geometry_wkb"]).drop(columns=["geometry_wkb"])


sindex = stream_lines.sindex
keep_mask = np.ones(len(stream_lines), dtype=bool)
removed_features = []

for i, (_, row) in enumerate(stream_lines.iterrows()):
    if not keep_mask[i]:
        continue
    possible_matches_index = list(sindex.intersection(row.geometry.bounds))
    possible_matches = stream_lines.iloc[possible_matches_index]
    for _, (other_idx, other_row) in enumerate(possible_matches.iterrows()):
        other_i = stream_lines.index.get_loc(other_idx)
        if other_i <= i or not keep_mask[other_i]:
            continue
        if row.geometry.intersects(other_row.geometry):
            intersection = row.geometry.intersection(other_row.geometry)
            if intersection.is_empty:
                continue
            row_length = row.geometry.length
            other_length = other_row.geometry.length
            overlap_ratio = intersection.length / min(row_length, other_length)

            # remove shorter feature when overlap is high
            if overlap_ratio > 0.8:
                if row_length > other_length:
                    keep_mask[other_i] = False
                    removed_features.append(other_row.to_dict())
                else:
                    keep_mask[i] = False
                    removed_features.append(row.to_dict())
                    break


if removed_features:
    removed_gdf = gpd.GeoDataFrame(removed_features, geometry="geometry")
    removed_gdf.set_crs(stream_lines.crs, inplace=True)
    removed_gdf.to_file("data/stream_geometry/removed_features.gpkg", driver="GPKG")


# output stream attributes
dedup_stream = stream_lines[keep_mask].copy()
dedup_stream.to_file("data/stream_geometry/streamall_attribute.gpkg", driver="GPKG")
named = dedup_stream[dedup_stream["name"].notna()].copy()

if len(named):
    named = named.explode(index_parts=False).reset_index(drop=True)
    merged_named = named.dissolve(by="name", as_index=False)
    merged_named = gpd.GeoDataFrame(merged_named, geometry="geometry", crs=dedup_stream.crs)
else:
    merged_named = gpd.GeoDataFrame(
        columns=dedup_stream.columns,
        geometry="geometry",
        crs=dedup_stream.crs,
    )

unnamed = dedup_stream[dedup_stream["name"].isna()].copy()


# merge named only and keep unnamed unchanged
merged_by_name = gpd.GeoDataFrame(
    pd.concat([merged_named, unnamed], ignore_index=True),
    geometry="geometry",
    crs=dedup_stream.crs,
)
merged_by_name["namemerge_id"] = range(1, len(merged_by_name) + 1)
merged_by_name.to_file("data/stream_geometry/streamall_attribute_namemerge.gpkg", driver="GPKG")


# output connected geometry
stream_proj = dedup_stream.to_crs("EPSG:25833")
line_parts = stream_proj.explode(index_parts=False).reset_index(drop=True)
line_parts = line_parts[line_parts.geometry.geom_type == "LineString"].copy()

# use small buffer to connect near-touching endpoints
merged_lines = linemerge(unary_union(line_parts.geometry.buffer(0.1)).boundary)
if merged_lines.geom_type == "MultiLineString" and len(merged_lines.geoms) > 1:
    merged_lines = linemerge(unary_union(line_parts.geometry.buffer(0.05)).boundary)

if merged_lines.geom_type == "LineString":
    connected_geometries = [merged_lines]
elif merged_lines.geom_type == "MultiLineString":
    connected_geometries = list(merged_lines.geoms)
else:
    connected_geometries = [merged_lines]

connected_lines = gpd.GeoDataFrame(geometry=connected_geometries, crs="EPSG:25833").to_crs("EPSG:25833")
connected_lines.to_file("data/stream_geometry/streamall_geometry.gpkg", driver="GPKG")