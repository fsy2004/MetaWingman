# Method references

Every method in this toolkit is a published, peer-reviewed estimator. Citations
are given at author–year–journal granularity; for exact bibliographic detail see
each R package's own `citation("<pkg>")`. Cite the methods you actually use.

## Software / general
- Viechtbauer W (2010). *Conducting meta-analyses in R with the metafor package.* Journal of Statistical Software 36(3).
- Balduzzi S, Rücker G, Schwarzer G (2019). *How to perform a meta-analysis with R: a practical tutorial.* Evidence-Based Mental Health 22.
- Borenstein M, Hedges LV, Higgins JPT, Rothstein HR (2009). *Introduction to Meta-Analysis.* Wiley.
- Hedges LV, Olkin I (1985). *Statistical Methods for Meta-Analysis.* Academic Press.

## Pooling model, heterogeneity & prediction interval
- DerSimonian R, Laird N (1986). *Meta-analysis in clinical trials.* Controlled Clinical Trials 7.
- Viechtbauer W (2005). *Bias and efficiency of meta-analytic variance estimators in the random-effects model.* Journal of Educational and Behavioral Statistics 30.
- Knapp G, Hartung J (2003). *Improved tests for a random effects meta-regression with a single covariate.* Statistics in Medicine 22.
- IntHout J, Ioannidis JPA, Borm GF (2014). *The Hartung-Knapp-Sidik-Jonkman method... outperforms DerSimonian-Laird.* BMC Medical Research Methodology 14.
- Higgins JPT, Thompson SG, Spiegelhalter DJ (2009). *A re-evaluation of random-effects meta-analysis.* Journal of the Royal Statistical Society A 172.
- Riley RD, Higgins JPT, Deeks JJ (2011). *Interpretation of random effects meta-analyses.* BMJ 342.
- Higgins JPT, Thompson SG (2002). *Quantifying heterogeneity in a meta-analysis.* Statistics in Medicine 21.

## Subgroup / meta-regression
- Thompson SG, Higgins JPT (2002). *How should meta-regression analyses be undertaken and interpreted?* Statistics in Medicine 21.

## Publication / small-study bias
- Egger M, Davey Smith G, Schneider M, Minder C (1997). *Bias in meta-analysis detected by a simple, graphical test.* BMJ 315.
- Begg CB, Mazumdar M (1994). *Operating characteristics of a rank correlation test for publication bias.* Biometrics 50.
- Duval S, Tweedie R (2000). *Trim and fill... method of testing and adjusting for publication bias.* Biometrics 56.
- Sterne JAC, et al. (2011). *Recommendations for examining and interpreting funnel plot asymmetry.* BMJ 343.
- Stanley TD, Doucouliagos H (2014). *Meta-regression approximations to reduce publication selection bias (PET-PEESE).* Research Synthesis Methods 5.
- Baujat B, Mahé C, Pignon JP, Hill C (2002). *A graphical method for exploring heterogeneity in meta-analyses.* Statistics in Medicine 21.

## Data preparation (median/IQR → mean/SD; effect-size conversion)
- Wan X, Wang W, Liu J, Tong T (2014). *Estimating the sample mean and standard deviation from the sample size, median, range and/or interquartile range.* BMC Medical Research Methodology 14.
- Luo D, Wan X, Liu J, Tong T (2018). *Optimally estimating the sample mean from the sample size, median, mid-range, and/or mid-quartile range.* Statistical Methods in Medical Research 27.
- Shi J, Luo D, Weng H, et al. (2020). *Optimally estimating the sample standard deviation from the five-number summary.* Research Synthesis Methods 11.
- McGrath S, Zhao X, Steele R, et al. (2020). *Estimating the sample mean and standard deviation from commonly reported quantiles in meta-analysis.* Statistical Methods in Medical Research 29. (`estmeansd`)
- Chinn S (2000). *A simple method for converting an odds ratio to effect size for use in meta-analysis.* Statistics in Medicine 19.

## Proportions / rates (single-arm)
- Freeman MF, Tukey JW (1950). *Transformations related to the angular and the square root.* Annals of Mathematical Statistics 21.
- Barendregt JJ, Doi SA, Lee YY, Norman RE, Vos T (2013). *Meta-analysis of prevalence.* Journal of Epidemiology and Community Health 67.
- Schwarzer G, Chemaitelly H, Abu-Raddad LJ, Rücker G (2019). *Seriously misleading results using inverse of Freeman-Tukey double arcsine transformation...* Research Synthesis Methods 10.

## Network meta-analysis
- Rücker G (2012). *Network meta-analysis, electrical networks and graph theory.* Research Synthesis Methods 3.
- Rücker G, Schwarzer G (2015). *Ranking treatments in frequentist network meta-analysis works without resampling methods (P-score).* BMC Medical Research Methodology 15.
- Balduzzi S, Rücker G, Nikolakopoulou A, et al. (2023). *netmeta: An R package for network meta-analysis using frequentist methods.* Journal of Statistical Software 106.
- Dias S, Welton NJ, Caldwell DM, Ades AE (2010). *Checking consistency in mixed treatment comparison meta-analysis (node-splitting).* Statistics in Medicine 29.

## Diagnostic test accuracy
- Reitsma JB, Glas AS, Rutjes AWS, et al. (2005). *Bivariate analysis of sensitivity and specificity produces informative summary measures.* Journal of Clinical Epidemiology 58.
- Rutter CM, Gatsonis CA (2001). *A hierarchical regression approach to meta-analysis of diagnostic test accuracy (HSROC).* Statistics in Medicine 20.
- Harbord RM, Deeks JJ, Egger M, Whiting P, Sterne JAC (2007). *A unification of models for meta-analysis of diagnostic accuracy studies.* Biostatistics 8.
- Doebler P, Holling H. *Meta-analysis of diagnostic accuracy with mada.* (`mada` package vignette.)

## Bayesian meta-analysis
- Röver C (2020). *Bayesian random-effects meta-analysis using the bayesmeta R package.* Journal of Statistical Software 93(6).
- Röver C, Bender R, Dias S, et al. (2021). *On weakly informative prior distributions for the heterogeneity parameter in Bayesian random-effects meta-analysis.* Research Synthesis Methods 12.

## Reporting & certainty frameworks
- Page MJ, McKenzie JE, Bossuyt PM, et al. (2021). *The PRISMA 2020 statement: an updated guideline for reporting systematic reviews.* BMJ 372:n71.
- Stroup DF, et al. (2000). *Meta-analysis of observational studies in epidemiology (MOOSE).* JAMA 283.
- Balshem H, Helfand M, Schünemann HJ, et al. (2011). *GRADE guidelines: 3. Rating the quality of evidence.* Journal of Clinical Epidemiology 64. (and the GRADE J Clin Epidemiol series, Guyatt et al. 2011)
- Sterne JAC, et al. (2019). *RoB 2: a revised tool for assessing risk of bias in randomised trials.* BMJ 366:l4898.
- Sterne JAC, et al. (2016). *ROBINS-I: a tool for assessing risk of bias in non-randomised studies of interventions.* BMJ 355:i4919.
- McGuinness LA, Higgins JPT (2021). *risk-of-bias VISualization (robvis): an R package and Shiny web app...* Research Synthesis Methods 12.
