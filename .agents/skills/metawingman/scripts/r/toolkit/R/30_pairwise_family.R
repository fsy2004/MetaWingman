## =====================================================================
## 30_pairwise_family.R  —  NEW leaves for the pairwise family adapter
## ---------------------------------------------------------------------
## Extra pooling methods and diagnostic scatter plots that sit alongside
## the core pairwise workhorse (02_pairwise_meta.R) but are surfaced as
## their own Meta Wingman menu leaves. Every function is a thin, honest
## wrapper over a published method in `meta` / `metafor` — nothing is
## re-derived:
##   * pw_gen_forest()  Generic inverse-variance forest (meta::metagen);
##                      the workhorse for pre-computed effects.
##   * pw_corr()        Correlation meta-analysis on Fisher's z with
##                      back-transform to r (meta::metacor; Schwarzer 2015).
##   * pw_metabin()     Build a meta::metabin object with a chosen pooling
##                      method — Mantel-Haenszel (Mantel & Haenszel 1959),
##                      Peto (Yusuf et al. 1985) or binomial-normal GLMM
##                      (Stijnen et al. 2010) — the rare/zero-event methods.
##   * pw_hr()          Hazard-ratio meta-analysis: inverse-variance pool
##                      of log-HR + SE (Parmar 1998; Tierney 2007).
##   * pw_labbe()       L'Abbe plot of event risks (L'Abbe et al. 1987).
##   * pw_radial()      Radial / Galbraith plot (Galbraith 1988).
## Figures open through the shared Nature device (mw_pdf) + nature_base()
## look, matching every other Meta Wingman figure.
##
## Depends: meta, metafor. Sourced after 00-06 (uses mw_pdf, nature_base,
##          the `%||%` helper and metafor::escalc).
## =====================================================================

## Back-transform sm string -> exp() for log measures (forest axes).
.pwf_islog <- function(sm) toupper(sm %||% "") %in% c("OR","RR","IRR","HR","ROM","PETO")

## ---- pw_gen_forest(): generic inverse-variance forest ----------------
## es   : data.frame/escalc carrying yi + vi (from mw_escalc()).
## slab : study labels. measure: label only (axis + sm back-transform).
## Draws meta::metagen()'s publication forest with RE + prediction interval.
pw_gen_forest <- function(es, out, slab = NULL, measure = NULL,
                          method.tau = "REML", knha = TRUE) {
  if (!all(c("yi","vi") %in% names(es))) stop("pw_gen_forest() needs yi & vi.")
  slab <- slab %||% attr(es, "slab") %||% paste("Study", seq_len(nrow(es)))
  sm <- toupper(measure %||% "")
  m <- meta::metagen(TE = es$yi, seTE = sqrt(es$vi), studlab = slab,
                     sm = if (nzchar(sm)) sm else "",
                     common = FALSE, random = TRUE,
                     method.tau = method.tau, hakn = isTRUE(knha),
                     prediction = TRUE)
  h <- max(4, 0.30 * nrow(es) + 3)
  mw_pdf(out, width = 11, height = h); nature_base()
  on.exit(grDevices::dev.off(), add = TRUE)
  meta::forest(m, prediction = TRUE)
  invisible(m)
}

## ---- pw_corr(): correlation meta-analysis (Fisher z) -----------------
## cor, n : numeric vectors (correlation + sample size); slab labels.
## meta::metacor pools on Fisher's z and back-transforms to r.
pw_corr <- function(cor, n, slab, out, method.tau = "REML", knha = TRUE) {
  m <- meta::metacor(cor = cor, n = n, studlab = slab,
                     common = FALSE, random = TRUE,
                     method.tau = method.tau, hakn = isTRUE(knha),
                     prediction = TRUE)
  h <- max(4, 0.30 * length(cor) + 3)
  mw_pdf(out, width = 11, height = h); nature_base()
  on.exit(grDevices::dev.off(), add = TRUE)
  meta::forest(m, prediction = TRUE)
  invisible(m)
}

