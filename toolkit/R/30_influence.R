## =====================================================================
## 30_influence.R  —  Per-leaf influence / robustness figure builders
## ---------------------------------------------------------------------
## The influence family (menu leaves #27-#31) shows ONE diagnostic per menu
## click. 05_influence.R's ma_influence() computes ALL of them at once —
## including GOSH, which fits 2^k-1 models and is far too slow to run when
## the user only wants, say, the leave-one-out forest. This module exposes
## each diagnostic as its own thin builder over the SAME published metafor
## APIs (Viechtbauer 2010, JSS 36:3), so the adapter computes only what the
## chosen leaf needs:
##
##   ma_loo_forest()            #27  metafor::leave1out + forest  (LOO caterpillar)
##   ma_baujat_plot()           #28  metafor::baujat             (Q vs influence)
##   ma_cumulative_forest()     #29  metafor::cumul   + forest   (cumulative)
##   ma_gosh_plot()             #30  metafor::gosh    + plot     (subset cloud)
##   ma_influence_diagnostics() #31  influence.rma.uni + plot + dfbetas
##
## Every figure is non-bar (caterpillar / scatter / cumulative forest), per
## the toolkit convention, and is drawn on the shared embedded-Arial vector
## device (mw_pdf), matching the rest of the family byte-for-byte.
##
## Depends: metafor. Assumes the foundation (00-02, 00a theme) is sourced
##          (uses the `ma_fit` object, `%||%`, `.ma_refline`, `mw_pdf`).
## =====================================================================

## -- internal: everything a figure needs out of an ma_fit / raw rma -----
.inf_parts <- function(fit) {
  if (inherits(fit, "ma_fit")) {
    re <- fit$re; es <- fit$es; transf <- fit$transf; measure <- fit$measure
  } else if (inherits(fit, "rma")) {
    re <- fit; es <- NULL; transf <- NULL; measure <- NULL
  } else {
    stop("influence builders need an 'ma_fit' (from ma_pairwise) or a raw 'rma' fit.")
  }
  ## restore human study labels (ma_pairwise stashes them on attr(es,'slab'))
  sl <- attr(es, "slab")
  if (!is.null(sl) && length(sl) == re$k) re$slab <- as.character(sl)
  list(re = re, es = es, transf = transf, tf = transf %||% identity,
       measure = measure,
       meas_lab = if (is.null(measure)) "effect" else toupper(measure),
       null0 = if (is.null(measure)) 0 else .ma_refline(measure))
}

## -- internal: open vector PDF, draw, always close (as in 05_influence) -
.inf_pdf <- function(path, expr, width = 7, height = 7) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  mw_pdf(path, width = width, height = height)
  on.exit(grDevices::dev.off(), add = TRUE)
  force(expr)
  invisible(path)
}

.inf_fh <- function(n) max(5, 0.28 * n + 2)   # forest height scales with k

## ---- #27 Leave-one-out caterpillar forest -------------------------------
## Returns invisibly the tidy leave-one-out table; writes <out>.
ma_loo_forest <- function(fit, out) {
  p <- .inf_parts(fit); re <- p$re; tf <- p$tf; tf_fn <- p$transf
  lo <- metafor::leave1out(re)
  full_sig <- (re$ci.lb > p$null0) || (re$ci.ub < p$null0)
  loo_sig  <- (lo$ci.lb > p$null0) | (lo$ci.ub < p$null0)
  .inf_pdf(out, height = .inf_fh(length(lo$slab)), {
    if (is.null(tf_fn)) {
      metafor::forest(lo$estimate, ci.lb = lo$ci.lb, ci.ub = lo$ci.ub,
        slab = lo$slab, refline = as.numeric(re$b[1]),
        xlab = paste0("Pooled ", p$meas_lab, " (study omitted)"),
        header = c("Study omitted", paste0(p$meas_lab, " [95% CI]")))
    } else {
      metafor::forest(lo$estimate, ci.lb = lo$ci.lb, ci.ub = lo$ci.ub,
        slab = lo$slab, atransf = tf_fn, refline = as.numeric(re$b[1]),
        xlab = paste0("Pooled ", p$meas_lab, " (study omitted)"),
        header = c("Study omitted", paste0(p$meas_lab, " [95% CI]")))
    }
  })
  loo_df <- data.frame(
    study = lo$slab, estimate = as.numeric(lo$estimate),
    ci.lb = as.numeric(lo$ci.lb), ci.ub = as.numeric(lo$ci.ub),
    pval = as.numeric(lo$pval), I2 = as.numeric(lo$I2), tau2 = as.numeric(lo$tau2),
    est_nat = as.numeric(tf(lo$estimate)), ci.lb_nat = as.numeric(tf(lo$ci.lb)),
    ci.ub_nat = as.numeric(tf(lo$ci.ub)), sig = loo_sig,
    sig_change = (loo_sig != full_sig), row.names = NULL, stringsAsFactors = FALSE)
  invisible(loo_df)
}

