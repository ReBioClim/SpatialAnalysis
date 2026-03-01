import geopandas as gpd
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
import contextily as ctx
import rasterio
from shapely.geometry import box
from rasterio.windows import from_bounds
from matplotlib.patches import Patch
from PIL import Image


input_gpkg = "data/clustering/kmeans_12vars/kmeans_100m_12vars.gpkg"
dtm_30m = "data/input/DTM_30m.tif"

radar_dir = "output/visual/clustering/radar"
top5_dir = "output/visual/clustering/top5_osm_dtm_30m"
merged_dir = "output/visual/clustering/merged_top5_radar_city"


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


# load
gdf = gpd.read_file(input_gpkg)

mask = gdf[features].replace([np.inf, -np.inf], np.nan).notna().all(axis=1)
gdf = gdf[mask]

X = gdf[features].values
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)


# clusters
clusters = sorted(gdf["kmeans_label"].unique())


# radar
for cid in clusters:

    idx = gdf[gdf["kmeans_label"] == cid].index
    arr = X_scaled[gdf.index.get_indexer(idx)].mean(axis=0)

    angles = np.linspace(0, 2*np.pi, len(features), endpoint=False)
    angles = np.append(angles, angles[0])
    vals = np.append(arr, arr[0])

    fig = plt.figure()
    ax = plt.subplot(111, polar=True)

    ax.plot(angles, vals)
    ax.fill(angles, vals, alpha=0.2)

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(features, fontsize=8)

    plt.title(f"Cluster {cid}")

    plt.savefig(f"{radar_dir}/radar_kmeans_cluster_{cid-1}.png")
    plt.close()


# top5 (osm + dtm)
for cid in clusters:

    idx = gdf[gdf["kmeans_label"] == cid].index

    Xc = X_scaled[gdf.index.get_indexer(idx)]
    center = Xc.mean(axis=0)

    dists = np.linalg.norm(Xc - center, axis=1)
    top5 = np.argsort(dists)[:5]

    seg_ids = idx[top5]

    fig, axes = plt.subplots(5, 2, figsize=(10, 25))

    for i, seg_idx in enumerate(seg_ids):

        row = gdf.loc[seg_idx]
        geom = row.geometry

        g = gpd.GeoDataFrame([row], geometry="geometry", crs=gdf.crs).to_crs(3857)

        ax1 = axes[i, 0]
        ax2 = axes[i, 1]

        ctx.add_basemap(ax1)

        g.plot(ax=ax1, color="red", linewidth=3)
        ax1.axis("off")

        with rasterio.open(dtm_30m) as src:
            bounds = geom.bounds
            window = from_bounds(*bounds, src.transform)
            img = src.read(1, window=window)

            ax2.imshow(img, cmap="terrain")

        g.plot(ax=ax2, color="red", linewidth=3)
        ax2.axis("off")

    plt.savefig(f"{top5_dir}/cluster_{cid}_top5_osm_dtm.png")
    plt.close()


# merge images
for cid in clusters:

    left = f"{top5_dir}/cluster_{cid}_top5_osm_dtm.png"
    right = f"{radar_dir}/radar_kmeans_cluster_{cid-1}.png"

    img1 = Image.open(left)
    img2 = Image.open(right)

    h = max(img1.height, img2.height)
    w = img1.width + img2.width

    new = Image.new("RGB", (w, h), "white")
    new.paste(img1, (0, 0))
    new.paste(img2, (img1.width, 0))

    new.save(f"{merged_dir}/cluster_{cid}_merged.png")