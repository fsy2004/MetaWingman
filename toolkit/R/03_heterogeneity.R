## =====================================================================
## 03_heterogeneity.R  —  Subgroup analysis & meta-regression
## ---------------------------------------------------------------------
## Explain (rather than merely quantify) between-study heterogeneity by
## relating the effect size to study-level moderators. Every routine is a
## thin wrapper over metafor's mixed-effects model machinery — no
## re-implemented estimators.
##
## Methods & primary references:
##   * Mixed-effects (moderator) meta-analysis model, fit by REML:
##       Viechtbauer 2010 (J Stat Softw 36:3, the 'metafor' package);
##       Raudenbush 2009 (in Cooper, Hedges & Valentine, Handbook, ch. 16).
##   * Subgroup analysis via the omnibus Q_M test for between-subgroup
##       DIFFERENCES (moderator = single categorical factor):
##       Borenstein, Hedges, Higgins & Rothstein 2009 (Introduction to
##       Meta-Analysis, ch. 19); Cochrane Handbook §10.11.
##   * Per-subgroup pooling with the Knapp-Hartung (HKSJ) small-sample
##       adjustment: Knapp & Hartung 2003 (Stat Med 22:2693).
##   * Meta-regression (continuous / mixed moderators) & the omnibus
##       Q_M coefficient test: Thompson & Higgins 2002 (Stat Med 21:1559);
##       Berkey et al. 1995 (Stat Med 14:395).
##   * Pseudo-R^2 (proportion of between-study variance explained):
##       Raudenbush 2009; López-López et al. 2014 (Br J Math Stat Psychol).
##   * Bubble plot of a meta-regression: metafor::regplot
##       (Viechtbauer 2010); point area ∝ study precision (inverse SE).
##
## Depends: metafor. Assumes the foundation (00–02) is already sourced,
##          so `%||%` and the `ma_fit` object from ma_pairwise() exist.
## =====================================================================

## ---------------------------------------------------------------------
## ma_subgroup(): categorical moderator / subgroup analysis.
##   fit    : an `ma_fit` (from ma_pairwise()).
##   by     : name (character) of a moderator column in fit$es.
##   digits : rounding for the printed summary.
##
## Fits a mixed-effects moderator model rma(yi, vi, mods = ~factor(by))
## for the between-subgroup Q_M test (H0: all subgroups share one effect),
## then fits a SEPARATE random-effects model per subgroup level (Knapp-
## Hartung) to report each subgroup's pooled estimate, k and I^2. Log/z/
## logit measures are back-transformed for display via fit$transf.
##
## Returns (invisibly) list(qm = <named list QM/df/p>,
##                          table = data.frame(level,k,est,ci.lb,ci.ub,I2)).
## Errors gracefully when the moderator has < 2 non-empty levels.
## ---------------------------------------------------------------------
ma_subgroup <- function(fit, by, digits = 3) {
  stopifnot(inherits(fit, "ma_fit"))
  if (!is.character(by) || length(by) != 1L)
    stop("`by` must be a single column name (character).")
  es <- fit$es
  if (!by %in% names(es))
    stop("Moderator '", by, "' is not a column of fit$es. Available: ",
         paste(names(es), collapse = ", "))

  vals <- es[[by]]
  keep <- !is.na(vals)
  if (is.factor(vals)) {
    levs <- levels(droplevels(vals[keep]))
  } else {
    levs <- sort(unique(as.character(vals[keep])))
  }
  if (length(levs) < 2L)
    stop("Subgroup analysis needs >= 2 non-empty levels of '", by,
         "'; found ", length(levs), ".")

  meth <- fit$re$method
  tf   <- fit$transf %||% identity

  ## ---- omnibus between-subgroup Q_M test (mixed-effects model) --------
  mods_f <- stats::reformulate(sprintf("factor(%s)", by))
  mod_model <- metafor::rma(yi, vi, mods = mods_f, data = es, method = meth)
  qm <- list(QM = as.numeric(mod_model$QM),
             df = as.numeric(mod_model$QMdf[1]),
             p  = as.numeric(mod_model$QMp))

  ## ---- per-subgroup random-effects pooling (Knapp-Hartung) ------------
  rows <- lapply(levs, function(lv) {
    sub <- es[keep & as.character(vals) == lv, , drop = FALSE]
    ## Knapp-Hartung needs residual df (k >= 2); fall back to z-test for k=1.
    m <- tryCatch(
      metafor::rma(yi, vi, data = sub, method = meth, test = "knha"),
      error = function(e)
        tryCatch(metafor::rma(yi, vi, data = sub, method = meth, test = "z"),
                 error = function(e2) NULL))
    if (is.null(m))
      return(data.frame(level = lv, k = nrow(sub), est = NA_real_,
                        ci.lb = NA_real_, ci.ub = NA_real_, I2 = NA_real_,
                        stringsAsFactors = FALSE))
    data.frame(level = lv, k = m$k,
               est   = as.numeric(tf(as.numeric(m$b))),
               ci.lb = as.numeric(tf(m$ci.lb)),
               ci.ub = as.numeric(tf(m$ci.ub)),
               I2    = as.numeric(m$I2),
               stringsAsFactors = FALSE)
  })
  tab <- do.call(rbind, rows)

  ## ---- tidy print -----------------------------------------------------
  natural <- !is.null(fit$transf)
  lab <- if (natural) toupper(fit$measure) else "effect"
  cat(sprintf("Subgroup analysis by '%s'  (%s model)\n", by, meth))
  disp <- tab
  disp$est   <- formatC(disp$est,   format = "f", digits = digits)
  disp$ci.lb <- formatC(disp$ci.lb, format = "f", digits = digits)
  disp$ci.ub <- formatC(disp$ci.ub, format = "f", digits = digits)
  disp$I2    <- paste0(formatC(disp$I2, format = "f", digits = 1), "%")
  names(disp)[names(disp) == "est"] <- lab
  print(disp, right = FALSE, row.names = FALSE)
  cat(sprintf("\nTest for subgroup differences: Q_M(df = %g) = %.2f, p = %s\n",
              qm$df, qm$QM, formatC(qm$p, format = "g", digits = 3)))

  invisible(list(qm = qm, table = tab))
}

