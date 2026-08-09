## =====================================================================
## run_pairwise.R —— launcher 适配层(配对 meta 分析家族)。
## 一个适配器靠 --analysis 选择具体叶子输出:先按需构建重对象一次,
## 再 switch(analysis, ...) 只产出该叶子的图/表。工具包本身不改;
## 此脚本 source 它、读用户 CSV、调 ma_pairwise / 森林 / 漏斗 / 30_pairwise_family。
##
## --analysis 取值(默认 forest):
##   SPLIT(复用现有):forest 成对森林 · summary 汇总表 · funnel 等高线漏斗 ·
##                    egger Egger回归 · begg Begg秩相关 · trimfill 剪补 · petpeese PET-PEESE
##   NEW(30_pairwise_family):gen_forest 通用倒方差 · corr 相关系数合并 ·
##                    mh 稀有事件MH · peto Peto法 · glmm 二项-正态GLMM ·
##                    hr 生存HR合并 · labbe L'Abbé图 · radial 放射图
##
## 用法:
##   Rscript run_pairwise.R --input studies.csv --outdir out --analysis forest \
##           --measure OR --slab study --method REML --knha true
##   相关型: --analysis corr --input correlation.csv (列 study,cor,n)
##   生存型: --analysis hr   --input hr.csv          (列 study,te,seTE ; te=log HR)
##   工具包路径: --toolkit <dir> 或环境变量 META_TOOLKIT
## =====================================================================
suppressWarnings(suppressMessages({ library(metafor); library(meta); library(pdftools) }))
## 载入同目录公共样板(getarg / mw_init / to_png / col_of / mw_escalc)
source(file.path(dirname(sub("^--file=", "", commandArgs(FALSE)[grep("^--file=", commandArgs(FALSE))][1])), "_common.R"))

init <- mw_init(); input <- init$input; outdir <- init$outdir
analysis <- tolower(getarg("analysis", "forest"))
measure  <- toupper(getarg("measure", "OR"))
slabcol  <- getarg("slab", "study")
method   <- getarg("method", "REML")
knha     <- tolower(getarg("knha", "true")) %in% c("true", "1", "yes", "t")

df <- mw_read_csv(input)
cat(sprintf("run_pairwise: analysis = %s,读入 %d 个研究\n", analysis, nrow(df)))

## ---- 惰性构建重对象(仅在需要时,避免多余重拟合)---------------------
.es_fit <- NULL
build_es_fit <- function() {
  if (is.null(.es_fit)) {
    es  <- mw_escalc(df, measure)
    slab_vec <- slab_of(df, slabcol)
    fit <- ma_pairwise(es, measure = measure, method = method, knha = knha)
    attr(es, "slab") <- slab_vec
    .es_fit <<- list(es = es, fit = fit, slab = slab_vec)
  }
  .es_fit
}

pngify <- function(pdf) to_png(pdf)

