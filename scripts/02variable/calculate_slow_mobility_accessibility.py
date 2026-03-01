import geopandas as gpd
import numpy as np
import pandas as pd
import pandana as pdna
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import nearest_points
from sklearn.cluster import DBSCAN


roads = gpd.read_file("data/input/roads_merged.gpkg")
segments = gpd.read_file("data/input/streamall_400m_segments_from_mouth_with_city.gpkg")

output_path = "data/production/variables/v2_access_slowmob.gpkg"

cities = ["Dresden", "Poznan", "Jablonec", "Senica"]

stream_belt = 10
road_tol = 30
cluster_eps = 15

max_dist = 1000
walk_speed = 1.2
gamma = 0.3
max_pois = 120


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

    s["n_entry"] = 0
    s["access"] = 0.0

    if len(r) == 0 or len(s) == 0:
        results.append(s)
        continue

    if "fclass" in r.columns:
        r = r[~r["fclass"].isin(["motorway", "motorway_link", "trunk", "trunk_link"])]

    if "fclass" in r.columns:
        slow = r[r["fclass"].isin(["footway", "path", "pedestrian", "steps", "cycleway", "bridleway", "living_street"])]
    else:
        slow = r.iloc[0:0]

    if len(slow) == 0:
        results.append(s)
        continue

    supply = slow.copy()
    supply["geometry"] = supply.geometry.centroid

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
        for l in lines:
            coords = list(l.coords)
            if len(coords) < 2:
                continue
            d = l.length
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
        "p",
        maxdist=max_dist,
        maxitems=max_pois,
        x_col=supply.geometry.x.values,
        y_col=supply.geometry.y.values,
    )

    entry_nodes = net.get_node_ids(entries.geometry.x, entries.geometry.y)
    dist = net.nearest_pois(max_dist, "p", max_pois)
    if dist.shape[1] == 0:
        results.append(s)
        continue

    d = dist.reindex(entry_nodes.values).to_numpy().copy()
    d[~np.isfinite(d)] = np.nan
    t = d / walk_speed / 60

    seg_ids = entries["segment400_id"].values
    seg_dict = {}
    seg_count = {}

    for i, sid in enumerate(seg_ids):
        seg_count[sid] = seg_count.get(sid, 0) + 1
        seg_dict.setdefault(sid, [])
        vals = t[i]
        vals = vals[np.isfinite(vals)]
        seg_dict[sid].extend(vals.tolist())

    raw = np.zeros(len(s))
    n_entry = np.zeros(len(s))

    for i, sid in enumerate(s["segment400_id"].values):
        n_entry[i] = seg_count.get(sid, 0)
        vals = seg_dict.get(sid, [])
        if vals:
            raw[i] = np.sum(np.exp(-gamma * np.array(vals)))

    s["n_entry"] = n_entry
    s["access"] = raw
    results.append(s)

all_data = pd.concat(results, ignore_index=True)
all_data["slowmob_access_index"] = minmax(all_data["access"].values)
all_data["slowMob_length"] = all_data["access"]

cols = ["segment400_id", "merged_id", "city", "slowMob_length", "slowmob_access_index", "geometry"]
out = gpd.GeoDataFrame(all_data[cols], geometry="geometry", crs=all_data.crs)
out.to_file(output_path, driver="GPKG")
