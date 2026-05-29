import os
from itertools import product
import geopandas as gpd
import numpy as np
import pandas as pd
import shap
from sklearn.cluster import KMeans
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler
from xgboost import XGBRegressor
import matplotlib.pyplot as plt


input_file = "data/production/variables/v_all_variables.gpkg"
out_dir = "data/intervention_optimization"
os.makedirs(out_dir, exist_ok=True)

v1 = [
    "absolute_slope",
    "distance_to_source",
    "upstream_area_log",
    "und_ratio",
    "sinuosity",
    "road_barrier",
]

v2 = [
    "impervious_density",
    "canopy_ratio",
    "riparian_width_mean",
    "riparian_continuity_longest_m",
    "riparian_tree_density",
    "edge_density",
    "open_space_ratio",
    "entrance_count",
    "slowMob_length",
    "poi_programme",
    "poi_amenities",
    "stop_count",
]

v3_spec = {
    "hq_mean": 1,
    "ndvi_0.4_ratio": 1,
    "carbon_sequest": 1,
    "lst_mean_100m": -1,
    "flooding_proxy_v3_clim": 1,
    "visibility_ratio": 1,
    "slowmob_access_index": 1,
    "poi_access_index": 1,
    "transport_access_index": 1,
}

bounds = {
    "impervious_density": (-0.20, 0.00),
    "canopy_ratio": (0.00, 0.20),
    "riparian_width_mean": (0.00, 0.15),
    "riparian_continuity_longest_m": (0.00, 0.15),
    "riparian_tree_density": (0.00, 0.20),
    "edge_density": (-0.10, 0.00),
    "open_space_ratio": (0.00, 0.10),
    "entrance_count": (0.00, 0.10),
    "slowMob_length": (0.00, 0.15),
    "poi_programme": (0.00, 0.10),
    "poi_amenities": (0.00, 0.10),
    "stop_count": (0.00, 0.05),
}

n_clusters = 7
n_steps = 7

gdf = gpd.read_file(input_file, layer="v_all_variables")
v3_cols = [v for v in v3_spec if v in gdf.columns]
variables = v1 + v2 + v3_cols

X = gdf[variables].replace([np.inf, -np.inf], np.nan).dropna(subset=v1 + v2).copy()
X_scaled = StandardScaler().fit_transform(X[v1 + v2])
X["cluster"] = KMeans(n_clusters=n_clusters, n_init=30, random_state=42).fit_predict(X_scaled) + 1

df_v3 = X[v3_cols].copy()
for var, sign in v3_spec.items():
    if var in df_v3.columns and sign == -1:
        df_v3[var] = -df_v3[var]

for var in df_v3.columns:
    min_val, max_val = df_v3[var].min(), df_v3[var].max()
    df_v3[var] = (df_v3[var] - min_val) / (max_val - min_val + 1e-9)

X["v3"] = df_v3.mean(axis=1)

shap_rows = []
opt_rows = []
unique_clusters = sorted(X["cluster"].unique())

for c in unique_clusters:
    sub = X[X["cluster"] == c].dropna(subset=v2 + ["v3"]).copy()
    X_c = sub[v2].values
    y_c = sub["v3"].values

    model = XGBRegressor(
        n_estimators=300,
        learning_rate=0.05,
        max_depth=4,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=0,
    )
    
    cv_r2 = float(np.mean(cross_val_score(model, X_c, y_c, cv=5, scoring="r2")))
    model.fit(X_c, y_c)

    explainer = shap.TreeExplainer(model)
    shap_vals = explainer.shap_values(X_c)

    cluster_shap = []
    for i, var in enumerate(v2):
        mean_abs = float(np.abs(shap_vals[:, i]).mean())
        mean_signed = float(shap_vals[:, i].mean())
        shap_rows.append(
            {
                "cluster": c,
                "variable": var,
                "mean_abs_shap": mean_abs,
                "mean_signed_shap": mean_signed,
            }
        )
        cluster_shap.append({"variable": var, "mean_abs_shap": mean_abs})

    cluster_shap_df = pd.DataFrame(cluster_shap).sort_values("mean_abs_shap", ascending=False)
    top5 = cluster_shap_df["variable"].head(5).tolist()

    base = sub[v2].mean()
    v2_range = sub[v2].quantile(0.95) - sub[v2].quantile(0.05)

    grids = []
    for var in top5:
        lower = bounds[var][0] * v2_range[var]
        upper = bounds[var][1] * v2_range[var]
        grids.append(np.linspace(lower, upper, n_steps))

    base_df = pd.DataFrame([base], columns=v2)
    base_y = float(model.predict(base_df)[0])
    
    best_y = base_y
    best_d = {}

    for deltas in product(*grids):
        x_try = base.copy()
        for var, d in zip(top5, deltas):
            x_try[var] += d
            
        x_try_df = pd.DataFrame([x_try], columns=v2)
        y_try = float(model.predict(x_try_df)[0])
        
        if y_try > best_y:
            best_y = y_try
            best_d = dict(zip(top5, deltas))

    delta_pct = (best_y - base_y) / (abs(base_y) + 1e-9) * 100
    
    row = {
        "cluster": c,
        "n": len(sub),
        "cv_r2": cv_r2,
        "v3_baseline": base_y,
        "v3_optimised": best_y,
        "delta_pct": delta_pct,
    }
    
    for i, var in enumerate(top5):
        row[f"top{i+1}"] = var
        row[f"delta{i+1}"] = best_d.get(var, 0.0)
        
    opt_rows.append(row)

shap_df = pd.DataFrame(shap_rows)
opt_df = pd.DataFrame(opt_rows)

shap_df.to_csv(f"{out_dir}/shap_summary.csv", index=False)
opt_df.to_csv(f"{out_dir}/intervention_results.csv", index=False)

fig, ax = plt.subplots(figsize=(10, 4))
plot_data = [X[X["cluster"] == c]["v3"].dropna().values for c in unique_clusters]
ax.boxplot(plot_data, patch_artist=True)
ax.set_xticklabels([f"Cluster {c}" for c in unique_clusters])
ax.set_ylabel("V3 composite score")
plt.tight_layout()
plt.savefig(f"{out_dir}/v3_boxplot.png", dpi=600)
plt.close()

fig, ax = plt.subplots(figsize=(10, 5))
x_pos = np.arange(len(opt_df))
ax.bar(x_pos - 0.2, opt_df["v3_baseline"], 0.4, label="Baseline", color="steelblue")
ax.bar(x_pos + 0.2, opt_df["v3_optimised"], 0.4, label="Optimised", color="tomato")
ax.set_xticks(x_pos)
ax.set_xticklabels([f"Cluster {c}" for c in opt_df["cluster"]])
ax.set_ylabel("V3 composite score")
ax.legend(frameon=False)
plt.tight_layout()
plt.savefig(f"{out_dir}/optimisation_bar.png", dpi=600)
plt.close()

print("n_complete:", len(X))
print("n_clusters:", n_clusters)
print("grid_steps:", n_steps)
print("\nOptimization results per cluster:")

result_print = opt_df.copy()
for col in ["cv_r2", "v3_baseline", "v3_optimised", "delta_pct"]:
    result_print[col] = pd.to_numeric(result_print[col], errors="coerce").round(4)
for col in [c for c in result_print.columns if c.startswith("delta") and c != "delta_pct"]:
    result_print[col] = pd.to_numeric(result_print[col], errors="coerce").round(4)

print(result_print.to_string(index=False))