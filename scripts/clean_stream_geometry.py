import osmnx as ox
import geopandas as gpd
from pathlib import Path
import folium
import pandas as pd
from shapely.ops import linemerge, unary_union
from shapely import union_all
from shapely.geometry import MultiLineString, LineString, Point
from geopandas.tools import sjoin


# 250630 following osm_stream_extract.py, the api stream data is more complete (with complete stream/drain/ditch included)
# merge into one allblue geometry
cities = ["Dresden", "Senica", "Poznan", "Jablonec"]

base_path = Path("data/stream_geometry/archived")

target_crs = "EPSG:4326"

gdfs = []

for city in cities:
    file_path = base_path / f"{city}_combined_clean_nopt.gpkg"
    gdf = gpd.read_file(file_path)
    gdf = gdf.to_crs(target_crs)  
    gdf["City"] = city
    gdfs.append(gdf)

combined_gdf = gpd.GeoDataFrame(pd.concat(gdfs, ignore_index=True), crs=target_crs)

combined_gdf.to_file("allblue.gpkg", driver="GPKG")


# if the allblue line - waterway = "drain" "ditch",  and it is not connected to any other waterway or allblue polygon , then it should be removed
allblue = gpd.read_file("allblue.gpkg")

allblue_lines = allblue[allblue.geometry.type == "LineString"].copy()
allblue_polygons = allblue[allblue.geometry.type == "Polygon"].copy()

ditch_lines = allblue_lines[allblue_lines["waterway"].isin(["drain", "ditch"])].copy()

other_lines = allblue_lines[~allblue_lines.index.isin(ditch_lines.index)].copy()

sindex_lines = other_lines.sindex
sindex_polys = allblue_polygons.sindex

connected_flags = []

for geom in ditch_lines.geometry:
    connected_to_line = any(
        other_lines.iloc[list(sindex_lines.intersection(geom.bounds))].intersects(geom)
    )
    connected_to_poly = any(
        allblue_polygons.iloc[list(sindex_polys.intersection(geom.bounds))].intersects(geom)
    )
    connected_flags.append(connected_to_line or connected_to_poly)

ditch_lines["connected"] = connected_flags
ditch_lines_clean = ditch_lines[ditch_lines["connected"]].copy()

final = gpd.GeoDataFrame(
    pd.concat([other_lines, ditch_lines_clean, allblue_polygons], ignore_index=True),
    crs=allblue.crs
)

final.to_file("allblue_cleaned.gpkg", driver="GPKG")

# 
city_boundary = gpd.read_file("data/city_boundaries/combined_city_boundaries.gpkg")
catchment = gpd.read_file("data/catchment/intersected_catchments.gpkg")


# 250701
gdf = gpd.read_file("allblue_cleaned.gpkg")
print(gdf.crs)  # EPSG:4326
waterlines = gdf[gdf.geometry.type == "LineString"].copy()
print(len(waterlines))   # n=19263

# dissolve by name, if no name, then still keep the geometry
has_name = waterlines[waterlines["name"].notna()]
no_name = waterlines[waterlines["name"].isna()]

waterlines_dissolve = pd.concat([
    has_name.dissolve(by="name", as_index=False, aggfunc="first"),
    no_name
], ignore_index=True)
print(len(waterlines_dissolve))  # n=1585

waterlines_dissolve.to_file("waterlines.gpkg", driver="GPKG")


# merge to continuous lines
projected = waterlines_dissolve.to_crs("EPSG:25833")  # UTM zone 33N
merged_union = union_all(projected.geometry)
merged_lines = linemerge(merged_union)
print(merged_lines.geom_type)  # MultiLineString

# filter lines by length, 100m
long_lines = [line for line in merged_lines.geoms if line.length >= 100]
print(len(long_lines)) # n=1206 minimum length = 100.47m

long_gdf = gpd.GeoDataFrame(geometry=long_lines, crs="EPSG:25833")
print(long_gdf.head())
long_gdf = long_gdf.to_crs("EPSG:4326")  # convert back to WGS84
long_gdf.to_file("long_lines.gpkg", driver="GPKG")


water_proj = waterlines_dissolve.to_crs("EPSG:25833")
long_proj = gpd.GeoDataFrame(geometry=long_lines, crs="EPSG:25833")

# union_all → linemerge, creates new geometries by combining lines. 
# These new lines have recomputed coordinates, so they don’t exactly match the original lines.
# Even they look the same, spatial operations like intersects() or overlay() fail to detect overlap.

sindex = long_proj.sindex

matched_idx = water_proj.geometry.apply(
    lambda geom: any(long_proj.iloc[list(sindex.intersection(geom.bounds))].intersects(geom))
)

