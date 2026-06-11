import geopandas as gpd


segments = gpd.read_file("data/input/streamall_200m_segments_from_mouth.gpkg")

out = segments[["segment200_id", "geometry"]].copy()
out["roads_crossings"] = 0
out["railways_crossings"] = 0
out["total_crossings"] = 0

out.to_file("data/production/variables/v2_crossings.gpkg", driver="GPKG")
