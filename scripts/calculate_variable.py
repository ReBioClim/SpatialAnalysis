import geopandas as gpd
import rasterio
import rioxarray
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import mapping
from rasterio.mask import mask
import pandas as pd
from scipy.stats import entropy

##############
# to calculate each variable, 
# clarify the length of stream line and the size of buffer radius, and other data needed


#  for 100m stream length
stream_segment = gpd.read_file("data/stream_segments/streamall_segment100.gpkg", driver="GPKG")
print(stream_segment.crs)

#  the variables are:
## variable 1. impervious cover 
### (built-up area / buffer area), 100m buffer

## variable 2. canopy cover 
### (tree cover area / buffer area), 50m buffer

## variable 3. green richness and shannon diversity index 
###   (number of unique green classes, and the Shannon index of green classes), 150m buffer

## variable 4. land surface temperature
### (average LST in the buffer), 50m buffer

# 1. impervious cover, 100m stream length + 100m buffer
# create buffer and retain segment_id
buffer = stream_segment.copy()
buffer["geometry"] = buffer.geometry.buffer(100) 

# visualize the buffer
# buffer.plot()
# plt.show()

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
# landcover_orig = rasterio.open("data/landcover/ESA_landcover_all.tif")

# reproject to EPSG:25833 with 10m resolution using rioxarray
# rds = rioxarray.open_rasterio("data/landcover/ESA_landcover_all.tif")
# rds = rds.rio.reproject("EPSG:25833", resolution=10)
# rds.rio.to_raster("data/landcover/ESA_landcover_all_25833_10m.tif")

# read the reprojected raster
landcover = rasterio.open("data/landcover/ESA_landcover_all_25833_10m.tif")
print(landcover.crs)

# function to calculate impervious ratio (built-up area / buffer area)
def get_impervious_ratio(row):
    geom = row.geometry
    shapes = [mapping(geom)]
    
    try:
        out_image, _ = mask(dataset=landcover, shapes=shapes, crop=True)
    except Exception:
        return 0.0  # handle masks with no overlap

    data = out_image[0].astype(np.int32)
    impervious_pixels = np.sum(data == 50)  # class 50 = built-up
    pixel_area = 100.0  # 10m × 10m
    impervious_area = impervious_pixels * pixel_area

    buffer_area = geom.area
    if buffer_area == 0:
        return 0.0

    return impervious_area / buffer_area

buffer["impervious_ratio"] = buffer.apply(get_impervious_ratio, axis=1)

# join impervious_ratio back to stream_segment using segment_id
impervious_df = buffer[["segment_id", "impervious_ratio"]]
stream_segment = stream_segment.merge(impervious_df, on="segment_id", how="left")

# some are over 1, as the pixel size can be slightly bigger than buffer size
# so replace those bigger than 1 as 1
stream_segment["impervious_ratio"] = stream_segment["impervious_ratio"].clip(upper=1.0)

stream_segment[["segment_id", "impervious_ratio", "geometry"]].to_file(
    "data/variable/stream100_impervious100.gpkg", driver="GPKG")



# 2. canopy cover, 100m stream length + 50m buffer
buffer = stream_segment.copy()
buffer["geometry"] = buffer.geometry.buffer(50) 

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
    canopy_area = canopy_pixels * pixel_area

    buffer_area = geom.area
    if buffer_area == 0:
        return 0.0

    return canopy_area / buffer_area

buffer["canopy_ratio"] = buffer.apply(get_canopy_ratio, axis=1)

# attach canopy_ratio back to stream_segment using segment_id
canopy_df = buffer[["segment_id", "canopy_ratio"]]
stream_segment = stream_segment.merge(canopy_df, on="segment_id", how="left")

# some are over 1, as the pixel size can be slightly bigger than buffer size
# so replace those bigger than 1 as 1
stream_segment["canopy_ratio"] = stream_segment["canopy_ratio"].clip(upper=1.0)

stream_segment[["segment_id", "canopy_ratio", "geometry"]].to_file(
    "data/variable/stream100_canopy50.gpkg", driver="GPKG")




############################
# 3. green richness and shannon diversity index
# calculate diversity index, 100m stream length + 150m buffer
buffer_150 = stream_segment.copy()
buffer_150["geometry"] = buffer_150.geometry.buffer(150)

# green classes for diversity calculations
green_classes = [10, 20, 30, 90, 95]

def get_diversity_indices(row):
    geom = row.geometry
    shapes = [mapping(geom)]
    
    try:
        out_image, _ = mask(dataset=landcover, shapes=shapes, crop=True)
    except Exception:
        return pd.Series({"richness_150m": 0, "shannon_150m": 0.0})

    data = out_image[0].astype(np.int32)
    # mask pixels not in green classes
    mask_valid = np.isin(data, green_classes)
    data_green = data[mask_valid]

    if data_green.size == 0:
        return pd.Series({"richness_150m": 0, "shannon_150m": 0.0})

    # richness: number of unique green classes present
    richness = len(np.unique(data_green))

    # calculate proportions for shannon index
    counts = np.array([np.sum(data_green == c) for c in green_classes if c in data_green])
    proportions = counts / counts.sum()
    shannon = entropy(proportions, base=np.e)

    return pd.Series({"richness_150m": richness, "shannon_150m": shannon})

diversity_buffer = buffer_150.apply(get_diversity_indices, axis=1)

buffer_150 = pd.concat([buffer_150, diversity_buffer], axis=1)

# attach diversity indices back to stream_segment using segment_id
diversity_df = buffer_150[["segment_id", "richness_150m", "shannon_150m"]]
stream_segment = stream_segment.merge(diversity_df, on="segment_id", how="left")

stream_segment[["segment_id", "richness_150m", "shannon_150m", "geometry"]].to_file(
    "data/variable/stream100_diversity150.gpkg", driver="GPKG")




########
# 4. land surface temperature, 100m stream length + 100m buffer
buffer = stream_segment.copy()
buffer["geometry"] = buffer.geometry.buffer(100)

lst_raster = rasterio.open("data/LST/2024summer.tif")  


def get_lst_mean(row):
    geom = [mapping(row.geometry)]

    try:
        out_image, _ = mask(dataset=lst_raster, shapes=geom, crop=True)
        data = out_image[0].astype(np.float32)

        valid_data = data[(data > 270) & (data < 330)]  # Kelvin range for LST

        if valid_data.size == 0:
            return np.nan

        return float(np.mean(valid_data) - 273.15)

    except Exception:
        return np.nan

buffer["lst_mean_100m"] = buffer.apply(get_lst_mean, axis=1)

print(buffer.columns)
print(buffer.head())

lst_df = buffer[["segment_id", "lst_mean_100m"]]
stream_segment = stream_segment.merge(lst_df, on="segment_id", how="left")
stream_segment[["segment_id", "lst_mean_100m", "geometry"]].to_file(
    "data/variable/stream100_lst100.gpkg", driver="GPKG")



########
# 5. sinuosity, 300m stream length







# 6. crossability, 500m stream length