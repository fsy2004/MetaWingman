#!/usr/bin/env python3
"""Plot all frozen-seed weakest-stage scores for the two-case evaluation."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from PIL import Image


CONFIGURATIONS = (
    "Conclusion-directed acquisition",
    "Decision-aware topic control",
    "Full MetaWingman",
    "Generic fixed acquisition",
)
CASES = ("Ag-RDT", "Suicide/self-harm")
COLORS = {
    20260820: "#0072B2",
    20260821: "#E69F00",
    20260822: "#009E73",
}
MARKERS = {20260820: "o", 20260821: "s", 20260822: "^"}


def load_rows(path: Path) -> list[dict[str, object]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 24:
        raise ValueError(f"expected 24 frozen rows, found {len(rows)}")
    parsed = []
    for row in rows:
        parsed.append(
            {
                "case": row["case"],
                "configuration": row["configuration"],
                "seed": int(row["seed"]),
                "score": float(row["end_to_end_min_stage_score"]),
            }
        )
    return parsed


def draw(rows: list[dict[str, object]]) -> plt.Figure:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8,
            "axes.labelsize": 8,
            "axes.titlesize": 9,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.7), sharex=True, sharey=True)
    offsets = {20260820: -0.16, 20260821: 0.0, 20260822: 0.16}
    for panel, (axis, case) in enumerate(zip(axes, CASES, strict=True)):
        for y, configuration in enumerate(CONFIGURATIONS):
            group = [
                row
                for row in rows
                if row["case"] == case and row["configuration"] == configuration
            ]
            for row in group:
                seed = int(row["seed"])
                axis.scatter(
                    float(row["score"]),
                    y + offsets[seed],
                    color=COLORS[seed],
                    marker=MARKERS[seed],
                    s=28,
                    linewidth=0.5,
                    edgecolor="white",
                    zorder=3,
                    label=str(seed) if panel == 1 and y == 0 else None,
                )
            mean = sum(float(row["score"]) for row in group) / len(group)
            axis.scatter(mean, y, color="black", marker="D", s=18, zorder=4)
        axis.set_title(case)
        axis.set_xlim(0, 0.26)
        axis.set_xticks((0, 0.05, 0.10, 0.15, 0.20, 0.25))
        axis.set_xlabel("End-to-end minimum stage score")
        axis.grid(axis="x", color="#D9D9D9", linewidth=0.6, zorder=0)
        axis.set_axisbelow(True)
        axis.text(-0.12, 1.05, chr(ord("a") + panel), transform=axis.transAxes,
                  fontsize=9, fontweight="bold", va="bottom")
    axes[0].set_yticks(range(len(CONFIGURATIONS)), CONFIGURATIONS)
    axes[0].invert_yaxis()
    handles, labels = axes[1].get_legend_handles_labels()
    mean_handle = mpl.lines.Line2D([], [], color="black", marker="D", linestyle="None",
                                   markersize=4, label="Mean")
    fig.legend(handles + [mean_handle], labels + ["Mean"], loc="upper center",
               bbox_to_anchor=(0.68, 1.02), ncol=4, frameon=False)
    fig.subplots_adjust(left=0.30, right=0.98, bottom=0.22, top=0.80, wspace=0.15)
    return fig


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    parser.add_argument("out", type=Path, help="output basename without extension")
    args = parser.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    rows = load_rows(args.data)
    figure = draw(rows)
    for extension in ("pdf", "svg", "png"):
        figure.savefig(
            args.out.with_suffix(f".{extension}"),
            dpi=300,
            facecolor="white",
        )
    png = args.out.with_suffix(".png")
    grayscale = args.out.with_name(args.out.name + "-grayscale").with_suffix(".png")
    with Image.open(png) as image:
        image.convert("L").convert("RGB").save(grayscale, dpi=(300, 300))
    plt.close(figure)


if __name__ == "__main__":
    main()
