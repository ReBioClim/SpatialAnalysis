import geopandas as gpd

city_name = "Dresden"
grids = gpd.read_file(f"{city_name}_grid_test.gpkg") # call it grids instead of fishnet, fishnet is non-rotated
target_crs = 25833 
print(grids.head())

from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
import matplotlib.pyplot as plt

features = grids[["sinuosity", "impervious_cover", "green_cover"]].copy()
features = features.fillna(0)

# standardise
scaler = StandardScaler()
X_scaled = scaler.fit_transform(features)

#elbow method
inertia = []
k_values = range(2, 10)

for k in k_values:
    km = KMeans(n_clusters=k, random_state=0)
    km.fit(X_scaled)
    inertia.append(km.inertia_)

plt.plot(k_values, inertia, marker='o')
plt.grid(True)
plt.show()

k = 4  
kmeans = KMeans(n_clusters=k, random_state=0)
grids["cluster"] = kmeans.fit_predict(X_scaled)


#print the number of grids in each cluster
cluster_counts = grids["cluster"].value_counts()
print(cluster_counts)
print(grids.head())

grids.to_file(f"{city_name}_grid_test.gpkg", driver="GPKG")

# calculate the centroid of each cluster
centroids = kmeans.cluster_centers_
print(centroids)
# inverse transform the centroids to get the original scale
centroids_original = scaler.inverse_transform(centroids)
print(centroids_original)
#[[1.03344644 0.41445571 0.19419281]
# [1.03220476 0.08459063 0.13746313]
# [1.48306881 0.15034512 0.26008053]
# [1.03011376 0.13247988 0.89955312]]
