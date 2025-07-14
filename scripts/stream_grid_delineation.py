
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
city_name = "Dresden"
target_crs = 25833  # poznan 2180
streams = gp.read_file(f"streams_{city_name}_singleline.gpkg").to_crs(epsg=target_crs)

print(streams.geometry.type.value_counts())

city_boundary = gp.read_file(f"city_boundary_{city_name}.gpkg").to_crs(epsg=target_crs)

# Find the optimal distance between squares
square_size = 100               # meters
min_stream_length_ratio = 1   # keep if stream inside box > = of box width
from shapely.affinity import rotate, translate
import math

best_result = (0, 0)
for test_distance in range(50, 301, 10):
    temp_boxes = []
    for idx, row in streams.iterrows():
        geometry = row.geometry
        if isinstance(geometry, LineString):
            num_points = int(geometry.length // test_distance)
            for i in range(num_points + 1):
                point = geometry.interpolate(i * test_distance)
                if i < num_points:
                    next_point = geometry.interpolate((i + 1) * test_distance)
                else:
                    next_point = geometry.interpolate(i * test_distance - 1)
                dx = next_point.x - point.x
                dy = next_point.y - point.y
                angle_rad = math.atan2(dy, dx)
                angle_deg = math.degrees(angle_rad)
                base_square = box(-square_size / 2, -square_size / 2, square_size / 2, square_size / 2)
                rotated_square = rotate(base_square, angle_deg, use_radians=False)
                moved_square = translate(rotated_square, point.x, point.y)
                temp_boxes.append(moved_square)

    filtered_boxes = []
    for geom in temp_boxes:
        center = geom.centroid
        if not any(center.within(existing) for existing in filtered_boxes):
            filtered_boxes.append(geom)

    valid_count = 0
    for square in filtered_boxes:
        clipped = streams.intersection(square)
        clipped_length = clipped.length.sum()
        if clipped_length >= min_stream_length_ratio * square_size:
            valid_count += 1

    if valid_count > best_result[1]:
        best_result = (test_distance, valid_count)

print(f" Best distance_between_squares = {best_result[0]} m, resulting in {best_result[1]} grids.")



# Parameters
distance_between_squares = 60  # meters


# Create squares along streams
from shapely.affinity import rotate, translate
import math

half_size = square_size / 2
boxes = []
for idx, row in streams.iterrows():
    geometry = row.geometry
    if isinstance(geometry, LineString):
        num_points = int(geometry.length // distance_between_squares)
        for i in range(num_points + 1):
            # Interpolation point
            point = geometry.interpolate(i * distance_between_squares)

            # Points used to estimate direction
            if i < num_points:
                next_point = geometry.interpolate((i + 1) * distance_between_squares)
            else:
                next_point = geometry.interpolate(i * distance_between_squares - 1)

            # Calculate angle (radians to degrees)
            dx = next_point.x - point.x
            dy = next_point.y - point.y
            angle_rad = math.atan2(dy, dx)
            angle_deg = math.degrees(angle_rad)

            # Create a square centered at (0,0)
            base_square = box(-half_size, -half_size, half_size, half_size)
            # Rotate and move to the target point
            rotated_square = rotate(base_square, angle_deg, use_radians=False)
            moved_square = translate(rotated_square, point.x, point.y)
            boxes.append(moved_square)

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
