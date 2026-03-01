
import matplotlib.pyplot as plt
import geopandas as gpd
import numpy as np
from matplotlib.colors import BoundaryNorm, LinearSegmentedColormap


plt.rcParams["font.size"] = 10


cities = ["Dresden", "Jablonec", "Poznan", "Senica"]

city_boundaries = {
    "Dresden": "data/input/city_boundaries/city_boundary_Dresden.gpkg",
    "Jablonec": "data/input/city_boundaries/city_boundary_Jablonec.gpkg",
    "Poznan": "data/input/city_boundaries/city_boundary_Poznan.gpkg",
    "Senica": "data/input/city_boundaries/city_boundary_Senica.gpkg",
}


mpi_data = gpd.read_file("data/clustering/selected_variables_100m_with_mpi.gpkg").to_crs("EPSG:25833")

output_dir = "output/visual/mpi_maps"


fig, axes = plt.subplots(2, 2, figsize=(20, 16))
axes = axes.flatten()


all_mpi_values = []
city_data = {}


for city in cities:
    boundary = gpd.read_file(city_boundaries[city]).to_crs("EPSG:25833")
    segments = gpd.sjoin(mpi_data, boundary, how="inner", predicate="intersects")

    valid = segments["MPI"].dropna()

    if len(valid) > 0:
        all_mpi_values.extend(valid.tolist())
        city_data[city] = (boundary, segments, valid)


if len(all_mpi_values) == 0:
    exit()


vmin = int(np.floor(np.percentile(all_mpi_values, 5)))
vmax = int(np.ceil(np.percentile(all_mpi_values, 95)))

bounds = np.arange(vmin, vmax + 2)

colors = [
    "#67001f","#b2182b","#d6604d","#f4a582","#fddbc7",
    "#d1e5f0","#92c5de","#4393c3","#2166ac","#053061"
]

n = len(bounds) - 1

if n > len(colors):
    base = LinearSegmentedColormap.from_list("c", colors, N=256)
    cmap_colors = [base(i/(n-1)) for i in range(n)]
else:
    cmap_colors = colors[:n]

cmap = LinearSegmentedColormap.from_list("mpi", cmap_colors, N=n)
norm = BoundaryNorm(bounds, cmap.N)


for i, city in enumerate(cities):

    ax = axes[i]

    if city not in city_data:
        ax.text(0.5, 0.5, city + "\nNo Data", ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        continue

    boundary, segments, valid = city_data[city]

    boundary.plot(ax=ax, color="lightgray", edgecolor="black", alpha=0.3)

    seg_valid = segments[segments["MPI"].notna()]
    seg_valid.plot(ax=ax, column="MPI", cmap=cmap, norm=norm, linewidth=1.5)

    title = (
        city + "\n"
        + f"MPI: {valid.mean():.2f} ± {valid.std():.2f}\n"
        + f"Range: {valid.min():.2f} - {valid.max():.2f}\n"
        + f"Segments: {len(segments)}"
    )

    ax.set_title(title)
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.3)


sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
sm.set_array([])

cbar = fig.colorbar(
    sm,
    ax=axes,
    fraction=0.015,
    pad=0.01,
    boundaries=bounds,
    ticks=bounds[:-1] + 0.5
)

cbar.set_ticklabels([str(int(b)) for b in bounds[:-1]])
cbar.set_label("MPI Value")


plt.savefig(output_dir + "/mpi_four_cities_2x2.png", dpi=300)
plt.close()