## =====================================================================
## 22_bayesian_meta.R  —  Bayesian random-effects meta-analysis
## ---------------------------------------------------------------------
## Bayesian normal-normal hierarchical model via the bayesmeta package
## (Roever 2020, JSS 93:6). Reports posterior summaries for the pooled
## effect (mu) and the heterogeneity (tau), a 95% prediction interval
## (the posterior predictive distribution, column "theta"), and study-level
## shrinkage. The default heterogeneity prior is a weakly-informative
## half-normal(scale=0.5), the recommendation of Roever et al. (2021) for
## log-scale effects; change tau_scale/tau_prior for other outcome types.
##
## Depends: bayesmeta (which pulls forestplot).
## =====================================================================

.bma_tau_prior <- function(kind, scale) {
  switch(kind,
    halfnormal = function(t) bayesmeta::dhalfnormal(t, scale = scale),
    halfcauchy = function(t) bayesmeta::dhalfcauchy(t, scale = scale),
    uniform    = function(t) stats::dunif(t, 0, scale * 10),
    stop("tau_prior must be 'halfnormal', 'halfcauchy' or 'uniform'"))
}

## Derive (yi, sei) from an ma_fit for a Bayesian re-analysis.
bma_from_fit <- function(fit) {
  stopifnot(inherits(fit, "ma_fit"))
  labs <- attr(fit$es, "slab"); if (is.null(labs)) labs <- paste0("Study ", seq_len(nrow(fit$es)))
  list(yi = fit$es$yi, sei = sqrt(fit$es$vi), labels = labs, measure = fit$measure)
}

## bma_run(): Bayesian random-effects meta-analysis.
##   yi, sei  : effect sizes (e.g. log-OR) and their standard errors
##   mu_prior : list(mean, sd) for the effect prior (default vague N(0, 4^2))
##   tau_prior/tau_scale : heterogeneity prior (default half-normal, scale 0.5)
bma_run <- function(yi, sei, labels = NULL,
                    mu_prior = list(mean = 0, sd = 4),
                    tau_prior = c("halfnormal", "halfcauchy", "uniform"),
                    tau_scale = 0.5, out_prefix = NULL) {
  tau_prior <- match.arg(tau_prior)
  bm <- bayesmeta::bayesmeta(y = yi, sigma = sei, labels = labels,
                             mu.prior.mean = mu_prior$mean, mu.prior.sd = mu_prior$sd,
                             tau.prior = .bma_tau_prior(tau_prior, tau_scale))
  S <- bm$summary
  row <- data.frame(
    k        = bm$k,
    mu.median= S["median", "mu"],  mu.lb = S["95% lower", "mu"],  mu.ub = S["95% upper", "mu"],
    tau.median = S["median", "tau"], tau.lb = S["95% lower", "tau"], tau.ub = S["95% upper", "tau"],
    pred.lb  = S["95% lower", "theta"], pred.ub = S["95% upper", "theta"],
    prior    = sprintf("%s(%.2g)", tau_prior, tau_scale),
    stringsAsFactors = FALSE)

  if (!is.null(out_prefix)) {
    # forestplot() is the generic from the 'forestplot' package; bayesmeta
    # registers forestplot.bayesmeta (shrinkage estimates + prediction interval).
    mw_pdf(paste0(out_prefix, "_forest.pdf"), width = 8, height = 0.4 * bm$k + 3)
    invisible(utils::capture.output(print(forestplot::forestplot(bm))))  # render to device, swallow struct dump
    grDevices::dev.off()
    # marginal posterior densities of mu and tau (density curves, not bars)
    mw_pdf(paste0(out_prefix, "_posterior.pdf"), width = 9, height = 4.5)
    graphics::par(mfrow = c(1, 2))
    plot(bm, which = 3, main = "Posterior of effect (mu)")           # marginal mu density
    plot(bm, which = 2, main = "Posterior of heterogeneity (tau)")   # marginal tau density
    grDevices::dev.off()
  }

  cat(sprintf("Bayesian random-effects meta-analysis (bayesmeta, k = %d)\n", bm$k))
  cat(sprintf("  mu  (effect)        median = %.3f  95%% CrI [%.3f, %.3f]\n", row$mu.median, row$mu.lb, row$mu.ub))
  cat(sprintf("  tau (heterogeneity) median = %.3f  95%% CrI [%.3f, %.3f]\n", row$tau.median, row$tau.lb, row$tau.ub))
  cat(sprintf("  95%% prediction interval [%.3f, %.3f]   (tau prior: %s)\n", row$pred.lb, row$pred.ub, row$prior))
  invisible(list(model = bm, row = row))
}
