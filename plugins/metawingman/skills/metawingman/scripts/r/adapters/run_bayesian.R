## =====================================================================
## run_bayesian.R —— launcher 适配层(贝叶斯家族):把 meta-analysis-toolkit
## 的贝叶斯随机效应 meta(R/22_bayesian_meta.R 的 bma_run)按 --analysis 拆成
## 两个菜单叶子。模型只拟合一次(bayesmeta),再 switch 只渲染被点选的那张图。
##   --analysis forest    #50 贝叶斯随机效应森林(收缩估计 + 预测区间)
##   --analysis posterior #51 mu / tau 后验密度曲线
## 汇总表(mu/tau 后验中位数与可信区间、95% 预测区间)两叶子都会写出。
##
## 用法:
##   Rscript run_bayesian.R --input bayesian.csv --outdir out --analysis forest \
##           --tau_prior halfnormal --tau_scale 0.5
##   工具包路径: --toolkit <dir> 或环境变量 META_TOOLKIT
##   输入 CSV 列: study(研究名), yi(各研究效应量,如 log-OR), sei(标准误)
## =====================================================================
suppressWarnings(suppressMessages({ library(bayesmeta); library(pdftools) }))
## 载入同目录公共样板(getarg / mw_init / to_png / slab_of)
source(file.path(dirname(sub("^--file=", "", commandArgs(FALSE)[grep("^--file=", commandArgs(FALSE))][1])), "_common.R"))

init <- mw_init(); input <- init$input; outdir <- init$outdir
analysis  <- tolower(getarg("analysis", "forest"))
tau_prior <- tolower(getarg("tau_prior", "halfnormal"))
tau_scale <- as.numeric(getarg("tau_scale", "0.5"))
slabcol   <- getarg("slab", "study")

## ---- 读数据(直接给定 yi,sei;这是贝叶斯 normal-normal 模型的输入)----
df <- mw_read_csv(input)
if (!all(c("yi", "sei") %in% names(df))) stop("CSV 需含列 yi(效应量)与 sei(标准误)")
slab_vec <- slab_of(df, slabcol)
cat(sprintf("Step 1/3: 读入 %d 个研究,tau 先验 = %s(scale=%.3g),analysis = %s\n",
            nrow(df), tau_prior, tau_scale, analysis))

## ---- 贝叶斯随机效应 meta:只拟合一次(out_prefix=NULL 即不渲染任何图)----
cat("Step 2/3: 贝叶斯合并(bayesmeta,后验 mu/tau + 预测区间)...\n")
res <- bma_run(df$yi, df$sei, labels = slab_vec,
               tau_prior = tau_prior, tau_scale = tau_scale, out_prefix = NULL)
bm <- res$model

## ---- 汇总表两叶子共用(mu/tau 后验中位数与 95% 可信区间、预测区间)----
write.csv(res$row, file.path(outdir, "bma_summary.csv"), row.names = FALSE)

## ---- 按 --analysis 只渲染被点选的那张图 → PDF → PNG(界面显示)----
cat(sprintf("Step 3/3: 渲染 [%s] 图 + 转 PNG...\n", analysis))
pdf_out <- switch(analysis,
  forest    = bma_forest_fig(bm,    file.path(outdir, "bma_forest.pdf")),
  posterior = bma_posterior_fig(bm, file.path(outdir, "bma_posterior.pdf")),
  stop(sprintf("未知 --analysis '%s'(应为 forest / posterior)", analysis)))
to_png(pdf_out)

cat(sprintf("完成。[%s] 图 + 后验汇总表写入 %s\n", analysis, outdir))
