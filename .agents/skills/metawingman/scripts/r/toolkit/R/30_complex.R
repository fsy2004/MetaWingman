## =====================================================================
## 30_complex.R  —  Complex data-structure meta-analysis (Meta Wingman
##                  family "复杂数据结构 / Complex Data Structures")
## ---------------------------------------------------------------------
## Four published methods for meta-analytic data that violate the
## independence / single-effect-per-study assumption of ordinary
## pairwise MA. Nothing here re-implements an estimator; every quantity
## comes straight from a citable package:
##
##   * Three-level meta-analysis (rma.mv, random = ~1|cluster/study) —
##     partitions heterogeneity into within-cluster (level 2) and
##     between-cluster (level 3) components. Effects nested in the same
##     cluster (lab, cohort, region ...) are correlated; a 2-level model
##     under-estimates the SE.  (Konstantopoulos 2011, Res Synth Methods
##     2:61; Cheung 2014, Psychol Methods 19:211; metafor::rma.mv.)
##   * Robust variance estimation (RVE) — sandwich SE that is valid under
##     an UNKNOWN within-cluster correlation structure. Primary estimate
##     from robumeta::robu (correlated-effects working model, small-sample
##     corrected); cross-checked with clubSandwich CR2 on the rma.mv fit.
##     (Hedges, Tipton & Johnson 2010, Res Synth Methods 1:39; Tipton 2015,
##     Psychol Methods 20:375.)
##   * Dose-response — linear (dosresmeta) — two-stage pooled log-linear
##     trend across ordered exposure levels, Greenland & Longnecker (1992)
##     covariance reconstruction within each study.  (Orsini, Bellocco &
##     Greenland 2006, Stata J 6:40; Crippa & Orsini 2016, JSS 72:1.)
##   * Dose-response — restricted cubic spline (dosresmeta + rms::rcs) —
##     flexible non-linear exposure-response with knots at the pooled
##     dose quantiles; a Wald test for departure from linearity.
##
## Figures are all non-bar (grouped forest, dot-and-whisker CI comparison,
## dose-response curve with CI band), per the toolkit convention.
##
## Depends: metafor, robumeta, clubSandwich, dosresmeta, rms. Assumes the
##          shared device/theme (00_/00a_) is already sourced (uses
##          mw_pdf + nature_base).
## =====================================================================

## -- internal: open a Nature vector PDF, draw, always close the device --
.cx_pdf <- function(path, expr, width = 7, height = 6) {
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  mw_pdf(path, width = width, height = height)
  on.exit(grDevices::dev.off(), add = TRUE)
  if (exists("nature_base", mode = "function")) try(nature_base(), silent = TRUE)
  force(expr)
  invisible(path)
}

.cx_num <- function(x) suppressWarnings(as.numeric(x))

