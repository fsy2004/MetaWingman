## =====================================================================
## 07_grade.R  —  GRADE certainty of evidence
## ---------------------------------------------------------------------
## Implements the GRADE algebra (Guyatt et al. 2011, J Clin Epidemiol
## series; Balshem et al. 2011): a body of RCT evidence starts at High and
## observational evidence at Low; certainty is lowered by five domains
## (risk of bias, inconsistency, indirectness, imprecision, publication
## bias) and — for observational evidence only — raised by three (large
## effect, dose-response, plausible residual confounding). This module is
## deliberately pure logic: it does NOT invent judgements. ma_grade_suggest()
## offers heuristic starting points a reviewer must confirm; it never
## finalises certainty on its own.
##
## Depends: none (base R). Uses metafor only inside ma_grade_suggest().
## =====================================================================

.CERTAINTY <- c("Very low", "Low", "Moderate", "High")

## ma_grade(): compute the GRADE certainty for one outcome.
##   design       : "rct" (start High=4) or "observational" (start Low=2)
##   downgrades   : rob, inconsistency, indirectness, imprecision, pub_bias
##                  each in {0, -1, -2}
##   upgrades     : large_effect, dose_response, conf_plausible in {0, 1, 2}
##                  (applied only for observational designs, per GRADE)
ma_grade <- function(outcome, design = c("rct", "observational"),
                     rob = 0, inconsistency = 0, indirectness = 0,
                     imprecision = 0, pub_bias = 0,
                     large_effect = 0, dose_response = 0, conf_plausible = 0,
                     verbose = TRUE) {
  design <- match.arg(design)
  downs <- c(rob, inconsistency, indirectness, imprecision, pub_bias)
  ups   <- c(large_effect, dose_response, conf_plausible)
  if (any(downs > 0) || any(downs < -2)) stop("downgrade domains must be in {0,-1,-2}")
  if (any(ups < 0)  || any(ups > 2))     stop("upgrade domains must be in {0,1,2}")
  start <- if (design == "rct") 4L else 2L
  up_total <- if (design == "observational") sum(ups) else 0L
  score <- max(1L, min(4L, start + sum(downs) + up_total))
  cert  <- .CERTAINTY[score]
  row <- data.frame(outcome = outcome, design = design, starting = .CERTAINTY[start],
                    rob = rob, inconsistency = inconsistency, indirectness = indirectness,
                    imprecision = imprecision, pub_bias = pub_bias,
                    upgrades = up_total, certainty = cert,
                    stringsAsFactors = FALSE)
  if (verbose) {
    dn <- c("risk of bias","inconsistency","indirectness","imprecision","publication bias")
    cat(sprintf("GRADE — %s\n  start: %s (%s)\n", outcome, .CERTAINTY[start], design))
    hit <- which(downs != 0)
    if (length(hit)) for (i in hit) cat(sprintf("  downgrade %-17s %+d\n", dn[i], downs[i]))
    if (up_total)   cat(sprintf("  upgrade (observational)  %+d\n", up_total))
    cat(sprintf("  => certainty: %s\n", cert))
  }
  invisible(row)
}

## ma_grade_suggest(): heuristic SUGGESTIONS only — a reviewer must confirm.
## Flags likely imprecision (CI crosses the null, or small total N),
## inconsistency (from I^2), and whether publication bias is testable (k>=10).
ma_grade_suggest <- function(fit, small_N = 400) {
  stopifnot(inherits(fit, "ma_fit"))
  re <- fit$re
  islog <- !is.null(fit$transf) && identical(fit$transf, exp)
  null_val <- 0                                   # yi scale: log(1)=0 for ratios, 0 for differences
  crosses <- (re$ci.lb <= null_val && re$ci.ub >= null_val)
  totN <- tryCatch(sum(fit$es$n1 + fit$es$n2, na.rm = TRUE), error = function(e) NA)
  if (is.na(totN) || totN == 0) totN <- NA
  imprecision <- if (isTRUE(crosses) || (!is.na(totN) && totN < small_N)) -1L else 0L
  inconsistency <- if (re$I2 > 75) -2L else if (re$I2 > 50) -1L else 0L
  pb_testable <- re$k >= 10
  msg <- c(
    sprintf("imprecision: CI %s the null%s -> suggest %d",
            if (crosses) "CROSSES" else "excludes",
            if (!is.na(totN)) sprintf(", total N = %d", as.integer(totN)) else "", imprecision),
    sprintf("inconsistency: I^2 = %.0f%% -> suggest %d", re$I2, inconsistency),
    sprintf("publication bias: k = %d -> %s", re$k,
            if (pb_testable) "testable (run ma_pubbias); judge from funnel/Egger" else "NOT testable (k<10); consider downgrading on suspicion")
  )
  cat("GRADE heuristic suggestions (REVIEW MANUALLY — not final):\n"); cat(paste0("  - ", msg), sep = "\n"); cat("\n")
  invisible(list(imprecision = imprecision, inconsistency = inconsistency,
                 pub_bias_testable = pb_testable, ci_crosses_null = crosses, total_N = totN))
}

## ma_sof_table(): assemble a Summary-of-Findings-style table from ma_grade rows.
ma_sof_table <- function(rows, out = NULL) {
  if (inherits(rows, "data.frame")) rows <- list(rows)
  tab <- do.call(rbind, rows)
  if (!is.null(out)) { utils::write.csv(tab, out, row.names = FALSE); message("wrote ", out) }
  tab
}
