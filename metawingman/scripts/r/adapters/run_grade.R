## =====================================================================
## run_grade.R —— launcher 适配层:把 meta-analysis-toolkit 的 GRADE 证据
## 分级 + Summary-of-Findings(SoF)表暴露成 --input/--outdir 的 CLI 方法。
## 这是【表格】方法:逐行读结局 -> ma_grade() 计算证据确定性 ->
## ma_sof_table() 汇总成 sof.csv;并额外用 gridExtra::tableGrob 把 SoF 表
## 渲成一张 sof_table.png(界面目前只显示 PNG,故补一张表图)。
##
## 用法:
##   Rscript run_grade.R --input grade.csv --outdir out
##   工具包路径: --toolkit <dir> 或环境变量 META_TOOLKIT
##
## 输入 CSV(每行一个结局):label, design(rct/observational),
##   rob, inconsistency, indirectness, imprecision, pubbias,
##   large_effect, dose_response, plausible_confounding(整数降/升级,缺省 0)。
## =====================================================================
suppressWarnings(suppressMessages({ library(utils) }))
## 载入同目录公共样板(getarg / mw_init)
source(file.path(dirname(sub("^--file=", "", commandArgs(FALSE)[grep("^--file=", commandArgs(FALSE))][1])), "_common.R"))

init <- mw_init(); input <- init$input; outdir <- init$outdir

## ---- 读数据 ----
df <- mw_read_csv(input)
cat(sprintf("Step 1/3: 读入 %d 个结局(outcomes)\n", nrow(df)))

## 列名容错:label 亦可为 outcome;缺省升/降级列一律补 0。
## 整数域列:兼容备用列名;空白/非数字单元格一律当 0(否则 ma_grade 遇 NA 崩溃)
gint <- function(name, alt = NULL) {
  raw <- if (name %in% names(df)) df[[name]]
         else if (!is.null(alt) && alt %in% names(df)) df[[alt]]
         else rep(0, nrow(df))
  v <- suppressWarnings(as.integer(raw)); v[is.na(v)] <- 0L; v
}
lab_vec <- if ("label" %in% names(df)) df[["label"]] else if ("outcome" %in% names(df)) df[["outcome"]] else paste("Outcome", seq_len(nrow(df)))
design_vec <- if ("design" %in% names(df)) tolower(trimws(df[["design"]])) else rep("rct", nrow(df))
design_vec[is.na(design_vec) | !design_vec %in% c("rct", "observational")] <- "rct"   # 非法/空 design 兜底为 rct
rob_v   <- gint("rob");           incon_v <- gint("inconsistency")
indir_v <- gint("indirectness");  imp_v   <- gint("imprecision")
pb_v    <- gint("pubbias", "pub_bias")
le_v    <- gint("large_effect");  dr_v    <- gint("dose_response")
cp_v    <- gint("plausible_confounding", "conf_plausible")

## ---- 逐行 GRADE 评级(工具包 ma_grade,纯 GRADE 代数:Guyatt 2011)----
cat("Step 2/3: 逐结局 GRADE 证据分级...\n")
rows <- vector("list", nrow(df))
for (i in seq_len(nrow(df))) {
  rows[[i]] <- ma_grade(lab_vec[i], design = design_vec[i],
                        rob = rob_v[i], inconsistency = incon_v[i],
                        indirectness = indir_v[i], imprecision = imp_v[i],
                        pub_bias = pb_v[i],
                        large_effect = le_v[i], dose_response = dr_v[i],
                        conf_plausible = cp_v[i], verbose = TRUE)
}

## ---- 汇总 SoF 表 -> CSV ----
cat("Step 3/3: 汇总 Summary-of-Findings 表 + 渲染表图...\n")
sof <- ma_sof_table(rows, out = file.path(outdir, "sof.csv"))
print(sof)

## ---- 额外:把 SoF 表渲成一张 PNG(界面目前仅显示 PNG)----
ok_png <- FALSE
if (requireNamespace("gridExtra", quietly = TRUE) &&
    requireNamespace("ggplot2",   quietly = TRUE) &&
    requireNamespace("grid",      quietly = TRUE)) {
  tryCatch({
    disp <- sof
    ## 表头改成更可读的中英标签
    hdr <- c(outcome = "Outcome", design = "Design", starting = "Start",
             rob = "RoB", inconsistency = "Incons.", indirectness = "Indir.",
             imprecision = "Imprec.", pub_bias = "PubBias", upgrades = "Upgrade",
             certainty = "Certainty")
    names(disp) <- ifelse(names(disp) %in% names(hdr), hdr[names(disp)], names(disp))
    th <- gridExtra::ttheme_minimal(
      core = list(fg_params = list(cex = 0.8),
                  bg_params = list(fill = c("#f7f7f7", "#ffffff"), col = "#dddddd")),
      colhead = list(fg_params = list(cex = 0.85, fontface = "bold", col = "#ffffff"),
                     bg_params = list(fill = "#2c3e50", col = "#2c3e50")))
    g <- gridExtra::tableGrob(disp, rows = NULL, theme = th)
    w <- max(6, 0.9 * ncol(disp)); h <- max(2.2, 0.5 * (nrow(disp) + 1.5))
    ggplot2::ggsave(file.path(outdir, "sof_table.png"), g,
                    width = w, height = h, dpi = 150, limitsize = FALSE)
    ok_png <- TRUE
    cat("  wrote sof_table.png\n")
  }, error = function(e) cat("  (表图渲染失败,仅出 CSV:", conditionMessage(e), ")\n"))
} else {
  cat("  (未安装 gridExtra/ggplot2,界面暂不显示表格,仅出 sof.csv)\n")
}

cat(sprintf("完成。SoF 表写入 %s(sof.csv%s)。\n", outdir,
            if (ok_png) " + sof_table.png" else ""))
