import geopandas as gpd
import rasterio
from shapely.geometry import Point
from shapely.ops import substring


stream_data = gpd.read_file("data/25833/streamall_merged_final.gpkg")


#### mouth points
rows = []

with rasterio.open("data/25833/DTM_30m.tif") as src:
    for i, r in stream_data.iterrows():
        line = r.geometry
        merged_id = r["merged_id"] if "merged_id" in stream_data.columns else i

        p0 = Point(line.coords[0])
        p1 = Point(line.coords[-1])

        z0 = src.sample([(p0.x, p0.y)])[0][0]
        z1 = src.sample([(p1.x, p1.y)])[0][0]

        mouth_point = p0 if z0 < z1 else p1
        mouth_elev = z0 if z0 < z1 else z1

        rows.append({"merged_id": merged_id, "geometry": mouth_point, "elevation": mouth_elev, "is_mouth": True})

mouth_points = gpd.GeoDataFrame(rows, crs=stream_data.crs)


#### segments from mouth
for length in [100, 200, 400]:

    segments = []
    seg_id = 1

    for i, r in stream_data.iterrows():
        line = r.geometry
        merged_id = r["merged_id"] if "merged_id" in stream_data.columns else i

        mouth = mouth_points[mouth_points["merged_id"] == merged_id].iloc[0].geometry

        mouth_distance = line.project(mouth)
        line_length = line.length

        forward = mouth_distance < line_length / 2
        current = mouth_distance

        while True:
            if forward:
                start_distance = current
                end_distance = current + length
            else:
                start_distance = current - length
                end_distance = current

            if start_distance < 0 or end_distance > line_length:
                break

            seg = substring(line, start_distance, end_distance)

            if abs(seg.length - length) < 0.1:
                segments.append(
                    {
                        "geometry": seg,
                        "merged_id": merged_id,
                        f"segment{length}_id": seg_id,
                        "segment_length": seg.length,
                        "start_distance": start_distance,
                        "end_distance": end_distance,
                    }
                )
                seg_id += 1

            current = end_distance if forward else start_distance

    out = gpd.GeoDataFrame(segments, crs=stream_data.crs)
    out.to_file(f"data/stream_segments/streamall_{length}m_segments_from_mouth.gpkg", driver="GPKG")


mouth_points.to_file("data/stream_segments/streamall_mouth_points.gpkg", driver="GPKG")