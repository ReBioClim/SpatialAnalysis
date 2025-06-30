import osmnx as ox
import geopandas as gpd
from pathlib import Path
import folium

cities = [
    "Dresden, Germany",
    "Senica, Slovakia",
    "Poznań, Poland",
    "Jablonec nad Nisou, Czech Republic"
]

output_dir = Path("underground_streams_gpkg")
output_dir.mkdir(exist_ok=True)

valid_types = ["stream", "drain", "river", "canal"] # Define valid waterway types for underground streams

for city in cities:
    city_slug = city.split(",")[0].lower().replace(" ", "_")
    boundary = ox.geocode_to_gdf(city)
    gdf = ox.features_from_place(city, {"waterway": True})
    lines = gdf[gdf.geometry.type == "LineString"].copy()

    underground = lines[
        (
            lines.get("tunnel").notna() |
            (lines.get("covered") == "yes") |
            (lines.get("location") == "underground")
        ) &
        (lines.get("waterway").isin(valid_types))
    ].copy()

    underground.to_file(output_dir / f"{city_slug}_underground_streams.gpkg", driver="GPKG")

    print(f"\n{city}")
    for col in ["waterway", "tunnel", "covered", "location"]:
        if col in underground.columns:
            counts = underground[col].value_counts(dropna=True)
            if not counts.empty:
                print(f"{col}:\n{counts.to_string()}\n")

import geopandas as gpd
import pandas as pd
from pathlib import Path

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
gdf = gpd.read_file("allblue_cleaned.gpkg")

waterlines = gdf[gdf.geometry.type == "LineString"]
waterpolygons = gdf[gdf.geometry.type == "Polygon"]

streamlines = waterlines[waterlines["waterway"].isin(["stream"])].copy()
streamlines = waterlines[waterlines["waterway"].isin(["stream", "canal", "drain", "ditch"])].copy()


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

# 3. All water lines
folium.GeoJson(waterlines, name="All water lines",
               style_function=lambda x: {"color": "royalblue", "weight": 2.5}).add_to(m)

# 4. All waterbodies
folium.GeoJson(waterpolygons, name="All waterbodies",
               style_function=lambda x: {"color": "lightsteelblue", "weight": 1, "dashArray": "4, 4"}).add_to(m)

# 5. Waterbodies


folium.LayerControl(collapsed=False).add_to(m)

m.save("all_cities_stream_map1.html")

