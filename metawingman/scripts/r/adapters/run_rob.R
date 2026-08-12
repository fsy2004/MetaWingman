## =====================================================================
## run_rob.R —— launcher 适配层:把 meta-analysis-toolkit 的偏倚风险图
## (09_rob.R,基于 robvis 包)暴露成 --input/--outdir 的 CLI 方法。
## 工具包本身不改;此脚本 source 它、读用户 CSV、调 rob_traffic/rob_summary,
## 出图(交通灯图 + 汇总图,PDF→PNG 供界面显示)。
##
## 用法:
##   Rscript run_rob.R --input rob2.csv --outdir out --tool ROB2 --weighted true
##   工具包路径: --toolkit <dir> 或环境变量 META_TOOLKIT
##
## 数据格式: robvis 格式 data.frame —— 首列 Study(研究名),随后为各风险
##   域判断列(RoB2=D1..D5;ROBINS-I=D1..D7;RoB1=D1..D7),然后 Overall
##   (总体判断),可选 Weight(汇总图加权用的 meta 权重)。判断取值如
##   "Low"/"Some concerns"/"High"/"No information"。不同 tool 需匹配的域列数不同。
## =====================================================================
suppressWarnings(suppressMessages({ library(robvis); library(ggplot2); library(pdftools) }))
## 载入同目录公共样板(getarg / mw_init / to_png)
source(file.path(dirname(sub("^--file=", "", commandArgs(FALSE)[grep("^--file=", commandArgs(FALSE))][1])), "_common.R"))

init <- mw_init(); input <- init$input; outdir <- init$outdir
tool     <- toupper(getarg("tool", "ROB2"))   # 大写规整:robins-i→ROBINS-I,防 match.arg 大小写崩
weighted <- tolower(getarg("weighted", "true")) %in% c("true", "1", "yes", "t")

## ---- 读数据 ----
df <- mw_read_csv(input)
if (weighted && !("Weight" %in% names(df))) {   # 无 Weight 列时加权汇总图会报错 → 自动降级
  weighted <- FALSE
  cat("  (未检测到 Weight 列,汇总图改用未加权)\n")
}
cat(sprintf("Step 1/3: 读入 %d 个研究,tool = %s,weighted = %s\n", nrow(df), tool, weighted))

## ---- 交通灯图(per-study 域 x 研究 逐点判断)----
cat("Step 2/3: 交通灯图(traffic-light)...\n")
f_traffic <- file.path(outdir, "traffic.pdf")
rob_traffic(df, tool, f_traffic)
to_png(f_traffic)

## ---- 汇总图(加权堆叠条:各域判断分布,Cochrane 标准图)----
cat("Step 3/3: 汇总图(weighted summary bar)...\n")
f_summary <- file.path(outdir, "summary.pdf")
rob_summary(df, tool, f_summary, weighted = weighted)
to_png(f_summary)

cat(sprintf("完成。交通灯图 + 汇总图写入 %s\n", outdir))
