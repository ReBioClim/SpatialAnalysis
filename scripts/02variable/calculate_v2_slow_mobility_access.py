import os
import geopandas as gpd
import pandas as pd


roads = gpd.read_file("data/input/roads_merged.gpkg").to_crs("EPSG:25833")
segments = gpd.read_file("data/input/streamall_400m_segments_from_mouth_with_city.gpkg").to_crs("EPSG:25833")

output_path = "data/production/variables/v2_access_slowmob.gpkg"

cities = ["Dresden", "Poznan", "Jablonec", "Senica"]

buffer_m = 400

slowmob_classes = {
    "footway",
    "path",
    "pedestrian",
    "steps",
    "cycleway",
    "bridleway",
    "living_street",
    "residential",
    "service",
    "unclassified",
    "track",
    "track_grade1",
    "track_grade2",
    "track_grade3",
    "track_grade4",
    "track_grade5",
}


results = []

for city in cities:
    print("city:", city)

    r = roads[roads["city"] == city].copy()
    s = segments[segments["city"] == city].copy()

    s["slowMob_length"] = 0.0

    if len(r) == 0 or len(s) == 0:
        results.append(s)
        continue

    if "fclass" in r.columns:
        road_class = r["fclass"].astype(str).str.lower()
        slow = r[road_class.isin(slowmob_classes)].copy()
    else:
        slow = r.iloc[0:0].copy()

    if len(slow) == 0:
        results.append(s)
        continue

    segment_buffers = gpd.GeoDataFrame(
        s[["segment400_id"]].copy(),
        geometry=s.geometry.buffer(buffer_m),
        crs=s.crs,
    )

    pairs = gpd.sjoin(
        slow[["geometry"]],
        segment_buffers,
        predicate="intersects",
        how="inner",
    )

    if len(pairs) == 0:
        results.append(s)
        continue

    buffer_lookup = segment_buffers.set_index("segment400_id").geometry.to_dict()
    pairs["intersect_length"] = [
        geom.intersection(buffer_lookup[sid]).length
        for geom, sid in zip(pairs.geometry, pairs["segment400_id"])
    ]

    lengths = pairs.groupby("segment400_id")["intersect_length"].sum()
    s["slowMob_length"] = s["segment400_id"].map(lengths).fillna(0).astype(float)

    results.append(s)


all_data = pd.concat(results, ignore_index=True)

cols = ["segment400_id", "merged_id", "city", "slowMob_length", "geometry"]
out = gpd.GeoDataFrame(all_data[cols], geometry="geometry", crs=all_data.crs)
if os.path.exists(output_path):
    os.remove(output_path)
out.to_file(output_path, driver="GPKG")
