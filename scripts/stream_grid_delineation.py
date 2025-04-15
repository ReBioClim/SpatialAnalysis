# extract stream from osm

######### collect streams for the four focused cities separately
import osmnx as ox
import geopandas as gpd

place_name = "Dresden, Germany"
# place_name = "Jablonec nad Nisou, Czech Republic"
# place_name = "Poznań, Poland"
# place_name = "Senica, Slovakia"

streams= ox.features_from_place(place_name,tags={"waterway":"stream"})

streams = streams.to_crs(epsg=3857)

print(streams.head())
print(f"Total streams found: {len(streams)}")

streams.to_file("dresden_stream.geojson", driver="GeoJSON")

city_boundary = ox.geocode_to_gdf(place_name) 
city_boundary = city_boundary.to_crs(epsg=3857)


#### method 3: remove overlapping
import geopandas as gp
from shapely.geometry import LineString, box
from shapely.strtree import STRtree

fishnet_boxes = []

# Step 1: Create boxes along streams every 50 meters
for idx, row in streams.iterrows():
    geometry = row.geometry
    
    if isinstance(geometry, LineString):
        distance = 50
        num_points = int(geometry.length // distance)
        
        for i in range(num_points + 1):
            point = geometry.interpolate(i * distance)
            fishnet = box(point.x - 25, point.y - 25, point.x + 25, point.y + 25)
            fishnet_boxes.append(fishnet)

# Step 2: Remove duplicates (exact same geometry)
fishnet_gseries = gp.GeoSeries(fishnet_boxes).drop_duplicates().reset_index(drop=True)

# Step 3: Remove overlaps using spatial indexing (efficient method)
tree = STRtree(fishnet_gseries)
non_overlapping_boxes = []

for geom in fishnet_gseries:
    # Check intersection with already selected boxes
    if not any(geom.intersects(existing_geom) for existing_geom in non_overlapping_boxes):
        non_overlapping_boxes.append(geom)

# Convert back to GeoDataFrame
fishnet_final_gdf = gp.GeoDataFrame(geometry=non_overlapping_boxes, crs=streams.crs)



# Visualize the final result 
fig, ax = plt.subplots(figsize=(12, 8))
city_boundary.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=2)
streams.plot(ax=ax, color="dodgerblue", linewidth=1, alpha=0.7)
fishnet_final_gdf.boundary.plot(ax=ax, color="red", linestyle='--', linewidth=1)
ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, alpha=0.5)
ax.set_title(place_name + " with Non-overlapping Fishnet Grid", fontsize=15)
ax.axis('off')
plt.show()


