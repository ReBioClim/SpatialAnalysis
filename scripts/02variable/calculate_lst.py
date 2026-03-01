import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping


segments = gpd.read_file("data/input/streamall_100m_segments_from_mouth.gpkg")
lst = rasterio.open("data/input/lst_2024summer.tif")

buf = segments.copy()
buf["geometry"] = buf.geometry.buffer(100)

vals = []
for g in buf.geometry:
    img, _ = mask(lst, [mapping(g)], crop=True)
    d = img[0].astype(float)
    d = d[(d > 270) & (d < 330)]
    vals.append(np.mean(d) - 273.15 if len(d) else np.nan)

out = segments[["segment100_id", "geometry"]].copy()
out["lst_mean_100m"] = vals
out.to_file("data/production/variables/v3_lst.gpkg", driver="GPKG")
