import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping


segments = gpd.read_file("data/input/streamall_100m_segments_from_mouth.gpkg")
landcover = rasterio.open("data/input/ESA_landcover_all.tif")

buf = segments.copy()
buf["geometry"] = buf.geometry.buffer(100)

vals = []
for g in buf.geometry:
    img, _ = mask(landcover, [mapping(g)], crop=True)
    d = img[0]
    if landcover.nodata is not None:
        d = d[d != landcover.nodata]
    if len(d) == 0:
        vals.append(np.nan)
        continue
    p50 = np.mean(d == 50)
    p40 = np.mean(d == 40)
    p30 = np.mean(d == 30)
    vals.append(5 * p50 + 3 * p40 + p30)

out = segments[["segment100_id", "geometry"]].copy()
out["landuse_intensity"] = vals
out.to_file("data/production/variables/v3_landuse_intensity.gpkg", driver="GPKG")
