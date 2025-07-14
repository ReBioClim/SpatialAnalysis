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

# # create 100m buffer 


# create buffer zone, need as complete waterway data as possible
allblue = gpd.read_file("data/stream_geometry/allblue_100plus.gpkg")
allblue = allblue.to_crs("epsg: 25833")
waterway_forbuffer = allblue[~allblue["waterway"].isin(["river"])].copy()

merged_line = linemerge(unary_union(waterway_forbuffer.geometry))
buffer_geom = merged_line.buffer(50)
buffer_gdf = gpd.GeoDataFrame(geometry=[buffer_geom], crs=waterway_forbuffer.crs)
buffer_gdf.to_file("data/stream_segments/buffer100.gpkg", driver="GPKG")

buffer_gdf = gpd.read_file("data/stream_segments/buffer100.gpkg", driver="GPKG")
buffer_gdf = buffer_gdf.explode(ignore_index=True) # important

print(buffer_gdf.crs)
print(len(buffer_gdf))


# create buffer cell

# first, find closest 4 points, B1 B2 is left/right side for Pstart, B3 B4 is left/right side for Pend
# below worked ok
# So I find the point on the vertical line from Pstart
# the vertical line here is 50 meters in distance， that point is the offset point, 
# and the distance between that point and Pstart is 50 meters. 
# Then from that point, we look for the nearest point on the boundary
# (difficult process, took long time T.T)

stream100_clean = gpd.read_file("data/stream_geometry/stream100_cleaned.gpkg")
stream100_clean = stream100_clean.explode(index_parts=False).reset_index(drop=True)


# extract P_start, P_end, B1–B4, and save as six-point file
OFFSET_DISTANCE = 50
buffer_boundary = unary_union(buffer_gdf.boundary)
boundary_point_cache = {}

def unit_vector(p1, p2):
    dx, dy = p2.x - p1.x, p2.y - p1.y
    length = np.hypot(dx, dy)
    return np.array([dx / length, dy / length]) if length != 0 else None

def perpendicular_vector(vec):
    return np.array([-vec[1], vec[0]])

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

#  six points
rows = []
for idx, row in tqdm(stream100_clean.iterrows(), total=len(stream100_clean), desc="Extracting 6 points"):
    sid = row["segment_id"]
    geom = row.geometry
    if not isinstance(geom, LineString) or geom.is_empty or len(geom.coords) < 2:
        continue
    p0 = Point(geom.coords[0])
    p3 = Point(geom.coords[-1])
    dir_vec = unit_vector(p0, p3)
    if dir_vec is None:
        continue
    perp_vec = perpendicular_vector(dir_vec)
    b1, b2 = find_left_right_by_offset_with_cache(p0, perp_vec, buffer_boundary)
    b3, b4 = find_left_right_by_offset_with_cache(p3, perp_vec, buffer_boundary)
    for tag, pt in zip(["P_start", "B1", "B2", "B3", "B4", "P_end"], [p0, b1, b2, b3, b4, p3]):
        rows.append({"segment_id": sid, "point_id": tag, "geometry": pt})

sixpt_gdf = gpd.GeoDataFrame(rows, geometry="geometry", crs=stream100_clean.crs)
sixpt_gdf.to_file("data/stream_segments/segment_sixpoints.gpkg", driver="GPKG")

##########
####
#####
