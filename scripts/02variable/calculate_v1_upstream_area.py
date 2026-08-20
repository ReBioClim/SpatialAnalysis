# reference Bartos (2020), pysheds

import geopandas as gpd
import numpy as np
import os
import rasterio
from pysheds.grid import Grid
from rasterio.io import MemoryFile
from rasterio.mask import mask
from shapely.geometry import mapping

# Compatibility for NumPy >= 2 where np.in1d is removed.
if not hasattr(np, "in1d"):
    np.in1d = np.isin


segments = gpd.read_file("data/stream_segments/streams_03_segments_200m.gpkg")
target_crs = "EPSG:25833"
segments = segments.to_crs(target_crs)
dem_path = "data/prepared/DTM_30m.tif"
dem_tmp_path = "data/production/variables/_tmp_dtm_30m_epsg25833.tif"

with rasterio.open(dem_path) as src:
    dem_arr = src.read(1)
    profile = src.profile.copy()
    pixel_area = abs(src.transform.a * src.transform.e)
    buffer_size = max(abs(src.transform.a), abs(src.transform.e))

with rasterio.open(dem_tmp_path, "w", **profile) as dst:
    dst.write(dem_arr, 1)

grid = Grid.from_raster(dem_tmp_path, data_name="dem")
dem = grid.read_raster(dem_tmp_path)
dem = grid.fill_depressions(dem)
dem = grid.resolve_flats(dem)
flow_dir = grid.flowdir(dem)
flow_acc = grid.accumulation(flow_dir)
upstream_area = np.array(flow_acc, dtype=float) * pixel_area

profile.update(dtype="float64", count=1, nodata=np.nan)

values_m2 = []
values_log = []

with MemoryFile() as mem:
    with mem.open(**profile) as ds:
        ds.write(upstream_area, 1)
        for geom in segments.geometry:
            g = geom.buffer(buffer_size, cap_style=2)
            arr, _ = mask(ds, [mapping(g)], crop=True)
            arr = arr[0]
            arr = arr[np.isfinite(arr)]
            if len(arr) == 0:
                values_m2.append(np.nan)
                values_log.append(np.nan)
            else:
                v = np.max(arr)
                values_m2.append(v)
                values_log.append(np.log1p(v))

out = segments[["segment200_id", "geometry"]].copy()
out["upstream_area_m2"] = values_m2
out["upstream_area"] = values_log
out.to_file("data/production/variables/v1_upstream_area.gpkg", driver="GPKG")

if os.path.exists(dem_tmp_path):  # Remove the temporary pysheds input.
    os.remove(dem_tmp_path)
