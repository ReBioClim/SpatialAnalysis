import pandas as pd
import numpy as np
import geopandas as gpd
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
from sklearn.mixture import GaussianMixture
import matplotlib.pyplot as plt
import seaborn as sns
from kneed import KneeLocator



gdf = gpd.read_file("data/variable/stream100_allvariables.gpkg", driver="GPKG")

feat_cols = [
    'canopy_ratio', 'richness_150m', 'shannon_150m',  
    'und_ratio_x', 'lst_mean_100m', 'sinuosity', 'impervious_ratio',
    'poi_count_300m', 'pt_count_300m', 'visibility'
]

# GMM Clustering
# Standardize features and drop rows with missing/infinite values
X = gdf[feat_cols].replace([np.inf, -np.inf], np.nan).dropna()
rows_kept = X.index
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# Use BIC to determine optimal number of clusters
bic = []
aic = []
n_range = range(1, 11)
for n in n_range:
    gmm = GaussianMixture(n_components=n, random_state=42)
    gmm.fit(X_scaled)
    bic.append(gmm.bic(X_scaled))
    aic.append(gmm.aic(X_scaled))

# Select optimal number of clusters based on lowest BIC
optimal_k = n_range[np.argmin(bic)]
print(f"Optimal number of clusters: {optimal_k}")


knee = KneeLocator(n_range, bic, curve="convex", direction="decreasing")
optimal_k = knee.knee
print(f"Optimal cluster by elbow method: {optimal_k}")




 # Plot BIC, AIC, and elbow point in one figure
plt.figure(figsize=(8, 5))
plt.plot(n_range, bic, label='BIC', color='lightblue')
plt.plot(n_range, aic, label='AIC', color='green')
if knee.knee is not None:
    plt.scatter(knee.knee, bic[knee.knee - n_range.start], color='orange', s=100, label=f'Elbow at k={knee.knee}', zorder=5)
plt.xlabel("Number of clusters")
plt.ylabel("Information Criterion")
plt.title("GMM Model Selection (BIC, AIC, Elbow)")
plt.legend()
plt.tight_layout()
plt.show()


# Fit GMM with optimal number of clusters
gmm = GaussianMixture(n_components=5, random_state=88)
gmm_labels = gmm.fit_predict(X_scaled)

# Assign results back to GeoDataFrame
gdf['gmm_label'] = np.nan
gdf.loc[rows_kept, 'gmm_label'] = gmm_labels

# Cluster summary statistics
counts = pd.Series(gmm_labels).value_counts().sort_index()
shares = (counts / len(gmm_labels)).rename('share')
summary_df = pd.concat([counts.rename('count'), shares], axis=1).reset_index().rename(columns={'index': 'label'})
print(summary_df.to_string(index=False, formatters={'share': '{:.1%}'.format}))


# create a column "cluster" for gdf which has value of gmm_label plus 1, when gmm_label is not NULL
gdf['cluster'] = gdf['gmm_label'].fillna(-1).astype(int)
gdf['cluster'] = gdf['gmm_label'] + 1


gdf.to_file("data/variable/stream100_gmm.gpkg", driver="GPKG")


from numpy.linalg import norm

# calculate distance to cluster center
distances = np.array([
    norm(X_scaled[i] - gmm.means_[label])
    for i, label in enumerate(gmm_labels)
])

gdf['gmm_distance'] = np.nan
gdf.loc[rows_kept, 'gmm_distance'] = distances

gdf.to_file("data/variable/stream100_gmm.gpkg", driver="GPKG")


# visualize
# 
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

fig, ax = plt.subplots(1, 1, figsize=(10, 10))
gdf.dropna(subset=['cluster']).plot(
    column='cluster',
    categorical=True,
    cmap='tab10',
    legend=True,
    linewidth=0.5,
    ax=ax,
    edgecolor='black'
)
ax.set_title("GMM Cluster Map (k=5)", fontsize=16)
ax.axis("off")
plt.tight_layout()
plt.show()

