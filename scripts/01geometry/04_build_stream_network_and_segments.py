from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import Point
from shapely.ops import linemerge, snap, substring, unary_union


# input
input_path = "data/stream_geometry/streamall.gpkg"
merged_output = "data/25833/streamall_merged_final.gpkg"
streams = gpd.read_file(input_path).to_crs("EPSG:25833")


# clean geometry
streams = streams[streams.geometry.notna() & (~streams.geometry.is_empty)].copy()
streams = streams[streams.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
streams = streams.explode(index_parts=False).reset_index(drop=True)
target = unary_union(streams.geometry.values)


# snap tiny endpoint gaps before grouping
streams["geometry"] = streams.geometry.apply(lambda g: snap(g, target, 0.5))
streams = streams[streams.geometry.notna() & (~streams.geometry.is_empty)].copy()
streams = streams[streams.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
streams = streams.explode(index_parts=False).reset_index(drop=True)

merged_mask = streams["name"].astype("string").str.startswith("merged_", na=False)
streams.loc[merged_mask, "name"] = None
named = streams[streams["name"].notna() & (streams["name"].astype(str).str.strip() != "")]
unnamed = streams[~streams.index.isin(named.index)].reset_index(drop=True).copy()
merged_rows = []

if len(named) > 0:
    for _, grp in named.groupby("name", dropna=True):
        if len(grp) == 1:
            merged_rows.append(grp.iloc[0].copy())
        else:
            row = grp.iloc[0].copy()
            row["geometry"] = linemerge(grp.geometry.unary_union)
            merged_rows.append(row)

if len(unnamed) > 0:
    sindex = unnamed.sindex
    visited = set()

    # group unnamed lines by distance connectivity
    for i in range(len(unnamed)):
        if i in visited:
            continue
        group = {i}
        queue = [i]
        visited.add(i)
        while queue:
            cur = queue.pop()
            cur_geom = unnamed.iloc[cur].geometry
            xmin, ymin, xmax, ymax = cur_geom.bounds
            candidate_idx = list(sindex.intersection((xmin - 10.0, ymin - 10.0, xmax + 10.0, ymax + 10.0)))
            for j in candidate_idx:
                if j in visited:
                    continue
                if cur_geom.distance(unnamed.iloc[j].geometry) <= 10.0:
                    visited.add(j)
                    group.add(j)
                    queue.append(j)
        group_df = unnamed.iloc[sorted(group)].copy()
        if len(group_df) == 1:
            merged_rows.append(group_df.iloc[0].copy())
        else:
            base = group_df.iloc[0].copy()
            base["geometry"] = linemerge(group_df.geometry.unary_union)
            base["name"] = None
            merged_rows.append(base)


# merged stream output
streams = gpd.GeoDataFrame(merged_rows, crs=streams.crs)
streams = streams[streams.geometry.notna() & (~streams.geometry.is_empty)].copy()
streams = streams[streams.geometry.geom_type.isin(["LineString", "MultiLineString"])].copy()
streams = streams.explode(index_parts=False).reset_index(drop=True)
streams["length"] = streams.geometry.length
streams = streams[streams["length"] >= 99.0].copy().reset_index(drop=True)
streams["merged_id"] = np.arange(1, len(streams) + 1, dtype=int)
preferred_cols = [
    "name", "osm_id", "source", "waterway", "covering", "city", "dresden_id",
    "namemerge_id", "merged_id", "length", "geometry",
]
streams = streams[[c for c in preferred_cols if c in streams.columns]].copy()

Path(merged_output).parent.mkdir(parents=True, exist_ok=True)
streams.to_file(merged_output, driver="GPKG")
print(f"saved: {merged_output} ({len(streams)} features)")


# mouth points by dtm elevation
dtm_path = "data/25833/DTM_30m.tif"
print(f"using DTM: {dtm_path}")
rows = []

with rasterio.open(dtm_path) as src:
    for _, row in streams.iterrows():
        line = row.geometry
        start = Point(line.coords[0])
        end = Point(line.coords[-1])
        start_elev = src.sample([(start.x, start.y)])[0][0]
        end_elev = src.sample([(end.x, end.y)])[0][0]
        if start_elev <= end_elev:
            mouth, elev = start, float(start_elev)
        else:
            mouth, elev = end, float(end_elev)
        rows.append({"merged_id": int(row["merged_id"]), "geometry": mouth, "elevation": elev, "is_mouth": True})

mouths = gpd.GeoDataFrame(rows, crs=streams.crs)
mouth_output = "data/stream_segments/streamall_merged_mouth_points.gpkg"
Path(mouth_output).parent.mkdir(parents=True, exist_ok=True)
mouths.to_file(mouth_output, driver="GPKG")
print(f"saved: {mouth_output} ({len(mouths)} points)")
mouth_lookup = mouths.set_index("merged_id")


# fixed-length segments
for seg_len in [100, 200, 400]:
    output = []
    seg_id = 1
    for _, stream in streams.iterrows():
        merged_id = int(stream["merged_id"])
        if merged_id not in mouth_lookup.index:
            continue
        line = stream.geometry
        mouth_pt = mouth_lookup.loc[merged_id, "geometry"]
        mouth_dist = line.project(mouth_pt)
        line_len = line.length

        # create equal-length segments from mouth
        if mouth_dist < line_len / 2.0:
            cur = mouth_dist
            while cur + seg_len <= line_len:
                start_dist = cur
                end_dist = cur + seg_len
                cur += seg_len
                seg = substring(line, start_dist, end_dist)
                if abs(seg.length - seg_len) < 0.1:
                    output.append(
                        {
                            "geometry": seg,
                            "merged_id": merged_id,
                            f"segment{seg_len}_id": seg_id,
                            "segment_length": float(seg.length),
                            "start_distance": float(start_dist),
                            "end_distance": float(end_dist),
                        }
                    )
                    seg_id += 1
        else:
            cur = mouth_dist
            while cur >= seg_len:
                start_dist = cur - seg_len
                end_dist = cur
                cur -= seg_len
                seg = substring(line, start_dist, end_dist)
                if abs(seg.length - seg_len) < 0.1:
                    output.append(
                        {
                            "geometry": seg,
                            "merged_id": merged_id,
                            f"segment{seg_len}_id": seg_id,
                            "segment_length": float(seg.length),
                            "start_distance": float(start_dist),
                            "end_distance": float(end_dist),
                        }
                    )
                    seg_id += 1
    segs = gpd.GeoDataFrame(output, crs=streams.crs)
    seg_path_stream = f"data/stream_segments/streamall_{seg_len}m_segments_from_mouth.gpkg"
    seg_path_25833 = f"data/25833/streamall_{seg_len}m_segments_from_mouth.gpkg"
    segs.to_file(seg_path_stream, driver="GPKG")
    segs.to_file(seg_path_25833, driver="GPKG")
    print(f"saved: {seg_path_stream} and {seg_path_25833} ({len(segs)} segments)")
