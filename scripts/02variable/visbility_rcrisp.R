library(sf)
library(rcrisp)
library(visor)
library(dplyr)
library(purrr)


streams <- st_read("data/input/streamall_merged_final.gpkg", quiet = TRUE)
buildings <- st_read("data/25833/buildings_merged.gpkg", quiet = TRUE)

id_col <- "merged_id"

ray_length <- 1000
buffer_dist <- ray_length
density <- 0.05
ray_num <- 160


stream_len <- st_length(streams)
long_idx <- which(stream_len > quantile(stream_len, 0.8, na.rm = TRUE))
selected <- streams[long_idx[1:3], ]

riverspace <- delineate_riverspace(selected, buildings)

plot(riverspace, col = "orange", border = NA)
plot(selected, add = TRUE)
plot(buildings, add = TRUE)


process_one <- function(stream_i, id_value) {
  buf <- st_buffer(stream_i, buffer_dist)
  b_near <- buildings[buf, , op = st_intersects]

  vpts <- get_viewpoints(stream_i, density = density)
  vpts <- st_sf(id = seq_along(vpts), geometry = vpts)

  iso <- get_isovist(
    viewpoints = vpts,
    occluders = b_near,
    ray_num = ray_num,
    ray_length = ray_length,
    remove_holes = FALSE
  )

  iso$merged_id <- id_value
  iso
}


ids <- as.character(streams[[id_col]])

isovist_all <- map_dfr(seq_len(nrow(streams)), function(i) {
  process_one(streams[i, ], ids[i])
})

st_write(isovist_all, "output/all_streams_isovist.gpkg", quiet = TRUE)

