from shapely.strtree import STRtree
import geopandas as gpd
from shapely.geometry import LineString, Point, MultiPoint, MultiLineString, MultiPolygon, Polygon
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
from shapely.ops import linemerge, unary_union, split, snap, substring
from tqdm import tqdm
from scipy.spatial import cKDTree
from shapely.ops import unary_union


# 250709
# # create 100m buffer 

# clearn 100m stream segments
stream100 = gpd.read_file("data/stream_segments/stream_segments_100m_with_attrs.gpkg",
                           layer="segments_100m_with_attrs", driver="GPKG")
cityboundary = gpd.read_file("data/city_boundaries/combined_city_boundaries.gpkg", driver = "GPKG")
cityboundary = cityboundary.to_crs(stream100.crs)
stream100_within_boundary = gpd.clip(stream100, cityboundary)
stream100_within_boundary["length"] = stream100_within_boundary.geometry.length

stream100_within_boundary["length"].hist() 

plt.show()
print(len(stream100_within_boundary))

stream100_segments_clean = stream100_within_boundary[(stream100_within_boundary["length"] >= 99) & (stream100_within_boundary["length"] <= 101)].copy()
stream100_segments_clean["segment_id"] = range(1, len(stream100_segments_clean)+1)

stream100_segments_clean.to_file("data/stream_geometry/stream100_cleaned.gpkg", driver="GPKG")

print(len(stream100_segments_clean))
print(stream100.crs)
print(stream100.columns.unique())

stream100_clean = gpd.read_file("data/stream_geometry/stream100_cleaned.gpkg", driver="GPKG")
print(stream100_clean.crs)

# create buffer zone, need as complete waterway data as possible
allblue = gpd.read_file("data/stream_geometry/allblue_100plus.gpkg")
allblue = allblue.to_crs("epsg: 25833")
waterway_forbuffer = allblue[~allblue["waterway"].isin(["river"])].copy()

merged_line = linemerge(unary_union(waterway_forbuffer.geometry))
buffer_geom = merged_line.buffer(50)
buffer_gdf = gpd.GeoDataFrame(geometry=[buffer_geom], crs=waterway_forbuffer.crs)
buffer_gdf.to_file("data/stream_segments/buffer100.gpkg", driver="GPKG")

stream100_clean = gpd.read_file("data/stream_geometry/stream100_cleaned.gpkg", driver="GPKG")
buffer_gdf = gpd.read_file("data/stream_segments/buffer100.gpkg", driver="GPKG")
buffer_gdf = buffer_gdf.explode(ignore_index=True) # important

print(buffer_gdf.crs)
print(len(buffer_gdf))
print(stream100_clean.crs)


# create buffer cell

# i tried created boundary points (every 5m) and to find the nearest. but still takes time. so not use below
# 合并边界为 MultiLineString
INTERVAL = 5
buffer_boundary = unary_union(buffer_gdf.boundary)

