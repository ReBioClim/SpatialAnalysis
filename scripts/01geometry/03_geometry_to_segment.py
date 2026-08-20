"""Identify downstream endpoints and split streams into fixed-length segments.

- endpoint elevation from DTM determines the stream mouth
- 100, 200, and 400 m segments are then measured upstream from that endpoint
- only complete segments are retained; the source-end remainder is excluded
"""

from pathlib import Path
import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import Point
from shapely.ops import substring


stream_data = gpd.read_file("data/stream_geometry/streams_02_network.gpkg")


# identify both endpoints and mark the lower one as the mouth
rows = []

with rasterio.open("data/prepared/DTM_30m.tif") as src:
    elevation = src.read(1)

    def endpoint_elevation(point):
        if not (
            src.bounds.left <= point.x <= src.bounds.right
            and src.bounds.bottom <= point.y <= src.bounds.top
        ):
            raise ValueError(f"Stream endpoint falls outside the DTM: {point.wkt}")
        raster_row, raster_col = src.index(point.x, point.y)
        value = float(elevation[raster_row, raster_col])
        if not np.isfinite(value) or (
            src.nodata is not None and np.isclose(value, float(src.nodata), equal_nan=True)
        ):
            raise ValueError(f"No valid DTM elevation at stream endpoint: {point.wkt}")
        return value

    for _, row in stream_data.iterrows():
        line = row.geometry
        merged_id = int(row["merged_id"])
        start = Point(line.coords[0])
        end = Point(line.coords[-1])
        start_elev = endpoint_elevation(start)
        end_elev = endpoint_elevation(end)
        mouth_type = "endpoint1" if start_elev < end_elev else "endpoint2"
        rows.extend(
            [
                {
                    "merged_id": merged_id,
                    "point_type": "endpoint1",
                    "elevation": start_elev,
                    "is_mouth": mouth_type == "endpoint1",
                    "geometry": start,
                },
                {
                    "merged_id": merged_id,
                    "point_type": "endpoint2",
                    "elevation": end_elev,
                    "is_mouth": mouth_type == "endpoint2",
                    "geometry": end,
                },
            ]
        )

mouth_points = gpd.GeoDataFrame(rows, crs=stream_data.crs)
mouth_points["point_id"] = np.arange(1, len(mouth_points) + 1, dtype=int)
mouth_output = "data/stream_segments/streams_03_endpoints.gpkg"
Path(mouth_output).parent.mkdir(parents=True, exist_ok=True)
mouth_points.to_file(mouth_output, driver="GPKG")
mouth_lookup = mouth_points[mouth_points["is_mouth"]].set_index("merged_id")
print(f"saved: {mouth_output} ({len(mouth_points)} points)")


# measure complete fixed-length segments upstream from each mouth.
for length in (100, 200, 400):
    segments = []

    for _, row in stream_data.iterrows():
        line = row.geometry
        merged_id = int(row["merged_id"])
        line_length = line.length
        forward = mouth_lookup.loc[merged_id, "point_type"] == "endpoint1"
        segment_count = int(np.floor(line_length / length))
        source_remainder = line_length - segment_count * length

        for position in range(segment_count):
            mouth_start = position * length
            mouth_end = (position + 1) * length

            if forward:
                start_distance, end_distance = mouth_start, mouth_end
            else:
                start_distance = line_length - mouth_end
                end_distance = line_length - mouth_start

            segment = substring(line, start_distance, end_distance)
            segments.append(
                {
                    "geometry": segment,
                    "merged_id": merged_id,
                    "city": row["city"],
                    f"segment{length}_id": len(segments) + 1,
                    "segment_length": float(segment.length),
                    "nominal_length": float(length),
                    "start_distance": float(start_distance),
                    "end_distance": float(end_distance),
                    "distance_from_mouth_start": float(mouth_start),
                    "distance_from_mouth_end": float(mouth_end),
                    "channel_length": float(line_length),
                    "mouth_endpoint": "endpoint1" if forward else "endpoint2",
                    "source_remainder_m": float(source_remainder),
                    "is_last_complete_segment": position == segment_count - 1,
                    "start_point": Point(segment.coords[0]).wkt,
                    "end_point": Point(segment.coords[-1]).wkt,
                }
            )

    output = gpd.GeoDataFrame(segments, crs=stream_data.crs)
    output_path = f"data/stream_segments/streams_03_segments_{length}m.gpkg"
    output.to_file(output_path, driver="GPKG")
    print(f"saved: {output_path} ({len(output)} segments)")
