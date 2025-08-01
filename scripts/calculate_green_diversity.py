import geopandas as gpd
import rasterio
import rioxarray
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import mapping
from rasterio.mask import mask
from collections import Counter
from skbio.diversity.alpha import shannon

##############
# calculate canopy cover, 100m stream length + 100m or 50m buffer
stream_segment = gpd.read_file("data/stream_segments/streamall_segment100.gpkg", driver="GPKG")
print(stream_segment.crs)

# create buffer and retain segment_id
buffer = stream_segment.copy()
buffer["geometry"] = buffer.geometry.buffer(150) 

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

# calculate land cover richness and Shannon diversity index for each buffer zone

def calculate_diversity(landcover_raster, buffer_gdf, green_classes=[10, 20, 30, 90, 95]):
    results = []
    for idx, row in buffer_gdf.iterrows():
        geom = [mapping(row['geometry'])]
        out_image, out_transform = mask(landcover_raster, geom, crop=True)
        masked_data = out_image[0]
        masked_data = masked_data[masked_data != landcover_raster.nodata]
        green_pixels = [val for val in masked_data.ravel() if val in green_classes]

        if green_pixels:
            counts = list(Counter(green_pixels).values())
            richness = len(counts)
            shannon_index = shannon(counts, base=2)
        else:
            richness = 0
            shannon_index = 0

        results.append({
            "segment_id": row["segment_id"],
            "richness_150m": richness,
            "shannon_150m": shannon_index,
            "geometry": row["geometry"]
        })

    return gpd.GeoDataFrame(results, geometry="geometry", crs=buffer_gdf.crs)

# Apply function
diversity_gdf = calculate_diversity(landcover, buffer)

