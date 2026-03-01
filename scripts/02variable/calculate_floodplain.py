import geopandas as gpd
import rasterio
import numpy as np
from rasterio.mask import mask
from shapely.geometry import mapping


segments = gpd.read_file("data/input/streamall_100m_segments_from_mouth.gpkg")


# floodplain 250m buffer
buffer_250 = segments.copy()
buffer_250["geometry"] = buffer_250.geometry.buffer(250)


with rasterio.open("data/input/floodplain_RP100_binary.tif") as src:

    pixel_area = abs(src.transform.a * src.transform.e)

    def calc(row):
        out, _ = mask(src, [mapping(row.geometry)], crop=True)
        data = out[0].astype(np.float32)

        if src.nodata is not None:
            data = data[data != src.nodata]

        flood_pixels = np.count_nonzero(data > 0)
        total_pixels = data.size

        flood_area = flood_pixels * pixel_area
        ratio = flood_area / row.geometry.area

        return flood_area, ratio


    vals = buffer_250.apply(calc, axis=1, result_type="expand")
    vals.columns = ["floodplain_area_250m", "floodplain_ratio_250m"]


segments = segments.join(vals)


segments.to_file("data/production/variables/v2_floodplain.gpkg", driver="GPKG")