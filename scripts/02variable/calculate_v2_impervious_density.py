import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping


segments = gpd.read_file("data/stream_segments/streams_03_segments_100m.gpkg")
impervious = rasterio.open("data/prepared/impervious_merged_25833.tif")

buf = segments.copy()
buf["geometry"] = buf.geometry.buffer(100)

vals = []
for g in buf.geometry:
    img, _ = mask(impervious, [mapping(g)], crop=True, filled=False)
    d = img[0].compressed().astype(float)
    d = d[np.isfinite(d)]
    vals.append(np.mean(d) if len(d) else np.nan)

out = segments[["segment100_id", "geometry"]].copy()
out["impervious_cover"] = np.clip(vals, 0, 100) / 100.0
out.to_file("data/production/variables/v2_impervious.gpkg", driver="GPKG")
