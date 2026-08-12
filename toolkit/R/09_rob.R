## =====================================================================
## 09_rob.R  —  Risk-of-bias figures (wraps the robvis package)
## ---------------------------------------------------------------------
## Publication-standard Cochrane risk-of-bias visualisations. This is a
## thin wrapper over robvis: all plotting numerics belong to the package,
## we add tool-string mapping, validation, and vector-PDF export.
##
## Methods & primary references:
##   * robvis (risk-of-bias visualisation)        : McGuinness & Higgins
##     2021 (Res Synth Methods 12:55-61) — the traffic-light plot and the
##     weighted summary bar plot.
##   * RoB 2 (randomised trials)                  : Sterne et al. 2019
##     (BMJ 366:l4898).
##   * ROBINS-I (non-randomised interventions)    : Sterne et al. 2016
##     (BMJ 355:i4919).
##   * RoB 1 (original Cochrane tool)             : Higgins et al. 2011
##     (BMJ 343:d5928).
##   * QUADAS-2 (diagnostic accuracy studies)     : Whiting et al. 2011
##     (Ann Intern Med 155:529-536).
##
## Depends: robvis, ggplot2.  Self-contained (defines functions only).
## Figures -> figures/ (vector PDF).
## =====================================================================

## Map the user-facing tool argument to the exact strings robvis expects.
## robvis validates on these literal strings ("ROB2","ROBINS-I","ROB1",
## "QUADAS-2"); the mapping is 1:1 but explicit so a typo fails loudly here
## rather than producing an empty plot inside robvis.
.rob_tool <- function(tool = c("ROB2", "ROBINS-I", "ROB1", "QUADAS-2")) {
  tool <- match.arg(tool)
  switch(tool,
         "ROB2"     = "ROB2",
         "ROBINS-I" = "ROBINS-I",
         "ROB1"     = "ROB1",
         "QUADAS-2" = "QUADAS-2")
}

## rob_traffic(): per-study domain x study "traffic-light" dot matrix — the
## primary per-study risk-of-bias figure (one coloured dot per domain per
## study, plus an Overall column). Wraps robvis::rob_traffic_light().
##   data  : robvis-format data.frame (Study, domain judgements, Overall).
##   tool  : one of "ROB2","ROBINS-I","ROB1","QUADAS-2".
##   out   : "figures/<name>.pdf" (vector).
##   psize : dot size passed to robvis (default 10).
## Returns the ggplot object invisibly.
rob_traffic <- function(data,
                        tool = c("ROB2", "ROBINS-I", "ROB1", "QUADAS-2"),
                        out, psize = 10) {
  tool_str <- .rob_tool(tool)
  plot <- robvis::rob_traffic_light(data = data, tool = tool_str, psize = psize)
  ## Height scales with the number of studies; width with the domain count.
  n_study  <- nrow(data)
  n_domain <- ncol(data) - 1L                      # drop the Study column
  ggplot2::ggsave(out, plot,
                  width  = max(6, 1.1 * n_domain),
                  height = max(5, 0.45 * n_study + 2),
                  device = mw_pdf,
                  limitsize = FALSE)
  invisible(plot)
}

## rob_summary(): weighted stacked-bar summary of risk of bias across
## studies (percentage of studies at each judgement level, per domain).
## Wraps robvis::rob_summary(). NOTE: this weighted stacked-bar summary is
## the canonical Cochrane risk-of-bias figure — the one sanctioned
## exception to the toolkit's no-bar-chart rule.
##   data     : robvis-format data.frame (needs the weight column when weighted).
##   tool     : one of "ROB2","ROBINS-I","ROB1","QUADAS-2".
##   out      : "figures/<name>.pdf" (vector).
##   weighted : weight each study by its meta-analytic weight (default TRUE).
## Returns the ggplot object invisibly.
rob_summary <- function(data,
                        tool = c("ROB2", "ROBINS-I", "ROB1", "QUADAS-2"),
                        out, weighted = TRUE) {
  tool_str <- .rob_tool(tool)
  plot <- robvis::rob_summary(data = data, tool = tool_str, weighted = weighted)
  ggplot2::ggsave(out, plot, width = 8, height = 2.6, device = mw_pdf)
  invisible(plot)
}
