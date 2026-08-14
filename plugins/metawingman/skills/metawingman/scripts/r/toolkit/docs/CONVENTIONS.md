# Toolkit conventions (shared contract)

Every module in `R/` follows these rules so the scripts compose into one
coherent toolkit. Read this before adding or editing a module.

## 0. Non-negotiables

- **Real APIs only.** Every function wraps a real, installed package
  (`metafor`, `meta`, `netmeta`, `mada`, `bayesmeta`, `robvis`, `metasens`,
  `estmeansd`, `metadat`). Never invent arguments or functions — if unsure of a
  signature, check `?fn` / the package source. No placeholder / stub code.
- **Cite the method.** Each script starts with a header comment naming the
  statistical method and its primary reference (e.g. Knapp-Hartung 2003,
  Rücker 2012 for NMA, Reitsma 2005 for DTA).
- **No plain bar charts.** Top journals rarely use them. Use forest, funnel,
  lollipop/dot, dumbbell, SROC, network graphs, rankograms, violin/raincloud.
  (If a magnitude-by-category display is unavoidable, use a lollipop.)
- **Test on real bundled data** (see §4), never on fabricated numbers.
- **Run R via PowerShell on this machine**, never Git Bash — the Bash↔Rscript
  bridge segfaults here. Invocation:
  `& "C:/Program Files/R/R-4.4.3/bin/Rscript.exe" script.R`
- Scripts are **self-contained**: `source()` the foundation files they need,
  load their own libraries, write figures to `figures/`, tables to `tables/`.

## 1. Foundation contract (R/00–02, already built & tested)

Source order: `00_data_prep.R` → `01_effect_sizes.R` → `02_pairwise_meta.R`.

- `es_calc(measure, data, slab = NULL, ...)` → an `escalc` data.frame with
  `yi`, `vi`, **all original columns preserved** (so moderators survive).
  `measure` ∈ {MD, SMD, SMDH, ROM, OR, RR, RD, PETO, ZCOR, COR, PLO, PFT, PR,
  IRLN, IRFT, MN, GEN}. `GEN` = pre-computed `yi` + (`vi` or `sei`), e.g. log-HR.
  Column args are NSE, resolved inside `data` (`ai = tpos` works). `slab` is a
  formula (`~paste(author, year)`) or a vector.
- `ma_pairwise(data, measure = NULL, slab = NULL, method = "REML",
  knha = TRUE, level = 95, ...)` → object of class **`ma_fit`** with fields:
  `$re` (random-effects `rma`), `$fe` (common-effect `rma`), `$es` (escalc df),
  `$measure`, `$transf` (back-transform fn or NULL), `$pred` (`predict` w/ PI),
  `$level`. Accepts an escalc df, or raw data + `measure` + columns.
- `ma_summary_row(fit, label)` → tidy one-row data.frame (k, est, ci, pi, I2,
  tau2, H2, Q, p) on the **natural scale**.
- Helpers available after sourcing: `%||%`, `.ma_transf(measure)`.

New modules that extend pairwise analysis should **accept an `ma_fit` or a raw
`rma`** and reuse `$re` / `$es`, not re-fit from scratch.

## 2. Naming

| Prefix | Domain |
|--------|--------|
| `es_`     | effect-size calculation / conversion |
| `dp_`     | data preparation |
| `ma_`     | pairwise meta-analysis (pool, heterogeneity, bias, influence, forest) |
| `prisma_` | PRISMA 2020 flow diagram |
| `rob_*` (via robvis) | risk-of-bias figures |
| `nma_`    | network meta-analysis |
| `dta_`    | diagnostic test accuracy |
| `bma_`    | Bayesian meta-analysis |

Figure functions take an `out = "figures/<name>.pdf"` argument (PDF, vector) and
return the fitted/derived object invisibly. Namespace figure filenames by module.

## 3. Installed packages (verified present)

`metafor` 5.0.1 · `meta` 8.5.0 · `netmeta` 3.5.0 · `metadat` 1.4.0 ·
`mada` 0.5.12 · `bayesmeta` 3.5 · `robvis` 0.3.1 · `metasens` 1.5-3 ·
`estmeansd` · `metaBLUE` · `mvmeta`/`mixmeta` (mada deps).

## 4. Verified test datasets & recipes (all real, bundled)

| Use | Dataset (pkg) | Recipe |
|-----|---------------|--------|
| SMD continuous | `dat.normand1999` (metadat) | `escalc("SMD", m1i,sd1i,n1i, m2i,sd2i,n2i)` |
| OR/RR/RD binary + moderators | `dat.bcg` (metadat) | `ai=tpos,bi=tneg,ci=cpos,di=cneg`; moderators `ablat`, `year`, `alloc` |
| Correlation | `dat.molloy2014` (metadat) | `ri, ni` |
| Proportion (1-arm) | `dat.pritz1997` (metadat) | `xi, ni` |
| Meta-regression | `dat.bcg` (`ablat`,`year`) or `dat.bangertdrowns2004` | — |
| NMA contrast-format | `Senn2013` (netmeta) | `TE, seTE, treat1, treat2, studlab`, `sm="MD"` |
| NMA arm-format binary | `Dong2013` / `Gurusamy2011` / `smokingcessation` (netmeta) | via `netmeta::pairwise()` |
| NMA continuous arm | `Franchini2012` (netmeta) | `y,sd,n` per arm |
| DTA (2×2 diagnostic) | `AuditC` (mada; TP,FN,FP,TN) or `SAQ`/`smoking` (labelled) | `reitsma()`, `madad()` |
| Bayesian | `CrinsEtAl2014` (bayesmeta) or `es$yi`,`sqrt(es$vi)` from `dat.bcg` | `bayesmeta(y, sigma, tau.prior=)` |
| Risk of bias | `data_rob2` (D1–D5), `data_robins` (D1–D7), `data_rob1` (robvis) | `rob_summary()`, `rob_traffic_light()` |

Load a dataset with e.g. `data(dat.bcg, package="metadat")`.
Do **not** use `data(package=...)` with no `list=` and no dataset — it segfaults
on this R build. Always `data(<name>, package="<pkg>")`.
