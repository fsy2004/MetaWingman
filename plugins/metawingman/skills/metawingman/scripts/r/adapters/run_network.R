## =====================================================================
## run_network.R —— launcher 适配层(网络 Meta 分析 NMA 家族)。
## 一个适配器靠 --analysis 选择具体叶子输出:先构建 netmeta 重对象一次,
## 再 switch(analysis, ...) 只产出该叶子的图/表。工具包本身不改;
## 此脚本 source 它、读用户 CSV、调 20_network_meta.R + 30_network_extra.R。
##
## --analysis 取值(默认 graph):
##   SPLIT(复用 20_network_meta.R):
##     graph 网络几何图 · forest 网络森林图(vs 参照) · league 联赛表 ·
##     rank SUCRA/P-score 排序 · nodesplit 节点分割(SIDE)一致性
##   NEW(30_network_extra.R):
##     rankogram 秩图 · netheat 设计交互热图 · cadj_funnel 比较校正漏斗 ·
##     component 成分网络meta · cinema 证据确信度(贡献矩阵近似)
##
## 用法:
##   Rscript run_network.R --input network.csv --outdir out --analysis graph \
##           --format contrast --sm MD --reference plac --small_values desirable
##   对比格式(默认): CSV 需列 studlab, treat1, treat2, TE, seTE
##   臂格式: --format arm(需 studlab, treat + 二分类 event,n 或连续 n,mean,sd)
##   工具包路径: --toolkit <dir> 或环境变量 META_TOOLKIT
## =====================================================================
suppressWarnings(suppressMessages({ library(netmeta); library(meta); library(pdftools) }))
## 载入同目录公共样板(getarg / mw_init / to_png)
source(file.path(dirname(sub("^--file=", "", commandArgs(FALSE)[grep("^--file=", commandArgs(FALSE))][1])), "_common.R"))

init <- mw_init(); input <- init$input; outdir <- init$outdir
analysis     <- tolower(getarg("analysis", "graph"))
format       <- tolower(getarg("format", "contrast"))
sm           <- toupper(getarg("sm", "MD"))
reference    <- getarg("reference", "plac")
small_values <- tolower(getarg("small_values", "desirable"))

## ---- 读数据 ----
df <- mw_read_csv(input)
cat(sprintf("run_network: analysis = %s,读入 %d 行(format=%s, sm=%s, reference=%s)\n",
            analysis, nrow(df), format, sm, reference))

## ---- 惰性构建网络 Meta 重对象(仅拟合一次)------------------------------
.net <- NULL
build_net <- function() {
  if (is.null(.net)) {
    nma_args <- list(data = df, format = format, sm = sm, studlab = getarg("studlab", "studlab"))
    if (format == "arm") {                     # 臂格式:转发 treat + (event,n) 或 (n,mean,sd)
      cols <- names(df)
      nma_args$treat <- getarg("treat", "treat")
      ev <- getarg("event", if ("event" %in% cols) "event" else NA)
      mm <- getarg("mean",  if ("mean"  %in% cols) "mean"  else NA)
      ss <- getarg("sd",    if ("sd"    %in% cols) "sd"    else NA)
      nn <- getarg("n",     if ("n"     %in% cols) "n"     else NA)
      if (!is.na(ev)) nma_args$event <- ev
      if (!is.na(mm)) nma_args$mean  <- mm
      if (!is.na(ss)) nma_args$sd    <- ss
      if (!is.na(nn)) nma_args$n     <- nn
      nma_args$allstudies <- TRUE
      treats <- unique(as.character(df[[nma_args$treat]]))
    } else {                                   # 对比格式
      nma_args$treat1 <- getarg("treat1", "treat1"); nma_args$treat2 <- getarg("treat2", "treat2")
      nma_args$TE <- getarg("TE", "TE"); nma_args$seTE <- getarg("seTE", "seTE")
      treats <- unique(c(as.character(df[[nma_args$treat1]]), as.character(df[[nma_args$treat2]])))
    }
    ## 参考处理不在数据中会让 netmeta 崩 → 回退到 netmeta 默认参考
    nma_args$reference <- if (nzchar(reference) && reference %in% treats) reference else ""
    if (nzchar(reference) && !(reference %in% treats))
      cat(sprintf("  (参考处理 '%s' 不在数据中,改用 netmeta 默认参考)\n", reference))
    .net <<- do.call(nma_run, nma_args)
  }
  .net
}

