import geopandas as gpd
import rasterio
import rioxarray
import numpy as np
import matplotlib.pyplot as plt
from shapely.geometry import mapping, LineString
from rasterio.mask import mask
import pandas as pd
from scipy.stats import entropy
import osmnx as ox


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
# 5. sinuosity, 250m stream length
stream_segment = gpd.read_file("data/stream_segments/streamall_segment250.gpkg", driver="GPKG")
print(stream_segment.crs)
print(stream_segment.geom_type)


# sinuosity = actual stream length / straight-line distance between endpoints

def sinuosity_from_geom(geom):
    if geom is None or geom.is_empty:
        return np.nan
    start = geom.coords[0]
    end = geom.coords[-1]
    straight_len = LineString([start, end]).length
    if straight_len == 0:
        return np.nan
    return float(geom.length / straight_len)

# compute sinuosity per segment
sinuosity_vals = stream_segment.geometry.apply(sinuosity_from_geom)
stream_segment["sinuosity"] = sinuosity_vals.values

stream_segment[["segment_id_250", "sinuosity", "geometry"]].to_file(
    "data/variable/stream250_sinuosity.gpkg", driver="GPKG")


# 6. contunuity, 500m stream length (also try 250m)
stream_segment = gpd.read_file("data/stream_segments/streamall_segment250.gpkg", driver="GPKG")
print(stream_segment.crs)

streamall = gpd.read_file("data/stream_geometry/streamall_underground.gpkg",driver="GPKG")

# print column 'tunnel' values
print(streamall["tunnel"].unique()) #[None 'verrohrt' 'culvert' 'yes']

# select the ones except None
underground = streamall[streamall["tunnel"].notna()]
print(underground.crs)
# underground.to_file("data/stream_geometry/streamall_underground.gpkg", driver="GPKG")


# intersect with segments
und_in_seg = gpd.overlay(underground[['geometry']], 
                         stream_segment[['segment_id_250','geometry']], 
                         how='intersection', keep_geom_type=False)


und_in_seg['und_len_m'] = und_in_seg.geometry.length
len_by_seg = und_in_seg.groupby('segment_id_250')['und_len_m'].sum().reset_index()

# merge the length back to the segment
stream_segment = stream_segment.merge(len_by_seg, on='segment_id_250', how='left').fillna({'und_len_m':0})
stream_segment['seg_len_m'] = stream_segment.geometry.length
stream_segment['und_ratio'] = stream_segment['und_len_m'] / stream_segment['seg_len_m']


stream_segment[['segment_id_250','und_len_m','und_ratio','geometry']].to_file(
    "data/variable/stream250_underground_ratio.gpkg", driver="GPKG"
)

# 7 accessibility to POI

stream_segment = gpd.read_file("data/stream_segments/streamall_segment500.gpkg", driver="GPKG")

# read shp file
poi_dresden_pt  = gpd.read_file("data/geofabrik/Dresden/osm_POI_point/osm_POI_point.shp").to_crs("EPSG:25833")
poi_jablonec_pt = gpd.read_file("data/geofabrik/Jablonec/osm_POI_point/osm_POI_point.shp").to_crs("EPSG:25833")
poi_poznan_pt   = gpd.read_file("data/geofabrik/Poznan/osm_POI_point/osm_POI_point.shp").to_crs("EPSG:25833")
poi_senica_pt   = gpd.read_file("data/geofabrik/Senica/osm_POI_point/osm_POI_point.shp").to_crs("EPSG:25833")

poi_dresden_pl  = gpd.read_file("data/geofabrik/Dresden/osm_POI_polygon/osm_POI_polygon.shp").to_crs("EPSG:25833")
poi_jablonec_pl = gpd.read_file("data/geofabrik/Jablonec/osm_POI_polygon/osm_POI_polygon.shp").to_crs("EPSG:25833")
poi_poznan_pl   = gpd.read_file("data/geofabrik/Poznan/osm_POI_polygon/osm_POI_polygon.shp").to_crs("EPSG:25833")
poi_senica_pl   = gpd.read_file("data/geofabrik/Senica/osm_POI_polygon/osm_POI_polygon.shp").to_crs("EPSG:25833")

# combine all POI points and polygons
poi_points = pd.concat([poi_dresden_pt, poi_jablonec_pt, poi_poznan_pt, poi_senica_pt], ignore_index=True)
poi_polygons = pd.concat([poi_dresden_pl, poi_jablonec_pl, poi_poznan_pl, poi_senica_pl], ignore_index=True)

# create poi_polygon_pt for the centroid of each polygon
poi_polygons_pt = poi_polygons.copy()
poi_polygons_pt["geometry"] = poi_polygons_pt.geometry.centroid
poi_polygons_pt = gpd.GeoDataFrame(poi_polygons_pt, geometry="geometry", crs="EPSG:25833")

# all POI = poi_points + poi_polygons_pt
all_poi = pd.concat(
    [poi_points[["geometry"]], poi_polygons_pt[["geometry"]]],
    ignore_index=True)
all_poi = gpd.GeoDataFrame(all_poi, geometry="geometry", crs="EPSG:25833")
all_poi = all_poi[all_poi.geometry.notnull()]

