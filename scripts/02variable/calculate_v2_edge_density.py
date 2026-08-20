import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask


segments = gpd.read_file("data/stream_segments/streams_03_segments_100m.gpkg")
landcover = rasterio.open("data/prepared/ESA_landcover_all.tif")
green = {10, 20, 30, 90, 95}

buf = segments.copy()
buf["geometry"] = buf.geometry.buffer(150)

edge_density_values = []
for geom in buf.geometry:
    img, transform = mask(landcover, [geom], crop=True, filled=False)
    arr = img[0]
    valid = ~arr.mask
    green_mask = np.isin(arr.data, list(green))
    if not np.any(green_mask & valid):
        edge_density_values.append(0.0)
        continue

    # Count only internal green/non-green cell adjacencies. 
    # This excludes the artificial perimeter created where the raster is clipped by the buffer.
    horizontal = (
        green_mask[:, 1:] != green_mask[:, :-1]
    ) & valid[:, 1:] & valid[:, :-1]
    vertical = (
        green_mask[1:, :] != green_mask[:-1, :]
    ) & valid[1:, :] & valid[:-1, :]
    patch_perimeter_m = float(horizontal.sum() * abs(transform.e))
    patch_perimeter_m += float(vertical.sum() * abs(transform.a))

    buffer_area_m2 = geom.area
    if buffer_area_m2 > 0:
        # m/ha as defined in draft: perimeter (m) / area (ha).
        edge_density_values.append(float(patch_perimeter_m) / (buffer_area_m2 / 10000.0))
    else:
        edge_density_values.append(0.0)

out = segments[["segment100_id", "geometry"]].copy()
out["edge_density"] = edge_density_values
out.to_file("data/production/variables/v2_edge_density.gpkg", driver="GPKG")
