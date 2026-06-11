import geopandas as gpd
import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.mask import mask
from shapely.geometry import shape


segments = gpd.read_file("data/input/streamall_100m_segments_from_mouth.gpkg")
landcover = rasterio.open("data/input/ESA_landcover_all.tif")
green = {10, 20, 30, 90, 95}

buf = segments.copy()
buf["geometry"] = buf.geometry.buffer(150)

edge_density_values = []
for geom in buf.geometry:
    img, transform = mask(landcover, [geom], crop=True, filled=True, nodata=0)
    arr = img[0]

    green_mask = np.isin(arr, list(green)).astype(np.uint8)
    if green_mask.sum() == 0:
        edge_density_values.append(0.0)
        continue

    patch_perimeter_m = 0.0
    for geom_json, value in shapes(green_mask, mask=green_mask.astype(bool), transform=transform):
        if value == 1:
            poly = shape(geom_json)
            patch_perimeter_m += poly.length

    buffer_area_m2 = geom.area
    if buffer_area_m2 > 0:
        # m/ha as defined in draft: perimeter (m) / area (ha).
        edge_density_values.append(float(patch_perimeter_m) / (buffer_area_m2 / 10000.0))
    else:
        edge_density_values.append(0.0)

out = segments[["segment100_id", "geometry"]].copy()
out["edge_density"] = edge_density_values
out.to_file("data/production/variables/v2_edge_density.gpkg", driver="GPKG")
