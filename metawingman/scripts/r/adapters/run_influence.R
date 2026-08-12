## =====================================================================
## run_influence.R —— launcher 适配层(家族适配器,一文件多叶子)。
## 把 meta-analysis-toolkit 的影响 / 稳健性诊断暴露成 --input/--outdir 的
## CLI。先照 run_pairwise 拟合随机效应模型(ma_pairwise),再按 --analysis
## 只产出被点选的那一张图 / 表:
##   loo         逐一剔除(Leave-one-out 森林)      -> leave_one_out.pdf/png + .csv
##   baujat      Baujat 图(异质性贡献 vs 影响)      -> baujat.pdf/png
##   cumulative  累积元分析(按精度/年份逐个纳入)    -> cumulative.pdf/png + .csv
##   gosh        GOSH 图(k<=20 枚举子集)            -> gosh.pdf/png
##   diagnostics 影响诊断(Cook/hat/DFFITS/DFBETAS)  -> influence_diag.pdf/png + .csv
##
## loo/baujat/cumulative/gosh 复用工具包 ma_influence(05_influence.R,已测),
## 只把请求的那份产物搬到 outdir;diagnostics 用新模块 ma_influence_diagnostics
## (30_influence.R,metafor::influence.rma.uni + plot + dfbetas)。
##
## 用法:
##   Rscript run_influence.R --input studies.csv --outdir out --analysis loo \
##           --measure OR --slab study --method REML --knha true
##   工具包路径: --toolkit <dir> 或环境变量 META_TOOLKIT
## =====================================================================
suppressWarnings(suppressMessages({ library(metafor); library(meta); library(pdftools) }))
## 载入同目录公共样板(getarg / mw_init / to_png / col_of / mw_escalc)
source(file.path(dirname(sub("^--file=", "", commandArgs(FALSE)[grep("^--file=", commandArgs(FALSE))][1])), "_common.R"))

init <- mw_init(); input <- init$input; outdir <- init$outdir
analysis <- tolower(getarg("analysis", "loo"))
measure  <- toupper(getarg("measure", "OR"))
slabcol  <- getarg("slab", "study")
method   <- getarg("method", "REML")
knha     <- tolower(getarg("knha", "true")) %in% c("true", "1", "yes", "t")

## ---- 读数据 + 算效应量 ----
df <- mw_read_csv(input)
cat(sprintf("Step 1/3: 读入 %d 个研究,measure = %s,analysis = %s\n", nrow(df), measure, analysis))
es <- mw_escalc(df, measure)
slab_vec <- slab_of(df, slabcol)
attr(es, "slab") <- slab_vec   ## 工具包从 attr(es,'slab') 恢复研究标签

## ---- 拟合随机效应模型(工具包 ma_pairwise,顶刊默认:REML + Knapp-Hartung)----
cat("Step 2/3: 随机效应合并(拟合待诊断模型)...\n")
fit <- ma_pairwise(es, measure = measure, method = method, knha = knha)

## ---- 按 --analysis 只产出对应叶子 ----
cat(sprintf("Step 3/3: 生成 [%s] 产物...\n", analysis))

if (analysis == "loo") {
  ## #27 逐一剔除(Leave-one-out 森林)+ 留一诊断表
  pdf <- file.path(outdir, "leave_one_out.pdf")
  loo_df <- ma_loo_forest(fit, pdf); to_png(pdf)
  write.csv(loo_df, file.path(outdir, "leave_one_out.csv"), row.names = FALSE)

} else if (analysis == "baujat") {
  ## #28 Baujat 图(异质性贡献 vs 影响)+ 坐标表
  pdf <- file.path(outdir, "baujat.pdf")
  bj_df <- ma_baujat_plot(fit, pdf); to_png(pdf)
  write.csv(bj_df, file.path(outdir, "baujat_points.csv"), row.names = FALSE)

} else if (analysis == "cumulative") {
  ## #29 累积元分析森林 + 累积表
  pdf <- file.path(outdir, "cumulative.pdf")
  cu_df <- ma_cumulative_forest(fit, pdf); to_png(pdf)
  write.csv(cu_df, file.path(outdir, "cumulative.csv"), row.names = FALSE)

} else if (analysis == "gosh") {
  ## #30 GOSH 图(枚举 2^k-1 子集,仅在 k<=20 时可行)
  if (fit$re$k > 20)
    stop(sprintf("GOSH 图需枚举 2^k-1 个子集,仅在研究数 k<=20 时可行;当前 k=%d 过大。", fit$re$k))
  pdf <- file.path(outdir, "gosh.pdf")
  ma_gosh_plot(fit, pdf); to_png(pdf)

} else if (analysis == "diagnostics") {
  ## #31 案例删除影响诊断图(Cook/hat/DFFITS/DFBETAS)+ 诊断表
  res <- ma_influence_diagnostics(fit, out_prefix = file.path(outdir, "influence_diag"),
                                  size = "double", height_mm = 180)
  to_png(res$pdf)
  write.csv(res$table, file.path(outdir, "influence_diag.csv"), row.names = FALSE)

} else {
  stop(sprintf("未知 --analysis '%s'(可选:loo / baujat / cumulative / gosh / diagnostics)", analysis))
}

cat(sprintf("完成。[%s] 图 / 表写入 %s\n", analysis, outdir))