# create buffers around each segment (300 m)
buf300 = stream_segment[["segment_id_500", "geometry"]].copy()
buf300["geometry"] = buf300.geometry.buffer(300)
buf300 = gpd.GeoDataFrame(buf300, geometry="geometry", crs=stream_segment.crs)

# count the number of all POI points within 300 m
joined = gpd.sjoin(all_poi[["geometry"]], buf300, predicate="within", how="inner")
counts = joined.groupby("segment_id_500").size().reset_index(name="poi_count_300m")

# merge back to the stream_segment with count of POI points in the buffer
stream_segment = stream_segment.merge(counts, on="segment_id_500", how="left")
stream_segment["poi_count_300m"] = stream_segment["poi_count_300m"].fillna(0).astype(int)

stream_segment[["segment_id_500", "poi_count_300m", "geometry"]].to_file(
    "data/variable/streamall500_poi300.gpkg", driver="GPKG")
all_poi.to_file("data/variable/poi_points.gpkg", driver="GPKG")


# 8 accessibility to public transportation

stream_segment = gpd.read_file("data/stream_segments/streamall_segment500.gpkg", driver="GPKG")

# read transport shapefiles
transport_dresden  = gpd.read_file("data/geofabrik/Dresden/osm_transportation/osm_transportation.shp").to_crs("EPSG:25833")
transport_jablonec = gpd.read_file("data/geofabrik/Jablonec/osm_transportation/osm_transportation.shp").to_crs("EPSG:25833")
transport_poznan   = gpd.read_file("data/geofabrik/Poznan/osm_transportation/osm_transportation.shp").to_crs("EPSG:25833")
transport_senica   = gpd.read_file("data/geofabrik/Senica/osm_transportation/osm_transportation.shp").to_crs("EPSG:25833")

# combine all transport features
transport_all = pd.concat([transport_dresden, transport_jablonec, transport_poznan, transport_senica], ignore_index=True)

# convert lines/polygons to centroids
geom_type = transport_all.geom_type.astype(str).str.lower()
transport_all.loc[geom_type.str.contains("polygon") | geom_type.str.contains("linestring"), "geometry"] = transport_all.geometry.centroid
transport_all = gpd.GeoDataFrame(transport_all, geometry="geometry", crs="EPSG:25833")
transport_all = transport_all[transport_all.geometry.notnull()]

# create buffers around each segment (300 m)
buf300 = stream_segment[["segment_id_500", "geometry"]].copy()
buf300["geometry"] = buf300.geometry.buffer(300)
buf300 = gpd.GeoDataFrame(buf300, geometry="geometry", crs=stream_segment.crs)

# count the number of transport points within 300 m
joined = gpd.sjoin(transport_all[["geometry"]], buf300, predicate="within", how="inner")
counts = joined.groupby("segment_id_500").size().reset_index(name="pt_count_300m")

# merge back to the stream_segment
stream_segment = stream_segment.merge(counts, on="segment_id_500", how="left")
stream_segment["pt_count_300m"] = stream_segment["pt_count_300m"].fillna(0).astype(int)

# save results
stream_segment[["segment_id_500", "pt_count_300m", "geometry"]].to_file(
    "data/variable/stream500_transport300.gpkg", driver="GPKG"
)
transport_all.to_file("data/variable/transport_points.gpkg", driver="GPKG")

# 9 visibility, 500m segment
stream_segment = gpd.read_file("data/stream_segments/streamall_segment500.gpkg", driver="GPKG")

bld_dresden  = gpd.read_file("data/geofabrik/Dresden/osm_buildings/osm_buildings.shp").to_crs(stream_segment.crs)
bld_jablonec = gpd.read_file("data/geofabrik/Jablonec/osm_buildings/osm_buildings.shp").to_crs(stream_segment.crs)
bld_poznan   = gpd.read_file("data/geofabrik/Poznan/osm_buildings/osm_buildings.shp").to_crs(stream_segment.crs)
bld_senica   = gpd.read_file("data/geofabrik/Senica/osm_buildings/osm_buildings.shp").to_crs(stream_segment.crs)

buildings = gpd.GeoDataFrame(
    pd.concat([bld_dresden[["geometry"]],
               bld_jablonec[["geometry"]],
               bld_poznan[["geometry"]],
               bld_senica[["geometry"]]], ignore_index=True),
    geometry="geometry", crs=stream_segment.crs
)
bld_u = buildings.union_all()

SAMPLE_STEP = 50.0  # every 50m sample point along the stream segment

def mean_nearest_building_distance(line: LineString, step: float = SAMPLE_STEP) -> float:
    L = line.length
    if L <= 0:
        return 0.0
    n = max(1, int(L // step))
    dists = np.linspace(0.0, L, n + 1)
    pts = [line.interpolate(d) for d in dists]
    vals = [p.distance(bld_u) for p in pts]
    return float(np.mean(vals))

# calculate mean distance to nearest building for each segment
stream_segment["visibility"] = stream_segment.geometry.apply(mean_nearest_building_distance)

stream_segment[["segment_id_500", "visibility", "geometry"]].to_file("data/variable/stream500_visibility.gpkg", driver="GPKG")

