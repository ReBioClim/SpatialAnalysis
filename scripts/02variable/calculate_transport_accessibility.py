import geopandas as gpd
import numpy as np
import pandas as pd
import pandana as pdna
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import nearest_points
from sklearn.cluster import DBSCAN


roads = gpd.read_file("data/input/roads_merged.gpkg")
segments = gpd.read_file("data/input/streamall_400m_segments_from_mouth_with_city.gpkg")
stops = gpd.read_file("data/input/transportation_merged.gpkg")

output_path = "data/production/variables/v2_access_transport.gpkg"

cities = ["Dresden", "Poznan", "Jablonec", "Senica"]

stream_belt = 10
road_tol = 30
cluster_eps = 15

max_dist = 1000
walk_speed = 1.2
gamma = 0.3
max_stops = 120


def minmax(x):
    v = x[np.isfinite(x)]
    if len(v) == 0:
        return np.zeros_like(x)
    mn, mx = v.min(), v.max()
    if mx <= mn:
        return np.zeros_like(x)
    out = (x - mn) / (mx - mn)
    out[~np.isfinite(out)] = 0
    return out


results = []


for city in cities:
    print("city:", city)

    r = roads[roads["city"] == city]
    s = segments[segments["city"] == city].copy()
    t = stops[stops["city"] == city]

    s["n_entry"] = 0
    s["access"] = 0.0

    if len(r) == 0 or len(s) == 0 or len(t) == 0:
        results.append(s)
        continue

    if "fclass" in r.columns:
        r = r[~r["fclass"].isin(["motorway", "motorway_link", "trunk", "trunk_link"])]

    if len(r) == 0:
        results.append(s)
        continue

    belt_union = s.geometry.buffer(stream_belt).union_all()
    cand = r[r.geometry.distance(belt_union) <= road_tol]

    pts = []
    for g in cand.geometry:
        if g is None or g.is_empty:
            continue
        p, _ = nearest_points(g, belt_union)
        pts.append(p)

    if len(pts) == 0:
        results.append(s)
        continue

    pts = gpd.GeoDataFrame({"geometry": pts}, crs=s.crs)
    coords = np.column_stack([pts.geometry.x, pts.geometry.y])
    labels = DBSCAN(eps=cluster_eps, min_samples=1).fit_predict(coords)
    pts["cluster"] = labels

    centroids = pts.groupby("cluster").geometry.apply(lambda g: Point(g.x.mean(), g.y.mean()))
    entries = gpd.GeoDataFrame({"geometry": centroids.values}, crs=s.crs)
    entries = gpd.sjoin_nearest(entries, s, how="left")

    if len(entries) == 0:
        results.append(s)
        continue

    node_map = {}
    nodes = []
    edges = []

    def nid(x, y):
        k = (round(x, 3), round(y, 3))
        if k not in node_map:
            node_map[k] = len(node_map)
            nodes.append((node_map[k], k[0], k[1]))
        return node_map[k]

    for g in r.geometry:
        if g is None or g.is_empty:
            continue
        lines = [g] if isinstance(g, LineString) else (list(g.geoms) if isinstance(g, MultiLineString) else [])
        for ln in lines:
            coords = list(ln.coords)
            if len(coords) < 2:
                continue
            d = ln.length
            if d <= 0:
                continue
            u = nid(coords[0][0], coords[0][1])
            v = nid(coords[-1][0], coords[-1][1])
            edges += [(u, v, d), (v, u, d)]

    if len(nodes) == 0:
        results.append(s)
        continue

    nodes = pd.DataFrame(nodes, columns=["id", "x", "y"])
    edges = pd.DataFrame(edges, columns=["u", "v", "d"])
    net = pdna.Network(nodes["x"], nodes["y"], edges["u"], edges["v"], edges[["d"]])

    net.set_pois(
        "k",
        maxdist=max_dist,
        maxitems=max_stops,
        x_col=t.geometry.x.values,
        y_col=t.geometry.y.values,
    )

    entry_nodes = net.get_node_ids(entries.geometry.x, entries.geometry.y)
    dist = net.nearest_pois(max_dist, "k", max_stops, include_poi_ids=True)

    if dist.shape[1] == 0:
        results.append(s)
        continue

    rows = dist.reindex(entry_nodes.values)
    if len(rows) == 0:
        results.append(s)
        continue

    dist_cols = [c for c in rows.columns if isinstance(c, (int, np.integer)) or str(c).isdigit()]
    poi_cols = [c for c in rows.columns if str(c).startswith("poi")]

    if len(dist_cols) == 0 or len(poi_cols) == 0:
        results.append(s)
        continue

    d = rows[dist_cols].to_numpy(dtype=float).copy()
    pid = rows[poi_cols].to_numpy(dtype=float).copy()

    d[~np.isfinite(d)] = np.nan
    pid[~np.isfinite(pid)] = np.nan
    tmin = d / walk_speed / 60

    seg_ids = entries["segment400_id"].values
    seg_to_stop = {}
    seg_count = {}

    for i, sid in enumerate(seg_ids):
        seg_count[sid] = seg_count.get(sid, 0) + 1
        seg_to_stop.setdefault(sid, {})
        for j in range(tmin.shape[1]):
            k = pid[i, j]
            tm = tmin[i, j]
            if not np.isfinite(k) or not np.isfinite(tm):
                continue
            k = int(k)
            prev = seg_to_stop[sid].get(k)
            if prev is None or tm < prev:
                seg_to_stop[sid][k] = float(tm)

    raw = np.zeros(len(s))
    n_entry = np.zeros(len(s))

    for i, sid in enumerate(s["segment400_id"].values):
        n_entry[i] = seg_count.get(sid, 0)
        local = seg_to_stop.get(sid, {})
        if local:
            raw[i] = np.sum(np.exp(-gamma * np.array(list(local.values()))))

    s["n_entry"] = n_entry
    s["access"] = raw
    results.append(s)

all_data = pd.concat(results, ignore_index=True)
all_data["transport_access_index"] = minmax(all_data["access"].values)
all_data["stop_count"] = all_data["access"]
all_data["entrance_count"] = all_data["n_entry"]

cols = [
    "segment400_id",
    "merged_id",
    "city",
    "entrance_count",
    "stop_count",
    "transport_access_index",
    "geometry",
]
out = gpd.GeoDataFrame(all_data[cols], geometry="geometry", crs=all_data.crs)
out.to_file(output_path, driver="GPKG")
