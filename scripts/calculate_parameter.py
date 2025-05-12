
import geopandas as gpd
from shapely.geometry import LineString

city_name = "Dresden"
grids = gpd.read_file(f"fishnet_{city_name}.gpkg") # call it grids instead of fishnet, fishnet is non-rotated
streams = gpd.read_file(f"streams_{city_name}_singleline.gpkg")
target_crs = 25833 

##############
#  Calculate sinuosity for each grid
sinuosity_values = []

for square in grids.geometry:
    # Clip the stream inside the square
    clipped = streams.intersection(square)
    clipped = clipped[~clipped.is_empty]  # remove empty
    
    total_channel_length = 0 
    total_downvalley_length = 0
    
    for part in clipped:
        if isinstance(part, LineString):
            channel_length = part.length
            coords = part.coords
            start = coords[0]
            end = coords[-1]
            downvalley_length = LineString([start, end]).length
            
            total_channel_length += channel_length
            total_downvalley_length += downvalley_length
    
    # Calculate sinuosity for this square
    if total_downvalley_length > 0:
        sinuosity = total_channel_length / total_downvalley_length
    else:
        sinuosity = None  # if no valid stream inside
    
    sinuosity_values.append(sinuosity)

# Add as a new column
grids["sinuosity"] = sinuosity_values

grids.to_file(f"{city_name}_stream_sinuosity.gpkg", driver="GPKG")

print(grids.head())

##############
#  Calculate building coverage for each grid
footprint = gpd.read_file("data/ready/Dresden/osm_buildings/osm_buildings.shp")
# check footprint crs
print(footprint.crs)
print(grids.crs)
#footprint = footprint.to_crs(grids.crs)

# Clip buildings to each grid (intersection)
intersections = gpd.overlay(grids, footprint, how='intersection')

# calculate area of buildings within each grid cell
intersections["building_area"] = intersections.geometry.area

# Sum building area per grid (group by original grid index)
building_area_sum = intersections.groupby(intersections.index)["building_area"].sum()

# Add area columns to the grid
grids["grid_area"] = grids.geometry.area
grids["building_area"] = building_area_sum
grids["building_area"] = grids["building_area"].fillna(0)

# calculate building coverage ratio
grids["building_cover"] = grids["building_area"] / grids["grid_area"]
grids.to_file(f"{city_name}_grid_test.gpkg", driver="GPKG")

print(grids[["sinuosity", "building_cover"]].head())


##############
#  Calculate green cover for each grid
greenspace = gpd.read_file("data/ready/Dresden/osm_greenspace/osm_greenspace.shp")
# check footprint crs
print(greenspace.crs)
print(grids.crs)

green_intersections = gpd.overlay(grids, greenspace, how='intersection')

green_intersections["green_area"] = green_intersections.geometry.area

green_area_sum = green_intersections.groupby(green_intersections.index)["green_area"].sum()

grids["green_area"] = green_area_sum
grids["green_area"] = grids["green_area"].fillna(0)

grids["green_cover"] = grids["green_area"] / grids["grid_area"]

grids.to_file(f"{city_name}_grid_test.gpkg", driver="GPKG")

print(grids[["sinuosity", "building_cover", "green_cover"]].head())

