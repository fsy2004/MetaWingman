# Choosing an effect measure

Pick the measure from the outcome type and the data you can extract, then feed it
to `es_calc()` / `ma_pairwise()`. `es_guide()` prints this table inside R.

| Outcome type | Data you have | Measure | Notes |
|--------------|---------------|---------|-------|
| Continuous, same scale across studies | mean, SD, n per group | **MD** | raw mean difference; only when the scale is identical & interpretable |
| Continuous, different scales/instruments | mean, SD, n per group | **SMD** (Hedges' g) | default for continuous; bias-corrected. Use `SMDH` for unequal variances |
| Continuous, ratio-natural (e.g. biomarker level) | mean, SD, n per group | **ROM** | log response ratio |
| Binary event | 2×2 counts (events/non-events per arm) | **OR** / **RR** / **RD** | OR/RR pooled on the log scale; RR is more interpretable for risks, OR for case-control. `PETO` for very rare events |
| Correlation | r, n | **ZCOR** | Fisher's z for pooling (variance-stabilised), back-transformed to r for display |
| Single-arm proportion / prevalence | events x, total n | **PFT** or **PLOGIT** | logit is usually preferable; Freeman-Tukey (`PFT`) stabilises near 0/1 but see Schwarzer 2019 caveat |
| Single-arm incidence rate | events, person-time | **IRLN** / **IRFT** | log or Freeman-Tukey rate |
| Single-group mean | mean, SD, n | **MN** | pooled mean |
| Time-to-event / already-computed | log-HR + SE (or any yi + vi/sei) | **GEN** | generic inverse-variance; also use for effects reconstructed from CIs |

## When the paper reports the "wrong" summary

Use `R/00_data_prep.R` first, then the table above:

- **median + IQR / range** → `dp_median_to_mean_sd(median, n, q1=, q3=, ...)` (Wan 2014;
  or `method="qe"/"bc"` for the Cochrane-recommended `estmeansd` estimators on skewed data),
  then treat as mean+SD.
- **SE instead of SD** → `dp_se_to_sd(se, n)`.
- **95% CI of a mean** → `dp_ci_to_sd(lower, upper, n)`.
- **only an OR / r but you need SMD** (or vice-versa) → `dp_lnOR_to_SMD()`, `dp_r_to_SMD()`,
  `dp_SMD_to_r()`, `dp_d_to_g()`.

## Fixed vs random effects

`ma_pairwise()` fits a **random-effects** model (REML + Knapp-Hartung) as the primary
result — appropriate when studies differ in population/design, which is almost always —
and reports a **common-effect** model alongside for comparison only. Report the random-effects
estimate **with its prediction interval**, not just the CI: the CI is the uncertainty of the
mean effect, the prediction interval is where a new study's true effect is expected to lie.
