import geopandas as gpd
import numpy as np
import rasterio
from pysheds.grid import Grid
from rasterio.io import MemoryFile
from rasterio.mask import mask
from shapely.geometry import mapping


segments = gpd.read_file("data/input/streamall_200m_segments_from_mouth.gpkg")
dem_path = "data/input/DTM_30m.tif"

with rasterio.open(dem_path) as src:
    profile = src.profile.copy()
    pixel_area = abs(src.transform.a * src.transform.e)
    buffer_size = max(abs(src.transform.a), abs(src.transform.e))

grid = Grid.from_raster(dem_path, data_name="dem")
dem = grid.read_raster(dem_path)
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
out["upstream_area_log"] = values_log
out.to_file("data/production/variables/v1_upstream_area.gpkg", driver="GPKG")
