## =====================================================================
## 04_publication_bias.R  —  Small-study effects / publication bias
## ---------------------------------------------------------------------
## Diagnose and adjust for small-study effects on top of an `ma_fit`
## (from ma_pairwise()). Every procedure is a published, citable method
## wrapping metafor (Viechtbauer 2010, JSS 36:3); nothing is re-derived:
##
##   * Egger's regression test for funnel asymmetry
##       Egger, Davey Smith, Schneider & Minder 1997 (BMJ 315:629);
##       regression form via metafor::regtest(model = "lm").
##   * Begg & Mazumdar rank-correlation test (Kendall's tau)
##       Begg & Mazumdar 1994 (Biometrics 50:1088); metafor::ranktest().
##   * Duval & Tweedie trim-and-fill (impute suppressed studies)
##       Duval & Tweedie 2000 (Biometrics 56:455); metafor::trimfill().
##   * PET-PEESE conditional small-study-adjusted estimate
##       Stanley & Doucouliagos 2014 (Res Synth Methods 5:60):
##       PET  = rma(yi, vi, mods = ~ sqrt(vi))   (precision-effect test)
##       PEESE= rma(yi, vi, mods = ~ vi)         (precision-effect est. w/ SE)
##       decision: if the PET intercept's one-sided p >= .10 the effect is
##       indistinguishable from null -> report the PET intercept; else the
##       (less-biased) PEESE intercept, back-transformed to the natural scale.
##   * Contour-enhanced funnel plot
##       Peters, Sutton, Jones, Abrams & Rushton 2008 (J Clin Epidemiol
##       61:991); metafor::funnel(level=, shade=).
##   * Reliability caveat: asymmetry tests are underpowered and unreliable
##       with < 10 studies — Sterne et al. 2011 (BMJ 343:d4002).
##
## Depends: metafor. Assumes the foundation (00-02) is already sourced
##          (uses the `ma_fit` object, its $re / $es / $transf fields,
##          the `%||%` helper and `.ma_refline()`).
## =====================================================================

## ---- internal: one-sided p for the PET intercept ----------------------
## Test whether the bias-corrected (SE=0) effect is non-null in the
## direction of the pooled random-effects estimate. For a symmetric test
## statistic the one-sided p is p2/2 when the intercept points the same
## way as the pooled effect, and 1 - p2/2 otherwise.
.pp_one_sided_p <- function(est, p2, ref_sign) {
  if (!is.finite(est) || !is.finite(p2)) return(NA_real_)
  if (ref_sign == 0) return(p2 / 2)          # no reference direction
  if (sign(est) == ref_sign) p2 / 2 else 1 - p2 / 2
}

