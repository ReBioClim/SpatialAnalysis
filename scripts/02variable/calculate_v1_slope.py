import geopandas as gpd
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
from shapely.geometry import Point


segments_path = Path("data/stream_segments/streams_03_segments_200m.gpkg")
streams_path = Path("data/stream_geometry/streams_02_network.gpkg")
fallback_dtm = Path("data/prepared/DTM_30m.tif")
dtm_by_city = {
    "Dresden": Path("data/25833/Dresden_DTM_1m.tif"),
    "Jablonec": Path("data/25833/Jablonec_dtm_1m_final.tif"),
    "Poznan": Path("data/25833/Poznan_dtm_1m_fixed.tif"),
    "Senica": Path("data/25833/Senica_DTM_25833.tif"),
}
output_path = Path("data/production/variables/v1_slope.gpkg")


def valid_sample(dataset, point):
    if not (
        dataset.bounds.left <= point.x <= dataset.bounds.right
        and dataset.bounds.bottom <= point.y <= dataset.bounds.top
    ):
        return np.nan
    value = float(next(dataset.sample([(point.x, point.y)]))[0])
    if not np.isfinite(value):
        return np.nan
    if dataset.nodata is not None and np.isclose(value, float(dataset.nodata)):
        return np.nan
    return value


def main():
    segments = gpd.read_file(segments_path).to_crs("EPSG:25833")
    streams = gpd.read_file(streams_path)[["merged_id", "city"]].drop_duplicates("merged_id")
    segments = segments.drop(columns=["city"], errors="ignore").merge(
        streams, on="merged_id", how="left"
    )

    city_dtm = {city: rasterio.open(path) for city, path in dtm_by_city.items()}
    fallback = rasterio.open(fallback_dtm)
    try:
        rows = []
        for _, segment in segments.iterrows():
            line = segment.geometry
            start = Point(line.coords[0])
            end = Point(line.coords[-1])
            dataset = city_dtm[segment["city"]]
            start_elevation = valid_sample(dataset, start)
            end_elevation = valid_sample(dataset, end)
            if not np.isfinite(start_elevation):
                start_elevation = valid_sample(fallback, start)
            if not np.isfinite(end_elevation):
                end_elevation = valid_sample(fallback, end)

            distance = float(line.length)
            # Positive longitudinal slope means elevation rises upstream.
            difference = (
                end_elevation - start_elevation
                if segment["mouth_endpoint"] == "endpoint1"
                else start_elevation - end_elevation
            )
            slope = difference / distance if distance > 0 else np.nan
            rows.append(
                {
                    "segment200_id": segment["segment200_id"],
                    "longitudinal_slope": slope,
                    "slope": abs(slope),
                    "start_elevation": start_elevation,
                    "end_elevation": end_elevation,
                    "elevation_difference": difference,
                    "actual_distance": distance,
                }
            )
    finally:
        fallback.close()
        for dataset in city_dtm.values():
            dataset.close()

    attributes = pd.DataFrame(rows)
    output = segments[["segment200_id", "geometry"]].merge(
        attributes, on="segment200_id", how="left"
    )
    output = gpd.GeoDataFrame(output, geometry="geometry", crs=segments.crs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_file(output_path, layer="v1_slope", driver="GPKG")
    print(f"saved: {output_path} ({len(output)} segments)")


if __name__ == "__main__":
    main()
