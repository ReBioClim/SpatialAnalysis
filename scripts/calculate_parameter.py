
import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

city_name = "Dresden"
grids = gpd.read_file(f"data/fishnet_{city_name}.gpkg") 
streams = gpd.read_file(f"data/stream_geometry/{city_name}_combined_clean_nopt.gpkg")

##############0528
# calculate impervious cover for each grid
city_name = "Dresden"
grids = gpd.read_file(f"data/fishnet_{city_name}.gpkg") 
impervious = gpd.read_file("data/ready/Dresden/Sealing/sealing.gpkg")
# CHECK FIELDS IN IMPERVIOUS DATA]
print(impervious.columns)

# check unique values in the versiegl_kl field
print(impervious["versiegl_kl"].unique())
print(impervious["deskn1"].unique())


# remove the data where field deskn1 =0 data
impervious = impervious[impervious["deskn1"] != 0]
print(impervious.crs)

#plot the impervious data
import matplotlib.pyplot as plt

impervious.plot(color="darkgrey")
plt.title('Impervious surface')
plt.axis("off")
plt.show()

# create grid_id and calculate impervious area for each grid
grids["grid_id"] = grids.index
print(grids.head())

impervious_intersections = gpd.overlay(grids, impervious, how='intersection')
print(impervious_intersections.head())

impervious_intersections.plot()
plt.show()

impervious_intersections["impervious_area"] = impervious_intersections.geometry.area
impervious_area_sum = impervious_intersections.groupby("grid_id")["impervious_area"].sum()
print(impervious_area_sum.head())
grids["impervious_area"] = grids["grid_id"].map(impervious_area_sum)
grids["impervious_area"] = grids["impervious_area"].fillna(0)
grids["impervious_cover"] = grids["impervious_area"] / 10000
grids["impervious_cover"] = grids["impervious_cover"].clip(upper=1)


grids.plot(column="impervious_cover", legend=True)
plt.title("Impervious Cover")
plt.axis("off")
plt.show()

# Save the grids with impervious cover
impervious_intersections.to_file(f"{city_name}_impervious.gpkg", driver="GPKG")
grids.to_file(f"{city_name}_grid_impervious.gpkg", driver="GPKG")

##############
# calculate slope for each grid

# import slope tif
import rasterio
slope = rasterio.open("Dresden_slope.tif") # calculated in qgis-gdal-slope

import matplotlib.pyplot as plt

# Read the first band (slope values)
slope_data = slope.read(1)

# mask no data value
slope_data[slope_data == slope.nodata] = 0
# Plot the slope data
plt.imshow(slope_data, cmap='terrain')
plt.colorbar(label='Slope (degrees)')
plt.title('Slope Map')
plt.axis('off')
plt.show()

#
city_name = "Dresden"
grids = gpd.read_file(f"data/fishnet_{city_name}.gpkg") 
grids["grid_id"] = grids.index

print(grids.head())

from rasterstats import zonal_stats
import geopandas as gpd
# Use the file path to the slope raster
slope_stats = zonal_stats(grids, "Dresden_slope.tif", stats=["mean"], nodata=-9999, geojson_out = True) 
slope_gdf = gpd.GeoDataFrame.from_features(slope_stats)
print(slope_gdf.head())


grids = grids.merge(slope_gdf[["grid_id", "mean"]], on="grid_id", how="left")
grids.rename(columns={"mean": "slope_mean"}, inplace=True)
print(grids.head())

grids.to_file(f"{city_name}_grid_slope.gpkg", driver="GPKG")



###############
#### 0529
from shapely.geometry import LineString, MultiLineString
from matplotlib import pyplot as plt
# calculate crossing count (road+railway crossing streams)
city_name = "Dresden"
grids = gpd.read_file(f"data/fishnet_{city_name}.gpkg") 
roads = gpd.read_file("data/ready/Dresden/osm_roads/osm_roads.shp")
railways = gpd.read_file("data/ready/Dresden/osm_railways/osm_railways.shp")
#combine roads and railways into one GeoDataFrame
transport = gpd.GeoDataFrame(pd.concat([roads, railways], ignore_index=True))
print(transport.head())
print(transport.fclass.unique())
streams = gpd.read_file(f"data/stream_geometry/{city_name}_combined_allstream.gpkg")

# Ensure CRS match
transport = transport.to_crs(grids.crs)
streams = streams.to_crs(grids.crs)

#from shapely.ops import unary_union, linemerge

#  MultiLineString explode to LineString, filter LineString only
streams = streams.explode(index_parts=False)
streams = streams[streams.geometry.type == 'LineString']

