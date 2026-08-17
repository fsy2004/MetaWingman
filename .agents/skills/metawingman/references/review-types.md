# Review and synthesis profiles

## Contents

1. Selection rule
2. Biomedical domain routing
3. Core profiles
4. Statistical extensions
5. Invalid substitutions

## Selection rule

Choose the profile from the decision question, evidence unit, design, and target estimand. A reporting extension does not define the statistical model, and an available R function does not justify a review type.

## Biomedical domain routing

Resolve the typed biomedical context before selecting a profile. The foundation pack governs shared clinical terminology and evidence-integrity boundaries; a profile pack constrains the question and method family; specialty packs add domain concepts and ambiguity checks. These packs are semantic controls, not alternative methodology authorities.

An unresolved or out-of-domain concept must stay explicit. Low-risk reversible work may use the foundation fallback, but ambiguity affecting eligibility, safety, diagnosis, prognosis, effect direction, or conclusions requires abstention. No specialty label permits changing frozen eligibility, substituting an appraisal tool, forcing pooling, or bypassing an accountable decision.

| Profile | Question frame / unit | Preferred appraisal | Reporting / core synthesis |
|---|---|---|---|
| Intervention effectiveness | PICO(S); randomized or non-randomized comparisons | RoB 2 by result; ROBINS-I by result for NRSI | PRISMA 2020; pairwise meta-analysis or SWiM |
| Network meta-analysis | connected competing interventions plus transitivity variables | primary-study RoB; ROB-MEN for missing evidence; RoB NMA for an existing NMA; CINeMA/GRADE for network certainty | PRISMA-NMA plus current update status; consistency and transitivity assessment |
| Diagnostic test accuracy | participants, index test, target condition, reference standard | QUADAS-3 current release; use QUADAS-2 only when protocol/version requires | PRISMA-DTA; bivariate/HSROC, not separate univariate pooling alone |
| Prognostic factor | population, index factor, outcome, timing, adjustment set | QUIPS or justified current instrument | adjusted association synthesis; separate crude and adjusted estimates |
| Prediction model | population, outcome, model, intended use, validation type | PROBAST+AI/current PROBAST family | CHARMS-style extraction; pool performance only with compatible definitions |
| Etiology/risk/exposure | PECO; target causal contrast | ROBINS-E or design-specific JBI tool | MOOSE plus PRISMA; adjusted estimates and confounding structure |
| Prevalence/incidence | condition, population, context, measurement, time | JBI prevalence tool or appropriate equivalent | proportion/rate models with design and denominator scrutiny |
| Harms/adverse effects | intervention/exposure, attribution, event definition, window | design-appropriate RoB plus harms-specific domains | PRISMA-Harms; do not substitute TEAE for TRAE or mix grades/windows |
| Dose-response | exposure/intervention doses and comparable reference | design-appropriate RoB | one/two-stage dose-response; nonlinearity and within-study covariance |
| Individual participant data | participant-level data from eligible studies | design-appropriate RoB plus availability/data-integrity bias | PRISMA-IPD; one-stage or two-stage with clustering handled |
| Outcome measurement instruments | construct, population, instrument, measurement property | COSMIN methodology | PRISMA-COSMIN for OMIs; property-specific synthesis |
| Scoping review | PCC: population, concept, context | appraisal optional and justified | PRISMA-ScR; mapping, not an effectiveness conclusion |
| Qualitative evidence synthesis | phenomenon, context, perspective | JBI/CASP or method-matched appraisal | thematic, framework, meta-aggregation, or meta-ethnographic synthesis |
| Mixed-methods review | linked quantitative and qualitative questions | design-specific tools | convergent or sequential integration with explicit transformation |
| Economic evidence review | population, alternatives, perspective, costs/outcomes, horizon | economic evaluation appraisal | JBI/Cochrane economic guidance; usually structured synthesis, careful currency/year conversion |
| Umbrella review / overview | systematic reviews as included units | ROBIS for bias; AMSTAR 2 or profile-specific AMSTAR-PF where applicable | overlap matrix, corrected covered area, no double-counting of primary studies |
| Rapid review | decision-bound accelerated review | same design-matched RoB, with declared shortcuts | record every shortcut and likely bias; never label an incomplete search comprehensive |
| Living systematic review | continuously monitored eligible evidence | same profile-specific tools | PRISMA-LSR add-on; surveillance and retirement rules |
| Prospective/cumulative review | studies incorporated prospectively or sequentially | profile-specific | prospective protocol; cumulative meta-analysis/TSA only with justified assumptions |

## Statistical extensions

Apply only when the data structure requires them:

- multilevel meta-analysis for nested effects;
- robust variance estimation for dependent effect sizes with adequate clusters and small-sample correction;
- multivariate meta-analysis for correlated outcomes;
- Bayesian hierarchical meta-analysis with justified priors and sensitivity analyses;
- component NMA for decomposable interventions and defensible additivity assumptions;
- meta-regression for prespecified study-level moderators with enough information and ecological-bias caution;
- rare-event methods selected from event balance and zero-cell structure;
- external-bias adjustment, E-values, selection models, p-curve, or PET-PEESE only as explicit sensitivity frameworks;
- trial sequential analysis only when the information-size model and error-spending assumptions are defensible.

## Invalid substitutions

- Do not call a scoping review a systematic review of effects.
- Do not pool sensitivity and specificity independently when a joint DTA model is required.
- Do not mix hazard ratios, odds ratios, risk ratios, and risk differences without an explicit valid transformation and compatible estimand.
- Do not combine adjusted and unadjusted observational estimates in one primary synthesis.
- Do not treat multiple reports as independent studies or multiple outcomes/timepoints as independent effects.
- Do not apply AMSTAR 2 to primary studies or use a reporting checklist as a bias instrument.
- Do not use a quality score as an inverse-variance weight.
