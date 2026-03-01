import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping


segments = gpd.read_file("data/input/streamall_100m_segments_from_mouth.gpkg")
landcover = rasterio.open("data/input/ESA_landcover_all.tif")
green = [10, 20, 30, 90, 95]

buf = segments.copy()
buf["geometry"] = buf.geometry.buffer(150)

rich = []
for g in buf.geometry:
    img, _ = mask(landcover, [mapping(g)], crop=True)
    d = img[0]
    d = d[np.isin(d, green)]
    rich.append(len(np.unique(d)) if len(d) else 0)

out = segments[["segment100_id", "geometry"]].copy()
out["richness_150m"] = rich
out.to_file("data/production/variables/v2_richness.gpkg", driver="GPKG")
