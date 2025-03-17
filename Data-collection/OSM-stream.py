######### collect streams for the four focused cities separately
import osmnx as ox
import geopandas as gpd
import matplotlib.pyplot as plt
import contextily as ctx

place_name = "Dresden, Germany"
place_name = "Jablonec nad Nisou, Czech Republic"
place_name = "Poznań, Poland"
place_name = "Senica, Slovakia"

streams= ox.features_from_place(place_name,tags={"waterway":"stream"})

streams = streams.to_crs(epsg=3857)

print(streams.head())
print(f"Total streams found: {len(streams)}")

streams.to_file("dresden_stream.geojson", driver="GeoJSON")

city_boundary = ox.geocode_to_gdf(place_name)
city_boundary = city_boundary.to_crs(epsg=3857)

# visualise
fig, ax=plt.subplots(figsize=(12,8))
city_boundary.plot(ax=ax, facecolor="none", edgecolor="black", linewidth=2)
streams.plot(ax=ax, color="dodgerblue",linewidth=1, alpha=0.7)
ctx.add_basemap(ax, source=ctx.providers.OpenStreetMap.Mapnik, alpha=0.5)
ax.set_title(place_name,fontsize=15)
ax.axis('off')
plt.show()