## ---- pw_metabin(): 2x2 pooling with a chosen method ------------------
## df must carry ai,bi,ci,di (+ study). method one of "MH","Peto","GLMM".
## sm the summary measure ("OR"/"RR"); Peto forces OR. Returns the metabin.
pw_metabin <- function(df, method = c("MH","Peto","GLMM"), sm = "OR",
                       slab = NULL, method.tau = "REML") {
  method <- match.arg(method)
  for (col in c("ai","bi","ci","di"))
    if (!col %in% names(df)) stop(sprintf("CSV 缺列 '%s'(二分类 2x2 需 ai,bi,ci,di)", col))
  if (method == "Peto") sm <- "OR"                 # Peto is defined for OR only
  slab <- slab %||% (if ("study" %in% names(df)) df$study else paste("Study", seq_len(nrow(df))))
  args <- list(event.e = df$ai, n.e = df$ai + df$bi,
               event.c = df$ci, n.c = df$ci + df$di,
               studlab = slab, sm = sm, method = method,
               common = TRUE, random = TRUE)
  ## GLMM has no separate tau2 estimator argument; MH/Peto keep method.tau.
  if (method != "GLMM") args$method.tau <- method.tau
  do.call(meta::metabin, args)
}

## Forest for a metabin object (rare-event methods #5/#6/#7).
pw_metabin_forest <- function(mb, out) {
  h <- max(4, 0.30 * length(mb$studlab) + 3)
  mw_pdf(out, width = 12, height = h); nature_base()
  on.exit(grDevices::dev.off(), add = TRUE)
  meta::forest(mb)
  invisible(out)
}

## Tidy one-row summary (natural scale) from a meta object (metabin/metagen/metacor).
pw_meta_summary <- function(m, label = NA) {
  bt <- if (.pwf_islog(m$sm)) exp else if (toupper(m$sm %||% "") == "COR") function(z) z else identity
  data.frame(
    label   = label,
    method  = m$method %||% NA,
    sm      = m$sm %||% NA,
    k       = m$k,
    est.random = bt(m$TE.random),
    ci.lb   = bt(m$lower.random),
    ci.ub   = bt(m$upper.random),
    p.random = m$pval.random,
    est.common = bt(m$TE.common),
    I2      = m$I2 * 100,
    tau2    = m$tau2,
    Q       = m$Q,
    Q.p     = m$pval.Q,
    row.names = NULL, stringsAsFactors = FALSE)
}

## ---- pw_hr(): hazard-ratio meta-analysis (log-HR + SE) ---------------
## te = log(HR), seTE = SE(log HR); slab labels. Pools inverse-variance.
pw_hr <- function(te, seTE, slab, out, method.tau = "REML", knha = TRUE) {
  m <- meta::metagen(TE = te, seTE = seTE, studlab = slab, sm = "HR",
                     common = FALSE, random = TRUE,
                     method.tau = method.tau, hakn = isTRUE(knha),
                     prediction = TRUE)
  h <- max(4, 0.30 * length(te) + 3)
  mw_pdf(out, width = 11, height = h); nature_base()
  on.exit(grDevices::dev.off(), add = TRUE)
  meta::forest(m, prediction = TRUE)
  invisible(m)
}

## ---- pw_labbe(): L'Abbe plot ----------------------------------------
## mb : a meta::metabin object. Scatter of control vs treatment event risk,
## point area ~ study weight; the line of no effect is the diagonal.
pw_labbe <- function(mb, out, width = 6.5, height = 6) {
  mw_pdf(out, width = width, height = height); nature_base()
  on.exit(grDevices::dev.off(), add = TRUE)
  meta::labbe(mb, bg = "grey70", col = "grey30")
  invisible(out)
}

## ---- pw_radial(): radial / Galbraith plot ---------------------------
## re : a metafor rma object. z-statistic vs precision; the fitted line's
## slope is the pooled effect and 95% of points should fall in the shaded band.
pw_radial <- function(re, out, width = 6.5, height = 6) {
  mw_pdf(out, width = width, height = height); nature_base()
  on.exit(grDevices::dev.off(), add = TRUE)
  metafor::radial(re)
  invisible(out)
}
