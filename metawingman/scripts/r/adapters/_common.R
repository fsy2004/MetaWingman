## =====================================================================
## _common.R —— 所有 run_*.R 适配脚本共用的样板。
## 各脚本以  source(file.path(<自身目录>, "_common.R"))  载入。工具包本身不改。
## 提供:参数解析(args/getarg)、初始化(mw_init:定位+载入工具包)、
##       PDF→PNG(to_png)、取列(col_of/slab_of)、效应量(mw_escalc)。
## =====================================================================
args <- commandArgs(trailingOnly = TRUE)
getarg <- function(k, d = NA) { i <- which(args == paste0("--", k)); if (length(i) && i[1] < length(args)) args[i[1] + 1] else d }

## 读 CSV:先 UTF-8,失败(如中文 Excel 默认导出的 GBK)自动回退 GBK/GB18030;--encoding 可显式指定。
## 修复:原先裸 read.csv 在 Windows(R 4.2+ 原生 UTF-8)读 GBK 文件会 "invalid multibyte string" 直接崩。
mw_read_csv <- function(path) {
  enc <- getarg("encoding", NA)
  if (!is.na(enc) && nzchar(enc)) { # 显式指定;UTF-8 在 Windows 上标记编码,避免经当前 locale 转码
    if (toupper(enc) %in% c("UTF-8", "UTF8", "UTF-8-BOM"))
      return(read.csv(path, check.names = FALSE, stringsAsFactors = FALSE, encoding = "UTF-8"))
    return(read.csv(path, check.names = FALSE, stringsAsFactors = FALSE, fileEncoding = enc))
  }
  ## 自动:UTF-8 → GBK → GB18030。★读 GBK 文件时 fileEncoding="UTF-8" 不报 error 而是
  ## warning + 返回 0 行,所以必须把 warning / 0 行 也当"该编码不适",回退下一个。
  try_read <- function(e) {
    ok <- TRUE
    df <- tryCatch(
      withCallingHandlers(
        if (e == "UTF-8")
          read.csv(path, check.names = FALSE, stringsAsFactors = FALSE, encoding = "UTF-8")
        else
          read.csv(path, check.names = FALSE, stringsAsFactors = FALSE, fileEncoding = e),
        # 只把"编码类"warning 当作该编码不适;"incomplete final line"(末行无换行)等无关 warning 不算失败,
        # 否则合法 UTF-8(缺末行换行)会被丢弃并落到 latin1 → 中文乱码。
        warning = function(w) {
          if (grepl("invalid|multibyte|byte|encoding|cannot", conditionMessage(w), ignore.case = TRUE))
            ok <<- FALSE
          invokeRestart("muffleWarning")
        }),
      error = function(err) { ok <<- FALSE; NULL })
    if (ok && !is.null(df) && nrow(df) >= 1) df else NULL
  }
  for (e in c("UTF-8", "GBK", "GB18030")) { df <- try_read(e); if (!is.null(df)) return(df) }
  read.csv(path, check.names = FALSE, stringsAsFactors = FALSE, fileEncoding = "latin1")  # 兜底:永不因编码崩
}

## 写可复现脚本 reproduce.R 到 outdir:复制输入为 data.csv、记录确切参数、覆写 commandArgs
## 后 source 适配器 → 在装有工具包的本机可一键重跑复现(RevMan/CMA 都没有此能力)。
mw_write_repro <- function(input, outdir, toolkit) {
  tryCatch({
    ca <- commandArgs(trailingOnly = FALSE)
    hit <- grep("^--file=", ca, value = TRUE)
    script <- if (length(hit)) sub("^--file=", "", hit[1]) else ""
    a <- commandArgs(trailingOnly = TRUE)
    dst <- file.path(outdir, "data.csv")
    if (!is.na(input) && nzchar(input) && file.exists(input) &&
        normalizePath(input, mustWork = FALSE) != normalizePath(dst, mustWork = FALSE))
      file.copy(input, dst, overwrite = TRUE)   # 防自拷贝清空(复现时 input 已是 data.csv)
    a2 <- a
    ii <- which(a2 == "--input");   if (length(ii)) a2[ii + 1] <- "data.csv"
    oi <- which(a2 == "--outdir");  if (length(oi)) a2[oi + 1] <- "."
    ti <- which(a2 == "--toolkit"); if (length(ti)) a2 <- a2[-c(ti, ti + 1)]
    q <- function(x) paste0('"', gsub('(["\\\\])', '\\\\\\1', x), '"')
    args_vec <- paste0("c(", paste(vapply(a2, q, ""), collapse = ", "), ")")
    nf <- function(p) if (nzchar(p)) normalizePath(p, winslash = "/", mustWork = FALSE) else p
    lines <- c(
      "## Meta Wingman —— 复现本次分析 / Reproduce this analysis",
      paste0("## 生成: ", format(Sys.time()), "   分析: ", paste(a, collapse = " ")),
      "## 用法: 在本文件所在目录执行   Rscript reproduce.R",
      "## (需已装好 R 与 Meta Wingman 的 toolkit;本次数据已随附为 data.csv)",
      "",
      paste0('Sys.setenv(META_TOOLKIT = "', nf(toolkit), '")'),
      paste0('.mw_file <- "', nf(script), '"'),
      paste0('.mw_args <- ', args_vec),
      'commandArgs <- function(trailingOnly = TRUE) if (trailingOnly) .mw_args else c(paste0("--file=", .mw_file), .mw_args)',
      'source(.mw_file)',
      "",
      "## 版本信息(排查差异):  print(sessionInfo())"
    )
    writeLines(enc2utf8(lines), file.path(outdir, "reproduce.R"), useBytes = TRUE)
  }, error = function(e) invisible(NULL))
}

