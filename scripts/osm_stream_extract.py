import osmnx as ox
import geopandas as gpd
import pandas as pd
import shapely.geometry as geom
from shapely.ops import linemerge
from osmnx._overpass import _overpass_request
import folium
from folium.features import DivIcon

# city info
#place_name = "Dresden, Germany"                                # to change city name
#place_name = "Jablonec nad Nisou, Czech Republic"
#place_name = "Poznań, Poland"
place_name = "Senica, Slovakia"
city_boundary = ox.geocode_to_gdf(place_name)
polygon = city_boundary.geometry.values[0]

# overpass accept poly input (lan, lon)
def polygon_to_overpass_poly(poly): 
    if isinstance(poly, geom.MultiPolygon):
        poly = list(poly.geoms)[0]
    return " ".join(f"{lat} {lon}" for lon, lat in poly.exterior.coords)

# Overpass API query, seems the only way to get stream full data: way+relation
poly_string = polygon_to_overpass_poly(polygon)
query = f"""
[out:json][timeout:180];
(
  way["waterway"="stream"](poly:"{poly_string}");
  relation["waterway"="stream"](poly:"{poly_string}");
);
(._;>;);
out body;
"""

response_json = _overpass_request(data={"data": query})
elements = response_json["elements"]

# geometry extraction

node_index = {
    elt["id"]: (elt["lon"], elt["lat"])
    for elt in elements if elt["type"] == "node"
}

# extract way
way_geoms, way_ids, way_names = [], [], []
for elt in elements:
    if elt["type"] == "way" and elt.get("tags", {}).get("waterway") == "stream":
        coords = [node_index[n] for n in elt["nodes"] if n in node_index]
        if len(coords) >= 2:
            way_geoms.append(geom.LineString(coords))
            way_ids.append(elt["id"])
            way_names.append(elt["tags"].get("name"))

# extract relation
all_way_geoms = {
    elt["id"]: geom.LineString([node_index[n] for n in elt["nodes"] if n in node_index])
    for elt in elements if elt["type"] == "way"
}

rel_geoms, rel_ids, rel_names = [], [], []
for elt in elements:
    if elt["type"] == "relation" and elt.get("tags", {}).get("waterway") == "stream":
        parts = [all_way_geoms[m["ref"]] for m in elt.get("members", []) if m["type"] == "way" and m["ref"] in all_way_geoms]
        if parts:
            merged = linemerge(parts) if len(parts) > 1 else parts[0]
            rel_geoms.append(merged)
            rel_ids.append(elt["id"])
            rel_names.append(elt["tags"].get("name"))

# into GeoDataFrame 
gdf_ways = gpd.GeoDataFrame({"osm_id": way_ids, "name": way_names, "geometry": way_geoms}, crs="EPSG:4326")
gdf_rels = gpd.GeoDataFrame({"osm_id": rel_ids, "name": rel_names, "geometry": rel_geoms}, crs="EPSG:4326")
streams_all = pd.concat([gdf_ways, gdf_rels], ignore_index=True).to_crs(epsg=2180)  # to change city crs #poznan 2180 #other 25833


# only dissolve if name is not null
named_streams = streams_all[streams_all["name"].notna()]
unnamed_streams = streams_all[streams_all["name"].isna()]
streams_named_dissolved = named_streams.dissolve(by="name", as_index=False)
streams_dissolve = pd.concat([streams_named_dissolved, unnamed_streams], ignore_index=True)


# save streams_all to gpkg
streams_dissolve.to_file(f"streams_{place_name}.gpkg", layer="streams_dissolve", driver="GPKG") 

# check number of streams
print(f"Number of streams: {len(streams_dissolve)}")


# check for geometry duplicates, should be empty
duplicate_geoms = streams_dissolve[streams_dissolve.duplicated(subset=["geometry"], keep=False)]
print(duplicate_geoms)



# select focus stream
#focus_stream = "Geberbach"  # to change focus stream name
#focus_stream = "Bílá Nisa"
focus_stream = "Piaśnica"
#focus_stream = "Teplica"

####### visualise
streams_all_wgs = streams_dissolve.to_crs(epsg=4326)
streams_case_wgs = streams_all_wgs[streams_all_wgs["name"] == focus_stream]
city_boundary_wgs = city_boundary.to_crs(epsg=4326)

