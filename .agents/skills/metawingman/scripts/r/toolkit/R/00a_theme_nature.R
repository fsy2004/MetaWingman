## =====================================================================
## 00a_theme_nature.R — ONE Nature-journal figure standard for the whole
## toolkit (both ggplot2 AND base graphics), plus the embedded-Arial device.
## ---------------------------------------------------------------------
## Every figure Meta Wingman emits (forest, contour funnel, SROC, network
## graph, bubble meta-regression, Baujat, rankogram, posterior density,
## PRISMA, RoB traffic-light, ...) must look like it came off the same press.
## Two rendering engines are in play:
##   * base graphics  — metafor::forest/funnel/regplot, meta::drapery,
##                       netmeta::netgraph, mada SROC, bayesmeta plots
##   * ggplot2         — robvis RoB, rankograms, any ggplot panel
## This file gives BOTH a shared look, anchored to Nature's own artwork
## specification, and a single embedded-Arial vector device (`mw_pdf`) so
## the two engines are visually indistinguishable in the final PDF.
##
## Nature "Guide to Preparing Final Artwork" (Nature branded research
## journals) + the Nature research-figure guide specify:
##   * Typeface  : sans-serif, Helvetica or Arial, ONE font throughout.
##   * Text size : max 7 pt, min 5 pt (all lettering at FINAL print size).
##   * Panel tag : a, b, c ... in 8 pt BOLD, upright, lowercase.
##   * Line/stroke weight: 0.25–1 pt at final size (thinner than 0.25 pt
##                 can drop out in print). Hairlines 0.25 pt; data/axes 0.5 pt.
##   * Width     : original-research 1-column = 88 mm, 2-column = 180 mm
##                 (the historically quoted 89 mm / 183 mm is the same slot).
##   * Colour    : RGB; keep palettes colour-blind safe (Okabe-Ito default).
##   * Ticks     : real tick marks on the axes; units in the axis label.
##   * Format    : vector (AI/EPS/PDF) for line art; >=300 dpi for bitmaps.
##   * No chart-junk: no bold plot titles, no gridlines-as-decoration, no
##                 3-D, no drop shadows, no boxed legends.
## Sources are listed in docs/TOP_JOURNAL_STANDARDS.md.
##
## Load order: sorts to just after 00_device.R, so in the vendored app the
## real cairo device wins; standalone it self-provides `mw_pdf`.
## Depends (soft): ggplot2 for theme_nature(); systemfonts/ragg optional.
## =====================================================================

## --- machine-readable copy of the spec (single source of truth) -------
NATURE_SPEC <- list(
  font          = "Arial",          # falls back to Helvetica / sans if absent
  font_max_pt   = 7,                # Nature: maximum lettering size
  font_min_pt   = 5,                # Nature: minimum lettering size
  panel_tag_pt  = 8,                # a, b, c panel labels, bold upright
  line_data_pt  = 0.5,              # data lines, axis rules
  line_hair_pt  = 0.25,             # hairlines / tick marks (Nature minimum)
  width_single_mm = 88,             # 1-column (research content)
  width_double_mm = 180,            # 2-column (research content)
  width_single_mm_legacy = 89,      # widely quoted equivalent
  width_double_mm_legacy = 183,
  dpi_bitmap    = 300,              # halftone / photographs
  ## Okabe-Ito colour-blind-safe qualitative palette (Okabe & Ito 2008)
  palette = c("#000000", "#E69F00", "#56B4E9", "#009E73",
              "#F0E442", "#0072B2", "#D55E00", "#CC79AC")
)

## font actually used (override globally with options(mw.font = "Helvetica"))
.nature_font <- function() getOption("mw.font", NATURE_SPEC$font)

## mm -> inches (grDevices device widths are in inches)
mm2in <- function(mm) mm / 25.4

## Canonical figure width in INCHES. Pass "single"/"double" or a number (mm).
nature_width_in <- function(size = c("single", "double")) {
  if (is.numeric(size)) return(mm2in(size))
  size <- match.arg(size)
  mm2in(if (size == "single") NATURE_SPEC$width_single_mm
        else                  NATURE_SPEC$width_double_mm)
}

## ---------------------------------------------------------------------
## (c) ONE device for every adapter: embedded-Arial cairo vector PDF.
## `mw_pdf` is the app's device; define it here only if absent so a
## stand-alone checkout of the toolkit is self-contained. cairo_pdf
## EMBEDS glyphs as outlines, so the Arial rendering is identical on any
## viewer / OS — no font substitution, no missing-glyph boxes for τ² ≤ ×.
## ---------------------------------------------------------------------
if (!exists("mw_pdf", mode = "function")) {
  mw_pdf <- function(filename, ..., family = getOption("mw.font", "Arial")) {
    if (isTRUE(capabilities("cairo")))
      grDevices::cairo_pdf(filename = filename, ..., family = family)
    else
      grDevices::pdf(file = filename, ...)   # last-resort, no Arial embed
  }
}

