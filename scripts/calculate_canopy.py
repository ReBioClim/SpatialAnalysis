import geopandas as gpd
import rasterio
import rioxarray
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import mapping
from rasterio.mask import mask

##############
# calculate canopy cover, 100m stream length + 100m or 50m buffer
stream_segment = gpd.read_file("data/stream_segments/streamall_segment100.gpkg", driver="GPKG")
print(stream_segment.crs)

# create buffer and retain segment_id
buffer = stream_segment.copy()
buffer["geometry"] = buffer.geometry.buffer(50) # try 100 and 50m

# visualize the buffer
buffer.plot()
plt.show()

# land cover
# data source: ESA worldcover 10m
# https://developers.google.com/earth-engine/datasets/catalog/ESA_WorldCover_v100
worldcover_legend = {
    10: {"color": "#006400", "label": "Tree cover"},
    20: {"color": "#ffbb22", "label": "Shrubland"},
    30: {"color": "#ffff4c", "label": "Grassland"},
    40: {"color": "#f096ff", "label": "Cropland"},
    50: {"color": "#fa0000", "label": "Built-up"},
    60: {"color": "#b4b4b4", "label": "Bare / sparse vegetation"},
    70: {"color": "#f0f0f0", "label": "Snow and ice"},
    80: {"color": "#0064c8", "label": "Permanent water bodies"},
    90: {"color": "#0096a0", "label": "Herbaceous wetland"},
    95: {"color": "#00cf75", "label": "Mangroves"},
    100: {"color": "#fae6a0", "label": "Moss and lichen"}
}

# original landcover raster (4326)
landcover_orig = rasterio.open("data/landcover/ESA_landcover_all.tif")
print(landcover_orig.crs)

# reproject to EPSG:25833 with 10m resolution using rioxarray
rds = rioxarray.open_rasterio("data/landcover/ESA_landcover_all.tif")
rds = rds.rio.reproject("EPSG:25833", resolution=10)
rds.rio.to_raster("data/landcover/ESA_landcover_all_25833_10m.tif")

# read the reprojected raster
landcover = rasterio.open("data/landcover/ESA_landcover_all_25833_10m.tif")
print(landcover.crs)

# function to calculate canopy ratio (tree cover area / buffer area)
def get_canopy_ratio(row):
    geom = row.geometry
    shapes = [mapping(geom)]
    
    try:
        out_image, _ = mask(dataset=landcover, shapes=shapes, crop=True)
    except Exception:
        return 0.0  # handle masks with no overlap

    data = out_image[0].astype(np.int32)
    canopy_pixels = np.sum(data == 10)  # class 10 = tree cover
    pixel_area = 100.0  # 10m × 10m
    builtup_area = canopy_pixels * pixel_area

    buffer_area = geom.area
    if buffer_area == 0:
        return 0.0

    return builtup_area / buffer_area

buffer["canopy_ratio"] = buffer.apply(get_canopy_ratio, axis=1)

# attach result back to stream_segment
stream_segment["canopy_ratio"] = buffer["canopy_ratio"]

# some are over 1, as the pixel size can be slightly bigger than buffer size
# so replace those bigger than 1 as 1
stream_segment["canopy_ratio"] = stream_segment["canopy_ratio"].clip(upper=1.0)


stream_segment[["segment_id", "canopy_ratio", "geometry"]].to_file(
    "data/variable/canopy_50.gpkg", driver="GPKG")

# export buffer with canopy ratio
buffer.to_file("data/variable/stream100_buffer50_with_canopy.gpkg", driver="GPKG")


