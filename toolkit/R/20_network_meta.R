## =====================================================================
## 20_network_meta.R  —  Frequentist network meta-analysis (netmeta)
## ---------------------------------------------------------------------
## Multiple treatments compared simultaneously by combining direct and
## indirect evidence in one coherent model. Every function is a thin,
## honest wrapper around the `netmeta` package — no re-implemented maths.
##
## Methods & primary references:
##   * Graph-theoretical / electrical-network NMA model
##       Rücker G (2012), Res Synth Methods 3:312-324.
##   * `netmeta` software
##       Balduzzi S, Rücker G, Nikolakopoulou A, et al. (2023),
##       J Stat Softw 106:1-40.
##   * P-score (frequentist analogue of SUCRA) for treatment ranking
##       Rücker G & Schwarzer G (2015), BMC Med Res Methodol 15:58.
##   * Rankogram / (cumulative) ranking probabilities
##       Salanti G, Ades AE, Ioannidis JPA (2011), J Clin Epidemiol 64:163.
##   * Direct/indirect evidence separation (SIDE / node-splitting,
##       "back-calculation") for local inconsistency
##       Dias S, Welton NJ, Caldwell DM, Ades AE (2010), Stat Med 29:932;
##       König J, Krahn U, Binder H (2013), Stat Med 32:5414 (net heat).
##   * League table of all pairwise estimates
##       Rücker & Schwarzer (2015), as above.
##
## Arm-format data are first converted to treatment contrasts with
## meta::pairwise() (Balduzzi 2023). NOTE: as of netmeta 3.x / meta 8.x,
## pairwise() is exported by `meta`, not `netmeta`.
##
## Depends: netmeta, meta. Composes with the toolkit foundation
## (00_data_prep.R -> 01_effect_sizes.R -> 02_pairwise_meta.R); it uses
## the `%||%` helper defined there, with a local fallback if sourced alone.
## =====================================================================

if (!exists("%||%", mode = "function"))
  `%||%` <- function(a, b) if (is.null(a)) b else a

## Ensure an output directory exists for a target file path.
.nma_ensure_dir <- function(out) {
  d <- dirname(out)
  if (nzchar(d) && !dir.exists(d)) dir.create(d, recursive = TRUE, showWarnings = FALSE)
  invisible(out)
}

## ---------------------------------------------------------------------
## nma_run(): fit a frequentist NMA from contrast- or arm-format data.
##
## format = "contrast": `data` already holds treatment contrasts. Columns
##   (name overridable) TE, seTE, treat1, treat2, studlab are passed to
##   netmeta::netmeta(). Use for pre-computed effect sizes (e.g. Senn2013).
## format = "arm":      one row per study arm. Columns treat, studlab and
##   EITHER (event, n) for a binary `sm` (OR/RR/RD) OR (n, mean, sd) for a
##   continuous `sm` (MD/SMD) are collapsed to contrasts by meta::pairwise()
##   and then fed to netmeta().
##
## Column arguments are given as strings (default to the conventional
## netmeta names). `reference` sets the reference treatment (""=none, the
## netmeta default). `allstudies` (arm format only) is passed to
## meta::pairwise(): TRUE keeps studies whose comparisons have zero events
## in both arms (needed e.g. for multi-arm trials with a double-zero
## contrast; netmeta's recommended remedy). Extra `...` are forwarded to
## netmeta::netmeta(). Returns the fitted `netmeta` object.
nma_run <- function(data,
                    format    = c("contrast", "arm"),
                    sm,
                    reference = NULL,
                    treat1    = "treat1",
                    treat2    = "treat2",
                    TE        = "TE",
                    seTE      = "seTE",
                    studlab   = "studlab",
                    treat     = "treat",
                    event     = NULL,
                    n         = NULL,
                    mean      = NULL,
                    sd        = NULL,
                    allstudies = FALSE,
                    common    = TRUE,
                    random    = TRUE,
                    ...) {
  format <- match.arg(format)
  if (missing(sm) || is.null(sm)) stop("Provide `sm` (summary measure, e.g. 'MD','OR','RR','SMD').")
  if (!is.data.frame(data)) stop("`data` must be a data.frame.")
  refg <- if (is.null(reference)) "" else reference

  need <- function(cols) {
    miss <- setdiff(cols, names(data))
    if (length(miss)) stop("Column(s) not found in data: ", paste(miss, collapse = ", "))
  }

  if (format == "contrast") {
    need(c(TE, seTE, treat1, treat2, studlab))
    net <- netmeta::netmeta(
      TE      = data[[TE]],
      seTE    = data[[seTE]],
      treat1  = data[[treat1]],
      treat2  = data[[treat2]],
      studlab = data[[studlab]],
      sm      = sm,
      common  = common,
      random  = random,
      reference.group = refg,
      ...)
    return(net)
  }

  ## ---- arm format: build contrasts with meta::pairwise() --------------
  need(c(treat, studlab))
  binary     <- !is.null(event)
  continuous <- !is.null(mean) && !is.null(sd)
  if (binary) {
    if (is.null(n)) stop("Binary arm format needs `event`, `n` and `treat`, `studlab`.")
    need(c(treat, event, n, studlab))
    p <- meta::pairwise(treat   = data[[treat]],
                        event   = data[[event]],
                        n       = data[[n]],
                        studlab = data[[studlab]],
                        sm      = sm,
                        allstudies = allstudies)
  } else if (continuous) {
    if (is.null(n)) stop("Continuous arm format needs `n`, `mean`, `sd` and `treat`, `studlab`.")
    need(c(treat, n, mean, sd, studlab))
    p <- meta::pairwise(treat   = data[[treat]],
                        n       = data[[n]],
                        mean    = data[[mean]],
                        sd      = data[[sd]],
                        studlab = data[[studlab]],
                        sm      = sm,
                        allstudies = allstudies)
  } else {
    stop("Arm format needs either `event`(+`n`) for binary or `mean`+`sd`(+`n`) for continuous outcomes.")
  }
  netmeta::netmeta(p, common = common, random = random,
                   reference.group = refg, ...)
}

