import geopandas as gpd
import numpy as np
import os
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping

# Floodplain availability proxy based on HAND contour flood-hazard mapping
# Nobre et al., 2016, HAND contour: a new proxy predictor of inundation extent: Mapping Flood Hazard Potential Using Topography


segments_path = "data/input/streamall_200m_segments_from_mouth.gpkg"
dem_path = "data/input/DTM_30m.tif"
output_path = "data/production/variables/v3_flooding.gpkg"


def raster_values(src, geom):
    try:
        img, _ = mask(src, [mapping(geom)], crop=True, filled=False, all_touched=True)
    except ValueError:
        return np.array([], dtype=float)
    vals = img[0].compressed().astype(float)
    return vals[np.isfinite(vals)]


segments = gpd.read_file(segments_path).to_crs("EPSG:25833")


# floodplain availability in 100m buffer
buffer_100 = segments.copy()
buffer_100["geometry"] = buffer_100.geometry.buffer(100)

with rasterio.open(dem_path) as src:
    stream_sample_m = max(abs(src.transform.a), abs(src.transform.e)) / 2

    def calc(row):
        stream_geom = segments.loc[row.name, "geometry"]
        stream_vals = raster_values(src, stream_geom.buffer(stream_sample_m))
        if len(stream_vals) == 0:
            return np.nan, np.nan, np.nan, np.nan, 0

        stream_elevation = float(np.nanmedian(stream_vals))
        buffer_vals = raster_values(src, row.geometry)
        valid_count = len(buffer_vals)
        if valid_count == 0:
            return stream_elevation, np.nan, np.nan, np.nan, 0

        relative_elevation = buffer_vals - stream_elevation
        avail_1m = float(np.mean(relative_elevation <= 1))
        avail_2m = float(np.mean(relative_elevation <= 2))
        avail_3m = float(np.mean(relative_elevation <= 3))

        return stream_elevation, avail_1m, avail_2m, avail_3m, valid_count

    values = buffer_100.apply(calc, axis=1, result_type="expand")


cols = [
    "stream_elevation_m",
    "floodplain_availability_1m",
    "floodplain_availability",
    "floodplain_availability_3m",
    "floodplain_valid_cell_count",
]
values.columns = cols
segments = segments.join(values)
if os.path.exists(output_path):
    os.remove(output_path)
segments.to_file(output_path, driver="GPKG")
