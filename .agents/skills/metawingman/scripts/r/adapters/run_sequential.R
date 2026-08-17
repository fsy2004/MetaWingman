## =====================================================================
## run_sequential.R —— launcher 适配层:序贯与效能(第 9 类)。
## 一个适配器 + --analysis 选择器服务 2 个菜单叶:
##   --analysis tsa  (#52) 试验序贯分析 TSA —— 序贯监测边界图 + 逐次统计量表
##   --analysis ris  (#53) 所需信息量 RIS  —— AIS vs 异质性校正 RIS 汇总表 + lollipop 图
## 二者共用同一份二分类结局输入(study,eI,nI,eC,nC),只跑一次 RTSA 重对象。
##
## 用法:
##   Rscript run_sequential.R --input seq.csv --outdir out --analysis tsa \
##           --outcome RR --mc 0.8 --alpha 0.05 --beta 0.1 --es_alpha esOF
## 工具包路径:--toolkit <dir> 或环境变量 META_TOOLKIT
## =====================================================================
suppressWarnings(suppressMessages({ library(RTSA); library(ggplot2); library(pdftools) }))
## 载入同目录公共样板(getarg / mw_init / to_png / mw_read_csv)
source(file.path(dirname(sub("^--file=", "", commandArgs(FALSE)[grep("^--file=", commandArgs(FALSE))][1])), "_common.R"))

init <- mw_init(); input <- init$input; outdir <- init$outdir
analysis <- getarg("analysis", "tsa")
outcome  <- toupper(getarg("outcome", "RR"))
mc       <- as.numeric(getarg("mc", "0.8"))
side     <- as.integer(getarg("side", "2"))
alpha    <- as.numeric(getarg("alpha", "0.05"))
beta     <- as.numeric(getarg("beta", "0.1"))
es_alpha <- getarg("es_alpha", "esOF")
futility <- getarg("futility", "none")

## ---- 读数据 ----
df <- mw_read_csv(input)
cat(sprintf("Step 1/3: 读入 %d 个研究(二分类结局),outcome=%s, mc=%s, analysis=%s\n",
            nrow(df), outcome, mc, analysis))

## ---- 一次性拟合 TSA 重对象(边界 + RIS 都在其中)----
cat("Step 2/3: 计算试验序贯分析(边界 + 所需信息量)...\n")
fit <- seq_fit(df, outcome = outcome, mc = mc, side = side,
               alpha = alpha, beta = beta, es_alpha = es_alpha, futility = futility)

## ---- 按 --analysis 只产出该叶的输出 ----
cat(sprintf("Step 3/3: 输出 [%s]...\n", analysis))
switch(analysis,
  "tsa" = {
    f_plot <- file.path(outdir, "tsa_boundary.pdf")
    seq_tsa_plot(fit, f_plot); to_png(f_plot)
    write.csv(seq_bounds_df(fit), file.path(outdir, "tsa_sequential_stats.csv"), row.names = FALSE)
    cat("  TSA 序贯监测边界图 + 逐次统计量表已写出。\n")
    invisible(tryCatch(cat(sprintf("  RIS=%.0f, HARIS=%.0f, AIS=%.0f\n",
                    fit$results$RIS, fit$results$HARIS, fit$results$AIS)),
                    error = function(e) NULL))
  },
  "ris" = {
    ris_df <- seq_ris_df(fit)
    write.csv(ris_df, file.path(outdir, "required_information_size.csv"), row.names = FALSE)
    f_plot <- file.path(outdir, "ris_lollipop.pdf")
    seq_ris_plot(ris_df, f_plot); to_png(f_plot)
    cat("  所需信息量汇总表 + lollipop 图已写出。\n")
    print(ris_df[, c("statistic", "participants")])
  },
  stop(sprintf("未知 --analysis '%s'(可用:tsa / ris)", analysis))
)

cat(sprintf("完成。输出写入 %s\n", outdir))
