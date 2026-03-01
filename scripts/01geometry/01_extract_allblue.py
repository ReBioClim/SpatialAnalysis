import geopandas as gpd
import osmnx as ox
import pandas as pd
import shapely.geometry as geom
from osmnx._overpass import _overpass_request
from shapely.ops import linemerge


# input
cities = [
    "Senica, Slovakia",
    "Poznań, Poland",
    "Jablonec nad Nisou, Czech Republic",
    "Dresden, Germany",
]


# collect waterways from osm
all_waterways = []
for place_name in cities:
    city_boundary = ox.geocode_to_gdf(place_name)
    polygon = city_boundary.geometry.values[0]
    if isinstance(polygon, geom.MultiPolygon):
        polygon = list(polygon.geoms)[0]

    poly_string = " ".join(f"{lat} {lon}" for lon, lat in polygon.exterior.coords)

    query = f"""
    [out:json][timeout:180];
    (
      way["waterway"~"^(stream|river|drain|ditch|canal|wadi)$"](poly:"{poly_string}");
      relation["waterway"~"^(stream|river|drain|ditch|canal|wadi)$"](poly:"{poly_string}");
      way["natural"="water"](poly:"{poly_string}");
      way["waterway"="basin"](poly:"{poly_string}");
      way["landuse"="reservoir"](poly:"{poly_string}");
      way["landuse"="basin"](poly:"{poly_string}");
    );
    (._;>;);
    out body;
    """

    # download full node-way-relation tree
    elements = _overpass_request(data={"data": query})["elements"]
    node_index = {e["id"]: (e["lon"], e["lat"]) for e in elements if e["type"] == "node"}
    landuse_map = {"reservoir": "reservoir_legacy", "basin": "basin_landuse"}

    all_way_geoms, way_rows = {}, []
    for e in elements:
        if e["type"] != "way":
            continue
        coords = [node_index[n] for n in e["nodes"] if n in node_index]
        if len(coords) < 2:
            continue
        g = (
            geom.Polygon(coords)
            if coords[0] == coords[-1] and len(coords) >= 4
            else geom.LineString(coords)
        )
        all_way_geoms[e["id"]] = g
        tags = e.get("tags", {})
        final_type = tags.get("waterway") or (
            tags.get("water", "water")
            if tags.get("natural") == "water"
            else landuse_map.get(tags.get("landuse"))
        )
        if not final_type:
            continue
        way_rows.append(
            {
                "osm_id": e["id"],
                "name": tags.get("name"),
                "waterway": final_type,
                "tunnel": tags.get("tunnel"),
                "geometry": g,
            }
        )

    rel_rows = []

    # rebuild relation geometry from member ways
    for e in elements:
        if e["type"] != "relation":
            continue
        tags = e.get("tags", {})
        final_type = tags.get("waterway") or (
            tags.get("water", "water")
            if tags.get("natural") == "water"
            else landuse_map.get(tags.get("landuse"))
        )
        if not final_type:
            continue
        parts = [
            all_way_geoms[m["ref"]]
            for m in e.get("members", [])
            if m["type"] == "way" and m["ref"] in all_way_geoms
        ]
        if not parts:
            continue
        line_parts = [p for p in parts if isinstance(p, (geom.LineString, geom.MultiLineString))]
        poly_parts = [p for p in parts if isinstance(p, (geom.Polygon, geom.MultiPolygon))]

        if line_parts:
            rel_rows.append(
                {
                    "osm_id": e["id"],
                    "name": tags.get("name"),
                    "waterway": final_type,
                    "tunnel": tags.get("tunnel"),
                    "geometry": linemerge(line_parts) if len(line_parts) > 1 else line_parts[0],
                }
            )

        if poly_parts:
            rel_rows.append(
                {
                    "osm_id": e["id"],
                    "name": tags.get("name"),
                    "waterway": final_type,
                    "tunnel": tags.get("tunnel"),
                    "geometry": geom.MultiPolygon(poly_parts) if len(poly_parts) > 1 else poly_parts[0],
                }
            )

    gdf_ways = gpd.GeoDataFrame(way_rows, crs="EPSG:4326")
    gdf_rels = gpd.GeoDataFrame(rel_rows, crs="EPSG:4326")
    waterways_all = pd.concat([gdf_ways, gdf_rels], ignore_index=True).to_crs(epsg=25833)

    # dissolve named waterways only
    named_waterways = waterways_all[waterways_all["name"].notna()]
    unnamed_waterways = waterways_all[waterways_all["name"].isna()]
    waterways_named_dissolved = named_waterways.dissolve(by="name", as_index=False)
    waterways_dissolve = pd.concat([waterways_named_dissolved, unnamed_waterways], ignore_index=True)

    city_name = {"Jablonec nad Nisou": "Jablonec", "Poznań": "Poznan"}.get(
        place_name.split(",")[0].strip(),
        place_name.split(",")[0].strip(),
    )
    waterways_dissolve["city"] = city_name
    all_waterways.append(waterways_dissolve)


