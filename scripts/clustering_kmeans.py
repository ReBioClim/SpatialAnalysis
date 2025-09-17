import pandas as pd
import numpy as np
import geopandas as gpd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
import matplotlib.pyplot as plt
import seaborn as sns


###################
# Clustering analysis
## DBSCAN clustering
stream_features = gpd.read_file("data/variable/stream100_allvariables.gpkg", driver="GPKG")

feat_cols = ['canopy_ratio', 'shannon_150m','richness_150m',
             'und_ratio_x', 'lst_mean_100m', 'sinuosity', 'impervious_ratio',
             'poi_count_300m', 'pt_count_300m', 'visibility']




# Prepare data for clustering (use the feature list defined above)
X_df = stream_features[feat_cols].copy()

# Clean: drop infs/NaNs and keep the row indices so we can write labels back
X_df = X_df.replace([np.inf, -np.inf], np.nan).dropna()
rows_kept = X_df.index

# Correlation matrix (on cleaned data)
corr_matrix = X_df.corr(method='pearson')
plt.figure(figsize=(10, 8))
sns.heatmap(corr_matrix, annot=True, cmap="coolwarm", center=0)
plt.tight_layout()
plt.show()

# Standardize the features
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_df.values)

# Silhouette search for optimal k 
k_min, k_max = 3, 10
n_samples = X_scaled.shape[0]
# Ensure k_max is valid given sample size
k_max = min(k_max, n_samples - 1)

k_values, sil_scores = [], []
for kk in range(k_min, max(k_min, k_max) + 1):
    km = KMeans(n_clusters=kk, n_init=10, random_state=42)
    lbls = km.fit_predict(X_scaled)
    # Silhouette requires at least 2 distinct labels
    if len(np.unique(lbls)) > 1:
        score = silhouette_score(X_scaled, lbls)
    else:
        score = np.nan
    k_values.append(kk)
    sil_scores.append(score)

# Plot silhouette score vs k
plt.figure(figsize=(7, 4))
plt.plot(k_values, sil_scores, marker='o')
plt.xlabel('k (number of clusters)')
plt.ylabel('Silhouette score')
plt.title('Silhouette score vs k')
plt.tight_layout()
plt.show()

# Choose k with the highest silhouette (ignoring NaNs)
valid = ~np.isnan(sil_scores)
if np.any(valid):
    best_k = int(np.array(k_values)[valid][np.argmax(np.array(sil_scores)[valid])])
else:
    best_k = 2
print(f"Chosen k by silhouette: {best_k}")

# Fit final KMeans with best_k
kmeans = KMeans(n_clusters=best_k, n_init=10, random_state=42)
labels = kmeans.fit_predict(X_scaled)

# Compute silhouette score for the chosen k
sil_score = silhouette_score(X_scaled, labels)
print(f"Silhouette Score (k={best_k}): {sil_score:.3f}")

# Write labels back to the original GeoDataFrame (rows not used get -1)
stream_features.loc[:, 'kmeans_label'] = -1
stream_features.loc[rows_kept, 'kmeans_label'] = labels

# Print number of points in each cluster
cluster_counts = pd.Series(labels).value_counts().sort_index()
print("Cluster counts:")
for cluster_id, count in cluster_counts.items():
    print(f"  Cluster {cluster_id}: {count}")

# 2D visualization with PCA
pca = PCA(n_components=2, random_state=42)
X_2d = pca.fit_transform(X_scaled)
plt.figure(figsize=(7, 6))
plt.scatter(X_2d[:, 0], X_2d[:, 1], c=labels)
plt.title(f'KMeans clustering (k={best_k})')
plt.xlabel('PC1')
plt.ylabel('PC2')
plt.tight_layout()
plt.show()

out_path = "data/variable/stream100_kmeans.gpkg"
stream_features.to_file(out_path, driver="GPKG")
print(f"Saved clustered GeoDataFrame to {out_path}")
print(stream_features['kmeans_label'].value_counts().sort_index())
