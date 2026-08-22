from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

def build_figure(data_path: Path):
    with data_path.open(encoding="utf-8", newline="") as handle:
        data = list(csv.DictReader(handle))
    required = {
        "arm", "arm_group", "target_hit_at_1", "target_hit_at_3",
        "false_opportunity_rate", "selected_count",
    }
    missing = sorted(required - set(data[0] if data else {}))
    if missing:
        raise ValueError(f"missing columns: {missing}")
    if len(data) != 8 or {int(row["selected_count"]) for row in data} != {3}:
        raise ValueError("expected eight locked arms with three selected candidates each")

    mpl.rcParams.update({
        "font.family": "Arial", "font.size": 8, "axes.labelsize": 8,
        "xtick.labelsize": 7, "ytick.labelsize": 7,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
    })
    fig, axes = plt.subplots(
        1, 2, figsize=(7.2, 4.2), sharey=True,
        gridspec_kw={"width_ratios": [1.0, 1.3]}, constrained_layout=True,
    )
    ax_hit, ax_false = axes
    y = np.arange(len(data))
    hit_color = "#0072B2"
    miss_color = "#D9D9D9"
    false_color = "#D55E00"

    for x, column in enumerate(("target_hit_at_1", "target_hit_at_3")):
        values = np.asarray([int(row[column]) for row in data])
        colors = [hit_color if value else miss_color for value in values]
        ax_hit.scatter(
            np.full(len(data), x), y, c=colors, marker="s", s=230,
            edgecolors="#333333", linewidths=0.65, zorder=3,
        )
        for yi, value in enumerate(values):
            ax_hit.text(x, yi, "Hit" if value else "Miss", ha="center", va="center",
                        color="white" if value else "#333333", fontsize=7, fontweight="bold")

    rates = np.asarray([float(row["false_opportunity_rate"]) for row in data])
    ax_false.barh(y, rates, color=false_color, height=0.54, alpha=0.82)
    ax_false.scatter(rates, y, color="#7A2700", marker="o", s=20, zorder=3)
    for yi, value in enumerate(rates):
        ax_false.text(min(value + 0.035, 1.03), yi, f"{value:.2f}", va="center", fontsize=7)

    labels = [row["arm"] for row in data]
    ax_hit.set_yticks(y, labels=labels)
    ax_hit.invert_yaxis()
    ax_hit.set_xticks([0, 1], labels=["Top-1", "Top-3"])
    ax_hit.set_xlabel("Published target recovered")
    ax_hit.set_xlim(-0.55, 1.55)
    ax_false.set_xlabel("False-opportunity rate among Top-3")
    ax_false.set_xlim(0, 1.12)
    ax_false.set_xticks([0, 0.25, 0.5, 0.75, 1.0])

    for ax in axes:
        ax.axhspan(4.5, 7.5, color="#F2F2F2", zorder=0)
        ax.axhline(4.5, color="#777777", linestyle="--", linewidth=0.75)
        ax.grid(axis="y", visible=False)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    for label, ax in zip("ab", axes, strict=True):
        ax.text(-0.14, 1.03, label, transform=ax.transAxes, fontsize=9,
                fontweight="bold", va="bottom")
    return fig


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    fig = build_figure(args.data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    preview = args.out.with_name(args.out.name + "-preview.png")
    fig.savefig(preview, dpi=150, facecolor="white")
    for extension in ("pdf", "svg", "png"):
        fig.savefig(args.out.with_suffix(f".{extension}"), dpi=600, facecolor="white")
    png = args.out.with_suffix(".png")
    grayscale = args.out.with_name(args.out.name + "_grayscale").with_suffix(".png")
    with Image.open(png) as image:
        image.convert("L").convert("RGB").save(grayscale, dpi=(600, 600))
    plt.close(fig)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
