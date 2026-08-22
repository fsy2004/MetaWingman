suppressWarnings(suppressMessages(library(metafor)))

args <- commandArgs(trailingOnly = TRUE)
getarg <- function(name, default = NA_character_) {
  hit <- which(args == paste0("--", name))
  if (length(hit) == 0 || hit[length(hit)] == length(args)) return(default)
  args[hit[length(hit)] + 1]
}

input <- getarg("input")
outdir <- getarg("outdir")
method <- getarg("method", "REML")
knha <- tolower(getarg("knha", "true")) %in% c("true", "1", "yes")
if (is.na(input) || is.na(outdir)) stop("--input and --outdir are required")
dir.create(outdir, recursive = TRUE, showWarnings = FALSE)
dat <- read.csv(input, stringsAsFactors = FALSE, check.names = FALSE)
if (!all(c("study_id", "yi", "vi") %in% names(dat))) stop("input requires study_id, yi, vi")
if (nrow(dat) < 2 || any(!is.finite(dat$yi)) || any(!is.finite(dat$vi)) || any(dat$vi <= 0)) {
  stop("verified-effects analysis requires at least two finite effects with positive variance")
}
fit <- metafor::rma(yi = yi, vi = vi, data = dat, method = method,
                    test = if (knha) "knha" else "z")
row <- data.frame(
  k = fit$k, estimate = as.numeric(fit$b), se = fit$se,
  ci_lower = fit$ci.lb, ci_upper = fit$ci.ub,
  prediction_lower = if (!is.null(fit$pi.lb)) fit$pi.lb else NA_real_,
  prediction_upper = if (!is.null(fit$pi.ub)) fit$pi.ub else NA_real_,
  tau2 = fit$tau2, I2 = fit$I2, Q = fit$QE, Q_p = fit$QEp,
  method = method, test = if (knha) "Knapp-Hartung" else "z"
)
write.csv(row, file.path(outdir, "synthesis-summary.csv"), row.names = FALSE)
