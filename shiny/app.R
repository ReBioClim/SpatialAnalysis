library(shiny)
library(sf)
library(leaflet)
library(DT)
library(bslib)
library(dplyr)
library(ggplot2)

score_levels <- c("very low","low","medium","high","very high"); score_lookup <- setNames(1:5, score_levels)
streams_raw <- c("BilaNisa","Geberbach","Piasnica","Teplica")
streams_lab <- c(BilaNisa="Bila Nisa",Geberbach="Geberbach",Piasnica="Piasnica",Teplica="Teplica")
quadrant_colors <- c("Actual conflict"="indianred3","Actual synergy"="steelblue3","Potential conflict"="tan3","Potential synergy"="darkseagreen4")
class_colors <- c("very low"="firebrick3",low="darkorange2",medium="gold2",high="yellowgreen","very high"="forestgreen")
stream_shapes <- c("Bila Nisa"=21,Geberbach=22,Piasnica=23,Teplica=24,Case=21)
quadrant_labels <- c("Actual synergy"="Recognized Asset","Potential synergy"="High Restoration Opportunity","Potential conflict"="Perception Gap","Actual conflict"="Information/ Restoration Gap")

variable_definitions <- read.csv("variable_definitions.csv", check.names=FALSE)
app_notes <- read.csv("app_notes.csv", check.names=FALSE)
example_cases <- read.csv("calculator_examples.csv", check.names=FALSE)
variable_labels <- setNames(variable_definitions$label, variable_definitions$variable)
example_text <- paste(c(paste(names(example_cases), collapse=","), apply(example_cases, 1, paste, collapse=",")), collapse="\n")

clean <- function(x) {x <- tolower(trimws(as.character(x))); x[x %in% c("","na","n.a.","nan")] <- NA; x}
score <- function(x) {y <- suppressWarnings(as.integer(x)); ifelse(!is.na(y) & y %in% 1:5, y, unname(score_lookup[clean(x)]))}
quad <- function(sc,ps) case_when(sc>3 & ps>=3~"Actual synergy", sc<=3 & ps>=3~"Potential synergy", sc>3 & ps<3~"Potential conflict", TRUE~"Actual conflict")
add_quadrant_fields <- function(x) mutate(x, class=quad(sc,ps), quadrant=unname(quadrant_labels[class]))

scores <- {
  raw <- read.csv("syncon_collaborate_table.csv", check.names=FALSE); names(raw) <- make.unique(names(raw)); names(raw)[1] <- "Measure_card"
  raw <- filter(raw, !is.na(`Short name`), `Short name`!="", `Short name`!="'--'")
  bind_rows(lapply(seq_len(nrow(raw)), \(i) bind_rows(lapply(streams_raw, \(s)
    tibble(measure=raw$Measure_card[i], abbr=raw$`Short name`[i], pilot_stream=streams_lab[[s]], sc=score(raw[[paste0(s,"_spatial")]][i]), ps=score(raw[[paste0(s,"_public")]][i])))))) |>
    filter(!is.na(sc), !is.na(ps)) |> add_quadrant_fields()
}
sections <- st_read("pilot_50msection_spatial_variables.gpkg", quiet=TRUE) |> st_transform(4326)
map_vars <- names(variable_labels)[names(variable_labels) %in% names(sections)]

read_cases <- function(txt) {
  x <- read.csv(text=txt, check.names=FALSE); names(x) <- gsub("_+","_",gsub("[^a-z0-9]+","_",tolower(names(x))))
  tibble(case=x[[grep("^case|site|city",names(x))[1]]], measure=x[[grep("measure|abbr|short_name",names(x))[1]]], sc=score(x[[grep("^sc|spatial",names(x))[1]]]), ps=score(x[[grep("^ps|public",names(x))[1]]])) |> filter(!is.na(sc), !is.na(ps)) |> add_quadrant_fields()
}

plot_quadrants <- function(x, lab="abbr") {
  if(!"pilot_stream" %in% names(x)) x$pilot_stream <- "Case"
  ggplot(x, aes(sc, ps)) +
    geom_vline(xintercept=3.5, linetype="22", color="gray50") + geom_hline(yintercept=2.5, linetype="22", color="gray50") +
    annotate("text", x=c(1.2,4,1.2,4), y=c(3.7,3.7,1.45,1.45), hjust=0, color="gray40", fontface="italic", size=3,
             label=c("High Restoration\nOpportunity","Recognized Asset","Information/ Restoration Gap","Perception Gap")) +
    geom_jitter(aes(fill=class, shape=pilot_stream), width=.07, height=.07, size=3.9, color="gray10", stroke=.25) +
    geom_point(aes(color=class), alpha=0, show.legend=TRUE) +
    geom_text(aes(label=.data[[lab]], color=class), vjust=-.9, size=3, check_overlap=TRUE, show.legend=FALSE) +
    scale_x_continuous("Spatial condition (SC)", breaks=1:5, limits=c(.5,5.5)) + scale_y_continuous("Public support (PS)", breaks=1:5, limits=c(.5,5.5)) +
    scale_fill_manual(values=quadrant_colors, guide="none") + scale_color_manual("Category", values=quadrant_colors) + scale_shape_manual("Water Body", values=stream_shapes) +
    guides(color=guide_legend(override.aes=list(shape=21, fill=unname(quadrant_colors), alpha=1, size=4.5)), shape=guide_legend(override.aes=list(fill="white", color="gray10"))) +
    theme_minimal(base_size=12) + theme(panel.grid.minor=element_blank(), legend.position="right", plot.background=element_rect(fill="white", color=NA))
}

