import osmnx as ox
import geopandas as gpd
from pathlib import Path
import folium
import pandas as pd
from shapely.ops import linemerge, unary_union, split, snap
from shapely import union_all
from shapely.geometry import MultiLineString, LineString, Point, MultiPoint
from geopandas.tools import sjoin
import math



# 250630 following osm_stream_extract.py, the api stream data is more complete (with complete stream/drain/ditch included)

# if the allblue line - waterway = "drain" "ditch",  and it is not connected to any other waterway or allblue polygon , then it should be removed
allblue = gpd.read_file("data/stream_geometry/allblue.gpkg")

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





# 20250810 — rewrite from here: build 500m & 250m segments cleanly
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, MultiPoint, MultiLineString
from shapely.ops import linemerge, unary_union, split, snap

# --- Load base data ---
streamall = gpd.read_file("data/stream_geometry/streamall.gpkg", driver="GPKG")
cityboundary = gpd.read_file("data/city_boundaries/combined_city_boundaries.gpkg", driver="GPKG")

print("Streamall CRS:", streamall.crs)  # should be EPSG:4326
print("City boundary CRS:", cityboundary.crs)  # should be EPSG:432

# Project to a metric CRS for length/segmentation
metric_crs = "EPSG:25833"
s_proj = streamall.to_crs(metric_crs)
boundary_proj = cityboundary.to_crs(metric_crs)

# --- Normalize geometry as single-part lines ---
stream_exploded = s_proj.explode(ignore_index=True)

# Merge connected lines to continuous lines
merged_geom = linemerge(unary_union(stream_exploded.geometry))
print("Merged geometry type:", merged_geom.geom_type)

if isinstance(merged_geom, LineString):
    merged_lines = [merged_geom]
else:
    merged_lines = list(merged_geom.geoms)  # MultiLineString -> list[LineString]

print("Count of merged base lines:", len(merged_lines))


def cut_lines(lines, interval_m):
    """Cut a list of LineStrings into ~interval_m segments using snap+split.
    Returns a list of LineStrings in metric_crs.
    """
    segs = []
    for line in lines:
        if line.length <= interval_m:
            segs.append(line)
            continue
        distances = np.arange(interval_m, line.length, interval_m)
        cut_pts = [line.interpolate(d) for d in distances]
        if not cut_pts:
            segs.append(line)
            continue
        mp = MultiPoint(cut_pts)
        snapped = snap(line, mp, tolerance=1e-6)
        split_result = split(snapped, mp)
        segs.extend(list(split_result.geoms))
    return segs


def attach_attrs(segments_gdf, source_lines_gdf):
    """Spatially join attributes from source (slightly buffered) to segments.
    Keeps all original columns from streamall (including a pre-existing
    'segment_id' if present) and adds an extra 'orig_index' column that records
    the row number in the exploded source before join.
    """
    src = source_lines_gdf.copy()
    # preserve all original attributes and add a stable row id
    src = src.assign(orig_index=src.index)
    # tiny buffer (1 cm) in metric CRS for robust intersects
    src["geometry"] = src.geometry.buffer(0.01)
    joined = gpd.sjoin(segments_gdf, src, how="left", predicate="intersects")
    if "index_right" in joined.columns:
        joined = joined.drop(columns=["index_right"]) 
    return joined


def clean_within_boundary(segment_gdf, boundary_gdf, interval_m):
    """Clip to boundary, keep ~interval_m length (+/-1m), drop duplicates by WKB."""
    clipped = gpd.clip(segment_gdf, boundary_gdf)
    clipped["length_m"] = clipped.geometry.length
    around = clipped[(clipped["length_m"] >= interval_m - 1) & (clipped["length_m"] <= interval_m + 1)].copy()
    around["_wkb"] = around.geometry.apply(lambda g: g.wkb)
    dedup = around.sort_values("_wkb").drop_duplicates("_wkb").drop(columns="_wkb").reset_index(drop=True)
    return dedup


def dissolve_and_merge(gdf, id_col):
    """Dissolve by id, then linemerge MultiLineString to single LineString when possible."""
    tmp = gdf.dissolve(by=id_col, as_index=False, aggfunc="first")
    def _merge(g):
        if g is None:
            return g
        if g.geom_type == "MultiLineString":
            try:
                return linemerge(g)
            except Exception:
                return g
        return g
    tmp["geometry"] = tmp.geometry.apply(_merge)
    return gpd.GeoDataFrame(tmp, geometry="geometry", crs=gdf.crs)


# ----- 500 m segments -----
segs_500 = cut_lines(merged_lines, 500)
seg500_gdf = gpd.GeoDataFrame(geometry=segs_500, crs=metric_crs)
seg500_with_attrs = attach_attrs(seg500_gdf, stream_exploded)
seg500_clean = clean_within_boundary(seg500_with_attrs, boundary_proj, 500)
seg500_clean["segment_id_500"] = range(1, len(seg500_clean) + 1)
seg500_merged = dissolve_and_merge(seg500_clean, "segment_id_500")

# save 500 m
out500 = seg500_merged.to_crs(streamall.crs)
out500.to_file("data/stream_segments/streamall_segment500.gpkg", driver="GPKG")
print("500m segments:", len(out500))



# ----- 250 m segments -----
segs_250 = cut_lines(merged_lines, 250)
seg250_gdf = gpd.GeoDataFrame(geometry=segs_250, crs=metric_crs)
seg250_with_attrs = attach_attrs(seg250_gdf, stream_exploded)
seg250_clean = clean_within_boundary(seg250_with_attrs, boundary_proj, 250)
seg250_clean["segment_id_250"] = range(1, len(seg250_clean) + 1)
seg250_merged = dissolve_and_merge(seg250_clean, "segment_id_250")