## ---------------------------------------------------------------------
## ma_metareg(): meta-regression on one or more moderators.
##   fit  : an `ma_fit`.
##   mods : a one-sided formula (e.g. ~ ablat) OR a character vector of
##          moderator column names (e.g. c("ablat","year")).
##   out  : optional PDF path for a bubble plot. Only produced when there
##          is a SINGLE CONTINUOUS moderator (a numeric column).
##
## Fits rma(yi, vi, mods = <formula>, data = fit$es, method = fit$re$method).
## Reports the coefficient table (est, se, CI, stat, p), the omnibus Q_M
## test, and metafor's pseudo-R^2. Returns list(model, coef).
## ---------------------------------------------------------------------
ma_metareg <- function(fit, mods, out = NULL) {
  stopifnot(inherits(fit, "ma_fit"))
  es <- fit$es

  ## ---- normalise `mods` to a one-sided formula -----------------------
  if (inherits(mods, "formula")) {
    mods_f <- mods
  } else if (is.character(mods) && length(mods) >= 1L) {
    miss <- setdiff(mods, names(es))
    if (length(miss))
      stop("Moderator(s) not in fit$es: ", paste(miss, collapse = ", "))
    mods_f <- stats::reformulate(mods)
  } else {
    stop("`mods` must be a one-sided formula or a character vector of column names.")
  }

  meth  <- fit$re$method
  model <- metafor::rma(yi, vi, mods = mods_f, data = es, method = meth)

  ## ---- coefficient table (natural regression scale) ------------------
  cs <- as.data.frame(coef(summary(model)))
  stat_col <- if ("tval" %in% names(cs)) "tval" else "zval"
  coef_tab <- data.frame(
    term  = rownames(cs),
    est   = cs$estimate,
    se    = cs$se,
    ci.lb = cs$ci.lb,
    ci.ub = cs$ci.ub,
    stat  = cs[[stat_col]],
    p     = cs$pval,
    row.names = NULL, stringsAsFactors = FALSE)

  R2  <- model$R2 %||% NA_real_        # NULL for intercept-only / FE

  ## ---- tidy print -----------------------------------------------------
  cat(sprintf("Meta-regression (%s%s), moderators: %s\n",
              meth, if (model$test == "knha") " + Knapp-Hartung" else "",
              paste(deparse(mods_f[[length(mods_f)]]), collapse = "")))
  disp <- coef_tab
  for (nm in c("est", "se", "ci.lb", "ci.ub", "stat"))
    disp[[nm]] <- formatC(disp[[nm]], format = "f", digits = 4)
  disp$p <- formatC(disp$p, format = "g", digits = 3)
  print(disp, right = FALSE, row.names = FALSE)
  cat(sprintf("\nOmnibus test of moderators: Q_M(df = %g) = %.2f, p = %s\n",
              as.numeric(model$QMdf[1]), as.numeric(model$QM),
              formatC(model$QMp, format = "g", digits = 3)))
  cat(sprintf("Pseudo-R^2 (variance explained): %s\n",
              if (is.na(R2)) "NA" else paste0(formatC(R2, format = "f", digits = 2), "%")))

  ## ---- bubble plot for a single continuous moderator ------------------
  if (!is.null(out)) {
    term_labels <- attr(stats::terms(mods_f), "term.labels")
    single_cont <- length(term_labels) == 1L &&
                   term_labels[1] %in% names(es) &&
                   is.numeric(es[[term_labels[1]]])
    if (!single_cont) {
      message("Bubble plot skipped: `out` requires exactly one CONTINUOUS ",
              "moderator (a numeric column). Moderators given: ",
              paste(term_labels, collapse = ", "))
    } else {
      modname <- term_labels[1]
      dir.create(dirname(out), recursive = TRUE, showWarnings = FALSE)
      natural <- !is.null(fit$transf)
      ylab <- if (natural) sprintf("log(%s)", toupper(fit$measure)) else "Effect size (yi)"
      mw_pdf(out, width = 7, height = 5.5)
      on.exit(grDevices::dev.off(), add = TRUE)
      metafor::regplot(model, mod = modname, ci = TRUE, pi = TRUE,
                       xlab = modname, ylab = ylab,
                       bg = "grey85", shade = TRUE,
                       refline = 0)
      cat(sprintf("Bubble plot written -> %s\n", out))
    }
  }

  invisible(list(model = model, coef = coef_tab))
}
