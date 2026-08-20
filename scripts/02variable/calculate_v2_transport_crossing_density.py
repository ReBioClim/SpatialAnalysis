from pathlib import Path
import geopandas as gpd
import numpy as np
from sklearn.cluster import DBSCAN


segments_path = Path("data/stream_segments/streams_03_segments_200m.gpkg")
roads_path = Path("data/prepared/roads_merged.gpkg")
railways_path = Path("data/prepared/railways_merged.gpkg")
output_path = Path("data/production/variables/v2_crossings.gpkg")


def crossing_count(line, candidates, spatial_index):
    hits = candidates.iloc[list(spatial_index.intersection(line.bounds))]
    points = []
    for geometry in hits.geometry:
        intersection = line.intersection(geometry)
        if intersection.is_empty:
            continue
        if intersection.geom_type in {"Point", "LineString"}:
            points.append(intersection.centroid)
        elif intersection.geom_type in {"MultiPoint", "MultiLineString"}:
            points.extend(part.centroid for part in intersection.geoms)
        elif intersection.geom_type == "GeometryCollection":
            points.extend(
                part.centroid
                for part in intersection.geoms
                if part.geom_type in {"Point", "LineString", "MultiPoint", "MultiLineString"}
            )
    if not points:
        return 0
    coords = np.array([(point.x, point.y) for point in points])
    return int(len(set(DBSCAN(eps=5.0, min_samples=1).fit_predict(coords))))


segments = gpd.read_file(segments_path).to_crs("EPSG:25833")
roads = gpd.read_file(roads_path).to_crs(segments.crs)
railways = gpd.read_file(railways_path).to_crs(segments.crs)

road_index = roads.sindex
railway_index = railways.sindex

out = segments[["segment200_id", "geometry"]].copy()
out["roads_crossings"] = [
    crossing_count(geometry, roads, road_index) for geometry in out.geometry
]
out["railways_crossings"] = [
    crossing_count(geometry, railways, railway_index) for geometry in out.geometry
]
out["total_crossings"] = out["roads_crossings"] + out["railways_crossings"]
out["transport_crossing_count"] = out["total_crossings"]
out["transport_crossing_density"] = (
    out["transport_crossing_count"] / (out.geometry.length / 1000.0)
)

output_path.parent.mkdir(parents=True, exist_ok=True)
out.to_file(output_path, driver="GPKG")
print(f"saved: {output_path} ({len(out)} segments)")