ui <- page_navbar(title="SYNERGY & CONFLICT analysis", theme=bs_theme(version=5, bootswatch="flatly", primary="black"), header=includeCSS("app.css"),
  nav_panel("SynCon Calculator", layout_columns(col_widths=c(4,8),
    div(class="cardx",h4("Input cases"), radioButtons("mode",NULL,c("Paste table"="batch","Single case"="single"),inline=TRUE),
      conditionalPanel("input.mode=='batch'", textAreaInput("paste","Input table",example_text,rows=12), actionButton("replace","CALCULATE",class="btn-primary")),
      conditionalPanel("input.mode=='single'", textInput("one_case","Case","New case"), textInput("one_measure","Measure","New measure"), selectInput("one_sc","SC",setNames(1:5,paste(1:5,score_levels)),3), selectInput("one_ps","PS",setNames(1:5,paste(1:5,score_levels)),3), actionButton("add","ADD",class="btn-primary")),
      actionButton("reset","RESET",class="btn-outline-secondary")), div(class="cardx",plotOutput("custom_plot",height=430), DTOutput("custom_table")))),
  nav_panel("ReBioClim Example", layout_columns(col_widths=c(3,9), div(class="cardx",h4("D1.3.1 pilot quadrants"), selectInput("stream","Water body",c("All",sort(unique(scores$pilot_stream)))), selectInput("measure","Measure",c("All",sort(unique(scores$abbr)))), selectInput("qclass","Category",c("All",names(quadrant_colors)))), div(class="cardx",plotOutput("report_plot",height=610)))),
  nav_panel("Pilot Zoom-in Maps", layout_columns(col_widths=c(3,9), div(class="cardx",h4("Pilot zoom-in"), selectInput("map_stream","Water body",sort(unique(sections$stream_name))), selectInput("map_var","Variable",setNames(map_vars,variable_labels[map_vars])), radioButtons("basemap","Basemap",c("Light"="CartoDB.Positron","OpenStreetMap","Satellite"="Esri.WorldImagery"),inline=TRUE)), div(class="cardx",leafletOutput("map",height=650), DTOutput("map_table")))),
  nav_panel("Variables and Sources", layout_columns(col_widths=c(7,5), div(class="cardx",h4("Variables"),DTOutput("variable_definitions")), div(class="cardx",h4("Input schema"),DTOutput("app_notes")))))

server <- function(input, output, session) {
  base <- add_quadrant_fields(example_cases); cases <- reactiveVal(base)
  observeEvent(input$replace, cases(read_cases(input$paste))); observeEvent(input$reset, cases(base))
  observeEvent(input$add, cases(bind_rows(cases(), add_quadrant_fields(tibble(case=input$one_case, measure=input$one_measure, sc=as.integer(input$one_sc), ps=as.integer(input$one_ps))))))
  output$custom_plot <- renderPlot(plot_quadrants(cases(),"measure")); output$custom_table <- renderDT(datatable(cases(), rownames=FALSE, options=list(pageLength=8, scrollX=TRUE)))
  filt <- reactive(scores |> filter((input$stream=="All"|pilot_stream==input$stream), (input$measure=="All"|abbr==input$measure), (input$qclass=="All"|class==input$qclass)))
  output$report_plot <- renderPlot(plot_quadrants(filt(),"abbr"))
  map_data <- reactive(filter(sections, stream_name==input$map_stream))
  output$map <- renderLeaflet({g <- map_data(); v <- input$map_var; cc <- paste0(v,"_class"); vals <- if(cc %in% names(g)) g[[cc]] else g[[v]]; pal <- if(cc %in% names(g)) colorFactor(class_colors, levels=score_levels) else colorFactor("Set2", na.omit(unique(vals))); leaflet(g) |> addProviderTiles(providers[[input$basemap]]) |> addPolylines(color=~pal(vals), weight=7, opacity=.9, label=~paste(section_id, vals)) |> addLegend("bottomright", pal=pal, values=vals, title=variable_labels[[v]])})
  output$map_table <- renderDT({v <- input$map_var; st_drop_geometry(map_data()) |> select(stream_name, section_id, all_of(v), any_of(paste0(v,"_class"))) |> datatable(rownames=FALSE, options=list(pageLength=30, scrollX=TRUE))})
  output$variable_definitions <- renderDT(datatable(variable_definitions, rownames=FALSE, options=list(pageLength=11, scrollX=TRUE))); output$app_notes <- renderDT(datatable(app_notes, rownames=FALSE, options=list(dom="t")))
}
shinyApp(ui, server)