intersected_lines = water_proj[matched_idx].copy()
print(len(intersected_lines))  # n=1367

intersected_lines = intersected_lines[["name", "osm_id", "source", "waterway", "layer", "tunnel", "City", "geometry"]].copy()
print(intersected_lines.head())

# find the shortest river for waterway=river (i checked the geometry and there is a wierd short river next to Priebniez, better to delete)
# Remove the shortest river line
riverlines = intersected_lines[intersected_lines["waterway"] == "river"].copy()
river_proj = riverlines.to_crs("EPSG:25833")
river_proj["length_m"] = river_proj.geometry.length
shortest_idx = river_proj.sort_values("length_m").index[0]
intersected_lines = intersected_lines.drop(index=shortest_idx)

intersected_lines.loc[intersected_lines["source"] == "streams", "waterway"] = "stream"

# and need to filter out the lines <100m again
intersected_lines1 = intersected_lines.to_crs("EPSG:25833")
intersected_lines1["length_m"] = intersected_lines.geometry.length
intersected_lines1 = intersected_lines[intersected_lines["length_m"] >= 100].copy()
intersected_lines1.drop(columns="length_m", inplace=True)

print(len(intersected_lines1))  # n=738
intersected_lines.to_file("allblue_100plus.gpkg", driver="GPKG")

allblue = gpd.read_file("allblue_100plus.gpkg")
allblue = intersected_lines.to_crs("EPSG:4326")  # convert back to WGS84
streamlines = allblue[allblue["waterway"] == "stream"].copy()
riverlines = allblue[allblue["waterway"] == "river"].copy()
otherwaterways = allblue[~allblue["waterway"].isin(["stream", "river"])].copy()
waterpolygons = gdf[gdf.geometry.type == "Polygon"].copy()
print(len(streamlines), len(riverlines), len(otherwaterways), len(waterpolygons))  
# 612 10 116 475

#######

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


## underground waterways
# there was another old version 250630

#250704
from pathlib import Path
import osmnx as ox
import geopandas as gpd
import pandas as pd

# List of cities
cities = [
    "Dresden, Germany",
    "Senica, Slovakia",
    "Poznań, Poland",
    "Jablonec nad Nisou, Czech Republic"
]

# Output directory
output_dir = Path("underground_streams_gpkg")
output_dir.mkdir(exist_ok=True)

# Store data from all cities
all_data = []

# Process each city
for city in cities:
    city_name = city.split(",")[0].strip()

    # name override
    name_overrides = {
    "Jablonec nad Nisou": "Jablonec",
    "Poznań": "Poznan"}
    city_name = name_overrides.get(city_name, city_name)


    city_slug = city_name.lower().replace(" ", "_")
    
    print(f"Processing {city_name}...")

    # get city boundary
    boundary = ox.geocode_to_gdf(city)

    # fetch waterway features
    water_features = ox.features_from_place(city, {"waterway": True})
    water_features = water_features[water_features.geometry.type.isin(["LineString", "MultiLineString"])]

    # ensure required columns exist
    for col in ["tunnel", "covered", "location", "layer", "waterway"]:
        if col not in water_features.columns:
            water_features[col] = None

    layer_str = water_features["layer"].astype(str)

    # filter for underground streams 
    underground = water_features[
        (
            water_features["tunnel"].isin(["yes", "culvert"]) |
            water_features["covered"].isin(["yes", "true", "1"]) |
            layer_str.isin(["-1", "-2"])
        ) &
        water_features["waterway"].notna()
    ].copy()

    underground["City"] = city_name  # Add city info

    all_data.append(underground)

# merge
all_underground = gpd.GeoDataFrame(pd.concat(all_data, ignore_index=True))
all_underground = all_underground[all_underground.geometry.notnull()]

summary = all_underground.groupby(["City", "waterway"]).size().unstack(fill_value=0)
print("\nFeature count per city per waterway type:\n")
print(summary)

all_underground.to_file("data/stream_geometry/all_blue.gpkg", driver="GPKG", layer = "underground")

# 250708
dresdenstream = gpd.read_file("data/Dresden_water/stream.gpkg", driver="GPKG")
print(dresdenstream["rohr_erl"].unique())

#>>> print(dresdenstream["rohr_erl"].unique())
#['oberirdisch, aber überdeckt (z.B. Brücke, Bewuchs)' 'offen' 'verrohrt' 'durch Bauwerk als offenes Gewässer']

# still need to add this Dresden official data as stream geometry. 
# It covers more watercourses. Still need to check which types should be included. 
# But not now. We do it after all four cities verified the stream geometry data.