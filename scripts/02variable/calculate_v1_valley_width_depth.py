import math

import geopandas as gpd
import numpy as np
import rasterio
from shapely.geometry import GeometryCollection, LineString, MultiLineString, Point


target_crs = "EPSG:25833"
segments_path = "data/stream_segments/streams_03_segments_200m.gpkg"
valleys_path = "data/production/variables/valleys_full_10kmbuf.gpkg"
dtm_by_city = {
    "Dresden": "data/DTM/buffered/DEM_30m_Dresden_10kmbuf_25833.tif",
    "Jablonec": "data/DTM/buffered/DEM_30m_Jablonec_10kmbuf_25833.tif",
    "Poznan": "data/DTM/buffered/DEM_30m_Poznan_10kmbuf_25833.tif",
    "Senica": "data/DTM/buffered/DEM_30m_Senica_10kmbuf_25833.tif",
}
output_path = "data/production/variables/v1_valley_morphology.gpkg"
output_layer = "v1_valley_morphology"

# Build a long normal section around each 200m segment midpoint.
cross_half_length_m = 5000.0


def _unit_perpendicular(line: LineString):
    coords = list(line.coords)
    if len(coords) < 2:
        return None
    x0, y0 = coords[0]
    x1, y1 = coords[-1]
    dx = x1 - x0
    dy = y1 - y0
    norm = math.hypot(dx, dy)
    if norm == 0:
        return None
    # Rotate by 90 degrees to get the normal vector.
    return np.array([-dy / norm, dx / norm], dtype=float)


def _extract_lines(geom):
    if geom is None or geom.is_empty:
        return []
    if isinstance(geom, LineString):
        return [geom]
    if isinstance(geom, MultiLineString):
        return [g for g in geom.geoms if not g.is_empty and g.length > 0]
    if isinstance(geom, GeometryCollection):
        lines = []
        for g in geom.geoms:
            lines.extend(_extract_lines(g))
        return lines
    return []


def _select_nearest_cross_section(section: LineString, candidates, center_point: Point):
    if not candidates:
        return None

    center_s = float(section.project(center_point))
    endpoints_s = []
    for ln in candidates:
        c = list(ln.coords)
        if len(c) < 2:
            continue
        for x, y in (c[0], c[-1]):
            pt = Point(x, y)
            endpoints_s.append(float(section.project(pt)))

    if len(endpoints_s) < 2:
        return None

    # Deduplicate projected positions.
    endpoints_s = sorted(set(round(v, 6) for v in endpoints_s))
    left = [v for v in endpoints_s if v <= center_s]
    right = [v for v in endpoints_s if v >= center_s]
    if not left or not right:
        return None

    s0 = max(left)
    s1 = min(right)
    if s1 <= s0:
        return None
    p0 = section.interpolate(s0)
    p1 = section.interpolate(s1)
    return LineString([p0, p1])


def _sample_elevation(src, x, y):
    val = next(src.sample([(x, y)]))[0]
    if val is None:
        return np.nan
    try:
        f = float(val)
    except Exception:
        return np.nan
    if not np.isfinite(f):
        return np.nan
    nodata = src.nodata
    if nodata is not None and np.isfinite(nodata) and f == float(nodata):
        return np.nan
    return f


def main():
    segments = gpd.read_file(segments_path).to_crs(target_crs)
    valleys = gpd.read_file(valleys_path).to_crs(target_crs)

    valley_lookup = valleys.set_index("merged_id").geometry.to_dict()

    widths = []
    depths = []

    dem_handles = {city: rasterio.open(path) for city, path in dtm_by_city.items()}
    try:
        for _, row in segments.iterrows():
            seg_geom = row.geometry
            merged_id = row["merged_id"]
            valley_geom = valley_lookup.get(merged_id)

            if valley_geom is None or valley_geom.is_empty or seg_geom is None or seg_geom.is_empty:
                widths.append(np.nan)
                depths.append(np.nan)
                continue

            center = seg_geom.interpolate(0.5, normalized=True)
            perp = _unit_perpendicular(seg_geom)
            if perp is None:
                widths.append(np.nan)
                depths.append(np.nan)
                continue

            left = Point(center.x - perp[0] * cross_half_length_m, center.y - perp[1] * cross_half_length_m)
            right = Point(center.x + perp[0] * cross_half_length_m, center.y + perp[1] * cross_half_length_m)
            section = LineString([left, right])

            inter = section.intersection(valley_geom)
            inter_lines = _extract_lines(inter)
            width_line = _select_nearest_cross_section(section, inter_lines, center)

            if width_line is None:
                widths.append(np.nan)
                depths.append(np.nan)
                continue

            width = float(width_line.length)
            widths.append(width)

            dem = dem_handles.get(row.get("city"), None)
            if dem is None:
                depths.append(np.nan)
                continue

            # Depth from boundary elevation mean minus thalweg proxy (min of 5 samples).
            sample_pts = [width_line.interpolate(t, normalized=True) for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
            elev = [_sample_elevation(dem, p.x, p.y) for p in sample_pts]
            elev = np.array(elev, dtype=float)
            valid = elev[np.isfinite(elev)]
            if len(valid) < 2:
                depths.append(np.nan)
                continue

            edge = elev[[0, -1]]
            edge_valid = edge[np.isfinite(edge)]
            if len(edge_valid) == 0:
                depths.append(np.nan)
                continue

            valley_edge_mean = float(np.mean(edge_valid))
            thalweg = float(np.min(valid))
            depths.append(valley_edge_mean - thalweg)
    finally:
        for ds in dem_handles.values():
            ds.close()

    out = segments[["segment200_id", "merged_id", "geometry"]].copy()
    out["valley_width"] = widths
    out["valley_depth"] = depths
    out.to_file(output_path, layer=output_layer, driver="GPKG")


if __name__ == "__main__":
    main()
