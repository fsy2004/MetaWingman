## =====================================================================
## 30_evalue.R —— E 值敏感性分析(EValue 包)
## E-value:一个未测量混杂因素若要把观察到的关联完全解释掉(推到无效值),
## 它与暴露、与结局都需达到的最小关联强度(RR 尺度)。越大越稳健。
## 参考 VanderWeele & Ding (2017) Ann Intern Med;实现直接调用 EValue::evalue。
## 支持比值型合并效应:RR / OR / HR(OR、HR 可指定 rare 罕见结局近似)。
## 本文件仅供 run_evalue.R 适配层使用,不改动其他 family 的工具模块。
## =====================================================================

## 单个合并效应 → EValue::evalue 矩阵(行 RR / E-values;列 point/lower/upper)
mw_evalue_one <- function(est, lo = NA, hi = NA, measure = "RR", rare = FALSE, true = 1) {
  measure <- toupper(measure)
  eff <- switch(measure,
    "RR" = EValue::RR(est),
    "OR" = EValue::OR(est, rare = rare),
    "HR" = EValue::HR(est, rare = rare),
    stop(sprintf("E 值适配支持 measure = RR / OR / HR,收到 '%s'", measure)))
  a <- list(est = eff, true = true)
  if (!is.na(lo)) a$lo <- lo
  if (!is.na(hi)) a$hi <- hi
  do.call(EValue::evalue, a)
}

## 一张表:对 CSV 每一行(一个合并效应)算 E 值。
## 返回 data.frame:label, measure, point, lo, hi, evalue_point, evalue_ci
##   evalue_point = 点估计的 E 值;evalue_ci = 置信限(离无效值最近的一端)的 E 值。
mw_evalue_table <- function(df, measure = "RR", rare = FALSE, true = 1,
                            est_col = "est", lo_col = "lo", hi_col = "hi",
                            label_col = "study") {
  for (cc in c(est_col)) if (!cc %in% names(df))
    stop(sprintf("CSV 缺列 '%s'(点估计;可用 --est_col 指定)", cc))
  has_lo <- lo_col %in% names(df); has_hi <- hi_col %in% names(df)
  has_lab <- label_col %in% names(df)
  rows <- lapply(seq_len(nrow(df)), function(i) {
    lo <- if (has_lo) suppressWarnings(as.numeric(df[[lo_col]][i])) else NA
    hi <- if (has_hi) suppressWarnings(as.numeric(df[[hi_col]][i])) else NA
    m  <- mw_evalue_one(as.numeric(df[[est_col]][i]), lo, hi, measure, rare, true)
    ev_ci <- { v <- m["E-values", c("lower", "upper")]; v <- v[!is.na(v)]; if (length(v)) v[1] else NA }
    data.frame(
      label        = if (has_lab) as.character(df[[label_col]][i]) else paste("Estimate", i),
      measure      = measure,
      point        = round(as.numeric(df[[est_col]][i]), 4),
      lo           = if (is.na(lo)) NA else round(lo, 4),
      hi           = if (is.na(hi)) NA else round(hi, 4),
      evalue_point = round(m["E-values", "point"], 4),
      evalue_ci    = if (is.na(ev_ci)) NA else round(ev_ci, 4),
      stringsAsFactors = FALSE)
  })
  do.call(rbind, rows)
}

## E 值偏倚图:画出"要把观察到的 RR 推到无效值,混杂—暴露(RR_EU)与
## 混杂—结局(RR_UD)需满足的联合强度边界曲线",曲线在对角线上的交点即 E 值。
##   曲线:RR_UD = RR(RR-1)/(RR_EU - RR) + RR;交点 (E,E),E = RR + sqrt(RR(RR-1))。
## 与 EValue::bias_plot 同一数学,但 bias_plot 的坐标轴硬编码为 5..40(小 E 值下几乎空白),
## 故这里用 base graphics 自绘并套 Nature 主题(nature_base),坐标随 E 值自适应。
## evmat = mw_evalue_one 的返回矩阵;out = PDF 路径。
mw_evalue_plot <- function(evmat, out, width = 3.6, height = 3.4) {
  rr <- as.numeric(evmat["RR", "point"])
  if (!is.finite(rr) || rr <= 0) rr <- 1
  if (rr < 1) rr <- 1 / rr                                        # 曲线定义在 >1 一侧
  E <- rr + sqrt(rr * (rr - 1))                                   # 点估计 E 值(交点坐标)
  ci <- suppressWarnings(as.numeric(evmat["E-values", c("lower", "upper")]))
  Eci <- { v <- ci[is.finite(ci)]; if (length(v)) v[1] else NA }  # 置信限 E 值(离无效值最近端)
  xmax <- max(ceiling(E * 1.6), 5)
  pal <- NATURE_SPEC$palette

  mw_pdf(out, width = width, height = height)
  on.exit(grDevices::dev.off(), add = TRUE)
  cx <- nature_base()
  x <- seq(rr + (xmax - rr) / 1000, xmax, length.out = 800)
  y <- rr * (rr - 1) / (x - rr) + rr
  plot(NA, xlim = c(1, xmax), ylim = c(1, xmax), xaxs = "i", yaxs = "i",
       xlab = "RR_EU (confounder-exposure)",
       ylab = "RR_UD (confounder-outcome)", main = "")
  graphics::abline(0, 1, lty = 3, lwd = cx$lwd.hair, col = "grey60")   # 对角线
  graphics::lines(x, y, lwd = cx$lwd, col = pal[6])                    # 偏倚边界曲线
  graphics::points(E, E, pch = 19, cex = cx$cex, col = pal[7])         # 点估计 E 值
  graphics::text(E, E, sprintf("E = %.2f", E), pos = 4, offset = 0.4,
                 cex = cx$cex.axis, col = pal[7])
  if (is.finite(Eci) && Eci > 1) {
    graphics::points(Eci, Eci, pch = 1, cex = cx$cex, col = pal[3])    # 置信限 E 值
    graphics::text(Eci, Eci, sprintf("CI: %.2f", Eci), pos = 1, offset = 0.5,
                   cex = cx$cex.axis, col = pal[3])
  }
  invisible(out)
}
