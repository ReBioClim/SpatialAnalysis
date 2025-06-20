
######check green space types in geofabrik landuse layer
import geopandas as gpd

landuse_path = "/Users/yehanwu/Github-projects/SpatialAnalysis/data/geofabrik/slovakia.shp/gis_osm_landuse_a_free_1.shp" ### to change
landuse_gdf = gpd.read_file(landuse_path)
print(landuse_gdf["fclass"].unique())


import geopandas as gpd
import osmnx as ox
import os

# Set parameters
# place_name = "Dresden, Germany"
# place_name = "Jablonec nad Nisou, Czech Republic"
# place_name = "Poznań, Poland"
place_name = "Senica, Slovakia"    # to change
city_name = "Senica"               # to change
target_crs = "EPSG:25833"         # to change
buffer_dist = 2000


greenspace_fclass = [
    "park", "allotments", "grass", "forest", "scrub", "meadow",
    "recreation_ground", "heath", "nature_reserve", "orchard"
]

# Load and project city boundary
print(f"Getting city boundary for {place_name}...")
city_boundary = ox.geocode_to_gdf(place_name)
city_boundary_proj = city_boundary.to_crs(target_crs)
city_boundary_gdf = gpd.GeoDataFrame(geometry=city_boundary_proj.geometry, crs=target_crs)

# Save city boundary shapefile
boundary_folder = "/Users/yehanwu/Github-projects/SpatialAnalysis/data/geofabrik/boundary"
os.makedirs(boundary_folder, exist_ok=True)
boundary_path = os.path.join(boundary_folder, "osm_city_boundary.shp")
city_boundary_proj.to_file(boundary_path, driver="ESRI Shapefile", index=False)

# Create buffer
buffered = city_boundary_proj.buffer(buffer_dist)
buffered_gdf = gpd.GeoDataFrame(geometry=buffered, crs=target_crs)

# Define data sources
base_path = "/Users/yehanwu/Github-projects/SpatialAnalysis/data/geofabrik/slovakia.shp" #### to change
layers = {
    "roads": f"{base_path}/gis_osm_roads_free_1.shp",
    "buildings": f"{base_path}/gis_osm_buildings_a_free_1.shp",
    "landuse": f"{base_path}/gis_osm_landuse_a_free_1.shp",
    "water_bodies": f"{base_path}/gis_osm_water_a_free_1.shp",
    "waterways": f"{base_path}/gis_osm_waterways_free_1.shp",
    "railways": f"{base_path}/gis_osm_railways_free_1.shp",
    "transportation": f"{base_path}/gis_osm_transport_free_1.shp",
    "POI_point": f"{base_path}/gis_osm_pois_free_1.shp",
    "POI_polygon": f"{base_path}/gis_osm_pois_a_free_1.shp"
}

# Reproject all layers
def change_crs_to_target(layers_dict, target_crs):
    for key, path in layers_dict.items():
        gdf = gpd.read_file(path).to_crs(target_crs)
        layers_dict[key] = gdf
    return layers_dict

layers = change_crs_to_target(layers, target_crs)

# Extract greenspace from landuse
landuse_gdf = layers["landuse"]
greenspace_gdf = landuse_gdf[landuse_gdf["fclass"].isin(greenspace_fclass)]
layers["greenspace"] = greenspace_gdf

# Define clipping boundaries
clip_config = {
    "roads": (layers["roads"], buffered_gdf),
    "railways": (layers["railways"], buffered_gdf),
    "waterways": (layers["waterways"], buffered_gdf),
    "buildings": (layers["buildings"], city_boundary_proj),
    "landuse": (layers["landuse"], city_boundary_proj),
    "greenspace": (layers["greenspace"], city_boundary_proj),
    "water_bodies": (layers["water_bodies"], city_boundary_proj),
    "transportation": (layers["transportation"], city_boundary_proj),
    "POI_point": (layers["POI_point"], city_boundary_proj),
    "POI_polygon": (layers["POI_polygon"], city_boundary_proj)
}

