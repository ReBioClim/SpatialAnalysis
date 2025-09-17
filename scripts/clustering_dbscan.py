import pandas as pd
import numpy as np
import geopandas as gpd
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
import matplotlib.pyplot as plt
import seaborn as sns

# Clustering analysis for stream typology
## data preparation

### 100m 
canopy = gpd.read_file("data/variable/stream100_canopy50.gpkg",driver="GPKG")
diversity = gpd.read_file("data/variable/diversity_buffer150m.gpkg",driver="GPKG")
impervious = gpd.read_file("data/variable/stream100_impervious100.gpkg",driver="GPKG")
lst = gpd.read_file("data/variable/stream100_lst100.gpkg",driver="GPKG")

# merge these into stream100_variables.gpkg, by join the same segment_id field
stream100 = canopy
stream100 = stream100.merge(diversity.drop(columns='geometry', errors='ignore'), on='segment_id', how='left')
stream100 = stream100.merge(impervious.drop(columns='geometry', errors='ignore'), on='segment_id', how='left')
stream100 = stream100.merge(lst.drop(columns='geometry', errors='ignore'), on='segment_id', how='left')

stream100.to_file("data/variable/stream100_variables.gpkg", driver="GPKG")


# 250m
sinuosity = gpd.read_file("data/variable/stream250_sinuosity.gpkg", driver="GPKG")
underground250 = gpd.read_file("data/variable/stream250_underground_ratio.gpkg", driver="GPKG")

# merge these into stream250_variables.gpkg, by join the same segment_id field
stream250 = sinuosity
stream250 = stream250.merge(underground250.drop(columns='geometry', errors='ignore'), on='segment_id_250', how='left')
stream250.to_file("data/variable/stream250_variables.gpkg", driver="GPKG")

# 500m
poi = gpd.read_file("data/variable/stream500_poi300.gpkg", driver="GPKG")
transport = gpd.read_file("data/variable/stream500_transport300.gpkg", driver="GPKG")
underground500 = gpd.read_file("data/variable/stream500_underground_ratio.gpkg", driver="GPKG")
visibility = gpd.read_file("data/variable/stream500_visibility.gpkg", driver="GPKG")

# merge these into stream500_variables.gpkg, by join the same segment_id field
stream500 = poi
stream500 = stream500.merge(transport.drop(columns='geometry', errors='ignore'), on='segment_id_500', how='left')
stream500 = stream500.merge(underground500.drop(columns='geometry', errors='ignore'), on='segment_id_500', how='left')
stream500 = stream500.merge(visibility.drop(columns='geometry', errors='ignore'), on='segment_id_500', how='left')
stream500.to_file("data/variable/stream500_variables.gpkg", driver="GPKG")

# - spatial join 250m and 500m into the 100m,
# only join id fields from 250m/500m
stream100_allvariables = gpd.sjoin(stream100, stream250[['segment_id_250','geometry']], how='left', predicate='intersects', rsuffix='_250')
stream100_allvariables = gpd.sjoin(stream100, stream500[['segment_id_500','geometry']], how='left', predicate='intersects', rsuffix='_500')


# - save the final stream100_variables.gpkg
stream100.to_file("data/variable/stream100_allvariables.gpkg", driver="GPKG")

stream100_allvariables = gpd.read_file("data/variable/stream100_allvariables.gpkg", driver="GPKG")

stream100_allvariables = stream100_allvariables.drop(columns=['index__250', 'index__500'], errors='ignore')

# only keep the first row of each segment_id
stream100_allvariables = stream100_allvariables.groupby('segment_id').first().reset_index()

print(stream100_allvariables.columns)
print(stream100_allvariables.geom_type.unique())

# attach stream250 and stream500 variables with the same segment_id_250 and segment_id_500
stream100_allvariables = stream100_allvariables.merge(stream250.drop(columns='geometry', errors='ignore'), left_on='segment_id_250', right_on='segment_id_250', how='left')
stream100_allvariables = stream100_allvariables.merge(stream500.drop(columns='geometry', errors='ignore'), left_on='segment_id_500', right_on='segment_id_500', how='left')

print(stream100_allvariables.columns)

