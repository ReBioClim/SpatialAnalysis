import geopandas as gpd
import numpy as np
from shapely.geometry import Point


segments = gpd.read_file("data/input/streamall_200m_segments_from_mouth.gpkg")

start = segments.geometry.apply(lambda g: Point(g.coords[0]))
end = segments.geometry.apply(lambda g: Point(g.coords[-1]))
straight = start.distance(end)

out = segments[["segment200_id", "geometry"]].copy()
out["sinuosity"] = segments.geometry.length / straight
out.loc[straight == 0, "sinuosity"] = np.nan

out.to_file("data/production/variables/v2_sinuosity.gpkg", driver="GPKG")
