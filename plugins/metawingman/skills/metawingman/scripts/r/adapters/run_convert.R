## =====================================================================
## run_convert.R —— 效应量/数据转换器套件。把用户手头的原始数据换算成
## 标准 yi(效应量)/ sei(标准误),输出 converted.csv,可直接喂"通用倒方差森林"
## 等分析。一个适配器 + --analysis 选择器服务多个转换叶。列名可用 --<role> 映射。
##   es_2x2   : 2×2(ai,bi,ci,di) → OR/RR/RD… 的 yi/sei(metafor::escalc)
##   es_means : 两组均值±SD → SMD/MD 的 yi/sei
##   es_cor   : 相关系数 r,n → Fisher z 的 yi/sei
##   ci_to_se : 点估计 + 95%CI → yi/sei(比值型自动取 log)
##   p_to_se  : 点估计 + 双侧 p → yi/sei
## =====================================================================
suppressWarnings(suppressMessages({ library(metafor) }))
source(file.path(dirname(sub("^--file=", "", commandArgs(FALSE)[grep("^--file=", commandArgs(FALSE))][1])), "_common.R"))

init <- mw_init(need_toolkit = FALSE); input <- init$input; outdir <- init$outdir
analysis <- tolower(getarg("analysis", "es_2x2"))
df <- mw_read_csv(input)
Z <- 1.959964
slabcol <- getarg("slab", "study")
slab <- if (slabcol %in% names(df)) as.character(df[[slabcol]]) else paste("Study", seq_len(nrow(df)))
numc <- function(k, d = k) as.numeric(col_of(df, k, d))
is_ratio <- function() tolower(getarg("ratio", "true")) %in% c("true", "1", "yes", "t")

cat(sprintf("转换 [%s]:读入 %d 行\n", analysis, nrow(df)))
out <- switch(analysis,
  es_2x2 = {
    measure <- toupper(getarg("measure", "OR"))
    es <- escalc(measure = measure, ai = col_of(df, "ai", "ai"), bi = col_of(df, "bi", "bi"),
                 ci = col_of(df, "ci", "ci"), di = col_of(df, "di", "di"))
    data.frame(study = slab, yi = as.numeric(es$yi), sei = sqrt(as.numeric(es$vi)), measure = measure)
  },
  es_means = {
    measure <- toupper(getarg("measure", "SMD"))
    es <- escalc(measure = measure, m1i = col_of(df, "m1i", "m1i"), sd1i = col_of(df, "sd1i", "sd1i"),
                 n1i = col_of(df, "n1i", "n1i"), m2i = col_of(df, "m2i", "m2i"),
                 sd2i = col_of(df, "sd2i", "sd2i"), n2i = col_of(df, "n2i", "n2i"))
    data.frame(study = slab, yi = as.numeric(es$yi), sei = sqrt(as.numeric(es$vi)), measure = measure)
  },
  es_cor = {
    es <- escalc(measure = "ZCOR", ri = col_of(df, "cor", "cor"), ni = col_of(df, "n", "n"))
    data.frame(study = slab, yi = as.numeric(es$yi), sei = sqrt(as.numeric(es$vi)), measure = "ZCOR (Fisher z)")
  },
  ci_to_se = {
    est <- numc("est"); lo <- numc("lo"); hi <- numc("hi")
    if (is_ratio()) { yi <- log(est); se <- (log(hi) - log(lo)) / (2 * Z); note <- "log-scale (ratio)" }
    else           { yi <- est;      se <- (hi - lo) / (2 * Z);           note <- "raw scale" }
    data.frame(study = slab, yi = yi, sei = se, note = note)
  },
  p_to_se = {
    est <- numc("est"); p <- numc("p")
    yi <- if (is_ratio()) log(est) else est
    z <- qnorm(1 - p / 2); se <- abs(yi) / z
    data.frame(study = slab, yi = yi, sei = se, note = if (is_ratio()) "log-scale (ratio)" else "raw scale")
  },
  stop(sprintf("未知转换 --analysis '%s'(可用:es_2x2/es_means/es_cor/ci_to_se/p_to_se)", analysis))
)
write.csv(out, file.path(outdir, "converted.csv"), row.names = FALSE)
cat(sprintf("完成:%s → converted.csv(%d 行;列 yi/sei 可直接用于「通用倒方差森林」)\n", analysis, nrow(out)))
