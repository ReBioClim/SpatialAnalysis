
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.mask import mask
from natcap.invest import habitat_quality
import glob


# paths
lulc_path = "data/input/ESA_landcover_all.tif"
stream_path = "data/input/streamall_100m_segments_from_mouth.gpkg"

workspace = "output/invest_hq_25833"
inputs = "output/invest_hq_25833/inputs"

lulc_fixed_path = inputs + "/lulc.tif"
threat_path = inputs + "/threat.tif"


# load data
streams = gpd.read_file(stream_path)

stream_buffer = streams.buffer(100).union_all()
aoi = streams.buffer(1000).union_all()


# prepare lulc
with rasterio.open(lulc_path) as src:
    lulc, transform = mask(src, [aoi], crop=True, filled=True, nodata=0)
    lulc = lulc[0]
    profile = src.profile.copy()

valid_codes = np.array([10,20,30,40,50,60,70,80,90,95,100])

lut = valid_codes[np.abs(np.arange(101)[:,None] - valid_codes).argmin(axis=1)]
lulc_fixed = lut[np.clip(lulc,0,100)]

profile.update(
    dtype=rasterio.int16,
    count=1,
    nodata=0,
    compress="lzw",
    height=lulc_fixed.shape[0],
    width=lulc_fixed.shape[1],
    transform=transform
)

with rasterio.open(lulc_fixed_path, "w", **profile) as dst:
    dst.write(lulc_fixed, 1)


# build threat (built-up)
threat = (lulc_fixed == 50).astype(float)

profile.update(dtype=rasterio.float32, nodata=0.0)

with rasterio.open(threat_path, "w", **profile) as dst:
    dst.write(threat, 1)


# threats table
pd.DataFrame([{
    "threat": "built",
    "max_dist": 1.0,
    "weight": 1.0,
    "decay": "exponential",
    "cur_path": threat_path
}]).to_csv(threats_csv, index=False)


# sensitivity table
codes = [0,10,20,30,40,50,60,70,80,90,95,100]

hab = {0:0,10:1,20:0.8,30:0.7,40:0.4,50:0,60:0.2,70:0.1,80:0.9,90:0.8,95:0.9,100:0.3}
sens = {0:0,10:0.9,20:0.8,30:0.7,40:0.5,50:0,60:0.3,70:0.1,80:0.3,90:0.6,95:0.6,100:0.2}

pd.DataFrame([{
    "lucode": c,
    "habitat": hab[c],
    "built": sens[c]
} for c in codes]).to_csv(sens_csv, index=False)


# run invest
args = {
    "workspace_dir": workspace,
    "lulc_cur_path": lulc_fixed_path,
    "threats_table_path": threats_csv,
    "sensitivity_table_path": sens_csv,
    "half_saturation_constant": 0.5,
}

habitat_quality.execute(args)


# find output raster
files = glob.glob(workspace + "/*.tif")
hq_file = [f for f in files if "habitat_quality" in f or "quality" in f][0]


# summarize in 100m buffer
with rasterio.open(hq_file) as src:
    out, _ = mask(src, [stream_buffer], crop=False, filled=False)
    v = out[0].compressed()


summary = pd.DataFrame({
    "metric": [
        "pixel_count",
        "mean",
        "median",
        "std",
        "p10",
        "p90",
        "low_share"
    ],
    "value": [
        len(v),
        np.mean(v),
        np.median(v),
        np.std(v),
        np.percentile(v, 10),
        np.percentile(v, 90),
        np.mean(v < 0.3)
    ]
})

