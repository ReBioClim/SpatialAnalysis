import os
from glob import glob

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping


# paths
segments_path = "data/input/streamall_100m_segments_from_mouth.gpkg"
ndvi_dir = "data/input/NDVI_riparian_GEE_Export"
output_path = "data/production/variables/v3_ndvi.gpkg"

ndvi_threshold = 0.4
target_year = "2025"

ndvi_tiles = sorted([
    p for p in glob(os.path.join(ndvi_dir, "s2_ndvi_growing_season*.tif"))
    if target_year in os.path.basename(p)])


# load segments
segments = gpd.read_file(segments_path)

zone = segments.copy()
zone["geometry"] = zone.geometry.buffer(5)

ratio_col = "ndvi_0.4_ratio"


#### ndvi raster
if len(ndvi_tiles) > 0:

    with rasterio.open(ndvi_tiles[0]) as src:

        def calc(g):
            img, _ = mask(src, [mapping(g)], crop=True)
            ndvi = img[0]

            valid = np.isfinite(ndvi)
            valid &= (ndvi >= -1) & (ndvi <= 1)

            if src.nodata is not None:
                valid &= ndvi != src.nodata

            if valid.any():
                return np.mean(ndvi[valid] > ndvi_threshold)
            else:
                return np.nan

        zone[ratio_col] = zone.geometry.apply(calc)


#### multiband raster
if len(ndvi_tiles) == 0 and len(multiband_tiles) > 0:

    with rasterio.open(multiband_tiles[0]) as src:

        def calc(g):
            img, _ = mask(src, [mapping(g)], crop=True)

            b4 = img[0].astype(np.float32)
            b8 = img[1].astype(np.float32)
            scl = img[2]

            valid = np.isin(scl, [4, 5, 7])
            valid &= (b4 > 0) & (b8 > 0)

            if src.nodata is not None:
                valid &= b4 != src.nodata
                valid &= b8 != src.nodata

            if not valid.any():
                return np.nan

            ndvi = (b8 - b4) / (b8 + b4)

            return np.mean(ndvi[valid] > ndvi_threshold)

        zone[ratio_col] = zone.geometry.apply(calc)


zone.to_file(output_path, driver="GPKG")