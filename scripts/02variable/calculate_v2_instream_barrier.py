import geopandas as gpd
import numpy as np
from osmnx._overpass import _overpass_request
from shapely.geometry import Point, LineString


# load
seg = gpd.read_file("data/input/streamall_200m_segments_from_mouth.gpkg")


# overpass
b = seg.to_crs("EPSG:4326").total_bounds
q = f"""
[out:json];
(
 node["waterway"]({b[1]},{b[0]},{b[3]},{b[2]});
 way["waterway"]({b[1]},{b[0]},{b[3]},{b[2]});
);
out body;
"""

res = _overpass_request(data={"data": q})["elements"]


# to points
nodes = {e["id"]:(e["lon"],e["lat"]) for e in res if e["type"]=="node" and "lon" in e}

pts = []

for e in res:
    if "tags" not in e:
        continue

    # node
    if e["type"] == "node":
        pts.append(Point(e["lon"], e["lat"]))

    # way → midpoint
    if e["type"] == "way":
        coords = [nodes[n] for n in e["nodes"] if n in nodes]
        if len(coords) > 1:
            l = LineString(coords)
            if l.length > 0:
                pts.append(l.interpolate(0.5, normalized=True))


bar = gpd.GeoDataFrame(geometry=pts, crs="EPSG:4326").to_crs(seg.crs)


# near stream
stream = seg.geometry.union_all()
bar = bar[bar.geometry.distance(stream) < 15]


# count
buf = seg.copy()
buf["geometry"] = buf.geometry.buffer(15)

j = gpd.sjoin(bar, buf, predicate="intersects")

c = j.groupby("segment200_id").size()
seg["barrier_n"] = seg["segment200_id"].map(c).fillna(0)


# density
seg["barrier_dens"] = seg["barrier_n"] / (seg.geometry.length / 1000)