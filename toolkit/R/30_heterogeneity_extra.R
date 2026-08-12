## =====================================================================
## 30_heterogeneity_extra.R  —  Heterogeneity leaves not covered by 03_*
## ---------------------------------------------------------------------
## Adds the reusable functions behind three Meta Wingman leaves that the
## original subgroup / meta-regression module (03_heterogeneity.R) did not
## expose on their own:
##   * het_stats_table()     — #13 heterogeneity statistics panel
##                             (I^2, H^2, tau^2, tau with profile-likelihood
##                              CIs from metafor::confint; Cochran's Q).
##   * het_subgroup_forest() — #14 subgroup forest (per-subgroup pooled
##                             polygons + between-group test), via meta.
##   * het_pred_forest()     — #16 forest with an explicit 95% prediction
##                             interval (Higgins 2009; Riley 2011), via meta.
##   * het_permute()         — #17 permutation test for meta-regression
##                             (Higgins & Thompson 2004), metafor::permutest.
##
## All routines are thin wrappers over metafor / meta — no re-implemented
## estimators. They consume the shared `ma_fit` object from ma_pairwise()
## so the same random-effects fit (REML defaults) is reused across leaves.
##
## Methods & primary references:
##   * Profile-likelihood CIs for tau^2 / I^2 / H^2: metafor::confint.rma.uni
##       (Viechtbauer 2007, Stat Med 26:37; Viechtbauer 2010, JSS 36:3).
##   * Prediction interval: Higgins, Thompson & Spiegelhalter 2009 (JRSS A
##       172:137); Riley, Higgins & Deeks 2011 (BMJ 342:d549).
##   * Subgroup (between-group) Q test: Borenstein et al. 2009, ch. 19;
##       Cochrane Handbook §10.11 (implemented by meta::metagen subgroup=).
##   * Permutation test for moderators: Higgins & Thompson 2004 (Stat Med
##       23:1663); metafor::permutest (Viechtbauer 2010).
##
## Depends: metafor, meta. Assumes 00-02 already sourced (ma_fit, %||%,
##          mw_pdf, nature_base all in scope).
## =====================================================================

## meta::metagen summary-measure code for a log/risk-difference measure.
.het_sm <- function(measure) {
  m <- toupper(measure %||% "")
  if (m %in% c("OR", "PETO")) "OR"
  else if (m %in% c("RR", "RD", "SMD", "MD", "ROM", "HR")) m
  else ""                                  # generic (no back-transform)
}

## ---------------------------------------------------------------------
## het_stats_table(): tidy heterogeneity statistics with CIs (#13).
##   fit : an `ma_fit` from ma_pairwise().
## Returns data.frame(statistic, estimate, ci.lb, ci.ub) covering
##   tau^2, tau, I^2 (%), H^2 (profile-likelihood CIs) plus Cochran's Q,
##   its df and p (no CI). Also prints a compact summary.
## ---------------------------------------------------------------------
het_stats_table <- function(fit, digits = 4) {
  stopifnot(inherits(fit, "ma_fit"))
  re <- fit$re
  ## profile-likelihood CIs for the variance-component statistics.
  ## `confint` is the stats generic; metafor supplies confint.rma.uni, so we
  ## call the generic (metafor is attached) rather than metafor::confint
  ## (which is not an exported object).
  ci <- tryCatch(stats::confint(re)$random, error = function(e) NULL)
  grab <- function(row) if (!is.null(ci) && row %in% rownames(ci))
      as.numeric(ci[row, c("estimate", "ci.lb", "ci.ub")]) else
      c(NA_real_, NA_real_, NA_real_)
  t2 <- grab("tau^2"); ta <- grab("tau"); i2 <- grab("I^2(%)"); h2 <- grab("H^2")
  tab <- data.frame(
    statistic = c("tau^2", "tau", "I^2 (%)", "H^2",
                  "Q (Cochran)", "Q df", "Q p-value"),
    estimate  = c(t2[1], ta[1], i2[1], h2[1], re$QE, re$k - 1, re$QEp),
    ci.lb     = c(t2[2], ta[2], i2[2], h2[2], NA, NA, NA),
    ci.ub     = c(t2[3], ta[3], i2[3], h2[3], NA, NA, NA),
    row.names = NULL, stringsAsFactors = FALSE)

  cat(sprintf("Heterogeneity statistics (%s, k = %d studies)\n", re$method, re$k))
  disp <- tab
  for (nm in c("estimate", "ci.lb", "ci.ub"))
    disp[[nm]] <- ifelse(is.na(tab[[nm]]), "", formatC(tab[[nm]], format = "f", digits = digits))
  print(disp, right = FALSE, row.names = FALSE)
  invisible(tab)
}

