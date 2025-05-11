
################
# 0508 found out the export has errors, because the stream lines are multistring, so need to convert them to linestring, see osm_stream_extract.py
# why not change below for multistring? just worry multistring will make more errors
# 0509&0511 re-run for four cities
# create 100m x 100m grids along the stream
import geopandas as gp
import numpy as np
from shapely.geometry import LineString, box
from shapely.strtree import STRtree
import matplotlib.pyplot as plt
import contextily as ctx
import folium

# Load data
city_name = "Senica"
target_crs = 25833  # poznan 2180
streams = gp.read_file(f"streams_{city_name}_singleline.gpkg").to_crs(epsg=target_crs)

print(streams.geometry.type.value_counts())

city_boundary = gp.read_file(f"city_boundary_{city_name}.gpkg").to_crs(epsg=target_crs)

# Parameters
distance_between_squares = 100  # meters
square_size = 100               # meters
min_stream_length_ratio = 1   # keep if stream inside box > = of box width


# Create squares along streams
half_size = square_size / 2
boxes = []

for idx, row in streams.iterrows():
    geometry = row.geometry
    if isinstance(geometry, LineString):
        num_points = int(geometry.length // distance_between_squares)
        for i in range(num_points + 1):
            point = geometry.interpolate(i * distance_between_squares)
            square = box(point.x - half_size, point.y - half_size, point.x + half_size, point.y + half_size)
            boxes.append(square)

# Remove duplicates
squares = gp.GeoSeries(boxes).drop_duplicates().reset_index(drop=True)

# Remove overlapping squares
tree = STRtree(squares)
final_boxes = []

for geom in squares:
    if not any(geom.intersects(existing) for existing in final_boxes):
        final_boxes.append(geom)

# Check stream length inside each box
valid_boxes = []

for square in final_boxes:
    # Clip the stream to the square
    clipped = streams.intersection(square)
    # Sum the length of all clipped parts
    clipped_length = clipped.length.sum()
    # If stream inside is long enough, keep
    if clipped_length >= min_stream_length_ratio * square_size:
        valid_boxes.append(square)

# Save as GeoDataFrame
fishnet = gp.GeoDataFrame(geometry=valid_boxes, crs=streams.crs) 

# check number of polygons in fishnet
print(f"Number of polygons in fishnet: {len(fishnet)}")

# export fishnet within city boundary
fishnet_final = fishnet[fishnet.within(city_boundary.geometry.union_all())]
fishnet_final.to_file(f"fishnet_{city_name}.gpkg", driver="GPKG")

#####visualise
# Create HTML map
streams_wgs84 = streams.to_crs(epsg=4326)
fishnet_wgs84 = fishnet_final.to_crs(epsg=4326)
city_boundary_wgs84 = city_boundary.to_crs(epsg=4326)

city_center = city_boundary_wgs84.geometry.centroid.iloc[0]
m = folium.Map(location=[city_center.y, city_center.x], zoom_start=12, tiles='OpenStreetMap')

folium.GeoJson(
    streams_wgs84,
    style_function=lambda x: {'color': 'blue', 'weight': 2},
    name="Streams"
).add_to(m)

folium.GeoJson(
    fishnet_wgs84,
    style_function=lambda x: {'color': 'red', 'weight': 1, 'fillOpacity': 0},
    name="Fishnet"
).add_to(m)

folium.GeoJson(
    city_boundary_wgs84,
    style_function=lambda x: {'color': 'black', 'weight': 2, 'fillOpacity': 0},
    name="City Boundary"
).add_to(m)

folium.LayerControl().add_to(m)
m.save(f"Grid_{city_name}.html")