# Clip layers
clipped_layers = {}
for name, (gdf, boundary) in clip_config.items():
    clipped = gpd.clip(gdf, boundary)
    clipped_layers[name] = clipped
    print(f"Clipped {name}: {len(clipped)} features")

# Export all clipped layers
base_output_dir = "/Users/yehanwu/Github-projects/SpatialAnalysis/data/geofabrik/osm_clipped_layers"
# after always showing errors, it seems the data type is messy, so only below were kept
for name, gdf in clipped_layers.items():
    geom_types = gdf.geometry.geom_type.unique()
    print(f"{name}: geometry types -> {geom_types}")

    if name in ["buildings", "landuse", "greenspace", "water_bodies", "POI_polygon"]:  
        gdf = gdf[gdf.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
    elif name in ["roads", "waterways", "railways"]:
        gdf = gdf[gdf.geometry.geom_type.isin(["LineString", "MultiLineString"])]
    elif name in ["transportation", "POI_point"]:
        gdf = gdf[gdf.geometry.geom_type.isin(["Point", "MultiPoint"])]

    folder_path = os.path.join(base_output_dir, f"osm_{name}")
    os.makedirs(folder_path, exist_ok=True)
    output_path = os.path.join(folder_path, f"osm_{name}.shp")

    gdf.to_file(output_path, driver="ESRI Shapefile", index=False)


# 20250620
# create catchment area for the 4 cities
# if the catchment area is intersect with city boundary, then keep the catchment area
# check working directory
os.getcwd()


city_boundary = gpd.read_file("data/city_boundaries/combined_city_boundaries.gpkg")     
catchment_all = gpd.read_file("data/catchment/hybas_lake_eu_lev12_v1c.shp")

print(city_boundary.crs)    
print(catchment_all.crs)

# only keep the full catchment area with city boundary intersected
catchment_all = catchment_all.to_crs(city_boundary.crs)
catchment = catchment_all[catchment_all.geometry.intersects(city_boundary.union_all())].copy()
len(catchment)

catchment.to_file("data/catchment/intersected_catchments.gpkg", driver="GPKG")

# clip waterway and water
# Define data sources
geofabrik_region = "poland"  # to change
city_name = "Poznan"  # to change

water_bodies = gpd.read_file(f"data/geofabrik/{geofabrik_region}.shp/gis_osm_water_a_free_1.shp")
waterways =  gpd.read_file(f"data/geofabrik/{geofabrik_region}.shp/gis_osm_waterways_free_1.shp")

print(water_bodies.crs)
print(waterways.crs)

water_bodies_clip = gpd.overlay(water_bodies, catchment, how="intersection")
waterways_clip    = gpd.overlay(waterways, catchment, how="intersection")

#stream = waterways_clip[waterways_clip["fclass"].isin(["stream", "river"])] # only applies to Senica, since in osm Teplica is both labeled as stream and river, the surrounding rivers were checked as well, also narrow
stream = waterways_clip[(waterways_clip["fclass"] == "stream")]

# only applies to Dresden, include "Prießnitz" river features as pointed out by Nora 
stream = waterways_clip[
    (waterways_clip["fclass"] == "stream") |
    ((waterways_clip["fclass"] == "river") & (waterways_clip["name"] == "Prießnitz"))
].copy()

output_dir = "data/geofabrik"

gpkg_path = os.path.join(output_dir, f"{city_name}_stream_geometry.gpkg")

water_bodies_clip.to_file(gpkg_path, layer="waterbodies", driver="GPKG")
waterways_clip.to_file(gpkg_path, layer="waterways", driver="GPKG")
stream.to_file(gpkg_path, layer="stream", driver="GPKG")

print(water_bodies_clip["fclass"].unique())
print(waterways_clip["fclass"].unique())
print(stream["fclass"].value_counts())