## ---- #28 Baujat plot ----------------------------------------------------
## Returns invisibly the per-study x (Q-contribution) / y (influence) coords.
ma_baujat_plot <- function(fit, out) {
  p <- .inf_parts(fit); re <- p$re
  ## baujat() both draws AND returns its coordinates, so open the device
  ## directly here (rather than via .inf_pdf) to capture the return value.
  dir.create(dirname(out), recursive = TRUE, showWarnings = FALSE)
  mw_pdf(out, width = 7, height = 7)
  on.exit(grDevices::dev.off(), add = TRUE)
  coords <- metafor::baujat(re,
    xlab = "Contribution to overall heterogeneity (Q)",
    ylab = "Influence on pooled estimate")
  bj <- data.frame(study = re$slab, x = as.numeric(coords$x), y = as.numeric(coords$y),
                   row.names = NULL, stringsAsFactors = FALSE)
  invisible(bj)
}

## ---- #29 Cumulative meta-analysis forest --------------------------------
## Returns invisibly the tidy cumulative table; ordered by year if present.
ma_cumulative_forest <- function(fit, out) {
  p <- .inf_parts(fit); re <- p$re; es <- p$es; tf <- p$tf; tf_fn <- p$transf
  if (!is.null(es) && "year" %in% names(es) && length(es$year) == re$k) {
    ord <- es$year;  ord_lab <- "year"
  } else {
    ord <- 1 / re$vi; ord_lab <- "precision (1/vi)"
  }
  cu <- metafor::cumul(re, order = ord)
  .inf_pdf(out, height = .inf_fh(length(cu$slab)), {
    if (is.null(tf_fn)) {
      metafor::forest(cu, xlab = paste0("Cumulative ", p$meas_lab, " (by ", ord_lab, ")"))
    } else {
      metafor::forest(cu, atransf = tf_fn,
        xlab = paste0("Cumulative ", p$meas_lab, " (by ", ord_lab, ")"))
    }
  })
  cu_df <- data.frame(
    study = cu$slab, k = as.integer(cu$k), estimate = as.numeric(cu$estimate),
    ci.lb = as.numeric(cu$ci.lb), ci.ub = as.numeric(cu$ci.ub),
    pval = as.numeric(cu$pval), I2 = as.numeric(cu$I2),
    est_nat = as.numeric(tf(cu$estimate)), row.names = NULL, stringsAsFactors = FALSE)
  invisible(cu_df)
}

## ---- #30 GOSH plot (heavy: fits 2^k-1 subsets) --------------------------
## Only tractable for small k; the adapter gates on k<=20 before calling.
ma_gosh_plot <- function(fit, out, subsets = NULL) {
  p <- .inf_parts(fit); re <- p$re
  g <- if (is.null(subsets)) metafor::gosh(re) else metafor::gosh(re, subsets = subsets)
  .inf_pdf(out, plot(g, het = "I2", pch = 16))
  invisible(out)
}

## ---- #31 Case-deletion influence diagnostics plot -----------------------
## metafor influence.rma.uni + plot.infl.rma.uni (+ DFBETAS). Returns
## invisibly list(table, pdf). Rendered on the Nature device (nature_pdf).
ma_influence_diagnostics <- function(fit, out_prefix = "figures/30",
                                     size = "double", height_mm = 180) {
  p  <- .inf_parts(fit); re <- p$re
  inf <- stats::influence(re)            # dispatches to influence.rma.uni
  dfb <- stats::dfbetas(re)              # dispatches to dfbetas.rma.uni
  dfb_col <- as.numeric(as.data.frame(dfb)[[1]])
  is_infl <- as.logical(inf$is.infl)

  pdf_path <- paste0(out_prefix, "_influence.pdf")
  nature_pdf(pdf_path, size = size, height_mm = height_mm)
  on.exit(grDevices::dev.off(), add = TRUE)
  plot(inf, plotdfb = TRUE)              # plot.infl.rma.uni (+ DFBETAS panel)

  d <- inf$inf
  tbl <- data.frame(
    study = d$slab, rstudent = as.numeric(d$rstudent), dffits = as.numeric(d$dffits),
    cook.d = as.numeric(d$cook.d), cov.r = as.numeric(d$cov.r),
    tau2.del = as.numeric(d$tau2.del), QE.del = as.numeric(d$QE.del),
    hat = as.numeric(d$hat), weight = as.numeric(d$weight),
    dfbetas = dfb_col, is.infl = is_infl, row.names = NULL, stringsAsFactors = FALSE)

  cat("Case-deletion influence diagnostics (Cook / hat / DFFITS / DFBETAS)\n")
  cat(sprintf("  k = %d studies; measure = %s\n", re$k, p$measure %||% "generic"))
  infl_names <- tbl$study[tbl$is.infl %in% TRUE]
  if (length(infl_names))
    cat("  Influential studies (metafor influence flag): ",
        paste(infl_names, collapse = "; "), "\n")
  else
    cat("  No studies flagged as influential by case-deletion diagnostics.\n")

  res <- list(table = tbl, pdf = pdf_path)
  attr(res, "infl_obj") <- inf; attr(res, "dfb_obj") <- dfb
  invisible(res)
}
