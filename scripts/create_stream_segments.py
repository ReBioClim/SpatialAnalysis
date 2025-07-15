from shapely.strtree import STRtree
import geopandas as gpd
from shapely.geometry import LineString, Point, MultiPoint, MultiLineString, MultiPolygon, Polygon
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
from shapely.ops import linemerge, unary_union, split, snap, substring
from tqdm import tqdm
from scipy.spatial import cKDTree
from shapely.ops import unary_union

streamall= gpd.read_file("data/stream_geometry/streamall.gpkg",driver="GPKG")


boundary = gpd.read_file("data/city_boundaries/combined_city_boundaries.gpkg")
boundary = boundary.to_crs(epsg= 25833)


##########
#####################


stream_exploded = streamall.explode(ignore_index=True)


# merge the lines that connect 
merged_geom = linemerge(unary_union(stream_exploded.geometry))
print(merged_geom.geom_type)

merged_lines = list(merged_geom.geoms)  # MultiLineString to LineString
print(len(merged_lines))


# create points with 100m intervals
cut_points = []

for line in merged_lines:
    if line.length <= 100:
        continue
    distances = np.arange(100, line.length, 100)
    points = [line.interpolate(d) for d in distances]
    cut_points.extend(points)

points_gdf = gpd.GeoDataFrame(geometry=cut_points, crs=streamall.crs)
points_gdf.to_file("data/stream_segments/streamall_cut_points.gpkg", layer="cut_points_100m", driver="GPKG")


# create segments with snap
segments = []

for line in merged_lines:
    if line.length <= 100:
        segments.append(line)
        continue

    distances = np.arange(100, line.length, 100)
    cut_pts = [line.interpolate(d) for d in distances]
    mp = MultiPoint(cut_pts)

    snapped_line = snap(line, mp, tolerance=1e-6)
    try:
        split_result = split(snapped_line, mp)
        segments.extend(split_result.geoms)
    except Exception as e:
        print(f"Failed to split line of length {line.length}: {e}")
        segments.append(line)  # fallback


gdf = gpd.GeoDataFrame(geometry=segments, crs=streamall.crs)
gdf.to_file("data/stream_segments/streamall_segments_100m_snapped.gpkg", layer="segments_100m", driver="GPKG")

# add original stream attributes to new segments
stream_exploded = stream_exploded.reset_index().rename(columns={"index": "orig_index"})
stream_exploded["geometry"] = stream_exploded.geometry.buffer(0.01)  # small buffer for reliable overlay

segment_gdf = gpd.read_file("data/stream_segments/streamall_segments_100m_snapped.gpkg", layer="segments_100m")

segment_with_attrs = gpd.sjoin(segment_gdf, stream_exploded, how="left", predicate="intersects")
segment_with_attrs.drop(columns=["index_right"], inplace=True)

segment_with_attrs.to_file("data/stream_segments/streamall_segments_100m_with_attrs.gpkg",driver="GPKG")




# 250709
# # create 100m buffer 

# clean 100m stream segments
stream100 = gpd.read_file("data/stream_segments/streamall_segments_100m_with_attrs.gpkg",driver="GPKG")
cityboundary = gpd.read_file("data/city_boundaries/combined_city_boundaries.gpkg", driver = "GPKG")
cityboundary = cityboundary.to_crs(stream100.crs)
stream100_within_boundary = gpd.clip(stream100, cityboundary)
stream100_within_boundary["length"] = stream100_within_boundary.geometry.length

stream100_within_boundary["length"].hist() 
stream100_within_boundary.to_file("data/stream_geometry/stream100_within_boundary.gpkg", driver="GPKG")

print(len(stream100_within_boundary))

stream100_segments_around100 = stream100_within_boundary[(stream100_within_boundary["length"] >= 99) & (stream100_within_boundary["length"] <= 101)].copy()
print(len(stream100_segments_around100))


# removed overlapped
stream100_segments_around100["geom"] = stream100_segments_around100.geometry.apply(lambda g: g.wkb)
stream100_segments_clean = stream100_segments_around100.sort_values("geom").drop_duplicates("geom")
stream100_segments_clean = stream100_segments_clean.drop(columns="geom").reset_index(drop=True)

print(len(stream100_segments_clean)) # actually not quite sure why there were so many overlaps



stream100_segments_clean["segment_id"] = range(1, len(stream100_segments_clean)+1)



stream100_segments_clean.to_file("data/stream_geometry/streamall100_cleaned.gpkg", driver="GPKG")



print(len(stream100_segments_clean)) # 5745

print(stream100_segments_clean.crs)
