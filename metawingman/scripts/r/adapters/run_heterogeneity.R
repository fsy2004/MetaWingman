## =====================================================================
## run_heterogeneity.R —— launcher 适配层(家族适配器):把 meta-analysis-toolkit
## 的异质性与调节分析暴露成 --input/--outdir/--analysis 的 CLI 方法。
## 一个适配器服务 5 个菜单叶(--analysis 选择其一,重活 escalc+ma_pairwise 只做一次):
##   stats       #13 异质性统计量(I²/τ²/H²/Q + 轮廓似然 CI)  -> het_stats_table
##   subgroup    #14 亚组分析 + 亚组森林(混合效应 Q_M 差异检验) -> ma_subgroup + het_subgroup_forest
##   metareg     #15 元回归 + 气泡图(连续调节变量,系数表/Q_M/伪R²) -> ma_metareg
##   pred_forest #16 预测区间森林(95% PI,展示真实效应弥散)      -> het_pred_forest
##   permute     #17 置换检验元回归(小 k 稳健 p 值)             -> het_permute
##
## 工具包本身不改;此脚本 source 它(00→30 全量),读用户 CSV,先算效应量(二分类
## 2×2 → OR/RR/RD/PETO)并拟合随机效应基线模型(REML + Knapp-Hartung),再按
## --analysis 分支只产出该叶的图/表。图 PDF→PNG 供界面显示。
##
## 用法:
##   Rscript run_heterogeneity.R --input bcg.csv --outdir out --analysis subgroup \
##           --measure OR --subgroup alloc --moderator ablat
##   工具包路径: --toolkit <dir> 或环境变量 META_TOOLKIT
## 输入 CSV: 每行一个研究,需列 ai,bi,ci,di + 研究名列(默认 study)
##           + 一个类别调节列(默认 alloc,用于 subgroup)
##           + 一个数值调节列(默认 ablat,用于 metareg / permute)。
## =====================================================================
suppressWarnings(suppressMessages({ library(metafor); library(meta); library(pdftools) }))
## 载入同目录公共样板(getarg / mw_init / to_png / col_of)
source(file.path(dirname(sub("^--file=", "", commandArgs(FALSE)[grep("^--file=", commandArgs(FALSE))][1])), "_common.R"))

init <- mw_init(); input <- init$input; outdir <- init$outdir
analysis  <- getarg("analysis", "stats")
measure   <- toupper(getarg("measure", "OR"))
slabcol   <- getarg("slab", "study")
subgroup  <- getarg("subgroup", "alloc")
moderator <- getarg("moderator", "ablat")
method    <- getarg("method", "REML")
knha      <- tolower(getarg("knha", "true")) %in% c("true", "1", "yes", "t")
iter      <- suppressWarnings(as.integer(getarg("iter", "1000")))
if (is.na(iter) || iter < 99) iter <- 1000

## ---- 读数据 + 算效应量(二分类 2x2 -> OR/RR/RD/PETO)----
df <- mw_read_csv(input)
cat(sprintf("异质性分析 [%s]:读入 %d 个研究,measure = %s\n", analysis, nrow(df), measure))

if (!measure %in% c("OR", "RR", "RD", "PETO"))
  stop(sprintf("本适配的异质性分析针对二分类 2x2(measure=OR/RR/RD/PETO),收到 measure=%s", measure))
ai <- col_of(df, "ai", "ai"); bi <- col_of(df, "bi", "bi")
ci <- col_of(df, "ci", "ci"); di <- col_of(df, "di", "di")
es <- as.data.frame(metafor::escalc(measure = measure, ai = ai, bi = bi, ci = ci, di = di))

## 研究级调节变量并入 es(供 ma_subgroup / ma_metareg / het_* 从 fit$es 读取);缺则跳过
slab_vec <- slab_of(df, slabcol)
if (subgroup  %in% names(df)) es[[subgroup]]  <- df[[subgroup]]
if (moderator %in% names(df)) es[[moderator]] <- df[[moderator]]
es[[slabcol]] <- slab_vec
attr(es, "slab") <- slab_vec

## ---- 拟合随机效应基线模型(所有叶共用,只拟合一次)----
fit <- ma_pairwise(es, measure = measure, method = method, knha = knha)

## ---- 按 --analysis 分支,只产出该叶输出 ----
switch(analysis,

  ## #13 异质性统计量面板(I²/τ²/H²/Q + CI)-> CSV
  "stats" = {
    tab <- het_stats_table(fit)
    write.csv(tab, file.path(outdir, "heterogeneity_stats.csv"), row.names = FALSE)
    cat(sprintf("完成。异质性统计量表写入 %s\n", outdir))
  },

  ## #14 亚组分析(表)+ 亚组森林图
  "subgroup" = {
    if (!subgroup %in% names(es))
      stop(sprintf("CSV 缺亚组列 '%s'(参数 --subgroup)", subgroup))
    sg <- ma_subgroup(fit, subgroup)
    write.csv(sg$table, file.path(outdir, "subgroup.csv"), row.names = FALSE)
    write.csv(as.data.frame(sg$qm), file.path(outdir, "subgroup_Qtest.csv"), row.names = FALSE)
    f_sg <- file.path(outdir, "subgroup_forest.pdf")
    het_subgroup_forest(fit, subgroup, f_sg, slab = slab_vec); to_png(f_sg)
    cat(sprintf("完成。亚组表 + 亚组森林图写入 %s\n", outdir))
  },

  ## #15 元回归 + 气泡图(连续调节变量)
  "metareg" = {
    if (!moderator %in% names(es))
      stop(sprintf("CSV 缺调节列 '%s'(参数 --moderator)", moderator))
    f_reg <- file.path(outdir, "metareg.pdf")
    mr <- ma_metareg(fit, as.formula(paste0("~", moderator)), out = f_reg)
    write.csv(mr$coef, file.path(outdir, "metareg_coef.csv"), row.names = FALSE)
    if (file.exists(f_reg)) to_png(f_reg) else
      cat("  (未生成气泡图:调节变量非单一连续型,已跳过)\n")
    cat(sprintf("完成。回归系数表 + 气泡图写入 %s\n", outdir))
  },

  ## #16 预测区间森林
  "pred_forest" = {
    f_pf <- file.path(outdir, "prediction_forest.pdf")
    het_pred_forest(fit, f_pf, slab = slab_vec); to_png(f_pf)
    write.csv(ma_summary_row(fit, "pooled"), file.path(outdir, "pooled_summary.csv"), row.names = FALSE)
    cat(sprintf("完成。预测区间森林图 + 汇总表写入 %s\n", outdir))
  },

  ## #17 置换检验元回归
  "permute" = {
    if (!moderator %in% names(es))
      stop(sprintf("CSV 缺调节列 '%s'(参数 --moderator)", moderator))
    res <- het_permute(fit, moderator, iter = iter)
    write.csv(res$table, file.path(outdir, "permutation_metareg.csv"), row.names = FALSE)
    cat(sprintf("完成。置换检验元回归表写入 %s\n", outdir))
  },

  stop(sprintf("未知 --analysis '%s'(可选 stats/subgroup/metareg/pred_forest/permute)", analysis))
)
