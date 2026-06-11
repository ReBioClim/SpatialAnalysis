import geopandas as gpd

segments_path = "data/input/streamall_100m_segments_from_mouth.gpkg"
roads_path = "data/input/roads_merged.gpkg"
railways_path = "data/input/railways_merged.gpkg"
output_path = "data/production/variables/v2_road_barrier.gpkg"

buffer_m = 100

road_weights = {
    "motorway": 5.0,
    "trunk": 4.5,
    "primary": 4.0,
    "secondary": 3.0,
    "tertiary": 2.0,
    "residential": 1.5,
    "service": 1.0,
    "unclassified": 1.0,
}

segments = gpd.read_file(segments_path).to_crs("EPSG:25833")
roads = gpd.read_file(roads_path).to_crs(segments.crs)

try:
    railways = gpd.read_file(railways_path).to_crs(segments.crs)
except Exception:
    railways = gpd.GeoDataFrame({"geometry": []}, geometry="geometry", crs=segments.crs)

if "highway" not in roads.columns:
    roads["highway"] = None

buffered = segments[["segment100_id", "geometry"]].copy()
buffered["geometry"] = buffered.geometry.buffer(buffer_m)

road_sindex = roads.sindex
if len(railways) > 0:
    rail_sindex = railways.sindex
else:
    rail_sindex = None

scores = []
for zone in buffered.geometry:
    score = 0.0

    road_ids = list(road_sindex.intersection(zone.bounds))
    if len(road_ids) > 0:
        road_part = roads.iloc[road_ids]
        road_part = road_part[road_part.intersects(zone)].copy()
        for _, row in road_part.iterrows():
            inter_geom = row.geometry.intersection(zone)
            highway = row["highway"]
            if highway is None:
                w = 1.0
            else:
                w = road_weights.get(str(highway).lower(), 1.0)
            score += inter_geom.length * w

    if rail_sindex is not None:
        rail_ids = list(rail_sindex.intersection(zone.bounds))
        if len(rail_ids) > 0:
            rail_part = railways.iloc[rail_ids]
            rail_part = rail_part[rail_part.intersects(zone)].copy()
            for _, row in rail_part.iterrows():
                inter_geom = row.geometry.intersection(zone)
                score += inter_geom.length * 4.0

    scores.append(float(score))

out = segments[["segment100_id", "geometry"]].copy()
out["road_barrier_index"] = scores
out.to_file(output_path, driver="GPKG")
