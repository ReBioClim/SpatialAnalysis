
import geopandas as gpd
import pandas as pd
from shapely.ops import linemerge, unary_union
import rasterio
from shapely.geometry import mapping
from rasterio.mask import mask
import numpy as np






##############
# calculate impervious cover, 100m stream length + 100m buffer
stream_segment = gpd.read_file("streamall.gpkg", driver="GPKG")

buffer100 = stream_segment.buffer(50)

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

landcover = rasterio.open("data/landcover/ESA_landcover_all.tif")
print(landcover.crs)


stream100_buffer = stream_segment.to_crs(landcover.crs)

# exact 50 Built-up area as impervious area
# calculate the impervious cover per buffer

def get_impervious_ratio(geometry, raster, class_value=50):
        geom = [mapping(geometry)]

        out_image, _ = mask(dataset=raster, shapes=geom, crop=True)
        data = out_image[0]  

        valid_pixels = data[data != raster.nodata]

        if valid_pixels.size == 0:
            return 0.0  

        impervious_count = np.sum(valid_pixels == class_value)
        return impervious_count / valid_pixels.size


from tqdm import tqdm
tqdm.pandas()  

stream100_buffer["impervious_ratio"] = stream100_buffer["geometry"].progress_apply(
    lambda geom: get_impervious_ratio(geom, landcover)
)

print(stream100_buffer[["segment_id", "impervious_ratio"]].head())
stream100_buffer.to_file("data/stream100_buffer_with_impervious.gpkg", driver="GPKG")