## Make sure "Arial" resolves; on Linux/CI fall back to Helvetica, then sans.
## Also registers Arial with systemfonts so ragg/gg raster previews match.
nature_register_fonts <- function() {
  want <- .nature_font()
  resolved <- want                       # assume the wanted font is present
  if (requireNamespace("systemfonts", quietly = TRUE)) {
    fams <- tryCatch(systemfonts::system_fonts()$family, error = function(e) character())
    if (length(fams) && !(want %in% fams)) {                 # not installed -> fall back
      resolved <- if ("Helvetica" %in% fams) "Helvetica"
                  else if ("Arimo" %in% fams) "Arimo"        # metric-compatible Arial
                  else "sans"
    }
  }
  options(mw.font = resolved)            # always deterministic
  invisible(resolved)
}

## Open the Nature vector device at a canonical width and apply base par().
## Every base-graphics adapter can standardise by replacing its bare
## mw_pdf()/pdf() with nature_pdf().  pointsize = 7 makes cex = 1 == 7 pt.
##   out    : output .pdf path
##   size   : "single"/"double" or width in mm
##   height : figure height in mm (default keeps a 4:3-ish panel)
nature_pdf <- function(out, size = "single", height_mm = NULL, pointsize = 7, ...) {
  w_in <- nature_width_in(size)
  if (is.null(height_mm)) height_mm <- (if (is.numeric(size)) size else
                                        if (size == "double") NATURE_SPEC$width_double_mm
                                        else NATURE_SPEC$width_single_mm) * 0.75
  dir.create(dirname(out), recursive = TRUE, showWarnings = FALSE)
  mw_pdf(out, width = w_in, height = mm2in(height_mm), pointsize = pointsize, ...)
  nature_base()      # apply the look immediately, before the plot call
  invisible(out)
}

## 300-dpi raster preview that matches the vector PDF (ragg + same Arial).
nature_png <- function(out, size = "single", height_mm = NULL,
                       dpi = NATURE_SPEC$dpi_bitmap, pointsize = 7, ...) {
  w_in <- nature_width_in(size)
  if (is.null(height_mm)) height_mm <- (if (is.numeric(size)) size else
                                        if (size == "double") NATURE_SPEC$width_double_mm
                                        else NATURE_SPEC$width_single_mm) * 0.75
  dir.create(dirname(out), recursive = TRUE, showWarnings = FALSE)
  if (requireNamespace("ragg", quietly = TRUE)) {
    ragg::agg_png(out, width = w_in, height = mm2in(height_mm), units = "in",
                  res = dpi, background = "white", ...)
  } else {
    grDevices::png(out, width = w_in, height = mm2in(height_mm), units = "in",
                   res = dpi, type = "cairo", family = .nature_font())
  }
  nature_base()
  invisible(out)
}

## ---------------------------------------------------------------------
## (b) BASE-GRAPHICS look: call once, right after the device is open and
## BEFORE the plot command. Sets Arial, Nature line/tick geometry, no
## chart-junk. Returns the cex multipliers to hand to metafor::forest(),
## funnel(), regplot(), netgraph(), mada plots, etc. (cex is relative to
## the device pointsize; open the device at pointsize = 7 so cex 1 == 7pt).
## ---------------------------------------------------------------------
nature_base <- function(lwd_data = NATURE_SPEC$line_data_pt,
                        lwd_hair = NATURE_SPEC$line_hair_pt) {
  ## grDevices lwd unit = 1/96 inch = 0.75 pt, so pt -> lwd is pt/0.75.
  pt2lwd <- function(pt) pt / 0.75
  graphics::par(
    family   = .nature_font(),
    cex.main = 1.0, font.main = 1,          # titles NOT bold (no chart-junk)
    cex.lab  = 1.0, cex.axis = 6/7,          # axis titles 7 pt, ticks ~6 pt
    lwd      = pt2lwd(lwd_data),             # 0.5 pt data / axis rules
    tcl      = -0.30,                        # short outward ticks
    mgp      = c(1.8, 0.45, 0),              # title/label/line spacing, tight
    las      = 1,                            # horizontal tick labels
    xaxs     = "r", yaxs = "r",
    col.axis = "black", col.lab = "black", fg = "black",
    mar      = c(3.2, 3.4, 1.2, 0.8) + 0.1   # tight, room for one axis title
  )
  ## values the plot functions want passed explicitly
  invisible(list(
    cex      = 6/7,                          # forest/funnel body text ~6 pt
    cex.axis = 6/7,
    lwd      = pt2lwd(lwd_data),
    lwd.hair = pt2lwd(lwd_hair),
    tcl      = -0.30,
    font     = .nature_font(),
    pal      = NATURE_SPEC$palette
  ))
}

