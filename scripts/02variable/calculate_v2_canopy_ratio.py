import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping


segments = gpd.read_file("data/stream_segments/streams_03_segments_100m.gpkg")
canopy = rasterio.open("data/canopy/tcd_2023_tiles/tcd_2023.vrt")

buf = segments.copy()
buf = buf.to_crs("EPSG:3035")
buf["geometry"] = buf.geometry.buffer(50)

vals = []
for g in buf.geometry:
    try:
        img, _ = mask(canopy, [mapping(g)], crop=True)
        d = img[0].astype(float)
        if canopy.nodata is not None:
            d = d[d != canopy.nodata]
        ratio = float(np.nanmean(d) / 100.0) if d.size else 0.0
    except ValueError:
        ratio = 0.0
    vals.append(float(np.clip(ratio, 0.0, 1.0)))

out = segments[["segment100_id", "geometry"]].copy()
out["canopy_cover"] = vals
out.to_file("data/production/variables/v2_canopy.gpkg", driver="GPKG")