## ---------------------------------------------------------------------
## Three-level meta-analysis  (#32, --analysis ml3)
## dat needs: yi, vi, cluster, study(=subunit id, unique within cluster).
## Writes  <outdir>/ml3_forest.pdf/.png  and  <outdir>/ml3_summary.csv.
## ---------------------------------------------------------------------
mw_complex_ml3 <- function(dat, yi = "yi", vi = "vi", cluster = "cluster",
                           study = "study", method = "REML", outdir = ".") {
  d <- data.frame(
    yi      = .cx_num(dat[[yi]]),
    vi      = .cx_num(dat[[vi]]),
    cluster = as.factor(dat[[cluster]]),
    inner   = seq_len(nrow(dat)),               # unique level-2 id (safe)
    slab    = if (study %in% names(dat)) as.character(dat[[study]])
              else paste0("Study", seq_len(nrow(dat)))
  )
  fit <- metafor::rma.mv(yi, V = vi, random = ~ 1 | cluster/inner,
                         data = d, method = method, slab = d$slab)

  ## Multilevel I^2 decomposition (Cheung 2014 / metafor FAQ): the share of
  ## total variance attributable to each random level, using the typical
  ## sampling variance of a Higgins-Thompson type weight matrix.
  W  <- diag(1 / d$vi)
  X  <- stats::model.matrix(fit)
  P  <- W - W %*% X %*% solve(t(X) %*% W %*% X) %*% t(X) %*% W
  typ <- (fit$k - fit$p) / sum(diag(P))
  denom <- sum(fit$sigma2) + typ
  I2_total <- 100 * sum(fit$sigma2) / denom
  I2_l3    <- 100 * fit$sigma2[1] / denom        # between-cluster (level 3)
  I2_l2    <- 100 * fit$sigma2[2] / denom        # within-cluster  (level 2)

  ## ---- forest, studies grouped by cluster --------------------------
  fh <- max(5, 0.24 * fit$k + 2.5)
  f_pdf <- file.path(outdir, "ml3_forest.pdf")
  ord <- order(d$cluster, d$slab)
  .cx_pdf(f_pdf, height = fh, {
    metafor::forest(fit, order = ord, addpred = TRUE,
      xlab = "Effect size (yi)  [three-level RE model]",
      header = c("Study (nested in cluster)", "Effect [95% CI]"),
      mlab   = sprintf("Pooled (RE.mv, k=%d in %d clusters)",
                       fit$k, nlevels(d$cluster)))
  })
  to_png(f_pdf)

  ## ---- summary table -----------------------------------------------
  summ <- data.frame(
    quantity = c("Pooled estimate", "SE", "95% CI lower", "95% CI upper",
                 "z", "p-value",
                 "sigma^2 level3 (between-cluster)",
                 "sigma^2 level2 (within-cluster)",
                 "I2 total (%)", "I2 level3 (%)", "I2 level2 (%)",
                 "Q", "Q df", "Q p-value",
                 "k (effects)", "n clusters", "tau2 method"),
    value = c(
      round(as.numeric(fit$b[1]), 4), round(fit$se, 4),
      round(fit$ci.lb, 4), round(fit$ci.ub, 4),
      round(fit$zval, 4), signif(fit$pval, 4),
      round(fit$sigma2[1], 5), round(fit$sigma2[2], 5),
      round(I2_total, 2), round(I2_l3, 2), round(I2_l2, 2),
      round(fit$QE, 3), fit$QEdf, signif(fit$QEp, 4),
      fit$k, nlevels(d$cluster), method),
    stringsAsFactors = FALSE)
  write.csv(summ, file.path(outdir, "ml3_summary.csv"), row.names = FALSE)

  cat(sprintf("Three-level MA: pooled = %.4f [%.4f, %.4f], p = %.4g\n",
              as.numeric(fit$b[1]), fit$ci.lb, fit$ci.ub, fit$pval))
  cat(sprintf("  I2 total = %.1f%%  (level3 %.1f%% + level2 %.1f%%)\n",
              I2_total, I2_l3, I2_l2))
  invisible(list(fit = fit, summary = summ))
}

