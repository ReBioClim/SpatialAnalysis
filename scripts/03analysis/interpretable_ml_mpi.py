import geopandas as gpd
import lightgbm as lgb
import numpy as np
import pandas as pd
import shap
from sklearn.cluster import KMeans
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.preprocessing import StandardScaler


# data
gdf = gpd.read_file("data/clustering/selected_variables_100m_with_mpi.gpkg")


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


# clustering
X_cluster = gdf[features].dropna()

scaler = StandardScaler()
X_scaled = scaler.fit_transform(X_cluster)

kmeans = KMeans(n_clusters=6)
labels = kmeans.fit_predict(X_scaled)

gdf["kmeans_label"] = -1
gdf.loc[X_cluster.index, "kmeans_label"] = labels


# city
cities = ["Dresden", "Jablonec", "Poznan", "Senica"]

gdf["city"] = None

for city in cities:
    boundary = gpd.read_file(f"data/input/city_boundaries/city_boundary_{city}.gpkg")
    boundary = boundary.to_crs("EPSG:25833")

    res = gpd.sjoin(gdf, boundary, how="inner", predicate="intersects")
    gdf.loc[res.index, "city"] = city


# data for model
data = gdf[features + ["MPI", "kmeans_label", "city"]].dropna()


# encode city
city_map = {"Dresden": 0, "Jablonec": 1, "Poznan": 2, "Senica": 3}
data["city_code"] = data["city"].map(city_map)


# X and y
X_num = data[features].values
X_cat = data[["kmeans_label", "city_code"]].values

X = np.hstack([X_num, X_cat])
y = data["MPI"].values


# leave one city out
logo = LeaveOneGroupOut()
groups = data["city_code"].values

for train_idx, test_idx in logo.split(X, y, groups):

    X_train = X[train_idx]
    X_test = X[test_idx]

    y_train = y[train_idx]
    y_test = y[test_idx]

    train_data = lgb.Dataset(X_train, label=y_train)

    params = {
        "objective": "regression",
        "metric": "rmse",
        "learning_rate": 0.05,
        "verbose": -1,
    }

    model = lgb.train(params, train_data, num_boost_round=100)


# full model
train_data = lgb.Dataset(X, label=y)
model = lgb.train(params, train_data, num_boost_round=100)


# shap
explainer = shap.TreeExplainer(model)
shap_values = explainer.shap_values(X)


# importance
importance = np.abs(shap_values).mean(0)

feature_names = features + ["cluster", "city"]

imp_df = pd.DataFrame({
    "feature": feature_names,
    "importance": importance
}).sort_values("importance", ascending=False)


# cluster summary
summary = []

for c in sorted(data["kmeans_label"].unique()):

    d = data[data["kmeans_label"] == c]

    if len(d) == 0:
        continue

    mpi_mean = d["MPI"].mean()

    shap_c = shap_values[data["kmeans_label"] == c]
    imp_c = np.abs(shap_c).mean(0)

    top_var = feature_names[np.argmax(imp_c)]

    summary.append([c, len(d), mpi_mean, top_var])


summary = pd.DataFrame(summary, columns=["cluster", "n", "mpi_mean", "top_var"])