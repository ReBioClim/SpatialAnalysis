import geopandas as gpd
from shapely.ops import linemerge, substring, unary_union
from shapely.geometry import LineString, MultiLineString, Point
import shapely
import matplotlib.pyplot as plt
from geopandas import GeoDataFrame


# create stream segments
# 0624
# need to be careful, if only divide stream with name, or the raw stream geometry, the interval starts with each feature, not the complete stream

stream = gpd.read_file("data/stream_geometry/combined_stream_geometry.gpkg", layer="stream_named_dissolved")  

stream_sample= stream[stream["City"] == "Senica"]

stream_sample = stream_sample.to_crs(epsg=25833)

merged = linemerge(unary_union(stream_sample.geometry))

# check if merged is a MultiLineString or LineString
lines = list(merged.geoms) if isinstance(merged, MultiLineString) else [merged]


interval = 100
split_points = []
# iterate over each line and create split points at the specified interval
for line in lines:
    length = line.length
    num_segments = int(length // interval)
    for i in range(1, num_segments):
        pt = line.interpolate(i * interval)
        split_points.append(pt)


import folium
import geopandas as gpd
from shapely.geometry import mapping

stream_gdf = gpd.GeoDataFrame(geometry=lines, crs="EPSG:25833").to_crs(epsg=4326)
points_gdf = gpd.GeoDataFrame(geometry=split_points, crs="EPSG:25833").to_crs(epsg=4326)

stream_gdf.to_file("data/stream_geometry/stream_segments.gpkg", layer="stream_segments", driver="GPKG")
points_gdf.to_file("data/stream_geometry/stream_split_points.gpkg", layer="stream_split_points", driver="GPKG")

centroid = stream_gdf.unary_union.centroid
map_center = [centroid.y, centroid.x]

m = folium.Map(location=map_center, zoom_start=12, tiles='cartodbpositron')

for geom in stream_gdf.geometry:
    if geom.geom_type == "LineString":
        folium.PolyLine(locations=[(pt[1], pt[0]) for pt in geom.coords],
                        color="blue", weight=2, opacity=0.7).add_to(m)
    elif geom.geom_type == "MultiLineString":
        for line in geom.geoms:
            folium.PolyLine(locations=[(pt[1], pt[0]) for pt in line.coords],
                            color="blue", weight=2, opacity=0.7).add_to(m)

for pt in points_gdf.geometry:
    folium.CircleMarker(location=(pt.y, pt.x), radius=3, color='red', fill=True, fill_opacity=0.8).add_to(m)

m
m.save("stream_network_split_points.html")