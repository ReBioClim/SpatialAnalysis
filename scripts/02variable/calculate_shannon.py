import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from scipy.stats import entropy
from shapely.geometry import mapping


segments = gpd.read_file("data/input/streamall_100m_segments_from_mouth.gpkg")
landcover = rasterio.open("data/input/ESA_landcover_all.tif")
green = [10, 20, 30, 90, 95]

buf = segments.copy()
buf["geometry"] = buf.geometry.buffer(150)

shan = []
for g in buf.geometry:
    img, _ = mask(landcover, [mapping(g)], crop=True)
    d = img[0]
    d = d[np.isin(d, green)]
    if len(d) == 0:
        shan.append(0)
        continue
    counts = [np.sum(d == c) for c in green if np.any(d == c)]
    shan.append(entropy(np.array(counts) / sum(counts)))

out = segments[["segment100_id", "geometry"]].copy()
out["shannon_150m"] = shan
out.to_file("data/production/variables/v2_shannon.gpkg", driver="GPKG")