import seaborn as sns

plt.figure(figsize=(8, 5))
sns.barplot(
    data=summary_df.sort_values('label'),
    x='label', y='share', palette='Set2'
)
plt.ylabel("Cluster Share")
plt.xlabel("Cluster Label")
plt.title("Proportion of Each GMM Cluster")
plt.ylim(0, 0.5)
for idx, row in summary_df.iterrows():
    plt.text(row['label'], row['share'] + 0.01, f"{row['share']:.1%}", ha='center', fontsize=10)
plt.tight_layout()
plt.show()


from sklearn.decomposition import PCA
import matplotlib.pyplot as plt
import seaborn as sns

# PCA for 2D visualization
pca = PCA(n_components=2)
X_pca = pca.fit_transform(X_scaled)

pca_df = pd.DataFrame(X_pca, columns=["PC1", "PC2"])
pca_df['cluster'] = gdf.loc[rows_kept, 'cluster'].values.astype(int)


cluster_palette = {
    1: "#A8D137",
    2: "#D963D9",
    3: '#E3A382',
    4: "#7940DB",
    5: "#16B290"
}

plt.figure(figsize=(8, 6))
sns.scatterplot(
    data=pca_df,
    x="PC1", y="PC2",
    hue="cluster",
    palette=cluster_palette,
    alpha=0.8,
    s=30
)

plt.title("GMM Clustering in PCA Space")
plt.xlabel("PC1")
plt.ylabel("PC2")
plt.legend(title="Cluster", loc='best')
plt.tight_layout()
plt.show()


from math import pi
import matplotlib.pyplot as plt

gdf.loc[gdf['cluster'].notna(), 'cluster'] = gdf.loc[gdf['cluster'].notna(), 'cluster'].astype(int)

# calculate mean feature values per cluster    
cluster_means = gdf.dropna(subset=['cluster'])[feat_cols + ['cluster']].groupby('cluster').mean()
cluster_means_scaled = pd.DataFrame(StandardScaler().fit_transform(cluster_means),
                                    index=cluster_means.index, columns=cluster_means.columns)

# radar chart setup
labels = feat_cols
n_vars = len(labels)
angles = [n / float(n_vars) * 2 * pi for n in range(n_vars)]
angles += angles[:1]  

# draw radar charts for each cluster
for cluster_id, row in cluster_means_scaled.iterrows():
    values = row.tolist()
    values += values[:1]  

    fig, ax = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
    ax.plot(angles, values, color=cluster_palette[cluster_id], linewidth=2)
    ax.fill(angles, values, color=cluster_palette[cluster_id], alpha=0.3)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylim(-2.5, 2.5)  
    ax.grid(True)
    plt.tight_layout()
    plt.show()


# make 'cluster' column numeric and drop rows where it is NaN
gdf['cluster'] = pd.to_numeric(gdf['cluster'], errors='coerce')
gdf = gdf[gdf['cluster'].notna()]
gdf['cluster'] = gdf['cluster'].astype(int)

cluster_means_original = gdf.groupby('cluster')[feat_cols].mean()

pd.set_option('display.float_format', '{:,.2f}'.format)  
print(cluster_means_original)
cluster_means_original.to_excel("data/cluster_means.xlsx")


import matplotlib.pyplot as plt
import seaborn as sns

# original means
cluster_means_original = gdf.groupby('cluster')[feat_cols].mean().reset_index()

melted = cluster_means_original.melt(id_vars='cluster', var_name='feature', value_name='value')

cluster_palette = {
    1: "#A8D137",
    2: "#D963D9",
    3: "#E3A382",
    4: "#7940DB",
    5: "#16B290"
}

plt.figure(figsize=(12, 6))
sns.barplot(
    data=melted,
    x='feature', y='value', hue='cluster',
    palette=cluster_palette
)
plt.title("Cluster Feature Means (Original Scale)")
plt.ylabel("Mean Value")
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.legend(title="Cluster")
plt.show()