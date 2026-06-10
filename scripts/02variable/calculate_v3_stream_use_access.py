from collections import defaultdict
import os

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import nearest_points
from sklearn.cluster import DBSCAN


segments = gpd.read_file("data/input/streamall_400m_segments_from_mouth_with_city.gpkg").to_crs("EPSG:25833")
roads = gpd.read_file("data/input/roads_merged.gpkg").to_crs("EPSG:25833")
poi_points = gpd.read_file("data/input/poi_points_merged.gpkg").to_crs("EPSG:25833")
poi_polygons = gpd.read_file("data/input/poi_polygons_merged.gpkg").to_crs("EPSG:25833")

output_path = "data/production/variables/v3_stream_use_access.gpkg"

cities = ["Dresden", "Poznan", "Jablonec", "Senica"]

stream_belt_m = 10
entry_cluster_eps_m = 10
programme_distance_m = 800
amenity_belt_m = 50
amenity_entry_m = 50

walkable_road_classes = {
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

programme_tags = {
    "school",
    "university",
    "college",
    "kindergarten",
    "childcare",
    "library",
    "theatre",
    "cinema",
    "arts_centre",
    "community_centre",
    "townhall",
    "public_building",
    "sports_centre",
    "sports_hall",
    "stadium",
    "pitch",
    "restaurant",
    "cafe",
    "fast_food",
    "bar",
    "food_court",
    "marketplace",
}

amenity_tags = {
    "bench",
    "picnic_table",
    "shelter",
    "drinking_water",
    "toilets",
    "viewpoint",
    "information_board",
    "bicycle_parking",
}

tag_columns = [
    "amenity",
    "leisure",
    "tourism",
    "shop",
    "office",
    "building",
    "landuse",
    "fclass",
    "class",
    "category",
    "type",
    "name",
]


def minmax(values):
    x = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    finite = x[np.isfinite(x)]
    if len(finite) == 0 or finite.max() <= finite.min():
        return np.zeros(len(x), dtype=float)
    out = (x - finite.min()) / (finite.max() - finite.min())
    out[~np.isfinite(out)] = 0
    return out


def geometry_lines(geom):
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    if isinstance(geom, MultiLineString):
        return list(geom.geoms)
    return []


def build_graph(roads_gdf):
    graph = nx.Graph()
    for geom in roads_gdf.geometry:
        for line in geometry_lines(geom):
            coords = list(line.coords)
            if len(coords) < 2:
                continue
            for a, b in zip(coords[:-1], coords[1:]):
                u = (round(a[0], 3), round(a[1], 3))
                v = (round(b[0], 3), round(b[1], 3))
                dist = Point(a).distance(Point(b))
                if dist <= 0:
                    continue
                if graph.has_edge(u, v):
                    graph[u][v]["weight"] = min(graph[u][v]["weight"], dist)
                else:
                    graph.add_edge(u, v, weight=dist)
    return graph


def snap_to_nodes(points, nodes, tree):
    if len(points) == 0:
        return [], np.array([])
    xy = np.column_stack([points.geometry.x, points.geometry.y])
    dist, idx = tree.query(xy, k=1)
    return [nodes[i] for i in idx], dist


def make_origin_lookup(origins, nodes, tree):
    snapped, snap_dist = snap_to_nodes(origins, nodes, tree)
    by_node = defaultdict(list)
    for i, (node, dist) in enumerate(zip(snapped, snap_dist)):
        by_node[node].append((i, float(dist)))
    return by_node


def count_reachable_from_entries(graph, entries, origins, threshold_m):
    if len(entries) == 0 or len(origins) == 0 or graph.number_of_nodes() == 0:
        return {}

    nodes = list(graph.nodes)
    tree = cKDTree(np.array(nodes, dtype=float))
    entry_nodes, entry_snap = snap_to_nodes(entries, nodes, tree)
    origin_lookup = make_origin_lookup(origins, nodes, tree)

    segment_entries = defaultdict(list)
    for i, (_, row) in enumerate(entries.iterrows()):
        segment_entries[row["segment400_id"]].append((entry_nodes[i], float(entry_snap[i])))

    counts = {}
    for segment_id, entry_data in segment_entries.items():
        source_nodes = {node for node, _ in entry_data}
        min_entry_snap = min(snap for _, snap in entry_data)
        lengths = nx.multi_source_dijkstra_path_length(
            graph,
            source_nodes,
            cutoff=threshold_m,
            weight="weight",
        )

        reached = set()
        for origin_node, network_dist in lengths.items():
            for origin_id, origin_snap in origin_lookup.get(origin_node, []):
                total_dist = min_entry_snap + network_dist + origin_snap
                if total_dist <= threshold_m:
                    reached.add(origin_id)

        counts[segment_id] = len(reached)

    return counts


def tag_text(row):
    parts = []
    for col in tag_columns:
        if col in row.index and pd.notna(row[col]):
            parts.append(str(row[col]).strip().lower())
    return " ".join(parts)


poi_polygons = poi_polygons.copy()
if len(poi_polygons):
    poi_polygons["geometry"] = poi_polygons.geometry.centroid

poi_all = gpd.GeoDataFrame(pd.concat([poi_points, poi_polygons], ignore_index=True), crs=poi_points.crs)
poi_all["tag_text"] = [tag_text(row) for _, row in poi_all.iterrows()]
poi_all["amenity_match"] = poi_all["tag_text"].apply(lambda text: next((tag for tag in amenity_tags if tag in text), None))
poi_all["programme_match"] = poi_all["tag_text"].apply(lambda text: next((tag for tag in programme_tags if tag in text), None))

results = []

for city in cities:
    print("city:", city)

    s = segments[segments["city"] == city].copy()
    r = roads[roads["city"] == city].copy()
    p = poi_all[poi_all["city"] == city].copy()

    out = s[["segment400_id", "merged_id", "city", "geometry"]].copy()
    out["stream_programme_access_count"] = 0.0
    out["stream_amenity_access_count"] = 0.0

    if len(s) == 0 or len(r) == 0 or len(p) == 0:
        results.append(out)
        continue

    if "fclass" in r.columns:
        road_class = r["fclass"].astype(str).str.lower()
        r = r[road_class.isin(walkable_road_classes)].copy()

    if len(r) == 0:
        results.append(out)
        continue

    segment_belts = gpd.GeoDataFrame(
        s[["segment400_id"]].copy(),
        geometry=s.geometry.buffer(stream_belt_m),
        crs=s.crs,
    )
    road_segment_pairs = gpd.sjoin(r[["geometry"]], segment_belts, predicate="intersects", how="inner")
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
    else:
        entries = gpd.GeoDataFrame(columns=["segment400_id", "geometry"], geometry="geometry", crs=s.crs)

    programme = p[p["programme_match"].notna()].copy()
    amenity = p[p["amenity_match"].notna()].copy()

    if len(programme) and len(entries):
        graph = build_graph(r)
        counts = count_reachable_from_entries(graph, entries, programme, programme_distance_m)
        out["stream_programme_access_count"] = out["segment400_id"].map(counts).fillna(0).astype(float)

    if len(amenity) and len(entries):
        stream_buffers = gpd.GeoDataFrame(
            s[["segment400_id"]].copy(),
            geometry=s.geometry.buffer(amenity_belt_m),
            crs=s.crs,
        )
        amenity_near_stream = gpd.sjoin(
            amenity[["amenity_match", "geometry"]],
            stream_buffers,
            predicate="within",
            how="inner",
        )

        if len(amenity_near_stream):
            if "index_right" in amenity_near_stream.columns:
                amenity_near_stream = amenity_near_stream.drop(columns=["index_right"])
            amenity_connected = gpd.sjoin_nearest(
                amenity_near_stream,
                entries[["geometry"]],
                how="inner",
                max_distance=amenity_entry_m,
                distance_col="entry_distance_m",
            )
            amenity_counts = amenity_connected.groupby("segment400_id").size()
            out["stream_amenity_access_count"] = out["segment400_id"].map(amenity_counts).fillna(0).astype(float)

    results.append(out)


all_data = pd.concat(results, ignore_index=True)
all_data["stream_programme_access_index"] = minmax(all_data["stream_programme_access_count"])
all_data["stream_amenity_access_index"] = minmax(all_data["stream_amenity_access_count"])

cols = [
    "segment400_id",
    "merged_id",
    "city",
    "stream_programme_access_count",
    "stream_programme_access_index",
    "stream_amenity_access_count",
    "stream_amenity_access_index",
    "geometry",
]
out = gpd.GeoDataFrame(all_data[cols], geometry="geometry", crs=segments.crs)
if os.path.exists(output_path):
    os.remove(output_path)
out.to_file(output_path, driver="GPKG")
