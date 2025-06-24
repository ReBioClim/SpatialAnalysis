import geopandas as gpd
from shapely.ops import linemerge, substring
from shapely.geometry import LineString, MultiLineString
import shapely
import matplotlib.pyplot as plt

# create stream segments
# 0623

stream = gpd.read_file("data/stream_geometry/combined_stream_geometry.gpkg", layer="stream_named_dissolved")  

# randomly select 1 stream from the stream geometry
stream_sample = stream.sample(n=1, random_state=919)
print(stream_sample)
print(stream_sample.crs)

import geopandas as gpd
from shapely.geometry import LineString, MultiLineString, Point
from shapely.ops import substring
import matplotlib.pyplot as plt

stream = gpd.read_file("data/stream_geometry/combined_stream_geometry.gpkg", layer="stream")
stream_sample = stream.sample(n=1, random_state=42).reset_index(drop=True)

stream_sample = stream_sample.to_crs(epsg=25833)
geom = stream_sample.geometry.iloc[0]

# check if the geometry is a LineString or MultiLineString
if isinstance(geom, LineString):
    lines = [geom]
elif isinstance(geom, MultiLineString):
    lines = list(geom.geoms)

interval = 100
split_points = []

#generate split points along the stream line
for line in lines:
    length = line.length
    num_segments = int(length // interval)
    for i in range(1, num_segments):
        dist = i * interval
        pt = line.interpolate(dist)
        split_points.append(pt)

for line in lines:
    split_points.append(line.interpolate(0))
    split_points.append(line.interpolate(line.length))

fig, ax = plt.subplots(figsize=(10, 6))

gpd.GeoSeries(lines, crs=stream_sample.crs).plot(ax=ax, color="lightgray", linewidth=2, label="Stream Line")

gpd.GeoSeries(split_points, crs=stream_sample.crs).plot(ax=ax, color="red", markersize=20, label="Split Points")

plt.legend()
plt.axis("equal")
plt.tight_layout()
plt.show()