## ---------------------------------------------------------------------
## Robust variance estimation  (#33, --analysis rve)
## Same clustered input. Compares three CIs for the pooled mean:
##   (1) naive multilevel model-based SE (rma.mv),
##   (2) clubSandwich CR2 sandwich SE on that fit (Satterthwaite df),
##   (3) robumeta correlated-effects RVE (small-sample corrected).
## Writes <outdir>/rve_compare.pdf/.png (dot-and-whisker) + rve_summary.csv.
## ---------------------------------------------------------------------
mw_complex_rve <- function(dat, yi = "yi", vi = "vi", cluster = "cluster",
                           method = "REML", outdir = ".") {
  d <- data.frame(
    yi      = .cx_num(dat[[yi]]),
    vi      = .cx_num(dat[[vi]]),
    cluster = as.factor(dat[[cluster]])   # a real column so clubSandwich can find it
  )

  ## (1)+(2) multilevel fit and clubSandwich CR2 robust test on it
  mv <- metafor::rma.mv(yi, V = vi, random = ~ 1 | cluster,
                        data = d, method = method)
  ct <- clubSandwich::coef_test(mv, vcov = "CR2", cluster = d$cluster,
                                test = "Satterthwaite")
  crit_cr2 <- stats::qt(0.975, df = ct$df_Satt)
  est_cr2  <- as.numeric(mv$b[1])
  se_cr2   <- ct$SE

  ## (3) robumeta correlated-effects RVE
  rb <- robumeta::robu(yi ~ 1, data = d, studynum = cluster,
                       var.eff.size = vi, modelweights = "CORR",
                       small = TRUE)
  reg <- rb$reg_table

  rows <- data.frame(
    method   = c("Model-based (rma.mv)",
                 "RVE CR2 (clubSandwich)",
                 "RVE correlated (robumeta)"),
    estimate = c(as.numeric(mv$b[1]), est_cr2, reg$b.r[1]),
    se       = c(mv$se, se_cr2, reg$SE[1]),
    ci.lb    = c(mv$ci.lb, est_cr2 - crit_cr2 * se_cr2, reg$CI.L[1]),
    ci.ub    = c(mv$ci.ub, est_cr2 + crit_cr2 * se_cr2, reg$CI.U[1]),
    df       = c(NA, round(ct$df_Satt, 2), round(reg$dfs[1], 2)),
    pval     = c(mv$pval, ct$p_Satt, reg$prob[1]),
    stringsAsFactors = FALSE)

  ## ---- dot-and-whisker comparison (non-bar) ------------------------
  f_pdf <- file.path(outdir, "rve_compare.pdf")
  .cx_pdf(f_pdf, width = 7, height = 3.4, {
    n <- nrow(rows); yv <- n:1
    xr <- range(c(rows$ci.lb, rows$ci.ub, 0)); pad <- diff(xr) * 0.12
    graphics::par(mar = c(4, 12, 1.2, 1) + 0.1)
    graphics::plot(rows$estimate, yv, xlim = c(xr[1] - pad, xr[2] + pad),
                   ylim = c(0.5, n + 0.5), pch = 19, cex = 1.1,
                   xlab = "Pooled mean effect [95% CI]", ylab = "",
                   yaxt = "n", bty = "n")
    graphics::abline(v = 0, lty = 2, col = "grey55")
    graphics::segments(rows$ci.lb, yv, rows$ci.ub, yv, lwd = 1.5)
    graphics::points(rows$estimate, yv, pch = 19, cex = 1.1)
    graphics::axis(2, at = yv, labels = rows$method, las = 1, tick = FALSE)
    graphics::mtext("Robust variance estimation vs model-based CI",
                    side = 3, line = 0.2, adj = 0, cex = 6/7)
  })
  to_png(f_pdf)

  out <- rows
  out[, c("estimate","se","ci.lb","ci.ub")] <-
    round(out[, c("estimate","se","ci.lb","ci.ub")], 4)
  out$pval <- signif(out$pval, 4)
  write.csv(out, file.path(outdir, "rve_summary.csv"), row.names = FALSE)

  cat("Robust variance estimation (pooled mean, three CIs):\n")
  print(out, row.names = FALSE)
  invisible(list(mv = mv, ct = ct, robu = rb, summary = out))
}

