import requests
import os

# data DTM or DGM in German
# data DSM or DOM in German
# data lod2 shape for building height
urls_raw = """
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33400_5654_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33400_5656_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33400_5658_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33400_5660_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33402_5654_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33402_5656_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33402_5658_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33402_5660_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33402_5662_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33404_5652_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33404_5654_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33404_5656_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33404_5658_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33404_5660_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33404_5662_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33406_5650_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33406_5652_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33406_5654_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33406_5656_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33406_5658_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33406_5660_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33408_5650_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33408_5652_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33408_5654_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33408_5656_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33408_5658_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33408_5660_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33408_5662_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33408_5664_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33410_5650_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33410_5652_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33410_5654_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33410_5656_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33410_5658_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33410_5660_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33410_5662_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33410_5664_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33410_5666_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33412_5648_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33412_5650_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33412_5652_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33412_5654_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33412_5656_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33412_5658_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33412_5660_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33412_5662_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33412_5664_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33412_5666_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33412_5668_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33412_5670_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33414_5646_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33414_5648_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33414_5650_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33414_5652_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33414_5654_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33414_5656_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33414_5658_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33414_5660_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33414_5662_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33414_5664_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33414_5666_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33414_5668_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33414_5670_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33416_5646_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33416_5648_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33416_5650_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33416_5652_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33416_5654_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33416_5656_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33416_5658_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33416_5660_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33416_5662_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33416_5664_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33416_5666_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33416_5668_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33418_5646_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33418_5648_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33418_5650_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33418_5652_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33418_5654_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33418_5656_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33418_5658_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33418_5660_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33418_5662_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33418_5664_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33418_5666_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33418_5668_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33420_5648_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33420_5650_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33420_5652_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33420_5654_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33420_5656_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33420_5658_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33420_5660_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33420_5662_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33420_5664_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33420_5666_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33420_5668_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33422_5648_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33422_5650_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33422_5652_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33422_5654_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33422_5656_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33422_5658_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33422_5660_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33422_5662_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33422_5664_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33422_5666_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33424_5650_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33424_5652_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33424_5654_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33424_5656_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33424_5658_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33426_5652_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33426_5654_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33426_5656_2_sn_laz.zip
https://geocloud.landesvermessung.sachsen.de/index.php/s/rqcqdt8QMcLFUvC/download?path=%2F&files=lsc_33426_5658_2_sn_laz.zip

"""


urls = urls_raw.strip().splitlines()

download_dir = "downloaded_files"
os.makedirs(download_dir, exist_ok=True)

for url in urls:
    filename = url.split("files=")[-1]  # Extract filename from URL
    filepath = os.path.join(download_dir, filename)
    
    print(f"Downloading {filename}...")
    
    
    response = requests.get(url)
    if response.status_code == 200:
        with open(filepath, 'wb') as file:
            file.write(response.content)
        print(f"Saved {filename}")
    else:
        print(f"Failed to download {filename} (status code {response.status_code})")



##########unzip
import os
import zipfile
import glob
import rasterio
from rasterio.merge import merge

# Directories
zip_dir = "downloaded_files"
unzip_dir = "unzipped_files"
merged_dir = "merged_files"

os.makedirs(unzip_dir, exist_ok=True)
os.makedirs(merged_dir, exist_ok=True)

# Unzip all files
for zip_path in glob.glob(os.path.join(zip_dir, "*.zip")):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(unzip_dir)
        print(f"Extracted {zip_path}")

############ for tiff files
# Merge all TIFF files into one
tiff_files = glob.glob(os.path.join(unzip_dir, "*.tif"))

# Open all TIFF files
src_files_to_mosaic = []
for tiff in tiff_files:
    src = rasterio.open(tiff)
    src_files_to_mosaic.append(src)

# Merge TIFF files
mosaic, out_trans = merge(src_files_to_mosaic)

# Get metadata from one of the TIFF files
out_meta = src_files_to_mosaic[0].meta.copy()
out_meta.update({
    "driver": "GTiff",
    "height": mosaic.shape[1],
    "width": mosaic.shape[2],
    "transform": out_trans,
})

