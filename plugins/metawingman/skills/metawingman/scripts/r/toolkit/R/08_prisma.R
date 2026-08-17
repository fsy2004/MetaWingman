## =====================================================================
## 08_prisma.R  —  PRISMA 2020 study-flow diagram (base graphics)
## ---------------------------------------------------------------------
## Draws the PRISMA 2020 flow diagram (Page et al. 2021, BMJ 372:n71)
## for a database-and-registers search, using only base R graphics — no
## PRISMA2020 package, no rsvg/DiagrammeR system dependencies — so it runs
## anywhere and exports a clean vector PDF. Counts are supplied by the user
## (they are review-specific bookkeeping, not estimated data); the function
## validates the arithmetic and warns on inconsistencies.
##
## Depends: none (base R graphics).
## =====================================================================

## internal: draw a bordered box with centered, wrapped text
.pr_box <- function(xc, yc, w, h, text, cex = 0.8, fill = "grey97", border = "grey30") {
  graphics::rect(xc - w/2, yc - h/2, xc + w/2, yc + h/2, col = fill, border = border, lwd = 1.4)
  lines <- unlist(strsplit(text, "\n", fixed = TRUE))
  lines <- unlist(lapply(lines, function(l) strwrap(l, width = floor(w * 2.1))))
  n <- length(lines); lh <- strheight("Ag", cex = cex) * 1.35
  y0 <- yc + (n - 1) / 2 * lh
  for (i in seq_len(n)) graphics::text(xc, y0 - (i - 1) * lh, lines[i], cex = cex)
}
.pr_varrow <- function(xc, y0, y1) graphics::arrows(xc, y0, xc, y1, length = 0.09, lwd = 1.4, col = "grey30")
.pr_harrow <- function(x0, x1, yc) graphics::arrows(x0, yc, x1, yc, length = 0.09, lwd = 1.4, col = "grey30")

## prisma_flow(counts, out): draw & save the flow diagram.
## counts (named list):
##   n_identified            int OR named vector of per-source counts
##   n_duplicates            records removed before screening
##   n_screened, n_excluded_screen
##   n_fulltext_sought, n_fulltext_notretrieved
##   n_fulltext_assessed, n_fulltext_excluded  (named int vector: reason -> n)
##   n_included_studies, n_included_reports
prisma_flow <- function(counts, out = "figures/08_prisma_flow.pdf", cex = 0.8) {
  g <- function(nm, d = 0) if (is.null(counts[[nm]])) d else counts[[nm]]
  ident <- g("n_identified"); ident_total <- sum(ident)
  ident_txt <- if (length(ident) > 1 && !is.null(names(ident)))
      paste0("Records identified (n = ", ident_total, ")\n",
             paste(sprintf("%s n=%d", names(ident), ident), collapse = "; "))
    else paste0("Records identified from\ndatabases/registers (n = ", ident_total, ")")
  excl <- g("n_fulltext_excluded")
  excl_txt <- if (length(excl) && !is.null(names(excl)))
      paste0("Reports excluded (n = ", sum(excl), "):\n",
             paste(sprintf("%s (n=%d)", names(excl), excl), collapse = "\n"))
    else paste0("Reports excluded (n = ", sum(excl), ")")

  ## ---- validate arithmetic (warn, never stop) ----
  chk <- function(cond, msg) if (!isTRUE(cond)) message("PRISMA count check: ", msg)
  chk(g("n_screened") == ident_total - g("n_duplicates"),
      sprintf("screened (%d) != identified (%d) - duplicates (%d)", g("n_screened"), ident_total, g("n_duplicates")))
  chk(g("n_fulltext_assessed") == g("n_fulltext_sought") - g("n_fulltext_notretrieved"),
      "assessed != sought - not retrieved")
  chk(g("n_included_studies") == g("n_fulltext_assessed") - sum(excl),
      "included studies != assessed - excluded")

  mw_pdf(out, width = 9.5, height = 8)
  on.exit(grDevices::dev.off(), add = TRUE)
  graphics::par(mar = c(0.5, 0.5, 0.5, 0.5))
  graphics::plot.new(); graphics::plot.window(xlim = c(0, 100), ylim = c(0, 100))

  xl <- 33; xr <- 76; w <- 40; wr <- 40                     # column centres / widths
  yy <- c(88, 66, 46, 28, 9)                                # main-flow rows
  ## tier labels (left band)
  graphics::text(3, 88, "Identification", srt = 90, cex = 0.95, font = 2, col = "grey35")
  graphics::text(3, 47, "Screening",      srt = 90, cex = 0.95, font = 2, col = "grey35")
  graphics::text(3, 9,  "Included",       srt = 90, cex = 0.95, font = 2, col = "grey35")

  ## main flow (left)
  .pr_box(xl, yy[1], w, 13, ident_txt, cex, fill = "#eef3fa")
  .pr_box(xl, yy[2], w, 9,  paste0("Records screened (n = ", g("n_screened"), ")"), cex)
  .pr_box(xl, yy[3], w, 9,  paste0("Reports sought for retrieval (n = ", g("n_fulltext_sought"), ")"), cex)
  .pr_box(xl, yy[4], w, 9,  paste0("Reports assessed for eligibility (n = ", g("n_fulltext_assessed"), ")"), cex)
  .pr_box(xl, yy[5], w, 11, paste0("Studies included in review (n = ", g("n_included_studies"), ")\n",
                                   "Reports of included studies (n = ", g("n_included_reports"), ")"),
          cex, fill = "#eaf5ee")
  ## exclusions (right)
  .pr_box(xr, yy[1], wr, 9, paste0("Records removed before screening:\nduplicate records (n = ", g("n_duplicates"), ")"), cex, fill = "grey96")
  .pr_box(xr, yy[2], wr, 8, paste0("Records excluded (n = ", g("n_excluded_screen"), ")"), cex, fill = "grey96")
  .pr_box(xr, yy[3], wr, 8, paste0("Reports not retrieved (n = ", g("n_fulltext_notretrieved"), ")"), cex, fill = "grey96")
  eh <- max(9, 4 + 2.1 * max(1, length(excl)))
  .pr_box(xr, yy[4], wr, eh, excl_txt, cex, fill = "grey96")

  ## arrows
  for (i in 1:4) .pr_varrow(xl, yy[i] - c(13,9,9,9)[i]/2, yy[i + 1] + c(9,9,9,11)[i + 1] / 2)
  .pr_harrow(xl + w/2, xr - wr/2, yy[1])
  for (i in 2:4) .pr_harrow(xl + w/2, xr - wr/2, yy[i])
  invisible(counts)
}
