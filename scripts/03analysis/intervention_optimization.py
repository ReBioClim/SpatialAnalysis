import os
import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import shap
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import cross_val_score
from xgboost import XGBRegressor

input_file = "data/production/variables/v_all_variables.gpkg"
out_dir = "data/intervention_optimization"

v1 = ["absolute_slope", "distance_to_source", "upstream_area_log",
      "und_ratio", "sinuosity", "road_barrier"]

v2 = ["impervious_density", "canopy_ratio", "riparian_width_mean",
      "riparian_continuity_longest_m", "riparian_tree_density", "edge_density",
      "open_space_ratio", "entrance_count", "slowMob_length",
      "poi_programme", "poi_amenities", "stop_count"]

# 1: higher is better, -1: lower is better
v3_spec = {
    "hq_mean": 1, "ndvi_0.4_ratio": 1, "carbon_sequest": 1,
    "lst_mean_100m": -1, "flooding_proxy_v3_clim": 1,
    "visibility_ratio": 1, "slowmob_access_index": 1,
    "poi_access_index": 1, "transport_access_index": 1,
}

# acceptable change limits for each variable
bounds = {
    "impervious_density": (-0.20, 0.00), "canopy_ratio": (0.00, 0.20),
    "riparian_width_mean": (0.00, 0.15), "riparian_continuity_longest_m": (0.00, 0.15),
    "riparian_tree_density": (0.00, 0.20), "edge_density": (-0.10, 0.00),
    "open_space_ratio": (0.00, 0.10), "entrance_count": (0.00, 0.10),
    "slowMob_length": (0.00, 0.15), "poi_programme": (0.00, 0.10),
    "poi_amenities": (0.00, 0.10), "stop_count": (0.00, 0.05),
}

n_clusters = 7
n_steps = 7

# load data and extract valid columns
gdf = gpd.read_file(input_file, layer="v_all_variables")

v3_cols = []
for v in v3_spec.keys():
    if v in gdf.columns:
        v3_cols.append(v)

all_cols = v1 + v2 + v3_cols
df = gdf[all_cols].copy()

# remove infinite values and missing rows
df = df.replace(np.inf, np.nan)
df = df.replace(-np.inf, np.nan)
df = df.dropna(subset=v1 + v2)

# standardize data and group into clusters
scaler = StandardScaler()
scaled_data = scaler.fit_transform(df[v1 + v2])

kmeans_model = KMeans(n_clusters=n_clusters, n_init=30, random_state=42)
clusters = kmeans_model.fit_predict(scaled_data)

df["cluster"] = clusters + 1

# calculate the composite v3 score
df_v3 = df[v3_cols].copy()

# flip negative indicators so higher is always better
for var in v3_spec.keys():
    if var in df_v3.columns:
        if v3_spec[var] == -1:
            df_v3[var] = df_v3[var] * -1

# normalize all scores to 0-1 range
for var in df_v3.columns:
    min_val = df_v3[var].min()
    max_val = df_v3[var].max()
    df_v3[var] = (df_v3[var] - min_val) / (max_val - min_val + 0.000000001)

df["v3"] = df_v3.mean(axis=1)

shap_rows = []
opt_rows = []

unique_clusters = df["cluster"].unique()
unique_clusters.sort()

