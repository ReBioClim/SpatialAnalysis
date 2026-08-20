"""Calculate near-bank vegetation condition from growing-season NDVI exports.

For each 100 m stream segment, this computes the mean fraction of valid
Sentinel-2 pixels with NDVI >= 0.4 in a 10 m half-width corridor around the
stream centreline (approximately 20 m total width), averaged across years.
"""

from glob import glob
from pathlib import Path
import re

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import box, mapping


segment_path = Path("data/stream_segments/streams_03_segments_100m.gpkg")
ndvi_dir = Path("data/prepared/NDVI_riparian_GEE_Export")
output_path = Path("data/production/variables/v3_ndvi.gpkg")
ndvi_threshold = 0.4
riparian_half_width_m = 10.0


def group_tiles_by_year(paths):
    grouped = {}
    for path in paths:
        match = re.search(r"growing_season_(\d{4})-", path)
        if match:
            grouped.setdefault(match.group(1), []).append(path)
    return grouped


tiles = sorted(glob(str(ndvi_dir / "s2_ndvi_growing_season*.tif")))

segments = gpd.read_file(segment_path).to_crs("EPSG:25833")
zones = segments.geometry.buffer(riparian_half_width_m)
tiles_by_year = group_tiles_by_year(tiles)
ratios = []
sources_by_year = {
    year: [rasterio.open(path) for path in paths]
    for year, paths in tiles_by_year.items()
}

try:
    for geometry in zones:
        annual_ratios = []
        for sources in sources_by_year.values():
            annual_values = []
            for source in sources:
                source_box = box(
                    source.bounds.left,
                    source.bounds.bottom,
                    source.bounds.right,
                    source.bounds.top,
                )
                if not geometry.intersects(source_box):
                    continue
                try:
                    image, _ = mask(source, [mapping(geometry)], crop=True, all_touched=True)
                except ValueError:
                    continue
                values = image[0].astype(np.float32)
                valid = np.isfinite(values) & (values >= -1.0) & (values <= 1.0)
                if source.nodata is not None:
                    valid &= values != source.nodata
                if valid.any():
                    annual_values.append(values[valid])
            if annual_values:
                values = np.concatenate(annual_values)
                annual_ratios.append(float(np.mean(values > ndvi_threshold)))
        ratios.append(float(np.mean(annual_ratios)) if annual_ratios else np.nan)
finally:
    for sources in sources_by_year.values():
        for source in sources:
            source.close()

out = segments.copy()
out["riparian_vegetation_condition"] = ratios
output_path.parent.mkdir(parents=True, exist_ok=True)
out.to_file(output_path, driver="GPKG")
