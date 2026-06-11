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
buildings = gpd.read_file("data/25833/buildings_merged.gpkg").to_crs("EPSG:25833")
transport = gpd.read_file("data/input/transportation_merged.gpkg").to_crs("EPSG:25833")

output_path = "data/production/variables/v3_building_transport_stream_access.gpkg"

cities = ["Dresden", "Poznan", "Jablonec", "Senica"]

stream_belt_m = 10
entry_cluster_eps_m = 10
building_distance_m = 800
transport_distance_m = 400
max_search_m = 1200

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


def accessibility_from_entries(graph, entries, origins, threshold_m, cutoff_m):
    if len(entries) == 0 or len(origins) == 0 or graph.number_of_nodes() == 0:
        return {}, {}

    nodes = list(graph.nodes)
    tree = cKDTree(np.array(nodes, dtype=float))
    entry_nodes, entry_snap = snap_to_nodes(entries, nodes, tree)
    origin_lookup = make_origin_lookup(origins, nodes, tree)

    segment_entries = defaultdict(list)
    for i, (_, row) in enumerate(entries.iterrows()):
        segment_entries[row["segment400_id"]].append((entry_nodes[i], float(entry_snap[i])))

    exposure = {}
    min_distance = {}

    for segment_id, entry_data in segment_entries.items():
        source_node = ("source", segment_id)
        for entry_node, entry_snap_dist in entry_data:
            graph.add_edge(source_node, entry_node, weight=entry_snap_dist)

        lengths = nx.single_source_dijkstra_path_length(
            graph,
            source_node,
            cutoff=cutoff_m,
            weight="weight",
        )
        graph.remove_node(source_node)

        reached = set()
        best = []
        for origin_node, network_dist in lengths.items():
            for origin_id, origin_snap in origin_lookup.get(origin_node, []):
                total_dist = network_dist + origin_snap
                if total_dist <= threshold_m:
                    reached.add(origin_id)
                if total_dist <= cutoff_m:
                    best.append(total_dist)

        exposure[segment_id] = len(reached)
        min_distance[segment_id] = float(np.nanmin(best)) if best else np.nan

    return exposure, min_distance


results = []

for city in cities:
    print("city:", city)

    s = segments[segments["city"] == city].copy()
    r = roads[roads["city"] == city].copy()
    b = buildings[buildings["city"] == city].copy()
    t = transport[transport["city"] == city].copy()

    out = s[["segment400_id", "merged_id", "city", "geometry"]].copy()
    out["building_stream_exposure_800m"] = 0.0
    out["building_min_network_distance_m"] = np.nan
    out["transport_stream_exposure_400m"] = 0.0
    out["transport_min_network_distance_m"] = np.nan

    if len(s) == 0 or len(r) == 0:
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

    if not entry_points:
        results.append(out)
        continue

    entry_gdf = gpd.GeoDataFrame({"geometry": entry_points}, geometry="geometry", crs=s.crs)
    coords = np.column_stack([entry_gdf.geometry.x, entry_gdf.geometry.y])
    labels = DBSCAN(eps=entry_cluster_eps_m, min_samples=1).fit_predict(coords)
    entry_gdf["cluster"] = labels
    centroids = entry_gdf.groupby("cluster").geometry.apply(lambda g: Point(g.x.mean(), g.y.mean()))
    entries = gpd.GeoDataFrame({"geometry": centroids.values}, geometry="geometry", crs=s.crs)
    entries = gpd.sjoin_nearest(entries, s, how="left")

    graph = build_graph(r)

    if len(b):
        building_origins = b.copy()
        building_origins["geometry"] = building_origins.geometry.representative_point()
        exposure, min_distance = accessibility_from_entries(
            graph,
            entries,
            building_origins,
            building_distance_m,
            max_search_m,
        )
        out["building_stream_exposure_800m"] = out["segment400_id"].map(exposure).fillna(0).astype(float)
        out["building_min_network_distance_m"] = out["segment400_id"].map(min_distance)

    if len(t):
        exposure, min_distance = accessibility_from_entries(
            graph,
            entries,
            t,
            transport_distance_m,
            max_search_m,
        )
        out["transport_stream_exposure_400m"] = out["segment400_id"].map(exposure).fillna(0).astype(float)
        out["transport_min_network_distance_m"] = out["segment400_id"].map(min_distance)

    results.append(out)


all_data = pd.concat(results, ignore_index=True)
out = gpd.GeoDataFrame(all_data, geometry="geometry", crs=segments.crs)
if os.path.exists(output_path):
    os.remove(output_path)
out.to_file(output_path, driver="GPKG")