center = streams_case_wgs.geometry.unary_union.centroid
m = folium.Map(location=[center.y, center.x], zoom_start=13, tiles="CartoDB Positron")

def add_layer(gdf, name, color, alpha=0.4, weight=3):
    folium.GeoJson(
        gdf.__geo_interface__,
        name=name,
        style_function=lambda _: {
            "color": color,
            "weight": weight,
            "fillColor": color,
            "fillOpacity": alpha
        }
    ).add_to(m)

add_layer(streams_all_wgs, "All Streams", "skyblue", alpha=0.6, weight=2)
add_layer(city_boundary_wgs, "City Boundary", "black", alpha=0.0, weight=2)
add_layer(streams_case_wgs, f"Focus Stream: {focus_stream}", "palevioletred", alpha=0.9, weight=4)    

# add stream names tags
names_fg = folium.FeatureGroup(name="Stream Names")
for _, r in streams_all_wgs.dropna(subset=["name"]).iterrows():
    n = r["name"].strip(); g = r.geometry.centroid
    if n: folium.Marker([g.y, g.x], icon=DivIcon(icon_size=(150,12), icon_anchor=(0,6),
        html=f'<div style="font-size:8pt; color:lightblue;">{n}</div>')).add_to(names_fg)
names_fg.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save(f"case_intro_{place_name}_v1.1.html")           





#########
#for senica, since the Teplica is regarded as river in OSM, we need to extract the river data in this city. 
# i checked the city map and it seems teplica is the widest. if it is regarded as stream in our study, then other rivers are also streams.
import osmnx as ox
import geopandas as gpd
import pandas as pd
import shapely.geometry as geom
from shapely.ops import linemerge
from osmnx._overpass import _overpass_request
import folium
from folium.features import DivIcon

# city info
#place_name = "Dresden, Germany"                                # to change city name
#place_name = "Jablonec nad Nisou, Czech Republic"
#place_name = "Poznań, Poland"
place_name = "Senica, Slovakia"
city_boundary = ox.geocode_to_gdf(place_name)
polygon = city_boundary.geometry.values[0]

# overpass accept poly input (lan, lon)
def polygon_to_overpass_poly(poly): 
    if isinstance(poly, geom.MultiPolygon):
        poly = list(poly.geoms)[0]
    return " ".join(f"{lat} {lon}" for lon, lat in poly.exterior.coords)

# Overpass API query, seems the only way to get stream full data: way+relation
poly_string = polygon_to_overpass_poly(polygon)
query = f"""
[out:json][timeout:180];
(
  way["waterway"~"^(stream|river)$"](poly:"{poly_string}");
  relation["waterway"~"^(stream|river)$"](poly:"{poly_string}");
);
(._;>;);
out body;
"""

response_json = _overpass_request(data={"data": query})
elements = response_json["elements"]

# geometry extraction

node_index = {
    elt["id"]: (elt["lon"], elt["lat"])
    for elt in elements if elt["type"] == "node"
}

# extract way
way_geoms, way_ids, way_names = [], [], []
for elt in elements:
    if elt["type"] == "way" and elt.get("tags", {}).get("waterway") in ["stream", "river"]:
        coords = [node_index[n] for n in elt["nodes"] if n in node_index]
        if len(coords) >= 2:
            way_geoms.append(geom.LineString(coords))
            way_ids.append(elt["id"])
            way_names.append(elt["tags"].get("name"))

# extract relation
all_way_geoms = {
    elt["id"]: geom.LineString([node_index[n] for n in elt["nodes"] if n in node_index])
    for elt in elements if elt["type"] == "way"
}

rel_geoms, rel_ids, rel_names = [], [], []
for elt in elements:
    if elt["type"] == "relation" and elt.get("tags", {}).get("waterway") in ["stream", "river"]:  #both stream and river
        parts = [all_way_geoms[m["ref"]] for m in elt.get("members", []) if m["type"] == "way" and m["ref"] in all_way_geoms]
        if parts:
            merged = linemerge(parts) if len(parts) > 1 else parts[0]
            rel_geoms.append(merged)
            rel_ids.append(elt["id"])
            rel_names.append(elt["tags"].get("name"))

