
import matplotlib.pyplot as plt
import numpy as np
import geopandas as gpd
from shapely import wkt
from matplotlib.gridspec import GridSpec


plt.rcParams["font.size"] = 10


cities = ["Dresden", "Jablonec", "Poznan", "Senica"]

city_boundaries = {
    "Dresden": "data/input/city_boundaries/city_boundary_Dresden.gpkg",
    "Jablonec": "data/input/city_boundaries/city_boundary_Jablonec.gpkg",
    "Poznan": "data/input/city_boundaries/city_boundary_Poznan.gpkg",
    "Senica": "data/input/city_boundaries/city_boundary_Senica.gpkg",
}


all_variables = gpd.read_file("data/production/variables/v_all_variables.gpkg").to_crs("EPSG:25833")

output_dir = "output/visual/maps/final"


variables_to_map = [
    ("lst_mean_100m", "RdYlBu_r"),
    ("impervious_density", "Reds"),
    ("canopy_ratio", "Greens"),
    ("shannon_150m", "viridis"),
    ("richness_150m", "plasma"),
    ("landuse_intensity", "YlOrBr"),
    ("absolute_slope", "viridis"),
    ("sinuosity", "plasma"),
    ("und_ratio", "Oranges"),
    ("total_crossings", "Oranges"),
    ("pop_density_1km", "magma"),
    ("poi_access_index", "Blues"),
    ("transport_access_index", "PuBuGn"),
    ("slowmob_access_index", "Greens"),
    ("visibility_ratio", "cividis"),
    ("ndvi_0.4_ratio", "Greens"),
    ("carbon_sequest", "YlGn"),
    ("flooding_proxy_v3_clim", "RdPu"),
]


for var, cmap in variables_to_map:

    all_values = []
    city_data = {}

    for city in cities:

        boundary = gpd.read_file(city_boundaries[city]).to_crs("EPSG:25833")
        segments = gpd.sjoin(all_variables, boundary, how="inner", predicate="intersects")

        if var in segments.columns:
            vals = segments[var].dropna()
            if len(vals) > 0:
                all_values.extend(vals.tolist())
                city_data[city] = (boundary, segments)

    if len(all_values) == 0:
        continue

    vmin, vmax = np.percentile(all_values, [2, 98])

    fig = plt.figure(figsize=(20, 16))
    gs = GridSpec(2, 2, figure=fig)

    for i, city in enumerate(cities):

        ax = fig.add_subplot(gs[i//2, i%2])

        boundary = gpd.read_file(city_boundaries[city]).to_crs("EPSG:25833")
        boundary.plot(ax=ax, color="lightgray", alpha=0.3)

        if city in city_data:

            boundary, segments = city_data[city]

            segments.plot(ax=ax, column=var, cmap=cmap, linewidth=2, vmin=vmin, vmax=vmax)
            boundary.plot(ax=ax, facecolor="none", edgecolor="black")

        ax.set_title(city)
        ax.set_aspect("equal")

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    sm.set_array([])
    fig.colorbar(sm, ax=fig.get_axes())

    plt.savefig(f"{output_dir}/{var}_200m_segments.png", dpi=300)
    plt.close()


morphology_data = gpd.read_file("data/input/all_segments_morphology_adjusted.gpkg").to_crs("EPSG:25833")

cross_valley = morphology_data[
    ["segment200_id", "merged_id", "city", "valley_width", "valley_depth", "valley_width_geometry"]
].dropna(subset=["valley_width_geometry"])

cross_valley["valley_width_geometry"] = cross_valley["valley_width_geometry"].apply(
    lambda x: wkt.loads(x) if isinstance(x, str) else x
)

cross_valley = cross_valley.set_geometry("valley_width_geometry")


cross_vars = [
    ("valley_width", "Blues"),
    ("valley_depth", "Reds"),
]


for var, cmap in cross_vars:

    all_values = []
    city_data = {}

    for city in cities:

        boundary = gpd.read_file(city_boundaries[city]).to_crs("EPSG:25833")
        data = cross_valley[cross_valley["city"] == city]

        if var in data.columns:
            vals = data[var].dropna()
            if len(vals) > 0:
                all_values.extend(vals.tolist())
                city_data[city] = (boundary, data)

    if len(all_values) == 0:
        continue

    vmin, vmax = np.percentile(all_values, [2, 98])

    fig = plt.figure(figsize=(20, 16))
    gs = GridSpec(2, 2, figure=fig)

    for i, city in enumerate(cities):

        ax = fig.add_subplot(gs[i//2, i%2])

        boundary = gpd.read_file(city_boundaries[city]).to_crs("EPSG:25833")
        boundary.plot(ax=ax, color="lightgray", alpha=0.3)

        if city in city_data:

            boundary, data = city_data[city]

            data.plot(ax=ax, column=var, cmap=cmap, linewidth=3, vmin=vmin, vmax=vmax)

            segments = gpd.sjoin(all_variables, boundary, how="inner", predicate="intersects")
            segments.plot(ax=ax, color="yellow", linewidth=1)

        ax.set_title(city)
        ax.set_aspect("equal")

    sm = plt.cm.ScalarMappable(cmap=cmap, norm=plt.Normalize(vmin=vmin, vmax=vmax))
    sm.set_array([])
    fig.colorbar(sm, ax=fig.get_axes())

    plt.savefig(f"{output_dir}/{var}_crosssection.png", dpi=300)
    plt.close()