switch(analysis,

  ## ===================== SPLIT:复用 20_network_meta.R =================
  "graph" = {
    net <- build_net(); print(net)
    f <- file.path(outdir, "netgraph.pdf"); nma_graph(net, f); to_png(f)
  },

  "forest" = {
    net <- build_net()
    f <- file.path(outdir, "nma_forest.pdf")
    nma_forest_ref(net, f, reference = if (nzchar(reference)) reference else NULL); to_png(f)
  },

  "league" = {
    net <- build_net()
    nma_league(net, out = file.path(outdir, "league.csv"))
  },

  "rank" = {
    net <- build_net()
    f <- file.path(outdir, "pscore_cumrank.pdf")
    tab <- nma_rank(net, small.values = small_values, out = f); to_png(f)
    write.csv(tab, file.path(outdir, "pscore_ranking.csv"), row.names = FALSE)
    print(tab)
  },

  "nodesplit" = {
    net <- build_net()
    f <- file.path(outdir, "netsplit.pdf")
    ns <- nma_inconsistency(net, out = f); to_png(f)
    ## 汇总直接/间接证据对比(SIDE)为 CSV:仅保留含直接证据的比较
    dr <- ns$direct.random; ir <- ns$indirect.random; cr <- ns$compare.random
    keep <- !is.na(dr$TE)
    tab <- data.frame(
      comparison        = dr$comparison[keep],
      direct.TE         = dr$TE[keep],
      direct.p          = dr$p[keep],
      indirect.TE       = ir$TE[keep],
      indirect.p        = ir$p[keep],
      difference.TE     = cr$TE[keep],
      difference.p      = cr$p[keep],
      row.names = NULL, stringsAsFactors = FALSE)
    write.csv(tab, file.path(outdir, "nodesplit.csv"), row.names = FALSE)
    print(tab)
  },

  ## ===================== NEW:30_network_extra.R =======================
  "rankogram" = {
    net <- build_net()
    f <- file.path(outdir, "rankogram.pdf")
    rg <- nma_rankogram_plot(net, f, small.values = small_values, cumulative = FALSE); to_png(f)
    mat <- as.data.frame(rg$ranking.matrix.random)
    mat <- cbind(treatment = rownames(mat), mat)
    write.csv(mat, file.path(outdir, "rankogram_probabilities.csv"), row.names = FALSE)
  },

  "netheat" = {
    net <- build_net()
    f <- file.path(outdir, "netheat.pdf")
    drawn <- nma_netheat(net, f)
    if (drawn) { to_png(f); cat("  (net heat 图已绘制)\n") }
    else cat("  (netheat 需多个含独立信息的设计, 星形网络无法绘制, 跳过图)\n")
    ## 无论图是否成功, 均输出 Q 分解表(design-by-treatment 一致性检验)
    dd <- netmeta::decomp.design(net)
    qd <- as.data.frame(dd$Q.decomp); qd <- cbind(source = rownames(qd), qd)
    write.csv(qd, file.path(outdir, "design_Q_decomposition.csv"), row.names = FALSE)
    print(dd$Q.decomp)
  },

  "cadj_funnel" = {
    net <- build_net()
    f <- file.path(outdir, "cadj_funnel.pdf")
    nma_cadj_funnel(net, f, small.values = small_values); to_png(f)
  },

  "component" = {
    net <- build_net()
    f <- file.path(outdir, "component_forest.pdf")
    tab <- nma_component(net, out = f); to_png(f)
    write.csv(tab, file.path(outdir, "component_effects.csv"), row.names = FALSE)
    print(tab)
  },

  "cinema" = {
    net <- build_net()
    f <- file.path(outdir, "contribution_matrix.pdf")
    tab <- nma_contrib(net, out = f); to_png(f)
    write.csv(tab, file.path(outdir, "contribution_matrix.csv"), row.names = FALSE)
  },

  stop(sprintf("未知 --analysis '%s'(见脚本头注释)", analysis))
)

cat(sprintf("完成:analysis=%s → %s\n", analysis, outdir))
