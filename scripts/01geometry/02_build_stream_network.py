"""Build the final stream network from extracted source features.

- exact geometry duplicates are removed before clipping to city boundaries
- named lines are merged by city and name
- unnamed lines are merged only when their geometries intersect
- lines shorter than 100 m are excluded
"""

from pathlib import Path
import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.ops import linemerge


target_crs = "EPSG:25833"
input_path = Path("data/stream_geometry/streams_01_extract.gpkg")
boundary_path = Path("data/city_boundaries/combined_city_boundaries.gpkg")
output_path = Path("data/stream_geometry/streams_02_network.gpkg")
minimum_length = 100


def merge_geometries(geometries):
    parts = list(geometries)
    return parts[0] if len(parts) == 1 else linemerge(parts)


def unique_values(values):
    result = []
    for value in values:
        if pd.isna(value) or str(value).strip() == "":
            continue
        for token in str(value).split("|"):
            token = token.strip()
            if token and token not in result:
                result.append(token)
    return "|".join(result) if result else None


def summarize_attributes(row, group):
    row = row.copy()
    for column in ["source", "waterway", "original_waterway", "network_role"]:
        row[column] = unique_values(group[column])
    coverings = group["covering"].dropna().unique()
    row["covering"] = coverings[0] if len(coverings) == 1 else "mixed"
    row["pilot_stream"] = bool(group["pilot_stream"].fillna(False).any())
    return row


def merge_named(streams):
    named = streams[streams["name"].notna() & streams["name"].str.strip().ne("")]
    rows = []
    for _, group in named.groupby(["city", "name"], sort=False, dropna=False):
        row = summarize_attributes(group.iloc[0], group)
        row["geometry"] = merge_geometries(group.geometry)
        rows.append(row)
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=streams.crs)


def connected_components(streams):
    """group unnamed lines that intersect through a shared topology."""
    spatial_index = streams.sindex
    remaining = set(streams.index)
    components = []

    while remaining:
        seed = remaining.pop()
        component = {seed}
        queue = [seed]
        while queue:
            current = queue.pop()
            geometry = streams.at[current, "geometry"]
            neighbours = {
                int(index)
                for index in spatial_index.intersection(geometry.bounds)
                if int(index) in remaining
                and geometry.intersects(streams.at[int(index), "geometry"])
            }
            remaining.difference_update(neighbours)
            component.update(neighbours)
            queue.extend(neighbours)
        components.append(sorted(component))
    return components


def merge_unnamed(streams):
    if streams.empty:
        return gpd.GeoDataFrame(columns=streams.columns, geometry="geometry", crs=streams.crs)

    rows = []
    for indices in connected_components(streams):
        group = streams.loc[indices]
        row = summarize_attributes(group.iloc[0], group)
        row["geometry"] = merge_geometries(group.geometry)
        row["name"] = None
        rows.append(row)
    return gpd.GeoDataFrame(rows, geometry="geometry", crs=streams.crs)


def main():
    streams = gpd.read_file(input_path).to_crs(target_crs)
    boundaries = gpd.read_file(boundary_path).to_crs(target_crs)
    streams = streams.loc[~streams.geometry.to_wkb().duplicated()].reset_index(drop=True)
    streams = gpd.clip(streams, boundaries).explode(index_parts=False).reset_index(drop=True)

    named = merge_named(streams)
    unnamed = merge_unnamed(streams[streams["name"].isna()].reset_index(drop=True))
    network = gpd.GeoDataFrame(
        pd.concat([named, unnamed], ignore_index=True),
        geometry="geometry",
        crs=streams.crs,
    ).explode(index_parts=False).reset_index(drop=True)
    network["length"] = network.geometry.length
    network = network[network["length"] >= minimum_length].reset_index(drop=True)
    network["merged_id"] = np.arange(1, len(network) + 1, dtype=int)

    columns = [
        "name", "osm_id", "source", "waterway", "original_waterway",
        "network_role", "pilot_stream", "covering", "city", "dresden_id",
        "merged_id", "length", "geometry",
    ]
    network = network[columns]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    network.to_file(output_path, driver="GPKG")
    print(f"saved: {output_path} ({len(network)} features)")


if __name__ == "__main__":
    main()