# into GeoDataFrame 
gdf_ways = gpd.GeoDataFrame({"osm_id": way_ids, "name": way_names, "geometry": way_geoms}, crs="EPSG:4326")
gdf_rels = gpd.GeoDataFrame({"osm_id": rel_ids, "name": rel_names, "geometry": rel_geoms}, crs="EPSG:4326")
streams_all = pd.concat([gdf_ways, gdf_rels], ignore_index=True).to_crs(epsg=25833)  # to change city crs #poznan 2180 #other 25833

######



# only dissolve if name is not null
named_streams = streams_all[streams_all["name"].notna()]
unnamed_streams = streams_all[streams_all["name"].isna()]
streams_named_dissolved = named_streams.dissolve(by="name", as_index=False)
streams_dissolve = pd.concat([streams_named_dissolved, unnamed_streams], ignore_index=True)


# save streams_all to gpkg
streams_dissolve.to_file(f"streams_{place_name}.gpkg", layer="streams_dissolve", driver="GPKG") 

# check number of streams
print(f"Number of streams: {len(streams_dissolve)}")


# check for geometry duplicates, should be empty
duplicate_geoms = streams_dissolve[streams_dissolve.duplicated(subset=["geometry"], keep=False)]
print(duplicate_geoms)






# select focus stream
#focus_stream = "Geberbach"  # to change focus stream name
#focus_stream = "Bílá Nisa"
#focus_stream = "Piaśnica"
focus_stream = "Teplica"

####### visualise
streams_all_wgs = streams_dissolve.to_crs(epsg=4326)
streams_case_wgs = streams_all_wgs[streams_all_wgs["name"] == focus_stream]
city_boundary_wgs = city_boundary.to_crs(epsg=4326)

center = streams_case_wgs.geometry.unary_union.centroid
m = folium.Map(location=[center.y, center.x], zoom_start=13, tiles="CartoDB Positron")

def add_layer(gdf, name, color, alpha=0.4, weight=3):
    folium.GeoJson(
        gdf.__geo_interface__,
        name=name,
        style_function=lambda _: {
            "color": color,
            "weight": weight,
            "fillColor": color,
            "fillOpacity": alpha
        }
    ).add_to(m)

add_layer(streams_all_wgs, "All Streams", "skyblue", alpha=0.6, weight=2)
add_layer(city_boundary_wgs, "City Boundary", "black", alpha=0.0, weight=2)
add_layer(streams_case_wgs, f"Focus Stream: {focus_stream}", "palevioletred", alpha=0.9, weight=4)    

# add stream names tags
names_fg = folium.FeatureGroup(name="Stream Names")
for _, r in streams_all_wgs.dropna(subset=["name"]).iterrows():
    n = r["name"].strip(); g = r.geometry.centroid
    if n: folium.Marker([g.y, g.x], icon=DivIcon(icon_size=(150,12), icon_anchor=(0,6),
        html=f'<div style="font-size:8pt; color:lightblue;">{n}</div>')).add_to(names_fg)
names_fg.add_to(m)

folium.LayerControl(collapsed=False).add_to(m)
m.save(f"case_intro_{place_name}_v1.1.html")           


#####


####### convert multiline string to single line string
# Load data
city_name = "Dresden"
target_crs = 25833  # poznan 2180

import geopandas as gp
from shapely.geometry import LineString, MultiLineString

def explode_multilines(gdf):
    rows = []
    for idx, row in gdf.iterrows():
        geom = row.geometry
        if isinstance(geom, LineString):
            rows.append(row)
        elif isinstance(geom, MultiLineString):
            for part in geom.geoms:
                new_row = row.copy()
                new_row.geometry = part
                rows.append(new_row)
    return gp.GeoDataFrame(rows, crs=gdf.crs)

streams = gp.read_file(f"streams_{city_name}.gpkg").to_crs(epsg=target_crs)
streams_clean = explode_multilines(streams)
streams_clean.to_file("streams_lines_only.gpkg", driver="GPKG")
print(f"Number of lines in streams_clean: {len(streams)}")


######0509&0511 explode stream multilinestring→single linestring
## still need to do, check if there are any duplicates
import geopandas as gpd

city_name = "Dresden"
multiline = gpd.read_file(f"streams_{city_name}_multi.gpkg")


singleline = multiline.explode(index_parts=True, ignore_index=True)  # multilinestring to linestring

singleline.to_file(f"streams_{city_name}_singleline.gpkg", driver="GPKG")  