# Save merged TIFF
merged_tiff_path = os.path.join(merged_dir, "merged.tif")
with rasterio.open(merged_tiff_path, "w", **out_meta) as dest:
    dest.write(mosaic)

print(f"Merged TIFF saved at {merged_tiff_path}")

# Close all raster files
for src in src_files_to_mosaic:
    src.close()

########## for shp files
import geopandas as gpd
import pandas as pd  
import glob
import os
import zipfile

# Directories
zip_dir = "downloaded_files"
unzip_dir = "unzipped_files"
merged_dir = "merged_files"

os.makedirs(unzip_dir, exist_ok=True)
os.makedirs(merged_dir, exist_ok=True)

# Unzip all files 
for zip_path in glob.glob(os.path.join(zip_dir, "*.zip")):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(unzip_dir)
        print(f"Extracted {zip_path}")

import geopandas as gpd
import glob
import os

# Define the directory containing unzipped shapefiles
unzip_dir = "unzipped_files"

# Find all shapefiles
shapefile_list = glob.glob(os.path.join(unzip_dir, "*.shp"))

import geopandas as gpd

import geopandas as gpd
import glob
import os

# Define the directory containing unzipped shapefiles
unzip_dir = "unzipped_files"

# Find all shapefiles
shapefile_list = glob.glob(os.path.join(unzip_dir, "*.shp"))

# Initialize an empty list for storing valid GeoDataFrames
gdfs = []

for shp in shapefile_list:
    try:
        print(f"Trying to load: {shp}")
        gdf = gpd.read_file(shp)
        print(f"Loaded {shp} with {len(gdf)} features")
        gdfs.append(gdf)
    except Exception as e:
        print(f"Error loading {shp}: {e}")


import geopandas as gpd

for shp in shapefile_list:
    try:
        print(f"Trying to load: {shp}")
        gdf = gpd.read_file(shp, engine="fiona")  # !!!!use Fiona instead of Pyogrio
        print(f"Loaded {shp} with {len(gdf)} features")
        gdfs.append(gdf)
    except Exception as e:
        print(f"Error loading {shp}: {e}")


from shapely.geometry import MultiPolygon, Polygon
import fiona
# for building height data, the .shp include single polygon to multipolygon, when processing them needs to convert to the same file
# Function to convert all geometries to MultiPolygon
def convert_to_multipolygon(geom):
    if isinstance(geom, Polygon):
        return MultiPolygon([geom])  # Convert single Polygon to MultiPolygon
    return geom  # Keep MultiPolygon as is

merged_gdf["geometry"] = merged_gdf["geometry"].apply(
    lambda geom: geom if isinstance(geom, Polygon) else list(geom.geoms)[0] if isinstance(geom, MultiPolygon) else geom
)

print(merged_gdf.is_valid.value_counts())  # Check for invalid geometries
merged_gdf["geometry"] = merged_gdf["geometry"].buffer(0)

if merged_gdf.crs is None:
    merged_gdf.set_crs("EPSG:4326", inplace=True)  

merged_gdf = merged_gdf.to_crs("EPSG:4326")

print(merged_gdf.crs)

#### for laz files
import os
import glob
import zipfile
import laspy
import numpy as np
import sys



# List of .laz files
laz_files = glob.glob(os.path.join(unzip_dir, "*.laz"))
laz_files
if not laz_files:
    print("No .laz files found!")
    sys.exit(1)

# Read the first file as reference
first_las = laspy.read(laz_files[0])

# Open output file for writing
merged_file_path = os.path.join(merged_dir, "merged_output.laz")
with laspy.open(merged_file_path, mode="w", header=first_las.header) as merged_las:
    for laz_file in laz_files:
        las = laspy.read(laz_file)
        merged_las.write_points(las.points)  # Write incrementally to avoid memory overload
        print(f" Merged {laz_file}")

print(f"Merging completed")

########20250422
##########unzip
import os
import zipfile
import glob
import rasterio
from rasterio.merge import merge

# setting the working directory
os.chdir("/Users/yehanwu/Github-projects/SpatialAnalysis/data/Jablonec")
# set the directory where the zip files are located
zip_dir = "DMR"
# count the number of files in the DRM
zip_count = len([name for name in os.listdir(zip_dir) if os.path.isfile(os.path.join(zip_dir, name))])
print(f"Number of files in {zip_dir}: {zip_count}")

