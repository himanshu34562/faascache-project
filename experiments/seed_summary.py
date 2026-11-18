#!/usr/bin/env python3
"""Robustness across trace seeds: each policy's cold-start overhead relative to GD.

For every policy and memory size it computes overhead / GD-overhead on each seed
separately (so seed-to-seed workload differences cancel), then the mean, min and max
across seeds, and on how many seeds the policy beats GD.

Writes to --outdir:
  ext_vs_gd-392.{pdf,png}       extension variants (+FREQ) as % of GD, min-max band across seeds
  baseline_vs_gd-392.{pdf,png}  TTL and LRU overhead as a multiple of GD's (reproduction check)
  seeds_vs_gd-392.csv           every number behind both figures (table view)
and prints a summary table.

Usage (from repo root):
  python experiments/seed_summary.py --resdir results/extension/seeds --outdir results/extension/figs
"""
import argparse
import csv
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter, NullFormatter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_baseline import INK, MUTED, STYLE, load, style_axis  # noqa: E402

# Colour follows the entity: GD/TTL/LRU/FREQ keep their baseline-figure colours. The
# variants take slots of policies that never appear in these figures (LND, HIST, SIZE)
# plus slot 8, each with its own marker and dash so identity never rests on colour alone.
EXT_STYLE = {
    "GDW_a1_b2_c1": ("#e34948", "D", "-"),    # slot 8 red
    "GDH":          ("#6250d6", "X", "-"),    # slot 7 violet (SIZE absent here)
    "GDD_t120":     ("#eda100", "v", "--"),   # slot 4 yellow (LND absent here)
    "FREQ":         (STYLE["FREQ"][0], STYLE["FREQ"][1], ":"),
}
LABEL = {"GDW_a1_b2_c1": "GD-W (b=2)", "GDH": "GD-H", "GDD_t120": "GD-D (τ=2h)", "FREQ": "FREQ (GD-W c=0)",
         "TTL": "TTL", "LRU": "LRU"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--resdir", default="results/extension/seeds")
    ap.add_argument("--outdir", default="results/extension/figs")
    ap.add_argument("--seeds", nargs="+", default=["a", "b", "c"])
    ap.add_argument("--numfuncs", type=int, default=392)
    ap.add_argument("--memmin", type=int, default=2000)
    ap.add_argument("--memmax", type=int, default=16000)
    ap.add_argument("--memstep", type=int, default=2000)
    args = ap.parse_args()

    mems = list(range(args.memmin, args.memmax + 1, args.memstep))
    per_seed = {s: load(args.resdir, args.numfuncs, s) for s in args.seeds}
    policies = list(EXT_STYLE) + ["TTL", "LRU"]

    # rel[p][mem] = [overhead_p / overhead_GD for each seed that has both]
    rel = {p: {} for p in policies}
    for p in policies:
        for m in mems:
            vals = []
            for s in args.seeds:
                r = per_seed[s].get(m, {})
                if p in r and "GD" in r and r["GD"]["overhead_h"] > 0:
                    vals.append(r[p]["overhead_h"] / r["GD"]["overhead_h"])
            rel[p][m] = vals

    os.makedirs(args.outdir, exist_ok=True)
    n = args.numfuncs
    with open(os.path.join(args.outdir, "seeds_vs_gd-{}.csv".format(n)), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["policy", "mem_gb", "n_seeds", "mean_pct_of_gd", "min_pct", "max_pct", "seeds_beating_gd"]
                   + ["seed_{}_pct".format(s) for s in args.seeds])
        for p in policies:
            for m in mems:
                v = rel[p][m]
                if not v:
                    continue
                w.writerow([p, m / 1000, len(v), "%.2f" % (100 * sum(v) / len(v)), "%.2f" % (100 * min(v)),
                            "%.2f" % (100 * max(v)), sum(x < 1 for x in v)]
                           + ["%.2f" % (100 * x) for x in v])

    # summary table
    print("overhead as % of GD: mean [min-max] (seeds beating GD / seeds)")
    print("{:14s}".format("policy") + "".join("{:>25s}".format("%dGB" % (m // 1000)) for m in mems))
    for p in policies:
        cells = []
        for m in mems:
            v = rel[p][m]
            cells.append("-" if not v else "%5.1f [%5.1f-%5.1f] %d/%d" % (
                100 * sum(v) / len(v), 100 * min(v), 100 * max(v), sum(x < 1 for x in v), len(v)))
        print("{:14s}".format(LABEL.get(p, p)) + "".join("{:>25s}".format(c) for c in cells))

    plt.rcParams.update({"font.size": 11, "text.color": INK, "axes.labelcolor": INK})

    def band(ax, p, color, marker, ls, scale=100):
        xs, mean, lo, hi = [], [], [], []
        for m in mems:
            v = rel[p][m]
            if v:
                xs.append(m / 1000)
                mean.append(scale * sum(v) / len(v))
                lo.append(scale * min(v))
                hi.append(scale * max(v))
        if not xs:
            return
        ax.fill_between(xs, lo, hi, color=color, alpha=0.15, linewidth=0)
        ax.plot(xs, mean, color=color, marker=marker, markersize=5, linewidth=2, linestyle=ls,
                label=LABEL.get(p, p))

    def finish(fig, ax, name, n_seeds):
        ax.set_xlabel("Server memory (GB)")
        style_axis(ax)
        ax.legend(frameon=False, loc="center left", bbox_to_anchor=(1.0, 0.5),
                  title="mean; band = min–max\nover {} trace seed{}".format(n_seeds, "s" if n_seeds > 1 else ""), title_fontsize=9)
        fig.tight_layout()
        base = os.path.join(args.outdir, "{}-{}".format(name, n))
        for ext in ("pdf", "png"):
            fig.savefig(base + "." + ext, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print("wrote", base + ".{pdf,png}")

    n_seeds = len(args.seeds)
    fig, ax = plt.subplots(figsize=(7, 4))
    for p in EXT_STYLE:
        c, mk, ls = EXT_STYLE[p]
        band(ax, p, c, mk, ls)
    ax.axhline(100, color=STYLE["GD"][0], linewidth=1.5, linestyle="--", label="GD (= 100%)")
    ax.set_ylabel("Cold-start overhead (% of GD)")
    ax.set_title("Extension variants vs GD (lower is better)", loc="left")
    finish(fig, ax, "ext_vs_gd", n_seeds)

    fig, ax = plt.subplots(figsize=(7, 4))
    for p in ("TTL", "LRU"):
        band(ax, p, STYLE[p][0], STYLE[p][1], "-", scale=1)
    ax.axhline(1, color=STYLE["GD"][0], linewidth=1.5, linestyle="--", label="GD (= 1×)")
    ax.set_yscale("log")
    ax.set_yticks([1, 2, 5, 10, 20])
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: "{:g}×".format(v)))
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_ylabel("Cold-start overhead (× GD, log)")
    ax.set_title("Baselines vs GD across trace seeds", loc="left")
    finish(fig, ax, "baseline_vs_gd", n_seeds)


if __name__ == "__main__":
    main()
