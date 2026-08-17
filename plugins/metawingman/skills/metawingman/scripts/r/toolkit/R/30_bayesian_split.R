## =====================================================================
## 30_bayesian_split.R — per-figure renderers for the Bayesian family,
## so Meta Wingman can surface the Bayesian RE forest (#50) and the
## posterior densities of mu/tau (#51) as INDEPENDENT menu leaves.
## ---------------------------------------------------------------------
## 22_bayesian_meta.R::bma_run() fits the bayesmeta model once and (when
## given out_prefix) bundles BOTH figures in one call. To expose each leaf
## on its own, we fit once with out_prefix=NULL and then render exactly one
## figure from the fitted `bayesmeta` object with the helpers below. Both
## use the real bayesmeta/forestplot plot methods (no re-fit, no fake API):
##   * bma_forest_fig()    : forestplot::forestplot(bm) — study-level
##                           shrinkage estimates + 95% prediction interval.
##   * bma_posterior_fig() : plot(bm, which=3/2) — marginal posterior
##                           density curves of the effect mu and the
##                           heterogeneity tau (density curves, not bars).
## Nature look: the posterior panel is base graphics, so nature_base() is
## applied after the device opens; the forestplot panel is grid graphics
## (Arial comes from the mw_pdf cairo device / options(mw.font)).
##
## Depends: bayesmeta (fit object), forestplot (registered forestplot method).
## =====================================================================

## Bayesian RE forest (#50): shrinkage estimates + pooled effect + 95% PI.
##   bm  : a fitted 'bayesmeta' object (from bma_run(..., out_prefix=NULL))
##   out : output .pdf path
bma_forest_fig <- function(bm, out) {
  stopifnot(inherits(bm, "bayesmeta"))
  # forestplot() is the generic from the 'forestplot' package; bayesmeta
  # registers forestplot.bayesmeta, which DRAWS the figure as a side effect
  # (via grid.newpage()) and returns the table+plot list invisibly. It must
  # therefore be called bare — NOT wrapped in print(): print()-ing the
  # returned list re-draws the $forestplot element, overlaying a second ghost
  # forest (a latent bug in the original bundled renderer). capture.output
  # swallows the table matrix so only the figure lands on the device.
  # Because forestplot() calls grid.newpage(), it advances past the device's
  # initial page, leaving a BLANK page 1 and the actual forest on page 2.
  mw_pdf(out, width = 8, height = 0.4 * bm$k + 3)
  invisible(utils::capture.output(forestplot::forestplot(bm)))
  grDevices::dev.off()
  # Drop the blank leading page so to_png()'s page-1 conversion shows the forest.
  np <- pdftools::pdf_info(out)$pages
  if (np > 1) {
    tmp <- tempfile(fileext = ".pdf")
    qpdf::pdf_subset(out, pages = np, output = tmp)  # keep only the content page
    file.copy(tmp, out, overwrite = TRUE); unlink(tmp)
  }
  invisible(out)
}

## Posterior densities (#51): marginal posterior of mu and of tau.
##   bm  : a fitted 'bayesmeta' object
##   out : output .pdf path
bma_posterior_fig <- function(bm, out) {
  stopifnot(inherits(bm, "bayesmeta"))
  mw_pdf(out, width = 9, height = 4.5)
  on.exit(grDevices::dev.off(), add = TRUE)
  if (exists("nature_base", mode = "function")) nature_base()  # Nature base-graphics look
  graphics::par(mfrow = c(1, 2))
  plot(bm, which = 3, main = "Posterior of effect (mu)")          # marginal mu density
  plot(bm, which = 4, main = "Posterior of heterogeneity (tau)")  # marginal tau density
  invisible(out)
}
