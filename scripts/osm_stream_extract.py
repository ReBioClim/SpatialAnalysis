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

