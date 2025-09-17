

# Jablonec raw pointcloud data converting to 1m DTM Workflow: 
# Clip in PDAL -> Merge -> Extract classification Ground -> Generate DTM


import os
import subprocess
import tempfile
import json
import geopandas as gpd
import glob

def run_pdal(pipeline):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(pipeline, f, indent=2)
        pipeline_file = f.name
    result = subprocess.run(['pdal', 'pipeline', pipeline_file], capture_output=True, text=True)
    os.unlink(pipeline_file)
    return result.returncode == 0

def main():
    base_dir = "/Users/yehanwu/Github-projects/SpatialAnalysis/data/Jablonec/cuzk"
    gpkg_file = os.path.join(base_dir, "ALS_meta_20250915.gpkg")
    laz_dir = os.path.join(base_dir, "Jablonec_ALS")
    output_dir = os.path.join(base_dir, "clipped_output")
    os.makedirs(output_dir, exist_ok=True)
    
    # Process each year
    layers = {
        '2010': 'alpc_blocks_dem_Jablonec_2010minus2017minus2019',
        '2017': 'alpc_blocks_dem_Jablonec_2017minus2019',
        '2019': 'alpc_blocks_dem_jablonec_2019'
    }
    
    clipped_files = []
    
    for year, layer_name in layers.items():
        print(f"Processing {year}...")
        
        # Extract and reproject geometry
        gdf = gpd.read_file(gpkg_file, layer=layer_name).to_crs('EPSG:25833')
        geometry_wkt = gdf.geometry.iloc[0].wkt
        
        # Find and merge LAZ files
        year_files = glob.glob(os.path.join(laz_dir, f"{year}_*", "*.laz"))
        merged_file = os.path.join(output_dir, f"merged_{year}.laz")
        
        merge_pipeline = {"pipeline": []}
        for laz_file in year_files:
            merge_pipeline["pipeline"].append({"type": "readers.las", "filename": laz_file})
        merge_pipeline["pipeline"].append({"type": "filters.merge"})
        merge_pipeline["pipeline"].append({"type": "writers.las", "filename": merged_file})
        run_pdal(merge_pipeline)
        
        # Clip merged file
        output_file = os.path.join(output_dir, f"Jablonec_ALS_clipped_{year}.laz")
        clip_pipeline = {
            "pipeline": [
                {"type": "readers.las", "filename": merged_file},
                {"type": "filters.crop", "polygon": geometry_wkt},
                {"type": "writers.las", "filename": output_file}
            ]
        }
        run_pdal(clip_pipeline)
        clipped_files.append(output_file)
        os.remove(merged_file)
    
    # Merge all clipped files
    print("Merging all years...")
    merged_file = os.path.join(output_dir, "Jablonec_ALS_merged_complete.laz")
    merge_pipeline = {"pipeline": []}
    for input_file in clipped_files:
        merge_pipeline["pipeline"].append({"type": "readers.las", "filename": input_file})
    merge_pipeline["pipeline"].append({"type": "filters.merge"})
    merge_pipeline["pipeline"].append({"type": "writers.las", "filename": merged_file})
    run_pdal(merge_pipeline)
    
    # Extract ground points
    print("Extracting ground points...")
    ground_file = os.path.join(output_dir, "Jablonec_ALS_ground_only.laz")
    ground_pipeline = {
        "pipeline": [
            {"type": "readers.las", "filename": merged_file},
            {"type": "filters.range", "limits": "Classification[2:2]"},
            {"type": "writers.las", "filename": ground_file}
        ]
    }
    run_pdal(ground_pipeline)
    
    # Generate DTM
    print("Generating DTM...")
    dtm_file = os.path.join(output_dir, "Jablonec_DTM_1m.tif")
    dtm_pipeline = {
        "pipeline": [
            {"type": "readers.las", "filename": ground_file},
            {"type": "writers.gdal", 
             "filename": dtm_file, 
             "resolution": 1.0, 
             "radius": 2.5, 
             "output_type": "idw", 
             "nodata": -9999, 
             "window_size": 3, 
             "power": 2.0}
        ]
    }
    run_pdal(dtm_pipeline)
    
    print("Complete!")

if __name__ == "__main__":
    main()
