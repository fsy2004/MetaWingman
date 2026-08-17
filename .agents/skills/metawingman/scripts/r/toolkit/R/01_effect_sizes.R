## =====================================================================
## 01_effect_sizes.R  —  Effect-size calculation (wraps metafor::escalc)
## ---------------------------------------------------------------------
## One entry point for every effect measure a clinical/biomedical
## meta-analysis needs, with a printable guide of which raw columns each
## measure requires. This is a thin, honest wrapper: the numerics are
## metafor::escalc (Viechtbauer 2010, JSS 36:3) — we add validation, a
## sensible study label, and a lookup table, nothing that re-implements
## the estimator.
##
## Depends: metafor.
## =====================================================================

## Supported measures -> required inputs + typical use (from metafor docs)
.ES_GUIDE <- rbind(
  data.frame(family="continuous (2 groups)", measure="MD",   inputs="m1i,sd1i,n1i,m2i,sd2i,n2i", use="raw mean difference, same scale"),
  data.frame(family="continuous (2 groups)", measure="SMD",  inputs="m1i,sd1i,n1i,m2i,sd2i,n2i", use="Hedges' g (bias-corrected); different scales"),
  data.frame(family="continuous (2 groups)", measure="SMDH", inputs="m1i,sd1i,n1i,m2i,sd2i,n2i", use="SMD w/ unequal variances (Bonett)"),
  data.frame(family="continuous (2 groups)", measure="ROM",  inputs="m1i,sd1i,n1i,m2i,sd2i,n2i", use="log ratio of means (response ratio)"),
  data.frame(family="binary (2x2)",          measure="OR",   inputs="ai,bi,ci,di  OR ai,n1i,ci,n2i", use="odds ratio (log scale)"),
  data.frame(family="binary (2x2)",          measure="RR",   inputs="ai,bi,ci,di  OR ai,n1i,ci,n2i", use="risk ratio (log scale)"),
  data.frame(family="binary (2x2)",          measure="RD",   inputs="ai,bi,ci,di  OR ai,n1i,ci,n2i", use="risk difference"),
  data.frame(family="binary (2x2)",          measure="PETO", inputs="ai,bi,ci,di",                 use="Peto odds ratio (rare events)"),
  data.frame(family="correlation",           measure="ZCOR", inputs="ri,ni",                       use="Fisher's z (recommended for pooling)"),
  data.frame(family="correlation",           measure="COR",  inputs="ri,ni",                       use="raw correlation"),
  data.frame(family="proportion (1 group)",  measure="PLO",  inputs="xi,ni",                       use="logit proportion"),
  data.frame(family="proportion (1 group)",  measure="PFT",  inputs="xi,ni",                       use="Freeman-Tukey double arcsine (stabilizes near 0/1)"),
  data.frame(family="proportion (1 group)",  measure="PR",   inputs="xi,ni",                       use="raw proportion"),
  data.frame(family="incidence rate",        measure="IRLN", inputs="xi,ti",                       use="log incidence rate (person-time)"),
  data.frame(family="incidence rate",        measure="IRFT", inputs="xi,ti",                       use="Freeman-Tukey incidence rate"),
  data.frame(family="mean (1 group)",        measure="MN",   inputs="mi,sdi,ni",                   use="single-group raw mean"),
  data.frame(family="pre-computed / HR / other", measure="GEN", inputs="yi,vi (or yi,sei)",        use="generic inverse-variance; use for log-HR, MD from CIs, etc."),
  stringsAsFactors = FALSE)

## Print / return the effect-size selection guide.
es_guide <- function(print = TRUE) {
  if (print) { cat("Effect measures supported by es_calc():\n\n"); print(.ES_GUIDE, right = FALSE, row.names = FALSE) }
  invisible(.ES_GUIDE)
}

## es_calc(): compute effect sizes + sampling variances.
## measure : one of .ES_GUIDE$measure (case-insensitive). "GEN" passes
##           pre-computed yi + (vi or sei) straight through.
## data    : data.frame holding the required columns.
## slab    : optional study-label expression/vector (e.g. ~paste(author,year)).
## ...     : the raw-count / summary columns (ai, m1i, ri, xi, ...) as in escalc.
## Returns an 'escalc' data.frame with yi, vi (ready for rma()).
## NSE note: column arguments (ai, m1i, ri, xi, yi, ...) are captured
## UNEVALUATED and resolved inside `data`, so `ai = tpos` works whether
## es_calc is called directly or forwarded through ma_pairwise's dots.
## `slab` may be a formula (~paste(author, year)) or an evaluated vector.
## All original columns of `data` are preserved (needed for moderators).
es_calc <- function(measure, data, slab = NULL, ...) {
  measure <- toupper(measure)
  if (!measure %in% .ES_GUIDE$measure)
    stop("Unknown measure '", measure, "'. See es_guide() for the menu.")
  dots <- eval(substitute(alist(...)))
  penv <- parent.frame()
  ev  <- function(nm) if (nm %in% names(dots)) eval(dots[[nm]], data, penv) else NULL

  slab_v <- NULL
  if (!is.null(slab)) {
    if (inherits(slab, "formula")) slab_v <- eval(slab[[length(slab)]], data, environment(slab))
    else slab_v <- slab
  }

  if (measure == "GEN") {                        # generic inverse variance
    yi <- ev("yi"); vi <- ev("vi"); sei <- ev("sei")
    if (is.null(yi)) stop("measure='GEN' needs yi and (vi or sei).")
    if (is.null(vi)) { if (is.null(sei)) stop("Provide vi or sei for GEN."); vi <- sei^2 }
    out <- data.frame(data, yi = as.numeric(yi), vi = as.numeric(vi))
  } else {
    cols <- lapply(dots, function(e) eval(e, data, penv))
    tmp  <- do.call(metafor::escalc, c(list(measure = measure), cols))
    out  <- data.frame(data, yi = as.numeric(tmp$yi), vi = as.numeric(tmp$vi))
  }
  class(out) <- c("escalc", "data.frame")
  attr(out, "yi.names") <- "yi"; attr(out, "vi.names") <- "vi"
  attr(out, "measure")  <- measure
  if (!is.null(slab_v)) attr(out, "slab") <- slab_v
  out
}
