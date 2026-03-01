import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping


segments = gpd.read_file("data/input/streamall_100m_segments_from_mouth.gpkg")
impervious = rasterio.open("data/input/impervious_merged_25833.tif")

buf = segments.copy()
buf["geometry"] = buf.geometry.buffer(100)

vals = []
for g in buf.geometry:
    img, _ = mask(impervious, [mapping(g)], crop=True)
    d = img[0].astype(float)
    if impervious.nodata is not None:
        d = d[d != impervious.nodata]
    vals.append(np.mean(d) if len(d) else 0)

out = segments[["segment100_id", "geometry"]].copy()
out["impervious_density"] = np.clip(vals, 0, 100)
out.to_file("data/production/variables/v2_impervious.gpkg", driver="GPKG")
