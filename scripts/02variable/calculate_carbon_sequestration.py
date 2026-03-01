import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping


segments_path = "data/input/streamall_100m_segments_from_mouth.gpkg"
ndvi_dir = "data/input/NDVI_riparian_GEE_Export"
output_path = "data/production/variables/v3_carbon_sequest.gpkg"

years = list(range(2018, 2025))


def mean_ndvi(src, geom):
    img, _ = mask(src, [mapping(geom)], crop=True)

    ndvi = img[0]
    valid = np.isfinite(ndvi) & (ndvi >= -1) & (ndvi <= 1)

    return np.mean(ndvi[valid]) if valid.any() else np.nan


# load segments
segments = gpd.read_file(segments_path)

# buffer 5 meters (riparian zone)
segments["geometry"] = segments.geometry.buffer(5)

# area in hectares
segments["area_ha"] = segments.geometry.area / 10000


# calculate NDVI for each year
for year in years:
    raster_path = f"{ndvi_dir}/ndvi_{year}.tif"

    with rasterio.open(raster_path) as src:
        segments[f"ndvi_{year}"] = segments.geometry.apply(
            lambda g: mean_ndvi(src, g)
        )


# convert NDVI → biomass → carbon
for year in years:
    ndvi_col = f"ndvi_{year}"

    if ndvi_col not in segments:
        continue

    segments[f"agb_{year}"] = (30 * segments[ndvi_col]).clip(lower=0)
    segments[f"carbon_{year}"] = segments[f"agb_{year}"] * 0.47


# carbon sequestration between years
for y0, y1 in zip(years[:-1], years[1:]):
    c0 = f"carbon_{y0}"
    c1 = f"carbon_{y1}"

    if c0 not in segments or c1 not in segments:
        continue

    delta = (segments[c1] - segments[c0]).clip(lower=0)

    segments[f"seq_{y0}_{y1}_t_ha"] = delta
    segments[f"seq_{y0}_{y1}_t"] = delta * segments["area_ha"]


# mean sequestration
seq_cols_ha = [c for c in segments.columns if c.startswith("seq_") and c.endswith("_t_ha")]
seq_cols_abs = [c for c in segments.columns if c.startswith("seq_") and c.endswith("_t")]

segments["seq_mean_t_ha"] = segments[seq_cols_ha].mean(axis=1)
segments["seq_mean_t"] = segments[seq_cols_abs].mean(axis=1)
segments["carbon_sequest"] = segments["seq_mean_t_ha"]


out = segments[["segment100_id", "carbon_sequest", "geometry"]].copy()
out.to_file(output_path, driver="GPKG")