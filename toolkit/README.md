# meta-analysis-toolkit

Reproducible, **publication-standard meta-analysis in R** — a curated set of small,
composable modules that wrap the field-standard packages (`metafor`, `meta`,
`netmeta`, `mada`, `bayesmeta`, `robvis`, `metasens`) with the defaults and outputs
that top journals and the reporting guidelines (PRISMA 2020, Cochrane, GRADE, MOOSE)
expect. Nothing here re-implements statistics from scratch: every function is a thin,
documented wrapper around a peer-reviewed estimator, and every module is tested on real
bundled datasets.

Built for the common workflow of a clinical/biomedical evidence synthesis: from raw
extracted numbers → effect sizes → pooling → heterogeneity → bias/robustness → certainty
→ the figures and tables a reviewer will ask for, plus network, diagnostic-accuracy, and
Bayesian designs.

## Why this exists

Most meta-analysis code in the wild is copy-pasted, bound to one project's data, and
missing half of what reviewers now require (prediction intervals, small-study-adjusted
estimates, GRADE, a PRISMA flow). This toolkit is the opposite: **generalised functions +
top-journal defaults + a standards checklist** (`docs/TOP_JOURNAL_STANDARDS.md`).

## Install

```r
# core (required)
install.packages(c("metafor", "meta", "netmeta", "metadat"))
# advanced modules + helpers
install.packages(c("mada", "bayesmeta", "robvis", "metasens", "estmeansd"))
```

The toolkit is sourced, not installed as a package:

```r
for (f in list.files("R", pattern = "\\.R$", full.names = TRUE)) source(f)
```

## Quick start

```r
library(metafor); library(metadat)
for (f in list.files("R", pattern = "\\.R$", full.names = TRUE)) source(f)

data(dat.bcg, package = "metadat")                      # classic BCG trials (OR)
fit <- ma_pairwise(dat.bcg, "OR",
                   ai = tpos, bi = tneg, ci = cpos, di = cneg,
                   slab = ~paste(author, year))
fit                                                     # pooled OR + CI + prediction interval + I^2/tau^2/Q

ma_forest(fit, "figures/forest.pdf")                    # publication forest
ma_pubbias(fit); ma_funnel(fit, "figures/funnel.pdf")   # Egger/Begg/trim-fill/PET-PEESE + contour funnel
ma_influence(fit, "figures/infl")                       # leave-one-out, Baujat, cumulative, GOSH
ma_subgroup(fit, "alloc"); ma_metareg(fit, ~ablat)      # heterogeneity sources
ma_grade("BCG vs TB", "rct", rob = -1, inconsistency = -1)   # GRADE certainty
```

## Modules

Source order matters only in that `R/00–02` are the foundation the rest build on.

| # | File | What it does | Key functions |
|---|------|--------------|---------------|
| 00 | `R/00_data_prep.R` | median/IQR/range → mean+SD (Wan 2014, estmeansd); SE/CI → SD; effect-size conversions | `dp_median_to_mean_sd`, `dp_ci_to_sd`, `dp_lnOR_to_SMD`, … |
| 01 | `R/01_effect_sizes.R` | effect sizes for every outcome type (wraps `escalc`) + selection guide | `es_calc`, `es_guide` |
| 02 | `R/02_pairwise_meta.R` | core random + common-effect pooling (REML + Knapp-Hartung, prediction interval) | `ma_pairwise`, `ma_summary_row` |
| 03 | `R/03_heterogeneity.R` | subgroup analysis + meta-regression (bubble plot) | `ma_subgroup`, `ma_metareg` |
| 04 | `R/04_publication_bias.R` | Egger, Begg, trim-and-fill, PET-PEESE; contour-enhanced funnel | `ma_pubbias`, `ma_funnel` |
| 05 | `R/05_influence.R` | leave-one-out, influence diagnostics, Baujat, cumulative, GOSH | `ma_influence` |
| 06 | `R/06_forest.R` | publication forest plot + drapery (p-value function) | `ma_forest`, `ma_drapery` |
| 07 | `R/07_grade.R` | GRADE certainty + Summary-of-Findings table | `ma_grade`, `ma_grade_suggest`, `ma_sof_table` |
| 08 | `R/08_prisma.R` | PRISMA 2020 study-flow diagram (base R, no extra deps) | `prisma_flow` |
| 09 | `R/09_rob.R` | risk-of-bias traffic-light & weighted summary (robvis) | `rob_traffic`, `rob_summary` |
| 10 | `R/10_proportion_meta.R` | single-arm proportion / mean / incidence-rate meta-analysis | `ma_proportion`, `ma_mean`, `ma_rate` |
| 20 | `R/20_network_meta.R` | network meta-analysis: graph, league table, P-score ranking, node-splitting | `nma_run`, `nma_graph`, `nma_league`, `nma_rank`, `nma_inconsistency` |
| 21 | `R/21_diagnostic_meta.R` | diagnostic test accuracy: bivariate/HSROC, SROC curve, pooled Sn/Sp/DOR | `dta_run` |
| 22 | `R/22_bayesian_meta.R` | Bayesian random-effects (bayesmeta): credible + prediction intervals, shrinkage | `bma_run` |

Run everything on the bundled example data:

```r
source("examples/run_all_examples.R")   # writes figures/ and tables/
```

## Documentation

- [`docs/TOP_JOURNAL_STANDARDS.md`](docs/TOP_JOURNAL_STANDARDS.md) — PRISMA/Cochrane/GRADE/MOOSE item → module map
- [`docs/EFFECT_SIZE_GUIDE.md`](docs/EFFECT_SIZE_GUIDE.md) — which effect measure to use
- [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) — the shared contract for contributors
- [`docs/REFERENCES.md`](docs/REFERENCES.md) — the method citations behind each module

## Citing

This toolkit orchestrates other people's packages. If you use it, cite the packages and
methods you actually relied on (see `docs/REFERENCES.md` and `CITATION.cff`), not just this repo.

## License

MIT — see [`LICENSE`](LICENSE).
