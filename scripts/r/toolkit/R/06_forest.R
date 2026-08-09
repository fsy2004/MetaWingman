## =====================================================================
## 06_forest.R  —  Publication forest plot & drapery (p-value function)
## ---------------------------------------------------------------------
## The forest plot is the centrepiece figure of any meta-analysis
## (PRISMA 2020 item 20a). ma_forest() draws the metafor publication
## forest with a random-effects summary polygon, the 95% prediction
## interval (Riley 2011), study weights, and a back-transformed axis for
## log measures (OR/RR/HR) and Fisher's z. ma_drapery() draws Ruecker &
## Schwarzer's (2020) p-value function ("drapery") plot, a resolution-free
## complement to the forest that shows significance across all null values.
##
## Depends: metafor, meta.  Sourced after 00-02 (needs the ma_fit object).
## =====================================================================

.forest_xlab <- function(measure) {
  if (is.null(measure)) return("Effect size")
  switch(toupper(measure),
    OR = "Odds ratio (log scale)", RR = "Risk ratio (log scale)",
    HR = "Hazard ratio (log scale)", IRR = "Incidence rate ratio (log scale)",
    ROM = "Ratio of means (log scale)",
    SMD = "Standardized mean difference (Hedges' g)", SMDH = "Standardized mean difference",
    MD = "Mean difference", ZCOR = "Correlation (r)", COR = "Correlation (r)",
    "Effect size")
}
.re_mlab <- function(re) {
  sprintf("RE model (I² = %.0f%%, τ² = %.3f, Q(%d) = %.1f, p %s)",
          re$I2, re$tau2, re$k - 1, re$QE,
          if (re$QEp < 0.001) "< 0.001" else sprintf("= %.3f", re$QEp))
}

## ma_forest(): publication-quality forest plot -> vector PDF.
##   fit         : an ma_fit (from ma_pairwise)
##   out         : output PDF path
##   showweights : print each study's weight
##   at, refline : passed to metafor::forest (auto on the correct scale)
ma_forest <- function(fit, out, showweights = TRUE, xlab = NULL,
                      at = NULL, refline = 0, cex = 0.9, ...) {
  stopifnot(inherits(fit, "ma_fit"))
  re <- fit$re
  islog  <- !is.null(fit$transf) && identical(fit$transf, exp)
  isz    <- !is.null(fit$measure) && toupper(fit$measure) == "ZCOR"
  atransf <- if (islog) exp else if (isz) metafor::transf.ztor else FALSE
  if (is.null(xlab)) xlab <- .forest_xlab(fit$measure)
  h <- max(5, 0.30 * re$k + 3)
  mw_pdf(out, width = 9, height = h)
  on.exit(grDevices::dev.off(), add = TRUE)
  metafor::forest(re, atransf = atransf, at = at, refline = refline,
                  showweights = showweights, addpred = TRUE, header = TRUE,
                  xlab = xlab, mlab = .re_mlab(re), cex = cex, ...)
  invisible(out)
}

## ma_drapery(): p-value / z-value function plot (Ruecker & Schwarzer 2020).
ma_drapery <- function(fit, out, type = c("pvalue", "zvalue"), ...) {
  stopifnot(inherits(fit, "ma_fit"))
  type <- match.arg(type)
  es <- fit$es
  slab <- attr(es, "slab"); if (is.null(slab)) slab <- paste0("Study ", seq_len(nrow(es)))
  sm <- toupper(fit$measure %||% "")
  m <- tryCatch(
    meta::metagen(TE = es$yi, seTE = sqrt(es$vi), studlab = slab, sm = sm,
                  common = FALSE, random = TRUE, method.tau = fit$re$method),
    error = function(e) meta::metagen(TE = es$yi, seTE = sqrt(es$vi), studlab = slab,
                                      common = FALSE, random = TRUE))
  mw_pdf(out, width = 8, height = 6)
  on.exit(grDevices::dev.off(), add = TRUE)
  meta::drapery(m, type = type, ...)
  invisible(out)
}
