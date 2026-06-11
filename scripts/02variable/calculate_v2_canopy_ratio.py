import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping


segments = gpd.read_file("data/input/streamall_100m_segments_from_mouth.gpkg")
landcover = rasterio.open("data/input/ESA_landcover_all.tif")

buf = segments.copy()
buf["geometry"] = buf.geometry.buffer(50)

vals = []
for g in buf.geometry:
    img, _ = mask(landcover, [mapping(g)], crop=True)
    d = img[0]
    canopy = np.sum(d == 10)
    area = g.area
    vals.append(min(1, canopy * 70.35 / area) if area > 0 else 0)

out = segments[["segment100_id", "geometry"]].copy()
out["canopy_ratio"] = vals
out.to_file("data/production/variables/v2_canopy.gpkg", driver="GPKG")
