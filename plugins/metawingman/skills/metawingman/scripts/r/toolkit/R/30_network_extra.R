## =====================================================================
## 30_network_extra.R  —  Extra network-meta (NMA) leaves for Meta Wingman
## ---------------------------------------------------------------------
## Companion to 20_network_meta.R. Adds the honest netmeta wrappers that
## the finer left-tree needs but 20_ did not expose: NMA forest vs a
## reference, (non-cumulative) rankogram, design-by-treatment net heat,
## comparison-adjusted funnel, additive component NMA, and a CINeMA-style
## contribution matrix. Every function is a thin wrapper around a real
## `netmeta` function — no re-implemented maths, no fabricated output.
##
## Methods & primary references:
##   * NMA forest plot vs reference (Rücker 2012; Balduzzi 2023)
##       netmeta::forest.netmeta
##   * Rankogram / ranking probabilities (Salanti 2011)
##       netmeta::rankogram, plot.rankogram
##   * Design-by-treatment interaction / net heat (König 2013; Krahn 2013)
##       netmeta::netheat, netmeta::decomp.design
##   * Comparison-adjusted funnel for small-study effects in NMA
##       (Chaimani & Salanti 2012)  netmeta::funnel.netmeta
##   * Additive component network meta-analysis (Rücker 2020, Welton 2009)
##       netmeta::netcomb
##   * Contribution matrix (basis of CINeMA's "contribution" domain;
##       Papakonstantinou 2018; Nikolakopoulou 2020)  netmeta::netcontrib
##
## All figures render through the shared Nature look: nature_pdf() opens
## the embedded-Arial cairo device AND applies nature_base(); the caller
## then converts PDF->PNG with to_png() in the adapter.
##
## Depends: netmeta (>= 3.x), meta. Uses `%||%` from the toolkit
## foundation with a local fallback if sourced alone.
## =====================================================================

if (!exists("%||%", mode = "function"))
  `%||%` <- function(a, b) if (is.null(a)) b else a

.nmax_ensure_dir <- function(out) {
  d <- dirname(out)
  if (nzchar(d) && !dir.exists(d)) dir.create(d, recursive = TRUE, showWarnings = FALSE)
  invisible(out)
}

## Open a Nature figure device if available, else plain mw_pdf. Returns TRUE
## if nature_base() was applied (so callers know cex is already Nature-sized).
.nmax_open <- function(out, size = "double", height_mm = 150) {
  .nmax_ensure_dir(out)
  if (exists("nature_pdf", mode = "function")) { nature_pdf(out, size = size, height_mm = height_mm); TRUE }
  else { mw_pdf(out, width = 8, height = height_mm / 25.4); FALSE }
}

## ---------------------------------------------------------------------
## nma_forest_ref(): NMA forest of every treatment vs one reference
## (netmeta::forest.netmeta). Random-effects estimates with 95% CI. -> PDF.
nma_forest_ref <- function(net, out, reference = NULL, pooled = "random", ...) {
  stopifnot(inherits(net, "netmeta"))
  refg <- if (is.null(reference) || !nzchar(reference)) net$reference.group else reference
  if (!nzchar(refg) || !(refg %in% net$trts)) refg <- net$trts[1]  # safe fallback
  .nmax_open(out, size = "double", height_mm = 130)
  on.exit(grDevices::dev.off(), add = TRUE)
  ## `forest`/`funnel` generics are exported by `meta`; netmeta only registers
  ## the S3 methods forest.netmeta / funnel.netmeta -> dispatch via meta::.
  meta::forest(net, reference.group = refg, pooled = pooled,
               drop.reference.group = TRUE, ...)
  invisible(out)
}

## ---------------------------------------------------------------------
## nma_rankogram_plot(): rankogram = probability each treatment holds each
## rank (Salanti 2011). Non-cumulative by default. -> PDF. Returns the
## rankogram object (its $ranking.matrix.random is a table).
nma_rankogram_plot <- function(net, out,
                               small.values = c("desirable", "undesirable"),
                               cumulative = FALSE, ...) {
  stopifnot(inherits(net, "netmeta"))
  small.values <- match.arg(small.values)
  rg <- netmeta::rankogram(net, small.values = small.values,
                           cumulative.rankprob = cumulative)
  .nmax_open(out, size = "double", height_mm = 130)
  on.exit(grDevices::dev.off(), add = TRUE)
  graphics::plot(rg, ...)
  invisible(rg)
}

## ---------------------------------------------------------------------
## nma_netheat(): design-by-treatment / net heat plot of inconsistency
## contributions (König 2013). netheat() needs >1 design with independent
## information; on a star-like network it errors -> caller should fall back.
## -> PDF. Returns TRUE on success, FALSE if netheat could not be drawn.
nma_netheat <- function(net, out, random = TRUE, ...) {
  stopifnot(inherits(net, "netmeta"))
  ok <- .nmax_open(out, size = "double", height_mm = 160); rm(ok)
  drawn <- tryCatch({ netmeta::netheat(net, random = random, ...); TRUE },
                    error = function(e) FALSE)
  grDevices::dev.off()
  drawn
}