# optimize interventions for each cluster separately
for c in unique_clusters:
    sub = df[df["cluster"] == c].copy()
    sub = sub.dropna(subset=v2 + ["v3"])
    
    x_data = sub[v2].values
    y_data = sub["v3"].values

    # train xgboost model
    model = XGBRegressor(
        n_estimators=300, 
        learning_rate=0.05, 
        max_depth=4,
        subsample=0.8, 
        colsample_bytree=0.8, 
        random_state=42, 
        verbosity=0
    )
    
    cv_scores = cross_val_score(model, x_data, y_data, cv=5, scoring="r2")
    model.fit(x_data, y_data)

    # calculate shap values to find the most important variables
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(x_data)
    
    cluster_shap_list = []
    for i in range(len(v2)):
        var_name = v2[i]
        abs_mean = float(np.abs(shap_values[:, i]).mean())
        signed_mean = float(shap_values[:, i].mean())
        
        row_dict = {
            "cluster": c, 
            "variable": var_name,
            "mean_abs_shap": abs_mean,
            "mean_signed_shap": signed_mean
        }
        shap_rows.append(row_dict)
        cluster_shap_list.append(row_dict)

    cluster_shap_df = pd.DataFrame(cluster_shap_list)
    cluster_shap_df = cluster_shap_df.sort_values(by="mean_abs_shap", ascending=False)
    
    # pick the top 5 most impactful variables
    top5_vars = []
    for v in cluster_shap_df["variable"].head(5):
        top5_vars.append(v)
        
    base = sub[v2].mean()
    p95 = sub[v2].quantile(0.95)
    p05 = sub[v2].quantile(0.05)
    v2_range = p95 - p05
    
    # create test grids based on the allowed bounds
    grids = []
    for var in top5_vars:
        lower_bound = bounds[var][0] * v2_range[var]
        upper_bound = bounds[var][1] * v2_range[var]
        grid_points = np.linspace(lower_bound, upper_bound, n_steps)
        grids.append(grid_points)

    base_df = pd.DataFrame([base])
    base_y = float(model.predict(base_df)[0])
    
    best_y = base_y
    best_d = {}

    # test all combinations to find the highest predicted score
    for d0 in grids[0]:
        for d1 in grids[1]:
            for d2 in grids[2]:
                for d3 in grids[3]:
                    for d4 in grids[4]:
                        
                        x_try = base.copy()
                        
                        x_try[top5_vars[0]] = x_try[top5_vars[0]] + d0
                        x_try[top5_vars[1]] = x_try[top5_vars[1]] + d1
                        x_try[top5_vars[2]] = x_try[top5_vars[2]] + d2
                        x_try[top5_vars[3]] = x_try[top5_vars[3]] + d3
                        x_try[top5_vars[4]] = x_try[top5_vars[4]] + d4
                        
                        x_try_df = pd.DataFrame([x_try])
                        y_try = float(model.predict(x_try_df)[0])
                        
                        if y_try > best_y:
                            best_y = y_try
                            best_d = {
                                top5_vars[0]: d0,
                                top5_vars[1]: d1,
                                top5_vars[2]: d2,
                                top5_vars[3]: d3,
                                top5_vars[4]: d4
                            }

    # record the best results for this cluster
    delta_pct = (best_y - base_y) / (abs(base_y) + 0.000000001) * 100
    
    row_result = {
        "cluster": c, 
        "n": len(sub), 
        "v3_baseline": round(base_y, 4),
        "v3_optimised": round(best_y, 4),
        "delta_pct": round(delta_pct, 2)
    }
    
    for i in range(len(top5_vars)):
        var_name = top5_vars[i]
        row_result["top" + str(i+1)] = var_name
        row_result["delta" + str(i+1)] = round(best_d.get(var_name, 0.0), 4)
            
    opt_rows.append(row_result)

shap_df = pd.DataFrame(shap_rows)
opt_df = pd.DataFrame(opt_rows)

shap_df.to_csv(out_dir + "/shap_summary.csv", index=False)
opt_df.to_csv(out_dir + "/intervention_results.csv", index=False)

# generate boxplot
plt.figure(figsize=(10, 4))
plot_data = []
x_labels = []

for c in unique_clusters:
    v3_scores = df[df["cluster"] == c]["v3"].dropna().values
    plot_data.append(v3_scores)
    x_labels.append("c" + str(c))

plt.boxplot(plot_data, patch_artist=True)
plt.xticks(range(1, len(unique_clusters) + 1), x_labels)
plt.ylabel("v3 composite score")
plt.title("v3 composite score by cluster")
plt.tight_layout()
plt.savefig(out_dir + "/fig_v3_boxplot.png", dpi=150)
plt.close()

# generate bar chart
plt.figure(figsize=(9, 4))

x_positions = np.arange(len(opt_df))
baselines = opt_df["v3_baseline"].values
optimized = opt_df["v3_optimised"].values
cluster_labels = []
for c in opt_df["cluster"]:
    cluster_labels.append("c" + str(c))

plt.bar(x_positions - 0.2, baselines, width=0.35, label="baseline", color="steelblue", alpha=0.8)
plt.bar(x_positions + 0.2, optimized, width=0.35, label="optimised", color="tomato", alpha=0.8)

plt.xticks(x_positions, cluster_labels)
plt.ylabel("v3 composite score")
plt.title("baseline vs optimised v3 per cluster")
plt.legend()
plt.tight_layout()
plt.savefig(out_dir + "/fig_optimisation.png", dpi=150)
plt.close()