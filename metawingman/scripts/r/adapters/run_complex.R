## =====================================================================
## run_complex.R —— launcher 适配层:复杂数据结构 meta 分析(family
## "复杂数据结构 / Complex Data Structures")。一个适配服务 4 个菜单叶子,
## 由 --analysis 选择,只产出该叶子的图/表:
##   --analysis ml3          三层元分析 (metafor::rma.mv 嵌套随机效应)
##   --analysis rve          稳健方差估计 (robumeta::robu + clubSandwich CR2)
##   --analysis dose_linear  剂量反应线性 (dosresmeta 对数线性趋势)
##   --analysis dose_spline  剂量反应样条 (dosresmeta + rms::rcs)
##
## 输入(两种形状,同族共享):
##   聚类型 (ml3/rve): 列 yi, vi, cluster, study —— 每行一个效应量,
##     同 cluster 内多个效应量相关(如同一实验室/队列的多个结局)。
##   剂量型 (dose_*): 列 id, type, dose, cases, n, logrr, se —— 每研究
##     多个有序暴露水平,参照行 se 留空(NA)。
##
## 工具包本身不改;此脚本 source 它、读 CSV、调 30_complex.R 的函数出图+表。
## 用法:
##   Rscript run_complex.R --input complex_clustered.csv --outdir out --analysis ml3
##   工具包路径: --toolkit <dir> 或环境变量 META_TOOLKIT
## =====================================================================
suppressWarnings(suppressMessages({
  library(metafor); library(robumeta); library(clubSandwich)
  library(dosresmeta); library(rms); library(pdftools)
}))
## 载入同目录公共样板(getarg / mw_init / to_png / mw_read_csv)
source(file.path(dirname(sub("^--file=", "", commandArgs(FALSE)[grep("^--file=", commandArgs(FALSE))][1])), "_common.R"))

init <- mw_init(); input <- init$input; outdir <- init$outdir
analysis <- getarg("analysis", "ml3")
method   <- getarg("method", "REML")

df <- mw_read_csv(input)
cat(sprintf("run_complex: analysis = %s, 读入 %d 行\n", analysis, nrow(df)))

switch(analysis,

  ## ---- #32 三层元分析 -------------------------------------------------
  ml3 = {
    mw_complex_ml3(df,
      yi      = getarg("yi", "yi"),
      vi      = getarg("vi", "vi"),
      cluster = getarg("cluster", "cluster"),
      study   = getarg("study", "study"),
      method  = method, outdir = outdir)
  },

  ## ---- #33 稳健方差估计 (RVE) ----------------------------------------
  rve = {
    mw_complex_rve(df,
      yi      = getarg("yi", "yi"),
      vi      = getarg("vi", "vi"),
      cluster = getarg("cluster", "cluster"),
      method  = method, outdir = outdir)
  },

  ## ---- #34 剂量反应 · 线性 -------------------------------------------
  dose_linear = {
    mw_complex_dose(df,
      id = getarg("id", "id"), type = getarg("type", "type"),
      dose = getarg("dose", "dose"), cases = getarg("cases", "cases"),
      n = getarg("n", "n"), logrr = getarg("logrr", "logrr"),
      se = getarg("se", "se"), spline = FALSE,
      method = method, outdir = outdir)
  },

  ## ---- #35 剂量反应 · 三次样条 ---------------------------------------
  dose_spline = {
    nk <- suppressWarnings(as.integer(getarg("knots", "3")))
    if (is.na(nk) || nk < 3) nk <- 3
    kn <- stats::quantile(as.numeric(df[[getarg("dose", "dose")]]),
                          probs = seq(0.05, 0.95, length.out = nk), na.rm = TRUE)
    mw_complex_dose(df,
      id = getarg("id", "id"), type = getarg("type", "type"),
      dose = getarg("dose", "dose"), cases = getarg("cases", "cases"),
      n = getarg("n", "n"), logrr = getarg("logrr", "logrr"),
      se = getarg("se", "se"), spline = TRUE, knots = kn,
      method = method, outdir = outdir)
  },

  stop(sprintf("未知 --analysis '%s'(应为 ml3 / rve / dose_linear / dose_spline)", analysis))
)

cat(sprintf("完成。输出写入 %s\n", outdir))
