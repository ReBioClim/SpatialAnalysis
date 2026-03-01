import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from shapely.geometry import mapping


segments = gpd.read_file("data/input/streamall_400m_segments_from_mouth.gpkg")
raster_paths = [
    "data/input/worldpop_deu_pd_2020_1km_UNadj.tif",
    "data/input/worldpop_pol_pd_2020_1km_UNadj.tif",
    "data/input/worldpop_cze_pd_2020_1km_UNadj.tif",
    "data/input/worldpop_svk_pd_2020_1km_UNadj.tif",
]

pop = []
for _, s in segments.iterrows():
    val = np.nan
    buf = s.geometry.buffer(400)
    for path in raster_paths:
        with rasterio.open(path) as src:
            arr, _ = mask(src, [mapping(buf)], crop=True)
            data = arr[0]
            data = data[np.isfinite(data)]
            data = data[data >= 0]
            if len(data) > 0:
                val = np.mean(data)
                break
    pop.append(val)

out = segments[["segment400_id", "geometry"]].copy()
out["pop_density_1km"] = pop
out.to_file("data/production/variables/v1_pop_density.gpkg", driver="GPKG")