## ---- ma_pubbias(): full small-study / publication-bias workup ---------
## fit    : an `ma_fit` (from ma_pairwise()). Uses fit$re, fit$es, fit$transf.
## min_k  : below this many studies the asymmetry tests are flagged
##          unreliable (Sterne 2011; default 10).
## Returns (invisibly) an object of class "ma_pubbias" and prints a
## readable summary. Estimates are reported back-transformed to the
## natural scale when fit$transf is set (e.g. OR = exp).
ma_pubbias <- function(fit, min_k = 10) {
  if (!inherits(fit, "ma_fit"))
    stop("ma_pubbias() needs an 'ma_fit' object from ma_pairwise().")
  re <- fit$re
  es <- fit$es
  k  <- re$k
  tf <- fit$transf %||% identity
  natural  <- !is.null(fit$transf)
  ref_sign <- sign(as.numeric(re$b))

  reliable <- k >= min_k
  if (!reliable)
    warning(sprintf(
      "Only k = %d studies (< %d): funnel-asymmetry tests are underpowered and unreliable (Sterne 2011).",
      k, min_k), call. = FALSE)

  ## -- Egger's regression test (regression form) -----------------------
  egger <- tryCatch({
    rt  <- metafor::regtest(re, model = "lm")
    df  <- rt$ddf %||% rt$dfs
    list(stat = as.numeric(rt$zval), df = df, p = as.numeric(rt$pval),
         predictor = rt$predictor,
         est = as.numeric(rt$est),               # predicted effect at SE = 0
         ci.lb = as.numeric(rt$ci.lb), ci.ub = as.numeric(rt$ci.ub),
         ok = TRUE)
  }, error = function(e) list(ok = FALSE, msg = conditionMessage(e)))

  ## -- Begg & Mazumdar rank-correlation test ---------------------------
  rank <- tryCatch({
    rk <- metafor::ranktest(re)
    list(tau = as.numeric(rk$tau), p = as.numeric(rk$pval), ok = TRUE)
  }, error = function(e) list(ok = FALSE, msg = conditionMessage(e)))

  ## -- Duval & Tweedie trim-and-fill -----------------------------------
  trimfill <- tryCatch({
    taf <- metafor::trimfill(re)
    list(k0 = as.integer(taf$k0), side = taf$side,
         est = as.numeric(taf$b), ci.lb = as.numeric(taf$ci.lb),
         ci.ub = as.numeric(taf$ci.ub), k.total = as.integer(taf$k),
         ok = TRUE)
  }, error = function(e) list(ok = FALSE, msg = conditionMessage(e)))

  ## -- PET-PEESE conditional estimate ----------------------------------
  petpeese <- tryCatch({
    pet   <- metafor::rma(yi, vi, mods = ~ sqrt(vi), data = es)
    peese <- metafor::rma(yi, vi, mods = ~ vi,        data = es)
    petc   <- coef(summary(pet))
    peesec <- coef(summary(peese))
    pet_est <- petc[1, "estimate"]; pet_p2 <- petc[1, "pval"]
    pet_p1  <- .pp_one_sided_p(pet_est, pet_p2, ref_sign)
    use_pet <- is.finite(pet_p1) && pet_p1 >= 0.10
    chosen  <- if (use_pet) "PET" else "PEESE"
    row     <- if (use_pet) petc[1, ] else peesec[1, ]
    list(model = chosen,
         pet.est = pet_est, pet.p.two = pet_p2, pet.p.one = pet_p1,
         peese.est = peesec[1, "estimate"], peese.p = peesec[1, "pval"],
         corrected = as.numeric(row["estimate"]),
         corrected.lb = as.numeric(row["ci.lb"]),
         corrected.ub = as.numeric(row["ci.ub"]),
         ok = TRUE)
  }, error = function(e) list(ok = FALSE, msg = conditionMessage(e)))

  out <- structure(
    list(k = k, min_k = min_k, reliable = reliable,
         measure = fit$measure, natural = natural, transf = tf,
         pooled = as.numeric(tf(as.numeric(re$b))),
         egger = egger, rank = rank, trimfill = trimfill, petpeese = petpeese),
    class = "ma_pubbias")
  print(out)
  invisible(out)
}

