# extract stream from osm

######### collect streams for the four focused cities separately
import osmnx as ox
import geopandas as gpd

place_name = "Dresden, Germany"
# place_name = "Jablonec nad Nisou, Czech Republic"
# place_name = "Poznań, Poland"
# place_name = "Senica, Slovakia"

streams= ox.features_from_place(place_name,tags={"waterway":"stream"})

streams = streams.to_crs(epsg=3857)

print(streams.head())
print(f"Total streams found: {len(streams)}")

streams.to_file("dresden_stream.geojson", driver="GeoJSON")

city_boundary = ox.geocode_to_gdf(place_name) 
city_boundary = city_boundary.to_crs(epsg=3857)

###


#### method 3: remove overlapping
import geopandas as gp
from shapely.geometry import LineString, box
from shapely.strtree import STRtree

fishnet_boxes = []

# Step 1: Create boxes along streams every 50 meters
for idx, row in streams.iterrows():
    geometry = row.geometry
    
    if isinstance(geometry, LineString):
        distance = 50
        num_points = int(geometry.length // distance)
        
        for i in range(num_points + 1):
            point = geometry.interpolate(i * distance)
            fishnet = box(point.x - 25, point.y - 25, point.x + 25, point.y + 25)
            fishnet_boxes.append(fishnet)

# Step 2: Remove duplicates (exact same geometry)
fishnet_gseries = gp.GeoSeries(fishnet_boxes).drop_duplicates().reset_index(drop=True)

# Step 3: Remove overlaps using spatial indexing (efficient method)
tree = STRtree(fishnet_gseries)
non_overlapping_boxes = []

for geom in fishnet_gseries:
    # Check intersection with already selected boxes
    if not any(geom.intersects(existing_geom) for existing_geom in non_overlapping_boxes):
        non_overlapping_boxes.append(geom)

# Convert back to GeoDataFrame
fishnet_final_gdf = gp.GeoDataFrame(geometry=non_overlapping_boxes, crs=streams.crs)



# Visualize the final result clearly
fig, ax = plt.subplots(figsize=(12, 8))
city_boundary.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=2)
streams.plot(ax=ax, color="dodgerblue", linewidth=1, alpha=0.7)
fishnet_final_gdf.boundary.plot(ax=ax, color="red", linestyle='--', linewidth=1)
ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, alpha=0.5)
ax.set_title(place_name + " with Non-overlapping Fishnet Grid", fontsize=15)
ax.axis('off')
plt.show()




####################
#### test with cutter every 100m along stream
stream = streams.sample(1)  # Select a test stream from the dataset

# function to generate points at fixed intervals along the geometries in a GeoDataFrame
def generate_points_for_streams(gdf, distance):
    all_points = []

    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        if geom.geom_type == 'LineString':
            # Handle a single line
            all_points.extend(_generate_points_from_line(geom, distance, idx))
        elif geom.geom_type == 'MultiLineString':
            # If there are multiple lines in one record, iterate through each
            for part in geom.geoms:
                all_points.extend(_generate_points_from_line(part, distance, idx))

    return gpd.GeoDataFrame(all_points, columns=["stream_id", "geometry"], crs=gdf.crs)

def _generate_points_from_line(line_geom, distance, stream_id):
    generated_points = []
    line_length = int(line_geom.length)
    for dist in range(0, line_length, distance):
        generated_points.append((stream_id, line_geom.interpolate(dist)))
    return generated_points

# generate points at 100m intervals for the single sampled stream
points_gdf = generate_points_for_streams(stream, 100)

print(points_gdf.head())


## 
from shapely.geometry import LineString, LineString
from shapely.affinity import rotate
import math