transport = transport.explode(index_parts=False)
transport = transport[transport.geometry.type == 'LineString']


fig, ax = plt.subplots(figsize=(10, 10))
streams.plot(ax=ax, color='blue', linewidth=1, label='Streams',alpha=0.7)
transport.plot(ax=ax, color='grey', linewidth=0.3, alpha=0.5, label='Transport')

ax.set_title('Transport and Streams Crossings')
ax.axis('off')
ax.legend()
plt.show()

grids.plot(edgecolor="black", facecolor="lightgray", linewidth=0.5)
plt.title("Grids Geometry")
plt.axis("off")
plt.show()


import matplotlib.pyplot as plt

# Create figure and axis
fig, ax = plt.subplots(figsize=(10, 10))

# Plot the grid polygons (base layer)
grids.plot(edgecolor="black", facecolor="lightgray", linewidth=0.5)

# Overlay the streams as lines
streams.plot(ax=ax, color="blue", linewidth=1, label="Streams")

# Add title and remove axis
ax.set_title("Grids and Streams")
ax.axis("off")

# Optional: Add a legend manually for streams
ax.legend()

plt.show()



# Get line-line intersections as points
crossings = gpd.overlay(transport, streams, how='intersection', keep_geom_type=False)
crossings.geom_type.unique()

crossings = crossings[crossings.geometry.type.isin(['Point', 'MultiPoint'])]
crossings = crossings.explode(index_parts=False)
crossings.head()
crossings = crossings.drop_duplicates(subset=["geometry"])
# check number of crossings
print(len(crossings))
print(len(grids))

# Count crossings in each grid
grids["grid_id"] = grids.index
crossings = crossings.to_crs(grids.crs)

# Perform spatial join to find which crossings fall within each grid
crossings_in_grid = gpd.sjoin(
    crossings, grids[["grid_id", "geometry"]],
    how="inner", predicate="intersects"
)

# Count crossings per grid
crossing_stats = crossings_in_grid.groupby("grid_id").size().reset_index(name="crossing_count")

# Merge crossing counts back to grids
grids = grids.merge(crossing_stats, on="grid_id", how="left")

grids["crossing_count"] = grids["crossing_count"].fillna(0).astype(int)

# calculate number of each crossing count
crossing_count_summary = grids["crossing_count"].value_counts().sort_index()
print(crossing_count_summary)

# Calculate stream length per grid
stream_in_grid = gpd.overlay(streams, grids[["grid_id", "geometry"]], how="intersection")
stream_in_grid["stream_len_m"] = stream_in_grid.geometry.length
stream_len_stats = stream_in_grid.groupby("grid_id")["stream_len_m"].sum().reset_index()
stream_len_stats["stream_length_100m"] = stream_len_stats["stream_len_m"] / 100

# Merge stream length into grids
grids = grids.merge(stream_len_stats[["grid_id", "stream_length_100m"]], on="grid_id", how="left")
grids["stream_length_100m"] = grids["stream_length_100m"].fillna(0)

# Calculate crossing per km of stream
grids["crossing_per_100m_stream"] = grids["crossing_count"] / (grids["stream_length_100m"] )

print(grids.head())
# visualize in 
grids.plot(column="crossing_per_100m_stream", legend=True)
plt.title("Crossings per km of Stream")
plt.axis("off")
plt.show()

grids.to_file(f"{city_name}_grid_crossing.gpkg", driver="GPKG")

##############
# merge the grid_impervious, grid_slope, and grid_crossing, keep only the columns we need
grids_impervious = gpd.read_file(f"{city_name}_grid_impervious.gpkg")
grids_slope = gpd.read_file(f"{city_name}_grid_slope.gpkg")
grids_crossing = gpd.read_file(f"{city_name}_grid_crossing.gpkg")

#print(grids_impervious.head())
grids_slope = grids_slope[["grid_id", "slope_mean"]]
grids_crossing = grids_crossing[["grid_id", "crossing_per_100m_stream"]]

grids_all = grids_impervious.merge(grids_slope, on="grid_id", how="left")
grids_all = grids_all.merge(grids_crossing, on="grid_id", how="left")

print(grids_all.columns.unique())
# select only required columns before saving
grids_all = grids_all[["grid_id", "geometry", "impervious_cover", "slope_mean", "crossing_per_100m_stream"]]
# Rename columns as specified
grids_all = grids_all.rename(
    columns={
        "impervious_cover": "impervious",
        "slope_mean": "slope",
        "crossing_per_100m_stream": "crossing"
    }
)

# save the grids_all
grids_all.to_file("grids_TC.gpkg", driver="GPKG")