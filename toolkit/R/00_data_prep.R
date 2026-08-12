## =====================================================================
## 00_data_prep.R  —  Data preparation helpers for meta-analysis
## ---------------------------------------------------------------------
## Convert commonly-reported summaries into the mean / SD / variance that
## effect-size formulas need, and inter-convert effect sizes. Every
## method is a published, citable estimator (no ad-hoc formulas):
##   * median + IQR / range  -> mean + SD : Wan 2014 (BMC Med Res Methodol
##     14:135); optionally the Cochrane-recommended QE/BC/MLN estimators
##     of McGrath 2020 (Stat Methods Med Res) via the 'estmeansd' package.
##   * SE / CI               -> SD        : Cochrane Handbook ch. 6.5.
##   * effect-size conversion             : Borenstein 2009 (Ch. 7),
##     Chinn 2000 (Stat Med 19:3127), Hedges & Olkin 1985.
##
## Depends: base R only for the core paths; estmeansd (optional) for
##          the QE/BC/MLN median-based estimators.
## =====================================================================

## ---- median (+ spread) -> mean & SD : Wan et al. 2014 -----------------
## Scenarios follow Wan 2014 Table/eqns exactly:
##   S1  {min, median, max, n}
##   S2  {q1,  median, q3,  n}
##   S3  {min, q1, median, q3, max, n}
## Returns c(mean = , sd = ).
dp_wan2014 <- function(median, n,
                       min = NA, q1 = NA, q3 = NA, max = NA) {
  stopifnot(is.finite(median), is.finite(n), n > 1)
  have <- function(x) length(x) == 1 && is.finite(x)
  Phi_inv <- qnorm
  if (have(q1) && have(q3) && have(min) && have(max)) {          # S3
    m  <- (min + 2*q1 + 2*median + 2*q3 + max) / 8
    sd <- (max - min) / (4 * Phi_inv((n - 0.375)/(n + 0.25))) +
          (q3  - q1 ) / (4 * Phi_inv((0.75*n - 0.125)/(n + 0.25)))
    scn <- "S3(min,q1,med,q3,max)"
  } else if (have(q1) && have(q3)) {                             # S2
    m  <- (q1 + median + q3) / 3
    sd <- (q3 - q1) / (2 * Phi_inv((0.75*n - 0.125)/(n + 0.25)))
    scn <- "S2(q1,med,q3)"
  } else if (have(min) && have(max)) {                          # S1
    m  <- (min + 2*median + max) / 4
    sd <- (max - min) / (2 * Phi_inv((n - 0.375)/(n + 0.25)))
    scn <- "S1(min,med,max)"
  } else stop("Provide {q1,q3}, {min,max}, or {min,q1,q3,max} together with median & n")
  list(mean = unname(m), sd = unname(sd), scenario = scn)
}

## ---- median -> mean & SD, choosing a published estimator --------------
## method = "wan"     : Wan 2014 (default; no dependency)
##          "qe"      : Quantile-Estimation (McGrath 2020) -- estmeansd
##          "bc"      : Box-Cox            (McGrath 2020) -- estmeansd
##          "mln"     : Median-of-Log-Normal (McGrath 2020) -- estmeansd
## The estmeansd methods are the Cochrane Handbook's current recommendation
## for skewed data; they gracefully fall back to Wan 2014 if the package
## is not installed (with a message, never a silent substitution).
dp_median_to_mean_sd <- function(median, n, min = NA, q1 = NA, q3 = NA, max = NA,
                                 method = c("wan", "qe", "bc", "mln")) {
  method <- match.arg(method)
  if (method == "wan") return(dp_wan2014(median, n, min, q1, q3, max))
  if (!requireNamespace("estmeansd", quietly = TRUE)) {
    message("estmeansd not installed; falling back to Wan 2014 for method='", method, "'")
    return(dp_wan2014(median, n, min, q1, q3, max))
  }
  fn <- switch(method, qe = estmeansd::qe.mean.sd,
                       bc = estmeansd::bc.mean.sd,
                       mln = estmeansd::mln.mean.sd)
  res <- fn(min.val = if (is.finite(min)) min else NA,
            q1.val  = if (is.finite(q1))  q1  else NA,
            med.val = median,
            q3.val  = if (is.finite(q3))  q3  else NA,
            max.val = if (is.finite(max)) max else NA,
            n = n)
  list(mean = unname(res$est.mean), sd = unname(res$est.sd), scenario = method)
}

## ---- SE / CI -> SD ----------------------------------------------------
dp_se_to_sd <- function(se, n) se * sqrt(n)
## CI of a MEAN -> SD.  dist = "t" (default, exact) or "z".
dp_ci_to_sd <- function(lower, upper, n, dist = c("t", "z"), conf = 0.95) {
  dist <- match.arg(dist)
  crit <- if (dist == "t") qt(1 - (1 - conf)/2, df = n - 1) else qnorm(1 - (1 - conf)/2)
  se <- (upper - lower) / (2 * crit)
  se * sqrt(n)
}
## IQR -> SD assuming approximate normality (Cochrane 6.5.2.3)
dp_iqr_to_sd <- function(q1, q3) (q3 - q1) / 1.35

## ---- effect-size inter-conversions (Borenstein 2009 unless noted) -----
## Cohen's d -> Hedges' g  (small-sample bias correction J).
dp_d_to_g <- function(d, df) d * (1 - 3 / (4 * df - 1))
## log odds ratio <-> standardized mean difference (Chinn 2000; logistic).
dp_lnOR_to_SMD <- function(lnOR) lnOR * (sqrt(3) / pi)           # ~ lnOR * 0.5513
dp_SMD_to_lnOR <- function(d)    d   * (pi / sqrt(3))
## correlation r <-> SMD d (Borenstein Eq 7.5 / 7.7); requires group sizes
## for the exact variance; point estimate below.
dp_r_to_SMD <- function(r) 2 * r / sqrt(1 - r^2)
dp_SMD_to_r <- function(d, n1, n2) {
  a <- (n1 + n2)^2 / (n1 * n2)
  d / sqrt(d^2 + a)
}
## Fisher's z <-> r
dp_r_to_z <- function(r) 0.5 * log((1 + r) / (1 - r))
dp_z_to_r <- function(z) (exp(2 * z) - 1) / (exp(2 * z) + 1)

## ---- quick self-check when sourced interactively ----------------------
if (identical(environment(), globalenv()) && !exists(".ma_sourced_quiet", inherits = FALSE)) {
  invisible(NULL)
}
