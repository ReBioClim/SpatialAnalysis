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
        gdf = gdf.to_crs(target_crs)  
        gdf["City"] = city
        merged[layer].append(gdf)

# merge
waterways = gpd.GeoDataFrame(pd.concat(merged["waterways"], ignore_index=True), crs=target_crs)
waterbodies = gpd.GeoDataFrame(pd.concat(merged["waterbodies"], ignore_index=True), crs=target_crs)

output_path = "data/stream_geometry/combined_stream_geometry.gpkg"
waterways.to_file(output_path, layer="waterways", driver="GPKG")
waterbodies.to_file(output_path, layer="waterbodies", driver="GPKG")



# 0630 update
import geopandas as gpd
gpkg_path = "data/stream_geometry/combined_stream_geometry.gpkg"
waterways = gpd.read_file(gpkg_path, layer="waterways")

# exclude elbe and warta rivers 
stream_noew = waterways[~waterways["name"].isin(["Elbe", "Warta"])].copy()

#exclde flass = drain, or flass= canal 
stream_noew_nodc = stream_noew[~stream_noew["fclass"].isin(["drain", "canal"])].copy()


print(len(stream_noew_nodc) )
print(len(stream_noew))

stream_noew.to_file(gpkg_path, layer="stream_no_elbe_warta", driver="GPKG")
stream_noew_nodc.to_file(gpkg_path, layer="stream_no_elbe_warta_drain_canal", driver="GPKG")

named = streams[streams["name"].notna() & (streams["name"].str.strip() != "")].copy()
unnamed = streams[streams["name"].isna() | (streams["name"].str.strip() == "")].copy()

# dissolve the named streams by "name"
dissolved = named.dissolve(by="name", as_index=False)

combined = gpd.GeoDataFrame(pd.concat([dissolved, unnamed], ignore_index=True), crs=streams.crs)
print(len(combined))
combined.to_file(gpkg_path, layer="stream_named_dissolved", driver="GPKG")

# visualize!!!!!!

allblue = gpd.read_file("data/stream_geometry/all_blue.gpkg", layer= "waterway")
allblue = allblue.to_crs("EPSG:4326")  # convert back to WGS84
streamlines = allblue[allblue["waterway"] == "stream"].copy()
riverlines = allblue[allblue["waterway"] == "river"].copy()
otherwaterways = allblue[~allblue["waterway"].isin(["stream", "river"])].copy()
underground = gpd.read_file("data/stream_geometry/all_blue.gpkg", layer= "underground")
waterpolygons = gpd.read_file("data/stream_geometry/all_blue.gpkg", layer= "waterbody")

print(underground.crs)

underground_intersecting = underground[underground.intersects(allblue.union_all())]

# map center
city_boundary = gpd.read_file("data/city_boundaries/combined_city_boundaries.gpkg")
catchment = gpd.read_file("data/catchment/intersected_catchments.gpkg")
center = city_boundary.geometry.unary_union.centroid

m = folium.Map(location=[center.y, center.x], zoom_start=7, tiles="OpenStreetMap", control=False)
folium.TileLayer("CartoDB positron").add_to(m)

# 1. City boundary
folium.GeoJson(city_boundary, name="City Boundaries",
               style_function=lambda x: {"color": "indianred", "weight": 2, "fillOpacity": 0.05}).add_to(m)

# 2. Catchment
folium.GeoJson(catchment, name="Catchments",
               style_function=lambda x: {"color": "gold", "weight": 1, "fillOpacity": 0.05}).add_to(m)

# 3. Stream
folium.GeoJson(streamlines, name="Streams",
               style_function=lambda x: {"color": "royalblue", "weight": 4}).add_to(m)

# 4. River
folium.GeoJson(riverlines, name="River lines",
               style_function=lambda x: {"color": "cyan", "weight": 4,"opacity": 0.5}).add_to(m)

# 5. All other waterways
folium.GeoJson(otherwaterways, name="Other waterways(ditch,drain,canal,etc.)",
               style_function=lambda x: {"color": "darkturquoise", "weight": 3}).add_to(m)

# 6. Underground
folium.GeoJson(underground_intersecting, name="Underground (tunnel,culvert)",
               style_function=lambda x: {"color": "palevioletred", "weight": 3,"opacity": 0.5 }).add_to(m)


# 7. All waterbodies
folium.GeoJson(waterpolygons, name="Waterbodies",
               style_function=lambda x: {
                   "color": "lightblue",   "fillColor": "lightblue", "weight": 1,  
                     "fillOpacity": 0.8  }).add_to(m)


folium.LayerControl(collapsed=False).add_to(m)

m.save("all_cities_stream_map1.2.html")