## ---- readable summary --------------------------------------------------
print.ma_pubbias <- function(x, digits = 3, ...) {
  tf <- x$transf
  scale_lab <- if (x$natural) toupper(x$measure %||% "effect") else "effect"
  ff <- function(v) if (is.finite(v)) formatC(v, format = "f", digits = digits) else "NA"
  fp <- function(p) if (is.finite(p)) formatC(p, format = "g", digits = 3) else "NA"

  cat("Small-study effects / publication-bias assessment\n")
  cat(sprintf("  k = %d studies; pooled %s = %s (natural scale)\n",
              x$k, scale_lab, ff(x$pooled)))
  if (!x$reliable)
    cat(sprintf("  ! k < %d: asymmetry tests underpowered & unreliable (Sterne 2011).\n",
                x$min_k))

  ## Egger
  e <- x$egger
  if (isTRUE(e$ok)) {
    cat(sprintf("  Egger regression test : t(%s) = %s, p = %s%s\n",
                ifelse(is.null(e$df), "NA", e$df), ff(e$stat), fp(e$p),
                if (is.finite(e$p) && e$p < 0.05) "  (asymmetry)" else ""))
    if (is.finite(e$est))
      cat(sprintf("      predicted effect at SE=0 = %s (natural: %s)\n",
                  ff(e$est), ff(as.numeric(tf(e$est)))))
  } else cat("  Egger regression test : unavailable (", e$msg, ")\n", sep = "")

  ## Rank correlation
  r <- x$rank
  if (isTRUE(r$ok))
    cat(sprintf("  Begg rank correlation : Kendall's tau = %s, p = %s\n",
                ff(r$tau), fp(r$p)))
  else cat("  Begg rank correlation : unavailable (", r$msg, ")\n", sep = "")

  ## Trim-and-fill
  tfl <- x$trimfill
  if (isTRUE(tfl$ok)) {
    cat(sprintf("  Trim-and-fill         : k0 = %d imputed on the %s; adjusted %s = %s [%s, %s]\n",
                tfl$k0, tfl$side, scale_lab,
                ff(as.numeric(tf(tfl$est))),
                ff(as.numeric(tf(tfl$ci.lb))), ff(as.numeric(tf(tfl$ci.ub)))))
  } else cat("  Trim-and-fill         : unavailable (", tfl$msg, ")\n", sep = "")

  ## PET-PEESE
  pp <- x$petpeese
  if (isTRUE(pp$ok)) {
    cat(sprintf("  PET-PEESE             : PET intercept one-sided p = %s -> use %s\n",
                fp(pp$pet.p.one), pp$model))
    cat(sprintf("      small-study-adjusted %s = %s [%s, %s]\n",
                scale_lab,
                ff(as.numeric(tf(pp$corrected))),
                ff(as.numeric(tf(pp$corrected.lb))),
                ff(as.numeric(tf(pp$corrected.ub)))))
  } else cat("  PET-PEESE             : unavailable (", pp$msg, ")\n", sep = "")

  invisible(x)
}

## ---- ma_funnel(): contour-enhanced funnel (+ trim-and-fill overlay) ---
## fit      : an `ma_fit`. Plots fit$re on its (log/native) scale.
## out      : PDF path (vector), e.g. "figures/04_funnel_bcg.pdf".
## contour  : significance-contour levels (%). Default 90/95/99 shading
##            reveals whether missing studies fall in non-significant
##            regions (Peters 2008).
## trimfill : if TRUE, refit trim-and-fill and draw the imputed studies
##            as open points on the same funnel (Duval & Tweedie 2000).
## Returns (invisibly) the object plotted (trimfill fit if requested,
## else fit$re).
ma_funnel <- function(fit, out, contour = c(90, 95, 99), trimfill = TRUE,
                      width = 7, height = 6) {
  if (!inherits(fit, "ma_fit"))
    stop("ma_funnel() needs an 'ma_fit' object from ma_pairwise().")
  contour <- sort(contour)
  ## shade: light-to-dark grey ramp, one colour per contour level
  shade <- if (length(contour) == 3) c("white", "gray85", "gray70")
           else grDevices::grey(seq(0.98, 0.60, length.out = length(contour)))
  refline <- tryCatch(.ma_refline(fit$measure), error = function(e) 0)

  obj <- if (isTRUE(trimfill)) metafor::trimfill(fit$re) else fit$re

  dir.create(dirname(out), showWarnings = FALSE, recursive = TRUE)
  mw_pdf(out, width = width, height = height)
  on.exit(grDevices::dev.off(), add = TRUE)
  metafor::funnel(obj, level = contour, shade = shade,
                  legend = TRUE, back = "white", refline = refline)
  title(main = sprintf("Contour-enhanced funnel%s",
                       if (isTRUE(trimfill)) " (trim-and-fill overlay)" else ""))
  invisible(obj)
}
