import os
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import nearest_points
from sklearn.cluster import DBSCAN


roads = gpd.read_file("data/input/roads_merged.gpkg").to_crs("EPSG:25833")
segments = gpd.read_file("data/input/streamall_400m_segments_from_mouth_with_city.gpkg").to_crs("EPSG:25833")
stops = gpd.read_file("data/input/transportation_merged.gpkg").to_crs("EPSG:25833")

output_path = "data/production/variables/v2_access_transport.gpkg"

cities = ["Dresden", "Poznan", "Jablonec", "Senica"]

stream_belt_m = 10
entry_cluster_eps_m = 10
stop_buffer_m = 400

excluded_road_classes = {
    "motorway",
    "motorway_link",
    "trunk",
    "trunk_link",
}


def geometry_lines(geom):
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    if isinstance(geom, MultiLineString):
        return list(geom.geoms)
    return []


results = []

for city in cities:
    print("city:", city)

    r = roads[roads["city"] == city].copy()
    s = segments[segments["city"] == city].copy()
    t = stops[stops["city"] == city].copy()

    s["entrance_count"] = 0.0
    s["stop_count"] = 0.0

    if len(r) == 0 or len(s) == 0:
        results.append(s)
        continue

    if "fclass" in r.columns:
        road_class = r["fclass"].astype(str).str.lower()
        r = r[~road_class.isin(excluded_road_classes)].copy()

    if len(r) == 0:
        results.append(s)
        continue

    segment_belts = gpd.GeoDataFrame(
        s[["segment400_id"]].copy(),
        geometry=s.geometry.buffer(stream_belt_m),
        crs=s.crs,
    )

    road_segment_pairs = gpd.sjoin(
        r[["geometry"]],
        segment_belts,
        predicate="intersects",
        how="inner",
    )

    belt_lookup = segment_belts.set_index("segment400_id").geometry.to_dict()
    entry_points = []

    for _, row in road_segment_pairs.iterrows():
        belt_geom = belt_lookup.get(row["segment400_id"])
        if belt_geom is None:
            continue
        for line in geometry_lines(row.geometry):
            if line.intersects(belt_geom):
                pt, _ = nearest_points(line, belt_geom)
                entry_points.append(pt)

    if entry_points:
        entry_gdf = gpd.GeoDataFrame({"geometry": entry_points}, geometry="geometry", crs=s.crs)
        coords = np.column_stack([entry_gdf.geometry.x, entry_gdf.geometry.y])
        labels = DBSCAN(eps=entry_cluster_eps_m, min_samples=1).fit_predict(coords)
        entry_gdf["cluster"] = labels
        centroids = entry_gdf.groupby("cluster").geometry.apply(lambda g: Point(g.x.mean(), g.y.mean()))
        entries = gpd.GeoDataFrame({"geometry": centroids.values}, geometry="geometry", crs=s.crs)
        entries = gpd.sjoin_nearest(entries, s, how="left")
        entrance_counts = entries.groupby("segment400_id").size()
        s["entrance_count"] = s["segment400_id"].map(entrance_counts).fillna(0).astype(float)

    if len(t):
        segment_buffers = gpd.GeoDataFrame(
            s[["segment400_id"]].copy(),
            geometry=s.geometry.buffer(stop_buffer_m),
            crs=s.crs,
        )
        joined = gpd.sjoin(t[["geometry"]], segment_buffers, predicate="within", how="inner")
        stop_counts = joined.groupby("segment400_id").size()
        s["stop_count"] = s["segment400_id"].map(stop_counts).fillna(0).astype(float)

    results.append(s)


all_data = pd.concat(results, ignore_index=True)

cols = ["segment400_id", "merged_id", "city", "entrance_count", "stop_count", "geometry"]
out = gpd.GeoDataFrame(all_data[cols], geometry="geometry", crs=all_data.crs)
if os.path.exists(output_path):
    os.remove(output_path)
out.to_file(output_path, driver="GPKG")
