## =====================================================================
## 30_sequential.R —— 试验序贯分析 (Trial Sequential Analysis) 与所需信息量
## (Required Information Size, RIS)。封装 RTSA 包 (Riberholt et al.,
## BMC Med Res Methodol 2024) 的 RTSA()/plot 与 required-information-size
## 计算,供 run_sequential.R 适配器复用。
##
## 供的函数:
##   seq_fit()        —— 对二分类结局数据跑一次 RTSA(type="analysis"),
##                       得到含边界(bounds)、RIS、逐步统计量的重对象。
##   seq_tsa_plot()   —— 序贯监测边界图(Z 曲线 vs O'Brien-Fleming 边界),
##                       RTSA 的 plot 方法返回 ggplot,叠加 Nature 主题后出图。
##   seq_bounds_df()  —— 逐次分析的时序/边界/检验统计量表 (data.frame)。
##   seq_ris_df()     —— 所需信息量汇总表:已累积样本量(AIS) vs 固定效应
##                       RIS 及按 tau^2 / D^2 / I^2 异质性校正后的 RIS。
##   seq_ris_plot()   —— 上表的 lollipop(棒棒糖)图,对数横轴(替代条形图)。
##
## 依赖:RTSA, ggplot2;Nature 主题函数 (theme_nature/nature_ggsave/nature_pal)
##       由 00a_theme_nature.R 提供,已在工具包加载链中。
## =====================================================================

## ---- 一次性拟合:二分类结局的 TSA 分析对象 ----
## df 需含列 eI,nI,eC,nC(处理组事件/样本、对照组事件/样本),可选 study 标签列。
##   outcome : "RR" | "OR" | "RD"
##   mc      : 最小临床相关值(RR/OR 为比值如 0.8;RD 为差值)
##   side    : 1 或 2(单/双侧)
##   alpha,beta : I/II 类错误
##   es_alpha: alpha-spending 函数("esOF" O'Brien-Fleming / "esPoc" Pocock)
##   futility: "none" | "non-binding" | "binding"
seq_fit <- function(df, outcome = "RR", mc = 0.8, side = 2,
                    alpha = 0.05, beta = 0.1, es_alpha = "esOF",
                    futility = "none", weights = "MH", re_method = "DL_HKSJ") {
  need <- c("eI", "nI", "eC", "nC")
  miss <- setdiff(need, names(df))
  if (length(miss))
    stop(sprintf("TSA 需要二分类结局列 %s,CSV 缺少:%s",
                 paste(need, collapse = "/"), paste(miss, collapse = ",")))
  df$eI <- as.numeric(df$eI); df$nI <- as.numeric(df$nI)
  df$eC <- as.numeric(df$eC); df$nC <- as.numeric(df$nC)
  fit <- RTSA::RTSA(type = "analysis", outcome = outcome, data = df,
                    mc = mc, side = side, alpha = alpha, beta = beta,
                    es_alpha = es_alpha, futility = futility, fixed = FALSE,
                    weights = weights, re_method = re_method)
  fit
}

## ---- 序贯监测边界图(TSA 图)----
## RTSA 的 plot() 返回 ggplot;叠加 Nature 主题并存 PDF→PNG。
seq_tsa_plot <- function(fit, out) {
  if (!requireNamespace("ggplot2", quietly = TRUE))
    stop("seq_tsa_plot() 需要 ggplot2。")
  p <- graphics::plot(fit)                        # RTSA:::plot.RTSA -> ggplot
  p <- p + theme_nature(base_size = 7)
  nature_ggsave(out, plot = p, size = "double", height_mm = 120)
  invisible(out)
}

## ---- 逐次分析的时序/边界/检验统计量表 ----
seq_bounds_df <- function(fit) {
  rd <- fit$results$results_df
  keep <- intersect(c("sma_timing", "upper", "lower", "fut_upper", "fut_lower",
                       "z_fixed", "z_random", "outcome_fixed", "outcome_random",
                       "pvalues_fixed", "pvalues_random"), names(rd))
  out <- rd[, keep, drop = FALSE]
  ## 圆整,便于表格阅读
  num <- vapply(out, is.numeric, logical(1))
  out[num] <- lapply(out[num], function(x) round(x, 4))
  out
}

## ---- 所需信息量 (RIS) 汇总表 ----
## 返回:统计量名 + 参与者数 + 说明。已累积 AIS 与不同异质性校正下的 RIS。
seq_ris_df <- function(fit) {
  res <- fit$results; ris <- fit$ris
  g <- function(x) if (is.null(x) || !is.finite(suppressWarnings(as.numeric(x)[1]))) NA_real_ else round(as.numeric(x)[1])
  rows <- list(
    c("Accrued information size (AIS)",           g(res$AIS),
      "研究已累积的信息量(总样本量)"),
    c("Fixed-effect RIS",                          g(ris$SMA_NF %||% res$RIS),
      "固定效应模型所需信息量"),
    c("Heterogeneity-adjusted RIS (tau^2)",        g(ris$SMA_tau2_full %||% res$HARIS),
      "按 tau^2 校正(随机效应)所需信息量"),
    c("Diversity-adjusted RIS (D^2)",              g(ris$SMA_D2_full),
      "按 D^2(多样性)校正所需信息量"),
    c("Inconsistency-adjusted RIS (I^2)",          g(ris$SMA_I2_full),
      "按 I^2(不一致性)校正所需信息量")
  )
  out <- as.data.frame(do.call(rbind, rows), stringsAsFactors = FALSE)
  names(out) <- c("statistic", "participants", "description")
  out$participants <- as.numeric(out$participants)
  out
}

## ---- RIS lollipop 图(对数横轴,顶刊风格,替代条形图)----
seq_ris_plot <- function(ris_df, out) {
  if (!requireNamespace("ggplot2", quietly = TRUE))
    stop("seq_ris_plot() 需要 ggplot2。")
  d <- ris_df[is.finite(ris_df$participants) & ris_df$participants > 0, , drop = FALSE]
  d$statistic <- factor(d$statistic, levels = rev(d$statistic))
  pal <- nature_pal(nrow(d))
  ## log 轴上 lollipop 的公共基线:取小于最小值的整十次幂,避免 log10(0)=-Inf。
  x0 <- 10 ^ floor(log10(min(d$participants)))
  p <- ggplot2::ggplot(d, ggplot2::aes(x = participants, y = statistic)) +
    ggplot2::geom_segment(ggplot2::aes(x = x0, xend = participants,
                                       y = statistic, yend = statistic,
                                       colour = statistic),
                          linewidth = NATURE_SPEC$line_data_pt / ggplot2::.pt) +
    ggplot2::geom_point(ggplot2::aes(colour = statistic), size = 2) +
    ggplot2::geom_text(ggplot2::aes(label = formatC(participants, format = "d", big.mark = ",")),
                       hjust = -0.15, size = 5 / ggplot2::.pt) +
    ggplot2::scale_x_continuous(trans = "log10",
                                expand = ggplot2::expansion(mult = c(0.02, 0.25))) +
    ggplot2::scale_colour_manual(values = pal, guide = "none") +
    ggplot2::labs(x = "Required participants (log scale)", y = NULL,
                  title = "Required information size") +
    theme_nature(base_size = 7)
  nature_ggsave(out, plot = p, size = "double", height_mm = 70)
  invisible(out)
}
