from glob import glob
from pathlib import Path
import re
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from shapely.ops import linemerge


segments_path = Path("data/stream_segments/streams_03_segments_100m.gpkg")
ndvi_dir = Path("data/prepared/NDVI_riparian_GEE_Export")
output_path = Path("data/production/variables/v2_riparian_continuity.gpkg")
ndvi_threshold = 0.4
transect_step = 10.0
transect_half_width = 50.0
bank_search_m = 20.0


def group_tiles_by_year(paths):
    grouped = {}
    for path in paths:
        match = re.search(r"growing_season_(\d{4})-", path)
        if match:
            grouped.setdefault(match.group(1), []).append(path)
    return grouped


def sample_year(sources, coordinates):
    values = np.full(len(coordinates), np.nan, dtype=np.float32)
    for i, (x, y) in enumerate(coordinates):
        for source in sources:
            if source.bounds.left <= x <= source.bounds.right and source.bounds.bottom <= y <= source.bounds.top:
                values[i] = next(source.sample([(x, y)]))[0]
                break
    return values


def main_line(geometry):
    if geometry is None or geometry.is_empty:
        return None
    if geometry.geom_type == "LineString":
        return geometry
    if geometry.geom_type == "MultiLineString":
        merged = linemerge(geometry)
        if merged.geom_type == "LineString":
            return merged
        return max(merged.geoms, key=lambda part: part.length)
    return None


def bank_width(side_distances, side_vegetation, pixel_size):
    """Width of the first continuous vegetation run beginning near the bank."""
    order = np.argsort(np.abs(side_distances))
    distances = np.abs(side_distances[order])
    vegetation = side_vegetation[order]
    starts = np.flatnonzero(vegetation & (distances <= bank_search_m))
    if not len(starts):
        return 0.0

    start = int(starts[0])
    end = start
    while end + 1 < len(vegetation) and vegetation[end + 1]:
        end += 1
    return min(transect_half_width, float((end - start + 1) * pixel_size))


def two_bank_width(distances, vegetation, pixel_size):
    left = bank_width(distances[distances < 0], vegetation[distances < 0], pixel_size)
    right = bank_width(distances[distances > 0], vegetation[distances > 0], pixel_size)
    return left, right, (left + right) / 2.0


tiles = sorted(glob(str(ndvi_dir / "s2_ndvi_growing_season*.tif")))
tiles_by_year = group_tiles_by_year(tiles)

segments = gpd.read_file(segments_path).to_crs("EPSG:25833")
all_widths = []
sources_by_year = {
    year: [rasterio.open(path) for path in paths]
    for year, paths in tiles_by_year.items()
}

try:
    first_source = next(iter(sources_by_year.values()))[0]
    pixel_size = min(abs(first_source.transform.a), abs(first_source.transform.e))
    distances = np.arange(
        -transect_half_width,
        transect_half_width + pixel_size,
        pixel_size,
    )
    if not np.any(np.isclose(distances, 0.0)):
        distances = np.sort(np.append(distances, 0.0))

    for geometry in segments.geometry:
        line = main_line(geometry)
        widths = []
        if line is not None:
            for distance in np.arange(transect_step / 2.0, line.length, transect_step):
                point = line.interpolate(distance)
                before = line.interpolate(max(0.0, distance - pixel_size))
                after = line.interpolate(min(line.length, distance + pixel_size))
                dx, dy = after.x - before.x, after.y - before.y
                norm = np.hypot(dx, dy)
                if norm == 0:
                    continue
                px, py = -dy / norm, dx / norm
                coordinates = [(point.x + d * px, point.y + d * py) for d in distances]
                annual_values = [
                    sample_year(sources, coordinates)
                    for sources in sources_by_year.values()
                ]
                values = np.nanmedian(np.asarray(annual_values), axis=0)
                valid = np.isfinite(values) & (values >= -1.0) & (values <= 1.0)
                widths.append(
                    two_bank_width(
                        distances,
                        (values > ndvi_threshold) & valid,
                        pixel_size,
                    )
                )
        all_widths.append(widths)
finally:
    for sources in sources_by_year.values():
        for source in sources:
            source.close()


def summarize(widths):
    if not widths:
        return pd.Series(
            {
                "riparian_continuity": np.nan,
            }
        )
    transects = np.asarray(widths, dtype=np.float32)
    left_values = transects[:, 0]
    right_values = transects[:, 1]
    values = transects[:, 2]
    longest = current = 0
    for present in values > 0:
        current = current + 1 if present else 0
        longest = max(longest, current)
    longest_m = float(longest * transect_step)
    return pd.Series(
        {
            "riparian_continuity": longest_m,
        }
    )


stats = pd.Series(all_widths).apply(summarize)
out = pd.concat([segments.reset_index(drop=True), stats.reset_index(drop=True)], axis=1)
output_path.parent.mkdir(parents=True, exist_ok=True)
out.to_file(output_path, driver="GPKG")
