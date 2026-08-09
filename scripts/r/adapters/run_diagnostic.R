## =====================================================================
## run_diagnostic.R —— launcher 适配层(诊断试验准确性 DTA 家族适配器)。
## 一个适配器服务多个菜单叶子,用 --analysis 选择输出:
##   sroc          #46 双变量 SROC 曲线          (mada::reitsma + plot)
##   paired_forest #47 敏感度/特异度森林          (mada::forest / madad)
##   lr_dor        #48 似然比 + 诊断比值比        (mada::madad / SummaryPts)
##   hsroc         #49 HSROC 模型(Rutter-Gatsonis)(mada::sroc type=ruttergatsonis)
## 重对象(madad 描述 + reitsma 双变量模型)只建一次,再 switch 出该叶子的图/表。
## 工具包本身不改;此脚本 source 它、读用户 CSV、调 30_diagnostic_split.R 的函数。
##
## 用法:
##   Rscript run_diagnostic.R --input diagnostic.csv --outdir out \
##           --analysis sroc --study study --add_correction 0.5
##   工具包路径: --toolkit <dir> 或环境变量 META_TOOLKIT
## 数据: 每行一个研究,2x2 诊断表列 TP,FN,FP,TN(+ 研究名列,默认 study)。
## =====================================================================
suppressWarnings(suppressMessages({ library(mada); library(pdftools) }))
## 载入同目录公共样板(getarg / mw_init / to_png)
source(file.path(dirname(sub("^--file=", "", commandArgs(FALSE)[grep("^--file=", commandArgs(FALSE))][1])), "_common.R"))

init <- mw_init(); input <- init$input; outdir <- init$outdir
analysis <- getarg("analysis", "sroc")
studycol <- getarg("study", "study")
add_corr <- as.numeric(getarg("add_correction", "0.5"))

## ---- 读数据 ----
df <- mw_read_csv(input)
need <- c("TP", "FN", "FP", "TN")
if (!all(need %in% names(df)))
  stop(sprintf("CSV 缺列:需要 %s(每行一个研究的 2x2 诊断表)", paste(need, collapse = ", ")))
cat(sprintf("Step 1/3: 读入 %d 个诊断研究(TP/FN/FP/TN),analysis = %s\n", nrow(df), analysis))

## 研究名 -> 数据框行名,便于森林图标注每个研究
dat <- df[, need]
slab <- if (studycol %in% names(df)) make.unique(as.character(df[[studycol]])) else paste("Study", seq_len(nrow(dat)))
rownames(dat) <- slab

## ---- 重对象只建一次(madad 描述 + reitsma 双变量模型)----
cat("Step 2/3: 双变量随机效应合并(Reitsma)+ 描述性统计...\n")
built <- dta_build(dat, add_correction = add_corr)
descr <- built$descr; fit <- built$fit

## ---- switch:只出该叶子的图/表 ----
cat(sprintf("Step 3/3: 生成 [%s] 输出...\n", analysis))
switch(analysis,

  ## #46 双变量 SROC 曲线 -----------------------------------------------
  "sroc" = {
    p <- file.path(outdir, "sroc.pdf"); dta_fig_sroc(fit, dat, p); to_png(p)
    s  <- summary(fit)$coefficients
    write.csv(data.frame(
      metric = c("Sensitivity", "Specificity", "SROC AUC"),
      estimate = c(s["sensitivity", "Estimate"], 1 - s["false pos. rate", "Estimate"],
                   mada::AUC(fit)$AUC),
      ci_low  = c(s["sensitivity", "95%ci.lb"], 1 - s["false pos. rate", "95%ci.ub"], NA),
      ci_high = c(s["sensitivity", "95%ci.ub"], 1 - s["false pos. rate", "95%ci.lb"], NA)
    ), file.path(outdir, "sroc_summary.csv"), row.names = FALSE)
  },

  ## #47 敏感度 / 特异度森林 -------------------------------------------
  "paired_forest" = {
    ps <- file.path(outdir, "forest_sens.pdf"); pp <- file.path(outdir, "forest_spec.pdf")
    dta_fig_paired(descr, ps, pp); to_png(ps); to_png(pp)
    write.csv(data.frame(
      study = slab,
      sensitivity = descr$sens$sens, sens_lo = descr$sens$sens.ci[, 1], sens_hi = descr$sens$sens.ci[, 2],
      specificity = descr$spec$spec, spec_lo = descr$spec$spec.ci[, 1], spec_hi = descr$spec$spec.ci[, 2]
    ), file.path(outdir, "paired_summary.csv"), row.names = FALSE)
  },

  ## #48 似然比 + 诊断比值比 -------------------------------------------
  "lr_dor" = {
    p <- file.path(outdir, "lr_dor.pdf")
    summ <- dta_lr_dor(fit, descr, p, slab = slab); to_png(p)
    write.csv(summ, file.path(outdir, "lr_dor_summary.csv"), row.names = FALSE)
  },

  ## #49 HSROC 模型(Rutter-Gatsonis)----------------------------------
  "hsroc" = {
    p <- file.path(outdir, "hsroc.pdf")
    summ <- dta_hsroc(fit, dat, p); to_png(p)
    write.csv(summ, file.path(outdir, "hsroc_summary.csv"), row.names = FALSE)
  },

  stop(sprintf("未知 --analysis '%s'(可选:sroc / paired_forest / lr_dor / hsroc)", analysis))
)

cat(sprintf("完成。[%s] 输出写入 %s\n", analysis, outdir))
