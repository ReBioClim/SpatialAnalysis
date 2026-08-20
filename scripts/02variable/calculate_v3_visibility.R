library(sf)
library(visor)

streams_path <- "data/stream_geometry/streams_02_network.gpkg"
buildings_path <- "data/prepared/buildings_merged.gpkg"
output_path <- "data/production/variables/all_streams_isovist.gpkg"

streams <- st_read(streams_path, quiet = TRUE)
buildings <- st_read(buildings_path, quiet = TRUE)

ray_length <- 300
buffer_dist <- 300
density <- 0.05
ray_num <- 40

process_one <- function(i) {
  stream_i <- streams[i, ]
  buffer <- st_buffer(stream_i, buffer_dist)
  buildings_near <- buildings[buffer, , op = st_intersects]
  geometry <- if (nrow(buildings_near) == 0) {
    st_geometry(buffer)
  } else {
    viewpoints <- get_viewpoints(stream_i, density = density)
    isovist <- get_isovist(
      viewpoints,
      buildings_near,
      ray_num = ray_num,
      ray_length = ray_length,
      remove_holes = FALSE
    )
    st_intersection(st_union(isovist), st_geometry(buffer))
  }
  st_sf(merged_id = stream_i$merged_id, geometry = geometry)
}

n <- nrow(streams)
step <- max(1, ceiling(n / 100))
visibility_list <- lapply(seq_len(n), function(i) {
  if (i == 1 || i %% step == 0 || i == n) {
    message(sprintf("Visibility: %d/%d (%.0f%%)", i, n, 100 * i / n))
  }
  process_one(i)
})
visibility <- do.call(rbind, visibility_list)

dir.create(dirname(output_path), recursive = TRUE, showWarnings = FALSE)
st_write(
  visibility,
  output_path,
  layer = "visibility",
  delete_dsn = TRUE,
  quiet = TRUE
)