# combine osm and dresden official data
combined_waterways = gpd.GeoDataFrame(pd.concat(all_waterways, ignore_index=True))
dresden_original = gpd.read_file("data/Dresden/Dresden_water/stream.gpkg", driver="GPKG")
dresden_final = dresden_original.rename(columns={"gewna": "name"})
dresden_final["city"] = "Dresden"
dresden_final["covering"] = dresden_final["rohr_erl"].apply(
    lambda x: "piped" if x == "verrohrt" else "open"
)
dresden_final["dresden_id"] = range(1, len(dresden_final) + 1)
dresden_final["waterway"] = "stream"
dresden_final["osm_id"] = None
dresden_final["source"] = "dresden_official"
dresden_final = dresden_final[
    ["name", "osm_id", "source", "waterway", "covering", "city", "dresden_id", "geometry"]
].copy()

combined_waterways["source"] = "osm"
combined_waterways["covering"] = combined_waterways["tunnel"].apply(
    lambda v: "piped" if v == "culvert" else ("covered" if v == "yes" else "open")
)
combined_waterways["dresden_id"] = None
combined_waterways = combined_waterways[
    ["name", "osm_id", "source", "waterway", "covering", "city", "dresden_id", "geometry"]
].copy()

osm_dresden_other = combined_waterways[
    (combined_waterways["city"] == "Dresden") & (combined_waterways["waterway"] != "stream")
]
osm_other_cities = combined_waterways[combined_waterways["city"] != "Dresden"]
all_waterways_combined = pd.concat([osm_other_cities, osm_dresden_other, dresden_final], ignore_index=True)
all_waterways_combined = gpd.GeoDataFrame(all_waterways_combined, geometry="geometry")
all_waterways_combined.set_crs(combined_waterways.crs, inplace=True)


# split geometrycollection
gc_mask = all_waterways_combined.geometry.geom_type == "GeometryCollection"
if gc_mask.any():
    new_features = []
    for _, row in all_waterways_combined[gc_mask].iterrows():
        for part in row.geometry.geoms:
            new_row = row.copy()
            new_row.geometry = part
            new_features.append(new_row)
    all_waterways_combined = all_waterways_combined[~gc_mask]
    if new_features:
        all_waterways_combined = pd.concat(
            [all_waterways_combined, gpd.GeoDataFrame(new_features, crs=all_waterways_combined.crs)],
            ignore_index=True,
        )
all_waterways_combined["pilot"] = "no"


# pilot rivers by name
mask_teplica = all_waterways_combined["name"].str.contains("teplica", case=False, na=False)
mask_bila = all_waterways_combined["name"].str.contains("bílá nisa", case=False, na=False)
mask_geber = all_waterways_combined["name"].str.contains("geberbach", case=False, na=False)
mask_pias = all_waterways_combined["name"].str.contains("piaśnica", case=False, na=False)

all_waterways_combined.loc[mask_teplica, "pilot"] = "yes"
all_waterways_combined.loc[mask_bila, "pilot"] = "yes"
all_waterways_combined.loc[mask_geber, "pilot"] = "yes"
all_waterways_combined.loc[mask_pias, "pilot"] = "yes"

columns = ["pilot"] + [col for col in all_waterways_combined.columns if col != "pilot"]
all_waterways_combined = all_waterways_combined[columns]
all_waterways_combined.to_file("data/stream_geometry/allblue.gpkg", driver="GPKG")