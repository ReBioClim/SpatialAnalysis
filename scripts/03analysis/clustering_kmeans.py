import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler


input_file = "data/production/variables/v_all_variables.gpkg"
gdf = gpd.read_file(input_file, layer="v_all_variables")


features = [
    "impervious_density",
    "canopy_ratio",
    "richness_150m",
    "shannon_150m",
    "lst_mean_100m",
    "absolute_slope",
    "valley_depth",
    "total_crossings",
    "poi_access_index",
    "transport_access_index",
    "visibility_ratio",
    "sinuosity",
]


# remove invalid values
X = gdf[features].replace([np.inf, -np.inf], np.nan).dropna()
valid_index = X.index


out_dir = "data/clustering/kmeans_12vars"


# feature correlation
corr = X.corr()
plt.figure(figsize=(10, 8))
sns.heatmap(corr, annot=True, cmap="coolwarm", center=0, fmt=".2f")
plt.tight_layout()
plt.savefig(f"{out_dir}/correlation_matrix.png", dpi=300)
plt.close()


# scale for kmeans
X_scaled = StandardScaler().fit_transform(X)


# select k by silhouette
k_values = range(3, min(15, len(X_scaled) - 1) + 1)

def get_score(k):
    labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(X_scaled)
    return silhouette_score(X_scaled, labels) if len(set(labels)) > 1 else np.nan

scores = np.array([get_score(k) for k in k_values])
best_k = k_values[np.nanargmax(scores)] if np.isfinite(scores).any() else 6


plt.figure(figsize=(7, 4))
plt.plot(list(k_values), scores, marker="o")
plt.xlabel("k")
plt.ylabel("silhouette score")
plt.title("silhouette vs k")
plt.tight_layout()
plt.savefig(f"{out_dir}/silhouette_score_vs_k.png", dpi=300)
plt.close()


kmeans = KMeans(n_clusters=best_k, n_init=10, random_state=42)
labels = kmeans.fit_predict(X_scaled)


# assign cluster labels
gdf["kmeans_label"] = -1
gdf.loc[valid_index, "kmeans_label"] = labels + 1


# pca for visualization
X_2d = PCA(n_components=2, random_state=42).fit_transform(X_scaled)

plt.figure(figsize=(7, 6))
plt.scatter(X_2d[:, 0], X_2d[:, 1], c=labels + 1, cmap="tab10", s=10, alpha=0.6)
plt.colorbar(label="cluster")
plt.xlabel("pc1")
plt.ylabel("pc2")
plt.title(f"kmeans k={best_k}")
plt.tight_layout()
plt.savefig(f"{out_dir}/pca_2d_visualization.png", dpi=300)
plt.close()


gdf.to_file(
    f"{out_dir}/kmeans_100m_12vars.gpkg",
    driver="GPKG",
    layer="kmeans_100m_12vars",
)


if "segment100_id" in gdf.columns:
    gdf[["segment100_id", "kmeans_label"]].to_csv(
        f"{out_dir}/kmeans_100m_12vars_labels.csv",
        index=False,
    )


# cluster summary
gdf.groupby("kmeans_label")[features].mean().to_csv(
    f"{out_dir}/kmeans_100m_12vars_cluster_means.csv"
)