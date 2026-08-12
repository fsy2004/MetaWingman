## =====================================================================
## run_evalue.R —— launcher 适配层:E 值敏感性分析(EValue::evalue)。
## 输入一个/多个合并效应(点估计 + 置信区间,RR/OR/HR 尺度),
## 输出每个效应的 E 值(点估计 + 置信限)表 + 首个效应的偏倚曲线图。
##
## 用法:
##   Rscript run_evalue.R --input evalue.csv --outdir out --analysis evalue \
##           --measure RR [--rare false] [--true 1] \
##           [--est_col est --lo_col lo --hi_col hi --slab study]
##   工具包路径:--toolkit <dir> 或环境变量 META_TOOLKIT
## =====================================================================
suppressWarnings(suppressMessages({ library(EValue); library(ggplot2); library(pdftools) }))
## 载入同目录公共样板(getarg / mw_init / to_png ...)
source(file.path(dirname(sub("^--file=", "", commandArgs(FALSE)[grep("^--file=", commandArgs(FALSE))][1])), "_common.R"))

init <- mw_init(); input <- init$input; outdir <- init$outdir
analysis <- getarg("analysis", "evalue")
measure  <- toupper(getarg("measure", "RR"))
rare     <- tolower(getarg("rare", "false")) %in% c("true", "1", "yes", "t")
true_val <- suppressWarnings(as.numeric(getarg("true", "1")))
est_col  <- getarg("est_col", "est")
lo_col   <- getarg("lo_col", "lo")
hi_col   <- getarg("hi_col", "hi")
labcol   <- getarg("slab", "study")

df <- mw_read_csv(input)
cat(sprintf("Step 1/3: 读入 %d 个合并效应,measure = %s%s\n",
            nrow(df), measure, if (rare) "(rare)" else ""))

switch(analysis,
  "evalue" = {
    ## ---- 每个合并效应的 E 值表 ----
    cat("Step 2/3: 计算 E 值(点估计 + 置信限)...\n")
    tab <- mw_evalue_table(df, measure = measure, rare = rare, true = true_val,
                           est_col = est_col, lo_col = lo_col, hi_col = hi_col,
                           label_col = labcol)
    print(tab)
    write.csv(tab, file.path(outdir, "evalue.csv"), row.names = FALSE)

    ## ---- 首个合并效应的偏倚曲线图 ----
    cat("Step 3/3: E 值偏倚曲线图(首个效应)...\n")
    lo1 <- if (lo_col %in% names(df)) suppressWarnings(as.numeric(df[[lo_col]][1])) else NA
    hi1 <- if (hi_col %in% names(df)) suppressWarnings(as.numeric(df[[hi_col]][1])) else NA
    evmat <- mw_evalue_one(as.numeric(df[[est_col]][1]), lo1, hi1, measure, rare, true_val)
    f <- file.path(outdir, "evalue_bias_plot.pdf")
    mw_evalue_plot(evmat, f); to_png(f)
  },
  stop(sprintf("run_evalue.R 不支持 analysis='%s'(仅 evalue)", analysis))
)

cat(sprintf("完成。E 值表 + 偏倚曲线图写入 %s\n", outdir))
