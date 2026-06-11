import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping

segments_path = "data/input/streamall_100m_segments_from_mouth.gpkg"
landcover_path = "data/input/ESA_landcover_all.tif"
output_path = "data/production/variables/v2_open_space_ratio.gpkg"

buffer_m = 100
open_space_classes = [30, 60, 80, 95, 100]

segments = gpd.read_file(segments_path).to_crs("EPSG:25833")
landcover = rasterio.open(landcover_path)

buffered = segments.copy()
buffered["geometry"] = buffered.geometry.buffer(buffer_m)

pixel_area = abs(landcover.transform.a * landcover.transform.e)
values = []

for geom in buffered.geometry:
    area = geom.area
    if area == 0:
        values.append(0.0)
        continue

    img, _ = mask(landcover, [mapping(geom)], crop=True)
    arr = img[0]

    if landcover.nodata is not None:
        arr = arr[arr != landcover.nodata]

    open_count = np.sum(np.isin(arr, open_space_classes))
    ratio = (open_count * pixel_area) / area
    ratio = float(np.clip(ratio, 0.0, 1.0))
    values.append(ratio)

out = segments[["segment100_id", "geometry"]].copy()
out["open_space_ratio"] = values
out.to_file(output_path, driver="GPKG")