## ---------------------------------------------------------------------
## (a) GGPLOT2 look: theme_nature(). A minimal, chart-junk-free theme at
## final print size (points are literal pt in ggplot text elements;
## element_line linewidth is mm, so pt -> linewidth is pt/ggplot2::.pt).
##   base_size : body text pt (default 7 = Nature max; 6 for dense panels)
##   border    : FALSE = L-shaped axis lines (default); TRUE = thin box
##   grid      : "none" (default) | "y" | "x" | "both" (faint 0.25 pt)
## Panel labels a,b,c come from patchwork::plot_annotation(tag_levels="a")
## and are styled here via plot.tag = 8 pt bold.
## ---------------------------------------------------------------------
theme_nature <- function(base_size = NATURE_SPEC$font_max_pt,
                        base_family = .nature_font(),
                        border = FALSE, grid = c("none", "y", "x", "both")) {
  if (!requireNamespace("ggplot2", quietly = TRUE))
    stop("theme_nature() needs the ggplot2 package.")
  grid <- match.arg(grid)
  el   <- ggplot2::element_line
  et   <- ggplot2::element_text
  eb   <- ggplot2::element_blank
  pt   <- ggplot2::.pt                       # pt = mm * .pt  ->  mm = pt/.pt
  ln   <- function(p) NATURE_SPEC[[p]] / pt  # pt line weight -> ggplot mm
  small <- base_size - 1                     # tick labels ~6 pt when base 7

  gridline <- el(colour = "grey92", linewidth = ln("line_hair_pt"))
  th <- ggplot2::theme(
    line  = el(colour = "black", linewidth = ln("line_data_pt"), lineend = "round"),
    rect  = ggplot2::element_rect(fill = NA, colour = NA),
    text  = et(family = base_family, colour = "black", size = base_size,
               lineheight = 0.9),
    ## axes -----------------------------------------------------------
    axis.line        = if (border) eb() else el(linewidth = ln("line_data_pt")),
    axis.ticks       = el(linewidth = ln("line_hair_pt")),
    axis.ticks.length = ggplot2::unit(2, "pt"),
    axis.text        = et(size = small, colour = "black"),
    axis.title       = et(size = base_size),
    ## panel ----------------------------------------------------------
    panel.background = eb(),
    panel.border     = if (border) ggplot2::element_rect(fill = NA, colour = "black",
                                                         linewidth = ln("line_data_pt")) else eb(),
    panel.grid.major = if (grid %in% c("both")) gridline else eb(),
    panel.grid.major.y = if (grid %in% c("y")) gridline else NULL,
    panel.grid.major.x = if (grid %in% c("x")) gridline else NULL,
    panel.grid.minor = eb(),
    ## legend (no box, compact) --------------------------------------
    legend.background = eb(), legend.key = eb(),
    legend.text  = et(size = small), legend.title = et(size = base_size),
    legend.key.size = ggplot2::unit(9, "pt"),
    legend.ticks = el(linewidth = ln("line_hair_pt")),
    ## titles: plain, left, small — NOT bold (no chart-junk) ----------
    plot.title    = et(size = base_size, face = "plain", hjust = 0),
    plot.subtitle = et(size = small, face = "plain", hjust = 0),
    plot.caption  = et(size = NATURE_SPEC$font_min_pt, colour = "grey30", hjust = 1),
    ## panel labels a, b, c: 8 pt bold upright ------------------------
    plot.tag      = et(size = NATURE_SPEC$panel_tag_pt, face = "bold"),
    plot.tag.position = c(0, 1),
    ## facets ---------------------------------------------------------
    strip.background = eb(), strip.text = et(size = base_size, face = "plain"),
    plot.margin = ggplot2::margin(3, 3, 3, 3, unit = "pt"),
    complete = TRUE
  )
  th
}

## Colour-blind-safe scales (Okabe-Ito). British + American spellings.
nature_pal <- function(n = NULL) { p <- NATURE_SPEC$palette; if (is.null(n)) p else rep_len(p, n) }
scale_colour_nature <- function(...) ggplot2::scale_colour_manual(values = NATURE_SPEC$palette, ...)
scale_color_nature  <- scale_colour_nature
scale_fill_nature   <- function(...) ggplot2::scale_fill_manual(values = NATURE_SPEC$palette, ...)

## ggsave wrapper: canonical width, embedded-Arial cairo, correct height.
## Use for any ggplot adapter output so it matches the base-graphics ones.
nature_ggsave <- function(out, plot = ggplot2::last_plot(), size = "single",
                         height_mm = NULL, ...) {
  w_in <- nature_width_in(size)
  if (is.null(height_mm)) height_mm <- (if (is.numeric(size)) size else
                                        if (size == "double") NATURE_SPEC$width_double_mm
                                        else NATURE_SPEC$width_single_mm) * 0.75
  dir.create(dirname(out), recursive = TRUE, showWarnings = FALSE)
  ggplot2::ggsave(out, plot, width = w_in, height = mm2in(height_mm),
                  units = "in", device = mw_pdf, ...)
  invisible(out)
}
