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


# 250709
# # create 100m buffer 

# clean 100m stream segments
stream100 = gpd.read_file("data/stream_segments/stream_segments_100m_with_attrs.gpkg",
                           layer="segments_100m_with_attrs", driver="GPKG")
cityboundary = gpd.read_file("data/city_boundaries/combined_city_boundaries.gpkg", driver = "GPKG")
cityboundary = cityboundary.to_crs(stream100.crs)
stream100_within_boundary = gpd.clip(stream100, cityboundary)
stream100_within_boundary["length"] = stream100_within_boundary.geometry.length

stream100_within_boundary["length"].hist() 

print(len(stream100_within_boundary))

stream100_segments_around100 = stream100_within_boundary[(stream100_within_boundary["length"] >= 99) & (stream100_within_boundary["length"] <= 101)].copy()
print(len(stream100_segments_around100))


# removed overlapped
stream100_segments_around100["geom_wkb"] = stream100_segments_around100.geometry.apply(lambda g: g.wkb)
stream100_segments_clean = stream100_segments_around100.sort_values("geom_wkb").drop_duplicates("geom_wkb")
stream100_segments_clean = stream100_segments_clean.drop(columns="geom_wkb").reset_index(drop=True)

print(len(stream100_segments_clean))



stream100_segments_clean["segment_id"] = range(1, len(stream100_segments_clean)+1)



stream100_segments_clean.to_file("data/stream_geometry/stream100_cleaned.gpkg", driver="GPKG")



print(len(stream100_segments_clean))

print(stream100_segments_clean.crs)

# 20250715
# replace Dresden data only, keep the rest stream data as it is

dresdenstream = gpd.read_file("data/Dresden_water/stream.gpkg", driver="GPKG")
print(dresdenstream["rohr_erl"].unique())
print(dresdenstream.crs)
print(dresdenstream.geometry.name)  

#['oberirdisch, aber überdeckt (z.B. Brücke, Bewuchs)' 'offen' 'verrohrt' 'durch Bauwerk als offenes Gewässer']

#oberirdisch, aber Ã¼berdeckt (z.B. Brücke, Bewuchs): above ground, but covered (e.g., bridge, vegetation)
#offen:open
#verrohrt: piped (enclosed in a pipe)
#durch Bauwerk als offenes GewÃ¤sser: open watercourse through a structure

# change the fieldname "gewna" as "name", create column city with value "Dresden", 
# create a column "tunnel", when field rohr_erl = verrohrt, add verrohrt

dresdenstream = dresdenstream.rename(columns={'gewna': 'name'})

dresdenstream['City'] = 'Dresden'

# assign 'verrohrt' where 'rohr_erl' == 'verrohrt', else keep as empty
dresdenstream['tunnel'] = dresdenstream['rohr_erl'].apply(
    lambda x: 'verrohrt' if x == 'verrohrt' else None
)
dresdenstream["id_d"] = range(1, len(dresdenstream)+1)


print(dresdenstream.columns.unique())
dresdenstream.to_file("data/Dresden_water/dresdenstream.gpkg", driver="GPKG")
dresdenstream = dresdenstream[["name", "City", "rohr_erl", "tunnel", "id_d", "geometry"]]

# select allblue when waterway is not river, and city is not dresden
allblue = gpd.read_file("data/stream_geometry/allblue_100plus.gpkg")
streamlines = allblue[~allblue["waterway"].isin(["river"])].copy()
streamlines_other3 = streamlines[~streamlines["City"].isin(["Dresden"])].copy()
print(streamlines_other3.crs)
print(dresdenstream.crs)

streamall = pd.concat([dresdenstream, streamlines_other3], ignore_index=True)
streamall = gpd.GeoDataFrame(streamall, geometry='geometry')

streamall.set_crs(dresdenstream.crs, inplace=True)

print(streamall.columns.unique())
print(streamall.crs)

streamall.to_file("data/stream_geometry/streamall.gpkg",driver="GPKG")
