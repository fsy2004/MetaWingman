# Quantitative and structured synthesis

## Contents

1. Estimand first
2. Pairwise synthesis
3. Special models
4. Heterogeneity and robustness
5. Reporting

## Estimand first

Define population, treatment/exposure/test contrast, outcome, timepoint, analysis population, effect measure, and handling of intercurrent events. Pool only results that estimate a scientifically coherent target.

## Pairwise synthesis

- Binary: RR is often interpretable; OR is suitable for logistic/case-control contexts; RD conveys absolute contrast but is baseline-risk sensitive. Handle rare events based on zero structure and model assumptions.
- Continuous: MD for the same scale; SMD for compatible constructs on different scales, with direction harmonized and interpretation supplied.
- Time-to-event: log HR with SE; do not substitute odds or risk ratios for hazards.
- Correlation: Fisher z transform and back-transform.
- Proportion/incidence: use appropriate binomial/GLMM or transformation methods; avoid automatic double-arcsine use.

Random-effects models generally need a defensible tau-squared estimator, uncertainty method, and prediction interval. REML plus Hartung-Knapp is a strong default in many pairwise settings, not a universal rule. Common-effect estimates are sensitivity analyses when effect homogeneity is implausible.

## Special models

- DTA: bivariate random-effects or HSROC; model threshold structure and reference standard.
- NMA: connected network, transitivity variables, design-by-treatment/global inconsistency and local checks, coherent multi-arm covariance, and cautious ranking.
- Dose-response: reconstruct dose-specific covariance; test nonlinearity with prespecified knots or functions.
- Multiple dependent effects: multilevel/multivariate models or RVE with adequate clusters and small-sample correction.
- IPD: one-stage hierarchical or two-stage synthesis; preserve participant clustering and harmonization decisions.
- Bayesian: justify likelihood, priors for effect and heterogeneity, convergence, posterior predictive checks, and prior sensitivity.
- Prediction-model performance: separate discrimination, calibration, and clinical utility; transform compatible metrics and model between-study heterogeneity.

## Heterogeneity and robustness

Report tau-squared, I-squared with uncertainty where available, Q, and prediction interval where meaningful. Investigate clinical and methodological heterogeneity before statistical moderators.

Subgroups and meta-regression require prespecification, interaction tests, adequate studies, and ecological caution. Do not compare significance within subgroups. Sensitivity analyses should target assumptions: bias, effect measure, estimator, dependency, imputation, influence, eligibility ambiguity, follow-up, and reporting availability.

Small-study methods, trim-and-fill, selection models, PET-PEESE, p-curve, E-values, GOSH, TSA, and cumulative meta-analysis are assumption-sensitive. Label them accordingly and avoid using them as binary proof of robustness.

## Reporting

For each synthesis report included studies/results, effect measure and direction, model and estimator, CI/CrI, prediction interval, heterogeneity, dependency handling, software/package versions, prespecified vs exploratory status, sensitivity results, RoB influence, certainty, and interpretation in absolute terms where possible.

If effect estimates are not meaningfully combinable, follow SWiM: group studies, describe standardized metrics or vote-count limitations, specify synthesis method, prioritize studies transparently, investigate heterogeneity, and communicate certainty without forced pooling.
