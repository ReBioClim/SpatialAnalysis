library(sf)
library(terra)
library(dplyr)
library(purrr)
library(rcrisp)
library(progressr)

streams_path <- "data/stream_geometry/streams_02_network.gpkg"
output_path <- "data/production/variables/valleys_full_10kmbuf.gpkg"
dem_paths <- c(
  Dresden = "data/DTM/buffered/DEM_30m_Dresden_10kmbuf_25833.tif",
  Jablonec = "data/DTM/buffered/DEM_30m_Jablonec_10kmbuf_25833.tif",
  Poznan = "data/DTM/buffered/DEM_30m_Poznan_10kmbuf_25833.tif",
  Senica = "data/DTM/buffered/DEM_30m_Senica_10kmbuf_25833.tif"
)

streams <- sf::st_read(streams_path, quiet = TRUE)
dems <- lapply(dem_paths, function(path) {
  dem <- terra::rast(path)
  dem
})

process_one_stream <- function(one_row, dem_full, id_col = "merged_id") {
  id <- one_row[[id_col]][[1]]
  g <- sf::st_geometry(one_row)

  valley_sfc <- delineate_valley(dem_full, g)

  sf::st_sf(
    merged_id = id,
    geometry = valley_sfc,
    crs = sf::st_crs(one_row)
  ) |>
    sf::st_make_valid() |>
    sf::st_cast("MULTIPOLYGON") |>
    dplyr::mutate(area_m2 = as.numeric(sf::st_area(geometry)))
}

handlers(global = TRUE)
valley_list <- with_progress({
  p <- progressor(steps = nrow(streams))
  purrr::map(seq_len(nrow(streams)), function(i) {
    p(message = sprintf("stream %d/%d", i, nrow(streams)))
    city <- as.character(streams$city[i])
    process_one_stream(streams[i, ], dem_full = dems[[city]])
  })
})

valleys <- dplyr::bind_rows(valley_list)

dir.create(dirname(output_path), recursive = TRUE, showWarnings = FALSE)
sf::st_write(
  valleys,
  output_path,
  layer = "valleys",
  delete_dsn = TRUE,
  quiet = TRUE
)