## ---------------------------------------------------------------------
## nma_cadj_funnel(): comparison-adjusted funnel plot for small-study
## effects in NMA (Chaimani & Salanti 2012). `order` (a treatment ordering,
## e.g. by assumed strength) is REQUIRED by netmeta::funnel.netmeta; if not
## supplied we order by P-score (best -> worst). -> PDF.
nma_cadj_funnel <- function(net, out, order = NULL,
                            small.values = c("desirable", "undesirable"),
                            pooled = "random", ...) {
  stopifnot(inherits(net, "netmeta"))
  small.values <- match.arg(small.values)
  if (is.null(order)) {
    nr <- netmeta::netrank(net, small.values = small.values)
    order <- names(sort(nr$ranking.random, decreasing = TRUE))
  }
  .nmax_open(out, size = "double", height_mm = 140)
  on.exit(grDevices::dev.off(), add = TRUE)
  meta::funnel(net, order = order, pooled = pooled, ...)
  invisible(order)
}

## ---------------------------------------------------------------------
## nma_component(): additive component network meta-analysis
## (netmeta::netcomb). Decomposes combination treatments (labels joined by
## `sep`, default " + ") into additive component effects. Draws the
## component forest (-> PDF) and returns a data.frame of component effects
## (random-effects) for CSV export.
nma_component <- function(net, out = NULL, sep.comps = "+", ...) {
  stopifnot(inherits(net, "netmeta"))
  nc <- netmeta::netcomb(net, sep.comps = sep.comps, ...)
  if (!is.null(out)) {
    .nmax_open(out, size = "double", height_mm = 130)
    on.exit(grDevices::dev.off(), add = TRUE)
    meta::forest(nc)
  }
  tab <- data.frame(
    component = nc$comps,
    effect    = as.numeric(nc$Comp.random),
    se        = as.numeric(nc$seComp.random),
    lower     = as.numeric(nc$lower.Comp.random),
    upper     = as.numeric(nc$upper.Comp.random),
    pval      = as.numeric(nc$pval.Comp.random),
    row.names = NULL, stringsAsFactors = FALSE)
  attr(tab, "netcomb") <- nc
  tab
}

## ---------------------------------------------------------------------
## nma_contrib(): contribution matrix (netmeta::netcontrib) — how much each
## direct comparison contributes to each network estimate. This is the
## quantitative backbone of CINeMA's "contribution / indirectness" domain
## (a local approximation; full CINeMA also grades within-study bias,
## imprecision, heterogeneity and incoherence). Draws a contribution
## heatmap (-> PDF) and returns the random-effects contribution matrix as a
## tidy data.frame for CSV export.
nma_contrib <- function(net, out = NULL, pooled = c("random", "common"), ...) {
  stopifnot(inherits(net, "netmeta"))
  pooled <- match.arg(pooled)
  nc <- netmeta::netcontrib(net, ...)
  M  <- if (pooled == "random") nc$random else nc$common
  if (!is.null(out)) {
    .nmax_open(out, size = "double", height_mm = 160)
    on.exit(grDevices::dev.off(), add = TRUE)
    op <- graphics::par(no.readonly = TRUE); on.exit(graphics::par(op), add = TRUE)
    graphics::par(mar = c(6, 8, 3, 4))
    nr <- nrow(M); ncl <- ncol(M)
    cols <- grDevices::colorRampPalette(c("#FFFFFF", "#56B4E9", "#0072B2"))(100)
    graphics::image(x = seq_len(ncl), y = seq_len(nr), z = t(M[nr:1, , drop = FALSE]),
                    col = cols, axes = FALSE, xlab = "", ylab = "", zlim = c(0, max(M)))
    graphics::axis(1, at = seq_len(ncl), labels = colnames(M), las = 2, cex.axis = 0.6, tick = FALSE)
    graphics::axis(2, at = seq_len(nr), labels = rev(rownames(M)), las = 1, cex.axis = 0.6, tick = FALSE)
    graphics::mtext("Direct comparison (evidence source)", side = 1, line = 4.2, cex = 0.7)
    graphics::mtext("Network estimate", side = 2, line = 6.2, cex = 0.7)
    graphics::title("Contribution matrix (random effects)", cex.main = 0.9, font.main = 1)
  }
  tab <- data.frame(network.estimate = rownames(M), M, check.names = FALSE,
                    row.names = NULL, stringsAsFactors = FALSE)
  attr(tab, "netcontrib") <- nc
  tab
}
