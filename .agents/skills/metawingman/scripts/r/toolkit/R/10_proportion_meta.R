## =====================================================================
## 10_proportion_meta.R  —  Single-arm (one-group) pooling
## ---------------------------------------------------------------------
## Meta-analysis of a summary reported by ONE group per study — a
## prevalence/proportion, a group mean, or an incidence rate — where there
## is no comparator arm. Everything wraps the `meta` package (real API,
## no re-implementation); back-transformations for the results table reuse
## metafor's published transformation functions so the tidy row matches
## exactly what meta::forest() draws.
##
## Statistical methods & primary references
##   * meta package engine ......... Balduzzi, Rucker & Schwarzer 2019,
##       Evid Based Ment Health 22:153-160 (metaprop / metamean / metarate).
##   * Freeman-Tukey double arcsine  Freeman & Tukey 1950, Ann Math Stat
##       21:607-611; harmonic-mean back-transform Miller 1978, Am Stat 32:138.
##   * Logit transformation of proportions ... Cochrane Handbook 10.6.
##   * Incidence rate on the log scale (person-time) ... Cochrane Handbook.
##   * REML tau^2 estimator ........ Viechtbauer 2005, J Educ Behav Stat 30:261.
##   * Prediction interval ......... Higgins, Thompson & Spiegelhalter 2009,
##       JRSS-A 172:137-159.
##
## >>> Freeman-Tukey (PFT) CAVEAT <<<
##   The double-arcsine back-transformation depends on an ASSUMED sample
##   size (metaprop/metafor use the harmonic mean of the study n's). With
##   markedly unequal study sizes it can be non-monotonic and yield
##   pooled proportions or interval limits that are unstable or fall
##   outside [0,1] before clamping. Schwarzer, Chemaitelly, Abu-Raddad &
##   Rucker 2019 (Res Synth Methods 10:476-483) and Barendregt et al. 2013
##   (J Epidemiol Community Health 67:974-978) therefore recommend the
##   logit ('PLOGIT') as the safer default. Both are offered here; report
##   PLOGIT when study sizes are heterogeneous.
##
## Depends: meta, metafor. Assumes the foundation (00-02) may be sourced,
## but this module is self-contained and needs only meta + metafor.
## Figures -> figures/  (PDF, vector).
## =====================================================================

## ---- NSE resolver: bare column in `data`, or an evaluated vector ------
## `sub` is a substitute()d expression captured in the caller; resolve it
## first inside `data` (as a list), falling back to the calling env, so
## `event = xi` (a column) and `event = my_vec` (a variable) both work.
.mp_get <- function(sub, data, env) {
  if (is.null(sub)) return(NULL)
  if (is.null(data)) return(eval(sub, envir = env))
  eval(sub, envir = as.list(data), enclos = env)
}

## ---- back-transform a meta value to the natural (reporting) scale -----
## Uses metafor's published inverse transforms so the table equals the
## forest plot. ni = study sample sizes (needed for PFT harmonic mean),
## ti = person-time (needed for IRFT). Monotone increasing transforms, so
## applying to (lower, upper) preserves ordering.
.mp_backtransf <- function(x, sm, ni = NULL, ti = NULL) {
  if (is.null(x)) return(NA_real_)
  sm <- toupper(sm)
  switch(sm,
    PFT    = metafor::transf.ipft.hm(x, targs = list(ni = ni)),
    PLOGIT = metafor::transf.ilogit(x),
    PAS    = metafor::transf.iarcsin(x),
    PLN    = exp(x),
    PRAW   = x,
    MRAW   = x,
    MLN    = exp(x),
    IR     = x,
    IRLN   = exp(x),
    IRS    = x^2,
    IRFT   = metafor::transf.iirft(x, ti = 1/mean(1/ti, na.rm = TRUE)),
    x)                                  # default: already natural scale
}

## ---- tidy one-row results summary (natural scale) --------------------
## Pooled estimate + 95% CI + prediction interval + heterogeneity, all
## back-transformed for `est`/CI/PI. `sm` records the working scale.
.mp_row <- function(m, label = NA_character_) {
  sm <- m$sm
  ni <- m$n            # denominators (prop) / sample sizes (mean); NULL for rate
  ti <- m$time         # person-time (rate); NULL otherwise
  bt <- function(v) .mp_backtransf(v, sm, ni = ni, ti = ti)
  data.frame(
    label = label,
    k     = m$k,
    sm    = sm,
    est   = bt(m$TE.random),
    ci.lb = bt(m$lower.random),
    ci.ub = bt(m$upper.random),
    pi.lb = bt(m$lower.predict),
    pi.ub = bt(m$upper.predict),
    I2    = 100 * m$I2,
    I2.lb = 100 * m$lower.I2,
    I2.ub = 100 * m$upper.I2,
    tau2  = m$tau2,
    H     = m$H,
    Q     = m$Q,
    Q.df  = m$df.Q,
    Q.p   = m$pval.Q,
    row.names = NULL, stringsAsFactors = FALSE)
}

