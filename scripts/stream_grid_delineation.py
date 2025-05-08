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

city_boundary.to_file("dresden_boundary.geojson", driver="GeoJSON")


################
# 0428
# create 100m x 100m grids along the stream
import geopandas as gp
import numpy as np
from shapely.geometry import LineString, box
from shapely.strtree import STRtree
import matplotlib.pyplot as plt
import contextily as ctx
import folium

# Parameters
distance_between_squares = 100  # meters
square_size = 100               # meters

# Load data
streams = gp.read_file("dresden_stream.geojson").to_crs(epsg=25833)
city_boundary = gp.read_file("dresden_boundary.geojson").to_crs(epsg=25833)
place_name = "Dresden"

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

# Save as GeoDataFrame
fishnet = gp.GeoDataFrame(geometry=final_boxes, crs=streams.crs)
fishnet.to_file("dresden_stream_fishnet_final.geojson", driver="GeoJSON")

# Create HTML map
streams_wgs84 = streams.to_crs(epsg=4326)
fishnet_wgs84 = fishnet.to_crs(epsg=4326)
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
m.save("dresden_stream_fishnet_map.html")


##############
import geopandas as gp
import numpy as np
from shapely.geometry import LineString, box
from shapely.strtree import STRtree
import matplotlib.pyplot as plt
import contextily as ctx
import folium

# Parameters
distance_between_squares = 100  # meters
square_size = 100               # meters
min_stream_length_ratio = 1   # keep if stream inside box > = of box width

# Load data
streams = gp.read_file("dresden_stream.geojson").to_crs(epsg=25833)
city_boundary = gp.read_file("dresden_boundary.geojson").to_crs(epsg=25833)
place_name = "Dresden"

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
fishnet.to_file("dresden_stream_fishnet_filtered.geojson", driver="GeoJSON")

# Create HTML map
streams_wgs84 = streams.to_crs(epsg=4326)
fishnet_wgs84 = fishnet.to_crs(epsg=4326)
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
m.save("dresden_stream_fishnet_filtered_map.html")


# Step 8: Calculate sinuosity for each grid
sinuosity_values = []

for square in fishnet.geometry:
    # Clip the stream inside the square
    clipped = streams.intersection(square)
    clipped = clipped[~clipped.is_empty]  # remove empty
    
    total_channel_length = 0 
    total_downvalley_length = 0
    
    for part in clipped:
        if isinstance(part, LineString):
            channel_length = part.length
            coords = part.coords
            start = coords[0]
            end = coords[-1]
            downvalley_length = LineString([start, end]).length
            
            total_channel_length += channel_length
            total_downvalley_length += downvalley_length
    
    # Calculate sinuosity for this square
    if total_downvalley_length > 0:
        sinuosity = total_channel_length / total_downvalley_length
    else:
        sinuosity = None  # if no valid stream inside
    
    sinuosity_values.append(sinuosity)

# Add as a new column
fishnet["sinuosity"] = sinuosity_values

fishnet.to_file("dresden_stream_sinuosity.geojson", driver="GeoJSON")

print(fishnet.head())

