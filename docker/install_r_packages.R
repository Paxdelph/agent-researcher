#!/usr/bin/env Rscript

options(
  repos = c(CRAN = "https://packagemanager.posit.co/cran/__linux__/bookworm/latest"),
  HTTPUserAgent = sprintf(
    "R/%s R (%s)",
    getRversion(),
    paste(R.version$platform, R.version$arch, R.version$os)
  ),
  Ncpus = 2L
)

# Only hard deps — avoid Suggests (showtext, shiny extras, etc.)
deps <- c("Depends", "Imports", "LinkingTo")

install_needed <- function(pkgs) {
  for (pkg in pkgs) {
    if (requireNamespace(pkg, quietly = TRUE)) {
      message("OK present: ", pkg)
      next
    }
    message("Installing: ", pkg)
    install.packages(pkg, dependencies = deps)
    if (!requireNamespace(pkg, quietly = TRUE)) {
      message("Binary failed, retry source CRAN: ", pkg)
      install.packages(
        pkg,
        repos = "https://cloud.r-project.org",
        dependencies = deps
      )
    }
    if (!requireNamespace(pkg, quietly = TRUE)) {
      stop("Failed to install: ", pkg)
    }
  }
}

install_needed(c(
  "knitr",
  "rmarkdown",
  "htmlwidgets",
  "jsonlite",
  "ggplot2",
  "plotly",
  "readr",
  "dplyr",
  "tidyr",
  "purrr",
  "stringr",
  "lubridate",
  "scales",
  "tibble"
))

required <- c("plotly", "dplyr", "readr", "rmarkdown", "htmlwidgets", "knitr")
ok <- vapply(required, requireNamespace, logical(1), quietly = TRUE)
if (!all(ok)) {
  stop("Missing required packages: ", paste(required[!ok], collapse = ", "))
}

cat("R packages OK\n")
