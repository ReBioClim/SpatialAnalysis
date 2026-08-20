import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping

segments_path = "data/stream_segments/streams_03_segments_100m.gpkg"
landcover_path = "data/prepared/ESA_landcover_all.tif"
output_path = "data/production/variables/v2_open_space_ratio.gpkg"

buffer_m = 100
open_space_classes = [30, 60, 80, 95, 100]

segments = gpd.read_file(segments_path).to_crs("EPSG:25833")
landcover = rasterio.open(landcover_path)

buffered = segments.copy()
buffered["geometry"] = buffered.geometry.buffer(buffer_m)

values = []

for geom in buffered.geometry:
    img, _ = mask(landcover, [mapping(geom)], crop=True, filled=False)
    arr = img[0].compressed()
    values.append(float(np.mean(np.isin(arr, open_space_classes))) if len(arr) else np.nan)

out = segments[["segment100_id", "geometry"]].copy()
out["open_space_cover"] = values
out.to_file(output_path, driver="GPKG")
