import geopandas as gpd


segments = gpd.read_file("data/stream_segments/streams_03_segments_200m.gpkg")

segments["distance_to_mouth_mid"] = (
    segments["distance_from_mouth_start"] + segments["distance_from_mouth_end"]
) / 2
segments["distance_to_source"] = segments["channel_length"] - segments["distance_to_mouth_mid"]
segments["distance_to_source"] = segments["distance_to_source"].clip(lower=0)
segments["distance_to_source_norm"] = segments["distance_to_source"] / segments["channel_length"]

out = segments[["segment200_id", "distance_to_source", "distance_to_source_norm", "geometry"]].copy()
out.to_file("data/production/variables/v1_distance_to_source.gpkg", driver="GPKG")
