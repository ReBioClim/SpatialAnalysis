import folium
import geopandas as gpd
import numpy as np
import pandas as pd
import branca.colormap as bcm


base_path = "data/production/variables/v_all_variables.gpkg"
out_html = "output/html/segment100m_variables_layers.html"


gdf = gpd.read_file(base_path, layer="v_all_variables").to_crs("EPSG:4326")
gdf["geometry"] = gdf.geometry.simplify(0.00001, preserve_topology=False)


# variables shown as "<source_gpkg>:<field>" to match production naming
layer_specs = [
    ("v1_slope", "absolute_slope"),
    ("v1_distance_to_source", "distance_to_source"),
    ("v1_upstream_area", "upstream_area_m2"),
    ("v1_pop_density", "pop_density_1km"),
    ("v2_impervious", "impervious_density"),
    ("v2_canopy", "canopy_ratio"),
    ("v2_richness", "richness_150m"),
    ("v2_shannon", "shannon_150m"),
    ("v2_riparian_width", "riparian_width_mean"),
    ("v2_riparian_width", "riparian_continuity_longest_m"),
    ("v2_floodplain", "floodplain_ratio_250m"),
    ("v2_crossings", "total_crossings"),
    ("v2_underground_ratio", "und_ratio"),
    ("v2_instream_barrier", "barrier_count"),
    ("v2_sinuosity", "sinuosity"),
    ("v2_access_poi", "POI_count"),
    ("v3_accessibility", "poi_access_index"),
    ("v2_access_transport", "stop_count"),
    ("v2_access_transport", "entrance_count"),
    ("v3_accessibility", "transport_access_index"),
    ("v2_access_slowmob", "slowMob_length"),
    ("v3_accessibility", "slowmob_access_index"),
    ("v3_ndvi", "ndvi_0.4_ratio"),
    ("v3_landuse_intensity", "landuse_intensity"),
    ("v3_lst", "lst_mean_100m"),
    ("v3_carbon_sequest", "carbon_sequest"),
    ("v3_flooding", "flooding_proxy_v3_clim"),
    ("v3_visibility", "visibility_ratio"),
]

vars_ok = [
    (src, col)
    for src, col in layer_specs
    if col in gdf.columns and pd.api.types.is_numeric_dtype(gdf[col])
]


# map
m = folium.Map(location=[50.2, 14.5], zoom_start=7, tiles="OpenStreetMap")
folium.TileLayer("CartoDB positron").add_to(m)
folium.TileLayer("CartoDB dark_matter").add_to(m)


# layers
for i, (src, var) in enumerate(vars_ok):

    s = pd.to_numeric(gdf[var], errors="coerce")
    valid = np.isfinite(s)
    if valid.sum() == 0:
        continue

    vmin = float(np.nanpercentile(s[valid], 2))
    vmax = float(np.nanpercentile(s[valid], 98))
    if vmin >= vmax:
        continue

    cmap = bcm.LinearColormap(
        colors=["#440154", "#3b528b", "#21918c", "#5ec962", "#fde725"],
        vmin=vmin,
        vmax=vmax,
    )

    work = gdf[["geometry"]].copy()
    work["segment100_id"] = gdf["segment100_id"]
    work["merged_id"] = gdf["merged_id"]
    if "city" in gdf.columns:
        work["city"] = gdf["city"]
    else:
        work["city"] = "NA"

    work[var] = s
    work["_color"] = "#bdbdbd"
    work.loc[valid, "_color"] = work.loc[valid, var].apply(lambda x: cmap(float(x)))
    work["_val"] = work[var].round(4).astype(str)
    work.loc[~valid, "_val"] = "NA"

    data = work.to_json()

    fg = folium.FeatureGroup(name=f"{src}:{var}", show=(i == 0))

    folium.GeoJson(
        data,
        style_function=lambda f: {
            "color": f["properties"]["_color"],
            "weight": 2,
            "opacity": 0.9,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["segment100_id", "merged_id", "city", "_val"],
            aliases=["segment100_id", "merged_id", "city", var],
        ),
    ).add_to(fg)

    fg.add_to(m)


folium.LayerControl(collapsed=False).add_to(m)


m.save(out_html)