## ---- render a meta object's forest plot to a vector PDF --------------
.mp_forest_pdf <- function(m, out, ...) {
  d <- dirname(out)
  if (nzchar(d) && !dir.exists(d)) dir.create(d, recursive = TRUE, showWarnings = FALSE)
  h <- max(4.5, 2.5 + 0.34 * m$k)      # height grows with number of studies
  mw_pdf(out, width = 9, height = h)
  on.exit(grDevices::dev.off(), add = TRUE)
  meta::forest(m, prediction = TRUE, ...)
  invisible(out)
}

## =====================================================================
## ma_proportion() — pool a single-arm proportion / prevalence
## ---------------------------------------------------------------------
## data    : data.frame holding the columns (or NULL to use vectors).
## event   : number of events per study (bare column or vector).
## n       : group size per study     (bare column or vector).
## studlab : study labels             (bare column or vector; optional).
## method  : "PFT"  = Freeman-Tukey double arcsine (see CAVEAT above), or
##           "PLOGIT" = logit (Schwarzer 2019 recommended default).
## out     : if given, a forest plot is written to this PDF path.
## Fits an inverse-variance random-effects model (REML tau^2, common=FALSE)
## with a prediction interval; metaprop back-transforms the pooled result
## to a proportion. NOTE: method = "Inverse" is forced so method.tau =
## "REML" is honoured (sm = "PLOGIT" otherwise defaults to a GLMM, which
## permits only ML).
## Returns list(model, row) — `row` is a tidy natural-scale summary.
## =====================================================================
ma_proportion <- function(data = NULL, event, n, studlab = NULL,
                          method = c("PFT", "PLOGIT"), out = NULL) {
  sm  <- match.arg(method)
  env <- parent.frame()
  event_v <- .mp_get(substitute(event),   data, env)
  n_v     <- .mp_get(substitute(n),       data, env)
  slab_v  <- .mp_get(substitute(studlab), data, env)

  a <- list(event = event_v, n = n_v, sm = sm, method = "Inverse",
            method.tau = "REML", random = TRUE, common = FALSE,
            prediction = TRUE)
  if (!is.null(slab_v)) a$studlab <- slab_v
  m <- do.call(meta::metaprop, a)

  if (!is.null(out)) .mp_forest_pdf(m, out,
                                    xlab = "Proportion",
                                    leftcols = c("studlab", "event", "n"),
                                    leftlabs = c("Study", "Events", "Total"))
  list(model = m, row = .mp_row(m, sprintf("Pooled proportion (%s)", sm)))
}

## =====================================================================
## ma_mean() — pool a single-group mean (metamean; raw-mean scale MRAW)
## ---------------------------------------------------------------------
## data, n, mean, sd : per-study group size, mean and SD (columns/vectors).
## studlab, out      : as for ma_proportion().
## Random-effects (REML), common=FALSE, with a prediction interval.
## Returns list(model, row).
## =====================================================================
ma_mean <- function(data = NULL, n, mean, sd, studlab = NULL, out = NULL) {
  env <- parent.frame()
  n_v    <- .mp_get(substitute(n),       data, env)
  mean_v <- .mp_get(substitute(mean),    data, env)
  sd_v   <- .mp_get(substitute(sd),      data, env)
  slab_v <- .mp_get(substitute(studlab), data, env)

  a <- list(n = n_v, mean = mean_v, sd = sd_v, method.tau = "REML",
            random = TRUE, common = FALSE, prediction = TRUE)
  if (!is.null(slab_v)) a$studlab <- slab_v
  m <- do.call(meta::metamean, a)

  if (!is.null(out)) .mp_forest_pdf(m, out, xlab = "Mean")
  list(model = m, row = .mp_row(m, "Pooled mean"))
}

## =====================================================================
## ma_rate() — pool a single-arm incidence rate over person-time
## ---------------------------------------------------------------------
## data, event, time : events and person-time per study (columns/vectors).
## studlab, out      : as above.
## method            : summary measure sm for metarate; default "IRLN"
##                     (log incidence rate) — also "IR", "IRFT", "IRS".
## Random-effects (REML), common=FALSE, with a prediction interval; metarate
## back-transforms to a rate per person-time unit.
## Returns list(model, row).
## =====================================================================
ma_rate <- function(data = NULL, event, time, studlab = NULL,
                    method = "IRLN", out = NULL) {
  env <- parent.frame()
  event_v <- .mp_get(substitute(event),   data, env)
  time_v  <- .mp_get(substitute(time),    data, env)
  slab_v  <- .mp_get(substitute(studlab), data, env)

  a <- list(event = event_v, time = time_v, sm = method, method.tau = "REML",
            random = TRUE, common = FALSE, prediction = TRUE)
  if (!is.null(slab_v)) a$studlab <- slab_v
  m <- do.call(meta::metarate, a)

  if (!is.null(out)) .mp_forest_pdf(m, out, xlab = "Incidence rate")
  list(model = m, row = .mp_row(m, sprintf("Pooled rate (%s)", method)))
}
