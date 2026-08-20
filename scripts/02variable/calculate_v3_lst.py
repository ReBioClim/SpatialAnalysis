import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping


segments = gpd.read_file("data/stream_segments/streams_03_segments_100m.gpkg")
lst = rasterio.open("data/prepared/lst_2022_2025_summer.tif")

buf = segments.copy()
buf["geometry"] = buf.geometry.buffer(100)

vals = []
for g in buf.geometry:
    img, _ = mask(lst, [mapping(g)], crop=True)
    d = img[0].astype(float)
    d = d[(d > 0) & (d < 60)]
    vals.append(np.mean(d) if len(d) else np.nan)

out = segments[["segment100_id", "geometry"]].copy()
out["land_surface_temperature"] = vals
out.to_file("data/production/variables/v3_lst.gpkg", driver="GPKG")
