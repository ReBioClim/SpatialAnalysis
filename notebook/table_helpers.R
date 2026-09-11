# helper functions for rendering paper tables
as_paper_table <- function(table_data) {
  flextable::flextable(table_data) |>
    flextable::theme_booktabs() |>
    flextable::fontsize(size = 8, part = "all") |>
    flextable::padding(padding = 2, part = "all") |>
    flextable::align(align = "left", part = "all") |>
    flextable::bold(part = "header") |>
    flextable::set_table_properties(width = 1, layout = "autofit")
}

paper_table <- function(path) {
  as_paper_table(read.csv(path, check.names = FALSE))
}

paper_variable_summary <- function(path) {
  table_data <- read.csv(path, check.names = FALSE)

  for (col in c("Missing %", "Median", "Mean")) {
    if (col %in% names(table_data)) {
      table_data[[col]] <- sprintf("%.1f", round(as.numeric(table_data[[col]]), 1))
    }
  }

  as_paper_table(table_data)
}

paper_table_width <- function(path, widths) {
  paper_table(path) |>
    flextable::width(width = widths) |>
    flextable::set_table_properties(width = 1, layout = "fixed")
}