switch(analysis,

  ## ===================== SPLIT:复用现有工具包函数 =====================
  "forest" = {
    o <- build_es_fit()
    f <- file.path(outdir, "forest.pdf"); ma_forest(o$fit, f, slab = o$slab); pngify(f)
    print(o$fit)
  },

  "summary" = {
    o <- build_es_fit()
    write.csv(ma_summary_row(o$fit, "pooled"), file.path(outdir, "summary.csv"), row.names = FALSE)
    print(o$fit)
  },

  "funnel" = {
    o <- build_es_fit()
    f <- file.path(outdir, "funnel.pdf"); ma_funnel(o$fit, f); pngify(f)
  },

  "egger" = {
    o <- build_es_fit()
    pb <- suppressWarnings(ma_pubbias(o$fit))
    e <- pb$egger
    write.csv(data.frame(test = "Egger regression (metafor::regtest)",
                         statistic = e$stat, df = e$df %||% NA, p = e$p,
                         predicted.effect.SE0 = e$est,
                         ci.lb = e$ci.lb, ci.ub = e$ci.ub,
                         row.names = NULL),
              file.path(outdir, "egger.csv"), row.names = FALSE)
  },

  "begg" = {
    o <- build_es_fit()
    pb <- suppressWarnings(ma_pubbias(o$fit))
    r <- pb$rank
    write.csv(data.frame(test = "Begg & Mazumdar rank correlation (metafor::ranktest)",
                         kendall.tau = r$tau, p = r$p, row.names = NULL),
              file.path(outdir, "begg.csv"), row.names = FALSE)
  },

  "trimfill" = {
    o <- build_es_fit()
    pb <- suppressWarnings(ma_pubbias(o$fit))
    tf <- pb$transf %||% identity; t <- pb$trimfill
    write.csv(data.frame(method = "Duval & Tweedie trim-and-fill (metafor::trimfill)",
                         k0.imputed = t$k0, side = t$side,
                         adjusted.est = as.numeric(tf(t$est)),
                         ci.lb = as.numeric(tf(t$ci.lb)), ci.ub = as.numeric(tf(t$ci.ub)),
                         k.total = t$k.total, row.names = NULL),
              file.path(outdir, "trimfill.csv"), row.names = FALSE)
    ## 附带带填补点的漏斗图
    f <- file.path(outdir, "funnel_trimfill.pdf"); ma_funnel(o$fit, f, trimfill = TRUE); pngify(f)
  },

  "petpeese" = {
    o <- build_es_fit()
    pb <- suppressWarnings(ma_pubbias(o$fit))
    tf <- pb$transf %||% identity; p <- pb$petpeese
    write.csv(data.frame(method = "PET-PEESE (Stanley & Doucouliagos 2014)",
                         chosen = p$model,
                         pet.intercept = p$pet.est, pet.p.one.sided = p$pet.p.one,
                         peese.intercept = p$peese.est,
                         adjusted.est = as.numeric(tf(p$corrected)),
                         ci.lb = as.numeric(tf(p$corrected.lb)), ci.ub = as.numeric(tf(p$corrected.ub)),
                         row.names = NULL),
              file.path(outdir, "petpeese.csv"), row.names = FALSE)
  },

  ## ===================== NEW:30_pairwise_family =======================
  "gen_forest" = {
    o <- build_es_fit()
    f <- file.path(outdir, "gen_forest.pdf")
    m <- pw_gen_forest(o$es, f, slab = o$slab, measure = measure,
                       method.tau = method, knha = knha); pngify(f)
    write.csv(pw_meta_summary(m, "generic-IV"), file.path(outdir, "gen_forest.csv"), row.names = FALSE)
  },

  "corr" = {
    cor <- as.numeric(col_of(df, "cor", "cor"))
    n   <- as.numeric(col_of(df, "n",   "n"))
    slab <- slab_of(df, slabcol)
    f <- file.path(outdir, "correlation.pdf")
    m <- pw_corr(cor, n, slab, f, method.tau = method, knha = knha); pngify(f)
    write.csv(pw_meta_summary(m, "correlation (r)"), file.path(outdir, "correlation.csv"), row.names = FALSE)
  },

  "mh" = {
    mb <- pw_metabin(df, method = "MH", sm = measure %||% "OR",
                     slab = slab_of(df, slabcol), method.tau = method)
    f <- file.path(outdir, "mh_forest.pdf"); pw_metabin_forest(mb, f); pngify(f)
    write.csv(pw_meta_summary(mb, "Mantel-Haenszel"), file.path(outdir, "mh.csv"), row.names = FALSE)
  },

  "peto" = {
    mb <- pw_metabin(df, method = "Peto", sm = "OR",
                     slab = slab_of(df, slabcol), method.tau = method)
    f <- file.path(outdir, "peto_forest.pdf"); pw_metabin_forest(mb, f); pngify(f)
    write.csv(pw_meta_summary(mb, "Peto OR"), file.path(outdir, "peto.csv"), row.names = FALSE)
  },

  "glmm" = {
    mb <- pw_metabin(df, method = "GLMM", sm = measure %||% "OR",
                     slab = slab_of(df, slabcol))
    f <- file.path(outdir, "glmm_forest.pdf"); pw_metabin_forest(mb, f); pngify(f)
    write.csv(pw_meta_summary(mb, "binomial-normal GLMM"), file.path(outdir, "glmm.csv"), row.names = FALSE)
  },

  "hr" = {
    te   <- as.numeric(col_of(df, "te",   "te"))
    seTE <- as.numeric(col_of(df, "seTE", "seTE"))
    slab <- slab_of(df, slabcol)
    f <- file.path(outdir, "hr_forest.pdf")
    m <- pw_hr(te, seTE, slab, f, method.tau = method, knha = knha); pngify(f)
    write.csv(pw_meta_summary(m, "hazard ratio"), file.path(outdir, "hr.csv"), row.names = FALSE)
  },

  "labbe" = {
    mb <- pw_metabin(df, method = "MH", sm = measure %||% "OR",
                     slab = slab_of(df, slabcol), method.tau = method)
    f <- file.path(outdir, "labbe.pdf"); pw_labbe(mb, f); pngify(f)
  },

  "radial" = {
    o <- build_es_fit()
    f <- file.path(outdir, "radial.pdf"); pw_radial(o$fit$re, f); pngify(f)
  },

  stop(sprintf("未知 --analysis '%s'(见脚本头注释)", analysis))
)

cat(sprintf("完成:analysis=%s → %s\n", analysis, outdir))
