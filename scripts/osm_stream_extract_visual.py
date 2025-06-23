# 20250623
### following the osm_data_collection.py script of collecting stream data, this script prepares it for visualization.
# but this .py was used to collect api data before June 20, 2025. see more details in git history.
import os
import osmnx as ox
import geopandas as gpd
import pandas as pd
import folium
from folium.features import DivIcon, FeatureGroup


# city_name = "Dresden" #focus_stream = "Geberbach"
# city_name = "Jablonec" #focus_stream = "Bílá Nisa"
# city_name = "Poznan" #focus_stream = "Piaśnica"
# city_name = "Senica"  focus_stream = "Teplica" 

import geopandas as gpd
import folium
from folium.features import DivIcon
from shapely.geometry import Point



catchment = gpd.read_file("data/catchment/intersected_catchments.gpkg")  
city_boundary = gpd.read_file("data/city_boundaries/combined_city_boundaries.gpkg") 

import geopandas as gpd
import pandas as pd

city_files = {
    "Dresden": "data/stream_geometry/Dresden_stream_geometry.gpkg",
    "Jablonec": "data/stream_geometry/Jablonec_stream_geometry.gpkg",
    "Poznan": "data/stream_geometry/Poznan_stream_geometry.gpkg",
    "Senica": "data/stream_geometry/Senica_stream_geometry.gpkg"
}

layers = ["stream", "waterways", "waterbodies"]
merged = {layer: [] for layer in layers}

target_crs = "EPSG:4326"


for city, filepath in city_files.items():
    for layer in layers:
        gdf = gpd.read_file(filepath, layer=layer)
        gdf = gdf.to_crs(target_crs)  # 统一投影
        gdf["City"] = city
        merged[layer].append(gdf)

# merge
stream = gpd.GeoDataFrame(pd.concat(merged["stream"], ignore_index=True), crs=target_crs)
waterways = gpd.GeoDataFrame(pd.concat(merged["waterways"], ignore_index=True), crs=target_crs)
waterbodies = gpd.GeoDataFrame(pd.concat(merged["waterbodies"], ignore_index=True), crs=target_crs)

output_path = "data/stream_geometry/combined_stream_geometry.gpkg"
stream.to_file(output_path, layer="stream", driver="GPKG")
waterways.to_file(output_path, layer="waterways", driver="GPKG")
waterbodies.to_file(output_path, layer="waterbodies", driver="GPKG")

#
import geopandas as gpd
gpkg_path = "data/stream_geometry/combined_stream_geometry.gpkg"

streams = gpd.read_file(gpkg_path, layer="stream")
print(len(streams))
named = streams[streams["name"].notna() & (streams["name"].str.strip() != "")].copy()
unnamed = streams[streams["name"].isna() | (streams["name"].str.strip() == "")].copy()

# dissolve the named streams by "name"
dissolved = named.dissolve(by="name", as_index=False)

combined = gpd.GeoDataFrame(pd.concat([dissolved, unnamed], ignore_index=True), crs=streams.crs)
print(len(combined))
combined.to_file(gpkg_path, layer="stream_named_dissolved", driver="GPKG")

# visualize!!!!!!


gpkg_path = "data/stream_geometry/combined_stream_geometry.gpkg"
stream = gpd.read_file(gpkg_path, layer="stream")
waterways = gpd.read_file(gpkg_path, layer="waterways")
waterbodies = gpd.read_file(gpkg_path, layer="waterbodies")
named_dissolved = gpd.read_file(gpkg_path, layer="stream_named_dissolved")
city_boundary = gpd.read_file("data/city_boundaries/combined_city_boundaries.gpkg")
catchment = gpd.read_file("data/catchment/intersected_catchments.gpkg")



# only keep the columns that are needed to decrease html file size
keep_cols = ["name", "osm_id", "fclass", "City", "geometry"]
stream = stream[[col for col in keep_cols if col in stream.columns]]
waterways = waterways[[col for col in keep_cols if col in waterways.columns]]
waterbodies = waterbodies[[col for col in keep_cols if col in waterbodies.columns]]
named_dissolved = named_dissolved[[col for col in keep_cols if col in named_dissolved.columns]]


focus_streams = {
    "Dresden": "Geberbach",
    "Jablonec": "Bílá Nisa",
    "Poznan": "Piaśnica",
    "Senica": "Teplica"
}

# all focus_stream 
focus_gdfs = []
for city, name in focus_streams.items():
    match = stream[(stream["City"] == city) & (stream["name"] == name)]
    if not match.empty:
        focus_gdfs.append(match)

focus_all = gpd.GeoDataFrame(pd.concat(focus_gdfs, ignore_index=True), crs=stream.crs)

# map center
center = city_boundary.geometry.unary_union.centroid
m = folium.Map(location=[center.y, center.x], zoom_start=7, tiles="OpenStreetMap", control=False)
folium.TileLayer("CartoDB positron").add_to(m)

# 1. City boundary
folium.GeoJson(city_boundary, name="City Boundaries",
               style_function=lambda x: {"color": "indianred", "weight": 4, "fillOpacity": 0.05}).add_to(m)

# 2. Catchment
folium.GeoJson(catchment, name="Catchments",
               style_function=lambda x: {"color": "gold", "weight": 1, "fillOpacity": 0.15}).add_to(m)

# 3. Stream
folium.GeoJson(stream, name="Stream",
               style_function=lambda x: {"color": "royalblue", "weight": 2.5}).add_to(m)

# 4. Waterways
folium.GeoJson(waterways, name="Waterways",
               style_function=lambda x: {"color": "lightsteelblue", "weight": 1, "dashArray": "4, 4"}).add_to(m)

# 5. Waterbodies
folium.GeoJson(waterbodies, name="Waterbodies",
               style_function=lambda x: {"color": "lightblue", "fillColor": "skyblue", "fillOpacity": 0.3}).add_to(m)

# 6. Focus Streams (all 4)
folium.GeoJson(focus_all, name="Focus Streams",
               style_function=lambda x: {"color": "navy", "weight": 2.5}).add_to(m)

# 7. Name Labels
name_label_layer = FeatureGroup(name="Name Labels", show=False)

for _, row in named_dissolved.iterrows():
    if row.geometry.is_empty or row["name"] is None:
        continue
    point = row.geometry.centroid
    folium.Marker(
        location=[point.y, point.x],
        icon=DivIcon(
            icon_size=(150, 20),
            icon_anchor=(0, 0),
            html=f'<div style="font-size:9pt; color:lightblue;"><b>{row["name"]}</b></div>',
        )
    ).add_to(name_label_layer)

name_label_layer.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)

m.save("all_cities_stream_map.html")
