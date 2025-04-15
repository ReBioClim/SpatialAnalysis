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

streams.to_file("dresden_stream.geojson", driver="GeoJSON")

city_boundary = ox.geocode_to_gdf(place_name) 
city_boundary = city_boundary.to_crs(epsg=3857)

# list all the variables in the attribute table
print(streams.columns)

#count the number of the names
print(streams['name'].value_counts())

# Dissolve stream geometries by name
streams_dissolved = streams.dissolve(by='name')

# Reset index to turn 'name' back into a column
streams_dissolved = streams_dissolved.reset_index()

# Save the dissolved streams to a new GeoJSON file
streams_dissolved.to_file("dresden_stream_dissolved.geojson", driver="GeoJSON")

# convert to shp
streams_dissolved.to_file("dresden_stream_dissolved.shp", driver="ESRI Shapefile")

# =============================
# Plot Geberbach at 4 Scales
# =============================
import matplotlib.pyplot as plt
import contextily as ctx

# Filter Geberbach
geberbach = streams_dissolved[streams_dissolved['name'].str.contains("Geberbach", case=False, na=False)]

if geberbach.empty:
    raise ValueError("Geberbach not found in dissolved streams.")

# Catchment (1000m buffer and envelope)
catchment_buffer = geberbach.buffer(1000).geometry.envelope
catchment_gdf = gpd.GeoDataFrame(geometry=catchment_buffer, crs=geberbach.crs)

# Stream Corridor (50m buffer)
corridor_buffer = geberbach.buffer(50)
corridor_gdf = gpd.GeoDataFrame(geometry=corridor_buffer, crs=geberbach.crs)

# Pilot Channel (5m buffer)
pilot_buffer = geberbach.buffer(5)
pilot_gdf = gpd.GeoDataFrame(geometry=pilot_buffer, crs=geberbach.crs)

# Plotting function
def plot_layer(layer_gdf, title, geberbach_line, filename=None):
    fig, ax = plt.subplots(figsize=(10, 10))
    layer_gdf.plot(ax=ax, color='lightblue', edgecolor='black', label=title)
    geberbach_line.plot(ax=ax, color='darkblue', linewidth=2, label='Geberbach Stream')
    ctx.add_basemap(ax, crs=layer_gdf.crs.to_string(), source=ctx.providers.OpenStreetMap.Mapnik)
    ax.set_title(title, fontsize=14)
    ax.set_xlabel("Easting (meters)")
    ax.set_ylabel("Northing (meters)")
    ax.legend()
    ax.axis("equal")
    plt.tight_layout()
    if filename:
        plt.savefig(filename, dpi=300)
    plt.show()

# Plot each scale separately
plot_layer(city_boundary, "City Boundary (Dresden)", geberbach)
plot_layer(catchment_gdf, "Catchment (~1000m Buffer)", geberbach)
plot_layer(corridor_gdf, "Stream Corridor (~50m Buffer)", geberbach)
plot_layer(pilot_gdf, "Pilot Channel (~5m Buffer)", geberbach)