def densify_line(line, interval=5.0):
    num_points = max(int(line.length // interval), 1)
    return [line.interpolate(i * interval) for i in range(num_points + 1)]

boundary_points = []
if hasattr(buffer_boundary, 'geoms'):
    for geom in buffer_boundary.geoms:
        boundary_points.extend(densify_line(geom, INTERVAL))
else:
    boundary_points.extend(densify_line(buffer_boundary, INTERVAL))

print(len(boundary_points))
boundary_points_gdf = gpd.GeoDataFrame(geometry=boundary_points, crs=stream100_clean.crs)
boundary_points_gdf.to_file("data/stream_segments/100buffer_boundary_points_5m.gpkg", driver="GPKG")
##


# create buffer cell

# first, find closest 4 points, B1 B2 is left/right side for Pstart, B3 B4 is left/right side for Pend
# below worked ok
# So I find the point on the vertical line from Pstart
# the vertical line here is 50 meters in distance， that point is the offset point, 
# and the distance between that point and Pstart is 50 meters. 
# Then from that point, we look for the nearest point on the boundary
# (difficult process, took long time T.T)

OFFSET_DISTANCE = 50  # 50m 

stream100_clean = gpd.read_file("data/stream_geometry/stream100_cleaned.gpkg")
stream100_clean = stream100_clean.explode(index_parts=False).reset_index(drop=True)

buffer_gdf = gpd.read_file("data/stream_segments/buffer100.gpkg")
buffer_gdf = buffer_gdf.explode(ignore_index=True)
buffer_gdf = buffer_gdf.to_crs(stream100_clean.crs)


#
buffer_boundary = unary_union(buffer_gdf.boundary)

def unit_vector(p1, p2):
    dx, dy = p2.x - p1.x, p2.y - p1.y
    length = np.hypot(dx, dy)
    if length == 0:
        return None
    return np.array([dx / length, dy / length])

def perpendicular_vector(vec):
    return np.array([-vec[1], vec[0]])

# overlapped point cache
boundary_point_cache = {}

def find_left_right_by_offset_with_cache(p, perp_vec, buffer_boundary, offset=OFFSET_DISTANCE):
    vec = np.array(perp_vec) / np.linalg.norm(perp_vec)
    results = {}

    for side, sign in [("left", +1), ("right", -1)]:
        key = (round(p.x, 3), round(p.y, 3), side)
        if key in boundary_point_cache:
            results[side] = boundary_point_cache[key]
            continue

        p_offset = Point(p.x + sign * vec[0] * offset, p.y + sign * vec[1] * offset)
        proj = buffer_boundary.interpolate(buffer_boundary.project(p_offset))
        boundary_point_cache[key] = proj
        results[side] = proj

    return results["left"], results["right"]

# main loop: extract B1-B4
rows = []

for idx, row in tqdm(stream100_clean.iterrows(), total=len(stream100_clean), desc="Processing segments"):
    seg_id = row["segment_id"] if "segment_id" in row else idx
    geom = row.geometry

    if not isinstance(geom, LineString) or geom.is_empty:
        continue

    coords = list(geom.coords)
    if len(coords) < 2:
        continue

    p_start, p_end = Point(coords[0]), Point(coords[-1])
    dir_vec = unit_vector(p_start, p_end)
    if dir_vec is None:
        continue

    perp_vec = perpendicular_vector(dir_vec)

    b1, b2 = find_left_right_by_offset_with_cache(p_start, perp_vec, buffer_boundary)
    b3, b4 = find_left_right_by_offset_with_cache(p_end, perp_vec, buffer_boundary)

    for i, pt in enumerate([b1, b2, b3, b4], start=1):
        if pt:
            rows.append({
                "segment_id": seg_id,
                "point_id": f"B{i}",
                "geometry": pt
            })

result_gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=stream100_clean.crs)
result_gdf.to_file("data/stream_segments/segment_boundary_points.gpkg", driver="GPKG")
print(len(result_gdf)) #59012






# removed overlapped
stream100_clean = gpd.read_file("data/stream_geometry/stream100_cleaned.gpkg")
stream100_clean["geom_wkb"] = stream100_clean.geometry.apply(lambda g: g.wkb)
stream100_clean["min_id"] = stream100_clean.groupby("geom_wkb")["segment_id"].transform("min")
stream100_clean = stream100_clean[stream100_clean["segment_id"] == stream100_clean["min_id"]]
stream100_clean = stream100_clean.drop(columns=["geom_wkb", "min_id"])
stream100_clean = stream100_clean.explode(index_parts=False).reset_index(drop=True)

print(len(stream100_clean))


stream100_clean.to_file("data/stream_geometry/stream100_cleaned1.gpkg", driver="GPKG")

result_gdf = gpd.read_file("data/stream_segments/segment_boundary_points.gpkg")
buffer_gdf = gpd.read_file("data/stream_segments/buffer100.gpkg").explode(ignore_index=True)


stream100_clean = gpd.read_file("data/stream_geometry/stream100_cleaned1.gpkg")

buffer_gdf = gpd.read_file("data/stream_segments/buffer100.gpkg").explode(ignore_index=True)

valid_ids = stream100_clean["segment_id"].unique()
result_gdf = result_gdf[result_gdf["segment_id"].isin(valid_ids)].copy()
print(len(result_gdf))
counts = result_gdf["point_id"].value_counts()
print(counts)


# construct Cell（P_start → B1 → B3 → P_end → B4 → B2 → P_start, six sides


hex_cells = []

# merge buffer boundaries
buffer_boundary = unary_union(buffer_gdf.boundary)
merged = linemerge(buffer_boundary)
if merged.geom_type == "MultiLineString":
    buffer_boundary = max(merged.geoms, key=lambda g: g.length)
else:
    buffer_boundary = merged

# group boundary points by segment
boundary_group = result_gdf.groupby("segment_id")

# build  cells
for _, row in tqdm(stream100_clean.iterrows(), total=len(stream100_clean), desc="Building hex cells"):
    seg_id = row["segment_id"]
    geom = row.geometry

    if geom.geom_type == "MultiLineString":
        geom = max(geom.geoms, key=lambda g: g.length)

    coords = list(geom.coords)
    if len(coords) < 2 or seg_id not in boundary_group.groups:
        continue

    p_start = Point(coords[0])
    p_end = Point(coords[-1])
    group = boundary_group.get_group(seg_id)
    b_points = {r["point_id"]: r.geometry for _, r in group.iterrows()}

    if not all(k in b_points for k in ["B1", "B2", "B3", "B4"]):
        continue

    try:
        d13_start = buffer_boundary.project(b_points["B1"])
        d13_end = buffer_boundary.project(b_points["B3"])
        line_13 = substring(buffer_boundary, min(d13_start, d13_end), max(d13_start, d13_end))

        d42_start = buffer_boundary.project(b_points["B4"])
        d42_end = buffer_boundary.project(b_points["B2"])
        line_42 = substring(buffer_boundary, min(d42_start, d42_end), max(d42_start, d42_end))

        ring_coords = [
            p_start.coords[0],
            b_points["B1"].coords[0],
            b_points["B3"].coords[0],
            p_end.coords[0],
            b_points["B4"].coords[0],
            b_points["B2"].coords[0],
            p_start.coords[0]
        ]
        polygon = Polygon(ring_coords)

        if polygon.is_valid and not polygon.is_empty:
            hex_cells.append({
                "segment_id": seg_id,
                "geometry": polygon
            })
    except:
        continue

hex_gdf = gpd.GeoDataFrame(hex_cells, geometry="geometry", crs=stream100_clean.crs)
hex_gdf.to_file("data/stream_segments/segment_buffer100_cell_hexshape.gpkg", driver="GPKG")