## 读 input/outdir/toolkit + 基本校验 + 建输出目录 + 按 00→22 顺序 source 工具包(载入全部函数与 %||% 等依赖)。
## need_toolkit=FALSE 用于不依赖工具包的方法(如 dataprep_msd,仅用 estmeansd)。
mw_init <- function(need_input = TRUE, need_toolkit = TRUE) {
  input   <- getarg("input")
  outdir  <- getarg("outdir", "results")
  toolkit <- getarg("toolkit", Sys.getenv("META_TOOLKIT", unset = ""))
  if (need_input && is.na(input)) stop("需要 --input CSV")
  if (need_toolkit && (!nzchar(toolkit) || !dir.exists(file.path(toolkit, "R"))))
    stop("找不到 meta 工具包,请设 --toolkit <dir> 或环境变量 META_TOOLKIT")
  dir.create(outdir, recursive = TRUE, showWarnings = FALSE)
  try(mw_write_repro(input, outdir, toolkit), silent = TRUE)   # 每次运行自动写可复现脚本
  if (need_toolkit)
    for (f in sort(list.files(file.path(toolkit, "R"), pattern = "\\.R$", full.names = TRUE))) source(f)
  list(input = input, outdir = outdir, toolkit = toolkit)
}

## PDF → PNG(界面仅显示 PNG)
to_png <- function(pdf) { png <- sub("\\.pdf$", ".png", pdf)
  suppressWarnings(pdftools::pdf_convert(pdf, format = "png", dpi = 150, pages = 1, filenames = png, verbose = FALSE)); invisible(png) }

## 从 df 取列(--key 可覆盖列名),缺列即报错
col_of <- function(df, k, d) { v <- getarg(k, d); if (v %in% names(df)) df[[v]] else stop(sprintf("CSV 缺列 '%s'(参数 --%s)", v, k)) }

## 研究标签向量(--slab 指定列;缺则 Study 1..n)
slab_of <- function(df, slabcol) if (slabcol %in% names(df)) as.character(df[[slabcol]]) else paste("Study", seq_len(nrow(df)))

## 统一算效应量(二分类 / 连续 / 相关型);pairwise 与 influence 共用。
## ★先在 escalc 之外解析列:缺列时给清晰报错("CSV 缺列 'm1i'"),
##   不会被 metafor::escalc 的非标准求值(NSE)吞成晦涩的 "Cannot find the object/variable"。
mw_escalc <- function(df, measure) {
  need <- if (measure %in% c("OR", "RR", "RD", "PETO")) c("ai", "bi", "ci", "di")
          else if (measure %in% c("SMD", "MD", "SMDH", "ROM")) c("m1i", "sd1i", "n1i", "m2i", "sd2i", "n2i")
          else if (measure %in% c("ZCOR", "COR")) c("ri", "ni")
          else stop(sprintf("本适配暂不支持 measure=%s(见 es_guide())", measure))
  vals <- lapply(need, function(k) col_of(df, k, k))   # 逐列解析,缺列即在此清晰报错
  names(vals) <- need
  as.data.frame(do.call(metafor::escalc, c(list(measure = measure), vals)))
}
