## =====================================================================
## 05_influence.R  —  Influence / robustness diagnostics for pairwise MA
## ---------------------------------------------------------------------
## Sensitivity and outlier/influence analysis for a fitted random-effects
## meta-analysis. Every quantity is a published, citable diagnostic and
## is computed by metafor (Viechtbauer 2010, JSS 36:3) — nothing here
## re-implements an estimator:
##
##   * Leave-one-out (LOO) sensitivity analysis — refit dropping each
##     study in turn; report the swing of the pooled estimate and flag
##     any study whose removal flips statistical significance.
##     (Cochrane Handbook §10.10; metafor::leave1out)
##   * Case-deletion influence diagnostics — externally studentized
##     residuals, Cook's distance, DFFITS, leverage (hat), covariance
##     ratio, and metafor's combined influence flag.
##     (Viechtbauer & Cheung 2010, Res Synth Methods 1:112–125)
##   * Baujat plot — per-study contribution to overall heterogeneity (Q)
##     vs influence on the pooled estimate.
##     (Baujat et al. 2002, Stat Med 21:2641–2652)
##   * Cumulative meta-analysis — studies added one at a time in a chosen
##     order (year, or precision 1/vi) to expose drift / early dominance.
##     (Lau et al. 1992, N Engl J Med 327:248–254)
##   * GOSH plot — Graphical display Of Study Heterogeneity: the pooled
##     estimate vs I^2 across all (or a sample of) study subsets, to see
##     whether heterogeneity is driven by a discordant cluster.
##     (Olkin, Dahabreh & Trikalinos 2012, Res Synth Methods 3:214–223)
##
## Figures are all non-bar (Baujat scatter, LOO caterpillar, cumulative
## forest, GOSH scatter), per the toolkit convention.
##
## Depends: metafor. Assumes the foundation (00–02) is already sourced
##          (uses the `ma_fit` object, `%||%`, `.ma_refline`).
## =====================================================================

## -- internal: pull the pieces we need from an ma_fit or a raw rma ------
.mi_parts <- function(fit) {
  if (inherits(fit, "ma_fit")) {
    list(re = fit$re, es = fit$es, transf = fit$transf, measure = fit$measure)
  } else if (inherits(fit, "rma")) {
    list(re = fit, es = NULL, transf = NULL, measure = NULL)
  } else {
    stop("ma_influence() needs an 'ma_fit' (from ma_pairwise) or a raw 'rma' fit.")
  }
}

## -- internal: open a vector PDF, draw, always close the device --------
.mi_pdf <- function(path, expr, width = 7, height = 7) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  mw_pdf(path, width = width, height = height)
  on.exit(grDevices::dev.off(), add = TRUE)
  force(expr)              # promise: the plotting call runs on the open device
  invisible(path)
}

