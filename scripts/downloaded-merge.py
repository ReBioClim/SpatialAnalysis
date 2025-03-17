import requests
import os

# data DTM or DGM in German
# data DSM or DOM in German
# data lod2 shape for building height
# data LiDAR or LSC in German
urls_raw = """
## pasted from https://www.geodaten.sachsen.de/digitale-hoehenmodelle-3994.html?_cp=%7B%22accordion-content-
4100%22%3A%7B%222%22%3Atrue%7D%2C%22previousOpen%22%3A%7B%22group%22%3A%22accordion-content-4100%22%2C%22idx%22%3A2%7D%7D
"""

urls = urls_raw.strip().splitlines()

download_dir = "downloaded_files"
os.makedirs(download_dir, exist_ok=True)

