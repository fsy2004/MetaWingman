## =====================================================================
## 00_device.R — Meta Wingman 统一出图设备
## 全产品所有图形一律经此函数出图,确保:
##   ① cairo 后端(Unicode 安全:≤、τ、× 等符号正常,不再字体回退)
##   ② 统一顶刊标准无衬线字体(默认 Arial;可用 options(mw.font=) 覆盖)
## 工具包与适配脚本里原先的 grDevices::pdf / cairo_pdf 调用已全部改为 mw_pdf。
## 命名参数 filename 兼容两种调用:base R 位置传参 mw_pdf(out, width=, height=)
## 与 ggplot2::ggsave(device = mw_pdf) 的 mw_pdf(filename=, width=, height=)。
## =====================================================================
mw_pdf <- function(filename, ..., family = getOption("mw.font", "Arial")) {
  if (isTRUE(capabilities("cairo"))) {
    grDevices::cairo_pdf(filename = filename, ..., family = family)
  } else {
    ## 极少数 R 未编译 cairo:退回基础 pdf(不传 Arial;Unicode 可能退化,但保证不崩)
    grDevices::pdf(file = filename, ...)
  }
}
