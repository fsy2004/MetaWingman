## =====================================================================
## 21_diagnostic_meta.R  —  Diagnostic test accuracy meta-analysis
## ---------------------------------------------------------------------
## Bivariate random-effects meta-analysis of sensitivity & specificity
## (Reitsma et al. 2005; equivalent to the Rutter-Gatsonis HSROC under a
## common model), via the mada package (Doebler & Holling). Reports the
## pooled operating point (sensitivity, specificity), likelihood ratios,
## the diagnostic odds ratio, the SROC AUC, and a test for a threshold
## effect (correlation of sensitivity and false-positive rate). Draws the
## summary ROC curve with per-study points and per-study forests.
##
## Depends: mada.  Data needs per-study TP, FN, FP, TN columns.
## =====================================================================

## dta_run(): full DTA meta-analysis + figures. Returns a structured list.
dta_run <- function(data, out_prefix = "figures/21", add_correction = 0.5) {
  need <- c("TP", "FN", "FP", "TN")
  if (!all(need %in% names(data))) stop("data needs columns: ", paste(need, collapse = ", "))

  descr <- mada::madad(data)                       # per-study Sn/Sp + threshold-effect test
  fit   <- mada::reitsma(data)                     # bivariate model
  s     <- summary(fit); co <- s$coefficients
  sens  <- co["sensitivity", "Estimate"]
  fpr   <- co["false pos. rate", "Estimate"]
  spec  <- 1 - fpr
  auc   <- mada::AUC(fit)
  pts   <- summary(mada::SummaryPts(fit, n.iter = 1000))  # posLR / negLR / DOR
  thr   <- descr$cor_sens_fpr                       # correlation of sens & fpr (threshold effect)
  thr_rho <- if (is.list(thr)) as.numeric(thr$estimate)[1] else as.numeric(thr)[1]

  ## per-study points for the SROC
  sens_i <- data$TP / (data$TP + data$FN)
  fpr_i  <- data$FP / (data$FP + data$TN)

  ## ---- figures (all non-bar) ----
  ff <- function(suffix, expr) { mw_pdf(paste0(out_prefix, suffix), width = 7, height = 6.2)
    on.exit(grDevices::dev.off()); force(expr) }
  ff("_sroc.pdf", {
    graphics::par(mar = c(4.5, 4.5, 2.5, 2))
    plot(fit, sroclwd = 2)                          # plot.reitsma sets its own axis labels
    graphics::title(main = "Summary ROC (bivariate model)")
    graphics::points(fpr_i, sens_i, pch = 21, bg = "grey70",
                     cex = 0.8 + 1.6 * (rowSums(data[need]) / max(rowSums(data[need]))))
    graphics::legend("bottomright", bty = "n",
                     legend = sprintf("AUC = %.3f", auc$AUC))
  })
  mw_pdf(paste0(out_prefix, "_sens.pdf"), width = 7, height = 5.5)
  mada::forest(descr, type = "sens"); grDevices::dev.off()
  mw_pdf(paste0(out_prefix, "_spec.pdf"), width = 7, height = 5.5)
  mada::forest(descr, type = "spec"); grDevices::dev.off()

  cat(sprintf("Diagnostic test accuracy meta-analysis (bivariate, k = %d)\n", nrow(data)))
  cat(sprintf("  Pooled sensitivity = %.3f [%.3f, %.3f]\n", sens,
              co["sensitivity", "95%ci.lb"], co["sensitivity", "95%ci.ub"]))
  cat(sprintf("  Pooled specificity = %.3f [%.3f, %.3f]\n", spec,
              1 - co["false pos. rate", "95%ci.ub"], 1 - co["false pos. rate", "95%ci.lb"]))
  cat(sprintf("  DOR = %.1f  |  +LR = %.2f  |  -LR = %.3f  |  SROC AUC = %.3f\n",
              pts["DOR", "Median"], pts["posLR", "Median"], pts["negLR", "Median"], auc$AUC))
  cat(sprintf("  Threshold effect (corr sens~fpr): rho = %.2f%s\n", thr_rho,
              if (abs(thr_rho) > 0.6) "  (note: strong -> consider HSROC)" else ""))

  invisible(list(descriptive = descr, reitsma = fit, summary = s,
                 sensitivity = sens, specificity = spec, auc = auc,
                 likelihood_ratios_DOR = pts, threshold_test = thr))
}