# save 250 m
out250 = seg250_merged.to_crs(streamall.crs)
out250.to_file("data/stream_segments/streamall_segment250.gpkg", driver="GPKG")
print("250m segments:", len(out250))




#########
# 20250810 — rewrite from here: build 500m & 250m segments cleanly

streamall = gpd.read_file("data/stream_geometry/streamall.gpkg", driver="GPKG")
cityboundary = gpd.read_file("data/city_boundaries/combined_city_boundaries.gpkg", driver="GPKG")

stream_exploded = streamall.to_crs("EPSG:25833").explode(ignore_index=True)
boundary_proj = cityboundary.to_crs("EPSG:25833")

# merge connected lines to continuous lines
merged_geom = linemerge(unary_union(stream_exploded.geometry))
print(merged_geom.geom_type)
merged_lines = list(getattr(merged_geom, "geoms", [merged_geom]))

# build 500 m segments
segs_500 = []
for line in merged_lines:
    if line.length <= 500:
        segs_500.append(line)
        continue
    dists = np.arange(500, line.length, 500)
    if len(dists) == 0:
        segs_500.append(line)
        continue
    pts = [line.interpolate(float(d)) for d in dists]
    mp = MultiPoint(pts)
    snapped = snap(line, mp, tolerance=1e-6)
    parts = split(snapped, mp)
    segs_500.extend(list(parts.geoms))

seg500_gdf = gpd.GeoDataFrame(geometry=segs_500, crs="EPSG:25833")

# attach attrs 
src500 = stream_exploded.copy()
src500 = src500.assign(orig_index=src500.index)
src500["geometry"] = src500.geometry.buffer(0.01)  # 1 cm buffer for robust join
seg500_join = gpd.sjoin(seg500_gdf, src500, how="left", predicate="intersects")
if "index_right" in seg500_join.columns:
    seg500_join = seg500_join.drop(columns=["index_right"])

# clean within boundary (clip, keep ~500±1 m, dedup by WKB)
seg500_clip = gpd.clip(seg500_join, boundary_proj)
seg500_clip["length_m"] = seg500_clip.geometry.length
seg500_keep = seg500_clip[(seg500_clip["length_m"] >= 499) & (seg500_clip["length_m"] <= 501)].copy()
seg500_keep["_wkb"] = seg500_keep.geometry.apply(lambda g: g.wkb)
seg500_dedup = (
    seg500_keep.sort_values("_wkb")
    .drop_duplicates("_wkb")
    .drop(columns="_wkb")
    .reset_index(drop=True)
)

seg500_dedup["segment_id_500"] = range(1, len(seg500_dedup) + 1)

# dissolve+merge 
seg500_diss = seg500_dedup.dissolve(by="segment_id_500", as_index=False, aggfunc="first")
seg500_diss["geometry"] = seg500_diss.geometry.apply(
    lambda g: linemerge(g) if (g is not None and getattr(g, "geom_type", "") == "MultiLineString") else g
)
out500 = gpd.GeoDataFrame(seg500_diss, geometry="geometry", crs="EPSG:25833").to_crs(streamall.crs)
out500.to_file("data/stream_segments/streamall_segment500.gpkg", driver="GPKG")
print(len(out500))

####
# build 250 m segments
segs_250 = []
for line in merged_lines:
    if line.length <= 250:
        segs_250.append(line)
        continue
    dists = np.arange(250, line.length, 250)
    if len(dists) == 0:
        segs_250.append(line)
        continue
    pts = [line.interpolate(float(d)) for d in dists]
    mp = MultiPoint(pts)
    snapped = snap(line, mp, tolerance=1e-6)
    parts = split(snapped, mp)
    segs_250.extend(list(parts.geoms))

seg250_gdf = gpd.GeoDataFrame(geometry=segs_250, crs="EPSG:25833")

# attach attrs 
src250 = stream_exploded.copy()
src250 = src250.assign(orig_index=src250.index)
src250["geometry"] = src250.geometry.buffer(0.01)
seg250_join = gpd.sjoin(seg250_gdf, src250, how="left", predicate="intersects")
if "index_right" in seg250_join.columns:
    seg250_join = seg250_join.drop(columns=["index_right"])

# clean within boundary (clip, keep ~250±1 m, dedup by WKB)
seg250_clip = gpd.clip(seg250_join, boundary_proj)
seg250_clip["length_m"] = seg250_clip.geometry.length
seg250_keep = seg250_clip[(seg250_clip["length_m"] >= 249) & (seg250_clip["length_m"] <= 251)].copy()
seg250_keep["_wkb"] = seg250_keep.geometry.apply(lambda g: g.wkb)
seg250_dedup = (
    seg250_keep.sort_values("_wkb")
    .drop_duplicates("_wkb")
    .drop(columns="_wkb")
    .reset_index(drop=True)
)

seg250_dedup["segment_id_250"] = range(1, len(seg250_dedup) + 1)

# dissolve+merge
seg250_diss = seg250_dedup.dissolve(by="segment_id_250", as_index=False, aggfunc="first")
seg250_diss["geometry"] = seg250_diss.geometry.apply(
    lambda g: linemerge(g) if (g is not None and getattr(g, "geom_type", "") == "MultiLineString") else g
)
out250 = gpd.GeoDataFrame(seg250_diss, geometry="geometry", crs="EPSG:25833").to_crs(streamall.crs)
out250.to_file("data/stream_segments/streamall_segment250.gpkg", driver="GPKG")
print(len(out250))