## ---------------------------------------------------------------------
## nma_graph(): network geometry plot. Node size ~ per-treatment sample
## size (when available; NULL for contrast data with no n), edge width ~
## number of studies contributing to each direct comparison. -> PDF.
## Returns the net invisibly.
nma_graph <- function(net, out, plastic = FALSE, col = "gray65", ...) {
  stopifnot(inherits(net, "netmeta"))
  .nma_ensure_dir(out)
  ## node sizing: scale by sample size per treatment if the net carries it
  cexp <- 3
  nt <- net$n.trts
  if (!is.null(nt) && all(is.finite(nt))) {
    nt <- nt[net$trts]                       # align to node/label order
    rng <- range(nt, na.rm = TRUE)
    cexp <- if (diff(rng) > 0) 1.6 + 3.2 * (nt - rng[1]) / diff(rng) else 3
  }
  mw_pdf(out, width = 8, height = 7)
  on.exit(grDevices::dev.off(), add = TRUE)
  netmeta::netgraph(net,
                    thickness  = "number.of.studies",  # edge width ~ #studies
                    plastic    = plastic,
                    points     = TRUE,
                    cex.points = cexp,                  # node size ~ sample
                    col        = col,
                    col.points = "#2C6E9B",
                    number.of.studies = TRUE,
                    ...)
  invisible(net)
}

## ---------------------------------------------------------------------
## nma_rank(): P-scores (Rücker & Schwarzer 2015) for every treatment.
## small.values = whether SMALL outcome values are 'desirable' (e.g. lower
## HbA1c is better) or 'undesirable'. If `out` is given, also draw a
## CUMULATIVE rankogram (step/line curves, not bars) to PDF.
## Returns a data.frame of P-scores (random & common), best treatment first.
nma_rank <- function(net,
                     small.values = c("desirable", "undesirable"),
                     out = NULL, ...) {
  stopifnot(inherits(net, "netmeta"))
  small.values <- match.arg(small.values)
  nr <- netmeta::netrank(net, small.values = small.values)

  tab <- data.frame(
    treatment     = names(nr$ranking.random),
    Pscore.random = as.numeric(nr$ranking.random),
    Pscore.common = as.numeric(nr$ranking.common[names(nr$ranking.random)]),
    row.names = NULL, stringsAsFactors = FALSE)
  tab <- tab[order(-tab$Pscore.random), , drop = FALSE]
  rownames(tab) <- NULL

  if (!is.null(out)) {
    .nma_ensure_dir(out)
    rg <- netmeta::rankogram(net, small.values = small.values,
                             cumulative.rankprob = TRUE)
    mw_pdf(out, width = 8, height = 6)
    on.exit(grDevices::dev.off(), add = TRUE)
    graphics::plot(rg, type = "step", ...)   # cumulative rank-prob curves
  }
  tab
}

## ---------------------------------------------------------------------
## nma_league(): full league table of all pairwise estimates + CIs
## (Rücker & Schwarzer 2015). If `out` is given, write the RANDOM-effects
## league matrix (diagonal = treatments, cells = effect [CI]) to CSV.
## Returns the netleague object invisibly.
nma_league <- function(net, out = NULL, digits = 2, ...) {
  stopifnot(inherits(net, "netmeta"))
  nl <- netmeta::netleague(net, digits = digits, ...)
  if (!is.null(out)) {
    .nma_ensure_dir(out)
    utils::write.csv(nl$random, file = out, row.names = FALSE, na = "")
  }
  invisible(nl)
}

## ---------------------------------------------------------------------
## nma_inconsistency(): split each comparison into direct vs indirect
## evidence (SIDE / node-splitting, Dias 2010) to flag local
## inconsistency. If `out` is given, draw the netsplit comparison plot
## (Bland-Altman of direct vs indirect) to PDF. Returns the netsplit obj.
nma_inconsistency <- function(net, out = NULL, ...) {
  stopifnot(inherits(net, "netmeta"))
  ns <- netmeta::netsplit(net)
  if (!is.null(out)) {
    .nma_ensure_dir(out)
    mw_pdf(out, width = 8, height = 7)
    on.exit(grDevices::dev.off(), add = TRUE)
    p <- tryCatch(graphics::plot(ns, ...), error = function(e) e)
    if (inherits(p, "error")) {
      ## fall back to the classic direct-vs-indirect forest if the
      ## Bland-Altman plot is unavailable in this netmeta build.
      ## (`forest` generic is exported by `meta`; netmeta only registers
      ## the S3 method `forest.netsplit`, so call it via `meta`.)
      meta::forest(ns)
    } else if (inherits(p, "ggplot")) {
      print(p)
    }
  }
  ns
}
