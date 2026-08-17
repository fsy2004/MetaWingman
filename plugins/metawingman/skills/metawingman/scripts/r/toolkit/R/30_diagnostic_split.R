## =====================================================================
## 30_diagnostic_split.R  —  Diagnostic test accuracy (DTA) split leaves
## ---------------------------------------------------------------------
## Companion to 21_diagnostic_meta.R (dta_run). Exposes the individual
## menu leaves of the diagnostics family so the family adapter
## run_diagnostic.R can build the heavy objects ONCE and switch() to a
## single leaf's output:
##   #46 sroc          — bivariate SROC curve            (mada::reitsma + plot)
##   #47 paired_forest — sensitivity & specificity forest (mada::forest / madad)
##   #48 lr_dor        — likelihood ratios + diagnostic OR (mada::madad / SummaryPts)
##   #49 hsroc         — Rutter-Gatsonis HSROC model       (mada::sroc type="ruttergatsonis")
##
## Every figure opens with mw_pdf()+nature_base() (Nature look) and is
## converted to PNG by the adapter. Only real mada APIs are used; the
## HSROC parameterisation replicates the published Harbord (2007)
## bivariate<->HSROC equivalence (verified numerically against mada's
## internal calc_hsroc_coef()).
## Depends: mada.  Data needs per-study TP, FN, FP, TN columns.
## =====================================================================

## Build the heavy objects once (per-study descriptives + bivariate model).
dta_build <- function(dat, add_correction = 0.5) {
  need <- c("TP", "FN", "FP", "TN")
  if (!all(need %in% names(dat))) stop("data needs columns: ", paste(need, collapse = ", "))
  descr <- mada::madad(dat, correction = add_correction)
  fit   <- mada::reitsma(dat)
  list(descr = descr, fit = fit, dat = dat[need])
}

## ---- #46 Bivariate SROC curve (Reitsma) ------------------------------
dta_fig_sroc <- function(fit, dat, out) {
  need <- c("TP", "FN", "FP", "TN")
  auc  <- mada::AUC(fit)
  sens_i <- dat$TP / (dat$TP + dat$FN)
  fpr_i  <- dat$FP / (dat$FP + dat$TN)
  n_i    <- rowSums(dat[need])
  mw_pdf(out, width = 7, height = 6.2); on.exit(grDevices::dev.off())
  nature_base()
  graphics::par(mar = c(4.5, 4.5, 2.5, 2))
  plot(fit, sroclwd = 2)
  graphics::title(main = "Summary ROC (bivariate model)")
  graphics::points(fpr_i, sens_i, pch = 21, bg = "grey70",
                   cex = 0.8 + 1.6 * (n_i / max(n_i)))
  graphics::legend("bottomright", bty = "n",
                   legend = sprintf("AUC = %.3f", auc$AUC))
  invisible(out)
}

## ---- #47 Paired sensitivity / specificity forest ---------------------
## Two base-graphics forests from madad(); returns the two file paths.
dta_fig_paired <- function(descr, out_sens, out_spec) {
  mw_pdf(out_sens, width = 7, height = 5.5); nature_base()
  mada::forest(descr, type = "sens"); grDevices::dev.off()
  mw_pdf(out_spec, width = 7, height = 5.5); nature_base()
  mada::forest(descr, type = "spec"); grDevices::dev.off()
  invisible(c(out_sens, out_spec))
}

## ---- #48 Likelihood ratios + diagnostic odds ratio -------------------
## Per-study DOR forest (log scale) + pooled +LR / -LR / DOR from the
## bivariate model (mada::SummaryPts). Returns the pooled summary table.
dta_lr_dor <- function(fit, descr, out, slab, n.iter = 5000) {
  dor    <- descr$DOR$DOR
  dor.ci <- descr$DOR$DOR.ci
  k      <- length(dor)
  if (missing(slab) || length(slab) != k) slab <- paste("Study", seq_len(k))

  pts    <- summary(mada::SummaryPts(fit, n.iter = n.iter))   # posLR / negLR / DOR pooled
  pooled_dor <- pts["DOR", "Median"]; pooled_lo <- pts["DOR", "2.5%"]; pooled_hi <- pts["DOR", "97.5%"]

  ## ---- figure: horizontal forest of per-study DOR (log axis) + pooled ----
  ord  <- order(dor)
  dor  <- dor[ord]; lo <- dor.ci[ord, 1]; hi <- dor.ci[ord, 2]; slb <- slab[ord]
  yy   <- seq_len(k)
  xall <- c(lo, hi, pooled_lo, pooled_hi); xall <- xall[is.finite(xall) & xall > 0]
  xlim <- range(xall)
  mw_pdf(out, width = 7, height = max(4.2, 0.32 * k + 1.6)); on.exit(grDevices::dev.off())
  nature_base()
  graphics::par(mar = c(4.2, 8.5, 2.2, 1.2))
  graphics::plot(NA, xlim = log(xlim), ylim = c(0.2, k + 1.2), xlab = "Diagnostic odds ratio (log scale)",
                 ylab = "", yaxt = "n", bty = "n")
  ticks <- axisTicks(log(xlim), log = TRUE, nint = 5)
  graphics::axis(1, at = log(ticks), labels = ticks)
  graphics::axis(2, at = yy, labels = slb, las = 1, tick = FALSE)
  graphics::segments(log(lo), yy, log(hi), yy, lwd = 1.2, col = "grey40")
  graphics::points(log(dor), yy, pch = 19, cex = 0.8)
  ## pooled diamond at y = k+0.7
  ycp <- k + 0.7; hh <- 0.28
  graphics::polygon(log(c(pooled_lo, pooled_dor, pooled_hi, pooled_dor)),
                    c(ycp, ycp + hh, ycp, ycp - hh), col = "black", border = NA)
  graphics::mtext("Pooled (bivariate)", side = 2, at = ycp, las = 1, line = 0.3, cex = 6/7)

  summ <- data.frame(
    metric   = c("Positive LR", "Negative LR", "Diagnostic OR"),
    estimate = c(pts["posLR", "Median"], pts["negLR", "Median"], pts["DOR", "Median"]),
    ci_low   = c(pts["posLR", "2.5%"],   pts["negLR", "2.5%"],   pts["DOR", "2.5%"]),
    ci_high  = c(pts["posLR", "97.5%"],  pts["negLR", "97.5%"],  pts["DOR", "97.5%"])
  )
  invisible(summ)
}

