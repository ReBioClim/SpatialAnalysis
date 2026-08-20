"""Extract stream geometry for the four ReBioClim pilot cities.
selection rules
- stream data source:
    - osm way and relation snapshots for senica, poznan, and jablonec
    - official municipal stream dataset for dresden
- keep every `waterway=stream` way as the core network
- keep a relation river component when it connects to a stream element
  in the same relation and the relation is either tagged waterway=stream
  (e.g. Prießnitz) or matches the project pilot stream (e.g. Teplica and
  Bílá Nisa)
- keep a same-name drain/ditch connector only when it joins two different
  core components (reconnecting streams split by drains or ditches)
"""

import json
import unicodedata
from pathlib import Path
import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

raw_dir = Path("data/raw/osm_waterways")
output_path = Path("data/stream_geometry/streams_01_extract.gpkg")
target_crs = "EPSG:25833"
linear_waterways = {"stream", "river", "drain", "ditch"}
cities = ["Senica", "Poznan", "Jablonec"]
pilot_streams = {
    "Senica": "Teplica", "Poznan": "Piaśnica",
    "Jablonec": "Bílá Nisa", "Dresden": "Geberbach",
}


def normalize_name(value):
    if pd.isna(value):
        return None
    decomposed = unicodedata.normalize("NFD", str(value).strip().casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def lines_connect(first, second):
    return first.boundary.intersects(second) or second.boundary.intersects(first)


def connected_components(features):
    remaining, components = set(features.index), []
    while remaining:
        seed = remaining.pop()
        component, queue = {seed}, [seed]
        while queue:
            current = queue.pop()
            geometry = features.at[current, "geometry"]
            neighbours = {
                index for index in remaining
                if lines_connect(features.at[index, "geometry"], geometry)
            }
            remaining.difference_update(neighbours)
            component.update(neighbours)
            queue.extend(neighbours)
        components.append(component)
    return components


def watercourse_names(normalized_way_name, relation_names):
    names = set(relation_names)
    if pd.notna(normalized_way_name) and normalized_way_name:
        names.add(normalized_way_name)
    return tuple(sorted(names))


def combine_features(*frames):
    frames = [frame for frame in frames if not frame.empty]
    return gpd.GeoDataFrame(
        pd.concat(frames, ignore_index=True), geometry="geometry", crs=frames[0].crs
    )


def select_connector_features(core, candidates):
    """add drain/ditch only when it touches at least two core components."""
    core_components, selected = connected_components(core), []
    for component in connected_components(candidates):
        component_features = candidates.loc[list(component)]
        connected_core = {
            core_index for core_index, core_component in enumerate(core_components)
            if any(
                lines_connect(candidate_geometry, core_geometry)
                for candidate_geometry in component_features.geometry
                for core_geometry in core.loc[list(core_component), "geometry"]
            )
        }
        if len(connected_core) >= 2:
            selected.extend(component)
    return selected


def select_relation_rivers(waterways, pilot_name=None):
    """keep relation river components connected to relation stream members."""
    relation_ids = sorted({
        relation_id
        for relations in waterways["stream_element_relations"]
        for relation_id, relation_name, relation_waterway in relations
        if relation_waterway == "stream" or relation_name == pilot_name
    })
    selected = []
    for relation_id in relation_ids:
        elements = waterways[waterways["stream_element_relations"].map(
            lambda relations: any(element_relation_id == relation_id
                                  for element_relation_id, _, _ in relations)
        )]
        streams, rivers = elements[elements.waterway == "stream"], elements[elements.waterway == "river"]
        for component in connected_components(rivers):
            river_geometries = rivers.loc[list(component)].geometry
            if any(lines_connect(river_geometry, stream_geometry)
                   for river_geometry in river_geometries
                   for stream_geometry in streams.geometry):
                selected.extend(component)
    return selected


def select_stream_network(waterways, pilot_stream=None):
    """apply the stream, relation-river, and connector rules."""
    waterways = waterways.copy()
    waterways["normalized_name"] = waterways["name"].map(normalize_name).astype("string")
    waterways["watercourse_names"] = [
        watercourse_names(name, relation_names)
        for name, relation_names in zip(
            waterways.normalized_name, waterways.relation_names
        )
    ]
    pilot_name = normalize_name(pilot_stream) if pilot_stream else None
    waterways["pilot_stream_match"] = waterways.watercourse_names.map(
        lambda names: pilot_name in names if pilot_name else False
    )

    streams = waterways[waterways.waterway == "stream"].copy()
    streams["original_waterway"] = "stream"
    streams["network_role"] = "stream"
    streams["pilot_stream"] = streams.pilot_stream_match

    relation_rivers = waterways.loc[sorted(set(select_relation_rivers(waterways, pilot_name)))].copy()
    relation_rivers["original_waterway"] = "river"
    relation_rivers["network_role"] = relation_rivers.stream_element_relations.map(
        lambda relations: "pilot_river" if any(
            relation_name == pilot_name for _, relation_name, _ in relations
        ) else "stream_relation_river"
    )
    relation_rivers["pilot_stream"] = relation_rivers.pilot_stream_match
    relation_rivers["waterway"] = "stream"
    core = combine_features(streams, relation_rivers)

    connector_indices = []
    for name in sorted({name for names in core.watercourse_names for name in names}):
        same_name_core = core[core.watercourse_names.map(lambda names: name in names)]
        candidates = waterways[
            waterways.waterway.isin({"drain", "ditch"})
            & waterways.watercourse_names.map(lambda names: name in names)
        ]
        connector_indices.extend(select_connector_features(same_name_core, candidates))
    connectors = waterways.loc[sorted(set(connector_indices))].copy()
    connectors["original_waterway"] = connectors.waterway
    connectors["network_role"] = "connector"
    connectors["pilot_stream"] = connectors.watercourse_names.map(
        lambda names: pilot_name in names if pilot_name else False
    )
    connectors["waterway"] = "stream"

    network = combine_features(core, connectors)
    return network.drop(columns=[
        "normalized_name", "watercourse_names", "relation_names",
        "stream_element_relations", "pilot_stream_match",
    ])


def read_overpass_waterways(raw_path, crs=target_crs, waterway_types=linear_waterways):
    """rebuild osm ways and relevant waterway relations from json."""
    with raw_path.open(encoding="utf-8") as source:
        elements = json.load(source)["elements"]
    nodes = {
        element["id"]: (element["lon"], element["lat"])
        for element in elements if element["type"] == "node"
    }
    way_waterways = {
        element["id"]: element.get("tags", {}).get("waterway")
        for element in elements if element["type"] == "way"
    }
    relation_names_by_way, stream_relations_by_way = {}, {}

    for element in elements:
        if element["type"] != "relation" or element.get("tags", {}).get("type") != "waterway":
            continue
        tags = element.get("tags", {})
        relation_name = tags.get("name")
        normalized_relation_name = normalize_name(relation_name)
        way_ids = [
            part["ref"] for part in element.get("members", [])
            if part.get("type") == "way" and part.get("role", "") in {"", "main_stream"}
        ]
        for way_id in way_ids:
            if normalized_relation_name:
                relation_names_by_way.setdefault(way_id, set()).add(normalized_relation_name)
        if any(way_waterways.get(way_id) == "stream" for way_id in way_ids):
            for way_id in way_ids:
                stream_relations_by_way.setdefault(way_id, set()).add(
                    (element["id"], normalized_relation_name, tags.get("waterway"))
                )
    rows = []
    for element in elements:
        if element["type"] != "way":
            continue
        tags = element.get("tags", {})
        waterway = tags.get("waterway")
        if waterway not in waterway_types:
            continue
        coordinates = [nodes[node] for node in element["nodes"]]
        rows.append({
            "osm_id": element["id"], "name": tags.get("name"),
            "waterway": waterway, "tunnel": tags.get("tunnel"),
            "relation_names": tuple(sorted(relation_names_by_way.get(element["id"], set()))),
            "stream_element_relations": tuple(sorted(stream_relations_by_way.get(element["id"], set()))),
            "geometry": LineString(coordinates),
        })
    return gpd.GeoDataFrame(rows, crs="EPSG:4326").to_crs(crs)


def read_city(city):
    candidates = sorted(raw_dir.glob(f"{city.lower()}_????-??-??.json"))
    if len(candidates) != 1:
        raise RuntimeError(
            f"Expected exactly one dated OSM waterway snapshot for {city}, "
            f"found {len(candidates)}: {candidates}"
        )
    raw_path = candidates[0]
    waterways = select_stream_network(read_overpass_waterways(raw_path), pilot_streams[city])
    waterways["city"] = city
    return waterways


def read_dresden():
    dresden = gpd.read_file("data/raw/dresden_official/stream.gpkg").rename(columns={"gewna": "name"})
    dresden["city"] = "Dresden"
    dresden["covering"] = dresden["rohr_erl"].map({
        "verrohrt": "piped",
        "oberirdisch, aber überdeckt (z.B. Brücke, Bewuchs)": "covered",
    }).fillna("open")
    dresden["dresden_id"] = range(1, len(dresden) + 1)
    dresden["waterway"] = dresden["original_waterway"] = "stream"
    dresden["network_role"] = "dresden_official"
    dresden["pilot_stream"] = dresden["name"].map(normalize_name).astype("string").str.contains(
        normalize_name(pilot_streams["Dresden"]), regex=False, na=False
    )
    dresden["osm_id"], dresden["source"] = None, "dresden_official"
    return dresden


def main():
    osm = gpd.GeoDataFrame(
        pd.concat([read_city(city) for city in cities], ignore_index=True),
        geometry="geometry", crs=target_crs,
    )
    osm["source"] = "osm"
    osm["covering"] = osm["tunnel"].map({"culvert": "piped", "yes": "covered"}).fillna("open")
    osm["dresden_id"] = None
    dresden = read_dresden()
    columns = [
        "name", "osm_id", "source", "waterway", "original_waterway",
        "network_role", "pilot_stream", "covering", "city", "dresden_id", "geometry",
    ]
    streams = gpd.GeoDataFrame(
        pd.concat([osm[columns], dresden[columns]], ignore_index=True),
        geometry="geometry", crs=target_crs,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    streams.to_file(output_path, driver="GPKG")
    print(f"saved: {output_path} ({len(streams)} features)")


if __name__ == "__main__":
    main()
