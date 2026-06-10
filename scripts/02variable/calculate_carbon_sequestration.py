import glob
import json
import os
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from natcap.invest import carbon
from rasterio.mask import mask
from shapely.geometry import mapping


lulc_path = "data/input/ESA_landcover_all.tif"
stream_path = "data/input/streamall_100m_segments_from_mouth.gpkg"

workspace = "output/invest_carbon_25833"
inputs = os.path.join(workspace, "inputs")
os.makedirs(inputs, exist_ok=True)

lulc_fixed_path = os.path.join(inputs, "lulc_bas_discrete_esa.tif")
pools_csv = os.path.join(inputs, "carbon_pools.csv")
args_json = os.path.join(inputs, "carbon_args.json")
output_path = "data/production/variables/v3_carbon_sequest.gpkg"


streams = gpd.read_file(stream_path).to_crs("EPSG:25833")
aoi = streams.buffer(1000).union_all()


# carbon storage from current LULC, kept under the historical sequest output path
# clip ESA LULC to AOI and snap to discrete ESA class codes
with rasterio.open(lulc_path) as src:
    lulc, transform = mask(src, [aoi], crop=True, filled=True, nodata=0)
    lulc = lulc[0]
    profile = src.profile.copy()

valid_codes = np.array([10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100], dtype=np.int16)
lut = valid_codes[np.abs(np.arange(101)[:, None] - valid_codes).argmin(axis=1)]
lulc_fixed = lut[np.clip(lulc, 0, 100)]

profile.update(
    dtype=rasterio.int16,
    count=1,
    nodata=0,
    compress="lzw",
    height=lulc_fixed.shape[0],
    width=lulc_fixed.shape[1],
    transform=transform,
)
with rasterio.open(lulc_fixed_path, "w", **profile) as dst:
    dst.write(lulc_fixed, 1)


# carbon pools table
# lucode, c_above, c_below, c_soil, c_dead   (units: Mg C / ha)
pools = [
    # forest / woody
    (10, 60.0, 13.8, 80.0, 5.0),
    (20, 12.0, 3.0, 50.0, 0.5),
    # grass / crop
    (30, 3.5, 9.0, 75.0, 0.0),
    (40, 5.0, 0.5, 50.0, 0.0),
    # urban
    (50, 1.0, 0.2, 30.0, 0.0),
    # bare / snow / water
    (60, 0.1, 0.05, 15.0, 0.0),
    (70, 0.0, 0.0, 0.0, 0.0),
    (80, 0.0, 0.0, 0.0, 0.0),
    # wetland / mangrove / lichen
    (90, 5.0, 5.0, 200.0, 0.5),
    (95, 100.0, 30.0, 250.0, 5.0),
    (100, 0.5, 0.3, 60.0, 0.0),
]
pd.DataFrame(pools, columns=["lucode", "c_above", "c_below", "c_soil", "c_dead"]).to_csv(
    pools_csv, index=False
)


# run InVEST Carbon (storage-only: no alternate scenario, no valuation)
args = {
    "workspace_dir": workspace,
    "results_suffix": "esa25833",
    "lulc_bas_path": lulc_fixed_path,
    "carbon_pools_path": pools_csv,
    "calc_sequestration": False,
    "do_valuation": False,
}
with open(args_json, "w", encoding="utf-8") as f:
    json.dump(args, f, indent=2)

carbon.execute(args)


# per-segment mean of total carbon raster inside 100 m buffer
totc_candidates = sorted(glob.glob(os.path.join(workspace, "c_storage_bas*.tif")))
if not totc_candidates:
    totc_candidates = sorted(glob.glob(os.path.join(workspace, "tot_c_bas*.tif")))
if not totc_candidates:
    raise RuntimeError(f"No total-carbon raster found in {workspace}")
totc_raster = totc_candidates[0]
print(f"Total-carbon raster: {totc_raster}")


def mean_in_buffer(src, geom) -> float:
    out, _ = mask(src, [mapping(geom)], crop=True, filled=False, all_touched=True)
    vals = out[0].compressed().astype(np.float32)
    vals = vals[np.isfinite(vals) & (vals >= 0)]
    return float(np.mean(vals)) if vals.size else np.nan


buffered = streams.copy()
buffered["geometry"] = buffered.geometry.buffer(100)

with rasterio.open(totc_raster) as src:
    carbon_mean = buffered.geometry.apply(lambda g: mean_in_buffer(src, g))

out = streams[["segment100_id", "geometry"]].copy()
out["carbon_storage"] = carbon_mean.values
out.to_file(output_path, driver="GPKG")

print(f"Wrote {len(out)} segments -> {output_path}")
print(out["carbon_storage"].describe().to_string())