## ---- #49 Rutter-Gatsonis HSROC model ---------------------------------
## HSROC parameters via the Harbord (2007) bivariate<->HSROC equivalence
## (the same closed form mada uses internally); HSROC curve via the
## exported mada::sroc(type="ruttergatsonis"). Returns the parameter table.
hsroc_coef_from_reitsma <- function(fit) {
  co  <- as.numeric(fit$coefficients)
  Psi <- fit$Psi; sd <- sqrt(diag(Psi))
  Theta  <- 0.5 * (sqrt(sd[2] / sd[1]) * co[1] + sqrt(sd[1] / sd[2]) * co[2])
  Lambda <- sqrt(sd[2] / sd[1]) * co[1] - sqrt(sd[1] / sd[2]) * co[2]
  s2theta <- 0.5 * (sd[1] * sd[2] + Psi[1, 2])
  s2alpha <- 2   * (sd[1] * sd[2] - Psi[1, 2])
  beta    <- log(sd[2] / sd[1])
  c(Theta = unname(Theta), Lambda = unname(Lambda), beta = unname(beta),
    sigma2theta = unname(s2theta), sigma2alpha = unname(s2alpha))
}

dta_hsroc <- function(fit, dat, out) {
  need <- c("TP", "FN", "FP", "TN")
  cf   <- hsroc_coef_from_reitsma(fit)
  auc  <- mada::AUC(fit, sroc.type = "ruttergatsonis")
  crv  <- mada::sroc(fit, type = "ruttergatsonis")        # 99 x 2: fpr, sens
  sens_i <- dat$TP / (dat$TP + dat$FN)
  fpr_i  <- dat$FP / (dat$FP + dat$TN)
  n_i    <- rowSums(dat[need])
  ## summary operating point (pooled sens / fpr)
  s  <- summary(fit)$coefficients
  s_sens <- s["sensitivity", "Estimate"]; s_fpr <- s["false pos. rate", "Estimate"]

  mw_pdf(out, width = 7, height = 6.2); on.exit(grDevices::dev.off())
  nature_base()
  graphics::par(mar = c(4.5, 4.5, 2.5, 2))
  graphics::plot(NA, xlim = c(0, 1), ylim = c(0, 1),
                 xlab = "False positive rate (1 - specificity)", ylab = "Sensitivity",
                 main = "HSROC curve (Rutter-Gatsonis)")
  graphics::abline(0, 1, col = "grey80", lty = 3)
  graphics::lines(crv[, 1], crv[, 2], lwd = 2)
  graphics::points(fpr_i, sens_i, pch = 21, bg = "grey70",
                   cex = 0.8 + 1.6 * (n_i / max(n_i)))
  graphics::points(s_fpr, s_sens, pch = 23, bg = "black", cex = 1.3)
  graphics::legend("bottomright", bty = "n",
                   legend = c(sprintf("AUC = %.3f", auc$AUC),
                              sprintf("Lambda = %.2f", cf["Lambda"]),
                              sprintf("beta = %.2f", cf["beta"])))

  summ <- data.frame(
    parameter = c("Theta (threshold)", "Lambda (accuracy)", "beta (asymmetry)",
                  "sigma2 theta", "sigma2 alpha", "SROC AUC"),
    estimate  = c(cf["Theta"], cf["Lambda"], cf["beta"], cf["sigma2theta"],
                  cf["sigma2alpha"], auc$AUC)
  )
  rownames(summ) <- NULL
  invisible(summ)
}
