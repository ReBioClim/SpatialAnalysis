import geopandas as gpd
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler


stream_features = gpd.read_file("data/production/variables/v_all_variables.gpkg", layer="v_all_variables")

feat_cols = [
    "impervious_density",
    "canopy_ratio",
    "richness_150m",
    "shannon_150m",
    "lst_mean_100m",
    "absolute_slope",
    "total_crossings",
    "poi_access_index",
    "transport_access_index",
    "visibility_ratio",
    "sinuosity",
]

rows_kept = stream_features[feat_cols].notna().all(axis=1)
X = stream_features.loc[rows_kept, feat_cols].values

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

dbscan = DBSCAN(eps=0.10, min_samples=15, metric="cosine")
labels = dbscan.fit_predict(X_scaled)

stream_features["cluster"] = np.nan
stream_features.loc[rows_kept, "cluster"] = labels + 1

out_path = "data/clustering/dbscan_100m_11vars.gpkg"
stream_features.to_file(out_path, driver="GPKG")
