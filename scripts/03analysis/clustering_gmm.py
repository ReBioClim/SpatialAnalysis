import geopandas as gpd
import numpy as np
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler


gdf = gpd.read_file("data/production/variables/v_all_variables.gpkg", layer="v_all_variables")

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

X = gdf[feat_cols].replace([np.inf, -np.inf], np.nan).dropna()
rows_kept = X.index
X_scaled = StandardScaler().fit_transform(X.values)

gmm = GaussianMixture(n_components=5, random_state=42)
labels = gmm.fit_predict(X_scaled)

gdf["gmm_label"] = np.nan
gdf.loc[rows_kept, "gmm_label"] = labels + 1

gdf.to_file(
    "data/clustering/gmm_100m_11vars.gpkg",
    driver="GPKG",
    layer="gmm_100m_11vars",
)
