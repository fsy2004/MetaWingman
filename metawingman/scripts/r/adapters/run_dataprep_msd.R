## =====================================================================
## run_dataprep_msd.R —— 数据准备:从中位数/四分位/极差估算 均值 ± 标准差
## 很多研究只报告 median (Q1, Q3) 或 median (min, max),做 SMD/MD 的 meta 分析
## 需要 mean ± sd。本工具用 estmeansd(Cai 2021 / McGrath 2020 等已发表方法)估算。
## estmeansd 自动按可得分位选场景:S1=min+median+max+n / S2=q1+median+q3+n / S3=五者全。
## 用法: Rscript run_dataprep_msd.R --input stats.csv --outdir out [--method qe|bc]
## 说明:本方法不依赖 meta 工具包(仅用 estmeansd),故 mw_init(need_toolkit=FALSE)。
## =====================================================================
suppressWarnings(suppressMessages(library(estmeansd)))
## 载入同目录公共样板(getarg / mw_init)
source(file.path(dirname(sub("^--file=", "", commandArgs(FALSE)[grep("^--file=", commandArgs(FALSE))][1])), "_common.R"))

init <- mw_init(need_toolkit = FALSE); input <- init$input; outdir <- init$outdir
method <- tolower(getarg("method", "qe"))

df <- mw_read_csv(input)
if (nrow(df) == 0) stop("输入 CSV 没有数据行,请检查文件。")
cat(sprintf("Step 1/2: 读入 %d 行,方法 = %s\n", nrow(df), method))
gv <- function(col) if (col %in% names(df)) suppressWarnings(as.numeric(df[[col]])) else rep(NA_real_, nrow(df))
mn <- gv("min"); q1 <- gv("q1"); med <- gv("median"); q3 <- gv("q3"); mx <- gv("max"); n <- gv("n")
fn <- if (method == "bc") estmeansd::bc.mean.sd else estmeansd::qe.mean.sd

cat("Step 2/2: 逐行估算 mean/sd...\n")
res <- lapply(seq_len(nrow(df)), function(i) {
  r <- tryCatch(fn(min.val = mn[i], q1.val = q1[i], med.val = med[i], q3.val = q3[i], max.val = mx[i], n = n[i]),
                error = function(e) NULL)
  data.frame(
    study    = if ("study" %in% names(df)) as.character(df$study[i]) else as.character(i),
    n        = n[i],
    est_mean = if (!is.null(r)) round(r$est.mean, 4) else NA_real_,
    est_sd   = if (!is.null(r)) round(r$est.sd, 4) else NA_real_,
    stringsAsFactors = FALSE)
})
out <- do.call(rbind, res)
write.csv(out, file.path(outdir, "estimated_mean_sd.csv"), row.names = FALSE)
ok <- sum(!is.na(out$est_mean))
cat(sprintf("完成。%d/%d 行成功估算,结果写入 %s\n", ok, nrow(out), file.path(outdir, "estimated_mean_sd.csv")))
if (ok < nrow(out)) cat("  (未成功的行:分位数不足以匹配任一场景,请检查是否提供了 min+median+max+n 或 q1+median+q3+n)\n")