# create folders for unzipped and merged files
unzip_dir = "unzipped_files"
merged_dir = "merged_files"
os.makedirs(unzip_dir, exist_ok=True)
os.makedirs(merged_dir, exist_ok=True)

# list the files in the zip_dir
print("Files in zip_dir:")
for file in os.listdir(zip_dir):
    print(file)


# Unzip all files
for zip_path in glob.glob(os.path.join(zip_dir, "*.zip")):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(unzip_dir)
        print(f"Extracted {zip_path}")



#### for laz files
import os
import glob
import zipfile
import laspy
import numpy as np
import sys

unzip_dir

# List of .laz files
laz_files = glob.glob(os.path.join(unzip_dir, "*.laz"))
laz_files
if not laz_files:
    print("No .laz files found!")
    sys.exit(1)

# Read the first file as reference
first_las = laspy.read(laz_files[0])

# Open output file for writing
merged_file_path = os.path.join(merged_dir, "merged_output.laz")
with laspy.open(merged_file_path, mode="w", header=first_las.header) as merged_las:
    for laz_file in laz_files:
        las = laspy.read(laz_file)
        merged_las.write_points(las.points)  # Write incrementally to avoid memory overload
        print(f" Merged {laz_file}")

print(f"Merging completed")


##################
# https://paulojraposo.github.io/pages/PDAL_tutorial.html
# conda create -n pdal_env python=3.11
# conda activate pdal_env
# python interpreter: pdal_env 
import pdal
import json
import os


# Input and output paths
input_laz = "/Users/yehanwu/Github-projects/SpatialAnalysis/data/Jablonec/merged_files/merged_output.laz"
output_tif = "/Users/yehanwu/Github-projects/SpatialAnalysis/data/Jablonec/merged_files/merged_output.tif"


print("Exists:", os.path.exists("/Users/yehanwu/Github-projects/SpatialAnalysis/data/Jablonec/merged_files/merged_output.laz"))
print("Writable:", os.access("/Users/yehanwu/Github-projects/SpatialAnalysis/data/Jablonec/merged_files/", os.W_OK))


pipeline_json = {
    "pipeline": [
        "/Users/yehanwu/Github-projects/SpatialAnalysis/data/Jablonec/merged_files/merged_output.laz"
    ]
}

pipeline = pdal.Pipeline(json.dumps(pipeline_json))

try:
    count = pipeline.execute()
    print("Point cloud loaded successfully.")
    print(f"Number of points: {count}")
except RuntimeError as e:
    print("Error reading LAZ file:", e)

import pdal
import json

pipeline_json = {
    "pipeline": [
        "/Users/yehanwu/Github-projects/SpatialAnalysis/data/Jablonec/merged_files/merged_output.laz",
        {
            "type": "filters.range",
            "limits": "Classification[2:2]"
        },
        {
            "type": "writers.las",
            "filename": "/Users/yehanwu/Github-projects/SpatialAnalysis/data/Jablonec/merged_files/ground_only.las"
        }
    ]
}

pipeline = pdal.Pipeline(json.dumps(pipeline_json))
try:
    count = pipeline.execute()
    print("Ground points extracted.")
    print(f"Ground point count: {count}")
except RuntimeError as e:
    print("Error:", e)


# convert shp to json
import geopandas as gpd

# Load the shapefile
gpkg_path = "/Users/yehanwu/Github-projects/SpatialAnalysis/data/Jablonec.gpkg"
gdf = gpd.read_file(gpkg_path)

# Save as GeoJSON
geojson_path = "/Users/yehanwu/Github-projects/SpatialAnalysis/data/Jablonec.json"
gdf.to_file(geojson_path, driver="GeoJSON")


# Load the shapefile
gpkg_path = "/Users/yehanwu/Github-projects/SpatialAnalysis/data/Jablonec.gpkg"
gdf = gpd.read_file(gpkg_path)

# Save as GeoJSON
geojson_path = "/Users/yehanwu/Github-projects/SpatialAnalysis/data/Jablonec.json"
gdf.to_file(geojson_path, driver="GeoJSON")



##############
