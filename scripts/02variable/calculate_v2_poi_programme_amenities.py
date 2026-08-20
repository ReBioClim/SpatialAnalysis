import re
import geopandas as gpd
import pandas as pd


segments_path = "data/stream_segments/streams_03_segments_400m.gpkg"
poi_points_path = "data/prepared/poi_points_merged.gpkg"
poi_polygons_path = "data/prepared/poi_polygons_merged.gpkg"
output_path = "data/production/variables/v2_access_poi_programme_amenities.gpkg"

cities = ["Dresden", "Poznan", "Jablonec", "Senica"]

poi_buffer_m = 50

programme_tags = {
    "school",
    "university",
    "college",
    "kindergarten",
    "childcare",
    "library",
    "theatre",
    "cinema",
    "arts_centre",
    "community_centre",
    "townhall",
    "public_building",
    "sports_centre",
    "sports_hall",
    "stadium",
    "pitch",
    "restaurant",
    "cafe",
    "fast_food",
    "bar",
    "food_court",
    "marketplace",
}

amenity_tags = {
    "bench",
    "picnic_table",
    "shelter",
    "drinking_water",
    "toilets",
    "viewpoint",
    "information_board",
    "bicycle_parking",
}

tag_columns = [
    "amenity",
    "leisure",
    "tourism",
    "shop",
    "office",
    "building",
    "landuse",
    "fclass",
    "class",
    "category",
    "type",
]


def tag_values(row):
    values = set()
    for col in tag_columns:
        if col in row.index and pd.notna(row[col]):
            values.update(
                token.strip().lower()
                for token in re.split(r"[;,|]", str(row[col]))
                if token.strip()
            )
    return values


segments = gpd.read_file(segments_path).to_crs("EPSG:25833")
poi_points = gpd.read_file(poi_points_path).to_crs("EPSG:25833")
poi_polygons = gpd.read_file(poi_polygons_path).to_crs("EPSG:25833")

poi_polygons = poi_polygons.copy()
if len(poi_polygons):
    poi_polygons["geometry"] = poi_polygons.geometry.centroid

poi_all = gpd.GeoDataFrame(pd.concat([poi_points, poi_polygons], ignore_index=True), crs=poi_points.crs)
poi_all = poi_all.copy()
poi_all["tag_values"] = [tag_values(row) for _, row in poi_all.iterrows()]
poi_all["amenity_match"] = poi_all["tag_values"].apply(
    lambda values: next((tag for tag in sorted(amenity_tags) if tag in values), None)
)
poi_all["programme_match"] = poi_all["tag_values"].apply(
    lambda values: next((tag for tag in sorted(programme_tags) if tag in values), None)
)

results = []

for city in cities:
    print("city:", city)

    s = segments[segments["city"] == city].copy()
    p = poi_all[poi_all["city"] == city].copy()

    s["poi_amenities"] = 0.0
    s["programme_count"] = 0.0

    if len(s) == 0 or len(p) == 0:
        results.append(s)
        continue

    segment_buffers = gpd.GeoDataFrame(
        s[["segment400_id"]].copy(),
        geometry=s.geometry.buffer(poi_buffer_m),
        crs=s.crs,
    )

    joined = gpd.sjoin(
        p[["amenity_match", "programme_match", "geometry"]],
        segment_buffers,
        predicate="within",
        how="inner",
    )

    amenity_joined = joined[joined["amenity_match"].notna()]
    programme_joined = joined[joined["programme_match"].notna()]

    amenity_counts = amenity_joined.groupby("segment400_id").size()
    programme_counts = programme_joined.groupby("segment400_id").size()
    s["poi_amenities"] = s["segment400_id"].map(amenity_counts).fillna(0).astype(float)
    s["programme_count"] = s["segment400_id"].map(programme_counts).fillna(0).astype(float)

    results.append(s)


all_data = pd.concat(results, ignore_index=True)

cols = [
    "segment400_id",
    "merged_id",
    "city",
    "poi_amenities",
    "programme_count",
    "geometry",
]
out = gpd.GeoDataFrame(all_data[cols], geometry="geometry", crs=all_data.crs)
out.to_file(output_path, driver="GPKG")
