## =====================================================================
## run_all_examples.R  —  end-to-end demo / smoke test of the toolkit
## Sources every module and runs each on real bundled data, writing the
## example figures (figures/) and tables (tables/) shipped with the repo.
## Run from the repo root:
##   & "C:/Program Files/R/R-4.4.3/bin/Rscript.exe" examples/run_all_examples.R
## =====================================================================
root <- tryCatch(dirname(dirname(normalizePath(sub("--file=", "",
          grep("--file=", commandArgs(FALSE), value = TRUE)[1])))),
        error = function(e) getwd())
if (!dir.exists(file.path(root, "R"))) root <- getwd()
setwd(root)
options(warn = 1)
suppressMessages({library(metafor); library(meta); library(netmeta)
  library(metadat); library(mada); library(bayesmeta); library(robvis)})
for (f in sort(list.files("R", pattern = "\\.R$", full.names = TRUE))) source(f)
dir.create("figures", showWarnings = FALSE); dir.create("tables", showWarnings = FALSE)
say <- function(...) cat(sprintf(...), "\n")
opt <- function(label, expr) tryCatch({expr; say("  [ok] %s", label)},
                                      error = function(e) say("  [skip] %s: %s", label, conditionMessage(e)))

## ---- data ----
data(dat.bcg, package = "metadat"); data(dat.normand1999, package = "metadat")
data(dat.molloy2014, package = "metadat"); data(dat.pritz1997, package = "metadat")

## ============ 01-02  effect sizes + pairwise pooling ============
say("[01-02] effect sizes + pairwise pooling")
fit_or  <- ma_pairwise(dat.bcg, "OR", ai = tpos, bi = tneg, ci = cpos, di = cneg, slab = ~paste(author, year))
fit_smd <- ma_pairwise(dat.normand1999, "SMD", m1i = m1i, sd1i = sd1i, n1i = n1i,
                       m2i = m2i, sd2i = sd2i, n2i = n2i, slab = ~source)
fit_z   <- ma_pairwise(dat.molloy2014, "ZCOR", ri = ri, ni = ni, slab = ~paste(authors, year))
print(fit_or)
write.csv(rbind(ma_summary_row(fit_or, "BCG (OR)"), ma_summary_row(fit_smd, "Normand (SMD)"),
                ma_summary_row(fit_z, "Molloy (r)")),
          "tables/02_pooled_summary.csv", row.names = FALSE)

## ============ 03  heterogeneity ============
say("[03] subgroup + meta-regression")
ma_subgroup(fit_or, "alloc")
ma_metareg(fit_or, ~ablat, out = "figures/03_metareg_bcg_ablat.pdf")

## ============ 04  publication bias ============
say("[04] publication bias")
ma_pubbias(fit_or)
ma_funnel(fit_or, "figures/04_funnel_bcg.pdf")

## ============ 05  influence ============
say("[05] influence / robustness")
ma_influence(fit_or, out_prefix = "figures/05_bcg")

## ============ 06  forest + drapery ============
say("[06] forest + drapery")
ma_forest(fit_or, "figures/06_forest_bcg.pdf")
ma_forest(fit_smd, "figures/06_forest_normand.pdf")
ma_drapery(fit_or, "figures/06_drapery_bcg.pdf")

## ============ 07  GRADE ============
say("[07] GRADE certainty + Summary of Findings")
g1 <- ma_grade("BCG vs TB (efficacy)", "rct", rob = -1, inconsistency = -1)
g2 <- ma_grade("Adverse events", "observational", rob = -1, large_effect = 1)
ma_sof_table(list(g1, g2), out = "tables/07_sof_example.csv")
invisible(ma_grade_suggest(fit_or))

## ============ 08  PRISMA 2020 flow ============
say("[08] PRISMA 2020 flow diagram")
counts <- list(n_identified = c(PubMed = 520, Embase = 610, WoS = 430), n_duplicates = 380,
  n_screened = 1180, n_excluded_screen = 980, n_fulltext_sought = 200, n_fulltext_notretrieved = 12,
  n_fulltext_assessed = 188,
  n_fulltext_excluded = c("Wrong population" = 60, "No usable data" = 48, "Duplicate cohort" = 15),
  n_included_studies = 65, n_included_reports = 68)
prisma_flow(counts, "figures/08_prisma_example.pdf")

## ============ 09  risk of bias (robvis) ============
say("[09] risk-of-bias figures")
data(data_rob2, package = "robvis"); data(data_robins, package = "robvis")
rob_traffic(data_rob2, "ROB2", "figures/09_rob2_traffic.pdf")
rob_summary(data_rob2, "ROB2", "figures/09_rob2_summary.pdf")
rob_traffic(data_robins, "ROBINS-I", "figures/09_robins_traffic.pdf")

## ============ 10  single-arm (proportion / mean / rate) ============
say("[10] single-arm meta-analysis")
ma_proportion(dat.pritz1997, event = xi, n = ni, studlab = study, method = "PFT",
              out = "figures/10_prop_forest.pdf")
opt("ma_mean (Normand tx arm)",
    ma_mean(dat.normand1999, n = n1i, mean = m1i, sd = sd1i, studlab = source,
            out = "figures/10_mean_forest.pdf"))

## ============ 20  network meta-analysis ============
say("[20] network meta-analysis")
data(Senn2013, package = "netmeta")
net <- nma_run(Senn2013, format = "contrast", sm = "MD", reference = "plac")
nma_graph(net, "figures/20_netgraph_senn.pdf")
nma_rank(net, small.values = "desirable", out = "figures/20_rankogram_senn.pdf")
nma_league(net, out = "tables/20_league_senn.csv")
nma_inconsistency(net, out = "figures/20_netsplit_senn.pdf")
opt("arm-format NMA (Dong2013)", {
  data(Dong2013, package = "netmeta")
  net2 <- nma_run(Dong2013, format = "arm", sm = "OR", allstudies = TRUE,
                  treat = "treatment", event = "death", n = "randomized", studlab = "id")
  nma_graph(net2, "figures/20_netgraph_dong.pdf")
})

## ============ 21  diagnostic test accuracy ============
say("[21] diagnostic test accuracy")
data(AuditC, package = "mada")
dta_run(AuditC, out_prefix = "figures/21_auditc")

## ============ 22  Bayesian meta-analysis ============
say("[22] Bayesian random-effects")
es_bcg <- escalc("OR", ai = tpos, bi = tneg, ci = cpos, di = cneg, data = dat.bcg)
bma_run(es_bcg$yi, sqrt(es_bcg$vi), labels = paste(dat.bcg$author, dat.bcg$year),
        out_prefix = "figures/22_bcg")

say("\n[run_all_examples DONE]  figures: %d  tables: %d",
    length(list.files("figures", pattern = "\\.pdf$")),
    length(list.files("tables", pattern = "\\.csv$")))