## ma_influence(): full robustness workup for a fitted pairwise model.
## fit        : an `ma_fit` (preferred) or a raw metafor `rma` object.
## out_prefix : path stem for the figures; four files are written:
##              <prefix>_baujat.pdf, <prefix>_loo.pdf,
##              <prefix>_cumulative.pdf, and (if k <= 20) <prefix>_gosh.pdf.
## Returns invisibly list(loo, influence, cumulative) — tidy data frames on
## both the model (log) and natural scales — with the raw metafor objects
## attached as attributes. Prints a short human-readable summary.
ma_influence <- function(fit, out_prefix = "figures/05") {
  p       <- .mi_parts(fit)
  re      <- p$re
  es      <- p$es
  measure <- p$measure
  tf      <- p$transf %||% identity          # natural-scale back-transform
  tf_fn   <- p$transf                        # NULL => no atransf on figures
  meas_lab <- if (is.null(measure)) "effect" else toupper(measure)
  null0   <- if (is.null(measure)) 0 else .ma_refline(measure)  # null on yi scale
  fmt     <- function(v) formatC(v, format = "f", digits = 3)

  ## Recover human study labels: ma_pairwise() keeps the slab as an
  ## attribute on $es but does not push it into rma(), so re$slab defaults
  ## to 1..k. Restore it here so every diagnostic + figure labels studies.
  sl <- attr(es, "slab")
  if (!is.null(sl) && length(sl) == re$k) re$slab <- as.character(sl)

  ## ---- 1. leave-one-out sensitivity --------------------------------
  lo <- metafor::leave1out(re)
  full_sig <- (re$ci.lb > null0) || (re$ci.ub < null0)
  loo_sig  <- (lo$ci.lb > null0) | (lo$ci.ub < null0)
  sig_flip <- loo_sig != full_sig
  loo_df <- data.frame(
    study      = lo$slab,
    estimate   = as.numeric(lo$estimate),
    ci.lb      = as.numeric(lo$ci.lb),
    ci.ub      = as.numeric(lo$ci.ub),
    pval       = as.numeric(lo$pval),
    I2         = as.numeric(lo$I2),
    tau2       = as.numeric(lo$tau2),
    est_nat    = as.numeric(tf(lo$estimate)),
    ci.lb_nat  = as.numeric(tf(lo$ci.lb)),
    ci.ub_nat  = as.numeric(tf(lo$ci.ub)),
    sig        = loo_sig,
    sig_change = sig_flip,
    row.names  = NULL, stringsAsFactors = FALSE)
  natloo <- loo_df$est_nat

  ## ---- 2. case-deletion influence diagnostics ----------------------
  inf <- stats::influence(re)   # dispatches to metafor's influence.rma.uni
  is_infl <- as.logical(inf$is.infl)
  influence_df <- data.frame(
    study    = inf$inf$slab,
    rstudent = as.numeric(inf$inf$rstudent),
    dffits   = as.numeric(inf$inf$dffits),
    cook.d   = as.numeric(inf$inf$cook.d),
    cov.r    = as.numeric(inf$inf$cov.r),
    hat      = as.numeric(inf$inf$hat),
    weight   = as.numeric(inf$inf$weight),
    is.infl  = is_infl,
    row.names = NULL, stringsAsFactors = FALSE)

  ## ---- 3. cumulative meta-analysis ---------------------------------
  if (!is.null(es) && "year" %in% names(es) && length(es$year) == re$k) {
    ord <- es$year;  ord_lab <- "year"
  } else {
    ord <- 1 / re$vi; ord_lab <- "precision (1/vi)"
  }
  cu <- metafor::cumul(re, order = ord)
  cumulative_df <- data.frame(
    study    = cu$slab,
    k        = as.integer(cu$k),
    estimate = as.numeric(cu$estimate),
    ci.lb    = as.numeric(cu$ci.lb),
    ci.ub    = as.numeric(cu$ci.ub),
    pval     = as.numeric(cu$pval),
    I2       = as.numeric(cu$I2),
    est_nat  = as.numeric(tf(cu$estimate)),
    row.names = NULL, stringsAsFactors = FALSE)

  ## ---- 4. figures (all non-bar) ------------------------------------
  fh <- function(n) max(5, 0.28 * n + 2)      # forest height scales with k

  ## Baujat: heterogeneity contribution vs influence (scatter, labelled)
  .mi_pdf(paste0(out_prefix, "_baujat.pdf"),
          metafor::baujat(re,
            xlab = "Contribution to overall heterogeneity (Q)",
            ylab = "Influence on pooled estimate"))

  ## Leave-one-out caterpillar/dot forest (forest.default on the LOO object)
  .mi_pdf(paste0(out_prefix, "_loo.pdf"), height = fh(length(lo$slab)), {
    if (is.null(tf_fn)) {
      metafor::forest(lo$estimate, ci.lb = lo$ci.lb, ci.ub = lo$ci.ub,
        slab = lo$slab, refline = as.numeric(re$b[1]),
        xlab = paste0("Pooled ", meas_lab, " (study omitted)"),
        header = c("Study omitted", paste0(meas_lab, " [95% CI]")))
    } else {
      metafor::forest(lo$estimate, ci.lb = lo$ci.lb, ci.ub = lo$ci.ub,
        slab = lo$slab, atransf = tf_fn, refline = as.numeric(re$b[1]),
        xlab = paste0("Pooled ", meas_lab, " (study omitted)"),
        header = c("Study omitted", paste0(meas_lab, " [95% CI]")))
    }
  })

  ## Cumulative forest (forest.cumul.rma)
  .mi_pdf(paste0(out_prefix, "_cumulative.pdf"), height = fh(length(cu$slab)), {
    if (is.null(tf_fn)) {
      metafor::forest(cu, xlab = paste0("Cumulative ", meas_lab, " (by ", ord_lab, ")"))
    } else {
      metafor::forest(cu, atransf = tf_fn,
        xlab = paste0("Cumulative ", meas_lab, " (by ", ord_lab, ")"))
    }
  })

  ## GOSH plot only when the subset space is tractable (k <= 20)
  gosh_written <- FALSE
  if (re$k <= 20) {
    g <- metafor::gosh(re)
    .mi_pdf(paste0(out_prefix, "_gosh.pdf"),
            plot(g, het = "I2", pch = 16))
    gosh_written <- TRUE
  }

  ## ---- 5. short summary --------------------------------------------
  cat("Influence / robustness diagnostics\n")
  cat(sprintf("  k = %d studies; measure = %s\n", re$k, measure %||% "generic"))
  cat(sprintf("  Pooled estimate (full model) = %s  [%s, %s]\n",
              fmt(tf(re$b[1])), fmt(tf(re$ci.lb)), fmt(tf(re$ci.ub))))
  cat(sprintf("  Leave-one-out pooled range = [%s, %s]  (full = %s)\n",
              fmt(min(natloo)), fmt(max(natloo)), fmt(tf(re$b[1]))))
  if (any(sig_flip)) {
    cat("  Significance FLIPS if omitted: ",
        paste(loo_df$study[sig_flip], collapse = "; "), "\n")
  } else {
    cat("  Significance robust: no single study's removal crosses the null.\n")
  }
  infl_names <- influence_df$study[influence_df$is.infl %in% TRUE]
  if (length(infl_names)) {
    cat("  Influential studies (metafor influence flag): ",
        paste(infl_names, collapse = "; "), "\n")
  } else {
    cat("  No studies flagged as influential by case-deletion diagnostics.\n")
  }
  cat(sprintf("  Cumulative order: %s\n", ord_lab))
  cat(sprintf("  Figures written: %s_{baujat,loo,cumulative%s}.pdf\n",
              out_prefix, if (gosh_written) ",gosh" else ""))

  res <- list(loo = loo_df, influence = influence_df, cumulative = cumulative_df)
  attr(res, "loo_obj")    <- lo
  attr(res, "infl_obj")   <- inf
  attr(res, "cumul_obj")  <- cu
  attr(res, "out_prefix") <- out_prefix
  invisible(res)
}
