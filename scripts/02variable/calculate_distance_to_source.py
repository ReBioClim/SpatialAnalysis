import geopandas as gpd


segments = gpd.read_file("data/input/streamall_200m_segments_from_mouth.gpkg")

channel_len = segments.groupby("merged_id")["end_distance"].max().reset_index()
channel_len = channel_len.rename(columns={"end_distance": "channel_total_len"})
segments = segments.merge(channel_len, on="merged_id", how="left")

segments["distance_to_mouth_mid"] = (segments["start_distance"] + segments["end_distance"]) / 2
segments["distance_to_source"] = segments["channel_total_len"] - segments["distance_to_mouth_mid"]
segments["distance_to_source"] = segments["distance_to_source"].clip(lower=0)
segments["distance_to_source_norm"] = segments["distance_to_source"] / segments["channel_total_len"]

out = segments[["segment200_id", "distance_to_source", "distance_to_source_norm", "geometry"]].copy()
out.to_file("data/production/variables/v1_distance_to_source.gpkg", driver="GPKG")