## ---------------------------------------------------------------------
## het_subgroup_forest(): forest grouped by a categorical moderator (#14).
##   fit  : an `ma_fit`; by : moderator column name in fit$es.
##   out  : output PDF path; slab : study labels (character vector).
## Draws per-subgroup random-effects polygons and the between-subgroup
## test using meta::metagen(subgroup=)+forest. Effect sizes are read from
## fit$es (yi/vi) so no raw-count re-derivation is needed.
## ---------------------------------------------------------------------
het_subgroup_forest <- function(fit, by, out, slab = NULL, digits = 2) {
  stopifnot(inherits(fit, "ma_fit"))
  es <- fit$es
  if (!by %in% names(es))
    stop("Subgroup column '", by, "' is not in fit$es.")
  if (is.null(slab)) slab <- attr(es, "slab") %||% paste("Study", seq_len(nrow(es)))
  sm  <- .het_sm(fit$measure)
  grp <- as.character(es[[by]])
  n_lev <- length(unique(grp[!is.na(grp)]))

  m <- meta::metagen(TE = es$yi, seTE = sqrt(es$vi), studlab = slab,
                     subgroup = grp, sm = sm, common = FALSE, random = TRUE,
                     method.tau = fit$re$method,
                     method.random.ci = if (fit$re$test == "knha") "HK" else "classic")

  h <- max(6, 0.32 * nrow(es) + 1.1 * n_lev + 3)
  mw_pdf(out, width = 9.5, height = h)
  on.exit(grDevices::dev.off(), add = TRUE)
  if (exists("nature_base", mode = "function")) nature_base()
  meta::forest(m, digits = digits, prediction = FALSE,
               test.subgroup = TRUE, print.subgroup.name = FALSE,
               col.square = "#0072B2", col.diamond = "#D55E00",
               leftlabs = c("Study", "TE", "seTE"))
  invisible(out)
}

## ---------------------------------------------------------------------
## het_pred_forest(): forest with an explicit 95% prediction interval (#16).
##   fit : an `ma_fit`; out : PDF path; slab : study labels.
## The random-effects summary shows BOTH the confidence interval (diamond)
## and the wider prediction interval (extended bar), so readers see the
## dispersion of TRUE effects, not just the mean.
## ---------------------------------------------------------------------
het_pred_forest <- function(fit, out, slab = NULL, digits = 2) {
  stopifnot(inherits(fit, "ma_fit"))
  es <- fit$es
  if (is.null(slab)) slab <- attr(es, "slab") %||% paste("Study", seq_len(nrow(es)))
  sm <- .het_sm(fit$measure)

  m <- meta::metagen(TE = es$yi, seTE = sqrt(es$vi), studlab = slab, sm = sm,
                     common = FALSE, random = TRUE, method.tau = fit$re$method,
                     method.random.ci = if (fit$re$test == "knha") "HK" else "classic",
                     prediction = TRUE, level.predict = fit$level / 100)

  h <- max(5.5, 0.32 * nrow(es) + 3.2)
  mw_pdf(out, width = 9.5, height = h)
  on.exit(grDevices::dev.off(), add = TRUE)
  if (exists("nature_base", mode = "function")) nature_base()
  meta::forest(m, prediction = TRUE, digits = digits,
               col.square = "#0072B2", col.diamond = "#D55E00",
               col.predict = "#009E73",
               leftlabs = c("Study", "TE", "seTE"))
  invisible(out)
}

## ---------------------------------------------------------------------
## het_permute(): permutation test for a meta-regression (#17).
##   fit  : an `ma_fit`; mods : character vector of moderator column names.
##   iter : number of permutations (approximate test).
## Refits rma(yi, vi, mods) on fit$es, then metafor::permutest to obtain
## permutation-based p-values that are robust to the small-k reference
## distribution problem. Returns a coefficient table (+ an omnibus row).
## ---------------------------------------------------------------------
het_permute <- function(fit, mods, iter = 1000, seed = 12345) {
  stopifnot(inherits(fit, "ma_fit"))
  es <- fit$es
  miss <- setdiff(mods, names(es))
  if (length(miss)) stop("Moderator(s) not in fit$es: ", paste(miss, collapse = ", "))
  model <- metafor::rma(yi, vi, mods = stats::reformulate(mods), data = es,
                        method = fit$re$method)
  set.seed(seed)
  pt <- metafor::permutest(model, iter = iter)

  coef_tab <- data.frame(
    term    = rownames(pt$beta),
    est     = as.numeric(pt$beta),
    se      = as.numeric(pt$se),
    stat    = as.numeric(pt$zval),
    p_perm  = as.numeric(pt$pval),
    row.names = NULL, stringsAsFactors = FALSE)
  ## omnibus moderator test (permutation p)
  omni <- data.frame(term = sprintf("Omnibus QM(df=%g)", as.numeric(pt$QMdf[1])),
                     est = NA_real_, se = NA_real_, stat = as.numeric(pt$QM),
                     p_perm = as.numeric(pt$QMp), stringsAsFactors = FALSE)
  tab <- rbind(coef_tab, omni)

  cat(sprintf("Permutation meta-regression (%s, %d iterations)\n", fit$re$method, iter))
  disp <- tab
  for (nm in c("est", "se", "stat"))
    disp[[nm]] <- ifelse(is.na(tab[[nm]]), "", formatC(tab[[nm]], format = "f", digits = 4))
  disp$p_perm <- formatC(tab$p_perm, format = "g", digits = 3)
  print(disp, right = FALSE, row.names = FALSE)
  invisible(list(model = model, permutest = pt, table = tab))
}
