# 20250930 valley width
# Attach required packages
library(rcrisp)
library(sf)

bucharest_osm <- get_osm_example_data()
bucharest_dem <- get_dem_example_data()

# Load data for valley delineation
dem <- bucharest_dem
river_centerline <- st_geometry(bucharest_osm$river_centerline)
river_surface <- st_geometry(bucharest_osm$river_surface)
river <- c(river_centerline, river_surface)

valley <- delineate_valley(dem, river)


plot(dem)
plot(river, add = TRUE, col = "lightblue")
plot(valley, add = TRUE, border = "pink")

########

library(terra)
library(sf)
library(rcrisp)
library(ggplot2)
library(tidyterra)


dem_dresden <- terra::rast("data/DTM/Dresden_DTM_1m.tif")
dem <- terra::rast("data/DTM/DEM_30m_combined.tif")
water <- sf::read_sf("data/valley/dresden_stream_single.gpkg" )
segments <- sf::read_sf("data/valley/dresden_stream_single100.gpkg" )
water1 <- sf::read_sf("data/valley/dresden_stream.gpkg" )
long <- sf::read_sf("data/stream_geometry/streamall_geometry.gpkg" )
long <- sf::st_geometry(long)

# only select 1 segment from segments
segments1 <- segments[1,]
segments2 <- segments[2,]
long1 <- long[188,]   # select first segment from long


# select another segment from segments


terra::crs(dem_dresden, proj=TRUE)
terra::crs(dem_dresden, proj=TRUE, describe=TRUE)$code
sf::st_crs(long)$epsg


terra::res(dem_dresden)



dem_30m <- terra::aggregate(dem_dresden, fact = 30, fun = mean, na.rm = TRUE)


terra::res(dem_5m)

long2 <- st_transform(long2, 25833)

long2_clean <- st_sf(
  seg_id = seq_len(nrow(long2)),
  geometry = st_geometry(long2),
  crs = st_crs(long2)
)

valley_30mdem <- delineate_valley(dem_30m, water)
valley_long2 <- delineate_valley(dem_30m, long2_clean)
valley_long1 <- delineate_valley(dem, long)

plot(sf::st_geometry(long2))

png("streamall_valley.png", width = 1000, height = 800, res = 300)

plot(valley_long1)
dev.off()

class(valley_long1)
str(valley_long1, max.level = 1)


plot(dem)
plot(streams, add = TRUE, col = "pink")
#plot(water1, add = TRUE, col = "lightblue")
plot(valley_long1, add = TRUE, col = "pink")
plot(long1, add = TRUE, border = "red")

#plot(segments1, add = TRUE, col = "red")
#plot(valley_100, add = TRUE, border = "red")
plot(valley_long2, add = TRUE, border = "orange")
plot(sf::st_geometry(long2), add = TRUE, col = "red")

dev.off()

#######
library(sf)
library(terra)
library(dplyr)
library(purrr)
library(rcrisp)
library(progressr)

dem <- terra::rast("data/input/DTM_30m.tif")
streams <- sf::st_read("data/input/streamall_merged_final.gpkg")


# check tif dem crs
terra::crs(dem, proj=TRUE)

process_one_stream <- function(one_row, dem_full, id_col = "merged_id",
                               crop_buffer_m = 6000) {
  id <- one_row[[id_col]][[1]]
  g  <- sf::st_geometry(one_row)

  g_buf <- sf::st_buffer(g, crop_buffer_m)
  dem_crop <- terra::crop(dem_full, terra::vect(g_buf))

  valley_sfc <- delineate_valley(dem_crop, g)

  sf::st_sf(
    namemerge_id = id,
    geometry     = valley_sfc,
    crs          = sf::st_crs(one_row)
  ) |>
    sf::st_make_valid() |>
    sf::st_cast("MULTIPOLYGON") |>
    mutate(area_m2 = as.numeric(sf::st_area(geometry)))
}

# batch
handlers(global = TRUE)   #
valley_list <- with_progress({
  p <- progressor(steps = nrow(streams))
  purrr::map(seq_len(nrow(streams)), function(i) {
    p(message = sprintf("stream %d/%d", i, nrow(streams)))
    process_one_stream(streams[i, ], dem_full = dem)
  })
})

# filter out NULL results and bind
valley_list <- valley_list[!vapply(valley_list, is.null, logical(1))]
valleys <- dplyr::bind_rows(valley_list)

# output
sf::st_write(valleys,
             "data/input/valleys.gpkg",
             layer = "valleys")