def create_perpendicular_lines(points_gdf, line_geom, half_length=50):

    line_list = []
    
    for idx, row in points_gdf.iterrows():
        point = row.geometry
        
        # 1. Find distance along the LineString for this point
        dist_along_line = line_geom.project(point)
        
        # 2. Interpolate a small distance ahead to approximate the tangent
        small_step = 0.1  # in projected CRS units (meters, if EPSG:3857)
        ahead_dist = dist_along_line + small_step
        # Make sure we don't exceed the line length
        if ahead_dist > line_geom.length:
            ahead_dist = line_geom.length
        
        ahead_point = line_geom.interpolate(ahead_dist)
        
        # 3. Direction vector (point -> ahead_point)
        dir_x = ahead_point.x - point.x
        dir_y = ahead_point.y - point.y
        
        # 4. Rotate this direction by 90° (pi/2 radians) to get the perpendicular
        #    shapely.affinity.rotate rotates around the origin, so shift to (0,0), rotate, shift back
        #    However, a simpler approach is to just swap and negate: (x, y) -> (-y, x) or (y, -x)
        perp_dir_x = -dir_y
        perp_dir_y = dir_x
        
        # Normalize to length = 1
        length_dir = math.sqrt(perp_dir_x**2 + perp_dir_y**2)
        if length_dir == 0:
            # If the direction is zero (could happen if small_step was too small on a near-vertical line),
            # skip this point or handle specially
            continue
        
        unit_x = perp_dir_x / length_dir
        unit_y = perp_dir_y / length_dir
        
        # 5. Build the line segment from (point - half_length * direction) to (point + half_length * direction)
        start_x = point.x - half_length * unit_x
        start_y = point.y - half_length * unit_y
        end_x   = point.x + half_length * unit_x
        end_y   = point.y + half_length * unit_y
        
        segment = LineString([(start_x, start_y), (end_x, end_y)])
        line_list.append(segment)
    
    # Create a GeoDataFrame of perpendicular lines
    lines_gdf = gpd.GeoDataFrame(geometry=line_list, crs=points_gdf.crs)
    return lines_gdf

line_geometry = stream.iloc[0].geometry  # Get the actual LineString from the GeoDataFrame
perp_lines_gdf = create_perpendicular_lines(points_gdf, line_geometry, half_length=50)
perp_lines_gdf.to_file("perpendicular_lines.geojson", driver="GeoJSON")

#visualise the points and lines


m = leafmap.Map(center=[center_lat, center_lon], zoom=12)
m.add_gdf(stream, layer_name="Stream", style={"color": "red", "weight": 5})
m.add_gdf(points_gdf, layer_name="Points", style={"color": "blue", "radius": 5})
m.add_gdf(city_boundary, layer_name="City Boundary")
m.add_gdf(perp_lines_gdf, layer_name="Perp Lines", style={"color": "green", "weight": 2})
m


######### create fishnet grid 
# method 1: every 50m along the stream
import geopandas as gp
import numpy as np
from shapely.geometry import LineString, box

fishnet_boxes = []

# loop through each stream
for idx, row in streams.iterrows():
    geometry = row.geometry
    
    if isinstance(geometry, LineString):
        # 每隔50米沿着stream真实路径插值放置一个网格
        distance = 50
        num_points = int(geometry.length // distance)
        
        for i in range(num_points + 1):
            point = geometry.interpolate(i * distance)
            fishnet = box(point.x - 25, point.y - 25, point.x + 25, point.y + 25)
            fishnet_boxes.append(fishnet)

# 转换为GeoDataFrame并去除可能的重复网格
fishnet_gdf = gp.GeoDataFrame(geometry=gp.GeoSeries(fishnet_boxes).drop_duplicates(), crs=streams.crs)

# 导出为文件
fishnet_gdf.to_file("dresden_stream_fishnet_fixed.geojson", driver="GeoJSON")

# 可视化查看结果
fig, ax = plt.subplots(figsize=(12, 8))
city_boundary.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=2)
streams.plot(ax=ax, color="dodgerblue", linewidth=1, alpha=0.7)
fishnet_gdf.boundary.plot(ax=ax, color="red", linestyle='--', linewidth=1)
ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, alpha=0.5)
ax.set_title(place_name + " with corrected fishnet grid", fontsize=15)
ax.axis('off')
plt.show()