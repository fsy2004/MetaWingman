## =====================================================================
## 02_pairwise_meta.R  —  Core pairwise pooling (random & common effect)
## ---------------------------------------------------------------------
## The workhorse. Fits a random-effects model with the defaults expected
## by top journals / Cochrane:
##   * REML tau^2 estimator (Viechtbauer 2005; Langan 2019 recommend REML)
##   * Knapp-Hartung (HKSJ) adjustment for the CI of the pooled effect
##     (Knapp & Hartung 2003; IntHout 2014) -> honest coverage with few k
##   * a 95% prediction interval (Higgins 2009; Riley 2011 BMJ) so the
##     reader sees the dispersion of true effects, not just the mean
## and reports I^2, tau^2, H^2, and Cochran's Q alongside a common-effect
## fit for comparison. Log-scale measures (OR/RR/IRR/ROM), Fisher's z and
## logit proportions are back-transformed for display.
##
## Depends: metafor.  Uses es_calc() from 01_effect_sizes.R when given raw data.
## =====================================================================

## Back-transform for a given measure (NULL = identity / already natural).
.ma_transf <- function(measure) {
  if (is.null(measure)) return(NULL)
  switch(toupper(measure),
    OR = exp, RR = exp, IRR = exp, PETO = exp, ROM = exp, HR = exp, IRLN = exp,
    ZCOR = metafor::transf.ztor,
    PLO  = metafor::transf.ilogit,
    NULL)
}
## Does this measure live on a log/other scale where "no effect" != 0?
.ma_refline <- function(measure) {
  if (is.null(measure)) return(0)
  if (toupper(measure) %in% c("OR","RR","IRR","PETO","ROM","HR","IRLN")) return(0) # log scale, ref line at log(1)=0
  0
}

## ma_pairwise(): fit RE (+ common-effect) with top-journal defaults.
## Provide EITHER an escalc object / a data.frame carrying yi & vi,
## OR raw data plus `measure` and the escalc column args via `...`.
ma_pairwise <- function(data, measure = NULL, slab = NULL,
                        method = "REML", knha = TRUE, level = 95, ...) {
  slab_expr <- substitute(slab)
  slab_v <- if (is.null(slab_expr)) NULL else eval(slab_expr, data, parent.frame())
  if (!is.null(measure) && !all(c("yi","vi") %in% names(data))) {
    es <- es_calc(measure, data, slab = slab_v, ...)
  } else {
    es <- data
    if (!all(c("yi","vi") %in% names(es))) stop("data needs yi & vi, or supply `measure` + raw columns.")
    if (!is.null(slab_v)) attr(es, "slab") <- slab_v
  }
  test <- if (knha) "knha" else "z"
  re <- metafor::rma(yi, vi, data = es, method = method, test = test, level = level)
  fe <- metafor::rma(yi, vi, data = es, method = "FE",  level = level)
  pr <- predict(re, level = level)
  structure(list(re = re, fe = fe, es = es, measure = measure,
                 transf = .ma_transf(measure), pred = pr, level = level),
            class = "ma_fit")
}

## Tidy one-row summary (natural scale) — for results tables.
ma_summary_row <- function(x, label = NA) {
  stopifnot(inherits(x, "ma_fit"))
  tf <- x$transf %||% identity
  re <- x$re; pr <- x$pred
  data.frame(
    label   = label,
    k       = re$k,
    est     = tf(as.numeric(re$b)),
    ci.lb   = tf(re$ci.lb),
    ci.ub   = tf(re$ci.ub),
    pi.lb   = tf(pr$pi.lb),
    pi.ub   = tf(pr$pi.ub),
    p       = re$pval,
    I2      = re$I2,
    tau2    = re$tau2,
    H2      = re$H2,
    Q       = re$QE,
    Q.p     = re$QEp,
    row.names = NULL, stringsAsFactors = FALSE)
}

`%||%` <- function(a, b) if (is.null(a)) b else a

print.ma_fit <- function(x, digits = 3, ...) {
  tf <- x$transf %||% identity
  re <- x$re; fe <- x$fe; pr <- x$pred
  natural <- !is.null(x$transf)
  lab <- if (natural) toupper(x$measure) else "effect"
  f <- function(v) formatC(tf(v), format = "f", digits = digits)
  cat(sprintf("Random-effects meta-analysis (%s, %s%s)\n",
              x$measure %||% "generic", re$method,
              if (re$test == "knha") " + Knapp-Hartung" else ""))
  cat(sprintf("  k = %d studies\n", re$k))
  cat(sprintf("  Pooled %s = %s  %d%% CI [%s, %s]  p = %s\n",
              lab, f(re$b), x$level, f(re$ci.lb), f(re$ci.ub),
              formatC(re$pval, format = "g", digits = 3)))
  cat(sprintf("  %d%% prediction interval [%s, %s]\n", x$level, f(pr$pi.lb), f(pr$pi.ub)))
  cat(sprintf("  Heterogeneity: I^2 = %.1f%%, tau^2 = %.4f, H^2 = %.2f; Q(%d) = %.2f, p = %s\n",
              re$I2, re$tau2, re$H2, re$k - 1, re$QE,
              formatC(re$QEp, format = "g", digits = 3)))
  cat(sprintf("  Common-effect %s = %s [%s, %s] (for comparison)\n",
              lab, f(fe$b), f(fe$ci.lb), f(fe$ci.ub)))
  invisible(x)
}
