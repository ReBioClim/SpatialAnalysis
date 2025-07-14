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



# create stream segments
# 250626 & 250703
# previous method create not continuous lines when there is a substream. 
# a bettter way is probably to identify the main stream
# now try the networkx method to find the longest path in the stream network

file1 = gpd.read_file("data/stream_geometry/allblue_cleaned.gpkg")
file2 = gpd.read_file("data/stream_geometry/allblue_100plus.gpkg")

waterbody = file1[file1.geometry.type == "Polygon"].copy()
waterbody = waterbody.to_crs(epsg=25833)
waterway = file2

waterbody.to_file("data/stream_geometry/all_blue.gpkg", layer= "waterbody", driver= "GPKG")
waterway.to_file("data/stream_geometry/all_blue.gpkg", layer= "waterway", driver= "GPKG")

print(waterbody.crs)
print(waterway.crs)
waterbody = gpd.read_file("data/stream_geometry/all_blue.gpkg", layer="waterbody")
waterway = gpd.read_file("data/stream_geometry/all_blue.gpkg", layer="waterway")

stream = waterway[waterway["waterway"] == "stream"].copy()
print(stream.crs)
# check the geometry type 
print(stream.geometry.type.unique()) # multilinestring
# check the mimum and maximum length of the stream lines
print(stream.geometry.length.min()) # 100.4
print(stream.geometry.length.max()) # 85003
print(len(stream))

boundary = gpd.read_file("data/city_boundaries/combined_city_boundaries.gpkg")
boundary = boundary.to_crs(epsg= 25833)

stream.plot()
plt.show()

# a try: when the stream passing through a waterbody, the waterbody should also be seen as part of stream
# but i decided to skip this process! there are waterbody data missing from raw osm data, so never complete
print(waterbody.crs)
print(stream.crs)

endpoints = []
for geom in stream.geometry:
    if geom.is_empty:
        continue
    for line in geom.geoms:  # 处理 MultiLineString
        start = Point(line.coords[0])
        end = Point(line.coords[-1])
        endpoints.extend([start, end])

endpoint_gdf = gpd.GeoDataFrame(geometry=endpoints, crs=stream.crs)

tolerance = 20
endpoint_buffer = endpoint_gdf.buffer(tolerance)
endpoint_buffer_gdf = gpd.GeoDataFrame(geometry=endpoint_buffer, crs=stream.crs)
joined = gpd.sjoin(waterbody, endpoint_buffer_gdf, how="inner", predicate="intersects")

connected = joined.groupby(joined.index).size()

double_connected_ids = connected[connected >= 2].index
double_connected_polygons = waterbody.loc[double_connected_ids].copy()
print(len(double_connected_polygons))
double_connected_polygons.to_file("data/stream_geometry/double_connected_waterbody.gpkg", driver="GPKG")

##########
#####################


# explode
stream = gpd.read_file("data/stream_geometry/all_blue.gpkg", layer="waterway")
stream = stream[stream["waterway"] == "stream"].copy()
print(len(stream))

stream_exploded = stream.explode(ignore_index=True)


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

points_gdf = gpd.GeoDataFrame(geometry=cut_points, crs=stream.crs)
points_gdf.to_file("data/stream_geometry/stream_cut_points.gpkg", layer="cut_points_100m", driver="GPKG")


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


gdf = gpd.GeoDataFrame(geometry=segments, crs=stream.crs)
gdf.to_file("data/stream_geometry/stream_segments_100m_snapped.gpkg", layer="segments_100m", driver="GPKG")

# add original stream attributes to new segments
stream_exploded = stream_exploded.reset_index().rename(columns={"index": "orig_index"})
stream_exploded["geometry"] = stream_exploded.geometry.buffer(0.01)  # small buffer for reliable overlay

segment_gdf = gpd.read_file("data/stream_geometry/stream_segments_100m_snapped.gpkg", layer="segments_100m")

segment_with_attrs = gpd.sjoin(segment_gdf, stream_exploded, how="left", predicate="intersects")
segment_with_attrs.drop(columns=["index_right"], inplace=True)

segment_with_attrs.to_file("data/stream_geometry/stream_segments_100m_with_attrs.gpkg",
                           layer="segments_100m_with_attrs", driver="GPKG")