# check for geometry duplicates, should be empty
singleline = gpd.read_file(f"streams_{city_name}_singleline.gpkg")
duplicate_geoms = singleline[singleline.duplicated(subset=["geometry"], keep=False)]
print(duplicate_geoms)
duplicate_geoms.to_file("duplicate_streams.gpkg", driver="GPKG")

#Senica, two duplicates removed; Poznan, 3 duplicates removed; Jablonec, 1 duplicate removed; Dresden, 1 duplicates removed

# if disolved, then multi linestring again

####### 20250526
# add Drain and Culvert to the stream
import os
import osmnx as ox
import geopandas as gpd
import pandas as pd

#city_name = "Dresden"
#city_name = "Jablonec"
city_name = "Poznan"
#city_name = "Senica"

streams_only = gpd.read_file(f"data/streams_{city_name}_singleline.gpkg")
target_crs = 2180  # poznan 2180 #other 25833  
#place_name = "Dresden, Germany"
#place_name = "Jablonec nad Nisou, Czech Republic"
place_name = "Poznań, Poland"
#place_name = "Senica, Slovakia"
                
out_dir     = "data"                  


streams_fp   = os.path.join(out_dir, f"streams_{city_name}_singleline.gpkg")
streams_only = gpd.read_file(streams_fp).to_crs(target_crs)


tags_culvert_drain = {
    "waterway": ["drain", "ditch"],
    "tunnel":   ["culvert"],
    #"man_made": ["culvert", "drain"]
}

tags_water = {
    "natural": ["water"]
}

tags_river = {
    "waterway": ["river"],
    "natural":  ["water"],
    "water":    ["river"]
}


def fetch_and_save(tag_dict, label):
    gdf = ox.features_from_place(place_name, tags=tag_dict).to_crs(target_crs)

    # river: extra filtering
    if label == "river":
        gdf = gdf[(gdf["waterway"] == "river") | (gdf["water"] == "river")]

    fp = os.path.join(out_dir, f"{label}_{city_name}.gpkg")
    gdf.to_file(fp, driver="GPKG")
    print(f"[{label:15}] {len(gdf):6} features  →  {os.path.basename(fp)}")
    return gdf

gdf_cd  = fetch_and_save(tags_culvert_drain, "culvert_drain")
gdf_wtr = fetch_and_save(tags_water,        "water")
gdf_riv = fetch_and_save(tags_river,        "river")


combined = gpd.GeoDataFrame(
    pd.concat([
        streams_only.assign(source="streams"),
        gdf_cd      .assign(source="culvert_drain"),
        gdf_wtr     .assign(source="water"),
        gdf_riv     .assign(source="river")
    ], ignore_index=True),
    crs=target_crs
).drop_duplicates(subset="geometry")

combined_stream = os.path.join(out_dir, f"{city_name}_combined_allblue.gpkg")
combined.to_file(combined_stream, driver="GPKG")


# 1) combine LineString / MultiLineString 
line_union = combined[
    combined.geometry.geom_type.isin(["LineString", "MultiLineString"])
].geometry.unary_union

# 2) check if line_union is empty
if line_union.is_empty:
    combined_clean = combined.copy()
else:
    # 2) 
    def keep_feature(geom):
        if geom.geom_type in ("Polygon", "MultiPolygon"):
            return geom.intersects(line_union)   # only keep polygons that intersect with the line_union
        else:
            return True                          # keep all LineString / MultiLineString features

    keep_mask = combined.geometry.apply(keep_feature)

    # 3) filter
    combined_clean = combined[keep_mask].copy()
    dropped = len(combined) - len(combined_clean)

# 4) write to file
clean_fp = os.path.join(out_dir, f"{city_name}_combined_clean.gpkg")
combined_clean.to_file(clean_fp, driver="GPKG")
print(f"✔  写入 {os.path.basename(clean_fp)}")

# 4) with point
clean_fp_with_points = os.path.join(out_dir, f"{city_name}_combined_clean.gpkg")
combined_clean.to_file(clean_fp_with_points, driver="GPKG")

non_point_mask = ~combined_clean.geometry.geom_type.isin(["Point", "MultiPoint"])
combined_nopt = combined_clean[non_point_mask].copy()

dropped_pts = len(combined_clean) - len(combined_nopt)

# nopint
final_fp = os.path.join(out_dir, f"{city_name}_combined_clean_nopt.gpkg")
combined_nopt.to_file(final_fp, driver="GPKG")
