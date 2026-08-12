## =====================================================================
## run_proportion.R —— launcher 适配层:把 meta-analysis-toolkit 的单臂
## (single-arm)比例/均值/发生率 meta 分析暴露成 --input/--outdir 的 CLI。
## 工具包本身不改;此脚本 source 它、读用户 CSV,按 --analysis 选择一个叶子:
##   logit      #9  单臂比例 logit(PLOGIT)            ma_proportion(method="PLOGIT")
##   glmm       #10 单臂比例 随机截距 GLMM            ma_proportion_glmm()
##   ft         #11 单臂比例 Freeman-Tukey 双反正弦   ma_proportion(method="PFT")
##   mean_rate  #12 单臂均值 / 发生率                 ma_mean() 或 ma_rate()
## 每个叶子只产出自己那份森林图(PDF→PNG 供界面)+ 汇总表(反变换回自然尺度)。
##
## 用法:
##   Rscript run_proportion.R --input proportion.csv --outdir out --analysis logit \
##           --event xi --n ni --studlab study
##   均值/率: --analysis mean_rate --submode rate  --event events --time time --studlab study
##            --analysis mean_rate --submode mean  --n n --mean mean --sd sd --studlab study
##   工具包路径: --toolkit <dir> 或环境变量 META_TOOLKIT
## =====================================================================
suppressWarnings(suppressMessages({ library(meta); library(metafor); library(pdftools) }))
## 载入同目录公共样板(getarg / mw_init / to_png / slab_of / mw_read_csv)
source(file.path(dirname(sub("^--file=", "", commandArgs(FALSE)[grep("^--file=", commandArgs(FALSE))][1])), "_common.R"))

init <- mw_init(); input <- init$input; outdir <- init$outdir
analysis <- getarg("analysis", "logit")
slabcol  <- getarg("studlab", "study")

df <- mw_read_csv(input)
col <- function(nm) { if (nm %in% names(df)) df[[nm]] else stop(sprintf("CSV 缺列 '%s'", nm)) }
slab_v <- slab_of(df, slabcol)

f_forest <- file.path(outdir, "forest.pdf")

res <- switch(analysis,

  ## ---- #9 单臂比例 logit(PLOGIT;研究规模异质时更稳的默认)---------------
  "logit" = {
    cat(sprintf("Step 1/2: 读入 %d 个研究 —— 单臂比例 logit(PLOGIT)\n", nrow(df)))
    ma_proportion(event = col(getarg("event", "xi")), n = col(getarg("n", "ni")),
                  studlab = slab_v, method = "PLOGIT", out = f_forest)
  },

  ## ---- #11 单臂比例 Freeman-Tukey 双反正弦(PFT)------------------------
  "ft" = {
    cat(sprintf("Step 1/2: 读入 %d 个研究 —— 单臂比例 Freeman-Tukey(PFT)\n", nrow(df)))
    ma_proportion(event = col(getarg("event", "xi")), n = col(getarg("n", "ni")),
                  studlab = slab_v, method = "PFT", out = f_forest)
  },

  ## ---- #10 单臂比例 随机截距二项-正态 GLMM(精确似然)-------------------
  "glmm" = {
    cat(sprintf("Step 1/2: 读入 %d 个研究 —— 单臂比例 GLMM(随机截距 logistic)\n", nrow(df)))
    ma_proportion_glmm(event = col(getarg("event", "xi")), n = col(getarg("n", "ni")),
                       studlab = slab_v, out = f_forest)
  },

  ## ---- #12 单臂均值 / 发生率 -------------------------------------------
  "mean_rate" = {
    submode <- tolower(getarg("submode", "rate"))
    if (submode == "mean") {
      cat(sprintf("Step 1/2: 读入 %d 个研究 —— 单臂均值(metamean, MRAW)\n", nrow(df)))
      ma_mean(n = col(getarg("n", "n")), mean = col(getarg("mean", "mean")),
              sd = col(getarg("sd", "sd")), studlab = slab_v, out = f_forest)
    } else {
      cat(sprintf("Step 1/2: 读入 %d 个研究 —— 单臂发生率(metarate, %s)\n",
                  nrow(df), toupper(getarg("ratemethod", "IRLN"))))
      ma_rate(event = col(getarg("event", "events")), time = col(getarg("time", "time")),
              studlab = slab_v, method = toupper(getarg("ratemethod", "IRLN")), out = f_forest)
    }
  },

  stop(sprintf("未知 --analysis '%s'(应为 logit / glmm / ft / mean_rate)", analysis))
)

to_png(f_forest)
print(res$row)

## ---- 汇总表(自然尺度:合并估计 + 95%CI + 预测区间 + I²/Q 异质性)----
cat("Step 2/2: 写出汇总表...\n")
write.csv(res$row, file.path(outdir, "summary.csv"), row.names = FALSE)
cat(sprintf("完成。森林图 + 汇总表(analysis=%s)写入 %s\n", analysis, outdir))
