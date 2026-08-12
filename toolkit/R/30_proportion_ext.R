## =====================================================================
## 30_proportion_ext.R  —  Single-arm proportion: random-intercept GLMM
## ---------------------------------------------------------------------
## Extension to 10_proportion_meta.R for the launcher's proportion family.
## Adds the binomial random-intercept logistic GLMM pooling of a single
## proportion (Stijnen et al. 2010, Stat Med 29:3046-3067) via the real
## meta::metaprop(method = "GLMM") engine — the exact-likelihood
## alternative to the two-step inverse-variance logit. No re-implemented
## statistics: this wraps meta/metafor and reuses the tidy-row and forest
## helpers already defined in 10_proportion_meta.R (both files are sourced
## together by _common.R, so the internal .mp_* helpers are in scope).
##
## Why a GLMM: the normal-approximation logit weights individual studies by
## a within-study variance that is itself estimated, which biases the pooled
## estimate when events are sparse or n small. The binomial-normal GLMM
## models the events with their exact binomial likelihood and a normal
## random study intercept, avoiding the continuity correction and the
## variance-instability of the two-step approach (Cochrane Handbook 10.6;
## Schwarzer, Chemaitelly, Abu-Raddad & Rucker 2019, Res Synth Methods
## 10:476-483). tau^2 is estimated by maximum likelihood (the GLMM does not
## admit REML for this parameterisation).
##
## Depends: meta (>= metaprop GLMM), lme4/metafor (pulled in by metaprop).
## Figures -> vector PDF via the shared mw_pdf device (Nature theme active).
## =====================================================================

## ---- NSE resolver (mirror of .mp_get in 10_; kept local so this file is
##      self-contained even if load order changes) ---------------------
.mpx_get <- function(sub, data, env) {
  if (is.null(sub)) return(NULL)
  if (is.null(data)) return(eval(sub, envir = env))
  eval(sub, envir = as.list(data), enclos = env)
}

## =====================================================================
## ma_proportion_glmm() — pool a single-arm proportion with a
##                        binomial random-intercept logistic GLMM
## ---------------------------------------------------------------------
## data    : data.frame holding the columns (or NULL to use vectors).
## event   : number of events per study (bare column or vector).
## n       : group size per study     (bare column or vector).
## studlab : study labels             (bare column or vector; optional).
## out     : if given, a forest plot is written to this PDF path.
## The summary measure is fixed to the logit scale (sm = "PLOGIT"), which
## is the scale on which metaprop fits the GLMM; the pooled estimate and
## interval are back-transformed to a proportion by the shared .mp_row().
## Returns list(model, row) — `row` is a tidy natural-scale summary.
## =====================================================================
ma_proportion_glmm <- function(data = NULL, event, n, studlab = NULL, out = NULL) {
  env <- parent.frame()
  event_v <- .mpx_get(substitute(event),   data, env)
  n_v     <- .mpx_get(substitute(n),       data, env)
  slab_v  <- .mpx_get(substitute(studlab), data, env)

  a <- list(event = event_v, n = n_v, sm = "PLOGIT", method = "GLMM",
            random = TRUE, common = FALSE, prediction = TRUE)
  if (!is.null(slab_v)) a$studlab <- slab_v
  m <- do.call(meta::metaprop, a)

  if (!is.null(out)) .mp_forest_pdf(m, out,
                                    xlab = "Proportion",
                                    leftcols = c("studlab", "event", "n"),
                                    leftlabs = c("Study", "Events", "Total"))
  ## metaprop(method="GLMM") reports Q as a length-2 vector (Wald-type Cochran Q
  ## and the LRT statistic), which makes .mp_row() recycle into two identical
  ## estimate rows. Keep the first (Wald-type Q, comparable to the IV Q).
  row <- .mp_row(m, "Pooled proportion (GLMM, logit)")
  if (nrow(row) > 1) row <- row[1, , drop = FALSE]
  list(model = m, row = row)
}
