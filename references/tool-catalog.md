# Bundled analysis tool catalog

Generated from live bundled source. Functions are wrappers around cited R packages; availability still depends on installed packages and compatible input data.

## Toolkit modules

| File | Exported functions |
|---|---|
| `scripts/r/toolkit/R/00_data_prep.R` | `dp_wan2014`, `dp_median_to_mean_sd`, `dp_se_to_sd`, `dp_ci_to_sd`, `dp_iqr_to_sd`, `dp_d_to_g`, `dp_lnOR_to_SMD`, `dp_SMD_to_lnOR`, `dp_r_to_SMD`, `dp_SMD_to_r`, `dp_r_to_z`, `dp_z_to_r` |
| `scripts/r/toolkit/R/00_device.R` | `mw_pdf` |
| `scripts/r/toolkit/R/00a_theme_nature.R` | `mm2in`, `nature_width_in`, `nature_register_fonts`, `nature_pdf`, `nature_png`, `nature_base`, `theme_nature`, `nature_pal`, `scale_colour_nature`, `scale_fill_nature`, `nature_ggsave` |
| `scripts/r/toolkit/R/01_effect_sizes.R` | `es_guide`, `es_calc` |
| `scripts/r/toolkit/R/02_pairwise_meta.R` | `ma_pairwise`, `ma_summary_row`, `print.ma_fit` |
| `scripts/r/toolkit/R/03_heterogeneity.R` | `ma_subgroup`, `ma_metareg` |
| `scripts/r/toolkit/R/04_publication_bias.R` | `ma_pubbias`, `print.ma_pubbias`, `ma_funnel` |
| `scripts/r/toolkit/R/05_influence.R` | `ma_influence` |
| `scripts/r/toolkit/R/06_forest.R` | `ma_forest`, `ma_drapery` |
| `scripts/r/toolkit/R/07_grade.R` | `ma_grade`, `ma_grade_suggest`, `ma_sof_table` |
| `scripts/r/toolkit/R/08_prisma.R` | `prisma_flow` |
| `scripts/r/toolkit/R/09_rob.R` | `rob_traffic`, `rob_summary` |
| `scripts/r/toolkit/R/10_proportion_meta.R` | `ma_proportion`, `ma_mean`, `ma_rate` |
| `scripts/r/toolkit/R/20_network_meta.R` | `nma_run`, `nma_graph`, `nma_rank`, `nma_league`, `nma_inconsistency` |
| `scripts/r/toolkit/R/21_diagnostic_meta.R` | `dta_run` |
| `scripts/r/toolkit/R/22_bayesian_meta.R` | `bma_from_fit`, `bma_run` |
| `scripts/r/toolkit/R/30_bayesian_split.R` | `bma_forest_fig`, `bma_posterior_fig` |
| `scripts/r/toolkit/R/30_complex.R` | `mw_complex_ml3`, `mw_complex_rve`, `mw_complex_dose` |
| `scripts/r/toolkit/R/30_diagnostic_split.R` | `dta_build`, `dta_fig_sroc`, `dta_fig_paired`, `dta_lr_dor`, `hsroc_coef_from_reitsma`, `dta_hsroc` |
| `scripts/r/toolkit/R/30_evalue.R` | `mw_evalue_one`, `mw_evalue_table`, `mw_evalue_plot` |
| `scripts/r/toolkit/R/30_heterogeneity_extra.R` | `het_stats_table`, `het_subgroup_forest`, `het_pred_forest`, `het_permute` |
| `scripts/r/toolkit/R/30_influence.R` | `ma_loo_forest`, `ma_baujat_plot`, `ma_cumulative_forest`, `ma_gosh_plot`, `ma_influence_diagnostics` |
| `scripts/r/toolkit/R/30_network_extra.R` | `nma_forest_ref`, `nma_rankogram_plot`, `nma_netheat`, `nma_cadj_funnel`, `nma_component`, `nma_contrib` |
| `scripts/r/toolkit/R/30_pairwise_family.R` | `pw_gen_forest`, `pw_corr`, `pw_metabin`, `pw_metabin_forest`, `pw_meta_summary`, `pw_hr`, `pw_labbe`, `pw_radial` |
| `scripts/r/toolkit/R/30_proportion_ext.R` | `ma_proportion_glmm` |
| `scripts/r/toolkit/R/30_sequential.R` | `seq_fit`, `seq_tsa_plot`, `seq_bounds_df`, `seq_ris_df`, `seq_ris_plot` |

Bundled public-function count: **97**.

## Executable adapter families

| Adapter | Purpose |
|---|---|
| `scripts/r/adapters/run_bayesian.R` | Bayesian random-effects summaries and posterior displays |
| `scripts/r/adapters/run_complex.R` | multilevel, robust variance and dose-response models |
| `scripts/r/adapters/run_convert.R` | effect and uncertainty conversions |
| `scripts/r/adapters/run_dataprep_msd.R` | median/range/IQR to mean and SD |
| `scripts/r/adapters/run_diagnostic.R` | DTA bivariate/HSROC, SROC, sensitivity/specificity, LR and DOR |
| `scripts/r/adapters/run_evalue.R` | E-value sensitivity analysis |
| `scripts/r/adapters/run_grade.R` | GRADE/SoF helpers |
| `scripts/r/adapters/run_heterogeneity.R` | heterogeneity, subgroup, meta-regression, permutation and prediction |
| `scripts/r/adapters/run_influence.R` | leave-one-out, Baujat, cumulative, GOSH and diagnostics |
| `scripts/r/adapters/run_network.R` | network models, graph, rank, league, inconsistency and component analyses |
| `scripts/r/adapters/run_pairwise.R` | pairwise effects, binary/continuous/correlation/survival plots and summaries |
| `scripts/r/adapters/run_prisma.R` | PRISMA flow diagram |
| `scripts/r/adapters/run_proportion.R` | proportion, mean and incidence-rate synthesis |
| `scripts/r/adapters/run_rob.R` | risk-of-bias visualizations |
| `scripts/r/adapters/run_sequential.R` | trial sequential analysis and required information size |

## Manifests

Bundled manifest count: **61**. Some legacy manifest text may contain encoding damage; treat executable R source and validated input/output behavior as authority.

## Method boundary

The catalog is not a recommendation to run every method. Select only analyses justified by the protocol, estimand, design, dependency structure, information size, and current methodological guidance. Record package citations from `scripts/r/toolkit/docs/REFERENCES.md`.