stream100_allvariables = gpd.GeoDataFrame(stream100_allvariables, geometry='geometry', crs=stream100.crs)
print(stream100_allvariables.crs)
stream100_allvariables.to_file("data/variable/stream100_allvariables.gpkg", driver="GPKG")





###################
# Clustering analysis
## DBSCAN clustering
stream_features = gpd.read_file("data/variable/stream100_allvariables.gpkg", driver="GPKG")


print(stream_features.columns)
print(len(stream_features))
# ['segment_id', 'canopy_ratio', 'richness_150m', 'shannon_150m','impervious_ratio', 
# 'lst_mean_100m', 'segment_id_250', 'segment_id_500',
# 'sinuosity', 'und_len_m_x', 'und_ratio_x', 'poi_count_300m',
# 'pt_count_300m', 'und_len_m_y', 'und_ratio_y', 'visibility','geometry'],dtype='object')


feat_cols = ['canopy_ratio', 'shannon_150m','richness_150m',
             'und_ratio_x', 'lst_mean_100m', 'sinuosity', 'impervious_ratio',
             'poi_count_300m', 'pt_count_300m', 'visibility']

# remove rows with NaN in the feature columns
rows_kept = stream_features[feat_cols].notna().all(axis=1)
X = stream_features.loc[rows_kept, feat_cols].values
print(len(X))

# correlation matrix
corr_matrix = pd.DataFrame(X, columns=feat_cols).corr(method='pearson')

plt.figure(figsize=(10, 8))
sns.heatmap(corr_matrix, annot=True, cmap="coolwarm", center=0)
plt.show()

# standardize the features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

#

min_samples = 15  
nn = NearestNeighbors(n_neighbors=min_samples, metric="cosine")
nn.fit(X_scaled)
distances, _ = nn.kneighbors(X_scaled)

# plot k-distance graph
k_dist = np.sort(distances[:, -1])
plt.plot(k_dist)
plt.ylabel(f"{min_samples}-NN distance (cosine)")
plt.xlabel("Points sorted by distance")
plt.show()

# grid search for eps and min_samples
results = []
for eps in [0.09, 0.10, 0.11, 0.12, 0.13, 0.14, 0.15]:
    for ms in [10, 12, 15, 18]:
        lbl = DBSCAN(eps=eps, min_samples=ms, metric="cosine").fit_predict(X_scaled)
        k = len(set(lbl)) - (1 if -1 in lbl else 0)
        noise = (lbl == -1).mean()
        results.append({"eps": eps, "min_samples": ms, "clusters": k, "noise_ratio": noise})

df_results = pd.DataFrame(results)

# heatmaps for clusters and noise ratio
pivot_clusters = df_results.pivot(index="min_samples", columns="eps", values="clusters")
plt.figure(figsize=(8, 5))
sns.heatmap(pivot_clusters, annot=True, fmt=".0f", cmap="YlGnBu")
plt.title("DBSCAN Clusters Count")
plt.ylabel("min_samples")
plt.xlabel("eps")
plt.show()

# heatmap for noise ratio
pivot_noise = df_results.pivot(index="min_samples", columns="eps", values="noise_ratio")
plt.figure(figsize=(8, 5))
sns.heatmap(pivot_noise, annot=True, fmt=".1%", cmap="YlOrRd")
plt.title("DBSCAN Noise Ratio")
plt.ylabel("min_samples")
plt.xlabel("eps")
plt.show()


# DBSCAN clustering ##core
dbscan = DBSCAN(eps=0.10, min_samples=15, metric="cosine")
labels = dbscan.fit_predict(X_scaled)

n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
n_noise = int((labels == -1).sum())
print(f"Estimated number of clusters: {n_clusters}")
print(f"Estimated number of noise points: {n_noise}")

cluster_counts = pd.Series(labels).value_counts().sort_index()
print(cluster_counts)

#>>> print(cluster_counts)
-1     775
 0      39
 1    2612
 2     130
 3      27
 4      52
 5      21




stream_features['cluster'] = np.nan
stream_features.loc[rows_kept, 'cluster'] = labels

out_path = "data/variable/stream100_dbscan_simple.gpkg"
stream_features.to_file(out_path, driver="GPKG")
print(f"Saved clustering result to {out_path}")