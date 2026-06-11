import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping

segments_path = "data/input/streamall_100m_segments_from_mouth.gpkg"
canopy_raster_path = "data/canopy/tcd_2023_tiles/tcd_2023.vrt"
output_path = "data/production/variables/v2_riparian_tree_density.gpkg"

buffer_m = 10

segments = gpd.read_file(segments_path).to_crs("EPSG:25833")
canopy = rasterio.open(canopy_raster_path)

segments_mask = segments.to_crs("EPSG:3035")
buffered = segments_mask.copy()
buffered["geometry"] = buffered.geometry.buffer(buffer_m)

pixel_area = abs(canopy.transform.a * canopy.transform.e)
values = []

for geom in buffered.geometry:
    area = geom.area
    if area == 0:
        values.append(0.0)
        continue

    try:
        img, _ = mask(canopy, [mapping(geom)], crop=True)
    except ValueError:
        values.append(0.0)
        continue
    arr = img[0].astype(float)

    if canopy.nodata is not None:
        arr = arr[arr != canopy.nodata]

    # Copernicus TCD is 0-100 canopy percentage per pixel.
    # Mean percentage / 100 gives canopy cover ratio.
    ratio = float(np.nanmean(arr) / 100.0) if len(arr) > 0 else 0.0
    ratio = float(np.clip(ratio, 0.0, 1.0))
    values.append(ratio)

out = segments[["segment100_id", "geometry"]].copy()
out["riparian_tree_density"] = values
out.to_file(output_path, driver="GPKG")