## ---------------------------------------------------------------------
## Dose-response  (#34 linear / #35 spline, --analysis dose_linear|dose_spline)
## dat needs: id, type, dose, cases, n, logrr, se  (referent row se = NA).
## spline = FALSE -> log-linear trend;  TRUE -> restricted cubic spline.
## Writes <outdir>/dose_response.pdf/.png (curve + CI band, log scale on RR)
##        and <outdir>/dose_pred.csv (predicted RR over the dose grid).
## ---------------------------------------------------------------------
mw_complex_dose <- function(dat, id = "id", type = "type", dose = "dose",
                            cases = "cases", n = "n", logrr = "logrr",
                            se = "se", spline = FALSE, knots = NULL,
                            method = "REML", outdir = ".") {
  d <- data.frame(
    id    = dat[[id]],
    type  = as.character(dat[[type]]),
    dose  = .cx_num(dat[[dose]]),
    cases = .cx_num(dat[[cases]]),
    n     = .cx_num(dat[[n]]),
    logrr = .cx_num(dat[[logrr]]),
    se    = .cx_num(dat[[se]])
  )
  method <- tolower(method)                 # dosresmeta wants "reml"/"ml"/...
  if (!method %in% c("fixed","ml","reml","mm","vc")) method <- "reml"
  dmax <- max(d$dose, na.rm = TRUE)
  grid <- data.frame(dose = seq(0, dmax, length.out = 100))

  if (!spline) {
    fit <- dosresmeta::dosresmeta(
      formula = logrr ~ dose, id = id, type = type, se = se,
      cases = cases, n = n, data = d, method = method)
    pr  <- as.data.frame(predict(fit, newdata = grid, exp = TRUE, xref = 0))
    lab <- "Linear (log-linear) dose-response"
    nonlin_p <- NA
  } else {
    if (is.null(knots)) knots <- stats::quantile(d$dose, c(0.25, 0.50, 0.75),
                                                 na.rm = TRUE)
    fit <- dosresmeta::dosresmeta(
      formula = logrr ~ rms::rcs(dose, knots), id = id, type = type, se = se,
      cases = cases, n = n, data = d, method = method)
    pr  <- as.data.frame(predict(fit, newdata = grid, exp = TRUE, xref = 0))
    lab <- sprintf("Restricted cubic spline (%d knots)", length(knots))
    ## Wald test for non-linearity: spline term(s) beyond the first = 0.
    b  <- as.numeric(fit$coefficients); V <- fit$vcov
    nl <- seq(2, length(b))
    nonlin_p <- tryCatch({
      W <- as.numeric(t(b[nl]) %*% solve(V[nl, nl, drop = FALSE]) %*% b[nl])
      stats::pchisq(W, df = length(nl), lower.tail = FALSE)
    }, error = function(e) NA)
  }

  pred <- data.frame(dose = grid$dose,
                     rr    = pr$pred,
                     ci.lb = pr$ci.lb,
                     ci.ub = pr$ci.ub)

  ## ---- dose-response curve with CI band ----------------------------
  f_pdf <- file.path(outdir, "dose_response.pdf")
  .cx_pdf(f_pdf, width = 6.4, height = 5, {
    yr <- range(c(pred$ci.lb, pred$ci.ub, 1), na.rm = TRUE)
    graphics::plot(pred$dose, pred$rr, type = "n", log = "y",
                   ylim = yr, xlab = "Dose", ylab = "Relative risk (95% CI)",
                   bty = "n")
    graphics::polygon(c(pred$dose, rev(pred$dose)),
                      c(pred$ci.lb, rev(pred$ci.ub)),
                      col = grDevices::adjustcolor("#0072B2", 0.18), border = NA)
    graphics::abline(h = 1, lty = 2, col = "grey55")
    graphics::lines(pred$dose, pred$rr, col = "#0072B2", lwd = 2)
    ## observed study log-RRs (back-transformed) as faint reference points
    graphics::points(d$dose, exp(d$logrr), pch = 1, cex = 0.5,
                     col = grDevices::adjustcolor("grey40", 0.6))
    graphics::mtext(lab, side = 3, line = 0.2, adj = 0, cex = 6/7)
  })
  to_png(f_pdf)

  ## ---- prediction table at representative doses --------------------
  reps <- pretty(c(0, dmax), n = 8); reps <- reps[reps >= 0 & reps <= dmax]
  prr  <- as.data.frame(predict(fit, newdata = data.frame(dose = reps),
                                exp = TRUE, xref = 0))
  ptab <- data.frame(dose = reps,
                     rr    = round(prr$pred, 4),
                     ci.lb = round(prr$ci.lb, 4),
                     ci.ub = round(prr$ci.ub, 4))
  if (!is.na(nonlin_p)) attr(ptab, "nonlin_p") <- nonlin_p
  write.csv(ptab, file.path(outdir, "dose_pred.csv"), row.names = FALSE)

  cat(sprintf("Dose-response (%s): %d studies, %d dose levels.\n",
              if (spline) "spline" else "linear",
              length(unique(d$id)), nrow(d)))
  if (!spline) {
    b1 <- as.numeric(fit$coefficients)[1]
    cat(sprintf("  Trend: RR per 1-unit dose = %.4f (log-linear slope %.4f).\n",
                exp(b1), b1))
  } else if (!is.na(nonlin_p)) {
    cat(sprintf("  Wald test for non-linearity: p = %.4g\n", nonlin_p))
  }
  invisible(list(fit = fit, pred = pred, table = ptab))
}
