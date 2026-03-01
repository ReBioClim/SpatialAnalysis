import os
from glob import glob
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.merge import merge
from rasterio.io import MemoryFile
from shapely.ops import linemerge


segments_path = "data/input/streamall_100m_segments_from_mouth.gpkg"
ndvi_dir = "data/input/NDVI_riparian_GEE_Export"
output_path = "data/production/variables/v2_riparian_width.gpkg"

ndvi_threshold = 0.4
transect_step = 10.0
transect_half = 50.0


# mosaic
tiles = sorted(glob(os.path.join(ndvi_dir, "s2_ndvi_growing_season*.tif")))

dss = [rasterio.open(p) for p in tiles]
m, tr = merge(dss)
meta = dss[0].meta.copy()
meta.update(height=m.shape[1], width=m.shape[2], transform=tr)

mem = MemoryFile()
with mem.open(**meta) as dst:
    dst.write(m)

for d in dss:
    d.close()


# load segments
segments = gpd.read_file(segments_path).to_crs("EPSG:25833")


# sample distances
with mem.open() as src:

    px = min(abs(src.transform.a), abs(src.transform.e))

    dist = np.arange(-transect_half, transect_half + px, px)
    if 0 not in dist:
        dist = np.sort(np.append(dist, 0))

    width_mean = []
    width_median = []
    width_max = []


    for geom in segments.geometry:

        if geom.geom_type == "LineString":
            line = geom
        elif geom.geom_type == "MultiLineString":
            m = linemerge(geom)
            line = m if m.geom_type == "LineString" else max(m.geoms, key=lambda x: x.length)
        else:
            line = None


        if line is None:
            width_mean.append(np.nan)
            width_median.append(np.nan)
            width_max.append(np.nan)
            continue


        ds = np.arange(transect_step / 2, line.length, transect_step)

        widths = []


        for d in ds:

            p = line.interpolate(d)
            p0 = line.interpolate(max(0, d - px))
            p1 = line.interpolate(min(line.length, d + px))

            dx = p1.x - p0.x
            dy = p1.y - p0.y

            n = np.hypot(dx, dy)
            if n == 0:
                continue

            pxv = -dy / n
            pyv = dx / n

            coords = [(p.x + dd * pxv, p.y + dd * pyv) for dd in dist]

            vals = np.array([v[0] for v in src.sample(coords)], dtype=float)

            valid = np.isfinite(vals)
            valid &= (vals >= -1) & (vals <= 1)

            if src.nodata is not None:
                valid &= vals != src.nodata

            veg = (vals > ndvi_threshold) & valid

            if len(veg) == 0:
                widths.append(0)
                continue

            i = np.argmin(np.abs(dist))

            if not veg[i]:
                widths.append(0)
                continue

            l = r = i

            while l - 1 >= 0 and veg[l - 1]:
                l -= 1

            while r + 1 < len(veg) and veg[r + 1]:
                r += 1

            w = dist[r] - dist[l] + (dist[1] - dist[0])
            widths.append(w)


        if len(widths) == 0:
            width_mean.append(np.nan)
            width_median.append(np.nan)
            width_max.append(np.nan)
        else:
            a = np.array(widths)
            width_mean.append(a.mean())
            width_median.append(np.median(a))
            width_max.append(a.max())


segments["riparian_width_mean"] = width_mean
segments["riparian_width_median"] = width_median
segments["riparian_continuity_longest_m"] = width_max


segments.to_file(output_path, driver="GPKG")